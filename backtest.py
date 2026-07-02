"""One-click backtests for the dashboard's Backtest Lab.

Replays every trading day x session of the chosen period through the EXACT
live Engine (current config + agent overrides), carrying one balance across
the whole run, then adds a Monte Carlo bootstrap to show the luck envelope.

    python backtest.py --assets GOLD,ES --session both --days 30

Yahoo's free tier caps 1-minute data at ~30 days back — that is the honest
limit of this backtest.

Everything runs sandboxed: live state.json / journal / dashboard data are
never touched. Results land in dashboard/backtests/<id>.json.
"""
import argparse
import json
import logging
import random
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import agent as agent_mod
import broker as broker_mod
import data_feed
import journal
from bot import Engine, day_key_for, load_cfg, session_window
from broker import PaperBroker
from news import NewsDesk

BASE = Path(__file__).resolve().parent
OUTDIR = BASE / "dashboard" / "backtests"
STATUS = OUTDIR / "status.json"
WORK = OUTDIR / "work"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    handlers=[logging.FileHandler(BASE / "logs" / "backtest.log",
                                                  encoding="utf-8")])
log = logging.getLogger("backtest")


def status(pct, msg, **kw):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps({"running": True, "pct": round(pct), "msg": msg, **kw}),
                      encoding="utf-8")


def fetch_history(ticker, days, label, base_pct, span_pct):
    """Chunked 1-minute history (Yahoo allows ~7 days per request)."""
    import yfinance as yf
    end = datetime.now(timezone.utc)
    cur = end - timedelta(days=days)
    frames, n_chunks = [], max(1, (days + 6) // 7)
    i = 0
    while cur < end:
        nxt = min(cur + timedelta(days=7), end)
        status(base_pct + span_pct * i / n_chunks, f"fetching {label} history ({i + 1}/{n_chunks})")
        try:
            df = yf.download(ticker, start=cur, end=nxt, interval="1m",
                             progress=False, auto_adjust=True)
            df = data_feed._normalize(df)
            if df is not None and not df.empty:
                frames.append(df)
        except Exception as e:
            log.warning("chunk fetch failed for %s: %s", ticker, e)
        cur = nxt
        i += 1
    if not frames:
        return None
    import pandas as pd
    full = pd.concat(frames)
    return full[~full.index.duplicated(keep="last")].sort_index()


def sandbox():
    shutil.rmtree(WORK, ignore_errors=True)
    broker_mod.STATE_FILE = WORK / "state.json"
    journal.JOURNAL = WORK / "journal"
    journal.TRADES_FILE = journal.JOURNAL / "trades.json"
    journal.LESSONS_JSON = journal.JOURNAL / "lessons.json"
    journal.LESSONS_MD = journal.JOURNAL / "lessons.md"
    journal.DATA_JS = WORK / "data.js"
    agent_mod.FEED_FILE = journal.JOURNAL / "agent_feed.json"
    agent_mod.LEARNING_FILE = journal.JOURNAL / "learning.json"
    agent_mod.SUGGESTIONS_FILE = journal.JOURNAL / "suggestions.json"
    agent_mod.OVERRIDES_FILE = WORK / "overrides.json"


def build_windows(cfg, sessions, days):
    """Chronological (open_utc, close_utc, session_name) for the period."""
    out, now = [], datetime.now(timezone.utc)
    for d in range(days, -1, -1):
        date = (now - timedelta(days=d)).date().isoformat()
        for s in sessions:
            o, c = session_window(cfg, s, date)
            if o.weekday() >= 5 or c >= now:   # weekend in session tz / not finished yet
                continue
            out.append((o, c, s))
    out.sort(key=lambda w: w[0])
    return out


def monte_carlo(trades, starting, paths=1000):
    rets = [t["pnl"] / (t["balance_after"] - t["pnl"]) for t in trades
            if (t["balance_after"] - t["pnl"]) > 0]
    if not rets:
        return None
    n = len(rets)
    eq_matrix = []   # paths x (n+1)
    finals, max_dds = [], []
    rng = random.Random(42)
    for _ in range(paths):
        bal, eq, peak, dd = starting, [starting], starting, 0.0
        for _ in range(n):
            bal *= (1 + rng.choice(rets))
            eq.append(bal)
            peak = max(peak, bal)
            dd = max(dd, (peak - bal) / peak)
        eq_matrix.append(eq)
        finals.append(bal)
        max_dds.append(dd)
    bands = {}
    for p in (5, 25, 50, 75, 95):
        idx = max(0, min(paths - 1, int(paths * p / 100)))
        bands[f"p{p}"] = [round(sorted(col)[idx], 2) for col in zip(*eq_matrix)]
    finals_sorted = sorted(finals)
    dds_sorted = sorted(max_dds)
    lo, hi = min(finals), max(finals)
    nbins = 24
    width = (hi - lo) / nbins or 1
    counts = [0] * nbins
    for f in finals:
        counts[min(nbins - 1, int((f - lo) / width))] += 1
    return {
        "bands": bands,
        "finals_hist": {"lo": round(lo, 2), "hi": round(hi, 2), "counts": counts},
        "stats": {
            "median_final": round(finals_sorted[len(finals) // 2], 2),
            "p5_final": round(finals_sorted[int(len(finals) * 0.05)], 2),
            "p95_final": round(finals_sorted[int(len(finals) * 0.95)], 2),
            "median_max_dd_pct": round(100 * dds_sorted[len(dds_sorted) // 2], 2),
            "p95_max_dd_pct": round(100 * dds_sorted[int(len(dds_sorted) * 0.95)], 2),
            "prob_profit_pct": round(100 * sum(1 for f in finals if f > starting) / len(finals), 1),
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", required=True, help="comma list of backtest_assets keys")
    ap.add_argument("--session", default="both", choices=["asia", "newyork", "both"])
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()

    try:
        run(args)
    except Exception as e:
        log.exception("backtest failed")
        STATUS.write_text(json.dumps({"running": False, "pct": 100, "error": True,
                                      "msg": f"backtest failed: {e}"}), encoding="utf-8")
        raise SystemExit(1)


def run(args):
    cfg = load_cfg()
    days = max(2, min(args.days, 29))
    asset_keys = [a.strip().upper() for a in args.assets.split(",") if a.strip()]
    catalog = cfg["backtest_assets"]
    asset_keys = [a for a in asset_keys if a in catalog]
    if not asset_keys:
        raise ValueError("no valid assets selected")
    sessions = ["asia", "newyork"] if args.session == "both" else [args.session]

    # rebuild the asset/session map so the Engine trades exactly what was chosen
    cfg["assets"] = {k: {"name": catalog[k]["name"], "yahoo": catalog[k]["yahoo"],
                         "tv_rating": None, "tv_widget_symbol": ""}
                     for k in asset_keys}
    for s in sessions:
        cfg["sessions"][s]["assets"] = asset_keys

    sandbox()
    status(1, "fetching price history...")
    all_bars = {}
    for i, k in enumerate(asset_keys):
        bars = fetch_history(catalog[k]["yahoo"], days + 4, catalog[k]["name"],
                             2 + 28 * i / len(asset_keys), 28 / len(asset_keys))
        if bars is not None:
            all_bars[k] = bars
    if not all_bars:
        raise ValueError("no historical data could be fetched")

    newsdesk = NewsDesk(cfg)
    try:
        newsdesk.refresh_calendar()
    except Exception:
        pass
    broker = PaperBroker(cfg)
    starting = broker.state["balance"]
    windows = build_windows(cfg, sessions, days)
    if not windows:
        raise ValueError("no completed sessions in the chosen period")

    all_trades = []
    for i, (open_utc, close_utc, sname) in enumerate(windows):
        status(30 + 62 * i / len(windows),
               f"replaying {sname} session of {open_utc.date()} "
               f"({i + 1}/{len(windows)})...")
        sliced = {}
        for a, b in all_bars.items():
            sl = b[(b.index >= open_utc - timedelta(days=4)) & (b.index <= close_utc)]
            if not sl[sl.index >= open_utc].empty:
                sliced[a] = sl
        if not sliced:
            continue
        broker.start_session(sname, day_key_for(cfg, open_utc))
        engine = Engine(cfg, broker, newsdesk, sname, open_utc, close_utc,
                        replay=True, agent=None)
        sim = open_utc + timedelta(minutes=1)
        while sim <= close_utc:
            cutoff = sim - timedelta(seconds=60)
            engine.step(sim, {a: b[b.index <= cutoff] for a, b in sliced.items()})
            sim += timedelta(minutes=1)
        engine.end_session(close_utc)
        all_trades.extend(engine.session_trades)

    status(93, "computing metrics and Monte Carlo...")
    stats = journal.compute_stats(all_trades, broker.state["equity_curve"], starting)
    daily = {}
    for t in all_trades:
        daily[t["day_key"]] = round(daily.get(t["day_key"], 0) + t["pnl"], 2)
    mc = monte_carlo(all_trades, starting) if len(all_trades) >= 5 else None

    bt_id = "bt_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    result = {
        "id": bt_id,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "params": {"assets": asset_keys, "session": args.session, "days": days,
                   "strategy": cfg["strategy"], "overrides": agent_mod._load(
                       BASE / "config_overrides.json", {})},
        "starting_balance": starting,
        "final_balance": broker.state["balance"],
        "stats": stats,
        "daily_pnl": daily,
        "best_day": max(daily.values()) if daily else 0,
        "worst_day": min(daily.values()) if daily else 0,
        "sessions_tested": len(windows),
        "equity_curve": broker.state["equity_curve"],
        "r_values": [t["r_multiple"] for t in all_trades][:1000],
        "trades": [{k: t[k] for k in ("trade_id", "day_key", "session", "asset",
                                      "direction", "entry_price", "exit_price",
                                      "exit_reason", "pnl", "r_multiple")}
                   for t in all_trades][:400],
        "mc": mc,
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / f"{bt_id}.json").write_text(json.dumps(result, default=str),
                                          encoding="utf-8")
    index_file = OUTDIR / "index.json"
    index = json.loads(index_file.read_text(encoding="utf-8")) if index_file.exists() else []
    index.insert(0, {"id": bt_id, "created": result["created"],
                     "assets": asset_keys, "session": args.session, "days": days,
                     "trades": len(all_trades),
                     "total_pnl": stats["total_pnl"]})
    index_file.write_text(json.dumps(index[:25], indent=1), encoding="utf-8")
    STATUS.write_text(json.dumps({"running": False, "pct": 100, "msg": "done",
                                  "result": bt_id}), encoding="utf-8")
    log.info("backtest %s complete: %d trades, P&L %+.2f",
             bt_id, len(all_trades), stats["total_pnl"])
    print(f"{bt_id}: {len(all_trades)} trades, P&L {stats['total_pnl']:+.2f}")


if __name__ == "__main__":
    main()

"""Trade journal: per-trade archives, auto-reflections, lessons, dashboard data.

Data stores (machine-readable):
    journal/trades.json   — every closed trade
    journal/lessons.json  — every lesson learned
    state.json            — live account state (owned by broker.py)

Human-readable output generated from those:
    journal/YYYY-MM-DD/trade-NN-ASSET.md  — pretty per-trade archive
    journal/lessons.md                    — running lessons log
    dashboard/data.js                     — feeds dashboard.html
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

log = logging.getLogger("journal")

BASE = Path(__file__).resolve().parent
JOURNAL = BASE / "journal"
TRADES_FILE = JOURNAL / "trades.json"
LESSONS_JSON = JOURNAL / "lessons.json"
LESSONS_MD = JOURNAL / "lessons.md"
DATA_JS = BASE / "dashboard" / "data.js"
HEARTBEAT_FILE = JOURNAL / "heartbeat.json"


def _atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def _load(path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


# --------------------------------------------------------------------------
# Heartbeat: written every live-loop iteration so ops/watchdog.py can tell a hung
# process (no exception, just stuck — see data_feed/yahoo.py's docstring for the
# failure mode this responds to) apart from one that's simply between sessions.
# --------------------------------------------------------------------------
def write_heartbeat(session_name, pid=None):
    _atomic_write(HEARTBEAT_FILE, json.dumps({
        "session": session_name,
        "pid": pid or os.getpid(),
        "t": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }))


# --------------------------------------------------------------------------
# Auto-reflection: turns the trade's hard data into an honest self-review.
# --------------------------------------------------------------------------
def build_reflection(trade):
    ctx = trade.get("context", {})
    ratio = ctx.get("range_atr_ratio")
    tv = ctx.get("tv_rating", "UNAVAILABLE")
    dur = trade.get("duration_min", 0)
    mfe, mae = trade.get("mfe", 0), trade.get("mae", 0)
    reason = trade["exit_reason"]
    r = trade["r_multiple"]

    side = "above" if trade["direction"] == "LONG" else "below"
    thinking = (
        f"Mechanical ORB entry: a 1-minute candle closed {side} the opening range "
        f"({ctx.get('range_low')}–{ctx.get('range_high')}, {ratio}x ATR), which by the "
        f"rules signals a {trade['direction']} with the stop at the far side of the "
        f"range and a 2R target. TradingView 15-min rating at entry: {tv}."
    )

    went_well, improve = [], []
    went_well.append("Followed the system exactly — entry, stop, size and target were all rule-based.")
    if reason == "target":
        went_well.append(f"Full {r:+.2f}R winner; the breakout had follow-through.")
        if mae >= 0.7:
            improve.append(f"Price moved {mae:.2f}R against entry before working — "
                           "entries may be slightly early; a retest-entry variant is worth tracking.")
        else:
            improve.append("Little to fault — a textbook trade for this system.")
    elif reason == "stop":
        if dur <= 10:
            improve.append(f"Stopped out in {dur} min — a fast fakeout. If these cluster, "
                           "consider requiring a second confirming close beyond the range.")
        if mfe >= 1.0:
            improve.append(f"Price reached {mfe:.2f}R in our favour before reversing to the stop — "
                           "data point in favour of a break-even stop after +1R.")
        if not improve:
            improve.append("A normal, controlled 1R loss — these are the cost of doing business; "
                           "the edge needs the winners to outpace them.")
        went_well.append(f"Loss contained to plan: {r:+.2f}R, exactly the risk budgeted.")
    elif reason == "time":
        if trade["pnl"] >= 0:
            went_well.append("Session-end exit banked a partial winner rather than gambling overnight.")
        else:
            improve.append("Faded into the session close without hitting stop or target — "
                           "late-session entries have less time to reach 2R; entry cut-off time is worth studying.")
    elif reason == "news_flatten":
        went_well.append(f"Flattened ahead of top-tier news ({ctx.get('flatten_event', 'event')}) — "
                         "protecting the account from a coin-flip spike.")
    if tv in ("SELL", "STRONG_SELL") and trade["direction"] == "LONG":
        improve.append("Note: TradingView rating disagreed at entry (filter was off or overridden).")

    return {"thinking": thinking, "went_well": went_well, "improve": improve}


# --------------------------------------------------------------------------
def record_trade(trade, cfg):
    trade["duration_min"] = _duration_min(trade)
    trade["reflection"] = build_reflection(trade)

    trades = _load(TRADES_FILE, [])
    trades.append(trade)
    _atomic_write(TRADES_FILE, json.dumps(trades, indent=2, default=str))

    _write_trade_md(trade, cfg)

    outcome = "WIN" if trade["pnl"] > 0 else ("LOSS" if trade["pnl"] < 0 else "FLAT")
    lesson_bits = trade["reflection"]["improve"][:1] or trade["reflection"]["went_well"][:1]
    add_lesson(f"[{trade['day_key']} {trade['session']} {trade['asset']} {outcome} "
               f"{trade['r_multiple']:+.2f}R] {lesson_bits[0]}")
    return trade


def _duration_min(trade):
    try:
        a = datetime.fromisoformat(str(trade["entry_time"]))
        b = datetime.fromisoformat(str(trade["exit_time"]))
        return int((b - a).total_seconds() // 60)
    except Exception:
        return 0


def _write_trade_md(t, cfg):
    ctx = t.get("context", {})
    ref = t["reflection"]
    outcome = "🟢 WIN" if t["pnl"] > 0 else ("🔴 LOSS" if t["pnl"] < 0 else "⚪ FLAT")
    name = cfg["assets"][t["asset"]]["name"]
    headlines = ctx.get("headlines") or []
    md = f"""# Trade #{t['trade_id']} — {name} — {outcome}

| | |
|---|---|
| **Date / Session** | {t['day_key']} — {t['session']} |
| **Direction** | {t['direction']} |
| **Entry** | {t['entry_price']} at {t['entry_time']} UTC |
| **Exit** | {t['exit_price']} at {t['exit_time']} UTC ({t['exit_reason']}) |
| **Size** | {t['units']} units (risking ${t['risk_usd']}) |
| **Stop / Target** | {t['stop']} / {t['target']} |
| **Result** | **{t['pnl']:+.2f} USD ({t['r_multiple']:+.2f}R)** |
| **Balance after** | ${t['balance_after']:,.2f} |
| **Duration** | {t['duration_min']} min |
| **Best / worst point** | +{t.get('mfe', 0):.2f}R / -{t.get('mae', 0):.2f}R |
| **Opening range** | {ctx.get('range_low')} – {ctx.get('range_high')} ({ctx.get('range_atr_ratio')}x ATR) |
| **TradingView 15m at entry** | {ctx.get('tv_rating', 'UNAVAILABLE')} |

## 🧠 My thinking
{ref['thinking']}

## ✅ What went well
""" + "\n".join(f"- {x}" for x in ref["went_well"]) + """

## 🔧 What needs improvement
""" + "\n".join(f"- {x}" for x in ref["improve"])
    if headlines:
        md += "\n\n## 📰 Market headlines at entry\n" + "\n".join(f"- {h}" for h in headlines)
    md += "\n"
    day_dir = JOURNAL / str(t["day_key"])
    _atomic_write(day_dir / f"trade-{t['trade_id']:02d}-{t['asset']}.md", md)


# --------------------------------------------------------------------------
def add_lesson(text):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lessons = _load(LESSONS_JSON, [])
    lessons.append({"t": now, "text": text})
    _atomic_write(LESSONS_JSON, json.dumps(lessons, indent=2))
    md = "# Lessons Learned\n\n" + "\n".join(
        f"- `{x['t']}` {x['text']}" for x in lessons) + "\n"
    _atomic_write(LESSONS_MD, md)


def write_session_review(session_name, day_key, session_trades, engine_snapshots, broker_state, cfg):
    wins = [t for t in session_trades if t["pnl"] > 0]
    losses = [t for t in session_trades if t["pnl"] < 0]
    pnl = sum(t["pnl"] for t in session_trades)
    lines = [f"# Session review — {day_key} — {cfg['sessions'][session_name]['label']}", ""]
    lines.append(f"**Trades:** {len(session_trades)}  |  **Wins:** {len(wins)}  |  "
                 f"**Losses:** {len(losses)}  |  **P&L:** {pnl:+.2f} USD")
    lines.append(f"**Balance:** ${broker_state['balance']:,.2f}")
    if broker_state.get("halted_reason"):
        lines.append(f"\n⚠️ {broker_state['halted_reason']}")
    lines.append("\n## Asset notes")
    for asset, snap in engine_snapshots.items():
        note = snap.get("filter_reason") or f"stage at close: {snap.get('stage')}"
        lines.append(f"- **{asset}**: {note}")
    if session_trades:
        avg_r = sum(t["r_multiple"] for t in session_trades) / len(session_trades)
        lines.append(f"\nAverage R this session: {avg_r:+.2f}")
        add_lesson(f"[{day_key} {session_name} review] {len(session_trades)} trades, "
                   f"{pnl:+.2f} USD, avg {avg_r:+.2f}R.")
    else:
        add_lesson(f"[{day_key} {session_name} review] No trades — "
                   "filters/caps kept the system flat. Patience is a position.")
    _atomic_write(JOURNAL / str(day_key) / f"session-review-{session_name}.md",
                  "\n".join(lines) + "\n")


# --------------------------------------------------------------------------
# Dashboard data export
# --------------------------------------------------------------------------
def compute_stats(trades, equity_curve, starting_balance):
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] < 0]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = -sum(t["pnl"] for t in losses)
    peak, max_dd = starting_balance, 0.0
    for p in equity_curve:
        peak = max(peak, p["balance"])
        max_dd = max(max_dd, peak - p["balance"])
    per_asset = {}
    for t in trades:
        a = per_asset.setdefault(t["asset"], {"trades": 0, "wins": 0, "pnl": 0.0})
        a["trades"] += 1
        a["wins"] += 1 if t["pnl"] > 0 else 0
        a["pnl"] = round(a["pnl"] + t["pnl"], 2)
    return {
        "total_trades": len(trades),
        "wins": len(wins), "losses": len(losses),
        "win_rate": round(100 * len(wins) / len(trades), 1) if trades else None,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else None,
        "avg_win": round(gross_win / len(wins), 2) if wins else None,
        "avg_loss": round(-gross_loss / len(losses), 2) if losses else None,
        "avg_r": round(sum(t["r_multiple"] for t in trades) / len(trades), 2) if trades else None,
        "total_pnl": round(sum(t["pnl"] for t in trades), 2),
        "max_drawdown": round(max_dd, 2),
        "per_asset": per_asset,
    }


def _derive_bot_state(bot_status):
    """Coarse lifecycle hint for the dashboard: LIVE / ASLEEP / HOLIDAY / OFF.

    Derived from the status text the bot exports each loop. The dashboard
    combines this with data.js freshness to decide when to show the wake button.
    'dormant' is matched too so Stage-2 dormant mode maps here automatically.
    HOLIDAY marks a deliberate bank-holiday stand-down (no wake button) so it is
    not mistaken for a recoverable data dropout.
    """
    s = (bot_status or "").lower()
    # The deliberate holiday stand-down status starts with "holiday —". Match the
    # prefix (not a bare "holiday" substring) so the data-dropout message
    # "standing down — no market data (holiday/closure?)" still reads as ASLEEP.
    if s.startswith("holiday"):
        return "HOLIDAY"
    if "standing down" in s or "dormant" in s or "asleep" in s:
        return "ASLEEP"
    if "complete" in s or "emergency stop" in s or "aborted" in s:
        return "OFF"
    return "LIVE"


def export_dashboard(cfg, broker_state, bot_status, engine_snapshots, newsdesk, now_utc,
                     agent=None, holiday_until=None):
    trades = _load(TRADES_FILE, [])
    lessons = _load(LESSONS_JSON, [])
    starting = cfg["account"]["starting_balance"]
    stats = compute_stats(trades, broker_state["equity_curve"], starting)
    syd = now_utc.astimezone(ZoneInfo(cfg["home_tz"]))
    day_pnl = (round(broker_state["balance"] - broker_state["day_start_balance"], 2)
               if broker_state.get("day_start_balance") is not None else 0.0)
    events = []
    if newsdesk is not None:
        events = [{"title": e["title"], "impact": e["impact"], "top_tier": e["top_tier"],
                   "when": e["when"].isoformat()} for e in newsdesk.upcoming(now_utc, 48)]
    data = {
        "generated_utc": now_utc.isoformat(timespec="seconds"),
        "generated_local": syd.strftime("%Y-%m-%d %H:%M:%S Sydney"),
        "bot_status": bot_status,
        "bot_state": _derive_bot_state(bot_status),
        # When the bot stands down for a bank holiday this is the skipped session's
        # scheduled close (ISO UTC); the dashboard shows the holiday badge only until
        # then, so a past holiday doesn't pin the UI. None on every normal export.
        "holiday_until": holiday_until,
        "balance": broker_state["balance"],
        "starting_balance": starting,
        "day_pnl": day_pnl,
        "session": broker_state.get("session_name"),
        "trades_this_session": broker_state.get("trades_this_session", 0),
        "trades_today": broker_state.get("trades_today", 0),
        "caps": {"per_session": cfg["risk"]["max_trades_per_session"],
                 "per_day": cfg["risk"]["max_trades_per_day"]},
        "halted_reason": broker_state.get("halted_reason"),
        "benched": broker_state.get("benched_until", {}),
        "open_positions": broker_state.get("open_positions", {}),
        "assets_stage": engine_snapshots,
        "equity_curve": broker_state["equity_curve"],
        "stats": stats,
        "trades": trades,
        "events": events,
        "headlines": (newsdesk.headlines if newsdesk else []),
        "lessons": lessons[-10:][::-1],
        "risk_config": cfg["risk"],
        "tv_widgets": {k: v["tv_widget_symbol"] for k, v in cfg["assets"].items()},
        "agent": agent.dashboard_payload() if agent else None,
        "schedule": {k: {"label": v["label"], "open_tz": v["open_tz"],
                         "open_time": v["open_time"],
                         "duration_minutes": v["duration_minutes"]}
                     for k, v in cfg["sessions"].items()},
        "effective_strategy": cfg["strategy"],
        "backtest_assets": {k: {"name": v["name"], "sector": v["sector"]}
                            for k, v in cfg.get("backtest_assets", {}).items()},
    }
    _atomic_write(DATA_JS, "window.DATA = " + json.dumps(data, indent=1, default=str) + ";\n")

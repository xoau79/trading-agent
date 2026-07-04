"""Trading bot entry point.

Live (started by Task Scheduler ~30 min before each session):
    python bot.py --session asia
    python bot.py --session newyork

Replay a past session through the exact same engine (for testing):
    python bot.py --session newyork --backtest 2026-06-11
"""
import argparse
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import agent as agent_mod
import data_feed
import journal
from agent import TradingAgent
from broker import paper as broker_mod
from broker.paper import PaperBroker
from news import NewsDesk, get_tv_rating, tv_allows
from strategy import AssetStrategy

# NOTE: the trading Engine below is still written directly against PaperBroker's specific
# state-dict interface (self.broker.state[...], can_open(), etc.), not broker/base.py's
# BrokerBase methods. broker.create_broker(cfg) exists and correctly builds an MT5Broker or
# IBKRBroker from config.json's "broker.provider", but plugging one of those into this Engine
# is separate follow-up work -- flipping the provider switch today would not (yet) change
# what the live loop does. See docs/ARCHITECTURE.md.

BASE = Path(__file__).resolve().parent
LOOP_SECONDS = 45
MAX_CONSECUTIVE_ERRORS = 10

log = logging.getLogger("bot")


def load_cfg():
    """Base config + the agent's bounded overrides (whitelist enforced here too,
    so a corrupted overrides file can never widen risk)."""
    cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    ov_file = BASE / "config_overrides.json"
    if not ov_file.exists():
        return cfg
    try:
        overrides = json.loads(ov_file.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("config_overrides.json unreadable (%s) — ignored", e)
        return cfg
    wl = cfg.get("tuning", {}).get("whitelist", {})
    for param, value in overrides.items():
        lim = wl.get(param)
        if lim is None or ("bool" not in lim and
                           not (lim["min"] <= value <= lim["max"])):
            log.warning("override %s=%s refused (not whitelisted / out of bounds)",
                        param, value)
            continue
        node = cfg
        *parts, leaf = param.split(".")
        for p in parts:
            node = node[p]
        node[leaf] = value
        log.info("override active: %s = %s", param, value)
    return cfg


def utcnow():
    return datetime.now(timezone.utc)


def session_window(cfg, session_name, date_str=None):
    """(open_utc, close_utc) for the session on the given date (default: today
    in the session's own timezone — DST-proof)."""
    scfg = cfg["sessions"][session_name]
    tz = ZoneInfo(scfg["open_tz"])
    hh, mm = map(int, scfg["open_time"].split(":"))
    if date_str:
        y, mo, d = map(int, date_str.split("-"))
        open_local = datetime(y, mo, d, hh, mm, tzinfo=tz)
    else:
        now_local = datetime.now(tz)
        open_local = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    open_utc = open_local.astimezone(timezone.utc)
    return open_utc, open_utc + timedelta(minutes=scfg["duration_minutes"])


def day_key_for(cfg, open_utc):
    return open_utc.astimezone(ZoneInfo(cfg["home_tz"])).date().isoformat()


# ---------------------------------------------------------------------------
class Engine:
    """One trading session. step() is called once per minute (live or replay)."""

    def __init__(self, cfg, broker, newsdesk, session_name, open_utc, close_utc,
                 replay=False, agent=None):
        self.cfg = cfg
        self.broker = broker
        self.news = newsdesk
        self.agent = agent
        self.session_name = session_name
        self.open_utc = open_utc
        self.close_utc = close_utc
        self.replay = replay
        self.assets = cfg["sessions"][session_name]["assets"]
        self.strats = {a: AssetStrategy(a, cfg) for a in self.assets}
        self.atr = {}
        self.last_bar_done = {a: open_utc for a in self.assets}
        self.last_price = {}
        self.session_trades = []
        self.status = "session starting"
        self._halt_announced = False
        self._bench_announced = set()
        self._skip_noted = set()
        self._last_bars = {}

    def candles(self, limit=240):
        """Latest per-asset 1-min OHLC as JSON-safe lists for the dashboard chart.

        [{t: epoch_sec, o, h, l, c}, ...] — capped so data.js stays small."""
        out = {}
        for asset, bars in self._last_bars.items():
            if bars is None or bars.empty:
                continue
            tail = bars.tail(limit)
            out[asset] = [
                {"t": int(ts.timestamp()),
                 "o": round(float(b["Open"]), 4), "h": round(float(b["High"]), 4),
                 "l": round(float(b["Low"]), 4), "c": round(float(b["Close"]), 4)}
                for ts, b in tail.iterrows()]
        return out

    def snapshots(self):
        snaps = {a: s.snapshot() for a, s in self.strats.items()}
        if self.agent:
            for a in snaps:
                snaps[a]["bias"] = self.agent.assessments.get(a)
        return snaps

    def step(self, now_utc, bars_by_asset):
        flatten_event = self.news.must_flatten(now_utc) if self.news else None
        blackout = self.news.in_blackout(now_utc) if self.news else None
        self._last_bars = bars_by_asset

        for asset in self.assets:
            bars = bars_by_asset.get(asset)
            if bars is None or bars.empty:
                continue
            session_bars = bars[bars.index >= self.open_utc]
            self.last_price[asset] = float(bars["Close"].iloc[-1])
            if self.agent:
                self.agent.assess(asset, bars, now=now_utc)

            if asset not in self.atr:
                pre = bars[bars.index < self.open_utc]
                self.atr[asset] = data_feed.atr_15m(pre, self.cfg["strategy"]["atr_period"])

            # manage the open position bar-by-bar (stops/targets, excursions)
            new_bars = session_bars[session_bars.index > self.last_bar_done[asset]]
            for ts, bar in new_bars.iterrows():
                if asset in self.broker.state["open_positions"]:
                    px, why = self.broker.update_position(asset, bar)
                    if px is not None:
                        self._close(asset, px, why, ts + timedelta(minutes=1))
                self.last_bar_done[asset] = ts

            # forced exits: top-tier news or daily loss halt
            if asset in self.broker.state["open_positions"]:
                if flatten_event:
                    pos = self.broker.state["open_positions"][asset]
                    pos["context"]["flatten_event"] = flatten_event
                    self._close(asset, self.last_price[asset], "news_flatten", now_utc)
                elif self.broker.state["halted_reason"]:
                    self._close(asset, self.last_price[asset], "daily_stop_flatten", now_utc)

            # narrated trade management while in a position
            pos = self.broker.state["open_positions"].get(asset)
            if pos and self.agent:
                risk = abs(pos["entry_price"] - pos["stop"])
                d = 1 if pos["direction"] == "LONG" else -1
                if risk > 0:
                    cur_r = (self.last_price[asset] - pos["entry_price"]) * d / risk
                    self.agent.on_manage(asset, pos, cur_r, self.last_price[asset],
                                         now=now_utc)

            # hunt for a new entry
            in_pos = asset in self.broker.state["open_positions"]
            strat = self.strats[asset]
            pre_stage = strat.stage
            signal = strat.on_bars(session_bars, self.open_utc,
                                   self.atr.get(asset), in_pos)
            if self.agent and pre_stage == "building_range" and strat.stage != pre_stage:
                if strat.stage == "hunting":
                    self.agent.on_range_set(asset, strat.range_low, strat.range_high,
                                            strat.range_atr_ratio, now=now_utc)
                elif strat.stage == "filtered":
                    self.agent.on_filtered(asset, strat.filter_reason, now=now_utc)
            if signal:
                self._try_open(asset, signal, now_utc, blackout)

        if self.agent and self.broker.state["halted_reason"] and not self._halt_announced:
            self._halt_announced = True
            self.agent.on_halt(self.broker.state["halted_reason"], now=now_utc)

        self.status = self._status_line(blackout)
        return self.status

    def _try_open(self, asset, signal, now_utc, blackout):
        cutoff = self.cfg["strategy"].get("entry_cutoff_minutes", 0)
        if cutoff and now_utc >= self.close_utc - timedelta(minutes=cutoff):
            left = int((self.close_utc - now_utc).total_seconds() // 60)
            log.info("signal on %s skipped: entry cutoff (%d min left)", asset, left)
            if self.agent and ("cutoff", asset) not in self._skip_noted:
                self._skip_noted.add(("cutoff", asset))
                self.agent.on_skipped(asset, signal["direction"],
                                      f"only {left} min left in the session — too little "
                                      f"time for a 2R run (my cutoff is {cutoff} min).",
                                      now=now_utc)
            return
        ok, why = self.broker.can_open(asset)
        if not ok:
            log.info("signal on %s skipped: %s", asset, why)
            if (self.agent and "halted" not in why.lower()
                    and ("skip", asset) not in self._skip_noted):
                self._skip_noted.add(("skip", asset))
                self.agent.on_skipped(asset, signal["direction"], why + ".", now=now_utc)
            return
        if blackout:
            log.info("signal on %s skipped: news blackout (%s)", asset, blackout)
            journal.add_lesson(f"[{self.broker.state['day_key']} {self.session_name}] "
                               f"Skipped a {asset} breakout inside the news blackout for "
                               f"'{blackout}' — rule held, volatility risk avoided.")
            if self.agent:
                self.agent.on_skipped(asset, signal["direction"],
                                      f"we're inside the ±15 min news blackout around "
                                      f"'{blackout}' — breakouts during data releases are "
                                      "coin-flips with slippage.", now=now_utc)
            return
        rating = "BACKTEST" if self.replay else get_tv_rating(self.cfg["assets"][asset])
        if self.cfg["strategy"]["tv_confluence_enabled"] and not tv_allows(signal["direction"], rating):
            log.info("signal on %s skipped: TradingView rating %s against %s",
                     asset, rating, signal["direction"])
            journal.add_lesson(f"[{self.broker.state['day_key']} {self.session_name}] "
                               f"Skipped {asset} {signal['direction']} — TradingView 15m "
                               f"rating was {rating} against the trade.")
            if self.agent:
                self.agent.on_skipped(asset, signal["direction"],
                                      f"TradingView's 15-min consensus reads {rating} — "
                                      "I don't fight a stacked technical read.", now=now_utc)
            return
        strat = self.strats[asset]
        sim_time = signal["bar_time"] + timedelta(minutes=1) if self.replay else now_utc
        context = {
            "range_low": strat.range_low, "range_high": strat.range_high,
            "range_atr_ratio": strat.range_atr_ratio,
            "tv_rating": rating,
            "headlines": self.news.top_headlines() if self.news else [],
            "min_into_session": int((sim_time - self.open_utc).total_seconds() // 60),
        }
        pos = self.broker.open_position(asset, signal, sim_time, context)
        if pos and self.agent:
            self.agent.on_entry(pos, strat.range_atr_ratio, now=sim_time)

    def _close(self, asset, price, reason, when_utc):
        trade = self.broker.close_position(asset, price, reason, when_utc)
        if trade:
            journal.record_trade(trade, self.cfg)
            self.session_trades.append(trade)
            if self.agent:
                self.agent.on_exit(trade, now=when_utc)
                self.agent.learn_from_trade(
                    trade, trade["context"].get("min_into_session", 0))
                benched = self.broker.state["benched_until"].get(asset)
                if benched == self.broker.state["day_key"] and asset not in self._bench_announced:
                    self._bench_announced.add(asset)
                    streak = self.broker.state["consecutive_losses"].get(asset, 0)
                    self.agent.on_bench(asset, streak, now=when_utc)

    def end_session(self, now_utc):
        closed = self.broker.flatten_all(self.last_price, "time", now_utc)
        for t in closed:
            journal.record_trade(t, self.cfg)
            self.session_trades.append(t)
        journal.write_session_review(self.session_name, self.broker.state["day_key"],
                                     self.session_trades, self.snapshots(),
                                     self.broker.state, self.cfg)

    def _status_line(self, blackout):
        if self.broker.state["halted_reason"]:
            return f"HALTED — {self.broker.state['halted_reason']}"
        bits = []
        for a, s in self.strats.items():
            if a in self.broker.state["open_positions"]:
                bits.append(f"{a}: managing position")
            elif s.stage == "building_range":
                bits.append(f"{a}: building opening range")
            elif s.stage == "hunting":
                bits.append(f"{a}: hunting breakout")
            elif s.stage == "filtered":
                bits.append(f"{a}: standing aside (filter)")
        line = "; ".join(bits) or "idle"
        if blackout:
            line = f"NEWS BLACKOUT ({blackout}) — " + line
        return line


# ---------------------------------------------------------------------------
def export(cfg, broker, status, snapshots, newsdesk, now_utc, replay=False, agent=None,
           holiday_until=None, candles=None):
    tag = "REPLAY — " if replay else ""
    try:
        journal.export_dashboard(cfg, broker.state, tag + status, snapshots,
                                 newsdesk, now_utc, agent=agent,
                                 holiday_until=holiday_until, candles=candles)
    except Exception as e:
        log.warning("dashboard export failed: %s", e)


def recover_stale_positions(cfg, broker, agent=None):
    """Crash recovery: the strategy rule is 'flat by session close, no exceptions,' so any
    open position still sitting in state.json when a new bot.py process starts can only mean
    the previous run died without reaching end_session() (a hang, a crash, a killed process —
    see the 2026-07-02 postmortem in docs/ARCHITECTURE.md). Flatten immediately, before doing
    anything else, using a fresh price.
    """
    positions = broker.state.get("open_positions") or {}
    if not positions:
        return
    log.warning("recovering %d stale open position(s) from a previous run: %s",
                len(positions), list(positions.keys()))
    now = utcnow()
    prices = {}
    for asset in positions:
        bars = data_feed.get_recent_bars(cfg["assets"][asset]["yahoo"], now_utc=now,
                                         twelvedata_symbol=cfg["assets"][asset].get("twelvedata"))
        if bars is not None and not bars.empty:
            prices[asset] = float(bars["Close"].iloc[-1])
        else:
            log.error("could not price %s for crash recovery — will retry next start", asset)
    closed = broker.flatten_all(prices, "crash_recovery", now)
    for t in closed:
        journal.record_trade(t, cfg)
    still_open = broker.state.get("open_positions") or {}
    if agent and closed:
        names = ", ".join(f"{t['asset']} {t['pnl']:+.2f} USD" for t in closed)
        note = "" if not still_open else (
            f" ({len(still_open)} more couldn't be priced yet and remain open — "
            "will retry on next start.)")
        agent.say("halt", f"Startup crash-recovery: found {len(closed)} position(s) left open "
                  f"by a run that didn't shut down cleanly ({names}). Flattened at current "
                  f"market price before doing anything else.{note}", discord=True, now=now)


def run_live(session_name):
    cfg = load_cfg()
    open_utc, close_utc = session_window(cfg, session_name)
    now = utcnow()
    if now > close_utc:
        log.info("session %s already over for today — exiting", session_name)
        return
    # weekends: futures are closed Saturday and most of Sunday (Sydney time)
    day_key = day_key_for(cfg, open_utc)
    newsdesk = NewsDesk(cfg)
    newsdesk.refresh_calendar()
    newsdesk.refresh_headlines()
    agent = TradingAgent(cfg)
    if agent.apply_approved_suggestions():
        cfg = load_cfg()          # pick up the freshly applied overrides
        agent.cfg = cfg
        agent.tuning = cfg.get("tuning", {})
    broker = PaperBroker(cfg)
    recover_stale_positions(cfg, broker, agent=agent)
    broker.start_session(session_name, day_key)
    engine = Engine(cfg, broker, newsdesk, session_name, open_utc, close_utc,
                    agent=agent)
    top_events = [e for e in newsdesk.upcoming(utcnow(), 24)
                  if e["impact"] == "High" and e["country"] == "USD"
                  and e["when"] <= close_utc]
    agent.on_session_start(cfg["sessions"][session_name]["label"], engine.assets,
                           broker.state["balance"], top_events)

    # Bank-holiday stand-down: even when prices still tick (e.g. gold on a JP/AU
    # holiday), don't trade thin holiday conditions. Skip the whole session cleanly.
    holiday = newsdesk.holiday_for_session(cfg["sessions"][session_name], open_utc)
    if holiday:
        agent.say("info", f"{holiday}: the markets I trade this session are closed. "
                  "Standing down for the day — no trades.", discord=True)
        export(cfg, broker, f"holiday — {holiday}, market closed (no trading)",
               engine.snapshots(), newsdesk, utcnow(), agent=agent,
               holiday_until=close_utc.isoformat())
        log.info("=== %s skipped: %s bank holiday ===", session_name, holiday)
        return

    while utcnow() < open_utc:
        wait = (open_utc - utcnow()).total_seconds()
        export(cfg, broker, f"waiting for {session_name} open "
               f"({int(wait // 60)} min to go)", engine.snapshots(), newsdesk, utcnow(),
               agent=agent)
        time.sleep(min(120, max(5, wait)))

    log.info("=== %s session live: %s -> %s UTC ===", session_name, open_utc, close_utc)
    errors, stale_strikes = 0, 0
    while utcnow() < close_utc:
        loop_start = utcnow()
        try:
            newsdesk.refresh_calendar()
            newsdesk.refresh_headlines()
            cutoff = utcnow() - timedelta(seconds=60)
            bars_by_asset, fresh = {}, False
            for asset in engine.assets:
                bars = data_feed.get_recent_bars(
                    cfg["assets"][asset]["yahoo"], now_utc=utcnow(),
                    twelvedata_symbol=cfg["assets"][asset].get("twelvedata"))
                if bars is not None:
                    bars_by_asset[asset] = bars[bars.index <= cutoff]
                    if not data_feed.is_stale(bars, utcnow()):
                        fresh = True
            if not fresh:
                stale_strikes += 1
                # ~30 min of patience: transient rate-limits shouldn't end a session
                if stale_strikes >= 40 and not broker.state["open_positions"]:
                    log.warning("no fresh data for %d loops — market closed/holiday, standing down",
                                stale_strikes)
                    agent.say("info", "No market data is coming in — looks like a holiday "
                              "or closure. Standing down; nothing to trade today.")
                    export(cfg, broker, "standing down — no market data (holiday/closure?)",
                           engine.snapshots(), newsdesk, utcnow(), agent=agent)
                    return
            else:
                stale_strikes = 0
            status = engine.step(utcnow(), bars_by_asset)
            export(cfg, broker, status, engine.snapshots(), newsdesk, utcnow(),
                   agent=agent, candles=engine.candles())
            errors = 0
        except Exception:
            errors += 1
            log.exception("loop error (%d/%d)", errors, MAX_CONSECUTIVE_ERRORS)
            if errors >= MAX_CONSECUTIVE_ERRORS:
                log.error("too many consecutive errors — flattening and exiting for safety")
                engine.end_session(utcnow())
                agent.say("halt", "Emergency stop: repeated errors in the trading loop. "
                          "I flattened everything and shut the session down — capital "
                          "first, pride second.", discord=True)
                export(cfg, broker, "EMERGENCY STOP — repeated errors, session aborted",
                       engine.snapshots(), newsdesk, utcnow(), agent=agent,
                       candles=engine.candles())
                return
        elapsed = (utcnow() - loop_start).total_seconds()
        time.sleep(max(1, LOOP_SECONDS - elapsed))

    engine.end_session(utcnow())
    agent.on_session_end(cfg["sessions"][session_name]["label"],
                         engine.session_trades, broker.state["balance"])
    agent.review_and_refine(broker.state["day_key"])
    export(cfg, broker, f"{session_name} session complete — flat, see journal",
           engine.snapshots(), newsdesk, utcnow(), agent=agent,
           candles=engine.candles())
    log.info("=== session complete: balance %.2f ===", broker.state["balance"])


def run_replay(session_name, date_str):
    cfg = load_cfg()
    sandbox = BASE / "backtest"
    sandbox.mkdir(exist_ok=True)
    # redirect every data store so replays never touch the live account
    broker_mod.STATE_FILE = sandbox / f"state_{date_str}_{session_name}.json"
    journal.JOURNAL = sandbox / f"journal_{date_str}_{session_name}"
    journal.TRADES_FILE = journal.JOURNAL / "trades.json"
    journal.LESSONS_JSON = journal.JOURNAL / "lessons.json"
    journal.LESSONS_MD = journal.JOURNAL / "lessons.md"
    journal.DATA_JS = sandbox / f"data_{date_str}_{session_name}.js"
    agent_mod.FEED_FILE = journal.JOURNAL / "agent_feed.json"
    agent_mod.LEARNING_FILE = journal.JOURNAL / "learning.json"
    agent_mod.SUGGESTIONS_FILE = journal.JOURNAL / "suggestions.json"
    agent_mod.OVERRIDES_FILE = sandbox / f"overrides_{date_str}_{session_name}.json"
    if broker_mod.STATE_FILE.exists():
        broker_mod.STATE_FILE.unlink()
    import shutil
    shutil.rmtree(journal.JOURNAL, ignore_errors=True)  # fresh sandbox per run

    open_utc, close_utc = session_window(cfg, session_name, date_str)
    day_key = day_key_for(cfg, open_utc)
    newsdesk = NewsDesk(cfg)
    newsdesk.refresh_calendar()
    agent = TradingAgent(cfg, replay=True)
    broker = PaperBroker(cfg)
    broker.start_session(session_name, day_key)
    engine = Engine(cfg, broker, newsdesk, session_name, open_utc, close_utc,
                    replay=True, agent=agent)
    agent.on_session_start(cfg["sessions"][session_name]["label"], engine.assets,
                           broker.state["balance"], [], now=open_utc)

    all_bars = {}
    for asset in engine.assets:
        b = data_feed.get_bars_between(cfg["assets"][asset]["yahoo"],
                                       open_utc - timedelta(days=4),
                                       close_utc + timedelta(minutes=5))
        if b is None or b[b.index >= open_utc].empty:
            print(f"  {asset}: no data for {date_str} (holiday/weekend?) — skipped")
        else:
            all_bars[asset] = b
    if not all_bars:
        print("No data for any asset on that date — nothing to replay.")
        return

    sim = open_utc + timedelta(minutes=1)
    while sim <= close_utc:
        cutoff = sim - timedelta(seconds=60)
        bars_now = {a: b[b.index <= cutoff] for a, b in all_bars.items()}
        engine.step(sim, bars_now)
        sim += timedelta(minutes=1)
    engine.end_session(close_utc)
    agent.on_session_end(cfg["sessions"][session_name]["label"],
                         engine.session_trades, broker.state["balance"], now=close_utc)
    export(cfg, broker, f"replay of {date_str} {session_name} complete",
           engine.snapshots(), newsdesk, close_utc, replay=True, agent=agent,
           candles=engine.candles())

    print(f"\nReplay {date_str} {session_name}: {len(engine.session_trades)} trades, "
          f"P&L {sum(t['pnl'] for t in engine.session_trades):+.2f} USD, "
          f"final balance {broker.state['balance']:.2f}")
    for t in engine.session_trades:
        print(f"  #{t['trade_id']} {t['asset']} {t['direction']}: "
              f"{t['entry_price']} -> {t['exit_price']} ({t['exit_reason']}) "
              f"{t['pnl']:+.2f} USD ({t['r_multiple']:+.2f}R)")
    for a, s in engine.snapshots().items():
        if s.get("filter_reason"):
            print(f"  {a} filtered: {s['filter_reason']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True, choices=["asia", "newyork"])
    ap.add_argument("--backtest", help="YYYY-MM-DD: replay a past date instead of live trading")
    args = ap.parse_args()

    logdir = BASE / "logs"
    logdir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(logdir / f"{args.session}_{stamp}.log", encoding="utf-8"),
                  logging.StreamHandler()])

    if args.backtest:
        run_replay(args.session, args.backtest)
    else:
        run_live(args.session)


if __name__ == "__main__":
    main()

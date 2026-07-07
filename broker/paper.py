"""Paper broker: simulated fills, position sizing, balances, and hard risk limits. The
default broker (config.json's "broker.provider" == "paper") and the only one exercised
against live trading today.

All persistent account state lives in state.json (repo root, written atomically so the
dashboard never reads a half-written file).

Universal risk rules (can_open, check_daily_stop, sizing, benching) live in broker/ledger.py's
TradeLedger now -- shared with any live broker via broker/live.py's LiveBroker facade -- not in
any strategy. See strategies/README.md. This file keeps its full original public API/behavior;
it now delegates bookkeeping to a TradeLedger instead of doing it inline.
"""
import logging
from pathlib import Path

from .base import BrokerBase
from .ledger import TradeLedger

log = logging.getLogger("broker")

BASE = Path(__file__).resolve().parent.parent
STATE_FILE = BASE / "state.json"


class PaperBroker(BrokerBase):
    def __init__(self, cfg):
        self.cfg = cfg
        self.risk = cfg["risk"]
        self.slippage = cfg["strategy"]["slippage_pct"] / 100.0
        # STATE_FILE is read here (not imported at module load time elsewhere) so
        # bot.py's run_replay() monkey-patching `broker.paper.STATE_FILE` before
        # constructing PaperBroker keeps working exactly as before.
        self.ledger = TradeLedger(cfg, STATE_FILE)

    @property
    def state(self):
        return self.ledger.state

    # ----- state ------------------------------------------------------------
    def save(self):
        self.ledger.save()

    # ----- session/day bookkeeping -------------------------------------------
    def start_session(self, session_name, day_key):
        self.ledger.start_session(session_name, day_key)

    def is_benched(self, asset):
        return self.ledger.is_benched(asset)

    # ----- hard limits ("no heavy losses") -- universal, apply to every strategy ---
    def can_open(self, asset):
        return self.ledger.can_open(asset)

    def check_daily_stop(self):
        self.ledger.check_daily_stop()

    # ----- order lifecycle -----------------------------------------------------
    def size_position(self, entry, stop):
        return self.ledger.size_position(entry, stop)

    def open_position(self, asset, signal, now_utc, context):
        units, risk_usd = self.ledger.size_position(signal["entry"], signal["stop"])
        if units <= 0:
            return None
        slip = signal["entry"] * self.slippage
        fill = signal["entry"] + slip if signal["direction"] == "LONG" else signal["entry"] - slip
        pos = {
            "asset": asset,
            "direction": signal["direction"],
            "entry_time": str(now_utc),
            "entry_price": round(fill, 4),
            "units": units,
            "risk_usd": risk_usd,
            "stop": round(signal["stop"], 4),
            "target": round(signal["target"], 4),
            "mfe": 0.0,  # max favorable excursion, in R
            "mae": 0.0,  # max adverse excursion, in R
            "context": context,  # range info, tv rating, headlines at entry
        }
        self.ledger.register_open(asset, pos)
        log.info("OPEN %s %s %.4f units @ %.4f stop %.4f target %.4f (risk $%.2f)",
                 signal["direction"], asset, units, fill, pos["stop"],
                 pos["target"], risk_usd)
        return pos

    def update_position(self, asset, bar):
        """Track excursions and check stop/target against the latest 1-min bar.

        Returns (exit_price, exit_reason) or (None, None).
        Worst-case rule: if a bar touches both stop and target, the stop wins.
        """
        return self.ledger.track_bar(asset, bar)

    def close_position(self, asset, exit_price, reason, now_utc):
        """Note: parameter order (exit_price before reason) predates broker/base.py's
        interface and is kept as-is -- every call site in bot.py's Engine already uses this
        order positionally; reordering it for interface purity isn't worth the regression
        risk to the live trading loop."""
        pos = self.ledger.pop_position(asset)
        if pos is None:
            return None
        slip = exit_price * self.slippage
        fill = exit_price - slip if pos["direction"] == "LONG" else exit_price + slip
        direction = 1 if pos["direction"] == "LONG" else -1
        pnl = (fill - pos["entry_price"]) * pos["units"] * direction
        risk = abs(pos["entry_price"] - pos["stop"]) * pos["units"]
        r_multiple = pnl / risk if risk else 0.0
        balance = self.ledger.register_close(asset, pnl)
        self.ledger.record_equity(now_utc)
        self.ledger.apply_streak(asset, pnl)
        self.ledger.check_daily_stop()
        self.ledger.save()

        trade = dict(pos)
        trade.update({
            "exit_time": str(now_utc), "exit_price": round(fill, 4),
            "exit_reason": reason, "pnl": round(pnl, 2),
            "r_multiple": round(r_multiple, 2),
            "balance_after": balance,
            "session": self.state["session_name"], "day_key": self.state["day_key"],
        })
        log.info("CLOSE %s %s @ %.4f (%s)  P&L %+.2f (%.2fR)  balance %.2f",
                 pos["direction"], asset, fill, reason, pnl, r_multiple, balance)
        return trade

    def flatten_all(self, prices, reason, now_utc):
        closed = []
        for asset in list(self.state["open_positions"].keys()):
            px = prices.get(asset)
            if px is not None:
                t = self.close_position(asset, px, reason, now_utc)
                if t:
                    closed.append(t)
        return closed

    # ----- BrokerBase compliance (broker/base.py) -------------------------------
    # Paper trading has no live clock/feed of its own -- these delegate to data_feed,
    # exactly like the engine already does directly. Kept thin on purpose.
    def connect(self):
        return True  # always "connected" -- there's nothing to dial into

    def get_bars(self, asset, interval="1m", lookback_minutes=300):
        import data_feed
        return data_feed.get_recent_bars(
            self.cfg["assets"][asset]["yahoo"],
            twelvedata_symbol=self.cfg["assets"][asset].get("twelvedata"))

    def get_price(self, asset):
        bars = self.get_bars(asset)
        return float(bars["Close"].iloc[-1]) if bars is not None and not bars.empty else None

    def place_order(self, asset, direction, units, stop, target):
        """Alias for open_position() with the interface's standardized name/shape. Engine
        calls open_position() directly (it also needs to pass through `signal`/`context`
        dicts this simplified interface doesn't carry) -- this exists for anything using the
        broker-agnostic surface instead."""
        import datetime
        signal = {"direction": direction, "entry": self.get_price(asset), "stop": stop,
                  "target": target}
        return self.open_position(asset, signal, datetime.datetime.now(datetime.timezone.utc), {})

    def get_positions(self):
        return self.state["open_positions"]

    def get_account_info(self):
        return {"balance": self.state["balance"], "currency": "USD"}

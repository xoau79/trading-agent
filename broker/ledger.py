"""TradeLedger: the broker-agnostic risk rules, bookkeeping, and state persistence that used
to live entirely inside broker/paper.py. Extracted so a live broker (broker/live.py's
LiveBroker facade, wrapping broker/ctrader/ or broker/mt5_broker.py) can share the exact same
universal risk rules (daily loss limit, trade/position caps, consecutive-loss bench) and the
exact same state.json-shaped bookkeeping that paper trading has always used -- without
duplicating that logic per broker.

broker/paper.py keeps its full public API and behavior; it now delegates to a TradeLedger
instance instead of doing this bookkeeping itself. This file changes NOTHING about what paper
trading (or a replay/backtest) does -- see tests/test_paper_parity.py, which must pass
unchanged before and after this refactor.
"""
import json
import logging
import os
from pathlib import Path

log = logging.getLogger("broker.ledger")


def _atomic_write(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


class TradeLedger:
    """Universal risk rules + position/session bookkeeping, keyed by asset. One instance per
    broker (paper or live); each live broker gets its own state file (see broker/live.py) so a
    live account's bookkeeping never shares a file with paper trading's state.json."""

    def __init__(self, cfg, state_file):
        self.cfg = cfg
        self.risk = cfg["risk"]
        self.state_file = Path(state_file)
        self.state = self._load_state()

    # ----- state ------------------------------------------------------------
    def _load_state(self):
        if self.state_file.exists():
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        return {
            "balance": self.cfg["account"]["starting_balance"],
            "equity_curve": [],          # [{t, balance}]
            "open_positions": {},        # asset -> position dict
            "day_key": None,             # Sydney calendar date of the trading day
            "day_start_balance": None,
            "trades_today": 0,
            "trades_this_session": 0,
            "session_name": None,
            "halted_reason": None,
            "consecutive_losses": {},    # asset -> int
            "benched_until": {},         # asset -> day_key string
            "trade_seq": 0,
        }

    def save(self):
        _atomic_write(self.state_file, json.dumps(self.state, indent=2, default=str))

    # ----- session/day bookkeeping -------------------------------------------
    def start_session(self, session_name, day_key, balance=None):
        """balance: when a live broker connects, it passes its broker-reported balance so a
        new trading day's loss-limit baseline is measured against ground truth, not the
        ledger's last-known (possibly stale) figure. None (paper trading) leaves it as-is."""
        s = self.state
        if balance is not None:
            s["balance"] = balance
        if s["day_key"] != day_key:
            s["day_key"] = day_key
            s["day_start_balance"] = s["balance"]
            s["trades_today"] = 0
            s["halted_reason"] = None  # a daily halt only clears on a NEW day
        s["session_name"] = session_name
        s["trades_this_session"] = 0
        if not s["equity_curve"]:
            s["equity_curve"].append({"t": f"{day_key} start", "balance": s["balance"]})
        self.check_daily_stop()
        self.save()

    def is_benched(self, asset):
        until = self.state["benched_until"].get(asset)
        return until is not None and self.state["day_key"] <= until

    # ----- hard limits ("no heavy losses") -- universal, apply to every strategy ---
    def can_open(self, asset):
        s = self.state
        if s["halted_reason"]:
            return False, s["halted_reason"]
        if s["trades_this_session"] >= self.risk["max_trades_per_session"]:
            return False, "session trade cap reached (4)"
        if s["trades_today"] >= self.risk["max_trades_per_day"]:
            return False, "daily trade cap reached (8)"
        if len(s["open_positions"]) >= self.risk["max_concurrent_positions"]:
            return False, "max concurrent positions open"
        if asset in s["open_positions"]:
            return False, "already in a position on this asset"
        if self.is_benched(asset):
            return False, "asset benched after losing streak"
        return True, None

    def check_daily_stop(self):
        s = self.state
        if s["day_start_balance"] is None or s["halted_reason"]:
            return
        loss_limit = s["day_start_balance"] * self.risk["daily_loss_limit_pct"] / 100.0
        day_pnl = s["balance"] - s["day_start_balance"]
        if day_pnl <= -loss_limit:
            s["halted_reason"] = (f"daily loss limit hit ({day_pnl:+.2f} USD) — "
                                  "trading halted until tomorrow")
            log.warning(s["halted_reason"])

    # ----- sizing -----------------------------------------------------------
    def size_position(self, entry, stop):
        """Units so that (entry - stop) * units = risk_per_trade_pct of balance,
        leverage-capped. risk_per_trade_pct is universal today (config.json's "risk"); once
        strategies/ carries its own risk_per_trade_pct per strategy (see
        strategies/README.md), this reads from the active strategy instead."""
        risk_usd = self.state["balance"] * self.risk["risk_per_trade_pct"] / 100.0
        stop_dist = abs(entry - stop)
        if stop_dist <= 0:
            return 0.0, 0.0
        units = risk_usd / stop_dist
        max_units = self.risk["max_notional_leverage"] * self.state["balance"] / entry
        if units > max_units:
            units = max_units
            risk_usd = units * stop_dist
        return round(units, 4), round(risk_usd, 2)

    # ----- position lifecycle bookkeeping ------------------------------------
    def register_open(self, asset, pos):
        """Record a newly-opened position (already filled/sized by the caller) in the ledger:
        counters, trade_seq, save. Returns the same pos dict with 'trade_id' set."""
        s = self.state
        s["open_positions"][asset] = pos
        s["trades_today"] += 1
        s["trades_this_session"] += 1
        s["trade_seq"] += 1
        pos["trade_id"] = s["trade_seq"]
        self.save()
        return pos

    def track_bar(self, asset, bar):
        """Track excursions and check stop/target against the latest 1-min bar for a
        position already in self.state['open_positions'].

        Returns (exit_price, exit_reason) or (None, None).
        Worst-case rule: if a bar touches both stop and target, the stop wins.
        """
        pos = self.state["open_positions"].get(asset)
        if pos is None:
            return None, None
        hi, lo = float(bar["High"]), float(bar["Low"])
        risk = abs(pos["entry_price"] - pos["stop"])
        if pos["direction"] == "LONG":
            pos["mfe"] = max(pos["mfe"], (hi - pos["entry_price"]) / risk)
            pos["mae"] = max(pos["mae"], (pos["entry_price"] - lo) / risk)
            if lo <= pos["stop"]:
                return pos["stop"], "stop"
            if hi >= pos["target"]:
                return pos["target"], "target"
        else:
            pos["mfe"] = max(pos["mfe"], (pos["entry_price"] - lo) / risk)
            pos["mae"] = max(pos["mae"], (hi - pos["entry_price"]) / risk)
            if hi >= pos["stop"]:
                return pos["stop"], "stop"
            if lo <= pos["target"]:
                return pos["target"], "target"
        return None, None

    def register_close(self, asset, pnl):
        """Book a realized pnl against the balance, update the equity curve, and apply
        consecutive-loss benching. Returns nothing -- the caller (PaperBroker/LiveBroker)
        assembles the trade dict itself, since only it knows the fill details."""
        s = self.state
        s["balance"] = round(s["balance"] + pnl, 2)
        return s["balance"]

    def record_equity(self, now_utc):
        self.state["equity_curve"].append({"t": str(now_utc), "balance": self.state["balance"]})

    def apply_streak(self, asset, pnl):
        """Consecutive-loss benching: a losing trade extends the asset's streak (benching it
        for the rest of the day past the configured threshold); any non-loss resets it."""
        s = self.state
        streaks = s["consecutive_losses"]
        if pnl < 0:
            streaks[asset] = streaks.get(asset, 0) + 1
            if streaks[asset] >= self.risk["consecutive_losses_to_bench"]:
                s["benched_until"][asset] = s["day_key"]  # benched through today; reviewed next day
                log.warning("%s benched after %d consecutive losses", asset, streaks[asset])
        else:
            streaks[asset] = 0

    def pop_position(self, asset):
        return self.state["open_positions"].pop(asset, None)

    def sync_balance(self, balance, equity=None):
        """Live hook: overwrite the ledger's simulated balance with the broker's own reported
        truth (paper trading never calls this -- its balance IS the ledger's)."""
        self.state["balance"] = round(balance, 2)

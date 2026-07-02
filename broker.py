"""Paper broker: simulated fills, position sizing, balances, and hard risk limits.

All persistent account state lives in state.json (written atomically so the
dashboard never reads a half-written file).
"""
import json
import logging
import os
from pathlib import Path

log = logging.getLogger("broker")

BASE = Path(__file__).resolve().parent
STATE_FILE = BASE / "state.json"


def _atomic_write(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


class PaperBroker:
    def __init__(self, cfg):
        self.cfg = cfg
        self.risk = cfg["risk"]
        self.slippage = cfg["strategy"]["slippage_pct"] / 100.0
        self.state = self._load_state()

    # ----- state ------------------------------------------------------------
    def _load_state(self):
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
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
        _atomic_write(STATE_FILE, json.dumps(self.state, indent=2, default=str))

    # ----- session/day bookkeeping -------------------------------------------
    def start_session(self, session_name, day_key):
        s = self.state
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

    # ----- hard limits ("no heavy losses") ------------------------------------
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

    # ----- order lifecycle -----------------------------------------------------
    def size_position(self, entry, stop):
        """Units so that (entry - stop) * units = 1% of balance, leverage-capped."""
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

    def open_position(self, asset, signal, now_utc, context):
        units, risk_usd = self.size_position(signal["entry"], signal["stop"])
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
        s = self.state
        s["open_positions"][asset] = pos
        s["trades_today"] += 1
        s["trades_this_session"] += 1
        s["trade_seq"] += 1
        pos["trade_id"] = s["trade_seq"]
        self.save()
        log.info("OPEN %s %s %.4f units @ %.4f stop %.4f target %.4f (risk $%.2f)",
                 signal["direction"], asset, units, fill, pos["stop"],
                 pos["target"], risk_usd)
        return pos

    def update_position(self, asset, bar):
        """Track excursions and check stop/target against the latest 1-min bar.

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

    def close_position(self, asset, exit_price, reason, now_utc):
        s = self.state
        pos = s["open_positions"].pop(asset, None)
        if pos is None:
            return None
        slip = exit_price * self.slippage
        fill = exit_price - slip if pos["direction"] == "LONG" else exit_price + slip
        direction = 1 if pos["direction"] == "LONG" else -1
        pnl = (fill - pos["entry_price"]) * pos["units"] * direction
        risk = abs(pos["entry_price"] - pos["stop"]) * pos["units"]
        r_multiple = pnl / risk if risk else 0.0
        s["balance"] = round(s["balance"] + pnl, 2)
        s["equity_curve"].append({"t": str(now_utc), "balance": s["balance"]})

        streaks = s["consecutive_losses"]
        if pnl < 0:
            streaks[asset] = streaks.get(asset, 0) + 1
            if streaks[asset] >= self.risk["consecutive_losses_to_bench"]:
                s["benched_until"][asset] = s["day_key"]  # benched through today; reviewed next day
                log.warning("%s benched after %d consecutive losses", asset, streaks[asset])
        else:
            streaks[asset] = 0

        self.check_daily_stop()
        self.save()

        trade = dict(pos)
        trade.update({
            "exit_time": str(now_utc), "exit_price": round(fill, 4),
            "exit_reason": reason, "pnl": round(pnl, 2),
            "r_multiple": round(r_multiple, 2),
            "balance_after": s["balance"],
            "session": s["session_name"], "day_key": s["day_key"],
        })
        log.info("CLOSE %s %s @ %.4f (%s)  P&L %+.2f (%.2fR)  balance %.2f",
                 pos["direction"], asset, fill, reason, pnl, r_multiple, s["balance"])
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

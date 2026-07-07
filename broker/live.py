"""LiveBroker: the facade that lets a real broker adapter (broker/ctrader/, broker/mt5_broker.py)
plug into bot.py's Engine exactly where PaperBroker plugs in today -- same state-dict shape,
same can_open()/open_position()/update_position()/close_position()/flatten_all()/
start_session() surface, same TradeLedger-backed bookkeeping (broker/ledger.py) so risk rules
behave identically to paper trading. Engine never needs to know it's talking to a live broker
instead of the simulator.

Everything genuinely "live" (safety latch, order sanity checks, drawdown halt, reconciliation)
lives here, in one place, shared by every live adapter -- see docs/ctrader_setup.md's go-live
checklist for how the pieces fit together operationally.

Live state is stored in its own file, state_live_<provider>.json (repo root), never
state.json -- paper trading and live trading must never be able to read or clobber each
other's balances.
"""
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from .base import BrokerBase
from .ledger import TradeLedger

log = logging.getLogger("broker.live")

# Overridable module global, read at LiveBroker construction time -- same pattern as
# broker/paper.py's STATE_FILE, so tests (and any future sandboxed/replay use) can
# monkeypatch broker.live.STATE_DIR to an isolated directory before constructing a
# LiveBroker instead of ever touching the real repo root.
STATE_DIR = Path(__file__).resolve().parent.parent


class LiveBroker(BrokerBase):
    def __init__(self, cfg, adapter):
        self.cfg = cfg
        self.adapter = adapter
        self.provider = cfg.get("broker", {}).get("provider", "live")
        state_file = STATE_DIR / f"state_live_{self.provider}.json"
        self.ledger = TradeLedger(cfg, state_file)
        self.last_order_error = None
        self.unmanaged_warnings = []

    @property
    def state(self):
        return self.ledger.state

    # ----- connection / safety latch -------------------------------------------------
    def connect(self):
        self.adapter.connect()
        self._enforce_live_latch()
        info = self.adapter.get_account_info()
        self.ledger.sync_balance(info["balance"])
        if self.ledger.state.get("live_baseline_balance") is None:
            self.ledger.state["live_baseline_balance"] = info["balance"]
        self.ledger.save()
        return True

    def _enforce_live_latch(self):
        """A LIVE (real-money) account only trades if BOTH config.json's
        live_trading.enabled is true AND .env's LIVE_TRADING_CONFIRM equals this exact
        account's id. Either one missing refuses to trade -- on purpose, so a copied .env or
        a stale config flag can never silently arm live trading. Demo accounts are unaffected.
        """
        if not self.adapter.is_live_account():
            return
        info = self.adapter.get_account_info()
        account_id = str(info.get("account_id", ""))
        enabled = bool(self.cfg.get("live_trading", {}).get("enabled"))
        confirm = os.getenv("LIVE_TRADING_CONFIRM", "")
        if not enabled or not confirm or confirm != account_id:
            raise RuntimeError(
                "Refusing to trade a LIVE (real-money) account without explicit "
                "confirmation. Both must be true: config.json's live_trading.enabled == "
                f"true, AND .env's LIVE_TRADING_CONFIRM == {account_id!r} (this account's "
                "exact id). This is a deliberate safety latch -- see "
                "docs/ctrader_setup.md's go-live checklist, not a bug.")

    # ----- session/day bookkeeping (Engine-facing, mirrors PaperBroker) --------------
    def start_session(self, session_name, day_key):
        info = self.adapter.get_account_info()
        self.ledger.sync_balance(info["balance"])
        self.ledger.start_session(session_name, day_key, balance=info["balance"])

    def can_open(self, asset):
        self._check_drawdown_halt()
        return self.ledger.can_open(asset)

    # ----- order lifecycle (Engine-facing) -------------------------------------------
    def open_position(self, asset, signal, now_utc, context):
        units, risk_usd = self.ledger.size_position(signal["entry"], signal["stop"])
        if units <= 0:
            return None
        ok, why = self._sanity_check_order(asset, signal, units)
        if not ok:
            self.last_order_error = f"{asset} {signal['direction']}: refused — {why}"
            log.warning("order sanity check refused: %s", self.last_order_error)
            return None
        try:
            pos = self.adapter.place_order(asset, signal["direction"], units,
                                           signal["stop"], signal["target"])
        except Exception as e:
            self.last_order_error = f"{asset} {signal['direction']}: {e}"
            log.error("live order placement failed: %s", self.last_order_error)
            return None
        if pos is None:
            return None
        pos["risk_usd"] = risk_usd
        pos["entry_time"] = str(now_utc)
        pos.setdefault("mfe", 0.0)
        pos.setdefault("mae", 0.0)
        pos["context"] = context
        self.ledger.register_open(asset, pos)
        self.last_order_error = None
        return pos

    def _sanity_check_order(self, asset, signal, units):
        """Refuse (never silently resize/adjust) an order that fails basic sanity checks --
        this runs in addition to, not instead of, the universal risk caps in can_open()."""
        lt = self.cfg.get("live_trading", {})
        entry, stop, target = signal["entry"], signal["stop"], signal["target"]
        if entry is None or entry <= 0:
            return False, "non-positive or missing entry price"

        max_units = lt.get("max_units_per_asset", {}).get(asset)
        if max_units is not None and units > max_units:
            return False, f"sized units {units} exceed live_trading.max_units_per_asset[{asset}]={max_units}"

        stop_dist_pct = abs(entry - stop) / entry * 100
        min_pct = lt.get("min_stop_distance_pct", 0)
        max_pct = lt.get("max_stop_distance_pct", 100)
        if stop_dist_pct < min_pct:
            return False, f"stop distance {stop_dist_pct:.4f}% below minimum {min_pct}%"
        if stop_dist_pct > max_pct:
            return False, f"stop distance {stop_dist_pct:.4f}% above maximum {max_pct}%"

        if signal["direction"] == "LONG" and not (stop < entry < target):
            return False, "LONG stop/target on the wrong side of entry"
        if signal["direction"] == "SHORT" and not (target < entry < stop):
            return False, "SHORT stop/target on the wrong side of entry"

        max_leverage = self.cfg["risk"]["max_notional_leverage"]
        balance = self.ledger.state["balance"]
        notional = units * entry
        if balance > 0 and notional > max_leverage * balance:
            return False, f"notional {notional:.2f} exceeds leverage cap ({max_leverage}x balance)"
        return True, None

    def update_position(self, asset, bar):
        """Excursion (mfe/mae) bookkeeping happens the same way as paper trading, but the
        actual exit decision does NOT come from this bar: a live stop/target executes
        server-side at the broker regardless of what this bot is looking at. This just
        checks whether the broker still shows the position open; if it's gone, the position
        closed server-side and we infer price/reason for the journal."""
        pos = self.ledger.state["open_positions"].get(asset)
        if pos is None:
            return None, None
        self.ledger.track_bar(asset, bar)  # updates mfe/mae; its exit signal is ignored here
        return self._check_broker_closure(asset, pos)

    def _check_broker_closure(self, asset, pos):
        try:
            broker_positions = self.adapter.get_positions()
        except Exception as e:
            log.warning("could not check %s's position status at the broker: %s", asset, e)
            return None, None
        if asset in broker_positions:
            return None, None  # still open at the broker
        price = self.adapter.get_price(asset)
        reason = self._infer_close_reason(pos, price)
        return price, reason

    @staticmethod
    def _infer_close_reason(pos, price):
        if price is None:
            return "closed_externally"
        to_stop = abs(price - pos["stop"])
        to_target = abs(price - pos["target"])
        return "stop" if to_stop <= to_target else "target"

    def close_position(self, asset, exit_price, reason, now_utc):
        """Same parameter order as PaperBroker.close_position (exit_price before reason) --
        Engine calls both broker types identically. If the position is still open at the
        broker (a forced exit Engine initiated, e.g. news flatten or daily-stop flatten),
        actually close it there and use its real fill price; if it's already gone (this call
        followed update_position's own closure detection, or reconcile() found it missing),
        skip re-closing and just book the price we already determined."""
        pos = self.ledger.pop_position(asset)
        if pos is None:
            return None
        fill_price = exit_price
        try:
            still_open = asset in self.adapter.get_positions()
        except Exception as e:
            log.warning("could not verify %s's broker status before closing: %s", asset, e)
            still_open = True  # safer to attempt the close than to silently skip it
        if still_open:
            try:
                result = self.adapter.close_position(asset, reason, price=exit_price, when=now_utc)
                if result and result.get("exit_price") is not None:
                    fill_price = result["exit_price"]
            except Exception as e:
                log.error("broker-side close failed for %s (%s) — booking at last-known "
                         "price %.4f; VERIFY THIS POSITION MANUALLY", asset, e, exit_price or 0.0)

        direction = 1 if pos["direction"] == "LONG" else -1
        pnl = ((fill_price - pos["entry_price"]) * pos["units"] * direction
              if fill_price is not None and pos.get("entry_price") is not None else 0.0)
        risk = abs(pos["entry_price"] - pos["stop"]) * pos["units"] if pos.get("entry_price") else 0
        r_multiple = pnl / risk if risk else 0.0

        balance = self.ledger.register_close(asset, pnl)
        self.ledger.record_equity(now_utc)
        self.ledger.apply_streak(asset, pnl)
        self.ledger.check_daily_stop()
        self._check_drawdown_halt()
        self.ledger.save()

        trade = dict(pos)
        trade.update({
            "exit_time": str(now_utc),
            "exit_price": round(fill_price, 4) if fill_price is not None else None,
            "exit_reason": reason, "pnl": round(pnl, 2), "r_multiple": round(r_multiple, 2),
            "balance_after": balance,
            "session": self.state["session_name"], "day_key": self.state["day_key"],
        })
        return trade

    def flatten_all(self, prices, reason, now_utc):
        closed = []
        for asset in list(self.ledger.state["open_positions"].keys()):
            t = self.close_position(asset, prices.get(asset), reason, now_utc)
            if t:
                closed.append(t)
        return closed

    def _check_drawdown_halt(self):
        s = self.ledger.state
        baseline = s.get("live_baseline_balance")
        max_dd_pct = self.cfg.get("live_trading", {}).get("max_total_drawdown_pct")
        if not baseline or not max_dd_pct or s.get("halted_reason"):
            return
        dd_pct = (baseline - s["balance"]) / baseline * 100
        if dd_pct >= max_dd_pct:
            s["halted_reason"] = (f"max total drawdown hit ({dd_pct:.2f}% from baseline "
                                  f"{baseline:.2f}) — live trading halted")
            log.warning(s["halted_reason"])
            self.ledger.save()

    # ----- reconciliation (crash recovery / startup) ---------------------------------
    def reconcile(self, now_utc):
        """Compares the ledger's last-known open positions against the broker's own current
        truth. Anything the ledger thought was open but the broker no longer shows closed
        while we weren't running -- book it now, priced at the best information available
        (current market price; this is an approximation when no live execution event was
        observed, and is labeled as such in the trade record). Anything the broker shows
        open that carries our order label but the ledger doesn't know about gets flagged
        (never auto-adopted or touched) via self.unmanaged_warnings for the dashboard."""
        try:
            broker_positions = self.adapter.get_positions()
        except Exception as e:
            log.error("reconcile(): could not reach the broker — %s. Leaving ledger "
                     "positions as-is; will retry next start.", e)
            return []
        ledger_positions = dict(self.ledger.state.get("open_positions", {}))
        closed = []
        for asset in ledger_positions:
            if asset in broker_positions:
                continue
            price = self.adapter.get_price(asset)
            trade = self.close_position(asset, price, "reconciled_externally", now_utc)
            if trade:
                closed.append(trade)

        self.unmanaged_warnings = []
        for asset, pos in broker_positions.items():
            if asset in ledger_positions:
                continue
            msg = (f"{asset}: the broker reports an open position (position_id="
                  f"{pos.get('position_id')}) that this bot isn't tracking — leaving it "
                  "untouched (never auto-adopting an unmanaged position). Investigate manually.")
            log.warning(msg)
            self.unmanaged_warnings.append(msg)
        return closed

    # ----- BrokerBase compliance (adapter passthrough) -------------------------------
    def get_bars(self, asset, interval="1m", lookback_minutes=300):
        return self.adapter.get_bars(asset, interval=interval, lookback_minutes=lookback_minutes)

    def get_price(self, asset):
        return self.adapter.get_price(asset)

    def place_order(self, asset, direction, units, stop, target):
        """Alias for open_position() with BrokerBase's standardized shape -- see
        PaperBroker.place_order for why Engine calls open_position() directly instead."""
        signal = {"direction": direction, "entry": self.get_price(asset), "stop": stop,
                 "target": target}
        return self.open_position(asset, signal, datetime.now(timezone.utc), {})

    def get_positions(self):
        return self.adapter.get_positions()

    def get_account_info(self):
        return self.adapter.get_account_info()

    # ----- dashboard --------------------------------------------------------------
    def status_payload(self):
        try:
            info = self.adapter.get_account_info()
            connected = True
        except Exception as e:
            info = {}
            connected = False
            log.warning("status_payload: could not reach the broker: %s", e)
        return {
            "provider": self.provider,
            "account_id": info.get("account_id"),
            "environment": "live" if info.get("is_live") else "demo",
            "connected": connected,
            "balance": info.get("balance", self.ledger.state.get("balance")),
            "equity": info.get("equity"),
            "currency": info.get("currency", "USD"),
            "last_order_error": self.last_order_error,
            "unmanaged_warnings": list(self.unmanaged_warnings),
        }

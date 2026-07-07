"""IC Markets (or any MetaTrader 5 broker) adapter.

Talks to a LOCALLY RUNNING MT5 terminal via the official `MetaTrader5` PyPI package
(maintained by MetaQuotes) -- there's no dedicated IC Markets REST API; this is the standard
integration path (pypi.org/project/metatrader5, mql5.com/en/docs/python_metatrader5).
Windows-only, which matches this machine.

INERT BY DEFAULT. Nothing here runs unless you deliberately:
  1. Install the MT5 terminal, log into your IC Markets account in it, and enable algo
     trading (Tools -> Options -> Expert Advisors -> "Allow algorithmic trading").
  2. `pip install MetaTrader5` (commented out in requirements.txt by default).
  3. Fill in MT5_LOGIN / MT5_PASSWORD / MT5_SERVER in .env (see .env.example).
  4. Fill in each traded asset's "mt5" symbol in config.json -- check your IC Markets
     terminal's Market Watch for the exact names (often "XAUUSD" for gold, index CFDs like
     "NAS100"/"US500" rather than literal futures; IC Markets sometimes suffixes symbols
     e.g. ".a" depending on account type). This file does NOT guess them.
  5. Set config.json's "broker": {"provider": "mt5"} (default is "paper").

No credentials were ever requested or pasted into chat to build this -- fill .env yourself.

Order placement now IS implemented (order_send() with attached SL/TP, volume floored to the
symbol's lot step -- see place_order()/close_position()), wrapped by broker/live.py's
LiveBroker facade exactly like broker/ctrader/. It cannot be integration-tested in this
repo's Linux sandbox (the MetaTrader5 package is Windows-only and needs a running terminal) --
tests/test_mt5_broker.py exercises it against a fake `MetaTrader5` module injected via
sys.modules; run ops/mt5_smoke_test.py on your actual Windows machine (read-only) before ever
flipping config.json's provider to "mt5", and ops/live_order_test.py (a minimum-size demo
order, shared with the cTrader adapter) before trusting it further.

Positions are tagged with a fixed `magic` number (see _magic()) instead of cTrader's string
label -- MT5 has no free-text label field on a position, magic numbers are the standard
MQL5/MT5 idiom for "which EA/bot owns this," and LiveBroker's reconciliation filters on it the
same way it filters cTrader positions by order label: this bot never touches a position that
isn't its own.
"""
import logging
import math
import os

import pandas as pd

from .base import BrokerBase

log = logging.getLogger("broker.mt5")

DEFAULT_MAGIC = 20260707  # arbitrary but fixed -- identifies positions this bot opened
DEFAULT_DEVIATION_POINTS = 20  # max acceptable slippage in points on a market order


class MT5Broker(BrokerBase):
    def __init__(self, cfg):
        self.cfg = cfg
        self._mt5 = None
        self._connected = False

    def connect(self):
        try:
            import MetaTrader5 as mt5
        except ImportError as e:
            raise RuntimeError(
                "MetaTrader5 package not installed. Run: pip install MetaTrader5 "
                "(Windows-only, requires the MT5 terminal). See broker/README.md.") from e

        login, password, server = (os.getenv("MT5_LOGIN"), os.getenv("MT5_PASSWORD"),
                                   os.getenv("MT5_SERVER"))
        if not all([login, password, server]):
            raise RuntimeError(
                "MT5_LOGIN / MT5_PASSWORD / MT5_SERVER not set in .env — see .env.example. "
                "Refusing to guess or silently fall back for a live-money connection.")
        if not mt5.initialize(login=int(login), password=password, server=server):
            raise RuntimeError(f"MT5 connection failed: {mt5.last_error()}")
        self._mt5 = mt5
        self._connected = True
        log.info("connected to MT5 (server=%s, login=%s)", server, login)
        return True

    def is_live_account(self):
        self._require_connection()
        info = self._mt5.account_info()
        return bool(info and info.trade_mode == self._mt5.ACCOUNT_TRADE_MODE_REAL)

    def _require_connection(self):
        if not self._connected:
            raise RuntimeError("MT5Broker.connect() must succeed before any other call.")

    def _symbol(self, asset):
        symbol = self.cfg["assets"].get(asset, {}).get("mt5")
        if not symbol:
            raise ValueError(
                f"{asset} has no 'mt5' symbol mapped in config.json — check your IC Markets "
                "terminal's Market Watch for the exact name and fill it in before trading it.")
        return symbol

    def _asset_for_symbol(self, symbol):
        for asset, acfg in self.cfg["assets"].items():
            if acfg.get("mt5") == symbol:
                return asset
        return None

    def _magic(self):
        return self.cfg.get("live_trading", {}).get("mt5_magic", DEFAULT_MAGIC)

    def get_bars(self, asset, interval="1m", lookback_minutes=300):
        self._require_connection()
        symbol = self._symbol(asset)
        rates = self._mt5.copy_rates_from_pos(symbol, self._mt5.TIMEFRAME_M1, 0, lookback_minutes)
        if rates is None:
            log.warning("no rates returned for %s (%s): %s", asset, symbol, self._mt5.last_error())
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.set_index("time").rename(columns={"open": "Open", "high": "High",
                                                   "low": "Low", "close": "Close",
                                                   "tick_volume": "Volume"})
        return df[["Open", "High", "Low", "Close", "Volume"]]

    def get_price(self, asset):
        self._require_connection()
        tick = self._mt5.symbol_info_tick(self._symbol(asset))
        return float(tick.bid) if tick else None

    # ----- volume conversion --------------------------------------------------------
    def _contract_size(self, symbol):
        info = self._mt5.symbol_info(symbol)
        return (info.trade_contract_size if info and info.trade_contract_size else 1.0)

    def units_to_lots(self, symbol, units):
        """Engine units -> MT5 lots, floored to the symbol's volume_step and clamped to
        [volume_min, volume_max]. Floors (never rounds up) so a rounding adjustment can only
        reduce risk, never inflate it. Returns 0.0 if the sized units round down below the
        symbol's minimum tradable lot size -- the caller must treat that as a refused order."""
        info = self._mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(f"no symbol_info for {symbol} — is it in Market Watch?")
        contract_size = info.trade_contract_size or 1.0
        step = info.volume_step or 0.01
        lots = units / contract_size
        lots = math.floor(lots / step + 1e-9) * step  # +epsilon guards against fp floor errors
        lots = round(lots, 8)
        if info.volume_min and lots < info.volume_min:
            return 0.0
        if info.volume_max and lots > info.volume_max:
            lots = info.volume_max
        return lots

    def _filling_type(self, symbol):
        """MT5's allowed order-filling modes are a bitmask on symbol_info().filling_mode;
        RETURN is always accepted as the fallback regardless of that bitmask (confirmed via
        MQL5's own filling-mode documentation) -- prefer IOC, then FOK, then RETURN."""
        info = self._mt5.symbol_info(symbol)
        mode = info.filling_mode if info else 0
        if mode & self._mt5.SYMBOL_FILLING_IOC:
            return self._mt5.ORDER_FILLING_IOC
        if mode & self._mt5.SYMBOL_FILLING_FOK:
            return self._mt5.ORDER_FILLING_FOK
        return self._mt5.ORDER_FILLING_RETURN

    # ----- orders ------------------------------------------------------------------
    def place_order(self, asset, direction, units, stop, target):
        self._require_connection()
        symbol = self._symbol(asset)
        lots = self.units_to_lots(symbol, units)
        if lots <= 0:
            raise ValueError(f"{asset}: sized units ({units}) round down to zero lots at "
                             "this symbol's step/minimum — order refused, not silently resized.")
        tick = self._mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"no tick data for {symbol} — market may be closed")
        order_type = (self._mt5.ORDER_TYPE_BUY if direction == "LONG"
                     else self._mt5.ORDER_TYPE_SELL)
        price = tick.ask if direction == "LONG" else tick.bid
        request = {
            "action": self._mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": lots,
            "type": order_type, "price": price, "sl": stop, "tp": target,
            "deviation": DEFAULT_DEVIATION_POINTS, "magic": self._magic(),
            "comment": "trading-agent", "type_time": self._mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_type(symbol),
        }
        result = self._mt5.order_send(request)
        if result is None or result.retcode != self._mt5.TRADE_RETCODE_DONE:
            code = result.retcode if result is not None else self._mt5.last_error()
            raise RuntimeError(f"order_send failed for {asset} ({symbol}): retcode={code}")
        filled_units = result.volume * self._contract_size(symbol)
        pos = {
            "asset": asset, "direction": direction, "entry_price": result.price,
            "units": filled_units, "stop": stop, "target": target,
            "position_id": result.order, "provider": "mt5",
        }
        log.info("OPEN %s %s %.4f units (mt5 order %s) @ %.5f stop %.5f target %.5f",
                 direction, asset, filled_units, pos["position_id"], result.price, stop, target)
        return pos

    def close_position(self, asset, reason, price=None, when=None):
        self._require_connection()
        symbol = self._symbol(asset)
        positions = self._mt5.positions_get(symbol=symbol) or ()
        ours = [p for p in positions if p.magic == self._magic()]
        if not ours:
            return None
        pos = ours[0]
        tick = self._mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"no tick data for {symbol} — market may be closed")
        close_type = (self._mt5.ORDER_TYPE_SELL if pos.type == self._mt5.ORDER_TYPE_BUY
                     else self._mt5.ORDER_TYPE_BUY)
        close_price = tick.bid if close_type == self._mt5.ORDER_TYPE_SELL else tick.ask
        request = {
            "action": self._mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": pos.volume,
            "type": close_type, "position": pos.ticket, "price": close_price,
            "deviation": DEFAULT_DEVIATION_POINTS, "magic": self._magic(),
            "comment": f"trading-agent close ({reason})"[:31],  # MT5 caps comment length
            "type_time": self._mt5.ORDER_TIME_GTC, "type_filling": self._filling_type(symbol),
        }
        result = self._mt5.order_send(request)
        if result is None or result.retcode != self._mt5.TRADE_RETCODE_DONE:
            code = result.retcode if result is not None else self._mt5.last_error()
            raise RuntimeError(f"close order_send failed for {asset} ({symbol}): retcode={code}")
        direction = "LONG" if pos.type == self._mt5.ORDER_TYPE_BUY else "SHORT"
        contract_size = self._contract_size(symbol)
        trade = {
            "asset": asset, "direction": direction, "entry_price": pos.price_open,
            "units": pos.volume * contract_size, "stop": pos.sl, "target": pos.tp,
            "position_id": pos.ticket, "provider": "mt5",
            "exit_price": result.price, "exit_reason": reason,
        }
        log.info("CLOSE %s %s @ %.5f (%s)", direction, asset, result.price, reason)
        return trade

    def get_positions(self):
        self._require_connection()
        positions = self._mt5.positions_get() or ()
        out = {}
        for p in positions:
            if p.magic != self._magic():
                continue  # not ours -- never manage a position this bot didn't open
            asset = self._asset_for_symbol(p.symbol)
            if asset is None:
                continue
            out[asset] = {
                "asset": asset,
                "direction": "LONG" if p.type == self._mt5.ORDER_TYPE_BUY else "SHORT",
                "entry_price": p.price_open, "units": p.volume * self._contract_size(p.symbol),
                "stop": p.sl, "target": p.tp, "position_id": p.ticket, "provider": "mt5",
            }
        return out

    def get_account_info(self):
        self._require_connection()
        info = self._mt5.account_info()
        if info is None:
            return {}
        return {"balance": info.balance, "equity": info.equity, "currency": info.currency,
               "account_id": info.login,
               "is_live": info.trade_mode == self._mt5.ACCOUNT_TRADE_MODE_REAL}

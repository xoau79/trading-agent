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

Order placement (place_order / close_position) is deliberately NotImplementedError: read-only
methods (pricing, positions, account info) are safe to leave wired up, but nothing that can
move money should exist un-tested. Wire those up deliberately, test on a demo account first,
before ever pointing this at a live account.
"""
import logging
import os
from datetime import timezone

import pandas as pd

from .base import BrokerBase

log = logging.getLogger("broker.mt5")


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

    def place_order(self, asset, direction, units, stop, target):
        self._require_connection()
        raise NotImplementedError(
            "Order placement is deliberately not implemented -- this adapter has never been "
            "tested against a real account. Wire this up on purpose (see "
            "mql5.com/en/docs/python_metatrader5's order_send() docs for the request format) "
            "and test on a demo account first, before ever pointing it at a live account.")

    def close_position(self, asset, reason, price=None, when=None):
        self._require_connection()
        raise NotImplementedError("See place_order() -- same reasoning.")

    def get_positions(self):
        self._require_connection()
        positions = self._mt5.positions_get() or ()
        return {p.symbol: p._asdict() for p in positions}

    def get_account_info(self):
        self._require_connection()
        info = self._mt5.account_info()
        if info is None:
            return {}
        return {"balance": info.balance, "equity": info.equity, "currency": info.currency}

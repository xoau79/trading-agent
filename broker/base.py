"""BrokerBase -- the interface every broker adapter implements, so the engine and dashboard
never talk to a specific broker's SDK directly. Switching config.json's "broker.provider" is
the only thing that should ever need to change to trade through a different broker.

Universal risk rules (daily loss limit, trade/position caps, consecutive-loss bench) are NOT
part of this interface -- they're enforced by broker/paper.py's pattern (can_open(),
check_daily_stop()) regardless of which adapter is actually filling orders. See
strategies/README.md and docs/ARCHITECTURE.md.

Note on signatures: paper trading has no live clock or price feed of its own, so
broker/paper.py's real methods take an explicit price/time the caller supplies (from
data_feed). A live adapter (broker/mt5_broker.py, broker/ibkr/) can source both itself. Python
doesn't enforce exact signatures on abstract methods, only that a method of the given name
exists -- this asymmetry is intentional, not an oversight.
"""
from abc import ABC, abstractmethod


class BrokerBase(ABC):
    @abstractmethod
    def connect(self):
        """Establish (or verify) the connection to the broker. Must raise on failure --
        never silently fall back to paper behavior for a live-money connection."""

    @abstractmethod
    def get_bars(self, asset, interval="1m", lookback_minutes=300):
        """Recent OHLCV bars for `asset` -- same contract as data_feed: tz-aware UTC
        DatetimeIndex, Open/High/Low/Close/Volume columns."""

    @abstractmethod
    def get_price(self, asset):
        """Latest tradable price for `asset`."""

    @abstractmethod
    def place_order(self, asset, direction, units, stop, target):
        """Submit a market order with attached stop/target. Returns a position dict."""

    @abstractmethod
    def close_position(self, asset, reason, price=None, when=None):
        """Close any open position on `asset`. Returns the closed trade dict, or None."""

    @abstractmethod
    def get_positions(self):
        """Currently open positions, keyed by asset."""

    @abstractmethod
    def get_account_info(self):
        """{'balance': ..., 'currency': ...} (and 'equity' where the broker can report it)."""

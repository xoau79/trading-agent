"""Interactive Brokers adapter -- stub, not implemented.

Reference material lives in docs/ibkr/ (40 lessons imported from the personal knowledge
vault: Python TWS API, Client Portal/Web API, and related courses). The Python TWS API is the
natural starting point -- see especially:
  docs/ibkr/python-tws-api/essential-components-of-tws-api-programs.md
  docs/ibkr/python-tws-api/defining-contracts-in-the-tws-api.md
  docs/ibkr/python-tws-api/python-placing-orders.md
  docs/ibkr/python-tws-api/python-receiving-market-data.md

Typical shape once you're ready to build this: subclass ibapi.wrapper.EWrapper +
ibapi.client.EClient (or use the friendlier `ib_insync` package), connect to a running
TWS/IB Gateway on IBKR_HOST:IBKR_PORT (see .env.example), and implement the same surface as
broker/base.py's BrokerBase.

This exists so config.json's "broker": {"provider": "ibkr"} fails loudly and clearly rather
than silently doing nothing, and so the shape of the remaining work is visible in the repo
before anyone starts it.
"""
from ..base import BrokerBase

_NOT_BUILT = (
    "IBKR adapter not built yet -- see broker/ibkr/ibkr_broker.py's module docstring and "
    "docs/ibkr/python-tws-api/ for where to start."
)


class IBKRBroker(BrokerBase):
    def __init__(self, cfg):
        self.cfg = cfg

    def connect(self):
        raise NotImplementedError(_NOT_BUILT)

    def get_bars(self, asset, interval="1m", lookback_minutes=300):
        raise NotImplementedError(_NOT_BUILT)

    def get_price(self, asset):
        raise NotImplementedError(_NOT_BUILT)

    def place_order(self, asset, direction, units, stop, target):
        raise NotImplementedError(_NOT_BUILT)

    def close_position(self, asset, reason, price=None, when=None):
        raise NotImplementedError(_NOT_BUILT)

    def get_positions(self):
        raise NotImplementedError(_NOT_BUILT)

    def get_account_info(self):
        raise NotImplementedError(_NOT_BUILT)

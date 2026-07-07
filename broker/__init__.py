"""Broker-agnostic trading interface. See broker/base.py for the contract and
docs/ARCHITECTURE.md for the design.

create_broker(cfg) is the only thing that needs to change to trade through a different
broker -- flip config.json's "broker": {"provider": ...} and everything else (engine,
strategies, dashboard) keeps working unchanged, because they only ever talk to the
BrokerBase interface. "mt5" and "ctrader" are wrapped in broker/live.py's LiveBroker facade,
which adds the universal risk ledger, the live-account safety latch, order sanity checks, and
reconciliation on top of the adapter -- see broker/live.py's docstring.
"""
from .base import BrokerBase

PROVIDERS = ("paper", "mt5", "ctrader", "ibkr")


def create_broker(cfg):
    provider = cfg.get("broker", {}).get("provider", "paper")
    if provider == "paper":
        from .paper import PaperBroker
        return PaperBroker(cfg)
    if provider == "mt5":
        from .live import LiveBroker
        from .mt5_broker import MT5Broker
        return LiveBroker(cfg, MT5Broker(cfg))
    if provider == "ctrader":
        from .ctrader.ctrader_broker import CTraderBroker
        from .live import LiveBroker
        return LiveBroker(cfg, CTraderBroker(cfg))
    if provider == "ibkr":
        from .ibkr.ibkr_broker import IBKRBroker
        return IBKRBroker(cfg)
    raise ValueError(f"unknown broker.provider {provider!r} — expected one of {PROVIDERS}")

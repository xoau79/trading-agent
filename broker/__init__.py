"""Broker-agnostic trading interface. See broker/base.py for the contract and
docs/ARCHITECTURE.md for the design.

create_broker(cfg) is the only thing that needs to change to trade through a different
broker -- flip config.json's "broker": {"provider": ...} and everything else (engine,
strategies, dashboard) keeps working unchanged, because they only ever talk to the
BrokerBase interface.
"""
from .base import BrokerBase

PROVIDERS = ("paper", "mt5", "ibkr")


def create_broker(cfg):
    provider = cfg.get("broker", {}).get("provider", "paper")
    if provider == "paper":
        from .paper import PaperBroker
        return PaperBroker(cfg)
    if provider == "mt5":
        from .mt5_broker import MT5Broker
        return MT5Broker(cfg)
    if provider == "ibkr":
        from .ibkr.ibkr_broker import IBKRBroker
        return IBKRBroker(cfg)
    raise ValueError(f"unknown broker.provider {provider!r} — expected one of {PROVIDERS}")

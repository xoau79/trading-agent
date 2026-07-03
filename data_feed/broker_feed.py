"""Price data sourced from whichever broker is currently connected (config.json's
"broker.provider" != "paper"). This is the intended end state for live trading -- one
connection, no separate data vendor dependency, and prices that match what the broker will
actually fill you at.

Inert while broker.provider == "paper" (the default): data_feed.get_recent_bars() keeps using
Yahoo/Twelve Data exactly as it does today, and nothing in this module is called. Nothing
changes about current behavior until a live broker is deliberately connected.
"""


def get_recent_bars(broker, asset, interval="1m"):
    return broker.get_bars(asset, interval=interval)


def get_price(broker, asset):
    return broker.get_price(asset)

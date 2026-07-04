"""The strategy library registry. bot.py's Engine looks up each session's assigned strategy
by name (config.json's sessions.<name>.strategy, defaults to "orb") through get_strategy() --
this is the one place that needs to know every strategy that exists.
"""
from .orb.strategy import ORBStrategy

STRATEGIES = {
    "orb": ORBStrategy,
}


def get_strategy(name):
    try:
        return STRATEGIES[name]
    except KeyError:
        raise ValueError(
            f"unknown strategy {name!r} — expected one of {sorted(STRATEGIES)}. "
            "Register new strategies in strategies/__init__.py's STRATEGIES dict.")

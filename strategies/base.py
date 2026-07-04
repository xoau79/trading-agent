"""StrategyBase -- the interface every strategy in the library implements, plus the metadata
each one must declare about itself. See strategies/README.md for the full pattern and how
this differs from the universal rules enforced in broker/paper.py.

A strategy is a per-asset state machine: one instance per traded asset per session, fed bars
once per loop iteration, returning a signal (or None) when its own entry rule fires. It owns
ONLY its own entry/exit logic -- position sizing, universal risk caps, and order execution
are the engine/broker's job, not the strategy's.
"""
from abc import ABC, abstractmethod


class StrategyBase(ABC):
    # ---- metadata every strategy must declare (used by the dashboard, docs, and the
    # strategies/README.md checklist -- not enforced by Python, but expected by convention) --
    name = "unnamed-strategy"
    description = ""
    applicable_assets = ()      # e.g. ("GOLD", "NQ", "ES")
    applicable_sessions = ()    # e.g. ("asia", "newyork")

    def __init__(self, asset_key, cfg):
        """cfg is the full loaded config.json. Read your own parameters from wherever your
        strategy's README says they live (today: config.json's own top-level block, since
        this repo has exactly one strategy live -- see strategies/README.md's config-sharing
        note for what changes once a second strategy exists)."""
        self.asset = asset_key
        self.cfg = cfg

    @abstractmethod
    def on_bars(self, bars, session_open_utc, atr_value, in_position):
        """Called once per loop with all session bars so far. Returns a signal dict
        {direction, entry, stop, target, bar_time} or None. Must never return a signal while
        in_position is True -- the engine (not the strategy) tracks open positions."""

    @abstractmethod
    def snapshot(self):
        """A small JSON-safe dict describing current state for the dashboard (stage, any
        filter reason, etc). Whatever your strategy needs to show its work."""

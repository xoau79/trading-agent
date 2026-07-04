"""<Strategy Name> — one-line summary of the edge.

Delete this docstring and replace it with your own explanation of the rules, mirroring
strategies/orb/strategy.py's style: what defines an entry, what defines an exit, and what
stage machine (if any) the asset moves through.
"""
import logging

from strategies.base import StrategyBase

log = logging.getLogger("strategy.TEMPLATE")  # rename to your strategy's name


class TemplateStrategy(StrategyBase):
    # ---- required metadata -- fill all of these in, don't leave placeholders ----
    name = "TEMPLATE"                  # short, lowercase, matches your folder name
    description = "TODO: one sentence describing the edge"
    applicable_assets = ()             # e.g. ("GOLD",)
    applicable_sessions = ()           # e.g. ("newyork",)

    def __init__(self, asset_key, cfg):
        super().__init__(asset_key, cfg)
        # TODO: read your own parameters. See strategies/README.md's config-sharing note --
        # for a genuinely new strategy, prefer your own strategies/<name>/strategy.json over
        # config.json's shared "strategy" block (that block is ORB's).
        self.stage = "TODO"

    def on_bars(self, bars, session_open_utc, atr_value, in_position):
        """Called once per loop with all session bars so far.

        Must return None while in_position is True -- the engine tracks open positions, not
        the strategy. Return a signal dict when (and only when) your entry rule fires:
            {"direction": "LONG" | "SHORT", "entry": <price>, "stop": <price>,
             "target": <price>, "bar_time": <the bar's timestamp>}
        """
        raise NotImplementedError("TODO: implement your entry rule")

    def snapshot(self):
        """Small JSON-safe dict for the dashboard. At minimum, expose whatever stage/state a
        human would want to see to understand what this strategy is currently doing."""
        return {"stage": self.stage}

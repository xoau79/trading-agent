"""Opening Range Breakout (ORB) strategy — 100% mechanical, per-asset state machine.

Rules (Zarattini & Aziz style) -- see README.md in this folder for the full plain-language
spec (entry, exit, RR, risk%, filters). Short version:
  1. The first `opening_range_minutes` of the session define the range high/low.
  2. Volatility filter: range must be range_atr_min..range_atr_max x the 15-minute ATR, else
     the asset is skipped for the whole session.
  3. A 1-minute CLOSE above the range high signals LONG; below the low, SHORT.
  4. Stop = far side of the range. Target = target_r_multiple x R. Time exit at session close.
  5. After an exit, a new signal is only armed once price closes back INSIDE the range
     (prevents instantly chasing the same move).

Stages an asset moves through:
  building_range -> hunting -> in_position -> hunting (rearmed) ... -> done
  (or 'filtered' if the volatility filter rejects the day)

Behaviorally identical to the original root-level strategy.py this replaced -- moved into the
library, not rewritten. Parameters still read from config.json's "strategy" block (that's
also where the agent's bounded auto-tuning writes overrides -- see agent.py's whitelist) and
"risk" block for risk_per_trade_pct.
"""
import logging

from strategies.base import StrategyBase

log = logging.getLogger("strategy.orb")


class ORBStrategy(StrategyBase):
    name = "orb"
    description = "Opening Range Breakout: trade a 1-minute close beyond the first 15 minutes' range."
    applicable_assets = ("GOLD", "NQ", "ES")
    applicable_sessions = ("asia", "newyork")
    target_r_multiple = None       # set from config.json in __init__ -- see README's config note
    risk_per_trade_pct = None      # set from config.json in __init__ -- see README's config note

    def __init__(self, asset_key, cfg):
        super().__init__(asset_key, cfg)
        self.scfg = cfg["strategy"]
        self.target_r_multiple = self.scfg["target_r_multiple"]
        self.risk_per_trade_pct = cfg["risk"]["risk_per_trade_pct"]
        self.stage = "building_range"
        self.range_high = None
        self.range_low = None
        self.range_atr_ratio = None
        self.filter_reason = None
        self.armed = True           # may a breakout signal fire?
        self.last_signal_bar = None

    # -- called once per loop with all session bars so far ------------------
    def on_bars(self, bars, session_open_utc, atr_value, in_position):
        """Returns a signal dict {direction, entry, stop, target} or None."""
        if bars is None or bars.empty:
            return None

        range_end = session_open_utc + self._range_delta()

        if self.stage == "building_range":
            if bars.index[-1] < range_end:
                return None  # still inside the opening-range window
            self._set_range(bars, session_open_utc, range_end, atr_value)
            if self.stage != "hunting":
                return None

        if self.stage in ("filtered", "done"):
            return None

        if in_position:
            return None

        # only act on completed bars after the range window
        post = bars[bars.index >= range_end]
        if post.empty:
            return None
        last_time = post.index[-1]
        if self.last_signal_bar is not None and last_time <= self.last_signal_bar:
            return None
        close = float(post["Close"].iloc[-1])

        # re-arm once price closes back inside the range after an exit
        if not self.armed:
            if self.range_low < close < self.range_high:
                self.armed = True
                log.info("%s re-armed (price back inside range)", self.asset)
            return None

        if close > self.range_high:
            return self._signal("LONG", close, last_time)
        if close < self.range_low:
            return self._signal("SHORT", close, last_time)
        return None

    def _signal(self, direction, close, bar_time):
        stop = self.range_low if direction == "LONG" else self.range_high
        risk = abs(close - stop)
        if risk <= 0:
            return None
        target = (close + self.target_r_multiple * risk if direction == "LONG"
                  else close - self.target_r_multiple * risk)
        self.last_signal_bar = bar_time
        self.armed = False  # will re-arm only after a close back inside the range
        return {"direction": direction, "entry": close, "stop": stop,
                "target": target, "bar_time": bar_time}

    def _set_range(self, bars, open_utc, range_end, atr_value):
        window = bars[(bars.index >= open_utc) & (bars.index < range_end)]
        if len(window) < 3:
            self.stage = "filtered"
            self.filter_reason = "not enough bars in the opening-range window (thin market)"
            return
        self.range_high = round(float(window["High"].max()), 4)
        self.range_low = round(float(window["Low"].min()), 4)
        rng = self.range_high - self.range_low

        if atr_value is None or atr_value <= 0:
            self.stage = "filtered"
            self.filter_reason = "ATR unavailable — cannot validate range size"
            return
        ratio = rng / atr_value
        self.range_atr_ratio = round(ratio, 2)
        if ratio < self.scfg["range_atr_min"]:
            self.stage = "filtered"
            self.filter_reason = (f"opening range too small ({ratio:.2f}x ATR) — "
                                  "dead market, breakouts unreliable")
        elif ratio > self.scfg["range_atr_max"]:
            self.stage = "filtered"
            self.filter_reason = (f"opening range too large ({ratio:.2f}x ATR) — "
                                  "news-spike conditions, stop would be oversized")
        else:
            self.stage = "hunting"
            log.info("%s range set: %.2f-%.2f (%.2fx ATR)",
                     self.asset, self.range_low, self.range_high, ratio)

    def _range_delta(self):
        from datetime import timedelta
        return timedelta(minutes=self.scfg["opening_range_minutes"])

    def snapshot(self):
        return {"stage": self.stage, "range_high": self.range_high,
                "range_low": self.range_low, "range_atr_ratio": self.range_atr_ratio,
                "filter_reason": self.filter_reason, "armed": self.armed}

"""Price data feed — provider-agnostic entry point.

get_recent_bars() tries Yahoo Finance first (data_feed.yahoo, hardened with a hard timeout —
see yahoo.py's docstring for why that matters). If Yahoo's bars are missing or stale and a
Twelve Data symbol + TWELVEDATA_API_KEY are available, it falls back to Twelve Data
(data_feed.twelvedata). Once a live broker is connected (see broker/), price data will come
from data_feed.broker_feed instead of either third-party source — not needed while paper
trading.

All bar DataFrames returned here have a tz-aware UTC DatetimeIndex and columns
Open, High, Low, Close, Volume — same contract regardless of provider.
"""
import logging
import os
from datetime import datetime, timezone

from . import twelvedata as td
from . import yahoo
from ._common import STALE_LIMIT_MIN, _normalize, atr_15m, is_stale  # noqa: F401 (re-exported)

log = logging.getLogger("data_feed")


def get_recent_bars(ticker, period="5d", interval="1m", now_utc=None, twelvedata_symbol=None):
    """Latest bars for live trading. Returns None if every source failed."""
    bars = yahoo.get_recent_bars(ticker, period=period, interval=interval)
    now_utc = now_utc or datetime.now(timezone.utc)
    if bars is not None and not is_stale(bars, now_utc):
        return bars
    if twelvedata_symbol and os.getenv("TWELVEDATA_API_KEY"):
        log.info("Yahoo bars missing/stale for %s — trying Twelve Data (%s)",
                 ticker, twelvedata_symbol)
        fallback = td.get_recent_bars(twelvedata_symbol)
        if fallback is not None and not is_stale(fallback, now_utc):
            return fallback
    return bars  # possibly None/stale — callers already handle that (data-dropout standdown)


def get_bars_between(ticker, start_utc, end_utc, interval="1m"):
    """Historical bars for replay mode. Yahoo-only — the ~30 day free-tier limit is the
    honest cap for backtesting; Twelve Data's free tier isn't a meaningful upgrade here."""
    return yahoo.get_bars_between(ticker, start_utc, end_utc, interval=interval)

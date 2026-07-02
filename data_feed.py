"""Price data feed — wraps yfinance and normalizes everything to UTC.

All bar DataFrames returned here have a tz-aware UTC DatetimeIndex and
plain columns: Open, High, Low, Close, Volume.
"""
import logging

import pandas as pd
import yfinance as yf

log = logging.getLogger("data_feed")

STALE_LIMIT_MIN = 10  # if the newest bar is older than this, the feed is considered stale


def _normalize(df):
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.tz_convert("UTC") if df.index.tz is not None else df.tz_localize("UTC")
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
    return df.sort_index()


def get_recent_bars(ticker, period="5d", interval="1m"):
    """Latest bars for live trading. Returns None on failure."""
    try:
        df = yf.download(ticker, period=period, interval=interval,
                         progress=False, auto_adjust=True)
        return _normalize(df)
    except Exception as e:
        log.warning("fetch failed for %s: %s", ticker, e)
        return None


def get_bars_between(ticker, start_utc, end_utc, interval="1m"):
    """Historical bars for replay mode. Yahoo only keeps ~30 days of 1m data."""
    try:
        df = yf.download(ticker, start=start_utc, end=end_utc, interval=interval,
                         progress=False, auto_adjust=True)
        return _normalize(df)
    except Exception as e:
        log.warning("history fetch failed for %s: %s", ticker, e)
        return None


def is_stale(bars, now_utc):
    """True when the feed stopped updating (holiday, outage, market closed)."""
    if bars is None or bars.empty:
        return True
    age_min = (now_utc - bars.index[-1]).total_seconds() / 60.0
    return age_min > STALE_LIMIT_MIN


def atr_15m(bars_1m, period=14):
    """ATR computed on 15-minute bars resampled from 1-minute data.

    Used by the volatility filter: the opening range is compared against
    this 'normal 15-minute movement' figure.
    """
    if bars_1m is None or len(bars_1m) < period * 15:
        return None
    o = bars_1m.resample("15min").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
    if len(o) < period + 1:
        return None
    prev_close = o["Close"].shift(1)
    tr = pd.concat([o["High"] - o["Low"],
                    (o["High"] - prev_close).abs(),
                    (o["Low"] - prev_close).abs()], axis=1).max(axis=1)
    val = tr.rolling(period).mean().iloc[-1]
    return float(val) if pd.notna(val) else None

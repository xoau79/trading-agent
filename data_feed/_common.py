"""Shared, provider-agnostic helpers used by every price-data source."""
import pandas as pd

STALE_LIMIT_MIN = 10  # if the newest bar is older than this, the feed is considered stale


def _normalize(df):
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.tz_convert("UTC") if df.index.tz is not None else df.tz_localize("UTC")
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
    return df.sort_index()


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

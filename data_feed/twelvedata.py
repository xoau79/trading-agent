"""Twelve Data fallback price feed — used automatically by data_feed.get_recent_bars() when
Yahoo Finance bars are missing or stale and TWELVEDATA_API_KEY is set in .env (see
.env.example). Inactive with no code changes required if the key isn't set — the bot behaves
exactly as it did before this module existed.

Free tier: 800 requests/day (twelvedata.com/pricing) — fine as an occasional fallback, not
enough to replace Yahoo as the primary feed for a whole session's worth of 45-second polling.

Honesty note: futures symbols (gold/NQ/ES) are not reliably available on Twelve Data's free
tier. Only map an asset to a "twelvedata" symbol in config.json if your plan actually
supports it (spot XAU/USD gold works on the free tier and is close enough to GC=F as a
fallback proxy) — an asset with no mapping simply has no fallback, which is honest and safe,
not a broken promise.
"""
import json
import logging
import os
import urllib.parse
import urllib.request

import pandas as pd

from ._common import _normalize

log = logging.getLogger("data_feed.twelvedata")

BASE_URL = "https://api.twelvedata.com/time_series"
TIMEOUT_SEC = 15


def get_recent_bars(symbol, interval="1min", outputsize=300):
    api_key = os.getenv("TWELVEDATA_API_KEY")
    if not api_key or not symbol:
        return None
    params = {"symbol": symbol, "interval": interval, "outputsize": outputsize,
              "apikey": api_key, "timezone": "UTC", "format": "JSON"}
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TradingAgent/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as r:
            payload = json.loads(r.read().decode())
    except Exception as e:
        log.warning("Twelve Data fetch failed for %s: %s", symbol, e)
        return None
    if not isinstance(payload, dict) or "values" not in payload:
        log.warning("Twelve Data error for %s: %s", symbol,
                    payload.get("message", payload) if isinstance(payload, dict) else payload)
        return None
    df = pd.DataFrame(payload["values"])
    if df.empty:
        return None
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df = df.set_index("datetime").sort_index()
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                            "close": "Close", "volume": "Volume"})
    for col in ("Open", "High", "Low", "Close", "Volume"):
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return _normalize(df)

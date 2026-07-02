"""Yahoo Finance price data — hardened against the failure mode that hung the bot for 24h+
on 2026-07-02: yf.download() has no reliable built-in timeout, so a stalled connection could
block the single-threaded trading loop forever with no exception ever raised.

Every call here runs in a daemon thread with a hard wall-clock timeout. If Yahoo doesn't
answer in time, the call is abandoned (not force-killed — Python can't do that to a thread)
and treated as a failure. Because the thread is a daemon, an abandoned call can never block
process exit, which is the actual mechanism that produced the hang: the old code's blocking
call had nothing bounding it, all the way down to the OS socket.
"""
import logging
import threading
import time

import yfinance as yf

from ._common import _normalize

log = logging.getLogger("data_feed.yahoo")

CALL_TIMEOUT_SEC = 15
MAX_RETRIES = 1
RETRY_BACKOFF_SEC = 2


def _with_timeout(fn, timeout):
    result = {}

    def target():
        try:
            result["value"] = fn()
        except Exception as e:
            result["error"] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        log.warning("call timed out after %ss — abandoning (bounded loop keeps running)", timeout)
        return None
    if "error" in result:
        raise result["error"]
    return result.get("value")


def _download(ticker, **kwargs):
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            df = _with_timeout(
                lambda: yf.download(ticker, progress=False, auto_adjust=True, **kwargs),
                CALL_TIMEOUT_SEC)
            if df is not None:
                return df
        except Exception as e:
            log.warning("fetch failed for %s (attempt %d/%d): %s",
                        ticker, attempt, MAX_RETRIES + 1, e)
        if attempt <= MAX_RETRIES:
            time.sleep(RETRY_BACKOFF_SEC)
    return None


def get_recent_bars(ticker, period="5d", interval="1m"):
    """Latest bars for live trading. Returns None on failure/timeout."""
    return _normalize(_download(ticker, period=period, interval=interval))


def get_bars_between(ticker, start_utc, end_utc, interval="1m"):
    """Historical bars for replay mode. Yahoo only keeps ~30 days of 1m data."""
    return _normalize(_download(ticker, start=start_utc, end=end_utc, interval=interval))

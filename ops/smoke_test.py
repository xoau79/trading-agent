"""Smoke test: verify every external feed the trading bot depends on.

Run:  python ops/smoke_test.py
Run:  python ops/smoke_test.py --discord   # also post a Discord alert on any FAIL
Each section prints PASS or FAIL with details. The bot is only viable if
the price feed passes; the others have graceful fallbacks.
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))  # so `python ops/smoke_test.py` can import ops.notify

RESULTS = []


def check(name, fn):
    try:
        detail = fn()
        RESULTS.append((name, True, detail))
        print(f"PASS  {name}: {detail}")
    except Exception as e:
        RESULTS.append((name, False, str(e)))
        print(f"FAIL  {name}: {type(e).__name__}: {e}")


# --- 1. Yahoo Finance 1-minute bars -----------------------------------------
def test_yahoo():
    import yfinance as yf
    details = []
    for ticker in ("GC=F", "NQ=F", "ES=F"):
        df = yf.download(ticker, period="1d", interval="1m", progress=False, auto_adjust=True)
        if df is None or df.empty:
            raise RuntimeError(f"no data for {ticker}")
        last = df.index[-1]
        details.append(f"{ticker} {len(df)} bars (latest {last})")
    return "; ".join(details)


# --- 2. ForexFactory economic calendar ---------------------------------------
def test_forexfactory():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        events = json.loads(r.read().decode())
    high = [e for e in events if e.get("impact") == "High" and e.get("country") == "USD"]
    sample = high[0]["title"] if high else "(none this week)"
    return f"{len(events)} events this week, {len(high)} high-impact USD (e.g. {sample})"


# --- 3. News headlines via RSS ------------------------------------------------
def test_rss():
    import feedparser
    feed = feedparser.parse("https://www.cnbc.com/id/100003114/device/rss/rss.html")
    if not feed.entries:
        raise RuntimeError("no entries from CNBC RSS")
    return f"{len(feed.entries)} headlines, latest: {feed.entries[0].title[:70]}"


# --- 4. TradingView technical ratings ----------------------------------------
def test_tradingview():
    from tradingview_ta import TA_Handler, Interval
    combos = [
        ("gold", "XAUUSD", "OANDA", "forex"),
        ("nasdaq-fut", "NQ1!", "CME_MINI", "america"),
        ("sp500-fut", "ES1!", "CME_MINI", "america"),
        ("nasdaq-proxy", "QQQ", "NASDAQ", "america"),
        ("sp500-proxy", "SPY", "AMEX", "america"),
    ]
    out = []
    for label, symbol, exchange, screener in combos:
        try:
            h = TA_Handler(symbol=symbol, exchange=exchange, screener=screener,
                           interval=Interval.INTERVAL_15_MINUTES)
            rec = h.get_analysis().summary["RECOMMENDATION"]
            out.append(f"{label}={rec}")
        except Exception as e:
            out.append(f"{label}=ERROR({e})")
    if all("ERROR" in o for o in out):
        raise RuntimeError("; ".join(out))
    return "; ".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--discord", action="store_true",
                    help="post a summary to Discord if any feed FAILs")
    ap.add_argument("--dry-run", action="store_true",
                    help="with --discord, print instead of posting (for testing)")
    args = ap.parse_args()

    check("Yahoo 1-min bars", test_yahoo)
    check("ForexFactory calendar", test_forexfactory)
    check("CNBC RSS headlines", test_rss)
    check("TradingView ratings", test_tradingview)

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} feeds OK")

    if failed and args.discord:
        from ops.notify import discord_post
        lines = [f"⚠️ **Smoke test**: {len(failed)}/{len(RESULTS)} feed(s) failed:"]
        lines += [f"- {name}: {detail}" for name, ok, detail in failed]
        discord_post("\n".join(lines), dry_run=args.dry_run)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

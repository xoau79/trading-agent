"""Broker-vs-Yahoo price feed parity check -- the manual verification docs/ctrader_setup.md's
"Known limitations" section already asks for ("cTrader price/volume scaling was verified
against Spotware's published proto source but not against a live account... compare its
printed price against a real gold price yourself"), automated and posted to Discord instead of
left as an eyeball-only step.

For each asset with a symbol configured for the active broker.provider, fetches the latest
bars from both the broker feed (data_feed/broker_feed.py, what the bot will actually trade
against once connected) and Yahoo Finance (data_feed/yahoo.py, the paper-trading default), and
reports the price delta, bar coverage, and staleness of each. A large delta or a stale broker
feed is exactly the kind of symbol-mapping or scaling mistake this is meant to catch before a
supervised demo session, per docs/ctrader_setup.md's go-live checklist.

Read-only: connects to the broker to fetch bars/price only -- never places an order, never
touches config.json, .env, or the live-trading confirmation latch.

Usage:
    python ops/feed_parity.py
    python ops/feed_parity.py --dry-run
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))  # so `python ops/feed_parity.py` can import the repo's modules

import data_feed  # noqa: E402
from broker import create_broker  # noqa: E402
from data_feed import broker_feed  # noqa: E402
from ops.notify import discord_post  # noqa: E402


def _bar_summary(bars, now_utc):
    if bars is None or bars.empty:
        return None
    last = bars.iloc[-1]
    return {
        "count": len(bars),
        "first": bars.index[0], "last": bars.index[-1],
        "close": float(last["Close"]),
        "stale": data_feed.is_stale(bars, now_utc),
    }


def check_asset(cfg, broker, asset, now_utc):
    acfg = cfg["assets"][asset]
    provider = cfg.get("broker", {}).get("provider", "paper")
    symbol = acfg.get(provider)
    if not symbol:
        return (f"- **{asset}**: no `{provider}` symbol configured in config.json yet — "
               f"see `{acfg.get(provider + '_note', 'docs/ctrader_setup.md')}`")

    try:
        broker_bars = broker_feed.get_recent_bars(broker, asset)
    except Exception as e:
        return f"- **{asset}** (`{symbol}`): broker feed error — {e}"
    b = _bar_summary(broker_bars, now_utc)
    if b is None:
        return f"- **{asset}** (`{symbol}`): broker returned no bars"

    yahoo_bars = data_feed.get_recent_bars(acfg["yahoo"], now_utc=now_utc,
                                          twelvedata_symbol=acfg.get("twelvedata"))
    y = _bar_summary(yahoo_bars, now_utc)
    if y is None:
        return (f"- **{asset}** (`{symbol}`): broker close {b['close']:.4f} "
               f"({b['count']} bars{', STALE' if b['stale'] else ''}) — no Yahoo bars to "
               "compare against")

    delta_pct = abs(b["close"] - y["close"]) / y["close"] * 100 if y["close"] else None
    flag = ""
    if delta_pct is not None and delta_pct > 1.0:
        flag = " ⚠️ large delta — check the symbol mapping and price scaling"
    if b["stale"]:
        flag += " ⚠️ broker feed is stale"
    return (f"- **{asset}** (`{symbol}`): broker {b['close']:.4f} vs Yahoo {y['close']:.4f} "
           f"({delta_pct:.2f}% delta, {b['count']}/{y['count']} bars){flag}")


def build_report(cfg, now_utc=None):
    now_utc = now_utc or datetime.now(timezone.utc)
    provider = cfg.get("broker", {}).get("provider", "paper")
    if provider == "paper":
        return ("**Feed parity check**: `broker.provider` is `paper` — nothing to compare "
               "against yet. Run this again once a demo cTrader/MT5 account is connected "
               "(see docs/ctrader_setup.md).")

    lines = [f"**Feed parity check** — provider `{provider}`"]
    try:
        broker = create_broker(cfg)
        broker.connect()
    except Exception as e:
        lines.append(f"⚠️ Could not connect to the broker: {e}")
        return "\n".join(lines)

    for asset in cfg.get("assets", {}):
        lines.append(check_asset(cfg, broker, asset, now_utc))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=str(BASE), help="repo root (override for testing)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import json
    cfg = json.loads((Path(args.base) / "config.json").read_text(encoding="utf-8"))
    report = build_report(cfg)
    print(report)
    discord_post(report, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

"""cTrader connectivity smoke test: verifies everything the bot needs from a cTrader account
BEFORE you ever flip config.json's broker.provider to "ctrader". Read-only -- never places an
order. Run this after `python ops/ctrader_auth.py` has produced ctrader_tokens.json and
you've filled in .env's CTRADER_ACCOUNT_ID.

Usage:
    python ops/ctrader_smoke_test.py              # full check against the configured account
    python ops/ctrader_smoke_test.py --symbols    # dump every symbol name on this account
                                                   # (use this to fill in config.json's
                                                   # assets.*.ctrader fields correctly)

See docs/ctrader_setup.md for the full walkthrough this fits into.
"""
import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BASE / ".env")

from broker.ctrader.ctrader_broker import CTraderBroker  # noqa: E402

RESULTS = []


def check(name, fn):
    try:
        detail = fn()
        RESULTS.append((name, True, detail))
        print(f"PASS  {name}: {detail}")
        return True
    except Exception as e:
        RESULTS.append((name, False, str(e)))
        print(f"FAIL  {name}: {type(e).__name__}: {e}")
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", action="store_true",
                    help="just dump every symbol name available on this account and exit "
                    "(use this to fill in config.json's assets.*.ctrader fields)")
    args = ap.parse_args()

    cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))

    broker = CTraderBroker(cfg)
    if not check("Connect + authenticate", lambda: _connect(broker)):
        print("\nCannot continue without a connection — check .env's CTRADER_CLIENT_ID / "
             "CTRADER_CLIENT_SECRET / CTRADER_ACCOUNT_ID and that "
             "`python ops/ctrader_auth.py` has been run.")
        sys.exit(1)

    if args.symbols:
        names = broker.list_symbol_names()
        print(f"\n{len(names)} symbols available on this account:")
        for n in names:
            print(f"  {n}")
        return

    check("Account info", lambda: _account_info(broker))
    check("Configured symbols resolve", lambda: _symbols_resolved(cfg, broker))
    check("Trendbars (GOLD, 60x M1)", lambda: _trendbars(broker))
    check("Live spot subscription (5s)", lambda: _spots(broker))

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks OK")
    sys.exit(1 if failed else 0)


def _connect(broker):
    broker.connect()
    return f"account {broker._account_id} ({'LIVE' if broker.is_live_account() else 'demo'})"


def _account_info(broker):
    info = broker.get_account_info()
    return (f"balance={info['balance']} {info['currency']}, equity={info['equity']}, "
           f"is_live={info['is_live']}")


def _symbols_resolved(cfg, broker):
    names = [f"{a}={cfg['assets'][a]['ctrader']}" for a in cfg["assets"] if cfg["assets"][a].get("ctrader")]
    return f"resolved: {', '.join(names)}" if names else "no assets have a 'ctrader' symbol configured yet"


def _trendbars(broker):
    asset = "GOLD" if cfg_has_asset("GOLD", broker) else next(iter(broker._symbols_by_asset))
    bars = broker.get_bars(asset, lookback_minutes=60)
    if bars is None or bars.empty:
        raise RuntimeError(f"no trendbars returned for {asset}")
    last = bars.iloc[-1]
    return (f"{len(bars)} bars, last close={last['Close']:.4f} at {bars.index[-1]} — sanity "
           "check this against a live gold price yourself (this script can't reach Yahoo "
           "to cross-check automatically)")


def cfg_has_asset(asset, broker):
    return asset in broker._symbols_by_asset


def _spots(broker):
    import time
    asset = next(iter(broker._symbols_by_asset), None)
    if asset is None:
        raise RuntimeError("no symbols resolved to subscribe to")
    seen = []
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        px = broker.get_price(asset)
        if px is not None:
            seen.append(px)
        time.sleep(0.5)
    if not seen:
        raise RuntimeError(f"no spot price observed for {asset} in 5s")
    return f"{asset} last price seen: {seen[-1]}"


if __name__ == "__main__":
    main()

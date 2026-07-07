"""Explicitly opt-in demo order test, shared by the cTrader and MT5 adapters: places one
small market order through the FULL broker/live.py LiveBroker path (sizing, sanity checks,
the real adapter's place_order), confirms it shows up in get_positions(), then closes it and
prints the resulting trade dict. This is the "did the whole order pipeline actually work"
check that ops/ctrader_smoke_test.py and ops/mt5_smoke_test.py (both read-only) can't cover.

REFUSES to run against a live (real-money) account outright -- demo only, always.

Usage:
    python ops/live_order_test.py --provider ctrader --yes
    python ops/live_order_test.py --provider mt5 --asset GOLD --yes
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BASE / ".env")

import broker as broker_pkg  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", required=True, choices=["ctrader", "mt5"])
    ap.add_argument("--asset", default="GOLD")
    ap.add_argument("--yes", action="store_true",
                    help="required -- confirms you understand this places a real demo order")
    args = ap.parse_args()

    if not args.yes:
        print("This places a REAL order on your DEMO account (tiny size, wide stop/target, "
             "closed again immediately after). Re-run with --yes once you're ready.")
        sys.exit(1)

    cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    cfg["broker"]["provider"] = args.provider
    live_broker = broker_pkg.create_broker(cfg)
    live_broker.connect()

    if live_broker.adapter.is_live_account():
        print("REFUSING: this account is LIVE (real money). This script only ever runs "
             "against a demo account — check .env's *_ACCOUNT_ID / MT5_LOGIN.")
        sys.exit(1)

    asset = args.asset
    price = live_broker.get_price(asset)
    if price is None:
        print(f"Could not get a price for {asset} — aborting.")
        sys.exit(1)

    # A deliberately wide stop keeps the risk-sized position tiny (units = risk_usd / stop_dist).
    stop_dist_pct = 10.0
    stop = price * (1 - stop_dist_pct / 100)
    target = price * (1 + stop_dist_pct / 200)
    signal = {"direction": "LONG", "entry": price, "stop": stop, "target": target}
    now = datetime.now(timezone.utc)

    print(f"Placing a tiny LONG on {asset} @ ~{price:.4f} (stop {stop:.4f}, target {target:.4f})...")
    pos = live_broker.open_position(asset, signal, now, {})
    if pos is None:
        print("Order was refused before reaching the broker — sizing may have rounded to "
             f"zero at this symbol's minimum tradable size, or a sanity check failed. "
             f"last_order_error={getattr(live_broker, 'last_order_error', None)}")
        sys.exit(1)
    print(f"Opened: {pos}")

    positions = live_broker.get_positions()
    print(f"Broker now shows: {positions.get(asset)}")
    if asset not in positions:
        print(f"WARNING: {asset} wasn't found in get_positions() right after opening — "
             "check the adapter's label/magic filtering.")

    print("Closing it now...")
    trade = live_broker.close_position(asset, price, "ops_test_close", datetime.now(timezone.utc))
    print(f"Closed: {trade}")


if __name__ == "__main__":
    main()

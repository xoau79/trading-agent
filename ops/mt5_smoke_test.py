"""MT5 connectivity smoke test: verifies everything the bot needs from a locally-running MT5
terminal BEFORE you ever flip config.json's broker.provider to "mt5". Read-only -- never
places an order. Windows-only (same constraint as broker/mt5_broker.py itself); run this on
the machine that will actually run the bot, with the MT5 terminal open and logged in.

Usage:
    python ops/mt5_smoke_test.py

See broker/README.md and docs/ctrader_setup.md's sibling MT5 notes for the full walkthrough.
"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BASE / ".env")

from broker.mt5_broker import MT5Broker  # noqa: E402

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
    cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    broker = MT5Broker(cfg)

    if not check("Connect to terminal", lambda: _connect(broker)):
        print("\nCannot continue — make sure the MT5 terminal is running, logged in, has "
             "algo trading enabled (Tools > Options > Expert Advisors), and that .env's "
             "MT5_LOGIN/MT5_PASSWORD/MT5_SERVER match.")
        sys.exit(1)

    check("Account info", lambda: _account_info(broker))
    check("Configured symbols resolve", lambda: _symbols(cfg, broker))
    for asset, acfg in cfg["assets"].items():
        if acfg.get("mt5"):
            check(f"Bars ({asset})", lambda a=asset: _bars(broker, a))
            check(f"Price ({asset})", lambda a=asset: _price(broker, a))

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks OK")
    sys.exit(1 if failed else 0)


def _connect(broker):
    broker.connect()
    return f"login={broker._mt5.account_info().login} ({'LIVE' if broker.is_live_account() else 'demo'})"


def _account_info(broker):
    info = broker.get_account_info()
    return f"balance={info['balance']} {info['currency']}, equity={info['equity']}"


def _symbols(cfg, broker):
    names = []
    for asset, acfg in cfg["assets"].items():
        symbol = acfg.get("mt5")
        if not symbol:
            continue
        info = broker._mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(f"{asset}: symbol {symbol!r} not found in Market Watch — add "
                              "it there (right-click Market Watch > Symbols) or check spelling")
        names.append(f"{asset}={symbol} (digits={info.digits}, "
                    f"volume_min={info.volume_min}, volume_step={info.volume_step})")
    if not names:
        return "no assets have an 'mt5' symbol configured yet"
    return "; ".join(names)


def _bars(broker, asset):
    bars = broker.get_bars(asset, lookback_minutes=60)
    if bars is None or bars.empty:
        raise RuntimeError("no bars returned")
    return f"{len(bars)} bars, last close={bars['Close'].iloc[-1]:.4f} at {bars.index[-1]}"


def _price(broker, asset):
    px = broker.get_price(asset)
    if px is None:
        raise RuntimeError("no price returned")
    return f"{px}"


if __name__ == "__main__":
    main()

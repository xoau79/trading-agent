"""Shared, network-free test fixtures: a minimal config and a synthetic ORB session's
1-minute bars, built by hand so every test in this suite runs deterministically without
Yahoo/TwelveData/TradingView network access (this sandbox has none of that -- see
docs/ARCHITECTURE.md's testing notes)."""
from datetime import datetime, timedelta, timezone

import pandas as pd


def make_cfg(**overrides):
    cfg = {
        "broker": {"provider": "paper", "provider_options": ["paper", "mt5", "ctrader", "ibkr"]},
        "account": {"starting_balance": 10000.0},
        "risk": {
            "risk_per_trade_pct": 1.0,
            "daily_loss_limit_pct": 3.0,
            "max_trades_per_session": 4,
            "max_trades_per_day": 8,
            "max_concurrent_positions": 2,
            "max_notional_leverage": 20,
            "consecutive_losses_to_bench": 4,
        },
        "strategy": {
            "opening_range_minutes": 15,
            "target_r_multiple": 2.0,
            "atr_period": 1,
            "range_atr_min": 0.3,
            "range_atr_max": 3.0,
            "slippage_pct": 0.0,
            "tv_confluence_enabled": True,
            "entry_cutoff_minutes": 0,
        },
        "live_trading": {
            "enabled": False,
            "order_label": "trading-agent",
            "max_units_per_asset": {"GOLD": 50, "NQ": 20, "ES": 20},
            "min_stop_distance_pct": 0.03,
            "max_stop_distance_pct": 5.0,
            "max_total_drawdown_pct": 10.0,
            "on_unmanaged_positions": "warn",
        },
        "sessions": {
            "test": {
                "label": "Test Session",
                "open_tz": "UTC",
                "open_time": "00:00",
                "duration_minutes": 60,
                "assets": ["GOLD"],
                "strategy": "orb",
                "holiday_currencies": [],
            }
        },
        "assets": {
            "GOLD": {
                "name": "Gold (XAU/USD)",
                "yahoo": "GC=F",
                "twelvedata": "XAU/USD",
                "mt5": None,
                "ctrader": None,
                "tv_rating": {"symbol": "GOLD", "exchange": "TVC", "screener": "cfd"},
                "tv_widget_symbol": "OANDA:XAUUSD",
            }
        },
        "home_tz": "UTC",
    }
    for path, value in overrides.items():
        node = cfg
        *parts, leaf = path.split(".")
        for p in parts:
            node = node[p]
        node[leaf] = value
    return cfg


def make_orb_long_win_bars(open_utc):
    """One deterministic session: 30 min of quiet pre-session bars (so ATR is computable
    with atr_period=1), a 15-min opening range of 99-101, a breakout close at 102 (LONG),
    then a bar that runs straight to the 2R target (108) with the stop (99) never touched,
    then a flat tail to the session's close. Exactly one trade, entry 102 -> exit 108.
    """
    rows = []
    idx = []

    def add(ts, o, h, l, c):
        idx.append(ts)
        rows.append({"Open": o, "High": h, "Low": l, "Close": c, "Volume": 100})

    # pre-session: 30 quiet 1-min bars so atr_15m (period=1) has something to chew on
    for i in range(30, 0, -1):
        add(open_utc - timedelta(minutes=i), 100.0, 100.5, 99.5, 100.0)

    # opening range: 15 bars, high 101 / low 99
    for i in range(15):
        add(open_utc + timedelta(minutes=i), 100.0, 101.0, 99.0, 100.0)

    # breakout bar: 1-min close above the range high -> LONG signal at 102
    add(open_utc + timedelta(minutes=15), 101.0, 102.0, 101.0, 102.0)

    # next bar runs to the 2R target (108) without ever touching the stop (99)
    add(open_utc + timedelta(minutes=16), 102.0, 109.0, 101.0, 108.0)

    # flat tail to session close (60 min duration) -- stays outside the re-arm band (99-101)
    for i in range(17, 60):
        add(open_utc + timedelta(minutes=i), 108.0, 108.5, 107.5, 108.0)

    df = pd.DataFrame(rows, index=pd.DatetimeIndex(idx, tz=timezone.utc))
    return df


def utc(y, mo, d, hh=0, mm=0):
    return datetime(y, mo, d, hh, mm, tzinfo=timezone.utc)


class FakeAdapter:
    """A BrokerBase-shaped double standing in for a real live adapter (CTraderBroker/
    MT5Broker) in broker/live.py's LiveBroker tests -- no network, fully scriptable."""

    def __init__(self, is_live=False, account_id="999", balance=10000.0, currency="USD"):
        self.is_live = is_live
        self.account_id = account_id
        self.balance = balance
        self.currency = currency
        self.positions = {}   # asset -> pos dict (broker truth)
        self.prices = {}      # asset -> float
        self.placed_orders = []
        self.close_calls = []
        self.connect_called = False
        self.next_position_id = 1

    def connect(self):
        self.connect_called = True
        return True

    def is_live_account(self):
        return self.is_live

    def get_account_info(self):
        return {"balance": self.balance, "equity": self.balance, "currency": self.currency,
                "account_id": self.account_id, "is_live": self.is_live}

    def get_bars(self, asset, interval="1m", lookback_minutes=300):
        raise NotImplementedError("not needed by these tests")

    def get_price(self, asset):
        return self.prices.get(asset)

    def place_order(self, asset, direction, units, stop, target):
        pos = {"asset": asset, "direction": direction,
              "entry_price": self.prices.get(asset, 100.0), "units": units,
              "stop": stop, "target": target, "position_id": self.next_position_id,
              "provider": "fake"}
        self.next_position_id += 1
        self.positions[asset] = pos
        self.placed_orders.append(pos)
        return pos

    def close_position(self, asset, reason, price=None, when=None):
        self.close_calls.append((asset, reason, price))
        pos = self.positions.pop(asset, None)
        if pos is None:
            return None
        fill = price if price is not None else pos["entry_price"]
        trade = dict(pos)
        trade.update({"exit_price": fill, "exit_reason": reason})
        return trade

    def get_positions(self):
        return dict(self.positions)

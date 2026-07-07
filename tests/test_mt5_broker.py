"""Tests for broker/mt5_broker.py's MT5Broker against a fake `MetaTrader5` module injected
via sys.modules -- the real package is Windows-only and needs a running terminal, so this is
the only way to exercise this adapter's logic in this sandbox. See ops/mt5_smoke_test.py for
the read-only check meant to run on an actual Windows box, and ops/live_order_test.py for a
real (demo-only) order-placement smoke test.
"""
import sys
import types
from collections import namedtuple

import pytest

from broker.mt5_broker import MT5Broker

from tests.helpers import make_cfg

AccountInfo = namedtuple("AccountInfo", ["balance", "equity", "currency", "login", "trade_mode"])
SymbolInfo = namedtuple("SymbolInfo", ["trade_contract_size", "volume_step", "volume_min",
                                      "volume_max", "filling_mode", "digits"])
Tick = namedtuple("Tick", ["bid", "ask"])
OrderResult = namedtuple("OrderSendResult", ["retcode", "order", "deal", "price", "volume", "comment"])
Position = namedtuple("Position", ["ticket", "symbol", "volume", "type", "price_open",
                                   "sl", "tp", "magic", "comment"])


def make_fake_mt5(**overrides):
    mod = types.SimpleNamespace()
    mod.TIMEFRAME_M1 = 1
    mod.ORDER_TYPE_BUY = 0
    mod.ORDER_TYPE_SELL = 1
    mod.TRADE_ACTION_DEAL = 1
    mod.ORDER_TIME_GTC = 0
    mod.TRADE_RETCODE_DONE = 10009
    mod.SYMBOL_FILLING_FOK = 1
    mod.SYMBOL_FILLING_IOC = 2
    mod.ORDER_FILLING_FOK = 0
    mod.ORDER_FILLING_IOC = 1
    mod.ORDER_FILLING_RETURN = 2
    mod.ACCOUNT_TRADE_MODE_DEMO = 0
    mod.ACCOUNT_TRADE_MODE_REAL = 2
    mod.initialize = lambda **kw: True
    mod.last_error = lambda: (0, "no error")
    mod.account_info = lambda: AccountInfo(balance=10000.0, equity=10000.0, currency="USD",
                                           login=12345, trade_mode=0)
    mod.symbol_info = lambda symbol: SymbolInfo(trade_contract_size=100.0, volume_step=0.01,
                                                volume_min=0.01, volume_max=100.0,
                                                filling_mode=2, digits=2)
    mod.symbol_info_tick = lambda symbol: Tick(bid=2010.0, ask=2010.2)
    mod.positions_get = lambda symbol=None: ()
    mod.order_send = lambda request: OrderResult(retcode=10009, order=555, deal=777,
                                                 price=2010.2, volume=request["volume"],
                                                 comment="ok")
    mod.copy_rates_from_pos = lambda symbol, timeframe, start, count: None
    for k, v in overrides.items():
        setattr(mod, k, v)
    return mod


def _connected_broker(monkeypatch, mt5_module=None, cfg=None):
    mod = mt5_module or make_fake_mt5()
    monkeypatch.setitem(sys.modules, "MetaTrader5", mod)
    monkeypatch.setenv("MT5_LOGIN", "12345")
    monkeypatch.setenv("MT5_PASSWORD", "pw")
    monkeypatch.setenv("MT5_SERVER", "ICMarkets-Demo")
    cfg = cfg or make_cfg(**{"assets.GOLD.mt5": "XAUUSD"})
    broker = MT5Broker(cfg)
    broker.connect()
    return broker, mod


def test_connect_requires_env_vars(monkeypatch):
    monkeypatch.setitem(sys.modules, "MetaTrader5", make_fake_mt5())
    monkeypatch.delenv("MT5_LOGIN", raising=False)
    monkeypatch.delenv("MT5_PASSWORD", raising=False)
    monkeypatch.delenv("MT5_SERVER", raising=False)
    broker = MT5Broker(make_cfg())
    with pytest.raises(RuntimeError, match="not set in .env"):
        broker.connect()


def test_connect_success(monkeypatch):
    broker, mod = _connected_broker(monkeypatch)
    assert broker._connected is True


def test_is_live_account_reflects_trade_mode(monkeypatch):
    demo_mod = make_fake_mt5(account_info=lambda: AccountInfo(10000, 10000, "USD", 1, 0))
    broker, _ = _connected_broker(monkeypatch, mt5_module=demo_mod)
    assert broker.is_live_account() is False

    live_mod = make_fake_mt5(account_info=lambda: AccountInfo(10000, 10000, "USD", 1, 2))
    broker2, _ = _connected_broker(monkeypatch, mt5_module=live_mod)
    assert broker2.is_live_account() is True


def test_units_to_lots_floors_and_clamps(monkeypatch):
    broker, _ = _connected_broker(monkeypatch)
    # contract_size=100, step=0.01, min=0.01, max=100.0
    assert broker.units_to_lots("XAUUSD", 100.0) == 1.0        # 100/100 = 1.0 lot exactly
    assert broker.units_to_lots("XAUUSD", 123.9) == 1.23        # floors to the 0.01 step
    assert broker.units_to_lots("XAUUSD", 0.5) == 0.0           # below volume_min -> refused
    assert broker.units_to_lots("XAUUSD", 100000.0) == 100.0    # clamped to volume_max


def test_get_bars_decodes_rates(monkeypatch):
    rates = [
        {"time": 1735689600, "open": 2010.0, "high": 2011.0, "low": 2009.0,
        "close": 2010.5, "tick_volume": 150},
    ]
    mod = make_fake_mt5(copy_rates_from_pos=lambda symbol, tf, start, count: rates)
    broker, _ = _connected_broker(monkeypatch, mt5_module=mod)
    bars = broker.get_bars("GOLD", lookback_minutes=1)
    assert bars is not None and len(bars) == 1
    assert bars.iloc[0]["Close"] == 2010.5
    assert bars.iloc[0]["Volume"] == 150
    assert list(bars.columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_place_order_returns_normalized_position(monkeypatch):
    broker, mod = _connected_broker(monkeypatch)
    pos = broker.place_order("GOLD", "LONG", units=100.0, stop=2000.0, target=2030.0)
    assert pos["entry_price"] == 2010.2
    assert pos["units"] == 100.0  # 1.0 lot * contract_size(100)
    assert pos["position_id"] == 555
    assert pos["provider"] == "mt5"


def test_place_order_raises_when_volume_rounds_to_zero(monkeypatch):
    broker, _ = _connected_broker(monkeypatch)
    with pytest.raises(ValueError, match="zero lots"):
        broker.place_order("GOLD", "LONG", units=0.5, stop=2000.0, target=2030.0)


def test_place_order_raises_on_bad_retcode(monkeypatch):
    mod = make_fake_mt5(order_send=lambda req: OrderResult(retcode=10004, order=0, deal=0,
                                                            price=0, volume=0, comment="requote"))
    broker, _ = _connected_broker(monkeypatch, mt5_module=mod)
    with pytest.raises(RuntimeError, match="order_send failed"):
        broker.place_order("GOLD", "LONG", units=100.0, stop=2000.0, target=2030.0)


def test_close_position_sends_opposite_order(monkeypatch):
    existing = Position(ticket=555, symbol="XAUUSD", volume=1.0, type=0, price_open=2010.0,
                        sl=2000.0, tp=2030.0, magic=20260707, comment="trading-agent")
    mod = make_fake_mt5(positions_get=lambda symbol=None: (existing,))
    broker, _ = _connected_broker(monkeypatch, mt5_module=mod)
    trade = broker.close_position("GOLD", "target", price=2030.0)
    assert trade["exit_price"] == 2010.2  # the fake order_send's canned fill price
    assert trade["exit_reason"] == "target"
    assert trade["direction"] == "LONG"
    assert trade["units"] == 100.0


def test_close_position_returns_none_when_no_matching_position(monkeypatch):
    broker, _ = _connected_broker(monkeypatch)  # positions_get() returns () by default
    trade = broker.close_position("GOLD", "target")
    assert trade is None


def test_close_position_ignores_positions_with_a_different_magic(monkeypatch):
    foreign = Position(ticket=1, symbol="XAUUSD", volume=1.0, type=0, price_open=2010.0,
                       sl=2000.0, tp=2030.0, magic=99999, comment="some other EA")
    mod = make_fake_mt5(positions_get=lambda symbol=None: (foreign,))
    broker, _ = _connected_broker(monkeypatch, mt5_module=mod)
    trade = broker.close_position("GOLD", "target")
    assert trade is None


def test_get_positions_filters_by_magic_and_maps_to_asset(monkeypatch):
    ours = Position(ticket=1, symbol="XAUUSD", volume=1.0, type=0, price_open=2010.0,
                    sl=2000.0, tp=2030.0, magic=20260707, comment="trading-agent")
    foreign = Position(ticket=2, symbol="XAUUSD", volume=5.0, type=1, price_open=100.0,
                       sl=110.0, tp=90.0, magic=1, comment="other")
    mod = make_fake_mt5(positions_get=lambda symbol=None: (ours, foreign))
    broker, _ = _connected_broker(monkeypatch, mt5_module=mod)
    positions = broker.get_positions()
    assert list(positions.keys()) == ["GOLD"]
    assert positions["GOLD"]["position_id"] == 1
    assert positions["GOLD"]["units"] == 100.0


def test_get_account_info_includes_account_id_and_is_live(monkeypatch):
    broker, _ = _connected_broker(monkeypatch)
    info = broker.get_account_info()
    assert info["account_id"] == 12345
    assert info["is_live"] is False
    assert info["balance"] == 10000.0

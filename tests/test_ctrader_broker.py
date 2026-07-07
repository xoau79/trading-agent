"""Tests for broker/ctrader/ctrader_broker.py's CTraderBroker, using a scripted, thread-free
FakeTransport double (injected via the `transport_factory` hook) instead of a real WebSocket
-- covers connect()'s account/host resolution, symbol loading, volume rounding, trendbar
decoding, and the place_order/close_position fill-waiting flow.
"""
import threading
import time

import pytest

from broker.ctrader import ctrader_broker as ctb
from broker.ctrader import messages as M
from broker.ctrader.transport import CTraderError

from tests.helpers import make_cfg


class FakeTransport:
    """handlers: {payloadType: fn(transport, payload) -> response_payload}."""

    def __init__(self, host, port, on_event=None, on_reconnect=None, handlers=None):
        self.host = host
        self.port = port
        self.on_event = on_event or (lambda pt, p: None)
        self.on_reconnect = on_reconnect
        self.handlers = handlers or {}
        self.sent = []

    def connect(self):
        pass

    def close(self):
        pass

    def request(self, payload_type, payload, timeout=10):
        self.sent.append((payload_type, payload))
        handler = self.handlers.get(payload_type)
        if handler is None:
            raise CTraderError("NO_HANDLER", f"no fake handler for payloadType {payload_type}")
        return None, handler(self, payload)

    def schedule_event(self, delay, payload_type, payload):
        def _emit():
            time.sleep(delay)
            self.on_event(payload_type, payload)
        threading.Thread(target=_emit, daemon=True).start()


class _FakeTokenStore:
    def __init__(self, *a, **kw):
        pass

    def access_token(self):
        return "fake-access-token"


ACCOUNT_ID = 12345


def _base_handlers(is_live=False):
    return {
        M.APPLICATION_AUTH_REQ: lambda t, p: {},
        M.ACCOUNT_AUTH_REQ: lambda t, p: {"ctidTraderAccountId": p["ctidTraderAccountId"]},
        M.GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ: lambda t, p: {
            "ctidTraderAccount": [
                {"ctidTraderAccountId": ACCOUNT_ID, "isLive": is_live, "brokerTitleShort": "ICM"}]},
        M.SYMBOLS_LIST_REQ: lambda t, p: {
            "symbol": [{"symbolId": 1, "symbolName": "XAUUSD", "enabled": True}]},
        M.SYMBOL_BY_ID_REQ: lambda t, p: {
            "symbol": [{"symbolId": 1, "digits": 2, "pipPosition": 1, "lotSize": 10000,
                       "minVolume": 100, "maxVolume": 5_000_000, "stepVolume": 100}]},
        M.SUBSCRIBE_SPOTS_REQ: lambda t, p: {},
        M.TRADER_REQ: lambda t, p: {"trader": {"balance": 1_000_000, "moneyDigits": 2}},
        M.RECONCILE_REQ: lambda t, p: {"position": []},
    }


def _connect_broker(monkeypatch, cfg=None, is_live=False):
    cfg = cfg or make_cfg(**{"assets.GOLD.ctrader": "XAUUSD"})
    monkeypatch.setenv("CTRADER_CLIENT_ID", "cid")
    monkeypatch.setenv("CTRADER_CLIENT_SECRET", "secret")
    monkeypatch.setenv("CTRADER_ACCOUNT_ID", str(ACCOUNT_ID))
    monkeypatch.setattr(ctb, "TokenStore", _FakeTokenStore)

    handlers = _base_handlers(is_live=is_live)

    def factory(host, port, on_event=None, on_reconnect=None):
        return FakeTransport(host, port, on_event=on_event, on_reconnect=on_reconnect,
                             handlers=handlers)

    broker = ctb.CTraderBroker(cfg, transport_factory=factory)
    broker.connect()
    return broker


def test_connect_resolves_demo_account_and_symbols(monkeypatch):
    broker = _connect_broker(monkeypatch, is_live=False)
    assert broker.is_live_account() is False
    assert broker._symbols_by_asset["GOLD"] == 1
    assert broker._symbol_meta[1]["minVolume"] == 100


def test_connect_resolves_live_account(monkeypatch):
    broker = _connect_broker(monkeypatch, is_live=True)
    assert broker.is_live_account() is True


def test_connect_raises_when_account_id_not_found(monkeypatch):
    cfg = make_cfg(**{"assets.GOLD.ctrader": "XAUUSD"})
    monkeypatch.setenv("CTRADER_CLIENT_ID", "cid")
    monkeypatch.setenv("CTRADER_CLIENT_SECRET", "secret")
    monkeypatch.setenv("CTRADER_ACCOUNT_ID", "99999")  # not in the fake account list
    monkeypatch.setattr(ctb, "TokenStore", _FakeTokenStore)
    handlers = _base_handlers()

    def factory(host, port, on_event=None, on_reconnect=None):
        return FakeTransport(host, port, on_event=on_event, on_reconnect=on_reconnect,
                             handlers=handlers)

    broker = ctb.CTraderBroker(cfg, transport_factory=factory)
    with pytest.raises(RuntimeError, match="was not found"):
        broker.connect()


def test_connect_raises_when_configured_symbol_is_missing(monkeypatch):
    cfg = make_cfg(**{"assets.GOLD.ctrader": "DOES_NOT_EXIST"})
    with pytest.raises(ValueError, match="DOES_NOT_EXIST"):
        _connect_broker(monkeypatch, cfg=cfg)


def test_get_account_info_scales_balance_by_money_digits(monkeypatch):
    broker = _connect_broker(monkeypatch)
    info = broker.get_account_info()
    assert info["balance"] == 10000.0
    assert info["is_live"] is False


def test_units_to_volume_floors_to_step_and_clamps(monkeypatch):
    broker = _connect_broker(monkeypatch)
    # step=100, min=100, max=5_000_000 (see _base_handlers)
    assert broker.units_to_volume("GOLD", 1.0) == 100          # 1.0 * 100 = 100 exactly
    assert broker.units_to_volume("GOLD", 1.239) == 100        # floors 123.9 -> 100 (never up)
    assert broker.units_to_volume("GOLD", 0.5) == 0            # 50 < minVolume(100) -> refused
    assert broker.units_to_volume("GOLD", 100000.0) == 5_000_000  # clamped to maxVolume


def test_get_bars_decodes_trendbar_deltas(monkeypatch):
    handlers = _base_handlers()
    handlers[M.GET_TRENDBARS_REQ] = lambda t, p: {"trendbar": [
        {"low": 201_000_000, "deltaOpen": 12_300, "deltaHigh": 45_600, "deltaClose": 23_400,
         "volume": 500, "utcTimestampInMinutes": 1_000_000},
    ]}
    broker = _connect_broker(monkeypatch, cfg=make_cfg(**{"assets.GOLD.ctrader": "XAUUSD"}))
    monkeypatch.setattr(broker, "_transport",
                       FakeTransport("demo", 5036, handlers=handlers))
    bars = broker.get_bars("GOLD", lookback_minutes=10)
    assert bars is not None and len(bars) == 1
    row = bars.iloc[0]
    assert row["Low"] == pytest.approx(2010.0)
    assert row["Open"] == pytest.approx(2010.123)
    assert row["High"] == pytest.approx(2010.456)
    assert row["Close"] == pytest.approx(2010.234)
    assert row["Volume"] == pytest.approx(5.0)  # 500 / VOLUME_SCALE(100)


def test_place_order_waits_for_execution_event_and_returns_fill(monkeypatch):
    handlers = _base_handlers()

    def new_order_handler(t, payload):
        exec_payload = {
            "executionType": M.EXEC_ORDER_FILLED,
            "deal": {"symbolId": 1, "executionPrice": 2010.55, "filledVolume": 100},
            "position": {"positionId": 555},
        }
        t.schedule_event(0.02, M.EXECUTION_EVENT, exec_payload)
        return {}

    handlers[M.NEW_ORDER_REQ] = new_order_handler
    broker = _connect_broker(monkeypatch)
    monkeypatch.setattr(broker, "_transport",
                       FakeTransport("demo", 5036, on_event=broker._on_event, handlers=handlers))

    pos = broker.place_order("GOLD", "LONG", units=1.0, stop=2005.0, target=2020.0)
    assert pos["entry_price"] == 2010.55
    assert pos["units"] == 1.0  # 100 volume / VOLUME_SCALE(100)
    assert pos["position_id"] == 555
    assert broker._positions_cache["GOLD"] == pos


def test_place_order_raises_when_volume_rounds_to_zero(monkeypatch):
    broker = _connect_broker(monkeypatch)
    with pytest.raises(ValueError, match="zero volume"):
        broker.place_order("GOLD", "LONG", units=0.5, stop=2005.0, target=2020.0)


def test_place_order_raises_ctrader_error_on_rejection(monkeypatch):
    handlers = _base_handlers()

    def new_order_handler(t, payload):
        t.schedule_event(0.02, M.EXECUTION_EVENT,
                         {"executionType": M.EXEC_ORDER_REJECTED, "errorCode": "NOT_ENOUGH_MONEY",
                          "deal": {"symbolId": 1}})
        return {}

    handlers[M.NEW_ORDER_REQ] = new_order_handler
    broker = _connect_broker(monkeypatch)
    monkeypatch.setattr(broker, "_transport",
                       FakeTransport("demo", 5036, on_event=broker._on_event, handlers=handlers))
    with pytest.raises(CTraderError, match="NOT_ENOUGH_MONEY"):
        broker.place_order("GOLD", "LONG", units=1.0, stop=2005.0, target=2020.0)


def test_close_position_returns_trade_with_exit_price(monkeypatch):
    handlers = _base_handlers()

    def close_handler(t, payload):
        t.schedule_event(0.02, M.EXECUTION_EVENT, {
            "executionType": M.EXEC_ORDER_FILLED,
            "deal": {"symbolId": 1, "executionPrice": 2015.0, "filledVolume": 100},
        })
        return {}

    handlers[M.CLOSE_POSITION_REQ] = close_handler
    broker = _connect_broker(monkeypatch)
    fake = FakeTransport("demo", 5036, on_event=broker._on_event, handlers=handlers)
    monkeypatch.setattr(broker, "_transport", fake)
    broker._positions_cache["GOLD"] = {
        "asset": "GOLD", "direction": "LONG", "entry_price": 2010.0, "units": 1.0,
        "stop": 2005.0, "target": 2020.0, "position_id": 555, "provider": "ctrader",
    }
    trade = broker.close_position("GOLD", "target", price=2020.0)
    assert trade["exit_price"] == 2015.0
    assert trade["exit_reason"] == "target"
    assert "GOLD" not in broker._positions_cache


def test_get_positions_filters_to_our_label_only(monkeypatch):
    handlers = _base_handlers()
    handlers[M.RECONCILE_REQ] = lambda t, p: {"position": [
        {"positionId": 1, "price": 2010.0, "stopLoss": 2005.0, "takeProfit": 2020.0,
         "tradeData": {"symbolId": 1, "volume": 100, "tradeSide": M.BUY, "label": "trading-agent"}},
        {"positionId": 2, "price": 100.0, "stopLoss": 90.0, "takeProfit": 110.0,
         "tradeData": {"symbolId": 1, "volume": 500, "tradeSide": M.SELL, "label": "some-other-app"}},
    ]}
    broker = _connect_broker(monkeypatch)
    monkeypatch.setattr(broker, "_transport", FakeTransport("demo", 5036, handlers=handlers))
    positions = broker.get_positions()
    assert list(positions.keys()) == ["GOLD"]
    assert positions["GOLD"]["position_id"] == 1

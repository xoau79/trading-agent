"""Tests for broker/live.py's LiveBroker facade against a FakeAdapter (tests/helpers.py):
the update_position/close_position flow when a position closes server-side, forced-exit
closes that must actually reach the broker, and reconcile()'s crash-recovery behavior
(ledger-only positions closed elsewhere, and unmanaged broker-side positions left untouched).
"""
import broker.live as live_mod

from tests.helpers import FakeAdapter, make_cfg


def _broker(tmp_path, monkeypatch, cfg=None, adapter=None):
    monkeypatch.setattr(live_mod, "STATE_DIR", tmp_path)
    monkeypatch.delenv("LIVE_TRADING_CONFIRM", raising=False)
    cfg = cfg or make_cfg()
    lb = live_mod.LiveBroker(cfg, adapter or FakeAdapter())
    lb.connect()
    return lb


def _open(lb, adapter, asset="GOLD", entry=100.0, stop=95.0, target=110.0, units=10.0):
    """Directly seed a ledger + broker-side position, bypassing size_position/sanity
    checks -- these tests are about post-open lifecycle, not order placement."""
    pos = {"asset": asset, "direction": "LONG", "entry_price": entry, "units": units,
          "stop": stop, "target": target, "risk_usd": abs(entry - stop) * units,
          "mfe": 0.0, "mae": 0.0, "context": {}, "entry_time": "2026-01-05T00:00:00Z"}
    lb.ledger.register_open(asset, dict(pos))
    adapter.positions[asset] = {**pos, "position_id": 1}
    return pos


def test_update_position_returns_none_while_still_open_at_broker(tmp_path, monkeypatch):
    adapter = FakeAdapter()
    lb = _broker(tmp_path, monkeypatch, adapter=adapter)
    _open(lb, adapter)
    bar = {"High": 105.0, "Low": 103.0}
    price, reason = lb.update_position("GOLD", bar)
    assert price is None and reason is None
    assert adapter.close_calls == []  # never touched the broker just to check


def test_update_position_detects_server_side_stop_close(tmp_path, monkeypatch):
    adapter = FakeAdapter()
    lb = _broker(tmp_path, monkeypatch, adapter=adapter)
    _open(lb, adapter, stop=95.0, target=110.0)
    # broker-side: the stop was hit and the position is simply gone now
    adapter.positions.pop("GOLD")
    adapter.prices["GOLD"] = 94.8  # close to the stop (95.0) vs. the target (110.0)
    bar = {"High": 96.0, "Low": 94.8}
    price, reason = lb.update_position("GOLD", bar)
    assert price == 94.8
    assert reason == "stop"


def test_update_position_detects_server_side_target_close(tmp_path, monkeypatch):
    adapter = FakeAdapter()
    lb = _broker(tmp_path, monkeypatch, adapter=adapter)
    _open(lb, adapter, stop=95.0, target=110.0)
    adapter.positions.pop("GOLD")
    adapter.prices["GOLD"] = 110.1  # close to the target
    bar = {"High": 110.2, "Low": 109.0}
    price, reason = lb.update_position("GOLD", bar)
    assert price == 110.1
    assert reason == "target"


def test_close_position_skips_broker_call_when_already_closed(tmp_path, monkeypatch):
    """Mirrors the real Engine flow: update_position() detects the closure first, THEN
    Engine calls close_position() with that price/reason -- close_position must not try to
    close an already-closed position at the broker again."""
    adapter = FakeAdapter()
    lb = _broker(tmp_path, monkeypatch, adapter=adapter)
    _open(lb, adapter, entry=100.0, stop=95.0, target=110.0, units=10.0)
    adapter.positions.pop("GOLD")  # already closed server-side
    trade = lb.close_position("GOLD", 95.0, "stop", "2026-01-05T00:10:00Z")
    assert adapter.close_calls == []  # never re-closes what's already gone
    assert trade["exit_price"] == 95.0
    assert trade["pnl"] == -50.0  # (95-100)*10
    assert "GOLD" not in lb.ledger.state["open_positions"]


def test_close_position_actually_closes_when_still_open(tmp_path, monkeypatch):
    """A forced exit (news flatten / daily-stop flatten) -- the position is still open at
    the broker, so close_position must call the adapter and trust its real fill price."""
    adapter = FakeAdapter()
    lb = _broker(tmp_path, monkeypatch, adapter=adapter)
    _open(lb, adapter, entry=100.0, stop=95.0, target=110.0, units=10.0)
    trade = lb.close_position("GOLD", 103.0, "news_flatten", "2026-01-05T00:05:00Z")
    assert len(adapter.close_calls) == 1
    assert adapter.close_calls[0][0] == "GOLD"
    assert trade["exit_reason"] == "news_flatten"
    assert "GOLD" not in adapter.positions


def test_flatten_all_closes_every_open_position(tmp_path, monkeypatch):
    adapter = FakeAdapter()
    lb = _broker(tmp_path, monkeypatch, adapter=adapter)
    _open(lb, adapter, asset="GOLD", entry=100.0, stop=95.0, target=110.0, units=10.0)
    _open(lb, adapter, asset="NQ", entry=200.0, stop=195.0, target=210.0, units=5.0)
    closed = lb.flatten_all({"GOLD": 101.0, "NQ": 199.0}, "time", "2026-01-05T06:30:00Z")
    assert {t["asset"] for t in closed} == {"GOLD", "NQ"}
    assert lb.ledger.state["open_positions"] == {}


# ----- reconciliation -----------------------------------------------------------------
def test_reconcile_books_a_position_closed_while_the_bot_was_down(tmp_path, monkeypatch):
    adapter = FakeAdapter()
    lb = _broker(tmp_path, monkeypatch, adapter=adapter)
    _open(lb, adapter, entry=100.0, stop=95.0, target=110.0, units=10.0)
    # simulate a restart: the broker no longer shows this position (it closed while we were
    # down), but our ledger still thinks it's open
    adapter.positions.pop("GOLD")
    adapter.prices["GOLD"] = 110.5
    closed = lb.reconcile("2026-01-05T07:00:00Z")
    assert len(closed) == 1
    assert closed[0]["asset"] == "GOLD"
    assert closed[0]["exit_reason"] == "reconciled_externally"
    assert lb.ledger.state["open_positions"] == {}


def test_reconcile_leaves_unmanaged_broker_positions_untouched(tmp_path, monkeypatch):
    adapter = FakeAdapter()
    lb = _broker(tmp_path, monkeypatch, adapter=adapter)
    # the broker shows a position our ledger has never heard of
    adapter.positions["NQ"] = {"asset": "NQ", "direction": "LONG", "entry_price": 200.0,
                               "units": 1.0, "stop": 190.0, "target": 220.0, "position_id": 99}
    closed = lb.reconcile("2026-01-05T07:00:00Z")
    assert closed == []
    assert "NQ" not in lb.ledger.state["open_positions"]
    assert adapter.close_calls == []  # never touched
    assert len(lb.unmanaged_warnings) == 1
    assert "NQ" in lb.unmanaged_warnings[0]


def test_reconcile_is_a_no_op_when_everything_matches(tmp_path, monkeypatch):
    adapter = FakeAdapter()
    lb = _broker(tmp_path, monkeypatch, adapter=adapter)
    _open(lb, adapter)
    closed = lb.reconcile("2026-01-05T07:00:00Z")
    assert closed == []
    assert lb.unmanaged_warnings == []
    assert "GOLD" in lb.ledger.state["open_positions"]


# ----- status payload -------------------------------------------------------------------
def test_status_payload_reflects_environment_and_connection(tmp_path, monkeypatch):
    adapter = FakeAdapter(is_live=False, account_id="42", balance=5000.0, currency="EUR")
    lb = _broker(tmp_path, monkeypatch, adapter=adapter)
    payload = lb.status_payload()
    assert payload["provider"] == "paper"  # make_cfg()'s default broker.provider
    assert payload["environment"] == "demo"
    assert payload["connected"] is True
    assert payload["balance"] == 5000.0
    assert payload["currency"] == "EUR"


def test_status_payload_survives_a_broken_connection(tmp_path, monkeypatch):
    adapter = FakeAdapter()
    lb = _broker(tmp_path, monkeypatch, adapter=adapter)  # connects fine first

    def _boom():
        raise ConnectionError("socket closed")

    adapter.get_account_info = _boom  # simulate the connection dropping afterward
    payload = lb.status_payload()
    assert payload["connected"] is False

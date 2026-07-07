"""Tests for broker/live.py's safety mechanisms in isolation: the live-account latch, the
per-order sanity checks, and the max-total-drawdown halt. These are the guardrails the user
explicitly wants verified before any real money is at risk.

Every test isolates its ledger's state file under tmp_path via broker.live.STATE_DIR (the
same monkeypatch-a-module-global pattern broker/paper.py's STATE_FILE uses) -- LiveBroker
must never write anywhere near the real repo root during a test run.
"""
import broker.live as live_mod
import pytest

from tests.helpers import FakeAdapter, make_cfg


def _broker(tmp_path, monkeypatch, cfg=None, adapter=None):
    monkeypatch.setattr(live_mod, "STATE_DIR", tmp_path)
    cfg = cfg or make_cfg()
    return live_mod.LiveBroker(cfg, adapter or FakeAdapter())


# ----- live-account latch --------------------------------------------------------------
def test_demo_account_never_needs_the_latch(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVE_TRADING_CONFIRM", raising=False)
    lb = _broker(tmp_path, monkeypatch, adapter=FakeAdapter(is_live=False))
    lb.connect()  # must not raise even with live_trading.enabled == False and no confirm


def test_live_account_refuses_without_enabled_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_TRADING_CONFIRM", "555")
    cfg = make_cfg(**{"live_trading.enabled": False})
    lb = _broker(tmp_path, monkeypatch, cfg=cfg, adapter=FakeAdapter(is_live=True, account_id="555"))
    with pytest.raises(RuntimeError, match="Refusing to trade a LIVE"):
        lb.connect()


def test_live_account_refuses_without_matching_confirm_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_TRADING_CONFIRM", "wrong-id")
    cfg = make_cfg(**{"live_trading.enabled": True})
    lb = _broker(tmp_path, monkeypatch, cfg=cfg, adapter=FakeAdapter(is_live=True, account_id="555"))
    with pytest.raises(RuntimeError, match="Refusing to trade a LIVE"):
        lb.connect()


def test_live_account_refuses_with_empty_confirm_even_if_enabled(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVE_TRADING_CONFIRM", raising=False)
    cfg = make_cfg(**{"live_trading.enabled": True})
    lb = _broker(tmp_path, monkeypatch, cfg=cfg, adapter=FakeAdapter(is_live=True, account_id="555"))
    with pytest.raises(RuntimeError, match="Refusing to trade a LIVE"):
        lb.connect()


def test_live_account_trades_when_both_conditions_match(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_TRADING_CONFIRM", "555")
    cfg = make_cfg(**{"live_trading.enabled": True})
    lb = _broker(tmp_path, monkeypatch, cfg=cfg, adapter=FakeAdapter(is_live=True, account_id="555"))
    lb.connect()  # must not raise
    assert lb.ledger.state["balance"] == 10000.0


# ----- order sanity checks ---------------------------------------------------------------
# Most of these use a generous max_units_per_asset override so the *other* checks can be
# exercised in isolation -- the default cap (50) combined with this repo's default 1% risk
# sizing would otherwise trip the units cap first for several of these scenarios.
GENEROUS_UNITS = {"live_trading.max_units_per_asset": {"GOLD": 1_000_000}}


def test_sanity_check_refuses_units_over_the_asset_cap(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVE_TRADING_CONFIRM", raising=False)
    cfg = make_cfg(**{"live_trading.max_units_per_asset": {"GOLD": 1}})
    adapter = FakeAdapter()
    adapter.prices["GOLD"] = 100.0
    lb = _broker(tmp_path, monkeypatch, cfg=cfg, adapter=adapter)
    lb.connect()
    signal = {"direction": "LONG", "entry": 100.0, "stop": 99.99, "target": 100.5}
    pos = lb.open_position("GOLD", signal, "2026-01-05T00:00:00Z", {})
    assert pos is None
    assert "max_units_per_asset" in lb.last_order_error
    assert adapter.placed_orders == []


def test_sanity_check_refuses_stop_distance_below_minimum(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVE_TRADING_CONFIRM", raising=False)
    cfg = make_cfg(**{**GENEROUS_UNITS, "live_trading.min_stop_distance_pct": 1.0})
    adapter = FakeAdapter()
    adapter.prices["GOLD"] = 100.0
    lb = _broker(tmp_path, monkeypatch, cfg=cfg, adapter=adapter)
    lb.connect()
    signal = {"direction": "LONG", "entry": 100.0, "stop": 99.9, "target": 101.0}  # 0.1% stop
    pos = lb.open_position("GOLD", signal, "2026-01-05T00:00:00Z", {})
    assert pos is None
    assert "below minimum" in lb.last_order_error


def test_sanity_check_refuses_stop_distance_above_maximum(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVE_TRADING_CONFIRM", raising=False)
    cfg = make_cfg(**{**GENEROUS_UNITS, "live_trading.max_stop_distance_pct": 1.0})
    adapter = FakeAdapter()
    adapter.prices["GOLD"] = 100.0
    lb = _broker(tmp_path, monkeypatch, cfg=cfg, adapter=adapter)
    lb.connect()
    signal = {"direction": "LONG", "entry": 100.0, "stop": 90.0, "target": 130.0}  # 10% stop
    pos = lb.open_position("GOLD", signal, "2026-01-05T00:00:00Z", {})
    assert pos is None
    assert "above maximum" in lb.last_order_error


def test_sanity_check_refuses_stop_on_the_wrong_side(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVE_TRADING_CONFIRM", raising=False)
    cfg = make_cfg(**GENEROUS_UNITS)
    adapter = FakeAdapter()
    adapter.prices["GOLD"] = 100.0
    lb = _broker(tmp_path, monkeypatch, cfg=cfg, adapter=adapter)
    lb.connect()
    # LONG with the stop ABOVE entry -- nonsensical
    signal = {"direction": "LONG", "entry": 100.0, "stop": 101.0, "target": 105.0}
    pos = lb.open_position("GOLD", signal, "2026-01-05T00:00:00Z", {})
    assert pos is None
    assert "wrong side" in lb.last_order_error


def test_sanity_check_leverage_guard_rejects_oversized_units_directly(tmp_path, monkeypatch):
    """size_position() already caps units at the leverage limit (broker/ledger.py), so a
    normally-sized order can never trip this check in practice -- it exists as defense in
    depth. Exercise it directly with a synthetic, larger-than-sizing-would-ever-produce
    units value to prove it still refuses if that invariant is ever broken upstream."""
    monkeypatch.delenv("LIVE_TRADING_CONFIRM", raising=False)
    cfg = make_cfg(**{"risk.max_notional_leverage": 1, **GENEROUS_UNITS})
    adapter = FakeAdapter(balance=10000.0)
    lb = _broker(tmp_path, monkeypatch, cfg=cfg, adapter=adapter)
    lb.connect()
    signal = {"direction": "LONG", "entry": 100.0, "stop": 99.0, "target": 110.0}
    # 5000 units * 100 entry = 500,000 notional vs. leverage(1) * balance(10000) = 10,000 cap
    ok, why = lb._sanity_check_order("GOLD", signal, units=5000.0)
    assert not ok
    assert "leverage cap" in why


def test_a_valid_order_passes_the_sanity_checks(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVE_TRADING_CONFIRM", raising=False)
    cfg = make_cfg(**GENEROUS_UNITS)
    adapter = FakeAdapter()
    adapter.prices["GOLD"] = 100.0
    lb = _broker(tmp_path, monkeypatch, cfg=cfg, adapter=adapter)
    lb.connect()
    signal = {"direction": "LONG", "entry": 100.0, "stop": 99.0, "target": 102.0}
    pos = lb.open_position("GOLD", signal, "2026-01-05T00:00:00Z", {})
    assert pos is not None
    assert lb.last_order_error is None
    assert len(adapter.placed_orders) == 1


# ----- max total drawdown halt ------------------------------------------------------------
def test_drawdown_halt_trips_after_baseline_established(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVE_TRADING_CONFIRM", raising=False)
    cfg = make_cfg(**{"live_trading.max_total_drawdown_pct": 10.0})
    adapter = FakeAdapter(balance=10000.0)
    lb = _broker(tmp_path, monkeypatch, cfg=cfg, adapter=adapter)
    lb.connect()  # baseline = 10000.0
    assert lb.ledger.state["live_baseline_balance"] == 10000.0

    lb.ledger.state["open_positions"]["GOLD"] = {
        "asset": "GOLD", "direction": "LONG", "entry_price": 100.0, "units": 100.0,
        "stop": 91.0, "target": 110.0,
    }
    adapter.positions["GOLD"] = {"asset": "GOLD", "position_id": 1}
    # a big loss: (89 - 100) * 100 = -1100 -> new balance 8900, dd = 11% >= 10% cap
    lb.close_position("GOLD", 89.0, "stop", "2026-01-05T00:10:00Z")
    assert lb.ledger.state["halted_reason"] is not None
    assert "drawdown" in lb.ledger.state["halted_reason"]
    ok, why = lb.can_open("GOLD")
    assert not ok


def test_drawdown_halt_does_not_trip_below_threshold(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVE_TRADING_CONFIRM", raising=False)
    cfg = make_cfg(**{"live_trading.max_total_drawdown_pct": 50.0})
    adapter = FakeAdapter(balance=10000.0)
    lb = _broker(tmp_path, monkeypatch, cfg=cfg, adapter=adapter)
    lb.connect()
    lb.ledger.state["open_positions"]["GOLD"] = {
        "asset": "GOLD", "direction": "LONG", "entry_price": 100.0, "units": 10.0,
        "stop": 95.0, "target": 110.0,
    }
    adapter.positions["GOLD"] = {"asset": "GOLD", "position_id": 1}
    lb.close_position("GOLD", 95.0, "stop", "2026-01-05T00:10:00Z")  # small loss, well under 50%
    assert lb.ledger.state["halted_reason"] is None

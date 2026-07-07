"""Unit tests for broker/ledger.py's TradeLedger in isolation -- the universal risk rules
(caps, daily-loss halt, consecutive-loss bench, sizing) that any broker (paper or live) shares.
"""
from datetime import datetime, timezone

from broker.ledger import TradeLedger

from tests.helpers import make_cfg


def _ledger(tmp_path, **overrides):
    cfg = make_cfg(**overrides)
    return TradeLedger(cfg, tmp_path / "state.json")


def test_fresh_state_starts_at_configured_balance(tmp_path):
    led = _ledger(tmp_path)
    assert led.state["balance"] == 10000.0
    assert led.state["open_positions"] == {}


def test_state_persists_across_instances(tmp_path):
    led = _ledger(tmp_path)
    led.start_session("test", "2026-01-05")
    led.state["balance"] = 10500.0
    led.save()

    reloaded = TradeLedger(led.cfg, led.state_file)
    assert reloaded.state["balance"] == 10500.0
    assert reloaded.state["day_key"] == "2026-01-05"


def test_size_position_respects_leverage_cap(tmp_path):
    led = _ledger(tmp_path, **{"risk.max_notional_leverage": 1})
    led.start_session("test", "2026-01-05")
    units, risk_usd = led.size_position(entry=100.0, stop=99.0)
    # leverage cap: max_units = 1 * 10000 / 100 = 100
    assert units == 100.0
    assert risk_usd == 100.0  # units * stop_dist = 100 * 1.0


def test_can_open_blocks_a_second_position_on_the_same_asset(tmp_path):
    led = _ledger(tmp_path, **{"risk.max_trades_per_session": 4})
    led.start_session("test", "2026-01-05")
    ok, why = led.can_open("GOLD")
    assert ok
    led.register_open("GOLD", {"asset": "GOLD"})
    ok, why = led.can_open("GOLD")
    assert not ok
    assert "already in a position" in why


def test_can_open_enforces_the_session_trade_cap(tmp_path):
    led = _ledger(tmp_path, **{"risk.max_trades_per_session": 1})
    led.start_session("test", "2026-01-05")
    led.register_open("GOLD", {"asset": "GOLD"})
    led.pop_position("GOLD")  # close it -- cap counts trades taken, not positions still open
    ok, why = led.can_open("GOLD")
    assert not ok
    assert "session trade cap" in why


def test_daily_stop_halts_trading(tmp_path):
    led = _ledger(tmp_path, **{"risk.daily_loss_limit_pct": 3.0})
    led.start_session("test", "2026-01-05")
    led.register_close("GOLD", -400.0)  # 4% loss on a 10,000 balance
    led.check_daily_stop()
    assert led.state["halted_reason"] is not None
    ok, why = led.can_open("GOLD")
    assert not ok
    assert why == led.state["halted_reason"]


def test_consecutive_losses_bench_the_asset(tmp_path):
    led = _ledger(tmp_path, **{"risk.consecutive_losses_to_bench": 2})
    led.start_session("test", "2026-01-05")
    led.apply_streak("GOLD", -50.0)
    assert not led.is_benched("GOLD")
    led.apply_streak("GOLD", -50.0)
    assert led.is_benched("GOLD")
    ok, why = led.can_open("GOLD")
    assert not ok
    assert "benched" in why


def test_a_winning_trade_resets_the_streak(tmp_path):
    led = _ledger(tmp_path, **{"risk.consecutive_losses_to_bench": 2})
    led.start_session("test", "2026-01-05")
    led.apply_streak("GOLD", -50.0)
    led.apply_streak("GOLD", 75.0)
    assert led.state["consecutive_losses"]["GOLD"] == 0
    assert not led.is_benched("GOLD")


def test_sync_balance_overwrites_simulated_balance(tmp_path):
    led = _ledger(tmp_path)
    led.start_session("test", "2026-01-05")
    led.sync_balance(9876.543)
    assert led.state["balance"] == 9876.54

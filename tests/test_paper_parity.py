"""End-to-end parity test for the paper-trading path: drives bot.py's real Engine over a
hand-built, deterministic session (see tests/helpers.py) with no network access at all.

This is the test that must produce byte-identical results before and after the broker/ledger
refactor (docs/ARCHITECTURE.md's "Engine refactor" work) -- it exercises the exact same public
surface (Engine.step/end_session, PaperBroker.state/can_open/open_position/close_position)
that a live broker will eventually share via broker/live.py's LiveBroker facade.
"""
from datetime import timedelta

import bot
import journal
from broker import paper as broker_mod
from broker.paper import PaperBroker

from tests.helpers import make_cfg, make_orb_long_win_bars, utc


def _redirect_state_and_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(broker_mod, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(journal, "JOURNAL", tmp_path / "journal")
    monkeypatch.setattr(journal, "TRADES_FILE", tmp_path / "journal" / "trades.json")
    monkeypatch.setattr(journal, "LESSONS_JSON", tmp_path / "journal" / "lessons.json")
    monkeypatch.setattr(journal, "LESSONS_MD", tmp_path / "journal" / "lessons.md")
    monkeypatch.setattr(journal, "DATA_JS", tmp_path / "data.js")


def _run_session(cfg, tmp_path, monkeypatch):
    _redirect_state_and_journal(tmp_path, monkeypatch)
    open_utc = utc(2026, 1, 5)  # a Monday -- irrelevant here, no calendar/network involved
    close_utc = open_utc + timedelta(minutes=cfg["sessions"]["test"]["duration_minutes"])
    bars = make_orb_long_win_bars(open_utc)

    broker = PaperBroker(cfg)
    broker.start_session("test", "2026-01-05")
    engine = bot.Engine(cfg, broker, newsdesk=None, session_name="test",
                        open_utc=open_utc, close_utc=close_utc, replay=True, agent=None)

    sim = open_utc + timedelta(minutes=1)
    while sim <= close_utc:
        cutoff = sim - timedelta(seconds=60)
        engine.step(sim, {"GOLD": bars[bars.index <= cutoff]})
        sim += timedelta(minutes=1)
    engine.end_session(close_utc)
    return broker, engine


def test_orb_long_hits_target_end_to_end(tmp_path, monkeypatch):
    cfg = make_cfg()
    broker, engine = _run_session(cfg, tmp_path, monkeypatch)

    assert len(engine.session_trades) == 1
    trade = engine.session_trades[0]
    assert trade["asset"] == "GOLD"
    assert trade["direction"] == "LONG"
    assert trade["entry_price"] == 102.0
    assert trade["exit_price"] == 108.0
    assert trade["exit_reason"] == "target"
    assert trade["r_multiple"] == 2.0
    assert trade["pnl"] == pytest_approx(200.0)
    assert broker.state["balance"] == pytest_approx(10200.0)
    assert broker.state["open_positions"] == {}
    assert broker.state["trades_today"] == 1
    assert broker.state["trades_this_session"] == 1


def test_risk_caps_still_enforced(tmp_path, monkeypatch):
    """Sanity check that the universal risk rules (still owned by PaperBroker/ledger) are
    unaffected: dropping the per-session cap to zero must produce zero trades."""
    cfg = make_cfg(**{"risk.max_trades_per_session": 0})
    broker, engine = _run_session(cfg, tmp_path, monkeypatch)
    assert len(engine.session_trades) == 0
    assert broker.state["balance"] == 10000.0


def pytest_approx(value, rel=1e-6):
    import pytest
    return pytest.approx(value, rel=rel)

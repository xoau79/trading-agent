"""Unit tests for agent.py's bounded auto-tuning pipeline (learn_from_trade's buckets ->
review_and_refine's candidate search -> _apply_override's whitelist enforcement ->
apply_approved_suggestions). This pipeline has never actually fired in production (the
evidence gates -- 20+ trades since the last change, 5+ days between changes -- mean it takes
weeks of live trading to reach), so it has to be exercised with a hand-built learning.json
rather than waiting for real data. See docs/ARCHITECTURE.md and agent.py's module docstring
for the hard boundary this enforces: only whitelisted params, only within their configured
bounds, risk caps and strategy rules never touched.
"""
import json
from datetime import datetime, timezone

import agent as agent_mod

from tests.helpers import make_cfg

DAY_KEY = "2026-07-08"


def _cfg_with_tuning(**overrides):
    cfg = make_cfg(**overrides)
    cfg["tuning"] = {
        "auto_budget": 15,
        "min_trades_per_change": 20,
        "min_days_between_changes": 5,
        "min_bucket_trades": 10,
        "whitelist": {
            "strategy.range_atr_min": {"min": 0.3, "max": 0.8, "step": 0.05},
            "strategy.range_atr_max": {"min": 1.5, "max": 3.0, "step": 0.25},
            "strategy.entry_cutoff_minutes": {"min": 0, "max": 120, "step": 30},
            "strategy.tv_confluence_enabled": {"bool": True},
        },
    }
    return cfg


def _agent(tmp_path, cfg, monkeypatch):
    """Redirect agent.py's module-level file paths into tmp_path (the same pattern bot.py's
    run_replay() uses for journal.py/broker.paper -- see its docstring/body), but via
    monkeypatch so each test's redirection is reverted afterward rather than leaking into
    whichever test runs next. Also clears DISCORD_WEBHOOK_URL: several of these paths call
    agent.say(..., discord=True), and a real webhook configured in a dev's own .env would
    otherwise make this network-free suite post live test messages to a real Discord server."""
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.setattr(agent_mod, "FEED_FILE", tmp_path / "agent_feed.json")
    monkeypatch.setattr(agent_mod, "LEARNING_FILE", tmp_path / "learning.json")
    monkeypatch.setattr(agent_mod, "SUGGESTIONS_FILE", tmp_path / "suggestions.json")
    monkeypatch.setattr(agent_mod, "OVERRIDES_FILE", tmp_path / "config_overrides.json")
    return agent_mod.TradingAgent(cfg)


def _write_learning(tmp_path, **fields):
    base = {"buckets": {}, "adjustments_used": 0, "trades_seen": 0,
            "trades_at_last_change": 0, "last_change_day": None, "history": []}
    base.update(fields)
    agent_mod.LEARNING_FILE.write_text(json.dumps(base), encoding="utf-8")
    return base


def _losing_range_bucket(trades=12, avg_r=-0.4):
    return {"range:<0.75": {"trades": trades, "wins": 1, "sum_r": round(avg_r * trades, 2)}}


# --------------------------------------------------------------------- auto-apply
def test_review_and_refine_auto_applies_a_bounded_override_when_evidence_and_gates_pass(tmp_path, monkeypatch):
    cfg = _cfg_with_tuning()
    agent = _agent(tmp_path, cfg, monkeypatch)
    _write_learning(tmp_path, buckets=_losing_range_bucket(), trades_seen=25)

    agent.review_and_refine(DAY_KEY)

    overrides = json.loads(agent_mod.OVERRIDES_FILE.read_text(encoding="utf-8"))
    assert overrides == {"strategy.range_atr_min": 0.35}  # 0.3 + step(0.05)

    led = json.loads(agent_mod.LEARNING_FILE.read_text(encoding="utf-8"))
    assert led["adjustments_used"] == 1
    assert led["trades_at_last_change"] == 25
    assert led["last_change_day"] == DAY_KEY
    assert led["history"][-1]["param"] == "strategy.range_atr_min"

    assert any(f["kind"] == "adjustment" for f in agent.feed)


def test_review_and_refine_does_nothing_without_a_losing_bucket(tmp_path, monkeypatch):
    cfg = _cfg_with_tuning()
    agent = _agent(tmp_path, cfg, monkeypatch)
    _write_learning(tmp_path, buckets={"range:<0.75": {"trades": 12, "wins": 8, "sum_r": 6.0}},
                    trades_seen=25)  # a WINNING bucket -- no candidate

    agent.review_and_refine(DAY_KEY)

    assert not agent_mod.OVERRIDES_FILE.exists()
    assert not agent_mod.SUGGESTIONS_FILE.exists()


# --------------------------------------------------------------------- evidence gates
def test_review_and_refine_blocks_on_too_few_trades_since_last_change(tmp_path, monkeypatch):
    cfg = _cfg_with_tuning()
    agent = _agent(tmp_path, cfg, monkeypatch)
    _write_learning(tmp_path, buckets=_losing_range_bucket(), trades_seen=15,
                    trades_at_last_change=0)  # only 15 new trades, gate wants 20

    agent.review_and_refine(DAY_KEY)

    assert not agent_mod.OVERRIDES_FILE.exists()
    assert not agent_mod.SUGGESTIONS_FILE.exists()


def test_review_and_refine_blocks_on_too_few_days_since_last_change(tmp_path, monkeypatch):
    cfg = _cfg_with_tuning()
    agent = _agent(tmp_path, cfg, monkeypatch)
    _write_learning(tmp_path, buckets=_losing_range_bucket(), trades_seen=30,
                    trades_at_last_change=0, last_change_day=DAY_KEY)  # gap == 0 days

    agent.review_and_refine(DAY_KEY)

    assert not agent_mod.OVERRIDES_FILE.exists()
    assert not agent_mod.SUGGESTIONS_FILE.exists()


# --------------------------------------------------------------------- suggestions once spent
def test_review_and_refine_becomes_a_pending_suggestion_once_budget_is_spent(tmp_path, monkeypatch):
    cfg = _cfg_with_tuning()
    agent = _agent(tmp_path, cfg, monkeypatch)
    _write_learning(tmp_path, buckets=_losing_range_bucket(), trades_seen=25,
                    adjustments_used=15)  # budget (15) already spent

    agent.review_and_refine(DAY_KEY)

    assert not agent_mod.OVERRIDES_FILE.exists()
    sugg = json.loads(agent_mod.SUGGESTIONS_FILE.read_text(encoding="utf-8"))
    assert len(sugg) == 1
    assert sugg[0]["status"] == "pending"
    assert sugg[0]["param"] == "strategy.range_atr_min"


def test_review_and_refine_does_not_duplicate_a_pending_suggestion(tmp_path, monkeypatch):
    cfg = _cfg_with_tuning()
    agent = _agent(tmp_path, cfg, monkeypatch)
    _write_learning(tmp_path, buckets=_losing_range_bucket(), trades_seen=25,
                    adjustments_used=15)

    agent.review_and_refine(DAY_KEY)
    agent.review_and_refine(DAY_KEY)  # same evidence, called again

    sugg = json.loads(agent_mod.SUGGESTIONS_FILE.read_text(encoding="utf-8"))
    assert len(sugg) == 1  # not two


# --------------------------------------------------------------------- whitelist enforcement
def test_apply_override_refuses_a_non_whitelisted_param(tmp_path, monkeypatch):
    cfg = _cfg_with_tuning()
    agent = _agent(tmp_path, cfg, monkeypatch)

    assert agent._apply_override("risk.daily_loss_limit_pct", 10.0) is False
    assert not agent_mod.OVERRIDES_FILE.exists()


def test_apply_override_refuses_an_out_of_bounds_value(tmp_path, monkeypatch):
    cfg = _cfg_with_tuning()
    agent = _agent(tmp_path, cfg, monkeypatch)

    assert agent._apply_override("strategy.range_atr_min", 0.95) is False  # max is 0.8
    assert not agent_mod.OVERRIDES_FILE.exists()


def test_apply_override_accepts_an_in_bounds_whitelisted_value(tmp_path, monkeypatch):
    cfg = _cfg_with_tuning()
    agent = _agent(tmp_path, cfg, monkeypatch)

    assert agent._apply_override("strategy.range_atr_min", 0.35) is True
    overrides = json.loads(agent_mod.OVERRIDES_FILE.read_text(encoding="utf-8"))
    assert overrides == {"strategy.range_atr_min": 0.35}


# --------------------------------------------------------------------- approve/reject flow
def test_apply_approved_suggestions_applies_an_in_bounds_approved_suggestion(tmp_path, monkeypatch):
    cfg = _cfg_with_tuning()
    agent = _agent(tmp_path, cfg, monkeypatch)
    agent_mod.SUGGESTIONS_FILE.write_text(json.dumps([
        {"id": "sg1", "created": DAY_KEY, "status": "approved",
         "param": "strategy.range_atr_min", "from": 0.3, "to": 0.35,
         "why": "test evidence", "evidence": "12 trades at -0.40R"},
    ]), encoding="utf-8")

    changed = agent.apply_approved_suggestions()

    assert changed is True
    overrides = json.loads(agent_mod.OVERRIDES_FILE.read_text(encoding="utf-8"))
    assert overrides == {"strategy.range_atr_min": 0.35}
    sugg = json.loads(agent_mod.SUGGESTIONS_FILE.read_text(encoding="utf-8"))
    assert sugg[0]["status"] == "applied"
    assert any("You approved it" in f["text"] for f in agent.feed)


def test_apply_approved_suggestions_rejects_an_out_of_bounds_approved_suggestion(tmp_path, monkeypatch):
    cfg = _cfg_with_tuning()
    agent = _agent(tmp_path, cfg, monkeypatch)
    agent_mod.SUGGESTIONS_FILE.write_text(json.dumps([
        {"id": "sg2", "created": DAY_KEY, "status": "approved",
         "param": "strategy.range_atr_min", "from": 0.3, "to": 0.95,
         "why": "test evidence", "evidence": "bad data"},
    ]), encoding="utf-8")

    agent.apply_approved_suggestions()

    assert not agent_mod.OVERRIDES_FILE.exists()
    sugg = json.loads(agent_mod.SUGGESTIONS_FILE.read_text(encoding="utf-8"))
    assert sugg[0]["status"] == "rejected"

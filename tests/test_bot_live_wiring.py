"""Tests for bot.py's broker-agnostic plumbing added for live trading: the bar-fetch
fallback (data_feed/broker_feed.py vs Yahoo/TwelveData) and the dashboard kill-switch flag.
No network access -- data_feed and broker calls are monkeypatched/faked throughout.
"""
from datetime import datetime, timezone

import pandas as pd
import pytest

import bot
import data_feed

from tests.helpers import make_cfg


def _bars(price=100.0, stale=False, now=None):
    now = now or datetime.now(timezone.utc)
    ts = now if not stale else now.replace(year=now.year - 1)
    return pd.DataFrame(
        {"Open": [price], "High": [price], "Low": [price], "Close": [price], "Volume": [1]},
        index=pd.DatetimeIndex([ts], tz=timezone.utc))


class _FakeBroker:
    def __init__(self, bars):
        self._bars = bars

    def get_bars(self, asset, interval="1m"):
        return self._bars


def test_fetch_bars_uses_yahoo_when_provider_is_paper(monkeypatch):
    cfg = make_cfg()  # broker.provider defaults to "paper"
    called = {}

    def fake_get_recent_bars(ticker, now_utc=None, twelvedata_symbol=None):
        called["ticker"] = ticker
        return _bars(100.0)

    monkeypatch.setattr(data_feed, "get_recent_bars", fake_get_recent_bars)
    bars, src = bot.fetch_bars(cfg, broker=None, asset="GOLD", now_utc=datetime.now(timezone.utc))
    assert src == "yahoo"
    assert called["ticker"] == "GC=F"
    assert not bars.empty


def test_fetch_bars_prefers_the_broker_feed_when_fresh(monkeypatch):
    cfg = make_cfg(**{"broker.provider": "ctrader"})
    now = datetime.now(timezone.utc)
    broker = _FakeBroker(_bars(150.0, now=now))

    def fail_if_called(*a, **kw):
        raise AssertionError("Yahoo/TwelveData should not be hit when the broker feed is fresh")

    monkeypatch.setattr(data_feed, "get_recent_bars", fail_if_called)
    bars, src = bot.fetch_bars(cfg, broker, "GOLD", now)
    assert src == "broker"
    assert float(bars["Close"].iloc[-1]) == 150.0


def test_fetch_bars_falls_back_when_broker_feed_is_stale(monkeypatch):
    cfg = make_cfg(**{"broker.provider": "ctrader"})
    now = datetime.now(timezone.utc)
    broker = _FakeBroker(_bars(150.0, stale=True, now=now))

    monkeypatch.setattr(data_feed, "get_recent_bars", lambda *a, **kw: _bars(101.0, now=now))
    bars, src = bot.fetch_bars(cfg, broker, "GOLD", now)
    assert src == "fallback"
    assert float(bars["Close"].iloc[-1]) == 101.0


def test_fetch_bars_falls_back_when_broker_feed_raises(monkeypatch):
    cfg = make_cfg(**{"broker.provider": "mt5"})
    now = datetime.now(timezone.utc)

    class _Boom:
        def get_bars(self, asset, interval="1m"):
            raise RuntimeError("connection dropped")

    monkeypatch.setattr(data_feed, "get_recent_bars", lambda *a, **kw: _bars(99.0, now=now))
    bars, src = bot.fetch_bars(cfg, _Boom(), "GOLD", now)
    assert src == "fallback"
    assert float(bars["Close"].iloc[-1]) == 99.0


def test_halt_requested_reflects_the_flag_file(tmp_path, monkeypatch):
    monkeypatch.setattr(bot, "HALT_FLAG", tmp_path / "halt.flag")
    assert not bot.halt_requested()
    (tmp_path / "halt.flag").write_text("{}")
    assert bot.halt_requested()

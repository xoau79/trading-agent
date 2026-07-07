"""Tests for dashboard_server.py's /api/halt kill-switch handler -- the write/clear side of
the same halt.flag mechanism bot.py's halt_requested() reads (see
tests/test_bot_live_wiring.py::test_halt_requested_reflects_the_flag_file). Exercises the
handler method directly (no real HTTP socket) by bypassing BaseHTTPRequestHandler.__init__,
which normally requires a live connection.
"""
import json

import dashboard_server as ds


class _RecordingHandler(ds.Handler):
    """Same _halt() logic as the real handler, but __init__ is skipped (no socket) and
    _json() just records what would have been sent instead of writing to a real client."""

    def __init__(self):
        self.responses = []

    def _json(self, code, obj):
        self.responses.append((code, obj))


def test_halt_action_writes_the_flag_file(tmp_path, monkeypatch):
    flag = tmp_path / "halt.flag"
    monkeypatch.setattr(ds, "HALT_FLAG", flag)
    h = _RecordingHandler()
    h._halt({"action": "halt"})
    assert flag.exists()
    payload = json.loads(flag.read_text(encoding="utf-8"))
    assert payload["by"] == "dashboard"
    assert h.responses[0][0] == 200
    assert h.responses[0][1]["halted"] is True


def test_clear_action_removes_the_flag_file(tmp_path, monkeypatch):
    flag = tmp_path / "halt.flag"
    flag.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(ds, "HALT_FLAG", flag)
    h = _RecordingHandler()
    h._halt({"action": "clear"})
    assert not flag.exists()
    assert h.responses[0][0] == 200
    assert h.responses[0][1]["halted"] is False


def test_clear_action_is_a_no_op_when_no_flag_exists(tmp_path, monkeypatch):
    flag = tmp_path / "halt.flag"
    monkeypatch.setattr(ds, "HALT_FLAG", flag)
    h = _RecordingHandler()
    h._halt({"action": "clear"})  # must not raise
    assert h.responses[0][0] == 200


def test_invalid_action_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "HALT_FLAG", tmp_path / "halt.flag")
    h = _RecordingHandler()
    h._halt({"action": "bogus"})
    assert h.responses[0][0] == 400

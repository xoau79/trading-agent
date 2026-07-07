"""Local dashboard server — http://localhost:8765

Serves the dashboard folder and gives the page two write-capable endpoints
(a static page can't save button clicks on its own):

    POST /api/decision  {"id": "...", "decision": "approved"|"rejected"}
        -> updates journal/suggestions.json; the bot applies approved ones
           at its next session start.
    POST /api/backtest  {"assets": ["GOLD","ES"], "session": "both", "days": 30}
        -> spawns backtest.py as a subprocess (one at a time); the page polls
           backtests/status.json for progress and results.

Bound to 127.0.0.1 only — nothing outside this PC can reach it.
"""
import json
import logging
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent
DASHBOARD = BASE / "dashboard"
SUGGESTIONS = BASE / "journal" / "suggestions.json"
BACKTESTS_DIR = DASHBOARD / "backtests"
STATUS = BACKTESTS_DIR / "status.json"
DATA_JS = DASHBOARD / "data.js"
HALT_FLAG = BASE / "halt.flag"  # bot.py's live loop watches this -- see bot.py's halt_requested()
BT_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[logging.FileHandler(BASE / "logs" / "dashboard_server.log", encoding="utf-8")])
log = logging.getLogger("dashboard_server")

_bt_proc = None
_bt_lock = threading.Lock()
_bot_proc = None
_bot_lock = threading.Lock()


def _write_status(payload):
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(payload), encoding="utf-8")


def _data_age_seconds():
    """Seconds since the bot last wrote data.js, or None if unknown.

    Any live bot (scheduled OR server-launched) rewrites data.js every ~45s, so a
    fresh file is a reliable 'a bot is already running' signal — this is how the
    wake button avoids ever starting a second bot, even one Task Scheduler began.
    """
    try:
        txt = DATA_JS.read_text(encoding="utf-8")
        i, j = txt.find("{"), txt.rfind("}")
        gen = json.loads(txt[i:j + 1])["generated_utc"]
        dt = datetime.fromisoformat(gen)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except Exception:
        return None


def _live_session():
    """Name of the session whose window contains 'now', or None.

    Reuses bot.session_window so the dashboard and bot agree on timing. Imported
    lazily so a heavy or broken import can never take down the dashboard server.
    """
    try:
        import bot as bot_mod
        cfg = bot_mod.load_cfg()
        now = datetime.now(timezone.utc)
        for name in cfg["sessions"]:
            open_utc, close_utc = bot_mod.session_window(cfg, name)
            if open_utc <= now < close_utc:
                return name
    except Exception as e:
        log.warning("session-window check failed: %s", e)
    return None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DASHBOARD), **kw)

    def log_message(self, fmt, *args):  # quiet the per-request console spam
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/suggestions":
            try:
                sugg = json.loads(SUGGESTIONS.read_text(encoding="utf-8")) \
                    if SUGGESTIONS.exists() else []
            except Exception:
                sugg = []
            return self._json(200, sugg)
        return super().do_GET()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json(400, {"error": "bad json"})
        if self.path == "/api/decision":
            return self._decide(data)
        if self.path == "/api/backtest":
            return self._backtest(data)
        if self.path == "/api/backtest/delete":
            return self._delete_backtest(data)
        if self.path == "/api/wake":
            return self._wake(data)
        if self.path == "/api/halt":
            return self._halt(data)
        return self._json(404, {"error": "unknown endpoint"})

    def _decide(self, data):
        sid, decision = data.get("id"), data.get("decision")
        if decision not in ("approved", "rejected"):
            return self._json(400, {"error": "decision must be approved/rejected"})
        try:
            sugg = json.loads(SUGGESTIONS.read_text(encoding="utf-8")) \
                if SUGGESTIONS.exists() else []
        except Exception:
            sugg = []
        hit = False
        for s in sugg:
            if s.get("id") == sid and s.get("status") == "pending":
                s["status"] = decision
                hit = True
        if not hit:
            return self._json(404, {"error": "suggestion not found or already decided"})
        tmp = str(SUGGESTIONS) + ".tmp"
        Path(tmp).write_text(json.dumps(sugg, indent=1), encoding="utf-8")
        Path(tmp).replace(SUGGESTIONS)
        log.info("suggestion %s -> %s", sid, decision)
        note = ("It will take effect at the next session start."
                if decision == "approved" else "Archived — the agent won't re-propose it soon.")
        return self._json(200, {"ok": True, "note": note})

    def _backtest(self, data):
        global _bt_proc
        assets = data.get("assets") or []
        session = data.get("session", "both")
        days = int(data.get("days", 30))
        if not assets:
            return self._json(400, {"error": "pick at least one asset"})
        with _bt_lock:
            if _bt_proc is not None and _bt_proc.poll() is None:
                return self._json(409, {"error": "a backtest is already running"})
            _write_status({"running": True, "pct": 0,
                           "msg": "starting backtest process..."})
            _bt_proc = subprocess.Popen(
                [sys.executable, str(BASE / "backtest.py"),
                 "--assets", ",".join(assets), "--session", session,
                 "--days", str(days)],
                cwd=str(BASE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            proc = _bt_proc

        def watch():
            code = proc.wait()
            if code != 0:  # backtest.py writes its own success status
                _write_status({"running": False, "pct": 100,
                               "msg": f"backtest failed (exit {code}) — see logs",
                               "error": True})
        threading.Thread(target=watch, daemon=True).start()
        log.info("backtest started: %s %s %sd", assets, session, days)
        return self._json(200, {"ok": True})

    def _delete_backtest(self, data):
        bt_id = data.get("id", "")
        if not BT_ID_RE.fullmatch(bt_id or ""):
            return self._json(400, {"error": "invalid id"})
        index_file = BACKTESTS_DIR / "index.json"
        try:
            index = json.loads(index_file.read_text(encoding="utf-8")) if index_file.exists() else []
        except Exception:
            index = []
        new_index = [x for x in index if x.get("id") != bt_id]
        if len(new_index) == len(index):
            return self._json(404, {"error": "run not found"})
        tmp = str(index_file) + ".tmp"
        Path(tmp).write_text(json.dumps(new_index, indent=1), encoding="utf-8")
        Path(tmp).replace(index_file)
        result_file = BACKTESTS_DIR / f"{bt_id}.json"
        if result_file.exists():
            result_file.unlink()
        log.info("backtest run deleted: %s", bt_id)
        return self._json(200, {"ok": True})

    def _wake(self, data):
        """Relaunch the bot for the currently-live session.

        Refuses (a) outside any session window — nothing to wake into — and
        (b) when a bot already appears to be running, judged by data.js freshness
        so a second bot can never be started alongside the scheduled one.
        """
        global _bot_proc
        session = _live_session()
        if not session:
            return self._json(409, {"error": "No session is live right now — the bot only "
                                    "runs inside a scheduled session window, so there's "
                                    "nothing to wake into."})
        age = _data_age_seconds()
        with _bot_lock:
            ours_alive = _bot_proc is not None and _bot_proc.poll() is None
            if ours_alive or (age is not None and age < 120):
                msg = "The bot already appears to be running"
                if age is not None:
                    msg += f" (data updated {int(age)}s ago)"
                return self._json(409, {"error": msg + "."})
            _bot_proc = subprocess.Popen(
                [sys.executable, str(BASE / "bot.py"), "--session", session],
                cwd=str(BASE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        log.info("wake: launched bot.py --session %s", session)
        return self._json(200, {"ok": True, "session": session,
                                "note": f"Waking the bot for the {session} session — "
                                "it should be live again within a minute."})


    def _halt(self, data):
        """Kill switch: writes/removes halt.flag, which bot.py's live loop checks every
        iteration (see bot.py's halt_requested()). Flattens everything and halts trading
        while the flag exists; clearing it resumes normal rules (a daily-loss halt still
        persists per the existing rules -- this only ever clears the manual kill switch).
        Purely a file write here — this process never talks to the broker directly, on
        purpose, so the dashboard can only make things safer, never riskier.
        """
        action = data.get("action")
        if action == "halt":
            HALT_FLAG.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps({"requested_utc": datetime.now(timezone.utc).isoformat(),
                                  "by": "dashboard"})
            tmp = str(HALT_FLAG) + ".tmp"
            Path(tmp).write_text(payload, encoding="utf-8")
            Path(tmp).replace(HALT_FLAG)
            log.warning("kill switch armed from the dashboard")
            return self._json(200, {"ok": True, "halted": True,
                                    "note": "Kill switch armed — the bot will flatten and "
                                    "halt within its next loop iteration (up to ~45s)."})
        if action == "clear":
            HALT_FLAG.unlink(missing_ok=True)
            log.info("kill switch cleared from the dashboard")
            return self._json(200, {"ok": True, "halted": False,
                                    "note": "Kill switch cleared — normal trading rules "
                                    "resume (a daily-loss halt, if any, still stands until "
                                    "tomorrow)."})
        return self._json(400, {"error": "action must be 'halt' or 'clear'"})


def main():
    (BASE / "logs").mkdir(exist_ok=True)
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    except OSError as e:
        log.error("port 8765 unavailable: %s", e)
        sys.exit(1)
    log.info("dashboard server on http://localhost:8765")
    srv.serve_forever()


if __name__ == "__main__":
    main()

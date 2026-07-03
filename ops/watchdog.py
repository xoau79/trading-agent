"""Dead-man's-switch for the live trading loop.

Run this on its own scheduled task every 5 minutes (see register_tasks.ps1 ->
TradingAgent-Watchdog). It exists because of a real incident: on 2026-07-02, bot.py hung
indefinitely on a stalled Yahoo Finance call with no exception and no timeout, leaving two
positions open for 24+ hours and silently blocking every subsequent scheduled run (Windows
Task Scheduler's IgnoreNew policy skips new runs while a previous one is still "running").
data_feed/yahoo.py now bounds every call with a hard timeout, which should prevent this from
recurring — this watchdog is the second line of defense in case something else ever hangs.

Logic, once per run:
    1. Read journal/heartbeat.json (written by bot.py every completed loop iteration).
    2. No heartbeat, or a fresh one -> nothing to do, exit quietly.
    3. A stale heartbeat while we're still inside that session's trading window -> the loop
       is hung. Kill it, flatten any open positions at a fresh price, alert Discord, and
       restart the session (time permitting).
    4. A stale heartbeat outside any session window -> normal idle state, do nothing.
"""
import json
import logging
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
load_dotenv(BASE / ".env")

import bot as bot_mod  # noqa: E402
import broker as broker_mod  # noqa: E402
import journal  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s watchdog: %(message)s",
    handlers=[logging.FileHandler(BASE / "logs" / "watchdog.log", encoding="utf-8"),
              logging.StreamHandler()])
log = logging.getLogger("watchdog")

STALE_THRESHOLD_MIN = 3  # loop cadence is ~45s; 3 min of silence is unambiguous


def _discord(content):
    url = os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        return
    try:
        body = json.dumps({"content": content[:1900], "username": "Watchdog"}).encode()
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": "TradingAgent-Watchdog/1.0"})
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:
        log.warning("discord alert failed: %s", e)


def _kill(pid):
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                       capture_output=True, text=True, timeout=15, check=False)
        log.info("killed hung process PID %s", pid)
        return True
    except Exception as e:
        log.warning("could not kill PID %s (may already be gone): %s", pid, e)
        return False


def main():
    (BASE / "logs").mkdir(exist_ok=True)
    hb_file = journal.HEARTBEAT_FILE
    if not hb_file.exists():
        log.info("no heartbeat file — bot has never run or nothing to check")
        return
    try:
        hb = json.loads(hb_file.read_text(encoding="utf-8"))
        last = datetime.fromisoformat(hb["t"])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
    except Exception as e:
        log.warning("unreadable heartbeat file: %s", e)
        return

    age_min = (datetime.now(timezone.utc) - last).total_seconds() / 60.0
    if age_min < STALE_THRESHOLD_MIN:
        log.info("heartbeat fresh (%.1f min old) — bot is alive", age_min)
        return

    session_name, pid = hb.get("session"), hb.get("pid")
    cfg = bot_mod.load_cfg()
    if session_name not in cfg["sessions"]:
        log.warning("heartbeat names unknown session %r — ignoring", session_name)
        return
    open_utc, close_utc = bot_mod.session_window(cfg, session_name)
    now = datetime.now(timezone.utc)
    if not (open_utc <= now < close_utc):
        log.info("heartbeat is %.1f min stale but %s session window has ended — normal idle, "
                 "no action", age_min, session_name)
        return

    log.error("heartbeat is %.1f min stale WHILE %s session is live (PID %s) — treating as hung",
              age_min, session_name, pid)
    if pid:
        _kill(pid)

    broker = broker_mod.PaperBroker(cfg)
    bot_mod.recover_stale_positions(cfg, broker, agent=None)

    resume_note = ""
    if now < close_utc - timedelta(minutes=2):
        subprocess.Popen([sys.executable, str(BASE / "bot.py"), "--session", session_name],
                         cwd=str(BASE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        resume_note = " Restarting it now for the rest of the session."
        log.info("relaunched bot.py --session %s", session_name)
    else:
        resume_note = " Too little of the session remains to restart — standing down until the next one."

    _discord(f"🛡️ Watchdog: {session_name} session went silent for {age_min:.0f} min (hung, no "
             f"error raised) — killed it, flattened any open positions at current price, and "
             f"logged the recovery.{resume_note}")


if __name__ == "__main__":
    main()

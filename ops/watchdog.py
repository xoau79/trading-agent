"""Mid-session dead-bot watchdog.

The in-process dead-man's-switch was removed in PR #6 (docs/ARCHITECTURE.md / git history);
since then a bot crash mid-session has no signal at all away from the dashboard -- during
school term the dashboard is only reachable from home, so a silent death could go unnoticed
for hours. This script is the replacement: run it on a short interval (Task Scheduler,
every ~15 min on weekdays -- see ops/register_tasks.ps1's Watchdog task) and it posts to
Discord the moment `dashboard/data.js` stops being fresh during a live session, or the moment
the bot's own status line reports an emergency/aborted stop.

Deliberately checks only the *live* window [open_utc, close_utc], not the pre-open wait --
the Sydney wall-clock lead time before a session's open varies with each session's own DST
calendar (config.json's sessions.asia.open_time_note has the full rationale), so a fixed
"pre-open buffer" here would either miss part of the wait or false-positive before the
scheduled task has even launched. Once a session is truly open, the live loop exports
dashboard/data.js every ~45s (bot.py's LOOP_SECONDS) -- if that has gone stale, something is
genuinely wrong, whether the cause is a crash, a hang, or the scheduled task never starting.

Read-only against the trading system: this only ever reads config.json/data.js and posts to
Discord. It has no path to config_overrides.json, state.json, or halt.flag.

Usage:
    python ops/watchdog.py                    # real run, real Discord post
    python ops/watchdog.py --dry-run           # print what would be posted, don't post
    python ops/watchdog.py --now 2026-07-08T02:15:00+00:00 --dry-run   # simulate a given time
"""
import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))  # so `python ops/watchdog.py` can import the repo's modules

import bot as bot_mod  # noqa: E402
from ops.notify import discord_post  # noqa: E402

DATA_JS = BASE / "dashboard" / "data.js"
STATE_FILE = BASE / "logs" / "watchdog_state.json"
STALE_MINUTES = 5
DEAD_KEYWORDS = ("emergency stop", "aborted")

log = logging.getLogger("ops.watchdog")


def _read_data_js(path):
    """Same tolerant parse dashboard_server.py's _data_age_seconds uses: data.js is
    `window.DATA = {...};`, so slice out the JSON object between the first `{` and the last
    `}` rather than depending on the exact JS wrapper."""
    try:
        txt = Path(path).read_text(encoding="utf-8")
        i, j = txt.find("{"), txt.rfind("}")
        return json.loads(txt[i:j + 1])
    except Exception as e:
        log.warning("could not read/parse %s: %s", path, e)
        return None


def _load_state(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + ".tmp"
    Path(tmp).write_text(json.dumps(state), encoding="utf-8")
    Path(tmp).replace(path)


def current_session(cfg, now_utc):
    """(session_name, day_key, open_utc, close_utc) for the session whose live window
    contains now_utc, or None if no session is live."""
    for name, scfg in cfg["sessions"].items():
        tz_date = now_utc.astimezone(bot_mod.ZoneInfo(scfg["open_tz"])).date().isoformat()
        open_utc, close_utc = bot_mod.session_window(cfg, name, date_str=tz_date)
        if open_utc <= now_utc < close_utc:
            return name, bot_mod.day_key_for(cfg, open_utc), open_utc, close_utc
    return None


def check(now_utc, data_js=DATA_JS, state_file=STATE_FILE, stale_minutes=STALE_MINUTES,
          dry_run=False):
    """Returns a human-readable status line; posts to Discord (at most once per session) if
    the bot looks dead."""
    cfg = bot_mod.load_cfg()
    live = current_session(cfg, now_utc)
    if not live:
        return "no session is currently live — nothing to watch"
    session, day_key, open_utc, close_utc = live

    state = _load_state(state_file)
    if state.get("day_key") != day_key or state.get("session") != session:
        state = {"day_key": day_key, "session": session, "alerted": False}

    if state.get("alerted"):
        return f"{session} ({day_key}): already alerted this session — skipping"

    data = _read_data_js(data_js)
    reasons = []
    if data is None:
        reasons.append(f"{data_js} is missing or unparseable")
    else:
        try:
            gen = datetime.fromisoformat(data["generated_utc"])
            if gen.tzinfo is None:
                gen = gen.replace(tzinfo=timezone.utc)
            age = (now_utc - gen).total_seconds() / 60.0
            if age > stale_minutes:
                reasons.append(f"data.js is {age:.1f} min old (threshold {stale_minutes})")
        except Exception as e:
            reasons.append(f"data.js has no readable generated_utc ({e})")
        status = str(data.get("bot_status") or "").lower()
        if any(k in status for k in DEAD_KEYWORDS):
            reasons.append(f"bot_status reads: {data.get('bot_status')!r}")

    if not reasons:
        return f"{session} ({day_key}): bot looks alive"

    message = (f"⚠️ **Watchdog**: the {session} session ({day_key}) looks dead — "
              + "; ".join(reasons) + ". Check the dashboard or logs when you can; "
              "no automatic action was taken.")
    posted = discord_post(message, dry_run=dry_run)
    if posted and not dry_run:
        state["alerted"] = True
        _save_state(state_file, state)
    return message


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--now", help="ISO 8601 UTC timestamp to evaluate instead of the real "
                    "current time (for testing)")
    ap.add_argument("--dry-run", action="store_true", help="print instead of posting to Discord")
    ap.add_argument("--data-js", default=str(DATA_JS))
    ap.add_argument("--state-file", default=str(STATE_FILE))
    ap.add_argument("--stale-minutes", type=float, default=STALE_MINUTES)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    now_utc = (datetime.fromisoformat(args.now) if args.now
              else datetime.now(timezone.utc))
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    result = check(now_utc, data_js=Path(args.data_js), state_file=Path(args.state_file),
                   stale_minutes=args.stale_minutes, dry_run=args.dry_run)
    print(result)


if __name__ == "__main__":
    main()

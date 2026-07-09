"""Post-session Discord digest: everything worth knowing about a just-finished session in
one compact message, so a school-term day (Discord notifications only, no dashboard access)
still gives a full picture -- not just the entry/exit narration the agent already posts live.

Reuses journal.write_session_review()'s output (journal/<day>/session-review-<session>.md)
for the P&L/wins/losses/balance/per-asset-filter summary rather than recomputing it, adds the
one thing that file doesn't carry (each trade's individual exit reason) from
journal/trades.json, and scans the session's log file for WARNING/ERROR lines -- the agent
narrates entries/exits/halts to Discord already (agent.py, always at INFO level), so anything
logged at WARNING/ERROR is, by construction, something that has never reached Discord before:
a data-feed fallback, a dashboard export failure, a refused config override, a TradingView
timeout, etc.

Usage:
    python ops/session_digest.py --session newyork
    python ops/session_digest.py --session asia --day-key 2026-07-08 --dry-run
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))  # so `python ops/session_digest.py` can import the repo's modules

from ops.notify import discord_post  # noqa: E402

NOISE_LEVELS = (" WARNING ", " ERROR ", " CRITICAL ")


def _session_window(cfg, session_name, date_str):
    """A trimmed copy of bot.py's session_window() (date_str branch only) so this reporting
    script has no import dependency on bot.py/data_feed (and the yfinance/dotenv/news.py chain
    that pulls in) just to do calendar math."""
    scfg = cfg["sessions"][session_name]
    tz = ZoneInfo(scfg["open_tz"])
    hh, mm = map(int, scfg["open_time"].split(":"))
    y, mo, d = map(int, date_str.split("-"))
    open_utc = datetime(y, mo, d, hh, mm, tzinfo=tz).astimezone(timezone.utc)
    return open_utc, open_utc + timedelta(minutes=scfg["duration_minutes"])


def most_recent_session_day_key(base, session, now_utc=None):
    """The day_key (Sydney calendar date, matching journal.py's own day_key) of the most
    recently closed -- or currently live -- window for `session`.

    Not simply "today in Sydney": the New York session opens ~23:30 Sydney and closes ~06:00
    the NEXT Sydney day, and during the part of the year when Sydney is on daylight saving
    but New York isn't (roughly Nov-Mar), its open can convert to a Sydney date one day past
    the date the scheduled task actually launched on. Reconstructing the window the same way
    bot.py's day_key_for()/session_window() do -- rather than guessing "today" -- keeps this
    correct year-round without the task scheduler having to compute a date itself.
    """
    cfg = json.loads((base / "config.json").read_text(encoding="utf-8"))
    now_utc = now_utc or datetime.now(timezone.utc)
    home_tz = ZoneInfo(cfg.get("home_tz", "Australia/Sydney"))
    today_local = now_utc.astimezone(home_tz).date()
    windows = [_session_window(cfg, session, (today_local + timedelta(days=delta)).isoformat())
              for delta in (0, -1)]
    past = [w for w in windows if w[1] <= now_utc]
    if past:
        open_utc = max(past, key=lambda w: w[1])[0]
    else:
        live = [w for w in windows if w[0] <= now_utc < w[1]]
        open_utc = (live[0] if live else max(windows, key=lambda w: w[0]))[0]
    return open_utc.astimezone(home_tz).date().isoformat()


def most_recent_log_file(base, session):
    """The session's log files are stamped with the local wall-clock date the process
    actually launched on (bot.py's main(), datetime.now().strftime('%Y%m%d')) -- which, for
    the same DST-mismatch reason as above, isn't reliably day_key with dashes removed. Rather
    than re-deriving that launch date too, just take the most recently modified matching log
    file -- simple and correct regardless of DST, manual reruns, or clock quirks."""
    logs_dir = base / "logs"
    if not logs_dir.exists():
        return None
    candidates = sorted(logs_dir.glob(f"{session}_*.log"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def _session_review_summary(path):
    """Pull the bits worth quoting straight out of journal.write_session_review()'s markdown
    rather than recomputing them: the summary line, an optional halt line, and the per-asset
    notes list."""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    summary = next((line for line in lines if line.startswith("**Trades:**")), "")
    balance = next((line for line in lines if line.startswith("**Balance:**")), "")
    halt = next((line for line in lines if line.startswith("⚠️")), "")
    notes = [line for line in lines if line.startswith("- **")]
    return {"summary": summary, "balance": balance, "halt": halt, "notes": notes}


def _trades_for(trades_file, day_key, session):
    if not trades_file.exists():
        return []
    trades = json.loads(trades_file.read_text(encoding="utf-8"))
    return [t for t in trades if t.get("day_key") == day_key and t.get("session") == session]


def _log_noise(log_file):
    if not log_file.exists():
        return [], 0
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    hits = [line for line in lines if any(lvl in line for lvl in NOISE_LEVELS)]
    return hits, len(hits)


def build_digest(base, session, day_key, log_file):
    review = _session_review_summary(base / "journal" / day_key / f"session-review-{session}.md")
    trades = _trades_for(base / "journal" / "trades.json", day_key, session)
    noise, noise_count = _log_noise(log_file) if log_file else ([], 0)

    lines = [f"**Session digest — {session} — {day_key}**"]
    if review:
        if review["summary"]:
            lines.append(review["summary"])
        if review["balance"]:
            lines.append(review["balance"])
        if review["halt"]:
            lines.append(review["halt"])
    else:
        lines.append("(no session-review file found — session may not have run/completed yet)")

    if trades:
        lines.append("")
        lines.append("**Trades:**")
        for t in trades:
            lines.append(f"- #{t['trade_id']} {t['asset']} {t['direction']}: "
                         f"{t['entry_price']} → {t['exit_price']} ({t['exit_reason']}) "
                         f"{t['pnl']:+.2f} USD ({t['r_multiple']:+.2f}R)")

    if review and review["notes"]:
        lines.append("")
        lines.append("**Asset notes:**")
        lines.extend(review["notes"])

    lines.append("")
    if noise_count:
        lines.append(f"**{noise_count} warning/error log line(s)** (never surfaced to "
                     "Discord before) — most recent:")
        for noise_line in noise[-5:]:
            lines.append(f"`{noise_line[:180]}`")
    else:
        lines.append("No warnings/errors in the session log.")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--session", required=True, choices=["asia", "newyork"])
    ap.add_argument("--day-key", help="YYYY-MM-DD Sydney calendar date (default: the most "
                    "recently closed/live session's own day_key, worked out automatically)")
    ap.add_argument("--log-file", help="explicit log file path (default: the most recently "
                    "modified logs/<session>_*.log)")
    ap.add_argument("--base", default=str(BASE), help="repo root (override for testing)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base = Path(args.base)
    day_key = args.day_key or most_recent_session_day_key(base, args.session)
    log_file = Path(args.log_file) if args.log_file else most_recent_log_file(base, args.session)

    digest = build_digest(base, args.session, day_key, log_file)
    print(digest)
    discord_post(digest, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

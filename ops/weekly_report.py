"""Weekly Discord report: trade stats, lessons, learning buckets, and -- the thing Anthony is
specifically waiting on -- a countdown to the agent's next auto-tuning refinement
(agent.py's review_and_refine(), which has never fired in production; its evidence gates
require 20+ trades and 5+ days since the last change, so it takes real elapsed time to reach).

Reuses journal.compute_stats() for the trade-level numbers (win rate, profit factor, avg R,
per-asset breakdown) rather than recomputing them, and constructs a read-only TradingAgent
just to call its existing _find_candidate() -- the exact bucket-threshold logic
review_and_refine() itself uses -- so "what would the agent propose right now" is never a
second copy of that decision logic. Nothing here writes to config_overrides.json,
suggestions.json, or any risk-relevant file; it only reads.

Usage:
    python ops/weekly_report.py
    python ops/weekly_report.py --days 7 --dry-run
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))  # so `python ops/weekly_report.py` can import the repo's modules

import agent as agent_mod  # noqa: E402
import journal  # noqa: E402
from ops.notify import discord_post  # noqa: E402


def _load(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def _state_file(base, cfg):
    provider = cfg.get("broker", {}).get("provider", "paper")
    if provider == "paper":
        return base / "state.json"
    return base / f"state_live_{provider}.json"


def _tuning_gate_lines(cfg, led, today):
    tuning = cfg.get("tuning", {})
    budget = tuning.get("auto_budget", 15)
    used = led.get("adjustments_used", 0) if led else 0
    lines = [f"**Auto-tuning gate:** {used}/{budget} auto-refinements used."]
    if not led:
        lines.append("No learning data yet — the agent hasn't closed a trade to learn from.")
        return lines
    min_trades = tuning.get("min_trades_per_change", 20)
    trades_since = led.get("trades_seen", 0) - led.get("trades_at_last_change", 0)
    trades_left = max(0, min_trades - trades_since)
    min_days = tuning.get("min_days_between_changes", 5)
    last_day = led.get("last_change_day")
    if last_day:
        gap = (date.fromisoformat(today) - date.fromisoformat(last_day)).days
        days_left = max(0, min_days - gap)
    else:
        days_left = 0
    if trades_left or days_left:
        bits = []
        if trades_left:
            bits.append(f"{trades_left} more trade(s)")
        if days_left:
            bits.append(f"{days_left} more day(s)")
        lines.append(f"Next change needs: {' and '.join(bits)}.")
    else:
        lines.append("Gates are open — the next session-end review can apply a change.")
    return lines


def build_report(base, days, now_utc=None):
    now_utc = now_utc or datetime.now(timezone.utc)
    cfg = json.loads((base / "config.json").read_text(encoding="utf-8"))
    home_tz = cfg.get("home_tz", "Australia/Sydney")
    from zoneinfo import ZoneInfo
    today = now_utc.astimezone(ZoneInfo(home_tz)).date()
    cutoff = (today - timedelta(days=days - 1)).isoformat()

    all_trades = _load(base / "journal" / "trades.json", [])
    week_trades = [t for t in all_trades if t.get("day_key", "") >= cutoff]

    state = _load(_state_file(base, cfg), {})
    equity_curve = state.get("equity_curve", [])
    starting_balance = cfg.get("account", {}).get("starting_balance", 10000.0)
    stats = journal.compute_stats(week_trades, equity_curve, starting_balance)

    lessons = _load(base / "journal" / "lessons.json", [])
    week_lessons = [l for l in lessons if l.get("t", "") >= cutoff]

    led = _load(base / "journal" / "learning.json", None)
    min_bucket = cfg.get("tuning", {}).get("min_bucket_trades", 10)
    buckets = []
    if led:
        for key, b in led.get("buckets", {}).items():
            if b["trades"] >= min_bucket:
                buckets.append((key, b["trades"], round(b["sum_r"] / b["trades"], 2)))
        buckets.sort(key=lambda x: x[2])  # worst avg R first

    agent_mod.FEED_FILE = base / "journal" / "agent_feed.json"
    tmp_agent = agent_mod.TradingAgent(cfg, replay=True)
    candidate = tmp_agent._find_candidate(led) if led else None

    pending = [s for s in _load(base / "journal" / "suggestions.json", [])
              if s.get("status") == "pending"]

    def _or_dash(v, suffix=""):
        return "—" if v is None else f"{v}{suffix}"

    lines = [f"**Weekly report — week ending {today.isoformat()} ({days}d)**", ""]
    lines.append(f"Trades: {stats['total_trades']}  |  Wins: {stats['wins']}  |  "
                f"Losses: {stats['losses']}  |  Win rate: {_or_dash(stats['win_rate'], '%')}")
    lines.append(f"P&L: {stats['total_pnl']:+.2f} USD  |  "
                f"Profit factor: {_or_dash(stats['profit_factor'])}  |  "
                f"Avg R: {_or_dash(stats['avg_r'])}  |  "
                f"Max drawdown (all-time): {stats['max_drawdown']:.2f} USD")
    if stats["per_asset"]:
        lines.append("")
        lines.append("**Per asset:**")
        for asset, a in stats["per_asset"].items():
            lines.append(f"- {asset}: {a['trades']} trades, {a['wins']} wins, "
                         f"{a['pnl']:+.2f} USD")

    lines.append("")
    if week_lessons:
        lines.append("**Lessons this week:**")
        for l in week_lessons[-8:]:
            lines.append(f"- {l['text']}")
    else:
        lines.append("No lessons recorded this week.")

    lines.append("")
    if buckets:
        lines.append(f"**Learning buckets (≥{min_bucket} trades, worst avg R first):**")
        for key, n, avg in buckets[:8]:
            lines.append(f"- `{key}`: {n} trades, avg {avg:+.2f}R")
    else:
        lines.append("No learning buckets have enough trades yet.")

    lines.append("")
    lines.extend(_tuning_gate_lines(cfg, led, today.isoformat()))
    if candidate:
        lines.append(f"Next candidate refinement if the gates were open right now: "
                     f"`{candidate['param']}` {candidate['from']} → {candidate['to']} "
                     f"({candidate['why']})")

    lines.append("")
    if pending:
        lines.append(f"**{len(pending)} pending suggestion(s) awaiting your decision:**")
        for s in pending:
            lines.append(f"- `{s['param']}` {s['from']} → {s['to']}: {s['why']}")
    else:
        lines.append("No pending suggestions.")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--base", default=str(BASE), help="repo root (override for testing)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    report = build_report(Path(args.base), args.days)
    print(report)
    discord_post(report, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

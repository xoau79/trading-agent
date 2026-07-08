"""For each pending agent suggestion (journal/suggestions.json), run two sandboxed backtests
-- current config vs the proposed override -- and post the metric deltas to Discord, so
approving/rejecting on the dashboard is an evidence-based comparison rather than just the
bucket average agent.py already quoted in the suggestion text.

Both backtests run through backtest.py's existing sandbox (dashboard/backtests/work/), never
touching state.json, journal/, or config_overrides.json -- see backtest.py's sandbox()
docstring. The "proposed" run uses backtest.py --set, which is refused outright for anything
outside config.json's tuning.whitelist bounds (see backtest.py's apply_set_override()).

Usage:
    python ops/suggestion_evidence.py --days 30
    python ops/suggestion_evidence.py --days 14 --dry-run
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))  # so `python ops/suggestion_evidence.py` can import ops.notify

from ops.notify import discord_post  # noqa: E402

OUTDIR = BASE / "dashboard" / "backtests"


def _pending_suggestions(base):
    path = base / "journal" / "suggestions.json"
    if not path.exists():
        return []
    return [s for s in json.loads(path.read_text(encoding="utf-8")) if s.get("status") == "pending"]


def _run_backtest(assets, session, days, set_override=None):
    """Runs backtest.py as a subprocess (same mechanism dashboard_server.py's /api/backtest
    uses) and returns the parsed result dict, or None on failure."""
    cmd = [sys.executable, str(BASE / "backtest.py"), "--assets", ",".join(assets),
          "--session", session, "--days", str(days)]
    if set_override:
        cmd += ["--set", set_override]
    proc = subprocess.run(cmd, cwd=str(BASE), capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        return None, proc.stderr[-2000:]
    status_file = OUTDIR / "status.json"
    status = json.loads(status_file.read_text(encoding="utf-8")) if status_file.exists() else {}
    bt_id = status.get("result")
    if not bt_id:
        return None, "no backtest result id in status.json"
    result_file = OUTDIR / f"{bt_id}.json"
    if not result_file.exists():
        return None, f"result file {result_file} missing"
    return json.loads(result_file.read_text(encoding="utf-8")), None


def _delta_line(label, before, after, fmt="{:+.2f}"):
    if before is None or after is None:
        return f"- {label}: — → —"
    return f"- {label}: {fmt.format(before)} → {fmt.format(after)} ({fmt.format(after - before)})"


def build_evidence(cfg, suggestion, session, days):
    assets = list(cfg.get("backtest_assets", {}).keys()) or ["GOLD"]
    # Only backtest the sessions/assets the affected strategy param can actually influence --
    # everything in cfg.assets today, since ORB is the only strategy in the bank.
    assets = [a for a in assets if a in cfg.get("assets", {})] or assets[:3]

    base_result, base_err = _run_backtest(assets, session, days)
    if base_err:
        return f"⚠️ Baseline backtest failed for `{suggestion['param']}`: {base_err}"

    spec = f"{suggestion['param']}={suggestion['to']}"
    proposed_result, prop_err = _run_backtest(assets, session, days, set_override=spec)
    if prop_err:
        return f"⚠️ Proposed-config backtest failed for `{suggestion['param']}`: {prop_err}"

    b, p = base_result["stats"], proposed_result["stats"]
    lines = [f"**Evidence for pending suggestion:** `{suggestion['param']}` "
            f"{suggestion['from']} → {suggestion['to']}",
            f"_{suggestion['why']}_",
            f"(backtest: {', '.join(assets)}, {session}, last {days}d)", ""]
    lines.append(_delta_line("Net P&L (USD)", b.get("total_pnl"), p.get("total_pnl")))
    lines.append(_delta_line("Profit factor", b.get("profit_factor"), p.get("profit_factor")))
    lines.append(_delta_line("Win rate (%)", b.get("win_rate"), p.get("win_rate")))
    lines.append(_delta_line("Avg R", b.get("avg_r"), p.get("avg_r")))
    lines.append(_delta_line("Max drawdown (USD)", b.get("max_drawdown"), p.get("max_drawdown")))
    lines.append(f"- Trades: {b.get('total_trades')} → {p.get('total_trades')}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=29, help="Yahoo's free 1-min tier caps at ~30d")
    ap.add_argument("--session", default="both", choices=["asia", "newyork", "both"])
    ap.add_argument("--base", default=str(BASE), help="repo root (override for testing)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base = Path(args.base)
    cfg = json.loads((base / "config.json").read_text(encoding="utf-8"))
    pending = _pending_suggestions(base)
    if not pending:
        print("No pending suggestions — nothing to evidence.")
        return

    for s in pending:
        evidence = build_evidence(cfg, s, args.session, args.days)
        print(evidence)
        print()
        discord_post(evidence, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

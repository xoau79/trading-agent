# Workflow rules

This repo trades real strategies against (eventually) a live broker account. The workflow exists to make
sure nothing reaches `main` — and therefore nothing the scheduled tasks run — without you having actually
looked at it.

## The rule

1. **`main` is protected.** No direct pushes. Every change lands on a branch and goes through a Pull
   Request.
2. **Branch naming**: `fix/…` for bug fixes, `feat/…` for new capability, `docs/…` for documentation-only
   changes. Short, descriptive, kebab-case (e.g. `fix/data-feed-hang-and-notifications`).
3. **PR description** states what changed and why, and calls out anything that touches risk parameters
   (position sizing, stop/target logic, daily loss limits, trade caps) explicitly — those get the closest
   read.
4. **You merge.** Whoever opens the PR (including Claude) does not merge it. You review, you approve, you
   click merge.
5. **Secrets never enter git history.** Real values live in `.env` (gitignored). `.env.example` documents
   every variable with a placeholder. If a secret is ever accidentally committed, treat it as compromised —
   rotate it — reverting the commit is not sufficient once something is pushed.

## Where things go

See `docs/ARCHITECTURE.md` for the full layout. Quick reference:

| Kind of change | Goes in |
|---|---|
| A new/changed trading rule for an existing strategy | `strategies/<name>/strategy.py` + its `README.md` |
| A brand-new strategy | Copy `strategies/_template/`, follow its checklist |
| A rule that should apply no matter which strategy is running (drawdown limits, trade caps, position caps) | the broker/engine layer (`broker/paper.py`'s `can_open`/`check_daily_stop`) — never inside a strategy file |
| Broker connectivity (new broker, or changes to an existing adapter) | `broker/<name>_broker.py`, implementing `broker/base.py`'s interface |
| Price data source | `data_feed/` |
| Dashboard styling | must follow `DESIGN.md` — extend it in the same PR if something new is genuinely needed |
| Ops/scheduling/monitoring | `ops/` |
| Reference material (IBKR docs, etc.) | `docs/` |

## Before opening a PR that touches trading logic

- Run a replay of a known historical session and confirm the trade sequence is what you'd expect:
  `python bot.py --session newyork --backtest YYYY-MM-DD`
- If risk parameters changed, say so explicitly in the PR — these get extra scrutiny before merge.

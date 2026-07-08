# Working with Anthony on this repo

Read this once at session start. It's how Anthony works, not what the code does — for that, see `README.md` and `docs/ARCHITECTURE.md`.

## Stack, tools, clients, formats

- **Runtime**: Python (pinned `pythoncore-3.14-64` on Windows), stdlib-first — no web framework, no build step, no chart library (the dashboard is hand-rolled canvas + vanilla JS on purpose; see `DESIGN.md`). Deps are pinned in `requirements.txt`; `pytest` is dev-only.
- **Where it runs**: Anthony's home Windows PC (`C:\CLAUDE CODE\Sessions\trading-agent`), driven by Windows Task Scheduler (`ops/register_tasks.ps1` is the source of truth for every scheduled task — never hand-create one in the Task Scheduler UI).
- **His actual access pattern**: during school term (~90% of the year) the dashboard (`localhost:8765`) is *unreachable* — Discord is his only signal, checked in passing during sessions. He's only at the PC ~2h/week (weekends/after school). Design every automation for the Discord case first; the dashboard is the exception, not the default.
- **Client for remote signal**: one Discord webhook (`DISCORD_WEBHOOK_URL` in `.env`), used by both `agent.py`'s live narration and the `ops/` scripts (`ops/notify.py` is the shared helper — reuse it, don't open a second webhook path).
- **Data flow**: Yahoo Finance → TwelveData fallback → broker feed once a demo/live broker is connected (`data_feed/`). Brokers: `paper` (default, no real money) → `cTrader`/`MT5` demo → live, gated by two independent things that must both be true (`config.json`'s `live_trading.enabled` + `.env`'s `LIVE_TRADING_CONFIRM` matching the exact account id). He is currently at the **demo-verification stage** — see `skills/verify-demo-broker.md`.
- **Formats**: `config.json` = all tunable numbers (never hardcode a value that belongs there); `.env` = secrets (gitignored, `.env.example` documents every var with a placeholder); JSON is the machine store, matching human-readable Markdown is generated *from* it (`journal/trades.json` → `journal/<day>/trade-NN-ASSET.md`); every file the dashboard reads is written atomically (`_atomic_write`: write `.tmp`, `os.replace`) — copy that pattern for anything similar.

## Tone and writing rules

Plain language, why over what, and **honesty about limits is a house style, not an apology**. Docstrings and commit messages say what a decision costs or where it's approximate, in the same breath as stating it — don't polish that away.

> "Yahoo's free tier caps 1-minute data at ~30 days back — that is the honest limit of this backtest."
> "likely 'XAUUSD'; verify with `python ops/ctrader_smoke_test.py --symbols` against your own account, do not trust this guess"

Commit messages: what changed, why, and what proves it still works — never just "fix bug." Real example (`ec2b664`):
```text
Add cTrader/live-trading config groundwork; extract TradeLedger from PaperBroker

- broker/ledger.py: new TradeLedger holding the universal risk rules and
  state.json bookkeeping that used to live inline in broker/paper.py, so a
  live broker can share the exact same rules via a future LiveBroker facade
- broker/paper.py: delegates to TradeLedger; public API and behavior
  unchanged (see tests/test_paper_parity.py, a network-free end-to-end check)
```
Emoji: sparing, functional only (status icons in Discord/dashboard — `agent.py`'s `ICONS` dict), never decorative in prose. No filler ("Great question!", "I've successfully...") — state the result.

## Weekly tasks → which skill file covers it

| Task | Skill file |
|---|---|
| Review, test, and merge a PR | `skills/review-and-merge-prs.md` |
| Watch a live Asian/NY session | `skills/monitor-live-sessions.md` |
| Read the journal / weekly stats / tuning-gate countdown | `skills/review-journal-and-weekly-stats.md` |
| Run a backtest or single-date replay | `skills/run-backtests-and-replays.md` |
| Approve/reject a pending agent suggestion | `skills/decide-agent-suggestions.md` |
| Check feed health (Yahoo/ForexFactory/RSS/TradingView + broker parity) | `skills/check-feed-health.md` |
| Set up/verify a cTrader or MT5 demo account | `skills/verify-demo-broker.md` |

Each file: one-line trigger, exact steps in order, one real output example, mistakes to avoid (traced to an actual repo correction). Read the relevant one before doing the task, don't improvise the procedure.

## What a good day's output looks like

**A normal trading day**: both sessions launch on their Task Scheduler trigger with no manual intervention; every entry/exit/halt/skip is narrated to Discord *with a reason*, not just a result; `journal/<day>/trade-NN-ASSET.md` and `session-review-*.md` exist for every trade and session; the post-session Discord digest (`ops/session_digest.py`, auto-scheduled shortly after each session's latest possible close) posts without you having to trigger it; the account is flat by session end, always; `ops/watchdog.py` stays silent because nothing needed it to speak. See the worked example in `skills/monitor-live-sessions.md`.

**A normal dev day**: small, focused PRs on a `fix/`/`feat/`/`docs/` branch — never a direct push to `main`; `pytest` (network-free, `tests/` only) green before asking for review; a `bot.py --backtest` replay run and its trade sequence sanity-checked *before* opening any PR that touches strategy/risk/sizing logic; the PR body says what changed, why, and calls out explicitly if it touches position sizing, stop/target logic, daily loss limits, or trade caps; Anthony reviews and merges it himself — Claude never merges its own PR.

## Hard rules (violating these is always wrong, no exceptions)

1. Automation (`ops/*.py`, the dashboard server) never touches `config.json`'s risk caps, `broker.provider`, or the live-trading confirmation latch. Read-only or Discord-only.
2. Every external network call (price feed, calendar, RSS, TradingView, broker) gets a hard timeout. This was corrected *twice* in this repo's history for the same unbounded-hang bug (`data_feed/yahoo.py`, then `news.py` two days later) — treat "add a network call" and "add a timeout" as one action.
3. Backtests and replays are always sandboxed (own state file, own journal dir) — never touch `state.json`, the real `journal/`, or `config_overrides.json`.
4. Dashboard changes follow `DESIGN.md`; a genuinely new token/pattern gets added to `DESIGN.md` in the *same* PR, never invented inline.
5. `tests/` stays network-free; `pytest.ini` scopes bare `pytest` there on purpose (`ops/*_test.py` are manual/live scripts, not the suite).
6. Never guess a broker symbol or a config value marked as a placeholder — verify against the real account or source first.
7. `day_key` is the Sydney calendar date of a session's *open*, not "today" — a New York session can close on the day after it opened, Sydney time, depending on the time of year.
8. A secret that reaches git history is compromised the moment it's pushed — rotate it; reverting the commit is not sufficient.

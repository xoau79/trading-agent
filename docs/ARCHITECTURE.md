# Architecture

How the pieces fit together, and which are live today vs. scaffolded for later.

## Today (paper trading by default; cTrader/MT5 available)

```
Task Scheduler ──▶ bot.py --session {asia|newyork}
                       │
                       ├── data_feed/                ──▶ Yahoo Finance (default) / broker feed (live)
                       ├── strategies/orb/            ──▶ Opening Range Breakout signal logic
                       ├── broker/create_broker(cfg)  ──▶ PaperBroker, or LiveBroker(adapter) for mt5/ctrader
                       │     ├── broker/ledger.py     ──▶ universal risk limits + bookkeeping (shared)
                       │     ├── broker/paper.py      ──▶ simulated fills, no real money
                       │     └── broker/live.py       ──▶ safety latch, sanity checks, drawdown halt, reconcile
                       │           ├── broker/ctrader/       ──▶ Spotware Open API (IC Markets, prop firms)
                       │           └── broker/mt5_broker.py  ──▶ MetaTrader5 package (IC Markets, any MT5 broker)
                       ├── news.py                    ──▶ ForexFactory calendar, CNBC RSS, TradingView rating
                       ├── agent.py                   ──▶ narrates every decision, learns, proposes bounded tweaks, Discord
                       └── journal.py                 ──▶ trade archives, dashboard/data.js

dashboard_server.py ──▶ http://localhost:8765 (serves dashboard/, Approve/Reject + Backtest Lab + kill-switch endpoints)
```

One loop iteration (`Engine.step`, in `bot.py`) per ~45 seconds: pull fresh bars, manage any open position,
check for forced exits (news/daily-halt/kill-switch), hunt for a new entry via the assigned strategy.
Nothing about this loop changes based on which broker or strategy is configured — that's the point of the
interfaces below. TradingView has no order-execution API; it's used only as a 15-minute rating confluence
filter (`news.get_tv_rating`) and for chart widgets — execution is always cTrader or MT5.

## Broker abstraction (`broker/`)

`broker/base.py` defines the contract every broker adapter implements: `connect()`, `get_bars()`,
`get_price()`, `place_order()`, `close_position()`, `get_positions()`, `get_account_info()`. `Engine`
itself talks to a richer, PaperBroker-shaped surface (`state`, `can_open()`, `open_position()`,
`update_position()`, `close_position()`, `flatten_all()`, `start_session()`) that every broker
`create_broker(cfg)` can return also satisfies — see `broker/README.md`.

- **`broker/ledger.py`** — `TradeLedger`: the universal risk rules (daily loss limit, trade/position caps,
  consecutive-loss bench) and state-file bookkeeping. Extracted out of `paper.py` so a live broker gets
  exactly the same rules, not a reimplementation of them.
- **`broker/paper.py`** — the default. Simulated fills against real market prices, no real money.
- **`broker/live.py`** — `LiveBroker`: wraps a real adapter (below) in the Engine-facing surface, backed by
  its own `TradeLedger` (`state_live_<provider>.json`, never `state.json`). Owns the live-only safety
  mechanisms — see `broker/README.md`'s "Safety, by design" section.
- **`broker/ctrader/`** — IC Markets or any cTrader account (including prop-firm cTrader accounts) via
  Spotware's Open API, over a small JSON-over-WebSocket client. Inert until `.env` has
  `CTRADER_CLIENT_ID`/`CTRADER_CLIENT_SECRET`/`CTRADER_ACCOUNT_ID` (see `docs/ctrader_setup.md`) and
  `config.json`'s `broker.provider` is `"ctrader"`.
- **`broker/mt5_broker.py`** — IC Markets (or any MT5 broker) via the official `MetaTrader5` Python package,
  which talks to a locally-running MT5 terminal. Inert until `.env` has `MT5_LOGIN` / `MT5_PASSWORD` /
  `MT5_SERVER` and `config.json`'s `broker.provider` is `"mt5"`.
- **`broker/ibkr/ibkr_broker.py`** — Interactive Brokers via TWS/IB Gateway. Scaffolded stub; the reference
  material for building it out lives in `docs/ibkr/` (all 40 lessons from the TWS Python API, Client
  Portal/Web API, and related courses, organized by course).

Switching `broker.provider` in `config.json` is the only thing that changes which broker is live. Strategy
logic, risk limits, and the dashboard are unaffected. No dashboard control can change it — see
`DESIGN.md`'s "deliberate safety constraint" note.

## Price data (`data_feed/`)

- **`data_feed/yahoo.py`** — default source, hardened with explicit timeouts and retry/backoff (see
  `docs/` changelog / PR history for the hang postmortem this responds to).
- **`data_feed/twelvedata.py`** — automatic fallback when Yahoo is stale and `TWELVEDATA_API_KEY` is set.
- **`data_feed/broker_feed.py`** — once a live broker is connected (`broker.provider != "paper"`), price
  data comes from the broker itself instead of a third-party feed (`bot.py`'s `fetch_bars()`), falling
  back to Yahoo/TwelveData if the broker feed is missing or stale. Safe either way: a live position's
  stop/target executes server-side at the broker regardless of which bars the bot is reading, so the
  fallback can only affect entry timing and journaled excursions, never fills.

## Strategy library (`strategies/`)

`strategies/base.py` defines what a strategy must declare: entry rule, exit rule, `target_r_multiple`,
`risk_per_trade_pct`, applicable assets/sessions, and any filters. Each strategy lives in its own folder
with its own `strategy.py` and `README.md` explaining its rules in plain language — see
`strategies/README.md` for the full pattern and `strategies/orb/README.md` for the one strategy currently
live.

**Universal rules are not part of any strategy.** Daily loss limit, max trades per session/day, max
concurrent positions, consecutive-loss bench, leverage cap — these are enforced by `broker/ledger.py`'s
`TradeLedger` (`can_open()` / `check_daily_stop()`) for every strategy and every broker, unconditionally. A
strategy cannot loosen them; it only decides entries/exits within them.

## Dashboard

Static HTML (`dashboard/dashboard.html`) + a JSON data file (`dashboard/data.js`) the bot rewrites every
loop, served by a small stdlib HTTP server (`dashboard_server.py`) that also exposes write endpoints
(approve/reject agent suggestions, kick off a backtest, wake a sleeping session, the kill switch). No
frontend framework, no build step — open the HTML file's source to change it, following `DESIGN.md`. The
broker/account status block (provider, demo-vs-LIVE, connection state) comes from
`broker.status_payload()` via `journal.export_dashboard()`'s `broker_meta` — paper trading keeps its
original "paper account" look unchanged.

## Ops (`ops/`)

- **`ops/smoke_test.py`** — checks every external price/news/rating feed is reachable; `--discord`
  posts a summary to Discord on any FAIL instead of only printing to a console nobody's watching.
- **`ops/ctrader_auth.py`** — one-time OAuth setup for the cTrader adapter (authorize in a browser, saves a
  refreshable token, lists the accounts available to pick `CTRADER_ACCOUNT_ID` from).
- **`ops/ctrader_smoke_test.py`** — read-only cTrader connectivity check (account info, symbol resolution,
  trendbars, live spot).
- **`ops/mt5_smoke_test.py`** — the MT5 equivalent, read-only, run on the Windows box with the terminal open.
- **`ops/live_order_test.py`** — shared, explicitly opt-in (`--yes`): places one minimum-size order through
  the full `LiveBroker` path on a demo account (refuses live accounts outright), then closes it — the
  "did the whole pipeline actually work" check the read-only smoke tests can't cover.
- **`ops/feed_parity.py`** — compares a connected demo broker's bars/prices against Yahoo per
  asset (delta %, staleness) — the automated version of the symbol-mapping/price-scaling
  eyeball check `docs/ctrader_setup.md`'s "Known limitations" section asks for. No-ops cleanly
  while `broker.provider` is `paper`.
- **`ops/register_tasks.ps1`** — versioned Task Scheduler setup, so the automation is reproducible from the
  repo instead of living only in one machine's scheduler configuration.

### Discord-first ops (`ops/notify.py` + friends)

The dashboard (`dashboard_server.py`) only binds `127.0.0.1` — reachable at home, not during
school term. These scripts close that gap by posting to the same `DISCORD_WEBHOOK_URL`
webhook `agent.py` already uses (`ops/notify.py`'s `discord_post()`, same failure posture as
`agent.py`'s own `_discord()`: never raises, truncated, short timeout). All read-only against
the trading system and all support `--dry-run` (print instead of posting).

- **`ops/watchdog.py`** — the replacement for the in-process dead-man's-switch removed in PR #6:
  polled every 15 min (`TradingAgent-Watchdog`), posts to Discord the moment a *live* session's
  `dashboard/data.js` goes stale or the bot's own status reports an emergency/aborted stop.
  Rate-limited to one alert per session.
- **`ops/session_digest.py`** — a full post-session Discord summary (P&L, each trade's exit
  reason, per-asset filter notes from `journal/<day>/session-review-*.md`, and any
  WARNING/ERROR log lines the agent's own INFO-level narration never surfaces). Works out the
  session's own `day_key` and log file itself — not naively "today", since New York's session
  can close on the Sydney calendar day *after* the one it opened on (`TradingAgent-DigestAsia`/
  `TradingAgent-DigestNY`).
- **`ops/weekly_report.py`** — Sunday-evening stats (reusing `journal.compute_stats()`),
  lessons, learning buckets, and a countdown against `tuning`'s evidence gates (trades/days
  since the last change, auto-budget used) — answering "when will the system next change
  itself." Also previews the current top candidate via `agent.py`'s own (read-only)
  `TradingAgent._find_candidate()`, rather than a second copy of that threshold logic.
- **`ops/suggestion_evidence.py`** — for each pending suggestion in `journal/suggestions.json`,
  runs two sandboxed `backtest.py` runs (current config vs `backtest.py --set param=value`,
  which is refused outright for anything outside `tuning.whitelist`'s bounds) and posts the
  metric deltas, so an approve/reject decision has comparative evidence behind it.

See `docs/ctrader_setup.md` for how the broker-setup ops scripts fit together into a go-live checklist.

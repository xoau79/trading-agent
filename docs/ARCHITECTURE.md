# Architecture

How the pieces fit together, and which are live today vs. scaffolded for later.

## Today (paper trading, live)

```
Task Scheduler ──▶ bot.py --session {asia|newyork}
                       │
                       ├── data_feed/yahoo.py ──▶ Yahoo Finance 1-min bars
                       ├── strategies/orb/       ──▶ Opening Range Breakout signal logic
                       ├── broker/paper.py       ──▶ simulated fills, sizing, universal risk limits, state.json
                       ├── news.py               ──▶ ForexFactory calendar, CNBC RSS, TradingView rating
                       ├── agent.py              ──▶ narrates every decision, learns, proposes bounded tweaks, Discord
                       └── journal.py            ──▶ trade archives, dashboard/data.js

dashboard_server.py ──▶ http://localhost:8765 (serves dashboard/, Approve/Reject + Backtest Lab endpoints)
ops/watchdog.py     ──▶ scheduled every 5 min, detects a hung bot.py via journal/heartbeat.json, recovers it
```

One loop iteration (`Engine.step`, in `bot.py`) per ~45 seconds: pull fresh bars, manage any open position,
check for forced exits (news/daily-halt), hunt for a new entry via the assigned strategy. Nothing about
this loop changes based on which broker or strategy is configured — that's the point of the
interfaces below.

## Broker abstraction (`broker/`)

`broker/base.py` defines the contract every broker adapter implements: `connect()`, `get_bars()`,
`get_price()`, `place_order()`, `close_position()`, `get_positions()`, `get_account_info()`. The engine
only ever talks to this interface, never to a specific broker's SDK directly.

- **`broker/paper.py`** — the default. Simulated fills against real market prices, no real money.
- **`broker/mt5_broker.py`** — IC Markets (or any MT5 broker) via the official `MetaTrader5` Python package,
  which talks to a locally-running MT5 terminal. Scaffolded; inert until `.env` has `MT5_LOGIN` /
  `MT5_PASSWORD` / `MT5_SERVER` and `config.json`'s `broker.provider` is set to `"mt5"`.
- **`broker/ibkr/ibkr_broker.py`** — Interactive Brokers via TWS/IB Gateway. Scaffolded stub; the reference
  material for building it out lives in `docs/ibkr/` (all 40 lessons from the TWS Python API, Client
  Portal/Web API, and related courses, organized by course).

Switching `broker.provider` in `config.json` is the only thing that changes which broker is live. Strategy
logic, risk limits, and the dashboard are unaffected.

## Price data (`data_feed/`)

- **`data_feed/yahoo.py`** — default source, hardened with explicit timeouts and retry/backoff (see
  `docs/` changelog / PR history for the hang postmortem this responds to).
- **`data_feed/twelvedata.py`** — automatic fallback when Yahoo is stale and `TWELVEDATA_API_KEY` is set.
- **`data_feed/broker_feed.py`** — once a live broker is connected (`broker.provider != "paper"`), price
  data comes from the broker itself instead of a third-party feed. This is the intended end state for live
  trading: one connection, no separate data vendor dependency.

## Strategy library (`strategies/`)

`strategies/base.py` defines what a strategy must declare: entry rule, exit rule, `target_r_multiple`,
`risk_per_trade_pct`, applicable assets/sessions, and any filters. Each strategy lives in its own folder
with its own `strategy.py` and `README.md` explaining its rules in plain language — see
`strategies/README.md` for the full pattern and `strategies/orb/README.md` for the one strategy currently
live.

**Universal rules are not part of any strategy.** Daily loss limit, max trades per session/day, max
concurrent positions, consecutive-loss bench, leverage cap — these are enforced by the broker/engine layer
(`broker/paper.py`'s `can_open()` / `check_daily_stop()`) for every strategy, unconditionally. A strategy
cannot loosen them; it only decides entries/exits within them.

## Dashboard

Static HTML (`dashboard/dashboard.html`) + a JSON data file (`dashboard/data.js`) the bot rewrites every
loop, served by a small stdlib HTTP server (`dashboard_server.py`) that also exposes two write endpoints
(approve/reject agent suggestions, kick off a backtest). No frontend framework, no build step — open the
HTML file's source to change it, following `DESIGN.md`.

## Ops (`ops/`)

- **`ops/smoke_test.py`** — checks every external feed is reachable; run manually or before trusting a
  fresh environment.
- **`ops/watchdog.py`** — the fix for the "bot goes dark mid-session" failure mode: a heartbeat file
  (`journal/heartbeat.json`) written every loop, checked by a separate scheduled task every 5 minutes. A
  stale heartbeat means the main loop hung (e.g. a network call with no timeout) — the watchdog kills the
  hung process, safely flattens anything left open, alerts Discord, and restarts if the session window is
  still active.
- **`ops/register_tasks.ps1`** — versioned Task Scheduler setup, so the automation is reproducible from the
  repo instead of living only in one machine's scheduler configuration.

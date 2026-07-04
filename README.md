# 🤖 Trading Agent

A fully automatic, emotion-free trading system. Today it trades a **simulated $10,000 account** against
**real live market prices** — no real money is at risk. It's built to grow into a live-broker-connected
system without a rewrite: see `docs/ARCHITECTURE.md` for the broker-agnostic design and `strategies/` for
the growing strategy library.

## Repo map

| Path | What it is |
|---|---|
| `bot.py` | Main program: session timing, live loop, replay mode |
| `agent.py` | The narrator/brain: feed, market reads, learning, refinements, Discord |
| `strategies/` | The strategy library — see `strategies/README.md` |
| `broker/` | Broker-agnostic trading interface (paper today, MT5/IBKR scaffolded) — see `broker/README.md` |
| `data_feed/` | Price data sources — see `data_feed/README.md` |
| `news.py` | ForexFactory calendar (bank-holiday detection, news blackout, top-tier flatten), CNBC headlines, TradingView ratings |
| `journal.py` | Trade archives, lessons, dashboard data |
| `dashboard/` + `dashboard_server.py` | The dashboard at http://localhost:8765 — visual rules in `DESIGN.md` |
| `ops/` | Smoke test, Task Scheduler setup — see `docs/ARCHITECTURE.md` |
| `docs/` | Architecture notes and reference material (including IBKR API course notes in `docs/ibkr/`) |
| `config.json` | Universal settings — risk %, trade caps, session times, news filters |
| `.env` | Secrets (Discord webhook, broker credentials, API keys) — gitignored, copy from `.env.example` |

`CONTRIBUTING.md` has the branch/PR workflow rules — read it before making changes.

## What it trades, and when (Sydney time)

| Session | When | Assets |
|---|---|---|
| Asian (2nd hour of Tokyo's market, 4 h) | 10:00 – 14:00 JST (~11:00–15:00 AEST / ~12:00–16:00 AEDT) | Gold |
| New York (full session) | ~23:30 – 06:00 | Gold, Nasdaq (NQ), S&P 500 (ES) |

Windows Task Scheduler starts the bot automatically every weekday
(`TradingAgent-Asia` at 10:30 AM, `TradingAgent-NY` at 11:00 PM). The bot works out
the exact market open by itself, including daylight-saving changes, and exits when
the session ends. **The PC just needs to stay on** (sleep is disabled while plugged in).
The Asian session is anchored to Tokyo's own clock (`Asia/Tokyo`, `10:00` — the *second*
hour of Japan's market, since the first hour's 1-minute bars are too thin for a reliable
opening range). Japan doesn't observe daylight saving, so this anchor never moves; what
moves is its Sydney-time *equivalent* (11:00 AEST in winter vs. 12:00 AEDT in summer) —
`bot.py`'s `session_window()` works that conversion out fresh every run via `zoneinfo`, so
the dashboard clock (always shown in `Australia/Sydney`) automatically tracks the correct
wall-clock hour across both timezones' independent DST calendars with no manual tweaking.

**Bank holidays are skipped automatically.** Before each session the bot reads the
ForexFactory calendar: a JPY or AUD bank holiday cancels the Asian session; a USD bank
holiday cancels New York. Gold trades globally on those days, but the bot won't trade
thin holiday conditions. The dashboard shows 🏖️ "Holiday — market closed" and never
shows the "Wake the bot" prompt.

## The strategy — Opening Range Breakout (ORB)

The one strategy live today. Full rules, entry/exit, RR, and risk% are documented in
`strategies/orb/README.md` — the short version:

1. Record the high and low of the **first 15 minutes** of the session — the "opening range".
2. If the range is abnormally small (dead market) or large (news spike), **skip the
   asset for the whole session** — and you'll get a Discord notification explaining why, not silence.
3. A 1-minute candle closing **above** the range = buy; **below** = sell short.
4. Stop-loss at the far side of the range; profit target at **2× the risk** ("2R").
5. Everything is force-closed at session end — no overnight positions, ever.
6. TradingView's 15-min technical rating is checked as a sanity filter.
7. No new trades within ±15 min of high-impact USD news; open trades are closed 5 min before FOMC/NFP/CPI.

## Safety rails ("no heavy losses") — universal, apply to every strategy

- Risk per trade: **1% ($100)** — position size is computed from the stop distance
- Daily loss limit: **−3% ($300)** → all trading halts until the next day
- Max **4 trades per session, 8 per day**, max 2 positions open at once
- An asset that loses 4 times in a row gets benched for a day
- Repeated errors or missing data → the bot flattens everything and shuts down safely

These live in the broker/engine layer, not any one strategy — see `docs/ARCHITECTURE.md`.

## Your dashboard 📊

Open **http://localhost:8765** in your browser (the `TradingAgent-Dashboard` task keeps
it running; it starts automatically when you log in). Balance, equity curve, win rate, profit factor,
drawdown, what the bot is doing right now, every trade with its full reasoning (click a row), upcoming
news, live charts. Refreshes every 60 seconds. Visual rules for any future changes: `DESIGN.md`.

### 🧠 The agent

The bot narrates everything it does into the **Agent feed** — what it's hunting, why it
enters, how it manages each trade, why it exits, and the lesson. Key events go to **Discord**, including
when it deliberately stands aside (opening-range filter failed, a rule blocked a signal, a holiday, etc.)
— you'll always know why it isn't trading, never just silence.

It **learns** from every trade and may refine whitelisted parameters in tiny bounded steps (at most one
change per 5 days, 20+ trades of evidence, 15 auto-changes ever). After that, every idea becomes a
**suggestion on the dashboard** with Approve/Reject buttons. Risk caps can never be touched by the agent.

### 🧪 Backtest Lab

Pick any of 10 assets, a session, a period, and click **Run Backtest**. It replays real historical sessions
through the exact live engine and shows metrics, equity curve, R-multiple distribution, and a Monte Carlo
simulation (1,000 reshuffled orderings).

## The journal 📓

- `journal/trades.json` — every trade, machine-readable (gitignored — local runtime data)
- `journal/<date>/trade-NN-ASSET.md` — a pretty archive per trade
- `journal/<date>/session-review-*.md` — end-of-session summary
- `journal/lessons.md` — the bot's accumulated lessons

## Useful commands (PowerShell)

```powershell
# Watch the bot's log live during a session
Get-Content "C:\CLAUDE CODE\Sessions\trading-agent\logs\asia_20260612.log" -Wait -Tail 20

# Run a session manually right now (visible console)
& "C:\CLAUDE CODE\Sessions\trading-agent\run_asia.bat"

# Replay any past date through the system (sandboxed — doesn't touch the live account)
python bot.py --session newyork --backtest 2026-06-10

# Pause / resume the automation
Disable-ScheduledTask -TaskName "TradingAgent-Asia","TradingAgent-NY"
Enable-ScheduledTask  -TaskName "TradingAgent-Asia","TradingAgent-NY"

# Check every external feed is healthy
python ops/smoke_test.py
```

## Setup

```powershell
pip install -r requirements.txt
Copy-Item .env.example .env   # then fill in DISCORD_WEBHOOK_URL at minimum
```

## Tuning

Everything universal lives in `config.json` — trade caps, session times, news windows. Strategy-specific
parameters live in each strategy's own folder. Change a number, save, and the next session uses it.
To reset the account back to $10,000: delete `state.json`, `journal\trades.json` and `journal\lessons.json`.

Scheduled tasks: `TradingAgent-Asia` (10:30 AM), `TradingAgent-NY` (11:00 PM),
`TradingAgent-Dashboard` (at logon).

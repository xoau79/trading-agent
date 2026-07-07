# broker/

Broker-agnostic trading interface. See `docs/ARCHITECTURE.md` for the full design and
`docs/ctrader_setup.md` for the end-to-end walkthrough of going from paper to a real cTrader
or MT5 account.

- **`base.py`** — `BrokerBase`, the interface every adapter implements.
- **`paper.py`** — the default (`config.json`'s `"broker": {"provider": "paper"}`). Simulated
  fills against real market prices, no real money. Delegates its risk rules and bookkeeping to
  `ledger.py`'s `TradeLedger`.
- **`ledger.py`** — `TradeLedger`: the universal risk rules (daily loss limit, trade/position
  caps, consecutive-loss bench) and state-file bookkeeping, shared by `paper.py` and
  `live.py` so a live broker enforces exactly the same rules paper trading always has.
- **`live.py`** — `LiveBroker`: the facade that wraps a real adapter (`mt5_broker.py`,
  `ctrader/ctrader_broker.py`) in the same surface `bot.py`'s `Engine` already talks to for
  paper trading, backed by its own `TradeLedger` (state stored in `state_live_<provider>.json`
  — never `state.json`). This is also where the live-specific safety mechanisms live: the
  live-account confirmation latch, per-order sanity checks, the max-total-drawdown halt, and
  startup reconciliation against the broker's own truth. See its module docstring.
- **`ctrader/`** — IC Markets (or any broker/prop-firm) cTrader account via Spotware's Open
  API: `messages.py` (payloadType/enum reference, sourced from Spotware's own proto files),
  `auth.py` (OAuth2 + token storage), `transport.py` (the JSON-over-WebSocket client — see its
  docstring for why not the official protobuf/Twisted package), `ctrader_broker.py`
  (`CTraderBroker(BrokerBase)`). Setup: `ops/ctrader_auth.py` then
  `ops/ctrader_smoke_test.py` — see `docs/ctrader_setup.md`.
- **`mt5_broker.py`** — IC Markets / any MetaTrader 5 broker, via the official `MetaTrader5`
  Python package talking to a locally-running MT5 terminal. Fully implemented (pricing,
  positions, account info, and order placement/close). Inert until `.env` has
  `MT5_LOGIN`/`MT5_PASSWORD`/`MT5_SERVER` and each traded asset has an `"mt5"` symbol in
  `config.json` (check your terminal's Market Watch — don't guess; the file ships with `null`
  placeholders, not guesses). Windows-only (the `MetaTrader5` package requires it), so it's
  tested here against a fake module (`tests/test_mt5_broker.py`) — run
  `ops/mt5_smoke_test.py` on your actual Windows machine before trusting it.
- **`ibkr/ibkr_broker.py`** — stub. Reference material for building it out is in `docs/ibkr/`.

## How the switch works

`create_broker(cfg)` (in `__init__.py`) builds whichever broker `config.json`'s
`broker.provider` names. `"paper"` returns `PaperBroker` directly; `"mt5"`/`"ctrader"` wrap
their adapter in `LiveBroker`. `bot.py`'s `run_live()` calls `create_broker(cfg)` and then
`broker.connect()` — a failed connection aborts the session (with a Discord alert) rather than
silently falling back to anything. Every broker built this way presents the exact same
surface to `Engine`: `state`, `can_open()`, `open_position()`, `update_position()`,
`close_position()`, `flatten_all()`, `start_session()`. Flipping `broker.provider` really is
the only thing that changes which broker is live — strategy logic, risk limits, and the
dashboard are unaffected.

## Safety, by design

- **Demo by default.** Nothing about connecting to a live/demo cTrader or MT5 account risks
  real money unless the account itself is live *and* you've deliberately armed the latch below.
- **Live-account latch** (`LiveBroker._enforce_live_latch`): a live account only trades if
  `config.json`'s `live_trading.enabled` is `true` **and** `.env`'s `LIVE_TRADING_CONFIRM`
  equals that exact account's id. Either one missing refuses to connect. A copied `.env` or a
  stale config flag can never silently arm live trading.
- **Order sanity checks** (`LiveBroker._sanity_check_order`): every order is checked against
  `config.json`'s `live_trading` block (max units per asset, min/max stop distance, correct
  stop/target side, leverage cap) before it ever reaches the broker. A failure refuses the
  order outright — it's never resized or "fixed" silently.
- **Max total drawdown halt**, independent of the existing daily-loss halt, measured against a
  baseline balance recorded the first time a live broker connects.
- **Reconciliation on startup** (`LiveBroker.reconcile`): positions the ledger thought were
  open but the broker has since closed are booked (best-effort priced); positions the broker
  shows that this bot didn't open are left completely untouched and surfaced as dashboard
  warnings — never auto-adopted.
- **Dashboard kill switch**: a "Flatten & halt" button writes `halt.flag` (repo root), which
  the live loop checks every iteration; the dashboard process itself never talks to a broker.
- **Broker switching is config-file/`.env`-only** — no dashboard control can change
  `broker.provider`, `live_trading.enabled`, or the confirmation latch.

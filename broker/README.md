# broker/

Broker-agnostic trading interface. See `docs/ARCHITECTURE.md` for the full design.

- **`base.py`** — `BrokerBase`, the interface every adapter implements.
- **`paper.py`** — the default (`config.json`'s `"broker": {"provider": "paper"}`). Simulated
  fills against real market prices, no real money. This is the only adapter actually
  exercised by the live trading loop today.
- **`mt5_broker.py`** — IC Markets / any MetaTrader 5 broker, via the official `MetaTrader5`
  Python package talking to a locally-running MT5 terminal. Read-only methods (pricing,
  positions, account info) are implemented; order placement is deliberately
  `NotImplementedError` until it's been wired up and tested against a demo account on
  purpose. Inert until `.env` has `MT5_LOGIN`/`MT5_PASSWORD`/`MT5_SERVER` and each traded
  asset has an `"mt5"` symbol in `config.json` (check your terminal's Market Watch — don't
  guess; the file ships with `null` placeholders, not guesses).
- **`ibkr/ibkr_broker.py`** — stub. Reference material for building it out is in `docs/ibkr/`.

## Important: the switch doesn't (yet) change live trading

`create_broker(cfg)` (in `__init__.py`) correctly builds a `PaperBroker`, `MT5Broker`, or
`IBKRBroker` from `config.json`'s `broker.provider`, and each adapter's read-only methods can
be tested independently. But `bot.py`'s `Engine` (the actual trading loop) is still written
directly against `PaperBroker`'s specific state-dict interface — universal risk rules
(`can_open()`, `check_daily_stop()`), position bookkeeping (`state["open_positions"]`), and
session accounting all assume `PaperBroker` specifically, not the generic `BrokerBase`
surface. Flipping `broker.provider` to `"mt5"`/`"ibkr"` today builds the right adapter object
but doesn't (yet) plug it into the live loop — that's a distinct follow-up once you're ready
to go live: rewriting `Engine`'s risk/position bookkeeping to work against any `BrokerBase`
implementation, not just `PaperBroker`'s dict.

This is intentional, not an oversight: it means nothing about live trading can accidentally
half-work. Paper trading is exactly as safe and unchanged as it was before this existed.

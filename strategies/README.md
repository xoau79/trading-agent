# strategies/ — the strategy bank

Each strategy is a self-contained folder: its own entry/exit rules, risk/reward, risk
percentage, and filters, documented in plain language in its own `README.md`. This is where
you build up a bank of tested, profitable strategies over time — see `_template/` to add one.

| Strategy | Assets | Sessions | RR | Risk/trade | Status |
|---|---|---|---|---|---|
| [`orb/`](orb/README.md) | Gold, NQ, ES | Asian, New York | 2R | 1% | **Live** |

## The pattern

- `strategies/base.py` — `StrategyBase`, the interface: `on_bars()` (called once per loop,
  returns a signal or `None`) and `snapshot()` (dashboard state). Every strategy also
  declares metadata (`name`, `description`, `applicable_assets`, `applicable_sessions`).
- `strategies/__init__.py` — the registry (`STRATEGIES` dict + `get_strategy(name)`).
  `bot.py`'s `Engine` looks up each session's assigned strategy by name
  (`config.json`'s `sessions.<name>.strategy`) through this — nothing else needs to know a
  new strategy exists once it's registered here.
- `strategies/<name>/strategy.py` + `strategies/<name>/README.md` — the strategy itself and
  its plain-language spec (entry rule, exit rule, RR, risk%, filters, applicable
  assets/sessions). Every strategy's `README.md` should be understandable without reading the
  code.

## Universal rules vs. per-strategy rules

**Universal** (apply to every strategy, unconditionally, enforced by `broker/paper.py` —
`can_open()` / `check_daily_stop()`, not any strategy file):
- Daily loss limit (`risk.daily_loss_limit_pct`)
- Max trades per session / per day (`risk.max_trades_per_session` / `max_trades_per_day`)
- Max concurrent positions (`risk.max_concurrent_positions`)
- Consecutive-loss bench (`risk.consecutive_losses_to_bench`)
- Max notional leverage (`risk.max_notional_leverage`)

A strategy can never loosen these — it only decides entries/exits *within* them. If you're
tempted to add a new "safety" rule inside a strategy file, it almost certainly belongs here
instead, so it protects every strategy in the bank, not just one.

**Per-strategy** (each strategy's own, documented in its own `README.md`):
- Entry rule, exit rule
- Risk/reward (target R-multiple, stop placement)
- Risk per trade (today: shared with the global config since there's only one strategy — see
  the config-sharing note below)
- Any filters specific to that strategy's edge (ORB's ATR/volatility filter, TradingView
  confluence, etc. — a different strategy might have none of these, or entirely different ones)

## Config-sharing note (today vs. once a second strategy exists)

Right now, ORB's parameters live in the root `config.json`'s `"strategy"` and `"risk"` blocks
— that's fine while there's exactly one strategy, and it's also where the agent's bounded
auto-tuning system writes its overrides (see `agent.py`'s whitelist). Once a genuinely second
strategy joins the bank with its *own* independent risk% or RR, the right move is:
1. Give it its own `strategies/<name>/strategy.json` for its own parameters.
2. Thread its `risk_per_trade_pct` through `broker/paper.py`'s `open_position()`/
   `size_position()` (today they read the global `risk.risk_per_trade_pct` — this is
   deliberately not rewired yet, since there's no second strategy to test it against; see
   `broker/paper.py`'s docstring). Don't build this plumbing speculatively — build it when the
   second strategy actually needs it, and test the sizing math carefully, since it directly
   controls how much money is risked per trade.

## Adding a new strategy

1. Copy `strategies/_template/` to `strategies/<your-strategy-name>/`.
2. Implement `on_bars()` and `snapshot()` in `strategy.py`; fill in the metadata attributes.
3. Fill in `README.md` from the template — every section, no placeholders left.
4. Register it in `strategies/__init__.py`'s `STRATEGIES` dict.
5. Assign it to a session in `config.json` (`sessions.<name>.strategy`).
6. **Backtest it first.** Run it through `bot.py --session <name> --backtest <date>` or the
   dashboard's Backtest Lab across a real historical period before it ever sees a live loop.
7. Open a PR (see `CONTRIBUTING.md`) — call out the risk parameters explicitly.

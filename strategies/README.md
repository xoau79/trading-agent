# strategies/

The strategy library. Scaffolded here in the baseline commit; implemented in the `feat/strategy-library`
PR. See `docs/ARCHITECTURE.md` for the design.

Planned contents:
- `base.py` — the `StrategyBase` interface: every strategy declares its own entry rule, exit rule,
  `target_r_multiple`, `risk_per_trade_pct`, applicable assets/sessions, and filters.
- `orb/` — the current live strategy (Opening Range Breakout), moved in unchanged, with a `README.md`
  spelling out its exact rules.
- `_template/` — copy-and-fill scaffold for adding the next strategy to the bank.

**Universal rules (daily loss limit, trade caps, position caps, consecutive-loss bench) are not strategy
rules** — they live in the broker/engine layer and apply no matter which strategy is active. See
`docs/ARCHITECTURE.md`.

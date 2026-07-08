# Skill: Run backtests and replays

## When to use it
Before merging any PR that changes trading logic (required by `CONTRIBUTING.md`), when validating a proposed agent suggestion, or whenever you want to see how the current strategy would have performed over a historical period.

## Steps, in order

1. **Decide which tool you need.** `bot.py --backtest` replays a single session on a single date through the live engine (fast, good for "does this PR change today's trade sequence?"). `backtest.py` (or the dashboard's Backtest Lab) replays many sessions over a period with a Monte Carlo bootstrap (good for "how has this actually performed over the last month?").
2. **For a single-date replay:**
   ```
   python bot.py --session newyork --backtest 2026-06-11
   ```
   This is fully sandboxed — it never touches `state.json`, the real `journal/`, or `config_overrides.json` (see `bot.py`'s `run_replay()`, which redirects every module-level path to a `backtest/` sandbox folder first).
3. **For a multi-session backtest:**
   ```
   python backtest.py --assets GOLD,NQ,ES --session both --days 30
   ```
   Remember Yahoo's free tier caps 1-minute history at ~30 days back — `--days` above 29 gets silently clamped, and that's the honest limit of this tool, not a bug.
4. **To A/B a proposed parameter change** (e.g., before approving an agent suggestion), add `--set param=value` to compare against the baseline:
   ```
   python backtest.py --assets GOLD,NQ,ES --session both --days 29 --set strategy.range_atr_min=0.35
   ```
   This only accepts params already in `config.json`'s `tuning.whitelist`, within their configured bounds — it will refuse anything else outright, on purpose. (`ops/suggestion_evidence.py` does exactly this automatically for every pending suggestion — see that skill file.)
5. **Read the result, not just the final balance.** For `backtest.py`, the JSON result in `dashboard/backtests/<id>.json` has `stats` (via `journal.compute_stats()`), `daily_pnl`, `best_day`/`worst_day`, `r_values`, and `mc` (the Monte Carlo bands) — the Monte Carlo envelope tells you whether an outcome was skill or luck, which the raw P&L number alone can't.
6. **Compare the trade sequence before/after a code change**, not just the final metrics. Two runs can land on the same final P&L for very different reasons (a real replay is the only way to catch that) — this is exactly why `CONTRIBUTING.md` requires a replay before merging trading-logic PRs, not just a metrics comparison.

## Example of a good final output

The real printed output of a `bot.py --backtest` replay (`run_replay()`'s actual print statements):

```
Replay 2026-06-11 newyork: 2 trades, P&L +212.40 USD, final balance 10212.40
  #1 GOLD LONG: 3350.20 -> 3362.80 (target) +210.40 USD (+2.00R)
  #2 NQ SHORT: 19800.00 -> 19850.00 (stop) -100.00 USD (-1.00R)
  ES filtered: range abnormally small (dead market)
```

And `backtest.py`'s own summary line, printed at the end of a multi-session run:
```
bt_20260709_143022: 47 trades, P&L +893.20
```
Both are good outputs because every trade is individually accounted for with its exact entry/exit/reason/R-multiple — never just a rolled-up total. If you can't reconstruct the whole session from the printed trades, something in the run didn't complete properly.

## Mistakes to avoid

- **Don't backtest a date range longer than Yahoo's free-tier 1-minute limit and expect a warning.** `backtest.py` clamps `--days` to a max of 29 silently (`days = max(2, min(args.days, 29))`) — if you asked for 90 days and got results, you actually got 29. Check `params.days` in the result JSON if you need to be sure.
- **A backtest with `--set` never touches the real config.** It's validated and applied only inside `backtest.py`'s own sandbox for that one run — if you want the change to actually take effect in live trading, that's a separate, deliberate step (approving the suggestion, or hand-editing `config.json`), not something a backtest run does for you.
- **Don't run two backtests at once.** The dashboard's `/api/backtest` endpoint already refuses a second run while one is in progress (`dashboard_server.py`'s `_bt_lock`) — if you're driving `backtest.py` directly from the command line instead, you don't get that protection automatically, so wait for one to finish before starting another.
- **A replay's "final balance" isn't comparable across different starting balances.** If you've reset the account (deleted `state.json`) between two replays you're comparing, the balance numbers won't be apples-to-apples — compare P&L and R-multiples instead, or reset both runs to the same `starting_balance` first.
- **Don't assume a backtest and a live session will produce identical fills for the same date/config.** `slippage_pct` is applied the same way in both, but a live session's actual fills depend on real-time data quality (feed source, staleness fallbacks) that a backtest's clean historical data doesn't have to contend with — treat a backtest as a strong signal, not a guarantee of live performance.

# Skill: Review the journal and the weekly stats report

## When to use it
After a trade closes (per-trade archive), at the end of a session (session review), or once a week to check overall performance and how close the agent is to its next auto-tuning change.

## Steps, in order

1. **For a single trade**, read `journal/<day_key>/trade-NN-ASSET.md` — it has the entry/exit prices, direction, size, stop/target, R-multiple, MFE/MAE, the opening-range context, TradingView rating at entry, and an auto-generated reflection (`journal.py`'s `build_reflection()`) split into "what went well" and "what needs improvement." Read the reflection, not just the P&L line — it's written to be a genuine self-review, not a summary.
2. **For a session**, read `journal/<day_key>/session-review-<session>.md` — trades, wins/losses, P&L, balance, any halt reason, and one note per asset (its final stage, or why it was filtered/skipped for the whole session).
3. **Run the weekly report** (manually or via the Sunday-evening `TradingAgent-WeeklyReport` task):
   ```
   python ops/weekly_report.py
   ```
   Read it in this order: (a) trade stats — win rate, profit factor, avg R, per-asset P&L; (b) this week's lessons — the one-line takeaways `journal/lessons.json` accumulated; (c) learning buckets — which asset/session/range/hour/TradingView-agreement combinations are actually losing money, worst first; (d) the auto-tuning gate countdown; (e) any pending suggestions.
4. **Check the tuning-gate countdown specifically** if you're wondering "when will the system change itself." It reports exactly how many more trades and/or days are needed before `agent.py`'s `review_and_refine()` can apply its next bounded change — don't guess from the trade count alone, since both a trade-count gate *and* a day-count gate have to clear together.
5. **If a candidate refinement is shown** ("Next candidate refinement if the gates were open right now..."), that's a live preview computed from the *exact* logic the agent itself uses (`agent.py`'s `_find_candidate()`), not a guess — it tells you what's about to happen once the gates open, before it happens.
6. **Cross-check big weekly swings against `journal/lessons.md`** (the human-readable running log) rather than trusting a single number — a bad week with a clear identified cause (e.g., a cluster of fast fakeout stops) is different from a bad week with no pattern.

## Example of a good final output

A real, verified `ops/weekly_report.py` output (this exact format, produced from `journal.compute_stats()` and `agent.py`'s own bucket logic):

```
**Weekly report — week ending 2026-07-09 (7d)**

Trades: 3  |  Wins: 1  |  Losses: 2  |  Win rate: 33.3%
P&L: +15.40 USD  |  Profit factor: 1.08  |  Avg R: 0.0  |  Max drawdown (all-time): 195.00 USD

**Per asset:**
- GOLD: 2 trades, 1 wins, +115.40 USD
- NQ: 1 trades, 0 wins, -100.00 USD

**Lessons this week:**
- [2026-07-08 newyork GOLD WIN +2.00R] Textbook trade for this system.
- [2026-07-07 newyork NQ LOSS -1.00R] Normal 1R loss.

**Learning buckets (≥10 trades, worst avg R first):**
- `range:<0.75`: 12 trades, avg -0.40R
- `asset:GOLD`: 14 trades, avg +0.60R

**Auto-tuning gate:** 3/15 auto-refinements used.
Next change needs: 5 more trade(s) and 1 more day(s).
Next candidate refinement if the gates were open right now: `strategy.range_atr_min` 0.3 → 0.35 (Small opening ranges keep producing fakeouts; demanding a livelier range filters them out.)

**1 pending suggestion(s) awaiting your decision:**
- `strategy.entry_cutoff_minutes` 0 → 30: Late-session entries lack time to reach 2R.
```
This is a good report to act on because every number traces back to a real source you can go re-check (the per-asset line to `journal/trades.json`, the bucket line to `journal/learning.json`, the candidate to `agent.py`'s live whitelist) — nothing here is a guess.

## Mistakes to avoid

- **Don't read "Max drawdown (all-time)" as this week's drawdown.** It's computed from the full account equity curve since inception, not sliced to the reporting window — the label says so on purpose; the trade-level numbers above it (win rate, P&L, avg R) *are* scoped to the week.
- **A `None`/`—` win rate or profit factor means zero trades, not zero performance.** Don't read a fresh install or an empty week as "a bad week" — check the trade count first.
- **Don't confuse `state.json` with `state_live_<provider>.json`.** Paper trading's balance/equity history lives in `state.json`; a live broker gets its own separate file per provider, and the two are never merged or shared — if a number looks wrong, check which one you're actually looking at (and which one `broker.provider` in `config.json` currently points to).
- **A bucket needing more evidence isn't wrong, it's just not ready yet.** `min_bucket_trades` (10 by default) is a floor for even *showing* a bucket in the report — a bucket with fewer trades than that isn't hidden because it's uninteresting, it's hidden because there isn't enough data to trust the average yet. Don't act on an average from a small sample just because you can see it in `journal/learning.json` directly.
- **The "next candidate" preview is not a promise.** It shows what the bucket math says *right now*; new trades between now and when the gates actually open can change which bucket is worst and what the next real candidate ends up being.

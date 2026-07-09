# Skill: Decide on a pending agent suggestion

## When to use it
Whenever `journal/suggestions.json` has an entry with `"status": "pending"` — either seen live on the dashboard's Approve/Reject cards, or surfaced in the weekly report / a Discord suggestion post.

## Steps, in order

1. **Read the suggestion's own text first.** Every suggestion (`agent.py`'s `review_and_refine()`) already includes the parameter, the proposed change, a plain-language "why," and the evidence (e.g., "12 trades with range <0.75x ATR averaged -0.40R"). Don't act before reading this — it's not boilerplate, it's the actual reasoning.
2. **Get comparative evidence, don't decide on the bucket average alone.** Run (or wait for the scheduled Sunday task to run):
   ```
   python ops/suggestion_evidence.py --days 29
   ```
   This backtests the current config against the proposed one over the same historical period and posts the P&L/profit-factor/win-rate/drawdown deltas to Discord — a single bucket average can be noisy; a full backtest comparison is a stronger signal.
3. **Check what the suggestion is actually allowed to touch.** Every suggestion's `param` is guaranteed to already be in `config.json`'s `tuning.whitelist` (the agent refuses to propose or apply anything outside it — see `agent.py`'s `_apply_override()`) — this can never include risk caps, position sizing, or daily loss limits. If you ever see something that looks like it touches those, that's not how this system is supposed to behave; investigate before doing anything else.
4. **Decide using both signals together**: the bucket evidence in the suggestion text, and the backtest comparison from step 2. Prefer waiting for at least a moderate backtest sample (`ops/suggestion_evidence.py --days 29` is your maximum available window) over deciding off a single week's numbers.
5. **Approve or reject on the dashboard** (`http://localhost:8765`, the suggestion card's Approve/Reject buttons — this hits `dashboard_server.py`'s `/api/decision` endpoint, which is localhost-only by design). An approval takes effect at the next session start, not immediately; a rejection is archived and the agent won't re-propose the same thing soon.
6. **After approving**, confirm the change actually landed — the next session-start Discord message from the agent will mention the applied override, and `config_overrides.json` will contain the new value.

## Example of a good final output

A real, verified `ops/suggestion_evidence.py` output (this exact format, evidence for a real pending suggestion structure this repo produces):

```
**Evidence for pending suggestion:** `strategy.entry_cutoff_minutes` 0 → 30
_Late-session entries lack the time to reach 2R._
(backtest: GOLD, NQ, ES, both, last 30d)

- Net P&L (USD): -45.20 → +62.10 (+107.30)
- Profit factor: +0.92 → +1.18 (+0.26)
- Win rate (%): +38.50 → +41.20 (+2.70)
- Avg R: -0.05 → +0.12 (+0.17)
- Max drawdown (USD): +310.00 → +240.00 (-70.00)
- Trades: 26 → 22
```
This is a good decision-making input because it shows *every* metric moving in the same direction (P&L up, drawdown down, profit factor up) — a suggestion where the metrics disagree with each other (e.g., P&L up but drawdown also up a lot) deserves more scrutiny before approving, not an automatic yes.

## Mistakes to avoid

- **Don't approve based on the bucket average alone if the backtest comparison disagrees with it.** The bucket average in the suggestion text is computed from live trades only, in a specific set of narrow slices (asset, session, range bucket, time-of-session, TradingView agreement); the backtest comparison replays the whole strategy with the change applied. If they point in different directions, that's a real signal to wait for more data, not to average the two opinions together.
- **A suggestion sitting pending for a while is not a bug.** The agent stops auto-applying changes once its `auto_budget` (15 by default) is used up — after that, everything becomes a suggestion waiting on you, by design, not because something is stuck.
- **Don't try to make the agent apply something outside its whitelist "just this once."** There is no path to do this that the code allows (`_apply_override()` refuses non-whitelisted params or out-of-bounds values unconditionally, logging an error and returning `False`) — if a change you want isn't achievable through a whitelisted param, it needs a manual `config.json` edit and its own PR, not a suggestion decision.
- **Rejecting isn't permanent silence forever, but it's not instant either.** A rejected suggestion is archived and the agent "won't re-propose it soon" — if the underlying pattern is real and persists, expect it to resurface eventually with fresh evidence, not immediately with the same evidence you already rejected.
- **Don't skip the backtest step because the suggestion "sounds obviously right."** The entry-cutoff and range-filter suggestions in this repo's own design are exactly the kind of change that sounds intuitively correct but needs the numbers to actually confirm it — that's the whole reason `ops/suggestion_evidence.py` exists instead of trusting the one-line "why."

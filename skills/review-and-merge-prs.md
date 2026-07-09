# Skill: Review and merge a pull request

## When to use it
Whenever a PR (from Claude or anyone else) is opened against this repo and needs your review before merging into `main`.

## Steps, in order

1. **Read the PR description first.** It must state what changed and why. If it touches position sizing, stop/target logic, daily loss limits, or trade caps, the description must call that out explicitly (`CONTRIBUTING.md` rule 3) — if it doesn't and the diff clearly touches those things, send it back before reading further.
2. **Check the diff for risk-surface files** before anything else: `config.json`, `broker/ledger.py`, `broker/live.py`, any `strategies/*/strategy.py`. If the CI risk-surface-guard step (`.github/workflows/ci.yml`) flagged the PR, read its job summary — it lists exactly which of these files changed.
3. **Confirm CI is green.** `pytest` must pass (network-free, `tests/` only — see `pytest.ini`). A red check is a hard stop; don't review further until it's fixed.
4. **Pull the branch locally and run a replay** if the PR touches trading logic (strategy rules, entry/exit, sizing, risk caps):
   ```
   python bot.py --session newyork --backtest 2026-06-11
   ```
   Confirm the trade sequence is what you'd expect for that date — same entries, same exits, same reasoning — before and after the change. This is required by `CONTRIBUTING.md`, not optional for logic PRs.
5. **Check `DESIGN.md` compliance** if the PR touches `dashboard/`: no new hex colors, spacing values, or component patterns that aren't already documented — or, if genuinely new, `DESIGN.md` must be updated in the *same* PR.
6. **Check for secrets.** Scan the diff for anything that looks like a credential, token, or webhook URL, even in an innocuous-looking file. `.env` is gitignored specifically so this never happens — if you find one anyway, treat it as compromised and rotate it; reverting the commit is not enough once it's been pushed (`CONTRIBUTING.md` rule 5).
7. **Verify a merge actually landed on `main`**, not just onto an intermediate branch. GitHub can show a PR as "Merged" while its actual commits sit on a branch that was itself merged into `main` moments *before* — meaning none of the real diff ever reaches `main`. Check `git log --oneline main` (or the repo's commit graph) for the PR's actual commits, not just the merge-PR badge.
8. **Merge it yourself.** Whoever opened the PR (including Claude) never merges their own PR — you review, you approve, you click merge (`CONTRIBUTING.md` rule 4).

## Example of a good final output

A real PR from this repo's history that followed the process correctly — `ec2b664`, "Add cTrader/live-trading config groundwork; extract TradeLedger from PaperBroker":

```
- config.json: ctrader provider option, live_trading safety block, per-asset
  ctrader symbol placeholders (to be verified against the real account)
- .env.example: CTRADER_* credentials + LIVE_TRADING_CONFIRM safety latch
- requirements.txt: websocket-client (cTrader transport), pytest (dev)
- broker/ledger.py: new TradeLedger holding the universal risk rules and
  state.json bookkeeping that used to live inline in broker/paper.py, so a
  live broker can share the exact same rules via a future LiveBroker facade
- broker/paper.py: delegates to TradeLedger; public API and behavior
  unchanged (see tests/test_paper_parity.py, a network-free end-to-end
  check)
```
This is a good commit message because it lists every file touched, states *why* each change was made (not just what), and explicitly names the test (`tests/test_paper_parity.py`) that proves behavior didn't change. This is exactly the PR the CI risk-surface guard would flag (it touches `config.json` and `broker/ledger.py`) — and it earns that scrutiny honestly, by being upfront about it.

## Mistakes to avoid

- **A PR can show "Merged" on GitHub without its code ever reaching `main`.** This actually happened in this repo: PR #3 (a strategy-library refactor) was merged into a branch that was itself merged into `main` nine seconds *before* PR #3 landed on it — so the real diff never made it past a stray placeholder file, and it took a dedicated recovery commit (`1ab722a`) to notice and fix. Always check the actual commit graph, not the badge.
- **Don't trust a config value that says "guess" or "don't trust this."** `config.json`'s broker symbol fields ship with comments like *"likely 'XAUUSD'; verify with `python ops/ctrader_smoke_test.py --symbols` against your own account, do not trust this guess"* — a PR that hardcodes one of these without that verification step should be sent back.
- **One fix to an unbounded network call doesn't mean the pattern is gone.** `data_feed/yahoo.py` was hardened with a hard timeout after a 24h+ hang on 2026-07-02 — but `news.py`'s `feedparser`/TradingView calls had the *exact same* unbounded-socket problem and needed a second, separate fix (`35fe887`) two days later. When reviewing a PR that adds any new network call, check it has a timeout — don't assume "we already fixed this."
- **UI PRs need more than the happy path.** A Customize-panel PR passed normal open/close testing but broke on *rapid* open-close-reopen (a stale `setTimeout` force-hid the overlay after a fast reopen) — caught only by deliberately testing the repeat-action case, not just a single open/close (`2d53bea`). For dashboard PRs, always try opening/closing rapidly, double-clicking, and reordering — not just the single-pass flow.
- **Don't approve without running the actual test suite.** `pytest` alone (bare, no path) used to accidentally collect `ops/smoke_test.py`'s live network-hitting functions as unit tests; if you see test failures that look like network errors from files under `ops/`, that's a collection-scope problem, not a real regression — check `pytest.ini`'s `testpaths` is being respected before concluding CI is broken.

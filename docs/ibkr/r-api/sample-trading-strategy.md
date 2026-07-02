---
title: Sample Trading Strategy (SMA crossover in R)
source: https://www.interactivebrokers.com/campus/trading-lessons/sample-trading-strategy/
type: reference
course: trading-using-r
date_added: 2026-06-13
tags: [ibkr-api, r-language, ibrokers-package, moving-average-crossover, paper-trading]
---

# Sample Trading Strategy (SMA crossover in R)

## Concepts

- Capstone lesson: ties the whole course together into a simple **two-SMA crossover** bot built on the IBrokers package.
- Flow:
  1. Connect to TWS with `twsConnect()` ([[introduction-to-ibrokers-package]]).
  2. Load the custom `snapshot` market-data callback from `snapshot.R` ([[customizing-market-data-functions]]).
  3. Define the contract and pull data - a historical seed plus streaming snapshots ([[market-data-functions]]).
  4. Compute a **fast** and a **slow** simple moving average each iteration.
  5. **Cross up** (fast above slow) while flat -> place a BUY; **cross down** (fast below slow) while long -> place a SELL, via `twsOrder` + `placeOrder` ([[order-functions]]).
  6. Track the current position (flat / long) so it does not re-enter, and loop continuously until stopped.

## Code examples

The full strategy script is presented in the lesson as **screenshots**, so there is no copy-paste source to reproduce faithfully here. Recorded as logic rather than code: seed a data frame with historical bars, then in a `while` loop append each new snapshot tick, dedupe, compute fast/slow SMAs on the close, and act on the crossover with a position flag guarding re-entry, pausing briefly (`Sys.sleep()`) between iterations. Rebuild it from the package functions in the linked notes rather than copying any unverified transcription - check the on-screen variable and function names against the lesson source.

## Gotchas

The lesson is explicit that TWS's default safeguards are not enough for an automated strategy. Before running anything live, add:

- a **risk-management layer** for strategy-specific risks beyond TWS's built-in checks;
- **sanity checks** on order price and quantity before each submission;
- **loop-prevention tests** so a bug cannot fire orders endlessly ("the strategy will keep placing orders until it is stopped");
- **regression testing** after every API/package upgrade;
- **error handling** for socket disconnects, broker messages, and network failures.

Standard IBKR disclaimer: trading stocks/options/futures/forex/fixed income carries a substantial risk of loss; this is educational material, not investment advice. Always validate in a **paper account** first.

## Related

- Previous: [[order-functions]]
- Builds on: [[introduction-to-ibrokers-package]], [[market-data-functions]], [[customizing-market-data-functions]], [[order-functions]]
- Conceptual cousin in Python: [[running-the-donchian-channel]] - another indicator/breakout bot wired to the IBKR API
- (Final lesson of the course.)

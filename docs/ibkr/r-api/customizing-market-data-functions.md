---
title: Customizing Market Data Functions (eWrapper)
source: https://www.interactivebrokers.com/campus/trading-lessons/customizing-market-data-functions/
type: reference
course: trading-using-r
date_added: 2026-06-13
tags: [ibkr-api, r-language, ibrokers-package, market-data, callbacks]
---

# Customizing Market Data Functions (eWrapper)

## Concepts

- The raw output of streaming functions is hard to read; you customize how incoming TWS messages are handled by supplying your own callback to the `CALLBACK` argument of `reqMktData` / `reqMktDepth` / `reqRealTimeBars`.
- Three pieces cooperate:
  - **`twsCALLBACK`** - the default callback. It reads message headers from TWS in an infinite loop and hands each to `processMsg`.
  - **`processMsg`** - a large if/else that branches on the message type and calls the matching `eWrapper` method.
  - **`eWrapper`** - an R **closure** holding a list of functions, one per incoming message type. You create an instance and override individual methods to reshape data on the fly.
- The eWrapper keeps state in an internal **`.Data`** store, reached through accessor methods **`get.Data`**, **`assign.Data`**, and **`remove.Data`**. A custom method typically uses `assign.Data` to stash formatted ticks (e.g. tag them with the symbol and bind them into a data frame).
- The course's worked example is a **`snapshot`** callback (loaded from an external `snapshot.R` file) that turns streaming ticks into a tidy table - reused in [[sample-trading-strategy]].

## Code examples

The lesson presents its eWrapper / `snapshot.R` customization entirely as **screenshots**, so there is no copy-paste text to transcribe faithfully. The shape it shows: create or modify an `eWrapper` instance, override its tick methods to call `assign.Data()` with symbol-tagged rows, then pass the wrapped function as the `CALLBACK` to a market-data request. See the lesson source for the exact script.

## Gotchas

- Customization is open-ended - the lesson encourages adapting the eWrapper methods to whatever data shape you need.
- Data accumulates in the eWrapper's `.Data` environment across callbacks, so clear/reset it (`remove.Data`) when appropriate.

## Related

- Previous: [[market-data-functions]]
- Next: [[order-functions]]
- The snapshot callback is reused by [[sample-trading-strategy]]

---
title: Market Data Functions (IBrokers)
source: https://www.interactivebrokers.com/campus/trading-lessons/market-data-functions/
type: reference
course: trading-using-r
date_added: 2026-06-13
tags: [ibkr-api, r-language, ibrokers-package, market-data, historical-data]
---

# Market Data Functions (IBrokers)

## Concepts

- Three real-time request types, plus historical:
  - **Level 1 (top-of-book)** - bid/ask/last - via `reqMktData()`.
  - **Level II (market depth / order book)** - via `reqMktDepth()`; returns up to 5 best bid/ask levels.
  - **Real-time bars** - streaming candlesticks - via `reqRealTimeBars()`.
  - **Historical bars** - via `reqHistoricalData()`.
- **Market data lines:** by default you can stream up to ~100 instruments at once; exceeding the limit raises an error.
- Define the instrument first with a contract object (`twsContract`/`twsEquity`/`twsFuture`/`twsOption` - see [[introduction-to-ibrokers-package]]), then pass it to the data request.
- **Snapshot vs. streaming:** `reqMktData`'s `snapshot` argument chooses a one-shot snapshot vs. a continuous stream.
- Default callbacks just print/return raw ticks; you reshape them by passing a custom `CALLBACK`/`eventWrapper` (see [[customizing-market-data-functions]]).

## Code examples

> Code in this lesson is shown as images; the parameter lists below are transcribed from the lesson's stated parameters / IBrokers docs, not copied from code blocks.

```r
# Streaming Level 1 quotes
reqMktData(conn, Contract, tickGenerics, snapshot, tickerId, timeStamp, file, eventWrapper, CALLBACK)

# Streaming market depth (order book, up to 5 levels)
reqMktDepth(conn, Contract, tickerId, timeStamp, playback, file, eventWrapper, CALLBACK)

# Streaming real-time bars
reqRealTimeBars(conn, Contract, tickerId, whatToShow, barSize, file, eventWrapper, CALLBACK)

# Historical bars
reqHistoricalData(tickerId, Contract, endDateTime, duration, barSize, whatToShow, Timeformat, eventHistoricalData, file)
```

Argument values to know for `reqHistoricalData`:

- **`duration`** is a `"n unit"` string, where unit is one of `S` (seconds), `D` (days), `W` (weeks), `M` (months), `Y` (years) - e.g. `"5 D"`.
- **`barSize`** valid values: 1 sec, 5 secs, 15 secs, 30 secs, 1 min, 2 mins, 3 mins, 5 mins, 10 mins, 15 mins, 20 mins, 30 mins, 1 hour, 2 hours, 3 hours, 4 hours, 8 hours, 1 day, 1 week, 1 month.
- **`whatToShow`** values: Trades, Midpoint, Bid, Ask, Bid_Ask.

## Gotchas

- ~100 simultaneous streaming lines max by default; more raises an error.
- Requires the relevant market-data subscription in your IBKR account for the instrument.
- Not every `barSize`/`duration` combination is valid for every security.
- Default streaming output is raw and hard to read - customize the callback ([[customizing-market-data-functions]]).

## Related

- Previous: [[introduction-to-ibrokers-package]]
- Next: [[customizing-market-data-functions]]
- Contract objects: [[introduction-to-ibrokers-package]]
- **Cross-platform equivalents:**
  - [[python-receiving-market-data]] (Python TWS API)
  - [[requesting-market-data]] (Web API / Client Portal API)

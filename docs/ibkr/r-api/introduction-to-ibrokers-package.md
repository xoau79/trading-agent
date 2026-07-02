---
title: Introduction to the IBrokers Package
source: https://www.interactivebrokers.com/campus/trading-lessons/introduction-to-ibrokers-package/
type: reference
course: trading-using-r
date_added: 2026-06-13
tags: [ibkr-api, r-language, ibrokers-package, tws-api, contracts]
---

# Introduction to the IBrokers Package

## Concepts

- **IBrokers** is a pure-R implementation of the TWS API (author Jeffrey Ryan, maintainer Joshua Ulrich). It lets R retrieve real-time data, read contract details and account info, and place/cancel orders - all through a running TWS/IB Gateway.
- **Install** with base R, then load it each session. Connect with `twsConnect()`, which returns a **twsConnection** object you pass to every later call. Reuse that one object; close it with `twsDisconnect()` when done.
- A **contract object** describes what you want to trade or quote. Build it with `twsContract()` (full, verbose) or the convenience wrappers `twsEquity()`, `twsFuture()`, `twsOption()`, `twsCurrency()`. Field values come from TWS's Financial Instrument Information.

## Code examples

> The lesson shows its R as screenshots; the signatures below are transcribed from the lesson's stated parameters and the IBrokers documentation, not copied from a code block. Treat them as a documented API reference.

```r
install.packages("IBrokers")   # one-time install from CRAN
library(IBrokers)              # load the package each session
```

```r
tws <- twsConnect(clientId = 1, port = 7497)  # connect to TWS; returns a twsConnection object
isConnected(tws)               # TRUE if the connection is live
twsConnectionTime(tws)         # timestamp the connection was opened
reqAccountUpdates(tws, acctCode = "All")  # request/print account details from TWS
twsDisconnect(tws)             # close the connection
```

```r
# Verbose contract constructor (most fields default to "" / 0):
twsContract(conId = 0, symbol = "IBM", sectype = "STK", exch = "SMART",
            primary = "", expiry = "", strike = 0.0, right = "", multiplier = "",
            cusip = "", rating = "", desc = "", expiryList = "", opt_vol_mult = "",
            func_code = "", combo_legs = "", comm_rule_id = "", sec_id_type = "",
            sec_id = "", hedge_type = "", hedge_param = "", underComp = "")

# Convenience wrappers (preferred for common cases):
twsEquity()    # stock contract
twsFuture()    # futures contract
twsOption()    # option contract
twsCurrency()  # forex/currency contract
```

## Gotchas

- `port` must match TWS's API socket (paper 7497 / live 7496 by convention) - see [[configuring-ibs-trader-workstation]].
- Pass a consistent `clientId`; a clientId already in use by another live connection is rejected.
- IBrokers is third-party; IBKR makes no guarantees about its accuracy or performance.

## Related

- Previous: [[configuring-ibs-trader-workstation]]
- Next: [[market-data-functions]]
- Order side of the package: [[order-functions]]

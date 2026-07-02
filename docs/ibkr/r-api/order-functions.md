---
title: Order Functions (IBrokers)
source: https://www.interactivebrokers.com/campus/trading-lessons/order-functions/
type: reference
course: trading-using-r
date_added: 2026-06-13
tags: [ibkr-api, r-language, ibrokers-package, order-placement, order-types]
---

# Order Functions (IBrokers)

## Concepts

- Four functions cover the order lifecycle:
  - **`reqIds()`** - get the next valid order ID from TWS (returned as a character string). Every order needs a unique ID greater than all previously used IDs.
  - **`twsOrder()`** - build an order object from your parameters.
  - **`placeOrder()`** - submit it (connection + contract + order).
  - **`cancelOrder()`** - cancel by connection + order ID.
- **Key `twsOrder` parameters:**
  - `action` - BUY, SELL, or SSHORT (short sell).
  - `totalQuantity` - shares/contracts.
  - `orderType` - MKT (market), LMT (limit), STP (stop), STPLMT (stop-limit), PEGMKT (trailing market), TRAILLIMIT (trailing limit).
  - `lmtPrice` - price for limit-type orders.
  - `trailStopPrice` - only for trailing-limit orders.
  - `transmit` - boolean; whether to route the order to TWS immediately.

## Code examples

> Code in this lesson is shown as images; the signatures below are transcribed from the lesson's stated parameters / IBrokers docs, not copied from code blocks.

```r
reqIds(conn)                  # next valid order ID (character) from a tws connection
twsOrder(orderId, action, totalQuantity, orderType, lmtPrice, transmit, trailStopPrice)  # build order object
placeOrder(twsconn, Contract, Order)   # submit order: connection, contract, order
cancelOrder(twsconn, orderId)          # cancel an order by id
```

## Gotchas

- Each new order needs a unique, increasing order ID; use `reqIds()` rather than hard-coding. The "Reset API order ID sequence" button in TWS only works with no active orders (see [[configuring-ibs-trader-workstation]]).
- `transmit = FALSE` stages an order without sending it - useful for building multi-leg/bracket orders before transmitting the parent.
- Market conditions affect execution: orders may fill at a different price or not at all.
- Test in a paper account before going live (the IBKR refrain across these courses).

## Related

- Previous: [[customizing-market-data-functions]]
- Next: [[sample-trading-strategy]]
- TWS order-ID reset: [[configuring-ibs-trader-workstation]]
- **Cross-platform equivalents:**
  - [[python-placing-orders]] (Python TWS API)
  - [[placing-orders]] (Web API / Client Portal API)
  - Excel: see [[introduction-to-the-tws-excel-api-initial-setup]]
- **Applied in strategy:** [[sample-trading-strategy]]

---
title: TWS Python API Placing Complex Orders
source: https://www.interactivebrokers.com/campus/trading-lessons/python-complex-orders/
type: reference
course: python-tws-api
date_added: 2026-06-13
tags: [ibkr-api, tws-api, bracket-orders, combo-orders, spreads, risk-management]
---

# TWS Python API Placing Complex Orders

## Concepts

### Combo orders (spreads, "BAG" contracts)
- A combo buys and sells multiple instruments as ONE order (e.g. buy TSLA, sell AAPL; or option spreads like iron condors).
- Contract setup: `symbol` lists both underlyings ("AAPL,TSLA"), `secType = "BAG"`, plus a list of **ComboLeg** objects, each with `conId` (the contract ID), `ratio`, `action`, `exchange`.
- Direction logic works like multiplying by +1/-1: buying the combo with a positive-ratio leg and a negative leg, or selling the reverse, produces the same net position. Ratios need not be 1:1.
- Up to six legs, exchange-dependent (NASDAQ stocks support 6, SPX/CBOE do not).

### Bracket orders
- One parent order plus two children (profit-taker LMT, stop-loss STP) that only activate when the parent fills. Same structure as hedging and OCA (one-cancels-all) groups.
- The transmission trick: parent and profit-taker are sent with `transmit = False` (held at TWS), the final stop-loss has `transmit = True`, which releases all three together. Children reference the parent via `parentId`; child IDs are parentId + 1, parentId + 2.

## Code examples

Combo order core (callbacks and connect as in [[python-placing-orders]]; clientId 1000):

```python
from ibapi.contract import ComboLeg
from ibapi.tag_value import TagValue

def nextValidId(self, orderId: int):
    mycontract = Contract()
    mycontract.symbol = "AAPL,TSLA"
    mycontract.secType = "BAG"
    mycontract.exchange = "SMART"
    mycontract.currency = "USD"

    leg1 = ComboLeg()
    leg1.conId = 76792991
    leg1.ratio = 1
    leg1.action = "BUY"
    leg1.exchange = "SMART"

    leg2 = ComboLeg()
    leg2.conId = 265598
    leg2.ratio = 1
    leg2.action = "SELL"
    leg2.exchange = "SMART"

    mycontract.comboLegs = []
    mycontract.comboLegs.append(leg1)
    mycontract.comboLegs.append(leg2)

    myorder = Order()
    myorder.orderId = orderId
    myorder.action = "BUY"
    myorder.orderType = "LMT"
    myorder.lmtPrice = 80
    myorder.totalQuantity = 10
    myorder.tif = "GTC"
    myorder.smartComboRoutingParams = []
    myorder.smartComboRoutingParams.append(TagValue('NonGuaranteed', '1'))

    self.placeOrder(orderId, mycontract, myorder)
```

Bracket order core (same scaffold):

```python
def nextValidId(self, orderId: int):
    mycontract = Contract()
    mycontract.symbol = "AAPL"
    mycontract.secType = "STK"
    mycontract.exchange = "SMART"
    mycontract.currency = "USD"

    parent = Order()
    parent.orderId = orderId
    parent.orderType = "LMT"
    parent.lmtPrice = 140
    parent.action = "BUY"
    parent.totalQuantity = 10
    parent.transmit = False

    profit_taker = Order()
    profit_taker.orderId = parent.orderId + 1
    profit_taker.parentId = parent.orderId
    profit_taker.action = "SELL"
    profit_taker.orderType = "LMT"
    profit_taker.lmtPrice = 137
    profit_taker.totalQuantity = 10
    profit_taker.transmit = False

    stop_loss = Order()
    stop_loss.orderId = parent.orderId + 2
    stop_loss.parentId = parent.orderId
    stop_loss.orderType = "STP"
    stop_loss.auxPrice = 155
    stop_loss.action = "SELL"
    stop_loss.totalQuantity = 10
    stop_loss.transmit = True

    self.placeOrder(parent.orderId, mycontract, parent)
    self.placeOrder(profit_taker.orderId, mycontract, profit_taker)
    self.placeOrder(stop_loss.orderId, mycontract, stop_loss)
```

## Gotchas

- **The lesson's bracket prices are inverted** (IBKR acknowledged this): for a BUY at 140, the profit-taker should be ABOVE 140 and the stop-loss BELOW - the sample's 137/155 are swapped. Logic and structure are correct; values are not.
- Forgetting `transmit = False` on the parent sends it alone immediately, without protection legs attached.
- Non-guaranteed combos require `TagValue('NonGuaranteed', '1')` in smartComboRoutingParams.
- **Order Efficiency Ratio**: IBKR tracks (submissions + modifications + cancellations) / executed orders per account; keep it around 20 or less. Relevant for any bot that frequently modifies orders.

## Related

- Previous: [[python-placing-orders]]
- Next: [[python-account-portfolio]]
- **Cross-platform equivalents:**
  - [[complex-orders]] (Web API / Client Portal API)
- **Trading concepts:**
  - Bracket orders = automated version of the stop-loss discipline in [[2026-06-08-math-of-winning-in-trading]]
  - Risk management concepts apply to all order types

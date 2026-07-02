---
title: Placing Orders using TWS Python API
source: https://www.interactivebrokers.com/campus/trading-lessons/python-placing-orders/
type: reference
course: python-tws-api
date_added: 2026-06-13
tags: [ibkr-api, tws-api, order-placement, order-status, executions, paper-trading]
---

# Placing Orders using TWS Python API

## Concepts

- `EClient.placeOrder(orderId, contract, order)` submits an order. Anything you can do in the TWS GUI you can do from the API, including IB Algos, bracket and conditional orders.
- An **Order object** needs at minimum: `orderId` (from nextValidId), `action` ("BUY"/"SELL"), `orderType` ("MKT", "LMT", ...), `totalQuantity`. Common extras: `tif` (time in force - "DAY" default, "GTC", "MOC"...), `lmtPrice` for limit orders.
- Three callbacks track an order's life:
  - `openOrder` - full order + contract echo, plus an orderState with commission and margin impact.
  - `orderStatus` - status updates: pre-submitted, submitted, filled, with fill counts and prices.
  - `execDetails` - one callback per fill (including each partial fill), with execution ID and liquidity flag.
- **Modifying an order**: resubmit via placeOrder with the SAME orderId and changed fields.
- This lesson's program structure is event-chained: nextValidId triggers reqContractDetails, whose callback places the order - no threading or sleeps needed.

## Code examples

Complete lesson program:

```python
from ibapi.client import *
from ibapi.wrapper import *

class TestApp(EClient, EWrapper):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId: OrderId):
        mycontract = Contract()
        mycontract.symbol = "AAPL"
        mycontract.secType = "STK"
        mycontract.exchange = "SMART"
        mycontract.currency = "USD"

        self.reqContractDetails(orderId, mycontract)

    def contractDetails(self, reqId: int, contractDetails: ContractDetails):
        print(contractDetails.contract)

        myorder = Order()
        myorder.orderId = reqId
        myorder.action = "SELL"
        myorder.tif = "GTC"
        myorder.orderType = "LMT"
        myorder.lmtPrice = 144.80
        myorder.totalQuantity = 10

        self.placeOrder(myorder.orderId, contractDetails.contract, myorder)

    def openOrder(self, orderId: OrderId, contract: Contract, order: Order, orderState: OrderState):
        print(f"openOrder. orderId: {orderId}, contract: {contract}, order: {order}")

    def orderStatus(self, orderId: OrderId, status: str, filled: Decimal, remaining: Decimal, avgFillPrice: float, permId: int, parentId: int, lastFillPrice: float, clientId: int, whyHeld: str, mktCapPrice: float):
        print(f"orderId: {orderId}, status: {status}, filled: {filled}, remaining: {remaining}, avgFillPrice: {avgFillPrice}, permId: {permId}, parentId: {parentId}, lastFillPrice: {lastFillPrice}, clientId: {clientId}, whyHeld: {whyHeld}, mktCapPrice: {mktCapPrice}")

    def execDetails(self, reqId: int, contract: Contract, execution: Execution):
        print(f"reqId: {reqId}, contract: {contract}, execution: {execution}")

app = TestApp()
app.connect("127.0.0.1", 7497, 100)
app.run()
```

## Gotchas

- **Always test in paper first** - the lesson repeats this; verify a complex order can even be built in the TWS GUI before coding it.
- **Minimum tick size**: AAPL has a one-cent min tick, so limit prices with more than two decimals are rejected. Varies per instrument.
- Multiple partial fills mean multiple execDetails callbacks for one order - sum them, do not assume one callback = one complete fill.
- Remember Read-Only API must be unchecked ([[installing-configuring-tws-for-the-api]]) or every order fails.

## Related

- Previous: [[python-receiving-market-data]]
- Next: [[python-complex-orders]]
- Contract setup: [[defining-contracts-in-the-tws-api]]
- **Cross-platform equivalents:**
  - [[placing-orders]] (Web API / Client Portal API)
  - [[order-functions]] (R API / IBrokers)
  - Excel: see [[introduction-to-the-tws-excel-api-initial-setup]] and [[advanced-tws-dde-functionality]]
- **Applied in strategy:** [[implementing-donchian-channel-trading-app]], [[running-the-donchian-channel]]

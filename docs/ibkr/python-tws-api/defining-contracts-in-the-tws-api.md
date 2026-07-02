---
title: Defining Contracts in the TWS API
source: https://www.interactivebrokers.com/campus/trading-lessons/defining-contracts-in-the-tws-api/
type: reference
course: python-tws-api
date_added: 2026-06-13
tags: [ibkr-api, tws-api, contracts, instruments, options, futures]
---

# Defining Contracts in the TWS API

## Concepts

- A **Contract object** describes the financial instrument you want to trade or get data for. It is the foundation for both market data requests and order placement.
- Four fields identify almost any instrument: `symbol`, `secType`, `exchange`, `currency`.
- `secType` codes: STK (stock), OPT (option), FUT (future), and others.
- To check what a Contract resolves to, send it to `EClient.reqContractDetails()` - the `contractDetails` callback returns a ContractDetails object with supported exchanges, trading hours, order types, timezone, and the fully resolved contract.
- The ContractDetails object is best printed with `vars()` to see all fields.
- Cross-check in TWS itself: search the instrument, right-click -> Financial Instrument Details -> Description.

## Code examples

Complete lesson program (scaffold is the same TestApp as [[essential-components-of-tws-api-programs]]):

```python
def contractDetails(self, reqId, contractDetails):
    attrs = vars(contractDetails)
    print("\n".join(f"{name}: {value}" for name, value in attrs.items()))
    # print(contractDetails.contract)

def contractDetailsEnd(self, reqId):
    print("End of contract details")
    self.disconnect()
```

Stock contract:

```python
mycontract = Contract()
mycontract.symbol = "AAPL"
mycontract.secType = "STK"
mycontract.currency = "USD"
mycontract.exchange = "SMART"
mycontract.primaryExchange = "NASDAQ"
```

Future contract:

```python
mycontract.symbol = "ES"
mycontract.secType = "FUT"
mycontract.currency = "USD"
mycontract.exchange = "CME"
mycontract.lastTradeDateOrContractMonth = 202412
```

Option contract:

```python
mycontract.symbol = "SPX"
mycontract.secType = "OPT"
mycontract.currency = "USD"
mycontract.exchange = "SMART"
mycontract.lastTradeDateOrContractMonth = 202412
mycontract.right = "P"
mycontract.tradingClass = "SPXW"
mycontract.strike = 5300
```

Request:

```python
app.reqContractDetails(app.nextId(), mycontract)
```

## Gotchas

- **SMART routing only works for stocks, options, and combos** - futures need a specific exchange like CME.
- Ambiguous symbols (multiple companies share a ticker): set `primaryExchange` to disambiguate.
- Index options with overlapping expirations (e.g. monthly SPX vs weekly SPXW): `tradingClass` may be the only distinguishing field. Without filters like `strike`, a request can return huge result lists.

## Related

- Previous: [[essential-components-of-tws-api-programs]]
- Next: [[python-receiving-market-data]]
- **Cross-platform equivalent:**
  - [[contract-search]] (Web API / Client Portal API)
- **Used throughout:**
  - [[python-receiving-market-data]]
  - [[python-placing-orders]]
  - [[python-complex-orders]]
  - [[implementing-donchian-channel-trading-app]]

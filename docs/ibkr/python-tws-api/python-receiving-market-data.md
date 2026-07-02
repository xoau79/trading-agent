---
title: Python API - Requesting Market Data
source: https://www.interactivebrokers.com/campus/trading-lessons/python-receiving-market-data/
type: reference
course: python-tws-api
date_added: 2026-06-13
tags: [ibkr-api, tws-api, market-data, historical-data, tick-types, data-subscriptions]
---

# Python API - Requesting Market Data

## Concepts

- **Subscriptions cost money and are per-user**: most accounts need a $500 minimum balance to subscribe. Data shown inside TWS is "on-platform" (often free); API access is "off-platform" and typically paid.
- **Four market data types** via `app.reqMarketDataType(n)`: 1 = live, 2 = frozen (last close), 3 = delayed 15 min, 4 = delayed frozen. If you hold a live subscription and ask for delayed, you get live anyway.
- **Streaming data**: `reqMktData()` returns the same data you would see in a TWS watchlist. Results arrive as ticks in the `tickPrice` and `tickSize` callbacks. Each tick type is an integer (bid, ask, last, close...); convert with `TickTypeEnum.toStr()`, full list in `ticktype.py` in the ibapi source.
- **Snapshot**: passing snapshot=True gives a single 11-second aggregate instead of a stream.
- **Historical data**: `reqHistoricalData()` returns bars to the `historicalData` callback; `reqHeadTimeStamp()` tells you how far back data exists for an instrument.

## Code examples

Streaming delayed data for AAPL (TestApp scaffold same as [[essential-components-of-tws-api-programs]]; new callbacks shown):

_Related: [[requesting-market-data]] (Web API equivalent), [[implementing-donchian-channel-trading-app]] (uses historical data in a strategy)_

```python
from ibapi.ticktype import TickTypeEnum

def tickPrice(self, reqId, tickType, price, attrib):
    print(f"reqId: {reqId}, tickType: {TickTypeEnum.toStr(tickType)}, price: {price}, attrib: {attrib}")

def tickSize(self, reqId, tickType, size):
    print(f"reqId: {reqId}, tickType: {TickTypeEnum.toStr(tickType)}, size: {size}")
```

```python
mycontract = Contract()
mycontract.symbol = "AAPL"
mycontract.secType = "STK"
mycontract.exchange = "SMART"
mycontract.currency = "USD"

app.reqMarketDataType(3)
app.reqMktData(app.nextId(), mycontract, "232", False, False, [])
```

reqMktData arguments: reqId, contract, genericTickList (comma-separated string, "232" = mark price), snapshot, regulatorySnapshot, options.

Earliest available data point:

```python
def headTimestamp(self, reqId, headTimeStamp):
    print(headTimeStamp)
    print(datetime.datetime.fromtimestamp(int(headTimeStamp)))
    self.cancelHeadTimeStamp(reqId)

app.reqHeadTimeStamp(app.nextId(), mycontract, "TRADES", 1, 2)
```

Historical bars:

```python
def historicalData(self, reqId, bar):
    print(reqId, bar)

def historicalDataEnd(self, reqId, start, end):
    print(f"Historical Data Ended for {reqId}. Started at {start}, ending at {end}")
    self.cancelHistoricalData(reqId)

app.reqHistoricalData(app.nextId(), mycontract, "20240523 16:00:00 US/Eastern", "1 D", "1 hour", "TRADES", 1, 1, False, [])
```

reqHistoricalData arguments in order:
1. reqId
2. contract
3. endDateTime - "YYYYMMDD HH:MM:SS TIMEZONE", empty string = now
4. durationString - e.g. "1 D"
5. barSizeSetting - e.g. "1 hour"
6. whatToShow - "TRADES", "BID", "ASK", ...
7. useRTH - 1 = regular trading hours only, 0 = include extended
8. formatDate - 1 = date string, 2 = epoch integer
9. keepUpToDate - True streams new bars via historicalDataUpdate()
10. chartOptions - empty list

## Gotchas

- **No subscription = no historical data** for that instrument (unlike delayed live data, there is no free fallback).
- Regulatory snapshots cost about $0.01 per request, capped at the subscription price.
- 5-second bars are only supported for durations up to 1 hour.
- endDateTime must use the exchange's timezone; returned timestamps follow your TWS timezone setting (UTC option in Global Configuration -> API).
- The first bar returned can be a partial session (e.g. a 30-minute "1 hour" bar at the open) - measure bar size from later bars, not the first.
- Beyond price/size ticks, reqMktData can return news, string and option Greek values depending on genericTickList.

## Related

- Previous: [[defining-contracts-in-the-tws-api]]
- Next: [[python-placing-orders]]
- Relevant to the trading agent's data layer once it moves off simulated data.

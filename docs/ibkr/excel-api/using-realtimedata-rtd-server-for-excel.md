---
title: Using RealTimeData (RTD) Server for Excel
source: https://www.interactivebrokers.com/campus/trading-lessons/using-realtimedata-rtd-server-for-excel/
type: reference
course: excel-and-the-tws-api
date_added: 2026-06-13
tags: [ibkr-api, excel-api, rtd, market-data, generic-ticks]
---

# Using RealTimeData (RTD) Server for Excel

## Concepts

- **RTD** is a built-in Excel worksheet function that pulls data from a real-time-data server. Here TWS or IB Gateway is that server, so each cell holds a formula for one market-data field of one instrument and updates automatically as quotes change.
- **Main use:** building dynamic, custom watchlists in Excel that show live quotes without manual refresh.
- The formula always starts with the progID `"tws.twsrtdserverctrl"`, then an empty second argument (the server - empty means the default local connection), followed by topic strings describing the instrument and the quote type.
- A custom host, port, and ClientID can be appended for non-default connections.

### Topic parameters

| Param | Example | Meaning |
|-------|---------|---------|
| `sym` | AMZN | Symbol |
| `sec` | STK, FUT, CASH | Security type |
| `exch` | SMART, COMEX, IDEALPRO | Exchange |
| `cur` | USD | Currency |
| `qt` | Last, Bid, Ask, Volume | Quote / tick type (the column you want) |
| `genticks` | 165, 456 | Generic tick id for extra data |
| `exp` | 202505 | Expiration (for futures) |

## Code examples

Explicit syntax - last price for Amazon stock:

```excel
=RTD("tws.twsrtdserverctrl",,"sym=AMZN", "sec=STK", "exch=SMART", "cur=USD", "qt=Last")
```

Shorthand syntax - same request, `SYMBOL@EXCHANGE` form:

```excel
=RTD("tws.twsrtdserverctrl",," AMZN@SMART")
```

52-week high via generic tick 165:

```excel
=RTD("tws.twsrtdserverctrl",,"sym=AMZN", "sec=STK", "exch=SMART", "cur=USD", "genticks=165", "qt=Week52Hi")
```

Dividend information via generic tick 456:

```excel
=RTD("tws.twsrtdserverctrl",,"sym=AMZN", "sec=STK", "exch=SMART", "cur=USD", "genticks=456", "qt=IBDividends")
```

## Gotchas

- **Error 321 "Incorrect generic tick list"** - returned when you request a generic tick the instrument does not support; the error message lists which ones are supported.
- Not all generic ticks are supported for all instrument types. Data that does not appear in TWS will not come back through the API.
- Because of RTD/Excel limitations there can be a small delay between the Excel value and the TWS value.
- Install the API on the OS drive (C:) or there may be issues.
- Quote-type (`qt`) strings are case-sensitive.
- The RTD sample spreadsheet uses **START** / **END** macro buttons to toggle the formulas active or inactive.

## Related

- Previous: [[introduction-to-the-tws-excel-api-initial-setup]]
- Next: [[the-dynamic-data-exchange-dde-in-excel-using-a-sample-spreadsheet]]

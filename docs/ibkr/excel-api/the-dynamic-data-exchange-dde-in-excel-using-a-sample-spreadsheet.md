---
title: The Dynamic Data Exchange (DDE) in Excel using a Sample Spreadsheet
source: https://www.interactivebrokers.com/campus/trading-lessons/the-dynamic-data-exchange-dde-in-excel-using-a-sample-spreadsheet/
type: reference
course: excel-and-the-tws-api
date_added: 2026-06-13
tags: [ibkr-api, excel-api, dde, socket-bridge, market-data]
---

# The Dynamic Data Exchange (DDE) in Excel using a Sample Spreadsheet

## Concepts

- **DDE** is a legacy Microsoft protocol for inter-process communication between Windows apps. IBKR's modern DDE (TWS API 975+) does not use the old `.dll`; instead a **Java socket bridge** translates DDE strings into socket calls.

### Legacy DDE vs the new socket bridge

| Aspect | Legacy DDE | Socket bridge |
|--------|-----------|---------------|
| Architecture | `.dll` file | Java socket connection |
| Connections | One per machine | Up to 32 instances per TWS session |
| TWS bitness | 32-bit only | 32- or 64-bit |
| Functions | Limited | All socket functions (news, tick data, PnL) |

### Setup

1. Launch TWS or IB Gateway.
2. **Global Configuration > API > Settings**.
3. Check **"Enable ActiveX and Socket Clients"** (IB Gateway enables this automatically).
4. Confirm the port is **7496** (default socket bridge port).
5. Leave **"Enable DDE connections"** unchecked - the old DDE path is deprecated since TWS Build 980+.
6. Double-click `C:\TWS API\samples\DdeSocketBridge\runDdeSocketBridge.bat`.
7. Wait for the popup to show **"Connected!"**.
8. Keep the terminal window open - closing it disconnects the bridge.

Default socket username is **twsserver**; default port **7496**. The sample workbook is **NewTwsDde.xls**, with tabs for **Tickers** (market data / watchlist), **historicalData**, **Account**, and more.

## Code examples

The batch file - edit the `-p` flag for a different port and the username after `-` (here `myDDE`):

```batch
echo off
if not exist "DdeSocketBridge.jar" goto :error
java -Djava.library.path=.src\main\resources -jar DdeSocketBridge.jar -myDDE -p7497
goto :end
:error
echo DdeSocketBridge.jar is not found
:end
```

Market data is a two-step request. Step 1 initializes request `id2` for Amazon stock:

```excel
=Stwsserver|tik!'id2?req?AMZN_STK_SMART_USD_~/'
```

Step 2 reads a specific tick type (here the bid) for that request id:

```excel
=Stwsserver|tik!id2?bid
```

Available tick types include `bid`, `ask`, `last` (plus generic ticks). The `twsserver` part is the socket bridge username - change it if you changed it in the batch file.

Converting a legacy DDE sheet: just swap the old username for `twsserver`.

```excel
=Ssample123|tik!'id1?req?EUR_CASH_IDEALPRO_USD_~/'
```

becomes

```excel
=Stwsserver|tik!'id1?req?EUR_CASH_IDEALPRO_USD_~/'
```

Workflow in the Tickers tab: fill the contract description (symbol, secType, exchange, currency, primaryExchange), select the symbol row(s) (Ctrl+click for several), click **Req Mkt Data** to stream, **Cancel Mkt Data** to stop.

## Gotchas

- **Java not installed** - the batch window flashes momentarily and disappears; install a fresh JRE.
- **"Server Error Validating Request"** - reset trading presets (IBKR Desktop: Portfolio > Settings > Trading > Revert to Defaults).
- The DdeSocketBridge terminal must stay open the entire session.
- Port mismatch: the batch file `-p` flag must match the TWS API Settings port.
- "Enable ActiveX and Socket Clients" must be checked before running the batch file.
- Windows only (uses `.bat`).

## Related

- Previous: [[using-realtimedata-rtd-server-for-excel]]
- Next: [[activex-in-excel-with-a-tws-sample-spreadsheet]]
- Advanced order placement with this sheet: [[advanced-tws-dde-functionality]]

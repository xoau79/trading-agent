---
title: ActiveX in Excel, with a TWS Sample Spreadsheet
source: https://www.interactivebrokers.com/campus/trading-lessons/activex-in-excel-with-a-tws-sample-spreadsheet/
type: reference
course: excel-and-the-tws-api
date_added: 2026-06-13
tags: [ibkr-api, excel-api, activex, vba, twslib]
---

# ActiveX in Excel, with a TWS Sample Spreadsheet

## Concepts

- **ActiveX** is a legacy Microsoft COM technology that lets applications share information. IBKR's implementation wraps the C#/.NET API as an open-source project called **TWSLib** (the `TwsLib.dll` from the `tests/` folder). Compared with RTD (data only) and DDE (string formulas), ActiveX gives the fullest programmatic control because you drive it from VBA.
- Connect with three parameters:
  - **Host** - leave blank for localhost (Excel and TWS on the same machine).
  - **Port** - default **7496**.
  - **ClientId** - any positive integer that identifies this API connection.
- The sample workbook (`C:\TWS API\samples\Excel`) has tabs for each function:
  - **General** - connectivity (Connect / Disconnect buttons).
  - **Tickers** - watchlist queries and market-data requests.
  - Plus **Orders / Basic Orders**, **Account**, **Executions**, **Portfolio**, and others.
- **Market data workflow:** enter the contract (symbol, exchange, currency, type), click the symbol row (e.g. IBM in row 12), click **Request Market Data**, watch the tick types populate, then **Cancel Market Data** to stop.
- **Multiple accounts:** supply the account ID per request - e.g. column AO on the "Basic Orders" tab, or cell A6 on the "Account" tab to choose which account receives account data.

## Code examples

No standalone formulas - the logic lives in VBA behind the buttons.

- Open the VBA editor with **Alt-F11** to read the subroutines, forms, and modules; the Tickers tab shows the request/response pattern.
- Sample location: `C:\TWS API\samples\Excel`
- Connection values: Host blank (localhost), Port `7496`, ClientId any positive integer.

## Gotchas

- **Windows only** - ActiveX Excel is not available on Linux or macOS.
- Requires `TwsLib.dll` (from the `tests/` folder) to be present.
- For multi-account logins you must specify the account ID on each relevant request, or it will not know where to route.
- IBKR cannot provide programming assistance; open a support ticket under the **API** category for help.
- The samples are for technical demonstration only, not trading advice.

## Related

- Previous: [[the-dynamic-data-exchange-dde-in-excel-using-a-sample-spreadsheet]]
- Next: [[advanced-tws-dde-functionality]]

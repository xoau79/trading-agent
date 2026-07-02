---
title: Advanced TWS DDE Functionality
source: https://www.interactivebrokers.com/campus/trading-lessons/advanced-tws-dde-functionality/
type: reference
course: excel-and-the-tws-api
date_added: 2026-06-13
tags: [ibkr-api, excel-api, dde, bracket-orders, vba]
---

# Advanced TWS DDE Functionality

## Concepts

- **Placing orders from the DDE sheet:** go to the **Basic Orders** tab, enter the contract (stock, future, option, etc.) and order parameters (type, quantity, price), highlight the symbol, and click **Place/Modify Order**. The order reaches TWS as if it were manually submitted.
  - Caveat from the lesson: "The sample spreadsheet is not meant to be used as a robust trading application."
- **Bracket orders** - a risk-management structure of one parent plus two child orders linked by a `parentId`:
  - **BUY bracket:** a high-side sell limit (take profit) + a low-side sell stop (stop loss).
  - **SELL bracket:** a high-side buy stop + a low-side buy limit.
  - Only the **final** child has `Transmit=True`; the parent and the first child are `Transmit=False` so all three release to the market together.
- **Extended Order Attributes** tab (rows 73-74) lets you set many order parameters at once: configure the values, run the **Apply Extended Template** macro, then copy the generated parent order id into row 74. Logic uses `0 = false`, `1 = true`.
- Beyond orders, advanced DDE use (historical data into cells, studies/indicators, custom conditional orders) requires your own VBA.

### Bracket example (GOOG limit buy)

1. Parent order: set `Transmit=0` via the Extended Order Attributes tab.
2. First child (profit-taker): SELL LMT, set `parentId`, `Transmit=0`.
3. Second child (stop-loss): STP order type, leave the limit blank, put the stop in the **auxiliary price field**, set `Transmit=1`.

Submitted correctly, all three appear in the TWS order monitor sharing the same "key" value.

## Code examples

No cell formulas - the advanced behavior is VBA behind the buttons.

- **Alt+F11** opens the Visual Basic Editor (Project Explorer, Properties Window, Code Window). Double-click an item under "Microsoft Excel Objects" to see that worksheet's code.
- To read a button's macro: **View** tab > **Macros** > **View Macros**, select it, click **Edit** (the lesson shows the `requestHistoricalData` button's macro as an example).
- Transmit logic for a bracket: parent and first child `Transmit=False` (0), final child `Transmit=True` (1).

## Gotchas

- The sample is explicitly **not** a production trading app.
- If you forget to set `Transmit=False` on the parent and first child, the bracket execution breaks (orders fire individually instead of as a group).
- When setting `parentId`, copy "the number only" - not surrounding text.
- Historical data and custom indicators need programmed VBA functions; that is outside the tutorial's scope.
- Use a paper account before any live trading.

## Related

- Previous: [[activex-in-excel-with-a-tws-sample-spreadsheet]]
- Builds on the DDE sample from [[the-dynamic-data-exchange-dde-in-excel-using-a-sample-spreadsheet]]
- Next: [[diagnosing-issues-and-troubleshooting-with-the-tws-api]]

---
title: Configuring IB's Trader Workstation (for the R API)
source: https://www.interactivebrokers.com/campus/trading-lessons/configuring-ibs-trader-workstation/
type: reference
course: trading-using-r
date_added: 2026-06-13
tags: [ibkr-api, r-language, api-configuration, tws-api, ibrokers-package]
---

# Configuring IB's Trader Workstation (for the R API)

## Concepts

- The connection path is three tiers: **your R app -> IB Trader Workstation (TWS) -> IBKR data centers.** The IBrokers package talks to TWS locally; TWS talks to IBKR. TWS (or IB Gateway) must be running and configured for the API first. Same model as every other IBKR API course - cf. [[installing-configuring-tws-for-the-api]] (Python) and [[introduction-to-the-tws-excel-api-initial-setup]] (Excel).
- **Enable the API in TWS:** menu **File > Global Configuration > Application Settings > API > Settings**, then check:
  - **Enable ActiveX and Socket Clients**
  - **Create API message log file**
  - **Include market data in API log file**

  Click **Apply**, then **OK**.
- **API message log** (for troubleshooting):
  - Location (Windows): the `C:\Jts` folder.
  - File name: `log.[day].txt`, where `[day]` is the weekday it was created.
  - Default logging level is **Error** (minimal). Set it to **Detail** to capture full API message traffic. Checking "include market data" adds real-time data to the log when diagnosing data issues.
- **Reset API order ID sequence** button: resets the order-ID counter, but only when no active orders exist. Every new order needs a unique ID greater than all previously used IDs (this matters in [[order-functions]]).

## Code examples

None - configuration is done in the TWS GUI.

## Gotchas

- The lesson does **not** state the socket port number. By IBKR convention (and a comment thread on the lesson page) it is **7497 for paper/simulated** and **7496 for live** - confirm yours in the same API Settings panel and pass it to `twsConnect(port = ...)` in [[introduction-to-ibrokers-package]].
- The order-ID reset only works with zero active orders.
- IBKR Lite accounts have restricted API access; API trading generally requires IBKR Pro (noted across the API courses).

## Related

- Previous: [[installing-r-and-rstudio]]
- Next: [[introduction-to-ibrokers-package]]
- Same settings panel as [[installing-configuring-tws-for-the-api]] and [[introduction-to-the-tws-excel-api-initial-setup]]

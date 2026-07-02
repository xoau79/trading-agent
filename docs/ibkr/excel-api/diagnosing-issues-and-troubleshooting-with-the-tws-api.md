---
title: Diagnosing Issues and Troubleshooting with the TWS API
source: https://www.interactivebrokers.com/campus/trading-lessons/diagnosing-issues-and-troubleshooting-with-the-tws-api/
type: reference
course: excel-and-the-tws-api
date_added: 2026-06-13
tags: [ibkr-api, tws-api, troubleshooting, api-logs, error-codes]
---

# Diagnosing Issues and Troubleshooting with the TWS API

## Concepts

- The API is an interface/extension of TWS and IB Gateway, so the first debugging step is to **reproduce the behavior directly in TWS**. If TWS does the same thing, it is not an API bug - it is expected platform behavior.
- API errors arrive through **callback functions**, each tied to a **request ID (reqId)** that links the error to a specific order, market-data subscription, or historical-data call. Matching error codes to request ids is how you isolate the cause.
- **Enable detailed logging** (off by default): **File > Global Configuration > API > Settings**, check **"create API message log file"** (a separate API-only log), set the **logging level** to **"Detail"**, optionally check **"Include market data in API log file"** when debugging market data, then **Apply** and **OK**.
- **View / export logs:** **Account > Diagnostics**, choose TWS or API logs, pick the date, and export to a directory (saved as text files).
- **Send logs to support:** press **Ctrl-Alt-Q** in TWS/IB Gateway, or **Help > Upload Diagnostics**, then submit.
- **Reading an API log:** the directional arrow shows message flow - an outbound arrow is a request going from the API to TWS; an inbound arrow is the response from TWS back to the API.

## Code examples

No code - these are the exact menu paths, settings, and shortcuts to remember:

- **File > Global Configuration > API > Settings** - enable logging
- Checkboxes: **"create API message log file"**, **"Include market data in API log file"**
- Logging level dropdown: **"Detail"**
- **Account > Diagnostics** - view/export logs
- **Help > Upload Diagnostics** or **Ctrl-Alt-Q** - send logs to support

## Gotchas

- **Error 200** - contract specification issue (e.g. an invalid symbol); check the security identifier. (From the RTD lesson, **Error 321** means a bad generic tick list.)
- Historical data respects market hours: requesting bars near a market close, or across days the market was shut, can return fewer bars than expected - not necessarily a bug.
- IBKR API support can review logs and troubleshoot, but cannot provide programming assistance or diagnose local operating-system issues.
- Escalation path: contact IBKR Client Services with the exported diagnostic files attached.

## Related

- Previous: [[advanced-tws-dde-functionality]]
- Logging settings build on [[installing-configuring-tws-for-the-api]]
- (Last lesson of the course.)

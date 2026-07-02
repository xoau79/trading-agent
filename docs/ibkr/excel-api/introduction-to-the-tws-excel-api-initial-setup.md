---
title: Introduction to the TWS Excel API & Initial Setup
source: https://www.interactivebrokers.com/campus/trading-lessons/introduction-to-the-tws-excel-api-initial-setup/
type: reference
course: excel-and-the-tws-api
date_added: 2026-06-13
tags: [ibkr-api, tws-api, excel-api, api-configuration, windows-only]
---

# Introduction to the TWS Excel API & Initial Setup

## Concepts

- The TWS Excel API lets Microsoft Excel connect to IBKR's trading platform to pull market data, place orders, and read account/portfolio info directly in spreadsheet cells. As with the Python TWS API, Excel never talks to IBKR's servers directly - it talks to TWS or IB Gateway running locally, so a host program must be open and configured first.
- Three integration methods, each covered in its own lesson:
  - **RTD (RealTimeData)** - Excel's native real-time streaming function; TWS/IB Gateway acts as the RTD server. See [[using-realtimedata-rtd-server-for-excel]].
  - **DDE (Dynamic Data Exchange)** - a legacy Microsoft inter-process protocol; the modern version uses a Java socket bridge. See [[the-dynamic-data-exchange-dde-in-excel-using-a-sample-spreadsheet]].
  - **ActiveX** - a COM wrapper (TWSLib) giving programmatic control via VBA. See [[activex-in-excel-with-a-tws-sample-spreadsheet]].
- **Windows only.** Not compatible with macOS. Requires a Java Runtime Environment (JRE), desktop Microsoft Excel (not the web version), and TWS or IB Gateway installed.

### Sample files (installed on the OS drive, usually C:)

| Folder | Contents |
|--------|----------|
| `samples/Excel/` | DDE, ActiveX, and RTD sample spreadsheets |
| `samples/DdeSocketBridge/` | Batch file that runs the DDE socket bridge |
| `tests/` | `TwsLib.dll` - the library the ActiveX sample uses |
| `source/` | Files for building custom API applications |

### Configuring TWS for the API

1. Launch Trader Workstation.
2. Menu: **Edit > Global Configuration > API > Settings**.
3. Check **"Enable ActiveX and Socket Clients"**.
4. Default socket port is **7496** (the sample spreadsheets expect this).
5. Click **Apply**, then **OK**.

Download the API from the IBKR site under **Trading > APIs > Download and Resources** (Stable or Latest).

## Code examples

None - setup is done in the TWS GUI. The only fixed value to remember is the default API port **7496**, which must match the port the sample spreadsheets and your code use.

## Gotchas

- TWS or IB Gateway must stay open the whole time Excel is connected.
- Install the API on the OS drive (C:) or there may be issues finding the sample files and DLLs.
- **IBKR Lite** accounts have restricted API access - an upgrade to **IBKR Pro** is required for API functionality.
- RTD quote-type strings are case-sensitive (e.g. "Last" is not the same as "last").
- The ActiveX sample needs `TwsLib.dll` from the `tests/` folder.
- Version notes: the API supports JDK 17+ (as of TWS v10.34+); the DdeSocketBridge is compiled with Java major version 52, so a current JRE is required.

## Related

- Next: [[using-realtimedata-rtd-server-for-excel]]
- Same API settings as the Python course's [[installing-configuring-tws-for-the-api]]
- (First lesson of the course.)

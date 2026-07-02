---
title: TWS Python API Market Parameters and Scanners
source: https://www.interactivebrokers.com/campus/trading-lessons/tws-python-api-market-parameters-and-scanners/
type: reference
course: python-tws-api
date_added: 2026-06-13
tags: [ibkr-api, tws-api, market-scanners, screening, filters]
---

# TWS Python API Market Parameters and Scanners

## Concepts

- **Market scanners** return ranked lists of securities matching criteria - the API version of TWS's Mosaic Market Scanner (e.g. "top % gainers on US majors with volume above X").
- Two-step workflow:
  1. `reqScannerParameters()` returns a ~2MB XML file listing every valid instrument code (STK, ...), location code ("STK.US.MAJOR", "STK.NASDAQ"), filter (volumeAbove, priceAbove, marketCapBelow...), and scan code ("TOP_PERC_GAIN", "MOST_ACTIVE"...). Write it to a file - it is too big for the terminal.
  2. `reqScannerSubscription(reqId, sub, scan_options, filter_options)` with a ScannerSubscription object runs the actual scan; results arrive in the `scannerData` callback ranked 0-49.
- Results cap at 50 items regardless of matches.

## Code examples

Step 1 - dump available parameters to XML:

```python
from ibapi.client import *
from ibapi.wrapper import *

port = 7497

class TestApp(EClient, EWrapper):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId: int):
        self.reqScannerParameters()

    def scannerParameters(self, xml):
        dir = "C:\\IBKR\\TWS API\\samples\\Python\\Testbed\\Traders Academy\\scanner.xml"
        open(dir, 'w').write(xml)
        print("Scanner parameters received!")

app = TestApp()
app.connect("127.0.0.1", port, 1001)
app.run()
```

Step 2 - run a scan:

```python
from ibapi.client import *
from ibapi.wrapper import *
from ibapi.tag_value import *

port = 7497

class TestApp(EClient, EWrapper):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId: int):
        sub = ScannerSubscription()
        sub.instrument = "STK"
        sub.locationCode = "STK.US.MAJOR"
        sub.scanCode = "TOP_OPEN_PERC_GAIN"

        scan_options = []
        filter_options = [
            TagValue("volumeAbove","10000"),
            TagValue("marketCapBelow1e6", "1000"),
            TagValue("priceAbove", '1')
        ]

        self.reqScannerSubscription(orderId, sub, scan_options, filter_options)

    def scannerData(self, reqId, rank, contractDetails, distance, benchmark, projection, legsStr):
        print(f"scannerData. reqId: {reqId}, rank: {rank}, contractDetails: {contractDetails}, distance: {distance}, benchmark: {benchmark}, projection: {projection}, legsStr: {legsStr}.")

    def scannerDataEnd(self, reqId):
        print("ScannerDataEnd!")
        self.cancelScannerSubscription(reqId)
        self.disconnect()

app = TestApp()
app.connect("127.0.0.1", port, 1001)
app.run()
```

## Gotchas

- **Always cancel**: skipping `cancelScannerSubscription()` causes "duplicate scanner id" errors on later requests.
- "TOP_OPEN_PERC_GAIN" only works during regular trading hours - error 165 ("no items retrieved") outside them; use "TOP_PERC_GAIN" instead.
- Not every TWS GUI filter is a valid API filter - check the downloaded XML for what is actually supported.
- Unrealistic filter values (e.g. earnings above $100/share) silently return nothing.
- Optional fields like legsStr may be absent depending on scanner type.

## Related

- Previous: [[python-account-portfolio]]
- Next: [[tws-python-api-concurrency-example]] (uses a scanner to pick symbols)
- **Cross-platform equivalent:**
  - [[market-scanners]] (Web API / Client Portal API)

---
title: Market Scanners (Client Portal API)
source: https://www.interactivebrokers.com/campus/trading-lessons/market-scanners/
type: reference
course: web-api
date_added: 2026-06-13
tags: [client-portal-api, market-scanners, screener, rest-api, filters]
---

# Market Scanners (Client Portal API)

## Concepts

- **Scanner parameters**: `GET /iserver/scanner/params` returns a large XML document listing every valid location tree, scan type, and filter code. You read this to find the exact strings for `location`, `type`, and filter `code`.
- **Run a scan**: `POST /iserver/scanner/run` with a JSON body; returns up to 50 matching contracts with basic info (symbol, conId, company name, exchange).
- Scan body has four main fields: `instrument` (e.g. `"STK"`), `location` (e.g. `"STK.US.MAJOR"`), `type` (scan algorithm, e.g. `"TOP_PERC_GAIN"`), and `filter` (optional array of `{code, value}` objects).
- Filters combine: e.g. `priceAbove` + `priceBelow` to bound a price range.

## Code examples

Dump scanner params to a file - `GET /iserver/scanner/params`:

```python
import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def scanParams():
    base_url = "https://localhost:5000/v1/api/"
    endpoint = "iserver/scanner/params"
    params_req = requests.get(url=base_url+endpoint, verify=False)
    params_json = json.dumps(params_req.json(), indent=2)
    paramFiles = open("./scannerParams.xml", "w")
    for i in params_json:
        paramFiles.write(i)
    paramFiles.close()
    print(params_req.status_code)

if __name__ == "__main__":
    scanParams()
```

Run a scan - `POST /iserver/scanner/run` with instrument/location/type/filter:

```python
import requests
import urllib3
import json
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def reqIserverScanner():
    base_url = "https://localhost:5000/v1/api/"
    endpoint = "iserver/scanner/run"
    scan_body = {
        "instrument": "STK",
        "location": "STK.US.MAJOR",
        "type": "TOP_PERC_GAIN",
        "filter": [
            {"code":"priceAbove", "value":101},
            {"code":"priceBelow", "value":110}
        ]
    }
    scan_req = requests.post(url=base_url+endpoint, verify=False, json=scan_body)
    scan_json = json.dumps(scan_req.json(), indent=2)
    print(scan_req.status_code)
    print(scan_json)

if __name__ == "__main__":
    reqIserverScanner()
```

## Gotchas

- Results carry only basic contract fields - pull live quotes for each hit with a separate `/iserver/marketdata/snapshot` call ([[requesting-market-data]]).
- Over-tight filters return zero results; loosen the range if nothing matches.
- Max 50 results per scan.
- Valid `location`, `type`, and filter `code` values differ by instrument class - read them out of the `scanner/params` XML rather than guessing.

## Related

- Previous: [[account-management]]
- Next lesson: [[websockets]]
- TWS-side equivalent: [[tws-python-api-market-parameters-and-scanners]]

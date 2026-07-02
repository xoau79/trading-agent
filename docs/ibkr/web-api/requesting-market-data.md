---
title: Requesting Market Data
source: https://www.interactivebrokers.com/campus/trading-lessons/requesting-market-data/
type: reference
course: web-api
date_added: 2026-06-13
tags: [client-portal-api, market-data, snapshot, historical-data, field-codes]
---

# Requesting Market Data

## Concepts

- Live snapshots come from `GET /iserver/marketdata/snapshot`, taking `conids` (one or more, comma-separated) and `fields` (numeric field codes) as URL params.
- **Two-call pattern**: the first call usually returns only the conid and "instantiates the market data stream"; call again to get the actual values. Calculated fields (e.g. option Greeks) can take a few requests or seconds to populate, especially on thin instruments.
- Common field codes: **31** = last price, **55** = symbol, **84** = bid, **86** = ask.
- Historical bars come from a separate endpoint, `GET /hmds/history` - single conid only, with `period`, `bar`, `outsideRth`, and `barType` params.

## Code examples

Live snapshot - `GET /iserver/marketdata/snapshot?conids=...&fields=...`:

```python
import requests
import json

# Disable SSL Warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def marketSnapshot():
    base_url = "https://localhost:5000/v1/api/"
    endpoint = "iserver/marketdata/snapshot"

    conid="conids=265598,8314"
    fields="fields=31,55,84,86"

    params = "&".join([conid, fields])
    request_url = "".join([base_url, endpoint, "?", params])

    md_req = requests.get(url=request_url, verify=False)
    md_json = json.dumps(md_req.json(), indent=2)

    print(md_req)
    print(md_json)

if __name__ == "__main__":
    marketSnapshot()
```

Resulting URL:

```
https://localhost:5000/v1/api/iserver/marketdata/snapshot?conids=265598,8314&fields=31,55,84,86
```

Historical bars - `GET /hmds/history` (one conid):

```python
import requests
import json

# Disable SSL Warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def historicalData():
    base_url = "https://localhost:5000/v1/api/"
    endpoint = "hmds/history"

    conid="conid=265598"
    period="period=1w"
    bar="bar=1d"
    outsideRth="outsideRth=true"
    barType="barType=midpoint"

    params = "&".join([conid, period, bar, outsideRth, barType])
    request_url = "".join([base_url, endpoint, "?", params])

    hd_req = requests.get(url=request_url, verify=False)
    hd_json = json.dumps(hd_req.json(), indent=2)

    print(hd_req)
    print(hd_json)

if __name__ == "__main__":
    historicalData()
```

## Gotchas

- The snapshot endpoint accepts multiple conids; `/hmds/history` accepts only one.
- First snapshot call often returns nothing useful - expect to call again to get populated fields.
- `period` values: `Xmin, Xh, Xd, Xw, Xm, Xy` (e.g. `1w`, `1d`). `bar` values: `Xmin, Xh, Xd, Xw, Xm` (e.g. `1d`, `5min`).
- `outsideRth`: `true` includes pre/post hours, `false` (default) is regular hours only (9:30-16:00).
- `barType`: `last, midpoint, bid, ask, inventory`. Default `last` includes volume (field `v`); other bar types may not. Historical Greeks are not available via any bar type.
- The gateway must run on the same machine generating the API calls.

## Related

- Previous: [[contract-search]]
- Next lesson: [[placing-orders]]
- **Cross-platform equivalents:**
  - [[python-receiving-market-data]] (Python TWS API)
  - [[market-data-functions]], [[customizing-market-data-functions]] (R API / IBrokers)
- **Applied in strategy:** [[implementing-donchian-channel-trading-app]], [[running-the-donchian-channel]]

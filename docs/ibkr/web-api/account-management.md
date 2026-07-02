---
title: Account Management (Client Portal API)
source: https://www.interactivebrokers.com/campus/trading-lessons/account-management/
type: reference
course: web-api
date_added: 2026-06-13
tags: [client-portal-api, portfolio, positions, account-summary, rest-api]
---

# Account Management (Client Portal API)

## Concepts

- **Account summary**: `GET /portfolio/{accountId}/summary` for available funds, margin, and balances.
- **Positions (paginated)**: `GET /portfolio/{accountId}/positions/{page}` returns ~30 securities per page; the trailing index (0, 1, 2...) pages through holdings.
- **Single position**: `GET /portfolio/{accountId}/position/{conid}` fetches one holding directly and avoids the latency of building a full paginated list.
- Field suffixes in account data: `-c` = commodity-segment value, `-s` = securities-segment value, no suffix = whole-account total.
- Position value metrics: `mktPrice` (per-share value), `mktValue` (mktPrice x quantity), `avgPrice` (average entry per share), `avgCost` (avgPrice x position x multiplier - matters for derivatives like ES futures).

## Code examples

Account summary - `GET /portfolio/{accountId}/summary`:

```python
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def acctSum():

    base_url = "https://localhost:5000/v1/api/"
    endpoint = "portfolio/DU5240685/summary"

    sum_req = requests.get(url=base_url+endpoint, verify=False)
    sum_json = json.dumps(sum_req.json(), indent=2)

    print(sum_req.status_code)
    print(sum_json)

if __name__ == "__main__":
    acctSum()
```

Positions, page 0 - `GET /portfolio/{accountId}/positions/{page}`:

```python
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def acctPos():

    base_url = "https://localhost:5000/v1/api/"
    endpoint = "portfolio/DU5240685/positions/0"

    pos_req = requests.get(url=base_url+endpoint, verify=False)
    pos_json = json.dumps(pos_req.json(), indent=2)

    print(pos_req.status_code)
    print(pos_json)

if __name__ == "__main__":
    acctPos()
```

Single position by conid - `GET /portfolio/{accountId}/position/{conid}`:

```python
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def acctPosSingle():

    base_url = "https://localhost:5000/v1/api/"
    endpoint = "portfolio/DU5240685/position/265598"

    pos_req = requests.get(url=base_url+endpoint, verify=False)
    pos_json = json.dumps(pos_req.json(), indent=2)

    print(pos_req.status_code)
    print(pos_json)

if __name__ == "__main__":
    acctPosSingle()
```

## Gotchas

- A `401` means the session is not authenticated - confirm `/iserver/auth/status` returns `authenticated: true` first ([[launching-and-authenticating-the-gateway]]).
- The paginated positions endpoint can lag while full contract details are generated; query a single position by conid to bypass that delay when you already know the conid.
- Always print `status_code` to confirm `200` before trusting the body.

## Related

- Previous: [[complex-orders]]
- Next lesson: [[market-scanners]]
- **Cross-platform equivalent:**
  - [[python-account-portfolio]] (Python TWS API)
- **Integration:** The [[project-trading-agent]] will need this for live position tracking.

---
title: Contract Search
source: https://www.interactivebrokers.com/campus/trading-lessons/contract-search/
type: reference
course: web-api
date_added: 2026-06-13
tags: [client-portal-api, contract-search, conid, secdef, options]
---

# Contract Search

## Concepts

- Every IBKR security has a unique **conid** (contract ID) tied to a specific symbol, security type, and currency. Most other endpoints need a conid, so contract search is usually the first call.
- `iserver/secdef/search` finds contracts by symbol or company name and returns matching conids plus metadata. POST with a JSON body.
- **Derivatives need a strict call order**: `secdef/search` -> `secdef/strikes` -> `secdef/info` (or `/rules`). Calling out of order returns empty results.
- Request style differs by method: POST endpoints take a JSON body; GET endpoints take URL query parameters joined by `&` and prefixed with `?`.

## Code examples

Stock contract search - `POST .../iserver/secdef/search` with a JSON body:

```python
import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def contractSearch():
    base_url = "https://localhost:5000/v1/api/"
    endpoint = "iserver/secdef/search"
    json_body = {"symbol" : "ES", "secType": "STK", "name": False}
    contract_req = requests.post(url=base_url+endpoint, verify=False, json=json_body)
    contract_json = json.dumps(contract_req.json(), indent=2)
    print(contract_json)

if __name__ == "__main__":
    contractSearch()
```

Response excerpt - note each result carries the `conid` you reuse downstream:

```json
[
  {
    "conid": "272093",
    "companyHeader": "MICROSOFT CORP – NASDAQ",
    "companyName": "MICROSOFT CORP",
    "symbol": "MSFT",
    "description": "NASDAQ",
    "restricted": null,
    "sections": [{"secType": "STK"}]
  }
]
```

Futures/option contract details - `GET .../iserver/secdef/info`, params joined into the URL:

```python
def contractInfo():
    base_url = "https://localhost:5000/v1/api/"
    endpoint = "iserver/secdef/info"

    conid="conid=11004968"
    secType = "secType=FOP"
    month = "month=JUL23"
    exchange = "exchange=CME"
    strike = "strike=4800"
    right = "right=C"

    params = "&".join([conid, secType, month, exchange, strike, right])
    request_url = "".join([base_url, endpoint, "?", params])

    contract_req = requests.get(url=request_url, verify=False)
    contract_json = json.dumps(contract_req.json(), indent=2)

    print(contract_req)
    print(contract_json)

if __name__ == "__main__":
    contractInfo()
```

Option strike retrieval - `GET .../iserver/secdef/strikes` (must run before `info` for derivatives):

```python
def contractStrikes():
    base_url = "https://localhost:5000/v1/api/"
    endpoint = "iserver/secdef/strikes"

    conid = "conid=11004968"
    secType = "secType=FOP"
    month = "month=JUL23"
    exchange = "exchange=CME"

    params = "&".join([conid, secType, month, exchange])
    request_url = "".join([base_url, endpoint, "?", params])

    strikes_req = requests.get(url=request_url, verify=False)
    strikes_json = json.dumps(strikes_req.json(), indent=2)

    print(strikes_req)
    print(strikes_json)

if __name__ == "__main__":
    contractStrikes()
```

## Gotchas

- An "Init session first" error means you have not authenticated the gateway yet - see [[launching-and-authenticating-the-gateway]].
- Derivatives: skipping the `search` -> `strikes` -> `info` order returns empty results or "no contracts received".
- A stock symbol search returns many matches (different exchanges, CDRs, bonds). Filter locally on the `description` field for the exchange you want (e.g. "NASDAQ").
- Closing-only or thin symbols may only match when you pass `"name": true`.
- Standard options can omit `exchange` (defaults to SMART); futures options must pass it explicitly.
- `verify=False` is only OK against the local gateway.

## Related

- Previous: [[launching-and-authenticating-the-gateway]]
- Next lesson: [[requesting-market-data]]
- **Cross-platform equivalent:**
  - [[defining-contracts-in-the-tws-api]] (Python TWS API)
- **Used in:**
  - [[requesting-market-data]]
  - [[placing-orders]]
  - [[complex-orders]]

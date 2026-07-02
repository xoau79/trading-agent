---
title: Placing Orders (Client Portal API)
source: https://www.interactivebrokers.com/campus/trading-lessons/placing-orders/
type: reference
course: web-api
date_added: 2026-06-13
tags: [client-portal-api, order-placement, order-reply, rest-api, paper-trading]
---

# Placing Orders (Client Portal API)

## Concepts

- Submit orders with `POST /iserver/account/{accountId}/orders` and a JSON body whose `orders` key holds an array of order objects.
- Core order fields: `conid`, `orderType` (MKT, LMT, STP, ...), `side` (BUY/SELL), `quantity`, `tif` (DAY, GTC, ...), `price` (for LMT). `auxPrice` is the stop price for STP_LMT / TRAIL orders.
- **Order reply / confirmation**: certain orders (e.g. stop-order precautions) come back with a warning that must be confirmed by POSTing `{"confirmed": True}` to `/iserver/reply/{replyId}`. You may get a chain of reply ids - keep feeding each one back until the order goes through.
- HTTP 200 means accepted, not filled - a "presubmitted" status means the order has not been elected yet.

## Code examples

Place a stop order - `POST /iserver/account/{accountId}/orders`:

```python
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def orderRequest():

    base_url = "https://localhost:5000/v1/api/"
    endpoint = "iserver/account/DU5240685/orders"

    json_body = {
        "orders": [
            {
            "conid": 265598,
            "orderType": "STP",
            "price":185,
            "side": "SELL",
            "tif": "DAY",
            "quantity":10,
            }
        ]
    }
    order_req = requests.post(url = base_url+endpoint, verify=False, json=json_body)
    order_json = json.dumps(order_req.json(), indent=2)

    print(order_req.status_code)
    print(order_json)

if __name__ == "__main__":
    orderRequest()
```

Confirm a warning - POST the returned `replyId` back to `/iserver/reply/`:

```python
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def orderRequest():

    base_url = "https://localhost:5000/v1/api/"
    endpoint = "iserver/reply/"
    replyId = "7a45bf17-ae07-430f-9888-a4d79539aaa0"
    reply_url = "".join([base_url,endpoint,replyId])

    json_body = {
        "confirmed":True
    }
    order_req = requests.post(url = reply_url, verify=False, json=json_body)
    order_json = json.dumps(order_req.json(), indent=2)

    print(order_req.status_code)
    print(order_json)

if __name__ == "__main__":
    orderRequest()
```

## Gotchas

- Stop orders trigger a precaution warning that requires a reply before they execute.
- STP_LMT and TRAIL orders price the stop via `auxPrice`, not `price`.
- You can get more than one reply id back - loop the confirm step until the order is accepted.
- TWS/Gateway settings that suppress precaution prompts (price cap, 3%, etc.) may not suppress them over the REST API - expect to handle replies in code regardless.
- Test in a paper account first; the `accountId` in the path (e.g. `DU5240685`, a "DU" paper account) is your own.

## Related

- Previous: [[requesting-market-data]]
- Next lesson: [[request-modify-orders]]
- Complex/bracket orders: [[complex-orders]]
- **Cross-platform equivalents:**
  - [[python-placing-orders]] (Python TWS API)
  - [[order-functions]] (R API / IBrokers)
  - Excel: see [[introduction-to-the-tws-excel-api-initial-setup]] and [[advanced-tws-dde-functionality]]
- **Applied in strategy:** [[implementing-donchian-channel-trading-app]], [[running-the-donchian-channel]]

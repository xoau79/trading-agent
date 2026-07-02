---
title: Request & Modify Orders
source: https://www.interactivebrokers.com/campus/trading-lessons/request-modify-orders/
type: reference
course: web-api
date_added: 2026-06-13
tags: [client-portal-api, order-management, modify-order, cancel-order, rest-api]
---

# Request & Modify Orders

## Concepts

- **List live orders**: `GET /iserver/account/orders`. Two-call pattern - the first call instantiates the request, the second returns the populated orders list (which gives you each `orderId`).
- **Modify an order**: `POST /iserver/account/{accountId}/order/{orderId}` with a JSON body of the fields you want changed.
- **Cancel an order**: `DELETE /iserver/account/{accountId}/order/{orderId}`, no body. Returns 200 with a `msg` confirming the cancel was submitted.
- You need the `orderId` (from the orders list) before you can modify or cancel.

## Code examples

List live orders - `GET /iserver/account/orders`:

```python
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def orderRequest():
    base_url = "https://localhost:5000/v1/api/"
    endpoint = "iserver/account/orders"

    order_req = requests.get(url = base_url+endpoint, verify=False)
    order_json = json.dumps(order_req.json(), indent=2)

    print(order_req.status_code)
    print(order_json)

if __name__ == "__main__":
    orderRequest()
```

Modify an order - `POST /iserver/account/{accountId}/order/{orderId}`:

```python
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def orderModify():
    base_url = "https://localhost:5000/v1/api/"
    endpoint = "iserver/account/DU5240685/order/"
    order_id = "1010551026"
    modify_url = "".join([base_url, endpoint, order_id])

    json_body = {
        "conid":265598,
        "orderType":"STP",
        "price":187,
        "side": "SELL",
        "tif": "DAY",
        "quantity":10
    }
    order_req = requests.post(url = modify_url, verify=False, json=json_body)
    order_json = json.dumps(order_req.json(), indent=2)

    print(order_req.status_code)
    print(order_json)

if __name__ == "__main__":
    orderModify()
```

Cancel an order - `DELETE /iserver/account/{accountId}/order/{orderId}`:

```python
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def orderCancel():
    base_url = "https://localhost:5000/v1/api/"
    endpoint = "iserver/account/DU5240685/order/"
    order_id = "1010551026"
    cancel_url = "".join([base_url, endpoint, order_id])

    cancel_req = requests.delete(url = cancel_url, verify=False)
    cancel_json = json.dumps(cancel_req.json(), indent=2)

    print(cancel_req.status_code)
    print(cancel_json)

if __name__ == "__main__":
    orderCancel()
```

Endpoint summary:

| Action | Method | Endpoint |
| --- | --- | --- |
| List orders | GET | `/iserver/account/orders` |
| Modify order | POST | `/iserver/account/{accountId}/order/{orderId}` |
| Cancel order | DELETE | `/iserver/account/{accountId}/order/{orderId}` |

## Gotchas

- `/iserver/account/orders` needs a second call to return the full body - same two-call pattern as market data snapshots.
- A modify can itself trigger a precaution warning - be ready to confirm via the reply endpoint ([[placing-orders]]).
- After cancellation, the order's `conid` and `accountId` come back null, signalling it is closed.
- A 200 with a `msg` field on cancel means "submitted to cancel", not "already cancelled".

## Related

- Previous: [[placing-orders]]
- Next lesson: [[complex-orders]]

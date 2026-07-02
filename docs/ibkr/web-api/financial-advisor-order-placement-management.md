---
title: Financial Advisor - Order Placement & Management
source: https://www.interactivebrokers.com/campus/trading-lessons/financial-advisor-order-placement-management/
type: reference
course: web-api
date_added: 2026-06-13
tags: [client-portal-api, financial-advisor, allocation-groups, account-switching, order-placement]
---

# Financial Advisor - Order Placement & Management

## Concepts

- A Financial Advisor (FA) account manages multiple subaccounts via **allocation groups**. Groups must be created in Trader Workstation first - the API only references existing group names, it cannot create them.
- Orders can target either an allocation group (e.g. `video_group`, hits every subaccount) or a single subaccount id (e.g. `DU74649`).
- **Discover accounts**: `GET /iserver/accounts` lists all connected accounts, group names, and the default "All" group.
- **Switch active account/context**: `POST /iserver/account` with `{"acctId": ...}` before querying orders/positions, so subsequent calls return data for the right account.
- Portfolio endpoints (`/portfolio/{acctId}/positions/0`) only accept individual account ids, never group names (position quantities vary per subaccount).

## Code examples

List accounts and groups - `GET /iserver/accounts`:

```python
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def reqAccounts():
    base_url = "https://localhost:5000/v1/api/"
    endpoint = "iserver/accounts"

    accts_req = requests.get(url=base_url+endpoint, verify=False)
    accts_json = json.dumps(accts_req.json(), indent=2)

    print(accts_req)
    print(accts_json)

if __name__ == "__main__":
    reqAccounts()
```

Place an order for a subaccount (swap `DU74649` for a group name like `video_group` to hit the whole group) - `POST /iserver/account/{acctId}/orders`:

```python
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def orderRequest():
    base_url = "https://localhost:5000/v1/api/"
    endpoint = "iserver/account/DU74649/orders"

    json_body = {
        "orders": [{
            "conid": 265598,
            "orderType": "LMT",
            "price": 190,
            "side": "BUY",
            "tif": "DAY",
            "quantity": 100
        }]
    }

    order_req = requests.post(url=base_url+endpoint, verify=False, json=json_body)
    order_json = json.dumps(order_req.json(), indent=2)

    print(order_req.status_code)
    print(order_json)

if __name__ == "__main__":
    orderRequest()
```

Switch active account - `POST /iserver/account` with `{"acctId": ...}`:

```python
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def switchAccount():
    base_url = "https://localhost:5000/v1/api/"
    endpoint = "iserver/account"

    acct_body = {
        "acctId": "video_group"
    }

    md_req = requests.post(url=base_url+endpoint, verify=False, json=acct_body)
    md_json = json.dumps(md_req.json(), indent=2)

    print(md_req)
    print(md_json)

if __name__ == "__main__":
    switchAccount()
```

Then get live orders for the now-active account - `GET /iserver/account/orders`:

```python
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def orderRequest():
    base_url = "https://localhost:5000/v1/api/"
    endpoint = "iserver/account/orders"

    order_req = requests.get(url=base_url+endpoint, verify=False)
    order_json = json.dumps(order_req.json(), indent=2)

    print(order_req.status_code)
    print(order_json)

if __name__ == "__main__":
    orderRequest()
```

Positions for one subaccount (individual id only) - `GET /portfolio/{acctId}/positions/0`:

```python
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def acctPos():
    base_url = "https://localhost:5000/v1/api/"
    endpoint = "portfolio/DU74649/positions/0"

    pos_req = requests.get(url=base_url+endpoint, verify=False)
    pos_json = json.dumps(pos_req.json(), indent=2)

    print(pos_req.status_code)
    print(pos_json)

if __name__ == "__main__":
    acctPos()
```

## Gotchas

- Allocation groups must be built in TWS first; the API can't create or edit them.
- You must POST to `/iserver/account` to switch context before `/iserver/account/orders`, or you may get another account's orders.
- `/portfolio/{acctId}/positions/0` rejects group names - individual accounts only.
- Orders placed to a group vs. a subaccount are queried separately - switch context for each.
- Market data subscriptions are tied to the username, not the account, so switching accounts does not change active market data streams.

## Related

- Previous: [[websockets]]
- Course start: [[what-is-ibkrs-client-portal-api]]
- Order placement basics: [[placing-orders]]

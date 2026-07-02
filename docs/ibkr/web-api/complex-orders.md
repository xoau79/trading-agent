---
title: Complex Orders (Client Portal API)
source: https://www.interactivebrokers.com/campus/trading-lessons/complex-orders/
type: reference
course: web-api
date_added: 2026-06-13
tags: [client-portal-api, bracket-orders, combo-orders, conidex, order-placement]
---

# Complex Orders (Client Portal API)

## Concepts

- **Bracket orders**: a parent entry plus child profit-taking (PT) and stop-loss (SL) legs, all submitted in one request. Link them with `cOID` (customer order id) on each order and `parentId` on each child pointing at the parent's `cOID`. Because of this linkage, no need to fetch the parent's id first - all legs go in one call.
- Child PT and SL legs must use the **opposite side** from the parent (BUY parent -> SELL children).
- **Combo / spread orders**: trade multiple legs at once using a single `conidex` string instead of a `conid`. Format: `{spread_conid};;;{leg_conid1}/{ratio},{leg_conid2}/{ratio}` (exactly three semicolons). Ratio sign sets direction (+ = buy/long, - = sell/short); its value multiplies the order quantity.
- Combo `price` is the net debit/credit across legs and can be negative: `(leg1_price x ratio1) + (leg2_price x ratio2)`.
- Max **6 legs** per order, matching TWS.

## Code examples

Bracket order - parent + PT + SL in one `orders` array:

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
            "cOID": "AAPL_BRACKET_MMDD",
            "conid": 265598,
            "orderType": "MKT",
            "side": "BUY",
            "tif": "DAY",
            "quantity": 10
            },
            {
            "parentId":"AAPL_BRACKET_MMDD",
            "cOID": "AAPL_BRACKET_MMDD-PT",
            "conid": 265598,
            "orderType": "LMT",
            "price":190,
            "side": "SELL",
            "tif": "DAY",
            "quantity": 10
            },
            {
            "parentId":"AAPL_BRACKET_MMDD",
            "cOID": "AAPL_BRACKET_MMDD-SL",
            "conid": 265598,
            "orderType": "STP",
            "price":185,
            "side": "SELL",
            "tif": "DAY",
            "quantity": 10
            }
        ]
    }

    order_req = requests.post(url=base_url+endpoint, verify=False, json=json_body)
    order_json = json.dumps(order_req.json(), indent=2)

    print(order_req.status_code)
    print(order_json)

if __name__ == "__main__":
    orderRequest()
```

Combo order - one leg long, one short, via `conidex`:

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
            "conidex":"28812380;;;497222760/1,495512552/-1",
            "orderType": "LMT",
            "price": -50,
            "side": "BUY",
            "tif": "DAY",
            "quantity": 3
            }
        ]
    }

    order_req = requests.post(url=base_url+endpoint, verify=False, json=json_body)
    order_json = json.dumps(order_req.json(), indent=2)

    print(order_req.status_code)
    print(order_json)

if __name__ == "__main__":
    orderRequest()
```

Spread conid by currency (the `{spread_conid}` that leads a `conidex` string): USD `28812380`, EUR `58666491`, GBP `58666494`, JPY `61227069`, AUD `61227077`, CAD `61227082`, CHF `61227087`, HKD `61227072`, SGD `426116555`, KRW `136000424`, CNH `136000441`, INR `136000444`, MXN `136000449`, SEK `136000429`. Non-USD combos use the form `{spread_conid}@{exchange}`.

## Gotchas

- The `conidex` separator is exactly **three** semicolons - some transcripts wrongly show four.
- PT and SL legs must be the opposite side of the parent or the bracket is invalid.
- Combo prices can be negative - that is the net debit/credit, not an error.
- Complex orders can still trigger precaution warnings; confirm via the reply endpoint ([[placing-orders]]).
- More than 6 legs fails - split into multiple orders.

## Related

- Previous: [[request-modify-orders]]
- Next lesson: [[account-management]]
- **Cross-platform equivalents:**
  - [[python-complex-orders]] (Python TWS API)
- **Trading concepts:**
  - Bracket orders = automated version of the stop-loss discipline in [[2026-06-08-math-of-winning-in-trading]]
  - Risk management applies to all order structures

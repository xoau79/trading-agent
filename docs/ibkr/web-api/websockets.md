---
title: Websockets (Client Portal API)
source: https://www.interactivebrokers.com/campus/trading-lessons/websockets/
type: reference
course: web-api
date_added: 2026-06-13
tags: [client-portal-api, websockets, streaming-data, live-orders, real-time]
---

# Websockets (Client Portal API)

## Concepts

- For streaming (instead of polling REST), connect a WebSocket to `wss://localhost:5000/v1/api/ws`. The gateway must be running and authenticated; SSL verification is disabled with `sslopt={"cert_reqs":ssl.CERT_NONE}`.
- Subscription messages follow `TOPIC+[TARGET]+{PARAMETERS}`. The server sends `tic`/tickle heartbeats to keep the connection alive.
- **Market data**: subscribe with `smd+{conid}+{"fields":[...]}`, unsubscribe with `unsmd`. Fields here: `31` last, `84` bid, `86` ask.
- **Live orders**: subscribe with `sor+{}` to stream order status, executions, and fills for the authenticated account.
- Returned messages carry routing/identity fields like `topic`, `conid`/`conidex`, `serverId`, `_updated` (epoch), and `tickNum`.

## Code examples

Stream market data - `smd+{conid}+{"fields":[...]}`:

```python
import websocket
import time
import ssl

def on_message(ws, message):
    print(message)

def on_error(ws, error):
    print(error)

def on_close(ws):
    print("## CLOSED! ##")

def on_open(ws):
    print("Opened Connection")
    time.sleep(3)
    conids = ["265598", "8314"]

    for conid in conids:
        ws.send('smd+'+conid+'+{"fields":["31","84","86"]}')

if __name__ == "__main__":
    ws = websocket.WebSocketApp(
        url="wss://localhost:5000/v1/api/ws",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever(sslopt={"cert_reqs":ssl.CERT_NONE})
```

Stream live order updates - `sor+{}`:

```python
import websocket
import time
import ssl

def on_message(ws, message):
    print(message)

def on_error(ws, error):
    print(error)

def on_close(ws):
    print("## CLOSED! ##")

def on_open(ws):
    print("Opened Connection")
    time.sleep(3)
    ws.send('sor+{}')

if __name__ == "__main__":
    ws = websocket.WebSocketApp(
        url="wss://localhost:5000/v1/api/ws",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever(sslopt={"cert_reqs":ssl.CERT_NONE})
```

Exact subscription strings (quoting is significant):

```
smd+265598+{"fields":["31","84","86"]}
sor+{}
```

## Gotchas

- The subscription string mixes single and double quotes in a precise pattern - deviating causes silent failures with no response.
- Sending a subscription too early can fail; the lesson notes you may need to wait for the initial `sts` status message before subscribing (move `ws.send` out of `on_open` and trigger it from `on_message` after `sts`).
- Install the client first: `pip install websocket-client`.
- Each subscription consumes a market data line; default accounts have ~100 lines.
- Outside regular trading hours, data may be stale or infrequent. Long-running connections may need periodic re-auth / heartbeat acknowledgment.

## Related

- Previous: [[market-scanners]]
- Next lesson: [[financial-advisor-order-placement-management]]
- REST polling equivalent: [[requesting-market-data]]
- TWS-side concurrency: [[tws-python-api-concurrency-example]]

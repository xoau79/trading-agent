---
title: Essential Components of TWS API Programs
source: https://www.interactivebrokers.com/campus/trading-lessons/essential-components-of-tws-api-programs/
type: reference
course: python-tws-api
date_added: 2026-06-13
tags: [ibkr-api, tws-api, eclient-ewrapper, threading, event-driven, error-handling]
---

# Essential Components of TWS API Programs

## Concepts

- Every TWS API program is built from two classes that work as a pair:
  - **EClient** - outgoing: sends your requests to TWS or IB Gateway.
  - **EWrapper** - incoming: receives the answers TWS sends back.
- The pattern is asynchronous request-response: one request can trigger one or many callback responses, arriving whenever TWS is ready. You do not call a function and get a return value - you send a request, and later a method on your class gets called with the data.
- Your app class inherits from both: `class TestApp(EClient, EWrapper)`. You override EWrapper methods (like `currentTime` or `error`) to decide what happens when data arrives.
- **Threading**: `app.run()` is a message loop that processes incoming data forever. It runs on its own thread so the main thread can keep sending requests. The `time.sleep(1)` after starting the thread gives the connection a moment to finish before requests are sent.
- **Order IDs**: on connection TWS calls `nextValidId()` with the first usable ID. Every later request/order needs a unique increasing ID, handled with a small `nextId()` helper.
- The `error()` callback receives everything TWS flags - but not all of it is an error. Messages like "ERROR -1 2104" are just notifications that market data farm connections are OK.

## Code examples

Complete minimal program from the lesson:

```python
from ibapi.client import *
from ibapi.wrapper import *
import time
import threading

class TestApp(EClient, EWrapper):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId):
        self.orderId = orderId

    def nextId(self):
        self.orderId += 1
        return self.orderId

    def currentTime(self, time):
        print(time)

    def error(self, reqId, errorCode, errorString, advancedOrderReject=""):
        print(f"reqId: {reqId}, errorCode: {errorCode}, errorString: {errorString}, orderReject: {advancedOrderReject}")

app = TestApp()
app.connect("127.0.0.1", 7497, 0)
threading.Thread(target=app.run).start()
time.sleep(1)

# for i in range(0,5):
#   print(app.nextId())
app.reqCurrentTime()
```

`connect()` arguments: host, port (7496/7497 TWS live/paper, 4001/4002 IB Gateway live/paper), clientId.

Updated error() signature required from API v10.33+ (errorTime parameter added Dec 2024):

```python
def error(self, reqId, errorTime, errorCode, errorMsg, advancedOrderRejectJson=""):
    print(f"reqId: {reqId}, errorCode: {errorCode}, errorString = {errorMsg}")
```

## Gotchas

- **TypeError "takes 5 positional arguments but 6 were given"** on v10.33+: use the updated error() signature above.
- **AttributeError "no attribute orderId"**: you called `nextId()` before TWS delivered the first ID. Increase the sleep to 3+ seconds or call `app.nextValidId(-1)` to force it.
- **Error 326 "client ID already in use"**: another API connection (Excel, NinjaTrader, second script) holds that clientId - pass a different third argument to connect().

## Related

- Previous: [[accessing-the-tws-python-api-source-code]]
- Next: [[defining-contracts-in-the-tws-api]]
- Same scaffold reused in all later lessons of this course.

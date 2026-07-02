---
title: Implementing the Donchian Channel Trading App
source: https://www.interactivebrokers.com/campus/trading-lessons/implementing-donchian-channel-trading-app/
type: reference
course: python-pandas-donchian-channels
date_added: 2026-06-13
tags: [ibkr-api, tws-api, donchian-channels, historical-data, order-placement]
---

# Implementing the Donchian Channel Trading App

## Concepts

- The strategy lives in a `TradingApp` class that **inherits from both `EClient` and `EWrapper`** - the same dual-inheritance pattern as the core TWS API course. `EClient` sends requests out; `EWrapper` receives callbacks in.
- **State it keeps:** a `data` dict mapping each request ID to a pandas DataFrame of bars, and `nextOrderId` (the next valid order ID, filled in by the API on connect).
- **Getting the first order ID:** `nextValidId()` fires once on connection; the app stores it so orders can be placed later. You must wait for this before placing any order.
- **Requesting history:** `get_historical_data()` calls `reqHistoricalData()` for **1 day of 1-minute MIDPOINT bars** (`durationStr="1 D"`, `barSizeSetting="1 min"`, `whatToShow="MIDPOINT"`), then sleeps 5 seconds to let bars stream in.
- **Receiving history:** the `historicalData()` callback writes each bar's high/low/close into the DataFrame, indexed by timestamp (`bar.date` is a Unix epoch, converted with `pd.to_datetime(..., unit="s")`), and casts everything to float.
- **Defining the instrument:** `get_contract()` builds a US stock contract (`secType="STK"`, `exchange="SMART"`, `currency="USD"`) for any ticker.
- **Placing a trade:** `place_order()` builds an `Order` (action, type, quantity), submits it with the stored `nextOrderId`, then increments that ID for the next order.
- This lesson defines the machinery; the actual Donchian computation and breakout loop are wired together in [[running-the-donchian-channel]].
- **Underlying API concepts:** market data via [[python-receiving-market-data]], contracts via [[defining-contracts-in-the-tws-api]], orders via [[python-placing-orders]].

## Code examples

The complete `TradingApp` class as built in this lesson (verbatim; long parameter docstrings condensed to one line, executable code unchanged):

```python
import time
import threading
from datetime import datetime
from typing import Dict, Optional
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.common import BarData


class TradingApp(EClient, EWrapper):
    """A trading app that interacts with the IB API by extending EClient and EWrapper:
    handles the connection, historical-data requests, and order placement."""

    def __init__(self) -> None:
        EClient.__init__(self, self)
        self.data: Dict[int, pd.DataFrame] = {}
        self.nextOrderId: Optional[int] = None

    def error(self, reqId: int, errorCode: int, errorString: str, advanced: any) -> None:
        """Handles errors received from the IB API."""
        print(f"Error: {reqId}, {errorCode}, {errorString}")

    def nextValidId(self, orderId: int) -> None:
        """Receives and stores the next valid order ID for placing trades."""
        super().nextValidId(orderId)
        self.nextOrderId = orderId

    def get_historical_data(self, reqId: int, contract: Contract) -> pd.DataFrame:
        """Requests and retrieves historical market data for a given contract."""
        self.data[reqId] = pd.DataFrame(columns=["time", "high", "low", "close"])
        self.data[reqId].set_index("time", inplace=True)
        self.reqHistoricalData(
            reqId=reqId,
            contract=contract,
            endDateTime="",
            durationStr="1 D",
            barSizeSetting="1 min",
            whatToShow="MIDPOINT",
            useRTH=0,
            formatDate=2,
            keepUpToDate=False,
            chartOptions=[],
        )
        time.sleep(5)
        return self.data[reqId]

    def historicalData(self, reqId: int, bar: BarData) -> None:
        """Processes and stores historical bars received from IB callbacks."""
        # Get the current DataFrame at the request ID
        df = self.data[reqId]

        # Set the current bar data into the DataFrame
        df.loc[
            pd.to_datetime(bar.date, unit="s"),
            ["high", "low", "close"]
        ] = [bar.high, bar.low, bar.close]

        # Cast data to floats
        df = df.astype(float)

        # Assign the DataFrame at the request ID
        self.data[reqId] = df

    @staticmethod
    def get_contract(symbol: str) -> Contract:
        """Creates and returns a US stock contract for the given symbol."""
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract

    def place_order(self, contract: Contract, action: str, order_type: str, quantity: int) -> None:
        """Places an order with the given contract, action, order type, and quantity."""
        order = Order()
        order.action = action
        order.orderType = order_type
        order.totalQuantity = quantity

        self.placeOrder(self.nextOrderId, contract, order)
        self.nextOrderId += 1
        print("Buy order placed")
```
The full strategy class: connection state, error handler, order-ID capture, a blocking historical-data request, the bar-storing callback, a stock-contract factory, and a market/limit order submitter.

## Gotchas

- **Blocking `time.sleep(5)`:** `get_historical_data()` pauses 5 seconds for bars to arrive. If bars are slow you can miss data; the lesson itself flags that an async approach is better.
- **`EClient.__init__(self, self)`** passes `self` twice on purpose - once as the client, once as the wrapper (callback receiver). Required by the API's event model.
- **Wait for `nextValidId` before ordering** - placing an order while `nextOrderId` is still `None` triggers "Invalid order ID" errors.
- **Unique `reqId` per request** - reusing an ID overwrites the DataFrame already stored under it.
- **Contract fields are mandatory** - missing `secType`/`exchange`/`currency` gets the request rejected.
- **Bar timestamps** arrive as Unix epochs; convert with `pd.to_datetime(bar.date, unit="s")` or you get parse errors.
- **No connection code here** - this lesson omits `connect()`/host/port/clientId. Those appear in [[running-the-donchian-channel]] (localhost `127.0.0.1`, port `7497` for paper).
- Minor: `place_order()` always prints "Buy order placed" even for sells - cosmetic only.

## Related

- Previous: [[introduction-to-donchian-channel]]
- Next: [[running-the-donchian-channel]]

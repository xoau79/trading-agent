---
title: Accessing Portfolio Data and Account Information
source: https://www.interactivebrokers.com/campus/trading-lessons/python-account-portfolio/
type: reference
course: python-tws-api
date_added: 2026-06-13
tags: [ibkr-api, tws-api, portfolio-data, account-data, positions, pnl]
---

# Accessing Portfolio Data and Account Information

## Concepts

- **No historical portfolio data by design** - TWS is a trading app, so the API only serves current state. If you want history, your program must record it (this is what the trading agent's own logs are for).
- Everything follows subscribe-and-publish: subscribing returns one complete dataset, then only changes stream in (on trades, or when account values change within a 3-minute window).
- Choosing the right request:
  - `reqAccountUpdates` - positions AND account values for a single account. Simplest for individual accounts.
  - `reqAccountSummary` - account values across multiple accounts at once; the more common multi-account choice.
  - `reqPositions` - position updates for up to 50 sub-accounts (advisor structures).
  - `reqPositionsMulti` / `reqAccountSummaryMulti` - single sub-account or model portfolio when there are 50+ subs.
- Callbacks: `updateAccountValue` (one call per key: cash, margin, net liquidity), `updatePortfolio` (one call per position: size, market value, average cost, unrealized PnL total, realized PnL today), `updateAccountTime`, `accountDownloadEnd` (fires once after the initial full batch only).
- Cash positions come in two flavors: virtual forex pairs (EUR.USD - bookkeeping markers) vs real single-currency balances ($20,000 USD) in account info.

## Code examples

Complete lesson program (note the Timer pattern to auto-stop after 5 seconds):

```python
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from threading import Timer

class TestApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

    def error(self, reqId, errorCode, errorString, advancedOrderReject=""):
        print("Error: ", reqId, " ", errorCode, " ", errorString)

    def nextValidId(self, orderId):
        self.start()

    def updatePortfolio(self, contract: Contract, position: float, marketPrice: float, marketValue: float,
                        averageCost: float, unrealizedPNL: float, realizedPNL: float, accountName: str):
        print("UpdatePortfolio.", "Symbol:", contract.symbol, "SecType:", contract.secType, "Exchange:", contract.exchange,
              "Position:", position, "MarketPrice:", marketPrice, "MarketValue:", marketValue, "AverageCost:", averageCost,
              "UnrealizedPNL:", unrealizedPNL, "RealizedPNL:", realizedPNL, "AccountName:", accountName)

    def updateAccountValue(self, key: str, val: str, currency: str, accountName: str):
        print("UpdateAccountValue. Key:", key, "Value:", val, "Currency:", currency, "AccountName:", accountName)

    def updateAccountTime(self, timeStamp: str):
        print("UpdateAccountTime. Time:", timeStamp)

    def accountDownloadEnd(self, accountName: str):
        print("AccountDownloadEnd. Account:", accountName)

    def start(self):
        # Account number can be omitted when using reqAccountUpdates with single account structure
        self.reqAccountUpdates(True, "")

    def stop(self):
        self.reqAccountUpdates(False, "")
        self.done = True
        self.disconnect()

def main():
    app = TestApp()
    app.connect("127.0.0.1", 7497, 0)

    Timer(5, app.stop).start()
    app.run()

if __name__ == "__main__":
    main()
```

## Gotchas

- `accountDownloadEnd` fires only after the first complete batch - never on later updates. Do not wait for it as an "update finished" signal.
- After the initial batch, only CHANGED positions/values arrive - keep your own state dictionary and update it, do not expect full snapshots.
- `reqAccountUpdates` cannot watch multiple sub-accounts at once - use reqAccountSummary/reqPositions for that.

## Related

- Previous: [[python-complex-orders]]
- Next: [[tws-python-api-market-parameters-and-scanners]]
- **Cross-platform equivalent:**
  - [[account-management]] (Web API / Client Portal API)
- **Integration:** The [[project-trading-agent]] will need this for live position tracking instead of its simulated portfolio file.

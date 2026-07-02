---
title: Running the Donchian Channel
source: https://www.interactivebrokers.com/campus/trading-lessons/running-the-donchian-channel/
type: reference
course: python-pandas-donchian-channels
date_added: 2026-06-13
tags: [ibkr-api, tws-api, donchian-channels, breakout, paper-trading]
---

# Running the Donchian Channel

## Concepts

- This final lesson wires the pieces together and runs the strategy live against a **paper** account.
- **Connect on a background thread:** the `TradingApp` connects to `127.0.0.1:7497` (paper) with `clientId=5`, then `app.run()` is started on a daemon thread so the main script can keep executing. A small loop waits until `nextOrderId` is an `int` before declaring "connected".
- **Fetch + compute:** request 1 day of 1-minute NVDA bars (request ID 99), then call `donchian_channel(data, period=30)` (the function from [[introduction-to-donchian-channel]]).
- **The trading loop:** repeatedly re-pull data, skip if fewer than `period` bars exist, recompute the channel, then compare the **latest close** to the latest `upper`/`lower` bands:
  - `last_price >= upper` -> breakout up -> market **BUY** 10 shares.
  - `last_price <= lower` -> breakout down -> market **SELL** 10 shares.
- It is a bare breakout executor: touch the band, send a market order for a fixed 10 shares.
- **Position sizing:** this lesson uses fixed 10-share orders; see [[2026-06-08-math-of-winning-in-trading]] for why position sizing matters.

## Code examples

Connect and confirm the session (verbatim):

```python
# Create an instance of our trading app
app = TradingApp()

# Connect the trading app to our paper trading account
# on port 7497 using client id 5
app.connect("127.0.0.1", 7497, clientId=5)

# Start the app on a thread so code can continue to execute
threading.Thread(target=app.run, daemon=True).start()

# Do a simple check to confirm we're connected
while True:
    if isinstance(app.nextOrderId, int):
        print("connected")
        break
    else:
        print("waiting for connection")
        time.sleep(1)
```
Instantiates the app, connects to the paper gateway on a daemon thread, and blocks until the API hands back a valid order ID.

Pull data and compute the channel once (verbatim):

```python
# Define a contract for use with the app
nvda = TradingApp.get_contract("NVDA")

# Request 1 minute bars over the last trading day
# for the contract we defined above. Use the
# (arbitrary) request ID 99.
data = app.get_historical_data(99, nvda)
data.tail()

# Using the acquired data, compute the Donchian
# channels over a 30 minute window.
donchian = donchian_channel(data, period=30)
donchian.tail()
```
Builds the NVDA contract, fetches a day of 1-minute bars, and computes a 30-period Donchian Channel.

The live breakout loop (verbatim):

```python
period = 30

while True:
    
    # Ask IB for data for our contract
    print("Getting data for contract...")
    data = app.get_historical_data(99, nvda)

    # We don't have enough data to compute the donchian
    # channel for period so skip the rest of the code
    if len(data) < period:
        print(f"There are only {len(data)} bars of data, skipping...")
        continue

    # Compute the donchian channel
    print("Computing the Donchian Channel...")
    donchian = donchian_channel(data, period=period)

    # Get the last traded price we have
    last_price = data.iloc[-1].close

    # Get the last channel values we have
    upper, lower = donchian[["upper", "lower"]].iloc[-1]

    print(f"Check if last price {last_price} is outside the channels {upper} and {lower}")
    
    # Breakout to the upside
    if last_price >= upper:
        print("Breakout dedected, going long...")
        # Enter a buy market order for 10 shares
        app.place_order(nvda, "BUY", "MKT", 10)
    
    # Breakout to the downside
    elif last_price <= lower:
        print("Breakout dedected, going long...")
        # Enter a sell market order for 10 shares
        app.place_order(nvda, "SELL", "MKT", 10)

app.disconnect()
```
Continuously re-fetches data, skips until there are `period` bars, recomputes the channel, and fires a 10-share market order whenever the last price touches the upper (buy) or lower (sell) band.

## Gotchas

- **TWS or IB Gateway must already be running and logged in** to a **paper** account before you launch the script; port `7497` is the paper port.
- **No breakout confirmation:** orders fire the instant price touches a band, so a single noisy tick can trigger a false entry.
- **No position or risk management:** the loop never checks existing positions, so it can stack repeated 10-share orders in the same direction - it is a teaching skeleton, not a safe live bot.
- **Tight request loop:** the loop re-requests history every iteration with no pause between cycles (only the internal `time.sleep(5)` in `get_historical_data`), which can bump into IBKR data rate limits.
- **`app.disconnect()` is unreachable** - it sits after `while True:`, which never exits on its own; stop the script manually.
- Source typos, left verbatim: "dedected" (should be "detected"), and the **SELL** branch prints "going long" (copy-paste slip) even though it sells.

## Related

- Previous: [[implementing-donchian-channel-trading-app]]
- **Strategy breadcrumb:** [[introduction-to-pyquant-and-python-pandas]] → [[introduction-to-donchian-channel]] → [[implementing-donchian-channel-trading-app]] → this lesson
- **Underlying API lessons:**
  - [[python-receiving-market-data]] (how to fetch bars)
  - [[python-placing-orders]] (how to send orders)
  - [[defining-contracts-in-the-tws-api]] (contract setup)
- **Trading concepts:**
  - [[2026-06-08-math-of-winning-in-trading]] (expectancy, position sizing, risk)
  - [[2026-06-09-stop-trading-like-an-idiot]] (breakout strategies, convex payoffs)
- This is the last lesson; the course closes with a final quiz ("Python Pandas - Donchian Channels Final"), which has no note.

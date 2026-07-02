---
title: Installing & Configuring TWS for the API
source: https://www.interactivebrokers.com/campus/trading-lessons/installing-configuring-tws-for-the-api/
type: reference
course: python-tws-api
date_added: 2026-06-13
tags: [ibkr-api, tws-api, api-configuration, paper-trading, socket-ports]
---

# Installing & Configuring TWS for the API

## Concepts

- Two host programs can serve the API: **TWS** (full trading platform with charts and GUI) and **IB Gateway** (lightweight, API-only, fewer resources). They are functionally identical for API purposes and are released in matching versions.
- Your Python program never talks to IBKR's servers directly - it talks to TWS or IB Gateway running on your machine, over a local socket. That is why TWS must be running and configured before any API code works.
- At login you choose live or paper account. Paper trading is the safe sandbox - use it for all development.

### The settings that matter (Global Configuration -> API -> Settings)

| Setting | Value | Why |
|---------|-------|-----|
| Enable ActiveX and Socket Clients | checked | Without it no API connection at all |
| Read-Only API | unchecked | Enabled by default; blocks all order placement until unchecked |
| Socket port (TWS) | 7496 live / 7497 paper | Must match the port in your code's connect() call |
| Socket port (IB Gateway) | 4001 live / 4002 paper | Same rule |

- For troubleshooting, enable "Create API Message Log" and set Logging Level to "Detail" to record all API traffic.
- Click Apply, then OK to save.

## Code examples

None in this lesson - configuration is done in the TWS GUI. Linux install commands from the lesson:

```bash
chmod u+x tws-stable-standalone-linux.sh
sudo ./tws-stable-standalone-linux.sh
./Jts/1019/tws
```

(Version number in the launch path varies by release.)

## Gotchas

- Read-Only API being ON by default is the classic first-day trap: connection works, market data works, but every order silently fails until you uncheck it.
- The four port numbers (7496/7497/4001/4002) encode both which host program and live-vs-paper. Mismatched port between TWS settings and your code is the most common connection failure.
- Market data permissions: live and historical data need a funded account with subscriptions; the "Try the Demo" login gives limited delayed data.

## Related

- Previous: [[what-is-the-tws-api]]
- Next: [[accessing-the-tws-python-api-source-code]]

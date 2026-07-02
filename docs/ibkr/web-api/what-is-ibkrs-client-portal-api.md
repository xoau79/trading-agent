---
title: What is IBKR's Client Portal API?
source: https://www.interactivebrokers.com/campus/trading-lessons/what-is-ibkrs-client-portal-api/
type: reference
course: web-api
date_added: 2026-06-13
tags: [ibkr-api, client-portal-api, rest-api, api-gateway, algo-trading]
---

# What is IBKR's Client Portal API?

## Concepts

- The Client Portal API (CPAPI, also called the Web API) is a single RESTful API for trading, monitoring, and managing an IBKR account over the internet using standard HTTP requests (GET, POST, etc.).
- Key difference from the [[what-is-the-tws-api|TWS API]]: CPAPI talks to IBKR over HTTPS through a small local Java gateway, instead of a TCP socket connection into a running copy of Trader Workstation. Much lighter footprint - just the gateway plus a command prompt, no full desktop platform.
- Language-agnostic: any language that can make HTTP requests works (Python, C#, JavaScript, C++, ...). The course examples use Python 3 with the `requests` library.
- Younger codebase than the TWS API - it does not yet have full feature parity, but IBKR keeps adding endpoints.
- Authentication is gateway-based: you launch and log into a local gateway first, then all API calls go through it (covered next lesson).

## Code examples

None in this lesson - it is the conceptual intro (lesson 1 of 11).

## Reference URLs

- Latest gateway download: `https://download2.interactivebrokers.com/portal/clientportal.gw.zip`
- CPAPI docs: `https://interactivebrokers.github.io/cpwebapi/`

## Gotchas

- APIs are not available for IBKR Lite accounts - a standard account or above is required.
- Market data calls can return error 10089 ("Requested market data requires additional subscription") without the right market data subscriptions.
- Feature gaps vs. the TWS API are expected; an endpoint you want may simply not exist yet.

## Related

- Sibling intro: [[what-is-the-tws-api]]
- Next lesson: [[launching-and-authenticating-the-gateway]]

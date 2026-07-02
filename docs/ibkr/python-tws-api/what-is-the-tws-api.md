---
title: What is the TWS API?
source: https://www.interactivebrokers.com/campus/trading-lessons/what-is-the-tws-api/
type: reference
course: python-tws-api
date_added: 2026-06-13
tags: [ibkr-api, tws-api, algo-trading, trading-platforms, api-licensing]
---

# What is the TWS API?

## Concepts

- The TWS API is an open-source interface to Trader Workstation (TWS), IBKR's desktop trading platform. Your own program connects to a running copy of TWS and tells it what to do.
- Key mental model: the API does not add new abilities beyond what TWS itself can do - it lets external software automate actions TWS already supports: placing orders, reading account values, pulling portfolio data, receiving market data, and looking up instrument details.
- IBKR has three trading platforms: TWS (desktop, Java-based), Client Portal (web), and IBKR Mobile. External programs can connect through three routes: the TWS API, the Web API, or FIX/CTCI. This course covers the first.
- Supported languages: Python, Java, C#, C++. Source code is downloadable under a non-commercial license; commercial licenses exist on request.
- There is a large third-party ecosystem (100+ apps) built on this API, many listed on IBKR's Investors Marketplace.

## Code examples

None in this lesson - it is the conceptual intro (lesson 1 of 11).

## Gotchas

- Stated prerequisites for the course: Python 3.3+, intermediate Python, and familiarity with sockets and threading. The threading part matters - the API is event-driven and runs a network loop on its own thread.
- Live or historical market data requires a funded account with active market data subscriptions - a fresh paper account alone gets limited data.

## Related

- Next lesson: [[installing-configuring-tws-for-the-api]]
- API install: [[accessing-the-tws-python-api-source-code]]

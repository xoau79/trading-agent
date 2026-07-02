---
title: Introduction to PyQuant and Python Pandas
source: https://www.interactivebrokers.com/campus/trading-lessons/introduction-to-pyquant-and-python-pandas/
type: reference
course: python-pandas-donchian-channels
date_added: 2026-06-13
tags: [ibkr-api, pandas, pyquant, donchian-channels, algorithmic-trading]
---

# Introduction to PyQuant and Python Pandas

## Concepts

- This is the orientation lesson for the **Python Pandas - Donchian Channels** course. The course is authored by **PyQuant** (PyQuant News), a third party - the lesson is explicit that "This is a third-party open-source library. It is not associated, supported, or managed by Interactive Brokers."
- **PyQuant** is an open-source ecosystem of tools for quantitative trading and financial analysis - building blocks for algorithmic strategies.
- **pandas** is the Python library used throughout the course for handling market data and time-series analysis (rolling windows, DataFrames). IBKR notes it "cannot help or offer support with Pandas specifically" - it is an independent library.
- **Goal of the course:** build a small trading application that pulls price data through the IBKR API, computes the Donchian Channel indicator with pandas, and acts on breakouts.
- **Donchian Channel preview** - a trend-following indicator with three components, developed here over the next three lessons:
  - **Upper band** - the highest high over a lookback period.
  - **Lower band** - the lowest low over the same period.
  - **Middle line** - the average of the upper and lower bands.
- Traders use it to spot breakouts, confirm trends, mark support/resistance, set entries/exits, and place stops.

## Code examples

None - this lesson is orientation only. The first code appears in the next lesson, [[introduction-to-donchian-channel]].

## Gotchas

- pandas and PyQuant are third-party; IBKR does not support or endorse them, and provides this material for technical demonstration only - not investment advice.
- "Placing trades in a paper account is recommended before any live trading." This carries through the whole course.

## Related

- Next: [[introduction-to-donchian-channel]]
- **Complete strategy pipeline:**
  - [[introduction-to-pyquant-and-python-pandas]] (this lesson - orientation)
  - [[introduction-to-donchian-channel]] (the indicator)
  - [[implementing-donchian-channel-trading-app]] (connecting API + indicator)
  - [[running-the-donchian-channel]] (live execution)
- **Underlying API lessons:**
  - [[python-receiving-market-data]] (fetching bars)
  - [[python-placing-orders]] (sending orders)
- (First lesson of the course.)

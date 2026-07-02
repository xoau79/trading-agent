---
title: Introduction to the Donchian Channel
source: https://www.interactivebrokers.com/campus/trading-lessons/introduction-to-donchian-channel/
type: reference
course: python-pandas-donchian-channels
date_added: 2026-06-13
tags: [ibkr-api, donchian-channels, trend-following, breakout, pandas]
---

# Introduction to the Donchian Channel

## Concepts

- The **Donchian Channel** is a trend-following indicator built from the highest high and lowest low over a fixed lookback window of N periods.
- **How the three bands are computed:**
  - **Upper band** = maximum `high` over the past N periods.
  - **Lower band** = minimum `low` over the past N periods.
  - **Middle band** = (upper + lower) / 2.
- **Signals / usage:** a price breaking **above the upper band** suggests a new uptrend (bullish breakout); breaking **below the lower band** suggests a downtrend (bearish breakout). The widening/narrowing of the channel visualizes volatility expansion and contraction, and the bands act as dynamic support/resistance.
- In pandas this is just two rolling-window reductions (`.rolling(window=period).max()` on highs, `.min()` on lows) plus their average - no special library needed.

## Code examples

The course's core indicator function, reproduced verbatim:

```python
def donchian_channel(df: pd.DataFrame, period: int = 30) -> pd.DataFrame:
    """
    Calculate the Donchian Channel for a given DataFrame.

    The Donchian Channel is a trend-following indicator that plots the highest high and 
    the lowest low over a specified period, along with a middle line that is the average 
    of the upper and lower bands. This indicator is often used to identify breakouts 
    and determine potential trading signals.

    Parameters
    ----------
    df : pandas.DataFrame
        A DataFrame containing at least the following columns:
        - 'high': The high prices of the asset.
        - 'low': The low prices of the asset.
        - 'close': The closing prices of the asset (not used directly in calculations but 
          generally present in the data).
          
    period : int, optional
        The number of periods to calculate the channel. Default is 30.
        This period determines the look-back window for the highest high 
        and the lowest low.

    Returns
    -------
    pandas.DataFrame
        The original DataFrame with three additional columns:
        - 'upper': The upper band of the Donchian Channel (highest high over the period).
        - 'lower': The lower band of the Donchian Channel (lowest low over the period).
        - 'mid': The middle line, which is the average of the upper and lower bands.

    Examples
    --------
    >>> data = {
    ...     'high': [10, 12, 13, 14, 15, 13, 11, 10, 12, 14],
    ...     'low': [8, 7, 6, 5, 8, 7, 6, 5, 6, 7],
    ...     'close': [9, 10, 12, 13, 14, 12, 10, 9, 11, 13]
    ... }
    >>> df = pd.DataFrame(data)
    >>> donchian_channel(df, period=5)
       high  low  close  upper  lower   mid
    0    10    8    9.0    NaN    NaN   NaN
    1    12    7   10.0    NaN    NaN   NaN
    2    13    6   12.0    NaN    NaN   NaN
    3    14    5   13.0    NaN    NaN   NaN
    4    15    8   14.0   15.0    5.0  10.0
    5    13    7   12.0   15.0    5.0  10.0
    6    11    6   10.0   15.0    5.0  10.0
    7    10    5    9.0   15.0    5.0  10.0
    8    12    6   11.0   15.0    5.0  10.0
    9    14    7   13.0   14.0    5.0   9.5
    """
    # Calculate the upper band (highest high over the period)
    df["upper"] = df["high"].rolling(window=period).max()

    # Calculate the lower band (lowest low over the period)
    df["lower"] = df["low"].rolling(window=period).min()
    
    # Optional: Calculate the middle line (average of upper and lower bands)
    df["mid"] = (df["upper"] + df["lower"]) / 2
    
    return df
```
Adds `upper`, `lower`, and `mid` columns to a high/low/close DataFrame using rolling-window max/min. This same function is reused unchanged in the next two lessons.

## Gotchas

- **Warmup NaNs:** the first `period - 1` rows are `NaN` because there isn't yet a full window of history. Code that consumes the channel must skip rows until enough bars exist (the run loop in [[running-the-donchian-channel]] does exactly this).
- **Lookback choice:** default `period=30`. Tune it to your timeframe - shorter periods react faster but whipsaw more; longer periods are smoother but lag.
- The doctest above is a clean way to sanity-check the function on toy data before pointing it at live prices.

## Related

- Previous: [[introduction-to-pyquant-and-python-pandas]]
- Next: [[implementing-donchian-channel-trading-app]]
- **Strategy completion:** [[running-the-donchian-channel]] (live execution)
- **Trading concepts:** 
  - [[2026-06-08-math-of-winning-in-trading]] (expectancy, variance, breakout trade-offs)
  - [[2026-06-09-stop-trading-like-an-idiot]] (algorithmic trading, prop firm optimization)

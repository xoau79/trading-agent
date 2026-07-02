# data_feed/

Price data sources. Scaffolded here in the baseline commit; hardened/extended in the
`fix/data-feed-hang-and-notifications` and `feat/broker-abstraction` PRs.

Planned contents:
- `yahoo.py` — default source (today's `data_feed.py`), hardened with explicit timeouts and retries.
- `twelvedata.py` — automatic fallback when Yahoo is stale, once `TWELVEDATA_API_KEY` is set in `.env`.
- `broker_feed.py` — once a live broker is connected, price data comes from the broker itself instead of a
  third-party feed.

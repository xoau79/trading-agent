# IBKR reference material

Distilled notes from Interactive Brokers' Traders Academy API courses (40 lessons across 5 courses),
imported from the personal knowledge vault. This is reference material for building out
`broker/ibkr/ibkr_broker.py` (Phase 2) — it is not itself part of the running bot.

See `_intake-checklist.md` for the full course index with source URLs.

| Folder | Course | Relevance to this bot |
|---|---|---|
| `python-tws-api/` | Python TWS API (11 lessons) | **Primary** — this is what `ibkr_broker.py` will be built on: contracts, market data, placing/managing orders, account/portfolio queries, concurrency. |
| `web-api/` | Client Portal / Web API (11 lessons) | Alternative to TWS API (REST + WebSocket, no local terminal needed) — worth reconsidering if TWS's always-running-terminal requirement becomes a problem. |
| `strategy-courses/` | Python/Pandas — Donchian Channels (4 lessons) | Example of a full strategy built on the TWS API; useful pattern reference, not this bot's strategy. |
| `excel-api/` | Excel + TWS API (6 lessons) | Not used by this bot; kept for completeness. |
| `r-api/` | Trading Using R (8 lessons) | Not used by this bot; kept for completeness. Note: source lessons were delivered as screenshots, so code in these notes is transcribed from prose, not copy-pasted — see the caveat in each file. |

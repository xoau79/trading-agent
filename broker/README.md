# broker/

Broker-agnostic trading interface. Scaffolded here in the baseline commit; implemented in the
`feat/broker-abstraction` PR. See `docs/ARCHITECTURE.md` for the design.

Planned contents:
- `base.py` — the `BrokerBase` interface every adapter implements.
- `paper.py` — the current simulated broker (today's `broker.py`), adapted to the interface. Stays the
  default.
- `mt5_broker.py` — IC Markets / MetaTrader 5 adapter (scaffolded, inert until configured).
- `ibkr/ibkr_broker.py` — Interactive Brokers adapter (stub). Reference material in `docs/ibkr/`.

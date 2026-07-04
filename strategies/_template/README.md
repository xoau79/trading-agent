# <Strategy Name>

One-line summary of the edge this strategy trades.

Fill in every section below — a strategy's README should be understandable without reading
its code. See `strategies/orb/README.md` for a filled-in example.

## What it trades

Which assets, which sessions. (`applicable_assets` / `applicable_sessions` in `strategy.py`
should match this exactly.)

## Entry rule

Precisely what has to happen for this strategy to take a trade. Be exact — "price looks
strong" is not an entry rule, "a 1-minute close above X" is.

## Exit rule

- **Stop-loss**: where, and why there.
- **Target**: where, and why there (or: not a fixed target — describe the actual exit logic).
- **Time exit**: does this strategy force-close at session end, or can it hold longer? If it
  can hold overnight, say so explicitly and explain how that interacts with the universal
  daily-loss-limit reset.

## Risk / reward

- **Risk per trade**: what %, and where it's configured (see `strategies/README.md`'s
  config-sharing note for whether this lives in your own `strategy.json` or shares the global
  block — for a genuinely second strategy, prefer your own file).
- **Target R-multiple** or whatever reward measure this strategy actually uses.

## Filters / conditions

Anything that can stand the strategy aside even when the entry rule technically fired
(volatility filters, confluence checks, news blackouts it adds on top of the universal one,
etc). If a filter fires, the bot should notify Discord explaining why (see how
`strategies/orb/strategy.py`'s filtered stage is handled in `bot.py`'s `Engine` and
`agent.py`'s `on_filtered()`) — a strategy that silently declines to trade is not
distinguishable from a bug.

## Backtest results (before going live)

Summarize what you found running this through the Backtest Lab or `bot.py --backtest` across
a real historical period before it ever traded live: win rate, profit factor, max drawdown,
sample size. Be honest about a small sample size — see `broker/paper.py`'s and `learn.py`-
style honesty patterns elsewhere in this repo about not overclaiming from thin evidence.

## Universal rules that also apply (not this strategy's own — see `strategies/README.md`)

Reminder: daily loss limit, trade/position caps, and the consecutive-loss bench apply
regardless of what's written above. Don't re-document them here — link to
`strategies/README.md`'s "Universal rules" section instead.

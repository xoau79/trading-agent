# ORB — Opening Range Breakout

The one strategy live in the bank today. 100% mechanical: no discretion, no opinions, the
same rules every session.

## What it trades

Gold (XAU/USD), Nasdaq 100 (NQ), S&P 500 (ES) — the Asian session trades Gold only; New York
trades all three. See `config.json`'s `sessions` block for the exact assignment.

## Entry rule

1. Record the high and low of the **first 15 minutes** of the session (`opening_range_minutes`
   in config) — the "opening range."
2. **Volatility filter**: the range must be between `range_atr_min` (0.3x) and `range_atr_max`
   (3.0x) the 15-minute ATR (`atr_period`: 14). Too small = dead market, breakouts are noise.
   Too large = a news spike already happened, the stop would be oversized. Fail either bound
   and the asset is **skipped for the entire session** — you'll get a Discord notification
   explaining why, not silence.
3. A completed **1-minute candle closing above** the range high signals **LONG**; closing
   **below** the range low signals **SHORT**.
4. After an exit, a new signal only arms once price closes back *inside* the range first —
   this stops the strategy from instantly re-chasing the same move.
5. **Confluence filter** (`tv_confluence_enabled`): the bot won't take a breakout that
   TradingView's 15-minute technical rating actively rates against it (won't buy into a
   STRONG_SELL, won't sell into a STRONG_BUY/BUY).
6. **News filter**: no new entries within ±15 minutes of high-impact USD news
   (`blackout_minutes_before`/`after` in `config.json`'s `news` block).
7. **Entry cutoff** (`entry_cutoff_minutes`, currently 0 = disabled): optionally refuses new
   entries once too little of the session remains to realistically reach the target.

## Exit rule

- **Stop-loss**: the far side of the opening range (i.e. the range low for a LONG, the range
  high for a SHORT).
- **Target**: `target_r_multiple` (2.0) × the initial risk — a "2R" target, no partials, no
  trailing. The rules don't move the stop early; the math needs full winners to outpace full
  losers.
- **Forced exits** (override stop/target): flattened 5 minutes before top-tier news
  (`flatten_minutes_before_top_tier`: FOMC/NFP/CPI), or immediately if the daily loss limit
  triggers (universal rule, not ORB's).
- **Time exit**: force-closed at session end regardless of where price is. No overnight
  positions, ever.

## Risk / reward

- **Risk per trade**: 1% of account balance (`risk_per_trade_pct` in `config.json`'s `risk`
  block). Position size is computed backward from the stop distance so the dollar risk is
  always exactly this percentage, capped by `max_notional_leverage` (20x).
- **Reward**: 2R target as above, so a full winner is roughly 2x a full loser — the strategy
  only needs to win more than ~1/3 of trades to be profitable over time (before considering
  the 2-loss-in-a-row-then-benched dynamic below).
- **Slippage**: `slippage_pct` (0.02%) applied to both entry and exit fills, in the
  unfavorable direction, to keep the simulation honest.

## Config note (today: shared with the global config)

There's exactly one strategy in the bank right now, so ORB's own parameters
(`opening_range_minutes`, `target_r_multiple`, `atr_period`, `range_atr_min`/`max`,
`entry_cutoff_minutes`, `tv_confluence_enabled`) live in the root `config.json`'s `"strategy"`
block, and `risk_per_trade_pct` lives in the `"risk"` block. This is also where the agent's
bounded auto-tuning system (`agent.py`'s whitelist) writes its own small, evidence-gated
adjustments — so don't move these keys without updating `config.json`'s `tuning.whitelist`
paths too. See `strategies/README.md` for what changes once a second strategy joins the bank
(each with genuinely independent config, not sharing this block).

## Universal rules that also apply (not ORB's — see `strategies/README.md`)

Daily loss limit (−3%), max 4 trades/session, max 8 trades/day, max 2 concurrent positions,
4-consecutive-losses bench. These are enforced by `broker/paper.py` for every strategy in the
bank, unconditionally — ORB cannot loosen them, only trade within them.

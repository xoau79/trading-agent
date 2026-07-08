# Skill: Check external feed health

## When to use it
Before a trading day starts (the scheduled `TradingAgent-SmokeTest` task runs this at ~10:00 Sydney, before the Asian session), after any network/ISP issue, or whenever the bot's behavior looks like it might be a data problem rather than a strategy problem.

## Steps, in order

1. **Run the smoke test:**
   ```
   python ops/smoke_test.py
   ```
   It checks four things independently: Yahoo Finance 1-minute bars (the price feed the bot is only viable without), the ForexFactory economic calendar (news blackout filter), CNBC RSS headlines, and TradingView technical ratings.
2. **Read each line's PASS/FAIL, don't just check the final count.** The price feed (Yahoo) is the only one that's load-bearing — if it FAILs, the bot cannot trade at all today. The other three have graceful fallbacks built in (ForexFactory falls back to its last cached copy; TradingView/RSS fail open with a logged warning) — a FAIL on one of those degrades a filter, it doesn't stop trading.
3. **If you want a Discord alert instead of watching a terminal**, use:
   ```
   python ops/smoke_test.py --discord
   ```
   This only posts to Discord when something actually FAILs — a clean run stays silent, so a Discord notification from this script is always worth reading.
4. **Once a demo broker (cTrader/MT5) is connected**, also run the feed parity check to compare the broker's own prices against Yahoo:
   ```
   python ops/feed_parity.py
   ```
   This is a different check from the smoke test — it's not "is Yahoo reachable," it's "does the broker's price agree with a known-good source," which catches symbol-mapping mistakes and price-scaling bugs the smoke test can't see.
5. **A large price delta or a stale broker feed in `feed_parity.py`'s output is not something to trade through.** Fix the symbol mapping in `config.json` (verify it with `ops/ctrader_smoke_test.py --symbols` or the MT5 terminal's Market Watch — never guess) before running a session against that broker.

## Example of a good final output

The real, verified output of `python ops/smoke_test.py` on a healthy day (this exact format — `check()`'s own print statements):

```
PASS  Yahoo 1-min bars: GC=F 391 bars (latest 2026-07-08 05:59:00+00:00); NQ=F 391 bars (latest 2026-07-08 05:59:00+00:00); ES=F 391 bars (latest 2026-07-08 05:59:00+00:00)
PASS  ForexFactory calendar: 34 events this week, 3 high-impact USD (e.g. Non-Farm Payrolls)
PASS  CNBC RSS headlines: 12 headlines, latest: Fed signals no rate change at July meeting
PASS  TradingView ratings: gold=BUY; nasdaq-fut=NEUTRAL; sp500-fut=BUY; nasdaq-proxy=NEUTRAL; sp500-proxy=BUY

4/4 feeds OK
```

And the real `--discord` alert format on a failure (this exact format, produced this session against a genuinely broken environment):
```
⚠️ **Smoke test**: 4/4 feed(s) failed:
- Yahoo 1-min bars: no data for GC=F
- ForexFactory calendar: <urlopen error Tunnel connection failed: 403 Forbidden>
- CNBC RSS headlines: No module named 'feedparser'
- TradingView ratings: No module named 'tradingview_ta'
```
The second example is a good *failure* report because each line gives you enough to diagnose the actual cause — a missing package is a different fix from a blocked network path, and the message doesn't blur the two together.

## Mistakes to avoid

- **Don't treat every FAIL the same way.** A Yahoo FAIL means don't trade today (paper trading has no other primary price source unless `TWELVEDATA_API_KEY` is set as a fallback). A ForexFactory/RSS/TradingView FAIL degrades a filter, not the whole system — the bot keeps trading, just with one fewer safety check active.
- **A stale ForexFactory cache is not the same as "no calendar data."** `news.py`'s `refresh_calendar()` falls back to its last successfully-fetched copy on a fetch failure — this is silently safer than it looks, but it also means a genuinely FAILing calendar check that's been silently using a week-old cache for a while is worth investigating, not just ignoring because "it still returned something."
- **Don't assume a clean smoke test today means the feeds will still be healthy at session time.** This is a point-in-time check; run it close to when it matters (the scheduled task runs ~30 minutes before the Asian session for this reason), not once in the morning and then forget about it for the whole trading day.
- **`ops/feed_parity.py` deliberately does nothing while `broker.provider` is `"paper"`.** Seeing "nothing to compare against yet" is the *correct*, expected output during paper trading — it's not a sign the tool is broken, it's the tool correctly recognizing there's no broker connection to check yet.
- **Don't hardcode or guess a broker symbol to make a FAIL go away.** Every `mt5`/`ctrader` symbol field in `config.json` ships with an explicit note not to trust the guess — the fix for a symbol-related FAIL is always to verify against the real account (`ops/ctrader_smoke_test.py --symbols`, or the MT5 terminal's Market Watch), never to type in whatever looks plausible.

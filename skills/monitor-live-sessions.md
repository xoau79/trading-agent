# Skill: Monitor a live trading session

## When to use it
During an active Asian (~11:00–15:00 AEST Sydney) or New York (~23:30–06:00 Sydney) session, whether you're watching the dashboard directly (home, weekends) or only getting Discord notifications (school term).

## Steps, in order

1. **Confirm the session actually started.** Check Discord for the agent's session-start message (`agent.py`'s `on_session_start`, posted with `discord=True`) or open `http://localhost:8765` if you're home. If neither shows up by ~10 minutes after the scheduled Task Scheduler trigger (`TradingAgent-Asia` 10:30, `TradingAgent-NY` 23:30 Sydney), something failed at launch — check `logs/<session>_<date>.log`.
2. **Read every Discord notification as it arrives, don't just glance at the count.** The agent posts on session start, opening-range set, entries, trade management milestones (every `manage_update_minutes`, or instantly at half-R milestones), exits, halts, benches, and session end — each message explains the *why*, not just the *what*. A message you don't understand is worth re-reading, not skipping.
3. **If `ops/watchdog.py`'s alert fires** (⚠️ "the `<session>` session looks dead"), that means `dashboard/data.js` has gone stale for 5+ minutes, or the bot's own status reports an emergency/aborted stop, during a *live* session window. Check the dashboard (if home) or `logs/<session>_<date>.log` (if remote — ask whoever has terminal access) before assuming the worst; it fires at most once per session so a second alert about the same session won't come even if the problem persists.
4. **Watch for the halt banner / halt Discord message.** A daily loss limit hit, a manual kill switch, or an emergency stop after repeated errors all post via `agent.say("halt", ..., discord=True)`. A halt is the system protecting the account working as designed — read the reason, don't panic, and don't try to "unstick" it unless it's the manual kill switch (see step 5).
5. **Use the dashboard's "Flatten & halt" kill switch only when something looks genuinely wrong** — a stuck position, erratic behavior, anything you wouldn't sign off on if asked. It flattens every open position and halts trading within ~45 seconds (one loop iteration). Clear it from the same spot ("Clear halt") once you're satisfied; a daily-loss halt (if one is *also* in effect) still stands until the next day regardless.
6. **At session end**, read the agent's session-end Discord message and, once you're home, the post-session digest (`ops/session_digest.py --session <asia|newyork>`, also auto-posted by the scheduled `TradingAgent-DigestAsia`/`TradingAgent-DigestNY` tasks) for anything the live narration didn't surface — WARNING/ERROR log lines, per-asset filter reasons.

## Example of a good final output

The agent's real entry narration format (`agent.py`'s `on_entry`), which is what a well-monitored trade actually looks like in Discord:

```
📈 ENTERED LONG GOLD at 3350.20 — price closed through the opening range (1.2x ATR).
Size 12.5 units so the stop at 3345.10 risks exactly $100.00 (1%). Target 3360.40 (2R).
TradingView 15m read: BUY. The breakout direction agrees with my broader read —
alignment I like to see. From here the plan owns the trade: stop, target, or
session close — whichever comes first.
```

And a real `ops/session_digest.py --dry-run` post-session summary (verified output format, this repo):

```
**Session digest — newyork — 2026-07-08**
**Trades:** 2  |  **Wins:** 1  |  **Losses:** 1  |  **P&L:** +110.40 USD
**Balance:** $10,110.40

**Trades:**
- #1 GOLD LONG: 3350.2 → 3362.8 (target) +210.40 USD (+2.00R)
- #2 NQ SHORT: 19800.0 → 19850.0 (stop) -100.00 USD (-1.00R)

**Asset notes:**
- **GOLD**: stage at close: hunting
- **NQ**: stage at close: filtered
- **ES**: range abnormally small (dead market) — skipped for the whole session

**3 warning/error log line(s)** (never surfaced to Discord before) — most recent:
`2026-07-08 14:05:33,220 WARNING data_feed.yahoo: rate-limited, retrying`
`2026-07-08 14:05:34,001 WARNING bot: broker feed missing/stale for NQ — falling back to Yahoo/TwelveData`
`2026-07-08 16:40:02,440 ERROR news: tradingview rating failed for Gold (XAU/USD): TimeoutError`
```
This is a good digest because it separates what the agent already told you live (trades, P&L) from what it never surfaces (the WARNING/ERROR lines) — the whole point of reading it is to catch the second half.

## Mistakes to avoid

- **Don't assume silence means "nothing happened."** The in-process dead-man's-switch (a watchdog that lived inside the bot process) was removed as a bad design in PR #6 — for a while after that, a mid-session crash produced *zero* signal away from the dashboard. `ops/watchdog.py` exists specifically to close that gap; if it isn't registered as a scheduled task on the machine you're relying on, silence during a session window is not proof of health.
- **Don't confuse a deliberate stand-down with a failure.** "Standing down — no market data (holiday/closure?)" and the 🏖️ holiday badge are the system correctly refusing to trade thin conditions, not an error. Read the reason before reacting.
- **A halt reason string prefix matters.** `broker.state["halted_reason"]` starting with `"manual kill switch"` is the dashboard's own kill switch and clears itself when you press "Clear halt." A daily-loss halt has a different reason text and does *not* clear until the next trading day — don't confuse the two when deciding whether something needs your action.
- **Remember New York's session can close on the Sydney calendar day *after* the one it opened on.** During the part of the year when Sydney is on daylight saving but New York isn't, a session that opens ~23:30 Monday Sydney time can have its `day_key` land on Tuesday. If you're hunting for a specific session's log file or journal entry by date and can't find it under the date you expected, check the next day too.
- **Don't treat a stale-data alert as a live-trading emergency if you're outside a session window.** `ops/watchdog.py` deliberately only checks staleness during a session's actual live window (`open_utc` to `close_utc`), not the pre-open wait — a fixed "lead time" buffer would misfire, since the real lead time varies between ~30 minutes and ~1.5 hours depending on the time of year (Tokyo's DST-free clock vs Sydney's own DST calendar).

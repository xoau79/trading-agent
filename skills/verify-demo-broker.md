# Skill: Verify a demo broker connection before trading it

## When to use it
When setting up a cTrader or MT5 demo account for the first time, or re-verifying one after a symbol/config change — this is the current stage of this project (paper trading works today; a demo broker account is the next milestone before ever considering live).

## Steps, in order (cTrader — MT5 follows the same shape, see `docs/ctrader_setup.md` Part 2)

1. **Register a Spotware Open API application** at https://openapi.ctrader.com, note the Client ID/Secret, and add the exact redirect URI `http://localhost:53123/callback`.
2. **Fill in `.env`** with `CTRADER_CLIENT_ID`/`CTRADER_CLIENT_SECRET`. Leave `CTRADER_ACCOUNT_ID` and `LIVE_TRADING_CONFIRM` empty at this stage — you haven't picked an account yet, and the live latch has no business being touched during demo setup.
3. **Authorize and discover accounts:**
   ```
   python ops/ctrader_auth.py
   ```
   This opens a browser, catches the OAuth redirect locally, saves a refreshable token to `ctrader_tokens.json` (gitignored — never commit it), and lists every account the token can access.
4. **Put the *demo* account's id into `.env`'s `CTRADER_ACCOUNT_ID`** — never the live one at this stage. If your account only shows up checking the live host, re-run with `--host live.ctraderapi.com --list-accounts` just to look, but still don't put a live id into `.env` yet.
5. **Verify symbols before touching `config.json`:**
   ```
   python ops/ctrader_smoke_test.py --symbols
   ```
   Find the real gold/index symbol names in the output and fill them into `config.json`'s `assets.*.ctrader` fields — every one of them ships as `null` with a note like *"likely 'XAUUSD'; verify... do not trust this guess."* That instruction is the whole point of this step; don't skip it and type in the likely-guess anyway.
6. **Run the full connectivity check:**
   ```
   python ops/ctrader_smoke_test.py
   ```
   All checks (account info, symbol resolution, trendbars, live spot) must PASS. If a symbol fails to resolve, the error lists near-matches — fix `config.json` and re-run rather than guessing again.
7. **Cross-check the broker's own prices against Yahoo:**
   ```
   python ops/feed_parity.py
   ```
   for an independent second opinion on whether the symbol mapping and price scaling are actually correct, not just that the API call succeeded.
8. **Place one real (tiny) demo order** through the full pipeline:
   ```
   python ops/live_order_test.py --provider ctrader --yes
   ```
   This refuses outright if the configured account is live. Read the printed trade dict — this is the strongest signal the whole chain (sizing → order → fill → close → journal) actually works, not just that individual API calls succeed.
9. **Flip `config.json`'s `broker.provider` to `"ctrader"`** and run one supervised demo session (`python bot.py --session newyork`, or the dashboard's wake button), watching it the whole time. Confirm the dashboard's hero tag shows **DEMO** with the right account id, test the "Flatten & halt" kill switch once mid-session, and confirm normal trading resumes after clearing it.
10. **Kill the bot process mid-session on purpose at least once** and restart it — confirm `broker.reconcile()` runs at startup and either finds nothing to reconcile or correctly books any position that closed while it was down (journaled as `reconciled_externally`).

## Example of a good final output

The real example account-listing output `ops/ctrader_auth.py` produces (from `docs/ctrader_setup.md`):
```
2 account(s) available on demo.ctraderapi.com:
  ctidTraderAccountId=1234567  [demo]  broker=ICM
  ctidTraderAccountId=1234568  [LIVE — real money]  broker=ICM
```
This is a good output to act on because it labels demo vs. LIVE explicitly right in the listing — the id you copy into `.env`'s `CTRADER_ACCOUNT_ID` at this stage should always be the one tagged `[demo]`, never the one tagged `[LIVE — real money]`, no matter how far along the setup is.

## Mistakes to avoid

- **Never fill in a broker symbol from memory or a guess, even a well-informed one.** Every symbol field in `config.json` ships `null` specifically because IC Markets (and other brokers) sometimes suffix symbols (e.g. `.a`) depending on account type — the only correct source is `ops/ctrader_smoke_test.py --symbols` (or the MT5 terminal's own Market Watch), run against *your* actual account.
- **Currency conversion isn't implemented.** `CTraderBroker.get_account_info()` assumes USD unless `config.json`'s `broker.ctrader.currency` is set — if the demo account isn't USD-denominated, the numbers you see will be wrong until that's configured, not because anything is broken.
- **Crash-recovery pricing is an approximation, not a bug.** If the bot is down when a live/demo position closes (stop/target hit server-side), `LiveBroker.reconcile()` books it at the *current* market price on the next startup, not the actual historical fill — it's clearly labeled `reconciled_externally` in the journal so this is never silently wrong, just approximate. Don't be alarmed by a slightly-off P&L on a reconciled trade; do be alarmed if it isn't labeled as reconciled.
- **The price/volume scaling has been checked against Spotware's published source, not against a live account, until you verify it yourself.** `broker/ctrader/messages.py`'s own docstring says so — `ops/ctrader_smoke_test.py`'s trendbar check exists specifically so you can compare its printed price against a real gold price yourself, which is a step to actually do, not skip because the check "passed."
- **Don't skip straight to flipping `config.json`'s `broker.provider`.** Every step before that (auth, symbol verification, connectivity check, tiny order test) exists to catch a mistake in a context where it's cheap to fix — skipping ahead means the first time a mapping or scaling bug shows up is during a live-watched session, which is a worse place to find it.
- **A demo account trading "cleanly for a while" has no fixed threshold — that's a judgment call, not a checklist item.** Don't treat any specific number of clean sessions as an automatic green light to go live; the actual go-live steps (`docs/ctrader_setup.md`'s "Going live" section) require a deliberate decision plus two separate confirmations (`live_trading.enabled` in `config.json` *and* `.env`'s `LIVE_TRADING_CONFIRM` matching the exact account id) — both are required specifically so this can never happen by accident.

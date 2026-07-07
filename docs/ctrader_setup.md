# Going live: cTrader (and MT5) setup

This is the step-by-step path from paper trading to a real IC Markets (or prop-firm) account,
demo first. Read `broker/README.md`'s "Safety, by design" section before starting — every
step below exists because of one of those mechanisms.

**Scope:** execution happens through **cTrader** (Spotware's Open API) or **MT5** — pick
whichever your account uses. TradingView has no order-execution API; it stays what it already
is in this repo, a 15-minute rating filter and chart widgets. IBKR (`broker/ibkr/`) is still a
stub.

## Part 1 — cTrader

### 1. Register a Spotware Open API application

1. Go to https://openapi.ctrader.com and sign in with your cTrader ID.
2. Create a new application. Note its **Client ID** and **Client Secret**.
3. Add this exact redirect URI to the application: `http://localhost:53123/callback`
   (`ops/ctrader_auth.py` listens on that port to catch the authorization code).

### 2. Fill in `.env`

Copy `.env.example` to `.env` if you haven't already, then fill in:

```
CTRADER_CLIENT_ID=<from step 1>
CTRADER_CLIENT_SECRET=<from step 1>
```

Leave `CTRADER_ACCOUNT_ID` and `LIVE_TRADING_CONFIRM` empty for now.

### 3. Authorize and discover your account

```
python ops/ctrader_auth.py
```

This opens a browser to authorize the app against your cTrader ID, catches the redirect
locally, and saves a refreshable token to `ctrader_tokens.json` (gitignored — never commit
it). It then lists every trading account the token can access, e.g.:

```
2 account(s) available on demo.ctraderapi.com:
  ctidTraderAccountId=1234567  [demo]  broker=ICM
  ctidTraderAccountId=1234568  [LIVE — real money]  broker=ICM
```

Put the **demo** account's id into `.env`'s `CTRADER_ACCOUNT_ID`. (If your account only shows
up when checking the live host, re-run with `--host live.ctraderapi.com --list-accounts`.)

### 4. Verify symbols and connectivity

```
python ops/ctrader_smoke_test.py --symbols
```

Find your gold/index symbol names in the output (commonly `XAUUSD`, `USTEC`, `US500` on IC
Markets — but verify, don't assume) and fill them into `config.json`'s `assets.*.ctrader`
fields (they ship as `null`; each has a `ctrader_note` pointing back here). Then run the full
check:

```
python ops/ctrader_smoke_test.py
```

All checks should PASS: account info, symbol resolution, trendbars, a live spot price. If a
symbol fails to resolve, the error lists near-matches — fix `config.json` and re-run.

### 5. A real (tiny) demo order

```
python ops/live_order_test.py --provider ctrader --yes
```

This refuses outright if the configured account is live — it only ever runs against demo. It
places a minimum-size market order with a wide stop/target through the exact same code path a
live session would use, confirms it via `get_positions()`, then closes it. Read the printed
trade dict; this is the strongest signal the whole pipeline (sizing → order → fill → close →
journal) actually works before trusting it with a real session.

### 6. A supervised demo session

Flip `config.json`:

```json
"broker": { "provider": "ctrader", ... }
```

Run a session live (`python bot.py --session newyork`, or start it early via the dashboard's
wake button) and watch it. Things worth deliberately checking once:

- The dashboard's hero tag shows **DEMO**, brand-sub shows `cTrader · demo · <account id>`.
- Press **Flatten & halt** once mid-session — confirm it flattens (if a position is open) and
  the halt banner appears within ~45s; press **Clear halt** and confirm normal trading resumes.
- Kill the bot process mid-session (or just let it crash-test naturally) and restart it —
  `broker.reconcile()` should run at startup and either find nothing to reconcile, or book any
  position that closed while it was down (journaled as `reconciled_externally`).

## Part 2 — MT5

1. Install the MT5 terminal, log into your IC Markets (or other) MT5 account in it, and enable
   algo trading: Tools → Options → Expert Advisors → "Allow algorithmic trading".
2. `pip install MetaTrader5` (Windows-only; commented out in `requirements.txt` by default).
3. Fill in `.env`'s `MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER`.
4. Check the terminal's Market Watch for your exact symbol names and fill in `config.json`'s
   `assets.*.mt5` fields (IC Markets sometimes suffixes symbols, e.g. `.a`, depending on
   account type — don't guess).
5. `python ops/mt5_smoke_test.py` — read-only, run on the actual Windows machine.
6. `python ops/live_order_test.py --provider mt5 --yes` — same demo-only order test as cTrader.
7. Flip `config.json`'s `broker.provider` to `"mt5"` and run a supervised demo session, same
   checklist as step 6 above.

## Going live

Once a demo account has run cleanly for a while (your judgment on "a while" — this is real
money next):

1. Get the **live** account's id (`python ops/ctrader_auth.py --host live.ctraderapi.com
   --list-accounts`, or your MT5 live login).
2. Consider lowering `config.json`'s `risk.risk_per_trade_pct` for the first live sessions.
3. Set `config.json`'s `live_trading.enabled` to `true`.
4. Set `.env`'s `LIVE_TRADING_CONFIRM` to the **exact** live account id from step 1. Both this
   and step 3 are required — see `broker/live.py`'s `_enforce_live_latch()`. Missing either
   one makes `connect()` refuse outright.
5. Update `.env`'s `CTRADER_ACCOUNT_ID` (or `MT5_LOGIN`) to the live account.
6. Run one supervised session. Watch the dashboard's LIVE banner and kill switch. Don't walk
   away for the first one.

Review `config.json`'s `live_trading` block before going live: `max_units_per_asset`,
`min_stop_distance_pct`/`max_stop_distance_pct`, and `max_total_drawdown_pct` are your
prop-firm-style guardrails — set them to whatever your actual account/prop-firm rules require
before risking anything.

## Known limitations

- **Crash-recovery pricing is an approximation.** If the bot is down when a live position
  closes (stop/target hit server-side), `LiveBroker.reconcile()` books it at the *current*
  market price on the next startup, not the actual historical fill — there's no deal-history
  lookup yet. The trade is clearly labeled `reconciled_externally` in the journal so this is
  never silently wrong, just approximate. This should be rare (positions are meant to be flat
  by session end every day) but isn't impossible during an unclean shutdown.
- **cTrader price/volume scaling was verified against Spotware's published proto source**
  (see `broker/ctrader/messages.py`'s docstring) but not against a live account by this
  implementation — `ops/ctrader_smoke_test.py`'s trendbar check exists specifically to catch a
  scaling mistake (compare its printed price against a real gold price yourself).
- **IC Markets symbol names are guesses** (`XAUUSD`/`USTEC`/`US500`) until you run
  `ops/ctrader_smoke_test.py --symbols` / `ops/mt5_smoke_test.py` against your own account.
- **Currency conversion isn't implemented.** `CTraderBroker.get_account_info()` assumes USD
  unless you set `config.json`'s `broker.ctrader.currency`; no FX conversion happens anywhere.

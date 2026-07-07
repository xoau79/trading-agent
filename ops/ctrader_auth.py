"""One-time cTrader (Spotware Open API) OAuth setup: authorizes this app against your
cTrader ID, discovers which trading accounts it can access, and saves a refreshable token to
ctrader_tokens.json (gitignored -- never commit it).

Before running this for the first time:
  1. Go to https://openapi.ctrader.com and register a new Open API application.
  2. Add this exact redirect URI to the app: http://localhost:53123/callback
  3. Copy the app's Client ID and Client Secret into .env's CTRADER_CLIENT_ID /
     CTRADER_CLIENT_SECRET (copy .env.example to .env first if you haven't already).

Usage:
    python ops/ctrader_auth.py                  # authorize in a browser, then list accounts
    python ops/ctrader_auth.py --list-accounts   # skip the browser step (reuse saved token)
    python ops/ctrader_auth.py --refresh         # force a token refresh and exit
    python ops/ctrader_auth.py --host live.ctraderapi.com --list-accounts  # check a live token

Whichever ctidTraderAccountId this prints for the account you want to trade goes into
.env's CTRADER_ACCOUNT_ID. See docs/ctrader_setup.md for the full walkthrough.
"""
import argparse
import http.server
import os
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))  # so `python ops/ctrader_auth.py` can import the repo's modules

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BASE / ".env")

from broker.ctrader import auth as ctrader_auth  # noqa: E402
from broker.ctrader import messages as M  # noqa: E402
from broker.ctrader.transport import CTraderTransport  # noqa: E402

TOKEN_FILE = BASE / "ctrader_tokens.json"
REDIRECT_PORT = 53123
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"
AUTH_WAIT_SECONDS = 300


def _capture_auth_code():
    """A one-shot local HTTP server that catches the OAuth redirect and grabs ?code=."""
    result = {}
    done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in qs:
                result["code"] = qs["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body><h2>Authorized \xe2\x80\x94 you can close "
                                 b"this tab and return to the terminal.</h2></body></html>")
            else:
                result["error"] = qs.get("error", ["unknown_error"])[0]
                self.send_response(400)
                self.end_headers()
            done.set()

        def log_message(self, *a):
            pass  # keep stdout to our own status lines

    server = http.server.HTTPServer(("localhost", REDIRECT_PORT), Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    try:
        if not done.wait(AUTH_WAIT_SECONDS):
            raise RuntimeError(f"timed out waiting for the OAuth redirect ({AUTH_WAIT_SECONDS}s)")
    finally:
        server.server_close()
    if "error" in result:
        raise RuntimeError(f"authorization was not granted: {result['error']}")
    return result["code"]


def authorize(client_id, client_secret):
    url = ctrader_auth.build_authorize_url(client_id, REDIRECT_URI)
    print(f"\nOpening your browser to authorize this app:\n  {url}\n")
    print("(If nothing opens automatically, copy that URL into a browser yourself. Log in "
          "with your cTrader ID and select the account(s) to grant access to.)\n")
    webbrowser.open(url)
    code = _capture_auth_code()
    print("Authorization code received — exchanging it for a token...")
    token = ctrader_auth.exchange_code(client_id, client_secret, REDIRECT_URI, code)
    store = ctrader_auth.TokenStore(TOKEN_FILE, client_id, client_secret)
    store.save(token)
    print(f"Token saved to {TOKEN_FILE} (gitignored — never commit this file).")
    return store


def list_accounts(store, host):
    events = []
    t = CTraderTransport(host, on_event=lambda pt, p: events.append((pt, p)))
    t.connect()
    try:
        t.request(M.APPLICATION_AUTH_REQ,
                 {"clientId": store.client_id, "clientSecret": store.client_secret})
        _, payload = t.request(M.GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ,
                               {"accessToken": store.access_token()})
        accounts = payload.get("ctidTraderAccount", [])
        if not accounts:
            print("\nNo trading accounts are authorized for this token yet — when you "
                  "authorize in the browser, make sure you select at least one account.")
            return []
        print(f"\n{len(accounts)} account(s) available on {host}:")
        for acc in accounts:
            env = "LIVE — real money" if acc.get("isLive") else "demo"
            print(f"  ctidTraderAccountId={acc['ctidTraderAccountId']}  [{env}]  "
                 f"broker={acc.get('brokerTitleShort', '?')}")
        print("\nPut the ctidTraderAccountId you want to trade into .env's CTRADER_ACCOUNT_ID.")
        return accounts
    finally:
        t.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="force a token refresh and exit")
    ap.add_argument("--list-accounts", action="store_true",
                    help="skip the browser step, just list accounts for the saved token")
    ap.add_argument("--host", default="demo.ctraderapi.com",
                    help="Open API host to query (default: demo.ctraderapi.com; use "
                    "live.ctraderapi.com to check a live-account token)")
    args = ap.parse_args()

    client_id = os.getenv("CTRADER_CLIENT_ID")
    client_secret = os.getenv("CTRADER_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("CTRADER_CLIENT_ID / CTRADER_CLIENT_SECRET are not set in .env.\n")
        print("Before running this script:")
        print("  1. Go to https://openapi.ctrader.com and register a new application.")
        print(f"  2. Add this exact redirect URI to the app: {REDIRECT_URI}")
        print("  3. Copy the Client ID and Client Secret into .env's CTRADER_CLIENT_ID / "
             "CTRADER_CLIENT_SECRET (copy .env.example to .env first if you haven't).")
        print("  4. Re-run this script.")
        sys.exit(1)

    if args.refresh:
        store = ctrader_auth.TokenStore(TOKEN_FILE, client_id, client_secret)
        store.force_refresh()
        print("Token refreshed and saved.")
        return

    if args.list_accounts:
        store = ctrader_auth.TokenStore(TOKEN_FILE, client_id, client_secret)
    else:
        store = authorize(client_id, client_secret)

    list_accounts(store, args.host)


if __name__ == "__main__":
    main()

---
title: Launching and Authenticating the Gateway
source: https://www.interactivebrokers.com/campus/trading-lessons/launching-and-authenticating-the-gateway/
type: reference
course: web-api
date_added: 2026-06-13
tags: [client-portal-api, api-gateway, authentication, session-management, rest-api]
---

# Launching and Authenticating the Gateway

## Concepts

- The Client Portal Gateway is a small Java service that runs locally and brokers every request between your program and IBKR. Your code never talks to IBKR servers directly - it talks to the gateway at `https://localhost:5000`.
- The base URL for all API calls is `https://localhost:5000/v1/api/`.
- Auth flow: download/extract the gateway, start it from the command line, open `https://localhost:5000` in a browser, log in with IBKR credentials (live or paper), and wait for "Client login succeeds". The gateway then holds the session.
- **Keepalive**: a live session lasts up to ~24 hours but only if kept alive. Send a periodic "tickle" (or call `/iserver/auth/status`) roughly every 30 seconds, or the session drops.
- Check auth state any time with the `/iserver/auth/status` endpoint.

## Code examples

Verify Java is installed:

```
java –version
```

Start the gateway (Windows):

```
cd {Your Directory}\clientportal.gw
bin\run.bat root\conf.yaml
```

Start the gateway (Unix/Mac):

```
cd {Your Directory}/clientportal.gw
bin/run.sh root/conf.yaml
```

Check authentication status from Python (note `verify=False` for the gateway's self-signed cert):

```python
import requests

# Disable SSL Warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# reauthenticate
def confirmStatus():
    base_url = "https://localhost:5000/v1/api/"
    endpoint = "iserver/auth/status"

    auth_req = requests.get(url=base_url+endpoint,verify=False)
    print(auth_req)
    print(auth_req.text)

if __name__ == "__main__":
    confirmStatus()
```

The endpoint and a success response:

```
GET https://localhost:5000/v1/api/iserver/auth/status

Response [200]
{"authenticated": true, "competing": false, "connected": true, ...}
```

## Gotchas

- Default ports/endpoint: gateway at `https://localhost:5000`, API base at `https://localhost:5000/v1/api/`.
- Status codes to handle: `200` OK, `401` session not authenticated, `403` access denied.
- The gateway uses a self-signed SSL cert, so browsers show an "insecure" warning and Python needs `verify=False`. This is expected for localhost; the connection is still local. Swap in your own cert via `sslCert`/`sslPwd` in `root\conf.yaml`, then restart.
- Auth fails if the account is logged in elsewhere (TWS, Client Portal, IB Desktop). Log out of other platforms first.
- Closing an app window without an explicit "Log Out" leaves a stale session that can block re-authentication.
- Paper account credentials differ from live - get them under Client Portal Settings > Account Configuration > Paper Trading Account.
- Install the Python deps: `pip install requests urllib3`.

## Related

- Previous: [[what-is-ibkrs-client-portal-api]]
- Next lesson: [[contract-search]]
- TWS-side equivalent setup: [[installing-configuring-tws-for-the-api]]

---
title: Accessing the TWS Python API Source Code
source: https://www.interactivebrokers.com/campus/trading-lessons/accessing-the-tws-python-api-source-code/
type: reference
course: python-tws-api
date_added: 2026-06-13
tags: [ibkr-api, tws-api, python-setup, ibapi-install, troubleshooting]
---

# Accessing the TWS Python API Source Code

## Concepts

- The TWS API source code defines the messages exchanged between TWS and your program over a TCP socket. It uses a **pub/sub pattern**: your client subscribes to data types, TWS publishes updates as they happen.
- The download is platform-specific packaging (Windows MSI installer vs Mac/Unix zip) but the source code inside is identical.
- Downloads live on the IBKR Campus TWS API documentation page - choose "stable" (recommended) or "latest". The Python package you end up installing is called `ibapi`.
- Installing means: extract the download, go to the Python client folder inside it, and run the setup script so `ibapi` becomes importable in your Python environment.

## Code examples

Mac/Unix extraction:

```bash
unzip twsapi_macunix.{major}{minor}.{micro}.zip
```

Install the ibapi package (run inside `{TWS API}/source/pythonclient/`):

```bash
python setup.py install
```

Verify the install - version shown should match the release you downloaded (e.g. 10.29):

```bash
python -m pip show ibapi
```

Run the bundled validation test (from `C:\TWS API\samples\Python\Testbed`):

```bash
python Program.py --port 7497
```

Port defaults to 7497 (paper) if omitted; 7496 is live.

## Gotchas

- **Error 502 "Couldn't connect to TWS"**: TWS isn't running, "Enable ActiveX and Socket Clients" isn't checked, or the port doesn't match - see [[installing-configuring-tws-for-the-api]].
- Latest releases require **Python 3.11+**. Releases 10.35+ have a known "missing ibapi.protobuf module" issue - fix by upgrading Python, reinstalling the API, or see https://github.com/awiseib/Python-testers/blob/main/README.md
- Minimum order size errors come from TWS Precautionary Settings (Global Configuration -> Presets -> instrument type), not from your code. Adjustable or can be set to 0.
- Real-time data may be unavailable outside regular trading hours; historical data still works.
- Windows install needs admin rights.

## Related

- Previous: [[installing-configuring-tws-for-the-api]]
- Next: [[essential-components-of-tws-api-programs]]

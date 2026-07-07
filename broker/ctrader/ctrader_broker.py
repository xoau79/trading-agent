"""IC Markets (or any broker/prop-firm) cTrader account via Spotware's Open API.

See broker/ctrader/transport.py for the wire client and broker/ctrader/messages.py for the
verified payloadType/field reference this is built from. This adapter is deliberately
synchronous -- every method blocks until its response (or the transport's timeout) arrives,
matching bot.py's Engine's plain polling loop; no async/await, no event loop for callers to
manage.

Any cTrader account -- IC Markets or a prop-firm's cTrader account -- plugs in the same way:
put its ctidTraderAccountId in .env's CTRADER_ACCOUNT_ID (see ops/ctrader_auth.py to discover
it). connect() asks the API which of the token's authorized accounts this id is and whether
it's live or demo (isLive), then connects to the matching host.

Known simplification (documented, not hidden): get_account_info()'s "currency" is not
resolved via an extra ASSET_LIST_REQ round trip for the account's deposit asset -- it assumes
USD (the common case for IC Markets). Override cfg["broker"]["ctrader"]["currency"] if your
account is denominated differently; that value is used verbatim without any conversion.
"""
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..base import BrokerBase
from . import messages as M
from .auth import TokenStore
from .transport import CTraderError, CTraderTransport

log = logging.getLogger("broker.ctrader")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_TOKEN_FILE = REPO_ROOT / "ctrader_tokens.json"
FILL_TIMEOUT_SECONDS = 10


class CTraderBroker(BrokerBase):
    def __init__(self, cfg, transport_factory=None):
        """transport_factory(host, port, on_event=None, on_reconnect=None) -> an object with
        connect()/close()/request(payload_type, payload, timeout=...) -- defaults to building
        a real CTraderTransport, overridable in tests for a fake, thread-free double."""
        self.cfg = cfg
        self._transport_factory = transport_factory or (
            lambda host, port, on_event=None, on_reconnect=None: CTraderTransport(
                host, port, on_event=on_event, on_reconnect=on_reconnect))
        ccfg = cfg.get("broker", {}).get("ctrader", {})
        self.host_demo = ccfg.get("host_demo", "demo.ctraderapi.com")
        self.host_live = ccfg.get("host_live", "live.ctraderapi.com")
        self.port = ccfg.get("port", 5036)
        self.currency = ccfg.get("currency", "USD")
        self.order_label = cfg.get("live_trading", {}).get("order_label", "trading-agent")

        self._client_id = None
        self._client_secret = None
        self._account_id = None
        self._is_live = None
        self._token_store = None
        self._transport = None
        self._connected = False

        self._symbols_by_asset = {}   # asset -> symbolId
        self._id_to_asset = {}        # symbolId -> asset
        self._symbol_meta = {}        # symbolId -> {digits, lotSize, minVolume, maxVolume, stepVolume}
        self._last_spot = {}          # asset -> last bid price (float)
        self._positions_cache = {}    # asset -> pos dict, refreshed by get_positions()

        self._fill_lock = threading.Lock()
        self._fill_waiters = {}       # symbolId -> {"event": Event, "result": payload}

    # ----- connection -----------------------------------------------------------
    def connect(self):
        self._client_id = os.getenv("CTRADER_CLIENT_ID")
        self._client_secret = os.getenv("CTRADER_CLIENT_SECRET")
        account_id = os.getenv("CTRADER_ACCOUNT_ID")
        if not all([self._client_id, self._client_secret, account_id]):
            raise RuntimeError(
                "CTRADER_CLIENT_ID / CTRADER_CLIENT_SECRET / CTRADER_ACCOUNT_ID must all be "
                "set in .env — see docs/ctrader_setup.md and run `python ops/ctrader_auth.py`.")
        self._account_id = int(account_id)
        self._token_store = TokenStore(DEFAULT_TOKEN_FILE, self._client_id, self._client_secret)

        match = self._find_account(self.host_demo) or self._find_account(self.host_live)
        if match is None:
            raise RuntimeError(
                f"CTRADER_ACCOUNT_ID={self._account_id} was not found in this token's "
                "authorized account list on either host. Run "
                "`python ops/ctrader_auth.py --list-accounts` to check.")
        self._is_live = bool(match.get("isLive"))
        host = self.host_live if self._is_live else self.host_demo

        self._transport = self._transport_factory(host, self.port, on_event=self._on_event,
                                                  on_reconnect=self._reauth)
        self._transport.connect()
        self._authenticate()
        self._load_symbols()
        self._subscribe_spots()
        self._connected = True
        log.info("connected to cTrader account %s (%s, %s)", self._account_id,
                "LIVE" if self._is_live else "demo", host)
        return True

    def is_live_account(self):
        self._require_connection()
        return self._is_live

    def close(self):
        if self._transport is not None:
            self._transport.close()
        self._connected = False

    def _require_connection(self):
        if not self._connected:
            raise RuntimeError("CTraderBroker.connect() must succeed before any other call.")

    def _find_account(self, host):
        t = self._transport_factory(host, self.port)
        t.connect()
        try:
            t.request(M.APPLICATION_AUTH_REQ,
                     {"clientId": self._client_id, "clientSecret": self._client_secret})
            _, payload = t.request(M.GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ,
                                   {"accessToken": self._token_store.access_token()})
            for acc in payload.get("ctidTraderAccount", []):
                if int(acc["ctidTraderAccountId"]) == self._account_id:
                    return acc
            return None
        except CTraderError as e:
            log.warning("account discovery against %s failed: %s", host, e)
            return None
        finally:
            t.close()

    def _authenticate(self):
        self._transport.request(M.APPLICATION_AUTH_REQ,
                                {"clientId": self._client_id, "clientSecret": self._client_secret})
        self._transport.request(M.ACCOUNT_AUTH_REQ,
                                {"ctidTraderAccountId": self._account_id,
                                 "accessToken": self._token_store.access_token()})

    def _reauth(self):
        """Callback from CTraderTransport after an automatic reconnect: re-establish app +
        account auth and spot subscriptions on the fresh socket."""
        try:
            self._authenticate()
            self._subscribe_spots()
        except Exception:
            log.exception("cTrader re-authentication after reconnect failed — the connection "
                          "is up but likely unusable until the next reconnect cycle")

    # ----- symbols ----------------------------------------------------------------
    def _load_symbols(self):
        _, payload = self._transport.request(M.SYMBOLS_LIST_REQ,
                                             {"ctidTraderAccountId": self._account_id})
        by_name = {s["symbolName"].upper(): s for s in payload.get("symbol", [])}
        asset_to_id, id_to_asset, missing = {}, {}, []
        for asset, acfg in self.cfg["assets"].items():
            name = acfg.get("ctrader")
            if not name:
                continue
            match = by_name.get(name.upper())
            if match is None:
                missing.append((asset, name))
                continue
            sid = match["symbolId"]
            asset_to_id[asset] = sid
            id_to_asset[sid] = asset
        if missing:
            sample = ", ".join(sorted(by_name)[:20])
            raise ValueError(
                "these configured 'ctrader' symbols were not found on this account: " +
                "; ".join(f"{a}={n!r}" for a, n in missing) +
                f". First symbol names available: {sample}... run "
                "`python ops/ctrader_smoke_test.py --symbols` to see the full list and fix "
                "config.json's assets.*.ctrader fields.")
        self._symbols_by_asset, self._id_to_asset = asset_to_id, id_to_asset
        if asset_to_id:
            _, payload = self._transport.request(
                M.SYMBOL_BY_ID_REQ,
                {"ctidTraderAccountId": self._account_id, "symbolId": list(asset_to_id.values())})
            for s in payload.get("symbol", []):
                self._symbol_meta[s["symbolId"]] = s

    def list_symbol_names(self):
        """Every symbol name available on this account -- for ops/ctrader_smoke_test.py
        --symbols, to help fill in config.json's assets.*.ctrader fields correctly."""
        self._require_connection()
        _, payload = self._transport.request(M.SYMBOLS_LIST_REQ,
                                             {"ctidTraderAccountId": self._account_id})
        return sorted(s["symbolName"] for s in payload.get("symbol", []))

    def _symbol_id(self, asset):
        sid = self._symbols_by_asset.get(asset)
        if sid is None:
            raise ValueError(f"{asset} has no 'ctrader' symbol resolved for this account — "
                             "see config.json's assets.*.ctrader and connect().")
        return sid

    def _digits(self, symbol_id):
        return self._symbol_meta.get(symbol_id, {}).get("digits", 5)

    # ----- volume conversion (BrokerBase adapters own this; the engine only knows units) --
    def units_to_volume(self, asset, units):
        """Engine units -> cTrader's integer volume (hundredths of a unit), floored to the
        symbol's stepVolume and clamped to [minVolume, maxVolume]. Floors (never rounds up)
        so a rounding adjustment can only reduce risk, never inflate it. Returns 0 if the
        sized units round down below the symbol's minimum tradable volume -- the caller must
        treat that as a refused order, not silently trade the minimum instead."""
        sid = self._symbol_id(asset)
        meta = self._symbol_meta.get(sid, {})
        step = meta.get("stepVolume") or M.VOLUME_SCALE
        min_vol = meta.get("minVolume") or step
        max_vol = meta.get("maxVolume")
        raw = int(units * M.VOLUME_SCALE)
        raw = (raw // step) * step
        if max_vol:
            raw = min(raw, max_vol)
        return raw if raw >= min_vol else 0

    def volume_to_units(self, volume):
        return volume / M.VOLUME_SCALE

    # ----- BrokerBase: market data ------------------------------------------------
    def get_bars(self, asset, interval="1m", lookback_minutes=300):
        self._require_connection()
        sid = self._symbol_id(asset)
        now_ms = int(time.time() * 1000)
        from_ms = now_ms - lookback_minutes * 60_000
        _, payload = self._transport.request(
            M.GET_TRENDBARS_REQ,
            {"ctidTraderAccountId": self._account_id, "symbolId": sid, "period": M.PERIOD_M1,
             "fromTimestamp": from_ms, "toTimestamp": now_ms, "count": lookback_minutes + 5},
            timeout=15)
        bars = payload.get("trendbar", [])
        if not bars:
            return None
        rows, idx = [], []
        for b in bars:
            low = b["low"] / M.PRICE_SCALE
            idx.append(datetime.fromtimestamp(b["utcTimestampInMinutes"] * 60, tz=timezone.utc))
            rows.append({
                "Open": low + b.get("deltaOpen", 0) / M.PRICE_SCALE,
                "High": low + b.get("deltaHigh", 0) / M.PRICE_SCALE,
                "Low": low,
                "Close": low + b.get("deltaClose", 0) / M.PRICE_SCALE,
                "Volume": b.get("volume", 0) / M.VOLUME_SCALE,
            })
        return pd.DataFrame(rows, index=pd.DatetimeIndex(idx, tz=timezone.utc)).sort_index()

    def get_price(self, asset):
        self._require_connection()
        px = self._last_spot.get(asset)
        if px is not None:
            return px
        bars = self.get_bars(asset, lookback_minutes=5)
        return float(bars["Close"].iloc[-1]) if bars is not None and not bars.empty else None

    # ----- BrokerBase: orders ------------------------------------------------------
    def place_order(self, asset, direction, units, stop, target):
        self._require_connection()
        sid = self._symbol_id(asset)
        volume = self.units_to_volume(asset, units)
        if volume <= 0:
            raise ValueError(f"{asset}: sized units ({units}) round down to zero volume at "
                             "this symbol's step/minimum — order refused, not silently resized.")
        digits = self._digits(sid)
        payload = {
            "ctidTraderAccountId": self._account_id, "symbolId": sid,
            "orderType": M.ORDER_TYPE_MARKET,
            "tradeSide": M.BUY if direction == "LONG" else M.SELL,
            "volume": volume,
            "stopLoss": round(stop, digits), "takeProfit": round(target, digits),
            "label": self.order_label, "comment": "trading-agent",
        }
        self._transport.request(M.NEW_ORDER_REQ, payload)
        event = self._wait_for_fill(sid, timeout=FILL_TIMEOUT_SECONDS)
        if event.get("executionType") == M.EXEC_ORDER_REJECTED:
            raise CTraderError(event.get("errorCode", "ORDER_REJECTED"),
                               "cTrader rejected the order")
        deal = event.get("deal", {})
        position = event.get("position", {})
        fill_price = deal.get("executionPrice")
        filled_volume = deal.get("filledVolume", volume)
        pos = {
            "asset": asset,
            "direction": direction,
            "entry_price": round(fill_price, digits) if fill_price is not None else None,
            "units": self.volume_to_units(filled_volume),
            "stop": round(stop, digits),
            "target": round(target, digits),
            "position_id": position.get("positionId"),
            "provider": "ctrader",
        }
        self._positions_cache[asset] = pos
        log.info("OPEN %s %s %.4f units (cTrader position %s) @ %.4f stop %.4f target %.4f",
                 direction, asset, pos["units"], pos["position_id"], pos["entry_price"] or 0.0,
                 pos["stop"], pos["target"])
        return pos

    def close_position(self, asset, reason, price=None, when=None):
        self._require_connection()
        pos = self._positions_cache.get(asset) or self.get_positions().get(asset)
        if pos is None:
            return None
        sid = self._symbol_id(asset)
        volume = self.units_to_volume(asset, pos["units"])
        payload = {"ctidTraderAccountId": self._account_id,
                  "positionId": pos["position_id"], "volume": volume}
        self._transport.request(M.CLOSE_POSITION_REQ, payload)
        event = self._wait_for_fill(sid, timeout=FILL_TIMEOUT_SECONDS)
        deal = event.get("deal", {})
        exit_price = deal.get("executionPrice", price)
        self._positions_cache.pop(asset, None)
        trade = dict(pos)
        trade.update({"exit_price": exit_price, "exit_reason": reason})
        log.info("CLOSE %s %s @ %s (%s)", pos["direction"], asset, exit_price, reason)
        return trade

    def get_positions(self):
        self._require_connection()
        _, payload = self._transport.request(M.RECONCILE_REQ,
                                             {"ctidTraderAccountId": self._account_id})
        out = {}
        for p in payload.get("position", []):
            td = p.get("tradeData", {})
            if td.get("label") != self.order_label:
                continue  # not ours -- never manage a position this bot didn't open
            asset = self._id_to_asset.get(td.get("symbolId"))
            if asset is None:
                continue
            pos = {
                "asset": asset,
                "direction": "LONG" if td.get("tradeSide") == M.BUY else "SHORT",
                "entry_price": p.get("price"),
                "units": self.volume_to_units(td.get("volume", 0)),
                "stop": p.get("stopLoss"),
                "target": p.get("takeProfit"),
                "position_id": p.get("positionId"),
                "provider": "ctrader",
            }
            out[asset] = pos
        self._positions_cache = out
        return out

    def get_account_info(self):
        self._require_connection()
        _, payload = self._transport.request(M.TRADER_REQ,
                                             {"ctidTraderAccountId": self._account_id})
        trader = payload.get("trader", {})
        money_digits = trader.get("moneyDigits", 2)
        balance = trader.get("balance", 0) / (10 ** money_digits)
        unrealized = 0.0
        for asset, pos in self.get_positions().items():
            px = self.get_price(asset)
            if px is None or pos.get("entry_price") is None:
                continue
            direction = 1 if pos["direction"] == "LONG" else -1
            unrealized += (px - pos["entry_price"]) * pos["units"] * direction
        return {
            "balance": round(balance, 2),
            "equity": round(balance + unrealized, 2),
            "currency": self.currency,
            "account_id": self._account_id,
            "is_live": self._is_live,
        }

    # ----- event stream --------------------------------------------------------------
    def _subscribe_spots(self):
        if not self._symbols_by_asset:
            return
        self._transport.request(M.SUBSCRIBE_SPOTS_REQ,
                                {"ctidTraderAccountId": self._account_id,
                                 "symbolId": list(self._symbols_by_asset.values())})

    def _on_event(self, payload_type, payload):
        if payload_type == M.SPOT_EVENT:
            asset = self._id_to_asset.get(payload.get("symbolId"))
            bid = payload.get("bid")
            if asset is not None and bid is not None:
                self._last_spot[asset] = bid / M.PRICE_SCALE
        elif payload_type == M.EXECUTION_EVENT:
            self._handle_execution_event(payload)
        elif payload_type == M.ORDER_ERROR_EVENT:
            log.warning("cTrader order error event: %s", payload)
            sid = payload.get("positionId")  # best-effort; ORDER_ERROR_EVENT may lack symbolId
            self._resolve_waiter(sid, {"executionType": M.EXEC_ORDER_REJECTED, **payload})
        elif payload_type == M.ACCOUNT_DISCONNECT_EVENT:
            log.warning("cTrader account disconnected server-side: %s", payload)
            self._connected = False

    def _handle_execution_event(self, payload):
        exec_type = payload.get("executionType")
        symbol_id = self._extract_symbol_id(payload)
        if symbol_id is not None and exec_type in (
                M.EXEC_ORDER_FILLED, M.EXEC_ORDER_PARTIAL_FILL, M.EXEC_ORDER_REJECTED):
            self._resolve_waiter(symbol_id, payload)

    @staticmethod
    def _extract_symbol_id(payload):
        deal = payload.get("deal")
        if deal:
            return deal.get("symbolId")
        for key in ("order", "position"):
            obj = payload.get(key)
            if obj and obj.get("tradeData"):
                return obj["tradeData"].get("symbolId")
        return None

    def _wait_for_fill(self, symbol_id, timeout):
        event = threading.Event()
        waiter = {"event": event, "result": None}
        with self._fill_lock:
            self._fill_waiters[symbol_id] = waiter
        try:
            if not event.wait(timeout):
                raise CTraderError("FILL_TIMEOUT",
                                   f"no execution event for symbolId {symbol_id} within {timeout}s")
        finally:
            with self._fill_lock:
                self._fill_waiters.pop(symbol_id, None)
        return waiter["result"]

    def _resolve_waiter(self, symbol_id, payload):
        with self._fill_lock:
            waiter = self._fill_waiters.get(symbol_id)
        if waiter is not None:
            waiter["result"] = payload
            waiter["event"].set()

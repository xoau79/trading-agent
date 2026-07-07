"""A minimal, synchronous-friendly JSON-over-WebSocket client for the cTrader Open API
(Spotware), connecting to demo.ctraderapi.com/live.ctraderapi.com on port 5036.

Why hand-rolled instead of the official `ctrader-open-api` PyPI package: that package wraps
protobuf messages in Twisted's reactor, which is a global, non-restartable event loop that
has to be bridged into synchronous code with `blockingCallFromThread` -- an awkward fit for
this bot's plain 45-second polling loop that starts and stops a couple of times a day via
Windows Task Scheduler. Spotware's port-5036 proxy accepts the exact same messages as JSON
(see messages.py's docstring for a confirmed example), so a small client built on
`websocket-client` (a single, actively-maintained, pure-Python dependency) gets the same
capability without pulling in Twisted or a protobuf toolchain, and is trivially testable with
a fake socket (see tests/test_ctrader_transport.py).
"""
import json
import logging
import threading
import time
import uuid

from . import messages as M

log = logging.getLogger("broker.ctrader.transport")

HEARTBEAT_INTERVAL_SECONDS = 10  # Spotware recommends a heartbeat roughly every 10s of idle
DEFAULT_TIMEOUT_SECONDS = 10
MAX_REQUESTS_PER_SECOND = 4  # comfortably under Spotware's documented 50/s (5/s historical)
MAX_BACKOFF_SECONDS = 30


class CTraderError(Exception):
    def __init__(self, error_code, description=""):
        super().__init__(f"{error_code}: {description}" if description else str(error_code))
        self.error_code = error_code
        self.description = description


class CTraderTransport:
    def __init__(self, host, port=5036, on_event=None, on_reconnect=None, ws_factory=None):
        self.host = host
        self.port = port
        self.on_event = on_event or (lambda payload_type, payload: None)
        self.on_reconnect = on_reconnect  # called (no args) after an automatic reconnect
        self._ws_factory = ws_factory or self._default_ws_factory
        self._ws = None
        self._pending = {}  # clientMsgId -> {"event": Event, "result": (payloadType, payload)}
        self._pending_lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._reader_thread = None
        self._heartbeat_thread = None
        self._stop = threading.Event()
        self._connected = threading.Event()
        self._last_send_monotonic = 0.0

    def _default_ws_factory(self):
        import websocket
        return websocket.create_connection(f"wss://{self.host}:{self.port}",
                                           timeout=DEFAULT_TIMEOUT_SECONDS)

    # ----- lifecycle ----------------------------------------------------------------
    def connect(self):
        self._stop.clear()
        self._ws = self._ws_factory()
        self._connected.set()
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True,
                                               name="ctrader-reader")
        self._reader_thread.start()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True,
                                                  name="ctrader-heartbeat")
        self._heartbeat_thread.start()

    def close(self):
        self._stop.set()
        self._connected.clear()
        try:
            if self._ws is not None:
                self._ws.close()
        except Exception:
            pass
        with self._pending_lock:
            for entry in self._pending.values():
                entry["event"].set()  # unblock any waiters -- request() will raise TIMEOUT
            self._pending.clear()

    @property
    def connected(self):
        return self._connected.is_set()

    # ----- reader / reconnect ---------------------------------------------------------
    def _read_loop(self):
        backoff = 1
        while not self._stop.is_set():
            try:
                raw = self._ws.recv()
            except Exception as e:
                if self._stop.is_set():
                    return
                log.warning("cTrader transport read error (%s) — reconnecting in %ds", e, backoff)
                self._connected.clear()
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
                if not self._reconnect_once():
                    continue
                backoff = 1
                continue
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except (TypeError, ValueError):
                log.warning("cTrader transport: dropped a non-JSON frame")
                continue
            self._dispatch(msg)

    def _reconnect_once(self):
        if self._stop.is_set():
            return False
        try:
            self._ws = self._ws_factory()
        except Exception as e:
            log.warning("cTrader reconnect attempt failed: %s", e)
            return False
        self._connected.set()
        log.info("cTrader transport reconnected — re-authenticating")
        if self.on_reconnect:
            try:
                self.on_reconnect()
            except Exception:
                log.exception("on_reconnect callback raised — connection is up but the "
                              "adapter may not have re-authenticated correctly")
        return True

    def _dispatch(self, msg):
        payload_type = msg.get("payloadType")
        payload = msg.get("payload") or {}
        client_msg_id = msg.get("clientMsgId")
        if client_msg_id:
            with self._pending_lock:
                entry = self._pending.get(client_msg_id)
            if entry is not None:
                entry["result"] = (payload_type, payload)
                entry["event"].set()
                return
        if payload_type == M.HEARTBEAT_EVENT:
            return  # nothing to act on beyond having read it (keeps the socket alive)
        self.on_event(payload_type, payload)

    def _heartbeat_loop(self):
        while not self._stop.wait(HEARTBEAT_INTERVAL_SECONDS):
            if self._connected.is_set():
                try:
                    self._send_raw(M.envelope(M.HEARTBEAT_EVENT, {}))
                except Exception as e:
                    log.warning("cTrader heartbeat send failed: %s", e)

    # ----- sending --------------------------------------------------------------------
    def _send_raw(self, msg):
        with self._send_lock:
            now = time.monotonic()
            min_interval = 1.0 / MAX_REQUESTS_PER_SECOND
            wait = self._last_send_monotonic + min_interval - now
            if wait > 0:
                time.sleep(wait)
            self._last_send_monotonic = time.monotonic()
            self._ws.send(json.dumps(msg))

    def request(self, payload_type, payload, timeout=DEFAULT_TIMEOUT_SECONDS):
        """Send a request and block for its correlated response (by clientMsgId).
        Raises CTraderError on a timeout or an explicit error response/event."""
        if not self._connected.is_set():
            raise CTraderError("NOT_CONNECTED", "cTrader transport is not connected")
        client_msg_id = uuid.uuid4().hex
        entry = {"event": threading.Event(), "result": None}
        with self._pending_lock:
            self._pending[client_msg_id] = entry
        try:
            self._send_raw(M.envelope(payload_type, payload, client_msg_id))
            if not entry["event"].wait(timeout):
                raise CTraderError("TIMEOUT",
                                   f"no response to payloadType {payload_type} within {timeout}s")
        finally:
            with self._pending_lock:
                self._pending.pop(client_msg_id, None)
        resp_type, resp_payload = entry["result"]
        if resp_type in M.ERROR_PAYLOAD_TYPES:
            raise CTraderError(resp_payload.get("errorCode", "UNKNOWN_ERROR"),
                               resp_payload.get("description", ""))
        return resp_type, resp_payload

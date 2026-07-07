"""Unit tests for broker/ctrader/transport.py using a fake WebSocket (queue-based, no real
network) injected via the `ws_factory` hook -- covers request/response correlation, error
mapping, unsolicited event dispatch, and reconnect + re-auth callback behavior.
"""
import json
import queue
import time

import pytest

from broker.ctrader import messages as M
from broker.ctrader.transport import CTraderError, CTraderTransport


class FakeWS:
    """Stands in for a websocket-client connection. `on_send` (if given) is called with
    (self, raw_json_str) synchronously inside send() -- tests use it to script replies by
    pushing JSON strings into self.incoming, exactly like a real server would."""

    def __init__(self, on_send=None):
        self.sent = []
        self.incoming = queue.Queue()
        self.closed = False
        self.fail_next_recv = False
        self.on_send = on_send

    def send(self, data):
        self.sent.append(data)
        if self.on_send:
            self.on_send(self, data)

    def recv(self):
        while True:
            if self.fail_next_recv:
                self.fail_next_recv = False
                raise ConnectionError("simulated drop")
            try:
                return self.incoming.get(timeout=0.05)
            except queue.Empty:
                if self.closed:
                    raise ConnectionError("closed")
                continue

    def close(self):
        self.closed = True


def _echo_handler(ws, raw):
    """A minimal fake cTrader server: answers auth requests, errors on anything else."""
    msg = json.loads(raw)
    pt, cid = msg["payloadType"], msg.get("clientMsgId")
    if pt == M.HEARTBEAT_EVENT:
        return  # real server doesn't ack client heartbeats either
    if pt == M.APPLICATION_AUTH_REQ:
        resp = M.envelope(M.APPLICATION_AUTH_RES, {}, cid)
    elif pt == M.ACCOUNT_AUTH_REQ:
        resp = M.envelope(M.ACCOUNT_AUTH_RES,
                          {"ctidTraderAccountId": msg["payload"]["ctidTraderAccountId"]}, cid)
    else:
        resp = M.envelope(M.ERROR_RES, {"errorCode": "UNKNOWN", "description": "no handler"}, cid)
    ws.incoming.put(json.dumps(resp))


def _wait_until(predicate, timeout=3.0, interval=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def test_request_response_roundtrip():
    def factory():
        return FakeWS(on_send=_echo_handler)

    t = CTraderTransport(host="fake", ws_factory=factory)
    t.connect()
    try:
        resp_type, payload = t.request(M.APPLICATION_AUTH_REQ,
                                       {"clientId": "x", "clientSecret": "y"})
        assert resp_type == M.APPLICATION_AUTH_RES

        resp_type, payload = t.request(M.ACCOUNT_AUTH_REQ,
                                       {"ctidTraderAccountId": 42, "accessToken": "tok"})
        assert resp_type == M.ACCOUNT_AUTH_RES
        assert payload["ctidTraderAccountId"] == 42
    finally:
        t.close()


def test_error_response_raises_ctrader_error():
    def factory():
        return FakeWS(on_send=_echo_handler)

    t = CTraderTransport(host="fake", ws_factory=factory)
    t.connect()
    try:
        with pytest.raises(CTraderError) as exc:
            t.request(M.SYMBOLS_LIST_REQ, {"ctidTraderAccountId": 1})
        assert exc.value.error_code == "UNKNOWN"
    finally:
        t.close()


def test_request_timeout_raises_ctrader_error():
    def factory():
        return FakeWS()  # never replies

    t = CTraderTransport(host="fake", ws_factory=factory)
    t.connect()
    try:
        with pytest.raises(CTraderError) as exc:
            t.request(M.TRADER_REQ, {"ctidTraderAccountId": 1}, timeout=0.2)
        assert exc.value.error_code == "TIMEOUT"
    finally:
        t.close()


def test_unsolicited_event_dispatched_to_on_event():
    events = []
    holder = {}

    def factory():
        ws = FakeWS()
        holder["ws"] = ws
        return ws

    t = CTraderTransport(host="fake", on_event=lambda pt, p: events.append((pt, p)),
                         ws_factory=factory)
    t.connect()
    try:
        holder["ws"].incoming.put(json.dumps(
            M.envelope(M.SPOT_EVENT, {"symbolId": 1, "bid": 123456})))
        assert _wait_until(lambda: len(events) == 1)
        assert events[0][0] == M.SPOT_EVENT
        assert events[0][1]["bid"] == 123456
    finally:
        t.close()


def test_heartbeat_event_is_not_forwarded_to_on_event():
    events = []
    holder = {}

    def factory():
        ws = FakeWS()
        holder["ws"] = ws
        return ws

    t = CTraderTransport(host="fake", on_event=lambda pt, p: events.append((pt, p)),
                         ws_factory=factory)
    t.connect()
    try:
        holder["ws"].incoming.put(json.dumps(M.envelope(M.HEARTBEAT_EVENT, {})))
        time.sleep(0.2)
        assert events == []
    finally:
        t.close()


def test_reconnect_gets_a_new_socket_and_calls_on_reconnect():
    instances = []

    def factory():
        ws = FakeWS()
        instances.append(ws)
        return ws

    reconnect_calls = []
    t = CTraderTransport(host="fake", on_reconnect=lambda: reconnect_calls.append(1),
                         ws_factory=factory)
    t.connect()
    try:
        assert len(instances) == 1
        instances[0].fail_next_recv = True
        assert _wait_until(lambda: len(instances) == 2, timeout=5.0)
        assert _wait_until(lambda: len(reconnect_calls) == 1, timeout=2.0)
    finally:
        t.close()

"""cTrader Open API (Spotware) message constants: payloadType numbers, key enum values, and
the JSON envelope shape used over the WebSocket JSON endpoint (port 5036).

Every numeric value below was pulled from Spotware's own published proto source,
https://github.com/spotware/openapi-proto-messages (OpenApiModelMessages.proto for the
ProtoOAPayloadType/enum definitions, OpenApiCommonModelMessages.proto for the common
ProtoPayloadType, OpenApiMessages.proto for request/response field shapes) -- NOT guessed.
Still, re-check this file against that repository (or https://help.ctrader.com/open-api/
if you can reach it) before trusting it against a real account: Spotware can add/change
messages, and this file is the ONE place all magic numbers live, by design, so a correction
never has to touch transport.py or ctrader_broker.py.

JSON envelope (confirmed from help.ctrader.com/open-api/sending-receiving-json/, quoting
their own example verbatim):
    {"clientMsgId": "cm_id_2", "payloadType": 2100,
     "payload": {"clientId": "...", "clientSecret": "..."}}
Responses echo the same "clientMsgId" back; unsolicited events (spots, execution, heartbeat,
disconnect) have no clientMsgId and are identified by payloadType alone. Field names inside
"payload" are the proto field names verbatim (camelCase) -- there is no snake_case renaming
in the JSON encoding.
"""

# ---- common (ProtoPayloadType, OpenApiCommonModelMessages.proto) ----------------------
ERROR_RES = 50
HEARTBEAT_EVENT = 51

# ---- ProtoOAPayloadType (OpenApiModelMessages.proto) ----------------------------------
APPLICATION_AUTH_REQ = 2100
APPLICATION_AUTH_RES = 2101
ACCOUNT_AUTH_REQ = 2102
ACCOUNT_AUTH_RES = 2103
VERSION_REQ = 2104
VERSION_RES = 2105
NEW_ORDER_REQ = 2106
TRAILING_SL_CHANGED_EVENT = 2107
CANCEL_ORDER_REQ = 2108
AMEND_ORDER_REQ = 2109
AMEND_POSITION_SLTP_REQ = 2110
CLOSE_POSITION_REQ = 2111
ASSET_LIST_REQ = 2112
ASSET_LIST_RES = 2113
SYMBOLS_LIST_REQ = 2114
SYMBOLS_LIST_RES = 2115
SYMBOL_BY_ID_REQ = 2116
SYMBOL_BY_ID_RES = 2117
SYMBOLS_FOR_CONVERSION_REQ = 2118
SYMBOLS_FOR_CONVERSION_RES = 2119
SYMBOL_CHANGED_EVENT = 2120
TRADER_REQ = 2121
TRADER_RES = 2122
TRADER_UPDATE_EVENT = 2123
RECONCILE_REQ = 2124
RECONCILE_RES = 2125
EXECUTION_EVENT = 2126
SUBSCRIBE_SPOTS_REQ = 2127
SUBSCRIBE_SPOTS_RES = 2128
UNSUBSCRIBE_SPOTS_REQ = 2129
UNSUBSCRIBE_SPOTS_RES = 2130
SPOT_EVENT = 2131
ORDER_ERROR_EVENT = 2132
DEAL_LIST_REQ = 2133
DEAL_LIST_RES = 2134
SUBSCRIBE_LIVE_TRENDBAR_REQ = 2135
UNSUBSCRIBE_LIVE_TRENDBAR_REQ = 2136
GET_TRENDBARS_REQ = 2137
GET_TRENDBARS_RES = 2138
EXPECTED_MARGIN_REQ = 2139
EXPECTED_MARGIN_RES = 2140
MARGIN_CHANGED_EVENT = 2141
OA_ERROR_RES = 2142
CASH_FLOW_HISTORY_LIST_REQ = 2143
CASH_FLOW_HISTORY_LIST_RES = 2144
GET_TICKDATA_REQ = 2145
GET_TICKDATA_RES = 2146
ACCOUNTS_TOKEN_INVALIDATED_EVENT = 2147
CLIENT_DISCONNECT_EVENT = 2148
GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ = 2149
GET_ACCOUNTS_BY_ACCESS_TOKEN_RES = 2150
GET_CTID_PROFILE_BY_TOKEN_REQ = 2151
GET_CTID_PROFILE_BY_TOKEN_RES = 2152
ASSET_CLASS_LIST_REQ = 2153
ASSET_CLASS_LIST_RES = 2154
DEPTH_EVENT = 2155
SUBSCRIBE_DEPTH_QUOTES_REQ = 2156
SUBSCRIBE_DEPTH_QUOTES_RES = 2157
UNSUBSCRIBE_DEPTH_QUOTES_REQ = 2158
UNSUBSCRIBE_DEPTH_QUOTES_RES = 2159
SYMBOL_CATEGORY_REQ = 2160
SYMBOL_CATEGORY_RES = 2161
ACCOUNT_LOGOUT_REQ = 2162
ACCOUNT_LOGOUT_RES = 2163
ACCOUNT_DISCONNECT_EVENT = 2164
SUBSCRIBE_LIVE_TRENDBAR_RES = 2165
UNSUBSCRIBE_LIVE_TRENDBAR_RES = 2166
MARGIN_CALL_LIST_REQ = 2167
MARGIN_CALL_LIST_RES = 2168
MARGIN_CALL_UPDATE_REQ = 2169
MARGIN_CALL_UPDATE_RES = 2170
MARGIN_CALL_UPDATE_EVENT = 2171
MARGIN_CALL_TRIGGER_EVENT = 2172
REFRESH_TOKEN_REQ = 2173
REFRESH_TOKEN_RES = 2174
ORDER_LIST_REQ = 2175
ORDER_LIST_RES = 2176

# Response payloadTypes we treat as terminal/error for request correlation.
ERROR_PAYLOAD_TYPES = frozenset({ERROR_RES, OA_ERROR_RES, ORDER_ERROR_EVENT})

# Event payloadTypes that arrive unsolicited (no matching clientMsgId) and get routed to the
# transport's on_event callback instead of a pending request.
EVENT_PAYLOAD_TYPES = frozenset({
    HEARTBEAT_EVENT, SPOT_EVENT, EXECUTION_EVENT, ORDER_ERROR_EVENT,
    ACCOUNT_DISCONNECT_EVENT, ACCOUNTS_TOKEN_INVALIDATED_EVENT, CLIENT_DISCONNECT_EVENT,
    TRADER_UPDATE_EVENT, SYMBOL_CHANGED_EVENT, TRAILING_SL_CHANGED_EVENT,
    MARGIN_CHANGED_EVENT, MARGIN_CALL_UPDATE_EVENT, MARGIN_CALL_TRIGGER_EVENT, DEPTH_EVENT,
})

# ---- ProtoOATradeSide ------------------------------------------------------------------
BUY = 1
SELL = 2

# ---- ProtoOAOrderType (only MARKET is used by this bot) --------------------------------
ORDER_TYPE_MARKET = 1

# ---- ProtoOATrendbarPeriod --------------------------------------------------------------
PERIOD_M1 = 1

# ---- ProtoOAExecutionType ---------------------------------------------------------------
EXEC_ORDER_ACCEPTED = 2
EXEC_ORDER_FILLED = 3
EXEC_ORDER_REPLACED = 4
EXEC_ORDER_CANCELLED = 5
EXEC_ORDER_EXPIRED = 6
EXEC_ORDER_REJECTED = 7
EXEC_ORDER_CANCEL_REJECTED = 8
EXEC_SWAP = 9
EXEC_DEPOSIT_WITHDRAW = 10
EXEC_ORDER_PARTIAL_FILL = 11
EXEC_BONUS_DEPOSIT_WITHDRAW = 12

# ---- ProtoOAPositionStatus ---------------------------------------------------------------
POSITION_STATUS_OPEN = 1
POSITION_STATUS_CLOSED = 2
POSITION_STATUS_CREATED = 3
POSITION_STATUS_ERROR = 4

# Price/volume scaling. Confirmed from the proto field docstrings themselves (not inferred):
# ProtoOASpotEvent.bid/ask: "Bid/Ask price in 1/100000 units" -- trendbar prices use the same
# fixed 1e5 scale (verify with ops/ctrader_smoke_test.py, which cross-checks a GOLD trendbar
# against Yahoo's price for exactly this reason). ProtoOATradeData.volume /
# ProtoOAClosePositionReq.volume: "Volume in cents (e.g. 1000 in protocol means 10.00 units)"
# -- i.e. hundredths of a unit, regardless of symbol.
PRICE_SCALE = 100_000
VOLUME_SCALE = 100


def envelope(payload_type, payload, client_msg_id=None):
    msg = {"payloadType": payload_type, "payload": payload}
    if client_msg_id is not None:
        msg["clientMsgId"] = client_msg_id
    return msg

"""cTrader (Spotware) OAuth2 -- authorization-code flow and token storage.

Endpoints confirmed against Spotware's own documentation/community examples (not the wire
protocol's proto files, so double-check if either ever 404s):
  - authorize: https://connect.spotware.com/apps/auth  (browser redirect, response_type=code,
    client_id, redirect_uri, scope=trading)
  - token exchange/refresh: https://openapi.ctrader.com/apps/token (POST form-encoded)
Access tokens are long-lived (~2,628,000 seconds / 30 days per Spotware's docs) but this
still refreshes proactively so a session never starts on an expired token.

Token response field casing (accessToken/refreshToken/expiresIn vs. access_token/
refresh_token/expires_in) isn't independently confirmed from a captured live example --
_normalize_token_response() accepts either. If the real response uses different field names
entirely, this raises CTraderAuthError with the raw body so it's obvious what to fix.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

AUTH_URL = "https://connect.spotware.com/apps/auth"
TOKEN_URL = "https://openapi.ctrader.com/apps/token"
REFRESH_MARGIN_SECONDS = 600  # refresh 10 min before expiry, not exactly at expiry


class CTraderAuthError(RuntimeError):
    pass


def build_authorize_url(client_id, redirect_uri, scope="trading"):
    params = {"response_type": "code", "client_id": client_id,
              "redirect_uri": redirect_uri, "scope": scope}
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def exchange_code(client_id, client_secret, redirect_uri, code):
    data = {"grant_type": "authorization_code", "code": code,
            "redirect_uri": redirect_uri, "client_id": client_id,
            "client_secret": client_secret}
    return _post_token(data)


def refresh_access_token(client_id, client_secret, refresh_token):
    data = {"grant_type": "refresh_token", "refresh_token": refresh_token,
            "client_id": client_id, "client_secret": client_secret}
    return _post_token(data)


def _post_token(data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise CTraderAuthError(
            f"token request failed: HTTP {e.code} — {e.read().decode('utf-8', 'replace')}"
        ) from e
    return _normalize_token_response(json.loads(raw))


def _normalize_token_response(body):
    def pick(*names):
        for n in names:
            if n in body:
                return body[n]
        return None

    access_token = pick("accessToken", "access_token")
    refresh_token = pick("refreshToken", "refresh_token")
    expires_in = pick("expiresIn", "expires_in")
    if not access_token or not refresh_token:
        raise CTraderAuthError(
            f"unexpected token response shape (fix broker/ctrader/auth.py's field names to "
            f"match): {body!r}")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": int(expires_in) if expires_in is not None else 2_628_000,
        "obtained_utc": time.time(),
    }


class TokenStore:
    """Persists {access_token, refresh_token, expires_in, obtained_utc} to a gitignored JSON
    file (default: ctrader_tokens.json, repo root) and auto-refreshes on access. Never logs
    token values."""

    def __init__(self, path, client_id, client_secret):
        self.path = Path(path)
        self.client_id = client_id
        self.client_secret = client_secret
        self._data = None

    def _load(self):
        if self._data is None:
            if not self.path.exists():
                raise CTraderAuthError(
                    f"{self.path} not found — run `python ops/ctrader_auth.py` first to "
                    "authorize this app and obtain a token.")
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        return self._data

    def save(self, token):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        tmp = str(self.path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(token, f)
        os.replace(tmp, self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass  # best-effort on platforms without POSIX permissions (e.g. some Windows setups)
        self._data = token

    def access_token(self):
        data = self._load()
        expires_at = data["obtained_utc"] + data["expires_in"]
        if time.time() >= expires_at - REFRESH_MARGIN_SECONDS:
            data = refresh_access_token(self.client_id, self.client_secret, data["refresh_token"])
            self.save(data)
        return data["access_token"]

    def force_refresh(self):
        """Unconditional refresh, regardless of expiry -- for ops/ctrader_auth.py --refresh."""
        data = self._load()
        data = refresh_access_token(self.client_id, self.client_secret, data["refresh_token"])
        self.save(data)
        return data["access_token"]

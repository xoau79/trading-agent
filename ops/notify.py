"""Shared Discord notifier for the ops/ scripts (watchdog, digests, reports, smoke tests).

Same webhook, same failure posture as agent.py's own `_discord()`: never raises (a
notification failure must never break the calling script's exit code), truncated to
Discord's message cap, a short timeout so a slow/unreachable webhook can't hang a scheduled
task. Kept separate from agent.py because these scripts run standalone (no TradingAgent
instance) -- both read the same DISCORD_WEBHOOK_URL from .env.
"""
import json
import logging
import os
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")

log = logging.getLogger("ops.notify")


def discord_post(content, username="Trading Agent Ops", dry_run=False):
    """Post `content` to the configured Discord webhook. Returns True on success (or on a
    dry run), False on any failure -- callers can log/ignore as they see fit, but a failure
    here should never raise or change the caller's exit code.
    """
    if dry_run:
        print(f"[dry-run] would post to Discord:\n{content}")
        return True
    url = os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        log.warning("DISCORD_WEBHOOK_URL not set — skipping notification")
        return False
    try:
        body = json.dumps({"content": content[:1900], "username": username}).encode()
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": "TradingAgent/2.0"})
        urllib.request.urlopen(req, timeout=5).read()
        return True
    except Exception as e:
        log.warning("discord notify failed: %s", e)
        return False

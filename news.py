"""News integrations: ForexFactory calendar, RSS headlines, TradingView ratings.

Design principle: news failures must never crash the bot. The calendar
blackout fails toward caution where it can (uses last cached copy), while
TradingView/RSS are nice-to-haves that fail open with a logged warning.
"""
import json
import logging
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

log = logging.getLogger("news")

BASE = Path(__file__).resolve().parent
CACHE_DIR = BASE / "journal"
CAL_CACHE = CACHE_DIR / "ff_calendar_cache.json"
CAL_REFRESH_HOURS = 6


class NewsDesk:
    def __init__(self, cfg):
        self.cfg = cfg["news"]
        self.events = []          # [{title, country, impact, when(datetime utc), top_tier}]
        self.headlines = []       # [{title, published}]
        self._cal_fetched = 0.0
        self._rss_fetched = 0.0

    # ----- ForexFactory calendar -------------------------------------------
    def refresh_calendar(self):
        if time.time() - self._cal_fetched < CAL_REFRESH_HOURS * 3600 and self.events:
            return
        raw = None
        try:
            req = urllib.request.Request(self.cfg["calendar_url"],
                                         headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = json.loads(r.read().decode())
            CAL_CACHE.parent.mkdir(parents=True, exist_ok=True)
            CAL_CACHE.write_text(json.dumps(raw), encoding="utf-8")
        except Exception as e:
            log.warning("calendar fetch failed (%s); falling back to cache", e)
            if CAL_CACHE.exists():
                raw = json.loads(CAL_CACHE.read_text(encoding="utf-8"))
        if raw is None:
            log.warning("no calendar available — news blackout filter inactive")
            return
        events = []
        for e in raw:
            try:
                when = datetime.fromisoformat(e["date"]).astimezone(timezone.utc)
            except Exception:
                continue
            title = e.get("title", "")
            events.append({
                "title": title,
                "country": e.get("country", ""),
                "impact": e.get("impact", ""),
                "when": when,
                "top_tier": any(k.lower() in title.lower()
                                for k in self.cfg["top_tier_keywords"]),
            })
        self.events = events
        self._cal_fetched = time.time()
        log.info("calendar loaded: %d events", len(events))

    def _usd_high_impact(self):
        return [e for e in self.events
                if e["impact"] == "High" and e["country"] == "USD"]

    def in_blackout(self, now_utc):
        """No NEW entries within the configured window around high-impact USD news."""
        before = timedelta(minutes=self.cfg["blackout_minutes_before"])
        after = timedelta(minutes=self.cfg["blackout_minutes_after"])
        for e in self._usd_high_impact():
            if e["when"] - before <= now_utc <= e["when"] + after:
                return e["title"]
        return None

    def must_flatten(self, now_utc):
        """Open positions are closed shortly before top-tier events (FOMC/NFP/CPI)."""
        window = timedelta(minutes=self.cfg["flatten_minutes_before_top_tier"])
        for e in self._usd_high_impact():
            if e["top_tier"] and now_utc <= e["when"] <= now_utc + window:
                return e["title"]
        return None

    def upcoming(self, now_utc, hours=24):
        # "Holiday" is ForexFactory's grey "Non-Economic" impact (bank holidays); show
        # those alongside High/Medium so an upcoming holiday is visible before the bot
        # skips it. The top-events caller in bot.py re-filters to High, so this is safe.
        out = [e for e in self.events
               if now_utc <= e["when"] <= now_utc + timedelta(hours=hours)
               and e["impact"] in ("High", "Medium", "Holiday")]
        return sorted(out, key=lambda e: e["when"])

    def holiday_for_session(self, session_cfg, open_utc):
        """Bank-holiday title if a gating currency is on holiday on the session's local date.

        Reuses the already-fetched calendar. Each session declares the currencies that
        gate it in `holiday_currencies` (asia -> JPY/AUD, newyork -> USD). When one of
        those currencies has a bank holiday on the session's own calendar day, the bot
        stands the whole session down. Returns the holiday title, or None.

        ForexFactory marks bank holidays with impact "Holiday"; we also accept any title
        containing "holiday" as a fallback for named days. Dates are compared in the
        session's local timezone so an AUD/JPY holiday lines up with the Asian day.
        """
        currencies = session_cfg.get("holiday_currencies") or []
        if not currencies:
            return None
        try:
            tz = ZoneInfo(session_cfg["open_tz"])
        except Exception:
            tz = timezone.utc
        session_date = open_utc.astimezone(tz).date()
        for e in self.events:
            if e["country"] not in currencies:
                continue
            title = e.get("title") or ""
            if str(e.get("impact", "")).lower() != "holiday" and "holiday" not in title.lower():
                continue
            if e["when"].astimezone(tz).date() == session_date:
                return title or "Bank Holiday"
        return None

    # ----- RSS headlines -----------------------------------------------------
    def refresh_headlines(self):
        if time.time() - self._rss_fetched < 300:  # at most every 5 min
            return
        try:
            import feedparser
            feed = feedparser.parse(self.cfg["rss_url"])
            self.headlines = [{"title": e.title,
                               "published": getattr(e, "published", "")}
                              for e in feed.entries[:12]]
            self._rss_fetched = time.time()
        except Exception as e:
            log.warning("rss fetch failed: %s", e)

    def top_headlines(self, n=3):
        return [h["title"] for h in self.headlines[:n]]


def get_tv_rating(asset_cfg):
    """TradingView 15-minute technical rating for an asset.

    Returns one of STRONG_BUY/BUY/NEUTRAL/SELL/STRONG_SELL, or 'UNAVAILABLE'
    on any failure (the confluence filter then lets the trade through).
    """
    try:
        from tradingview_ta import TA_Handler, Interval
        tv = asset_cfg["tv_rating"]
        h = TA_Handler(symbol=tv["symbol"], exchange=tv["exchange"],
                       screener=tv["screener"],
                       interval=Interval.INTERVAL_15_MINUTES)
        return h.get_analysis().summary["RECOMMENDATION"]
    except Exception as e:
        log.warning("tradingview rating failed for %s: %s",
                    asset_cfg.get("name", "?"), e)
        return "UNAVAILABLE"


def tv_allows(direction, rating):
    """Confluence rule: don't take a breakout that TradingView actively bets against."""
    if rating in ("UNAVAILABLE", "BACKTEST"):
        return True
    if direction == "LONG":
        return rating not in ("SELL", "STRONG_SELL")
    return rating not in ("BUY", "STRONG_BUY")

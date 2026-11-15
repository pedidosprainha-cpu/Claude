"""High-impact economic calendar filter.

MetaTrader's own calendar is not exposed to Python, so the bot reads the public
weekly ForexFactory feed, caches it on disk and blocks new entries around
scheduled high-impact releases for the currencies involved.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from .config import currencies_of
from .timeutil import UTC, iso


def _fetch(url: str) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (calendar-reader)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


class NewsCalendar:
    def __init__(self, ncfg: dict, cache_path: Path, log=None, fetch=_fetch):
        self.cfg, self.cache_path, self.log, self._fetch = ncfg, Path(cache_path), log, fetch
        self.events: list[dict] = []
        self.fetched_at: datetime | None = None
        self.next_try: datetime | None = None
        self.error: str | None = None
        self._load_cache()

    def _load_cache(self) -> None:
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.fetched_at = datetime.fromisoformat(data["fetched_at"])
            self.events = self._parse(data["raw"])
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def _parse(self, raw: list) -> list[dict]:
        out = []
        for e in raw or []:
            try:
                when = datetime.fromisoformat(str(e["date"])).astimezone(UTC)
                out.append({"time": when, "currency": str(e.get("country", "")).upper(),
                            "impact": str(e.get("impact", "")), "title": str(e.get("title", ""))})
            except (ValueError, KeyError, TypeError):
                continue
        return out

    def refresh(self, now: datetime) -> None:
        if not self.cfg["enabled"]:
            return
        fresh = self.fetched_at and now - self.fetched_at < timedelta(hours=self.cfg["refresh_hours"])
        if fresh or (self.next_try and now < self.next_try):
            return
        try:
            raw = self._fetch(self.cfg["url"])
            self.events = self._parse(raw)
            self.fetched_at, self.error = now, None
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump({"fetched_at": now.isoformat(), "raw": raw}, f)
        except Exception as exc:  # network, JSON, rate limit: keep the previous cache
            self.error = f"{type(exc).__name__}: {exc}"
            self.next_try = now + timedelta(minutes=30)
            if self.log:
                self.log.warning("news calendar refresh failed: %s", self.error)

    def usable(self, now: datetime) -> bool:
        """The cache covers the current week only; older than 6 days is useless."""
        return bool(self.fetched_at and now - self.fetched_at < timedelta(days=6))

    def blocked(self, symbol: str, now: datetime) -> tuple[bool, str]:
        if not self.cfg["enabled"]:
            return False, ""
        if not self.usable(now):
            if self.cfg["fail_mode"] == "block":
                return True, "news calendar unavailable (fail_mode=block)"
            return False, ""
        base, quote = currencies_of(symbol)
        watch = {quote, "ALL"} | ({"USD"} if base.startswith("X") else {base})
        before = timedelta(minutes=self.cfg["block_before_min"])
        after = timedelta(minutes=self.cfg["block_after_min"])
        for e in self.events:
            if e["impact"] in self.cfg["impacts"] and e["currency"] in watch and e["time"] - before <= now <= e["time"] + after:
                return True, f"news: {e['currency']} {e['title']} at {iso(e['time'])}"
        return False, ""

    def upcoming(self, now: datetime, hours: int = 24) -> list[dict]:
        return [{"time": iso(e["time"]), "currency": e["currency"], "title": e["title"]}
                for e in sorted(self.events, key=lambda x: x["time"])
                if e["impact"] in self.cfg["impacts"] and now <= e["time"] <= now + timedelta(hours=hours)]

    def status(self, now: datetime) -> dict:
        return {"enabled": self.cfg["enabled"], "usable": self.usable(now), "events": len(self.events),
                "fetched_at": iso(self.fetched_at) if self.fetched_at else None, "error": self.error,
                "fail_mode": self.cfg["fail_mode"]}

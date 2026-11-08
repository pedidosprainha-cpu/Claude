"""Live executable spot quotes (bid/ask) from Swissquote's public BBO feed."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .http import DataError, Http

URL = "https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/{b}/{q}"
PREFERRED_PROFILES = ("premium", "prime", "standard", "elite")


@dataclass
class Quote:
    bid: float
    ask: float
    ts: datetime
    source: str

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    def age_s(self, now: datetime) -> float:
        return (now - self.ts).total_seconds()


def quote(http: Http, base: str, quote_ccy: str, ttl: float = 3) -> Quote:
    d = http.get(URL.format(b=base, q=quote_ccy), ttl=ttl)
    return parse(d)


def parse(d: list) -> Quote:
    if not d:
        raise DataError("Swissquote: resposta vazia")
    best = None
    for server in d:
        ts = server.get("ts")
        profiles = {p.get("spreadProfile"): p for p in server.get("spreadProfilePrices", [])}
        for name in PREFERRED_PROFILES:
            p = profiles.get(name)
            if p and p.get("bid") and p.get("ask") and p["ask"] >= p["bid"]:
                cand = (ts or 0, p["bid"], p["ask"])
                if best is None or cand[0] > best[0]:
                    best = cand
                break
    if best is None:
        raise DataError("Swissquote: sem preços válidos")
    ts = datetime.fromtimestamp(best[0] / 1000, tz=timezone.utc)
    return Quote(bid=float(best[1]), ask=float(best[2]), ts=ts, source="Swissquote")

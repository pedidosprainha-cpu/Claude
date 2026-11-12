"""Calendário econômico (feed semanal público do ForexFactory/FairEconomy)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from .base import HttpProvider, ProviderError
from .models import utcnow

FEEDS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
]

# Eventos que, mesmo marcados como "Medium", movem fortemente os mercados
CRITICAL_KEYWORDS = ("Non-Farm", "CPI", "Rate Decision", "Interest Rate", "FOMC", "Cash Rate",
                     "Monetary Policy", "Press Conference", "GDP", "Employment Change",
                     "Unemployment Rate", "Retail Sales", "PCE", "Powell", "Lagarde", "Bailey",
                     "Ueda")


@dataclass
class EconEvent:
    title: str
    currency: str
    time: datetime
    impact: str      # High | Medium | Low | Holiday
    forecast: str
    previous: str

    @property
    def critical(self) -> bool:
        return self.impact == "High" or (
            self.impact == "Medium" and any(k.lower() in self.title.lower() for k in CRITICAL_KEYWORDS))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["time"] = self.time.isoformat()
        d["critical"] = self.critical
        d["minutes_to"] = round((self.time - utcnow()).total_seconds() / 60.0, 1)
        return d


class CalendarProvider(HttpProvider):
    name = "calendar"

    def __init__(self, timeout: float = 15.0):
        super().__init__(timeout=timeout)
        self._cache: list[EconEvent] = []
        self._fetched: datetime | None = None

    @staticmethod
    def parse(items: list[dict]) -> list[EconEvent]:
        out = []
        for x in items:
            try:
                t = datetime.fromisoformat(x["date"]).astimezone(timezone.utc)
            except (KeyError, ValueError):
                continue
            out.append(EconEvent(
                title=x.get("title", ""), currency=(x.get("country") or "").upper(), time=t,
                impact=x.get("impact", "Low"), forecast=x.get("forecast", ""),
                previous=x.get("previous", ""),
            ))
        out.sort(key=lambda e: e.time)
        return out

    def events(self, max_age_min: int = 60) -> list[EconEvent]:
        now = utcnow()
        if self._fetched and now - self._fetched < timedelta(minutes=max_age_min) and self._cache:
            return self._cache
        last: Exception | None = None
        for url in FEEDS:
            try:
                data = self.get_json(url)
                self._cache = self.parse(data)
                self._fetched = now
                return self._cache
            except ProviderError as exc:
                last = exc
        if self._cache:
            return self._cache  # usa cache antigo, marcado pelo horário de coleta
        raise ProviderError(f"calendário indisponível: {last}")

    @property
    def fetched_at(self) -> datetime | None:
        return self._fetched

"""Clock helpers: FX trading week, New York rollover, sessions.

Everything is computed from UTC with a hand-rolled US DST rule so the bot has
no dependency on the OS timezone database (Windows ships without one).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

UTC = timezone.utc

TF_SECONDS = {"M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 86400}


def utcnow() -> datetime:
    return datetime.now(UTC)


def _nth_sunday(year: int, month: int, n: int) -> datetime:
    d = datetime(year, month, 1, tzinfo=UTC)
    d += timedelta(days=(6 - d.weekday()) % 7)  # first Sunday
    return d + timedelta(weeks=n - 1)


def ny_offset_hours(dt_utc: datetime) -> int:
    """UTC offset of New York at the given instant (-4 in DST, -5 otherwise)."""
    start = _nth_sunday(dt_utc.year, 3, 2).replace(hour=7)   # 02:00 EST
    end = _nth_sunday(dt_utc.year, 11, 1).replace(hour=6)    # 02:00 EDT
    return -4 if start <= dt_utc < end else -5


def to_ny(dt_utc: datetime) -> datetime:
    """New York wall-clock time as a naive datetime."""
    return (dt_utc + timedelta(hours=ny_offset_hours(dt_utc))).replace(tzinfo=None)


def trading_day(dt_utc: datetime) -> str:
    """FX trading-day label. The day rolls at 17:00 New York."""
    return (to_ny(dt_utc) + timedelta(hours=7)).date().isoformat()


def market_open(dt_utc: datetime) -> bool:
    """Spot FX/metals week: Sunday 17:00 NY to Friday 17:00 NY."""
    ny = to_ny(dt_utc)
    wd, hm = ny.weekday(), ny.hour * 60 + ny.minute
    if wd == 5:
        return False
    if wd == 6:
        return hm >= 17 * 60
    if wd == 4:
        return hm < 17 * 60
    return True


def minutes_to_rollover(dt_utc: datetime) -> int:
    """Signed minutes relative to the nearest 17:00 NY rollover (negative = before)."""
    ny = to_ny(dt_utc)
    hm = ny.hour * 60 + ny.minute
    diff = hm - 17 * 60
    if diff > 12 * 60:
        diff -= 24 * 60
    elif diff < -12 * 60:
        diff += 24 * 60
    return diff


def in_rollover_window(dt_utc: datetime, before_min: int, after_min: int) -> bool:
    """True around the daily rollover, when spreads blow out and fills are poor."""
    m = minutes_to_rollover(dt_utc)
    return -before_min <= m <= after_min


def friday_after(dt_utc: datetime, hour_ny: float) -> bool:
    ny = to_ny(dt_utc)
    return ny.weekday() == 4 and (ny.hour + ny.minute / 60.0) >= hour_ny


def session_name(dt_utc: datetime) -> str:
    """Coarse liquidity session, by UTC hour."""
    h = dt_utc.hour
    if 12 <= h < 16:
        return "overlap"      # London + New York
    if 7 <= h < 12:
        return "london"
    if 16 <= h < 21:
        return "newyork"
    if 0 <= h < 7:
        return "asia"
    return "late"


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def from_ts(ts: float) -> datetime:
    return datetime.fromtimestamp(float(ts), UTC)

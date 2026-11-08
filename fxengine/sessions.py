"""Trading-session clock: market open/closed, active sessions, liquidity factor."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

SESSIONS = {
    "Sydney": (ZoneInfo("Australia/Sydney"), time(7, 0), time(16, 0)),
    "Tóquio": (ZoneInfo("Asia/Tokyo"), time(9, 0), time(18, 0)),
    "Londres": (ZoneInfo("Europe/London"), time(8, 0), time(17, 0)),
    "Nova York": (ZoneInfo("America/New_York"), time(8, 0), time(17, 0)),
}

HOME = {
    "EUR": {"Londres"}, "GBP": {"Londres"}, "CHF": {"Londres"},
    "USD": {"Nova York"}, "CAD": {"Nova York"},
    "JPY": {"Tóquio"}, "AUD": {"Sydney", "Tóquio"}, "NZD": {"Sydney", "Tóquio"},
    "XAU": {"Londres", "Nova York"}, "XAG": {"Londres", "Nova York"},
    "XPT": {"Londres", "Nova York"}, "XPD": {"Londres", "Nova York"},
}


@dataclass
class SessionState:
    active: list[str]
    fx_open: bool
    metals_open: bool
    rollover: bool
    label: str


def _in_session(now: datetime, tz: ZoneInfo, start: time, end: time) -> bool:
    local = now.astimezone(tz)
    if local.weekday() >= 5:
        return False
    return start <= local.time() < end


def fx_open(now: datetime) -> bool:
    """Spot FX: Sunday 17:00 NY -> Friday 17:00 NY."""
    ny = now.astimezone(NY)
    wd, t = ny.weekday(), ny.time()
    if wd == 5:
        return False
    if wd == 6:
        return t >= time(17, 0)
    if wd == 4:
        return t < time(17, 0)
    return True


def metals_open(now: datetime) -> bool:
    """Spot metals: Sunday 18:00 NY -> Friday 17:00 NY, daily break 17:00-18:00 NY."""
    ny = now.astimezone(NY)
    wd, t = ny.weekday(), ny.time()
    if wd == 5:
        return False
    if wd == 6:
        return t >= time(18, 0)
    if wd == 4 and t >= time(17, 0):
        return False
    return not (time(17, 0) <= t < time(18, 0))


def state(now: datetime) -> SessionState:
    active = [n for n, (tz, a, b) in SESSIONS.items() if _in_session(now, tz, a, b)]
    ny_t = now.astimezone(NY).time()
    rollover = time(16, 45) <= ny_t < time(18, 15)
    fo, mo = fx_open(now), metals_open(now)
    if not fo:
        label = "Mercado fechado (fim de semana)"
    elif rollover:
        label = "Rollover NY (spreads largos, liquidez baixa)"
    elif "Londres" in active and "Nova York" in active:
        label = "Sobreposição Londres + Nova York (liquidez máxima)"
    elif active:
        label = " + ".join(active)
    else:
        label = "Entre sessões"
    ny = now.astimezone(NY)
    if fo and ny.weekday() == 6:
        label += " — abertura semanal (gaps e liquidez fina)"
    return SessionState(active, fo, mo, rollover, label)


def liquidity_factor(st: SessionState, base: str, quote: str, is_metal: bool) -> tuple[float, str]:
    if not (st.metals_open if is_metal else st.fx_open):
        return 0.0, "mercado fechado"
    if st.rollover:
        return 0.55, "rollover NY: spread largo"
    act = set(st.active)
    home = HOME.get(base, set()) | HOME.get(quote, set())
    if {"Londres", "Nova York"} <= act:
        return 1.0, "overlap Londres/NY"
    if act & {"Londres", "Nova York"}:
        return (1.0, "sessão principal do ativo") if act & home else (0.92, "sessão ativa")
    if act & home:
        return 0.9, "sessão asiática (moeda local ativa)"
    if act:
        return 0.75, "sessão asiática fora da moeda do par"
    return 0.7, "entre sessões"

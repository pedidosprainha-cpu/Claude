"""Risco de eventos do calendário econômico por instrumento (janelas de bloqueio)."""
from __future__ import annotations

from datetime import datetime, timedelta

from .. import instruments as I
from ..data.calendar import EconEvent


def relevant_currencies(inst: I.Instrument) -> set[str]:
    cur = {inst.base, inst.quote} - {"XAU", "XAG"}
    if inst.kind == "metal":
        cur |= {"USD"}
    return cur


def event_risk(inst: I.Instrument, events: list[EconEvent], now: datetime,
               before_min: int = 60, after_min: int = 30, horizon_h: int = 24) -> dict:
    cur = relevant_currencies(inst)
    rel = [e for e in events if e.currency in cur and e.impact != "Holiday"]
    upcoming = [e for e in rel if now <= e.time <= now + timedelta(hours=horizon_h)]
    recent = [e for e in rel if now - timedelta(minutes=after_min) <= e.time < now]
    crit_up = [e for e in upcoming if e.critical]
    block = None
    nxt = crit_up[0] if crit_up else None
    if nxt and (nxt.time - now) <= timedelta(minutes=before_min):
        block = (f"Evento de alto impacto em {int((nxt.time - now).total_seconds() // 60)} min: "
                 f"{nxt.currency} {nxt.title}")
    crit_recent = [e for e in recent if e.critical]
    if crit_recent and block is None:
        e = crit_recent[-1]
        block = (f"Janela pós-evento ({int((now - e.time).total_seconds() // 60)} min após "
                 f"{e.currency} {e.title}): volatilidade e spreads anormais")
    holidays = [e for e in events if e.currency in cur and e.impact == "Holiday"
                and abs((e.time - now).total_seconds()) < 86400]
    return {
        "blocked": block is not None,
        "reason": block,
        "next_critical": nxt.to_dict() if nxt else None,
        "upcoming": [e.to_dict() for e in upcoming[:8]],
        "holidays": [e.to_dict() for e in holidays],
        "minutes_to_next_critical": round((nxt.time - now).total_seconds() / 60, 1) if nxt else None,
    }

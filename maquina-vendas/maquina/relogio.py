"""Relógio da máquina.

No modo simulação o tempo anda mais rápido (cada "hora" simulada leva alguns
segundos), para você ver dias de operação em poucos minutos.
"""
from datetime import datetime, timedelta, timezone

from . import config, db

try:
    from zoneinfo import ZoneInfo

    FUSO = ZoneInfo("America/Sao_Paulo")
except Exception:  # sem base de fusos no sistema
    FUSO = timezone(timedelta(hours=-3))


def agora():
    if config.MODO == "simulacao":
        inicio = db.cfg("sim_inicio")
        if inicio is None:
            hoje = datetime.now(FUSO).replace(hour=0, minute=0, second=0, microsecond=0)
            inicio = hoje.isoformat()
            db.cfg_definir("sim_inicio", inicio)
        return datetime.fromisoformat(inicio) + timedelta(hours=db.cfg("sim_horas", 0))
    return datetime.now(FUSO)


def agora_iso():
    return agora().isoformat(timespec="seconds")


def hoje():
    return agora().date().isoformat()


def dia_menos(dias):
    return (agora().date() - timedelta(days=dias)).isoformat()


def horas_desde(iso):
    if not iso:
        return float("inf")
    return (agora() - datetime.fromisoformat(iso)).total_seconds() / 3600


def avancar(horas=1):
    db.cfg_definir("sim_horas", db.cfg("sim_horas", 0) + horas)

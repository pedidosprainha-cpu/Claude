"""Trava de gasto: o único caminho para mexer em orçamento passa por aqui.

Nenhuma campanha é criada, reativada ou ganha verba sem que a soma dos
orçamentos ativos caiba no teto diário. O teto diário nunca passa do
TETO_ABSOLUTO definido no servidor.
"""
from . import config, db, relogio
from .util import brl


class GastoBloqueado(Exception):
    pass


def teto():
    return min(float(db.cfg("teto_diario", config.TETO_INICIAL)), config.TETO_ABSOLUTO)


def comprometido(excluir_campanha=None):
    """Soma dos orçamentos diários das campanhas ativas."""
    if excluir_campanha is None:
        return db.valor("SELECT SUM(orcamento_diario) FROM campanhas WHERE status = 'ativa'")
    return db.valor(
        "SELECT SUM(orcamento_diario) FROM campanhas WHERE status = 'ativa' AND id != ?",
        (excluir_campanha,),
    )


def disponivel():
    return round(teto() - comprometido(), 2)


def gasto_hoje():
    return db.valor("SELECT SUM(gasto) FROM metricas WHERE dia = ?", (relogio.hoje(),))


def checar(novo_orcamento, campanha_id=None):
    """Retorna None se o orçamento pode ser usado; senão, o motivo do bloqueio."""
    if db.cfg("pausado"):
        return "A máquina está pausada"
    if novo_orcamento < config.ORCAMENTO_MINIMO:
        return f"Orçamento abaixo do mínimo de {brl(config.ORCAMENTO_MINIMO)}/dia"
    if novo_orcamento > config.TETO_ABSOLUTO:
        return f"Orçamento acima do teto absoluto de {brl(config.TETO_ABSOLUTO)}/dia"
    t = teto()
    if comprometido(campanha_id) + novo_orcamento > t + 0.001:
        return f"Passaria do teto diário de {brl(t)}"
    if gasto_hoje() >= t - 0.01:
        return "O teto de hoje já foi gasto"
    return None


def exigir(novo_orcamento, campanha_id=None):
    motivo = checar(novo_orcamento, campanha_id)
    if motivo:
        raise GastoBloqueado(motivo)

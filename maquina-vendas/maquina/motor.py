"""Motor: o ciclo que roda sozinho e as decisões que chegam do app."""
import json

from . import (avisos, campanhas, config, db, otimizador, produtos, relogio,
               simulador, trava)
from .util import brl


def iniciar():
    db.conn()
    if config.MODO == "simulacao":
        relogio.agora()  # fixa o início da simulação
        produtos.semear_simulacao()
        if not db.valor("SELECT COUNT(*) FROM diario WHERE acao = 'Máquina ligada'"):
            avisos.diario("Máquina ligada", f"Modo simulação, teto de {brl(trava.teto())}/dia, "
                                            f"autonomia \"{db.cfg('autonomia')}\"")
    elif config.MODO == "real":
        raise SystemExit("O modo real entra na etapa 2. Use MAQUINA_MODO=simulacao por enquanto.")
    else:
        raise SystemExit("MAQUINA_MODO deve ser 'simulacao' ou 'real'")


def ciclo(horas=1):
    """Uma volta do motor por hora (simulada ou real)."""
    with db.transacao():
        for _ in range(horas):
            dia_antes = relogio.hoje()
            if config.MODO == "simulacao":
                simulador.simular_hora()
                relogio.avancar(1)
            if relogio.hoje() != dia_antes:
                virar_dia(dia_antes)
            campanhas.verificar_gasto()
            otimizador.executar()


def virar_dia(dia_anterior):
    s = campanhas.stats(dia=dia_anterior)
    total = campanhas.stats()
    sinal = "lucro" if s["lucro"] >= 0 else "prejuízo"
    avisos.alerta(
        "info", f"Resumo de {dia_anterior[8:10]}/{dia_anterior[5:7]}: {sinal} de {brl(abs(s['lucro']))}",
        f"Gasto {brl(s['gasto'])}, {s['vendas']} venda(s), comissão {brl(s['comissao'])}. "
        f"Acumulado: {brl(total['lucro'])}.",
        celular=True,
    )
    campanhas.reativar_pausadas_por_teto()


def decidir(aprovacao_id, aprovar):
    """Aplica a sua decisão sobre um pedido de aprovação."""
    with db.transacao():
        a = db.um("SELECT * FROM aprovacoes WHERE id = ?", (aprovacao_id,))
        if not a or a["status"] != "pendente":
            raise ValueError("Esse pedido já foi decidido")
        detalhe = json.loads(a["detalhe"] or "{}")
        resultado = "ok"
        if a["tipo"] == "criativo":
            db.executar("UPDATE criativos SET status = ? WHERE id = ?",
                        ("aprovado" if aprovar else "rejeitado", a["ref_id"]))
        elif a["tipo"] == "aumento_teto" and aprovar:
            novo = min(float(detalhe["novo_teto"]), config.TETO_ABSOLUTO)
            db.cfg_definir("teto_diario", novo)
            resultado = f"Teto diário agora é {brl(novo)}"
        elif a["tipo"] == "campanha" and not aprovar:
            db.executar("UPDATE criativos SET status = 'rejeitado' WHERE id = ?", (a["ref_id"],))
        elif a["tipo"] == "campanha" and aprovar:
            cr = db.um("SELECT * FROM criativos WHERE id = ?", (a["ref_id"],))
            try:
                campanhas.criar(cr["produto_id"], cr["id"], float(detalhe.get("orcamento", config.ORCAMENTO_TESTE)),
                                "Publicada com sua aprovação")
            except trava.GastoBloqueado as erro:
                resultado = f"Não publicada: {erro}"
        db.executar("UPDATE aprovacoes SET status = ?, decidido_em = ? WHERE id = ?",
                    ("aprovada" if aprovar else "rejeitada", relogio.agora_iso(), aprovacao_id))
        avisos.diario("Decisão sua", f"{'Aprovou' if aprovar else 'Rejeitou'}: {a['titulo']}")
        otimizador.executar()
        return resultado


def ajustar(teto_diario=None, autonomia=None, notificar_vendas=None, sim_auto=None):
    with db.transacao():
        if teto_diario is not None:
            teto_diario = float(teto_diario)
            if not config.ORCAMENTO_MINIMO <= teto_diario <= config.TETO_ABSOLUTO:
                raise ValueError(f"O teto precisa ficar entre {brl(config.ORCAMENTO_MINIMO)} e "
                                 f"{brl(config.TETO_ABSOLUTO)} (teto absoluto do servidor)")
            antigo = trava.teto()
            if teto_diario > antigo:
                raise ValueError("Para aumentar o teto, aprove um pedido da máquina ou mude o servidor. "
                                 "Pelo app só é possível reduzir.")
            db.cfg_definir("teto_diario", teto_diario)
            campanhas.ajustar_ao_teto("Teto diário reduzido no app")
            avisos.diario("Teto alterado", f"{brl(antigo)} → {brl(teto_diario)}")
        if autonomia is not None:
            if autonomia not in config.AUTONOMIAS:
                raise ValueError("Autonomia inválida")
            db.cfg_definir("autonomia", autonomia)
            avisos.diario("Autonomia alterada", autonomia)
        if notificar_vendas is not None:
            db.cfg_definir("notificar_vendas", bool(notificar_vendas))
        if sim_auto is not None:
            db.cfg_definir("sim_auto", bool(sim_auto))

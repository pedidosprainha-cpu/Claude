"""O cérebro da máquina: decide o que pausar, o que escalar e o que testar.

As regras são as de um gestor de tráfego cuidadoso, escritas em código:
1. Corta rápido o que dá prejuízo (sem venda, CTR baixo, ROAS ruim).
2. Aumenta aos poucos (+20%/dia) a verba do que dá lucro, sem passar do teto.
3. Usa a verba que sobra para testar anúncios e produtos novos.
"""
from . import avisos, campanhas, config, criativos, db, produtos, relogio, trava
from .util import brl, num, pct


def _janela(campanha, total=None):
    """Campanhas com mais de JANELA_DIAS dias também são julgadas pelos últimos dias."""
    if relogio.horas_desde(campanha["criada_em"]) >= config.JANELA_DIAS * 24:
        return campanhas.stats(campanha_id=campanha["id"], desde=relogio.dia_menos(config.JANELA_DIAS - 1))
    return total if total is not None else campanhas.stats(campanha_id=campanha["id"])


def avaliar_campanha(c):
    produto = produtos.obter(c["produto_id"])
    comissao = produtos.comissao_valor(produto)
    total = campanhas.stats(campanha_id=c["id"])
    janela = _janela(c, total)

    limite_sem_venda = min(config.FATOR_CORTE_SEM_VENDA * comissao, config.DIAS_TETO_CORTE_SEM_VENDA * trava.teto())
    if total["vendas"] == 0 and total["gasto"] >= limite_sem_venda:
        campanhas.pausar(c["id"], f"Gastou {brl(total['gasto'])} sem nenhuma venda")
        return "pausada"
    if total["impressoes"] >= config.IMPRESSOES_MIN_CTR and total["ctr"] < config.CTR_MINIMO:
        campanhas.pausar(c["id"], f"CTR de {pct(total['ctr'])}: o anúncio não chama atenção")
        return "pausada"
    if total["gasto"] >= config.GASTO_MIN_CORTE_ROAS * comissao and total["roas"] < config.ROAS_CORTE:
        campanhas.pausar(c["id"], f"ROAS {num(total['roas'])}: devolvendo menos do que gasta")
        return "pausada"
    if (janela is not total and janela["gasto"] >= config.GASTO_MIN_CORTE_ROAS * comissao
            and janela["roas"] < config.ROAS_CORTE):
        campanhas.pausar(c["id"], f"Parou de dar resultado: ROAS {num(janela['roas'])} nos últimos "
                                  f"{config.JANELA_DIAS} dias")
        return "pausada"

    if (janela["vendas"] >= config.VENDAS_MIN_ESCALA and janela["roas"] >= config.ROAS_ESCALA
            and relogio.horas_desde(c["ultima_escala_em"] or c["criada_em"]) >= config.HORAS_ENTRE_ESCALAS):
        return escalar(c, janela)
    return "mantida"


def escalar(c, janela):
    novo = round(c["orcamento_diario"] * (1 + config.PASSO_ESCALA), 2)
    motivo = trava.checar(novo, c["id"])
    if motivo is None:
        campanhas.definir_orcamento(c["id"], novo, f"Escalando: ROAS {num(janela['roas'])} com {janela['vendas']} vendas")
        return "escalada"
    # Cabe no teto se outras campanhas piores abrirem espaço.
    if trava.comprometido(c["id"]) + novo > trava.teto():
        _abrir_espaco(c, novo)
        if trava.checar(novo, c["id"]) is None:
            campanhas.definir_orcamento(c["id"], novo, f"Escalando: ROAS {num(janela['roas'])}")
            return "escalada"
        _pedir_teto_maior(c, novo, janela)
    return "no_teto"


def _abrir_espaco(vencedora, novo):
    """Pausa campanhas em teste que estão pior que a vencedora para liberar verba."""
    roas_vencedora = _janela(vencedora)["roas"]
    candidatas = []
    for c in campanhas.ativas():
        if c["id"] == vencedora["id"]:
            continue
        if relogio.horas_desde(c["criada_em"]) < 24:  # teste novo ainda sem dados suficientes
            continue
        s = _janela(c)
        if s["roas"] < 1.0 and s["roas"] < roas_vencedora:
            candidatas.append((s["roas"], c))
    for _, c in sorted(candidatas, key=lambda x: x[0]):
        if trava.comprometido(vencedora["id"]) + novo <= trava.teto():
            break
        campanhas.pausar(c["id"], "Verba transferida para uma campanha que dá lucro")


def _pedir_teto_maior(c, novo, janela):
    teto_atual = trava.teto()
    if teto_atual >= config.TETO_ABSOLUTO:
        if not db.um("SELECT 1 FROM alertas WHERE titulo = 'Teto absoluto atingido' AND criado_em >= ?",
                     (relogio.dia_menos(0),)):
            avisos.alerta("atencao", "Teto absoluto atingido",
                          f"Há campanha lucrativa querendo mais verba, mas o teto absoluto é {brl(config.TETO_ABSOLUTO)}. "
                          "Só muda editando TETO_ABSOLUTO_BRL no servidor.")
        return
    if avisos.tem_pendente("aumento_teto"):
        return
    sugerido = min(config.TETO_ABSOLUTO, round(max(teto_atual + 10, teto_atual + (novo - c["orcamento_diario"]) * 2)))
    produto = produtos.obter(c["produto_id"])
    avisos.pedir_aprovacao(
        "aumento_teto", c["id"],
        f"Aumentar o teto diário de {brl(teto_atual)} para {brl(sugerido)}?",
        {"teto_atual": teto_atual, "novo_teto": sugerido, "campanha_id": c["id"], "produto": produto["nome"],
         "roas": round(janela["roas"], 2), "vendas": janela["vendas"], "lucro": janela["lucro"]},
    )


def _criativos_prontos():
    """Criativos aprovados que ainda não viraram campanha."""
    return db.todos(
        "SELECT cr.* FROM criativos cr JOIN produtos p ON p.id = cr.produto_id "
        "WHERE cr.status = 'aprovado' AND p.status IN ('testando', 'vencedor') "
        "AND NOT EXISTS (SELECT 1 FROM campanhas c WHERE c.criativo_id = cr.id) ORDER BY cr.id"
    )


def publicar_aprovados():
    autonomia = db.cfg("autonomia", "limites")
    for cr in _criativos_prontos():
        if trava.checar(config.ORCAMENTO_TESTE) is not None:
            return
        if autonomia == "manual":
            avisos.pedir_aprovacao("campanha", cr["id"], f"Publicar o anúncio \"{cr['titulo']}\"?",
                                   {"orcamento": config.ORCAMENTO_TESTE})
            continue
        campanhas.criar(cr["produto_id"], cr["id"], config.ORCAMENTO_TESTE, "Teste inicial")


def _precisa_de_criativos(produto_id, limite=config.MAX_CRIATIVOS_POR_PRODUTO):
    total = db.valor("SELECT COUNT(*) FROM criativos WHERE produto_id = ? AND status != 'bloqueado'", (produto_id,))
    em_fila = db.valor(
        "SELECT COUNT(*) FROM criativos cr WHERE cr.produto_id = ? AND (cr.status = 'pendente' OR "
        "(cr.status = 'aprovado' AND NOT EXISTS (SELECT 1 FROM campanhas c WHERE c.criativo_id = cr.id)))",
        (produto_id,))
    ativas = db.valor("SELECT COUNT(*) FROM campanhas WHERE produto_id = ? AND status = 'ativa'", (produto_id,))
    return total < limite and em_fila == 0 and ativas == 0


def planejar_testes():
    """Se sobra verba e não há nada esperando, prepara anúncios novos."""
    if trava.disponivel() < config.ORCAMENTO_TESTE:
        return
    if _criativos_prontos():
        return
    if db.valor("SELECT COUNT(*) FROM criativos WHERE status = 'pendente'") >= config.LIMITE_CRIATIVOS_PENDENTES:
        return
    # 1) Produto vencedor sem campanha rodando (anúncios cansaram) ou produto em
    #    teste que já gastou a primeira rodada: nova rodada de ângulos.
    for p in db.todos("SELECT * FROM produtos WHERE status IN ('vencedor', 'testando') "
                      "ORDER BY status = 'vencedor' DESC, pontuacao DESC"):
        limite = config.MAX_CRIATIVOS_POR_PRODUTO * (2 if p["status"] == "vencedor" else 1)
        if _precisa_de_criativos(p["id"], limite):
            criativos.gerar(p["id"])
            return
    # 2) Produto novo, se ainda cabe mais um em teste.
    em_teste = db.valor("SELECT COUNT(*) FROM produtos WHERE status = 'testando'")
    if em_teste >= config.MAX_PRODUTOS_EM_TESTE:
        return
    candidato = produtos.proximo_candidato()
    if candidato:
        produtos.definir_status(candidato["id"], "testando")
        avisos.diario("Produto entrou em teste", f"#{candidato['id']} {candidato['nome']} (nota {candidato['pontuacao']:.0f})")
        criativos.gerar(candidato["id"])


def avaliar_produtos():
    for p in db.todos("SELECT * FROM produtos WHERE status IN ('testando', 'vencedor')"):
        s = campanhas.stats(produto_id=p["id"])
        if p["status"] == "testando" and s["vendas"] >= 5 and s["lucro"] > 0:
            produtos.definir_status(p["id"], "vencedor")
            avisos.alerta("bom", f"Oferta lucrativa encontrada: {p['nome']}",
                          f"{s['vendas']} vendas, lucro de {brl(s['lucro'])}, ROAS {num(s['roas'])}. "
                          "A máquina vai concentrar verba nela.", celular=True)
            continue
        comissao = produtos.comissao_valor(p)
        limite_teste = min(config.GASTO_MIN_REPROVAR * comissao, config.DIAS_TETO_REPROVAR * trava.teto())
        if (p["status"] == "testando" and s["gasto"] >= limite_teste and s["roas"] < config.ROAS_REPROVAR
                and not _tem_campanha_lucrativa(p["id"])):
            reprovar(p, s)
            continue
        tentou = db.valor("SELECT COUNT(*) FROM criativos WHERE produto_id = ? AND status != 'bloqueado'", (p["id"],))
        ativas = db.valor("SELECT COUNT(*) FROM campanhas WHERE produto_id = ? AND status = 'ativa'", (p["id"],))
        em_fila = db.valor("SELECT COUNT(*) FROM criativos WHERE produto_id = ? AND status IN ('pendente', 'aprovado') "
                           "AND id NOT IN (SELECT criativo_id FROM campanhas)", (p["id"],))
        if (p["status"] == "testando" and ativas == 0 and em_fila == 0
                and tentou >= config.MAX_CRIATIVOS_POR_PRODUTO and s["lucro"] <= 0):
            reprovar(p, s)
            continue
        if s["vendas"] >= 5 and s["reembolsos"] / (s["vendas"] + s["reembolsos"]) > 0.15:
            if not db.um("SELECT 1 FROM alertas WHERE titulo = ?", (f"Muitos reembolsos: {p['nome']}",)):
                avisos.alerta("atencao", f"Muitos reembolsos: {p['nome']}",
                              "Mais de 15% das vendas foram devolvidas. Vale rever se a oferta entrega o que promete.")


def _tem_campanha_lucrativa(produto_id):
    for c in db.todos("SELECT * FROM campanhas WHERE produto_id = ? AND status = 'ativa'", (produto_id,)):
        j = _janela(c)
        if j["vendas"] >= 1 and j["roas"] >= 1.0:
            return True
    return False


def reprovar(p, s):
    """Desiste do produto: pausa as campanhas e descarta anúncios que ainda esperavam."""
    for c in db.todos("SELECT id FROM campanhas WHERE produto_id = ? AND status = 'ativa'", (p["id"],)):
        campanhas.pausar(c["id"], "Produto reprovado")
    for cr in db.todos("SELECT id FROM criativos WHERE produto_id = ? AND status IN ('pendente', 'aprovado') "
                       "AND id NOT IN (SELECT criativo_id FROM campanhas)", (p["id"],)):
        db.executar("UPDATE criativos SET status = 'descartado' WHERE id = ?", (cr["id"],))
        avisos.cancelar_pendentes("criativo", cr["id"])
    produtos.definir_status(p["id"], "reprovado")
    avisos.alerta("info", f"Produto reprovado: {p['nome']}",
                  f"{campanhas.resumo_texto(s)}. Prejuízo de {brl(-s['lucro'])} no teste. Indo para o próximo.")


def executar():
    if db.cfg("pausado"):
        return
    for c in campanhas.ativas():
        avaliar_campanha(c)
    publicar_aprovados()
    planejar_testes()
    publicar_aprovados()  # no modo "total" os anúncios novos já saem aprovados
    avaliar_produtos()

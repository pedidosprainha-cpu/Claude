"""Campanhas: criar, pausar, escalar e medir resultado.

Toda mudança de orçamento passa pela trava de gasto e fica no diário.
"""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import anuncios, avisos, db, relogio, trava
from .util import brl, num, pct


def link_rastreado(link_afiliado, campanha_id):
    """Acrescenta ao link de afiliado os códigos que dizem de qual campanha veio a venda.

    Hotmart e Kiwify devolvem `sck`/`src` no aviso de venda; `utm_*` cobre o resto.
    """
    partes = urlsplit(link_afiliado)
    params = dict(parse_qsl(partes.query))
    codigo = f"cmp{campanha_id}"
    params.update({"sck": codigo, "src": "meta", "utm_source": "meta",
                   "utm_medium": "pago", "utm_campaign": codigo})
    return urlunsplit(partes._replace(query=urlencode(params)))


def obter(campanha_id):
    return db.um("SELECT * FROM campanhas WHERE id = ?", (campanha_id,))


def criar(produto_id, criativo_id, orcamento, motivo=""):
    with db.transacao():
        trava.exigir(orcamento)
        agora = relogio.agora_iso()
        cid = db.executar(
            "INSERT INTO campanhas (produto_id, criativo_id, status, orcamento_diario, "
            "criada_em, atualizada_em) VALUES (?, ?, 'criando', ?, ?, ?)",
            (produto_id, criativo_id, orcamento, agora, agora),
        )
        produto = db.um("SELECT * FROM produtos WHERE id = ?", (produto_id,))
        criativo = db.um("SELECT * FROM criativos WHERE id = ?", (criativo_id,))
        link = link_rastreado(produto["link_afiliado"], cid)
        id_externo = anuncios.plataforma().criar_campanha(obter(cid), produto, criativo, link)
        db.executar(
            "UPDATE campanhas SET status = 'ativa', id_externo = ?, motivo = ? WHERE id = ?",
            (id_externo, motivo or "Em teste", cid),
        )
        avisos.diario(
            "Campanha criada",
            f"#{cid} {produto['nome']} — ângulo \"{criativo['angulo']}\", {brl(orcamento)}/dia. {motivo}".strip(),
        )
    return cid


def definir_orcamento(campanha_id, novo, motivo):
    with db.transacao():
        c = obter(campanha_id)
        trava.exigir(novo, campanha_id)
        anuncios.plataforma().definir_orcamento(c["id_externo"], novo)
        agora = relogio.agora_iso()
        escala = agora if novo > c["orcamento_diario"] else c["ultima_escala_em"]
        db.executar(
            "UPDATE campanhas SET orcamento_diario = ?, ultima_escala_em = ?, motivo = ?, "
            "atualizada_em = ? WHERE id = ?",
            (novo, escala, motivo, agora, campanha_id),
        )
        avisos.diario(
            "Orçamento alterado",
            f"#{campanha_id}: {brl(c['orcamento_diario'])} → {brl(novo)}/dia. {motivo}",
        )


def pausar(campanha_id, motivo, status="pausada"):
    with db.transacao():
        c = obter(campanha_id)
        if c["status"] != "ativa":
            return
        anuncios.plataforma().pausar(c["id_externo"])
        db.executar(
            "UPDATE campanhas SET status = ?, motivo = ?, atualizada_em = ? WHERE id = ?",
            (status, motivo, relogio.agora_iso(), campanha_id),
        )
        avisos.diario("Campanha pausada", f"#{campanha_id}: {motivo}")


def reativar(campanha_id, motivo):
    with db.transacao():
        c = obter(campanha_id)
        trava.exigir(c["orcamento_diario"], campanha_id)
        anuncios.plataforma().ativar(c["id_externo"])
        db.executar(
            "UPDATE campanhas SET status = 'ativa', motivo = ?, atualizada_em = ? WHERE id = ?",
            (motivo, relogio.agora_iso(), campanha_id),
        )
        avisos.diario("Campanha reativada", f"#{campanha_id}: {motivo}")


def ativas():
    return db.todos("SELECT * FROM campanhas WHERE status = 'ativa' ORDER BY id")


# --- Resultados ---------------------------------------------------------------

def stats(campanha_id=None, produto_id=None, dia=None, desde=None):
    """Soma gasto, cliques e comissões (vendas aprovadas) com os filtros dados."""
    fm, am, fv, av = [], [], [], []
    if campanha_id is not None:
        fm.append("m.campanha_id = ?"); am.append(campanha_id)
        fv.append("v.campanha_id = ?"); av.append(campanha_id)
    if produto_id is not None:
        fm.append("c.produto_id = ?"); am.append(produto_id)
        fv.append("v.produto_id = ?"); av.append(produto_id)
    if dia is not None:
        fm.append("m.dia = ?"); am.append(dia)
        fv.append("v.dia = ?"); av.append(dia)
    if desde is not None:
        fm.append("m.dia >= ?"); am.append(desde)
        fv.append("v.dia >= ?"); av.append(desde)
    where_m = (" WHERE " + " AND ".join(fm)) if fm else ""
    where_v = (" AND " + " AND ".join(fv)) if fv else ""
    m = db.um(
        "SELECT COALESCE(SUM(m.impressoes),0) AS impressoes, COALESCE(SUM(m.cliques),0) AS cliques, "
        "COALESCE(SUM(m.visitas),0) AS visitas, COALESCE(SUM(m.gasto),0) AS gasto "
        "FROM metricas m JOIN campanhas c ON c.id = m.campanha_id" + where_m,
        am,
    )
    v = db.um(
        "SELECT COUNT(*) AS vendas, COALESCE(SUM(v.comissao),0) AS comissao, "
        "COALESCE(SUM(v.valor),0) AS faturamento FROM vendas v WHERE v.status = 'aprovada'" + where_v,
        av,
    )
    reemb = db.valor(
        "SELECT COUNT(*) FROM vendas v WHERE v.status IN ('reembolsada','chargeback')" + where_v, av
    )
    r = {**m, **v, "reembolsos": reemb}
    r["gasto"] = round(r["gasto"], 2)
    r["comissao"] = round(r["comissao"], 2)
    r["lucro"] = round(r["comissao"] - r["gasto"], 2)
    r["ctr"] = r["cliques"] / r["impressoes"] if r["impressoes"] else 0.0
    r["roas"] = r["comissao"] / r["gasto"] if r["gasto"] else 0.0
    r["cpa"] = r["gasto"] / r["vendas"] if r["vendas"] else None
    return r


def resumo_texto(s):
    return (f"gasto {brl(s['gasto'])}, {s['vendas']} venda(s), comissão {brl(s['comissao'])}, "
            f"ROAS {num(s['roas'])}, CTR {pct(s['ctr'])}")


def listar():
    linhas = db.todos(
        "SELECT c.*, p.nome AS produto, p.plataforma, cr.angulo, cr.titulo "
        "FROM campanhas c JOIN produtos p ON p.id = c.produto_id "
        "JOIN criativos cr ON cr.id = c.criativo_id "
        "ORDER BY CASE c.status WHEN 'ativa' THEN 0 ELSE 1 END, c.id DESC"
    )
    for linha in linhas:
        linha["stats"] = stats(campanha_id=linha["id"])
        linha["hoje"] = stats(campanha_id=linha["id"], dia=relogio.hoje())
    return linhas


# --- Ações gerais da trava --------------------------------------------------

def verificar_gasto():
    """Se o gasto de hoje chegou no teto, pausa tudo até virar o dia."""
    t = trava.teto()
    gasto = trava.gasto_hoje()
    abertas = ativas()
    if gasto < t - 0.01 or not abertas:
        return
    for c in abertas:
        pausar(c["id"], "Teto diário atingido; volta amanhã", status="pausada_teto")
    nivel = "urgente" if gasto > t * 1.1 else "atencao"
    avisos.alerta(nivel, "Teto diário atingido",
                  f"Gasto de hoje: {brl(gasto)} (teto {brl(t)}). Campanhas pausadas até amanhã.")


def ajustar_ao_teto(motivo):
    """Se o teto baixou, pausa as campanhas de pior resultado até caber."""
    t = trava.teto()
    while trava.comprometido() > t + 0.001:
        piores = sorted(ativas(), key=lambda c: (stats(campanha_id=c["id"])["roas"], -c["id"]))
        if not piores:
            break
        pausar(piores[0]["id"], motivo)


def pausar_tudo():
    db.cfg_definir("pausado", True)
    for c in ativas():
        pausar(c["id"], "Pausa geral acionada no app", status="pausada_geral")
    avisos.alerta("urgente", "Máquina pausada", "Todas as campanhas foram pausadas pelo app.")


def retomar():
    db.cfg_definir("pausado", False)
    voltaram = 0
    for c in db.todos("SELECT * FROM campanhas WHERE status = 'pausada_geral' ORDER BY id"):
        if trava.checar(c["orcamento_diario"], c["id"]) is None:
            reativar(c["id"], "Retomada pelo app")
            voltaram += 1
    avisos.alerta("info", "Máquina retomada", f"{voltaram} campanha(s) voltaram a rodar.")


def reativar_pausadas_por_teto():
    for c in db.todos("SELECT * FROM campanhas WHERE status = 'pausada_teto' ORDER BY id"):
        if trava.checar(c["orcamento_diario"], c["id"]) is None:
            reativar(c["id"], "Novo dia: teto renovado")

"""Leads: quem demonstrou interesse e o quão perto está de comprar.

Cada ação na página de captura soma pontos na hora. Quem passa de 60 pontos
é um lead quente. Contato (nome, e-mail, WhatsApp) só é guardado com
consentimento explícito, como exige a LGPD.
"""
import hashlib
import json
import re

from . import avisos, config, db, relogio

PONTOS = {
    "visita": 5,
    "rolou_50": 10,
    "ficou_30s": 10,
    "voltou": 15,
    "cadastro": 20,
    "clicou_oferta": 25,
    "abandonou_checkout": 30,
}
ROTULOS = {
    "visita": "visitou a página",
    "rolou_50": "leu até a metade",
    "ficou_30s": "ficou mais de 30s",
    "voltou": "voltou outro dia",
    "cadastro": "deixou o contato",
    "clicou_oferta": "clicou na oferta",
    "abandonou_checkout": "abandonou o checkout",
}
EVENTOS_PUBLICOS = {"visita", "rolou_50", "ficou_30s"}
TEXTO_CONSENTIMENTO = (
    "Aceito receber conteúdos e ofertas sobre este assunto por e-mail ou WhatsApp. "
    "Posso pedir a exclusão dos meus dados a qualquer momento."
)


def hash_email(email):
    email = (email or "").strip().lower()
    return hashlib.sha256(email.encode()).hexdigest() if email else ""


def temperatura(pontos):
    if pontos >= config.LEAD_QUENTE:
        return "quente"
    if pontos >= config.LEAD_MORNO:
        return "morno"
    return "frio"


def _obter(visitante, campanha_id):
    lead = db.um("SELECT * FROM leads WHERE visitante = ?", (visitante,))
    if lead:
        return lead
    produto_id = db.valor("SELECT produto_id FROM campanhas WHERE id = ?", (campanha_id,), None)
    agora = relogio.agora_iso()
    db.executar(
        "INSERT INTO leads (visitante, campanha_id, produto_id, criado_em, atualizado_em) VALUES (?, ?, ?, ?, ?)",
        (visitante, campanha_id, produto_id, agora, agora),
    )
    return db.um("SELECT * FROM leads WHERE visitante = ?", (visitante,))


def evento(visitante, campanha_id, tipo):
    if tipo not in PONTOS:
        raise ValueError("Evento desconhecido")
    with db.transacao():
        lead = _obter(visitante, campanha_id)
        if lead["cliente"]:
            return lead
        eventos = json.loads(lead["eventos"] or "{}")
        if tipo == "visita" and eventos.get("visita"):
            if relogio.horas_desde(eventos.get("_ultima_visita")) < 6:
                return lead
            tipo = "voltou"
        limite = 2 if tipo == "voltou" else 1
        if eventos.get(tipo, 0) >= limite:
            return lead
        eventos[tipo] = eventos.get(tipo, 0) + 1
        if tipo in ("visita", "voltou"):
            eventos["_ultima_visita"] = relogio.agora_iso()
        pontos = min(100, lead["pontuacao"] + PONTOS[tipo])
        antes, depois = lead["temperatura"], temperatura(pontos)
        db.executar(
            "UPDATE leads SET pontuacao = ?, temperatura = ?, eventos = ?, atualizado_em = ? WHERE id = ?",
            (pontos, depois, json.dumps(eventos), relogio.agora_iso(), lead["id"]),
        )
        lead = db.um("SELECT * FROM leads WHERE id = ?", (lead["id"],))
        if depois == "quente" and antes != "quente" and lead["consentimento_em"]:
            avisos.alerta(
                "bom",
                f"Lead quente: {lead['nome'] or 'sem nome'} ({pontos} pts)",
                "Fez: " + ", ".join(ROTULOS[k] for k in eventos if k in ROTULOS)
                + ". Bom candidato para remarketing.",
            )
        return lead


def cadastro(visitante, campanha_id, nome, email, whatsapp, consentimento):
    if not consentimento:
        raise ValueError("Para guardar seu contato é preciso marcar o consentimento")
    email = (email or "").strip()
    whatsapp = re.sub(r"\D", "", whatsapp or "")
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("E-mail inválido")
    if whatsapp and not 10 <= len(whatsapp) <= 13:
        raise ValueError("WhatsApp inválido")
    if not email and not whatsapp:
        raise ValueError("Informe e-mail ou WhatsApp")
    with db.transacao():
        lead = _obter(visitante, campanha_id)
        db.executar(
            "UPDATE leads SET nome = ?, email = ?, whatsapp = ?, email_hash = ?, consentimento_em = ?, "
            "atualizado_em = ? WHERE id = ?",
            ((nome or "").strip()[:80], email or None, whatsapp or None, hash_email(email) or None,
             relogio.agora_iso(), relogio.agora_iso(), lead["id"]),
        )
        return evento(visitante, campanha_id, "cadastro")


def marcar_cliente(email_hash):
    if email_hash:
        db.executar(
            "UPDATE leads SET cliente = 1, temperatura = 'cliente', atualizado_em = ? WHERE email_hash = ?",
            (relogio.agora_iso(), email_hash),
        )


def abandono(email_hash):
    """A plataforma avisou que alguém começou a compra e desistiu: sinal fortíssimo."""
    if not email_hash:
        return None
    lead = db.um("SELECT * FROM leads WHERE email_hash = ?", (email_hash,))
    if lead:
        return evento(lead["visitante"], lead["campanha_id"], "abandonou_checkout")
    return None


def listar(filtro=None, limite=100):
    sql = ("SELECT l.id, l.nome, l.email, l.whatsapp, l.pontuacao, l.temperatura, l.eventos, l.cliente, "
           "l.criado_em, l.atualizado_em, p.nome AS produto FROM leads l "
           "LEFT JOIN produtos p ON p.id = l.produto_id WHERE l.consentimento_em IS NOT NULL")
    args = []
    if filtro:
        sql += " AND l.temperatura = ?"
        args.append(filtro)
    sql += " ORDER BY l.cliente ASC, l.pontuacao DESC, l.atualizado_em DESC LIMIT ?"
    args.append(limite)
    linhas = db.todos(sql, args)
    for linha in linhas:
        ev = json.loads(linha.pop("eventos") or "{}")
        linha["acoes"] = [ROTULOS[k] for k in ev if k in ROTULOS]
    return linhas


def contagens():
    r = db.um(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN temperatura = 'quente' THEN 1 ELSE 0 END) AS quentes, "
        "SUM(CASE WHEN temperatura = 'morno' THEN 1 ELSE 0 END) AS mornos, "
        "SUM(cliente) AS clientes FROM leads WHERE consentimento_em IS NOT NULL"
    )
    return {k: int(v or 0) for k, v in r.items()}


def apagar(lead_id):
    """Direito de exclusão da LGPD."""
    db.executar("DELETE FROM leads WHERE id = ?", (lead_id,))
    avisos.diario("Lead apagado", f"#{lead_id} a pedido (LGPD)")

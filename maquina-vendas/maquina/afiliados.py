"""Avisos de venda (webhooks) da Hotmart, Kiwify e Eduzz.

Cada plataforma manda os dados num formato diferente; aqui tudo vira um
EventoVenda igual. O código `cmp<N>` que a máquina coloca no link de
afiliado volta no aviso e diz de qual campanha veio a venda.

ATENÇÃO (etapa 2): os formatos abaixo seguem a documentação pública das
plataformas, mas precisam ser conferidos com um aviso real de cada uma antes
de ligar o dinheiro de verdade. O da Eduzz é o que tem mais variações.
"""
import hashlib
import hmac
import re
from dataclasses import dataclass

from . import avisos, db, leads, relogio
from .util import brl


@dataclass
class EventoVenda:
    plataforma: str
    transacao: str
    status: str  # aprovada | reembolsada | chargeback | cancelada | pendente | abandono | ignorar
    produto_externo: str = ""
    produto_nome: str = ""
    valor: float = 0.0
    comissao: float = 0.0
    rastreio: str = ""
    comprador_email: str = ""


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


# --- Hotmart ------------------------------------------------------------------

_STATUS_HOTMART = {
    "PURCHASE_APPROVED": "aprovada",
    "PURCHASE_COMPLETE": "aprovada",
    "PURCHASE_REFUNDED": "reembolsada",
    "PURCHASE_CHARGEBACK": "chargeback",
    "PURCHASE_CANCELED": "cancelada",
    "PURCHASE_EXPIRED": "cancelada",
    "PURCHASE_PROTEST": "pendente",
    "PURCHASE_DELAYED": "pendente",
    "PURCHASE_BILLET_PRINTED": "pendente",
    "PURCHASE_OUT_OF_SHOPPING_CART": "abandono",
}


def normalizar_hotmart(p):
    d = p.get("data") or {}
    compra = d.get("purchase") or {}
    produto = d.get("product") or {}
    comissoes = d.get("commissions") or []
    minha = next((c for c in comissoes if str(c.get("source", "")).upper() == "AFFILIATE"), None)
    origem = compra.get("origin") or {}
    return EventoVenda(
        plataforma="hotmart",
        transacao=str(compra.get("transaction") or p.get("id") or ""),
        status=_STATUS_HOTMART.get(str(p.get("event", "")).upper(), "ignorar"),
        produto_externo=str(produto.get("id") or ""),
        produto_nome=str(produto.get("name") or ""),
        valor=_num((compra.get("price") or {}).get("value")),
        comissao=_num((minha or {}).get("value")),
        rastreio=str(origem.get("sck") or origem.get("src") or origem.get("xcod") or ""),
        comprador_email=str((d.get("buyer") or {}).get("email") or ""),
    )


def validar_hotmart(cabecalhos, token):
    recebido = cabecalhos.get("x-hotmart-hottok", "")
    return bool(token) and hmac.compare_digest(recebido, token)


# --- Kiwify -------------------------------------------------------------------

_STATUS_KIWIFY = {
    "paid": "aprovada",
    "approved": "aprovada",
    "refunded": "reembolsada",
    "chargedback": "chargeback",
    "refused": "cancelada",
    "canceled": "cancelada",
    "waiting_payment": "pendente",
}


def normalizar_kiwify(p):
    comissoes = p.get("Commissions") or {}
    rastreio = p.get("TrackingParameters") or {}
    produto = p.get("Product") or {}
    status = _STATUS_KIWIFY.get(str(p.get("order_status", "")).lower(), "ignorar")
    if str(p.get("webhook_event_type", "")).lower() == "abandoned_cart":
        status = "abandono"
    # A Kiwify manda valores em centavos.
    return EventoVenda(
        plataforma="kiwify",
        transacao=str(p.get("order_id") or p.get("id") or ""),
        status=status,
        produto_externo=str(produto.get("product_id") or ""),
        produto_nome=str(produto.get("product_name") or ""),
        valor=_num(comissoes.get("charge_amount")) / 100,
        comissao=_num(comissoes.get("my_commission")) / 100,
        rastreio=str(rastreio.get("sck") or rastreio.get("src") or rastreio.get("utm_campaign") or ""),
        comprador_email=str((p.get("Customer") or {}).get("email") or ""),
    )


def validar_kiwify(corpo, assinatura, token):
    if not token or not assinatura:
        return False
    esperado = hmac.new(token.encode(), corpo, hashlib.sha1).hexdigest()
    return hmac.compare_digest(esperado, assinatura)


# --- Eduzz --------------------------------------------------------------------

_STATUS_EDUZZ_LEGADO = {"1": "pendente", "3": "aprovada", "4": "cancelada", "6": "pendente", "7": "reembolsada"}


def normalizar_eduzz(p):
    if "trans_cod" in p:  # formato antigo (formulário)
        return EventoVenda(
            plataforma="eduzz",
            transacao=str(p.get("trans_cod")),
            status=_STATUS_EDUZZ_LEGADO.get(str(p.get("trans_status")), "ignorar"),
            produto_externo=str(p.get("product_cod") or ""),
            produto_nome=str(p.get("product_name") or ""),
            valor=_num(p.get("trans_value")),
            comissao=_num(p.get("aff_value")),
            rastreio=str(p.get("tracker") or p.get("utm_campaign") or ""),
            comprador_email=str(p.get("cus_email") or ""),
        )
    evento = str(p.get("event", "")).lower()
    d = p.get("data") or {}
    if evento.endswith("invoice_paid"):
        status = "aprovada"
    elif evento.endswith("invoice_refunded"):
        status = "reembolsada"
    elif evento.endswith(("invoice_canceled", "invoice_expired")):
        status = "cancelada"
    elif evento.endswith(("invoice_opened", "invoice_waiting_payment")):
        status = "pendente"
    elif evento.endswith("cart_abandonment"):
        status = "abandono"
    else:
        status = "ignorar"
    itens = d.get("items") or [{}]
    utm = d.get("utm") or {}
    return EventoVenda(
        plataforma="eduzz",
        transacao=str(d.get("id") or p.get("id") or ""),
        status=status,
        produto_externo=str(itens[0].get("productId") or ""),
        produto_nome=str(itens[0].get("name") or ""),
        valor=_num((d.get("price") or {}).get("value")),
        comissao=_num((d.get("commission") or {}).get("value")),
        rastreio=str(d.get("tracker") or utm.get("campaign") or ""),
        comprador_email=str((d.get("buyer") or {}).get("email") or ""),
    )


NORMALIZADORES = {"hotmart": normalizar_hotmart, "kiwify": normalizar_kiwify, "eduzz": normalizar_eduzz}


# --- Registro -----------------------------------------------------------------

def _campanha_do_rastreio(rastreio):
    achado = re.search(r"cmp(\d+)", rastreio or "")
    if not achado:
        return None
    return db.um("SELECT * FROM campanhas WHERE id = ?", (int(achado.group(1)),))


def registrar(ev):
    """Grava a venda (sem duplicar) e avisa o que for importante."""
    if ev.status == "ignorar" or not ev.transacao:
        return {"ok": True, "ignorado": True}
    email_hash = leads.hash_email(ev.comprador_email)
    if ev.status == "abandono":
        leads.abandono(email_hash)
        return {"ok": True, "abandono": True}

    campanha = _campanha_do_rastreio(ev.rastreio)
    produto = None
    if ev.produto_externo:
        produto = db.um("SELECT * FROM produtos WHERE plataforma = ? AND id_externo = ?",
                        (ev.plataforma, ev.produto_externo))
    if produto is None and campanha:
        produto = db.um("SELECT * FROM produtos WHERE id = ?", (campanha["produto_id"],))
    comissao = ev.comissao
    estimada = False
    if comissao <= 0 and produto and ev.status == "aprovada":
        comissao = round(produto["preco"] * produto["comissao_pct"] / 100, 2)
        estimada = True

    agora = relogio.agora_iso()
    nome = (produto or {}).get("nome") or ev.produto_nome or "produto"
    with db.transacao():
        existente = db.um("SELECT * FROM vendas WHERE plataforma = ? AND transacao = ?",
                          (ev.plataforma, ev.transacao))
        if existente:
            if existente["status"] == ev.status:
                return {"ok": True, "duplicado": True}
            db.executar("UPDATE vendas SET status = ?, atualizada_em = ? WHERE id = ?",
                        (ev.status, agora, existente["id"]))
            if ev.status in ("reembolsada", "chargeback") and existente["status"] == "aprovada":
                avisos.alerta("atencao", f"Reembolso: -{brl(existente['comissao'])}",
                              f"{nome} ({ev.plataforma}).")
                avisos.diario("Venda estornada", f"{ev.plataforma} {ev.transacao}: {ev.status}")
            elif ev.status == "aprovada":
                _avisar_venda(nome, existente["comissao"], ev.plataforma)
                leads.marcar_cliente(email_hash)
            return {"ok": True, "atualizado": True}

        db.executar(
            "INSERT INTO vendas (plataforma, transacao, produto_id, campanha_id, valor, comissao, status, "
            "comprador_hash, dia, recebida_em, atualizada_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ev.plataforma, ev.transacao, (produto or {}).get("id"), (campanha or {}).get("id"),
             ev.valor, comissao, ev.status, email_hash or None, relogio.hoje(), agora, agora),
        )
        if ev.status == "aprovada":
            _avisar_venda(nome, comissao, ev.plataforma)
            leads.marcar_cliente(email_hash)
            if estimada:
                avisos.diario("Comissão estimada", f"{ev.plataforma} {ev.transacao}: aviso veio sem comissão")
    return {"ok": True, "novo": True}


def _avisar_venda(nome, comissao, plataforma):
    avisos.alerta("bom", f"Venda! +{brl(comissao)}", f"{nome} ({plataforma})",
                  celular=bool(db.cfg("notificar_vendas", True)))


def processar(plataforma, payload):
    return registrar(NORMALIZADORES[plataforma](payload))

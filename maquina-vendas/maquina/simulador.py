"""Simulador de mercado: faz o papel do Meta Ads e das plataformas de afiliado.

A cada hora simulada, gasta o orçamento das campanhas ativas, gera
impressões, cliques, visitas, leads e vendas. As vendas e reembolsos chegam
pelo MESMO caminho dos avisos reais (formato Hotmart/Kiwify/Eduzz), então a
simulação testa o código que vai rodar com dinheiro de verdade.

A máquina não enxerga as taxas escondidas (`sim_conv`, `sim_ctr`): ela
precisa descobrir o que funciona testando.
"""
import math
import random
import uuid

from . import afiliados, campanhas, db, leads, relogio, trava

_PERFIL_BRUTO = [0.35, 0.25, 0.2, 0.2, 0.25, 0.4, 0.6, 0.9, 1.1, 1.2, 1.25, 1.3,
                 1.35, 1.3, 1.25, 1.25, 1.3, 1.35, 1.45, 1.5, 1.5, 1.35, 1.0, 0.6]
PERFIL_HORA = [x * 24 / sum(_PERFIL_BRUTO) for x in _PERFIL_BRUTO]  # média 1

_NOMES = ["Ana", "Bruno", "Carla", "Daniel", "Eduarda", "Felipe", "Gabriela", "Henrique", "Isabela",
          "João", "Karina", "Lucas", "Mariana", "Nicolas", "Patrícia", "Rafael", "Sabrina", "Thiago",
          "Vanessa", "William"]


def binom(n, p):
    if n <= 0 or p <= 0:
        return 0
    if n < 60:
        return sum(1 for _ in range(n) if random.random() < p)
    media, dp = n * p, math.sqrt(n * p * (1 - p))
    return max(0, min(n, round(random.gauss(media, dp))))


def _aprendizado(campanha_id):
    """O algoritmo do Meta entrega melhor depois de aprender com as vendas."""
    vendas = db.valor("SELECT COUNT(*) FROM vendas WHERE campanha_id = ? AND status = 'aprovada'", (campanha_id,))
    return 0.7 + 0.3 * min(1.0, vendas / 8)


def _fadiga(campanha):
    """O mesmo anúncio cansa o público com o tempo."""
    dias = relogio.horas_desde(campanha["criada_em"]) / 24
    return max(0.6, 1 - 0.012 * dias)


def payload(produto, campanha_id, transacao, status, email):
    """Monta o aviso de venda no formato de cada plataforma."""
    preco = produto["preco"]
    comissao = round(preco * produto["comissao_pct"] / 100, 2)
    codigo = f"cmp{campanha_id}"
    plataforma = produto["plataforma"]
    if plataforma == "hotmart":
        evento = {"aprovada": "PURCHASE_APPROVED", "reembolsada": "PURCHASE_REFUNDED",
                  "abandono": "PURCHASE_OUT_OF_SHOPPING_CART"}[status]
        return {
            "id": str(uuid.uuid4()), "event": evento, "version": "2.0.0",
            "data": {
                "product": {"id": produto["id_externo"], "name": produto["nome"]},
                "buyer": {"email": email},
                "purchase": {"transaction": transacao, "price": {"value": preco, "currency_value": "BRL"},
                             "origin": {"sck": codigo, "src": "meta"}},
                "commissions": [{"value": round(preco * 0.099, 2), "source": "MARKETPLACE"},
                                {"value": comissao, "source": "AFFILIATE"}],
            },
        }
    if plataforma == "kiwify":
        return {
            "order_id": transacao,
            "order_status": {"aprovada": "paid", "reembolsada": "refunded", "abandono": "waiting_payment"}[status],
            "webhook_event_type": {"aprovada": "order_approved", "reembolsada": "order_refunded",
                                   "abandono": "abandoned_cart"}[status],
            "Product": {"product_id": produto["id_externo"], "product_name": produto["nome"]},
            "Customer": {"email": email},
            "Commissions": {"charge_amount": int(round(preco * 100)), "my_commission": int(round(comissao * 100))},
            "TrackingParameters": {"sck": codigo, "src": "meta", "utm_campaign": codigo},
        }
    evento = {"aprovada": "myeduzz.invoice_paid", "reembolsada": "myeduzz.invoice_refunded",
              "abandono": "myeduzz.cart_abandonment"}[status]
    return {
        "id": str(uuid.uuid4()), "event": evento,
        "data": {"id": transacao, "items": [{"productId": produto["id_externo"], "name": produto["nome"]}],
                 "price": {"value": preco}, "commission": {"value": comissao},
                 "utm": {"campaign": codigo}, "buyer": {"email": email}},
    }


def _lead_aleatorio(campanha_id):
    return db.um(
        "SELECT * FROM leads WHERE campanha_id = ? AND cliente = 0 AND email IS NOT NULL "
        "ORDER BY RANDOM() LIMIT 1", (campanha_id,))


def _gerar_leads(campanha, produto, visitas):
    cid = campanha["id"]
    for _ in range(binom(visitas, 0.06)):
        visitante = "sim-" + uuid.uuid4().hex[:12]
        leads.evento(visitante, cid, "visita")
        if random.random() < 0.7:
            leads.evento(visitante, cid, "rolou_50")
        if random.random() < 0.5:
            leads.evento(visitante, cid, "ficou_30s")
        nome = random.choice(_NOMES)
        email = f"{nome.lower().replace('ã', 'a').replace('í', 'i').replace('ç', 'c')}.{uuid.uuid4().hex[:5]}@example.com"
        leads.cadastro(visitante, cid, f"{nome} (simulado)", email, "", True)
        if random.random() < 0.35:
            leads.evento(visitante, cid, "clicou_oferta")
            if random.random() < 0.25:
                afiliados.processar(produto["plataforma"],
                                    payload(produto, cid, str(uuid.uuid4()), "abandono", email))
    # Leads antigos que voltam à página.
    for _ in range(3):
        if random.random() < 0.12:
            lead = _lead_aleatorio(cid)
            if lead:
                leads.evento(lead["visitante"], cid, "visita")
                if random.random() < 0.4:
                    leads.evento(lead["visitante"], cid, "clicou_oferta")


def _gerar_venda(campanha, produto):
    lead = _lead_aleatorio(campanha["id"]) if random.random() < 0.4 else None
    email = lead["email"] if lead else f"comprador.{uuid.uuid4().hex[:6]}@example.com"
    transacao = ("HP" if produto["plataforma"] == "hotmart" else "TX") + uuid.uuid4().hex[:10].upper()
    afiliados.processar(produto["plataforma"], payload(produto, campanha["id"], transacao, "aprovada", email))


def _gerar_reembolsos():
    recentes = db.todos(
        "SELECT v.*, p.reembolso_pct FROM vendas v JOIN produtos p ON p.id = v.produto_id "
        "WHERE v.status = 'aprovada' AND v.dia >= ?", (relogio.dia_menos(7),))
    for venda in recentes:
        chance_hora = (venda["reembolso_pct"] or 0) / 100 / 168
        if random.random() < chance_hora:
            produto = db.um("SELECT * FROM produtos WHERE id = ?", (venda["produto_id"],))
            afiliados.processar(produto["plataforma"],
                                payload(produto, venda["campanha_id"], venda["transacao"], "reembolsada", ""))


def simular_hora():
    dia = relogio.hoje()
    hora = relogio.agora().hour
    teto = trava.teto()
    gasto_dia = trava.gasto_hoje()
    for c in campanhas.ativas():
        restante = teto - gasto_dia
        if restante <= 0.005:  # a conta tem limite de gasto: a plataforma para de entregar
            break
        produto = db.um("SELECT * FROM produtos WHERE id = ?", (c["produto_id"],))
        criativo = db.um("SELECT * FROM criativos WHERE id = ?", (c["criativo_id"],))
        gasto = c["orcamento_diario"] / 24 * PERFIL_HORA[hora] * random.uniform(0.8, 1.2)
        gasto = round(min(gasto, restante), 2)
        impressoes = int(gasto / random.uniform(12, 24) * 1000)  # CPM de R$12 a R$24
        cliques = binom(impressoes, (criativo["sim_ctr"] or 0.01) * _fadiga(c))
        visitas = binom(cliques, 0.82)  # parte dos cliques não espera a página abrir
        db.executar(
            "INSERT INTO metricas (campanha_id, dia, impressoes, cliques, visitas, gasto) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(campanha_id, dia) DO UPDATE SET impressoes = impressoes + excluded.impressoes, "
            "cliques = cliques + excluded.cliques, visitas = visitas + excluded.visitas, "
            "gasto = ROUND(gasto + excluded.gasto, 2)",
            (c["id"], dia, impressoes, cliques, visitas, gasto),
        )
        gasto_dia += gasto
        _gerar_leads(c, produto, visitas)
        for _ in range(binom(visitas, (produto["sim_conv"] or 0) * _aprendizado(c["id"]))):
            _gerar_venda(c, produto)
    _gerar_reembolsos()

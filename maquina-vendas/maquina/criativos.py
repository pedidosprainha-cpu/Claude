"""Criação dos textos dos anúncios (criativos).

Com uma chave da API da Anthropic configurada, quem escreve é o Claude; sem
chave, a máquina usa modelos prontos. Todo texto passa pelo pente-fino de
política antes de ir para aprovação ou publicação.
"""
import json
import os
import random

from . import avisos, config, db, politica, relogio

CTAS = {
    "LEARN_MORE": "Saiba mais",
    "SHOP_NOW": "Comprar agora",
    "SIGN_UP": "Cadastre-se",
    "GET_OFFER": "Ver oferta",
}

ANGULOS = ["benefício direto", "curiosidade", "objeção de tempo", "prova social",
           "passo a passo", "identificação com o problema"]

_SISTEMA = """Você é redator de anúncios para Facebook e Instagram (Meta Ads) no Brasil, \
especialista em produtos digitais vendidos por afiliados.

Regras obrigatórias (política de anúncios do Meta e Código de Defesa do Consumidor):
- Nunca afirme nem insinue características pessoais de quem lê (peso, saúde, dívidas, \
estado emocional, aparência, estado civil). Proibido: "Você está acima do peso?", "Você tem dívidas?".
- Nunca prometa resultado garantido, renda, valores de ganho, cura, prazos milagrosos ou "sem esforço".
- Nada de "antes e depois", CAIXA ALTA, "clique aqui", pontuação exagerada ou escassez falsa.
- Seja honesto: fale do que o produto ensina ou entrega, não de resultados que dependem da pessoa.

Formato de cada anúncio:
- titulo: até 40 caracteres.
- texto: texto principal, até 125 caracteres, tom conversado, português do Brasil.
- descricao: até 30 caracteres.
- cta: um destes códigos: LEARN_MORE, SHOP_NOW, SIGN_UP, GET_OFFER.
- angulo: nome curto da abordagem usada."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "criativos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "angulo": {"type": "string"},
                    "titulo": {"type": "string"},
                    "texto": {"type": "string"},
                    "descricao": {"type": "string"},
                    "cta": {"type": "string", "enum": list(CTAS)},
                },
                "required": ["angulo", "titulo", "texto", "descricao", "cta"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["criativos"],
    "additionalProperties": False,
}


def ia_disponivel():
    if config.IA_CRIATIVOS == "desligada":
        return False
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def gerar_com_ia(produto, quantidade, angulos_usados):
    import anthropic

    pedido = (
        f"Produto: {produto['nome']}\n"
        f"Nicho: {produto.get('nicho') or '-'}\n"
        f"O que a pessoa aprende ou consegue fazer: {produto.get('beneficio') or '-'}\n"
        f"Para quem é: {produto.get('publico') or '-'}\n"
        f"Preço: R$ {produto['preco']:.2f}\n"
        f"Ângulos já testados (use outros): {', '.join(angulos_usados) or 'nenhum'}\n\n"
        f"Escreva {quantidade} anúncios diferentes entre si, cada um com um ângulo distinto."
    )
    cliente = anthropic.Anthropic()
    resposta = cliente.beta.messages.create(
        model=config.MODELO_IA,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": _SCHEMA},
        },
        system=_SISTEMA,
        messages=[{"role": "user", "content": pedido}],
    )
    if resposta.stop_reason != "end_turn":
        raise RuntimeError(f"A IA não terminou o texto (motivo: {resposta.stop_reason})")
    texto = next(b.text for b in resposta.content if b.type == "text")
    return json.loads(texto)["criativos"][:quantidade]


def _corta(texto, limite):
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def gerar_com_modelos(produto, quantidade, angulos_usados):
    beneficio = (produto.get("beneficio") or "aprender algo novo").rstrip(".")
    nome = produto["nome"].replace(" (exemplo)", "")
    def cabe(*opcoes):
        return next((o for o in opcoes if len(o) <= 40), opcoes[-1])

    modelos = {
        "benefício direto": (cabe(f"Aprenda a {beneficio}", f"Aprenda com o {nome}", "Aprenda no seu ritmo"), f"{nome}: um passo a passo para {beneficio}, no seu ritmo.", "Acesso imediato", "LEARN_MORE"),
        "curiosidade": ("O método que está chamando atenção", f"Veja como o {nome} ensina a {beneficio} e decida se é para você.", "Conheça o método", "LEARN_MORE"),
        "objeção de tempo": ("Pouco tempo? Comece com 20 min", f"Aulas curtas para quem quer {beneficio} sem complicar.", "Aulas curtas", "LEARN_MORE"),
        "prova social": ("Veja a opinião de quem já fez", f"Conheça a experiência de quem fez o {nome} antes de decidir.", "Veja os depoimentos", "LEARN_MORE"),
        "passo a passo": ("Do zero, um passo de cada vez", f"Conteúdo organizado em etapas para {beneficio}. Garantia de 7 dias.", "Garantia de 7 dias", "SHOP_NOW"),
        "identificação com o problema": ("Feito para quem está começando", f"Se {beneficio} sempre pareceu difícil, o {nome} explica do básico.", "Explicação do básico", "LEARN_MORE"),
    }
    livres = [a for a in ANGULOS if a not in angulos_usados] or ANGULOS
    escolhidos = livres[:quantidade]
    return [
        {"angulo": a, "titulo": modelos[a][0], "texto": modelos[a][1], "descricao": modelos[a][2], "cta": modelos[a][3]}
        for a in escolhidos
    ]


def gerar(produto_id, quantidade=config.CRIATIVOS_POR_RODADA):
    """Cria criativos novos para o produto e os coloca na fila certa.

    - Bloqueados pela política: descartados (ficam no diário).
    - Autonomia "total" e sem avisos: já entram aprovados.
    - Senão: vão para a aba Aprovar do app.
    """
    produto = db.um("SELECT * FROM produtos WHERE id = ?", (produto_id,))
    usados = [r["angulo"] for r in db.todos("SELECT angulo FROM criativos WHERE produto_id = ?", (produto_id,))]
    origem = "modelo"
    itens = None
    if ia_disponivel():
        try:
            itens = gerar_com_ia(produto, quantidade, usados)
            origem = "ia"
        except Exception as erro:  # sem crédito, sem rede, recusa etc.
            avisos.diario("IA indisponível", f"Usando modelos prontos. Motivo: {erro}")
    if not itens:
        itens = gerar_com_modelos(produto, quantidade, usados)

    autonomia = db.cfg("autonomia", "limites")
    criados, pendentes = [], 0
    for item in itens:
        titulo = _corta(item["titulo"], 40)
        texto = _corta(item["texto"], 180)
        descricao = _corta(item.get("descricao", ""), 30)
        cta = item["cta"] if item.get("cta") in CTAS else "LEARN_MORE"
        achados = politica.checar(titulo, texto, descricao)
        if politica.bloqueia(achados):
            status = "bloqueado"
        elif autonomia == "total" and not achados:
            status = "aprovado"
        else:
            status = "pendente"
        sim_ctr = random.uniform(0.005, 0.03) if config.MODO == "simulacao" else None
        cid = db.executar(
            "INSERT INTO criativos (produto_id, angulo, titulo, texto, descricao, cta, origem, avisos, "
            "status, sim_ctr, criado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (produto_id, item.get("angulo", "")[:60], titulo, texto, descricao, cta, origem,
             json.dumps(achados, ensure_ascii=False), status, sim_ctr, relogio.agora_iso()),
        )
        if status == "bloqueado":
            avisos.diario("Criativo barrado pela política",
                          f"#{cid} \"{titulo}\": {'; '.join(a['motivo'] for a in achados)}")
        elif status == "pendente":
            avisos.pedir_aprovacao("criativo", cid, f"Anúncio novo para {produto['nome']}",
                                   {"angulo": item.get("angulo", "")}, notificar=False)
            pendentes += 1
        criados.append(cid)
    if pendentes:
        avisos.enviar_celular(f"Preciso da sua decisão: {pendentes} anúncio(s) novo(s) para "
                              f"{produto['nome']}.\nAbra o app na aba Aprovar.")
    avisos.diario("Criativos gerados",
                  f"{len(criados)} para {produto['nome']} ({'Claude' if origem == 'ia' else 'modelos prontos'})")
    return criados

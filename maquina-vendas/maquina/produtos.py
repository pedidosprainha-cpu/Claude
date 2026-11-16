"""Catálogo de produtos de afiliado: pontuação e escolha do próximo a testar.

Hotmart, Kiwify e Eduzz não deixam um robô se afiliar sozinho a produtos
(a afiliação é um clique seu e, às vezes, o produtor precisa aprovar). Por isso
você cadastra os produtos em que já é afiliado e a máquina decide quais testar,
em que ordem, e quais abandonar.
"""
from . import avisos, config, db, relogio, trava
from .util import brl

PLATAFORMAS = ("hotmart", "kiwify", "eduzz")


def comissao_valor(p):
    return round(p["preco"] * p["comissao_pct"] / 100, 2)


def pontuar(p):
    """Nota de 0 a 100 e os motivos dela."""
    comissao = comissao_valor(p)
    motivos = []
    pts = min(40.0, comissao / 150 * 40)
    motivos.append(f"comissão de {brl(comissao)}")
    temperatura = max(0.0, min(100.0, float(p.get("temperatura") or 0)))
    pts += temperatura / 100 * 30
    if 47 <= p["preco"] <= 497:
        pts += 15
        motivos.append("preço bom para tráfego frio")
    else:
        pts += 5
    if p.get("pagina_vendas"):
        pts += 5
    if p.get("beneficio"):
        pts += 5
    if p.get("publico"):
        pts += 5
    reembolso = float(p.get("reembolso_pct") or 0)
    if reembolso:
        pts -= min(20.0, reembolso * 2)
        if reembolso >= 10:
            motivos.append(f"reembolso alto ({reembolso:.0f}%)")
    teto = trava.teto()
    if comissao > 5 * teto:
        pts -= 15
        motivos.append(f"ticket alto para um teto de {brl(teto)}/dia: o teste demora")
    if comissao < config.COMISSAO_MINIMA:
        pts = min(pts, 20.0)
        motivos.append(f"comissão abaixo de {brl(config.COMISSAO_MINIMA)}: difícil pagar o anúncio")
    return round(max(0.0, min(100.0, pts)), 1), motivos


def adicionar(dados, sim_conv=None):
    plataforma = str(dados.get("plataforma", "")).lower()
    if plataforma not in PLATAFORMAS:
        raise ValueError("Plataforma deve ser hotmart, kiwify ou eduzz")
    if not str(dados.get("link_afiliado", "")).startswith(("http://", "https://")):
        raise ValueError("Informe o seu link de afiliado (começa com https://)")
    p = {
        "plataforma": plataforma,
        "id_externo": str(dados.get("id_externo") or ""),
        "nome": str(dados["nome"]).strip()[:120],
        "nicho": str(dados.get("nicho") or "")[:60],
        "preco": float(dados["preco"]),
        "comissao_pct": float(dados["comissao_pct"]),
        "link_afiliado": dados["link_afiliado"],
        "pagina_vendas": dados.get("pagina_vendas") or "",
        "beneficio": str(dados.get("beneficio") or "")[:200],
        "publico": str(dados.get("publico") or "")[:200],
        "temperatura": float(dados.get("temperatura") or 0),
        "reembolso_pct": float(dados.get("reembolso_pct") or 0),
    }
    if p["preco"] <= 0 or not 0 < p["comissao_pct"] <= 100:
        raise ValueError("Preço e comissão (%) precisam ser válidos")
    nota, motivos = pontuar(p)
    pid = db.executar(
        "INSERT INTO produtos (plataforma, id_externo, nome, nicho, preco, comissao_pct, link_afiliado, "
        "pagina_vendas, beneficio, publico, temperatura, reembolso_pct, pontuacao, sim_conv, criado_em) "
        "VALUES (:plataforma, :id_externo, :nome, :nicho, :preco, :comissao_pct, :link_afiliado, "
        ":pagina_vendas, :beneficio, :publico, :temperatura, :reembolso_pct, :pontuacao, :sim_conv, :criado_em)",
        {**p, "pontuacao": nota, "sim_conv": sim_conv, "criado_em": relogio.agora_iso()},
    )
    avisos.diario("Produto cadastrado", f"#{pid} {p['nome']} — nota {nota:.0f} ({'; '.join(motivos)})")
    return pid


def obter(produto_id):
    return db.um("SELECT * FROM produtos WHERE id = ?", (produto_id,))


def proximo_candidato():
    return db.um(
        "SELECT * FROM produtos WHERE status = 'candidato' AND pontuacao >= ? "
        "AND preco * comissao_pct / 100 >= ? ORDER BY pontuacao DESC, id LIMIT 1",
        (config.PONTUACAO_MINIMA, config.COMISSAO_MINIMA),
    )


def definir_status(produto_id, status):
    db.executar("UPDATE produtos SET status = ? WHERE id = ?", (status, produto_id))


# Produtos fictícios para a simulação. `sim_conv` é a chance real (escondida)
# de uma visita virar venda; a máquina não enxerga esse número, ela descobre
# testando, igual faria com dinheiro de verdade.
CATALOGO_SIMULADO = [
    dict(plataforma="hotmart", nome="Inglês Fluente em 90 Dias (exemplo)", nicho="idiomas", preco=197,
         comissao_pct=50, temperatura=80, reembolso_pct=6, beneficio="conversar em inglês com confiança",
         publico="adultos que travam na hora de falar inglês", sim_conv=0.026),
    dict(plataforma="kiwify", nome="Confeitaria Lucrativa em Casa (exemplo)", nicho="culinária",
         preco=147, comissao_pct=60, temperatura=75, reembolso_pct=5,
         beneficio="fazer doces bonitos para vender por encomenda",
         publico="quem quer uma renda extra cozinhando em casa", sim_conv=0.024),
    dict(plataforma="eduzz", nome="Planilha de Finanças Pessoais Pro (exemplo)", nicho="finanças",
         preco=47, comissao_pct=70, temperatura=60, reembolso_pct=3,
         beneficio="organizar as contas do mês em uma planilha simples",
         publico="quem não sabe para onde vai o salário", sim_conv=0.040),
    dict(plataforma="hotmart", nome="Excel do Zero ao Avançado (exemplo)", nicho="carreira", preco=297,
         comissao_pct=40, temperatura=70, reembolso_pct=4, beneficio="dominar o Excel para o trabalho",
         publico="profissionais que usam planilhas no dia a dia", sim_conv=0.011),
    dict(plataforma="kiwify", nome="Fotografia com o Celular (exemplo)", nicho="hobbies", preco=97,
         comissao_pct=50, temperatura=40, reembolso_pct=8, beneficio="tirar fotos bonitas só com o celular",
         publico="quem gosta de fotografar mas não tem câmera", sim_conv=0.012),
    dict(plataforma="hotmart", nome="Rotina Organizada para Mães (exemplo)", nicho="produtividade",
         preco=67, comissao_pct=60, temperatura=35, reembolso_pct=7,
         beneficio="organizar a semana da família com menos correria",
         publico="mães que trabalham fora", sim_conv=0.009),
    dict(plataforma="eduzz", nome="Mentoria de Marketing Digital (exemplo)", nicho="negócios", preco=997,
         comissao_pct=30, temperatura=50, reembolso_pct=12, beneficio="montar a divulgação do seu negócio",
         publico="pequenos empreendedores", sim_conv=0.006),
    dict(plataforma="hotmart", nome="Violão para Iniciantes (exemplo)", nicho="música", preco=127,
         comissao_pct=50, temperatura=65, reembolso_pct=5, beneficio="tocar as primeiras músicas no violão",
         publico="adultos que sempre quiseram aprender um instrumento", sim_conv=0.030),
    dict(plataforma="kiwify", nome="Ebook de Receitas Rápidas (exemplo)", nicho="culinária", preco=37,
         comissao_pct=50, temperatura=70, reembolso_pct=2, beneficio="preparar jantares em 15 minutos",
         publico="quem chega cansado do trabalho", sim_conv=0.035),
]


def semear_simulacao():
    if db.valor("SELECT COUNT(*) FROM produtos"):
        return
    for i, item in enumerate(CATALOGO_SIMULADO, start=1):
        dados = {k: v for k, v in item.items() if k != "sim_conv"}
        dados.update(id_externo=f"sim-{i}", link_afiliado=f"https://example.com/afiliado/produto-{i}",
                     pagina_vendas=f"https://example.com/vendas/produto-{i}")
        adicionar(dados, sim_conv=item["sim_conv"])

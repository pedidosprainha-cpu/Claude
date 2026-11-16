import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from maquina import config, db, produtos, relogio  # noqa: E402


@pytest.fixture(autouse=True)
def banco_limpo(monkeypatch):
    monkeypatch.setattr(config, "MODO", "simulacao")
    monkeypatch.setattr(config, "IA_CRIATIVOS", "desligada")
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "")
    random.seed(42)
    db.usar(":memory:")
    relogio.agora()
    yield
    db.usar(":memory:")


def criar_produto(**extra):
    dados = dict(plataforma="hotmart", nome="Curso Teste", preco=200, comissao_pct=50,
                 link_afiliado="https://example.com/a", beneficio="aprender algo", publico="adultos",
                 temperatura=80, id_externo="P1")
    dados.update(extra)
    sim_conv = dados.pop("sim_conv", 0.02)
    return produtos.adicionar(dados, sim_conv=sim_conv)


def criar_criativo(produto_id, status="aprovado", sim_ctr=0.02):
    return db.executar(
        "INSERT INTO criativos (produto_id, angulo, titulo, texto, cta, origem, status, sim_ctr, criado_em) "
        "VALUES (?, 'teste', 'Título', 'Texto', 'LEARN_MORE', 'modelo', ?, ?, ?)",
        (produto_id, status, sim_ctr, relogio.agora_iso()),
    )


def gastar(campanha_id, valor, impressoes=1000, cliques=20, dia=None):
    db.executar(
        "INSERT INTO metricas (campanha_id, dia, impressoes, cliques, visitas, gasto) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(campanha_id, dia) DO UPDATE SET gasto = gasto + excluded.gasto, "
        "impressoes = impressoes + excluded.impressoes, cliques = cliques + excluded.cliques",
        (campanha_id, dia or relogio.hoje(), impressoes, cliques, cliques, valor),
    )


def vender(campanha_id, comissao, transacao):
    from maquina import afiliados
    return afiliados.processar("hotmart", {
        "event": "PURCHASE_APPROVED",
        "data": {"product": {"id": "P1"}, "purchase": {"transaction": transacao, "price": {"value": 200},
                                                       "origin": {"sck": f"cmp{campanha_id}"}},
                 "commissions": [{"value": comissao, "source": "AFFILIATE"}]},
    })

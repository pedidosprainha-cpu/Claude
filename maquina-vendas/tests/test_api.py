import pytest
from fastapi.testclient import TestClient

from maquina import api, config, db


@pytest.fixture
def cliente(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "PAINEL_TOKEN", "segredo-de-teste")
    monkeypatch.setattr(config, "DADOS", tmp_path)
    monkeypatch.setattr(config, "SIM_SEGUNDOS_POR_HORA", 3600)
    with TestClient(api.app) as c:
        c.headers["Authorization"] = "Bearer segredo-de-teste"
        yield c


def test_painel_exige_token(cliente):
    assert cliente.get("/api/painel", headers={"Authorization": "Bearer errado"}).status_code == 401
    d = cliente.get("/api/painel").json()
    assert d["modo"] == "simulacao" and d["teto"] == 30 and len(d["produtos"]) == 9


def test_fluxo_aprovar_simular_e_pausar(cliente):
    cliente.post("/api/simulacao/avancar", json={"horas": 1})
    pendentes = cliente.get("/api/painel").json()["aprovacoes"]
    assert pendentes and pendentes[0]["criativo"]["titulo"]
    for a in pendentes:
        assert cliente.post(f"/api/aprovacoes/{a['id']}", json={"aprovar": True}).json()["ok"]
    assert cliente.post(f"/api/aprovacoes/{pendentes[0]['id']}", json={"aprovar": True}).status_code == 409
    cliente.post("/api/simulacao/avancar", json={"horas": 48})
    d = cliente.get("/api/painel").json()
    assert d["campanhas"] and d["gasto_hoje"] <= d["teto"]
    cliente.post("/api/pausar")
    d = cliente.get("/api/painel").json()
    assert d["pausado"] and not [c for c in d["campanhas"] if c["status"] == "ativa"]


def test_pagina_de_captura_clique_e_cadastro(cliente):
    cliente.post("/api/simulacao/avancar", json={"horas": 1})
    for a in cliente.get("/api/painel").json()["aprovacoes"]:
        cliente.post(f"/api/aprovacoes/{a['id']}", json={"aprovar": True})
    cid = cliente.get("/api/painel").json()["campanhas"][0]["id"]
    assert "Privacidade" in cliente.get(f"/p/{cid}").text
    r = cliente.get(f"/ir/{cid}?v=visitante-api-1", follow_redirects=False)
    assert r.status_code == 302 and f"sck=cmp{cid}" in r.headers["location"]
    ruim = cliente.post("/api/v/cadastro", json={"v": "visitante-api-1", "c": cid, "email": "x@example.com"})
    assert ruim.status_code == 400
    ok = cliente.post("/api/v/cadastro", json={"v": "visitante-api-1", "c": cid, "nome": "Eva",
                                               "email": "eva@example.com", "consentimento": True})
    assert ok.status_code == 200
    assert db.valor("SELECT pontuacao FROM leads WHERE visitante = 'visitante-api-1'") == 45


def test_webhook_com_token_configurado_recusa_assinatura_errada(cliente, monkeypatch):
    monkeypatch.setattr(config, "HOTMART_HOTTOK", "hottok-certo")
    corpo = {"event": "PURCHASE_APPROVED", "data": {"purchase": {"transaction": "Z1"}}}
    assert cliente.post("/webhooks/hotmart", json=corpo, headers={"X-HOTMART-HOTTOK": "errado"}).status_code == 401
    assert cliente.post("/webhooks/hotmart", json=corpo, headers={"X-HOTMART-HOTTOK": "hottok-certo"}).status_code == 200

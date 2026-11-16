import pytest

from maquina import campanhas, criativos, db, leads, politica

from conftest import criar_criativo, criar_produto


@pytest.fixture
def campanha():
    p = criar_produto()
    return campanhas.criar(p, criar_criativo(p), 10)


def test_pontuacao_soma_na_hora_e_nao_duplica(campanha):
    leads.evento("visitante-1", campanha, "visita")
    leads.evento("visitante-1", campanha, "visita")  # recarregou a página
    leads.evento("visitante-1", campanha, "rolou_50")
    lead = db.um("SELECT * FROM leads WHERE visitante = 'visitante-1'")
    assert lead["pontuacao"] == 15 and lead["temperatura"] == "frio"


def test_lead_vira_quente_e_gera_alerta(campanha):
    leads.cadastro("visitante-2", campanha, "Ana", "ana@example.com", "", True)
    for tipo in ("visita", "rolou_50", "ficou_30s", "clicou_oferta"):
        leads.evento("visitante-2", campanha, tipo)
    lead = db.um("SELECT * FROM leads WHERE visitante = 'visitante-2'")
    assert lead["temperatura"] == "quente"
    assert db.um("SELECT 1 FROM alertas WHERE titulo LIKE 'Lead quente: Ana%'")


def test_cadastro_exige_consentimento(campanha):
    with pytest.raises(ValueError):
        leads.cadastro("visitante-3", campanha, "Bia", "bia@example.com", "", False)
    assert leads.contagens()["total"] == 0


def test_abandono_de_checkout_e_compra_reconhecem_o_lead_pelo_email(campanha):
    leads.cadastro("visitante-4", campanha, "Caio", "Caio@Example.com", "", True)
    leads.abandono(leads.hash_email("caio@example.com"))
    assert db.valor("SELECT pontuacao FROM leads WHERE visitante = 'visitante-4'") == 50
    leads.marcar_cliente(leads.hash_email(" CAIO@example.com "))
    assert db.valor("SELECT cliente FROM leads WHERE visitante = 'visitante-4'") == 1


def test_apagar_lead(campanha):
    leads.cadastro("visitante-5", campanha, "Duda", "duda@example.com", "", True)
    lead_id = db.valor("SELECT id FROM leads WHERE visitante = 'visitante-5'")
    leads.apagar(lead_id)
    assert leads.contagens()["total"] == 0


@pytest.mark.parametrize("texto", [
    "Você está acima do peso? Conheça o método",
    "Renda garantida trabalhando de casa",
    "Ganhe R$ 500 por dia no celular",
    "Fique rico em 30 dias",
    "Veja o antes e depois dos alunos",
    "A cura definitiva para a ansiedade",
])
def test_politica_barra_o_que_o_meta_reprova(texto):
    assert politica.bloqueia(politica.checar(texto=texto))


def test_modelos_prontos_passam_no_pente_fino():
    from maquina.produtos import CATALOGO_SIMULADO
    for item in CATALOGO_SIMULADO:
        for c in criativos.gerar_com_modelos(item, 6, []):
            assert not politica.bloqueia(politica.checar(c["titulo"], c["texto"], c["descricao"])), c
            assert len(c["titulo"]) <= 40, c["titulo"]


def test_link_de_afiliado_ganha_codigo_de_rastreio():
    link = campanhas.link_rastreado("https://go.hotmart.com/X123?ap=abc", 7)
    assert "ap=abc" in link and "sck=cmp7" in link and "utm_campaign=cmp7" in link

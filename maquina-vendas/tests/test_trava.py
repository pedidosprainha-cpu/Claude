"""A trava de gasto é a parte mais importante: nada pode passar do teto."""
import pytest

from maquina import campanhas, config, db, motor, trava

from conftest import criar_criativo, criar_produto


def test_teto_nunca_passa_do_absoluto():
    db.cfg_definir("teto_diario", config.TETO_ABSOLUTO * 10)
    assert trava.teto() == config.TETO_ABSOLUTO


def test_bloqueia_campanha_que_passaria_do_teto():
    p = criar_produto()
    for _ in range(3):
        campanhas.criar(p, criar_criativo(p), 10)
    assert trava.comprometido() == 30
    with pytest.raises(trava.GastoBloqueado):
        campanhas.criar(p, criar_criativo(p), 10)
    assert db.valor("SELECT COUNT(*) FROM campanhas WHERE status = 'ativa'") == 3


def test_bloqueia_orcamento_abaixo_do_minimo_e_com_maquina_pausada():
    assert trava.checar(1) is not None
    db.cfg_definir("pausado", True)
    assert trava.checar(10) == "A máquina está pausada"


def test_app_nao_consegue_aumentar_o_teto():
    with pytest.raises(ValueError):
        motor.ajustar(teto_diario=50)
    assert trava.teto() == 30


def test_reduzir_teto_pausa_campanhas_ate_caber():
    p = criar_produto()
    for _ in range(3):
        campanhas.criar(p, criar_criativo(p), 10)
    motor.ajustar(teto_diario=15)
    assert trava.comprometido() <= 15


def test_pausa_geral_desliga_tudo_e_impede_novas_campanhas():
    p = criar_produto()
    campanhas.criar(p, criar_criativo(p), 10)
    campanhas.pausar_tudo()
    assert not campanhas.ativas()
    criar_criativo(p)
    motor.ciclo(24)
    assert not campanhas.ativas()
    campanhas.retomar()
    assert len(campanhas.ativas()) >= 1


def test_simulacao_de_60_dias_nunca_passa_do_teto():
    motor.iniciar()
    for _ in range(60):
        for a in db.todos("SELECT id, tipo FROM aprovacoes WHERE status = 'pendente'"):
            # aprova anúncios, recusa aumento de teto
            motor.decidir(a["id"], a["tipo"] == "criativo")
        motor.ciclo(24)
    maior = db.valor("SELECT MAX(g) FROM (SELECT SUM(gasto) AS g FROM metricas GROUP BY dia)")
    assert maior <= 30.01
    assert db.valor("SELECT COUNT(*) FROM campanhas") > 0

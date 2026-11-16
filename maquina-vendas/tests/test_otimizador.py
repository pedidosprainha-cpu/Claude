from maquina import avisos, campanhas, config, db, otimizador, produtos, relogio, trava

from conftest import criar_criativo, criar_produto, gastar, vender


def test_pausa_campanha_que_gastou_sem_vender():
    p = criar_produto(preco=200, comissao_pct=50)  # comissão R$100, limite = min(100, 3 dias de teto)
    c = campanhas.criar(p, criar_criativo(p), 10)
    gastar(c, 89)
    otimizador.avaliar_campanha(campanhas.obter(c))
    assert campanhas.obter(c)["status"] == "ativa"
    gastar(c, 2)
    otimizador.avaliar_campanha(campanhas.obter(c))
    assert campanhas.obter(c)["status"] == "pausada"
    assert "sem nenhuma venda" in campanhas.obter(c)["motivo"]


def test_pausa_anuncio_com_ctr_baixo():
    p = criar_produto()
    c = campanhas.criar(p, criar_criativo(p), 10)
    gastar(c, 20, impressoes=3000, cliques=10)  # CTR 0,33%
    otimizador.avaliar_campanha(campanhas.obter(c))
    assert "CTR" in campanhas.obter(c)["motivo"]


def test_escala_vencedora_em_20_por_cento_uma_vez_por_dia():
    p = criar_produto()
    c = campanhas.criar(p, criar_criativo(p), 10)
    gastar(c, 40)
    vender(c, 100, "A")
    vender(c, 100, "B")
    relogio.avancar(25)
    otimizador.avaliar_campanha(campanhas.obter(c))
    assert campanhas.obter(c)["orcamento_diario"] == 12
    otimizador.avaliar_campanha(campanhas.obter(c))
    assert campanhas.obter(c)["orcamento_diario"] == 12  # não escala duas vezes no mesmo dia


def test_sem_espaco_no_teto_pede_aprovacao_para_aumentar():
    p = criar_produto()
    c = campanhas.criar(p, criar_criativo(p), 30)
    gastar(c, 40)
    vender(c, 100, "A")
    vender(c, 100, "B")
    relogio.avancar(25)
    otimizador.avaliar_campanha(campanhas.obter(c))
    assert campanhas.obter(c)["orcamento_diario"] == 30
    assert avisos.tem_pendente("aumento_teto")
    assert trava.teto() == 30  # só muda se você aprovar


def test_produto_ruim_e_reprovado_e_o_proximo_entra_em_teste():
    ruim = criar_produto(nome="Ruim", id_externo="R")
    criar_produto(nome="Próximo", id_externo="N", temperatura=60)
    produtos.definir_status(ruim, "testando")
    c = campanhas.criar(ruim, criar_criativo(ruim), 10)
    gastar(c, 7 * 30 + 1)  # 7 dias de teto, sem venda
    otimizador.avaliar_produtos()
    assert produtos.obter(ruim)["status"] == "reprovado"
    assert campanhas.obter(c)["status"] == "pausada"
    otimizador.planejar_testes()
    assert db.valor("SELECT COUNT(*) FROM produtos WHERE status = 'testando'") == 1


def test_produto_com_campanha_lucrativa_nao_e_reprovado():
    p = criar_produto()
    produtos.definir_status(p, "testando")
    ruim = campanhas.criar(p, criar_criativo(p), 10)
    boa = campanhas.criar(p, criar_criativo(p), 10)
    gastar(ruim, 300)
    gastar(boa, 20)
    vender(boa, 100, "X")
    otimizador.avaliar_produtos()
    assert produtos.obter(p)["status"] == "testando"


def test_autonomia_com_limites_pede_aprovacao_de_anuncio_novo():
    criar_produto()
    otimizador.planejar_testes()
    pendentes = db.valor("SELECT COUNT(*) FROM aprovacoes WHERE tipo = 'criativo' AND status = 'pendente'")
    assert pendentes == config.CRIATIVOS_POR_RODADA
    assert not campanhas.ativas()


def test_autonomia_total_publica_sozinha():
    db.cfg_definir("autonomia", "total")
    criar_produto()
    otimizador.executar()
    assert campanhas.ativas()

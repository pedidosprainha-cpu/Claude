import hashlib
import hmac

from maquina import afiliados, campanhas, db

from conftest import criar_criativo, criar_produto, vender


def test_hotmart_usa_a_comissao_do_afiliado():
    ev = afiliados.normalizar_hotmart({
        "event": "PURCHASE_APPROVED",
        "data": {"product": {"id": 9, "name": "X"}, "buyer": {"email": "a@b.com"},
                 "purchase": {"transaction": "HP1", "price": {"value": 197}, "origin": {"sck": "cmp7"}},
                 "commissions": [{"value": 19.5, "source": "MARKETPLACE"}, {"value": 98.5, "source": "AFFILIATE"},
                                 {"value": 70, "source": "PRODUCER"}]},
    })
    assert (ev.status, ev.transacao, ev.comissao, ev.valor, ev.rastreio) == ("aprovada", "HP1", 98.5, 197, "cmp7")


def test_kiwify_converte_centavos_e_confere_assinatura():
    ev = afiliados.normalizar_kiwify({
        "order_id": "K1", "order_status": "paid", "Commissions": {"charge_amount": 14700, "my_commission": 8820},
        "TrackingParameters": {"sck": "cmp3"}, "Product": {"product_id": "abc"},
    })
    assert (ev.status, ev.valor, ev.comissao, ev.rastreio) == ("aprovada", 147.0, 88.2, "cmp3")
    corpo = b'{"order_id":"K1"}'
    assinatura = hmac.new(b"segredo", corpo, hashlib.sha1).hexdigest()
    assert afiliados.validar_kiwify(corpo, assinatura, "segredo")
    assert not afiliados.validar_kiwify(corpo, assinatura, "outro")
    assert not afiliados.validar_kiwify(corpo, "", "segredo")


def test_eduzz_formato_antigo_e_novo():
    antigo = afiliados.normalizar_eduzz({"trans_cod": "123", "trans_status": "3", "trans_value": "47.00",
                                         "aff_value": "32.90", "tracker": "cmp2"})
    assert (antigo.status, antigo.comissao, antigo.rastreio) == ("aprovada", 32.9, "cmp2")
    novo = afiliados.normalizar_eduzz({"event": "myeduzz.invoice_refunded", "data": {"id": "9"}})
    assert novo.status == "reembolsada"


def test_hottok_errado_e_recusado():
    assert afiliados.validar_hotmart({"x-hotmart-hottok": "certo"}, "certo")
    assert not afiliados.validar_hotmart({"x-hotmart-hottok": "errado"}, "certo")
    assert not afiliados.validar_hotmart({}, "")


def test_venda_e_atribuida_a_campanha_sem_duplicar_e_reembolso_desconta():
    p = criar_produto()
    c = campanhas.criar(p, criar_criativo(p), 10)
    assert vender(c, 100, "T1")["novo"]
    assert vender(c, 100, "T1")["duplicado"]
    assert campanhas.stats(campanha_id=c)["comissao"] == 100
    afiliados.processar("hotmart", {"event": "PURCHASE_REFUNDED",
                                    "data": {"purchase": {"transaction": "T1"}}})
    s = campanhas.stats(campanha_id=c)
    assert (s["vendas"], s["comissao"], s["reembolsos"]) == (0, 0, 1)
    assert db.um("SELECT 1 FROM alertas WHERE titulo LIKE 'Reembolso%'")


def test_aviso_sem_comissao_usa_estimativa_do_produto():
    p = criar_produto(preco=100, comissao_pct=40)
    c = campanhas.criar(p, criar_criativo(p), 10)
    afiliados.processar("hotmart", {"event": "PURCHASE_APPROVED",
                                    "data": {"product": {"id": "P1"},
                                             "purchase": {"transaction": "T9", "origin": {"sck": f"cmp{c}"}}}})
    assert campanhas.stats(campanha_id=c)["comissao"] == 40

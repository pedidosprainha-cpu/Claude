"""Conexão com a plataforma de anúncios.

A máquina conversa com o Meta Ads sempre por esta interface. Na simulação, a
"plataforma" é falsa e quem gera impressões, cliques e vendas é o simulador.
Na etapa 2, a classe MetaReal passa a falar com a Marketing API do Meta.
"""
from . import config


class PlataformaAds:
    nome = "base"

    def criar_campanha(self, campanha, produto, criativo, link):
        raise NotImplementedError

    def definir_orcamento(self, id_externo, valor):
        raise NotImplementedError

    def pausar(self, id_externo):
        raise NotImplementedError

    def ativar(self, id_externo):
        raise NotImplementedError


class MetaSimulado(PlataformaAds):
    nome = "Meta Ads (simulado)"

    def criar_campanha(self, campanha, produto, criativo, link):
        return f"sim-{campanha['id']}"

    def definir_orcamento(self, id_externo, valor):
        pass

    def pausar(self, id_externo):
        pass

    def ativar(self, id_externo):
        pass


class MetaReal(PlataformaAds):
    nome = "Meta Ads"

    def __init__(self):
        raise NotImplementedError(
            "A conexão real com o Meta Ads entra na etapa 2 (precisa das suas chaves de acesso)."
        )


def plataforma():
    if config.MODO == "simulacao":
        return MetaSimulado()
    return MetaReal()

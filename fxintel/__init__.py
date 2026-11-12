"""FXIntel — motor de inteligência de mercado para Forex e metais preciosos.

Camadas:
    data         -> provedores de cotações/barras/calendário, cache e failover
    technical    -> indicadores, estrutura (BOS/CHoCH), SMC (FVG/OB/liquidez), níveis, padrões, MTF
    fundamental  -> calendário econômico, intermercados, bancos centrais, força relativa de moedas
    quant        -> regimes, features, rotulagem triple-barrier, modelo probabilístico calibrado,
                    correlações, anomalias, estatística
    signals      -> geração de candidatos, níveis de SL/TP, pontuação multifatorial, validação
    risk         -> dimensionamento, limites de perda/exposição, aprovação de sinais
    backtest     -> simulador com custos, walk-forward, métricas e relatórios
    execution    -> adaptadores de corretora (paper/demo e OANDA), separados da geração de sinal
    engine       -> orquestração do comando "ANALISAR MERCADO AGORA"
"""

__version__ = "1.0.0"

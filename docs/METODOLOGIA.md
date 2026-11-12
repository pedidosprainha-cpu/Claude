# Metodologia

Este documento descreve *como* o motor decide e *por que* cada escolha foi feita. Os parâmetros citados são
os padrões de `fxintel/config.py`; todos são configuráveis.

## 1. Dados

| Ativo | Cotação ao vivo | Histórico (análise e backtest) |
|---|---|---|
| Pares de moedas | Yahoo (último preço) ou OANDA (bid/ask) | Yahoo H1 (~2,8 anos), M15/M5 (60 dias) |
| XAU/USD | gold-api.com (spot) ou OANDA | PAXG-USD (token 1:1 em ouro, 24/7; fins de semana removidos), nível ajustado ao spot |
| XAG/USD | gold-api.com (spot) ou OANDA | Futuro SI=F com reparo de saltos de rolagem/intercalação, ajuste de base ao spot |
| Intermercados | — | DXY, ^TNX, ^FVX, ^IRX, ^VIX, ES=F, CL=F (H1) |

- **H4 e D1 são derivados de H1** e alinhados ao fechamento de Nova York (22:00 UTC). Isso garante que o backtest e a
  análise ao vivo vejam exatamente as mesmas barras.
- **Spread:** quando o provedor não fornece bid/ask, o spread é estimado (tabela por instrumento × multiplicador
  de sessão: rolagem 3×, Ásia 1,3×, Londres/sobreposição 1×, Nova York 1,1×, fim de sexta 1,6×) e marcado como
  `estimated` em toda a cadeia.
- **VWAP** só é calculado quando há volume real (metais via futuros); para FX spot o motor informa que não é aplicável.

## 2. Análise técnica e estrutural (multi-timeframe)

Tudo é **causal**: o valor em *t* usa apenas dados até *t*. Um swing com janela direita *R* só passa a existir
na barra *i+R*. Um teste automatizado recalcula o quadro com dados truncados e exige igualdade exata
(`tests/test_technical.py::test_frame_is_causal`).

- **Tendências:** primária (D1), secundária (H4), intradiária (H1/M15/M5), combinando estado da estrutura, empilhamento
  de EMAs 8/20/50, sequência de topos e fundos e DI±. O alinhamento ponderado (D1 30%, H4 30%, H1 20%, M15 12%,
  M5 8%) vai de −1 a +1.
- **Estrutura:** fractais (3/3 em H1, 2/2 em H4/D1). **BOS** = fechamento além do último swing na direção da
  tendência; **CHoCH** = fechamento além do swing protegido contra a tendência.
- **Liquidez:** pools de swings ativos, **topos/fundos iguais** (tolerância de 0,15 ATR), máxima/mínima do pregão e
  da semana anteriores, faixa asiática. **Varredura (sweep):** pavio além do pool com fechamento de volta,
  que sinaliza um possível falso rompimento.
- **FVG:** padrão de 3 velas com gap ≥ 0,15 ATR, mitigado quando preenchido. **Order Block:** última vela contrária
  antes de um BOS/CHoCH, invalidada por fechamento além dela. **Deslocamento:** corpo ≥ 1,2 ATR e ≥ 60% da faixa.
- **S/R:** agrupamento de swings de H4/D1 (tolerância de 0,25 ATR diário), com força ponderada por toques e
  recência. **Oferta/demanda:** base de 1 a 3 velas estreitas seguida de saída ≥ 1,5 ATR, válida até ser atravessada.
- **Indicadores:** RSI, MACD (histograma e inclinação), ATR (14/5/50), ADX/DI, Bollinger, estocástico e
  eficiência direcional, usados em contexto (ex.: RSI para medir recuo, ADX para medir regime), nunca de forma
  isolada.
- **Padrões:** engolfo, pin bar (rejeição), inside bar, doji, compressão (faixa de 5 vs. 50 barras),
  rompimento/falso rompimento de Donchian e divergência de RSI entre swings confirmados.

### Setups candidatos (execução a mercado no fechamento do candle H1)

| Setup | Condições principais | Stop |
|---|---|---|
| PULLBACK | H4 na direção, D1 não contrário, recuo (RSI < 45 / > 55), toque na EMA50 ou em FVG/OB (H1/H4), gatilho (engolfo, pin, retomada ou BOS), sem sobre-extensão | extremo de 6 barras ± 0,25 ATR |
| BREAKOUT | BOS/CHoCH + deslocamento + FVG novo, H4 não contrário, D1 não fortemente contrário | extremo de 3 barras ± 0,2 ATR |
| SWEEP | varredura de pool relevante (PDH/PDL, topos/fundos iguais, swing H4), fechamento de volta, contexto não contrário | extremo da vela ± 0,25 ATR |
| TREND | BOS de continuação com D1, H4 e H1 alinhados, ADX D1 ≥ 20 | último swing ± 0,25 ATR |

- O risco fica entre **1,0 e 2,5 ATR(H1)**. Abaixo de 1 ATR o stop é alargado; acima de 2,5 ATR o setup é descartado.
- **TP1** é o primeiro pool de liquidez oposto entre 1,3R e 3R (ligeiramente antecipado). Se não houver, usa
  1,5R. **TP2** é o próximo pool ≥ TP1 + 0,8R, ou max(2,5R, TP1 + 1R).
- **Gestão:** 50% no TP1, stop do restante movido para o preço de entrada, restante no TP2. Horizonte de 36 horas.
- **Espaço livre (`room_r`):** distância até o primeiro obstáculo oposto (FVG/OB/pool), em R.

## 3. Fundamentos e macroeconomia

- **Intermercados point-in-time** (z-scores de variações de 1 e 5 dias): DXY, Treasuries 5a/10a, curva 10a–3m,
  VIX (nível e percentil), S&P (futuro), petróleo. **Índice de risco** = z(S&P 1d) − z(ΔVIX 1d).
- **Força relativa das moedas:** média dos log-retornos (com sinal) de cada moeda nos pares, normalizada e
  centrada (1 e 5 dias).
- **Política monetária:** `config/central_banks.json` (taxa, viés, próximas reuniões, fontes). O motor alerta quando
  a tabela tem mais de 45 dias. Diferencial de juros (carry) e diferença de viés.
- **Score fundamentalista** em [−1, 1], com componentes explicáveis e pesos definidos *a priori*:
  diferencial de juros 0,22, viés 0,13, força relativa 0,25, sentimento de risco × sensibilidade do par 0,15,
  macro EUA (pares com USD) 0,15 e petróleo (pares com CAD) 0,10. Para os metais, os pesos são proxy de juro
  real (−ΔUS10Y) 0,25 e dólar 0,20, mais força e risco.
- **Eventos:** bloqueio de 60 min antes e 30 min depois de eventos críticos das moedas do par (eventos do USD valem
  para os metais). Eventos "Medium" com palavras-chave críticas (CPI, NFP, decisões de juros…) contam como críticos.
- **Geopolítica:** não há feed de notícias. O risco geopolítico é capturado indiretamente pelos preços (VIX,
  ouro, JPY/CHF, índice de risco). Isso é uma limitação documentada.

> A tabela de juros e o calendário não têm histórico point-in-time disponível e por isso **não entram no modelo
> estatístico**. Eles entram apenas no score fundamentalista (peso limitado) e nos portões de evento.

## 4. Quantitativo e IA

- **Regimes:** a regra explicável usa o percentil de ATR (baixa/normal/alta/extrema), ADX + eficiência
  (tendência/lateral/transição) e choque (ATR5/ATR50 ≥ 2). O regime estatístico usa uma mistura gaussiana de 3
  estados sobre (log-volatilidade, eficiência, ADX), ordenados por volatilidade, com persistência do estado.
- **Anomalias:** z-score robusto (mediana/MAD) da faixa e do retorno do último H1. **Qualidade de dados:** candles
  congelados, atraso e divergência entre cotação e último fechamento.
- **Correlações:** Spearman dos retornos H1 (480 barras), usadas no controle de exposição.
- **Rótulo (triple-barrier):** 1 se o TP1 é atingido antes do stop, dentro de 36h, simulado com bid/ask,
  slippage, gaps e a convenção conservadora "stop primeiro" quando os dois níveis cabem no mesmo candle.
- **Features (54):** normalizadas pela direção do trade (o mesmo modelo serve compra e venda). Incluem setup,
  alinhamentos D1/H4/H1, ADX, RSI, MACD, extensões, volatilidade, R:R, espaço livre, posição no dia, sessão,
  intermercados ajustados à exposição em USD e força relativa.
- **Modelo primário:** regressão logística L2 (C = 0,2), escolhida *a priori* por estabilidade e
  interpretabilidade. Secundário: gradient boosting raso com calibração por validação temporal.
- **Validação walk-forward:** janelas mensais e treino expansivo, com *purging* (só entram rótulos resolvidos
  antes do teste) e embargo de 24h. O holdout de 2026 foi reservado: nenhuma decisão de desenho usou seus resultados.
- **Probabilidade exibida:** a frequência observada **fora da amostra** na faixa da previsão, com IC 90% de Wilson e
  o *n* da faixa. Assim, o número mostrado é verificável e não uma confiança declarada pelo próprio modelo.
- **Valor esperado:** EV = p·k·R1 + (1−p)·L, em que k (fração do R1 capturada quando o TP1 é atingido) e L
  (resultado médio quando não é) são estimados no treino.
- **Controle de sobreajuste:** poucos hiperparâmetros fixados *a priori*, registro de todas as iterações de
  desenho (3 desenhos × 2 modelos), Deflated Sharpe Ratio, baseline de seleção aleatória e holdout.

## 5. Pontuação multifatorial (0–100)

`score = 50 + 50 × Σ wᵢ·cᵢ`, com componentes em [−1, 1]:

| Componente | Peso | Definição |
|---|---:|---|
| Valor esperado | 0,45 | EV / 0,5R, limitado |
| Técnico | 0,20 | alinhamento MTF, zona institucional, alvo estrutural, espaço livre, gatilho, confluência de setups |
| Fundamental | 0,15 | score fundamentalista × direção |
| Regime | 0,10 | compatibilidade do setup com o regime; penaliza choque e volatilidade extrema |
| Custo | 0,10 | 1 − 2·(custo em R / custo máximo) |

A pontuação **ordena** os candidatos. A **elegibilidade** é decidida pelos portões.

## 6. Portões de validação (todos obrigatórios)

1. Mercado aberto.
2. Cotação com no máximo 180 s de idade.
3. Qualidade dos dados.
4. Sem anomalia de preço.
5. Sem choque de volatilidade nem volatilidade extrema.
6. Sem evento crítico na janela de bloqueio.
7. Spread ≤ 0,12 ATR(H1).
8. Preço atual ainda aquém do stop.
9. Custo de entrada ≤ 0,15R.
10. R:R líquido ≥ 1,2.
11. Deriva do preço desde o sinal ≤ 0,35 ATR.
12. Modelo validado (BSS OOS > 0, AUC OOS ≥ 0,52 e trades selecionados OOS com R médio > 0, p < 0,10, n ≥ 30).
13. EV ≥ +0,05R.
14. Aprovação do gestor de risco.

## 7. Gestão de risco

- Risco por trade de 0,5% do capital, com lote arredondado **para baixo**. Se o lote mínimo exceder o risco,
  o sinal é bloqueado.
- Limites de perda: 2% diária, 4% semanal e 1,5% por sessão (posições demo/registradas).
- Máximo de 3 posições abertas, 1 por instrumento e risco agregado de 1% por moeda/direção.
- Máximo de posições correlacionadas: 2 com ρ ≥ 0,7, considerando a direção da posição.
- Margem estimada de no máximo 50% do capital.
- As mesmas regras de portfólio são aplicadas no backtest.

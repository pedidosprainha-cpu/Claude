# Análise técnica de Forex em tempo real — Quarta-feira, 04/11/2026

**Snapshot final:** 15:06:50–15:06:53 UTC (12:06 em Brasília, UTC−3), logo depois do ISM Services dos EUA (15:00 UTC).
**Snapshot anterior ao dado:** 14:46 UTC, usado só como contexto.

## Veredito

> **NÃO HÁ ENTRADA A MERCADO TECNICAMENTE JUSTIFICÁVEL NO INSTANTE DA ANÁLISE.**
>
> Foram analisados 32 pares. Nenhum reúne ao mesmo tempo:
> - tendência H1 alinhada;
> - momentum a favor;
> - preço perto da média;
> - espaço livre até o próximo obstáculo.
>
> Os pares com tendência e momentum bons estão a **0,2–0,5 ATR(M15)** de uma resistência ou suporte relevante (máxima ou mínima do dia, clusters de topos H1/D1). Os pares com espaço livre são **contra a tendência H1** ou estão **esticados**. Pelas regras 6.1–6.3 e 6.5, qualquer ordem a mercado agora seria compra em topo ou venda em fundo.
>
> A melhor assimetria é **condicional**: **CAD/JPY BUY** no rompimento confirmado de 113,67 (seção C). **Não é um sinal executável agora.**

---

## 0. Dados: origem, horários e defasagem

| Item | Detalhe |
|---|---|
| **Cotações executáveis (Bid/Ask)** | Feed público BBO da Swissquote (`forex-data-feed.swissquote.com`, servidores *Live5/Live7*). Usado o perfil **"prime"**; o perfil "elite" (bruto) serviu de controle. |
| **Horário da coleta** | 15:06:50–15:06:53 UTC (timestamps em ms do próprio servidor, por par) |
| **Defasagem medida** | 0,06 s a 1,43 s entre o timestamp do servidor e o recebimento |
| **Validação cruzada** | TrueFX (feed interbancário): 10 pares coincidentes, com diferença de mid de **≤ 0,5 pip** e timestamps 15:06:51–15:06:53 UTC |
| **Candles (estrutura e indicadores)** | Yahoo Finance spot (CCY), 1 min × 5 dias, reamostrados para M5/M15/M30/H1, mais H1 de 3 meses e D1 de 1 ano. Último candle de 1 min com 0–30 s de idade. São candles **indicativos (mid)**: servem para estrutura, **não** para preço de execução. |
| **Fita do evento** | Bid/Ask de 14 pares a cada ~5 s, das 14:59 às 15:04 UTC, cobrindo a divulgação do ISM |
| **Calendário (só horários)** | ISM Services PMI EUA às 15:00 UTC (impacto médio). Amanhã, 12:00 UTC: decisão do BoE (alto impacto para GBP). |

**Limitações declaradas**

- Forex é mercado de balcão: **não há fluxo de ordens nem volume real**. "Liquidez" aqui significa só regiões prováveis de stops (máximas e mínimas de swing, números redondos). É inferência, não medição.
- Os candles de 1 min do Yahoo são esparsos em AUD/USD e NZD/USD (um tick a cada ~2 min). Nesses dois pares, o timing em M1/M5 tem baixa confiabilidade.
- Em USD/MXN, o Yahoo diverge **~49 pips** do preço executável. A estrutura intradiária desse par foi tratada como **não confiável**.
- AUD/CHF e CAD/CHF mostram pavios espúrios no Yahoo, que inflam o ATR. Nesses pares, os níveis foram conferidos em H1/D1.
- "Dia" vai de 00:00 UTC até agora. ADR = média de (máxima − mínima) dos últimos 20 dias. Pip = 0,01 nos pares JPY e 0,0001 nos demais.

## Contexto do instante

**Força relativa do dia** (variação desde a abertura UTC, normalizada por ADR, média entre os pares):

`AUD +0,77 > NZD +0,59 > CAD +0,16 > EUR +0,09 > GBP −0,01 > CHF −0,24 > USD −0,54 > JPY −0,75` (MXN +0,81)

**Reação ao ISM (fita das 14:59 às 15:04):**
- Leve fortalecimento do USD: EUR/USD −5 pips, USD/CHF +5, USD/JPY +2.
- Os spreads ficaram ordenados: máximo de 1,3–3,3 pips (EUR/USD 1,3; USD/JPY 1,4; EUR/CHF 3,3).
- Não houve choque de volatilidade. O dado não rompeu as faixas pré-evento.

**Regime:** a maior parte dos pares está **comprimida desde ~09:00–13:00 UTC** nos extremos do dia, depois de fortes movimentos na Ásia e no início de Londres. A amplitude do dia já passa de 1 ADR em vários pares:
- EUR/AUD: 1,74×
- CAD/JPY: 1,6×
- AUD/JPY e NZD/JPY: > 1×

Isso é fase de **absorção**, não de impulso. É o cenário clássico de excursão adversa alta para entradas a mercado.

## Metodologia de pontuação (0–100, pesos fixos e explícitos)

| Bloco | Peso | O que mede |
|---|---|---|
| A. Tendência | 20 | Pilha EMA 8>20>50 e inclinação da EMA20 em H1 (30%), M30 (25%), M15 (25%) e M5 (20%), mais estrutura de swings em M15 e H1 |
| B. Momentum | 20 | Sinal e inclinação do histograma MACD, ADX com DI±, RSI em zona de continuação (52–68), em M15 e M5 |
| C. Local da entrada | 20 | Distância do preço executável à EMA20-M15, em ATR(M15). Ideal de 0 a 1,2. Penalidade acima de 2. |
| D. Espaço | 15 | Distância até o próximo obstáculo (swings M15/H1, máxima e mínima do dia e da véspera, números redondos .x00/.x50) em ATR(M15). Pleno com ≥ 3 ATR. |
| E. Timing M1/M5 | 10 | Pullback de 0,2–1,5 ATR(M5) concluído, retomada em M1 (fechamento além da EMA8 com MACD virando a favor), mínimas ascendentes (compra) ou máximas descendentes (venda) mantidas |
| F. Exaustão | 10 | RSI H1/M15 < 72 (ou > 28), movimento do dia < 1 ADR, distância do extremo do dia |
| G. Custo | 5 | Spread ÷ ATR(M5) |

**Filtros eliminatórios**, que rebaixam o par para a classe C ou abaixo, qualquer que seja o score:
- obstáculo a menos de 0,8 ATR(M15);
- esticado mais de 2 ATR;
- dia acima de 1 ADR;
- RSI H1 extremo;
- spread acima de 35% do ATR(M5);
- H1 não alinhado com a direção;
- momentum M15 contrário e piorando.

O score é **ferramenta de ordenação**, **não** probabilidade de acerto. Nenhum percentual de acerto é apresentado, porque não há modelo estatístico validado por trás.

---

## A. Varredura do mercado (32 pares, snapshot das 15:06 UTC)

O "lado" de cada linha é a melhor direção encontrada pelo modelo. z = afastamento da EMA20-M15 em ATR. "Espaço" = distância até o próximo obstáculo em ATR(M15).

| # | Par | Bid / Ask (prime) | Spread (pips) | Cotação (UTC) | Tendência CP | Momentum | Situação da entrada | Risco correção | Score | Classe | Filtros violados |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | EUR/CHF | 0.91963 / 0.91978 | 1.5 | 15:06:50 | Alta | Fraco/neutro | BUY colado em resistência (z=+1.0, espaço 0.2 ATR) | Médio | 77 | C | obstáculo < 0,8 ATR |
| 2 | CAD/JPY | 113.630 / 113.643 | 1.3 | 15:06:52 | Alta | Perdendo força ↓ | BUY colado em resistência (z=+1.4, espaço 0.2 ATR) | Médio | 74 | C | obstáculo < 0,8 ATR |
| 3 | EUR/AUD | 1.60234 / 1.60250 | 1.6 | 15:06:52 | Baixa | Forte ↓ | SELL levemente esticado (z=+1.7, espaço 1.4 ATR*) | Médio | 73 | C | H1 não alinhado |
| 4 | GBP/AUD | 1.92003 / 1.92018 | 1.5 | 15:06:52 | Baixa | Forte ↓ | SELL colado em suporte (z=+1.6, espaço 0.3 ATR) | Médio | 73 | C | obstáculo < 0,8 ATR; H1 não alinhado |
| 5 | USD/JPY | 158.567 / 158.575 | 0.8 | 15:06:51 | Alta | Moderado ↑ | BUY colado em resistência (z=+1.7, espaço 0.2 ATR) | Médio | 73 | C | obstáculo < 0,8 ATR |
| 6 | GBP/CHF | 1.10197 / 1.10210 | 1.3 | 15:06:52 | Alta fraca | Fraco/neutro | BUY colado em resistência (z=+1.1, espaço 0.2 ATR) | Médio | 73 | C | obstáculo < 0,8 ATR |
| 7 | GBP/JPY | 213.639 / 213.661 | 2.2 | 15:06:52 | Alta | Moderado ↓ | BUY colado em resistência (z=+0.7, espaço 0.5 ATR) | Médio | 71 | C | obstáculo < 0,8 ATR |
| 8 | CAD/CHF | 0.58608 / 0.58623 | 1.5 | 15:06:52 | Lateral | Fraco/neutro | BUY no valor (z=+0.9, espaço 1.1 ATR) | Baixo | 69 | C | H1 não alinhado |
| 9 | NZD/JPY | 89.229 / 89.242 | 1.3 | 15:06:52 | Alta | Forte ↓ | BUY no valor (z=+0.6, espaço 1.6 ATR) | Médio | 68 | C | dia > 1 ADR; momentum M15 contrário |
| 10 | USD/CHF | 0.81789 / 0.81801 | 1.2 | 15:06:51 | Baixa fraca | Fraco/neutro | BUY levemente esticado (z=+1.7, espaço 2.1 ATR) | Médio | 67 | C | H1 não alinhado |
| 11 | AUD/CHF | 0.57388 / 0.57401 | 1.3 | 15:06:53 | Alta | Moderado ↑ | BUY levemente esticado (z=+1.2, espaço 0.8 ATR) | Médio | 67 | C | H1 não alinhado |
| 12 | AUD/NZD | 1.24681 / 1.24708 | 2.7 | 15:06:53 | Alta | Fraco/neutro | BUY colado em resistência (z=+1.6, espaço 0.2 ATR) | Médio | 65 | C | obstáculo < 0,8 ATR |
| 13 | AUD/CAD | 0.97911 / 0.97924 | 1.3 | 15:06:53 | Alta fraca | Perdendo força ↓ | BUY colado em resistência (z=+0.6, espaço 0.2 ATR) | Médio | 65 | C | obstáculo < 0,8 ATR; H1 não alinhado |
| 14 | GBP/CAD | 1.88006 / 1.88023 | 1.7 | 15:06:52 | Lateral | Fraco/neutro | SELL colado em suporte (z=+0.8, espaço 0.8 ATR) | Médio | 65 | C | obstáculo < 0,8 ATR; H1 não alinhado |
| 15 | USD/CAD | 1.39539 / 1.39554 | 1.5 | 15:06:51 | Baixa | Moderado ↑ | BUY no valor (z=+0.4, espaço 0.9 ATR) | Baixo | 63 | C | H1 não alinhado |
| 16 | NZD/CHF | 0.46021 / 0.46036 | 1.5 | 15:06:52 | Alta fraca | Perdendo força ↓ | BUY colado em resistência (z=+1.0, espaço 0.4 ATR) | Médio | 62 | C | obstáculo < 0,8 ATR; H1 não alinhado |
| 17 | EUR/JPY | 178.294 / 178.310 | 1.6 | 15:06:51 | Alta | Forte ↓ | BUY colado em resistência (z=+0.4, espaço 0.3 ATR) | Médio | 62 | C | obstáculo < 0,8 ATR; momentum M15 contrário |
| 18 | USD/MXN | 18.65856 / 18.66051 | 19.5 | 15:06:53 | Lateral | Perdendo força ↑ | SELL colado em suporte (z=-0.1, espaço 0.2 ATR) | Médio | 61 | C | obstáculo < 0,8 ATR; **dados de candle não confiáveis** |
| 19 | EUR/CAD | 1.56894 / 1.56911 | 1.7 | 15:06:51 | Alta fraca | Moderado ↓ | SELL colado em suporte (z=+0.8, espaço 0.3 ATR) | Médio | 61 | C | obstáculo < 0,8 ATR; H1 não alinhado |
| 20 | CHF/JPY | 193.859 / 193.881 | 2.2 | 15:06:52 | Alta | Forte ↓ | SELL no valor (z=+0.7, espaço 1.1 ATR) | Baixo | 61 | C | H1 não alinhado |
| 21 | AUD/JPY | 111.264 / 111.281 | 1.7 | 15:06:52 | Alta | Perdendo força ↓ | BUY colado em resistência (z=+1.9, espaço 0.2 ATR) | Alto | 60 | C | obstáculo < 0,8 ATR; dia > 1 ADR |
| 22 | USD/SEK | 9.76064 / 9.76246 | 18.2 | 15:06:53 | Baixa fraca | Fraco/neutro | BUY colado em resistência (z=+1.2, espaço 0.2 ATR) | Médio | 60 | C | obstáculo < 0,8 ATR; H1 não alinhado |
| 23 | USD/SGD | 1.27861 / 1.27892 | 3.1 | 15:06:52 | Baixa | Forte ↑ | BUY levemente esticado (z=+1.6, espaço 1.3 ATR) | Baixo | 58 | C | spread alto vs ATR M5; H1 não alinhado |
| 24 | AUD/USD | 0.70164 / 0.70175 | 1.1 | 15:06:52 | Alta | Moderado ↓ | BUY no valor (z=+0.6, espaço 1.2 ATR) | Médio | 57 | C | dia > 1 ADR; spread alto vs ATR M5; **M1 esparso** |
| 25 | GBP/NZD | 2.39409 / 2.39450 | 4.1 | 15:06:52 | Baixa fraca | Forte ↑ | BUY colado em resistência (z=+0.1, espaço 0.2 ATR) | Médio | 57 | C | obstáculo < 0,8 ATR; H1 não alinhado |
| 26 | USD/NOK | 9.25862 / 9.26061 | 19.9 | 15:06:53 | Baixa | Moderado ↑ | BUY colado em resistência (z=+1.8, espaço 0.4 ATR) | Médio | 57 | C | obstáculo < 0,8 ATR; H1 não alinhado |
| 27 | GBP/USD | 1.34729 / 1.34739 | 1.0 | 15:06:51 | Alta | Moderado ↓ | SELL colado em suporte (z=+1.5, espaço 0.2 ATR) | Médio | 57 | C | obstáculo < 0,8 ATR; H1 não alinhado |
| 28 | EUR/GBP | 0.83449 / 0.83461 | 1.2 | 15:06:51 | Alta fraca | Fraco/neutro | SELL no valor (z=+0.4, espaço 1.1 ATR) | Baixo | 56 | C | spread alto vs ATR M5; H1 não alinhado |
| 29 | NZD/CAD | 0.78519 / 0.78534 | 1.5 | 15:06:53 | Alta | Moderado ↓ | SELL colado em suporte (z=+0.3, espaço 0.2 ATR) | Médio | 54 | D | obstáculo < 0,8 ATR; H1 não alinhado |
| 30 | EUR/NZD | 1.99798 / 1.99832 | 3.4 | 15:06:52 | Baixa fraca | Moderado ↑ | BUY no valor (z=-0.0, espaço 1.0 ATR) | Baixo | 52 | D | spread alto vs ATR M5; H1 não alinhado |
| 31 | EUR/USD | 1.12435 / 1.12448 | 1.3 | 15:06:51 | Alta | Moderado ↓ | SELL colado em suporte (z=+2.0, espaço 0.2 ATR) | Médio | 43 | D | obstáculo < 0,8 ATR; H1 não alinhado |
| 32 | NZD/USD | 0.56265 / 0.56280 | 1.5 | 15:06:51 | Alta | Forte ↓ | SELL colado em suporte (z=+1.5, espaço 0.5 ATR) | Médio | 43 | D | obstáculo < 0,8 ATR; spread alto vs ATR M5; H1 não alinhado; **M1 esparso** |

\* Em EUR/AUD, o motor só enxerga os 3 últimos swings. O mapa de 15 dias mostra uma **zona de polaridade em 1,6000–1,6025**: mínimas H1 em 1,6008/1,6011/1,6015/1,6018/1,6021/1,6023, que foram topos em 21/10, 22/10 e 02/11. O espaço real é menor que 1 ATR.

**Classes:**
- **A:** nenhum par.
- **B:** nenhum par.
- **C:** 28 pares.
- **D:** 4 pares.

Nenhum par passou em todos os filtros eliminatórios.

## B. Ranking das 5 melhores configurações (nenhuma executável agora)

1. **CAD/JPY — BUY (condicional ao rompimento).**
   - Tendência alinhada em H1, M30 e M15: EMAs empilhadas, RSI H1 65.
   - Desde 12:45 forma um **triângulo ascendente**: teto plano em 113,637–113,661 (4 toques) e mínimas ascendentes em 113,435 → 113,494 → 113,520 → 113,568 → 113,573 → 113,598.
   - Acima de 113,66 há **vácuo de oferta até 113,79** (topo H1) e depois **até 114,10** (topo D1). É o par com o melhor espaço *depois* do gatilho.
   - Hoje está a 0,2 ATR do teto, por isso não se compra a mercado.

2. **EUR/CHF — BUY.**
   - Maior score bruto (77). Tendência alinhada.
   - Fraqueza do CHF depois do ISM: USD/CHF +27 pips desde 14:30, GBP/CHF e CAD/CHF também em alta.
   - Está 3 pips abaixo da máxima do dia (0,92006) e do redondo 0,9200, com oferta densa logo acima (0,92035 / 0,92069 / 0,9210). Mesmo rompendo, o espaço é curto.

3. **USD/JPY — BUY.**
   - Momentum M5/M15 forte depois do ISM. Spread de 0,8 pip.
   - Está **dentro** do cluster de resistências 158,576 / 158,592 / 158,606 (máxima do dia), com novas camadas a cada 3–5 pips até 158,79.
   - Há ainda risco de cauda de intervenção do Japão em JPY a 158,5.

4. **GBP/CHF — BUY.**
   - Mesmo tema de CHF fraco. Retomada limpa em M5.
   - Está **na** máxima da véspera (1,10213), com a máxima do dia em 1,10275.
   - O BoE amanhã às 12:00 UTC desaconselha carregar posição em GBP.

5. **EUR/AUD — SELL.**
   - BOS baixista em M15 (perdeu a mínima de 10:30, 1,60257), com máximas e mínimas descendentes desde 04:30. AUD é a moeda mais forte do dia.
   - Contra: o preço está sobre a zona de polaridade 1,6000–1,6025, o RSI M15 está em 30, a amplitude do dia é de 1,74 ADR e a estrutura H1 maior é altista (1,578 → 1,617 entre 28/10 e 04/11). Seria vender em fundo.

**Descartes relevantes:**
- **AUD/CHF:** é a combinação mais forte contra a mais fraca, mas está em um **topo triplo H1** em 0,5737–0,5738 e há um cluster de máximas D1 em 0,5745–0,5750. Sobram ~6 pips de espaço.
- **NZD/JPY:** o dia já passa de 1 ADR e o momentum M15 é contrário. É um range de 89,18 a 89,39.
- **USD/CHF:** o rali vai contra a tendência H1, está esticado em M5 (z = 2,6) e encosta na EMA50-H1 (0,8185).

---

## C. Operação principal selecionada

```
ATIVO:              NENHUM — não há entrada a mercado tecnicamente justificável agora
DIREÇÃO:            —
HORÁRIO DA ANÁLISE: 04/11/2026, 15:06:53 UTC (12:06:53 BRT, UTC−3)
```

### Setup condicional prioritário (NÃO executar a mercado agora)

| Campo | Valor |
|---|---|
| **ATIVO** | CAD/JPY |
| **DIREÇÃO** | BUY, **somente após o gatilho** |
| **PREÇO SPOT ATUAL** | 113.630 / 113.643 (Swissquote prime, 15:06:52 UTC; spread 1,3 pip) |
| **GATILHO** | Fechamento de candle **M5 acima de 113,670** (≥ 1 pip acima da máxima do dia, 113,661), sem que esse candle tenha amplitude maior que 2× o ATR(M5), ou seja, ~12 pips |
| **ENTRADA A MERCADO** | No primeiro tick depois do fechamento do candle de gatilho. Referência: **ask ≈ 113,680**. Alternativa mais conservadora: limite em 113,665 no reteste do teto rompido. |
| **STOP-LOSS** | **113,560**: abaixo das mínimas ascendentes 113,568/113,573. Perder esse nível desfaz o triângulo. Risco ≈ **12,0 pips** (entrada no ask, saída no bid, spread já incluído). |
| **TAKE-PROFIT 1** | **113,785** (50% da posição): logo abaixo do topo H1 em 113,793. **+10,5 pips**. Depois disso, mover o stop para o breakeven. |
| **TAKE-PROFIT 2** | **114,080** (50% restantes): logo abaixo do topo D1 em 114,104. **+40,0 pips**. |
| **RELAÇÃO RISCO/RETORNO** | TP1 0,9 : 1. TP2 3,3 : 1. **Média ponderada (50/50) ≈ 2,1 : 1** com o spread vigente incluído. Slippage não modelado: na abertura de Londres e no ISM, os spreads ficaram ≤ 2,3 pips no par. |
| **VALIDADE DO SINAL** | Até **16:00 UTC** (fechamento de Londres; a liquidez cai depois disso). **Cancelar** se: (a) o preço perder 113,560 antes do gatilho; (b) o rompimento vier em um único candle esticado acima de 2 ATR(M5); (c) USD/JPY for rejeitado com força em 158,61 (os crosses de JPY andam juntos); (d) não houver gatilho até 16:00 UTC. Reavaliar com novo snapshot no gatilho. |
| **CONFIANÇA DA CONFIGURAÇÃO** | **Moderada-baixa.** A estrutura (triângulo ascendente em tendência alinhada, com vácuo acima) é de boa qualidade, mas: o dia já percorreu 1,6× o ADR; o momentum M15 está desacelerando (histograma MACD negativo, ainda que subindo); e o rompimento depende de o USD/JPY superar sua própria resistência. |

## D. Justificativa técnica

**1. Por que não há operação a mercado agora.**

O objetivo é deslocamento favorável *imediato* com baixa MAE (excursão adversa máxima). No instante analisado, todos os pares com tendência e momentum a favor estão a 2–5 pips de uma barreira:

| Par | Barreira | Distância |
|---|---|---|
| EUR/CHF | 0,9200–0,92006 | 3 pips |
| CAD/JPY | 113,661 | 2 pips |
| USD/JPY | 158,576–158,606 | 0,5–3,5 pips |
| GBP/CHF | 1,10213 | 0,3 pip |
| AUD/NZD, AUD/CAD | máxima do dia | ~2 pips |
| GBP/AUD, EUR/USD, GBP/USD | mínimas de swing | 2–4 pips |

Entrar a mercado nesses pontos é comprar resistência ou vender suporte (regra 6.3). Os únicos pares com espaço medido acima de 1,5 ATR são USD/CHF (contra H1 e esticado), NZD/JPY (dia acima de 1 ADR e momentum contrário) e EUR/AUD (zona de polaridade logo abaixo). Todos violam outras regras: 6.1, 6.2 e 6.5.

**2. Por que CAD/JPY é a melhor assimetria condicional.**

- Uma compressão de 5 horas (113,43–113,66, só 23 pips) **no extremo superior** de um dia altista, com mínimas ascendentes, é absorção de oferta. Em tendência alinhada (H1, M30 e M15 com EMAs 8>20>50 e RSI H1 65, sem sobrecompra), esse padrão tende a se resolver na direção da tendência.
- Comprar só **depois** do fechamento acima do teto faz a entrada acontecer quando a barreira já não está à frente. O próximo obstáculo fica a 11 pips (113,79), e depois disso a 44 pips (114,10).
- No mapa de níveis, é o único par com tendência alinhada e um vácuo real acima do gatilho. EUR/CHF e USD/JPY têm oferta escalonada a cada 3–5 pips.

**3. Evidências de continuação esperada (se o gatilho ocorrer).**

- Quatro testes do teto, cada um com mínima mais alta: a pressão compradora está aumentando.
- O ATR(M5) de 5,9 pips é compatível com expansão de 10–15 pips no candle de rompimento.
- Contexto de moedas: JPY é a moeda mais fraca do dia (−0,75 ADR) e CAD fica no bloco intermediário-forte (+0,16).
- O ISM não produziu choque. O USD só se firmou levemente, e USD/JPY segue pressionando 158,6.

**4. Por que não é compra em topo.**

A compra *agora* seria (preço a 2 pips do teto), e por isso foi recusada. No setup condicional, o topo do dia deixa de ser obstáculo e vira suporte de reteste. O stop fica atrás da estrutura (as mínimas ascendentes), não em um número arbitrário. O preço também não está esticado: z = +1,35 em M15, dentro da faixa de valor.

**5. O que pode provocar correção ou reversão.**

- **Falso rompimento:** varredura dos stops acima de 113,66 seguida de volta para dentro do triângulo. Defesa: exigir fechamento em M5 e cancelar candles esticados.
- **Rejeição do USD/JPY** em 158,6 puxando todos os crosses de JPY.
- **Extensão do dia** (1,6× ADR). A reversão à média na sessão de Nova York é um risco real.
- **Notícias** de petróleo (CAD) ou declarações oficiais japonesas sobre o câmbio (JPY a 158,5).

**6. Invalidação imediata.**

- Antes do gatilho: perda de **113,560** (rompe a sequência de mínimas ascendentes e anula o setup).
- Depois da entrada: fechamento em M5 abaixo de **113,630** (volta para dentro do triângulo). Nesse caso, encerrar sem esperar o stop.
- Em qualquer momento: stop técnico em 113,560.

---

### Reprodutibilidade

- `fx_fetch_live.py <dir>`: baixa Bid/Ask ao vivo (Swissquote + TrueFX) e candles de 32 pares.
- `fx_scan_live.py <dir>`: motor multitemporal e score de qualidade de entrada.
- `fx_report_table.py <dir>`: gera a tabela da seção A com rótulos e filtros mecânicos.
- `snapshots/2026-11-04T1506Z/`:
  - cotações brutas (`quotes.json`, `truefx.csv`);
  - saída do motor (`scan.json`, `scan.txt`);
  - fita do ISM (`tape_ism_1459-1504.jsonl`);
  - varredura das 14:46 anterior ao dado (`scan_pre_ism_1446.json`, gerada antes da correção de pip em SEK/NOK/MXN; só a exibição desses três pares muda).

Nenhuma análise, sinal ou opinião de terceiros foi consultada. As fontes externas forneceram só preços, timestamps e o horário oficial dos eventos.

*Isto não é recomendação de investimento. Operar câmbio alavancado envolve risco elevado de perda. Os resultados são probabilísticos e não garantidos.*

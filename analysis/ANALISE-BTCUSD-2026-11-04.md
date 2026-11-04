# Análise técnica BTC/USD spot em tempo real — Quarta-feira, 04/11/2026

**Snapshot final:** 16:02:22–16:02:24 UTC (13:02 em Brasília, UTC−3). Snapshots de controle às 16:00:26 e 16:01:16 UTC.

## Veredito

> **NÃO HÁ ENTRADA A MERCADO TECNICAMENTE JUSTIFICÁVEL NO INSTANTE DA ANÁLISE.**
>
> - **Compra agora:** o BTC subiu +3,9% no dia, numa amplitude de **2,87× o ADR(20)**, com RSI de 77 (H1), 75 (M30) e 73 (M15), preço **2,6 ATR(M15) acima da EMA20** e paredes de venda a **US$ 90–150** acima (80.400–80.600). Isso viola as regras 6.1, 6.3 e 6.6: compra em topo estendido, contra resistência, com o movimento já realizado.
> - **Venda agora:** seria contra a tendência de H1, M30 e M15, sem CHoCH (mudança de caráter) confirmado, e direto sobre o suporte 80.000–80.200 (round number, retração de 38,2% e paredes de compra). Isso viola as regras 6.2, 6.3 e 6.5.
>
> A melhor assimetria é **condicional**: **BUY em pullback para 79.550–79.700, com confirmação** (seção C).

---

## 0. Dados: origem, horários e defasagem

| Item | Detalhe |
|---|---|
| **Cotações executáveis (Bid/Ask)** | APIs públicas das próprias exchanges spot BTC/USD (dólar, não USDT): Coinbase Exchange, Kraken, Bitstamp e Gemini |
| **Horário da coleta** | 16:02:22–16:02:24 UTC (timestamp de cada venue) |
| **Defasagem** | Coinbase 1,06 s · Kraken 3,85 s · Bitstamp 1,56 s · Gemini: o endpoint só informa o horário do volume (16:02:00), não o da cotação, por isso foi **excluída** da referência |
| **Dispersão entre venues** | Mid a mid: **US$ 3,06** (0,4 bp). O mercado estava consistente. |
| **Candles** | Kraken nativos em M1, M5, M15, M30, H1 e D1, **incluindo a barra em formação**: a última barra de 1 min tinha < 30 s. Os candles da Coinbase (defasados de 1 a 5 min) serviram só de conferência, com diferença de US$ 40–110 nas barras em formação. |
| **Livro de ofertas (medido)** | Coinbase L2 completo e Kraken com 500 níveis por lado |
| **Fluxo agressor (medido)** | Kraken: 5.806 negócios entre 15:42:17 e 16:02:24, com o lado do agressor informado. Coinbase: últimos 1.000 negócios (16:00:38–16:02:14), com lado inferido pela ordem passiva. |
| **Calendário (só horários)** | Nada de impacto médio ou alto nos EUA até amanhã às 13:30 UTC (pedidos de seguro-desemprego). Amanhã às 12:00 UTC: BoE (GBP). |

**Limitações declaradas**

- **O livro e o fluxo são de duas venues**, não do mercado inteiro. Há liquidez relevante em offshore e em USDT, que ficou fora.
- As **paredes do livro podem ser canceladas** a qualquer momento (spoofing). Elas indicam onde há oferta e demanda visíveis; não garantem nada.
- **Não usei derivativos** (futuros, perpétuos, funding, open interest), conforme a regra 2.2.
- **Não investiguei a causa** do impulso entre 14:30 e 15:15 UTC: isso exigiria notícias e análises de terceiros, o que a regra 3 proíbe.
- "Dia" = 00:00 UTC até agora, pela barra D1 da Kraken. ADR = média de (máxima − mínima) dos 20 dias anteriores = **US$ 1.933**.

## A. Varredura do ativo

### A.1 Cotação spot por venue

| Venue | Bid | Ask | Spread | Horário (UTC) | Defasagem |
|---|---|---|---|---|---|
| Coinbase | 80.307,59 | 80.310,96 | US$ 3,37 (0,42 bp) | 16:02:24 | 1,06 s |
| Kraken | 80.310,80 | 80.310,90 | US$ 0,10 (0,01 bp) | 16:02:22 | 3,85 s |
| Bitstamp | 80.305,00 | 80.310,59 | US$ 5,59 (0,70 bp) | 16:02:24 | 1,56 s |
| Gemini | 80.306,85 | 80.312,38 | US$ 5,53 | ≤ 16:02:00 (horário não verificável) | — |

**O spread é irrelevante; o custo real é a taxa da corretora.** As tabelas-base públicas que conheço ficam por volta de 0,25–0,40% de taxa taker na Kraken e até 0,60% na Coinbase Advanced, caindo com o volume operado. **Confirme a tabela do seu nível de conta.** Uma ida e volta com 0,40% por lado custa ~US$ 640 por BTC: mais do que um movimento típico de 15 minutos (ATR M15 = US$ 430).

### A.2 Contexto do dia (Kraken, dia UTC)

| Métrica | Valor |
|---|---|
| Abertura / Máxima / Mínima | 77.331,7 / **81.179,6** (15:15) / **75.625,0** (03:05) |
| Variação | **+2.978 (+3,85%)**, ou 1,54 ADR desde a abertura |
| Amplitude | **5.555 = 2,87 × ADR(20)**: dia excepcionalmente estendido |
| Posição na faixa do dia | 0,84 (terço superior) |
| VWAP do dia / VWAP ancorado na mínima / VWAP ancorado na máxima | 78.353 / 78.767 / **80.506** (o preço está *abaixo* do VWAP ancorado na máxima: quem comprou depois do topo está no prejuízo) |
| Impulso principal | 14:30 → 15:15 UTC: de 78.101 a 81.180 (+3.079) em 45 min. A barra H1 das 15:00 teve **892 BTC**, cerca de 6× a média das horas anteriores. |
| Retrações do impulso | 23,6% = 80.453 · **38,2% = 80.004** · **50% = 79.640** · 61,8% = 79.277 |
| Perfil de volume (bins de US$ 100) | Nó de alto volume em **80.600** (aceitação depois do impulso). Vácuo de volume entre ~78.600 e 80.000 (a perna do impulso). Nó de alto volume em 78.200–78.400 (faixa da manhã). |
| Oferta acima | 80.400–80.600 (paredes), máxima do dia 81.180, região de 28–29/10 em **81.700–81.880** (máximas D1 antes da queda de 29/10) |

### A.3 Matriz multitemporal (Kraken, 16:02 UTC)

| TF | Pilha EMA 8/20/50 | RSI | ADX (+DI/−DI) | MACD hist | Afastamento da EMA20 | Leitura |
|---|---|---|---|---|---|---|
| H1 | 8>20>50 ↑ (EMA20 78.342) | **77,0** | 25 (47/14) | + e subindo | +3,3 ATR(H1) | Tendência forte, **sobrecomprado** |
| M30 | 8>20>50 ↑ | **75,4** | 36 (47/10) | + e subindo | — | Forte, sobrecomprado |
| M15 | 8>20>50 ↑ (EMA20 79.203) | **72,8** | 41 (39/8) | + mas **caindo** (200 → 185) | **+2,6 ATR(M15)** | Esticado, momentum desacelerando |
| M5 | 8>20>50 ↑ (EMA20 79.926) | 64,5 | 45 (35/17) | **− e caindo** (−25 → −38) | +1,3 ATR(M5) | **Correção em curso** |
| M1 | sem pilha | 51 | 18 | ~0 | ~0 | Neutro, lateral |

**Estrutura de preço:**
- **H1:** BOS altista confirmado (rompeu 77.970, máxima de 03/11). Sem sinal de reversão.
- **M15/M5, desde 15:15:** **máximas descendentes** em 81.180 → 80.790 → 80.779 → 80.512 → 80.432 → 80.410 e **mínimas descendentes** em 80.266 → 80.181 → 80.116 → 80.078. É um canal de correção, uma *bull flag* em potencial, ainda **sem rompimento para nenhum lado**.
- **O piso atual (80.078)** coincide com a **retração de 38,2% (80.004)** e com o redondo 80.000.

### A.4 Microestrutura (medida)

**Livro de ofertas.** Profundidade em BTC; o desequilíbrio vai de −1 a +1, com valor positivo indicando mais compra.

| Faixa | Coinbase (compra / venda / deseq.) | Kraken (compra / venda / deseq.) |
|---|---|---|
| ±0,1% | 20 / 23 / −0,07 | 66 / 43 / **+0,21** |
| ±0,25% | 63 / 93 / **−0,19** | 110 / 139 / −0,12 |
| ±0,5% | 148 / 178 / −0,09 | 138 / 172 / −0,11 |
| ±1,0% | 157 / 186 / −0,09 | 165 / 251 / **−0,21** |

- **Maiores concentrações de venda (baldes de US$ 100):** 80.400 (56 + 71 = 127 BTC), 80.500 (44 + 58 = 102 BTC), 80.600 (60 BTC), 80.800 (46 BTC).
- **Maiores concentrações de compra:** 80.000 (61 + 18 = 79 BTC), 80.100 (42 + 31), 80.200 (39 + 50).
- **Leitura:** o preço está **preso num corredor de ~US$ 200**, entre a demanda em 80.000–80.200 e a oferta em 80.400–80.600. A oferta visível dentro de ±1% é maior que a demanda.

**Fluxo agressor (Kraken):**

| Janela | Compra agressora | Venda agressora | Delta |
|---|---|---|---|
| 3 min | 11,6 | 55,4 | **−43,8 BTC (−0,65)** |
| 5 min | 15,2 | 72,8 | **−57,6 BTC (−0,65)** |
| 10 min | 29,4 | 83,2 | −53,8 BTC (−0,48) |
| 20 min | 106,6 | 104,0 | +2,6 BTC (≈ 0) |

- **Coinbase, últimos ~96 s:** delta de −7,2 BTC (−0,21).
- **Leitura:**
  - Das 15:48 às 15:50, compras agressoras levaram o preço a 80.445, mas não romperam a oferta em 80.400–80.500.
  - Às 15:58–15:59, uma venda agressora forte (−42 BTC) foi **absorvida** em 80.078–80.110 por ordens passivas de compra. Isso sustenta o piso.
  - Depois disso, o fluxo segue vendedor, mas o preço não cai. **O mercado está equilibrado e em disputa, sem direção imediata.**

### A.5 Classificação pelo mesmo modelo usado no Forex (0–100)

| Direção | Score | A tend. | B mom. | C local | D espaço | E timing | F exaustão | G custo | Filtros violados | Classe |
|---|---|---|---|---|---|---|---|---|---|---|
| BUY | 60,6 | 20,0 | 11,9 | 10,7 | 1,0 | 10,0 | 2,0 | 5,0 | obstáculo a 0,2 ATR (80.400); esticado 2,6 ATR; dia > 1 ADR; RSI H1 > 72 | **C** |
| SELL | 29,6 | 0 | 6,8 | 2,0 | 3,9 | 2,0 | 10,0 | 5,0 | H1 contrário; suporte a 0,7 ATR (80.000) | **D** |

O score é **ferramenta de ordenação, não probabilidade**. Nenhuma taxa de acerto é apresentada.

---

## B. Ranking das configurações avaliadas no BTC/USD

1. **BUY em pullback para 79.550–79.700, com confirmação (condicional). É a melhor assimetria.**
   - A zona junta: 50% do impulso (79.640), o topo das 14:45 que pode virar suporte (79.548), um cluster de níveis H1 (79.560–79.710) e a EMA20-M15 subindo em direção a ela.
   - Fica a favor da tendência H1 e **fora** da zona esticada.
   - Ponto fraco: está dentro do vácuo de volume (78.600–80.000), então o preço pode atravessá-lo rápido. Por isso a confirmação é obrigatória.

2. **BUY no rompimento da bull flag (fechamento M15 acima de 80.800).**
   - A favor da tendência, mas com só ~US$ 380 (0,9 ATR M15) até a máxima do dia e oferta em 81.700–81.880 logo depois.
   - Em dia de 2,9 ADR, rompimentos de máxima descendente têm risco alto de falhar.

3. **BUY a mercado agora (80.311). Recusado.**
   - Paredes de 127 BTC a US$ 90 acima.
   - Preço esticado em 2,6 ATR, RSI H1 de 77 e o movimento do dia já realizado.

4. **SELL no CHoCH (fechamento M15 abaixo de 79.950). Recusado como operação.**
   - Seria contra a tendência.
   - O alvo natural (79.650) fica a ~US$ 300, com stop acima de 80.450 (~US$ 500): relação risco/retorno abaixo de 1.
   - Esse cenário serve como **caminho** que levaria o preço à zona do setup nº 1.

5. **SELL a mercado agora. Recusado.**
   - Contra a tendência H1/M30/M15.
   - Direto sobre o suporte 80.000–80.200 (79 BTC visíveis em 80.000 e venda agressora já absorvida ali).

---

## C. Operação principal selecionada

```
ATIVO:              BTC/USD (spot)
DIREÇÃO:            NENHUMA A MERCADO AGORA — sem entrada imediata tecnicamente justificável
PREÇO SPOT ATUAL:   Coinbase 80.307,59 / 80.310,96 · Kraken 80.310,80 / 80.310,90 (16:02:22–24 UTC)
HORÁRIO DA ANÁLISE: 04/11/2026, 16:02:24 UTC (13:02:24 BRT, UTC−3)
```

### Setup condicional prioritário: BUY em pullback (NÃO executar a mercado agora)

| Campo | Valor |
|---|---|
| **ATIVO / DIREÇÃO** | BTC/USD, **BUY somente após o gatilho** |
| **ZONA DE INTERESSE** | **79.550–79.700**: 50% do impulso (79.640), topo das 14:45 (79.548) e cluster de níveis H1 |
| **GATILHO** | Dentro da zona, um candle **M5 fecha acima da máxima do M5 anterior** e o **delta agressor desse candle é positivo** na Kraken ou na Coinbase (compra voltando a agredir). Sem esses dois sinais, não entrar. |
| **ENTRADA A MERCADO** | No primeiro tick depois do fechamento do candle de gatilho. Referência: **ask ≈ 79.700**. |
| **STOP-LOSS** | **79.150**: abaixo da retração de 61,8% (79.277) e da mínima da H1 das 15:00 (79.194). Perder esse nível desfaz a leitura de pullback saudável. Risco ≈ **US$ 550 (0,69%)**. |
| **TAKE-PROFIT 1** | **80.450** (50%): logo abaixo das paredes de 80.400–80.600 e do VWAP ancorado na máxima (80.506). **+US$ 750**. Depois disso, mover o stop para a entrada. |
| **TAKE-PROFIT 2** | **81.100** (50%): logo abaixo da máxima do dia (81.180). **+US$ 1.400**. |
| **RELAÇÃO RISCO/RETORNO (bruta)** | TP1 1,36 : 1 · TP2 2,55 : 1 · **média ponderada ≈ 1,95 : 1**. O spread (< 1 bp) não altera o resultado. |
| **RELAÇÃO RISCO/RETORNO (com taxas)** | Com **0,10% por lado** (~US$ 160 por BTC na ida e volta): TP1 0,83 : 1 · TP2 1,75 : 1 · **média ≈ 1,3 : 1**. Com **0,40% por lado** (~US$ 640): **inviável** (média ≈ 0,4 : 1). Só faz sentido com taxa ≤ 0,10% por lado ou com ordem limitada (maker). |
| **VALIDADE DO SINAL** | Até **20:00 UTC** de hoje, com reavaliação por novo snapshot no gatilho. **Cancelar** se: (a) o preço fizer nova máxima acima de 81.180 antes do pullback (setup obsoleto); (b) houver fechamento M15 abaixo de 79.150 antes do gatilho (correção profunda, próximo ímã no VWAP do dia em 78.350); (c) o preço chegar à zona num único candle M5 maior que 2 ATR(M5), ou seja, > US$ 620, com delta muito negativo (esperar estabilizar). |
| **CONFIANÇA DA CONFIGURAÇÃO** | **Moderada-baixa.** A favor: tendência H1 forte e pullback para a zona de valor. Contra: dia de 2,87 ADR (mais risco de reversão à média), zona dentro de um vácuo de volume, livro com mais oferta que demanda dentro de ±1%, e taxas que comprimem a assimetria. |

## D. Justificativa técnica

**1. Por que este setup é o melhor entre os avaliados.**

É o único que combina as três condições: tendência alinhada (H1, M30 e M15 com EMAs empilhadas e BOS em H1), entrada **perto do valor** e não no extremo, e espaço até o primeiro obstáculo relevante. O espaço vai até 80.000 (~0,7 ATR, onde as antigas paredes de compra podem virar resistência) e depois até 80.400–80.600.

As alternativas falham por motivos objetivos:
- **Comprar agora:** esticado e colado na oferta.
- **Comprar o rompimento:** pouco espaço até 81.180 e 81.700.
- **Vender:** contra a tendência e com relação risco/retorno abaixo de 1.

**2. Por que a zona 79.550–79.700 é tecnicamente favorável.**

- A **retração de 50%** de um impulso de alto volume é o ponto clássico de reentrada quando a tendência continua.
- **79.548** foi o topo das 14:45 antes da aceleração: resistência rompida que tende a virar suporte.
- A **EMA20-M15** (79.203 e subindo ~US$ 60 por barra) deve se aproximar da zona nas próximas horas, juntando média e nível.
- Entrar ali reduz o afastamento da EMA20-M15 de +2,6 ATR (agora) para ~+1 ATR, saindo da zona de exaustão.

**3. Evidências que sustentam a continuação, se o gatilho ocorrer.**

- Estrutura H1 intacta, com sequência de topos e fundos ascendentes e BOS sobre 77.970.
- Correção atual em canal, com volume menor que o do impulso (M5 de 20–70 BTC contra 100–140 BTC no impulso). Esse é o padrão de uma pausa, não de distribuição.
- A absorção da venda agressora em 80.078–80.110 mostra demanda passiva defendendo a região.
- O gatilho exige que a **compra agressora volte**, medida no delta do candle. Assim a entrada não depende só do nível.

**4. Por que não é compra em topo.**

- O topo do dia está em 81.180. A zona de entrada fica **US$ 1.500–1.600 abaixo** (cerca de 3,5 ATR de M15).
- A retração já teria devolvido metade do impulso e o RSI M15 tenderia a voltar à faixa de 45–55.
- O stop fica atrás de uma estrutura (61,8% e a mínima da H1 das 15:00), não num número arbitrário.

**5. O que pode provocar correção ou reversão.**

- **Reversão à média de um dia de 2,87 ADR.** O VWAP do dia (78.353) e o nó de alto volume em 78.200–78.400 são ímãs naturais se 79.150 cair.
- **Vácuo de volume** entre 78.600 e 80.000: sem negociação acumulada, o preço pode atravessar a zona sem reagir. Por isso o gatilho é obrigatório.
- **Oferta acima:** 80.400–80.600 e, sobretudo, a região de 81.700–81.880, de onde houve a queda de 29/10.
- **Eventos não programados.** Cripto opera 24/7 e é sensível a notícias regulatórias ou de fluxo de ETFs fora do horário comercial.

**6. Invalidação imediata.**

- **Antes do gatilho:** fechamento M15 abaixo de **79.150**. O setup morre e a próxima referência é 78.350–78.770 (VWAP do dia e VWAP ancorado na mínima).
- **Depois da entrada:** fechamento M5 abaixo de **79.450** com delta negativo, ou seja, o fundo do gatilho perdido com venda agressora. Sair sem esperar o stop.
- **Em qualquer momento:** stop técnico em **79.150**.

---

### Reprodutibilidade

- `btc_fetch_live.py <dir>`: baixa top of book de 4 venues, candles Kraken e Coinbase, livros L2 e negócios com o lado do agressor (com paginação na Kraken).
- `btc_analyze.py <dir>`: matriz multitemporal, contexto diário, VWAPs, perfil de volume, profundidade e desequilíbrio do livro, delta e score de qualidade de entrada (mesmos pesos do scanner de Forex).
- `snapshots/2026-11-04T1602Z-BTC/`: tickers brutos, a saída completa da análise (`analysis.txt`) e os snapshots anteriores de controle.

Nenhuma análise, sinal ou opinião de terceiros foi consultada. As fontes externas forneceram só preços, livros, negócios, timestamps e o horário oficial dos eventos.

*Isto não é recomendação de investimento. Criptoativos são altamente voláteis e operar com alavancagem amplia as perdas. Os resultados são probabilísticos e não garantidos.*

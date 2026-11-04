# Análise Forex Spot Intraday — Quarta-feira, 04/11/2026, 05:46 UTC

**Snapshot ao vivo**: cotações spot do feed FX do Yahoo Finance, carimbos de
05:45 a 05:46 UTC, com atraso de cerca de 40 s. Todas as leituras são cálculos
próprios feitos sobre os candles M1/M5/H1, sem análises de terceiros. Era o fim
da sessão asiática; Frankfurt abre às 07:00 UTC e Londres às 08:00 UTC.

## Sinal emitido

| Campo | Valor |
|---|---|
| **Par** | **GBP/JPY** |
| **Direção** | **COMPRA (long) a mercado** |
| **Preço no sinal** | **212.536** (05:46:18 UTC) |
| **Stop loss** | **212.27** (−26 pips; ≈1,1 ATR H1) |
| **Take profit 1** | **212.80** (+27 pips): realizar 50% e mover o stop para o breakeven |
| **Take profit 2** | **212.95** (+42 pips), logo abaixo do topo duplo 212.998/213.042 |
| **R:R ponderado** | ≈ 1 : 1,3 (TP1 1:1,0, TP2 1:1,6) |
| **Invalidação antecipada** | Fechamento M15 abaixo de 212.38 (base da bandeira): sair sem esperar o stop |
| **Validade** | Intraday, até a abertura de Londres. Sem progresso até 08:30 UTC → encerrar |

## Metodologia

**38 pares** analisados: as 28 combinações do G8 (USD, EUR, GBP, JPY, CHF, CAD,
AUD, NZD) mais USDSEK, USDNOK, EURSEK, EURNOK, USDMXN, USDZAR, USDSGD, USDHUF,
USDPLN e EURPLN.

- Seis timeframes: M1, M5, M15, H1, H4 e D1. O D1 e o H4 foram reconstruídos a
  partir do H1, com fechamento às 22:00 UTC (fechamento de NY), porque os
  candles diários do Yahoo para FX trazem fechamentos inconsistentes.
- Indicadores: EMA 8/20/50/200, RSI(14), MACD(12,26,9), ATR(14), ADX/DI± e
  largura das Bandas de Bollinger.
- Estrutura: swings fractais H1 (10 dias) e D1 (6 meses), máxima e mínima do
  dia anterior e posição do preço no range do dia.
- Filtros anti-perseguição (sem comprar no topo nem vender no fundo):
  - extensão do preço vs EMA20 em M5, M15 e H1, medida em ATRs;
  - RSI extremo;
  - posição maior que 90% no range do dia;
  - distância até o próximo nível contrário;
  - range do dia já consumido (> 1,3× ATR diário).
- Teste condicional histórico do setup no próprio GBPJPY (6 meses de H1), ver abaixo.

## Leitura do mercado (desde o fechamento de NY, 22:00 UTC)

1. **00:00–02:00 UTC — choque de aversão a risco.** O USD foi vendido em bloco:
   EURUSD +81 pips, USDJPY −127, USDCHF −69. JPY e CHF foram comprados. O
   horário coincide com a apuração das eleições de meio de mandato dos EUA (3/nov).
2. **04:35 UTC — virada para apetite a risco.** AUD, ZAR, MXN e HUF passaram a
   ser comprados. JPY e CHF devolveram os ganhos. As cruzadas de JPY subiram em
   bloco e o USD se recuperou parcialmente.
3. **Força relativa** (média % por moeda):
   - Desde 22:00 UTC: JPY +0,19 · CHF +0,17 · EUR +0,09 · GBP +0,02 · CAD −0,01 ·
     NZD −0,04 · AUD −0,10 · USD −0,31.
   - Últimas 3 h: AUD +0,32 · USD +0,13 · CAD +0,07 · NZD +0,07 · GBP −0,01 ·
     EUR −0,10 · JPY −0,11 · CHF −0,36.

## Tese do trade (GBPJPY long)

1. **A tendência maior está a favor.** No D1, os fechamentos sobem há duas
   semanas (209.87 → 212.83). H4 e H1 têm as EMAs 8 > 20 > 50 empilhadas, com o
   preço acima da EMA8/EMA20 do H1 (212.52 / 212.47).
2. **O pullback do dia terminou num suporte defendido.** A queda do choque de
   risco (212.998 → 212.066) segurou acima do número redondo de 212.00 e muito
   acima da mínima de ontem (211.516). A partir daí o M5 fez mínimas
   ascendentes: 212.066 → 212.113 → 212.162 → 212.259 → 212.288 → 212.38.
3. **A bandeira de continuação foi rompida.** Houve 45 minutos de consolidação
   entre 212.38 e 212.513 (base dupla em 212.384/212.382). O rompimento veio às
   05:40 UTC (212.534, depois 212.554). Em seguida o preço reteve acima do topo
   da bandeira e o candle H1 das 05:00 fechou perto da máxima.
4. **A entrada não está no topo.** O preço está a 46% do range do dia
   (212.066–212.998), +0,2 ATR acima da EMA20 do H1 e +0,3 ATR acima da EMA20
   do M15. O RSI está em 62 no M5, 53 no M15 e 55 no H1, sem sobrecompra. Há 46
   pips livres até a máxima do dia (212.998).
5. **O fluxo vigente ajuda.** O JPY é uma das moedas que mais perdem nas últimas
   3 h, e o GBPUSD se estabilizou e voltou a subir (1.3452 → 1.3459). As duas
   pernas do cruzamento empurram na mesma direção.
6. **Há catalisador de liquidez.** Frankfurt abre às 07:00 UTC e Londres às
   08:00 UTC, e o GBP é moeda doméstica dessa sessão.

## Teste estatístico do setup (honestidade sobre a vantagem)

O setup testado no GBPJPY usa 6 meses de H1: EMA 8 > 20 > 50 no H1 e no H4,
com fechamento a menos de 0,5 ATR da EMA20 do H1. O resultado é medido em
alvo/stop dentro de 8 h:

| SL / TP | Ocorrências | Acerto | Expectativa |
|---|---|---|---|
| 17 / 25 pips | 108 | 44% | +1,3 pip |
| 27 / 25 pips | 98 | 58% | +3,2 pips |
| 27 / 35 pips | 83 | 48% | +2,9 pips |
| 27 / 35 + H1 fechando acima da EMA8 | 20 | 55% | +7,1 pips (amostra pequena) |

**Conclusão:** a vantagem é positiva, mas modesta. O stop curto (≈0,7 ATR) foi
estatisticamente ruim, por isso o stop final ficou em ≈1,1 ATR H1 (26 pips). O
spread e o slippage do fim da sessão asiática, de 2 a 4 pips no GBPJPY, consomem
parte da expectativa. Não existe garantia de continuação imediata.

## Setups rejeitados (filtro anti-topo/fundo e anti-reversão)

| Par | Setup aparente | Motivo da rejeição |
|---|---|---|
| AUDUSD | Long (AUD é a moeda mais forte em 3 h) | Na máxima da sessão (99% do range), +3,9 ATR acima da EMA20 M5: compra no topo |
| USDZAR / USDMXN | Short (apetite a risco) | Nas mínimas da sessão, depois de quedas de 60–77 pips em 1 h: venda no fundo |
| EURAUD / GBPAUD | Short (−80 pips em 1 h) | Venda no fundo de uma queda vertical (−1,6/−1,9 ATR) e contra H1/H4 de alta |
| AUDJPY / NZDJPY | Long (JPY fraco) | Repique contra H1/H4 de baixa e já esticado (+2,1 ATR M5) |
| USDJPY | Long | Travado no 158.00 redondo e no cluster de swings 157.97–158.07; rejeitado 2× |
| CADJPY | Long | Abaixo da EMA20 do H1 (113.09) e colado no cluster 113.07–113.12 |
| AUDNZD | Long | Topo duplo em 1.2481 só 20 pips acima; momentum perdendo força (−12 pips em 30 min) |
| EURGBP | Short | ADX H1 15 e ATR H1 de 6,7 pips: sem energia para continuação imediata |
| USDCHF | Long (CHF mais fraco em 3 h) | Compra dentro do retrace de 50–61,8% de impulso de baixa, contra H1/H4 |
| EURCHF / GBPCHF / CADCHF / AUDCHF / NZDCHF | Long (CHF fraco) | Já subiram 30–40 pips em 1 h contra H1/H4 de baixa e encostaram na abertura do dia |
| EURNZD / GBPNZD | — | Sinais conflitantes: H4/D1 de alta, mas −60 pips intraday em 1,5 h |
| NZDUSD / NZDCAD | Short | ADX H1 de 12 e variação de 3 h nula: sem tendência intraday |
| Demais (escandinavos, PLN, HUF, SGD, EURCAD, GBPCAD, USDCAD) | — | Ranges estreitos, ADX baixo ou preço já colado em nível |

## Gestão de risco e ressalvas

- **Stop em 212.27.** Fica abaixo da base da bandeira (212.38), da estrutura das
  04:45–04:50 e do antigo swing D1 212.346. A perda desse nível invalida a
  sequência de mínimas ascendentes.
- **Alvos.** O TP1 (212.80) fica no meio da retomada até o topo. O TP2 (212.95)
  fica antes do topo duplo 212.998/213.042, onde se espera realização. Só manter
  um resto da posição além disso se o H1 fechar acima de 213.05.
- **Eventos.**
  - A apuração das eleições dos EUA continua e pode gerar novos choques no USD,
    que se transmitem ao JPY.
  - PMIs europeus e do Reino Unido saem na manhã europeia; dados dos EUA à tarde.
  - Confira o calendário antes de executar.
- **Risco de cauda no JPY.** Com o USDJPY perto de 158, existe risco de
  declarações das autoridades japonesas, que podem derrubar todas as cruzadas
  de JPY em segundos. Por isso o stop é obrigatório.
- **Spread e slippage não modelados.** Os dados são preços spot médios. No fim
  da sessão asiática o spread do GBPJPY costuma ficar mais largo.

---
*Análise técnica automatizada gerada a partir de dados spot ao vivo. Não constitui
recomendação de investimento. Scripts em `analysis/`: `fx_fetch.py` (coleta),
`fx_analyze.py` (ranking com 38 pares) e `fx_inspect.py` (detalhe por par).*

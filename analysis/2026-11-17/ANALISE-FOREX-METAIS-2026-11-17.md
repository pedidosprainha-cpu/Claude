# Varredura Forex + Metais: terça-feira, 17/11/2026, ~01:30 UTC

**Universo:** os 31 símbolos de Forex e Metais disponíveis no terminal MT5 RoboForex-ECN.
São 28 pares de moedas mais XAUUSD, XAGUSD e XAUEUR.
**Conta:** demo ECN, alavancagem 1:500, modo hedge, saldo de US$ 402,70 antes da operação.
**Dados:** OHLC do Yahoo Finance em M5, M15, H1 e D1. O H4 e o D1 foram reconstruídos a partir do H1, com
fechamento às 22:00 UTC, igual aos candles do servidor MT5. Os metais usam os futuros da COMEX como proxy
e o XAUEUR é sintético (GC/EURUSD). Bid/ask, spread, margem, swap e comissão foram lidos diretamente do terminal.

## Ordem executada

| Campo | Valor |
|---|---|
| **Ticket** | 785784643 |
| **Par / direção** | **EURUSD: VENDA (short) a mercado** |
| **Volume** | **1,01 lote** (101.000 EUR, cerca de US$ 111 mil de nocional) |
| **Entrada** | 1,09854 (03:32:18 no horário do servidor, 01:32 UTC) |
| **Stop loss** | 1,10140 (−28,6 pips, cerca de −US$ 289) |
| **Take profit** | 1,09400 (+45,4 pips, cerca de +US$ 459) |
| **R:R** | 1 : 1,59 |
| **Margem inicial** | US$ 221,91, nível de margem de 178% na abertura |
| **Alavancagem efetiva** | cerca de 276× o patrimônio |

### Por que esse volume ("o mais alavancado possível sem stop-out antes do SL")

Condição: com o preço no SL, o nível de margem (patrimônio/margem) precisa continuar acima do stop-out.

```
perda até o SL por lote  = (1,10140 − bid) × 100.000 + comissão de abertura (0,001% do nocional)
margem por lote no SL    = 1,10140 × 100.000 / 500 = US$ 220,28
volume máx               = Equity / (perda_por_lote + SO × margem_por_lote)
```

- Usei **SO = 50%**. A RoboForex informa 40% para contas ECN, mas não consegui confirmar no site oficial,
  porque a página carrega via JavaScript. Os 10 pontos percentuais extras cobrem slippage do SL (cerca de 2 pips)
  e a incerteza sobre o nível real.
- Resultado: **1,01 lote**. No SL, o patrimônio fica em cerca de US$ 113 e a margem em cerca de US$ 222,
  o que dá um **nível de margem de cerca de 51%**, acima dos 40% e também de um stop-out hipotético de 50%.
- **Risco real: se o SL for atingido, a perda é de cerca de 72% do saldo.** Esse é o custo direto da
  instrução "o mais alavancado possível".

## Metodologia (`analyze_all.py`)

Cada símbolo é pontuado em 6 camadas, que depois são combinadas:

1. **Regime de tendência D1/H4/H1**: empilhamento das EMAs 20/50/200, inclinação da EMA50 em ATRs,
   preço vs EMA50, ADX/DI±, sinal do histograma do MACD. Gera um score de −1 a +1 por timeframe.
2. **Estrutura de mercado H4/H1**: pivôs fractais, sequência HH/HL vs LH/LL.
3. **Força relativa das 8 moedas**: matriz dos 28 pares, retornos normalizados por ATR em 1, 5 e 20 dias.
4. **Qualidade do momentum**: zonas de RSI, aceleração do MACD, consistência direcional das últimas 12 barras M15.
5. **Localização e R:R**: S/R agrupados (pivôs D1+H4, máxima/mínima do dia e da semana anterior, números redondos),
   stop técnico atrás do último swing H1/H4, espaço até o primeiro nível contrário.
6. **Filtros de exaustão**: distância à EMA20-H4 em ATRs, RSI extremo, movimento do dia vs ATR D1, stop largo demais.

Depois do ranking, os finalistas passaram por revisão discricionária: gráficos D1/H4/H1 em `charts/`,
níveis de 2 anos e contexto fundamental.

## Força relativa das moedas

| Horizonte | Mais forte → mais fraca |
|---|---|
| 1 dia | USD, EUR, AUD, NZD, GBP, JPY, CAD, CHF (dia recém-aberto, pouco informativo) |
| 5 dias | **USD 1,65**, JPY 1,37, CAD 0,57, GBP −0,03, EUR −0,47, CHF −0,58, NZD −0,84, **AUD −1,68** |
| 20 dias | **USD 4,39**, GBP 1,56, JPY 0,96, EUR 0,15, CHF −0,19, CAD −0,44, NZD −2,55, **AUD −3,87** |

O dólar está perto da máxima de 19 meses, com o mercado precificando mais aperto do Fed depois do CPI forte.
O iene é sustentado pelo temor de intervenção, com USDJPY em cerca de 159,5. AUD e NZD são as moedas mais fracas da carteira.

## Ranking sistemático (top 12; tabela completa em `scan_output.txt`)

| # | Par | Dir. | Score | Tend. D1/H4/H1 | Estr. H4/H1 | RSI D1/H4/H1 | Ext. H4 (ATR) |
|---|---|---|---|---|---|---|---|
| 1 | **EURUSD** | Short | **4,62** | −0,98 / −1,00 / −1,00 | −1 / −1 | 30 / 20 / 31 | −2,86 |
| 2 | USDCHF | Long | 4,42 | 0,88 / 0,60 / 0,61 | 0 / +1 | 70 / 74 / 61 | +2,07 |
| 3 | NZDUSD | Short | 4,42 | −0,97 / −1,00 / −1,00 | 0 / −1 | 32 / 20 / 29 | −2,97 |
| 4 | USDCAD | Long | 4,29 | 0,94 / 0,60 / 0,91 | +1 / +1 | 73 / 79 / 67 | +1,92 |
| 5 | EURGBP | Short | 4,23 | −0,60 / −0,82 / −0,87 | −1 / −1 | 33 / 41 / 44 | −0,78 |
| 6 | GBPAUD | Long | 4,09 | 0,80 / 0,98 / 0,54 | +1 / +1 | 72 / 72 / 62 | +1,55 |
| 7 | GBPUSD | Short | 4,07 | −0,80 / −0,60 / −0,52 | −1 / −1 | 36 / 25 / 38 | −2,34 |
| 8 | XAGUSD | Short | 4,04 | −0,99 / −1,00 / −0,60 | −1 / −1 | 29 / 23 / 37 | −2,50 |
| 9 | AUDCAD | Short | 4,02 | −0,72 / −0,85 / −0,49 | −1 / −1 | 33 / 29 / 41 | −1,25 |
| 10 | CHFJPY | Short | 4,02 | −0,79 / −1,00 / −0,58 | −1 / −1 | 38 / 25 / 36 | −2,25 |
| 11 | GBPJPY | Short | 3,99 | −0,72 / −0,72 / −0,58 | −1 / −1 | 44 / 32 / 35 | −1,76 |
| 12 | GBPCHF | Long | 3,76 | 0,77 / 0,16 / 0,45 | +1 / +1 | 60 / 61 / 54 | +0,64 |

## Por que EURUSD short

1. **É o único par com tendência perfeitamente alinhada nos três timeframes** (−0,98/−1/−1) e com estrutura
   LH/LL confirmada no H4 e no H1. No H1, o preço desce em "escada" colado na EMA20 há 6 sessões, sem nenhum
   fechamento acima da EMA50.
2. **Rompimento de nível-chave:** perdeu 1,1000 (número redondo) depois de 4 horas de compressão entre
   1,0998 e 1,1006, e opera na menor cotação em cerca de 19 meses. As mínimas de outubro (1,1110/1,1095)
   ficaram para trás.
3. **Espaço livre até o alvo:** não há pivô diário entre 1,1000 e 1,0955. O alvo de 1,0940 equivale a
   cerca de 0,6 ATR D1 (73 pips) e está dentro da extensão típica de um dia direcional.
4. **Fundamentos a favor:** USD é a moeda mais forte em 5 e 20 dias, e EUR está no bloco fraco.
5. **Custo e execução:** spread de 0,1 a 0,2 pip, liquidez máxima (menor slippage no SL) e
   **swap positivo na venda (+1,9 pts/dia)**.

## Candidatos rejeitados

| Par | Motivo |
|---|---|
| NZDUSD short | Vende em cima da **mínima de 2 anos (0,5491, abr/2025)**, suporte maior a 5 pips |
| AUDUSD short | Esticado demais: RSI H4 14,6 e −3,1 ATR da EMA20-H4, caiu 3% em 9 dias sem respiro |
| GBPUSD short | No suporte de vários meses 1,3139–1,3185 (mínimas mensais de out/nov) |
| USDCAD long | Na resistência de vários meses 1,4248–1,4310 (triplo topo), RSI H4 79 |
| USDCHF long | 2º colocado e boa alternativa, mas com estrutura H4 indefinida, RSI H4 74, CHF porto seguro, e é a mesma aposta no USD (correlação de cerca de −0,9 com EURUSD) |
| EURGBP short | Encostado na mínima de setembro 0,8322; UK CPI e emprego nesta semana |
| XAGUSD short | Suporte 45,4–46,8 (mínimas de 2025) logo abaixo; spread de 15 pontos |
| AUDJPY / NZDJPY / CHFJPY / EURJPY short | Fortemente sobrevendidos no H4 (RSI 24–27), e o JPY sobe por temor de intervenção, que é um catalisador binário e pode reverter |
| XAUUSD / XAUEUR | Tendência D1 baixista, mas H4/H1 sem estrutura definida (0) e R:R < 0,5 |

## Riscos da operação

- **Sobrevenda:** RSI H4 em 20 e preço a −2,9 ATR da EMA20-H4. O SL em 1,1014 aguenta um reteste de
  1,1000–1,1006, mas **não aguenta um repique até a EMA20-H4 (cerca de 1,1046)**. O stop fica acima do
  último topo descendente do H1: se o preço voltar acima disso, a tese de rompimento cai.
- **Eventos:** US Retail Sales hoje às 13:30 UTC, ata do FOMC na quarta e CPI do Reino Unido na quarta.
  Um dado fraco nos EUA pode provocar correção do USD.
- **Suporte em 1,0955** (topo de mar/2025) antes do alvo: pode haver pausa ou repique ali.
- **Rollover às 22:00 UTC:** o spread alarga e a posição vendida é avaliada pelo ask. Um pico de spread
  pode acionar o SL. Isso seria uma saída pelo SL, não um stop-out.
- **Gestão sugerida (não automatizada):** se 1,0955 for rompido com fechamento H1 abaixo, mover o SL para
  o breakeven (1,0985).

## Observação técnica sobre o terminal web

No navegador usado para executar a ordem (Chromium headless), o painel de ordens do terminal web não
renderizava por causa de um erro de JavaScript do próprio terminal: `offsetWidth` de elemento indefinido em
um tooltip. O contorno foi um ajuste local de uma linha (`?.offsetWidth`) aplicado só nessa sessão do
navegador. A ordem foi enviada pelo formulário padrão do terminal.

---
*Análise técnica gerada por varredura automatizada e revisão manual. Não constitui recomendação de investimento.
Arquivos: `fetch_all.py` (coleta), `analyze_all.py` (varredura), `charts.py` (gráficos), `scan_output.txt`, `charts/`.*

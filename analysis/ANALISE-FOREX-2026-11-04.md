# Análise Forex Spot ao vivo — Quarta-feira, 04/11/2026, 01:22 UTC (sessão de Tóquio)

**Fonte de preços:** feed spot CCY (Yahoo Finance), coletado em snapshot simultâneo dos
40 pares (4 timeframes cada). Último tick usado: **01:22:06 UTC**. Atraso medido do
feed: ~20–50 s. Nenhuma análise de terceiros foi usada: todos os cálculos foram feitos
aqui, pelos scripts `fx_fetch.py` → `fx_analyze.py` → `fx_entry.py` → `fx_pick.py`.

## Sinal

| Campo | Valor |
|---|---|
| **Par** | **AUD/JPY** |
| **Direção** | **VENDA a mercado** |
| **Preço spot no sinal** | **110.217** (01:22:06 UTC) |
| **Faixa de entrada válida** | 110.18 – 110.28 (**não vender abaixo de 110.15**, pois aí já fica colado no suporte 109.95–110.00) |
| **Stop loss** | **110.40** (~18 pips ≈ 1,0 ATR-H1), acima da última máxima menor (110.366–110.374) |
| **Alvo 1** | **110.00** (~22 pips): realizar 50% e mover o stop para o breakeven |
| **Alvo 2** | **109.88** (~34 pips): cumprimento do ADR (máx. da sessão 110.617 − ATR-D1 73,9) |
| **R:R ponderado** | ≈ 1 : 1,6 |
| **Invalidação antecipada** | Candle M5 fechando **acima de 110.33** (volta para dentro do triângulo e acima da EMA20-M5): sair sem esperar o stop |

## Por que AUDJPY (e por que *não* é "venda no fundo")

1. **Moeda mais fraca × moeda que se fortalece.** O AUD é a moeda mais fraca em todas as
   janelas medidas: −0,26% no dia, −0,25% em 3h e −0,55% em 24h. O JPY está estável ou firme:
   +0,00% no dia e +0,05% em 3h. O diferencial é consistente nas três janelas.
2. **Ambiente de risk-off confirmado com dados próprios.** S&P fut −0,65%, Nasdaq fut −1,28%,
   Nikkei −1,47%, ASX −0,54%, DXY −0,32%. Venda de risco + iene é a combinação clássica que
   derruba AUDJPY.
3. **Alinhamento total de tendência.** EMAs 8<20<50 empilhadas para baixo em M5, M15, H1 e H4.
   O histograma do MACD está se expandindo negativamente **ao mesmo tempo** em M15 (−3,1), H1
   (−2,0 vindo de −0,9) e H4 (−3,0 vindo de −1,6). É momentum novo, sem divergência. ADX-H1 21
   com −DI 20,7 > +DI 10,9: tendência ganhando força.
4. **Estrutura de continuação.** Triângulo descendente desde as 22:00 UTC, com máximas menores
   em 110.617 → 110.571 → 110.528 → 110.501 → 110.374 contra a base 110.20–110.215. A base
   rompeu às 01:20 (mín. 110.182).
5. **Localização (o filtro anti-fundo):**
   - RSI H1 = 40 e H4 = 38, sem sobrevenda nos timeframes estruturais; RSI M15 = 35 (> 30).
   - O preço está no **meio do range de 20 dias** (108.65–111.55), não numa mínima relevante.
   - O próximo suporte relevante (109.95–109.97, mínima de ontem) fica a ~25 pips (≈1,4 ATR-H1).
   - Ainda há ~47% do ADR disponível na direção da venda.
6. **Menor exposição ao fluxo de USD:** no par, o fluxo de USD se compensa entre USDJPY
   (caindo) e AUDUSD. O trade isola a fraqueza do AUD contra o iene, ao contrário dos pares
   de USD, que estão todos esticados.

## Força relativa (01:22 UTC)

| Moeda | vs fech. anterior | 3h | 24h |
|---|---|---|---|
| CHF | +0,29% | +0,34% | +0,41% |
| EUR | +0,23% | +0,20% | +0,46% |
| GBP | +0,09% | +0,04% | +0,36% |
| JPY | +0,00% | +0,05% | −0,28% |
| NZD | −0,01% | −0,05% | −0,35% |
| CAD | −0,04% | −0,02% | +0,05% |
| AUD | −0,26% | −0,25% | −0,55% |
| USD | −0,30% | −0,31% | −0,10% |

Leitura: o USD está sendo vendido desde as 00:00 UTC, em 4 pernadas (00:15, 01:00, 01:13
e 01:20). CHF e EUR são os grandes compradores. O AUD é a moeda fraca de risco. O NZD caiu
com o dado de emprego (21:45 UTC) e **está repicando agora**, por isso os shorts de NZD
foram descartados.

## Quadro completo: 39 pares analisados (28 combinações G8 + 11 exóticos)

Ordenado pelo score bruto de continuação (tendência + momentum + força relativa), **antes**
dos filtros de localização. Os pares do topo foram rejeitados justamente porque estão nos
extremos. (USDCNH ficou de fora porque o feed não trouxe dados intradiários.)

| # | Par | Viés | Spot | EMA M5/M15/H1/H4/D1 | RSI M15 | RSI H1 | Var. dia (pips) | Veredito |
|---|---|---|---|---|---|---|---|---|
| 1 | AUDCHF | Venda | 0.56861 | −−−−− | 25 | 30 | -25.6 | Rompeu mínima de 20d com RSI M15 ~24 / H1 ~29 — venda no fundo |
| 2 | USDCHF | Venda | 0.81588 | −−−−0 | 23 | 31 | -42.4 | ADR >100% consumido, RSI M15 23, 1 pip da mínima |
| 3 | NZDCHF | Venda | 0.45675 | −−−−− | 29 | 32 | -8.9 | RSI M15 ~29, NZD repicando agora |
| 4 | AUDCAD | Venda | 0.97376 | −−−−− | 33 | 38 | -17.1 | RSI H4 30,6 e mínima de 120d (0.9717) a ~20 pips |
| 5 | EURAUD | Compra | 1.61279 | ++++− | 81 | 76 | +72.7 | RSI M15 81, +0,96 ADR no dia — compra no topo |
| 6 | AUDJPY | Venda | 110.217 | −−−−− | 35 | 40 | -27.1 | **SELECIONADO** |
| 7 | CHFJPY | Compra | 193.802 | ++++0 | 68 | 68 | +58.4 | Máxima de 20d, ADR esgotado |
| 8 | CADCHF | Venda | 0.58391 | −−−−+ | 27 | 34 | -15.4 | RSI M15 ~27, colado na mínima |
| 9 | GBPAUD | Compra | 1.93051 | +++++ | 78 | 74 | +65.5 | RSI M15 78, na máxima — compra no topo |
| 10 | EURJPY | Compra | 177.774 | ++++− | 67 | 74 | +31.8 | Resistência 177.80–177.91 a 3–14 pips, RSI H1 72 |
| 11 | GBPCHF | Venda | 1.09783 | −−−−0 | 27 | 39 | -21.8 | RSI M15 ~29, perto da mínima |
| 12 | EURNZD | Compra | 2.00722 | +++++ | 73 | 77 | +42.4 | RSI H1 76, máxima de 20d |
| 13 | EURCHF | Venda | 0.91717 | −00−− | 34 | 47 | -8.8 | Forte vs forte (EUR≈CHF), diferencial fraco |
| 14 | EURUSD | Compra | 1.12423 | ++++− | 79 | 73 | +50.3 | RSI M15 80 / H1 77, na máxima, ADR esgotado — compra no topo |
| 15 | EURCAD | Compra | 1.57059 | +++0− | 74 | 70 | +36.6 | Na máxima da hora, D1 baixista |
| 16 | GBPNZD | Compra | 2.40261 | +++++ | 67 | 73 | +29.3 | RSI H1 ~74, +1,15 ADR em 24h; NZD repicando |
| 17 | USDMXN | Compra | 18.82200 | 0++++ | 57 | 68 | +120.0 | Exótico: spread/feed menos líquido; sem setup superior |
| 18 | GBPUSD | Compra | 1.34561 | ++++0 | 75 | 71 | +44.4 | RSI M15 76, ext. 4 ATR-M5 acima da EMA20 |
| 19 | NZDJPY | Venda | 88.556 | −−−−− | 38 | 40 | -1.9 | NZD repicando; rejeição forte em 87.80 (suporte de 60d) |
| 20 | USDCAD | Venda | 1.39737 | −0+0− | 30 | 43 | -33.1 | ADR ~80% consumido, suporte 1.3950–1.3970 |
| 21 | USDSEK | Venda | 9.74357 | −−−−0 | 31 | 31 | -410.1 | Exótico: spread/feed menos líquido; sem setup superior |
| 22 | GBPCAD | Compra | 1.88008 | ++++− | 59 | 63 | +18.7 | D1 baixista, momentum fraco |
| 23 | USDJPY | Venda | 158.156 | −0++0 | 30 | 45 | -46.8 | RSI M15 ~29, na mínima, contra tendência H1/H4 |
| 24 | USDNOK | Venda | 9.25468 | −−00− | 37 | 44 | -207.0 | Exótico: spread/feed menos líquido; sem setup superior |
| 25 | NZDCAD | Venda | 0.78230 | −−−−− | 38 | 36 | +3.1 | Na mínima de 20d; NZD repicando |
| 26 | USDZAR | Venda | 16.58380 | −−−0+ | 39 | 42 | -236.0 | Exótico: spread/feed menos líquido; sem setup superior |
| 27 | EURHUF | Venda | 364.452 | 0−−−0 | 53 | 51 | +12.1 | Exótico: spread/feed menos líquido; sem setup superior |
| 28 | USDTRY | Compra | 50.006 | +++++ | 53 | 57 | -19.0 | Exótico: spread/feed menos líquido; sem setup superior |
| 29 | EURSEK | Venda | 10.95447 | −00−− | 44 | 47 | -60.8 | Exótico: spread/feed menos líquido; sem setup superior |
| 30 | EURNOK | Compra | 10.40490 | +++0− | 67 | 59 | +168.1 | Exótico: spread/feed menos líquido; sem setup superior |
| 31 | EURGBP | Compra | 0.83538 | ++0−− | 71 | 65 | +14.7 | Na máxima, H4/D1 contra |
| 32 | CADJPY | Venda | 113.177 | −0++0 | 43 | 51 | -3.2 | CAD≈JPY, sem diferencial |
| 33 | GBPJPY | Compra | 212.798 | −+++0 | 49 | 65 | +17.5 | Lateral 212.62–213.00 há 3h, momentum M5/M15 negativo |
| 34 | AUDNZD | Venda | 1.24444 | 0+00+ | 50 | 53 | -25.1 | Sem tendência (spike do dado NZ revertendo) |
| 35 | EURPLN | Compra | 4.41490 | +00++ | 63 | 52 | +73.4 | Exótico: spread/feed menos líquido; sem setup superior |
| 36 | AUDUSD | Venda | 0.69720 | +0−−− | 52 | 42 | +2.9 | Briga de fracos (AUD × USD), sem direção |
| 37 | USDHKD | Compra | 7.84604 | −0+++ | 47 | 51 | +2.4 | Exótico: spread/feed menos líquido; sem setup superior |
| 38 | NZDUSD | Compra | 0.55991 | 0−−−− | 48 | 40 | +12.8 | Briga de fracos (NZD × USD), consolidação |
| 39 | USDSGD | Venda | 1.27944 | −−0++ | 27 | 39 | -18.0 | Exótico: spread/feed menos líquido; sem setup superior |

## Metodologia

- **Timeframes:** M1, M5, M15 (reamostrado do M5), H1, H4 (reamostrado do H1) e D1. O
  fechamento diário do feed vem corrompido (close ≈ open), então foi reconstruído a partir da
  abertura do dia seguinte, usando o spot atual como fechamento do dia em formação.
- **Indicadores:** EMA 8/20/50/200, RSI(14), MACD(12,26,9), ATR(14), ADX(14)/DI±, swings
  fractais (D1 e H1), máx./mín. de 20/60/120/250 dias e range da sessão desde 22:00 UTC
  (fechamento de NY).
- **Força relativa:** média da variação % de cada moeda contra as outras 7 do G8, nas
  janelas do dia, de 3h, de 24h e de 10/30/60 min (M1).
- **Filtros de localização (proíbem comprar topo e vender fundo):** ADR restante ≥ 35%,
  RSI-M15 ≤ 70 e RSI-H1 ≤ 72 na direção do trade, extensão ≤ 1,6 ATR-M5 da EMA20, distância
  ≥ 1 ATR-H1 até a próxima barreira relevante, posição no range da última hora e retração da
  última pernada M5.

## Riscos e gestão

- **PMI de serviços da China previsto para ~01:45 UTC** (confira no seu calendário): pode
  provocar um spike no AUD nos dois sentidos. Quem quiser evitar o evento pode reduzir o lote
  ou já sair com 50% no Alvo 1.
- **Apuração das eleições de meio de mandato dos EUA (03/11):** é o fluxo que move o USD na
  sessão. Uma reversão brusca de USD (USDJPY subindo forte) é o principal risco de squeeze
  contra o trade.
- **Execução:** os preços são cotações médias do feed spot, sem spread nem slippage. Confira o
  bid na sua plataforma antes de executar. Se o preço já estiver abaixo de 110.15, não entre.
- **Gestão:** ao atingir 110.00, realizar 50% e mover o stop para a entrada. Para o restante,
  arrastar o stop acima de cada nova máxima menor de M5.

---
*Análise técnica gerada a partir de dados spot ao vivo. Não constitui recomendação de
investimento. Operar Forex envolve risco elevado de perda.*

# Análise Forex Spot ao Vivo — Quarta-feira, 04/11/2026, 13:42 UTC

**Fonte de preço:** feed spot CCY (Yahoo Finance), 36 pares capturados em paralelo no
mesmo snapshot (idade do último tick: 0–3 s nos crosses/majors; 18 s em AUDUSD/NZDUSD).
Coerência dos cruzamentos checada (ex.: EURCHF ÷ EURUSD = 0.8149 ≈ USDCHF 0.8151).
Análise 100% própria — nenhuma análise de terceiros consultada.
Dia de trading contado a partir do fechamento de NY (22:00 UTC de 03/11).

## Sinal

| Campo | Valor |
|---|---|
| **Par** | **USD/CHF** |
| **Direção** | **VENDA a mercado** |
| **Preço spot no sinal** | **0.81543** (13:42:25 UTC) |
| **Stop loss** | **0.8166** (+12 pips) |
| **Take profit 1** | **0.8133** (−21 pips, R 1.75) — realizar 50% e mover o stop para o breakeven |
| **Take profit 2** | **0.8115** (−39 pips, R 3.25) |
| **R:R ponderado** | ≈ 1 : 2.5 |
| **Invalidação** | fechamento M15 acima de 0.8162 |
| **Acelerador** | rompimento de 0.8145 (piso da micro-consolidação, testado 3×) |

## Por que este é o melhor ponto de entrada

1. **Moeda mais fraca contra a mais forte no curto prazo.** USD é a moeda mais
   fraca do dia (−0.59 % médio contra os 7 pares G8) e de novo na janela de 4 h e de 1 h.
   O CHF é a moeda mais forte nas últimas 4 h (+0.08 % a +0.13 % ao longo das
   leituras). Considerando dia + 4 h + 1 h, **USDCHF tem o maior diferencial de
   força entre os 72 setups pontuados** (36 pares × 2 direções).
2. **Tendência alinhada em todos os tempos gráficos.** EMAs 8<20<50 empilhadas
   para baixo de M1 a H4; ADX H4 37 (DI− 31.9 contra DI+ 9.8) e ADX H1 29 (DI− 27.9
   contra DI+ 14.3). No diário, topos e fundos descendentes desde a máxima de
   14/out (0.8395): topos 0.8313 → 0.8255 → 0.8253 → 0.8217 → 0.8211, fundos 0.8176 → 0.8149 → 0.8127.
3. **Venda no repique, não no fundo.** A 1ª perna do dia levou de 0.8211 a 0.8127
   (84 pips). Depois veio uma correção de 64 % até 0.8181 (10:00–11:00 UTC) e,
   desde então, a 2ª perna, com topos M15 descendentes (0.8181 → 0.8172 → 0.8162 → 0.8155).
   O preço está consolidando entre 0.8145 e 0.8158 e **a entrada fica no teto
   dessa faixa**: em cima da EMA20 de M5 (0.8155) e 0.6 ATR abaixo da EMA20 de M15
   (0.8161). Às 13:41 o preço foi rejeitado em 0.8157.
4. **Sem esticamento e sem sobrevenda.** RSI M15 42, RSI H1 38, distância da
   EMA20-M5 de −0.3 ATR. O preço está a 27 pips da mínima do dia, ou seja, não é
   venda no fundo.
5. **Espaço até o alvo.** Abaixo da mínima do dia (0.8127/0.8131), o próximo
   swing H1 relevante só aparece em 0.8084 (09–10/set). Projetando a 2ª perna
   com o tamanho da 1ª, o alvo fica em ~0.8097, e o TP2 em 0.8115 é conservador.
6. **Stop técnico curto.** O stop em 0.8166 fica acima dos topos da
   micro-faixa (0.8158), da EMA20-M15 (0.8161) e do swing de 12:30 (0.81616).
   Se o preço chegar lá, a sequência de topos descendentes da 2ª perna deixa de existir.

## Ranking final (scanner `fx_setups.py`, 13:42 UTC)

| # | Setup | Score | Observação |
|---|---|---|---|
| 1 | **USDCHF venda** | **14.7** | escolhido |
| 2 | USDCAD venda | 11.2 | rejeitado: fundo triplo em 1.3926 (12:45/13:00/13:15), venda em cima de suporte |
| 3 | USDSEK venda | 10.3 | exótico (spread largo), M1/M5 ainda subindo, sem retomada |
| 4 | EURCAD compra | 10.0 | lateral 1.5686–1.5716 há 3 h, força líquida baixa (EUR +0.14 vs CAD −0.05) |
| 5 | NZDCAD compra | 8.6 | pullback à EMA50-M15 válido, mas só 16 pips até a máxima 0.7875 (0.4 ATR-M15) |

## Setups rejeitados pelo filtro anti-topo/anti-fundo

| Pares | Motivo |
|---|---|
| EURJPY, GBPJPY, CHFJPY, AUDJPY, NZDJPY, CADJPY (compra) | Na máxima do dia (posição 0.95–1.00 do range), RSI M15 65–69, 1.4–2.2× o ADR. Compra no topo |
| EURUSD, GBPUSD (compra) | A 0.05–0.07 da máxima, em máximas de 20 dias. Compra no topo |
| AUDUSD, NZDUSD (compra) | Posição 0.91–0.94 do range, +2.2 ATR acima da EMA20-M5 (esticado) |
| USDPLN, USDSGD, USDZAR (venda) | A 0.05–0.10 da mínima do dia. Venda no fundo |
| EURNZD, GBPNZD, EURAUD, GBPAUD (venda) | Perto da mínima do dia (0.11–0.18 do range), depois de quedas de 130–180 pips |
| USDMXN | Exótico; spread incompatível com entrada de precisão |
| EURGBP, EURCHF, GBPCHF, CADCHF, AUDNZD, AUDCHF, NZDCHF, GBPCAD, USDJPY, EURNOK, EURSEK, USDNOK, AUDCAD | Sem tendência intradiária limpa (ADX-M15 13–24), lateral ou com sinais conflitantes entre tempos gráficos |

## Medidor de força (média % contra os pares G8, 13:42 UTC)

| Moeda | Dia | 4 h | 1 h |
|---|---|---|---|
| NZD | +0.47 | +0.02 | +0.12 |
| AUD | +0.25 | +0.04 | +0.04 |
| EUR | +0.14 | −0.01 | −0.02 |
| CHF | +0.11 | **+0.08** | +0.03 |
| GBP | +0.06 | −0.05 | −0.02 |
| CAD | −0.05 | +0.02 | −0.02 |
| JPY | −0.39 | −0.03 | −0.05 |
| USD | **−0.59** | **−0.07** | **−0.08** |

## Riscos e gestão

- **Calendário:** o ISM de Serviços dos EUA costuma sair no 3º dia útil do mês,
  às 10:00 ET (15:00 UTC), o que cai hoje. Se o TP1 não tiver sido atingido até
  14:55 UTC, mover o stop para o breakeven ou reduzir a posição antes do dado.
- O dia já está esticado: o range de USDCHF é de 84 pips, 1.7× o ADR de 20 dias.
  Por isso o TP1 fica antes da mínima do dia, e o TP2 só é buscado com o stop
  já no breakeven.
- Se o preço voltar acima de 0.8158 e fechar o M15 acima de 0.8162, encerrar sem
  esperar o stop.
- Spread e slippage não estão modelados (o feed é mid spot). Com spread típico de
  1–1.5 pip, o R:R efetivo fica em torno de 1 : 2.2.

---
*Análise técnica automatizada feita a partir de dados spot ao vivo. Não é
recomendação de investimento. Scripts em `analysis/`: `fx_fetch.py` (coleta),
`fx_analyze.py` (indicadores + força), `fx_setups.py` (pontuação de setups).*

## Atualização 13:58 UTC: o que deu errado

- **Feed spot:** a máxima de USDCHF depois do sinal foi **0.81617** (13:56 UTC) e
  o preço está em 0.8159 às 13:57:43. No feed mid, o stop de 0.8166 ficou 4 pips
  acima e não foi tocado. Um stop executado na corretora indica cotação ask mais
  alta, spread alargado ou stop mais apertado do que o publicado.
- **De qualquer forma, a tese perdeu validade.** O preço rompeu o teto da
  micro-faixa (0.8158) e quebrou a sequência de topos descendentes da 2ª perna.
- **Causa:** o fluxo virou contra a operação. Na abertura de NY, o USD passou de
  moeda mais fraca a mais forte no curto prazo (15 min +0.04 %, 1 h +0.03 %), e o
  CHF ficou negativo em 1 h (−0.05 %).
- **Erro de leitura:** no snapshot do sinal (13:42), o USD já era a moeda mais
  forte na janela de 15 min (+0.02 %). O scanner dava peso pequeno a essa janela e
  peso grande à força acumulada do dia (1.7× o ADR). Esse primeiro sinal de
  cobertura de vendidos em USD na abertura de NY deveria ter vetado a entrada.
- **Situação às 13:58:** nenhum dos 72 setups passa ao mesmo tempo no filtro de
  localização e no de retomada. O USD está em correção contra a tendência do dia e
  o ISM de Serviços sai às 15:00 UTC. **Sem nova entrada até o fluxo se definir.**

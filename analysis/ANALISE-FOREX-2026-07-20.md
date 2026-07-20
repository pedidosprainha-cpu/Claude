# Análise Forex Spot Intraday — Segunda-feira, 20/07/2026, 06:57 UTC

**Snapshot ao vivo** (feed spot CCY / Yahoo Finance, timestamps 06:52–06:57 UTC — minutos antes da abertura de Londres, 07:00 UTC).

## Sinal emitido

| Campo | Valor |
|---|---|
| **Par** | **CAD/JPY** |
| **Direção** | **COMPRA (long) a mercado** |
| **Preço no sinal** | 115.943 (06:57:07 UTC) |
| **Stop loss** | 115.79 (−15 pips) |
| **Take profit 1** | 116.08 (+14 pips, parcial 50% + stop no breakeven) |
| **Take profit 2** | 116.28 (+34 pips) |
| **R:R ponderado** | ≈ 1 : 1.6 |
| **Validade** | Intraday; invalidação técnica se fechar M15 abaixo de 115.85 |

## Metodologia

20 pares analisados individualmente em 4 timeframes (M5, M15, H1, D1):
EMA 8/20/50/200, RSI(14), MACD(12,26,9), ATR(14), ADX(14)/DI±, estrutura de
máximas/mínimas, níveis diários de 6 meses, gaps de abertura semanal, range
asiático, posição no range do dia, extensão do preço vs EMA20-M5 em ATRs
(filtro anti-sobre-extensão) e consistência direcional dos últimos 12 candles M15.

## Quadro de força relativa (variação no dia, em pips vs fech. sexta)

**CAD ≫ CHF, NZD > USD, JPY, AUD > EUR, GBP**

- EURCAD −47 | USDCAD −34 | GBPCAD −60 | CADJPY +28 → CAD moeda mais forte
- CHFJPY +40 | EURCHF −21 | GBPCHF −28 → CHF forte
- GBPUSD −16 | GBPJPY −22 → GBP mais fraca, junto com EUR

## Tese do trade (CADJPY long)

1. **Combinação forte-vs-fraco**: CAD é a moeda mais forte do dia; JPY está no
   bloco fraco (confirmação fundamental: CAD apontado como major mais forte e
   JPY como mais fraco, drivers petróleo/risk-on).
2. **Gap de abertura semanal altista (+25 pips) não preenchido e defendido** —
   mínima do dia 115.795 vs fech. sexta 115.657: comportamento "gap and go".
3. **Triângulo ascendente em M15**: mínimas ascendentes (115.795 → 115.846 →
   115.871 → 115.898) contra teto em 115.94–115.947 — máxima de sexta (115.940)
   testada 3× entre sexta e hoje. Coil comprimido: range do dia de só 13 pips
   vs ATR diário de 59 pips → energia acumulada para expansão.
4. **Alinhamento total de tendência**: EMAs 8>20>50 empilhadas em M5, M15 e H1;
   D1 em 4ª alta consecutiva (114.77 → 115.41 → 115.43 → 115.66 → 115.94).
   Consistência direcional M15 = 93%.
5. **Céu aberto acima do gatilho**: acima de 115.95, única resistência diária em
   116.086 (05/mai); depois, vácuo até 117.19. RSI H1 = 60 (força sem sobrecompra).
6. **Sem sobre-extensão**: preço a apenas +0.78 ATR da EMA20-M5 — não é
   perseguição de preço esticado; é compra de rompimento de compressão.
7. **Catalisador imediato**: injeção de liquidez da abertura de Londres no exato
   momento do sinal, com o preço encostado no gatilho (115.943).

## Setups rejeitados (filtro anti-pullback/reversão)

| Par | Setup aparente | Motivo da rejeição |
|---|---|---|
| USDCAD | Short (momentum CAD) | Preço **sentado em 1.4000** (número redondo + mínimas de junho 1.3990/1.3979 logo abaixo) — venda direto em cluster de suporte |
| EURCAD | Short (−47 pips no dia) | Prateleira de suporte 1.6015/1.6011/1.6004 + 1.6000 redondo a 18 pips — alvo sem espaço, risco de bounce e de gap-fill p/ 1.6065 |
| CHFJPY | Long (CHF forte, +40 no dia) | Cluster pesado de topos diários 201.32–201.47 (4 máximas de julho) a 15–30 pips — oferta logo acima |
| GBPCAD | Short (GBP fraca vs CAD forte) | Prateleira 1.8825–1.8807 a ~30 pips; par no meio de range semanal, sem tendência limpa |
| AUDNZD | Long (+12 pips em 3h) | Rebote contra tendência H1/D1 baixista após gap −31 pips — contra-tendência |
| GBPJPY | — | Gap baixista vs estrutura M15 altista: sinais conflitantes |
| EURUSD, USDJPY e demais | — | ADX baixo (<15 H1), sem direção, ranges estreitos pré-Londres |

## Gestão de risco e caveats

- Stop 115.79: abaixo da mínima do dia e da zona de defesa do gap — invalida a
  tese de "gap and go" e a sequência de mínimas ascendentes.
- TP1 116.08 na resistência de 05/mai; realizar 50% e proteger no breakeven.
- TP2 116.28 ≈ abertura do dia + 0.6× ATR diário (extensão típica de um dia direcional).
- **Risco de cauda**: USDJPY a 162.4 mantém risco de intervenção do MoF/BoJ sobre
  todos os crosses de JPY — mais um motivo para operação curta, com stop e TP intraday.
- Segunda-feira: calendário econômico tipicamente leve, mas conferir eventos de
  última hora antes da execução. Spread/slippage não modelados (dados spot mid).
- Falha de rompimento: se 115.95 for rompido e o preço devolver para dentro do
  triângulo com fechamento M15 < 115.88, reduzir/encerrar sem esperar o stop.

---
*Análise técnica automatizada gerada a partir de dados spot ao vivo; não constitui
recomendação de investimento. Scripts em `analysis/`.*

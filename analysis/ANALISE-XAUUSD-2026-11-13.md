# Análise XAU/USD ao vivo — Sexta-feira, 13/11/2026, 02:09 UTC

**Snapshot**: spot XAU/USD bid/ask **3909.17 / 3909.82** (Swissquote, 02:08:41 UTC), confirmado
por gold-api (3911.2, 02:08:16 UTC). Barras intraday vêm do COMEX GC=F (dez/26) e foram convertidas
para spot pela base ao vivo (≈ +5,5). Todos os níveis abaixo estão em spot e são aproximados (±3).
Sessão asiática, com baixa liquidez.

## Sinal

| Campo | Valor |
|---|---|
| **Ativo** | **XAU/USD** |
| **Direção** | **VENDA (short) a mercado** |
| **Preço no sinal** | ~3909.5 |
| **Stop loss** | 3936 (−26,5) — acima da zona de rompimento 3924–3934 |
| **Take profit 1** | 3880 (+29,5): realizar 50% e mover o stop para o breakeven |
| **Take profit 2** | 3853 (+56,5): mínima de 12/11, menor nível em 1 ano |
| **R:R** | TP1 1:1,1 · TP2 1:2,1 · ponderado ≈ 1:1,6 |
| **Convicção** | Moderada (a favor da tendência, mas entrando numa sessão de baixa liquidez) |
| **Invalidação** | Fechamento de H1 acima de 3925; nesse caso o repique deve buscar 3960–3964 |

## Tese

1. **Tendência primária baixista.** EMAs 8<20<50 estão empilhadas para baixo em H1, H4, D1 e W1.
   O ouro caiu do topo histórico de ~5.586 (jan/26) para a mínima de 1 ano em 3.852 (12/11).
   No D1: ADX 25, DI− 30,7 contra DI+ 15,6.
2. **O fundamental empurra para baixo.** O CPI quente aumentou as apostas de alta da Fed em dezembro
   (8–9/12) para ~87–90%. O DXY está na máxima de 19 meses (103,13, +1,6% em 5 dias), o
   US10Y está acima de 5% (5,10%, +5,5% em 5 dias) e o Brent está perto de US$ 96.
   Na correlação H1, o ouro tem −0,34 com o DXY.
3. **O repique asiático chegou sobrecomprado à resistência.** A alta foi de ~+37 (3877→3914),
   e o preço está encostado na EMA20 de H1 (3909,8), logo abaixo da Fibo 23,6% do último impulso
   (4150→3852 = 3920) e da antiga mínima de Londres de 12/11 (3924, suporte que virou resistência).
4. **O lower-TF mostra exaustão.** RSI de 72 no M5 e 71,5 no M15. StochRSI de 96 no M15 e 95 no H1.
   No M15 o preço está 2,5 ATR acima da EMA20 (esticado). O histograma do MACD no M5 está
   enfraquecendo (1,18 → 0,95), e o preço está lateral sob 3915 há ~45 min.
5. **O fechamento diário foi fraco.** O dia 12/11 fechou em 3878, no quintil inferior de um range
   de 149 pontos, sem reação de compradores em NY.

## Contra-argumentos e riscos

- O H4 StochRSI está em 14/5 (sobrevendido). Um repique mais longo, até 3924–3934 ou até a
  Fibo 38,2% (3964), é possível antes da retomada da queda. O stop foi posto fora dessa primeira zona.
- O D1 fechou levemente acima da mínima de 30/out (3871,7), o que deixa uma possível falha de rompimento.
  Se o preço perder 3871 de novo, a tese de venda se confirma.
- **PPI dos EUA (out) às 13:30 UTC hoje.** É evento de volatilidade nos dois sentidos. Se o TP1 não
  tiver saído antes, avalie reduzir o tamanho ou subir o stop para o breakeven antes do dado.
- Há fluxo físico Oeste→Leste: compradores asiáticos costumam aparecer em mínimas.
- Spread de ~0,65 e slippage não modelados. Os níveis vêm de futuros convertidos para spot.

## Níveis-chave (spot)

| Resistências | Suportes |
|---|---|
| 3915 máx. asiática de hoje | 3895–3898 EMA20 M5/M15, base do impulso |
| 3920 Fibo 23,6% | 3877–3880 abertura asiática / base pós-NY |
| 3924–3934 zona de rompimento de 12/11 | 3871,7 mínima de 30/out |
| 3960–3964 EMA200 M15 / Fibo 38,2% | 3852 mínima de 12/11 (1 ano) |
| 4000 Fibo 50% / número redondo | 3830 / 3800 extensões |

---
*Análise técnica automatizada feita com dados ao vivo. Não é recomendação de investimento.
Scripts: `analysis/xau_fetch.py` (coleta) e `analysis/xau_analyze.py` (indicadores).*

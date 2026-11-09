# Rompimentos — validação histórica do detector

Reconstituição walk-forward de **26437 alertas** em 64 dias (2026-08-25 a 2026-11-06): 32 ativos, M15 e H1, entrada a mercado no fechamento do candle do alerta, spread descontado, stop testado primeiro quando os dois são tocados no mesmo candle. Escolhas feitas por validação walk-forward (3 blocos) até 2026-10-23; **todos os números abaixo são do período de teste**, que o modelo não viu.

## Antes x depois

| | alertas | por dia | alvo antes do stop | R médio por trade |
|---|---|---|---|---|
| todos os rompimentos, plano antigo | 5750 | 442.3 | 27.8% | -0.168 |
| acionáveis pela regra antiga | 2917 | 224.4 | 30.0% | -0.144 |
| todos os rompimentos, geometria nova | 5750 | 442.3 | 45.8% | -0.084 |
| **melhores do modelo novo (A/A+)** | 650 | 50.0 | 53.2% | -0.023 |

Erro-padrão do R médio dos melhores (A/A+): ±0.035R (walk-forward: 1611 alertas, R médio -0.110).

## Estabilidade por bloco (walk-forward, fora da amostra)

| bloco | todos, plano antigo | todos, geometria nova | melhores do modelo (A/A+) | alertas |
|---|---|---|---|---|
| 1 | -0.217 | -0.165 | -0.168 | 540 |
| 2 | -0.227 | -0.121 | -0.090 | 578 |
| 3 | -0.181 | -0.120 | -0.071 | 493 |

Geometria escolhida na validação: stop ≥ 1,5 ATR H1, alvo 1 do plano. Notas por quantil da expectativa calibrada: A+ = melhores 3%, A = melhores 10% (corte -0.05R), B = 25%, C = 50%.
Poder de separação (AUC, 0,5 = acaso): modelo **0.652** x nota antiga 0.537.

## Por nota (modelo novo, teste)

| | alertas | por dia | alvo antes do stop | R médio por trade |
|---|---|---|---|---|
| A+ | 94 | 7.2 | 50.0% | -0.034 |
| A | 556 | 42.8 | 53.8% | -0.021 |
| B | 1200 | 92.3 | 54.7% | -0.041 |
| C | 1428 | 109.8 | 50.3% | -0.097 |
| D | 2316 | 178.2 | 38.0% | -0.107 |

## Por nota (regra antiga, teste)

| | alertas | por dia | alvo antes do stop | R médio por trade |
|---|---|---|---|---|
| A+ | 571 | 43.9 | 29.4% | -0.195 |
| A | 1239 | 95.3 | 31.0% | -0.135 |
| B | 1434 | 110.3 | 29.4% | -0.133 |
| C | 1290 | 99.2 | 25.4% | -0.201 |
| D | 1216 | 93.5 | 24.3% | -0.197 |

## Acionáveis do modelo novo por timeframe e classe (teste)

| | alertas | por dia | alvo antes do stop | R médio por trade |
|---|---|---|---|---|
| M15 | 549 | 42.2 | 54.3% | -0.004 |
| H1 | 101 | 7.8 | 47.5% | -0.125 |
| major | 249 | 19.2 | 58.6% | +0.084 |
| cross | 345 | 26.5 | 50.7% | -0.076 |
| metal | 56 | 4.3 | 44.6% | -0.168 |

## Calibração no teste (probabilidade prevista x frequência real)

| faixa | prevista | real | eventos |
|---|---|---|---|
| (0.0469, 0.312] | 24.3% | 27.7% | 1150 |
| (0.312, 0.403] | 35.7% | 35.3% | 1150 |
| (0.403, 0.482] | 44.3% | 46.3% | 1150 |
| (0.482, 0.557] | 52.0% | 56.3% | 1150 |
| (0.557, 0.718] | 60.2% | 63.1% | 1150 |

## Geometrias avaliadas (walk-forward)

| stop/alvo | alertas | R médio | AUC |
|---|---|---|---|
| p/p | 1611 | -0.198 | 0.545 |
| p/r1 | 1611 | -0.131 | 0.533 |
| p/r15 | 1611 | -0.190 | 0.527 |
| p/r2 | 1611 | -0.219 | 0.538 |
| h075/p | 1611 | -0.149 | 0.566 |
| h075/r1 | 1611 | -0.130 | 0.531 |
| h075/r15 | 1611 | -0.171 | 0.531 |
| h075/r2 | 1611 | -0.130 | 0.544 |
| h1/p | 1611 | -0.147 | 0.592 |
| h1/r1 | 1611 | -0.133 | 0.528 |
| h1/r15 | 1611 | -0.127 | 0.533 |
| h1/r2 | 1611 | -0.159 | 0.548 |
| h15/p | 1611 | -0.100 | 0.639 |
| h15/r1 | 1611 | -0.130 | 0.521 |
| h15/r15 | 1611 | -0.128 | 0.532 |
| h15/r2 | 1611 | -0.210 | 0.543 |

## O que mais pesa (coeficientes padronizados)

| feature | peso |
|---|---|
| rr1 | -0.272 |
| spread_ratio | -0.163 |
| rr1^2 | -0.154 |
| strength_dir | +0.101 |
| st_falso*brk_clv | +0.096 |
| brk_range | -0.070 |
| atr_pct | -0.065 |
| is_metal*htf_trend | +0.061 |
| liq | +0.059 |
| st_falso | -0.059 |
| htf_mom | -0.059 |
| tf_h1*rr1 | -0.057 |
| run_atr | -0.057 |
| tf_h1*htf_trend | +0.050 |
| brk_clv | -0.045 |

Limitações: spreads típicos constantes (sem bid/ask histórico), sem agenda econômica histórica, metais com candles de futuros, ~2,5 meses de M15 (limite do Yahoo), um único regime de mercado. Resultado passado não garante resultado futuro; o modelo deve ser retreinado periodicamente (research/breakout_replay.py + train_breakout_model.py).

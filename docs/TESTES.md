# Relatório de testes e avaliação

Data de execução: 12/11/2026 (ambiente Linux, 4 vCPU, dados reais via internet).

## 1. Testes automatizados

### Python (`python -m pytest`): 21 testes, 21 aprovados

| Área | Testes |
|---|---|
| Técnico | faixas dos indicadores; VWAP exige volume; BOS em tendência sintética; detecção de FVG; **causalidade do quadro MTF** (recalcular com dados truncados reproduz exatamente os valores passados) |
| Execução/rotulagem | stop primeiro em candle ambíguo; parcial no TP1 + breakeven; custos reduzem R; simetria de venda |
| Risco | conversão de moedas, dimensionamento (incluindo bloqueio quando o lote mínimo excede o risco), limites de perda e de posição por instrumento |
| Estatística/modelo | intervalo de Wilson, drawdown, PSR; o modelo **detecta habilidade em dados informativos e não detecta em ruído**; **purging** do walk-forward; limites do portfólio no backtest |
| Dados | parsing OANDA (pricing/candles); calendário e bloqueio por eventos (incluindo USD → metais); reparo de saltos de rolagem; ajuste spot dos metais |
| Integração | motor completo **offline** com provedor falso (estrutura do sinal e ausência de sinal sem modelo validado); API com autenticação, validação de configurações, análise, gráfico e bloqueio de execução real |

Os testes revelaram e corrigiram um erro de arredondamento no dimensionamento (0,0999… lote → 0,09).

### Android (`./gradlew testDebugUnitTest`): 5 testes, 5 aprovados

Decodificação, com os modelos Kotlin do app, de respostas **reais** capturadas do backend: health, quotes,
análise sem sinal, análise com sinal (todos os campos), gráfico, sinais, alertas e histórico.
Renderização JVM (Paparazzi) do cartão de sinal e do gráfico com níveis: ver [ANDROID.md](ANDROID.md).

## 2. Latência e confiabilidade (servidor local, 16 instrumentos)

Script: `scripts/benchmark.py` (55 requisições, **0 erros**).

| Operação | p50 | máx. |
|---|---:|---:|
| `GET /health` | 13 ms | 46 ms |
| `GET /quotes` (cache do servidor) | 14 ms | 17 ms |
| `GET /chart` H1 150 barras | 22 ms | 53 ms |
| `POST /analyze` com cache aquecido (×5) | 2,36 s | 2,40 s |
| `POST /analyze` a frio (1ª da hora) | 20,1 s | — |

Decomposição da análise aquecida: cotações 263 ms, dados 49 ms e cálculo 1,85 s.
Idade das cotações Yahoo no momento do teste: 17–26 s; gold-api: ~17 s.

## 3. Backtest e validação walk-forward

Relatório completo: [`reports/RELATORIO-BACKTEST-2026-11-12.md`](../reports/RELATORIO-BACKTEST-2026-11-12.md).

| Modelo | Período | n OOS | BSS | AUC | Trades (portfólio) | R médio | PF | Retorno | Máx. DD | Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| logística (primário) | desenv. 06/2024–12/2025 | 7.717 | −0,015 | 0,546 | 428 | −0,316 | 0,56 | −49,7% | −50,8% | −4,91 |
| logística (primário) | **holdout 2026** | 4.084 | +0,011 | 0,569 | 66 | +0,095 | 1,17 | +3,0% | −3,1% | 1,22 |
| logística (primário) | completo | 11.801 | −0,006 | 0,553 | 494 | −0,243 | 0,65 | −45,7% | −49,1% | −3,63 |
| gradient boosting | completo | 11.801 | +0,005 | 0,542 | 178 | −0,259 | 0,66 | −20,9% | −22,4% | −3,16 |
| todos os candidatos | completo | 11.801 | — | — | (portfólio) | −0,184 | — | −90,4% | — | — |

- Expectativa bruta (sem custos) de todos os candidatos: −0,040R (IC 90%: −0,059 a −0,021).
- Deflated Sharpe Ratio dos trades selecionados (6 configurações): ≈ 0.
- **Veredito:** sem vantagem estatística e econômica robusta. O modelo não é validado e o motor bloqueia sinais.

Métricas reportadas: Sharpe, Sortino, Calmar, Profit Factor, drawdown máximo e duração, expectativa com
bootstrap (IC 90%), teste t, PSR/DSR, estabilidade (R² da curva de capital), % de meses positivos, retornos
mensais, desempenho por setup, por instrumento e por período, além da tabela de confiabilidade das probabilidades.

## 4. Testes funcionais do painel web

Capturas automatizadas (Playwright) em desktop (1360 px, tema escuro) e celular (390 px, tema claro): ver
`docs/img/painel-*.png`. Sem erros de console, sem rolagem horizontal no celular, WebSocket ao vivo, imagens
do relatório carregando.

![Painel](img/painel-desktop.png)

## 5. O que NÃO foi testado (e por quê)

| Item | Motivo | Como validar |
|---|---|---|
| App em dispositivo/emulador | ambiente sem virtualização (KVM) | checklist em [ANDROID.md](ANDROID.md) |
| OANDA (dados e ordens) | sem credenciais | conta *practice*, `FXI_OANDA_*` |
| Período de operação em conta demo | requer semanas de mercado | usar "Executar em conta demo" e acompanhar o Histórico |
| Bloqueio por eventos no backtest | sem calendário histórico point-in-time | — |
| Usabilidade com usuários reais | fora do escopo do ambiente | — |

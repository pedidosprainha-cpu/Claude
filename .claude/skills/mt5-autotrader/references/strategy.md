# Estratégia, evidência e limites

## Índice
1. Universo e gráficos analisados
2. Setup padrão: reversão à média (MR)
3. Setups de tendência (PB, BO) — desligados
4. Pontuação de confluência
5. Gestão de risco
6. O que os testes mostraram
7. Limitações do backtest
8. Como pesquisar mudanças sem se enganar
9. Parâmetros

## 1. Universo e gráficos analisados

28 pares de Forex (7 majors + 21 cruzados) e metais (XAUUSD, XAGUSD; XPTUSD/XPDUSD se a
corretora oferecer). Para cada instrumento o motor baixa o gráfico H1 e reconstrói H4 e D1 a
partir dele — cerca de 90 gráficos reavaliados a cada hora fechada. Reconstruir a partir do H1
garante que operação ao vivo e backtest vejam exatamente os mesmos números.

Nomes de corretora (`EURUSDm`, `GOLD.a`, `EURUSD.pro`) são resolvidos automaticamente; casos
exóticos vão em `symbol_map` no `config.json`.

## 2. Setup padrão: reversão à média (MR)

Ideia: quando um par cruzado anda demais em poucas semanas, parte desse movimento costuma
devolver nos dias seguintes. O robô opera contra o esticão, com stop largo e saída por tempo.

- **Medida de esticão:** retorno dos últimos 20 dias dividido pela volatilidade diária
  (z-score, campo `daily_stretch_z` no `scan`).
- **Entrada:** `z ≥ +1,0` → vende; `z ≤ −1,0` → compra. Só em pares **cruzados**
  (`reversion_classes`), onde o efeito apareceu.
- **Stop:** 3 × ATR diário a partir do preço de entrada. É largo de propósito: o trade precisa
  de espaço para o movimento terminar antes de voltar.
- **Alvo:** nenhum. Sai após 240 barras H1 (10 dias de pregão) ou no stop.
- **Sem breakeven e sem trailing:** apertar o stop cedo corta justamente os trades que
  devolvem depois de piorar mais um pouco.
- **Mantém no fim de semana** (um trade de 10 dias atravessa pelo menos um).
- **Intervalo:** 24 barras antes de reentrar no mesmo símbolo.

Frequência esperada: cerca de 2 operações por semana na carteira toda, cada uma durando vários
dias. Taxa de acerto perto de 57%, com ganhos pequenos e perdas de 1R quando o stop pega.

## 3. Setups de tendência (PB, BO) — desligados

Implementados e disponíveis (`strategy.enable_pullback`, `strategy.enable_breakout`), mas
desligados porque perderam dinheiro no teste (seção 6).

- **PB (pullback):** tendência de alta no H4 (preço > EMA50 > EMA200, EMA50 subindo, ADX ≥ 18),
  D1 não contrário; no H1 o preço recua até a EMA20, o RSI esfria, e um candle de alta fecha
  acima da máxima anterior. Stop abaixo do fundo do recuo (1 a 2,5 ATR), alvo 2R.
- **BO (rompimento):** mesma tendência; consolidação apertada de 12 barras rompida com candle
  forte acima da máxima de 24 barras. Stop 1,5 ATR, alvo 2R.

Gestão dos dois: stop para o zero a zero em +1R, saída por tempo em 72 barras, tudo fechado
antes do fim de semana. Vendas espelham as compras.

## 4. Pontuação de confluência

Cada candidato recebe 0–100; o motor só opera com `min_score` (70) ou mais e, havendo vários ao
mesmo tempo, prioriza os de maior nota.

- MR: 72 a 80 conforme o tamanho do esticão, mais sessão (0–5), custo (0–5) e 5 fixos.
- PB/BO: viés D1 (até 15) + força da tendência H4 (até 25) + alinhamento H1 (até 15) +
  qualidade do gatilho (até 25) + força relativa das moedas (até 10) + sessão (até 5) +
  custo (até 5).

Força relativa: o momentum de cada moeda é a média do que ela fez contra todas as outras nos
28 pares; comprar a forte contra a fraca pontua mais.

## 5. Gestão de risco

| Regra | Conservador (padrão) | Moderado | Teto em código |
|---|---|---|---|
| Risco por operação | 0,5% do capital | 1,0% | 2,0% |
| Posições simultâneas | 4 | 5 | 10 |
| Risco total aberto | 2% | 4% | 6% |
| Perda máxima no dia | 2% → trava até o dia seguinte | 3% | 5% |
| Drawdown máximo | 8% → para tudo até liberação manual | 12% | 20% |

Outras travas: no máximo 2 posições com a mesma moeda do mesmo lado; uma posição por símbolo;
pausa de 12h após 4 perdas seguidas; no máximo 8 entradas por dia; spread acima de 12% da
distância do stop bloqueia; sem entradas na virada do dia (17h de Nova York, −30/+75 min) nem
depois das 12h de sexta (NY); bloqueio de 30 min antes e depois de notícia de alto impacto das
moedas envolvidas; nível de margem mínimo de 300%.

Tamanho do lote: perda no stop ≈ risco em dinheiro, arredondado **para baixo** ao passo da
corretora. Se nem o lote mínimo couber em 1,5× o orçamento, a operação é pulada — forçar
multiplicaria o risco sem ninguém perceber.

Com stop de 3 ATR diários, o lote mínimo de 0,01 costuma arriscar entre 15 e 25 dólares por
operação. A 0,5% de risco isso pede algo em torno de 2 a 3 mil dólares de capital; abaixo
disso a maioria das entradas é pulada. O `doctor` calcula o número exato para a conta e a
corretora em uso.

## 6. O que os testes mostraram

Dados: H1 de 30 instrumentos, 29/01/2024 a 13/11/2026 (Yahoo Finance; ouro e prata pelos
futuros). Custos assumidos por operação: 1,2 pip nos majors, 2,5 pips nos cruzados, US$ 0,35 no
ouro, US$ 0,035 na prata. Stop sempre considerado antes do alvo quando os dois cabem na mesma
barra.

**Tendência (PB + BO), todos os sinais:** 4.285 operações, −0,106R por operação, fator de
lucro 0,81, t = −5,9. Mesmo com custo zero o resultado foi negativo (−0,058R). Variações de
saída testadas (sem breakeven, alvo 1,5R e 3R, trailing, stop mais largo, ADX ≥ 25) ficaram
todas negativas. Só os metais ficaram positivos, o que reflete a alta forte do ouro no período
e não é base para uma regra.

**Efeitos clássicos, medidos direto no preço:** momentum de 24h a 50 dias, rompimento de
máxima de 20 e 55 dias, e fade de esticão intradiário — todos negativos depois de custos.

**Reversão em horizonte de dias:** foi o único efeito com o mesmo sinal nas duas metades da
amostra (reversão após movimento de 10–20 dias, mais clara nos cruzados).

**MR como configurado, perfil conservador:**

| | Amostra toda | Primeiros 60% | Últimos 40% |
|---|---|---|---|
| Operações | 253 | 150 | 103 |
| Expectativa por operação | +0,087R | +0,109R | +0,055R |

Fator de lucro 1,36 · acerto 57% · retorno total +11,3% em ~2,8 anos (≈ 4% ao ano) ·
drawdown máximo 7,7% · t = 1,97.

Leia esses números com cuidado:

- t ≈ 2 com 253 operações é evidência fraca, e os 28 pares compartilham moedas, o que infla a
  significância.
- A configuração saiu de uma grade de 12 combinações; a melhor de várias sempre parece melhor
  do que é.
- O resultado não cresce com o limiar (z ≥ 2 foi pior que z ≥ 1), o contrário do que um efeito
  robusto mostraria.
- É sensível à seleção: mudar só a hipótese de custo troca ~20% das operações e a expectativa
  oscila entre +0,08R e +0,11R.
- O drawdown do teste (7,7%) encosta no limite de 8% do perfil conservador: um halt na vida
  real é um cenário plausível, não uma anomalia.

Conclusão honesta: MR é a melhor candidata entre as testadas, não uma vantagem comprovada. Por
isso o robô começa em demo e a conta real passa por um critério de validação.

## 7. Limitações do backtest

- **Sem swap.** Trades de 10 dias pagam ou recebem juros todo dia; nos cruzados isso pode
  valer ±0,03 a 0,07R por operação — da mesma ordem da vantagem medida. O `report` ao vivo
  mostra o swap real.
- **Dados de terceiros.** Cotações indicativas, não o feed da corretora do usuário. Rode
  `backtest` na máquina dele para testar com o histórico real.
- **Spread fixo.** Sem alargamento em notícia ou na virada do dia.
- **Sem filtro de notícias** no histórico (ao vivo existe).
- **Fuso do servidor:** o backtest por MT5 estima o deslocamento atual e o aplica ao passado,
  errando em 1h nas mudanças de horário de verão.
- **Um único período**, de menos de 3 anos, com um regime específico de juros e de dólar.

## 8. Como pesquisar mudanças sem se enganar

1. Escreva a hipótese e o critério de sucesso **antes** de rodar.
2. Mude um parâmetro por vez com `set`, rode `backtest`.
3. Exija melhora nas duas metades (`consistency.first_60pct` e `last_40pct`), não só no total.
4. Repita com `--cost-mult 2`. Se a vantagem some, ela era custo otimista.
5. Desconfie de poucas operações: abaixo de ~200 quase tudo é ruído.
6. Conte quantas variações você tentou. A décima tentativa "boa" provavelmente é acaso.
7. Valide em demo antes de qualquer conversa sobre conta real.

`backtest --ignore-halt` continua a simulação depois do halt de drawdown — útil para estudar a
estratégia; para estimar o que a conta viveria, use sem a opção.

Motor ao vivo e backtester compartilham as mesmas funções de sinal, risco e gestão, e um teste
automático confere que os dois tomam as mesmas operações com o mesmo resultado
(`scripts/tests/test_fxbot.py`, `test_engine_and_backtest_agree`). Se mexer no código, rode
`python -m unittest discover -s tests` dentro de `scripts/`.

## 9. Parâmetros

Tudo em `config.json` (só as diferenças em relação ao padrão), alterado com `set`.

| Chave | Padrão | Significado |
|---|---|---|
| `strategy.enable_reversion` | true | Liga o setup MR |
| `strategy.reversion_classes` | ["cross"] | Classes onde MR opera (`major`, `cross`, `metal`) |
| `strategy.mr_lookback` | 20 | Dias do movimento medido |
| `strategy.mr_z` | 1.0 | Esticão mínimo (z-score) |
| `strategy.mr_sl_atr` | 3.0 | Stop em ATRs diários |
| `strategy.mr_tp_r` | 0.0 | Alvo em R (0 = sem alvo) |
| `management.reversion.max_hold_bars` | 240 | Saída por tempo (barras H1) |
| `strategy.enable_pullback` / `enable_breakout` | false | Setups de tendência |
| `strategy.min_score` | 70 | Nota mínima para operar |
| `risk.risk_per_trade_pct` | 0.5 | Risco por operação |
| `risk.max_open_positions` | 4 | Posições simultâneas |
| `risk.daily_loss_limit_pct` | 2.0 | Trava diária |
| `risk.max_drawdown_pct` | 8.0 | Halt de drawdown |
| `news.enabled` / `news.fail_mode` | true / "allow" | Filtro de notícias; `block` para não operar sem calendário |
| `symbols` | 32 instrumentos | Universo analisado |
| `timeframe` | "H1" | Gráfico de entrada |

`python scripts/fxbot.py config` mostra a configuração efetiva completa e os tetos.

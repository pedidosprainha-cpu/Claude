# fxengine — motor de análise de Forex e metais para entrada a mercado

Sempre que você der o comando, o motor busca **preço spot ao vivo (bid/ask)** e candles
de 5 timeframes para **28 pares de Forex + ouro, prata, platina e paládio**, roda quatro
camadas de análise (gráfica, quantitativa, força relativa e fundamental), aplica filtros
de execução e aponta **a melhor oportunidade para execução imediata a mercado**, com
entrada, stop, alvos, tamanho de lote e a probabilidade histórica do setup.

Se nenhuma oportunidade passar nos filtros, o motor diz **"nenhuma entrada recomendada"**
e mostra o melhor candidato com o motivo do bloqueio.

## Como usar

```bash
pip install -r requirements.txt

./analisar                                  # varre os 32 ativos (≈10 s)
./analisar -a metais                        # só metais
./analisar -a EURUSD,XAUUSD --detalhe       # ativos escolhidos + tabela por timeframe
./analisar --saldo 25000 --risco 0.5        # dimensiona o lote para a sua conta
./analisar --salvar                         # grava reports/AAAA-MM-DD_HHMM.md e .json
./analisar --json -                         # saída JSON (integração com outros sistemas)
python3 -m fxengine --offline               # demonstração com dados sintéticos (sem rede)
```

Análise completa de um único ativo (qualquer um dos 28 pares ou 4 metais):

```bash
python3 -m fxengine ativo -a EURUSD         # decisão, timeframes, níveis, dia, quant, fundamentos
python3 -m fxengine ativo -a XAUUSD --json - # mesma análise em JSON
```

Carrega o histórico completo só do ativo escolhido; os outros pares entram em versão leve
(5 dias de M15 + 1 mês de H1), apenas para a força relativa das moedas — a análise de um
ativo leva ≈5 s.

Rompimentos (breakouts) em tempo real:

```bash
python3 -m fxengine rompimentos                     # varredura única (nota ≥ B)
python3 -m fxengine rompimentos --monitorar 120     # repete a cada 2 min e avisa os novos/confirmados
python3 -m fxengine rompimentos --plano limite      # plano com ordem limite no reteste
python3 -m fxengine rompimentos -a metais --min-nota A
```

No **Claude Code**, digite `/analisar` (ou "analise agora"): a skill roda o motor, revisa
manchetes e agenda e devolve a decisão final em português.

### App Android

O mesmo motor roda dentro de um app Android (Python embutido no APK, sem servidor):
um botão **ANALISAR** (todos os ativos ou um ativo escolhido, com gráfico de candles e
o plano desenhado), a decisão em destaque, rompimentos em tempo real, ranking, painel de
mercado e ajustes de saldo e risco. Instalação, uso e build em
[`android/README.md`](android/README.md).

## O que sai

- **Melhor oportunidade**: lado, entrada (ask para compra, bid para venda), stop, TP1
  (realizar 50% e mover stop para a entrada), TP2, R:R, lote, invalidação.
- **Edge histórico**: em quantos sinais parecidos no último ano (H1) o TP1 veio antes do
  stop, com a mesma geometria do trade proposto e spread incluso.
- **Por que / Riscos**: a lista de fatores a favor e contra, por camada.
- **Ranking** dos 10 melhores, **força relativa** das 8 moedas, **macro** (VIX, Treasuries,
  DXY, petróleo, cobre), **juros** dos bancos centrais, **COT**, **agenda** de alto impacto
  e **manchetes**.

## Arquitetura

```
fxengine/
  data/          yahoo.py (candles) · swissquote.py (bid/ask ao vivo) · fundamentals.py
                 (agenda, juros BIS, COT CFTC, manchetes) · provider.py · synthetic.py
  analysis/      indicators · structure · patterns · technical · quant · strength ·
                 fundamental · edge
  sessions.py    relógio de sessões, mercado aberto/fechado, rollover, liquidez
  risk.py        plano do trade e tamanho de posição
  engine.py      orquestração, multiplicadores, filtros e ranking
  report.py      relatório no terminal / Markdown / JSON
  breakouts.py   detector de rompimentos em tempo real + rastreador de eventos novos
  app_api.py     interface JSON usada pelo app Android
```

### Camadas

| Camada | Peso | O que mede |
|---|---|---|
| **Técnica (MTF)** | 40% | M5/M15/H1/H4/D1 (pesos 10/25/30/20/15): EMAs 8/21/50/200, inclinação, SuperTrend, Ichimoku, estrutura HH/HL, RSI, MACD, ROC, ADX como fator de convicção. Setups: pullback ao valor na tendência, rompimento de squeeze (Bollinger dentro de Keltner), quebra de estrutura (BOS/CHoCH) e fade de reversão à média. Candles (engolfo, pin bar, marubozu), divergências RSI. |
| **Quantitativa** | 20% | Regime por votação (Hurst, razão de variância de Lo-MacKinlay, efficiency ratio, ADX); momentum de série temporal ajustado à volatilidade (1/5/20/60 dias); z-score de reversão à média; percentil de volatilidade realizada. |
| **Força relativa** | 20% | Medidor cross-sectional nos 28 cruzamentos: retornos normalizados pela volatilidade em 4h/24h/5d; forte contra fraco. Metais: momentum normalizado contra o USD. |
| **Fundamental** | 20% | Carry (juros BIS), trajetória de política em 6 meses, apetite a risco (VIX, S&P futuro) × beta de risco da moeda, juros dos EUA (5a/10a; inverso para metais, como proxy de juro real), DXY (metais), commodities (petróleo→CAD, cobre→AUD/NZD/metais industriais, ouro→AUD), COT CFTC (tendência do posicionamento e contrarian nos extremos), sentimento de manchetes. |

### Do score à decisão

`composto = Σ peso × camada` (−100 a +100; o sinal dá a direção). O score final
(0–100) é `|composto| ×` multiplicadores:

- **timing** da entrada (distância da EMA21-M15 em ATR, RSI extremo, candle de gatilho,
  divergência contra, M5 contra);
- **regime** (tendência persistente a favor ×1.05, contra ×0.82);
- **confluência** (quantas das 4 camadas concordam);
- **espaço** até a próxima zona de S/R oposta, em R;
- **histórico**: expectativa calibrada do modelo histórico para este sinal (sem o modelo:
  edge do setup no último ano);
- **spread** relativo ao stop, **liquidez** da sessão, **agenda**, **volatilidade** extrema;
- **dia**: quanto da amplitude diária média (ADR, 20 dias) já foi usada. Se o preço já andou
  mais de 1 ADR a favor hoje (×0.85, risco de exaustão) ou o dia já usou mais de 130% da
  ADR (×0.92), o score cai;
- **rompimento**: confluência com o detector de rompimentos no mesmo ativo — só alertas
  acionáveis do perfil validado contam (×1.06 a favor, ×0.90 contra). As features são
  calculadas na mesma janela curta usada no treino do modelo.

Os multiplicadores **dia** e **rompimento** são regras de bom senso, não parâmetros
otimizados no histórico; o filtro de edge histórico continua sendo a trava principal.

Notas: A+ ≥ 65 · A ≥ 55 · B ≥ 45 · C ≥ 35 · D < 35. Só é recomendado o que tem nota ≥ B
**e** passa nos filtros obrigatórios:

- mercado aberto e cotação ao vivo (< 10 min);
- nenhum evento de alto impacto da moeda entre 45 min antes e 20 min depois;
- spread ≤ 25% do stop;
- o gráfico (técnico MTF) não pode estar contra a direção;
- o sinal precisa estar entre os **2% melhores do histórico** pelo modelo calibrado (sem o
  modelo: edge histórico não pode ser < −0.15R com amostra ≥ 25).

### Validação histórica da análise principal

A análise principal foi reconstituída sem olhar o futuro em todas as horas de 32 ativos
(abr/2024 → nov/2026, ~500 mil barras H1), com entrada a mercado e spread típico, nas duas
direções (`research/signal_replay.py`). Medido fora da amostra:

| bloco de teste (jul → nov/2026, nunca visto) | trades | no lucro | R por trade |
|---|---|---|---|
| lógica e plano antigos (tendência + stop curto + 50% em 1,5R) | 7.774 | 33% | **−0,17R** |
| tendência com o plano novo | 4.505 | 46% | −0,07R |
| **modelo novo (2% melhores sinais, plano novo)** | 261 | 48% | **−0,02R** |

- Entrar em qualquer hora perde de −0,07R a −0,19R por trade (o spread), e **seguir a
  tendência de H1/H4/D1 foi pior que entrar ao acaso** no horizonte de horas.
- No walk-forward (6 períodos de ~4 meses), os 2% melhores sinais do modelo ficaram em média
  em **+0,004R** por trade (pior período −0,04R, 2 de 6 positivos). **Não passa** na regra de
  vantagem comprovada (≥ 75% dos períodos positivos): para entradas a mercado, a expectativa
  dos melhores sinais fica perto de zero depois do spread.
- Probabilidade prevista × real nos trades do teste: 51% × 48% (levemente otimista).

Por isso o motor agora usa um **modelo histórico calibrado** (`fxengine/analysis/signal_model.py`,
GBM treinado em `research/train_signal_model.py`) em toda análise:

- **probabilidade de lucro e expectativa em R** dos sinais parecidos, recalibradas fora da
  amostra (substituem o antigo estudo de edge de 1 ano por ativo);
- **filtro**: só recomenda executar se o sinal estiver entre os melhores do histórico
  (o mesmo corte usado na validação); fora dele, "histórico desfavorável";
- **plano validado**: stop 2× ATR H1 e, a partir de +1R, stop móvel 1 ATR H1 atrás do melhor
  preço; encerrar a mercado em 48 h se nada acontecer. Stops estruturais curtos com alvos
  fixos foram a geometria que mais perdeu no histórico, porque o spread pesa mais;
- aviso quando o histórico favorece o lado oposto ao da análise.

O ajuste "Modelo histórico" (app) / `--sem-edge` (CLI) desliga o modelo e volta ao plano
estrutural antigo.

### Plano do trade

- **Stop**: além do swing M15/H1 mais próximo que fique entre 0.6×ATR H1 (e 1.2×ATR M15)
  e 2.2×ATR H1, com buffer de 0.25×ATR M15 + spread; sem swing válido, usa 1.3×ATR H1.
- **TP1**: logo antes da primeira zona de S/R entre 1R e 2R; senão 1.5R.
- **TP2**: próxima zona até 4R, limitada a ~1.3×ATR diário (horizonte intraday).
- **Zonas de S/R**: swings H1/H4/D1, máxima/mínima do dia e da semana anteriores,
  aberturas, pivôs clássicos e números redondos, agrupados por proximidade e pesados
  por confluência e recência.
- **Lote**: `saldo × risco% ÷ (pips de stop × valor do pip por lote)`, com conversão
  para USD pelos preços ao vivo. Contratos: FX 100.000, XAU 100 oz, XAG 5.000 oz,
  XPT/XPD 100 oz (ajuste em `instruments.py` se sua corretora usar outro tamanho).

### Rompimentos em tempo real

Para cada ativo, em M15 e H1, o detector monta os níveis relevantes: máxima/mínima de
12h (M15), 24h e 5 dias (H1), caixas de consolidação apertada (altura pequena em ATR),
range asiático e as zonas de S/R do motor (dia/semana anteriores, swings, pivôs, números
redondos). Em cada nível, classifica o que o preço está fazendo agora:

- **rompendo**: preço ao vivo além do nível, candle ainda aberto;
- **confirmado**: um candle fechou além do nível;
- **reteste**: depois de romper, voltou ao nível e segurou;
- **falso**: rompeu e fechou de volta para dentro, uma armadilha operada na direção contrária.

A nota (0–100) soma vários fatores:

- importância do nível e confluência de referências;
- compressão de volatilidade antes do rompimento;
- força do candle de rompimento;
- tendência do timeframe acima e força relativa das moedas;
- distância já percorrida (rompimentos esticados são penalizados);
- eventos de alto impacto, liquidez da sessão e spread em relação ao stop;
- taxa histórica de continuação de rompimentos naquele ativo e timeframe.

**Precisão validada e planos de entrada.** O detector foi reconstituído no histórico, sem olhar
o futuro e com spread: cerca de **100 mil rompimentos H1 em ~3 anos** e 26 mil M15 em ~2 meses.
Foram testadas 112 combinações de entrada, stop e saída e modelos linear e não linear (GBM).
O app oferece dois planos para os 10% melhores alertas H1 (nota A/A+):

| plano | como entra | trades no lucro (teste) | R médio no teste | R médio walk-forward |
|---|---|---|---|---|
| **A mercado (tempo real)** — padrão | alerta quando o candle seguinte fecha a favor; entrada a mercado na hora; stop 0,5 ATR H1 além do nível | **49,5%** | +0,037 | −0,005 |
| **Limite no reteste** | ordem limite no nível rompido; stop 1 ATR H1 além do nível | 57,6% | **+0,102** | **+0,080** (5/5 blocos +) |
| referência: app 1.2 (a mercado, sem filtro) | — | 29,5% | −0,151 | — |

Nos dois planos, a partir de +1R o stop vira móvel (1 ATR H1 atrás do melhor preço).

- O plano **a mercado** quase dobra a assertividade do app 1.2 e elimina a perda média. Mesmo
  assim, a expectativa histórica é ≈ zero: rompimento comprado a mercado não teve vantagem
  robusta depois do spread, mesmo com contexto e modelo não linear.
- O único plano com resultado positivo validado é o **limite no reteste**, porque entra a um
  preço melhor.
- Rompimentos M15 não passaram na validação em nenhum plano e aparecem só como informação.

Detalhes em `research/RESULTADOS_ENTRADAS*.json`; como refazer em
[`research/README.md`](research/README.md).

O plano tem stop do outro lado do nível, alvos na próxima zona e na projeção da altura do
range, e lote pelo risco escolhido. Um rastreador em disco lembra os eventos já vistos, para
que o monitor só avise o que é novo.

### Edge histórico (anti-overfitting)

Reexecuta uma versão vetorizada do sinal técnico em ~1 ano de H1, seleciona os momentos
parecidos com o atual (mesma direção, força de sinal e extensão semelhantes) e simula o
trade exato proposto agora: entrada na abertura da barra seguinte, stop testado primeiro
quando os dois são tocados na mesma barra, trades sem sobreposição, saída por tempo após
48 h e spread descontado. Uma priori Beta centrada no acerto de empate encolhe amostras
pequenas para não superestimar a probabilidade. Validação: com entradas aleatórias o
acerto simulado bate com a teoria do passeio aleatório (testes em `tests/`).

## Fontes de dados

| Dado | Fonte |
|---|---|
| Bid/ask spot ao vivo (FX e metais) | Swissquote (feed público) |
| Candles M5/M15/H1 | Yahoo Finance (FX spot; metais via futuros GC/SI/PL/PA ajustados ao spot pela razão spot/futuro) |
| Macro (VIX, Treasuries, DXY, S&P, petróleo, cobre) | Yahoo Finance |
| Juros de política | BIS (WS_CBPOL), com tabela local de reserva |
| Posicionamento | CFTC Commitments of Traders (legacy, futures-only) |
| Agenda econômica | ForexFactory (semana corrente) |
| Manchetes | Investing.com (RSS forex, commodities, indicadores) |

Cada fonte é independente: se uma falhar, o motor continua e avisa em "Falhas de dados".
O cache local fica em `.cache/` (TTL curto para preços).

## Limitações

- Os candles dos metais vêm de futuros ajustados; viradas de contrato podem criar pequenos
  saltos no histórico.
- Volume real não existe em FX spot; o motor não usa volume.
- Spreads são os do feed público e podem diferir dos da sua corretora; confira antes de executar.
- O sentimento de manchetes é por palavras-chave, com peso baixo; a skill `/analisar`
  acrescenta uma leitura qualitativa das manchetes.

## Testes

```bash
pip install -r requirements-dev.txt
python3 -m pytest -q
```

---
**Aviso:** ferramenta de análise automatizada e probabilística. Não constitui recomendação
de investimento. Operar alavancado envolve risco de perdas superiores ao capital.

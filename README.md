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

Rompimentos (breakouts) em tempo real:

```bash
python3 -m fxengine rompimentos                     # varredura única (nota ≥ B)
python3 -m fxengine rompimentos --monitorar 120     # repete a cada 2 min e avisa os novos
python3 -m fxengine rompimentos -a metais --min-nota A
```

No **Claude Code**, digite `/analisar` (ou "analise agora"): a skill roda o motor, revisa
manchetes e agenda e devolve a decisão final em português.

### App Android

O mesmo motor roda dentro de um app Android (Python embutido no APK, sem servidor):
um botão **ANALISAR**, a decisão em destaque, ranking, painel de mercado e ajustes de
saldo e risco. Instalação, uso e build em [`android/README.md`](android/README.md).

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
- **edge** histórico (expectativa posterior do setup);
- **spread** relativo ao stop, **liquidez** da sessão, **agenda**, **volatilidade** extrema.

Notas: A+ ≥ 65 · A ≥ 55 · B ≥ 45 · C ≥ 35 · D < 35. Só é recomendado o que tem nota ≥ B
**e** passa nos filtros obrigatórios:

- mercado aberto e cotação ao vivo (< 10 min);
- nenhum evento de alto impacto da moeda entre 45 min antes e 20 min depois;
- spread ≤ 25% do stop;
- o gráfico (técnico MTF) não pode estar contra a direção;
- edge histórico não pode ser claramente negativo (< −0.15R com amostra ≥ 25).

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

**Precisão validada e plano de entrada.** O detector foi reconstituído no histórico, sem olhar
o futuro e com spread: cerca de **100 mil rompimentos H1 em ~3 anos** e 26 mil M15 em ~2
meses. Um laboratório testou 112 combinações de entrada, stop e saída. Um modelo calibrado por
timeframe ordena os alertas.

Plano escolhido por walk-forward:

- **Entrada:** ordem limite no reteste do nível rompido (válida por 6h no H1).
- **Stop:** 1 ATR do H1 além do nível.
- **Saída:** a partir de +1R, stop móvel 1 ATR atrás do melhor preço, sem alvo fixo.

Resultado dos 10% melhores alertas H1 (nota A/A+):

| | trades | no lucro | R médio por trade |
|---|---|---|---|
| walk-forward (5 blocos de ~3,6 meses) | 5.698 | – | **+0,080** (5 de 5 blocos positivos) |
| teste final (últimos ~3,6 meses, intocado) | 920 | **57,6%** | **+0,102** |
| plano anterior (app 1.2), mesmo período | 13.721 | 29,5% | −0,151 |

Os rompimentos M15 não passaram na validação: walk-forward negativo em todos os blocos. Eles
aparecem só como informação, sem nota A nem alerta. Detalhes em
`research/RESULTADOS_ENTRADAS.json`; como refazer em [`research/README.md`](research/README.md).
É desempenho histórico, simulado com spreads típicos: não garante resultado futuro.

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

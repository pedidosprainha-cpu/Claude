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

No **Claude Code**, digite `/analisar` (ou "analise agora"): a skill roda o motor, revisa
manchetes e agenda e devolve a decisão final em português.

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

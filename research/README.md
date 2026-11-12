# Pesquisa — validação da análise principal e dos rompimentos

Scripts que medem e calibram o sinal principal do motor (`fxengine/analysis/signal_model.py`)
e o detector de rompimentos (`fxengine/breakouts.py`), e escolhem os planos de entrada e
saída que o app recomenda.

## Análise principal (aba Analisar)

```bash
# 1) reconstituição: todas as barras H1 fechadas de 32 ativos (~2,6 anos), features da mesma
#    função usada ao vivo e resultado de uma entrada a mercado nas duas direções, com spread,
#    para 15 geometrias (stop 1/1,5/2 ATR H1 × saídas alvo fixo, break-even, stop móvel, parcial)
python3 research/signal_replay.py                    # ~1 min → research/data/signal_events.pkl
python3 research/signal_replay.py --grid swing --out research/data/signal_events_swing.pkl

# 2) walk-forward (8 blocos de ~4 meses; o último é o teste, intocado) e modelo final
python3 research/train_signal_model.py                         # ridge, 15 geometrias (rápido)
python3 research/train_signal_model.py --model gbm --geoms "s20|tr10"   # modelo do app (~25 min)
```

- A geometria e o filtro (top q% dos sinais) são escolhidos pelo **pior bloco** do walk-forward;
  a recalibração da probabilidade e da expectativa usa só previsões fora da amostra do
  walk-forward; o bloco de teste é avaliado uma vez, no fim.
- Grava `fxengine/data/signal_model.json` (usado pelo app e pelo CLI) e
  `research/RESULTADOS_SINAL.json`.
- Regra para `validated: true`: média > 0, ≥ 75% dos blocos positivos, pior bloco > −0,05R.

Resultado atual (`research/RESULTADOS_SINAL.json`, modelo GBM, stop 2× ATR H1 + stop móvel 1 ATR
após +1R, horizonte 48 h, filtro top 2%):

| | trades | no lucro | R por trade |
|---|---|---|---|
| walk-forward, 6 blocos (média / pior bloco) | 165+ por bloco | — | +0,004R / −0,037R (2 de 6 positivos) |
| teste final (10/07 → 06/11/2026) | 261 | 48,3% | −0,016R |
| teste: tendência ingênua com o mesmo plano | 4.505 | 45,6% | −0,066R |
| teste: lógica e plano antigos (stop 1 ATR, 50% em 1,5R) | 7.774 | 33,4% | −0,175R |

Não validado pela regra (`validated: false`): o app usa o modelo para filtrar e calibrar e
mostra esses números no cartão "Validação histórica da análise". O modelo linear (ridge) e o
horizonte swing (até 5 dias) foram piores no walk-forward.

## Explosões de preço (aba Explosões)

```bash
python3 research/explosion_replay.py          # ~1 min → research/data/explosion_events.pkl
python3 research/train_explosion_model.py     # ~25 min → fxengine/data/explosion_model.json
```

Explosão = movimento ≥ 0,5× ADR a partir do fechamento, para qualquer lado, em até 4 barras H1
(13% das horas). Regras fixadas antes do teste: alerta = top 5% das previsões de treino;
detecção validada se em todos os blocos do walk-forward o acerto dos alertas for ≥ 2× a taxa
base e o modelo superar um GBM só com a hora da semana (AUC) em ≥ 5 de 6 blocos.

| | walk-forward (6 blocos) | teste (13/07 → 09/11/2026) |
|---|---|---|
| acerto dos alertas / taxa base | 2,7× a 4,5× (média 3,3×) | 42,7% / 13,1% (3,3×) |
| AUC modelo / só horário | 6/6 blocos acima | 0,727 / 0,681 |
| nível extremo (top 1%) | — | 59,2% |
| direção (AUC) | 0,47–0,56 (sem poder) | 0,555 |
| OCO, melhor variante | −0,23R (0/6 blocos positivos) | −0,36R |

Resultados completos em `research/RESULTADOS_EXPLOSAO.json`.

Direção (`python3 research/train_explosion_direction.py`, ~20 min; atualiza o bloco
`direction` de `explosion_model.json`): GBM espelhado nas explosões, alertas refeitos fora da
amostra em cada bloco, trades a mercado no lado previsto avaliados com `signal_events.pkl`.

| | walk-forward (6 blocos) | teste |
|---|---|---|
| lado previsto saiu primeiro (explosões em alerta) | 53%–61% (média 56%) | 60,4% |
| leituras de alta confiança (30% mais confiantes) | 55%–71% (ponderado 58%) | 69,6% (358) |
| AUC | 0,51–0,64 (média 0,544 < 0,55: **não útil pela regra**) | 0,563 |
| trade a mercado no lado previsto (melhor geometria) | −0,07R (0/6 blocos positivos) | +0,10R (791) |

Resultados em `research/RESULTADOS_EXPLOSAO_DIRECAO.json`.

## Combinação dos modelos

```bash
python3 research/ensemble_oos.py       # ~20 min → research/data/ensemble_oos.pkl (previsões fora da amostra)
python3 research/train_ensemble.py     # políticas pré-registradas → research/RESULTADOS_COMBINACAO.json
python3 research/feature_ranges.py     # faixas das entradas vistas no treino (alerta "fora do histórico")
```

| política (melhor geometria) | walk-forward média / pior bloco | blocos positivos | teste (jul–nov/2026) |
|---|---|---|---|
| explosão + direção + sinal concordam (s20\|tr10) | −0,072R / −0,101R | 0/6 | +0,126R (542) |
| sinal principal top 2% (modelo atual) | −0,025R / −0,208R | 2/6 | +0,035R (205) |

Nenhuma das 30 combinações passou na regra (média > 0, ≥ 75% dos blocos positivos, pior bloco
> −0,05R).

## Rompimentos (aba Rompimentos)

```bash
# 1) reconstituições walk-forward do monitor (sem olhar o futuro, com spread)
python3 research/breakout_replay_h1.py     # H1, ~3 anos, 32 ativos (~40 min)
python3 research/breakout_replay.py        # M15, ~60 dias (limite do Yahoo) (~20 min)

# 2) laboratório de entradas/saídas: 112 combinações por alerta
python3 research/entry_exit_lab.py --events research/data/breakout_events_h1.csv --bars h1 --blocks 7 \
        --out research/data/lab_h1.csv
python3 research/entry_exit_lab.py --events research/data/breakout_events.csv --bars m15 --blocks 5 \
        --out research/data/lab_m15.csv

# 2b) features de contexto (hora, amplitude do dia, diário/semanal), mesma função do app
python3 research/augment_features.py --events research/data/breakout_events_h1.csv --bars h1
python3 research/augment_features.py --events research/data/breakout_events.csv --bars m15

# 3) modelo por timeframe sobre o melhor plano (walk-forward + teste final intocado)
#    perfil "mercado" (padrão do app): --entries mercado,confirmacao --profile mercado \
#        --force-enable H1 --model-out fxengine/data/breakout_model_mercado.json
#    perfil "limite": sem --entries, --profile limite --model-out fxengine/data/breakout_model_limite.json
#    --model gbm testa o modelo não linear (não melhorou nos dados atuais)
python3 research/train_entry_model.py \
        --tf H1  --events research/data/breakout_events_h1_ctx.csv --sim research/data/lab_h1.csv --blocks 7 \
        --tf M15 --events research/data/breakout_events_ctx.csv   --sim research/data/lab_m15.csv --blocks 5
```

- Os dados ficam em `research/data/` (não versionado).
- O passo 3 grava:
  - `fxengine/data/breakout_model_mercado.json` e `breakout_model_limite.json` (um por perfil),
    usados pelo app e pelo CLI;
  - `research/RESULTADOS_ENTRADAS*.json`, com os números de walk-forward e de teste.
- Um timeframe só fica ativo (nota A/A+, alertas) se no walk-forward tiver média positiva,
  pelo menos 75% dos blocos positivos e nenhum bloco abaixo de −0,05R.
- `--force-enable` liga um timeframe por escolha do usuário mesmo sem passar na regra, gravando
  `validated: false`; o app mostra isso no cartão de validação. É o caso do H1 no perfil "mercado".
- `train_breakout_model.py` é a versão 1 (um modelo só, plano a mercado), mantida para
  comparação.

Retreine periodicamente, por exemplo todo mês: o mercado muda de regime.

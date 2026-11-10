# Pesquisa — validação dos rompimentos

Scripts que medem e calibram o detector de rompimentos (`fxengine/breakouts.py`) e escolhem
o plano de entrada e saída que o app recomenda.

```bash
# 1) reconstituições walk-forward do monitor (sem olhar o futuro, com spread)
python3 research/breakout_replay_h1.py     # H1, ~3 anos, 32 ativos (~40 min)
python3 research/breakout_replay.py        # M15, ~60 dias (limite do Yahoo) (~20 min)

# 2) laboratório de entradas/saídas: 112 combinações por alerta
python3 research/entry_exit_lab.py --events research/data/breakout_events_h1.csv --bars h1 --blocks 7 \
        --out research/data/lab_h1.csv
python3 research/entry_exit_lab.py --events research/data/breakout_events.csv --bars m15 --blocks 5 \
        --out research/data/lab_m15.csv

# 3) modelo por timeframe sobre o melhor plano (walk-forward + teste final intocado)
python3 research/train_entry_model.py \
        --tf H1  --events research/data/breakout_events_h1.csv --sim research/data/lab_h1.csv --blocks 7 \
        --tf M15 --events research/data/breakout_events.csv   --sim research/data/lab_m15.csv --blocks 5
```

- Os dados ficam em `research/data/` (não versionado).
- O passo 3 grava:
  - `fxengine/data/breakout_model.json`, usado pelo app e pelo CLI;
  - `research/RESULTADOS_ENTRADAS.json`, com os números de walk-forward e de teste.
- Um timeframe só fica ativo (nota A/A+, alertas) se no walk-forward tiver média positiva,
  pelo menos 75% dos blocos positivos e nenhum bloco abaixo de −0,05R.
- `train_breakout_model.py` é a versão 1 (um modelo só, plano a mercado), mantida para
  comparação.

Retreine periodicamente, por exemplo todo mês: o mercado muda de regime.

# Pesquisa — validação dos rompimentos

Scripts que medem e calibram o detector de rompimentos (`fxengine/breakouts.py`).

```bash
# 1) reconstitui o monitor em cada fechamento de M15 dos últimos ~60 dias (32 ativos, ~20 min)
python3 research/breakout_replay.py
# 2) escolhe geometria/cortes por walk-forward, testa no último bloco e grava o modelo
python3 research/train_breakout_model.py
```

- Saída do passo 1: `research/data/breakout_events.csv` (não versionado).
- Saída do passo 2:
  - `fxengine/data/breakout_model.json` (usado pelo app e pelo CLI);
  - `research/RESULTADOS_ROMPIMENTOS.md` (relatório com os números do período de teste).

Retreine periodicamente (por exemplo, todo mês): o mercado muda de regime.

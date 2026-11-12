"""Validação walk-forward com purging/embargo, calibração fora da amostra e baselines.

Protocolo
1. Janelas de teste mensais. Para cada mês M, o modelo é treinado apenas com candidatos cujo
   rótulo foi *resolvido* (saída do trade) antes de início(M) − embargo. Isso remove o
   vazamento por sobreposição de rótulos (purging, López de Prado 2018).
2. Previsões do mês M são estritamente fora da amostra. Concatenadas, formam o conjunto OOS.
3. Seleção: mesmos portões da operação ao vivo (EV mínimo em R, custo máximo em R, R:R).
4. Simulação de portfólio com as mesmas regras de risco do motor ao vivo.
5. Baselines: (a) todos os candidatos sem filtro; (b) seleção aleatória com o mesmo número de
   trades por mês (Monte Carlo) para medir se o filtro do modelo agrega valor.
6. O período a partir de HOLDOUT_START foi reservado: nenhuma decisão de desenho do sistema
   foi tomada olhando seus resultados.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..quant.dataset import feature_cols
from ..quant.model import ProbabilityModel, calibration_table, evaluate
from .engine import simulate_portfolio
from .metrics import trade_metrics

log = logging.getLogger("fxintel.backtest.wf")

HOLDOUT_START = pd.Timestamp("2026-01-01", tz="UTC")


def walk_forward(df: pd.DataFrame, settings: dict, kind: str = "logistic", min_train: int | None = None,
                 embargo_h: int = 24, first_test: str | None = None) -> pd.DataFrame:
    """Retorna o conjunto OOS com colunas p (probabilidade), ev (R esperado) e fold."""
    min_train = min_train or settings["model"]["min_train_samples"]
    xc = feature_cols(df)
    df = df.sort_values("decision_time")
    start = pd.Timestamp(first_test, tz="UTC") if first_test else (
        df["decision_time"].min() + pd.Timedelta(days=150)).normalize().replace(day=1)
    months = pd.date_range(start, df["decision_time"].max(), freq="MS")
    out = []
    for m in months:
        m_end = m + pd.offsets.MonthBegin(1)
        cutoff = m - pd.Timedelta(hours=embargo_h)
        train = df[(df["exit_time"] < cutoff) & df["resolved"]]
        test = df[(df["decision_time"] >= m) & (df["decision_time"] < m_end)]
        if len(train) < min_train or test.empty:
            continue
        model = ProbabilityModel(kind=kind, calibration=settings["model"].get("calibration", "sigmoid"))
        model.fit(train[xc], train["y"].to_numpy(), train["r"].to_numpy(), train["rr1"].to_numpy())
        p = model.predict(test[xc])
        t = test.copy()
        t["p"] = p
        t["ev"] = model.expected_r(p, t["rr1"].to_numpy())
        t["base_rate_train"] = model.meta["base_rate"]
        t["n_train"] = len(train)
        t["fold"] = m.strftime("%Y-%m")
        out.append(t)
        log.info("fold %s: treino=%d teste=%d base=%.3f", m.strftime("%Y-%m"), len(train), len(test),
                 model.meta["base_rate"])
    return pd.concat(out) if out else pd.DataFrame()


def select(oos: pd.DataFrame, settings: dict) -> pd.DataFrame:
    g = settings["gates"]
    m = (oos["ev"] >= g["min_ev_r"]) & (oos["cost_r"] <= g["max_cost_r"])
    rr_net = oos["rr1"] * (1 - oos["cost_r"]) - oos["cost_r"]
    m &= rr_net >= g["min_rr_net"]
    return oos[m]


def random_baseline(oos: pd.DataFrame, selected: pd.DataFrame, n_iter: int = 500, seed: int = 5) -> dict:
    """Distribuição do R médio de seleções aleatórias com o mesmo nº de trades por mês."""
    rng = np.random.default_rng(seed)
    counts = selected.groupby("fold").size()
    pools = {f: oos.loc[oos["fold"] == f, "r"].to_numpy() for f in counts.index}
    means = []
    for _ in range(n_iter):
        pick = [rng.choice(pools[f], size=min(int(k), len(pools[f])), replace=False) for f, k in counts.items()]
        if pick:
            means.append(np.concatenate(pick).mean())
    means = np.array(means)
    obs = float(selected["r"].mean()) if len(selected) else float("nan")
    return {"observed_avg_r": obs, "random_mean_avg_r": float(means.mean()) if len(means) else None,
            "random_p95_avg_r": float(np.quantile(means, 0.95)) if len(means) else None,
            "p_value": float((means >= obs).mean()) if len(means) else None, "iterations": int(n_iter)}


def oos_calibration(oos: pd.DataFrame) -> dict:
    y = oos["y"].to_numpy()
    p = oos["p"].to_numpy()
    base = oos["base_rate_train"].to_numpy()
    ev = evaluate(y, p, float(np.mean(base)))
    # Brier da climatologia usando a taxa-base de *cada* fold de treino (honesto)
    ref = float(np.mean((base - y) ** 2))
    ev["brier_climatology"] = ref
    ev["bss"] = 1 - ev["brier"] / ref if ref > 0 else float("nan")
    return {"metrics": ev, "table": calibration_table(y, p)}


def run(df: pd.DataFrame, settings: dict, kind: str = "logistic") -> dict:
    oos = walk_forward(df, settings, kind=kind)
    if oos.empty:
        return {"error": "amostra insuficiente para walk-forward"}
    sel = select(oos, settings)
    res = {"kind": kind, "oos": oos, "selected": sel}
    periods = {"completo": (None, None), "desenvolvimento": (None, HOLDOUT_START),
               "holdout_2026": (HOLDOUT_START, None)}
    for name, (a, b) in periods.items():
        mo = oos
        ms = sel
        if a is not None:
            mo, ms = mo[mo["decision_time"] >= a], ms[ms["decision_time"] >= a]
        if b is not None:
            mo, ms = mo[mo["decision_time"] < b], ms[ms["decision_time"] < b]
        if mo.empty:
            continue
        port = simulate_portfolio(ms, settings) if len(ms) else None
        allp = simulate_portfolio(mo, settings)
        res[name] = {
            "period": [mo["decision_time"].min().isoformat(), mo["decision_time"].max().isoformat()],
            "calibration": oos_calibration(mo),
            "candidates_all": trade_metrics(mo["r"].to_numpy()),
            "selected_trades": trade_metrics(ms["r"].to_numpy()) if len(ms) else {"n": 0},
            "portfolio_selected": None if port is None else {
                "trade_metrics": port["trade_metrics"], "equity_metrics": port["equity_metrics"],
                "rejected": port["rejected"], "final_equity": port["final_equity"]},
            "portfolio_all_candidates": {
                "trade_metrics": allp["trade_metrics"], "equity_metrics": allp["equity_metrics"],
                "rejected": allp["rejected"], "final_equity": allp["final_equity"]},
            "random_selection_baseline": random_baseline(mo, ms) if len(ms) else None,
            "_port": port,
        }
    return res

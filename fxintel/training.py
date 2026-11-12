"""Pipeline de treino, validação walk-forward e publicação do modelo de produção."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import walkforward as WF
from .backtest.metrics import clean, trade_metrics
from .config import MODEL_DIR, load_settings
from .data.hub import DataHub
from .quant import stats as S
from .quant.dataset import build_dataset, feature_cols
from .quant.model import ProbabilityModel

log = logging.getLogger("fxintel.training")

MODEL_PATH = MODEL_DIR / "probability_model.pkl"
REPORT_JSON = MODEL_DIR / "report_latest.json"

# Registro honesto do processo de pesquisa (entra no Deflated Sharpe Ratio)
RESEARCH_LOG = [
    {"iteration": 1, "change": "Desenho inicial (PULLBACK, BREAKOUT, SWEEP; stop mínimo 0,6 ATR)",
     "note": "Agregados de amostra completa (frequência e R médio por setup) foram observados uma vez "
             "antes da definição do holdout."},
    {"iteration": 2, "change": "SWEEP restrito a pools relevantes (PDH/PDL, topos/fundos iguais, swing H4); "
                               "stop mínimo 1,0 ATR (custo/R)", "note": "Avaliado apenas no período de desenvolvimento."},
    {"iteration": 3, "change": "Inclusão do setup TREND (momentum de série temporal)",
     "note": "Avaliado apenas no período de desenvolvimento. Nenhuma iteração adicional."},
]
N_TRIALS = len(RESEARCH_LOG) * 2  # x2 famílias de modelo (logística, gradient boosting)


def _summ(res: dict) -> dict:
    out = {k: v for k, v in res.items() if k not in ("oos", "selected")}
    for per in ("completo", "desenvolvimento", "holdout_2026"):
        if per in out:
            out[per] = {k: v for k, v in out[per].items() if k != "_port"}
    return out


EXPORT_PATH = MODEL_DIR / "model_export.json"


def export_model(model: ProbabilityModel) -> dict | None:
    """Exporta o modelo logístico em JSON (avaliação no aplicativo Android, sem servidor)."""
    if model.kind != "logistic":
        return None
    imp, sc, lr = (model.est.named_steps[k] for k in ("imp", "sc", "lr"))
    keep = ("trained_at", "data_start", "data_end", "n_train", "base_rate", "k_win", "r_loss", "validated",
            "validation_rule", "oos_metrics", "oos_holdout_metrics", "oos_calibration_table", "horizon_bars")
    d = {"kind": "logistic", "features": model.features,
         "impute_median": [float(x) for x in imp.statistics_], "scaler_mean": [float(x) for x in sc.mean_],
         "scaler_scale": [float(x) for x in sc.scale_], "coef": [float(x) for x in lr.coef_[0]],
         "intercept": float(lr.intercept_[0]), "meta": clean({k: model.meta.get(k) for k in keep})}
    txt = json.dumps(d, ensure_ascii=False, indent=1)
    EXPORT_PATH.write_text(txt, encoding="utf-8")
    assets = Path(__file__).resolve().parent.parent / "android" / "app" / "src" / "main" / "assets"
    if assets.exists():
        (assets / "model.json").write_text(txt, encoding="utf-8")
    return d


def deflated(selected_r: np.ndarray) -> dict:
    r = np.asarray(selected_r, dtype=float)
    if len(r) < 20:
        return {"n": int(len(r)), "note": "amostra insuficiente"}
    sr = r.mean() / r.std(ddof=1)
    sr0 = S.expected_max_sharpe(N_TRIALS, 1.0 / (len(r) - 1))
    return {"n": int(len(r)), "sharpe_per_trade": float(sr), "trials": N_TRIALS,
            "sr_benchmark_max_under_h0": float(sr0),
            "psr_vs_0": S.probabilistic_sharpe(r, 0.0), "dsr": S.probabilistic_sharpe(r, sr0)}


def train(settings: dict | None = None, hub: DataHub | None = None, write_report: bool = True,
          dataset: pd.DataFrame | None = None) -> dict:
    settings = settings or load_settings()
    hub = hub or DataHub(settings)
    t0 = time.time()
    df = dataset if dataset is not None else build_dataset(hub, settings["universe"], settings)
    if df.empty or len(df) < settings["model"]["min_train_samples"]:
        raise RuntimeError("amostra insuficiente para treinar o modelo")
    xc = feature_cols(df)
    primary = settings["model"].get("kind", "logistic")
    results = {}
    for kind in ("logistic", "hgb"):
        results[kind] = WF.run(df, settings, kind=kind)
    prim = results[primary]

    # modelo de produção: todos os candidatos resolvidos até agora
    resolved = df[df["resolved"]]
    model = ProbabilityModel(kind=primary, calibration=settings["model"].get("calibration", "sigmoid"))
    model.fit(resolved[xc], resolved["y"].to_numpy(), resolved["r"].to_numpy(), resolved["rr1"].to_numpy())
    oos_full = prim["completo"]["calibration"]
    gate = settings["gates"]
    m = oos_full["metrics"]
    # validação estatística (calibração/discriminação) E econômica (trades selecionados OOS lucrativos)
    st_sel = prim["completo"].get("selected_trades", {}) or {}
    econ_ok = bool((st_sel.get("n") or 0) >= 30 and (st_sel.get("avg_r") or -1) > 0
                   and (st_sel.get("p_value_mean_gt0") if st_sel.get("p_value_mean_gt0") is not None else 1) < 0.10)
    validated = bool(m.get("bss", -1) > gate["min_model_bss"] and m.get("auc", 0) >= gate["min_model_auc"] and econ_ok)
    model.meta.update({
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "data_start": df["decision_time"].min().isoformat(),
        "data_end": df["decision_time"].max().isoformat(),
        "n_candidates": int(len(df)),
        "oos_metrics": clean(m),
        "oos_calibration_table": clean(oos_full["table"]),
        "oos_holdout_metrics": clean(prim.get("holdout_2026", {}).get("calibration", {}).get("metrics")),
        "validated": validated,
        "validation_rule": (f"BSS OOS > {gate['min_model_bss']}, AUC OOS >= {gate['min_model_auc']} e trades "
                            "selecionados OOS com R médio > 0 (p < 0,10, n >= 30)"),
        "oos_selected_trades": clean(st_sel),
        "coefficients": model.coefficients()[:15],
        "features": xc,
        "horizon_bars": settings["model"]["horizon_bars"],
    })
    model.save(MODEL_PATH)
    export_model(model)

    sel = prim["selected"]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(time.time() - t0, 1),
        "primary_model": primary,
        "model_validated": validated,
        "validation_rule": model.meta["validation_rule"],
        "universe": settings["universe"],
        "dataset": {
            "n_candidates": int(len(df)), "start": df["decision_time"].min().isoformat(),
            "end": df["decision_time"].max().isoformat(),
            "by_setup": clean(df.groupby("setup").agg(n=("r", "size"), hit_rate=("y", "mean"),
                                                       avg_r=("r", "mean"), avg_r_gross=("r_gross", "mean"),
                                                       avg_cost_r=("cost_r", "mean")).round(4).to_dict("index")),
            "by_symbol": clean(df.groupby("symbol").agg(n=("r", "size"), hit_rate=("y", "mean"),
                                                         avg_r=("r", "mean"), avg_r_gross=("r_gross", "mean"),
                                                         avg_cost_r=("cost_r", "mean")).round(4).to_dict("index")),
            "outcomes": clean(df["outcome"].value_counts(normalize=True).round(4).to_dict()),
            "all_candidates_net": clean(trade_metrics(df["r"].to_numpy())),
            "all_candidates_gross": clean(trade_metrics(df["r_gross"].dropna().to_numpy())),
        },
        "walk_forward": {k: clean(_summ(v)) for k, v in results.items()},
        "deflated_sharpe_selected": clean(deflated(sel["r"].to_numpy())) if len(sel) else None,
        "research_log": RESEARCH_LOG,
        "settings": {"gates": settings["gates"], "risk": settings["risk"], "account": settings["account"], "slippage": settings["slippage"],
                     "session_spread_multipliers": settings["session_spread_multipliers"],
                     "horizon_bars": settings["model"]["horizon_bars"]},
    }
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    if write_report:
        from .backtest.report import write_markdown
        report["files"] = write_markdown(report, results, primary)
    return report

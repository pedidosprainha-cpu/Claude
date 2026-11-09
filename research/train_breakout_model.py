"""Train and validate the breakout probability model from the historical replay.

    python research/train_breakout_model.py [--events research/data/breakout_events.csv]

Time-ordered split (never shuffled): first 60% of days = train, next 15% =
validation (L2 strength, grade cut-offs, actionable threshold), last 25% =
test (untouched; every number in the report comes from it). The shipped model
is then refit on all days with the same settings.

Model: L2-regularised logistic regression of y = "target 1 before stop" on the
detector's features (fxengine.breakouts.FEATURES), solved by Newton/IRLS with
numpy only, so the app needs nothing beyond a dot product at runtime.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fxengine.breakouts import FEATURES, MODEL_PATH, derived_value  # noqa: E402

DERIVED = [
    "ext_atr^2", "run_atr^2", "approach^2", "rr1^2", "room_atr^2",
    "st_falso*htf_trend", "st_falso*strength_dir", "st_falso*approach", "st_falso*brk_clv",
    "st_reteste*htf_trend", "tf_h1*htf_trend", "tf_h1*rr1", "is_metal*htf_trend",
    "kind_box*bbw_pct", "sess_asia*brk_range",
]


def design(df: pd.DataFrame, names: list[str]) -> np.ndarray:
    base = [dict(zip(FEATURES, row)) for row in df[[f"f_{f}" for f in FEATURES]].to_numpy(float)]
    return np.array([[derived_value(n, b) for n in names] for b in base], dtype=float)

GRADE_QUANTILES = [(0.95, "A+"), (0.85, "A"), (0.70, "B"), (0.45, "C")]


def fit_logreg(X: np.ndarray, y: np.ndarray, lam: float, iters: int = 100) -> np.ndarray:
    n, k = X.shape
    Xb = np.hstack([np.ones((n, 1)), X])
    w = np.zeros(k + 1)
    R = lam * np.eye(k + 1)
    R[0, 0] = 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(Xb @ w)))
        W = np.clip(p * (1 - p), 1e-9, None)
        g = Xb.T @ (p - y) + R @ w
        H = Xb.T @ (Xb * W[:, None]) + R
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return w


def predict(w: np.ndarray, X: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-(w[0] + X @ w[1:])))


def auc(y: np.ndarray, s: np.ndarray) -> float:
    order = np.argsort(s)
    ranks = np.empty(len(s))
    ranks[order] = np.arange(1, len(s) + 1)
    pos = y == 1
    n1, n0 = pos.sum(), (~pos).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def logloss(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def summary(df: pd.DataFrame, mask, days: float) -> dict:
    sub = df[mask]
    if len(sub) == 0:
        return {"n": 0, "por_dia": 0.0, "acerto_tp1": None, "r_tp1": None, "r_gerenciado": None}
    return {"n": int(len(sub)), "por_dia": round(len(sub) / days, 1),
            "acerto_tp1": round(float(sub.y_tp1.mean()), 3),
            "r_tp1": round(float(sub.r_tp1.mean()), 3),
            "r_gerenciado": round(float(sub.r_managed.mean()), 3)}


def grade_of(ev: np.ndarray, cuts: list[tuple[float, str]]) -> np.ndarray:
    out = np.full(len(ev), "D", dtype=object)
    for t, g in reversed(cuts):          # lowest first, best overwrite last
        out[ev >= t] = g
    return out


STOPS = {"p": None, "h075": 0.75, "h1": 1.0, "h15": 1.5}
TARGETS = {"p": None, "r1": 1.0, "r15": 1.5, "r2": 2.0}
EXCLUDE = {"is_long"}          # period-specific drift (USD trend), not a durable signal


def geometry_frame(df: pd.DataFrame, sk: str, tk: str) -> pd.DataFrame:
    """Same events, with labels/plan-dependent features recomputed for one stop/target geometry."""
    g = df.copy()
    sl = g[f"sl_{sk}"]
    rr = (g.plan_tp / sl) if TARGETS[tk] is None else pd.Series(TARGETS[tk], index=g.index)
    g["f_spread_ratio"] = (g.spread / sl).clip(upper=1.0)
    g["f_rr1"] = rr.clip(upper=4.0)
    g["rr"] = rr
    g["y"] = g[f"y_{sk}_{tk}"]
    g["r"] = g[f"r_{sk}_{tk}"]
    return g


def _unused_fit_select(g: pd.DataFrame, names: list[str], tr, va, lams=(10, 30, 100, 300, 1000)):
    X = design(g, names)
    mu, sd = X[tr].mean(0), X[tr].std(0)
    sd[sd < 1e-9] = 1.0
    Z = (X - mu) / sd
    y = g.y.to_numpy(float)
    best = None
    for lam in lams:
        w = fit_logreg(Z[tr], y[tr], lam)
        ll = logloss(y[va], predict(w, Z[va]))
        if best is None or ll < best[1]:
            best = (lam, ll, w)
    return best[0], best[2], X, Z


def tune_threshold(g: pd.DataFrame, ev: np.ndarray, mask, hard) -> tuple[float, float, int]:
    best = None
    n_min = max(40, int(0.04 * mask.sum()))
    for t in np.linspace(-0.2, 0.8, 101):
        m = mask & (ev >= t) & ~hard
        if m.sum() < n_min:
            continue
        r = float(g[m].r.mean())
        if best is None or r > best[1]:
            best = (float(t), r, int(m.sum()))
    return best if best else (0.0, float("nan"), 0)


def stats(g: pd.DataFrame, mask, days: float) -> dict:
    sub = g[mask]
    if len(sub) == 0:
        return {"n": 0, "por_dia": 0.0, "acerto": None, "r": None}
    return {"n": int(len(sub)), "por_dia": round(len(sub) / days, 1),
            "acerto": round(float(sub.y.mean()), 3), "r": round(float(sub.r.mean()), 3)}


def walk_forward(g: pd.DataFrame, names: list[str], blocks: np.ndarray, lams=(10, 30, 100, 300, 1000)):
    """Expanding-window out-of-sample predictions for blocks 2..4 (block 5 = final test, untouched).

    Returns (lambda, oos_prob) where oos_prob is NaN outside the CV blocks."""
    X = design(g, names)
    y = g.y.to_numpy(float)
    best = None
    for lam in lams:
        oos = np.full(len(g), np.nan)
        for k in (1, 2, 3):
            trm, tem = blocks < k, blocks == k
            mu, sd = X[trm].mean(0), X[trm].std(0)
            sd[sd < 1e-9] = 1.0
            w = fit_logreg((X[trm] - mu) / sd, y[trm], lam)
            oos[tem] = predict(w, (X[tem] - mu) / sd)
        m = ~np.isnan(oos)
        ll = logloss(y[m], oos[m])
        if best is None or ll < best[1]:
            best = (lam, ll, oos)
    return best[0], best[2], X


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default=os.path.join(ROOT, "research", "data", "breakout_events.csv"))
    ap.add_argument("--model-out", default=MODEL_PATH)
    ap.add_argument("--report", default=os.path.join(ROOT, "research", "RESULTADOS_ROMPIMENTOS.md"))
    a = ap.parse_args()

    df = pd.read_csv(a.events)
    df["t"] = pd.to_datetime(df.time, utc=True)
    df = df.sort_values("t").reset_index(drop=True)
    df["day"] = df.t.dt.floor("D")
    days = np.sort(df.day.unique())
    # 5 consecutive blocks of days: 0 = first training block, 1-3 = walk-forward CV, 4 = final test
    edges = [days[int(len(days) * q)] for q in (0.2, 0.4, 0.6, 0.8)]
    blocks = np.searchsorted(np.array(edges), df.day.to_numpy(), side="right")
    cv = (blocks >= 1) & (blocks <= 3)
    te = blocks == 4
    nd = {"cv": float(df[cv].day.nunique()), "te": float(df[te].day.nunique())}
    names = [f for f in FEATURES if f not in EXCLUDE] + DERIVED


    # --- geometry chosen on walk-forward OOS predictions (blocks 1-3): best mean R of the
    #     model's top 10% (a fixed quantile, not an optimised threshold, to limit overfitting)
    trials = []
    for sk in STOPS:
        for tk in TARGETS:
            g = geometry_frame(df, sk, tk)
            lam, oos, X = walk_forward(g, names, blocks)
            ev = oos * g.rr.to_numpy() - (1 - oos)
            hard = ((g.extended == 1) | (g.f_spread_ratio > 0.3)).to_numpy()
            ok = cv & ~hard
            thr = float(np.quantile(ev[ok], 0.90))
            top = ok & (ev >= thr)
            trials.append({"geo": (sk, tk), "lam": lam, "X": X, "oos": oos, "hard": hard, "g": g,
                           "r_va": float(g[top].r.mean()), "n_va": int(top.sum()),
                           "r_all": float(g[ok].r.mean()), "auc_va": auc(g.y.to_numpy()[cv], oos[cv])})
            print(f"  walk-forward {sk:>4}/{tk:<3} λ={lam:<5} auc={trials[-1]['auc_va']:.3f} "
                  f"todos R={trials[-1]['r_all']:+.3f} · top10% n={top.sum()} R={trials[-1]['r_va']:+.3f}",
                  flush=True)
    best = max(trials, key=lambda t: t["r_va"])
    sk, tk = best["geo"]
    g, oos, hard = best["g"], best["oos"], best["hard"]
    y = g.y.to_numpy(float)
    print(f"  escolhido: stop {sk}, alvo {tk}")

    # --- Platt recalibration of the OOS probabilities (makes the displayed odds honest)
    lo = np.log(np.clip(oos[cv], 1e-6, 1 - 1e-6) / (1 - np.clip(oos[cv], 1e-6, 1 - 1e-6)))
    wa = fit_logreg(lo[:, None], y[cv], 1e-6)
    pa, pb = float(wa[1]), float(wa[0])

    def recal(pv):
        z = np.log(np.clip(pv, 1e-6, 1 - 1e-6) / (1 - np.clip(pv, 1e-6, 1 - 1e-6)))
        return 1 / (1 + np.exp(-(pa * z + pb)))

    p_cv = recal(np.nan_to_num(oos, nan=0.5))
    ev_cv = p_cv * g.rr.to_numpy() - (1 - p_cv)
    ok = cv & ~hard
    cuts = [(float(np.quantile(ev_cv[ok], q)), gname) for q, gname in
            ((0.97, "A+"), (0.90, "A"), (0.75, "B"), (0.50, "C"))]
    thr = cuts[1][0]
    n_cv2 = int((ok & (ev_cv >= thr)).sum())
    r_cv2 = float(g[ok & (ev_cv >= thr)].r.mean())
    exclude_status, exclude_metals = [], False

    # --- final test: train on blocks 0-3, predict block 4 (never used above)
    X = best["X"]
    trm = blocks <= 3
    mu, sd = X[trm].mean(0), X[trm].std(0)
    sd[sd < 1e-9] = 1.0
    w = fit_logreg((X[trm] - mu) / sd, y[trm], best["lam"])
    p_te = recal(predict(w, (X - mu) / sd))
    ev_te = p_te * g.rr.to_numpy() - (1 - p_te)
    gr = grade_of(ev_te, cuts)
    plan = geometry_frame(df, "p", "p")
    plan["y"], plan["r"] = df.y_tp1, df.r_tp1
    old_act = te & (df.actionable_old == 1).to_numpy()
    new_act = te & (ev_te >= thr) & ~hard
    yte, pte = y[te], p_te[te]
    calib = []
    qb = pd.qcut(pte, 5, duplicates="drop")
    for b, grp in pd.Series(yte).groupby(qb, observed=True):
        calib.append((str(b), round(float(pte[qb == b].mean()), 3), round(float(grp.mean()), 3), int(len(grp))))
    r_new = g[new_act].r.to_numpy()
    se = float(r_new.std(ddof=1) / np.sqrt(len(r_new))) if len(r_new) > 1 else float("nan")
    blocks_tbl = []
    for b in (1, 2, 3):
        m = (blocks == b) & ~hard
        mt = m & (ev_cv >= thr)
        mp = (blocks == b)
        blocks_tbl.append({"bloco": b, "todos_plano_antigo": round(float(plan[mp].r.mean()), 3),
                           "todos_geometria_nova": round(float(g[m].r.mean()), 3),
                           "melhores_modelo": round(float(g[mt].r.mean()), 3), "n_melhores": int(mt.sum())})
    res = {
        "eventos": int(len(df)), "dias": int(len(days)),
        "periodo": [str(df.t.min()), str(df.t.max())], "teste_desde": str(edges[3])[:10],
        "geometria": {"stop": sk, "alvo": tk, "stop_atr_h1": STOPS[sk], "tp1_r": TARGETS[tk]},
        "lambda": best["lam"], "ev_minimo_acionavel": round(thr, 3),
        "auc_teste": round(auc(yte, pte), 3),
        "auc_nota_antiga_teste": round(auc(df.y_tp1.to_numpy()[te], df.score_old.to_numpy()[te]), 3),
        "todos_plano_antigo": stats(plan, te, nd["te"]),
        "acionaveis_regra_antiga": stats(plan, old_act, nd["te"]),
        "todos_geometria_nova": stats(g, te, nd["te"]),
        "acionaveis_modelo_novo": stats(g, new_act, nd["te"]),
        "erro_padrao_r_novo": round(se, 3),
        "acionaveis_modelo_novo_validacao": {"n": n_cv2, "r": round(r_cv2, 3)},
        "blocos_walk_forward": blocks_tbl,
        "excluidos": {"status": exclude_status, "metais": exclude_metals},
        "por_nota_nova": {gn: stats(g, te & (gr == gn) & ~hard, nd["te"]) for gn in ("A+", "A", "B", "C", "D")},
        "por_nota_antiga": {gn: stats(plan, te & (df.grade_old == gn).to_numpy(), nd["te"])
                            for gn in ("A+", "A", "B", "C", "D")},
        "calibracao_teste": calib,
        "por_tf_novo": {tf: stats(g, new_act & (df.tf == tf).to_numpy(), nd["te"]) for tf in ("M15", "H1")},
        "por_classe_novo": {c: stats(g, new_act & df.symbol.map(cls).eq(c).to_numpy(), nd["te"])
                            for c in ("major", "cross", "metal")},
        "geometrias_validacao": [{"geo": "/".join(t["geo"]), "r_va": round(t["r_va"], 3), "n_va": t["n_va"],
                                  "auc_va": round(t["auc_va"], 3)} for t in trials],
    }

    # --- refit on all days for shipping (same geometry, lambda, thresholds)
    mu_f, sd_f = X.mean(0), X.std(0)
    sd_f[sd_f < 1e-9] = 1.0
    w_f = fit_logreg((X - mu_f) / sd_f, y, best["lam"])
    w_f = np.concatenate([[pa * w_f[0] + pb], pa * w_f[1:]])      # fold the Platt recalibration in
    coef = {f: round(float(c), 4) for f, c in zip(names, w_f[1:])}
    model = {
        "features": names, "mean": mu_f.round(6).tolist(), "std": sd_f.round(6).tolist(),
        "coef": [coef[f] for f in names], "intercept": round(float(w_f[0]), 5),
        "ev_grades": [[round(t, 4), gname] for t, gname in cuts],
        "ev_actionable": round(thr, 4), "p_actionable": 0.0,
        "geometry": {"stop_atr_h1": STOPS[sk], "tp1_r": TARGETS[tk]},
        "exclude_status": exclude_status, "exclude_metals": exclude_metals,
        "info": {"trained_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                 "events": int(len(df)), "period": res["periodo"],
                 "test": {k: res[k] for k in ("auc_teste", "acionaveis_regra_antiga", "acionaveis_modelo_novo")}},
    }
    with open(a.model_out, "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, indent=1)
    res["coeficientes"] = dict(sorted(coef.items(), key=lambda kv: -abs(kv[1])))
    print(json.dumps({k: v for k, v in res.items() if k not in ("coeficientes", "geometrias_validacao")},
                     ensure_ascii=False, indent=1))
    write_report(a.report, res)
    return 0


def cls(sym: str) -> str:
    if sym.startswith("X"):
        return "metal"
    return "major" if sym in {"EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"} else "cross"


def _row(name, s):
    if not s["n"]:
        return f"| {name} | 0 | – | – | – |"
    return f"| {name} | {s['n']} | {s['por_dia']} | {s['acerto'] * 100:.1f}% | {s['r']:+.3f} |"


GEO_TXT = {"p": "do plano", "h075": "≥ 0,75 ATR H1", "h1": "≥ 1 ATR H1", "h15": "≥ 1,5 ATR H1",
           "r1": "1R", "r15": "1,5R", "r2": "2R"}


def write_report(path: str, r: dict) -> None:
    head = "| | alertas | por dia | alvo antes do stop | R médio por trade |\n|---|---|---|---|---|"
    geo = r["geometria"]
    L = [
        "# Rompimentos — validação histórica do detector",
        "",
        f"Reconstituição walk-forward de **{r['eventos']} alertas** em {r['dias']} dias "
        f"({r['periodo'][0][:10]} a {r['periodo'][1][:10]}): 32 ativos, M15 e H1, entrada a mercado no "
        f"fechamento do candle do alerta, spread descontado, stop testado primeiro quando os dois são tocados "
        f"no mesmo candle. Escolhas feitas por validação walk-forward (3 blocos) até {r['teste_desde']}; **todos os números abaixo são do período "
        f"de teste**, que o modelo não viu.",
        "",
        "## Antes x depois",
        "", head,
        _row("todos os rompimentos, plano antigo", r["todos_plano_antigo"]),
        _row("acionáveis pela regra antiga", r["acionaveis_regra_antiga"]),
        _row("todos os rompimentos, geometria nova", r["todos_geometria_nova"]),
        _row("**melhores do modelo novo (A/A+)**", r["acionaveis_modelo_novo"]),
        "",
        f"Erro-padrão do R médio dos melhores (A/A+): ±{r['erro_padrao_r_novo']:.3f}R "
        f"(walk-forward: {r['acionaveis_modelo_novo_validacao']['n']} alertas, "
        f"R médio {r['acionaveis_modelo_novo_validacao']['r']:+.3f}).",
        "",
        "## Estabilidade por bloco (walk-forward, fora da amostra)",
        "",
        "| bloco | todos, plano antigo | todos, geometria nova | melhores do modelo (A/A+) | alertas |",
        "|---|---|---|---|---|",
    ] + [f"| {b['bloco']} | {b['todos_plano_antigo']:+.3f} | {b['todos_geometria_nova']:+.3f} | "
         f"{b['melhores_modelo']:+.3f} | {b['n_melhores']} |" for b in r["blocos_walk_forward"]] + [
        "",
        f"Geometria escolhida na validação: stop {GEO_TXT[geo['stop']]}, alvo 1 {GEO_TXT[geo['alvo']]}. "
        f"Notas por quantil da expectativa calibrada: A+ = melhores 3%, A = melhores 10% "
        f"(corte {r['ev_minimo_acionavel']:+.2f}R), B = 25%, C = 50%.",
        f"Poder de separação (AUC, 0,5 = acaso): modelo **{r['auc_teste']}** x nota antiga "
        f"{r['auc_nota_antiga_teste']}.",
        "",
        "## Por nota (modelo novo, teste)", "", head,
    ]
    L += [_row(g, s) for g, s in r["por_nota_nova"].items()]
    L += ["", "## Por nota (regra antiga, teste)", "", head]
    L += [_row(g, s) for g, s in r["por_nota_antiga"].items()]
    L += ["", "## Acionáveis do modelo novo por timeframe e classe (teste)", "", head]
    L += [_row(k, s) for k, s in r["por_tf_novo"].items()]
    L += [_row(k, s) for k, s in r["por_classe_novo"].items()]
    L += ["", "## Calibração no teste (probabilidade prevista x frequência real)", "",
          "| faixa | prevista | real | eventos |", "|---|---|---|---|"]
    L += [f"| {b} | {p * 100:.1f}% | {o * 100:.1f}% | {n} |" for b, p, o, n in r["calibracao_teste"]]
    L += ["", "## Geometrias avaliadas (walk-forward)", "", "| stop/alvo | alertas | R médio | AUC |",
          "|---|---|---|---|"]
    L += [f"| {t['geo']} | {t['n_va']} | {t['r_va']:+.3f} | {t['auc_va']} |" for t in r["geometrias_validacao"]]
    L += ["", "## O que mais pesa (coeficientes padronizados)", "", "| feature | peso |", "|---|---|"]
    L += [f"| {k} | {v:+.3f} |" for k, v in list(r["coeficientes"].items())[:15]]
    L += ["", "Limitações: spreads típicos constantes (sem bid/ask histórico), sem agenda econômica "
               "histórica, metais com candles de futuros, ~2,5 meses de M15 (limite do Yahoo), um único "
               "regime de mercado. Resultado passado não garante resultado futuro; o modelo deve ser "
               "retreinado periodicamente (research/breakout_replay.py + train_breakout_model.py)."]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())

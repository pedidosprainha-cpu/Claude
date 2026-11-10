"""Train the per-timeframe breakout model on the best validated entry/exit plan (version 2).

    python research/train_entry_model.py \\
        --tf H1  --events research/data/breakout_events_h1.csv --sim research/data/lab_h1.csv \\
        --tf M15 --events research/data/breakout_events.csv   --sim research/data/lab_m15.csv

For each timeframe:
  1. candidate plans = the most robust variants of research/entry_exit_lab.py
  2. for each plan, an L2 logistic model of P(trade ends in profit) is trained
     walk-forward (expanding window) over time blocks 1..n-2
  3. plan + filter (top 10% / 25% / 50% / all) are chosen by the best WORST
     block of out-of-sample mean R; grades are quantiles of that ranking
  4. the last block, untouched by every choice, is the test reported
  5. a timeframe whose chosen setup is not positive in the walk-forward is
     shipped with enabled=false (never graded A, never alerted)
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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gbm import GBM  # noqa: E402
from train_breakout_model import auc, design, fit_logreg, logloss, predict  # noqa: E402

from fxengine.breakouts import EXIT_CFG, FEATURES, MODEL_PATH  # noqa: E402

EXCLUDE = {"is_long"}
DERIVED = ["ext_atr^2", "run_atr^2", "approach^2", "st_falso*htf_trend", "st_falso*strength_dir",
           "st_reteste*htf_trend", "is_metal*htf_trend", "kind_box*bbw_pct", "sess_asia*brk_range",
           "adr_used^2", "day_pos^2", "move_today^2", "st_falso*d1_trend", "st_falso*day_pos",
           "st_falso*adr_used", "h_london*brk_range", "h_ny*brk_range", "d1_trend*htf_trend"]
FILTERS = (0.05, 0.10, 0.25, 0.50, 1.00)  # share of best-ranked alerts kept
LAMS = (10, 30, 100, 300, 1000)
GBM_GRID = ({"depth": 2, "min_leaf": 600, "n_trees": 150, "lr": 0.05},
            {"depth": 3, "min_leaf": 400, "n_trees": 150, "lr": 0.05})
MODEL_TYPE = "logit"                     # set by --model


def fit_predict(param, Xtr, ytr, Xte):
    """Return (predict function on Xte, fitted object) for the current MODEL_TYPE."""
    if MODEL_TYPE == "gbm":
        m = GBM(**param).fit(Xtr, ytr)
        return m.predict(Xte), m
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd[sd < 1e-9] = 1.0
    w = fit_logreg((Xtr - mu) / sd, ytr, param)
    return predict(w, (Xte - mu) / sd), (w, mu, sd)


def prepare(events: str, sim: str, n_blocks: int) -> pd.DataFrame:
    ev = pd.read_csv(events)
    ev["eid"] = np.arange(len(ev))
    df = ev.merge(pd.read_csv(sim), on="eid").copy()
    df["t"] = pd.to_datetime(df.time, utc=True)
    df = df.sort_values("t").reset_index(drop=True)
    days = np.sort(df.t.dt.floor("D").unique())
    edges = [days[int(len(days) * q / n_blocks)] for q in range(1, n_blocks)]
    df["block"] = np.searchsorted(np.array(edges), df.t.dt.floor("D").to_numpy(), side="right")
    df.attrs["days"] = len(days)
    df.attrs["edges"] = [str(e)[:10] for e in edges]
    df.attrs["period"] = [str(days[0])[:10], str(days[-1])[:10]]
    return df


def variant_frame(df: pd.DataFrame, v: str) -> pd.DataFrame:
    em, sk, xk = v.split("|")
    g = df[df[v].notna()].copy()
    sl = g[f"sl|{em}|{sk}"]
    kind, val = EXIT_CFG[xk]
    g["f_spread_ratio"] = (g.spread / sl).clip(upper=1.0)
    g["f_rr1"] = 1.0 if kind == "trail" else val
    g["r"] = g[v]
    g["y"] = (g.r > 0).astype(float)
    return g


def walk_forward(g: pd.DataFrame, names: list[str], n_blocks: int):
    X = design(g, names)
    y = g.y.to_numpy(float)
    b = g.block.to_numpy()
    best = None
    for lam in (GBM_GRID if MODEL_TYPE == "gbm" else LAMS):
        oos = np.full(len(g), np.nan)
        for k in range(1, n_blocks - 1):
            tr, te = b < k, b == k
            if tr.sum() < 200 or te.sum() == 0:
                continue
            oos[te] = fit_predict(lam, X[tr], y[tr], X[te])[0]
        m = ~np.isnan(oos)
        ll = logloss(y[m], oos[m])
        if best is None or ll < best[1]:
            best = (lam, ll, oos)
    return best[0], best[2], X


def block_stats(g: pd.DataFrame, mask: np.ndarray, blocks) -> dict:
    per = {int(k): float(g[mask & (g.block == k).to_numpy()].r.mean()) for k in blocks}
    vals = [v for v in per.values() if np.isfinite(v)]
    return {"por_bloco": per, "pior": min(vals) if vals else -9, "media": float(g[mask].r.mean()),
            "n": int(mask.sum())}


def train_tf(tf: str, df: pd.DataFrame, n_blocks: int, candidates: list[str]) -> tuple[dict, dict]:
    names = [f for f in FEATURES if f not in EXCLUDE] + DERIVED
    cv_blocks = list(range(1, n_blocks - 1))
    test_block = n_blocks - 1
    trials = []
    for v in candidates:
        g = variant_frame(df, v)
        lam, oos, X = walk_forward(g, names, n_blocks)
        cv = g.block.isin(cv_blocks).to_numpy() & ~np.isnan(oos)
        for f in FILTERS:
            thr = float(np.quantile(oos[cv], 1 - f)) if f < 1 else -1.0
            sel = cv & (np.nan_to_num(oos, nan=-1) >= thr)
            st = block_stats(g, sel, cv_blocks)
            trials.append({"v": v, "lam": lam, "filtro": f, "thr": thr, "oos": oos, "X": X, "g": g, **st,
                           "auc": auc(g.y.to_numpy()[cv], oos[cv])})
            print(f"  [{tf}] {v:<22} top {int(f * 100):>3}%  n={st['n']:<5} média {st['media']:+.3f}  "
                  f"pior bloco {st['pior']:+.3f}  auc {trials[-1]['auc']:.3f}", flush=True)
    def robust(t):
        return (t["pior"], t["media"])              # best worst block, then best average

    best = max((t for t in trials if t["n"] >= 30 * (n_blocks - 2)), key=robust, default=None) \
        or max(trials, key=robust)
    v, g, oos, X = best["v"], best["g"], best["oos"], best["X"]
    em, sk, xk = v.split("|")
    print(f"  [{tf}] escolhido: {v}, top {int(best['filtro'] * 100)}% (pior bloco {best['pior']:+.3f})")

    y = g.y.to_numpy(float)
    cv = g.block.isin(cv_blocks).to_numpy() & ~np.isnan(oos)
    # Platt recalibration on the walk-forward predictions
    z = np.log(np.clip(oos[cv], 1e-6, 1 - 1e-6) / (1 - np.clip(oos[cv], 1e-6, 1 - 1e-6)))
    wa = fit_logreg(z[:, None], y[cv], 1e-6)
    pa, pb = float(wa[1]), float(wa[0])

    def recal(p):
        zz = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
        return 1 / (1 + np.exp(-(pa * zz + pb)))

    win_r = float(g[cv & (g.r > 0).to_numpy()].r.mean())
    loss_r = float(g[cv & (g.r <= 0).to_numpy()].r.mean())
    p_cv = recal(np.nan_to_num(oos, nan=0.5))
    ev_cv = p_cv * win_r + (1 - p_cv) * loss_r
    q = lambda f: float(np.quantile(ev_cv[cv], 1 - f))        # noqa: E731
    a_cut = q(best["filtro"]) if best["filtro"] < 1 else float(ev_cv[cv].min()) - 1
    vals = [x for x in best["por_bloco"].values() if np.isfinite(x)]
    enabled = (best["media"] > 0 and sum(x > 0 for x in vals) >= int(np.ceil(0.75 * len(vals)))
               and best["pior"] > -0.05)
    cuts = [(max(q(0.03), a_cut + 1e-6), "A+"), (a_cut, "A"), (min(q(0.30), a_cut - 1e-6), "B"),
            (min(q(0.55), a_cut - 2e-6), "C")]

    # final test on the last block (trained on everything before it)
    tr = (g.block < test_block).to_numpy()
    te = (g.block == test_block).to_numpy()
    p_te = recal(fit_predict(best["lam"], X[tr], y[tr], X)[0])
    ev_te = p_te * win_r + (1 - p_te) * loss_r
    sel_te = te & (ev_te >= a_cut)
    ref = "mercado|a15|tp2"
    gr_ref = variant_frame(df, ref) if ref in df.columns else None
    days_te = max(df[df.block == test_block].t.dt.floor("D").nunique(), 1)

    def s(mask, frame):
        sub = frame[mask]
        return {"n": int(len(sub)), "por_dia": round(len(sub) / days_te, 2),
                "acerto": round(float((sub.r > 0).mean()), 3) if len(sub) else None,
                "r": round(float(sub.r.mean()), 3) if len(sub) else None}

    calib = []
    if te.sum() > 50:
        qb = pd.qcut(p_te[te], 4, duplicates="drop")
        for b, grp in pd.Series(y[te]).groupby(qb, observed=True):
            calib.append([str(b), round(float(p_te[te][qb == b].mean()), 3), round(float(grp.mean()), 3), int(len(grp))])
    report = {
        "tf": tf, "plano": v, "filtro_top": best["filtro"], "ativo": enabled, "lambda": best["lam"],
        "modelo": MODEL_TYPE,
        "dias": df.attrs["days"], "blocos": df.attrs["edges"], "periodo": df.attrs["period"],
        "alertas": int(len(df)),
        "walk_forward": {"media": round(best["media"], 3), "pior_bloco": round(best["pior"], 3),
                         "por_bloco": {k: round(v2, 3) for k, v2 in best["por_bloco"].items()}, "n": best["n"]},
        "teste": {
            "referencia_app_1_2": s((gr_ref.block == test_block).to_numpy(), gr_ref) if gr_ref is not None else None,
            "plano_sem_filtro": s(te, g),
            "plano_com_filtro_A": s(sel_te, g),
            "auc": round(auc(y[te], p_te[te]), 3) if te.sum() > 20 else None,
            "calibracao": calib,
        },
        "candidatos": [{"v": t["v"], "filtro": t["filtro"], "media": round(t["media"], 3), "pior": round(t["pior"], 3),
                        "n": t["n"]} for t in sorted(trials, key=lambda t: -t["pior"])[:12]],
    }

    # ship: refit on all blocks, fold Platt into the coefficients
    window = {"H1": 6, "M15": 8}[tf]
    if MODEL_TYPE == "gbm":
        _, gb = fit_predict(best["lam"], X, y, X[:1])
        body = {"type": "gbm", "gbm": gb.export(), "platt": [round(pa, 6), round(pb, 6)],
                "mean": [0.0] * len(names), "std": [1.0] * len(names), "coef": [0.0] * len(names),
                "intercept": 0.0}
    else:
        mu_f, sd_f = X.mean(0), X.std(0)
        sd_f[sd_f < 1e-9] = 1.0
        w = fit_logreg((X - mu_f) / sd_f, y, best["lam"])
        w = np.concatenate([[pa * w[0] + pb], pa * w[1:]])
        body = {"type": "logit", "mean": mu_f.round(6).tolist(), "std": sd_f.round(6).tolist(),
                "coef": [round(float(c), 4) for c in w[1:]], "intercept": round(float(w[0]), 5)}
    model = {
        "features": names, **body,
        "ev_grades": [[round(t, 4), gname] for t, gname in cuts], "ev_actionable": round(a_cut, 4),
        "p_actionable": 0.0, "enabled": enabled, "win_r": round(win_r, 4), "loss_r": round(loss_r, 4),
        "plan": {"entry": em, "stop": sk, "exit": xk, "window": window},
        "test": report["teste"], "walk_forward": report["walk_forward"],
    }
    return model, report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", action="append", required=True)
    ap.add_argument("--events", action="append", required=True)
    ap.add_argument("--sim", action="append", required=True)
    ap.add_argument("--blocks", action="append", type=int, default=None)
    ap.add_argument("--candidates", type=int, default=8)
    ap.add_argument("--entries", default="", help="restrict entry modes, e.g. mercado,confirmacao")
    ap.add_argument("--model", choices=("logit", "gbm"), default="logit")
    ap.add_argument("--force-enable", default="",
                    help="timeframes to enable even if they fail the rule (user choice); marked validated=false")
    ap.add_argument("--profile", default="", help="name stored in the file (e.g. mercado, limite)")
    ap.add_argument("--model-out", default=MODEL_PATH)
    ap.add_argument("--report", default=os.path.join(ROOT, "research", "RESULTADOS_ENTRADAS.json"))
    a = ap.parse_args()
    global MODEL_TYPE
    MODEL_TYPE = a.model
    blocks = a.blocks or [7 if tf == "H1" else 5 for tf in a.tf]
    models, reports = {}, {}
    for tf, evp, simp, nb in zip(a.tf, a.events, a.sim, blocks):
        df = prepare(evp, simp, nb)
        df = df[df.tf == tf]
        lab = pd.read_csv(os.path.splitext(simp)[0] + "_resumo.csv")
        if a.entries:
            allowed = {x.strip() for x in a.entries.split(",")}
            lab = lab[lab.variante.str.split("|").str[0].isin(allowed)]
        cands = list(lab.sort_values("pior_bloco", ascending=False).variante.head(a.candidates))
        print(f"== {tf}: {len(df)} alertas, candidatos: {cands}")
        models[tf], reports[tf] = train_tf(tf, df, nb, cands)
        models[tf]["validated"] = bool(models[tf]["enabled"])
        if tf in {x.strip() for x in a.force_enable.split(",") if x.strip()}:
            models[tf]["enabled"] = True
    out = {"version": 2, "profile": a.profile, "models": models,
           "info": {"trained_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                    "events": int(sum(r["alertas"] for r in reports.values())),
                    "period": [min(r["periodo"][0] for r in reports.values()),
                               max(r["periodo"][1] for r in reports.values())],
                    "test": {tf: r["teste"] for tf, r in reports.items()}}}
    with open(a.model_out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(a.report, "w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False, indent=1, default=str)
    print(json.dumps({tf: {k: r[k] for k in ("plano", "filtro_top", "ativo", "walk_forward", "teste")}
                      for tf, r in reports.items()}, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

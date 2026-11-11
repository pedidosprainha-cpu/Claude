"""Train and validate the price-explosion detector.

    python3 research/train_explosion_model.py

Data: research/data/explosion_events.pkl (research/explosion_replay.py).
Explosion = the price moves >= THETA x ADR away from the decision close within 4 H1 bars.

Pre-registered rules (fixed before looking at any result):
  * time split in 8 blocks; the LAST block is the test, untouched until the end
  * walk-forward on blocks 1..6 (expanding window, 2-day embargo)
  * alert = top ALERT_Q of the model's training predictions
  * detection is VALIDATED when, in every walk-forward block, alert precision >= 2x the base
    rate AND the model beats a seasonality-only model (same GBM, hour-of-week features) in AUC
    in at least 5 of 6 blocks
  * direction is USEFUL when the walk-forward AUC averages >= 0.55 and no block is < 0.52
  * a bracket (OCO) plan is VALIDATED when, on alerts, mean R > 0, >= 75% of blocks positive
    and worst block > -0.05R (variant chosen by the worst block)
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
from train_breakout_model import auc, fit_logreg  # noqa: E402

from fxengine.analysis import explosion as ex  # noqa: E402

THETA = 0.5
ALERT_Q = 0.05
LEVEL_Q = [(0.99, "extrema"), (0.95, "alta"), (0.85, "elevada")]
SEASONAL = ["seas_fwd", "seas_now", "h_sin", "h_cos", "dow_mon", "dow_fri", "is_metal"]
EMBARGO = pd.Timedelta(days=2)
GBM_PARAM = {"n_trees": 150, "depth": 3, "lr": 0.05, "min_leaf": 2000}
MAX_ROWS = 300_000


def X_of(df: pd.DataFrame, cols) -> np.ndarray:
    return np.nan_to_num(df[cols].to_numpy(np.float64))


def fit_gbm(tr: pd.DataFrame, cols, y) -> GBM:
    step = max(1, len(tr) // MAX_ROWS)
    return GBM(**GBM_PARAM).fit(X_of(tr, cols)[::step], y[::step])


def bracket_trades(va: pd.DataFrame, alert: np.ndarray, col: str) -> np.ndarray:
    """R of non-overlapping bracket trades on alerts (one per instrument every 16 hours)."""
    sub = va[alert]
    out, free = [], {}
    for sym, t, r in zip(sub.symbol.to_numpy(), sub.time.to_numpy(), sub[col].to_numpy()):
        t = pd.Timestamp(t)
        if sym in free and t < free[sym]:
            continue
        free[sym] = t + pd.Timedelta(hours=16)
        if np.isfinite(r):
            out.append(float(r))
    return np.array(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(ROOT, "research", "data", "explosion_events.pkl"))
    ap.add_argument("--blocks", type=int, default=8)
    ap.add_argument("--model-out", default=ex.MODEL_PATH)
    ap.add_argument("--report", default=os.path.join(ROOT, "research", "RESULTADOS_EXPLOSAO.json"))
    a = ap.parse_args()

    df = pd.read_pickle(a.data)
    df["time"] = pd.to_datetime(df.time, utc=True)
    df["y"] = (df.exc >= THETA).astype(float)
    t0, t1 = df.time.min(), df.time.max()
    edges = [t0 + (t1 - t0) * i / a.blocks for i in range(a.blocks + 1)]
    df["block"] = np.clip(np.searchsorted(edges, df.time, side="right") - 1, 0, a.blocks - 1)
    test_b = a.blocks - 1
    oco_cols = [c for c in df.columns if c.startswith("oco|")]
    first = f"first_{THETA}"
    print(f"{len(df)} barras · explosão = movimento ≥ {THETA}× ADR em 4h · taxa base {df.y.mean() * 100:.1f}% · "
          f"teste = bloco {test_b} ({edges[test_b]:%d/%m/%Y} → {t1:%d/%m/%Y})", flush=True)

    wf, oos = [], {"z": [], "y": [], "exc": [], "alert": []}
    oco_wf = {c: [] for c in oco_cols}
    dir_auc = []
    for b in range(1, test_b):
        tr = df[(df.block < b) & (df.time < edges[b] - EMBARGO)]
        va = df[df.block == b]
        ytr, yva = tr.y.to_numpy(), va.y.to_numpy()
        m = fit_gbm(tr, ex.FEATURES, ytr)
        ms = fit_gbm(tr, SEASONAL, ytr)
        z_tr = m.decision(X_of(tr.iloc[::5], ex.FEATURES))
        z = m.decision(X_of(va, ex.FEATURES))
        zs = ms.decision(X_of(va, SEASONAL))
        thr = float(np.quantile(z_tr, 1 - ALERT_Q))
        alert = z >= thr
        sq = (va["squeeze"].to_numpy() > 0) & (va["bbw_pct"].to_numpy() <= 0.2)
        base = float(yva.mean())
        row = {"block": b, "base": round(base, 4), "auc": round(auc(yva, z), 4), "auc_seas": round(auc(yva, zs), 4),
               "prec_alert": round(float(yva[alert].mean()), 4), "n_alert": int(alert.sum()),
               "lift": round(float(yva[alert].mean()) / base, 2),
               "prec_squeeze": round(float(yva[sq].mean()), 4) if sq.any() else None}
        wf.append(row)
        print("  ", row, flush=True)
        oos["z"].append(z)
        oos["y"].append(yva)
        oos["exc"].append(va.exc.to_numpy())
        oos["alert"].append(alert)
        for c in oco_cols:
            r = bracket_trades(va, alert, c)
            oco_wf[c].append((float(r.mean()) if len(r) else 0.0, len(r)))
        # direction of the explosion (only rows that exploded with a clear first side)
        ex_tr = tr[tr[first].isin([1, -1])]
        ex_va = va[va[first].isin([1, -1])]
        Xd = X_of(ex_tr, ex.DIR_FEATURES)
        mu, sd = Xd.mean(0), Xd.std(0)
        sd[sd < 1e-9] = 1.0
        w = fit_logreg((Xd - mu) / sd, (ex_tr[first].to_numpy() == 1).astype(float), 10.0)
        zd = w[0] + ((X_of(ex_va, ex.DIR_FEATURES) - mu) / sd) @ w[1:]
        dir_auc.append(round(auc((ex_va[first].to_numpy() == 1).astype(float), zd), 4))

    lifts = [r["lift"] for r in wf]
    beats = sum(r["auc"] > r["auc_seas"] for r in wf)
    validated = bool(min(lifts) >= 2.0 and beats >= 5)
    dir_useful = bool(np.mean(dir_auc) >= 0.55 and min(dir_auc) >= 0.52)
    print(f"\ndetecção: lift mínimo {min(lifts):.2f} · AUC > sazonalidade em {beats}/6 blocos → "
          f"{'VALIDADA' if validated else 'NÃO validada'}")
    print(f"direção: AUC por bloco {dir_auc} → {'útil' if dir_useful else 'sem poder preditivo'}")

    oco_rows = []
    for c, lst in oco_wf.items():
        means = [m for m, _ in lst]
        n = sum(k for _, k in lst)
        tot = sum(m * k for m, k in lst) / max(n, 1)
        oco_rows.append({"plan": c, "worst": round(min(means), 4), "mean": round(tot, 4),
                         "pos_share": float(np.mean([m > 0 for m in means])), "n": n, "blocks": means})
    oco_df = pd.DataFrame(oco_rows).sort_values("worst", ascending=False)
    print(oco_df.drop(columns="blocks").to_string(index=False))
    best_oco = oco_df.iloc[0]
    oco_ok = bool(best_oco["mean"] > 0 and best_oco.pos_share >= 0.75 and best_oco.worst > -0.05)
    print(f"OCO: {best_oco.plan} → {'VALIDADO' if oco_ok else 'NÃO validado'}")

    # ------------------------------------------------------------ recalibration (walk-forward OOS only)
    z_all, y_all = np.concatenate(oos["z"]), np.concatenate(oos["y"])
    wp = fit_logreg(z_all[:, None], y_all, 1e-6, iters=50)
    platt = (float(wp[1]), float(wp[0]))
    p_all = 1 / (1 + np.exp(-(platt[0] * z_all + platt[1])))
    dec = pd.DataFrame({"p": p_all, "y": y_all}).groupby(pd.qcut(p_all, 10, labels=False, duplicates="drop")).mean()
    print("calibração (walk-forward): previsto " + " ".join(f"{v:.2f}" for v in dec.p) +
          "\n                           real     " + " ".join(f"{v:.2f}" for v in dec.y))
    exc_all, al_all = np.concatenate(oos["exc"]), np.concatenate(oos["alert"])
    move_q = {"alert_median": round(float(np.median(exc_all[al_all])), 3),
              "alert_p75": round(float(np.quantile(exc_all[al_all], 0.75)), 3),
              "all_median": round(float(np.median(exc_all)), 3),
              "alert_p_ge_075": round(float((exc_all[al_all] >= 0.75).mean()), 3),
              "alert_p_ge_1": round(float((exc_all[al_all] >= 1.0).mean()), 3)}
    print("tamanho do movimento (ADR):", move_q)

    # ------------------------------------------------------------ final fit + untouched test
    trf = df[(df.block < test_b) & (df.time < edges[test_b] - EMBARGO)]
    te = df[df.block == test_b]
    m = fit_gbm(trf, ex.FEATURES, trf.y.to_numpy())
    ms = fit_gbm(trf, SEASONAL, trf.y.to_numpy())
    z_tr = m.decision(X_of(trf.iloc[::3], ex.FEATURES))
    p_tr = 1 / (1 + np.exp(-(platt[0] * z_tr + platt[1])))
    alert_p = float(np.quantile(p_tr, 1 - ALERT_Q))
    levels = [(float(np.quantile(p_tr, q)), lab) for q, lab in LEVEL_Q]
    zt = m.decision(X_of(te, ex.FEATURES))
    pt = 1 / (1 + np.exp(-(platt[0] * zt + platt[1])))
    yt = te.y.to_numpy()
    alert = pt >= alert_p
    test = {"base": round(float(yt.mean()), 4), "auc": round(auc(yt, zt), 4),
            "auc_seas": round(auc(yt, ms.decision(X_of(te, SEASONAL))), 4),
            "n_alert": int(alert.sum()), "prec_alert": round(float(yt[alert].mean()), 4),
            "lift": round(float(yt[alert].mean() / yt.mean()), 2),
            "p_mean_alert": round(float(pt[alert].mean()), 4),
            "move_median_alert": round(float(np.median(te.exc.to_numpy()[alert])), 3),
            "move_median_all": round(float(np.median(te.exc)), 3)}
    zs_tr = ms.decision(X_of(trf.iloc[::3], SEASONAL))
    al_s = ms.decision(X_of(te, SEASONAL)) >= np.quantile(zs_tr, 1 - ALERT_Q)
    test["prec_seasonal_alert"] = round(float(yt[al_s].mean()), 4)          # same filter, hour-of-week only
    for lab_cut, lab in levels:
        sel = pt >= lab_cut
        test[f"prec_{lab}"] = round(float(yt[sel].mean()), 4) if sel.any() else None
    r_oco = bracket_trades(te, alert, best_oco.plan)
    test["oco"] = {"plan": best_oco.plan, "n": int(len(r_oco)), "mean_r": round(float(r_oco.mean()), 4) if len(r_oco) else None,
                   "win": round(float((r_oco > 0).mean()), 4) if len(r_oco) else None}
    # final direction model + test AUC
    ex_tr, ex_te = trf[trf[first].isin([1, -1])], te[te[first].isin([1, -1])]
    Xd = X_of(ex_tr, ex.DIR_FEATURES)
    mu, sd = Xd.mean(0), Xd.std(0)
    sd[sd < 1e-9] = 1.0
    w = fit_logreg((Xd - mu) / sd, (ex_tr[first].to_numpy() == 1).astype(float), 10.0)
    zd = w[0] + ((X_of(ex_te, ex.DIR_FEATURES) - mu) / sd) @ w[1:]
    test["dir_auc"] = round(auc((ex_te[first].to_numpy() == 1).astype(float), zd), 4)
    print(f"TESTE ({te.time.min():%d/%m/%Y} → {te.time.max():%d/%m/%Y}):", test)

    _, e_s, s_s, x_s = best_oco.plan.split("|")
    model = {
        "version": 1, "features": ex.FEATURES, "gbm": m.export(), "platt": list(platt),
        "theta": THETA, "horizon": 4, "alert_p": alert_p, "levels": levels, "move_q": move_q,
        "direction": ({"features": ex.DIR_FEATURES, "mean": mu.tolist(), "std": sd.tolist(),
                       "coef": w[1:].tolist(), "intercept": float(w[0])} if dir_useful else {}),
        "bracket": {"offset_adr": float(e_s), "stop": s_s, "exit": x_s, "validated": oco_ok,
                    "wf_mean_r": float(best_oco["mean"]), "wf_worst_r": float(best_oco.worst),
                    "wf_pos_share": float(best_oco.pos_share)},
        "validated": validated,
        "info": {"trained": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "bars": int(len(df)),
                 "instruments": int(df.symbol.nunique()), "period": f"{t0:%d/%m/%Y} → {t1:%d/%m/%Y}",
                 "test_period": f"{te.time.min():%d/%m/%Y} → {te.time.max():%d/%m/%Y}",
                 "alert_q": ALERT_Q, "walk_forward": wf, "dir_auc_wf": dir_auc, "dir_useful": dir_useful,
                 "calibration": {"pred": [round(float(v), 3) for v in dec.p], "real": [round(float(v), 3) for v in dec.y]},
                 "test": test},
    }
    with open(a.model_out, "w", encoding="utf-8") as fh:
        json.dump(model, fh, ensure_ascii=False)
    with open(a.report, "w", encoding="utf-8") as fh:
        json.dump({"walk_forward": wf, "validated": validated, "direction_auc": dir_auc, "direction_useful": dir_useful,
                   "oco": oco_df.to_dict(orient="records"), "oco_validated": oco_ok, "move": move_q,
                   "test": test}, fh, ensure_ascii=False, indent=1, default=float)
    print(f"modelo → {a.model_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

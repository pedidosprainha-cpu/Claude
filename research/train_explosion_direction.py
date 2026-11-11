"""Direction of a price explosion: which side moves 0.5x ADR first, and is it tradable?

    python3 research/train_explosion_direction.py

Data: research/data/explosion_events.pkl (explosion_replay.py) joined with
research/data/signal_events.pkl (signal_replay.py: R of a market entry in each direction).

Model: gradient-boosted trees on the explosions of the training blocks, label = first side
up, features = signed pressure (returns, range position, trend, currency strength and its
acceleration...) + unsigned context (hour, compression...). Every sample is also used
MIRRORED (signed features negated, label flipped) and predictions are symmetrised, so the
model cannot just learn the drift of the training period.

Pre-registered rules (fixed before looking at any result):
  * same 8 time blocks as the explosion detector; the last block is the test
  * explosion alerts are recomputed out-of-sample in each walk-forward block (same model and
    filter as research/train_explosion_model.py)
  * direction is USEFUL when the AUC on the alerts that exploded averages >= 0.55 over the
    walk-forward blocks and no block is < 0.52
  * a directional market trade on alerts is VALIDATED when mean R > 0, >= 75% of blocks positive
    and worst block > -0.05R (geometry and confidence filter chosen by the worst block)
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
import train_explosion_model as TE  # noqa: E402

from fxengine.analysis import explosion as ex  # noqa: E402

GEOMS = ["s10|tp15", "s15|tp15", "s15|tr10", "s20|tr10", "s20|tp2"]
CONF = (0.0, 0.7)                       # all alerts | only the 30% most confident directions
DIR_PARAM = {"n_trees": 150, "depth": 3, "lr": 0.05, "min_leaf": 400}
FIRST = f"first_{TE.THETA}"


def dir_X(df: pd.DataFrame, mirror: bool = False) -> np.ndarray:
    s = np.nan_to_num(df[ex.DIR_SIGNED].to_numpy(np.float64))
    c = np.nan_to_num(df[ex.DIR_CONTEXT].to_numpy(np.float64))
    return np.hstack([-s if mirror else s, c])


def fit_dir(tr: pd.DataFrame) -> GBM:
    e = tr[tr[FIRST].isin([1, -1])]
    X = np.vstack([dir_X(e), dir_X(e, True)])
    y = np.concatenate([(e[FIRST].to_numpy() == 1), (e[FIRST].to_numpy() == -1)]).astype(float)
    return GBM(**DIR_PARAM).fit(X, y)


def dir_logit(m: GBM, df: pd.DataFrame) -> np.ndarray:
    """Symmetrised logit of P(up first): (z(x) - z(mirror x)) / 2."""
    return (m.decision(dir_X(df)) - m.decision(dir_X(df, True))) / 2


def trades(df: pd.DataFrame, take: np.ndarray, d: np.ndarray, g: str) -> np.ndarray:
    """R of non-overlapping market trades in direction d (one per instrument every 16 h)."""
    out, free = [], {}
    sub = df[take]
    rl, rs = sub[f"L|{g}"].to_numpy(), sub[f"S|{g}"].to_numpy()
    for sym, t, dd, a, b in zip(sub.symbol.to_numpy(), sub.time.to_numpy(), d[take], rl, rs):
        t = pd.Timestamp(t)
        if sym in free and t < free[sym]:
            continue
        free[sym] = t + pd.Timedelta(hours=16)
        r = a if dd > 0 else b
        if np.isfinite(r):
            out.append(float(r))
    return np.array(out)


def block_metrics(va, alert, z, cut) -> dict:
    """Direction quality on the alerts of one block."""
    y_exp = va.y.to_numpy() > 0
    first = va[FIRST].to_numpy()
    pred = np.where(z >= 0, 1, -1)
    conf = np.abs(1 / (1 + np.exp(-z)) - 0.5)
    e_al = alert & np.isin(first, [1, -1])
    hit = alert & (first == pred)                           # moved 0.5 ADR first on the predicted side
    c_al = e_al & (conf >= cut)
    return {"auc_alert": round(auc((first[e_al] == 1).astype(float), z[e_al]), 4) if e_al.sum() > 50 else None,
            "acc_alert": round(float((first[e_al] == pred[e_al]).mean()), 4),
            "acc_conf": round(float((first[c_al] == pred[c_al]).mean()), 4) if c_al.any() else None,
            "n_conf": int(c_al.sum()),
            "hit_pred_side": round(float(hit.sum() / max(alert.sum(), 1)), 4),
            "exploded": round(float(y_exp[alert].mean()), 4)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(ROOT, "research", "data", "explosion_events.pkl"))
    ap.add_argument("--signal", default=os.path.join(ROOT, "research", "data", "signal_events.pkl"))
    ap.add_argument("--model", default=ex.MODEL_PATH)
    ap.add_argument("--report", default=os.path.join(ROOT, "research", "RESULTADOS_EXPLOSAO_DIRECAO.json"))
    a = ap.parse_args()

    df = pd.read_pickle(a.data)
    df["time"] = pd.to_datetime(df.time, utc=True)
    sig = pd.read_pickle(a.signal)
    sig["time"] = pd.to_datetime(sig.time, utc=True)
    keep = ["symbol", "time"] + [f"{s}|{g}" for g in GEOMS for s in ("L", "S")]
    df = df.merge(sig[keep], on=["symbol", "time"], how="left")
    df["y"] = (df.exc >= TE.THETA).astype(float)
    t0, t1 = df.time.min(), df.time.max()
    edges = [t0 + (t1 - t0) * i / 8 for i in range(9)]
    df["block"] = np.clip(np.searchsorted(edges, df.time, side="right") - 1, 0, 7)
    test_b = 7
    print(f"{len(df)} barras · {int(df.y.sum())} explosões · teste {edges[test_b]:%d/%m/%Y} → {t1:%d/%m/%Y}", flush=True)

    wf, oos_z, oos_y = [], [], []
    tr_res = {(g, c): [] for g in GEOMS for c in CONF}
    for b in range(1, test_b):
        tr = df[(df.block < b) & (df.time < edges[b] - TE.EMBARGO)]
        va = df[df.block == b]
        me = TE.fit_gbm(tr, ex.FEATURES, tr.y.to_numpy())
        thr = float(np.quantile(me.decision(TE.X_of(tr.iloc[::5], ex.FEATURES)), 1 - TE.ALERT_Q))
        alert = me.decision(TE.X_of(va, ex.FEATURES)) >= thr
        md = fit_dir(tr)
        e_tr = tr[tr[FIRST].isin([1, -1])]
        z_tr = dir_logit(md, e_tr)
        cut = float(np.quantile(np.abs(1 / (1 + np.exp(-z_tr)) - 0.5), CONF[1]))
        z = dir_logit(md, va)
        row = {"block": b, **block_metrics(va, alert, z, cut)}
        wf.append(row)
        print("  ", row, flush=True)
        e_va = np.isin(va[FIRST].to_numpy(), [1, -1])
        oos_z.append(z[e_va])
        oos_y.append((va[FIRST].to_numpy()[e_va] == 1).astype(float))
        conf = np.abs(1 / (1 + np.exp(-z)) - 0.5)
        d = np.where(z >= 0, 1, -1)
        for g in GEOMS:
            for c in CONF:
                take = alert & (conf >= (cut if c > 0 else -1))
                r = trades(va, take, d, g)
                tr_res[(g, c)].append((float(r.mean()) if len(r) else 0.0, len(r)))

    aucs = [r["auc_alert"] for r in wf if r["auc_alert"] is not None]
    useful = bool(np.mean(aucs) >= 0.55 and min(aucs) >= 0.52)
    print(f"\ndireção nos alertas: AUC {aucs} → média {np.mean(aucs):.3f} → {'ÚTIL' if useful else 'sem poder suficiente'}")
    rows = []
    for (g, c), lst in tr_res.items():
        means = [m for m, _ in lst]
        n = sum(k for _, k in lst)
        rows.append({"geom": g, "conf": c, "worst": round(min(means), 4),
                     "mean": round(sum(m * k for m, k in lst) / max(n, 1), 4),
                     "pos_share": float(np.mean([m > 0 for m in means])), "n": n, "blocks": means})
    res = pd.DataFrame(rows).sort_values("worst", ascending=False)
    print(res.drop(columns="blocks").to_string(index=False))
    best = res.iloc[0]
    trade_ok = bool(best["mean"] > 0 and best.pos_share >= 0.75 and best.worst > -0.05)
    print(f"trade direcional: {best.geom} conf≥{best.conf} → {'VALIDADO' if trade_ok else 'NÃO validado'}")

    # recalibration of P(up first) on walk-forward OOS
    zz, yy = np.concatenate(oos_z), np.concatenate(oos_y)
    wp = fit_logreg(zz[:, None], yy, 1e-6, iters=50)
    platt = (float(wp[1]), 0.0)                       # symmetric by construction: no intercept

    # ------------------------------------------------------------ final fit + untouched test
    trf = df[(df.block < test_b) & (df.time < edges[test_b] - TE.EMBARGO)]
    te = df[df.block == test_b]
    me = TE.fit_gbm(trf, ex.FEATURES, trf.y.to_numpy())
    thr = float(np.quantile(me.decision(TE.X_of(trf.iloc[::3], ex.FEATURES)), 1 - TE.ALERT_Q))
    alert = me.decision(TE.X_of(te, ex.FEATURES)) >= thr
    md = fit_dir(trf)
    e_tr = trf[trf[FIRST].isin([1, -1])]
    z_tr = dir_logit(md, e_tr)
    cut = float(np.quantile(np.abs(1 / (1 + np.exp(-platt[0] * z_tr)) - 0.5), CONF[1]))
    z = platt[0] * dir_logit(md, te)
    test = block_metrics(te, alert, z, cut)
    conf = np.abs(1 / (1 + np.exp(-z)) - 0.5)
    d = np.where(z >= 0, 1, -1)
    r = trades(te, alert & (conf >= (cut if best.conf > 0 else -1)), d, best.geom)
    test["trade"] = {"geom": best.geom, "conf": float(best.conf), "n": int(len(r)),
                     "mean_r": round(float(r.mean()), 4) if len(r) else None,
                     "win": round(float((r > 0).mean()), 4) if len(r) else None}
    print(f"TESTE: {test}")

    m = json.load(open(a.model, encoding="utf-8"))
    m["direction"] = {
        "type": "gbm", "signed": ex.DIR_SIGNED, "context": ex.DIR_CONTEXT, "gbm": md.export(),
        "platt": list(platt), "conf_cut": cut, "useful": useful,
        "trade": {"geom": best.geom, "conf": float(best.conf), "validated": trade_ok,
                  "wf_mean_r": float(best["mean"]), "wf_worst_r": float(best.worst),
                  "wf_pos_share": float(best.pos_share)},
        "wf": wf, "test": test,
        "trained": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    m["info"]["dir_useful"] = useful
    m["info"]["dir_auc_wf"] = aucs
    with open(a.model, "w", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False)
    with open(a.report, "w", encoding="utf-8") as fh:
        json.dump({"walk_forward": wf, "useful": useful, "trades": res.to_dict(orient="records"),
                   "trade_validated": trade_ok, "test": test}, fh, ensure_ascii=False, indent=1, default=float)
    print(f"direção → {a.model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

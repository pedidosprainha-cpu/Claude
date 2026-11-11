"""Train and validate the probability model of the main market-entry signal.

    python3 research/train_signal_model.py            # walk-forward + test, writes the model

Data: research/data/signal_events.pkl (research/signal_replay.py): every closed H1 bar of
32 instruments, features + outcome of a market entry in BOTH directions for 15 geometries.

  1. time is split into N blocks; the LAST block is the test, untouched by every choice
  2. walk-forward on blocks 1..N-2 (expanding window, 3-day embargo before each block):
     a ridge regression of the trade R (spread included) on the oriented features, one per
     geometry, ranks every (bar, direction)
  3. policy: per instrument, at each bar take the direction with the higher predicted R if it
     is in the top q% of the training predictions; no new trade while one is open
  4. geometry + filter q are chosen by the best WORST walk-forward block (robustness), never
     by the average alone; the rule to ship it enabled: mean > 0, >= 75% of blocks positive,
     worst block > -0.05R
  5. the final model is refit on blocks 0..N-2 and the test block is reported once
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

from signal_replay import ALL_EXITS, ALL_STOPS  # noqa: E402
from train_breakout_model import fit_logreg  # noqa: E402

from fxengine.analysis import signal_model as sm  # noqa: E402

DERIVED = ["ext^2", "mr_z^2", "move_today^2", "day_pos^2", "d1_dist^2", "adr_used^2", "ext_slow^2",
           "trend_h1*adx", "trend_h4*adx", "ext*trend_h4", "mr_z*er20", "strength*trend_h4", "ts24*er20",
           "ext*h_asia", "mr_z*h_asia", "move_today*adr_used", "d1_trend*trend_h4", "cost*h_asia",
           "ext*atr_ratio", "rsi_c*adx"]
NAMES = sm.FEATURES + DERIVED
FILTERS = (0.01, 0.02, 0.05, 0.10, 0.25)
LAM = 300.0
EMBARGO = pd.Timedelta(days=3)
GRADE_Q = [(0.995, "A+"), (0.98, "A"), (0.95, "B"), (0.85, "C")]   # share of bars below the cut


def design(df: pd.DataFrame, d: int) -> np.ndarray:
    X = np.zeros((len(df), len(NAMES)), dtype=np.float64)
    base = {}
    for f in sm.FEATURES:
        v = np.nan_to_num(df[f].to_numpy(np.float64))
        base[f] = v * d if f in sm.SIGNED else v
    for j, n in enumerate(NAMES):
        if n.endswith("^2"):
            X[:, j] = base[n[:-2]] ** 2
        elif "*" in n:
            a, b = n.split("*", 1)
            X[:, j] = base[a] * base[b]
        else:
            X[:, j] = base[n]
    return X


class Ridge:
    """Ridge regressions of R on standardised features, one target column per geometry."""

    def fit(self, X: np.ndarray, Y: np.ndarray, lam: float = LAM) -> "Ridge":
        self.mu, self.sd = X.mean(0), X.std(0)
        self.sd[self.sd < 1e-9] = 1.0
        Z = (X - self.mu) / self.sd
        self.ym = Y.mean(0)
        A = Z.T @ Z + lam * np.eye(Z.shape[1])
        self.W = np.linalg.solve(A, Z.T @ (Y - self.ym))
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return ((X - self.mu) / self.sd) @ self.W + self.ym


def targets(df: pd.DataFrame, tag: str, geoms) -> np.ndarray:
    return np.column_stack([df[f"{tag}|{g}"].to_numpy(np.float64) for g in geoms])


def fit_block(tr: pd.DataFrame, geoms) -> Ridge:
    X = np.vstack([design(tr, 1), design(tr, -1)])
    Y = np.vstack([targets(tr, "L", geoms), targets(tr, "S", geoms)])
    return Ridge().fit(X, Y)


def predict_both(m: Ridge, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    return m.predict(design(df, 1)), m.predict(design(df, -1))


class GBMEV:
    """Gradient-boosted P(R > 0) for one geometry; expected R = p * avg win + (1 - p) * avg loss."""

    def __init__(self, g: str, max_rows: int = 300_000, **param):
        self.g, self.max_rows = g, max_rows
        self.param = param or {"n_trees": 150, "depth": 3, "lr": 0.05, "min_leaf": 2000}

    def fit(self, tr: pd.DataFrame) -> "GBMEV":
        from gbm import GBM
        X = np.vstack([design(tr, 1), design(tr, -1)])
        r = np.concatenate([tr[f"L|{self.g}"].to_numpy(), tr[f"S|{self.g}"].to_numpy()]).astype(float)
        step = max(1, len(X) // self.max_rows)
        self.win_r, self.loss_r = float(r[r > 0].mean()), float(r[r <= 0].mean())
        self.m = GBM(**self.param).fit(X[::step], (r[::step] > 0).astype(float))
        return self

    def raw(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """(EV long, EV short, logit long, logit short)."""
        zl, zs = self.m.decision(design(df, 1)), self.m.decision(design(df, -1))
        pl, ps = 1 / (1 + np.exp(-zl)), 1 / (1 + np.exp(-zs))
        return pl * self.win_r + (1 - pl) * self.loss_r, ps * self.win_r + (1 - ps) * self.loss_r, zl, zs

    def ev(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        el, es, _, _ = self.raw(df)
        return el, es


def policy(df: pd.DataFrame, ev_l: np.ndarray, ev_s: np.ndarray, g: str, thr: float) -> pd.DataFrame:
    """Non-overlapping trades per instrument: best direction when its predicted R >= thr."""
    best = np.maximum(ev_l, ev_s)
    d = np.where(ev_l >= ev_s, 1, -1)
    cand = np.flatnonzero(best >= thr)
    if len(cand) == 0:
        return pd.DataFrame(columns=["symbol", "time", "d", "r", "ev"])
    sub = df.iloc[cand]
    r = np.where(d[cand] == 1, sub[f"L|{g}"], sub[f"S|{g}"])
    k = np.where(d[cand] == 1, sub[f"L|{g}|k"], sub[f"S|{g}|k"])
    out = []
    free: dict[str, pd.Timestamp] = {}
    for sym, t, dd, rr, kk, ev in zip(sub.symbol.to_numpy(), sub.time.to_numpy(), d[cand], r, k, best[cand]):
        t = pd.Timestamp(t)
        if sym in free and t < free[sym]:
            continue
        free[sym] = t + pd.Timedelta(hours=int(kk) + 1)
        out.append((sym, t, dd, float(rr), float(ev)))
    return pd.DataFrame(out, columns=["symbol", "time", "d", "r", "ev"])


def baseline_old_plan(te: pd.DataFrame) -> dict:
    """The engine before the model: trend direction + short stop (1 ATR H1) with 50% at 1.5R."""
    d = np.sign(te.trend_h1 + te.trend_h4 + 0.5 * te.d1_trend.fillna(0) + 2 * te.strength).replace(0, 1)
    return stats(policy(te, np.where(d > 0, 1.0, -1.0), np.where(d < 0, 1.0, -1.0), "s10|p15", 0.5))


def stats(tr: pd.DataFrame) -> dict:
    if tr.empty:
        return {"n": 0, "mean_r": 0.0, "win": 0.0, "pf": 0.0, "sum_r": 0.0}
    r = tr.r.to_numpy()
    gl = -r[r < 0].sum()
    return {"n": int(len(r)), "mean_r": round(float(r.mean()), 4), "win": round(float((r > 0).mean()), 4),
            "pf": round(float(r[r > 0].sum() / gl), 3) if gl > 0 else None, "sum_r": round(float(r.sum()), 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(ROOT, "research", "data", "signal_events.pkl"))
    ap.add_argument("--blocks", type=int, default=8)
    ap.add_argument("--min-trades", type=int, default=40, help="per walk-forward block")
    ap.add_argument("--model-out", default=sm.MODEL_PATH)
    ap.add_argument("--report", default=os.path.join(ROOT, "research", "RESULTADOS_SINAL.json"))
    ap.add_argument("--model", choices=("ridge", "gbm"), default="ridge")
    ap.add_argument("--geoms", default="", help="restrict geometries, e.g. s20|tr10,s20|tp15")
    a = ap.parse_args()

    df = pd.read_pickle(a.data)
    df["time"] = pd.to_datetime(df.time, utc=True)
    GEOMS = [c[2:] for c in df.columns if c.startswith("L|") and not c.endswith("|k")]
    if a.geoms:
        GEOMS = [g for g in GEOMS if g in a.geoms.split(",")]
    horizon = int(df["horizon"].iloc[0]) if "horizon" in df else 48
    global EMBARGO
    EMBARGO = pd.Timedelta(days=max(3, int(np.ceil(horizon / 24 * 7 / 5)) + 1))   # labels look `horizon` bars ahead
    t0, t1 = df.time.min(), df.time.max()
    edges = [t0 + (t1 - t0) * i / a.blocks for i in range(a.blocks + 1)]
    df["block"] = np.clip(np.searchsorted(edges, df.time, side="right") - 1, 0, a.blocks - 1)
    test_b = a.blocks - 1
    print(f"{len(df)} barras · blocos de {(t1 - t0).days / a.blocks:.0f} dias · teste = bloco {test_b} "
          f"({edges[test_b]:%d/%m/%Y} → {t1:%d/%m/%Y})", flush=True)

    # ------------------------------------------------------------ walk-forward (blocks 1..N-2)
    wf: dict = {g: {q: [] for q in FILTERS} for g in GEOMS}
    oos_store: dict = {}          # gbm: walk-forward out-of-sample (raw EV, logit, realised R)
    for b in range(1, test_b):
        tr = df[(df.block < b) & (df.time < edges[b] - EMBARGO)]
        va = df[df.block == b]
        if a.model == "gbm":
            ms = [GBMEV(g).fit(tr) for g in GEOMS]
            pr = [mm.ev(tr.iloc[::7]) for mm in ms]
            vr = [mm.raw(va) for mm in ms]
            for gg, x in zip(GEOMS, vr):
                oos_store.setdefault(gg, []).append((x[0], x[2], va[f"L|{gg}"].to_numpy()))
                oos_store[gg].append((x[1], x[3], va[f"S|{gg}"].to_numpy()))
            pl, ps = np.column_stack([x[0] for x in pr]), np.column_stack([x[1] for x in pr])
            vl, vs = np.column_stack([x[0] for x in vr]), np.column_stack([x[1] for x in vr])
        else:
            m = fit_block(tr, GEOMS)
            pl, ps = predict_both(m, tr.iloc[::7])
            vl, vs = predict_both(m, va)
        for j, g in enumerate(GEOMS):
            ref = np.maximum(pl[:, j], ps[:, j])
            for q in FILTERS:
                thr = float(np.quantile(ref, 1 - q))
                wf[g][q].append(stats(policy(va, vl[:, j], vs[:, j], g, thr)))
        print(f"  bloco {b}: treino {len(tr)} barras, validação {len(va)}", flush=True)

    rows = []
    for g in GEOMS:
        for q in FILTERS:
            bl = wf[g][q]
            means = [x["mean_r"] for x in bl]
            ns = [x["n"] for x in bl]
            tot = sum(x["sum_r"] for x in bl) / max(sum(ns), 1)
            rows.append({"geom": g, "q": q, "worst": min(means), "mean": round(tot, 4),
                         "pos_share": float(np.mean([m > 0 for m in means])), "min_n": min(ns),
                         "blocks": means})
    res = pd.DataFrame(rows).sort_values("worst", ascending=False)
    print(res.drop(columns="blocks").head(15).to_string(index=False))
    ok = res[res.min_n >= a.min_trades]
    pick = ok.iloc[0] if len(ok) else res.iloc[0]
    g, q = pick.geom, float(pick.q)
    enabled = bool(pick["mean"] > 0 and pick.pos_share >= 0.75 and pick.worst > -0.05)
    print(f"\nescolha: {g} · top {q * 100:.0f}% · pior bloco {pick.worst:+.3f}R · média {pick['mean']:+.3f}R · "
          f"blocos positivos {pick.pos_share * 100:.0f}% → {'HABILITADO' if enabled else 'NÃO validado'}")

    # ------------------------------------------------------------ recalibration (walk-forward OOS only)
    def fit_both(tr: pd.DataFrame):
        """Ridge expected R + logistic P(R > 0) for geometry g, trained on `tr`."""
        rm = fit_block(tr, [g])
        X = np.vstack([design(tr, 1), design(tr, -1)])
        y = np.concatenate([tr[f"L|{g}"].to_numpy() > 0, tr[f"S|{g}"].to_numpy() > 0]).astype(float)
        mu, sd = X.mean(0), X.std(0)
        sd[sd < 1e-9] = 1.0
        w = fit_logreg((X[::3] - mu) / sd, y[::3], 100.0, iters=30)
        return rm, (mu, sd, w)

    def raw_pred(models, df_: pd.DataFrame, d: int):
        rm, (mu, sd, w) = models
        X = design(df_, d)
        return rm.predict(X)[:, 0], w[0] + ((X - mu) / sd) @ w[1:]

    oos_ev, oos_z, oos_r = [], [], []
    if a.model == "gbm":
        for e_, z_, r_ in oos_store[g]:
            oos_ev.append(e_)
            oos_z.append(z_)
            oos_r.append(r_)
    else:
        for b in range(1, test_b):
            tr = df[(df.block < b) & (df.time < edges[b] - EMBARGO)]
            va = df[df.block == b]
            ms = fit_both(tr)
            for d, tag in ((1, "L"), (-1, "S")):
                e_, z_ = raw_pred(ms, va, d)
                oos_ev.append(e_)
                oos_z.append(z_)
                oos_r.append(va[f"{tag}|{g}"].to_numpy())
    oos_ev, oos_z, oos_r = map(np.concatenate, (oos_ev, oos_z, oos_r))
    b_cal, a_cal = np.polyfit(oos_ev, oos_r, 1)                       # realised R = a + b * raw
    wp = fit_logreg(oos_z[:, None], (oos_r > 0).astype(float), 1e-6, iters=50)
    platt = (float(wp[1]), float(wp[0]))
    dec = pd.DataFrame({"ev": a_cal + b_cal * oos_ev, "r": oos_r}).groupby(pd.qcut(oos_ev, 10, labels=False)).mean()
    print("recalibração (walk-forward fora da amostra): R = %.4f + %.4f × bruto · Platt %s" % (a_cal, b_cal, platt))
    print("  decis: previsto " + " ".join(f"{v:+.3f}" for v in dec.ev) + "\n         realizado " +
          " ".join(f"{v:+.3f}" for v in dec.r))

    # ------------------------------------------------------------ final fit + untouched test
    trf = df[(df.block < test_b) & (df.time < edges[test_b] - EMBARGO)]
    te = df[df.block == test_b]
    if a.model == "gbm":
        gm = GBMEV(g).fit(trf)
        fl, fs = gm.ev(trf.iloc[::3])
        tl, ts_, zl, zs = gm.raw(te)
    else:
        ms = fit_both(trf)
        fl, _ = raw_pred(ms, trf, 1)
        fs, _ = raw_pred(ms, trf, -1)
        tl, zl = raw_pred(ms, te, 1)
        ts_, zs = raw_pred(ms, te, -1)
    ref = np.maximum(fl, fs)
    thr = float(np.quantile(ref, 1 - q))
    test = policy(te, tl, ts_, g, thr)
    base_dir = np.sign(te.trend_h1 + te.trend_h4 + 0.5 * te.d1_trend.fillna(0) + 2 * te.strength).replace(0, 1)
    base = policy(te, np.where(base_dir > 0, 1.0, -1.0), np.where(base_dir < 0, 1.0, -1.0), g, 0.5)
    test_stats, base_stats = stats(test), stats(base)
    old_plan = baseline_old_plan(te)
    print(f"TESTE ({te.time.min():%d/%m/%Y} → {te.time.max():%d/%m/%Y}): modelo {test_stats} | "
          f"tendência ingênua {base_stats}")
    calib = {}
    if not test.empty:
        pos = te.reset_index(drop=True).set_index(["symbol", "time"]).index.get_indexer(list(zip(test.symbol, test.time)))
        zsel = np.where(test.d.to_numpy() == 1, zl[pos], zs[pos])
        p_sel = 1 / (1 + np.exp(-(platt[0] * zsel + platt[1])))
        calib = {"p_mean": round(float(p_sel.mean()), 4), "win_real": round(float((test.r > 0).mean()), 4),
                 "ev_mean": round(float((a_cal + b_cal * test.ev).mean()), 4), "r_real": round(float(test.r.mean()), 4)}
    print("calibração no teste (trades escolhidos):", calib)

    grades = [(float(np.quantile(ref, qq)), gr) for qq, gr in GRADE_Q]
    stop_k = ALL_STOPS[g.split("|")[0]]
    kind, val = ALL_EXITS[g.split("|")[1]]
    model = {
        "version": 2, "features": NAMES, "mtype": a.model,
        "ev_cal": [float(a_cal), float(b_cal)], "platt": list(platt),
        "geometry": {"stop_atr": stop_k, "exit": kind, "val": val, "trail_atr": val if kind == "trail" else None,
                     "horizon": horizon, "key": g},
        "ev_exec": thr, "filter_q": q, "grades": grades, "enabled": enabled, "validated": enabled,
        "info": {"trained": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                 "period": f"{t0:%d/%m/%Y} → {t1:%d/%m/%Y}", "blocks": a.blocks, "bars": int(len(df)),
                 "instruments": int(df.symbol.nunique()),
                 "walk_forward": {"worst": float(pick.worst), "mean": float(pick["mean"]),
                                  "pos_share": float(pick.pos_share), "blocks": list(map(float, pick.blocks))},
                 "deciles": {"pred": [round(float(v), 4) for v in dec.ev], "real": [round(float(v), 4) for v in dec.r]},
                 "test": test_stats, "test_baseline": base_stats, "test_baseline_old_plan": old_plan,
                 "calibration": calib,
                 "test_period": f"{te.time.min():%d/%m/%Y} → {te.time.max():%d/%m/%Y}"},
    }
    if a.model == "gbm":
        model.update({"gbm": gm.m.export(), "win_r": gm.win_r, "loss_r": gm.loss_r})
    else:
        rm, (mu, sd, w) = ms
        model.update({"ev": {"mean": rm.mu.tolist(), "std": rm.sd.tolist(), "coef": rm.W[:, 0].tolist(),
                             "intercept": float(rm.ym[0])},
                      "logit": {"mean": mu.tolist(), "std": sd.tolist(), "coef": w[1:].tolist(),
                                "intercept": float(w[0])}})
    with open(a.model_out, "w", encoding="utf-8") as fh:
        json.dump(model, fh, ensure_ascii=False)
    with open(a.report, "w", encoding="utf-8") as fh:
        json.dump({"walk_forward": res.to_dict(orient="records"), "choice": {"geom": g, "q": q, "enabled": enabled},
                   "test": test_stats, "test_baseline": base_stats, "calibration": calib}, fh,
                  ensure_ascii=False, indent=1, default=float)
    print(f"modelo → {a.model_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

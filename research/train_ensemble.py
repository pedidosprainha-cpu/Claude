"""Can the three models together give a validated directional edge?

    python3 research/train_ensemble.py      # needs research/data/ensemble_oos.pkl (ensemble_oos.py)

Pre-registered (written before the out-of-sample predictions existed):

  policies (direction d, entry at the next bar's open, spread included)
    sinal2        signal model, best side, top 2% (the shipped rule)                 [baseline]
    sinal10       signal model, best side, top 10%
    sinal10+exp   sinal10 AND explosion alert (top 5%)
    exp+dir       explosion alert AND confident explosion direction, d = that direction
    exp+dir+sinal explosion alert AND explosion direction == signal model's best side
    exp+dirc+sinal  same, with a confident explosion direction
  geometries      s20|tr10, s15|tr10, s10|tp15, s15|tp15, s20|tp2
  one trade per instrument every 24 h (no overlapping positions on the same symbol)

  choice: best WORST block over the walk-forward blocks 1..6 (>= 30 trades in every block)
  VALIDATED when mean R > 0, >= 75% of blocks positive and worst block > -0.05R
  block 7 (untouched) is reported once for the chosen policy
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEOMS = ["s20|tr10", "s15|tr10", "s10|tp15", "s15|tp15", "s20|tp2"]
POLICIES = ["sinal2", "sinal10", "sinal10+exp", "exp+dir", "exp+dir+sinal", "exp+dirc+sinal"]
MIN_TRADES = 30


def decide(df: pd.DataFrame, pol: str) -> tuple[np.ndarray, np.ndarray]:
    """(take mask, direction) for every row."""
    best = np.maximum(df.sig_el, df.sig_es).to_numpy()
    d_sig = np.where(df.sig_el >= df.sig_es, 1, -1)
    alert = (df.exp_z >= df.exp_thr5).to_numpy()
    p_up = 1 / (1 + np.exp(-df.dir_z.to_numpy()))
    d_dir = np.where(p_up >= 0.5, 1, -1)
    conf = np.abs(p_up - 0.5) >= df.dir_cut.to_numpy()
    if pol == "sinal2":
        return best >= df.sig_thr2.to_numpy(), d_sig
    if pol == "sinal10":
        return best >= df.sig_thr10.to_numpy(), d_sig
    if pol == "sinal10+exp":
        return (best >= df.sig_thr10.to_numpy()) & alert, d_sig
    if pol == "exp+dir":
        return alert & conf, d_dir
    if pol == "exp+dir+sinal":
        return alert & (d_dir == d_sig), d_dir
    if pol == "exp+dirc+sinal":
        return alert & conf & (d_dir == d_sig), d_dir
    raise ValueError(pol)


def trades(df: pd.DataFrame, take: np.ndarray, d: np.ndarray, g: str) -> np.ndarray:
    sub = df[take]
    out, free = [], {}
    for sym, t, dd, rl, rs in zip(sub.symbol.to_numpy(), sub.time.to_numpy(), d[take],
                                  sub[f"L|{g}"].to_numpy(), sub[f"S|{g}"].to_numpy()):
        t = pd.Timestamp(t)
        if sym in free and t < free[sym]:
            continue
        free[sym] = t + pd.Timedelta(hours=24)
        r = rl if dd > 0 else rs
        if np.isfinite(r):
            out.append(float(r))
    return np.array(out)


def stats(r: np.ndarray) -> dict:
    if len(r) == 0:
        return {"n": 0, "mean_r": None, "win": None}
    return {"n": int(len(r)), "mean_r": round(float(r.mean()), 4), "win": round(float((r > 0).mean()), 4)}


def main() -> int:
    df = pd.read_pickle(os.path.join(ROOT, "research", "data", "ensemble_oos.pkl"))
    rows = []
    for pol in POLICIES:
        for g in GEOMS:
            blocks = []
            for b in range(1, 7):
                v = df[df.block == b]
                take, d = decide(v, pol)
                r = trades(v, take, d, g)
                blocks.append((float(r.mean()) if len(r) else 0.0, len(r)))
            means = [m for m, _ in blocks]
            n = sum(k for _, k in blocks)
            rows.append({"policy": pol, "geom": g, "worst": round(min(means), 4),
                         "mean": round(sum(m * k for m, k in blocks) / max(n, 1), 4),
                         "pos_share": float(np.mean([m > 0 for m in means])),
                         "min_n": min(k for _, k in blocks), "n": n, "blocks": [round(m, 4) for m in means]})
    res = pd.DataFrame(rows).sort_values("worst", ascending=False)
    print(res.drop(columns="blocks").to_string(index=False))
    ok = res[res.min_n >= MIN_TRADES]
    pick = ok.iloc[0]
    validated = bool(pick["mean"] > 0 and pick.pos_share >= 0.75 and pick.worst > -0.05)
    te = df[df.block == 7]
    take, d = decide(te, pick.policy)
    test = stats(trades(te, take, d, pick.geom))
    base_take, base_d = decide(te, "sinal2")
    base = stats(trades(te, base_take, base_d, "s20|tr10"))
    print(f"\nescolha: {pick.policy} · {pick.geom} · pior bloco {pick.worst:+.3f}R · média {pick['mean']:+.3f}R · "
          f"{pick.pos_share * 100:.0f}% blocos positivos → {'VALIDADO' if validated else 'NÃO validado'}")
    print(f"TESTE (bloco 7): {test} | modelo atual (sinal2): {base}")
    rep = {"choice": {"policy": pick.policy, "geom": pick.geom, "validated": validated,
                      "wf_mean_r": float(pick["mean"]), "wf_worst_r": float(pick.worst),
                      "wf_pos_share": float(pick.pos_share), "wf_blocks": pick.blocks},
           "test": test, "test_baseline_sinal2": base, "walk_forward": res.to_dict(orient="records")}
    with open(os.path.join(ROOT, "research", "RESULTADOS_COMBINACAO.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1, default=float)
    return 0


if __name__ == "__main__":
    sys.exit(main())

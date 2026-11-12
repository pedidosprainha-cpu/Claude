"""Out-of-sample predictions of the three models on the SAME time blocks, for combining them.

    python3 research/ensemble_oos.py        # ~40 min → research/data/ensemble_oos.pkl

For every block b = 1..7 the signal model (GBM, research/train_signal_model.py), the explosion
detector (research/train_explosion_model.py) and the explosion-direction model
(research/train_explosion_direction.py) are fitted on the blocks before b (embargo of the
longest label horizon) and predict block b. Block 7 is the untouched test: its predictions
come from models trained on blocks 0..6, exactly like the shipped models. Per-block
thresholds (top-q of the training predictions) are stored too, so policies can be replayed
without refitting anything.
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import train_explosion_direction as TD  # noqa: E402
import train_explosion_model as TE  # noqa: E402
import train_signal_model as TS  # noqa: E402

from fxengine.analysis import explosion as ex  # noqa: E402

SIG_GEOMS = ["s20|tr10", "s15|tr10", "s10|tp15", "s15|tp15", "s20|tp2"]
BLOCKS = 8
EMBARGO = pd.Timedelta(days=4)


def main() -> int:
    t0 = time.time()
    sig = pd.read_pickle(os.path.join(ROOT, "research", "data", "signal_events.pkl"))
    exp = pd.read_pickle(os.path.join(ROOT, "research", "data", "explosion_events.pkl"))
    for d in (sig, exp):
        d["time"] = pd.to_datetime(d.time, utc=True)
        d["key"] = d.symbol + "|" + d.time.astype(str)
    common = set(sig.key) & set(exp.key)
    sig = sig[sig.key.isin(common)].sort_values(["time", "symbol"]).reset_index(drop=True)
    exp = exp[exp.key.isin(common)].sort_values(["time", "symbol"]).reset_index(drop=True)
    assert (sig.key.to_numpy() == exp.key.to_numpy()).all()
    exp["y"] = (exp.exc >= TE.THETA).astype(float)
    t_0, t_1 = sig.time.min(), sig.time.max()
    edges = [t_0 + (t_1 - t_0) * i / BLOCKS for i in range(BLOCKS + 1)]
    block = np.clip(np.searchsorted(edges, sig.time, side="right") - 1, 0, BLOCKS - 1)
    sig["block"] = exp["block"] = block
    print(f"{len(sig)} barras comuns · {t_0:%d/%m/%Y} → {t_1:%d/%m/%Y}", flush=True)

    out = []
    for b in range(1, BLOCKS):
        tr_mask = (block < b) & (sig.time < edges[b] - EMBARGO).to_numpy()
        va_mask = block == b
        str_, sva = sig[tr_mask], sig[va_mask]
        etr, eva = exp[tr_mask], exp[va_mask]
        o = pd.DataFrame({"symbol": sva.symbol.to_numpy(), "time": sva.time.to_numpy(), "block": b})
        # signal model (GBM on the validated geometry s20|tr10)
        gm = TS.GBMEV("s20|tr10").fit(str_)
        fl, fs = gm.ev(str_.iloc[::7])
        o["sig_thr2"] = float(np.quantile(np.maximum(fl, fs), 0.98))
        o["sig_thr10"] = float(np.quantile(np.maximum(fl, fs), 0.90))
        el, es, _, _ = gm.raw(sva)
        o["sig_el"], o["sig_es"] = el, es
        # explosion detector
        me = TE.fit_gbm(etr, ex.FEATURES, etr.y.to_numpy())
        o["exp_thr5"] = float(np.quantile(me.decision(TE.X_of(etr.iloc[::5], ex.FEATURES)), 0.95))
        o["exp_z"] = me.decision(TE.X_of(eva, ex.FEATURES))
        # explosion direction (mirrored GBM)
        md = TD.fit_dir(etr)
        z_tr = TD.dir_logit(md, etr[etr[TD.FIRST].isin([1, -1])])
        o["dir_cut"] = float(np.quantile(np.abs(1 / (1 + np.exp(-z_tr)) - 0.5), 0.7))
        o["dir_z"] = TD.dir_logit(md, eva)
        # outcomes
        for g in SIG_GEOMS:
            o[f"L|{g}"], o[f"S|{g}"] = sva[f"L|{g}"].to_numpy(), sva[f"S|{g}"].to_numpy()
        o["exc"], o["first"] = eva.exc.to_numpy(), eva[TD.FIRST].to_numpy()
        out.append(o)
        print(f"  bloco {b}: {len(o)} barras · {time.time() - t0:.0f} s", flush=True)
    df = pd.concat(out, ignore_index=True)
    df.to_pickle(os.path.join(ROOT, "research", "data", "ensemble_oos.pkl"))
    print(f"ok · {len(df)} previsões fora da amostra · {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

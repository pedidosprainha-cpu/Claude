"""Store the 0.5%-99.5% range of every model input seen in training (blocks 0..6, no labels).

    python3 research/feature_ranges.py

The live engine flags readings whose inputs fall outside these ranges (the model would be
extrapolating) as less reliable (fxengine/data/quality.py: out_of_range)."""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fxengine.analysis import explosion as ex  # noqa: E402
from fxengine.analysis import signal_model as sm  # noqa: E402


def ranges(pkl: str, cols: list[str]) -> dict:
    df = pd.read_pickle(pkl)
    t = pd.to_datetime(df.time, utc=True)
    df = df[t < t.min() + (t.max() - t.min()) * 7 / 8]          # training blocks only
    out = {}
    for c in cols:
        v = df[c].to_numpy(float)
        v = v[np.isfinite(v)]
        if len(v) and np.nanstd(v) > 0:
            out[c] = [float(np.quantile(v, 0.005)), float(np.quantile(v, 0.995))]
    return out


def patch(path: str, rng: dict) -> None:
    with open(path, encoding="utf-8") as fh:
        m = json.load(fh)
    m["feature_ranges"] = rng
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False)
    print(f"{path}: {len(rng)} faixas")


if __name__ == "__main__":
    data = os.path.join(ROOT, "research", "data")
    patch(sm.MODEL_PATH, ranges(os.path.join(data, "signal_events.pkl"), sm.FEATURES))
    cols = list(dict.fromkeys(ex.FEATURES + ex.DIR_SIGNED + ex.DIR_CONTEXT))
    patch(ex.MODEL_PATH, ranges(os.path.join(data, "explosion_events.pkl"), cols))

"""Which candidate (instrument x side) is the best market entry right now?

The ranking model (fxengine/data/ranker_model.json, research/ranking_study.py) scores every
candidate from the out-of-sample outputs of the other models (signal model expected R of
both sides, explosion detector, explosion direction) and, in the "micro -> macro" version,
the macro features of fxengine/analysis/macro_features.py. Without that file (or when the
study did not adopt it) the signal model's expected R is the ranking key - the rule that
was validated as monotone in its deciles.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

import numpy as np

from . import macro_features as mf

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ranker_model.json")


def _gbm_logit(g: dict, x: np.ndarray) -> float:
    z = float(g.get("base", 0.0))
    for nodes in g.get("trees", []):
        i = 0
        while nodes[i][0] >= 0:
            f, thr, li, ri, _ = nodes[i]
            i = li if x[int(f)] <= thr else ri
        z += nodes[i][4]
    return z


@dataclass
class Ranker:
    method: str
    features: list[str]
    gbm: dict
    win_r: float
    loss_r: float
    info: dict

    def score(self, feats: dict) -> tuple[float, float]:
        """(P(trade ends in profit), expected R) of one candidate."""
        x = np.array([float(feats.get(f, 0.0)) for f in self.features], dtype=float)
        p = float(1 / (1 + np.exp(-_gbm_logit(self.gbm, np.where(np.isfinite(x), x, 0.0)))))
        return p, p * self.win_r + (1 - p) * self.loss_r


_CACHE: dict = {}


def load(path: str = MODEL_PATH) -> Ranker | None:
    if path in _CACHE:
        return _CACHE[path]
    r = None
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        r = Ranker(d["method"], d["features"], d["gbm"], float(d["win_r"]), float(d["loss_r"]), d)
    except (OSError, KeyError, ValueError, TypeError):
        r = None
    _CACHE[path] = r
    return r


def candidate(d: int, sig_raw_d: float, sig_raw_o: float, exp_z: float, dir_z: float, macro: dict | None) -> dict:
    """Inputs of one candidate, as built in research/ranking_study.py."""
    p_up = 1 / (1 + np.exp(-dir_z))
    f = {"sig_d": sig_raw_d, "sig_o": sig_raw_o, "sig_gap": sig_raw_d - sig_raw_o, "exp_z": exp_z,
         "dir_d": p_up if d == 1 else 1 - p_up}
    if macro:
        f.update(mf.oriented(macro, d))
    return f

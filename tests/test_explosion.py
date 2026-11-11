import json

import numpy as np
import pytest

from fxengine import app_api
from fxengine.analysis import explosion as ex

from test_signal_model import h1_walk


def test_explosion_features_are_causal():
    h1 = h1_walk(4000, seed=7)
    cols = ex.FEATURES + ex.DIR_FEATURES
    full = ex.feature_frame(h1)
    for cut in (len(h1) // 2, len(h1) * 3 // 4, len(h1) - 3):
        part = ex.feature_frame(h1.iloc[:cut + 1])
        a = full.iloc[cut][cols].fillna(0).to_numpy(float)
        b = part.iloc[-1][cols].fillna(0).to_numpy(float)
        assert np.allclose(a, b, atol=1e-9)


def test_permutation_entropy_bounds():
    h1 = h1_walk(600)
    pe = ex._perm_entropy(h1.c, 24).dropna()
    assert ((pe >= 0) & (pe <= 1.0000001)).all() and pe.mean() > 0.8      # random walk ≈ maximum entropy
    trend = h1.c.copy()
    trend[:] = np.linspace(1, 2, len(trend))
    assert ex._perm_entropy(trend, 24).dropna().max() < 1e-9               # monotone series = one pattern


@pytest.fixture
def model():
    m = ex.load_model()
    if m is None:
        pytest.skip("modelo de explosões não gerado")
    return m


def test_model_probability_and_levels(model):
    ff = ex.feature_frame(h1_walk(3000))
    feats = {k: float(v) for k, v in ff.iloc[-1][ex.FEATURES].items() if np.isfinite(v)}
    p = model.prob(feats)
    assert 0 < p < 1
    assert model.level(1.0) == model.levels[0][1] and model.level(0.0) == "baixa"
    assert model.theta == 0.5 and model.horizon == 4


def test_scan_explosions_offline(tmp_path, model):
    d = json.loads(app_api.scan_explosions(str(tmp_path), offline=True))
    assert d["ok"], d.get("error")
    assert d["scanned"] == 32 and len(d["items"]) == 32
    ps = [it["p"] for it in d["items"]]
    assert ps == sorted(ps, reverse=True) and all(0 < p < 1 for p in ps)
    it = d["items"][0]
    assert it["range_low"] < it["range_high"] and it["move_pips"] > 0
    m = d["model"]
    assert m["available"] and m["bars"] > 100_000 and m["test_precision"] > m["base_rate"]

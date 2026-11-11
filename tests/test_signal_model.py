import json

import numpy as np
import pandas as pd
import pytest

from fxengine.analysis import signal_model as sm
from fxengine.analysis.structure import LevelMap
from fxengine.instruments import get, typical_spread_pips
from fxengine.risk import build_plan


def h1_walk(n: int = 4000, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-06", periods=n, freq="1h", tz="UTC")
    idx = idx[idx.dayofweek < 5][:n]
    c = 1.10 * np.exp(np.cumsum(rng.normal(0, 0.0012, len(idx))))
    o = np.r_[c[0], c[:-1]]
    sp = np.abs(rng.normal(0, 0.0008, len(idx))) * c
    return pd.DataFrame({"o": o, "h": np.maximum(o, c) + sp, "l": np.minimum(o, c) - sp, "c": c,
                         "v": 0.0}, index=idx)


def test_features_are_causal():
    """The value at a bar must not change when later bars are added (no look-ahead)."""
    h1 = h1_walk()
    full = sm.feature_frame(h1, 30.0, 0.0001)
    for cut in (1500, 2500, len(h1) - 5):
        part = sm.feature_frame(h1.iloc[:cut + 1], 30.0, 0.0001)
        a, b = full.iloc[cut][sm.FEATURES], part.iloc[-1][sm.FEATURES]
        assert np.allclose(a.fillna(0).to_numpy(float), b.fillna(0).to_numpy(float), atol=1e-9)


def test_live_window_matches_full_history():
    """evaluate() uses the last 3000 bars only: it must match the full-history value."""
    h1 = h1_walk(5000)
    full = sm.feature_frame(h1, 0.0, 0.0001).iloc[-1][sm.FEATURES].fillna(0).to_numpy(float)
    tail = sm.feature_frame(h1.iloc[-3000:], 0.0, 0.0001).iloc[-1][sm.FEATURES].fillna(0).to_numpy(float)
    assert np.allclose(full, tail, atol=1e-4)


def test_oriented_flips_only_signed_features():
    row = {f: 0.5 for f in sm.FEATURES}
    s = sm.oriented(row, -1)
    assert all(s[f] == -0.5 for f in sm.SIGNED)
    assert all(s[f] == 0.5 for f in sm.UNSIGNED)


def test_closed_bars_drops_forming_bar():
    h1 = h1_walk(100)
    now = h1.index[-1] + pd.Timedelta(minutes=20)        # last bar still forming
    assert sm.closed_bars(h1, now).index[-1] == h1.index[-2]


@pytest.fixture
def shipped_model():
    m = sm.load_model()
    if m is None:
        pytest.skip("modelo do sinal não gerado")
    return m


def test_shipped_model_evaluates(shipped_model):
    h1 = h1_walk()
    inst = get("EURUSD")
    ev = sm.evaluate(shipped_model, h1, 20.0, typical_spread_pips("EURUSD") * inst.pip, False, 1)
    assert ev is not None and 0 < ev.p < 1 and -1.5 < ev.ev_r < 1.5
    assert ev.grade in {"A+", "A", "B", "C", "D"}
    summary = sm.model_summary()
    assert summary["available"] and summary["bars"] > 100_000
    with open(sm.MODEL_PATH, encoding="utf-8") as fh:
        assert len(json.load(fh)["features"]) == len(shipped_model.features)


def test_plan_with_validated_geometry():
    h1 = h1_walk(600)
    inst = get("EURUSD")
    atr_h1 = 0.0010
    geo = {"stop_atr": 2.0, "exit": "trail", "val": 1.0, "trail_atr": 1.0, "horizon": 48}
    p = build_plan(inst, 1, 1.1000, 1.1001, {"H1": h1}, 0.0005, atr_h1, 0.006, LevelMap([], None, None),
                   10_000, 1.0, {"EURUSD": 1.1}, geometry=geo)
    assert abs(p.sl_dist - 2 * atr_h1) < 1e-12 and p.exit_kind == "trail"
    assert abs(p.tp1 - (p.entry + p.sl_dist)) < 1e-12          # +1R activates the trailing stop
    assert p.horizon_h == 48 and "após 48 h" in p.invalidation
    assert abs(p.trail_dist - atr_h1) < 1e-12

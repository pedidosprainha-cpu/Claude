import numpy as np
import pandas as pd
import pytest

from fxengine import explosions as xp
from fxengine.analysis import explosion as ex
from fxengine.config import Settings
from fxengine.data import quality
from fxengine.data.provider import InstrumentData, MarketContext
from fxengine.data.synthetic import SyntheticProvider
from fxengine.instruments import UNIVERSE, get

from test_signal_model import h1_walk


def _now(h1):
    return (h1.index[-1] + pd.Timedelta(hours=1, minutes=5)).to_pydatetime()


def test_clean_data_passes():
    h1 = h1_walk(4000)
    c = quality.check_h1(h1, _now(h1), market_open=True)
    assert c.severity == "ok", c.issues


def test_short_history_blocks():
    h1 = h1_walk(800)
    assert quality.check_h1(h1, _now(h1), True).blocked


def test_stale_candles_block_only_when_market_open():
    h1 = h1_walk(4000)
    later = (h1.index[-1] + pd.Timedelta(hours=6)).to_pydatetime()
    assert quality.check_h1(h1, later, market_open=True).blocked
    assert not quality.check_h1(h1, later, market_open=False).blocked


def test_bad_tick_spike_blocks_if_recent():
    h1 = h1_walk(4000).copy()
    h1.iloc[-1, h1.columns.get_loc("h")] = h1.c.iloc[-1] * 1.08          # absurd last-bar high
    c = quality.check_h1(h1, _now(h1), True)
    assert c.blocked and any("pico" in i for i in c.issues)


def test_quote_checks():
    assert quality.check_quote(1.1002, 1.1000, 1.1001, 0.007, 0.0001).blocked          # crossed
    assert quality.check_quote(1.2000, 1.2001, 1.1000, 0.007, 0.0001).blocked          # far from chart
    c = quality.check_quote(1.1000, 1.1008, 1.1004, 0.007, 0.0001)                     # 8x spread
    assert c.severity == "aviso"


def test_out_of_range_needs_clear_extrapolation():
    rng = {"a": [0.0, 1.0], "b": [-1.0, 1.0]}
    assert quality.out_of_range({"a": 1.1, "b": 0.0}, rng) == []                       # inside the margin
    assert quality.out_of_range({"a": 1.4, "b": 3.0}, rng) == ["a", "b"]


# ------------------------------------------------------------------ live vs replay parity
class HistProvider:
    """Serves synthetic history cut at time T, like the live feed would have looked then."""

    def __init__(self, h1: dict, T):
        self.h1, self.now = h1, T.to_pydatetime()

    def load_instruments(self, targets, now, progress=None, spec=None):
        out = {}
        for inst in targets:
            h = self.h1[inst.symbol]
            h = h[h.index < pd.Timestamp(self.now)]
            px = float(h.c.iloc[-1])
            half = inst.pip
            out[inst.symbol] = InstrumentData(inst, {"H1": h}, px, px - half, px + half, self.now, "hist", True, [])
        return out, {}

    def load_events(self, now):
        return MarketContext(now=now)


@pytest.fixture(scope="module")
def synth_h1():
    prov = SyntheticProvider(Settings(offline=True), days=200)
    now = prov.now if hasattr(prov, "now") else None
    return {s: prov.load_instrument(i, now).frames["H1"] for s, i in UNIVERSE.items()}


def test_explosion_live_matches_replay(synth_h1):
    """Training/serving skew guard: the live scan must compute the replay's features exactly."""
    m = ex.load_model()
    if m is None:
        pytest.skip("modelo de explosões não gerado")
    from research.signal_replay import strength_series
    st = strength_series(synth_h1)
    ref = synth_h1["EURUSD"]
    T = ref.index[-30].floor("h")
    alerts, errors, _ = xp.scan(Settings(), provider=HistProvider(synth_h1, T), model=m)
    assert not errors and len(alerts) == 32
    cols = list(dict.fromkeys(ex.FEATURES + ex.DIR_SIGNED + ex.DIR_CONTEXT))
    for a in alerts[:8]:
        h1 = synth_h1[a.symbol]
        rep = ex.feature_frame(h1, get(a.symbol).is_metal, m.horizon, st[a.symbol])
        row = rep.loc[T - pd.Timedelta(hours=1)]
        for f in cols:
            v = float(row[f])
            if np.isfinite(v):
                assert abs(a.feats.get(f, np.nan) - v) < 2e-3, (a.symbol, f, a.feats.get(f), v)   # 3000-bar live window

import numpy as np
import pandas as pd

from fxintel.data.hub import derive
from fxintel.technical import indicators as ind
from fxintel.technical.mtf import build_frame
from fxintel.technical.smc import smc_frame
from fxintel.technical.structure import market_structure

from .conftest import synthetic_bars


def test_indicator_ranges(bars):
    r = ind.rsi(bars["c"]).dropna()
    assert ((r >= 0) & (r <= 100)).all()
    a = ind.atr(bars).dropna()
    assert (a > 0).all()
    adx, pdi, mdi = ind.adx(bars)
    assert adx.dropna().between(0, 100).all()
    er = ind.efficiency_ratio(bars["c"]).dropna()
    assert er.between(0, 1).all()


def test_vwap_requires_volume(bars):
    assert ind.vwap_session(bars) is None
    b = bars.copy()
    b["v"] = 100.0
    v = ind.vwap_session(b)
    assert v is not None and v.notna().all()


def test_bos_in_uptrend():
    n = 400
    idx = pd.date_range("2025-01-06", periods=n, freq="1h", tz="UTC")
    t = np.arange(n)
    c = 1.0 + 0.0005 * t + 0.01 * np.sin(t / 5)  # tendência de alta com recuos
    df = pd.DataFrame({"o": np.r_[c[0], c[:-1]], "c": c}, index=idx)
    df["h"] = df[["o", "c"]].max(axis=1) + 0.0003
    df["l"] = df[["o", "c"]].min(axis=1) - 0.0003
    st, swings = market_structure(df, ind.atr(df))
    assert (st["event"] == 1).sum() > 3          # BOS de alta recorrentes
    assert st["trend"].iloc[-1] == 1
    assert (st["event"] < 0).sum() <= 1


def test_fvg_detection():
    idx = pd.date_range("2025-01-06", periods=40, freq="1h", tz="UTC")
    c = np.full(40, 1.0)
    df = pd.DataFrame({"o": c, "h": c + 0.001, "l": c - 0.001, "c": c}, index=idx)
    # candle 30 com gap: mínima acima da máxima do candle 28
    df.iloc[29] = [1.0, 1.006, 0.999, 1.005]
    df.iloc[30] = [1.005, 1.008, 1.004, 1.007]
    a = pd.Series(0.002, index=idx)
    st = pd.DataFrame({"event": np.zeros(40, dtype=int)}, index=idx)
    f = smc_frame(df, a, st, min_fvg_atr=0.1)
    assert f["new_fvg"].iloc[30] == 1


def test_frame_is_causal():
    """Recalcular com dados truncados deve reproduzir exatamente as linhas passadas (sem look-ahead)."""
    h1 = synthetic_bars(2500, seed=3)
    F, _ = build_frame(h1, derive(h1, "H4"), derive(h1, "D1"))
    cut = h1.index[-300]
    h1c = h1[h1.index <= cut]
    F2, _ = build_frame(h1c, derive(h1c, "H4"), derive(h1c, "D1"))
    a, b = F.loc[cut], F2.loc[cut]
    cols = [c for c in F.columns if np.issubdtype(F[c].dtype, np.number)]
    diff = [c for c in cols if not np.isclose(a[c], b[c], equal_nan=True)]
    assert diff == [], f"colunas com vazamento de informação futura: {diff}"

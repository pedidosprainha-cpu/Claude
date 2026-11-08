from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from fxengine import sessions
from fxengine.analysis import edge, indicators as ta, quant, strength
from fxengine.analysis.fundamental import headline_sentiment
from fxengine.analysis.structure import cluster_levels, market_structure, swings
from fxengine.data import swissquote, yahoo
from fxengine.data.provider import inject_live
from fxengine.instruments import FX_PAIRS, UNIVERSE, get
from fxengine.risk import build_plan, conversion_to_usd
from fxengine.analysis.structure import LevelMap


def frame(close, spread=0.0005, start="2026-01-05", freq="1h"):
    c = np.asarray(close, dtype=float)
    o = np.concatenate([[c[0]], c[:-1]])
    idx = pd.date_range(start, periods=len(c), freq=freq, tz="UTC")
    return pd.DataFrame({"o": o, "h": np.maximum(o, c) + spread, "l": np.minimum(o, c) - spread,
                         "c": c, "v": 0.0}, index=idx)


# ------------------------------------------------------------------ instruments
def test_universe_has_28_fx_and_4_metals():
    assert len(FX_PAIRS) == 28
    assert {"XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD"} <= set(UNIVERSE)
    assert get("eur/usd").pip == 0.0001 and get("USDJPY").pip == 0.01
    with pytest.raises(KeyError):
        get("FOOBAR")


# ------------------------------------------------------------------ indicators
def test_rsi_extremes():
    up = pd.Series(np.arange(1, 60, dtype=float))
    assert ta.rsi(up).iloc[-1] == pytest.approx(100.0)
    flat = pd.Series(np.ones(60))
    assert ta.rsi(flat).iloc[-1] == pytest.approx(50.0)


def test_atr_constant_range():
    df = frame(np.full(100, 1.1), spread=0.001)
    assert ta.atr(df).iloc[-1] == pytest.approx(0.002, rel=1e-6)


def test_supertrend_follows_trend():
    up = frame(np.linspace(1.0, 1.2, 200))
    dn = frame(np.linspace(1.2, 1.0, 200))
    assert ta.supertrend(up).iloc[-1] == 1
    assert ta.supertrend(dn).iloc[-1] == -1


def test_ny_daily_merges_sunday_into_monday():
    # Sunday 22:00 UTC (17:00 NY, EST) through Monday
    idx = pd.date_range("2026-11-08 22:00", periods=10, freq="1h", tz="UTC")
    df = pd.DataFrame({"o": 1.0, "h": 1.01, "l": 0.99, "c": 1.0}, index=idx)
    d = ta.ny_daily(df)
    assert len(d) == 1 and d.index[0].dayofweek == 0


# ------------------------------------------------------------------ structure
def test_swings_and_structure_uptrend():
    x = np.linspace(0, 6 * np.pi, 300)
    c = 1.0 + 0.0005 * np.arange(300) + 0.01 * np.sin(x)
    df = frame(c, spread=0.0001)
    sw = swings(df, 3)
    assert any(s.kind == "H" for s in sw) and any(s.kind == "L" for s in sw)
    # no swing may be confirmed inside the last k bars (no look-ahead)
    assert all(s.i <= len(df) - 1 - 3 for s in sw)
    assert market_structure(df).trend == 1


def test_cluster_levels_merges_close_points():
    raw = [(1.1000, 2.0, "a"), (1.1003, 2.0, "b"), (1.1100, 3.0, "c")]
    lv = cluster_levels(raw, tol=0.0005, min_strength=0)
    assert len(lv) == 2
    assert lv[0].price == pytest.approx(1.10015, abs=1e-6)


# ------------------------------------------------------------------ quant
def test_hurst_distinguishes_regimes():
    rng = np.random.default_rng(1)
    rw = np.cumsum(rng.normal(0, 1, 6000))
    ou = np.zeros(6000)
    for i in range(1, 6000):
        ou[i] = 0.5 * ou[i - 1] + rng.normal()
    assert 0.4 < quant.hurst(rw) < 0.6
    assert quant.hurst(ou) < 0.3
    vr, _ = quant.variance_ratio(ou, 4)
    assert vr < 1


# ------------------------------------------------------------------ strength
def test_strength_meter_recovers_planted_leader():
    rng = np.random.default_rng(3)
    n = 800
    paths = {c: np.cumsum(rng.normal(0, 3e-4, n)) for c in "EUR GBP AUD NZD USD CAD CHF JPY".split()}
    paths["AUD"] += np.linspace(0, 0.3, n)
    paths["JPY"] -= np.linspace(0, 0.3, n)
    frames = {p.symbol: frame(np.exp(paths[p.base] - paths[p.quote])) for p in FX_PAIRS}
    res = strength.compute(frames)
    assert res.ranking[0][0] == "AUD" and res.ranking[-1][0] == "JPY"
    assert res.pair_score("AUD", "JPY") > 50 > -50 > res.pair_score("JPY", "AUD")


# ------------------------------------------------------------------ edge
def test_edge_random_walk_matches_theory():
    rng = np.random.default_rng(11)
    c = 1.1 * np.exp(np.cumsum(rng.normal(0, 0.001, 9000)))
    df = frame(c, spread=0.0003)
    import fxengine.analysis.edge as em
    orig = em.core_signal
    try:
        em.core_signal = lambda d: orig(d).assign(core=1.0, ext=0.0)
        r = edge.evaluate(df, 1, sl_atr=1.5, tp_atr=1.5, spread=0.0, max_hold=200)
    finally:
        em.core_signal = orig
    assert r.n > 200
    assert r.win_rate == pytest.approx(0.5, abs=0.07)       # symmetric barriers on a random walk


def test_edge_detects_trend():
    c = 1.1 + np.arange(4000) * 0.0002 + 0.0004 * np.sin(np.arange(4000) / 3)
    r = edge.evaluate(frame(c, spread=0.0002), 1, 1.5, 1.5, spread=0.0)
    assert r.win_rate > 0.8 and r.exp_post_r > 0.3


# ------------------------------------------------------------------ risk
def test_position_sizing_eurusd_and_jpy_cross():
    prices = {"EURUSD": 1.10, "USDJPY": 150.0}
    assert conversion_to_usd("JPY", prices) == pytest.approx(1 / 150)
    inst = get("EURUSD")
    df = frame(np.full(300, 1.1))
    lm = LevelMap([], None, None)
    p = build_plan(inst, 1, 1.0999, 1.1000, {"M15": df, "H1": df}, atr_m15=0.0010, atr_h1=0.0020,
                   atr_d1=0.0070, levels=lm, balance=10_000, risk_pct=1.0, prices=prices)
    assert p.sl < p.entry < p.tp1 < p.tp2
    assert p.rr1 >= 1.0
    # $100 risk / (sl_pips * $10 per pip per lot)
    assert p.lots == pytest.approx(np.floor(100 / (p.sl_pips * 10) * 100) / 100)
    s = build_plan(get("EURJPY"), -1, 165.00, 165.02, {"M15": df * 150, "H1": df * 150}, 0.15, 0.30, 1.0,
                   lm, 10_000, 1.0, prices)
    assert s.tp2 < s.tp1 < s.entry < s.sl
    assert s.pip_value_lot == pytest.approx(1000 / 150)


# ------------------------------------------------------------------ data parsing
def test_swissquote_parser_picks_latest_server():
    d = [{"ts": 1000, "spreadProfilePrices": [{"spreadProfile": "premium", "bid": 1.1, "ask": 1.1002}]},
         {"ts": 2000, "spreadProfilePrices": [{"spreadProfile": "prime", "bid": 1.2, "ask": 1.2001}]}]
    q = swissquote.parse(d)
    assert q.bid == 1.2 and q.mid == pytest.approx(1.20005)


def test_yahoo_parser_drops_nulls():
    d = {"chart": {"result": [{"meta": {"symbol": "X"}, "timestamp": [0, 60, 120],
                               "indicators": {"quote": [{"open": [1, None, 1.2], "high": [1.1, None, 1.3],
                                                         "low": [0.9, None, 1.1], "close": [1.0, None, 1.25],
                                                         "volume": [0, 0, 0]}]}}]}}
    df, meta = yahoo.parse_chart(d)
    assert len(df) == 2 and df.c.iloc[-1] == 1.25


def test_inject_live_updates_or_appends():
    df = frame([1.0, 1.1], freq="5min", start="2026-11-09 10:00")
    up = inject_live(df, datetime(2026, 11, 9, 10, 7, tzinfo=timezone.utc), 1.2, "5min")
    assert len(up) == 2 and up.c.iloc[-1] == 1.2 and up.h.iloc[-1] >= 1.2
    new = inject_live(df, datetime(2026, 11, 9, 10, 12, tzinfo=timezone.utc), 1.05, "5min")
    assert len(new) == 3 and new.o.iloc[-1] == 1.05


def test_headline_sentiment():
    assert headline_sentiment("Dollar sees best day since June after stellar jobs report") == {"USD": 1.0}
    assert headline_sentiment("Yen slides as BOJ keeps policy unchanged")["JPY"] == -1.0
    assert "USD" not in headline_sentiment("Australian dollar rallies")


# ------------------------------------------------------------------ sessions
def test_sessions_open_close():
    sat = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
    sun_open = datetime(2026, 11, 8, 22, 30, tzinfo=timezone.utc)      # 17:30 NY
    wed = datetime(2026, 11, 4, 14, 0, tzinfo=timezone.utc)
    assert not sessions.fx_open(sat)
    assert sessions.fx_open(sun_open) and not sessions.metals_open(sun_open)
    st = sessions.state(wed)
    assert "Londres" in st.active and "Nova York" in st.active
    assert sessions.liquidity_factor(st, "EUR", "USD", False)[0] == 1.0

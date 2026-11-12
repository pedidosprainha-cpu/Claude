"""Probability of a price explosion (a large move in the next hours) before it happens.

Volatility is far more predictable than direction: it clusters (GARCH / HAR-RV), compressed
ranges tend to expand, and activity follows the hour of the week. `feature_frame` measures
these on every *closed* H1 bar; the historical replay (research/explosion_replay.py) and the
live scan call this same function, so the model sees identical inputs in both.

Features (all causal):
  realised volatility   HAR components (4h / 24h / 120h) of close-to-close, Parkinson and
                        Garman-Klass variance, EWMA (RiskMetrics) short/long ratio, ATR ratio
  compression           Bollinger width percentile, Bollinger-inside-Keltner squeeze and its
                        length, NR7 / narrow-range count, 4/12/24-bar range in ADR units
  complexity / jumps    permutation entropy (order 3), bipower-variation jump share, kurtosis
  seasonality           typical activity of the coming 4 hours of the week (trailing weeks)
  context               ADR used today, distance to prior-day / prior-week extremes, trend
                        efficiency, time of day

Target (research): the price moves at least `theta` x ADR away from the decision close, in
either direction, within the next `horizon` H1 bars.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import indicators as ta

FEATURES = ["rv4", "rv24", "rv120", "pk24", "gk24", "ewm_ratio", "atr_ratio", "bbw_pct", "squeeze", "sq_len",
            "rng4", "rng12", "rng24", "nr7", "nr_cnt", "pe24", "jump24", "kurt120", "seas_fwd", "seas_now",
            "seas_ratio", "h_sin", "h_cos", "dow_mon", "dow_fri", "adr_used", "dist_pd", "dist_pw", "er20",
            "abs_ts24", "abs_ts120", "is_metal"]
# signed features (positive = pressure upwards), used by the direction model
DIR_FEATURES = ["cl24", "ts24", "ts120", "slope50", "rsi_c", "day_pos", "move_today", "d1_trend"]
# direction model v2: signed pressure (flipped when a sample is mirrored) + unsigned context
DIR_SIGNED = DIR_FEATURES + ["ret1", "ret4", "cl12", "ext21", "near_pdh", "near_pdl", "strength", "dstr4", "dstr24"]
DIR_CONTEXT = ["h_sin", "h_cos", "dow_mon", "dow_fri", "adr_used", "rng24", "bbw_pct", "atr_ratio", "ewm_ratio",
               "er20", "is_metal"]
WARMUP_BARS = 1200
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "explosion_model.json")


def _clip(s, lo, hi):
    return s.replace([np.inf, -np.inf], np.nan).clip(lo, hi)


def _daily_context(h1: pd.DataFrame) -> pd.DataFrame:
    """Per-bar ADR (14-day ATR of completed NY days) and prior-day / prior-week extremes."""
    ny = h1.index.tz_convert("America/New_York")
    day = pd.Index((ny + pd.Timedelta(hours=7)).normalize().tz_localize(None))
    g = h1.groupby(day)
    daily = pd.DataFrame({"o": g.o.first(), "h": g.h.max(), "l": g.l.min(), "c": g.c.last()})
    daily = daily[daily.index.dayofweek < 5]
    wk = daily.index.to_period("W-FRI")
    wh, wl = daily.h.groupby(wk).max(), daily.l.groupby(wk).min()
    prev = pd.DataFrame({"adr": ta.atr(daily).shift(1), "pdh": daily.h.shift(1), "pdl": daily.l.shift(1),
                         "pwh": pd.Series(wk.map(wh.shift(1)), index=daily.index),
                         "pwl": pd.Series(wk.map(wl.shift(1)), index=daily.index)}, index=daily.index)
    p = prev.reindex(day)
    p.index = h1.index
    p["run_h"], p["run_l"], p["d_open"] = g.h.cummax(), g.l.cummin(), g.o.transform("first")
    return p


def _perm_entropy(c: pd.Series, n: int = 24) -> pd.Series:
    """Normalised permutation entropy (order 3) of the last n closes: 1 = pure noise."""
    a, b, d = c.shift(2).to_numpy(), c.shift(1).to_numpy(), c.to_numpy()
    pid = np.select([(a <= b) & (b <= d), (a <= d) & (d < b), (d < a) & (a <= b),
                     (b < a) & (a <= d), (b <= d) & (d < a)], [0, 1, 2, 3, 4], 5)
    pid = np.where(np.isnan(a) | np.isnan(d), -1, pid)
    onehot = pd.DataFrame({k: (pid == k).astype(float) for k in range(6)}, index=c.index)
    cnt = onehot.rolling(n, min_periods=n // 2).sum()
    p = cnt.div(cnt.sum(axis=1), axis=0)
    h = -(p * np.log(p.where(p > 0))).sum(axis=1, min_count=1)
    return h / np.log(6)


def feature_frame(h1: pd.DataFrame, is_metal: bool = False, horizon: int = 4, strength=None,
                  strength_hist: dict | None = None) -> pd.DataFrame:
    """strength: pair score -100..100 as a Series aligned to h1 (replay) or a scalar (live, last bar);
    strength_hist: live only, {"4": score 4 bars ago, "24": score 24 bars ago}."""
    with np.errstate(divide="ignore", invalid="ignore"):      # log(0) / x/0 become NaN or are clipped
        return _feature_frame(h1, is_metal, horizon, strength, strength_hist or {})


def _feature_frame(h1: pd.DataFrame, is_metal: bool, horizon: int, strength=None,
                   strength_hist: dict | None = None) -> pd.DataFrame:
    c, h, l, o = h1.c, h1.h, h1.l, h1.o
    out = pd.DataFrame(index=h1.index)
    dc = _daily_context(h1)
    adr = dc.adr.where(dc.adr > 0)
    adr_l = adr / c                                      # ADR in log-return units
    r = np.log(c).diff()
    a = ta.atr(h1)

    # ---- realised volatility (HAR components) in ADR units
    for n in (4, 24, 120):
        out[f"rv{n}"] = _clip(np.log(np.sqrt((r ** 2).rolling(n, min_periods=n // 2).mean()) / adr_l), -6, 3)
    pk = np.log(h / l) ** 2 / (4 * np.log(2))
    gk = 0.5 * np.log(h / l) ** 2 - (2 * np.log(2) - 1) * np.log(c / o) ** 2
    out["pk24"] = _clip(np.log(np.sqrt(pk.rolling(24, min_periods=12).mean()) / adr_l), -6, 3)
    out["gk24"] = _clip(np.log(np.sqrt(gk.clip(lower=0).rolling(24, min_periods=12).mean()) / adr_l), -6, 3)
    ew_s = (r ** 2).ewm(alpha=0.06, adjust=False).mean()
    ew_l = (r ** 2).ewm(alpha=0.005, adjust=False).mean()
    out["ewm_ratio"] = _clip(np.log(np.sqrt(ew_s / ew_l)), -2, 2)
    out["atr_ratio"] = _clip(np.log(ta.atr(h1, 5) / ta.atr(h1, 50)), -2, 2)

    # ---- compression
    sd20 = c.rolling(20).std(ddof=0)
    bbw = 4 * sd20 / c.rolling(20).mean()
    out["bbw_pct"] = bbw.rolling(500, min_periods=100).rank(pct=True)
    kel = 1.5 * ta.atr(h1, 20)
    sq = (2 * sd20 < kel).astype(float)
    out["squeeze"] = sq
    grp = (sq != sq.shift()).cumsum()
    out["sq_len"] = (sq.groupby(grp).cumcount() + 1).where(sq > 0, 0).clip(0, 48) / 48
    for n in (4, 12, 24):
        out[f"rng{n}"] = _clip((h.rolling(n).max() - l.rolling(n).min()) / adr, 0, 4)
    bar_rng = h - l
    out["nr7"] = (bar_rng <= bar_rng.rolling(7).min()).astype(float)
    out["nr_cnt"] = out.nr7.rolling(6).sum() / 6

    # ---- complexity / jumps / tails
    out["pe24"] = _perm_entropy(c, 24)
    bv = (np.pi / 2) * (r.abs() * r.abs().shift()).rolling(24, min_periods=12).sum()
    rv = (r ** 2).rolling(24, min_periods=12).sum()
    out["jump24"] = _clip((rv - bv) / rv, 0, 1)
    out["kurt120"] = _clip(r.rolling(120, min_periods=60).kurt(), -2, 30) / 10

    # ---- seasonality: typical activity of the next `horizon` hours of the week (past weeks only)
    s = (bar_rng / adr)
    how = h1.index.dayofweek * 24 + h1.index.hour
    prof = s.groupby(how).transform(lambda x: x.rolling(6, min_periods=2).mean())
    prof = prof[~prof.index.duplicated()]
    fwd = pd.Series(0.0, index=h1.index)
    for k in range(1, horizon + 1):
        look = h1.index + pd.Timedelta(hours=k) - pd.Timedelta(days=7)
        fwd += prof.reindex(look, method="ffill").fillna(0).to_numpy()
    out["seas_fwd"] = _clip(fwd, 0, 5)
    out["seas_now"] = _clip(prof.reindex(h1.index), 0, 2)
    recent = s.rolling(24, min_periods=12).mean() * horizon
    out["seas_ratio"] = _clip(np.log(fwd / recent), -2, 2)

    # ---- time and daily context
    t = h1.index + pd.Timedelta(hours=1)
    hour = np.asarray(t.hour, dtype=float)
    out["h_sin"], out["h_cos"] = np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24)
    out["dow_mon"] = (t.dayofweek == 0).astype(float)
    out["dow_fri"] = (t.dayofweek == 4).astype(float)
    rng_today = dc.run_h - dc.run_l
    out["adr_used"] = _clip(rng_today / adr, 0, 3)
    out["dist_pd"] = _clip(np.minimum((c - dc.pdh).abs(), (c - dc.pdl).abs()) / adr, 0, 3)
    out["dist_pw"] = _clip(np.minimum((c - dc.pwh).abs(), (c - dc.pwl).abs()) / adr, 0, 5)
    out["er20"] = ta.efficiency_ratio(c, 20)
    lr = np.log(c)
    sig = r.rolling(750, min_periods=200).std()
    ts24 = _clip((lr - lr.shift(24)) / (sig * np.sqrt(24)), -4, 4)
    ts120 = _clip((lr - lr.shift(120)) / (sig * np.sqrt(120)), -4, 4)
    out["abs_ts24"], out["abs_ts120"] = ts24.abs(), ts120.abs()
    out["is_metal"] = float(is_metal)

    # ---- direction pressure (signed)
    hi24, lo24 = h.rolling(24).max(), l.rolling(24).min()
    out["cl24"] = _clip(2 * (c - lo24) / (hi24 - lo24) - 1, -1, 1)
    out["ts24"], out["ts120"] = ts24 / 2, ts120 / 2
    e50 = ta.ema(c, 50)
    out["slope50"] = np.tanh((e50 - e50.shift(5)) / (5 * a) * 4)
    out["rsi_c"] = ((ta.rsi(c) - 50) / 20).clip(-1, 1)
    out["day_pos"] = _clip((c - (dc.run_h + dc.run_l) / 2) / (rng_today / 2).replace(0, np.nan), -1.5, 1.5)
    out["move_today"] = _clip((c - dc.d_open) / adr, -3, 3)
    ema_d = c.ewm(span=20 * 24, adjust=False).mean()
    out["d1_trend"] = _clip((ema_d - ema_d.shift(120)) / adr, -3, 3)

    out["ret1"] = _clip((c - c.shift(1)) / adr, -1, 1)
    out["ret4"] = _clip((c - c.shift(4)) / adr, -2, 2)
    hi12, lo12 = h.rolling(12).max(), l.rolling(12).min()
    out["cl12"] = _clip(2 * (c - lo12) / (hi12 - lo12) - 1, -1, 1)
    out["ext21"] = _clip((c - ta.ema(c, 21)) / a, -5, 5) / 2
    out["near_pdh"] = _clip((c - dc.pdh) / adr, -2, 2)
    out["near_pdl"] = _clip((c - dc.pdl) / adr, -2, 2)
    # cross-sectional currency strength and its acceleration (flows between currencies)
    if isinstance(strength, pd.Series):
        st = strength.reindex(h1.index).ffill().fillna(0.0) / 100
        out["strength"], out["dstr4"], out["dstr24"] = st, (st - st.shift(4)).fillna(0), (st - st.shift(24)).fillna(0)
    else:
        now = float(strength or 0.0) / 100
        hist = strength_hist or {}
        out["strength"] = now
        out["dstr4"] = now - float(hist.get("4", strength or 0.0)) / 100
        out["dstr24"] = now - float(hist.get("24", strength or 0.0)) / 100

    out["adr"], out["atr"] = adr, a
    return out.replace([np.inf, -np.inf], np.nan)


# ---------------------------------------------------------------------------- model
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
class ExplosionModel:
    features: list[str]
    gbm: dict                        # P(explosion) trees (logit)
    platt: tuple                     # calibrated p = sigmoid(a * z + b)
    theta: float                     # explosion = move >= theta x ADR ...
    horizon: int                     # ... within this many H1 bars
    alert_p: float                   # calibrated probability for an alert (validation filter)
    levels: list                     # [(min p, label)], strongest first
    move_q: dict                     # typical size of the move by alert level (ADR units)
    direction: dict                  # {"features", "mean", "std", "coef", "intercept", "useful"}
    bracket: dict                    # validated OCO plan (or {} if none)
    validated: bool
    info: dict = field(default_factory=dict)

    def prob(self, feats: dict) -> float:
        x = np.array([float(feats.get(f, 0.0)) for f in self.features], dtype=float)
        x = np.where(np.isfinite(x), x, 0.0)
        a, b = self.platt
        return float(1 / (1 + np.exp(-(a * _gbm_logit(self.gbm, x) + b))))

    def p_up(self, feats: dict) -> float:
        d = self.direction
        if not d:
            return 0.5
        if d.get("type") == "gbm":
            sv = np.array([float(feats.get(f, 0.0)) for f in d["signed"]], dtype=float)
            cv = np.array([float(feats.get(f, 0.0)) for f in d["context"]], dtype=float)
            sv, cv = np.where(np.isfinite(sv), sv, 0.0), np.where(np.isfinite(cv), cv, 0.0)
            z = (_gbm_logit(d["gbm"], np.r_[sv, cv]) - _gbm_logit(d["gbm"], np.r_[-sv, cv])) / 2   # symmetrised
            a, b = d.get("platt", (1.0, 0.0))
            return float(1 / (1 + np.exp(-(a * z + b))))
        x = np.array([float(feats.get(f, 0.0)) for f in d["features"]], dtype=float)
        x = np.where(np.isfinite(x), x, 0.0)
        z = ((x - np.asarray(d["mean"])) / np.asarray(d["std"])) @ np.asarray(d["coef"]) + d["intercept"]
        return float(1 / (1 + np.exp(-z)))

    @property
    def direction_useful(self) -> bool:
        return bool(self.direction.get("useful", False))

    def direction_confident(self, p_up: float) -> bool:
        return abs(p_up - 0.5) >= float(self.direction.get("conf_cut", 0.5))

    def level(self, p: float) -> str:
        for cut, lab in self.levels:
            if p >= cut:
                return lab
        return "baixa"


_CACHE: dict = {}


def load_model(path: str = MODEL_PATH) -> ExplosionModel | None:
    if path in _CACHE:
        return _CACHE[path]
    m = None
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        m = ExplosionModel(d["features"], d["gbm"], tuple(d["platt"]), float(d["theta"]), int(d["horizon"]),
                           float(d["alert_p"]), [tuple(x) for x in d["levels"]], d.get("move_q", {}),
                           d.get("direction", {}), d.get("bracket", {}), bool(d.get("validated", False)),
                           d.get("info", {}))
        m.info["feature_ranges"] = d.get("feature_ranges", {})
    except (OSError, KeyError, ValueError, TypeError):
        m = None
    _CACHE[path] = m
    return m

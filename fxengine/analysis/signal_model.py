"""Calibrated probability for the main market-entry signal.

`feature_frame` computes, for every *closed* H1 bar, causal features of trend, momentum,
extension, regime, currency strength, daily range and time of day. The historical replay
(research/signal_replay.py) and the live engine call this same function, so the model sees
identical inputs in both. Signed features are oriented by the trade direction before the
model is applied (positive = in favour of the trade).

The model file (fxengine/data/signal_model.json) is written by research/train_signal_model.py:
a logistic or gradient-boosted model of P(trade ends in profit) for one validated trade
geometry (stop in ATR H1, exit rule), recalibrated, with the walk-forward and test results.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import indicators as ta

SIGNED = ["trend_h1", "mom_h1", "trend_h4", "di", "ext", "ext_slow", "mr_z", "ts24", "ts120", "ts480",
          "strength", "move_today", "day_pos", "d1_trend", "d1_dist", "w1_pos", "rsi_c"]
UNSIGNED = ["adx", "er20", "er120", "atr_ratio", "cost", "adr_used", "h_sin", "h_cos", "h_london", "h_ny",
            "h_asia", "dow_mon", "dow_fri", "is_metal"]
FEATURES = SIGNED + UNSIGNED
WARMUP_BARS = 1200          # H1 bars needed before the features are stable (EMA 200, 750-bar vol, D1 ATR)

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "signal_model.json")


def _clip(s, lo, hi):
    v = np.asarray(s, dtype=float)
    with np.errstate(invalid="ignore"):
        v = np.clip(np.where(np.isfinite(v), v, np.nan), lo, hi)      # inf -> NaN, then clip (NaN stays)
    return pd.Series(v, index=s.index)


def feature_frame(h1: pd.DataFrame, strength=None, spread: float = 0.0, is_metal: bool = False) -> pd.DataFrame:
    """Signed (direction-free) features for every bar of `h1` (closed bars only).

    strength: pair score -100..100 as a Series aligned to h1 (replay) or a scalar (live).
    spread: typical spread in price units (the model was trained with a fixed table)."""
    c = h1.c
    a = ta.atr(h1)
    out = pd.DataFrame(index=h1.index)

    # ---- H1 trend / momentum (same ingredients as the technical layer)
    e8, e21, e50, e200 = (ta.ema(c, n) for n in (8, 21, 50, 200))
    stack = (np.sign(e8 - e21) + np.sign(e21 - e50)) / 2
    slope50 = np.tanh((e50 - e50.shift(5)) / (5 * a) * 4)
    st = ta.supertrend(h1)
    out["trend_h1"] = 0.3 * stack + 0.2 * np.sign(c - e200) + 0.25 * slope50 + 0.25 * st
    r = ta.rsi(c)
    line, _, _ = ta.macd(c)
    out["rsi_c"] = ((r - 50) / 20).clip(-1, 1)
    roc = np.tanh((c - c.shift(10)) / (a * np.sqrt(10)))
    out["mom_h1"] = 0.35 * out.rsi_c + 0.3 * np.tanh(line / a * 1.5) + 0.35 * roc

    # ---- slower trend (~H4) from longer EMAs on the same bars
    s1, s2, s3 = ta.ema(c, 32), ta.ema(c, 84), ta.ema(c, 200)
    stack4 = (np.sign(s1 - s2) + np.sign(s2 - s3)) / 2
    slope4 = np.tanh((s3 - s3.shift(20)) / (a * np.sqrt(20)))
    out["trend_h4"] = 0.5 * stack4 + 0.5 * slope4

    adx_, pdi, mdi = ta.adx(h1)
    out["adx"] = (adx_ / 50).clip(0, 1.5)
    out["di"] = ((pdi - mdi) / (pdi + mdi).replace(0, np.nan)).fillna(0.0)
    out["er20"] = ta.efficiency_ratio(c, 20)
    out["er120"] = ta.efficiency_ratio(c, 120)
    out["ext"] = _clip((c - e21) / a, -5, 5) / 2
    out["ext_slow"] = _clip((c - s2) / a, -10, 10) / 4
    sd20 = c.rolling(20).std(ddof=0)
    out["mr_z"] = _clip((c - c.rolling(20).mean()) / sd20, -3, 3) / 2

    # ---- time-series momentum, vol-normalised
    lr = np.log(c)
    sig = lr.diff().rolling(750, min_periods=200).std()
    for n in (24, 120, 480):
        out[f"ts{n}"] = _clip((lr - lr.shift(n)) / (sig * np.sqrt(n)), -4, 4) / 2

    out["atr_ratio"] = _clip(a / a.rolling(500, min_periods=100).median(), 0.3, 3)
    out["cost"] = _clip(spread / a, 0, 1) * 5

    # ---- cross-sectional strength
    if isinstance(strength, pd.Series):
        out["strength"] = strength.reindex(h1.index).ffill().fillna(0.0) / 100
    else:
        out["strength"] = float(strength or 0.0) / 100

    # ---- daily range context (NY-close days; only data up to each bar)
    ny = h1.index.tz_convert("America/New_York")
    day = pd.Index((ny + pd.Timedelta(hours=7)).normalize().tz_localize(None))
    g = h1.groupby(day)
    run_h, run_l = g.h.cummax(), g.l.cummin()
    d_open = g.o.transform("first")
    daily = pd.DataFrame({"o": g.o.first(), "h": g.h.max(), "l": g.l.min(), "c": g.c.last()})
    daily = daily[daily.index.dayofweek < 5]
    atr_d = ta.atr(daily)
    ema_d = ta.ema(daily.c, 20)
    wk = daily.index.to_period("W-FRI")
    wh = daily.h.groupby(wk).max()
    wl = daily.l.groupby(wk).min()
    prev_wh = pd.Series(wk.map(wh.shift(1)), index=daily.index)
    prev_wl = pd.Series(wk.map(wl.shift(1)), index=daily.index)
    prev = pd.DataFrame({"atr_d": atr_d.shift(1), "ema_d": ema_d.shift(1), "ema_d5": ema_d.shift(6),
                         "wh": prev_wh, "wl": prev_wl}, index=daily.index)
    p = prev.reindex(day)
    p.index = h1.index
    ad = p.atr_d.where(p.atr_d > 0)
    rng = run_h - run_l
    out["adr_used"] = _clip(rng / ad, 0, 3)
    out["move_today"] = _clip((c - d_open) / ad, -3, 3)
    out["day_pos"] = _clip((c - (run_h + run_l) / 2) / (rng / 2).replace(0, np.nan), -1.5, 1.5)
    out["d1_trend"] = _clip((p.ema_d - p.ema_d5) / (5 * ad) * 5, -3, 3)
    out["d1_dist"] = _clip((c - p.ema_d) / ad, -4, 4) / 2
    wr = (p.wh - p.wl) / 2
    out["w1_pos"] = _clip((c - (p.wh + p.wl) / 2) / wr.replace(0, np.nan), -3, 3)

    # ---- time of the decision (close of the bar)
    t = h1.index + pd.Timedelta(hours=1)
    hour = np.asarray(t.hour + t.minute / 60, dtype=float)
    out["h_sin"], out["h_cos"] = np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24)
    out["h_london"] = ((hour >= 7) & (hour < 10)).astype(float)
    out["h_ny"] = ((hour >= 12) & (hour < 15)).astype(float)
    out["h_asia"] = ((hour >= 22) | (hour < 6)).astype(float)
    out["dow_mon"] = (t.dayofweek == 0).astype(float)
    out["dow_fri"] = (t.dayofweek == 4).astype(float)
    out["is_metal"] = float(is_metal)

    out["atr"] = a
    return out.replace([np.inf, -np.inf], np.nan)


def oriented(feats: dict | pd.Series, d: int) -> dict:
    """Feature dict in trade direction: signed features multiplied by d, NaN -> 0."""
    out = {}
    for f in FEATURES:
        v = float(feats.get(f, 0.0))
        v = 0.0 if not np.isfinite(v) else v
        out[f] = v * d if f in SIGNED else v
    return out


def closed_bars(h1: pd.DataFrame, now) -> pd.DataFrame:
    """Drop the forming bar: the model was trained on bars that had closed."""
    if h1 is None or h1.empty:
        return h1
    cut = pd.Timestamp(now) - pd.Timedelta(hours=1)
    return h1[h1.index <= cut]


def derived_value(name: str, feats: dict) -> float:
    if name.endswith("^2"):
        v = feats.get(name[:-2], 0.0)
        return v * v
    if "*" in name:
        a, b = name.split("*", 1)
        return feats.get(a, 0.0) * feats.get(b, 0.0)
    return feats.get(name, 0.0)


@dataclass
class SignalModel:
    """P(profit) and expected R for one trade geometry, recalibrated on the walk-forward
    out-of-sample predictions. mtype "gbm": gradient-boosted trees for P(R > 0), expected R =
    p * avg win + (1 - p) * avg loss; mtype "ridge": ridge regression of R + logistic P(R > 0)."""
    features: list[str]
    ev: dict                         # ridge: {"mean", "std", "coef", "intercept"} raw expected R
    logit: dict                      # ridge: {"mean", "std", "coef", "intercept"} raw P(R > 0)
    ev_cal: tuple                    # calibrated R = a + b * raw
    platt: tuple                     # calibrated p = sigmoid(a * logit(raw) + b)
    geometry: dict                   # {"stop_atr", "exit", "val", "trail_atr", "horizon", "key"}
    ev_exec: float                   # minimum RAW expected R (top-q filter of the validation)
    grades: list                     # [(min RAW expected R, grade)], best first
    enabled: bool
    validated: bool
    info: dict = field(default_factory=dict)
    mtype: str = "ridge"
    gbm: dict = field(default_factory=dict)      # {"base", "trees": [[f, thr, left, right, leaf], ...]}
    win_r: float = 1.0                           # gbm: average R of profitable trades (training)
    loss_r: float = -1.0                         # gbm: average R of losing trades (training)

    @staticmethod
    def _lin(m: dict, x: np.ndarray) -> float:
        return float(((x - np.asarray(m["mean"])) / np.asarray(m["std"])) @ np.asarray(m["coef"]) + m["intercept"])

    def raw(self, feats: dict) -> tuple[float, float]:
        """(raw expected R, raw logit of P(profit))."""
        x = np.array([derived_value(f, feats) for f in self.features], dtype=float)
        if self.mtype == "gbm":
            z = float(self.gbm.get("base", 0.0))
            for nodes in self.gbm.get("trees", []):
                i = 0
                while nodes[i][0] >= 0:
                    f, thr, li, ri, _ = nodes[i]
                    i = li if x[int(f)] <= thr else ri
                z += nodes[i][4]
            p = 1 / (1 + np.exp(-z))
            return float(p * self.win_r + (1 - p) * self.loss_r), z
        return self._lin(self.ev, x), self._lin(self.logit, x)

    def calibrated(self, raw_ev: float, raw_z: float) -> tuple[float, float]:
        a, b = self.ev_cal
        pa, pb = self.platt
        return float(1 / (1 + np.exp(-(pa * raw_z + pb)))), float(a + b * raw_ev)

    def grade(self, raw_ev: float) -> str:
        for cut, g in self.grades:
            if raw_ev >= cut:
                return g
        return "D"


_CACHE: dict = {}


def load_model(path: str = MODEL_PATH) -> SignalModel | None:
    if path in _CACHE:
        return _CACHE[path]
    m = None
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        m = SignalModel(d["features"], d.get("ev", {}), d.get("logit", {}), tuple(d.get("ev_cal", (0.0, 1.0))),
                        tuple(d.get("platt", (1.0, 0.0))), d["geometry"], float(d["ev_exec"]),
                        [tuple(x) for x in d.get("grades", [])], bool(d.get("enabled", False)),
                        bool(d.get("validated", False)), d.get("info", {}), d.get("mtype", "ridge"),
                        d.get("gbm", {}), float(d.get("win_r", 1.0)), float(d.get("loss_r", -1.0)))
        m.info.setdefault("filter_q", float(d.get("filter_q", 0.1)))
        m.info["feature_ranges"] = d.get("feature_ranges", {})
    except (OSError, KeyError, ValueError, TypeError):
        m = None
    _CACHE[path] = m
    return m


@dataclass
class SignalEval:
    direction: int
    p: float              # calibrated probability that the trade ends in profit
    ev_r: float           # calibrated expected R per trade (spread included)
    raw_ev: float         # model ranking score (thresholds and grades use it)
    grade: str
    passes: bool          # inside the filter used in the historical validation
    other_ev_r: float     # calibrated expected R of the opposite direction
    feats: dict
    raw_feats: dict = field(default_factory=dict)   # direction-free inputs (compared with training ranges)
    raw_ev_other: float = 0.0                        # raw model score of the opposite direction


def evaluate_both(model: SignalModel | None, h1_closed: pd.DataFrame, strength_score: float, spread: float,
                  is_metal: bool) -> dict | None:
    """Model reading for BOTH directions from one feature computation: {1: SignalEval, -1: SignalEval}."""
    if model is None or h1_closed is None or len(h1_closed) < WARMUP_BARS // 2:
        return None
    row = feature_frame(h1_closed.iloc[-3000:], strength_score, spread, is_metal).iloc[-1]
    raw = {f: float(row[f]) for f in FEATURES if np.isfinite(row[f])}
    out = {}
    for dd in (1, -1):
        feats = oriented(row, dd)
        rev, rz = model.raw(feats)
        p, ev = model.calibrated(rev, rz)
        out[dd] = (p, ev, rev, feats)
    return {d: SignalEval(d, out[d][0], out[d][1], out[d][2], model.grade(out[d][2]), out[d][2] >= model.ev_exec,
                          out[-d][1], out[d][3], raw, out[-d][2]) for d in (1, -1)}


def evaluate(model: SignalModel | None, h1_closed: pd.DataFrame, strength_score: float, spread: float,
             is_metal: bool, d: int) -> SignalEval | None:
    """Model reading for direction d on the closed H1 bars (last bar = the decision bar)."""
    both = evaluate_both(model, h1_closed, strength_score, spread, is_metal)
    return None if both is None else both[d]


EXIT_TEXT = {"trail": "stop móvel após +1R", "be": "stop na entrada após +1R", "tp": "alvo fixo",
             "partial": "50% no alvo 1 e stop na entrada"}


def model_summary(path: str = MODEL_PATH) -> dict:
    """Validation card shown in the app (numbers from research/train_signal_model.py)."""
    m = load_model(path)
    if m is None:
        return {"available": False}
    i, g = m.info, m.geometry
    wf, test = i.get("walk_forward", {}), i.get("test", {})
    base, cal = i.get("test_baseline", {}), i.get("calibration", {})
    return {
        "available": True, "validated": m.validated, "enabled": m.enabled,
        "trained": i.get("trained", ""), "period": i.get("period", ""), "instruments": i.get("instruments", 0),
        "bars": i.get("bars", 0), "test_period": i.get("test_period", ""),
        "filter_pct": round(float(i.get("filter_q", 0.1)) * 100),
        "geometry": f"stop {g.get('stop_atr')}× ATR H1 · {EXIT_TEXT.get(g.get('exit'), g.get('exit'))} · "
                    f"até {g.get('horizon')} h",
        "wf_mean_r": wf.get("mean"), "wf_worst_r": wf.get("worst"), "wf_pos_share": wf.get("pos_share"),
        "wf_blocks": wf.get("blocks", []),
        "test_n": test.get("n"), "test_mean_r": test.get("mean_r"), "test_win": test.get("win"),
        "baseline_test_mean_r": base.get("mean_r"), "baseline_test_n": base.get("n"),
        "old_test_mean_r": i.get("test_baseline_old_plan", {}).get("mean_r"),
        "old_test_win": i.get("test_baseline_old_plan", {}).get("win"),
        "old_test_n": i.get("test_baseline_old_plan", {}).get("n"),
        "p_mean": cal.get("p_mean"), "win_real": cal.get("win_real"),
        "deciles": i.get("deciles", {}),
    }

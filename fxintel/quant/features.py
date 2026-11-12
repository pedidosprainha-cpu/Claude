"""Engenharia de features (normalizadas pela direção do trade) para o modelo probabilístico."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import instruments as I
from ..data.models import session_of
from ..fundamental.macro import RISK_BETA

FEATURES = [
    "setup_pullback", "setup_breakout", "setup_sweep", "setup_trend", "n_setups",
    "d1_align", "h4_align", "h1_align", "d1_stack", "h4_stack", "h1_stack",
    "adx_h1", "adx_h4", "adx_d1", "di_h1", "rsi_h1", "rsi_h4", "rsi_d1",
    "macd_h1", "macd_h4", "ext20", "ext50", "ext_d1", "atr_pct", "er", "compression",
    "risk_atr", "rr1", "room_r", "tp1_structural", "day_pos", "pd_dist", "rsi_div",
    "close_pos", "since_event", "in_zone", "at_ema", "trigger_engulf", "trigger_pin", "pd_sweep",
    "sess_asia", "sess_london", "sess_overlap", "sess_ny",
    "usd_dxy24", "usd_dxy120", "usd_y5", "risk_beta_ro", "vix_pct", "oil_cad",
    "str24", "str120", "is_metal", "is_jpy",
]


def usd_exposure(inst: I.Instrument, d: int) -> int:
    """+1 se a posição fica comprada em USD, -1 se vendida, 0 se não envolve USD."""
    if inst.base == "USD":
        return d
    if inst.quote == "USD":
        return -d
    return 0


def build_features(inst: I.Instrument, F: pd.DataFrame, cand: pd.DataFrame,
                   macro: pd.DataFrame | None, strength: pd.DataFrame | None) -> pd.DataFrame:
    if cand.empty:
        return pd.DataFrame(columns=FEATURES)
    f = F.loc[cand.index]
    d = cand["dir"].astype(float)
    atr = f["atr"]
    X = pd.DataFrame(index=cand.index)
    X["setup_pullback"] = (cand["setup"] == "PULLBACK").astype(float)
    X["setup_breakout"] = (cand["setup"] == "BREAKOUT").astype(float)
    X["setup_sweep"] = (cand["setup"] == "SWEEP").astype(float)
    X["setup_trend"] = (cand["setup"] == "TREND").astype(float)
    X["n_setups"] = cand["n_setups"].astype(float)
    X["d1_align"] = cand["d1_dir"] * d
    X["h4_align"] = f["h4_trend"].fillna(0) * d
    X["h1_align"] = f["trend"] * d
    X["d1_stack"] = f["d1_ema_stack"].fillna(0) * d
    X["h4_stack"] = f["h4_ema_stack"].fillna(0) * d
    X["h1_stack"] = f["ema_stack"] * d
    X["adx_h1"] = f["adx"] / 50
    X["adx_h4"] = f["h4_adx"] / 50
    X["adx_d1"] = f["d1_adx"] / 50
    X["di_h1"] = d * (f["pdi"] - f["mdi"]) / (f["pdi"] + f["mdi"]).replace(0, np.nan)
    X["rsi_h1"] = d * (f["rsi"] - 50) / 50
    X["rsi_h4"] = d * (f["h4_rsi"] - 50) / 50
    X["rsi_d1"] = d * (f["d1_rsi"] - 50) / 50
    X["macd_h1"] = (d * f["macd_hist"] / atr).clip(-3, 3)
    X["macd_h4"] = (d * f["h4_macd_hist"] / f["h4_atr"]).clip(-3, 3)
    X["ext20"] = (d * (f["c"] - f["ema20"]) / atr).clip(-5, 5)
    X["ext50"] = (d * (f["c"] - f["ema50"]) / atr).clip(-8, 8)
    X["ext_d1"] = (d * (f["c"] - f["d1_ema50"]) / f["d1_atr"]).clip(-6, 6)
    X["atr_pct"] = f["atr_pct"]
    X["er"] = f["er"]
    X["compression"] = f["compression"].clip(0, 3)
    X["risk_atr"] = cand["risk_atr"]
    X["rr1"] = cand["rr1"]
    X["room_r"] = cand["room_r"]
    X["tp1_structural"] = cand["tp1_structural"].astype(float)
    rng = (f["day_h"] - f["day_l"]).replace(0, np.nan)
    pos = (f["c"] - f["day_l"]) / rng
    X["day_pos"] = np.where(d > 0, pos, 1 - pos)
    pd_level = np.where(d > 0, f["pdh"], f["pdl"])
    X["pd_dist"] = (d * (pd_level - f["c"]) / atr).clip(-6, 6)
    X["rsi_div"] = f["rsi_div"] * d
    X["close_pos"] = np.where(d > 0, f["close_pos"], 1 - f["close_pos"])
    X["since_event"] = np.log1p(f["since_event"].clip(upper=500))
    for k in ("in_zone", "at_ema", "trigger_engulf", "trigger_pin", "pd_sweep"):
        X[k] = cand[k].astype(float)
    sess = pd.Series([session_of(t) for t in cand.index], index=cand.index)
    X["sess_asia"] = (sess == "asia").astype(float)
    X["sess_london"] = (sess == "london").astype(float)
    X["sess_overlap"] = (sess == "overlap").astype(float)
    X["sess_ny"] = sess.isin(["newyork", "late"]).astype(float)

    ux = np.array([usd_exposure(inst, int(v)) for v in d])
    m = macro.reindex(cand.index) if macro is not None and not macro.empty else pd.DataFrame(index=cand.index)
    g = lambda k: m[k] if k in m else pd.Series(0.0, index=cand.index)  # noqa: E731
    X["usd_dxy24"] = ux * g("dxy_r24").fillna(0)
    X["usd_dxy120"] = ux * g("dxy_r120").fillna(0)
    X["usd_y5"] = ux * g("us5y_d120").fillna(0)
    beta = RISK_BETA.get(inst.base, 0) - RISK_BETA.get(inst.quote, 0)
    X["risk_beta_ro"] = d * beta * g("risk_on").fillna(0)
    X["vix_pct"] = g("vix_pct").fillna(0.5)
    cad = 1 if inst.base == "CAD" else (-1 if inst.quote == "CAD" else 0)
    X["oil_cad"] = d * cad * g("wti_r120").fillna(0)
    s = strength.reindex(cand.index) if strength is not None and not strength.empty else pd.DataFrame(index=cand.index)
    X["str24"] = d * (s["str_diff_24"] if "str_diff_24" in s else 0.0)
    X["str120"] = d * (s["str_diff_120"] if "str_diff_120" in s else 0.0)
    X["is_metal"] = float(inst.kind == "metal")
    X["is_jpy"] = float("JPY" in (inst.base, inst.quote))
    X = X.replace([np.inf, -np.inf], np.nan)
    return X[FEATURES]

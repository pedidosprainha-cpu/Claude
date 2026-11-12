"""Análise multi-timeframe: quadros técnicos por TF e alinhamento causal em H1."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.models import TF_SECONDS
from .indicators import compute_basic, rolling_percentile
from .levels import session_levels
from .patterns import breakout_state, candle_patterns, rsi_divergence
from .smc import smc_frame
from .structure import describe_trend, market_structure

SWING_PARAMS = {"M5": (3, 3), "M15": (3, 3), "H1": (3, 3), "H4": (2, 2), "D1": (2, 2)}


def tf_frame(df: pd.DataFrame, tf: str, with_percentiles: bool = True) -> tuple[pd.DataFrame, list]:
    ind = compute_basic(df)
    left, right = SWING_PARAMS.get(tf, (3, 3))
    st, swings = market_structure(df, ind["atr"], left, right)
    smc = smc_frame(df, ind["atr"], st)
    pat = candle_patterns(df, ind["atr"])
    brk = breakout_state(df, ind["atr"])
    div = rsi_divergence(swings, ind["rsi"], len(df))
    f = pd.concat([df[["o", "h", "l", "c"]], ind, st, smc, pat, brk], axis=1)
    f["rsi_div"] = div
    # alinhamento de médias: +1 empilhadas para alta, -1 para baixa
    f["ema_stack"] = np.where((f.ema8 > f.ema20) & (f.ema20 > f.ema50), 1,
                              np.where((f.ema8 < f.ema20) & (f.ema20 < f.ema50), -1, 0))
    f["above_ema200"] = np.sign(f["c"] - f["ema200"]).fillna(0)
    f["macd_slope"] = f["macd_hist"].diff()
    f["ret1"] = np.log(f["c"]).diff()
    if with_percentiles:
        f["atr_pct"] = rolling_percentile(f["atr"] / f["c"], 500)
    return f, swings


def completion_index(index: pd.DatetimeIndex, tf: str) -> pd.DatetimeIndex:
    if tf == "D1":  # rótulo 00:00 do pregão iniciado às 22:00 da véspera
        return index + pd.Timedelta(hours=22)
    return index + pd.Timedelta(seconds=TF_SECONDS[tf])


HTF_COLS = ["c", "ema20", "ema50", "ema200", "atr", "rsi", "adx", "pdi", "mdi", "macd_hist",
            "macd_slope", "trend", "last_event", "since_event", "swing_bias", "ema_stack",
            "above_ema200", "last_sh", "last_sl", "near_hi", "near_lo", "er", "bb_width",
            "in_fvg_bull", "in_fvg_bear", "in_ob_bull", "in_ob_bear", "fvg_bull_top",
            "fvg_bull_bot", "fvg_bear_top", "fvg_bear_bot", "ob_bull_top", "ob_bull_bot",
            "ob_bear_top", "ob_bear_bot", "rsi_div"]


def align_htf(base: pd.DataFrame, base_tf: str, htf: pd.DataFrame, tf: str, prefix: str) -> pd.DataFrame:
    """Anexa ao quadro base as colunas do TF superior conhecidas no fechamento de cada barra base."""
    left = pd.DataFrame({"_t": completion_index(base.index, base_tf)}, index=base.index)
    cols = [c for c in HTF_COLS if c in htf.columns]
    right = htf[cols].copy()
    right["_t"] = completion_index(htf.index, tf)
    right = right.sort_values("_t")
    merged = pd.merge_asof(left.sort_values("_t"), right, on="_t", direction="backward")
    merged.index = left.sort_values("_t").index
    merged = merged.drop(columns=["_t"]).reindex(base.index)
    merged.columns = [f"{prefix}{c}" for c in merged.columns]
    return merged


def build_frame(h1: pd.DataFrame, h4: pd.DataFrame, d1: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Quadro H1 com contexto H4/D1 alinhado sem vazamento de informação futura."""
    f1, sw1 = tf_frame(h1, "H1")
    f4, sw4 = tf_frame(h4, "H4", with_percentiles=False)
    fd, swd = tf_frame(d1, "D1", with_percentiles=False)
    sess = session_levels(h1)
    F = pd.concat([f1, sess,
                   align_htf(f1, "H1", f4, "H4", "h4_"),
                   align_htf(f1, "H1", fd, "D1", "d1_")], axis=1)
    return F, {"H1": (f1, sw1), "H4": (f4, sw4), "D1": (fd, swd)}


def tf_summary(f: pd.DataFrame, tf: str) -> dict:
    """Resumo legível do estado técnico do último candle fechado de um TF."""
    r = f.iloc[-1]
    adx = float(r["adx"]) if np.isfinite(r["adx"]) else 0.0
    direction = int(np.sign(
        0.45 * r["trend"] + 0.25 * r["ema_stack"] + 0.15 * r["swing_bias"]
        + 0.15 * (1 if r["pdi"] > r["mdi"] else -1)))
    momentum = "acelerando" if r["macd_hist"] * r["macd_slope"] > 0 else "desacelerando"
    ob = "sobrecompra" if r["rsi"] >= 70 else ("sobrevenda" if r["rsi"] <= 30 else "neutro")
    return {
        "tf": tf,
        "direction": direction,
        "trend_text": describe_trend(int(r["trend"]), int(r["swing_bias"]), adx),
        "structure_state": int(r["trend"]),
        "last_event": {1: "BOS de alta", 2: "CHoCH de alta", -1: "BOS de baixa",
                       -2: "CHoCH de baixa", 0: "—"}[int(r["last_event"])],
        "bars_since_event": int(r["since_event"]) if r["since_event"] < 9999 else None,
        "ema_stack": int(r["ema_stack"]),
        "adx": round(adx, 1),
        "rsi": round(float(r["rsi"]), 1) if np.isfinite(r["rsi"]) else None,
        "rsi_state": ob,
        "macd_hist": float(r["macd_hist"]) if np.isfinite(r["macd_hist"]) else None,
        "momentum": momentum,
        "atr": float(r["atr"]) if np.isfinite(r["atr"]) else None,
        "close": float(r["c"]),
        "time": f.index[-1].isoformat(),
        "last_swing_high": float(r["last_sh"]) if np.isfinite(r["last_sh"]) else None,
        "last_swing_low": float(r["last_sl"]) if np.isfinite(r["last_sl"]) else None,
        "vwap": float(r["vwap"]) if np.isfinite(r.get("vwap", np.nan)) else None,
        "divergence": {1: "divergência de alta (RSI)", -1: "divergência de baixa (RSI)", 0: None}[int(r["rsi_div"])],
    }


def alignment_score(summaries: dict[str, dict]) -> float:
    """Alinhamento ponderado entre TFs, em [-1, 1]."""
    w = {"D1": 0.30, "H4": 0.30, "H1": 0.20, "M15": 0.12, "M5": 0.08}
    tot = sum(w[k] for k in summaries if k in w)
    if not tot:
        return 0.0
    return sum(w[k] * summaries[k]["direction"] for k in summaries if k in w) / tot

"""Multi-timeframe trend-continuation strategy with confluence scoring.

One entry timeframe (default H1) is fetched per symbol; the trend (H4) and bias
(D1) timeframes are rebuilt from it so live trading and the backtest see
exactly the same numbers. Three setups in two families:

  reversion  MR  a multi-day move is statistically stretched; fade it (swing)
  trend      PB  trend intact, price retraces to the fast EMA, then resumes
             BO  trend intact, tight consolidation breaks in trend direction

Every candidate gets a 0-100 confluence score; the engine only trades scores
at or above `min_score`. See references/strategy.md for the full rationale.
"""
from __future__ import annotations

import numpy as np

from . import indicators as ind
from .config import currencies_of
from .timeutil import TF_SECONDS


def _resample(t, h, l, c, tf_sec: int):
    """Aggregate entry bars into a higher timeframe. Returns (keys, high, low, close)."""
    keys = t // tf_sec
    uniq, first = np.unique(keys, return_index=True)
    last = np.append(first[1:], len(t)) - 1
    return uniq, np.maximum.reduceat(h, first), np.minimum.reduceat(l, first), c[last]


def _align(uniq, t, entry_sec: int, tf_sec: int):
    """For each entry bar, index of the last higher-timeframe bar that is fully closed."""
    target = (t + entry_sec) // tf_sec - 1
    pos = np.searchsorted(uniq, target, side="right") - 1
    return np.clip(pos, 0, None), pos >= 0


def compute_features(bars: dict, sp: dict, entry_tf: str = "H1") -> dict:
    """bars: dict of equal-length arrays time/open/high/low/close (closed bars only)."""
    t = np.asarray(bars["time"], dtype=np.int64)
    o, h, l, c = (np.asarray(bars[k], dtype=float) for k in ("open", "high", "low", "close"))
    entry_sec = TF_SECONDS[entry_tf]
    f = {"time": t, "open": o, "high": h, "low": l, "close": c, "entry_sec": entry_sec}

    f["ema_fast"] = ind.ema(c, sp["ema_fast"])
    f["ema_mid"] = ind.ema(c, sp["ema_mid"])
    f["ema_slow"] = ind.ema(c, sp["ema_slow"])
    f["atr"] = ind.atr(h, l, c, 14)
    f["rsi"] = ind.rsi(c, 14)
    f["adx"], f["pdi"], f["mdi"] = ind.adx(h, l, c, 14)
    f["macd"] = ind.macd_hist(c)

    # Trend timeframe (H4)
    sec = TF_SECONDS[sp["trend_tf"]]
    uq, hh, ll, cc = _resample(t, h, l, c, sec)
    pos, ok = _align(uq, t, entry_sec, sec)
    e_mid, e_slow = ind.ema(cc, sp["ema_mid"]), ind.ema(cc, sp["ema_slow"])
    adx4, _, _ = ind.adx(hh, ll, cc, 14)
    f["t_close"], f["t_mid"], f["t_slow"] = cc[pos], e_mid[pos], e_slow[pos]
    f["t_mid_prev"] = ind.shift(e_mid, 3)[pos]
    f["t_adx"] = adx4[pos]
    f["t_atr"] = ind.atr(hh, ll, cc, 14)[pos]
    f["t_bars"] = np.where(ok, pos + 1, 0)

    # Bias timeframe (D1)
    sec = TF_SECONDS[sp["bias_tf"]]
    uq, hh, ll, cc = _resample(t, h, l, c, sec)
    pos, ok = _align(uq, t, entry_sec, sec)
    f["b_close"] = cc[pos]
    f["b_fast"] = ind.ema(cc, sp["ema_fast"])[pos]
    f["b_mid"] = ind.ema(cc, sp["ema_mid"])[pos]
    f["b_bars"] = np.where(ok, pos + 1, 0)
    f["b_atr"] = ind.atr(hh, ll, cc, 14)[pos]
    ret = np.diff(np.log(cc), prepend=np.log(cc[0]))
    vol = np.sqrt(ind.rma(ret ** 2, 20)) + 1e-12
    n_mr = sp["mr_lookback"]
    f["b_z"] = (np.log(cc / ind.shift(cc, n_mr)) / (vol * np.sqrt(n_mr)))[pos]

    # Momentum used for the cross-sectional currency-strength ranking
    atr_safe = np.where(f["atr"] > 0, f["atr"], np.nan)
    for name, n in (("mom_fast", sp["strength_fast"]), ("mom_slow", sp["strength_slow"])):
        f[name] = np.nan_to_num((c - ind.shift(c, n)) / (atr_safe * np.sqrt(n)))
    f["mom"] = 0.5 * (f["mom_fast"] + f["mom_slow"])
    return f


def _side(f: dict, sp: dict, sgn: int) -> dict:
    """Vectorised setup detection + scoring for one direction (+1 long, -1 short).

    Prices are mirrored for shorts so the logic below reads as the long case.
    """
    c, o = sgn * f["close"], sgn * f["open"]
    hi = f["high"] if sgn > 0 else -f["low"]
    lo = f["low"] if sgn > 0 else -f["high"]
    ef, em, es = sgn * f["ema_fast"], sgn * f["ema_mid"], sgn * f["ema_slow"]
    atr = f["atr"]
    rsi = f["rsi"] if sgn > 0 else 100.0 - f["rsi"]
    macd = sgn * f["macd"]
    tc, tm, ts, tmp = sgn * f["t_close"], sgn * f["t_mid"], sgn * f["t_slow"], sgn * f["t_mid_prev"]
    bc, bf, bm = sgn * f["b_close"], sgn * f["b_fast"], sgn * f["b_mid"]
    rng = np.maximum(hi - lo, 1e-12)

    # --- hard gates -------------------------------------------------------
    warm = (f["t_bars"] >= sp["ema_mid"] + 10) & (f["b_bars"] >= sp["ema_fast"] + 5) & (atr > 0)
    trend = (tc > tm) & (tm > ts) & (tm > tmp) & (f["t_adx"] >= sp["adx_min"])
    bias_against = (bc < bm) & (bf < bm)            # daily chart clearly the other way
    base = warm & trend & ~bias_against & (c > es)

    # --- setup PB: pullback to the fast EMA, then resumption ---------------
    lb = sp["pullback_lookback"]
    prev_lo = ind.shift(ind.rolling_min(lo, lb), 1)
    touched = ind.shift(ind.rolling_min(lo - ef, lb), 1) <= 0.15 * atr
    held = ind.shift(ind.rolling_min(c - es, lb), 1) > 0
    cooled = ind.shift(ind.rolling_min(rsi, lb), 1) <= sp["rsi_pullback"]
    trigger = (c > o) & (c > ind.shift(hi, 1)) & (c > ef) & ((c - ef) <= sp["max_ext_atr"] * atr) & (rsi < 70)
    pb_dist = c - (np.minimum(prev_lo, lo) - sp["sl_buffer_atr"] * atr)
    pb_ok = pb_dist <= sp["sl_atr_max"] * atr
    pb_dist = np.maximum(pb_dist, sp["sl_atr_min"] * atr)
    pb = base & touched & held & cooled & trigger & pb_ok & bool(sp["enable_pullback"])

    # --- setup BO: breakout from a tight box -------------------------------
    n, box = sp["breakout_lookback"], sp["box_bars"]
    don = ind.shift(ind.rolling_max(hi, n), 1)
    box_rng = ind.shift(ind.rolling_max(hi, box) - ind.rolling_min(lo, box), 1)
    strong = ((c - o) >= 0.5 * rng) & ((hi - c) <= 0.3 * rng)
    bo = (base & (c > don) & (ind.shift(c, 1) <= don) & (box_rng <= sp["box_atr_max"] * atr) & strong
          & ((c - ef) <= 2.0 * atr) & (rsi < 78) & bool(sp["enable_breakout"]))
    bo_dist = sp["breakout_sl_atr"] * atr

    # --- confluence score ---------------------------------------------------
    s_bias = np.where((bc > bf) & (bf > bm), 15.0, np.where(bc > bm, 10.0, 4.0))
    s_trend = (10.0 + np.clip((f["t_adx"] - sp["adx_min"]) / 12.0, 0, 1) * 8.0
               + np.clip((tm - tmp) / np.maximum(f["t_atr"], 1e-12), 0, 1) * 7.0)
    s_entry = (np.where((ef > em) & (em > es), 8.0, np.where(ef > em, 5.0, 2.0))
               + np.where(macd > 0, 4.0, 0.0) + np.where(macd > ind.shift(macd, 1), 3.0, 0.0))
    body = np.clip((c - o) / rng, 0, 1)
    s_pb = 10.0 + 6.0 * body + np.where(rsi > 50, 4.0, 0.0) + np.where(f["adx"] >= 20, 5.0, 0.0)
    s_bo = 8.0 + 6.0 * body + np.clip(1.0 - box_rng / (sp["box_atr_max"] * np.maximum(atr, 1e-12)), 0, 1) * 6.0 \
        + np.where(f["adx"] > ind.shift(f["adx"], 3), 5.0, 0.0)
    common = s_bias + s_trend + s_entry

    # --- setup MR: fade a stretched multi-day move (swing mean reversion) ----
    zs = sgn * f["b_z"]
    mr = ((f["b_bars"] >= sp["mr_lookback"] + 25) & (zs <= -sp["mr_z"]) & (f["b_atr"] > 0)
          & bool(sp["enable_reversion"]))
    mr_dist = sp["mr_sl_atr"] * f["b_atr"]
    s_mr = 72.0 + 8.0 * np.clip((-zs - sp["mr_z"]) / 1.0, 0, 1)

    use_mr = mr
    use_pb = pb & ~mr
    use_bo = bo & ~pb & ~mr
    return {
        "signal": use_mr | use_pb | use_bo,
        "setup": np.where(use_mr, 3, np.where(use_pb, 1, np.where(use_bo, 2, 0))),
        "score": np.where(use_mr, s_mr, np.where(use_pb, common + s_pb, np.where(use_bo, common + s_bo, 0.0))),
        "dist": np.where(use_mr, mr_dist, np.where(use_pb, pb_dist, bo_dist)),
        "trend": warm & trend,
    }


SETUP_NAMES = {0: "", 1: "PB", 2: "BO", 3: "MR"}
FAMILY = {"PB": "trend", "BO": "trend", "MR": "reversion"}


def family_of(setup: str) -> str:
    return FAMILY.get(setup, "trend")


def tp_r_of(setup: str, sp: dict) -> float:
    return sp["mr_tp_r"] if family_of(setup) == "reversion" else sp["tp_r"]


def cooldown_bars_of(setup: str, sp: dict) -> int:
    return sp["mr_cooldown_bars"] if family_of(setup) == "reversion" else sp["cooldown_bars"]


def compute_signals(f: dict, sp: dict) -> dict:
    """Arrays over the entry bars: direction (+1/-1/0), setup id, base score, stop distance."""
    lg, sh = _side(f, sp, +1), _side(f, sp, -1)
    take_long = lg["signal"] & (~sh["signal"] | (lg["score"] >= sh["score"]))
    take_short = sh["signal"] & ~take_long
    return {
        "dir": np.where(take_long, 1, np.where(take_short, -1, 0)),
        "setup": np.where(take_long, lg["setup"], np.where(take_short, sh["setup"], 0)),
        "score": np.where(take_long, lg["score"], np.where(take_short, sh["score"], 0.0)),
        "dist": np.where(take_long, lg["dist"], np.where(take_short, sh["dist"], 0.0)),
        "trend": np.where(lg["trend"], 1, np.where(sh["trend"], -1, 0)),
    }


def currency_strength(mom_by_symbol: dict) -> dict:
    """Average momentum per currency across every pair that contains it.

    mom_by_symbol maps canonical symbol -> momentum (scalar or equal-length arrays).
    A pair rising means its base is strong and its quote is weak.
    """
    acc: dict[str, list] = {}
    for sym, m in mom_by_symbol.items():
        base, quote = currencies_of(sym)
        acc.setdefault(base, []).append(m)
        acc.setdefault(quote, []).append(-np.asarray(m, dtype=float))
    return {cur: np.nanmean(np.stack([np.asarray(v, dtype=float) for v in vals]), axis=0)
            for cur, vals in acc.items()}


def strength_diff(strength: dict, symbol: str):
    """Strength of the base currency minus strength of the quote currency."""
    base, quote = currencies_of(symbol)
    return np.asarray(strength[base], dtype=float) - np.asarray(strength[quote], dtype=float)


def strength_score(diff, direction):
    """0-10 points: are we buying the stronger currency against the weaker one?"""
    return np.clip(5.0 + 5.0 * np.asarray(diff, dtype=float) * direction, 0.0, 10.0)


def session_score(session: str) -> float:
    return {"overlap": 5.0, "london": 5.0, "newyork": 4.0, "asia": 2.0, "late": 0.0}.get(session, 0.0)


def cost_score(spread: float, dist: float) -> float:
    """0-5 points: how small the spread is relative to the stop distance."""
    if dist <= 0:
        return 0.0
    frac = spread / dist
    return 5.0 if frac <= 0.04 else 4.0 if frac <= 0.07 else 2.0 if frac <= 0.10 else 0.0


def levels(direction: int, entry: float, dist: float, tp_r: float) -> tuple[float, float]:
    """Stop-loss and take-profit prices. tp_r <= 0 means no take-profit (returns 0.0)."""
    tp = entry + direction * dist * tp_r if tp_r > 0 else 0.0
    return entry - direction * dist, tp


def manage(direction: int, entry: float, risk_dist: float, sl: float, close: float, bars_held: int, mp: dict):
    """Position management on each closed entry bar. Returns (new_sl, exit_reason|None).

    Pure function shared by the live engine and the backtest. The stop only
    ever moves in the trade's favour.
    """
    progress = direction * (close - entry) / risk_dist if risk_dist > 0 else 0.0
    new_sl = sl
    if mp["breakeven_at_r"] > 0 and progress >= mp["breakeven_at_r"]:
        be = entry + direction * mp["breakeven_lock_r"] * risk_dist
        if direction * (be - new_sl) > 0:
            new_sl = be
    if mp["trail_start_r"] > 0 and progress >= mp["trail_start_r"]:
        tr = close - direction * mp["trail_dist_r"] * risk_dist
        if direction * (tr - new_sl) > 0:
            new_sl = tr
    reason = "time_stop" if mp["max_hold_bars"] > 0 and bars_held >= mp["max_hold_bars"] else None
    return new_sl, reason

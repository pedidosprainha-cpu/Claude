"""Multi-timeframe technical analysis: trend, momentum, structure, setups and timing."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import indicators as ta
from .patterns import Candle, Squeeze, candle_patterns, rsi_divergence, squeeze
from .structure import Structure, market_structure


def _tanh(x: float) -> float:
    return float(np.tanh(x)) if np.isfinite(x) else 0.0


@dataclass
class TFView:
    tf: str
    close: float
    atr: float
    ema8: float
    ema21: float
    ema50: float
    ema200: float
    rsi: float
    macd_hist: float
    macd_hist_prev: float
    adx: float
    pdi: float
    mdi: float
    st_dir: int
    ichi: int
    er: float
    stoch_k: float
    structure: Structure
    trend: float           # -1..1
    momentum: float        # -1..1
    score: float           # -1..1
    candles: list[Candle] = field(default_factory=list)
    squeeze: Squeeze | None = None
    divergence: int = 0
    divergence_desc: str = ""

    @property
    def direction(self) -> int:
        return int(np.sign(self.score)) if abs(self.score) > 0.1 else 0


def analyze_tf(tf: str, df: pd.DataFrame) -> TFView | None:
    if df is None or len(df) < 60:
        return None
    c = df.c
    a = ta.atr(df).iloc[-1]
    if not np.isfinite(a) or a <= 0:
        return None
    e8, e21, e50 = ta.ema(c, 8).iloc[-1], ta.ema(c, 21).iloc[-1], ta.ema(c, 50).iloc[-1]
    e50s = ta.ema(c, 50)
    e200 = ta.ema(c, 200).iloc[-1] if len(c) >= 200 else np.nan
    r = float(ta.rsi(c).iloc[-1])
    line, sig, hist = ta.macd(c)
    adx_, pdi, mdi = ta.adx(df)
    st = int(ta.supertrend(df).iloc[-1])
    tk, kj, sa, sb = ta.ichimoku(df)
    px = float(c.iloc[-1])
    top, bot = np.nanmax([sa.iloc[-1], sb.iloc[-1]]), np.nanmin([sa.iloc[-1], sb.iloc[-1]])
    ichi = 0 if not np.isfinite(top) else (1 if px > top else (-1 if px < bot else 0))
    er = float(ta.efficiency_ratio(c, 20).iloc[-1])
    k, _ = ta.stochastic(df)
    stru = market_structure(df, k=3 if tf in ("M5", "M15", "H1") else 2)

    # ---- trend (-1..1)
    stack = (np.sign(e8 - e21) + np.sign(e21 - e50)) / 2
    pos200 = np.sign(px - e200) if np.isfinite(e200) else 0.0
    slope50 = _tanh((e50s.iloc[-1] - e50s.iloc[-6]) / (5 * a) * 4)
    trend = (0.25 * stack + 0.15 * pos200 + 0.20 * slope50 + 0.15 * st + 0.10 * ichi + 0.15 * stru.score)

    # ---- momentum (-1..1)
    rsi_c = float(np.clip((r - 50) / 20, -1, 1))
    macd_c = _tanh(line.iloc[-1] / a * 1.5)
    h_now, h_prev = float(hist.iloc[-1]), float(hist.iloc[-2])
    accel = 0.5 * np.sign(h_now) + 0.5 * np.sign(h_now - h_prev)
    roc = _tanh((px - c.iloc[-11]) / (a * np.sqrt(10)))
    momentum = 0.30 * rsi_c + 0.25 * macd_c + 0.20 * accel + 0.25 * roc

    # ADX modulates conviction: weak ADX shrinks the score toward zero.
    adx_v = float(adx_.iloc[-1])
    conv = 0.65 + 0.35 * min(adx_v / 30, 1.2)
    score = float(np.clip((0.6 * trend + 0.4 * momentum) * conv, -1, 1))

    view = TFView(tf, px, float(a), float(e8), float(e21), float(e50), float(e200), r, h_now, h_prev,
                  adx_v, float(pdi.iloc[-1]), float(mdi.iloc[-1]), st, ichi, er,
                  float(k.iloc[-1]) if np.isfinite(k.iloc[-1]) else 50.0, stru,
                  float(trend), float(momentum), score)
    if tf in ("M15", "H1", "H4"):
        view.candles = candle_patterns(df, float(a))
        view.squeeze = squeeze(df)
        view.divergence, view.divergence_desc = rsi_divergence(df)
    return view


@dataclass
class Setup:
    name: str
    direction: int
    quality: float     # 0..1
    detail: str


@dataclass
class TechnicalResult:
    views: dict[str, TFView]
    score: float                  # -100..100 (MTF composite incl. setup bonus)
    mtf_raw: float                # -1..1 before setup bonus
    alignment: float              # share of TF weight agreeing with the composite sign
    setups: list[Setup]
    timing_mult: float            # 0.4..1.1 entry-timing quality for sign(score)
    timing_notes: list[str]
    reasons: list[str]
    warnings: list[str]


def detect_setups(v: dict[str, TFView], price: float) -> list[Setup]:
    out: list[Setup] = []
    m5, m15, h1, h4 = v.get("M5"), v.get("M15"), v.get("H1"), v.get("H4")
    if not (m15 and h1):
        return out
    higher = (h1.trend + (h4.trend if h4 else h1.trend)) / 2

    # 1) Trend pullback to value with trigger-TF momentum re-acceleration
    for d in (1, -1):
        if d * higher < 0.35:
            continue
        dist21 = d * (price - m15.ema21) / m15.atr      # > 0: on the trend side of the EMA21
        dist50 = d * (price - m15.ema50) / m15.atr
        near_value = (-0.8 <= dist21 <= 0.9) or (-1.2 < dist50 <= 0.6)
        trigger = (np.sign(m15.macd_hist - m15.macd_hist_prev) == d) and (m5 is None or m5.momentum * d > 0.1)
        not_extreme = h1.rsi < 70 if d == 1 else h1.rsi > 30
        if near_value and trigger and not_extreme:
            q = min(1.0, 0.5 + 0.5 * d * higher)
            out.append(Setup("pullback a favor da tendência", d, q,
                             f"H1/H4 em tendência, preço no valor (EMA21-M15 a {dist21:+.2f} ATR) "
                             "e momentum M15 reacelerando"))

    # 2) Volatility-squeeze release
    for view in (m15, h1):
        sq = view.squeeze
        if sq and sq.fired:
            q = 0.55 + min(sq.bars_on, 20) / 50
            out.append(Setup(f"rompimento de compressão ({view.tf})", sq.fired, min(q, 1.0),
                             f"squeeze de {sq.bars_on} barras liberado; largura BB no percentil {sq.width_pct:.0f}"))

    # 3) Break of structure aligned with H1 trend
    for view in (m15, h1):
        s = view.structure
        if s.bos and s.bos_bars_ago is not None and s.bos_bars_ago <= 6 and s.bos * h1.trend > 0.2:
            out.append(Setup(f"quebra de estrutura ({view.tf})", s.bos, 0.6 + (0.2 if not s.choch else 0.0),
                             f"BOS {'altista' if s.bos > 0 else 'baixista'} há {s.bos_bars_ago} barras"
                             + (" (CHoCH)" if s.choch else "")))

    # 4) Mean-reversion fade at band extremes in a weak-trend market
    if h1.adx < 20:
        bb_dev = (price - h1.ema21) / h1.atr
        for d in (1, -1):
            if -d * bb_dev > 2.2 and ((d == 1 and h1.rsi < 30) or (d == -1 and h1.rsi > 70)):
                out.append(Setup("reversão à média (fade)", d, 0.55,
                                 f"preço {abs(bb_dev):.1f} ATR da média H1 com RSI {h1.rsi:.0f} e ADX baixo"))
    return out


def entry_timing(views: dict[str, TFView], price: float, d: int) -> tuple[float, list[str], list[str], list[str]]:
    """Quality of entering *now* in direction d: (multiplier 0.4..1.1, timing notes, reasons, warnings)."""
    reasons: list[str] = []
    warnings: list[str] = []
    mult, tnotes = 1.0, []
    m15, h1, m5 = views.get("M15"), views.get("H1"), views.get("M5")
    if m15:
        ext = d * (price - m15.ema21) / m15.atr
        if ext > 2.2:
            pen = max(0.45, 1 - 0.18 * (ext - 2.2))
            mult *= pen
            tnotes.append(f"preço esticado {ext:.1f} ATR da EMA21-M15 (perseguição)")
        elif -0.5 <= ext <= 1.2:
            mult *= 1.05
            tnotes.append(f"entrada próxima do valor (EMA21-M15 a {ext:+.1f} ATR)")
        if (d == 1 and m15.rsi > 74) or (d == -1 and m15.rsi < 26):
            mult *= 0.85
            tnotes.append(f"RSI M15 em extremo ({m15.rsi:.0f})")
        for cd in m15.candles:
            if cd.direction == d:
                mult *= 1.04
                tnotes.append(f"candle M15 confirma: {cd.name}")
            elif cd.direction == -d:
                mult *= 0.92
                tnotes.append(f"candle M15 contra: {cd.name}")
    if h1:
        if (d == 1 and h1.rsi > 76) or (d == -1 and h1.rsi < 24):
            mult *= 0.85
            tnotes.append(f"RSI H1 em extremo ({h1.rsi:.0f})")
        if h1.divergence == -d:
            mult *= 0.85
            warnings.append(f"H1: {h1.divergence_desc}")
        elif h1.divergence == d:
            reasons.append(f"H1: {h1.divergence_desc}")
    if m15 and m15.divergence == -d:
        mult *= 0.92
        warnings.append(f"M15: {m15.divergence_desc}")
    if m5 and m5.score * d < -0.35:
        mult *= 0.9
        tnotes.append("M5 contra a direção no momento (aguardar gatilho melhora o preço)")

    if h1 and h1.adx >= 25:
        reasons.append(f"ADX H1 {h1.adx:.0f}: tendência com força")
    elif h1 and h1.adx < 18:
        warnings.append(f"ADX H1 {h1.adx:.0f}: mercado sem tendência definida")

    return float(np.clip(mult, 0.4, 1.1)), tnotes, reasons, warnings


def analyze(frames: dict[str, pd.DataFrame], price: float, tf_weights: dict[str, float]) -> TechnicalResult:
    views = {tf: vw for tf in tf_weights if (vw := analyze_tf(tf, frames.get(tf))) is not None}
    reasons: list[str] = []
    warnings: list[str] = []
    if not views:
        return TechnicalResult({}, 0.0, 0.0, 0.0, [], 0.0, ["sem dados"], [], ["dados insuficientes"])

    wsum = sum(tf_weights[t] for t in views)
    raw = sum(tf_weights[t] * views[t].score for t in views) / wsum
    sign = int(np.sign(raw)) or 1
    align = sum(tf_weights[t] for t in views if np.sign(views[t].score) == sign and abs(views[t].score) > 0.1) / wsum

    setups = detect_setups(views, price)
    bonus = 0.0
    for s in setups:
        bonus += s.direction * s.quality * 0.12
    bonus = float(np.clip(bonus, -0.25, 0.25))
    score = float(np.clip(raw + bonus, -1, 1)) * 100

    d = int(np.sign(score)) or 1
    word = "alta" if d > 0 else "baixa"
    agree = [t for t in views if np.sign(views[t].score) == d and abs(views[t].score) > 0.1]
    if agree:
        reasons.append(f"viés de {word} em {', '.join(agree)} (alinhamento {align * 100:.0f}% do peso MTF)")
    for s in setups:
        if s.direction == d:
            reasons.append(f"setup: {s.name} — {s.detail}")
        elif s.direction == -d:
            warnings.append(f"setup contrário: {s.name} — {s.detail}")

    mult, tnotes, r2, w2 = entry_timing(views, price, d)
    reasons += r2
    warnings += w2

    return TechnicalResult(views, score, float(raw), float(align), setups, mult, tnotes, reasons, warnings)

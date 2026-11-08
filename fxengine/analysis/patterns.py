"""Price-action patterns: candlesticks, volatility squeeze, RSI divergences."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import indicators as ta
from .structure import swings


@dataclass
class Candle:
    name: str
    direction: int   # +1 bullish / -1 bearish


def candle_patterns(df: pd.DataFrame, atr_val: float) -> list[Candle]:
    """Patterns on the last *closed* bar (index -2 is closed; -1 is forming)."""
    if len(df) < 4 or atr_val <= 0:
        return []
    b, p = df.iloc[-2], df.iloc[-3]
    out: list[Candle] = []
    rng = b.h - b.l
    body = abs(b.c - b.o)
    if rng <= 0:
        return out
    up_wick = b.h - max(b.c, b.o)
    lo_wick = min(b.c, b.o) - b.l
    p_body_lo, p_body_hi = min(p.o, p.c), max(p.o, p.c)

    if b.c > b.o and p.c < p.o and b.c >= p_body_hi and b.o <= p_body_lo and body > 0.25 * atr_val:
        out.append(Candle("engolfo de alta", 1))
    if b.c < b.o and p.c > p.o and b.c <= p_body_lo and b.o >= p_body_hi and body > 0.25 * atr_val:
        out.append(Candle("engolfo de baixa", -1))
    if lo_wick >= 2 * max(body, 1e-12) and up_wick <= 0.35 * rng and rng >= 0.8 * atr_val:
        out.append(Candle("pin bar de alta (martelo)", 1))
    if up_wick >= 2 * max(body, 1e-12) and lo_wick <= 0.35 * rng and rng >= 0.8 * atr_val:
        out.append(Candle("pin bar de baixa (estrela cadente)", -1))
    if body >= 0.8 * rng and rng >= 1.3 * atr_val:
        out.append(Candle("marubozu de momentum", 1 if b.c > b.o else -1))
    if b.h < p.h and b.l > p.l:
        out.append(Candle("inside bar", 0))
    return out


@dataclass
class Squeeze:
    on: bool
    fired: int          # +1 / -1 released in the last 3 bars, 0 otherwise
    bars_on: int        # length of the latest squeeze
    width_pct: float    # Bollinger width percentile over the window (0..100)


def squeeze(df: pd.DataFrame, window: int = 250) -> Squeeze:
    if len(df) < 40:
        return Squeeze(False, 0, 0, 50.0)
    bl, bm, bu = ta.bollinger(df.c, 20, 2.0)
    kl, km, ku = ta.keltner(df, 20, 1.5)
    sq = ((bu < ku) & (bl > kl)).to_numpy()
    width = ((bu - bl) / bm).iloc[-window:]
    pct = float((width.rank(pct=True).iloc[-1]) * 100) if width.notna().sum() > 10 else 50.0
    # count consecutive squeeze bars ending at the most recent squeeze bar
    bars_on, i = 0, len(sq) - 1
    while i >= 0 and not sq[i] and len(sq) - 1 - i < 4:
        i -= 1
    while i >= 0 and sq[i]:
        bars_on += 1
        i -= 1
    fired = 0
    recent = sq[-4:]
    if not sq[-1] and recent[:-1].any() and bars_on >= 5:
        mom = df.c.iloc[-1] - ((df.h.rolling(20).max() + df.l.rolling(20).min()) / 2 + km).iloc[-1] / 2
        fired = 1 if mom > 0 else -1
    return Squeeze(bool(sq[-1]), fired, bars_on, pct)


def rsi_divergence(df: pd.DataFrame, k: int = 3, lookback: int = 60) -> tuple[int, str]:
    """Regular divergence between the last two confirmed swings.
    Returns (+1 bullish / -1 bearish / 0, description)."""
    if len(df) < lookback:
        return 0, ""
    sub = df.iloc[-lookback:]
    r = ta.rsi(df.c).iloc[-lookback:].to_numpy()
    sw = swings(sub, k)
    hs = [s for s in sw if s.kind == "H"][-2:]
    ls = [s for s in sw if s.kind == "L"][-2:]
    res, desc = 0, ""
    if len(hs) == 2 and hs[1].price > hs[0].price and r[hs[1].i] < r[hs[0].i] - 2 and r[hs[0].i] > 55:
        res, desc = -1, "divergência baixista (preço topo mais alto, RSI mais baixo)"
    if len(ls) == 2 and ls[1].price < ls[0].price and r[ls[1].i] > r[ls[0].i] + 2 and r[ls[0].i] < 45:
        if res == 0 or ls[1].i > hs[1].i:
            res, desc = 1, "divergência altista (preço fundo mais baixo, RSI mais alto)"
    # stale divergences (swing too old) are ignored
    last_i = max([s.i for s in hs + ls], default=0)
    if res and len(sub) - 1 - last_i > 15:
        return 0, ""
    return res, desc


def bars_since(mask: np.ndarray) -> int | None:
    idx = np.flatnonzero(mask)
    return None if len(idx) == 0 else len(mask) - 1 - int(idx[-1])

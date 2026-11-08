"""Price structure: swing pivots, HH/HL market structure, break of structure and
multi-source support/resistance zones (swings H1/H4/D1, prior day/week, pivots,
round numbers), clustered into weighted zones."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Swing:
    i: int           # positional index in the frame
    ts: pd.Timestamp
    price: float
    kind: str        # "H" | "L"


def swings(df: pd.DataFrame, k: int = 3) -> list[Swing]:
    """Fractal pivots confirmed by k bars on each side (no look-ahead beyond k)."""
    if len(df) < 2 * k + 1:
        return []
    w = 2 * k + 1
    hmax = df.h.rolling(w, center=True).max()
    lmin = df.l.rolling(w, center=True).min()
    is_h = (df.h == hmax).to_numpy()
    is_l = (df.l == lmin).to_numpy()
    out: list[Swing] = []
    hv, lv, idx = df.h.to_numpy(), df.l.to_numpy(), df.index
    last_h = last_l = -10
    for i in range(len(df)):
        if is_h[i] and i - last_h > k:
            out.append(Swing(i, idx[i], float(hv[i]), "H"))
            last_h = i
        if is_l[i] and i - last_l > k:
            out.append(Swing(i, idx[i], float(lv[i]), "L"))
            last_l = i
    return out


@dataclass
class Structure:
    trend: int               # +1 HH/HL, -1 LH/LL, 0 mixed
    score: float             # -1..1 (partial structures score 0.5)
    last_high: float | None
    last_low: float | None
    bos: int                 # +1 bullish / -1 bearish break of structure in the recent window
    bos_bars_ago: int | None
    choch: bool              # the BOS goes against the prior structure (change of character)


def market_structure(df: pd.DataFrame, k: int = 3, recent: int = 8) -> Structure:
    sw = swings(df, k)
    highs = [s for s in sw if s.kind == "H"]
    lows = [s for s in sw if s.kind == "L"]
    if len(highs) < 2 or len(lows) < 2:
        return Structure(0, 0.0, highs[-1].price if highs else None, lows[-1].price if lows else None,
                         0, None, False)
    hh = highs[-1].price > highs[-2].price
    hl = lows[-1].price > lows[-2].price
    score = (0.5 if hh else -0.5) + (0.5 if hl else -0.5)
    trend = 1 if score == 1 else (-1 if score == -1 else 0)

    # Break of structure: first close beyond the latest confirmed swing, within `recent` bars.
    c = df.c.to_numpy()
    n = len(df)
    bos, ago = 0, None
    for sh, sign in ((highs[-1], 1), (lows[-1], -1)):
        start = sh.i + k + 1
        for j in range(max(start, n - recent), n):
            if (sign == 1 and c[j] > sh.price) or (sign == -1 and c[j] < sh.price):
                if ago is None or n - 1 - j < ago:
                    bos, ago = sign, n - 1 - j
                break
    choch = bos != 0 and trend != 0 and bos != trend
    return Structure(trend, score, highs[-1].price, lows[-1].price, bos, ago, choch)


@dataclass
class Level:
    price: float
    strength: float
    sources: list[str]

    def label(self) -> str:
        return ", ".join(sorted(set(self.sources)))


def _round_levels(price: float, step: float, span: float) -> list[tuple[float, float, str]]:
    out = []
    lo, hi = price - span, price + span
    first = np.floor(lo / step) * step
    x = first
    while x <= hi:
        big = abs((x / (step * 2)) - round(x / (step * 2))) < 1e-9
        out.append((float(x), 1.6 if big else 0.9, "número redondo"))
        x += step
    return out


def collect_levels(frames: dict[str, pd.DataFrame], price: float, round_step: float) -> list[tuple[float, float, str]]:
    raw: list[tuple[float, float, str]] = []
    for tf, k, look, w in (("H1", 3, 400, 1.0), ("H4", 2, 300, 1.8), ("D1", 2, 250, 2.6)):
        df = frames.get(tf)
        if df is None or len(df) < 10:
            continue
        sub = df.iloc[-look:]
        n = len(sub)
        for s in swings(sub, k):
            recency = 0.6 + 0.4 * (s.i / max(n - 1, 1))
            raw.append((s.price, w * recency, f"swing {tf}"))

    d1 = frames.get("D1")
    if d1 is not None and len(d1) >= 2:
        prev = d1.iloc[-2]
        raw += [(prev.h, 2.4, "máx. dia anterior"), (prev.l, 2.4, "mín. dia anterior"),
                (prev.c, 1.0, "fech. dia anterior"), (d1.o.iloc[-1], 1.0, "abertura do dia")]
        p = (prev.h + prev.l + prev.c) / 3
        raw += [(p, 1.3, "pivot P"), (2 * p - prev.l, 1.1, "pivot R1"), (2 * p - prev.h, 1.1, "pivot S1"),
                (p + (prev.h - prev.l), 0.9, "pivot R2"), (p - (prev.h - prev.l), 0.9, "pivot S2")]
    w1 = frames.get("W1")
    if w1 is not None and len(w1) >= 2:
        pw = w1.iloc[-2]
        raw += [(pw.h, 3.0, "máx. semana anterior"), (pw.l, 3.0, "mín. semana anterior"),
                (w1.o.iloc[-1], 1.4, "abertura semanal")]

    atr_d = _atr_last(d1) if d1 is not None else price * 0.006
    raw += _round_levels(price, round_step, 3 * atr_d)
    return raw


def _atr_last(df: pd.DataFrame, n: int = 14) -> float:
    pc = df.c.shift()
    tr = pd.concat([df.h - df.l, (df.h - pc).abs(), (df.l - pc).abs()], axis=1).max(axis=1)
    return float(tr.ewm(alpha=1 / n, adjust=False).mean().iloc[-1])


def cluster_levels(raw: list[tuple[float, float, str]], tol: float, min_strength: float = 1.5) -> list[Level]:
    """Greedy 1-D clustering into zones; strength = sum of weights (saturating)."""
    if not raw:
        return []
    pts = sorted(raw, key=lambda x: x[0])
    zones: list[list[tuple[float, float, str]]] = [[pts[0]]]
    for p in pts[1:]:
        cur = zones[-1]
        center = sum(x[0] * x[1] for x in cur) / sum(x[1] for x in cur)
        if abs(p[0] - center) <= tol:
            cur.append(p)
        else:
            zones.append([p])
    out = []
    for z in zones:
        wsum = sum(x[1] for x in z)
        price = sum(x[0] * x[1] for x in z) / wsum
        strength = 10 * (1 - np.exp(-wsum / 4))       # 0..10, saturates with confluence
        if strength >= min_strength:
            out.append(Level(float(price), float(strength), [x[2] for x in z]))
    return out


@dataclass
class LevelMap:
    levels: list[Level]
    support: Level | None        # nearest meaningful zone below price
    resistance: Level | None     # nearest meaningful zone above price

    def above(self, price: float, min_strength: float = 3.0) -> list[Level]:
        return sorted([lv for lv in self.levels if lv.price > price and lv.strength >= min_strength],
                      key=lambda lv: lv.price)

    def below(self, price: float, min_strength: float = 3.0) -> list[Level]:
        return sorted([lv for lv in self.levels if lv.price < price and lv.strength >= min_strength],
                      key=lambda lv: -lv.price)


def level_map(frames: dict[str, pd.DataFrame], price: float, round_step: float, atr_h1: float) -> LevelMap:
    d1 = frames.get("D1")
    atr_d = _atr_last(d1) if d1 is not None and len(d1) > 15 else atr_h1 * 4
    tol = max(0.12 * atr_d, 0.35 * atr_h1)
    lv = cluster_levels(collect_levels(frames, price, round_step), tol)
    gap = 0.15 * atr_h1
    above = [x for x in lv if x.price > price + gap and x.strength >= 3.0]
    below = [x for x in lv if x.price < price - gap and x.strength >= 3.0]
    res = min(above, key=lambda x: x.price) if above else None
    sup = max(below, key=lambda x: x.price) if below else None
    return LevelMap(lv, sup, res)

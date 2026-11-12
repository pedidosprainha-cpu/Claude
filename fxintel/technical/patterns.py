"""Padrões de candles, compressão, rompimento/rejeição e divergências (causais)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import candle_parts
from .structure import Swing


def candle_patterns(df: pd.DataFrame, atr: pd.Series) -> pd.DataFrame:
    p = candle_parts(df)
    o, c = df["o"], df["c"]
    po, pc = o.shift(), c.shift()
    bull_engulf = (c > o) & (pc < po) & (c >= po) & (o <= pc) & (p["body"] > 0.5 * atr)
    bear_engulf = (c < o) & (pc > po) & (c <= po) & (o >= pc) & (p["body"] > 0.5 * atr)
    # pin bar / rejeição: pavio >= 2x corpo e >= 55% da faixa
    bull_pin = (p["lower"] >= 2 * p["body"]) & (p["lower_ratio"] >= 0.55) & (p["range"] >= 0.6 * atr)
    bear_pin = (p["upper"] >= 2 * p["body"]) & (p["upper_ratio"] >= 0.55) & (p["range"] >= 0.6 * atr)
    inside = (df["h"] <= df["h"].shift()) & (df["l"] >= df["l"].shift())
    doji = p["body_ratio"] <= 0.1
    # compressão: faixa média de 5 barras < 60% da faixa média de 50 barras
    rng = df["h"] - df["l"]
    compression = rng.rolling(5).mean() / rng.rolling(50).mean()
    return pd.DataFrame({
        "bull_engulf": bull_engulf.astype(np.int8), "bear_engulf": bear_engulf.astype(np.int8),
        "bull_pin": bull_pin.astype(np.int8), "bear_pin": bear_pin.astype(np.int8),
        "inside": inside.astype(np.int8), "doji": doji.astype(np.int8),
        "compression": compression, "close_pos": (df["c"] - df["l"]) / p["range"],
    }, index=df.index)


def rsi_divergence(swings: list[Swing], rsi: pd.Series, n: int, persist: int = 10) -> pd.Series:
    """+1 divergência de alta (preço LL, RSI HL); -1 de baixa (preço HH, RSI LH).

    Sinal passa a valer na barra de confirmação do segundo swing e persiste por `persist` barras.
    """
    out = np.zeros(n, dtype=np.int8)
    r = rsi.to_numpy()
    lows = [s for s in swings if s.kind == "L"]
    highs = [s for s in swings if s.kind == "H"]
    for seq, sign in ((lows, 1), (highs, -1)):
        for a, b in zip(seq, seq[1:]):
            if b.idx - a.idx > 60 or not (np.isfinite(r[a.idx]) and np.isfinite(r[b.idx])):
                continue
            if sign == 1 and b.price < a.price and r[b.idx] > r[a.idx] + 2:
                out[b.confirm_idx:b.confirm_idx + persist] = 1
            if sign == -1 and b.price > a.price and r[b.idx] < r[a.idx] - 2:
                out[b.confirm_idx:b.confirm_idx + persist] = -1
    return pd.Series(out, index=rsi.index)


def breakout_state(df: pd.DataFrame, atr: pd.Series, n: int = 20) -> pd.DataFrame:
    """Rompimento do canal de Donchian anterior e falso rompimento (retorno em até 3 barras)."""
    hi = df["h"].rolling(n).max().shift()
    lo = df["l"].rolling(n).min().shift()
    up = (df["c"] > hi).astype(np.int8)
    dn = (df["c"] < lo).astype(np.int8)
    # falso rompimento: rompeu nas últimas 3 barras e fechou de volta dentro do canal
    recent_up = up.rolling(3, min_periods=1).max().shift().fillna(0)
    recent_dn = dn.rolling(3, min_periods=1).max().shift().fillna(0)
    fail_up = ((recent_up > 0) & (df["c"] < hi)).astype(np.int8)
    fail_dn = ((recent_dn > 0) & (df["c"] > lo)).astype(np.int8)
    return pd.DataFrame({"brk_up": up, "brk_dn": dn, "fail_up": fail_up, "fail_dn": fail_dn,
                         "don_hi": hi, "don_lo": lo}, index=df.index)

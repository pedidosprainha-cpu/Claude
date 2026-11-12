"""Vectorised technical indicators (pandas/numpy). Frames use columns o,h,l,c."""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def wilder(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1 / n, adjust=False).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    h, l, c = df.h.to_numpy(float), df.l.to_numpy(float), df.c.to_numpy(float)
    pc = np.r_[np.nan, c[:-1]]
    with np.errstate(invalid="ignore"):
        tr = np.fmax(h - l, np.fmax(np.abs(h - pc), np.abs(l - pc)))   # fmax skips NaN like max(axis=1)
    return pd.Series(tr, index=df.index)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return wilder(true_range(df), n)


def rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    up = wilder(d.clip(lower=0), n).to_numpy()
    dn = wilder((-d).clip(lower=0), n).to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        out = 100 - 100 / (1 + up / np.where(dn == 0, np.nan, dn))
    out = np.where(dn != 0, out, 100.0)                  # no losses -> 100 (NaN rows stay 100 as before)
    out = np.where((up == 0) & (dn == 0), 50.0, out)     # flat -> 50
    return pd.Series(out, index=c.index)


def macd(c: pd.Series, fast: int = 12, slow: int = 26, sig: int = 9):
    line = ema(c, fast) - ema(c, slow)
    signal = ema(line, sig)
    return line, signal, line - signal


def adx(df: pd.DataFrame, n: int = 14):
    up = df.h.diff()
    dn = -df.l.diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    tr = wilder(true_range(df), n).replace(0, np.nan)
    pdi = 100 * wilder(plus, n) / tr
    mdi = 100 * wilder(minus, n) / tr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return wilder(dx.fillna(0), n), pdi.fillna(0), mdi.fillna(0)


def bollinger(c: pd.Series, n: int = 20, k: float = 2.0):
    mid = sma(c, n)
    sd = c.rolling(n).std(ddof=0)
    return mid - k * sd, mid, mid + k * sd


def keltner(df: pd.DataFrame, n: int = 20, k: float = 1.5):
    mid = ema(df.c, n)
    a = atr(df, n)
    return mid - k * a, mid, mid + k * a


def stochastic(df: pd.DataFrame, n: int = 14, d: int = 3, smooth: int = 3):
    lo = df.l.rolling(n).min()
    hi = df.h.rolling(n).max()
    k = 100 * (df.c - lo) / (hi - lo).replace(0, np.nan)
    k = k.rolling(smooth).mean()
    return k, k.rolling(d).mean()


def donchian(df: pd.DataFrame, n: int = 20):
    return df.l.rolling(n).min(), df.h.rolling(n).max()


def supertrend(df: pd.DataFrame, n: int = 10, mult: float = 3.0) -> pd.Series:
    """Direction series (+1 up / -1 down) of the classic SuperTrend."""
    a = atr(df, n).to_numpy()
    hl2 = ((df.h + df.l) / 2).to_numpy()
    c = df.c.to_numpy()
    upper = hl2 + mult * a
    lower = hl2 - mult * a
    fu, fl = upper.copy(), lower.copy()
    d = np.ones(len(c))
    for i in range(1, len(c)):
        fu[i] = upper[i] if (upper[i] < fu[i - 1] or c[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lower[i] if (lower[i] > fl[i - 1] or c[i - 1] < fl[i - 1]) else fl[i - 1]
        if d[i - 1] == 1:
            d[i] = -1 if c[i] < fl[i] else 1
        else:
            d[i] = 1 if c[i] > fu[i] else -1
    return pd.Series(d, index=df.index)


def ichimoku(df: pd.DataFrame, t: int = 9, k: int = 26, s: int = 52):
    tenkan = (df.h.rolling(t).max() + df.l.rolling(t).min()) / 2
    kijun = (df.h.rolling(k).max() + df.l.rolling(k).min()) / 2
    span_a = ((tenkan + kijun) / 2).shift(k)
    span_b = ((df.h.rolling(s).max() + df.l.rolling(s).min()) / 2).shift(k)
    return tenkan, kijun, span_a, span_b


def efficiency_ratio(c: pd.Series, n: int = 20) -> pd.Series:
    """Kaufman ER: |net move| / path length. 1 = straight line, 0 = noise."""
    net = (c - c.shift(n)).abs()
    path = c.diff().abs().rolling(n).sum()
    return net / path.replace(0, np.nan)


def linreg(c: pd.Series, n: int = 20) -> tuple[float, float]:
    """(slope per bar, R^2) of the last n closes."""
    y = c.iloc[-n:].to_numpy()
    if len(y) < 3:
        return 0.0, 0.0
    x = np.arange(len(y))
    slope, icpt = np.polyfit(x, y, 1)
    fit = slope * x + icpt
    ss_res = float(((y - fit) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return float(slope), (1 - ss_res / ss_tot) if ss_tot > 0 else 0.0


def resample(df: pd.DataFrame, rule: str, offset: str | None = None) -> pd.DataFrame:
    agg = {"o": "first", "h": "max", "l": "min", "c": "last", "v": "sum"}
    cols = {k: v for k, v in agg.items() if k in df.columns}
    out = df.resample(rule, offset=offset).agg(cols) if offset else df.resample(rule).agg(cols)
    return out.dropna(subset=["c"])


def ny_daily(h1: pd.DataFrame) -> pd.DataFrame:
    """FX trading days that close at 17:00 New York (handles DST and the Sunday stub)."""
    ny = h1.index.tz_convert("America/New_York")
    day = (ny + pd.Timedelta(hours=7)).normalize().tz_localize(None)
    g = h1.groupby(day)
    out = pd.DataFrame({"o": g.o.first(), "h": g.h.max(), "l": g.l.min(), "c": g.c.last()})
    # Sunday-evening bars belong to Monday's session (already true via +7h shift).
    out = out[out.index.dayofweek < 5]
    return out

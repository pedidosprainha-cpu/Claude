"""Technical indicators on numpy arrays. All are causal (bar i uses bars <= i)."""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


def _recursive(x: np.ndarray, alpha: float) -> np.ndarray:
    out = np.empty(len(x), dtype=float)
    if len(x) == 0:
        return out
    prev = float(x[0])
    out[0] = prev
    xs = x.tolist()
    for i in range(1, len(xs)):
        prev += alpha * (xs[i] - prev)
        out[i] = prev
    return out


def ema(x, n: int) -> np.ndarray:
    return _recursive(np.asarray(x, dtype=float), 2.0 / (n + 1.0))


def rma(x, n: int) -> np.ndarray:
    """Wilder's smoothing (used by ATR, RSI, ADX)."""
    return _recursive(np.asarray(x, dtype=float), 1.0 / n)


def true_range(h, l, c) -> np.ndarray:
    h, l, c = (np.asarray(a, dtype=float) for a in (h, l, c))
    pc = np.empty_like(c)
    pc[0] = c[0]
    pc[1:] = c[:-1]
    return np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))


def atr(h, l, c, n: int = 14) -> np.ndarray:
    return rma(true_range(h, l, c), n)


def rsi(c, n: int = 14) -> np.ndarray:
    c = np.asarray(c, dtype=float)
    d = np.diff(c, prepend=c[0])
    up = rma(np.clip(d, 0, None), n)
    dn = rma(np.clip(-d, 0, None), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = up / dn
        out = 100.0 - 100.0 / (1.0 + rs)
    out[dn == 0] = np.where(up[dn == 0] > 0, 100.0, 50.0)
    return out


def adx(h, l, c, n: int = 14):
    """Returns (adx, +DI, -DI)."""
    h, l, c = (np.asarray(a, dtype=float) for a in (h, l, c))
    up = np.diff(h, prepend=h[0])
    dn = -np.diff(l, prepend=l[0])
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = rma(true_range(h, l, c), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100.0 * rma(plus, n) / tr
        mdi = 100.0 * rma(minus, n) / tr
        dx = 100.0 * np.abs(pdi - mdi) / (pdi + mdi)
    pdi, mdi, dx = (np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0) for a in (pdi, mdi, dx))
    return rma(dx, n), pdi, mdi


def macd_hist(c, fast: int = 12, slow: int = 26, signal: int = 9) -> np.ndarray:
    line = ema(c, fast) - ema(c, slow)
    return line - ema(line, signal)


def _rolling(x, n: int, fn) -> np.ndarray:
    """Rolling reduction including the current bar; expanding during warm-up."""
    x = np.asarray(x, dtype=float)
    out = np.empty(len(x), dtype=float)
    if len(x) == 0:
        return out
    n = max(1, int(n))
    k = min(n - 1, len(x))
    for i in range(k):
        out[i] = fn(x[: i + 1])
    if len(x) >= n:
        out[n - 1:] = fn(sliding_window_view(x, n), axis=1)
    return out


def rolling_max(x, n: int) -> np.ndarray:
    return _rolling(x, n, np.max)


def rolling_min(x, n: int) -> np.ndarray:
    return _rolling(x, n, np.min)


def shift(x, k: int = 1) -> np.ndarray:
    """Value k bars ago (first k entries repeat the first value)."""
    x = np.asarray(x)
    if k <= 0 or len(x) == 0:
        return x.copy()
    out = np.empty_like(x)
    out[:k] = x[0]
    out[k:] = x[:-k]
    return out

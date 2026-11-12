"""Indicadores técnicos vetorizados e causais (cada valor em t usa apenas dados até t)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    pc = df["c"].shift()
    return pd.concat([df["h"] - df["l"], (df["h"] - pc).abs(), (df["l"] - pc).abs()], axis=1).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return true_range(df).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = up / dn.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.fillna(100.0).where(dn.notna())


def macd(c: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    line = ema(c, fast) - ema(c, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return line, sig, line - sig


def adx(df: pd.DataFrame, n: int = 14):
    up = df["h"].diff()
    dn = -df["l"].diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    a = atr(df, n)
    pdi = 100 * plus.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / a
    mdi = 100 * minus.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / a
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False, min_periods=n).mean(), pdi, mdi


def bollinger(c: pd.Series, n: int = 20, k: float = 2.0):
    m = sma(c, n)
    sd = c.rolling(n, min_periods=n).std(ddof=0)
    return m, m + k * sd, m - k * sd


def stochastic(df: pd.DataFrame, n: int = 14, d: int = 3):
    lo = df["l"].rolling(n, min_periods=n).min()
    hi = df["h"].rolling(n, min_periods=n).max()
    k = 100 * (df["c"] - lo) / (hi - lo).replace(0, np.nan)
    return k, k.rolling(d).mean()


def efficiency_ratio(c: pd.Series, n: int = 20) -> pd.Series:
    """Kaufman: |deslocamento líquido| / soma dos deslocamentos. ~1 tendência limpa, ~0 ruído."""
    net = (c - c.shift(n)).abs()
    path = c.diff().abs().rolling(n, min_periods=n).sum()
    return net / path.replace(0, np.nan)


def donchian(df: pd.DataFrame, n: int = 20):
    return df["h"].rolling(n, min_periods=n).max(), df["l"].rolling(n, min_periods=n).min()


def realized_vol(c: pd.Series, n: int = 24) -> pd.Series:
    return np.log(c).diff().rolling(n, min_periods=n).std()


def vwap_session(df: pd.DataFrame, anchor_hour: int = 22) -> pd.Series | None:
    """VWAP ancorado na abertura do pregão (22:00 UTC). Requer volume real; senão None."""
    if "v" not in df or (df["v"] <= 0).mean() > 0.2:
        return None
    tp = (df["h"] + df["l"] + df["c"]) / 3
    day = (df.index - pd.Timedelta(hours=anchor_hour)).floor("1D")
    pv = (tp * df["v"]).groupby(day).cumsum()
    vv = df["v"].groupby(day).cumsum()
    return pv / vv.replace(0, np.nan)


def rolling_percentile(s: pd.Series, n: int = 500) -> pd.Series:
    """Percentil do valor atual dentro da janela móvel (0..1), causal."""
    def pct(x: np.ndarray) -> float:
        return (x[:-1] < x[-1]).mean() if len(x) > 1 else np.nan
    return s.rolling(n, min_periods=max(50, n // 5)).apply(pct, raw=True)


def robust_z(s: pd.Series, n: int = 500) -> pd.Series:
    """z-score robusto (mediana/MAD) causal."""
    med = s.rolling(n, min_periods=max(50, n // 5)).median()
    mad = (s - med).abs().rolling(n, min_periods=max(50, n // 5)).median()
    return (s - med) / (1.4826 * mad.replace(0, np.nan))


def candle_parts(df: pd.DataFrame) -> pd.DataFrame:
    body = (df["c"] - df["o"]).abs()
    rng = (df["h"] - df["l"]).replace(0, np.nan)
    upper = df["h"] - df[["o", "c"]].max(axis=1)
    lower = df[["o", "c"]].min(axis=1) - df["l"]
    return pd.DataFrame({"body": body, "range": rng, "upper": upper, "lower": lower,
                         "body_ratio": body / rng, "upper_ratio": upper / rng,
                         "lower_ratio": lower / rng, "bull": df["c"] > df["o"]}, index=df.index)


def compute_basic(df: pd.DataFrame) -> pd.DataFrame:
    """Conjunto padrão de indicadores para um timeframe."""
    c = df["c"]
    out = pd.DataFrame(index=df.index)
    for n in (8, 20, 50, 200):
        out[f"ema{n}"] = ema(c, n)
    out["atr"] = atr(df, 14)
    out["rsi"] = rsi(c, 14)
    line, sig, hist = macd(c)
    out["macd"], out["macd_sig"], out["macd_hist"] = line, sig, hist
    a, pdi, mdi = adx(df, 14)
    out["adx"], out["pdi"], out["mdi"] = a, pdi, mdi
    m, up, lo = bollinger(c)
    out["bb_mid"], out["bb_up"], out["bb_lo"] = m, up, lo
    out["bb_width"] = (up - lo) / m
    out["er"] = efficiency_ratio(c, 20)
    k, d = stochastic(df)
    out["stoch_k"], out["stoch_d"] = k, d
    out["atr_fast"] = atr(df, 5)
    out["atr_slow"] = atr(df, 50)
    v = vwap_session(df)
    out["vwap"] = v if v is not None else np.nan
    return out

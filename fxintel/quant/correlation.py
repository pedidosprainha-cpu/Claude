"""Correlações entre instrumentos e risco de concentração direcional."""
from __future__ import annotations

import numpy as np
import pandas as pd


def returns_matrix(closes: dict[str, pd.Series], bars: int = 480) -> pd.DataFrame:
    df = pd.DataFrame({s: c for s, c in closes.items()}).sort_index().ffill()
    return np.log(df).diff().iloc[-bars:].dropna(how="all")


def correlation_matrix(closes: dict[str, pd.Series], bars: int = 480) -> pd.DataFrame:
    """Correlação de Spearman (robusta a caudas) dos retornos H1 das últimas `bars` barras."""
    r = returns_matrix(closes, bars)
    return r.corr(method="spearman", min_periods=100)


def directional_correlation(corr: pd.DataFrame, a: str, dir_a: int, b: str, dir_b: int) -> float:
    """Correlação das *posições* (considera direção): >0 indica exposição redundante."""
    if a not in corr.index or b not in corr.columns:
        return 0.0
    v = corr.loc[a, b]
    return float(v * dir_a * dir_b) if np.isfinite(v) else 0.0


def top_pairs(corr: pd.DataFrame, k: int = 10) -> list[dict]:
    out = []
    cols = list(corr.columns)
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            v = corr.loc[a, b]
            if np.isfinite(v):
                out.append({"a": a, "b": b, "corr": round(float(v), 3)})
    out.sort(key=lambda d: -abs(d["corr"]))
    return out[:k]

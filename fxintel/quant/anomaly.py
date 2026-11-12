"""Detecção de anomalias de mercado e de qualidade de dados."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..technical.indicators import robust_z


def market_anomalies(f: pd.DataFrame, max_z: float = 5.0) -> dict:
    rng = (f["h"] - f["l"]) / f["c"]
    zr = robust_z(rng, 500)
    zret = robust_z(f["ret1"].abs(), 500)
    zr_last = float(zr.iloc[-1]) if np.isfinite(zr.iloc[-1]) else 0.0
    zret_last = float(zret.iloc[-1]) if np.isfinite(zret.iloc[-1]) else 0.0
    flags = []
    if zr_last > max_z:
        flags.append(f"Faixa do último candle H1 anormal (z robusto {zr_last:.1f})")
    if zret_last > max_z:
        flags.append(f"Retorno do último candle H1 anormal (z robusto {zret_last:.1f})")
    recent_z = zr.iloc[-6:].max()
    if np.isfinite(recent_z) and recent_z > max_z * 1.4:
        flags.append(f"Pico de volatilidade nas últimas 6 horas (z {recent_z:.1f})")
    return {"range_z": round(zr_last, 2), "return_z": round(zret_last, 2), "flags": flags,
            "anomalous": bool(flags)}


def data_quality(h1: pd.DataFrame, quote_mid: float | None, atr: float, bar_age_min: float,
                 max_bar_age_min: float) -> dict:
    issues = []
    if bar_age_min > max_bar_age_min:
        issues.append(f"Último candle H1 com {bar_age_min:.0f} min de idade (limite {max_bar_age_min})")
    tail = h1.iloc[-24:]
    flat = float(((tail["h"] - tail["l"]) <= 0).mean()) if len(tail) else 1.0
    if flat > 0.3:
        issues.append(f"{flat:.0%} dos últimos candles sem variação (feed congelado?)")
    if quote_mid and np.isfinite(atr) and atr > 0:
        gap = abs(quote_mid - float(h1["c"].iloc[-1])) / atr
        if gap > 3:
            issues.append(f"Divergência cotação vs. último fechamento de {gap:.1f} ATR")
    return {"ok": not issues, "issues": issues, "flat_ratio": round(flat, 3)}

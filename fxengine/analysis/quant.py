"""Quantitative layer: regime detection, time-series momentum, mean-reversion
z-scores and volatility state."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import indicators as ta


def hurst(log_price: np.ndarray, max_lag: int = 64) -> float:
    """Hurst exponent from the scaling of lagged-difference dispersion.
    ~0.5 random walk, >0.5 persistent (trending), <0.5 anti-persistent (mean-reverting)."""
    x = np.asarray(log_price, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < max_lag * 4:
        return 0.5
    lags = np.unique(np.logspace(np.log10(2), np.log10(max_lag), 14).astype(int))
    tau = [np.std(x[lag:] - x[:-lag]) for lag in lags]
    tau = np.asarray(tau)
    ok = tau > 0
    if ok.sum() < 4:
        return 0.5
    slope = np.polyfit(np.log(lags[ok]), np.log(tau[ok]), 1)[0]
    return float(np.clip(slope, 0.0, 1.0))


def variance_ratio(log_price: np.ndarray, q: int = 4) -> tuple[float, float]:
    """Lo-MacKinlay variance ratio VR(q) and its homoskedastic z-stat.
    VR>1 => positive autocorrelation (momentum), VR<1 => mean reversion."""
    x = np.asarray(log_price, dtype=float)
    r = np.diff(x)
    t = len(r)
    if t < q * 10:
        return 1.0, 0.0
    mu = r.mean()
    var1 = np.sum((r - mu) ** 2) / (t - 1)
    rq = x[q:] - x[:-q]
    m = q * (t - q + 1) * (1 - q / t)
    varq = np.sum((rq - q * mu) ** 2) / m
    vr = varq / var1 if var1 > 0 else 1.0
    z = (vr - 1) / np.sqrt(2 * (2 * q - 1) * (q - 1) / (3 * q * t))
    return float(vr), float(z)


@dataclass
class QuantResult:
    regime: str             # "tendência" | "reversão à média" | "aleatório"
    hurst: float
    vr: float
    vr_z: float
    er: float
    tsmom: float            # -1..1 vol-adjusted multi-horizon momentum
    mr_z: float             # price z-score vs 20-bar H1 mean
    vol_pct: float          # realized-vol percentile (0..100) vs 1y
    vol_ann: float          # annualised realized vol (%)
    autocorr: float
    score: float            # -100..100 directional quant signal
    notes: list[str]


def analyze(frames: dict[str, pd.DataFrame]) -> QuantResult:
    h1, d1 = frames["H1"], frames["D1"]
    lp = np.log(h1.c.to_numpy()[-1500:])
    H = hurst(lp)
    vr, vz = variance_ratio(lp, 4)
    er = float(ta.efficiency_ratio(h1.c, 30).iloc[-1])
    adx_h1 = float(ta.adx(h1)[0].iloc[-1])
    r1 = np.diff(lp)
    ac = float(np.corrcoef(r1[:-1], r1[1:])[0, 1]) if len(r1) > 50 else 0.0

    trend_votes = (H > 0.53) + (vz > 1.5) + (er > 0.35) + (adx_h1 > 25)
    mr_votes = (H < 0.47) + (vz < -1.5) + (er < 0.15) + (adx_h1 < 17)
    regime = "tendência" if trend_votes >= 2 and trend_votes > mr_votes else (
        "reversão à média" if mr_votes >= 2 and mr_votes > trend_votes else "aleatório")

    # --- time-series momentum on daily closes, vol-scaled (Moskowitz-Ooi-Pedersen style)
    dc = d1.c
    dr = np.log(dc).diff().dropna()
    sig_d = float(dr.iloc[-60:].std()) if len(dr) > 20 else np.nan
    ts_parts = []
    for n, w in ((1, 0.15), (5, 0.30), (20, 0.35), (60, 0.20)):
        if len(dc) > n + 1 and sig_d and np.isfinite(sig_d):
            z = np.log(dc.iloc[-1] / dc.iloc[-1 - n]) / (sig_d * np.sqrt(n))
            ts_parts.append((w, float(np.tanh(z / 1.2))))
    tsmom = sum(w * v for w, v in ts_parts) / max(sum(w for w, _ in ts_parts), 1e-9)

    # --- mean-reversion z (H1)
    m = h1.c.rolling(20).mean().iloc[-1]
    s = h1.c.rolling(20).std(ddof=0).iloc[-1]
    mr_z = float((h1.c.iloc[-1] - m) / s) if s > 0 else 0.0

    # --- volatility state
    hr = np.log(h1.c).diff()
    rv = hr.rolling(24).std() * np.sqrt(24 * 260)
    vol_ann = float(rv.iloc[-1] * 100) if np.isfinite(rv.iloc[-1]) else 0.0
    vol_pct = float(rv.iloc[-2000:].rank(pct=True).iloc[-1] * 100) if rv.notna().sum() > 50 else 50.0

    notes = [f"regime {regime} (Hurst {H:.2f}, VR(4) {vr:.2f} z={vz:+.1f}, ER {er:.2f}, ADX-H1 {adx_h1:.0f})"]
    if regime == "tendência":
        score = 100 * tsmom                      # persistent regime: follow momentum
    elif regime == "reversão à média":
        score = 100 * (0.35 * tsmom + 0.65 * float(np.tanh(-mr_z / 1.5)))
        if abs(mr_z) > 1.5:
            notes.append(f"preço a {mr_z:+.1f}σ da média H1: reversão favorecida")
    else:
        score = 100 * (0.7 * tsmom + 0.3 * float(np.tanh(-mr_z / 2.5)))
    if vol_pct > 90:
        notes.append(f"volatilidade realizada no percentil {vol_pct:.0f} (reduzir tamanho)")
    elif vol_pct < 12:
        notes.append(f"volatilidade comprimida (percentil {vol_pct:.0f}): expansão provável")
    return QuantResult(regime, H, vr, vz, er, float(tsmom), mr_z, vol_pct, vol_ann, ac,
                       float(np.clip(score, -100, 100)), notes)

"""Identificação de regimes de mercado (volatilidade e tendência) e mudanças de regime."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler


def rule_regime(row: pd.Series) -> dict:
    """Regime explicável a partir de percentil de ATR, ADX e eficiência direcional."""
    pct = row.get("atr_pct", np.nan)
    adx = row.get("adx", np.nan)
    er = row.get("er", np.nan)
    shock = row.get("atr_fast", np.nan) / row.get("atr_slow", np.nan) if row.get("atr_slow", 0) else np.nan
    if not np.isfinite(pct):
        vol = "desconhecida"
    elif pct >= 0.95:
        vol = "extrema"
    elif pct >= 0.75:
        vol = "alta"
    elif pct <= 0.25:
        vol = "baixa"
    else:
        vol = "normal"
    if np.isfinite(adx) and np.isfinite(er) and adx >= 22 and er >= 0.30:
        trend = "tendência"
    elif np.isfinite(adx) and np.isfinite(er) and adx < 18 and er < 0.20:
        trend = "lateral"
    else:
        trend = "transição"
    shocked = bool(np.isfinite(shock) and shock >= 2.0)
    return {"volatility": vol, "trend": trend, "vol_shock": shocked,
            "atr_percentile": None if not np.isfinite(pct) else round(float(pct), 3),
            "short_long_vol_ratio": None if not np.isfinite(shock) else round(float(shock), 2),
            "label": f"{trend} / volatilidade {vol}" + (" / CHOQUE de volatilidade" if shocked else "")}


class StatisticalRegime:
    """Mistura gaussiana (3 estados) sobre [log vol, eficiência, ADX], ordenada por volatilidade."""

    def __init__(self, n_states: int = 3, seed: int = 11):
        self.n = n_states
        self.seed = seed
        self.scaler = StandardScaler()
        self.gmm: GaussianMixture | None = None
        self.order: np.ndarray | None = None

    @staticmethod
    def _x(f: pd.DataFrame) -> pd.DataFrame:
        x = pd.DataFrame({"lv": np.log((f["atr"] / f["c"]).clip(lower=1e-9)), "er": f["er"], "adx": f["adx"]})
        return x.replace([np.inf, -np.inf], np.nan).dropna()

    def fit(self, f: pd.DataFrame) -> "StatisticalRegime":
        x = self._x(f)
        if len(x) < 300:
            return self
        z = self.scaler.fit_transform(x)
        self.gmm = GaussianMixture(self.n, covariance_type="full", random_state=self.seed).fit(z)
        lv_means = self.scaler.inverse_transform(self.gmm.means_)[:, 0]
        self.order = np.argsort(lv_means)
        return self

    def current(self, f: pd.DataFrame) -> dict | None:
        if self.gmm is None:
            return None
        x = self._x(f.iloc[-50:])
        if x.empty:
            return None
        p = self.gmm.predict_proba(self.scaler.transform(x.iloc[[-1]]))[0]
        p = p[self.order]
        names = ["calmo", "intermediário", "turbulento"][: self.n]
        k = int(np.argmax(p))
        # persistência do estado nas últimas 50 barras
        seq = self.gmm.predict(self.scaler.transform(x))
        inv = {int(o): i for i, o in enumerate(self.order)}
        seq = np.array([inv[int(s)] for s in seq])
        run = 1
        for s in seq[::-1][1:]:
            if s == seq[-1]:
                run += 1
            else:
                break
        return {"state": names[k], "probabilities": {names[i]: round(float(p[i]), 3) for i in range(self.n)},
                "bars_in_state": run, "changed_recently": run <= 3}

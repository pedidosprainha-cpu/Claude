"""Cross-sectional currency strength meter built from all 28 FX crosses.

For each horizon, every pair's log return is volatility-normalised (z-score),
then each currency's strength is the mean z it shows across its 7 pairs
(+z when base, -z when quote). This removes the 'USD-centric' bias of looking
at a single pair and identifies the strong-vs-weak combinations."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..instruments import MAJORS

HORIZONS = (("4h", 4, 0.30), ("24h", 24, 0.40), ("5d", 120, 0.30))


@dataclass
class StrengthResult:
    scores: dict[str, float]                  # combined z-score per currency
    by_horizon: dict[str, dict[str, float]]
    metal_z: dict[str, float]                 # vol-normalised move of each metal vs USD

    @property
    def ranking(self) -> list[tuple[str, float]]:
        return sorted(self.scores.items(), key=lambda kv: -kv[1])

    def pair_score(self, base: str, quote: str) -> float:
        """-100..100: positive = base stronger than quote."""
        if base in self.metal_z:
            return float(np.tanh(self.metal_z[base] / 1.5) * 100)
        if base not in self.scores or quote not in self.scores:
            return 0.0
        return float(np.tanh((self.scores[base] - self.scores[quote]) / 1.5) * 100)


def _z_moves(c: pd.Series) -> dict[str, float]:
    lr = np.log(c.dropna())
    sig = lr.diff().iloc[-750:].std()
    out = {}
    for name, n, _ in HORIZONS:
        if len(lr) > n + 1 and sig > 0:
            out[name] = float((lr.iloc[-1] - lr.iloc[-1 - n]) / (sig * np.sqrt(n)))
        else:
            out[name] = 0.0
    return out


def compute(h1_by_symbol: dict[str, pd.DataFrame], metals: dict[str, pd.DataFrame] | None = None) -> StrengthResult:
    acc = {h: {c: [] for c in MAJORS} for h, _, _ in HORIZONS}
    for sym, df in h1_by_symbol.items():
        base, quote = sym[:3], sym[3:]
        if base not in MAJORS or quote not in MAJORS:
            continue
        z = _z_moves(df.c)
        for h in z:
            acc[h][base].append(z[h])
            acc[h][quote].append(-z[h])
    by_h = {h: {c: (float(np.mean(v)) if v else 0.0) for c, v in d.items()} for h, d in acc.items()}
    combined = {c: sum(w * by_h[h][c] for h, _, w in HORIZONS) for c in MAJORS}
    metal_z = {}
    for code, df in (metals or {}).items():
        z = _z_moves(df.c)
        metal_z[code] = sum(w * z[h] for h, _, w in HORIZONS)
    return StrengthResult(combined, by_h, metal_z)

"""Estatística para avaliação: intervalos de confiança, métricas de desempenho, PSR."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats as st


def wilson(k: int, n: int, z: float = 1.645) -> tuple[float, float]:
    """Intervalo de Wilson (90% por padrão) para uma proporção."""
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def bootstrap_mean_ci(x: np.ndarray, n_boot: int = 2000, alpha: float = 0.10, seed: int = 7) -> tuple[float, float]:
    x = np.asarray(x, dtype=float)
    if len(x) < 5:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = rng.choice(x, size=(n_boot, len(x)), replace=True).mean(axis=1)
    return (float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2)))


def max_drawdown(equity: np.ndarray) -> tuple[float, int]:
    """Drawdown máximo (fração) e duração máxima (em passos)."""
    e = np.asarray(equity, dtype=float)
    if len(e) == 0:
        return 0.0, 0
    peak = np.maximum.accumulate(e)
    dd = (e - peak) / peak
    dur, cur = 0, 0
    for v in dd:
        cur = cur + 1 if v < 0 else 0
        dur = max(dur, cur)
    return float(dd.min()), dur


def sharpe(returns: np.ndarray, periods: int = 252) -> float:
    r = np.asarray(returns, dtype=float)
    if len(r) < 2 or r.std(ddof=1) == 0:
        return float("nan")
    return float(r.mean() / r.std(ddof=1) * math.sqrt(periods))


def sortino(returns: np.ndarray, periods: int = 252) -> float:
    r = np.asarray(returns, dtype=float)
    dn = r[r < 0]
    if len(r) < 2 or len(dn) < 2 or dn.std(ddof=1) == 0:
        return float("nan")
    return float(r.mean() / math.sqrt((dn ** 2).mean()) * math.sqrt(periods))


def probabilistic_sharpe(returns: np.ndarray, sr_benchmark: float = 0.0) -> float:
    """PSR (Bailey & López de Prado): P(SR verdadeiro > benchmark), por período (não anualizado)."""
    r = np.asarray(returns, dtype=float)
    n = len(r)
    if n < 10 or r.std(ddof=1) == 0:
        return float("nan")
    sr = r.mean() / r.std(ddof=1)
    sk = st.skew(r)
    ku = st.kurtosis(r, fisher=False)
    den = math.sqrt(max(1e-12, 1 - sk * sr + (ku - 1) / 4 * sr * sr))
    return float(st.norm.cdf((sr - sr_benchmark) * math.sqrt(n - 1) / den))


def expected_max_sharpe(n_trials: int, var_sr: float) -> float:
    """SR máximo esperado sob H0 após N tentativas (para o Deflated Sharpe Ratio)."""
    if n_trials <= 1:
        return 0.0
    g = 0.5772156649
    z1 = st.norm.ppf(1 - 1 / n_trials)
    z2 = st.norm.ppf(1 - 1 / (n_trials * math.e))
    return math.sqrt(var_sr) * ((1 - g) * z1 + g * z2)


def profit_factor(r: np.ndarray) -> float:
    r = np.asarray(r, dtype=float)
    gains, losses = r[r > 0].sum(), -r[r < 0].sum()
    return float(gains / losses) if losses > 0 else float("inf") if gains > 0 else float("nan")


def binomial_pvalue(k: int, n: int, p0: float) -> float:
    """P-valor unilateral de observar >= k acertos em n sob taxa p0."""
    if n == 0:
        return 1.0
    return float(st.binom.sf(k - 1, n, p0))


def t_test_mean(x: np.ndarray) -> tuple[float, float]:
    x = np.asarray(x, dtype=float)
    if len(x) < 3:
        return float("nan"), float("nan")
    t, p = st.ttest_1samp(x, 0.0)
    return float(t), float(p / 2 if t > 0 else 1 - p / 2)  # unilateral (média > 0)

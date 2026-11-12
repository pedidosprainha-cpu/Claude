"""Métricas de desempenho de estratégias (por trade e por curva de capital)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..quant import stats as S


def trade_metrics(r: np.ndarray) -> dict:
    r = np.asarray(r, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    if n == 0:
        return {"n": 0}
    lo, hi = S.bootstrap_mean_ci(r)
    t, p = S.t_test_mean(r)
    return {
        "n": n, "win_rate": float((r > 0).mean()), "avg_r": float(r.mean()),
        "median_r": float(np.median(r)), "std_r": float(r.std(ddof=1)) if n > 1 else float("nan"),
        "expectancy_ci90": [lo, hi], "t_stat": t, "p_value_mean_gt0": p,
        "profit_factor": S.profit_factor(r), "best_r": float(r.max()), "worst_r": float(r.min()),
        "sum_r": float(r.sum()),
    }


def equity_metrics(daily_equity: pd.Series, initial: float) -> dict:
    if daily_equity.empty:
        return {}
    eq = daily_equity.to_numpy(dtype=float)
    rets = np.diff(np.concatenate([[initial], eq])) / np.concatenate([[initial], eq[:-1]])
    days = max(1, (daily_equity.index[-1] - daily_equity.index[0]).days)
    total = eq[-1] / initial - 1
    cagr = (eq[-1] / initial) ** (365.25 / days) - 1 if eq[-1] > 0 else -1.0
    mdd, dur = S.max_drawdown(np.concatenate([[initial], eq]))
    x = np.arange(len(eq))
    y = np.log(np.maximum(eq, 1e-9))
    r2 = float(np.corrcoef(x, y)[0, 1] ** 2) if len(eq) > 2 and y.std() > 0 else float("nan")
    monthly = daily_equity.resample("ME").last()
    mret = monthly.pct_change()
    mret.iloc[0] = monthly.iloc[0] / initial - 1
    return {
        "total_return_pct": total * 100, "cagr_pct": cagr * 100, "max_drawdown_pct": mdd * 100,
        "max_dd_duration_days": dur, "sharpe": S.sharpe(rets), "sortino": S.sortino(rets),
        "calmar": (cagr / abs(mdd)) if mdd < 0 else float("nan"),
        "psr_vs_0": S.probabilistic_sharpe(rets), "equity_r2": r2,
        "pct_profitable_months": float((mret > 0).mean() * 100) if len(mret) else float("nan"),
        "monthly_returns_pct": {k.strftime("%Y-%m"): round(float(v) * 100, 2) for k, v in mret.items()},
        "days": days,
    }


def clean(obj):
    """Converte NaN/inf para None (JSON) recursivamente."""
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, (float, np.floating)):
        v = float(obj)
        return None if not math.isfinite(v) else v
    if isinstance(obj, (np.integer,)):
        return int(obj)
    return obj

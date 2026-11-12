"""Macro features per instrument, identical in the historical replay and in the live engine.

Each signed feature is the macro pressure for the PAIR TO GO UP (base stronger than quote),
built from the instrument's exposures (fxengine/analysis/fundamental.py betas):

  m_risk       risk appetite (VIX level/change, S&P momentum) x (risk beta base - quote)
  m_usd_yield  5-day change of the US 10y yield x USD side (USD quote -> pair down when yields rise)
  m_dxy        5-day dollar-index momentum x USD side
  m_oil        oil momentum x CAD side            m_copper  copper momentum x copper betas
  m_gold       gold momentum x AUD / metal side
  m_carry      policy-rate differential base - quote (BIS)
  m_traj       6-month policy-rate change, base - quote
  m_cot        speculative net positioning (% of open interest), base - quote (CFTC)
unsigned:
  vix_z        VIX vs its 1-year mean (stress regime)      vix_chg5   5-day VIX change

Daily inputs use only COMPLETED days (the day before the decision), so the live engine and
the replay see the same values.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .fundamental import COPPER_BETA, OIL_BETA, RISK_BETA

SIGNED = ["m_risk", "m_usd_yield", "m_dxy", "m_oil", "m_copper", "m_gold", "m_carry", "m_traj", "m_cot"]
UNSIGNED = ["vix_z", "vix_chg5"]
FEATURES = SIGNED + UNSIGNED
GOLD_BETA = {"AUD": 0.3, "XAU": 1.0, "XAG": 0.6}


def _mom(c: pd.Series, n: int = 5) -> pd.Series:
    r = np.log(c).diff()
    return (np.log(c) - np.log(c.shift(n))) / (r.rolling(60, min_periods=20).std() * np.sqrt(n))


def daily_table(d1: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Per-day macro state from the daily closes of the macro tickers (provider.MACRO_TICKERS)."""
    def close(name):
        df = d1.get(name)
        if df is None or df.empty:
            return None
        s = df.c.copy()
        s.index = pd.DatetimeIndex(s.index).tz_convert("UTC").normalize() if s.index.tz is not None else \
            pd.DatetimeIndex(s.index).normalize()
        return s[~s.index.duplicated(keep="last")]

    cols = {}
    vix = close("VIX")
    if vix is not None:
        m, sd = vix.rolling(252, min_periods=120).mean(), vix.rolling(252, min_periods=120).std()
        cols["vix_z"] = ((vix - m) / sd).clip(-4, 6)
        cols["vix_chg5"] = np.log(vix / vix.shift(5)).clip(-1, 1)
    for name, key in (("SPX_FUT", "spx_mom5"), ("DXY", "dxy_mom5"), ("OIL", "oil_mom5"),
                      ("COPPER", "copper_mom5"), ("GOLD_FUT", "gold_mom5")):
        c = close(name)
        if c is not None:
            cols[key] = _mom(c).clip(-4, 4)
    tnx = close("US10Y")
    if tnx is not None:
        cols["us10_chg5"] = (tnx - tnx.shift(5)).clip(-1.5, 1.5)        # percentage points
    t = pd.DataFrame(cols).sort_index()
    return t.ffill()


def _side(ccy: str, base: str, quote: str) -> int:
    return 1 if base == ccy else (-1 if quote == ccy else 0)


def pair_features(base: str, quote: str, day: pd.Series | dict | None, rates: dict | None = None,
                  cot: dict | None = None) -> dict:
    """Signed (pair-up pressure) and unsigned macro features for one instrument.

    day: one row of daily_table (last completed day); rates: {ccy: (rate, change_6m)};
    cot: {asset: net % of open interest}. Missing inputs give 0 (neutral)."""
    g = (lambda k: float(day.get(k, 0.0)) if day is not None and np.isfinite(day.get(k, np.nan)) else 0.0)  # noqa: E731
    risk_on = -0.5 * g("vix_z") - 0.5 * np.tanh(g("vix_chg5") * 4) + 0.5 * np.tanh(g("spx_mom5"))
    usd = _side("USD", base, quote)                    # +1 USD base, -1 USD quote (incl. metals)
    f = {
        "m_risk": float(np.clip(risk_on * (RISK_BETA.get(base, 0.0) - RISK_BETA.get(quote, 0.0)), -3, 3)),
        "m_usd_yield": float(usd * g("us10_chg5")),
        "m_dxy": float(usd * g("dxy_mom5")) / 2,
        "m_oil": float((OIL_BETA.get(base, 0.0) - OIL_BETA.get(quote, 0.0)) * g("oil_mom5")),
        "m_copper": float((COPPER_BETA.get(base, 0.0) - COPPER_BETA.get(quote, 0.0)) * g("copper_mom5")),
        "m_gold": float((GOLD_BETA.get(base, 0.0) - GOLD_BETA.get(quote, 0.0)) * g("gold_mom5")),
        "m_carry": 0.0, "m_traj": 0.0, "m_cot": 0.0,
        "vix_z": g("vix_z") / 2, "vix_chg5": g("vix_chg5"),
    }
    if rates:
        rb, rq = rates.get(base), rates.get(quote)
        if base in ("XAU", "XAG", "XPT", "XPD"):
            rb = (0.0, 0.0)                                     # metals pay no interest
        if rb is not None and rq is not None:
            f["m_carry"] = float(np.tanh((rb[0] - rq[0]) / 2.0))
            f["m_traj"] = float(np.tanh((rb[1] - rq[1]) / 0.5))
    if cot:
        cb, cq = cot.get(base), cot.get(quote)
        if cb is not None and cq is not None:
            f["m_cot"] = float(np.clip((cb - cq) / 50.0, -2, 2))
        elif cb is not None and quote == "USD":
            f["m_cot"] = float(np.clip(cb / 50.0, -2, 2))
    return f


def oriented(f: dict, d: int) -> dict:
    return {k: (v * d if k in SIGNED else v) for k, v in f.items()}

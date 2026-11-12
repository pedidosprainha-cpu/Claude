"""Intermercados, sentimento de risco e força relativa das moedas (séries point-in-time).

Todas as séries são alinhadas ao índice H1 pelo horário de *conclusão* das barras, para que
o modelo quantitativo use somente informação disponível no instante da decisão.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import instruments as I

# Sensibilidade ao sentimento de risco (beta qualitativo usado pela literatura de FX):
# moedas de commodities/carry ganham em risk-on; refúgios (JPY, CHF, ouro) em risk-off.
RISK_BETA = {"AUD": 1.0, "NZD": 1.0, "CAD": 0.5, "GBP": 0.3, "EUR": 0.1, "USD": -0.3,
             "CHF": -0.7, "JPY": -1.0, "XAU": -0.5, "XAG": 0.2}


def _align(series: pd.Series, index: pd.DatetimeIndex, max_gap_h: int = 80) -> pd.Series:
    s = series.copy()
    s.index = s.index + pd.Timedelta(hours=1)  # conclusão da barra H1
    left = pd.DataFrame({"_t": index + pd.Timedelta(hours=1)})
    right = pd.DataFrame({"_t": s.index, "v": s.to_numpy()}).sort_values("_t")
    m = pd.merge_asof(left, right, on="_t", direction="backward",
                      tolerance=pd.Timedelta(hours=max_gap_h))
    return pd.Series(m["v"].to_numpy(), index=index)


def _z(s: pd.Series, n: int = 500) -> pd.Series:
    sd = s.rolling(n, min_periods=100).std()
    return (s / sd.replace(0, np.nan)).clip(-4, 4)


def macro_features(macro: dict[str, pd.DataFrame], index: pd.DatetimeIndex) -> pd.DataFrame:
    """Features intermercado para cada barra H1 do índice dado."""
    out = pd.DataFrame(index=index)
    closes = {k: _align(v["c"], index) for k, v in macro.items() if v is not None and len(v)}
    if "DXY" in closes:
        lc = np.log(closes["DXY"])
        out["dxy_r24"] = _z(lc.diff(24))
        out["dxy_r120"] = _z(lc.diff(120))
    for k, col in (("US10Y", "us10y"), ("US5Y", "us5y")):
        if k in closes:
            out[f"{col}_d24"] = _z(closes[k].diff(24))
            out[f"{col}_d120"] = _z(closes[k].diff(120))
    if "US10Y" in closes and "US3M" in closes:
        out["curve_10y3m"] = closes["US10Y"] - closes["US3M"]
    if "VIX" in closes:
        v = closes["VIX"]
        out["vix_lvl"] = v
        out["vix_d24"] = _z(v.diff(24))
        out["vix_pct"] = v.rolling(1500, min_periods=200).rank(pct=True)
    if "SPX_FUT" in closes:
        lc = np.log(closes["SPX_FUT"])
        out["es_r24"] = _z(lc.diff(24))
        out["es_r120"] = _z(lc.diff(120))
    if "WTI" in closes:
        lc = np.log(closes["WTI"])
        out["wti_r24"] = _z(lc.diff(24))
        out["wti_r120"] = _z(lc.diff(120))
    parts = [c for c in ("es_r24",) if c in out] + [c for c in ("vix_d24",) if c in out]
    if parts:
        ro = out.get("es_r24", 0) - out.get("vix_d24", 0)
        out["risk_on"] = (ro / 2).clip(-3, 3)
    return out


def currency_strength(closes: dict[str, pd.Series], windows=(24, 120)) -> dict[int, pd.DataFrame]:
    """Medidor de força relativa: média dos log-retornos com sinal de cada moeda nos pares."""
    fx = {s: c for s, c in closes.items() if I.get(s).kind == "fx"}
    if not fx:
        return {}
    idx = None
    for c in fx.values():
        idx = c.index if idx is None else idx.union(c.index)
    lc = pd.DataFrame({s: np.log(c.reindex(idx).ffill()) for s, c in fx.items()})
    res = {}
    currencies = sorted({I.get(s).base for s in fx} | {I.get(s).quote for s in fx})
    for w in windows:
        r = lc.diff(w)
        r = r / r.rolling(500, min_periods=100).std().replace(0, np.nan)
        st = pd.DataFrame(index=idx)
        for cur in currencies:
            terms = []
            for s in fx:
                inst = I.get(s)
                if inst.base == cur:
                    terms.append(r[s])
                elif inst.quote == cur:
                    terms.append(-r[s])
            st[cur] = pd.concat(terms, axis=1).mean(axis=1) if terms else np.nan
        res[w] = st.sub(st.mean(axis=1), axis=0)  # centrado no cruzamento
    return res


def strength_diff(strength: dict[int, pd.DataFrame], inst: I.Instrument, index: pd.DatetimeIndex) -> pd.DataFrame:
    out = pd.DataFrame(index=index)
    for w, st in strength.items():
        st = st.reindex(index, method="ffill")
        b = st[inst.base] if inst.base in st else 0.0
        q = st[inst.quote] if inst.quote in st else 0.0
        if inst.kind == "metal":  # metal vs USD: usa apenas -força do USD
            b = 0.0
        out[f"str_diff_{w}"] = (b - q) if not isinstance(b - q, float) else np.nan
    return out


def macro_snapshot(mf: pd.DataFrame) -> dict:
    """Último valor de cada feature macro (para o score fundamental ao vivo)."""
    if mf.empty:
        return {}
    last = mf.ffill().iloc[-1]
    return {k: (float(v) if np.isfinite(v) else None) for k, v in last.items()}

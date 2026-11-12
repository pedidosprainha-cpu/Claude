"""Suportes/resistências, oferta/demanda, níveis de sessão e números redondos."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .structure import Swing


def trading_day(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Pregão de FX começa às 22:00 UTC (fechamento de NY)."""
    return (index + pd.Timedelta(hours=2)).floor("1D")


def session_levels(h1: pd.DataFrame) -> pd.DataFrame:
    """Máx/mín do pregão anterior, da semana anterior e da sessão asiática corrente (causal)."""
    day = trading_day(h1.index)
    g = h1.groupby(day)
    dh, dl = g["h"].max(), g["l"].min()
    prev_h = dh.shift(1).reindex(day).to_numpy()
    prev_l = dl.shift(1).reindex(day).to_numpy()
    week = (day - pd.to_timedelta(day.weekday, unit="D"))
    gw = h1.groupby(week)
    wh, wl = gw["h"].max(), gw["l"].min()
    pw_h = wh.shift(1).reindex(week).to_numpy()
    pw_l = wl.shift(1).reindex(week).to_numpy()
    # faixa asiática acumulada (22:00–07:00 UTC) do pregão corrente, até a barra atual
    hours = h1.index.hour
    asia = (hours >= 22) | (hours < 7)
    ah = h1["h"].where(asia).groupby(day).cummax()
    al = h1["l"].where(asia).groupby(day).cummin()
    ah = ah.groupby(day).ffill()
    al = al.groupby(day).ffill()
    # máx/mín do próprio pregão até a barra (inclusive)
    cur_h = h1["h"].groupby(day).cummax()
    cur_l = h1["l"].groupby(day).cummin()
    day_open = h1["o"].groupby(day).transform("first")
    return pd.DataFrame({"pdh": prev_h, "pdl": prev_l, "pwh": pw_h, "pwl": pw_l,
                         "asia_h": ah.to_numpy(), "asia_l": al.to_numpy(),
                         "day_h": cur_h.to_numpy(), "day_l": cur_l.to_numpy(),
                         "day_open": day_open.to_numpy()}, index=h1.index)


def round_step(symbol: str, price: float) -> float:
    if symbol == "XAUUSD":
        return 50.0
    if symbol == "XAGUSD":
        return 0.5
    if price > 50:  # pares JPY
        return 0.5
    return 0.005


def round_levels(symbol: str, price: float, n: int = 2) -> list[float]:
    step = round_step(symbol, price)
    base = np.floor(price / step) * step
    return [round(base + k * step, 6) for k in range(-n + 1, n + 1)]


def cluster_levels(swings: list[Swing], atr_value: float, price: float, tol_atr: float = 0.35,
                   max_age_bars: int | None = None, last_idx: int | None = None) -> list[dict]:
    """Agrupa swings próximos em níveis de S/R; força = nº de toques ponderado por recência."""
    if not swings or not np.isfinite(atr_value) or atr_value <= 0:
        return []
    pts = [s for s in swings if (max_age_bars is None or last_idx is None or last_idx - s.idx <= max_age_bars)]
    pts.sort(key=lambda s: s.price)
    tol = tol_atr * atr_value
    clusters: list[list[Swing]] = []
    for s in pts:
        if clusters and abs(s.price - np.mean([x.price for x in clusters[-1]])) <= tol:
            clusters[-1].append(s)
        else:
            clusters.append([s])
    out = []
    li = last_idx if last_idx is not None else max(s.idx for s in pts)
    for cl in clusters:
        lvl = float(np.mean([x.price for x in cl]))
        rec = max(x.idx for x in cl)
        strength = sum(1.0 / (1.0 + (li - x.idx) / 200.0) for x in cl)
        out.append({
            "price": lvl, "touches": len(cl), "strength": round(strength, 2),
            "kind": "resistência" if lvl > price else "suporte",
            "last_touch": cl[-1].time.isoformat(), "recent_idx": rec,
            "distance_atr": round((lvl - price) / atr_value, 2),
        })
    out.sort(key=lambda d: abs(d["price"] - price))
    return out


def supply_demand_zones(df: pd.DataFrame, atr: pd.Series, lookback: int = 400,
                        base_max: int = 3, depart_atr: float = 1.5) -> list[dict]:
    """Zonas de oferta/demanda: base curta (1–3 velas estreitas) seguida de saída forte.

    Uma zona permanece válida enquanto não for atravessada por fechamento.
    """
    sub = df.iloc[-lookback:]
    a = atr.iloc[-lookback:].to_numpy()
    o, h, lo, c = (sub[k].to_numpy() for k in ("o", "h", "l", "c"))
    n = len(sub)
    zones = []
    for t in range(base_max + 1, n - 1):
        if not np.isfinite(a[t]):
            continue
        move = c[t] - o[t]
        if abs(move) < depart_atr * a[t]:
            continue
        b0 = t - 1
        b1 = b0
        while b1 - 1 >= 0 and t - b1 < base_max and (h[b1 - 1] - lo[b1 - 1]) < 0.8 * a[t]:
            b1 -= 1
        top, bot = float(h[b1:b0 + 1].max()), float(lo[b1:b0 + 1].min())
        kind = "demanda" if move > 0 else "oferta"
        after_c = c[t + 1:]
        if kind == "demanda" and (after_c < bot).any():
            continue
        if kind == "oferta" and (after_c > top).any():
            continue
        zones.append({"kind": kind, "top": top, "bottom": bot, "time": sub.index[b1].isoformat(),
                      "departure_atr": round(abs(move) / a[t], 2)})
    return zones[-8:]

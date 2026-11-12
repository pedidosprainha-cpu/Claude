"""Conceitos de fluxo institucional (SMC): Fair Value Gaps, Order Blocks e deslocamento.

Implementação causal: zonas nascem na barra em que são observáveis e morrem quando
mitigadas/invalidadas; o estado por barra descreve apenas zonas ativas naquele instante.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def smc_frame(df: pd.DataFrame, atr: pd.Series, structure: pd.DataFrame,
              min_fvg_atr: float = 0.15, disp_atr: float = 1.2, max_zones: int = 25) -> pd.DataFrame:
    n = len(df)
    o = df["o"].to_numpy()
    h = df["h"].to_numpy()
    lo = df["l"].to_numpy()
    c = df["c"].to_numpy()
    a = atr.to_numpy()
    ev = structure["event"].to_numpy()

    cols = {k: np.full(n, np.nan) for k in (
        "fvg_bull_top", "fvg_bull_bot", "fvg_bear_top", "fvg_bear_bot",
        "ob_bull_top", "ob_bull_bot", "ob_bear_top", "ob_bear_bot")}
    flags = {k: np.zeros(n, dtype=np.int8) for k in (
        "in_fvg_bull", "in_fvg_bear", "in_ob_bull", "in_ob_bear", "new_fvg", "displacement")}

    fvg_bull: list[list[float]] = []  # [top, bot]
    fvg_bear: list[list[float]] = []
    ob_bull: list[list[float]] = []
    ob_bear: list[list[float]] = []

    for t in range(n):
        at = a[t] if np.isfinite(a[t]) else np.nan
        # --- novos FVGs (padrão de 3 velas) ---
        if t >= 2 and np.isfinite(at):
            if lo[t] > h[t - 2] and (lo[t] - h[t - 2]) >= min_fvg_atr * at:
                fvg_bull.append([lo[t], h[t - 2]])
                flags["new_fvg"][t] = 1
            elif h[t] < lo[t - 2] and (lo[t - 2] - h[t]) >= min_fvg_atr * at:
                fvg_bear.append([lo[t - 2], h[t]])
                flags["new_fvg"][t] = -1
            body = abs(c[t] - o[t])
            rng = h[t] - lo[t]
            if rng > 0 and body >= disp_atr * at and body / rng >= 0.6:
                flags["displacement"][t] = 1 if c[t] > o[t] else -1

        # --- order blocks nos eventos de estrutura ---
        if ev[t] > 0:
            for j in range(t - 1, max(t - 12, 0) - 1, -1):
                if c[j] < o[j]:
                    ob_bull.append([h[j], lo[j]])
                    break
        elif ev[t] < 0:
            for j in range(t - 1, max(t - 12, 0) - 1, -1):
                if c[j] > o[j]:
                    ob_bear.append([h[j], lo[j]])
                    break

        # --- mitigação / invalidação e interação com o preço ---
        keep = []
        for z in fvg_bull:
            top, bot = z
            if lo[t] <= bot:          # preenchido totalmente
                continue
            if lo[t] <= top and c[t] >= bot:
                flags["in_fvg_bull"][t] = 1
            keep.append(z)
        fvg_bull = keep[-max_zones:]
        keep = []
        for z in fvg_bear:
            top, bot = z
            if h[t] >= top:
                continue
            if h[t] >= bot and c[t] <= top:
                flags["in_fvg_bear"][t] = 1
            keep.append(z)
        fvg_bear = keep[-max_zones:]
        keep = []
        for z in ob_bull:
            top, bot = z
            if c[t] < bot:            # fechamento abaixo invalida o OB de compra
                continue
            if lo[t] <= top:
                flags["in_ob_bull"][t] = 1
            keep.append(z)
        ob_bull = keep[-max_zones:]
        keep = []
        for z in ob_bear:
            top, bot = z
            if c[t] > top:
                continue
            if h[t] >= bot:
                flags["in_ob_bear"][t] = 1
            keep.append(z)
        ob_bear = keep[-max_zones:]

        # zona ativa mais próxima abaixo (compra) / acima (venda) do fechamento
        below = [z for z in fvg_bull if z[1] <= c[t]]
        if below:
            z = max(below, key=lambda z: z[0])
            cols["fvg_bull_top"][t], cols["fvg_bull_bot"][t] = z
        above = [z for z in fvg_bear if z[0] >= c[t]]
        if above:
            z = min(above, key=lambda z: z[1])
            cols["fvg_bear_top"][t], cols["fvg_bear_bot"][t] = z
        below = [z for z in ob_bull if z[1] <= c[t]]
        if below:
            z = max(below, key=lambda z: z[0])
            cols["ob_bull_top"][t], cols["ob_bull_bot"][t] = z
        above = [z for z in ob_bear if z[0] >= c[t]]
        if above:
            z = min(above, key=lambda z: z[1])
            cols["ob_bear_top"][t], cols["ob_bear_bot"][t] = z

    out = pd.DataFrame({**cols, **flags}, index=df.index)
    return out


def active_zones(df: pd.DataFrame, atr: pd.Series, structure: pd.DataFrame,
                 min_fvg_atr: float = 0.15, lookback: int = 300) -> dict[str, list[dict]]:
    """Lista de zonas ativas no último candle (para exibição no app/painel)."""
    sub = df.iloc[-lookback:]
    a = atr.iloc[-lookback:]
    st = structure.iloc[-lookback:]
    o, h, lo, c = (sub[k].to_numpy() for k in ("o", "h", "l", "c"))
    av = a.to_numpy()
    ev = st["event"].to_numpy()
    zones = {"fvg_bull": [], "fvg_bear": [], "ob_bull": [], "ob_bear": []}
    n = len(sub)
    for t in range(2, n):
        if not np.isfinite(av[t]):
            continue
        if lo[t] > h[t - 2] and lo[t] - h[t - 2] >= min_fvg_atr * av[t]:
            zones["fvg_bull"].append({"top": lo[t], "bot": h[t - 2], "t": sub.index[t - 1], "i": t})
        elif h[t] < lo[t - 2] and lo[t - 2] - h[t] >= min_fvg_atr * av[t]:
            zones["fvg_bear"].append({"top": lo[t - 2], "bot": h[t], "t": sub.index[t - 1], "i": t})
        if ev[t] > 0:
            for j in range(t - 1, max(t - 12, 0) - 1, -1):
                if c[j] < o[j]:
                    zones["ob_bull"].append({"top": h[j], "bot": lo[j], "t": sub.index[j], "i": t})
                    break
        elif ev[t] < 0:
            for j in range(t - 1, max(t - 12, 0) - 1, -1):
                if c[j] > o[j]:
                    zones["ob_bear"].append({"top": h[j], "bot": lo[j], "t": sub.index[j], "i": t})
                    break
    out: dict[str, list[dict]] = {}
    for k, zs in zones.items():
        alive = []
        for z in zs:
            after = slice(z["i"] + 1, n)
            if k == "fvg_bull" and (lo[after] <= z["bot"]).any():
                continue
            if k == "fvg_bear" and (h[after] >= z["top"]).any():
                continue
            if k == "ob_bull" and (c[after] < z["bot"]).any():
                continue
            if k == "ob_bear" and (c[after] > z["top"]).any():
                continue
            alive.append({"top": float(z["top"]), "bottom": float(z["bot"]), "time": z["t"].isoformat()})
        out[k] = alive[-5:]
    return out

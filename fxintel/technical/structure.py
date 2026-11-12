"""Estrutura de mercado causal: swings (fractais), BOS/CHoCH, pools de liquidez e varreduras.

Todos os sinais são computados de forma *causal*: um swing com janela direita R só passa a
existir para o algoritmo na barra i+R (quando é confirmado). Isso elimina o viés de
"repintura" típico de implementações ingênuas de ZigZag/fractais em backtests.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

EVENT_NAMES = {0: "", 1: "BOS_UP", 2: "CHOCH_UP", -1: "BOS_DN", -2: "CHOCH_DN"}


@dataclass
class Swing:
    idx: int
    confirm_idx: int
    time: pd.Timestamp
    price: float
    kind: str        # "H" | "L"
    label: str = ""  # HH/LH/HL/LL
    equal: bool = False


def find_swings(df: pd.DataFrame, left: int = 3, right: int = 3) -> list[Swing]:
    h = df["h"].to_numpy()
    lo = df["l"].to_numpy()
    n = len(df)
    out: list[Swing] = []
    for i in range(left, n - right):
        hw = h[i - left:i + right + 1]
        if h[i] == hw.max() and (h[i] > h[i + 1:i + right + 1]).all():
            out.append(Swing(i, i + right, df.index[i], float(h[i]), "H"))
        lw = lo[i - left:i + right + 1]
        if lo[i] == lw.min() and (lo[i] < lo[i + 1:i + right + 1]).all():
            out.append(Swing(i, i + right, df.index[i], float(lo[i]), "L"))
    out.sort(key=lambda s: (s.confirm_idx, s.idx))
    return out


def market_structure(df: pd.DataFrame, atr: pd.Series, left: int = 3, right: int = 3,
                     eq_tol_atr: float = 0.15, max_active: int = 40) -> tuple[pd.DataFrame, list[Swing]]:
    """Máquina de estados de estrutura (causal). Retorna (frame por barra, swings)."""
    n = len(df)
    swings = find_swings(df, left, right)
    by_confirm: dict[int, list[Swing]] = {}
    for s in swings:
        by_confirm.setdefault(s.confirm_idx, []).append(s)

    h = df["h"].to_numpy()
    lo = df["l"].to_numpy()
    c = df["c"].to_numpy()
    a = atr.to_numpy()

    trend = np.zeros(n, dtype=np.int8)
    event = np.zeros(n, dtype=np.int8)
    last_event = np.zeros(n, dtype=np.int8)
    since_event = np.full(n, 9999, dtype=np.int32)
    last_sh = np.full(n, np.nan)
    last_sl = np.full(n, np.nan)
    near_hi = np.full(n, np.nan)
    near_lo = np.full(n, np.nan)
    near_hi_eq = np.zeros(n, dtype=np.int8)
    near_lo_eq = np.zeros(n, dtype=np.int8)
    sweep_hi = np.full(n, np.nan)   # nível de liquidez acima varrido com fechamento abaixo
    sweep_lo = np.full(n, np.nan)   # nível abaixo varrido com fechamento acima
    sweep_hi_eq = np.zeros(n, dtype=np.int8)  # nível varrido era pool de topos iguais
    sweep_lo_eq = np.zeros(n, dtype=np.int8)
    swing_bias = np.zeros(n, dtype=np.int8)  # +1 HH&HL, -1 LH&LL
    leg_origin_lo = np.full(n, np.nan)  # mínima de origem da perna que gerou o último evento de alta
    leg_origin_hi = np.full(n, np.nan)

    state = 0
    sh_price = sl_price = np.nan
    sh_broken = sl_broken = True
    prev_sh = prev_sl = None
    lab_h = lab_l = ""
    act_hi: list[list] = []  # [price, idx, equal]
    act_lo: list[list] = []
    ev_last, ev_at = 0, -10_000
    origin_lo = origin_hi = np.nan
    recent_lows: list[float] = []
    recent_highs: list[float] = []

    for t in range(n):
        tol = (a[t] if np.isfinite(a[t]) else 0.0) * eq_tol_atr
        for s in by_confirm.get(t, ()):
            if s.kind == "H":
                if prev_sh is not None:
                    s.label = "HH" if s.price > prev_sh.price else "LH"
                lab_h = s.label
                prev_sh = s
                sh_price, sh_broken = s.price, False
                eq = False
                for lv in act_hi:
                    if abs(lv[0] - s.price) <= tol:
                        lv[2] = True
                        eq = True
                s.equal = eq
                act_hi.append([s.price, s.idx, eq])
                recent_highs.append(s.price)
            else:
                if prev_sl is not None:
                    s.label = "HL" if s.price > prev_sl.price else "LL"
                lab_l = s.label
                prev_sl = s
                sl_price, sl_broken = s.price, False
                eq = False
                for lv in act_lo:
                    if abs(lv[0] - s.price) <= tol:
                        lv[2] = True
                        eq = True
                s.equal = eq
                act_lo.append([s.price, s.idx, eq])
                recent_lows.append(s.price)
        if len(act_hi) > max_active:
            act_hi = act_hi[-max_active:]
        if len(act_lo) > max_active:
            act_lo = act_lo[-max_active:]
        recent_lows = recent_lows[-5:]
        recent_highs = recent_highs[-5:]

        # varreduras e consumo de liquidez (por pavio)
        swept_h = [lv for lv in act_hi if h[t] > lv[0]]
        if swept_h:
            best = max(swept_h, key=lambda lv: lv[0])
            if c[t] < best[0]:
                sweep_hi[t] = best[0]
                sweep_hi_eq[t] = int(any(lv[2] for lv in swept_h))
            act_hi = [lv for lv in act_hi if h[t] <= lv[0]]
        swept_l = [lv for lv in act_lo if lo[t] < lv[0]]
        if swept_l:
            best = min(swept_l, key=lambda lv: lv[0])
            if c[t] > best[0]:
                sweep_lo[t] = best[0]
                sweep_lo_eq[t] = int(any(lv[2] for lv in swept_l))
            act_lo = [lv for lv in act_lo if lo[t] >= lv[0]]

        # BOS / CHoCH por fechamento
        ev = 0
        if not sh_broken and c[t] > sh_price:
            ev = 1 if state == 1 else 2
            state = 1
            sh_broken = True
            origin_lo = min(recent_lows[-1:] or [lo[t]])
        if not sl_broken and c[t] < sl_price:
            ev = -1 if state == -1 else -2
            state = -1
            sl_broken = True
            origin_hi = max(recent_highs[-1:] or [h[t]])
        if ev:
            ev_last, ev_at = ev, t
        trend[t] = state
        event[t] = ev
        last_event[t] = ev_last
        since_event[t] = t - ev_at if ev_at >= 0 else 9999
        last_sh[t] = sh_price
        last_sl[t] = sl_price
        leg_origin_lo[t] = origin_lo
        leg_origin_hi[t] = origin_hi
        if act_hi:
            lv = min(act_hi, key=lambda x: x[0])
            near_hi[t], near_hi_eq[t] = lv[0], int(lv[2])
        if act_lo:
            lv = max(act_lo, key=lambda x: x[0])
            near_lo[t], near_lo_eq[t] = lv[0], int(lv[2])
        swing_bias[t] = 1 if (lab_h == "HH" and lab_l == "HL") else (-1 if (lab_h == "LH" and lab_l == "LL") else 0)

    out = pd.DataFrame({
        "trend": trend, "event": event, "last_event": last_event, "since_event": since_event,
        "last_sh": last_sh, "last_sl": last_sl, "near_hi": near_hi, "near_lo": near_lo,
        "near_hi_eq": near_hi_eq, "near_lo_eq": near_lo_eq, "sweep_hi": sweep_hi,
        "sweep_lo": sweep_lo, "sweep_hi_eq": sweep_hi_eq, "sweep_lo_eq": sweep_lo_eq,
        "swing_bias": swing_bias, "leg_origin_lo": leg_origin_lo,
        "leg_origin_hi": leg_origin_hi,
    }, index=df.index)
    return out, swings


def describe_trend(state: int, bias: int, adx: float) -> str:
    base = {1: "alta", -1: "baixa", 0: "indefinida"}[int(state)]
    force = "forte" if adx >= 25 else ("moderada" if adx >= 18 else "fraca")
    seq = {1: "topos e fundos ascendentes", -1: "topos e fundos descendentes", 0: "sequência mista"}[int(bias)]
    return f"{base} ({force}, ADX {adx:.0f}; {seq})"

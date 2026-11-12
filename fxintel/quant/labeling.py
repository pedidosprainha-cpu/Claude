"""Rotulagem triple-barrier e simulação de execução com custos (bid/ask, slippage).

Convenções (conservadoras):
- Entrada a mercado na abertura do candle seguinte ao sinal (o sinal só existe no fechamento).
- Compra executa no ASK (+spread/2) com slippage adverso; venda no BID.
- Stop é ordem a mercado: executa no pior entre o nível e a abertura (gaps), mais slippage.
- Alvo é ordem limitada: executa no nível, sem slippage positivo.
- Se stop e alvo cabem no mesmo candle, assume-se que o STOP ocorreu primeiro.
- Gestão: 50% no TP1, stop do restante movido para o preço de entrada, restante no TP2.
- Barreira vertical (horizonte): encerramento a mercado no fechamento do último candle.
- Rótulo binário do modelo: TP1 atingido antes do stop.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .. import instruments as I
from ..data.models import session_of


@dataclass
class TradeResult:
    entry_idx: int
    entry: float
    exit_idx: int
    r: float              # resultado total em R (já líquido de custos)
    hit_tp1: int
    outcome: str          # sl | tp1_be | tp1_tp2 | tp1_timeout | timeout
    bars: int
    cost_r: float         # custo de spread+slippage da entrada em R
    risk_price: float


def spread_series(inst: I.Instrument, index: pd.DatetimeIndex, multipliers: dict,
                  override_pips: float | None = None) -> np.ndarray:
    pips = override_pips if override_pips is not None else inst.typical_spread_pips
    sess = [multipliers.get(session_of(t), 1.0) for t in index]
    return np.asarray(sess) * pips * inst.pip


def simulate(o, h, l, c, spread, t: int, d: int, sl: float, tp1: float, tp2: float,
             horizon: int, slip: float, partial: bool = True) -> TradeResult | None:
    n = len(o)
    e = t + 1
    if e >= n:
        return None
    half = spread[e] / 2
    entry = o[e] + d * (half + slip)
    risk = d * (entry - sl)
    if risk <= 0:
        return None  # preço já além do stop na abertura: sinal inválido
    cost_r = (half + slip) / risk
    remaining = 1.0
    realized = 0.0
    phase = 1
    stop = sl
    last = min(n - 1, e + horizon - 1)
    for k in range(e, last + 1):
        hs = spread[k] / 2
        if d == 1:
            bid_o, bid_l, bid_h = o[k] - hs, l[k] - hs, h[k] - hs
            stop_hit = bid_l <= stop
            stop_px = min(bid_o, stop) - (slip if phase == 1 else 0.0)
            tgt = tp1 if phase == 1 else tp2
            tgt_hit = bid_h >= tgt
        else:
            ask_o, ask_l, ask_h = o[k] + hs, l[k] + hs, h[k] + hs
            stop_hit = ask_h >= stop
            stop_px = max(ask_o, stop) + (slip if phase == 1 else 0.0)
            tgt = tp1 if phase == 1 else tp2
            tgt_hit = ask_l <= tgt
        if stop_hit:
            realized += remaining * d * (stop_px - entry) / risk
            outcome = "sl" if phase == 1 else "tp1_be"
            return TradeResult(e, entry, k, realized, int(phase == 2), outcome, k - e + 1, cost_r, risk)
        if tgt_hit:
            if phase == 1 and partial:
                realized += 0.5 * d * (tp1 - entry) / risk
                remaining = 0.5
                phase = 2
                stop = entry  # break-even
                continue
            realized += remaining * d * (tgt - entry) / risk
            outcome = "tp1_tp2" if phase == 2 else "tp1"
            return TradeResult(e, entry, k, realized, 1, outcome, k - e + 1, cost_r, risk)
    hs = spread[last] / 2
    exit_px = c[last] - d * hs
    realized += remaining * d * (exit_px - entry) / risk
    return TradeResult(e, entry, last, realized, int(phase == 2),
                       "tp1_timeout" if phase == 2 else "timeout", last - e + 1, cost_r, risk)


def label_candidates(inst: I.Instrument, bars: pd.DataFrame, cand: pd.DataFrame, horizon: int,
                     multipliers: dict, slip_pips: float, slip_atr: float,
                     override_pips: float | None = None) -> pd.DataFrame:
    """Simula cada candidato e anexa resultado, rótulo e horário de resolução (para purging)."""
    if cand.empty:
        return cand
    o, h, l, c = (bars[k].to_numpy(dtype=float) for k in ("o", "h", "l", "c"))
    spread = spread_series(inst, bars.index, multipliers, override_pips)
    pos = {t: i for i, t in enumerate(bars.index)}
    res = []
    for t, r in cand.iterrows():
        i = pos.get(t)
        if i is None:
            res.append(None)
            continue
        slip = slip_pips * inst.pip + slip_atr * r["atr"]
        tr = simulate(o, h, l, c, spread, i, int(r["dir"]), r["sl"], r["tp1"], r["tp2"], horizon, slip)
        res.append(tr)
    out = cand.copy()
    out["r"] = [x.r if x else np.nan for x in res]
    out["y"] = [x.hit_tp1 if x else np.nan for x in res]
    out["outcome"] = [x.outcome if x else None for x in res]
    out["bars_held"] = [x.bars if x else np.nan for x in res]
    out["cost_r"] = [x.cost_r if x else np.nan for x in res]
    out["entry_exec"] = [x.entry if x else np.nan for x in res]
    out["exit_time"] = [bars.index[x.exit_idx] + pd.Timedelta(hours=1) if x else pd.NaT for x in res]
    out["resolved"] = [bool(x) and (x.exit_idx < len(bars) - 1 or x.outcome not in ("timeout", "tp1_timeout")
                       or x.bars >= horizon) for x in res]
    return out

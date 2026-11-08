"""Trade plan for immediate market execution: entry at the executable side of the
live quote, structural stop, level-aware targets and position size."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from .analysis.structure import LevelMap, swings
from .instruments import Instrument


@dataclass
class TradePlan:
    direction: int
    entry: float
    sl: float
    tp1: float
    tp2: float
    sl_dist: float
    rr1: float
    rr2: float
    sl_atr_h1: float
    tp1_atr_h1: float
    sl_pips: float
    tp1_pips: float
    tp2_pips: float
    lots: float
    risk_amount: float
    pip_value_lot: float
    spread_ratio: float
    room_r: float
    sl_basis: str
    tp1_basis: str
    tp2_basis: str
    invalidation: str
    notes: list[str] = field(default_factory=list)


def conversion_to_usd(ccy: str, prices: dict[str, float]) -> float | None:
    """USD value of 1 unit of `ccy`, from the live prices of loaded pairs."""
    if ccy == "USD":
        return 1.0
    if f"{ccy}USD" in prices:
        return prices[f"{ccy}USD"]
    if f"USD{ccy}" in prices and prices[f"USD{ccy}"]:
        return 1.0 / prices[f"USD{ccy}"]
    return None


def build_plan(inst: Instrument, direction: int, bid: float, ask: float, frames: dict[str, pd.DataFrame],
               atr_m15: float, atr_h1: float, atr_d1: float, levels: LevelMap,
               balance: float, risk_pct: float, prices: dict[str, float], account_ccy: str = "USD") -> TradePlan:
    d = direction
    entry = ask if d == 1 else bid
    spread = max(ask - bid, 0.0)
    notes: list[str] = []

    # ---------------------------------------------------------------- stop
    min_d = max(0.6 * atr_h1, 1.2 * atr_m15, 4 * spread)
    max_d = 2.2 * atr_h1
    buffer = 0.25 * atr_m15 + spread
    cands: list[tuple[float, str]] = []
    for tf, k, look in (("M15", 3, 80), ("H1", 2, 48)):
        df = frames.get(tf)
        if df is None or len(df) < 10:
            continue
        for s in swings(df.iloc[-look:], k):
            if d == 1 and s.kind == "L" and s.price < entry:
                cands.append((s.price - buffer, f"abaixo do fundo {tf} {inst.fmt(s.price)}"))
            if d == -1 and s.kind == "H" and s.price > entry:
                cands.append((s.price + buffer, f"acima do topo {tf} {inst.fmt(s.price)}"))
    cands.sort(key=lambda x: d * (entry - x[0]))     # nearest first
    sl, sl_basis = None, ""
    for px, why in cands:
        dist = d * (entry - px)
        if dist < min_d:
            continue
        if dist <= max_d:
            sl, sl_basis = px, f"estrutural: {why} + buffer"
        break
    if sl is None:
        dist = min(max(1.3 * atr_h1, min_d), max_d)
        sl = entry - d * dist
        sl_basis = "volatilidade: 1.3× ATR H1 (sem swing utilizável no intervalo ideal)"
    sl_dist = d * (entry - sl)

    # ---------------------------------------------------------------- targets
    opp = levels.above(entry) if d == 1 else levels.below(entry)
    first = next((lv for lv in opp if d * (lv.price - entry) > 0.25 * sl_dist), None)
    room_r = (d * (first.price - entry) / sl_dist) if first else 3.0
    front = 0.1 * atr_m15

    tp1_dist, tp1_basis = None, ""
    for lv in opp:
        dist = d * (lv.price - entry) - front
        if dist >= 1.0 * sl_dist:
            if dist <= 2.0 * sl_dist:
                tp1_dist, tp1_basis = dist, f"antes da zona {inst.fmt(lv.price)} ({lv.label()})"
            break
    if tp1_dist is None:
        tp1_dist = 1.5 * sl_dist
        tp1_basis = "1.5R (sem zona relevante no intervalo 1R–2R)"
    if first and d * (first.price - entry) < tp1_dist:
        notes.append(f"zona {inst.fmt(first.price)} ({first.label()}) antes do TP1: possível reação")

    tp2_dist, tp2_basis = None, ""
    for lv in opp:
        dist = d * (lv.price - entry) - front
        if dist >= tp1_dist + 0.5 * sl_dist and dist <= 4.0 * sl_dist:
            tp2_dist, tp2_basis = dist, f"antes da zona {inst.fmt(lv.price)} ({lv.label()})"
            break
    if tp2_dist is None:
        tp2_dist = max(2.0 * sl_dist, tp1_dist + 0.8 * sl_dist)
        tp2_basis = f"{tp2_dist / sl_dist:.1f}R (extensão)"
    cap = max(1.3 * atr_d1, tp1_dist + 0.5 * sl_dist)
    if tp2_dist > cap:
        tp2_dist, tp2_basis = cap, "limitado a ~1.3× ATR diário (horizonte intraday)"

    tp1 = entry + d * tp1_dist
    tp2 = entry + d * tp2_dist

    # ---------------------------------------------------------------- sizing
    risk_amount = balance * risk_pct / 100
    pip_quote = inst.pip * inst.contract_size            # quote-ccy value of 1 pip per lot
    conv = conversion_to_usd(inst.quote, prices)
    if account_ccy != "USD":
        acc = conversion_to_usd(account_ccy, prices)
        conv = conv / acc if conv and acc else None
    pip_val = pip_quote * conv if conv else float("nan")
    sl_pips = inst.pips(sl_dist)
    lots = math.floor(risk_amount / (sl_pips * pip_val) * 100) / 100 if pip_val and pip_val == pip_val and sl_pips > 0 else 0.0
    if lots < 0.01:
        notes.append("tamanho calculado < 0.01 lote para o risco escolhido")

    inval_px = entry - d * 0.6 * sl_dist
    inval = (f"fechamento M15 {'abaixo' if d == 1 else 'acima'} de {inst.fmt(inval_px)} "
             "(60% do caminho até o stop) invalida o gatilho — sair sem esperar o stop")

    return TradePlan(
        direction=d, entry=entry, sl=sl, tp1=tp1, tp2=tp2, sl_dist=sl_dist,
        rr1=tp1_dist / sl_dist, rr2=tp2_dist / sl_dist,
        sl_atr_h1=sl_dist / atr_h1, tp1_atr_h1=tp1_dist / atr_h1,
        sl_pips=sl_pips, tp1_pips=inst.pips(tp1_dist), tp2_pips=inst.pips(tp2_dist),
        lots=lots, risk_amount=risk_amount, pip_value_lot=pip_val,
        spread_ratio=spread / sl_dist if sl_dist > 0 else 1.0, room_r=room_r,
        sl_basis=sl_basis, tp1_basis=tp1_basis, tp2_basis=tp2_basis, invalidation=inval, notes=notes,
    )

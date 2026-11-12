"""Simulador de portfólio orientado a eventos com as mesmas regras de risco da operação ao vivo.

Entrada: trades candidatos já simulados individualmente (resultado em R, horários de decisão
e saída). O simulador decide quais são aceitos respeitando: máximo de posições abertas,
uma posição por instrumento, limite de risco por moeda/direção, limites de perda diária e
semanal; dimensiona cada posição em % do capital corrente (juros compostos).
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from .. import instruments as I
from .metrics import equity_metrics, trade_metrics


def exposures(symbol: str, d: int) -> dict[str, int]:
    inst = I.get(symbol)
    return {inst.base: d, inst.quote: -d}


def simulate_portfolio(trades: pd.DataFrame, settings: dict, initial: float | None = None) -> dict:
    risk = settings["risk"]
    initial = initial or settings["account"]["equity"]
    rpt = risk["risk_per_trade_pct"] / 100
    max_open = risk["max_open_positions"]
    max_cur = risk["max_risk_per_currency_pct"] / 100
    dl = risk["max_daily_loss_pct"] / 100
    wl = risk["max_weekly_loss_pct"] / 100

    trades = trades.sort_values("decision_time")
    equity = initial
    open_pos: list[dict] = []
    taken = []
    rejected = defaultdict(int)
    day_pnl: dict = defaultdict(float)
    week_pnl: dict = defaultdict(float)
    curve = []

    def close_until(ts):
        nonlocal equity, open_pos
        still = []
        for p in sorted(open_pos, key=lambda p: p["exit_time"]):
            if p["exit_time"] <= ts:
                pnl = p["r"] * p["risk_amt"]
                equity += pnl
                day_pnl[p["exit_time"].date()] += pnl
                wk = (p["exit_time"] - pd.Timedelta(days=p["exit_time"].weekday())).date()
                week_pnl[wk] += pnl
                curve.append((p["exit_time"], equity))
            else:
                still.append(p)
        open_pos = still

    for _, t in trades.iterrows():
        ts = t["decision_time"]
        close_until(ts)
        day = ts.date()
        wk = (ts - pd.Timedelta(days=ts.weekday())).date()
        if day_pnl[day] <= -dl * equity:
            rejected["limite_perda_diaria"] += 1
            continue
        if week_pnl[wk] <= -wl * equity:
            rejected["limite_perda_semanal"] += 1
            continue
        if len(open_pos) >= max_open:
            rejected["max_posicoes"] += 1
            continue
        if any(p["symbol"] == t["symbol"] for p in open_pos):
            rejected["instrumento_ja_aberto"] += 1
            continue
        ex = exposures(t["symbol"], int(t["dir"]))
        blocked = False
        for cur, sgn in ex.items():
            used = sum(p["risk_pct"] for p in open_pos if p["exp"].get(cur) == sgn)
            if used + rpt > max_cur + 1e-12:
                blocked = True
                break
        if blocked:
            rejected["limite_exposicao_moeda"] += 1
            continue
        pos = {"symbol": t["symbol"], "exit_time": t["exit_time"], "r": float(t["r"]),
               "risk_amt": equity * rpt, "risk_pct": rpt, "exp": ex}
        open_pos.append(pos)
        taken.append({**t.to_dict(), "risk_amt": pos["risk_amt"], "equity_before": equity})
    close_until(pd.Timestamp.max.tz_localize("UTC"))

    tk = pd.DataFrame(taken)
    if curve:
        cs = pd.Series([e for _, e in curve], index=pd.DatetimeIndex([t for t, _ in curve]))
        daily = cs.groupby(cs.index.normalize()).last()
    else:
        daily = pd.Series(dtype=float)
    out = {
        "trades": tk,
        "daily_equity": daily,
        "trade_metrics": trade_metrics(tk["r"].to_numpy() if len(tk) else np.array([])),
        "equity_metrics": equity_metrics(daily, initial) if len(daily) else {},
        "rejected": dict(rejected),
        "final_equity": equity,
    }
    return out

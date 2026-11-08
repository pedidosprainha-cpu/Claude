"""Historical edge study (walk-forward, no look-ahead).

Replays a vectorised version of the engine's core signal over ~1 year of H1
bars, finds past moments that look like *now* (same direction, similar signal
strength and similar extension from value), and simulates the exact trade
geometry proposed now (stop and target in ATR units, spread included):

  * entry at the next bar's open, SL first if both are touched in one bar
  * non-overlapping trades, max holding period, timeout marked-to-market

A Beta prior centred on the break-even hit-rate shrinks small samples, so the
reported probability is conservative.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import indicators as ta


@dataclass
class EdgeResult:
    n: int
    wins: int
    losses: int
    timeouts: int
    win_rate: float          # raw, over resolved trades
    p_post: float            # Bayesian posterior hit-rate (TP before SL)
    expectancy_r: float      # raw mean R per trade (incl. timeouts and spread)
    exp_post_r: float        # expectancy implied by the posterior hit-rate
    profit_factor: float
    rr: float
    avg_bars: float

    @property
    def reliable(self) -> bool:
        return self.n >= 25


def core_signal(df: pd.DataFrame) -> pd.DataFrame:
    c = df.c
    e21, e50, e200 = ta.ema(c, 21), ta.ema(c, 50), ta.ema(c, 200)
    st = ta.supertrend(df)
    r = ta.rsi(c)
    _, _, hist = ta.macd(c)
    a = ta.atr(df)
    trend = (0.35 * np.sign(e21 - e50) + 0.25 * np.sign(c - e200) + 0.25 * st
             + 0.15 * np.sign(e50 - e50.shift(5)))
    mom = 0.5 * ((r - 50) / 20).clip(-1, 1) + 0.5 * np.sign(hist)
    core = 0.6 * trend + 0.4 * mom
    ext = (c - e21) / a
    return pd.DataFrame({"core": core, "ext": ext, "atr": a})


def evaluate(h1: pd.DataFrame, direction: int, sl_atr: float, tp_atr: float, spread: float,
             max_hold: int = 48, prior_strength: float = 12.0, warmup: int = 220) -> EdgeResult | None:
    if len(h1) < warmup + max_hold + 50 or sl_atr <= 0 or tp_atr <= 0:
        return None
    sig = core_signal(h1)
    core, ext, atr = sig.core.to_numpy(), sig.ext.to_numpy(), sig.atr.to_numpy()
    o, h, l, c = (h1[k].to_numpy() for k in ("o", "h", "l", "c"))
    n = len(h1)
    d = direction
    now_core, now_ext = d * core[-1], d * ext[-1]
    thr = max(0.25, min(now_core, 0.85) - 0.25)
    cond = (d * core >= thr) & (np.abs(d * ext - now_ext) <= 0.9)
    cond[:warmup] = False
    cond[n - max_hold - 1:] = False
    rr = tp_atr / sl_atr

    results, bars, costs = [], [], []
    idx = np.flatnonzero(cond)
    k = 0
    while k < len(idx):
        i = idx[k]
        entry = o[i + 1]
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            k += 1
            continue
        sl_d, tp_d = sl_atr * a, tp_atr * a
        sl = entry - d * sl_d
        tp = entry + d * tp_d
        cost_r = spread / sl_d
        costs.append(cost_r)
        outcome, exit_j = None, i + max_hold
        for j in range(i + 1, min(i + 1 + max_hold, n)):
            hit_sl = l[j] <= sl if d == 1 else h[j] >= sl
            hit_tp = h[j] >= tp if d == 1 else l[j] <= tp
            if hit_sl:
                outcome, exit_j = -1.0, j
                break
            if hit_tp:
                outcome, exit_j = rr, j
                break
        if outcome is None:
            exit_j = min(i + max_hold, n - 1)
            outcome = d * (c[exit_j] - entry) / sl_d
            results.append(("t", outcome - cost_r))
        else:
            results.append(("w" if outcome > 0 else "l", outcome - cost_r))
        bars.append(exit_j - i)
        # non-overlapping: jump past the exit bar
        k = int(np.searchsorted(idx, exit_j + 1))

    if not results:
        return EdgeResult(0, 0, 0, 0, 0.0, 1 / (1 + rr), 0.0, 0.0, 0.0, rr, 0.0)
    wins = sum(1 for t, _ in results if t == "w")
    losses = sum(1 for t, _ in results if t == "l")
    touts = sum(1 for t, _ in results if t == "t")
    rs = np.array([r for _, r in results])
    resolved = wins + losses
    p_be = 1 / (1 + rr)
    a0, b0 = prior_strength * p_be, prior_strength * (1 - p_be)
    p_post = (wins + a0) / (resolved + a0 + b0)
    gross_win = rs[rs > 0].sum()
    gross_loss = -rs[rs < 0].sum()
    pf = float(gross_win / gross_loss) if gross_loss > 0 else float("inf")
    return EdgeResult(
        n=len(results), wins=wins, losses=losses, timeouts=touts,
        win_rate=wins / resolved if resolved else 0.0, p_post=float(p_post),
        expectancy_r=float(rs.mean()), exp_post_r=float(p_post * rr - (1 - p_post) - np.mean(costs)),
        profit_factor=pf, rr=float(rr), avg_bars=float(np.mean(bars)),
    )

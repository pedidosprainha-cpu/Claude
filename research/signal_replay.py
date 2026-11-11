"""Walk-forward replay of the main market-entry signal over ~2 years of H1 (32 instruments).

At every closed H1 bar it stores the features the live engine computes
(fxengine.analysis.signal_model.feature_frame, same function) and, for BOTH directions,
the outcome of a market entry at the next bar's open (spread included, stop checked first
when a bar touches both) for a grid of trade geometries:

  stop   s10 / s15 / s20      1.0 / 1.5 / 2.0 ATR H1 from the fill
  exit   tp15 / tp2           fixed target at 1.5 / 2 R
         be2                  stop to break-even at +1R, target 2R
         tr10                 after +1R trail the stop 1 ATR H1 behind the best price
         p15                  engine plan: half at 1.5R, rest with stop at entry and target 3R
  horizon 48 bars (timeouts closed at market)

Each outcome also stores the exit bar offset (for non-overlapping trade simulation).

    python3 research/signal_replay.py --out research/data/signal_events.pkl
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from breakout_replay import spread_pips  # noqa: E402

from fxengine.analysis import signal_model as sm  # noqa: E402
from fxengine.analysis import strength as strength_mod  # noqa: E402
from fxengine.data import yahoo  # noqa: E402
from fxengine.data.http import Http  # noqa: E402
from fxengine.instruments import FX_PAIRS, MAJORS, UNIVERSE  # noqa: E402

HORIZON = 48
STOPS = {"s10": 1.0, "s15": 1.5, "s20": 2.0}
EXITS = {"tp15": ("tp", 1.5), "tp2": ("tp", 2.0), "be2": ("be", 2.0), "tr10": ("trail", 1.0),
         "p15": ("partial", 1.5)}
GEOMS = [f"{s}|{x}" for s in STOPS for x in EXITS]
# --grid swing: longer trades (up to 5 days), where the spread weighs less per R
GRIDS = {
    "intraday": (STOPS, EXITS, HORIZON),
    "swing": ({"s20": 2.0, "s30": 3.0},
              {"tp2": ("tp", 2.0), "tp3": ("tp", 3.0), "be3": ("be", 3.0), "tr15": ("trail", 1.5)}, 120),
}
ALL_STOPS = {"s10": 1.0, "s15": 1.5, "s20": 2.0, "s30": 3.0}
ALL_EXITS = {**EXITS, "tp3": ("tp", 3.0), "be3": ("be", 3.0), "tr15": ("trail", 1.5)}


def load_h1(cache: str, ttl_days: float) -> dict[str, pd.DataFrame]:
    http = Http(cache, timeout=60)
    out = {}
    for sym, inst in UNIVERSE.items():
        out[sym] = yahoo.candles(http, inst.yahoo, "1h", "730d", ttl=ttl_days * 24 * 3600)[0]
    return out


# ---------------------------------------------------------------- strength (vectorised)
def _z_frame(c: pd.Series) -> pd.DataFrame:
    lr = np.log(c)
    sig = lr.diff().rolling(750, min_periods=50).std()
    return pd.DataFrame({name: (lr - lr.shift(n)) / (sig * np.sqrt(n)) for name, n, _ in strength_mod.HORIZONS})


def strength_series(data: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    """Pair score -100..100 at every hour, as strength_mod.compute would return it then."""
    idx = sorted(set().union(*[data[p.symbol].index for p in FX_PAIRS]))
    idx = pd.DatetimeIndex(idx)
    acc = {h: {c: [] for c in MAJORS} for h, _, _ in strength_mod.HORIZONS}
    for p in FX_PAIRS:
        z = _z_frame(data[p.symbol].c).reindex(idx).ffill()
        for h in z.columns:
            acc[h][p.base].append(z[h])
            acc[h][p.quote].append(-z[h])
    score = {c: sum(w * pd.concat(acc[h][c], axis=1).mean(axis=1).fillna(0.0)
                    for h, _, w in strength_mod.HORIZONS) for c in MAJORS}
    out = {}
    for sym, inst in UNIVERSE.items():
        if inst.is_metal:
            z = _z_frame(data[sym].c).fillna(0.0)
            mz = sum(w * z[h] for h, _, w in strength_mod.HORIZONS)
            out[sym] = np.tanh(mz / 1.5) * 100
        else:
            out[sym] = (np.tanh((score[inst.base] - score[inst.quote]) / 1.5) * 100).reindex(data[sym].index).ffill()
    return out


def check_strength(data: dict[str, pd.DataFrame], series: dict[str, pd.Series], n_checks: int = 3) -> float:
    """Max abs difference vs the engine's strength_mod.compute at a few random hours."""
    rng = np.random.default_rng(0)
    ref = data["EURUSD"].index
    worst = 0.0
    for t in rng.choice(ref[2000:-10], n_checks, replace=False):
        sl = {p.symbol: data[p.symbol][data[p.symbol].index <= t] for p in FX_PAIRS}
        metals = {s[:3]: data[s][data[s].index <= t] for s, i in UNIVERSE.items() if i.is_metal}
        st = strength_mod.compute(sl, metals)
        for sym in ("EURUSD", "GBPJPY", "AUDNZD", "XAUUSD"):
            inst = UNIVERSE[sym]
            live = st.pair_score(inst.base, inst.quote)
            rep = float(series[sym].asof(t))
            worst = max(worst, abs(live - rep))
    return worst


# ---------------------------------------------------------------- outcomes (vectorised)
def _first(mask: np.ndarray) -> np.ndarray:
    T = mask.shape[1]
    return np.where(mask.any(1), mask.argmax(1), T)


def exits(fav: np.ndarray, adv: np.ndarray, closeR: np.ndarray, kind: str, val: float, tR: np.ndarray):
    """(R, exit offset) per row; fav/adv are (N, T) excursions in R from the fill."""
    N, T = fav.shape
    cols = np.arange(T)[None, :]
    i_sl = _first(adv <= -1)
    last = np.full(N, T - 1)
    if kind == "tp":
        i_tp = _first(fav >= val)
        loss = (i_sl < T) & (i_sl <= i_tp)
        r = np.where(loss, -1.0, np.where(i_tp < T, val, closeR))
        k = np.where(loss, i_sl, np.where(i_tp < T, i_tp, last))
        return r, k
    if kind in ("be", "partial"):
        trig = 1.0 if kind == "be" else val
        tgt = val if kind == "be" else 3.0
        i_1 = _first(fav >= trig)
        loss = (i_sl < T) & (i_sl <= i_1)
        reached = (~loss) & (i_1 < T)
        after = cols > i_1[:, None]
        same_bar = reached & (np.take_along_axis(fav, np.minimum(i_1, T - 1)[:, None], 1)[:, 0] >= tgt)
        j_be = _first((adv <= 0) & after)
        j_tp = _first((fav >= tgt) & after)
        be_first = (j_be < T) & (j_be <= j_tp)
        rest = np.where(same_bar, tgt, np.where(be_first, 0.0, np.where(j_tp < T, tgt, np.maximum(closeR, 0.0))))
        k_rest = np.where(same_bar, i_1, np.where(be_first, j_be, np.where(j_tp < T, j_tp, last)))
        if kind == "be":
            r = np.where(loss, -1.0, np.where(reached, rest, closeR))
        else:
            r = np.where(loss, -1.0, np.where(reached, 0.5 * trig + 0.5 * rest, closeR))
        k = np.where(loss, i_sl, np.where(reached, k_rest, last))
        return r, k
    # trailing
    prev_best = np.concatenate([np.full((N, 1), -np.inf), np.maximum.accumulate(fav, axis=1)[:, :-1]], axis=1)
    stop = np.where(prev_best >= 1, np.maximum(prev_best - tR[:, None], 0.0), -1.0)
    hit = _first(adv <= stop)
    r = np.where(hit < T, np.take_along_axis(stop, np.minimum(hit, T - 1)[:, None], 1)[:, 0], closeR)
    return r, np.where(hit < T, hit, last)


def replay_symbol(args) -> pd.DataFrame:
    sym, h1, st, grid = args
    stops, exits_, horizon = GRIDS[grid]
    inst = UNIVERSE[sym]
    spread = spread_pips(sym) * inst.pip
    half = spread / 2
    ff = sm.feature_frame(h1, st, spread, inst.is_metal)
    o, h, l, c = (h1[k].to_numpy() for k in ("o", "h", "l", "c"))
    a = ff["atr"].to_numpy()
    n = len(h1)
    idx = np.arange(sm.WARMUP_BARS, n - horizon - 1)
    idx = idx[np.isfinite(a[idx]) & (a[idx] > 0)]
    win = np.lib.stride_tricks.sliding_window_view
    H = win(h, horizon)[idx + 1]
    L = win(l, horizon)[idx + 1]
    fill_mid = o[idx + 1]
    close_last = c[idx + horizon]
    out = ff.iloc[idx][sm.FEATURES].astype("float32").reset_index(drop=False).rename(columns={"index": "time"})
    out.insert(0, "symbol", sym)
    out["atr"] = a[idx].astype("float32")
    out["horizon"] = np.int16(horizon)
    for d, tag in ((1, "L"), (-1, "S")):
        fill = fill_mid + d * half
        fav_px = (H - half) if d == 1 else (L + half)
        adv_px = (L - half) if d == 1 else (H + half)
        exit_last = close_last - d * half
        for sk, m in stops.items():
            sl_d = np.maximum(m * a[idx], 8 * half)
            favR = d * (fav_px - fill[:, None]) / sl_d[:, None]
            advR = d * (adv_px - fill[:, None]) / sl_d[:, None]
            closeR = d * (exit_last - fill) / sl_d
            for xk, (kind, val) in exits_.items():
                tR = val * a[idx] / sl_d if kind == "trail" else np.zeros(len(idx))
                r, k = exits(favR, advR, closeR, kind, val, tR)
                out[f"{tag}|{sk}|{xk}"] = r.astype("float32")
                out[f"{tag}|{sk}|{xk}|k"] = (k + 1).astype("int16")      # bars held (fill bar = 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "research", "data", "signal_events.pkl"))
    ap.add_argument("--cache", default=os.path.join(ROOT, ".cache", "research"))
    ap.add_argument("--ttl-days", type=float, default=3.0)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--grid", choices=list(GRIDS), default="intraday")
    a = ap.parse_args()
    t0 = time.time()
    data = load_h1(a.cache, a.ttl_days)
    for s, df in data.items():
        print(f"  {s}: {len(df)} barras H1 ({df.index[0]:%d/%m/%Y} → {df.index[-1]:%d/%m/%Y})", flush=True)
    st = strength_series(data)
    print(f"força relativa vetorizada: diferença máx. vs motor = {check_strength(data, st):.2f} pontos (de ±100)")
    with ProcessPoolExecutor(a.workers) as ex:
        parts = list(ex.map(replay_symbol, [(s, data[s], st[s], a.grid) for s in UNIVERSE]))
    df = pd.concat(parts, ignore_index=True).sort_values(["time", "symbol"]).reset_index(drop=True)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    df.to_pickle(a.out)
    print(f"{len(df)} barras · {df.symbol.nunique()} ativos · {df.time.min():%d/%m/%Y} → {df.time.max():%d/%m/%Y} "
          f"· {time.time() - t0:.0f} s → {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

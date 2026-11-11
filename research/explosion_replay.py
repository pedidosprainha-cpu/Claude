"""Historical replay for the price-explosion detector (H1, ~2.6 years, 32 instruments).

At every closed H1 bar it stores the features of fxengine.analysis.explosion.feature_frame
(the same function the live scan uses) and what happened next:

  exc / up / dn       largest move away from the decision close within the next 4 bars, in
                      ADR units (either side / upwards / downwards)
  first_<theta>       which side reached theta x ADR first (+1 up, -1 down, 0 none, 2 same bar)
  oco|e|s|x           R of a bracket (OCO) order: buy stop and sell stop e x ADR away from the
                      close (valid 4 bars, spread included, a bar touching both = loss), stop
                      s = "opp" (the other side of the bracket) or "half" (back to the close),
                      exit x = tp2 (2R) or tr (after +1R trail 1R behind the best price),
                      closed at market 12 bars after the fill

    python3 research/explosion_replay.py --out research/data/explosion_events.pkl
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

from signal_replay import exits, load_h1  # noqa: E402

from fxengine.analysis import explosion as ex  # noqa: E402
from fxengine.instruments import UNIVERSE, typical_spread_pips  # noqa: E402

HORIZON = 4          # bars to detect the explosion
HOLD = 12            # bars a bracket trade may stay open after the fill
THETAS = (0.3, 0.4, 0.5)
OFFSETS = (0.10, 0.20)
STOPS = ("opp", "half")
EXITS = {"tp2": ("tp", 2.0), "tr": ("trail", 1.0)}


def bracket(o, h, l, c, adr, idx, e, stop, xk, half):
    """R of an OCO bracket placed at the close of each bar in idx."""
    n = len(c)
    a = adr[idx]
    buy = c[idx] + e * a + half                   # ask trigger
    sell = c[idx] - e * a - half                  # bid trigger
    W = np.lib.stride_tricks.sliding_window_view
    Hw, Lw = W(h, HORIZON)[idx + 1], W(l, HORIZON)[idx + 1]
    hit_b = (Hw + half) >= buy[:, None]
    hit_s = (Lw - half) <= sell[:, None]
    kb = np.where(hit_b.any(1), hit_b.argmax(1), HORIZON)
    ks = np.where(hit_s.any(1), hit_s.argmax(1), HORIZON)
    filled = (kb < HORIZON) | (ks < HORIZON)
    both = filled & (kb == ks)
    d = np.where(kb < ks, 1, -1)
    k = np.minimum(kb, ks)
    fbar = idx + 1 + np.minimum(k, HORIZON - 1)
    op = o[fbar]
    fill = np.where(d == 1, np.maximum(buy, op + half), np.minimum(sell, op - half))
    risk = (buy - sell) if stop == "opp" else e * a
    risk = np.maximum(risk, 8 * half)
    r = np.zeros(len(idx))
    ok = filled & ~both & (fbar + HOLD < n)
    if ok.any():
        fb = fbar[ok]
        cols = fb[:, None] + np.arange(HOLD)[None, :]
        hh, ll = h[cols], l[cols]
        dd, ff, rk = d[ok], fill[ok], risk[ok]
        fav = np.where(dd[:, None] == 1, hh - half - ff[:, None], ff[:, None] - (ll + half))
        adv = np.where(dd[:, None] == 1, ll - half - ff[:, None], ff[:, None] - (hh + half))
        last = c[fb + HOLD - 1]
        closeR = np.where(dd == 1, last - half - ff, ff - (last + half)) / rk
        kind, val = EXITS[xk]
        tR = np.ones(ok.sum()) * val if kind == "trail" else np.zeros(ok.sum())
        rr, _ = exits(fav / rk[:, None], adv / rk[:, None], closeR, kind, val, tR)
        r[ok] = rr
    r[both] = -1.0
    r[~filled] = np.nan                                  # no trade
    return r.astype("float32"), d.astype("int8")


def replay_symbol(args) -> pd.DataFrame:
    sym, h1 = args
    inst = UNIVERSE[sym]
    half = typical_spread_pips(sym) * inst.pip / 2
    ff = ex.feature_frame(h1, inst.is_metal, HORIZON)
    o, h, l, c = (h1[k].to_numpy() for k in ("o", "h", "l", "c"))
    adr = ff["adr"].to_numpy()
    n = len(c)
    idx = np.arange(ex.WARMUP_BARS, n - HORIZON - HOLD - 2)
    idx = idx[np.isfinite(adr[idx]) & (adr[idx] > 0)]
    W = np.lib.stride_tricks.sliding_window_view
    Hw, Lw = W(h, HORIZON)[idx + 1], W(l, HORIZON)[idx + 1]
    up = (Hw.max(1) - c[idx]) / adr[idx]
    dn = (c[idx] - Lw.min(1)) / adr[idx]
    out = ff.iloc[idx][ex.FEATURES + ex.DIR_FEATURES].astype("float32").reset_index()
    out = out.rename(columns={out.columns[0]: "time"})
    out.insert(0, "symbol", sym)
    out["up"], out["dn"] = up.astype("float32"), dn.astype("float32")
    out["exc"] = np.maximum(up, dn).astype("float32")
    for th in THETAS:
        cu = (Hw - c[idx][:, None]) / adr[idx][:, None] >= th
        cd = (c[idx][:, None] - Lw) / adr[idx][:, None] >= th
        ku = np.where(cu.any(1), cu.argmax(1), HORIZON)
        kd = np.where(cd.any(1), cd.argmax(1), HORIZON)
        first = np.where((ku == HORIZON) & (kd == HORIZON), 0, np.where(ku == kd, 2, np.where(ku < kd, 1, -1)))
        out[f"first_{th}"] = first.astype("int8")
    for e in OFFSETS:
        for s in STOPS:
            for xk in EXITS:
                r, d = bracket(o, h, l, c, adr, idx, e, s, xk, half)
                out[f"oco|{e}|{s}|{xk}"] = r
        out[f"oco_dir|{e}"] = d
    out["spread_adr"] = (2 * half / adr[idx]).astype("float32")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "research", "data", "explosion_events.pkl"))
    ap.add_argument("--cache", default=os.path.join(ROOT, ".cache", "research"))
    ap.add_argument("--ttl-days", type=float, default=3.0)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    t0 = time.time()
    data = load_h1(a.cache, a.ttl_days)
    with ProcessPoolExecutor(a.workers) as pool:
        parts = list(pool.map(replay_symbol, [(s, data[s]) for s in UNIVERSE]))
    df = pd.concat(parts, ignore_index=True).sort_values(["time", "symbol"]).reset_index(drop=True)
    df.to_pickle(a.out)
    print(f"{len(df)} barras · {df.symbol.nunique()} ativos · {df.time.min():%d/%m/%Y} → {df.time.max():%d/%m/%Y} "
          f"· {time.time() - t0:.0f} s → {a.out}")
    for th in THETAS:
        print(f"  movimento ≥ {th:.1f}× ADR em {HORIZON}h: {(df.exc >= th).mean() * 100:.1f}% das horas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Walk-forward replay of the real-time breakout detector.

Re-runs `fxengine.breakouts.detect` at every M15 close of the last ~60 trading
days, exactly as the app's monitor would have seen the market at that instant
(5 days of M15 + 1 month of H1, current H1 bar still forming, no future data),
keeps only events the tracker flags as *new* (= what would have triggered an
alert) and labels each one by simulating the proposed market order on the
following M15 bars:

  y_tp1       1 if target 1 was hit before the stop (bid/ask aware, stop first
              when both are touched in the same bar), else 0
  r_tp1       R of a plain TP1/SL trade (timeout marked to market)
  r_managed   R with 50% at TP1, stop to entry, rest to TP2
  y_atr       1 if price moved +1 ATR before -1 ATR

Output: one CSV row per event with the detector's features, the old rule-based
grade/actionable flag and the labels. Usage:

    python research/breakout_replay.py --out research/data/breakout_events.csv
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from fxengine import breakouts as bk  # noqa: E402
from fxengine import sessions  # noqa: E402
from fxengine.analysis import strength as strength_mod  # noqa: E402
from fxengine.config import Settings  # noqa: E402
from fxengine.data import yahoo  # noqa: E402
from fxengine.data.http import Http  # noqa: E402
from fxengine.data.provider import InstrumentData, build_frames  # noqa: E402
from fxengine.instruments import FX_PAIRS, UNIVERSE  # noqa: E402

M15_BARS = 480            # live profile: 5 days of M15
H1_BARS = 528             # live profile: ~1 month of H1
HORIZON = {"M15": 32, "H1": 96}   # M15 bars to resolve a trade (8h / 24h)
MAJORS = {"EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"}
METAL_SPREAD = {"XAUUSD": 3.0, "XAGUSD": 3.0, "XPTUSD": 40.0, "XPDUSD": 60.0}


def spread_pips(sym: str) -> float:
    """Conservative typical retail spreads (no historical bid/ask is available)."""
    if sym in METAL_SPREAD:
        return METAL_SPREAD[sym]
    if sym in MAJORS:
        return 1.0
    if sym in {"EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURCHF", "CADJPY", "CHFJPY"}:
        return 1.8
    return 2.6


class StrengthAt:
    """Duck-typed StrengthResult for one hour (precomputed pair scores)."""

    def __init__(self, scores: dict[str, float] | None):
        self.scores = scores or {}

    def pair_score(self, base: str, quote: str) -> float:
        return self.scores.get(base + quote, 0.0)


def load_data(cache_dir: str) -> dict[str, tuple[pd.DataFrame, pd.DataFrame]]:
    http = Http(cache_dir, timeout=40)
    out = {}
    for sym, inst in UNIVERSE.items():
        m15, _ = yahoo.candles(http, inst.yahoo, "15m", "60d", ttl=24 * 3600)
        h1, _ = yahoo.candles(http, inst.yahoo, "1h", "6mo", ttl=24 * 3600)
        out[sym] = (m15, h1)
        print(f"  {sym}: M15 {len(m15)} barras ({m15.index[0]:%d/%m} → {m15.index[-1]:%d/%m}), H1 {len(h1)}",
              flush=True)
    return out


def strength_by_hour(data, hours: pd.DatetimeIndex) -> dict:
    fx = {i.symbol: data[i.symbol][1] for i in FX_PAIRS}
    res = {}
    for h in hours:
        sl = {k: v[v.index + pd.Timedelta(hours=1) <= h].iloc[-H1_BARS:] for k, v in fx.items()}
        if min(len(v) for v in sl.values()) < 150:
            continue
        st = strength_mod.compute(sl)
        res[h] = {p.symbol: st.pair_score(p.base, p.quote) for p in FX_PAIRS}
    return res


def h1_view(h1: pd.DataFrame, m15: pd.DataFrame, i: int, now: pd.Timestamp) -> pd.DataFrame:
    """Closed H1 bars + the forming H1 bar rebuilt from the M15 bars of the current hour."""
    hour = now.floor("1h")
    closed = h1[h1.index + pd.Timedelta(hours=1) <= now].iloc[-H1_BARS:]
    part = m15.iloc[max(0, i - 4):i + 1]
    part = part[part.index >= hour]
    if len(part):
        row = pd.DataFrame({"o": [part.o.iloc[0]], "h": [part.h.max()], "l": [part.l.min()],
                            "c": [part.c.iloc[-1]], "v": [0.0]}, index=pd.DatetimeIndex([hour]))
        closed = pd.concat([closed[closed.index < hour], row])
    return closed


STOPS = {"p": None, "h075": 0.75, "h1": 1.0, "h15": 1.5}      # stop = max(plan stop, k x ATR H1)
TARGETS = {"p": None, "r1": 1.0, "r15": 1.5, "r2": 2.0}       # target = plan TP1 or k x stop
GEO_H = 96                                                      # 24h of M15 bars for every geometry


def geometry_labels(m15: pd.DataFrame, i: int, b: bk.Breakout, half: float, atr_h1: float) -> dict | None:
    """Outcome of the same entry under alternative stop/target geometries (vectorised)."""
    if i + GEO_H >= len(m15):
        return None
    d, p = b.direction, b.plan
    entry = p.entry
    plan_sl, plan_tp = abs(entry - p.sl), abs(p.tp1 - entry)
    hi = m15.h.to_numpy()[i + 1:i + 1 + GEO_H]
    lo = m15.l.to_numpy()[i + 1:i + 1 + GEO_H]
    last = m15.c.to_numpy()[i + GEO_H]
    if d == 1:
        fav, adv, exit_last = hi - half, lo - half, last - half
    else:
        fav, adv, exit_last = lo + half, hi + half, last + half
    out = {"spread": 2 * half, "atr_h1": atr_h1, "plan_sl": plan_sl, "plan_tp": plan_tp}
    for sk, sm in STOPS.items():
        sl_d = plan_sl if sm is None else max(plan_sl, sm * atr_h1)
        hit_sl = (adv <= entry - sl_d) if d == 1 else (adv >= entry + sl_d)
        i_sl = int(np.argmax(hit_sl)) if hit_sl.any() else GEO_H
        for tk, tm in TARGETS.items():
            tp_d = plan_tp if tm is None else tm * sl_d
            hit_tp = (fav >= entry + tp_d) if d == 1 else (fav <= entry - tp_d)
            i_tp = int(np.argmax(hit_tp)) if hit_tp.any() else GEO_H
            if i_sl < GEO_H and i_sl <= i_tp:
                y, r = 0, -1.0
            elif i_tp < GEO_H:
                y, r = 1, tp_d / sl_d
            else:
                y, r = 0, d * (exit_last - entry) / sl_d
            out[f"y_{sk}_{tk}"] = y
            out[f"r_{sk}_{tk}"] = round(r, 4)
            out[f"sl_{sk}"] = sl_d
    return out


def simulate(m15: pd.DataFrame, i: int, b: bk.Breakout, half: float) -> dict | None:
    H = HORIZON[b.tf]
    if i + H >= len(m15):
        return None
    d, p = b.direction, b.plan
    entry, sl, tp1, tp2 = p.entry, p.sl, p.tp1, p.tp2
    sl_d = abs(entry - sl)
    hi = m15.h.to_numpy()[i + 1:i + 1 + H]
    lo = m15.l.to_numpy()[i + 1:i + 1 + H]
    cl = m15.c.to_numpy()[i + 1:i + 1 + H]
    # exits happen on the opposite side of the book
    ex_hi, ex_lo = (hi - half, lo - half) if d == 1 else (hi + half, lo + half)

    def hits(k, level, favourable):
        if d == 1:
            return ex_hi[k] >= level if favourable else ex_lo[k] <= level
        return ex_lo[k] <= level if favourable else ex_hi[k] >= level

    y_tp1, r_tp1, r_man, k_tp1 = 0, None, None, None
    for k in range(H):
        if hits(k, sl, False):
            r_tp1 = r_man = -1.0
            break
        if hits(k, tp1, True):
            y_tp1, r_tp1, k_tp1 = 1, p.rr1, k
            break
    if r_tp1 is None:
        last = (cl[-1] - half) if d == 1 else (cl[-1] + half)
        r_tp1 = r_man = d * (last - entry) / sl_d
    if k_tp1 is not None:                       # 50% off at TP1, stop to entry, run to TP2
        rest = None
        for k in range(k_tp1 + 1, H):
            if hits(k, entry, False):
                rest = 0.0
                break
            if hits(k, tp2, True):
                rest = p.rr2
                break
        if rest is None:
            last = (cl[-1] - half) if d == 1 else (cl[-1] + half)
            rest = max(d * (last - entry) / sl_d, 0.0)
        r_man = 0.5 * p.rr1 + 0.5 * rest
    a = b.atr
    y_atr = 0
    for k in range(H):
        up = (hi[k] - entry) * d if d == 1 else (entry - lo[k])
        dn = (entry - lo[k]) if d == 1 else (hi[k] - entry)
        if dn >= a:
            break
        if up >= a:
            y_atr = 1
            break
    return {"y_tp1": y_tp1, "r_tp1": r_tp1, "r_managed": r_man, "y_atr": y_atr}


def replay(sym: str, m15: pd.DataFrame, h1: pd.DataFrame, strength: dict, start: pd.Timestamp) -> list[dict]:
    inst = UNIVERSE[sym]
    s = Settings()
    half = spread_pips(sym) * inst.pip / 2
    tracker = bk.Tracker(None)
    rows: list[dict] = []
    cache, cache_hour = {}, None
    idx = m15.index
    for i in range(len(m15)):
        if idx[i] < start or i < M15_BARS:
            continue
        now = idx[i] + pd.Timedelta(minutes=15, seconds=1)
        frames = build_frames(None, m15.iloc[i - M15_BARS + 1:i + 1], h1_view(h1, m15, i, now))
        if len(frames["H1"]) < 200:
            continue
        price = float(m15.c.iloc[i])
        data = InstrumentData(inst, frames, price, price - half, price + half, now.to_pydatetime(),
                              "replay", True, [])
        hour = now.floor("1h")
        if hour != cache_hour:
            cache, cache_hour = {}, hour
        sess = sessions.state(now.to_pydatetime())
        st = StrengthAt(strength.get(hour)) if not inst.is_metal else None
        evs = bk.detect(data, now.to_pydatetime(), s, {sym: price}, st, [], sess, cache=cache, model=bk.NO_MODEL)
        tracker.mark(evs, now.to_pydatetime())
        for b in evs:
            if not b.is_new:
                continue
            lab = simulate(m15, i, b, half)
            geo = geometry_labels(m15, i, b, half, cache.get("atr_h1") or b.atr)
            if lab is None or geo is None:
                continue
            row = {"symbol": sym, "time": now.isoformat(), "tf": b.tf, "status": b.status,
                   "kind": b.level.kind, "direction": b.direction, "break_dir": b.break_dir,
                   "grade_old": b.grade, "score_old": b.heuristic, "actionable_old": int(b.actionable),
                   "rr1": b.plan.rr1, "rr2": b.plan.rr2, "extended": int(b.extended),
                   "level": b.level.price, "entry": b.plan.entry, "mid": b.price, "atr_tf": b.atr,
                   "extreme": b.extreme, "bar_i": i}
            row.update({f"f_{k}": v for k, v in b.features.items()})
            row.update(lab)
            row.update(geo)
            rows.append(row)
    return rows


def _job(args):
    sym, m15, h1, strength, start = args
    t = time.time()
    rows = replay(sym, m15, h1, strength, start)
    return sym, rows, time.time() - t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "research", "data", "breakout_events.csv"))
    ap.add_argument("--cache", default=os.path.join(ROOT, ".cache", "research"))
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--symbols", default="")
    a = ap.parse_args()

    print("Baixando histórico (M15 60 dias, H1 6 meses)…", flush=True)
    data = load_data(a.cache)
    syms = [x.strip().upper() for x in a.symbols.split(",") if x.strip()] or list(UNIVERSE)
    first = min(data[i.symbol][0].index[M15_BARS] for i in FX_PAIRS)
    end = max(v[0].index[-1] for v in data.values())
    hours = pd.date_range(first.floor("1h"), end.ceil("1h"), freq="1h")
    print(f"Força relativa por hora ({len(hours)} horas)…", flush=True)
    strength = strength_by_hour(data, hours)

    rows: list[dict] = []
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(_job, (sym, data[sym][0], data[sym][1], strength, first)) for sym in syms]
        for f in as_completed(futs):
            sym, r, dt = f.result()
            rows += r
            print(f"  {sym}: {len(r)} eventos ({dt:.0f}s)", flush=True)
    df = pd.DataFrame(rows).sort_values("time")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    df.to_csv(a.out, index=False)
    print(f"{len(df)} eventos em {time.time() - t0:.0f}s → {a.out}")
    print(f"período: {df.time.min()} → {df.time.max()}")
    print(df.groupby("status")[["y_tp1", "r_tp1", "r_managed"]].mean().round(3))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Two-year walk-forward replay of the H1 breakout detector.

Yahoo keeps 15-minute data for only ~60 days but hourly data for ~730 days,
so H1 breakouts can be validated across many more market regimes. At every H1
close the detector sees exactly what the live monitor's H1 path sees (one month
of H1, H4/D1/W1 derived from it, no future data); new events are stored with
the fields the entry/exit lab needs to simulate trades on the following bars.

    python research/breakout_replay_h1.py --out research/data/breakout_events_h1.csv
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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from breakout_replay import H1_BARS, StrengthAt, spread_pips  # noqa: E402

from fxengine import breakouts as bk  # noqa: E402
from fxengine import sessions  # noqa: E402
from fxengine.analysis import strength as strength_mod  # noqa: E402
from fxengine.config import Settings  # noqa: E402
from fxengine.data import yahoo  # noqa: E402
from fxengine.data.http import Http  # noqa: E402
from fxengine.data.provider import InstrumentData, build_frames  # noqa: E402
from fxengine.instruments import FX_PAIRS, UNIVERSE  # noqa: E402


def load_h1(cache_dir: str) -> dict[str, pd.DataFrame]:
    http = Http(cache_dir, timeout=60)
    out = {}
    for sym, inst in UNIVERSE.items():
        h1, _ = yahoo.candles(http, inst.yahoo, "1h", "730d", ttl=7 * 24 * 3600)
        out[sym] = h1
        print(f"  {sym}: H1 {len(h1)} barras ({h1.index[0]:%d/%m/%Y} → {h1.index[-1]:%d/%m/%Y})", flush=True)
    return out


def strength_by_4h(data: dict[str, pd.DataFrame]) -> dict:
    fx = {i.symbol: data[i.symbol] for i in FX_PAIRS}
    start = max(v.index[H1_BARS] for v in fx.values())
    end = min(v.index[-1] for v in fx.values())
    res = {}
    for t in pd.date_range(start.ceil("4h"), end, freq="4h"):
        sl = {k: v[v.index < t].iloc[-H1_BARS:] for k, v in fx.items()}
        st = strength_mod.compute(sl)
        res[t] = {p.symbol: st.pair_score(p.base, p.quote) for p in FX_PAIRS}
    return res


def replay(sym: str, h1: pd.DataFrame, strength: dict) -> list[dict]:
    inst = UNIVERSE[sym]
    s = Settings()
    half = spread_pips(sym) * inst.pip / 2
    tracker = bk.Tracker(None)
    rows: list[dict] = []
    cache, bucket = {}, None
    for i in range(H1_BARS, len(h1) - 1):
        now = h1.index[i] + pd.Timedelta(hours=1, seconds=1)
        h1s = h1.iloc[i - H1_BARS + 1:i + 1]
        frames = build_frames(None, h1s, h1s)
        frames.pop("M15")                        # H1 path only
        price = float(h1.c.iloc[i])
        data = InstrumentData(inst, frames, price, price - half, price + half, now.to_pydatetime(),
                              "replay", True, [])
        b4 = now.floor("4h")
        if b4 != bucket:
            cache, bucket = {}, b4
        st = StrengthAt(strength.get(b4)) if not inst.is_metal else None
        evs = bk.detect(data, now.to_pydatetime(), s, {sym: price}, st, [], sessions.state(now.to_pydatetime()),
                        cache=cache, model=bk.NO_MODEL)
        tracker.mark(evs, now.to_pydatetime())
        for b in evs:
            if not b.is_new or b.tf != "H1":
                continue
            row = {"symbol": sym, "time": now.isoformat(), "tf": b.tf, "status": b.status,
                   "kind": b.level.kind, "direction": b.direction, "break_dir": b.break_dir,
                   "score_old": b.heuristic, "actionable_old": int(b.actionable), "extended": int(b.extended),
                   "rr1": b.plan.rr1, "level": b.level.price, "entry": b.plan.entry, "mid": b.price,
                   "atr_tf": b.atr, "atr_h1": cache.get("atr_h1") or b.atr, "extreme": b.extreme,
                   "plan_sl": abs(b.plan.entry - b.plan.sl), "plan_tp": abs(b.plan.tp1 - b.plan.entry),
                   "spread": 2 * half, "bar_i": i}
            row.update({f"f_{k}": v for k, v in b.features.items()})
            rows.append(row)
    return rows


def _job(args):
    sym, h1, strength = args
    t = time.time()
    return sym, replay(sym, h1, strength), time.time() - t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "research", "data", "breakout_events_h1.csv"))
    ap.add_argument("--cache", default=os.path.join(ROOT, ".cache", "research"))
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--symbols", default="")
    a = ap.parse_args()
    print("Baixando H1 de 2 anos…", flush=True)
    data = load_h1(a.cache)
    print("Força relativa a cada 4h…", flush=True)
    strength = strength_by_4h(data)
    syms = [x.strip().upper() for x in a.symbols.split(",") if x.strip()] or list(UNIVERSE)
    rows: list[dict] = []
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(_job, (sym, data[sym], strength)) for sym in syms]
        for f in as_completed(futs):
            sym, r, dt = f.result()
            rows += r
            print(f"  {sym}: {len(r)} eventos ({dt:.0f}s)", flush=True)
    df = pd.DataFrame(rows).sort_values("time")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    df.to_csv(a.out, index=False)
    print(f"{len(df)} eventos em {time.time() - t0:.0f}s → {a.out} ({df.time.min()} → {df.time.max()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

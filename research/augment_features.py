"""Add the context features (fxengine.breakouts.context_features) to replayed events.

Rebuilds, for every event, the exact H1 window the live monitor saw at alert time
(H1 replay: the last 528 closed bars; M15 replay: closed H1 bars + the forming
H1 bar rebuilt from M15) and calls the same function the app uses, so training
and live values are identical. Row order is preserved (lab results join on it).

    python research/augment_features.py --events research/data/breakout_events_h1.csv --bars h1
    python research/augment_features.py --events research/data/breakout_events.csv --bars m15
"""
from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from breakout_replay import H1_BARS, h1_view  # noqa: E402

from fxengine.breakouts import context_features  # noqa: E402
from fxengine.data import yahoo  # noqa: E402
from fxengine.data.http import Http  # noqa: E402
from fxengine.instruments import UNIVERSE  # noqa: E402


def _job(args):
    kind, rows, h1, m15 = args
    out = []
    for r in rows.itertuples():
        now = pd.Timestamp(r.time)
        if kind == "h1":
            i = int(r.bar_i)
            assert h1.index[i] + pd.Timedelta(hours=1, seconds=1) == now, "H1 data does not match the replay"
            win = h1.iloc[max(0, i - H1_BARS + 1):i + 1]
        else:
            i = int(r.bar_i)
            assert m15.index[i] + pd.Timedelta(minutes=15, seconds=1) == now, "M15 data does not match the replay"
            win = h1_view(h1, m15, i, now)
        f = context_features(win, float(r.mid), int(r.direction), now.to_pydatetime())
        out.append((r.Index, f))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", required=True)
    ap.add_argument("--bars", choices=("h1", "m15"), required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--cache", default=os.path.join(ROOT, ".cache", "research"))
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    ev = pd.read_csv(a.events)
    http = Http(a.cache, timeout=60)
    jobs = []
    for sym, g in ev.groupby("symbol"):
        y = UNIVERSE[sym].yahoo
        if a.bars == "h1":
            h1, _ = yahoo.candles(http, y, "1h", "730d", ttl=30 * 24 * 3600)
            m15 = None
        else:
            h1, _ = yahoo.candles(http, y, "1h", "6mo", ttl=30 * 24 * 3600)
            m15, _ = yahoo.candles(http, y, "15m", "60d", ttl=30 * 24 * 3600)
        jobs.append((a.bars, g, h1, m15))
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        results = [x for part in ex.map(_job, jobs) for x in part]
    feats = pd.DataFrame({idx: f for idx, f in results}).T.add_prefix("f_")
    for c in feats.columns:
        ev[c] = feats[c].astype(float)
    out = a.out or a.events.replace(".csv", "_ctx.csv")
    ev.to_csv(out, index=False)
    print(f"{len(feats)} eventos com contexto → {out}")
    print(ev[[c for c in feats.columns]].describe().T[["mean", "std", "min", "max"]].round(3))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

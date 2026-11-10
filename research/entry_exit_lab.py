"""Entry/exit laboratory for breakout alerts.

For every replayed alert, simulates on the bars that followed it (bid/ask
aware, stop checked first when a bar touches both) a grid of:

  entry  mercado      market order at the alert close (what the app does today)
         confirmacao  wait one bar; enter at its close only if it closed in favour
         reteste      limit order back at the broken level (+0.1 ATR), valid W bars
         meio         limit order at 50% between level and alert price, valid W bars
  stop   n05 / n10    anchored beyond the level (0.5 / 1.0 ATR H1); traps: beyond the extreme
         a10 / a15    1.0 / 1.5 ATR H1 from the fill
  exit   tp15/tp2/tp3 fixed target at 1.5 / 2 / 3 R
         be2 / be3    stop to break-even at +1R, target 2 / 3 R
         tr10 / tr15  after +1R trail the stop 1.0 / 1.5 ATR H1 behind the best price

Variants are ranked by their WORST time block (robustness across regimes),
never by the average alone.

    python research/entry_exit_lab.py --events research/data/breakout_events_h1.csv --bars h1
    python research/entry_exit_lab.py --events research/data/breakout_events.csv --bars m15
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fxengine.data import yahoo  # noqa: E402
from fxengine.data.http import Http  # noqa: E402
from fxengine.instruments import UNIVERSE  # noqa: E402

ENTRIES = ("mercado", "confirmacao", "reteste", "meio")
STOPS = {"n05": ("level", 0.5), "n10": ("level", 1.0), "a10": ("fill", 1.0), "a15": ("fill", 1.5)}
EXITS = {"tp15": ("tp", 1.5), "tp2": ("tp", 2.0), "tp3": ("tp", 3.0), "be2": ("be", 2.0), "be3": ("be", 3.0),
         "tr10": ("trail", 1.0), "tr15": ("trail", 1.5)}
CFG = {"m15": {"interval": "15m", "range": "60d", "horizon": 96, "window": 8},
       "h1": {"interval": "1h", "range": "730d", "horizon": 48, "window": 6}}


def load_bars(kind: str, symbols, cache: str) -> dict[str, pd.DataFrame]:
    http = Http(cache, timeout=60)
    c = CFG[kind]
    return {s: yahoo.candles(http, UNIVERSE[s].yahoo, c["interval"], c["range"], ttl=30 * 24 * 3600)[0]
            for s in symbols}


def _first(mask: np.ndarray) -> int:
    return int(np.argmax(mask)) if mask.any() else -1


def exit_r(favR: np.ndarray, advR: np.ndarray, closeR_last: float, kind: str, val: float, tR: float) -> float:
    """R of a trade given favourable/adverse excursions per bar (in R units, from the fill)."""
    n = len(favR)
    if n == 0:
        return 0.0
    if kind == "tp":
        i_sl, i_tp = _first(advR <= -1), _first(favR >= val)
        if i_sl >= 0 and (i_tp < 0 or i_sl <= i_tp):
            return -1.0
        return val if i_tp >= 0 else closeR_last
    if kind == "be":
        i_sl, i_1 = _first(advR <= -1), _first(favR >= 1)
        if i_sl >= 0 and (i_1 < 0 or i_sl <= i_1):
            return -1.0
        if i_1 < 0:
            return closeR_last
        if favR[i_1] >= val:
            return val
        rest_f, rest_a = favR[i_1 + 1:], advR[i_1 + 1:]
        j_be, j_tp = _first(rest_a <= 0), _first(rest_f >= val)
        if j_be >= 0 and (j_tp < 0 or j_be <= j_tp):
            return 0.0
        return val if j_tp >= 0 else max(closeR_last, 0.0)
    # trailing: initial stop -1R; after the best excursion reached +1R the stop trails
    # tR behind the best excursion of the previous bars, never below break-even
    prev_best = np.concatenate([[-np.inf], np.maximum.accumulate(favR)[:-1]])
    active = prev_best >= 1
    stop = np.where(active, np.maximum(prev_best - tR, 0.0), -1.0)
    hit = _first(advR <= stop)
    return float(stop[hit]) if hit >= 0 else closeR_last


def simulate_symbol(args) -> pd.DataFrame:
    rows, bars, horizon, window = args
    idx = bars.index
    o, h, l, c = (bars[k].to_numpy() for k in ("o", "h", "l", "c"))
    out = []
    for r in rows.itertuples(index=False):
        t_open = pd.Timestamp(r.time) - pd.Timedelta(seconds=1) - (pd.Timedelta(hours=1) if r.tf_bars == "h1"
                                                                    else pd.Timedelta(minutes=15))
        i = idx.searchsorted(t_open)
        if i >= len(idx) or idx[i] != t_open or i + horizon + window + 1 >= len(idx):
            continue
        td, bd, half = int(r.direction), int(r.break_dir), r.spread / 2
        L, a_tf, a_h1, mid = r.level, r.atr_tf, r.atr_h1, r.mid
        trap = r.status == "falso"
        res = {"eid": r.eid}
        for em in ENTRIES:
            # ---------------------------------------------------------- fill
            k0, fill = None, None
            if em == "mercado":
                k0, fill = i + 1, mid + td * half
            elif em == "confirmacao":
                if td * (c[i + 1] - mid) > 0:
                    k0, fill = i + 2, c[i + 1] + td * half
            else:
                limit = (L + td * 0.1 * a_tf) if em == "reteste" else (mid - td * 0.5 * abs(mid - L))
                if td * ((mid + td * half) - limit) <= 0:          # market already at/through the limit
                    k0, fill = i + 1, mid + td * half
                else:
                    seg_l = l[i + 1:i + 1 + window] + half if td == 1 else h[i + 1:i + 1 + window] - half
                    hit = _first(seg_l <= limit) if td == 1 else _first(seg_l >= limit)
                    if hit >= 0:
                        k0, fill = i + 1 + hit, limit           # fill bar itself is checked for the stop
            if k0 is None:
                for sk in STOPS:
                    res[f"sl|{em}|{sk}"] = np.nan
                    for xk in EXITS:
                        res[f"{em}|{sk}|{xk}"] = np.nan
                continue
            hh, ll, cc = h[k0:k0 + horizon], l[k0:k0 + horizon], c[min(k0 + horizon, len(c) - 1)]
            fav_px = hh - half if td == 1 else ll + half
            adv_px = ll - half if td == 1 else hh + half
            exit_last = cc - td * half
            for sk, (anchor, m) in STOPS.items():
                if anchor == "level":
                    sl_px = (r.extreme + bd * m * 0.5 * a_h1) if trap else (L - td * m * a_h1)
                    sl_d = td * (fill - sl_px)
                else:
                    sl_d = m * a_h1
                sl_d = max(sl_d, 0.3 * a_h1, 8 * half)
                res[f"sl|{em}|{sk}"] = round(sl_d, 8)
                favR = td * (fav_px - fill) / sl_d
                advR = td * (adv_px - fill) / sl_d
                closeR = td * (exit_last - fill) / sl_d
                for xk, (kind, val) in EXITS.items():
                    tR = val * a_h1 / sl_d if kind == "trail" else 0.0
                    res[f"{em}|{sk}|{xk}"] = round(exit_r(favR, advR, closeR, kind, val, tR), 4)
        out.append(res)
    return pd.DataFrame(out)


def summarize(ev: pd.DataFrame, sim: pd.DataFrame, n_blocks: int, label: str) -> pd.DataFrame:
    df = ev.merge(sim, on="eid")
    df["t"] = pd.to_datetime(df.time, utc=True)
    days = np.sort(df.t.dt.floor("D").unique())
    edges = [days[int(len(days) * q / n_blocks)] for q in range(1, n_blocks)]
    df["block"] = np.searchsorted(np.array(edges), df.t.dt.floor("D").to_numpy(), side="right")
    nd = len(days)
    var_cols = [c for c in sim.columns if c.count("|") == 2 and not c.startswith("sl|")]
    rows = []
    for v in var_cols:
        filled = df[v].notna()
        per = df[filled].groupby("block")[v].mean()
        cnt = df[filled].groupby("block")[v].size()
        rows.append({"variante": v, "trades": int(filled.sum()), "por_dia": round(filled.sum() / nd, 1),
                     "preenchidas": round(float(filled.mean()), 3), "R_medio": round(float(df.loc[filled, v].mean()), 4),
                     "pior_bloco": round(float(per.min()), 4), "melhor_bloco": round(float(per.max()), 4),
                     "blocos_positivos": int((per > 0).sum()), "min_trades_bloco": int(cnt.min())})
    out = pd.DataFrame(rows).sort_values("pior_bloco", ascending=False)
    print(f"\n=== {label}: {len(df)} alertas, {nd} dias, {n_blocks} blocos ===")
    print(out.head(15).to_string(index=False))
    base = out[out.variante == "mercado|a15|tp2"]
    if len(base):
        print("referência (app 1.2: mercado, stop 1,5 ATR, alvo ~2R):")
        print(base.to_string(index=False, header=False))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", required=True)
    ap.add_argument("--bars", choices=list(CFG), required=True)
    ap.add_argument("--blocks", type=int, default=6)
    ap.add_argument("--cache", default=os.path.join(ROOT, ".cache", "research"))
    ap.add_argument("--out", default="")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    ev = pd.read_csv(a.events)
    if "atr_h1" not in ev.columns:
        raise SystemExit("eventos sem atr_h1: rode a reconstituição atualizada")
    ev["eid"] = np.arange(len(ev))
    ev = ev[ev.extended == 0].copy()                       # the app never alerts extended moves
    ev["tf_bars"] = a.bars
    if a.bars == "m15":
        ev = ev[ev.tf == "M15"]
    cfg = CFG[a.bars]
    bars = load_bars(a.bars, sorted(ev.symbol.unique()), a.cache)
    jobs = [(g, bars[s], cfg["horizon"], cfg["window"]) for s, g in ev.groupby("symbol")]
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        sim = pd.concat(list(ex.map(simulate_symbol, jobs)), ignore_index=True)
    if a.out:
        sim.to_csv(a.out, index=False)
    res = summarize(ev, sim, a.blocks, f"{a.bars.upper()} — todos os alertas não esticados")
    res.to_csv(os.path.splitext(a.out or os.path.join(ROOT, "research", "data", f"lab_{a.bars}"))[0] + "_resumo.csv",
               index=False)
    print(json.dumps({"melhor_robusto": res.iloc[0].to_dict()}, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

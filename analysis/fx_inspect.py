#!/usr/bin/env python3
"""Detailed per-pair dump: M15 path of the current session, swing levels, multi-TF indicator state."""
import sys, os
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_analyze as A

def fmt(x, p): return f"{x:.3f}" if A.pip(p) >= 0.001 else f"{x:.5f}"

for p in sys.argv[1:]:
    r = A.analyze(p); pp = r["pip"]; i = r["ind"]; px = r["px"]
    print(f"\n===== {p}  px={fmt(px,p)} @ {r['t'].strftime('%H:%M:%S')}  dayO={fmt(r['day_open'],p)} H={fmt(r['day_hi'],p)} L={fmt(r['day_lo'],p)}  prevH={fmt(r['prev_hi'],p)} prevL={fmt(r['prev_lo'],p)} prevC={fmt(r['prev_cl'],p)}  ATRd={r['atr_d1']:.0f} ATRh1={r['atr_h1']:.1f}")
    for tf in ("m5","m15","h1","h4","d1"):
        x = i[tf]
        print(f"  {tf:>3}: stack={x['stack']:+d} e8={fmt(x['ema8'],p)} e20={fmt(x['ema20'],p)} e50={fmt(x['ema50'],p)} e200={fmt(x['ema200'],p) if not np.isnan(x['ema200']) else '-'} RSI={x['rsi']:.0f} ADX={x['adx']:.0f} DI+={x['pdi']:.0f} DI-={x['mdi']:.0f} MACDh={'+' if x['mh']>0 else '-'}{'^' if x['mh']>x['mh_prev'] else 'v'} BBw/med={x['bbw']/x['bbw_med']:.2f} BBpos={x['bbpos']:.2f}")
    m15 = r["m15"].iloc[-28:]
    print("  M15 (t o h l c):")
    print("   " + " | ".join(f"{t.strftime('%H:%M')} {fmt(b.h,p)}/{fmt(b.l,p)} c{fmt(b.c,p)}" for t, b in m15.iloc[-16:].iterrows()))
    m1 = r["m1"].iloc[-20:]
    print("  M1 last 20 closes:", " ".join(fmt(c,p) for c in m1.c))
    h1 = r["h1"]; d1 = r["d1"]
    hh, hl = A.pivots(h1.iloc[-240:], 4); dh, dl = A.pivots(d1.iloc[-130:], 3)
    above = sorted([(v, "H1sw " + t.strftime("%m-%d %H")) for t, v in hh.items() if v > px] + [(v, "D1sw " + t.strftime("%m-%d")) for t, v in dh.items() if v > px] + [(v, n) for v, n in ((r["prev_hi"], "prevH"), (r["day_hi"], "dayH")) if v > px])[:6]
    below = sorted([(v, "H1sw " + t.strftime("%m-%d %H")) for t, v in hl.items() if v < px] + [(v, "D1sw " + t.strftime("%m-%d")) for t, v in dl.items() if v < px] + [(v, n) for v, n in ((r["prev_lo"], "prevL"), (r["day_lo"], "dayL")) if v < px], reverse=True)[:6]
    print("  Res:", "; ".join(f"{fmt(v,p)} ({(v-px)/pp:+.0f}p {n})" for v, n in above))
    print("  Sup:", "; ".join(f"{fmt(v,p)} ({(v-px)/pp:+.0f}p {n})" for v, n in below))
    # last 10 daily bars
    print("  D1:", " ".join(f"{t.strftime('%m%d')}:{fmt(b.c,p)}" for t, b in d1.iloc[-10:].iterrows()))

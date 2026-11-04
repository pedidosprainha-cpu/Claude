#!/usr/bin/env python3
"""Final selector: combines trend, currency strength, momentum and *location*
(anti top-buying / bottom-selling) into one entry score per pair & direction.

Location rules (hard filters):
  * remaining ADR from the session extreme (session = since 22:00 UTC NY close)
    must be >= 35% of ATR-D1
  * RSI-M15 in trade direction <= 70 and RSI-H1 <= 72
  * |ext5| (distance from EMA20-M5) in trade direction <= 1.6 ATR-M5
  * distance to the next major barrier (prev-day extreme, 20-day extreme,
    session extreme already printed) >= 1.0 ATR-H1
"""
import json, os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fx_analyze import load, pip, ema

R = json.load(open(os.path.join(HERE, "results.json")))
S = R["strength"]
G8 = set(["EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "JPY"])
rows = []
for p, r in R["pairs"].items():
    m1, _ = load(p, "1m"); m5, _ = load(p, "5m"); d1, _ = load(p, "1d")
    pp = pip(p); px = float(m1.c.iloc[-1]); b, q = p[:3], p[3:]
    sess = m5[m5.index >= (m5.index[-1].normalize() - pd.Timedelta(hours=2))]
    s_hi, s_lo = sess.h.max(), sess.l.min()
    atr_d1 = r["atr_d1"] * pp; atr_h1 = r["atr_h1"] * pp
    prev_hi, prev_lo = d1.h.iloc[-2], d1.l.iloc[-2]
    hi20, lo20 = r["hi20"], r["lo20"]
    e8, e21 = ema(m1.c, 8).iloc[-1], ema(m1.c, 21).iloc[-1]
    for d in (1, -1):
        sc = r["score"][str(d)]
        al = r["align"]
        trend = (al["m5"] + al["m15"] + 1.5 * al["h1"] + 1.5 * al["h4"] + al["d1"]) * d
        # daily structure: last 4 completed days making lower highs+lows (d=-1) or higher (d=1)
        hh = np.sign(np.diff(d1.h.iloc[-6:-1].values)) * d
        ll = np.sign(np.diff(d1.l.iloc[-6:-1].values)) * d
        dstruct = float((hh > 0).sum() + (ll > 0).sum()) / 8  # 0..1
        if b in G8 and q in G8:
            csd = (S["d"][b] - S["d"][q]) * d; cs3 = (S["3h"][b] - S["3h"][q]) * d
            cs24 = (S["24h"][b] - S["24h"][q]) * d
        else:
            csd = cs3 = cs24 = 0.0
        travelled = (px - s_lo) if d == 1 else (s_hi - px)
        rem_adr = (atr_d1 - travelled) / atr_d1
        rsi15 = r["ind"]["m15"]["rsi"] if d == 1 else 100 - r["ind"]["m15"]["rsi"]
        rsi1h = r["ind"]["h1"]["rsi"] if d == 1 else 100 - r["ind"]["h1"]["rsi"]
        ext5 = r["ext5"] * d
        if d == 1:
            barriers = [x for x in (prev_hi, hi20, s_hi) if x > px + 0.5 * pp]
            room = (min(barriers) - px) if barriers else 3 * atr_h1
        else:
            barriers = [x for x in (prev_lo, lo20, s_lo) if x < px - 0.5 * pp]
            room = (px - max(barriers)) if barriers else 3 * atr_h1
        room_atr = room / atr_h1
        micro = float((px - e8) * d > 0) + float((e8 - e21) * d > 0)
        ok = (rem_adr >= 0.35) and rsi15 <= 70 and rsi1h <= 72 and ext5 <= 1.6 and room_atr >= 1.0
        total = (trend + 3 * dstruct + sc["mom"] + 40 * csd + 25 * cs3 + 15 * cs24
                 + 2 * min(rem_adr, 1) + min(room_atr, 3) + 0.5 * micro)
        rows.append(dict(pair=p, dir="BUY" if d == 1 else "SELL", ok=ok, total=round(total, 2),
                         px=px, trend=trend, dstr=round(dstruct, 2), mom=sc["mom"],
                         csd=round(csd, 3), cs3=round(cs3, 3), cs24=round(cs24, 3),
                         remADR=round(rem_adr, 2), room_atr=round(room_atr, 2),
                         room_pips=round(room / pp, 1), rsi15=round(rsi15), rsi1h=round(rsi1h),
                         ext5=round(ext5, 2), micro=micro, s_hi=s_hi, s_lo=s_lo,
                         atr_h1=round(r["atr_h1"], 1), atr_d1=round(r["atr_d1"], 1)))
df = pd.DataFrame(rows).set_index("pair")
df = df[df.trend > 0].sort_values("total", ascending=False)
pd.set_option("display.width", 260)
print("PASS location filters:")
print(df[df.ok].head(15).to_string())
print("\nTop rejected by location filters:")
print(df[~df.ok].head(12).to_string())

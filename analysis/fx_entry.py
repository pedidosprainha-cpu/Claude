#!/usr/bin/env python3
"""Entry-quality filter: locates each pair's latest M5 impulse leg (in the
direction chosen by fx_analyze) and measures where spot sits inside it.
Good market entry = trend intact, price retraced 25-65% of the last leg
(not at the extreme = no buying tops / selling bottoms), M1 turning back in
trend direction, and the leg's extreme + next level offering room.
"""
import json, os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fx_analyze import load, pip, ema, rsi

R = json.load(open(os.path.join(HERE, "results.json")))
rows = []
for p, r in R["pairs"].items():
    sc = r["score"]
    d = 1 if sc["1"]["total"] >= sc["-1"]["total"] else -1
    m1, meta = load(p, "1m"); m5, _ = load(p, "5m")
    pp = pip(p); px = float(m1.c.iloc[-1])
    w = m5.iloc[-24:]                       # last 2h of M5
    if d == 1:
        ext_i = w.h.values.argmax(); ext = w.h.iloc[ext_i]
        org = w.l.iloc[:ext_i + 1].min() if ext_i > 0 else w.l.iloc[0]
        retr = (ext - px) / (ext - org) if ext > org else 0
    else:
        ext_i = w.l.values.argmin(); ext = w.l.iloc[ext_i]
        org = w.h.iloc[:ext_i + 1].max() if ext_i > 0 else w.h.iloc[0]
        retr = (px - ext) / (org - ext) if org > ext else 0
    bars_since_ext = len(w) - 1 - ext_i
    # M1 turn: last 3 one-minute closes moving in trend direction & above/below EMA8-M1
    m1c = m1.c.iloc[-6:]
    m1_turn = float(np.sign(m1c.iloc[-1] - m1c.iloc[-4]) == d)
    m1_ema = ema(m1.c, 8).iloc[-1]; m1_side = float((px - m1_ema) * d > 0)
    rsi1 = rsi(m1.c).iloc[-1]
    leg = abs(ext - org) / pp
    to_ext = abs(ext - px) / pp
    room = (r["room_up"] if d == 1 else r["room_dn"]) * r["atr_h1"]
    rows.append(dict(pair=p, dir="BUY" if d == 1 else "SELL", score=round(sc[str(d)]["total"], 1),
                     px=px, leg=round(leg, 1), retr=round(retr, 2), to_ext=round(to_ext, 1),
                     bars=bars_since_ext, m1turn=m1_turn, m1side=m1_side, rsi1=round(rsi1),
                     room_pips=round(room, 1), atr_m5=round(r["atr_m5"], 1), atr_h1=round(r["atr_h1"], 1),
                     posD=round(r["posD"], 2), pos20=round(r["pos20"], 2),
                     nxt=r["nxt_res"] if d == 1 else r["nxt_sup"]))
df = pd.DataFrame(rows).set_index("pair").sort_values("score", ascending=False)
pd.set_option("display.width", 250)
print(df.to_string())

#!/usr/bin/env python3
"""Setup scorer: trend-continuation entries *after* a pullback (never at the extreme).

For every pair and both directions:
  trend    : EMA stacks + DI agreement on H4/H1/M15 (+ADX filter)
  strength : base-minus-quote currency strength (day + 4h + 1h)
  location : position in the day range — hard penalty if buying the top/selling the bottom
  pullback : last M15 impulse leg retraced 23-70% and price re-turning (M1/M5 momentum) in trend direction
  stretch  : |price-EMA20| in ATR on M5/M15 must be small (no chasing)
  room     : distance to nearest opposing H1 swing / day extreme in M15-ATRs
Usage: fx_setups.py DATA_DIR
"""
import json, os, sys, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.argv = sys.argv[:2]
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    import fx_analyze as A           # reuse indicators + per-pair results
R, S = A.R, A.S

def score(p, r, d):
    i = r["ind"]; pp = r["pp"]
    b, q = p[:3], p[3:]
    sb = S.loc[b] if b in S.index else None; sq = S.loc[q] if q in S.index else None
    if sb is not None and sq is not None:
        strength = d*((sb["day%"]-sq["day%"]) + 1.5*(sb["4h%"]-sq["4h%"]) + 2*(sb["1h%"]-sq["1h%"]))
    else:
        strength = d*(r["dchg"]*pp/r["px"]*100 + 1.5*r["c240"]*pp/r["px"]*100 + 2*r["c60"]*pp/r["px"]*100)
    trend = sum(d*i[tf]["st"] for tf in ["m15","h1","h4"]) \
          + sum(0.5*np.sign(d*(i[tf]["pdi"]-i[tf]["mdi"])) for tf in ["m15","h1"]) \
          + (0.5 if i["h1"]["adx"] > 20 else 0) + (0.5 if i["m15"]["adx"] > 20 else 0)
    pos = r["pos_day"] if d == 1 else 1 - r["pos_day"]          # 1 = at the extreme in trade direction
    loc = 0.0
    if pos > 0.92: loc -= 4          # buying the top / selling the bottom
    elif pos > 0.85: loc -= 2
    elif 0.45 <= pos <= 0.80: loc += 1.5
    elif pos < 0.30: loc -= 1        # counter to the day's move
    stretch = -max(0, abs(r["ext5"]) - 1.0)*1.5 - max(0, abs(r["ext15"]) - 1.2)*1.5
    if d*r["ext5"] < 0 and d*r["ext15"] > -1.0: stretch += 0.8   # price dipped under the M5 EMA20 in an uptrend = pullback entry zone
    # M15 last impulse and its retracement
    m15 = A.rs(A.load(p, "5m")[0], "15min").iloc[-40:]
    if d == 1:
        lo_i = m15.l.iloc[:-2].idxmin(); leg = m15.loc[lo_i:]; ext = leg.h.max()
        retr = (ext - r["px"])/(ext - m15.l.loc[lo_i]) if ext > m15.l.loc[lo_i] else 0
    else:
        hi_i = m15.h.iloc[:-2].idxmax(); leg = m15.loc[hi_i:]; ext = leg.l.min()
        retr = (r["px"] - ext)/(m15.h.loc[hi_i] - ext) if m15.h.loc[hi_i] > ext else 0
    pb = 0.0
    if 0.23 <= retr <= 0.70: pb += 1.5
    elif retr < 0.12: pb -= 1.0      # no pullback at all -> chasing
    elif retr > 0.85: pb -= 1.5      # leg failed
    resume = (0.6 if d*i["m1"]["st"] == 1 else 0) + (0.4 if d*r["c15"] > 0 else -0.4) + (0.4 if d*i["m5"]["mh"] > d*i["m5"]["mh1"] else 0)
    room = (r["room_up"] if d == 1 else r["room_dn"])
    room_atr = room*pp/i["m15"]["atr"] if room == room else 3
    rm = 1.0 if room_atr >= 2 else (0 if room_atr >= 1 else -1.5)
    rsi_pen = -1.5 if (d == 1 and i["m15"]["rsi"] > 72) or (d == -1 and i["m15"]["rsi"] < 28) else 0
    total = 1.2*trend + 6*strength + loc + stretch + pb + resume + rm + rsi_pen
    return dict(pair=p, dir="BUY" if d == 1 else "SELL", total=round(total,2), trend=trend, strength=round(strength,3),
                pos=round(pos,2), retr=round(retr,2), resume=round(resume,1), room_pips=round(room,1) if room==room else None,
                room_atr=round(room_atr,1), x5=round(r["ext5"],1), x15=round(r["ext15"],1),
                rsi15=round(i["m15"]["rsi"]), px=r["px"])

rows = [score(p, r, d) for p, r in R.items() for d in (1, -1)]
T = pd.DataFrame(rows).sort_values("total", ascending=False)
pd.set_option("display.width", 250)
print(buf.getvalue().split("=== PAIR SCAN")[0])
print(T.head(25).to_string(index=False))
print("\n... worst (for reference):"); print(T.tail(5).to_string(index=False))

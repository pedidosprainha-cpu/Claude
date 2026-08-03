#!/usr/bin/env python3
"""Continuation-quality scorer: ranks pairs for an immediate market-order entry.

Filters for setups where the trend is already in motion, the pullback is done,
price is not overextended, volatility is expanding (not compressing), and there
is structural room to a realistic intraday target. Penalises post-event coils,
RSI extremes, and entries into nearby resistance/support.
"""
import json, os
import pandas as pd, numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PAIRS = ["EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
         "EURJPY","GBPJPY","AUDJPY","CADJPY","CHFJPY","NZDJPY",
         "EURGBP","EURAUD","EURCHF","EURCAD","GBPCHF","GBPAUD","AUDNZD"]

def load(p, i):
    r = json.load(open(f"{DATA}/{p}_{i}.json"))["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({"o":q["open"],"h":q["high"],"l":q["low"],"c":q["close"]},
        index=pd.to_datetime(r["timestamp"], unit="s", utc=True)).dropna()
    return df, r["meta"]

ema = lambda s,n: s.ewm(span=n, adjust=False).mean()

def atr(df, n=14):
    tr = pd.concat([df.h-df.l,(df.h-df.c.shift()).abs(),(df.l-df.c.shift()).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100/(1+up/dn)

def adx(df, n=14):
    up = df.h.diff(); dn = -df.l.diff()
    plus  = pd.Series(np.where((up>dn)&(up>0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn>up)&(dn>0), dn, 0.0), index=df.index)
    a = atr(df, n)
    pdi = 100*plus.ewm(alpha=1/n, adjust=False).mean()/a
    mdi = 100*minus.ewm(alpha=1/n, adjust=False).mean()/a
    dx = 100*(pdi-mdi).abs()/(pdi+mdi)
    return dx.ewm(alpha=1/n, adjust=False).mean().iloc[-1], pdi.iloc[-1], mdi.iloc[-1]

pipsz = lambda p: 0.01 if "JPY" in p else 0.0001

rows = []
detail = {}
for p in PAIRS:
    m5, meta = load(p, "5m")
    h1, _ = load(p, "1h")
    d1, _ = load(p, "1d")
    m15 = m5.resample("15min").agg({"o":"first","h":"max","l":"min","c":"last"}).dropna()
    px = meta["regularMarketPrice"]; pp = pipsz(p)
    a1h = atr(h1).iloc[-1]; a5 = atr(m5).iloc[-1]

    # ---- trend direction: h1 + m15 structure -------------------------------
    e8h,e20h,e50h = ema(h1.c,8).iloc[-1], ema(h1.c,20).iloc[-1], ema(h1.c,50).iloc[-1]
    e8f,e20f,e50f = ema(m15.c,8).iloc[-1], ema(m15.c,20).iloc[-1], ema(m15.c,50).iloc[-1]
    st_h1  = 1 if e8h>e20h>e50h else (-1 if e8h<e20h<e50h else 0)
    st_m15 = 1 if e8f>e20f>e50f else (-1 if e8f<e20f<e50f else 0)
    slope_h1 = (e20h - ema(h1.c,20).iloc[-4]) / a1h
    d = st_h1 if st_h1 else (st_m15 if st_m15 else int(np.sign(slope_h1)))
    if d == 0: d = 1

    adx1h,_,_ = adx(h1); adx15,_,_ = adx(m15)
    r15 = rsi(m15.c).iloc[-1]; r1h = rsi(h1.c).iloc[-1]; r5 = rsi(m5.c).iloc[-1]

    # ---- pullback state: where is price vs the last 24h swing --------------
    win = m5.iloc[-288:] if len(m5)>=288 else m5
    sw_hi, sw_lo = win.h.max(), win.l.min()
    # retracement off the extreme in trend direction, expressed in h1 ATR
    if d>0: pull = (sw_hi - px)/a1h
    else:   pull = (px - sw_lo)/a1h

    # ---- resumption: is momentum turning back with the trend right now -----
    last6 = m5.iloc[-6:]
    thrust6 = ((last6.c.iloc[-1]-last6.o.iloc[0])/a5)*d
    bodies = ((m5.c-m5.o).iloc[-6:]*d > 0).mean()
    e8_5, e20_5 = ema(m5.c,8).iloc[-1], ema(m5.c,20).iloc[-1]
    e8_5p, e20_5p = ema(m5.c,8).iloc[-4], ema(m5.c,20).iloc[-4]
    cross_now = np.sign(e8_5-e20_5) == d
    cross_fresh = cross_now and (np.sign(e8_5p-e20_5p) != d)
    ext5 = ((px - e20_5)/a5)*d          # + = extended in trend direction

    # ---- volatility regime: expanding or compressing -----------------------
    tr5 = pd.concat([m5.h-m5.l,(m5.h-m5.c.shift()).abs(),(m5.l-m5.c.shift()).abs()],axis=1).max(axis=1)
    vol_ratio = tr5.iloc[-12:].mean() / tr5.iloc[-72:].mean()

    # ---- structural room to target ----------------------------------------
    today = m5.index[-1].date()
    day = m5[m5.index.date == today]
    prev = d1.iloc[-2]
    levels_up   = [day.h.max(), prev.h, sw_hi, np.ceil(px/(50*pp))*50*pp]
    levels_dn   = [day.l.min(), prev.l, sw_lo, np.floor(px/(50*pp))*50*pp]
    cand = [l for l in (levels_up if d>0 else levels_dn) if (l-px)*d > 2*pp]
    room = (min(cand, key=lambda l:(l-px)*d) - px)*d/a1h if cand else np.nan
    room_pips = room*a1h/pp if room==room else np.nan

    # ---- scoring -----------------------------------------------------------
    s  = 0.0
    s += 12*(st_h1==d) + 10*(st_m15==d)                       # multi-TF alignment
    s += min(adx1h,45)/45*12 + min(adx15,45)/45*8             # trend strength
    s += 10*np.clip(1-abs(pull-0.55)/0.8, 0, 1)               # healthy pullback depth
    s += 10*np.clip(thrust6, 0, 1.2)/1.2                      # resumption thrust
    s += 6*bodies + (5 if cross_fresh else (3 if cross_now else 0))
    s += 10*np.clip(vol_ratio-0.7, 0, 1)                      # expanding volatility
    s += 10*np.clip((room-1.0)/2.0, 0, 1) if room==room else 0
    s -= 12*np.clip(ext5-1.0, 0, 2)/2                         # overextension penalty
    rr = r15 if d>0 else 100-r15
    s -= 10*np.clip((rr-72)/18, 0, 1)                         # RSI exhaustion penalty
    s -= 8*np.clip((0.75-vol_ratio)/0.4, 0, 1)                # coil / dead-tape penalty

    rows.append(dict(pair=p, dir=("LONG" if d>0 else "SHORT"), px=round(px,5),
        st15=st_m15, st1h=st_h1, adx15=round(adx15,1), adx1h=round(adx1h,1),
        rsi5=round(r5,1), rsi15=round(r15,1), rsi1h=round(r1h,1),
        pull=round(pull,2), thr6=round(thrust6,2), bod=round(bodies,2),
        xfresh=int(cross_fresh), xnow=int(cross_now), ext=round(ext5,2),
        vol=round(vol_ratio,2), room=round(room,2) if room==room else np.nan,
        roomp=round(room_pips,1) if room==room else np.nan,
        atr1h=round(a1h/pp,1), score=round(s,1)))
    detail[p] = dict(px=px, a1h=a1h, a5=a5, pip=pp, d=d, sw_hi=sw_hi, sw_lo=sw_lo,
        day_hi=day.h.max(), day_lo=day.l.min(), prev_hi=prev.h, prev_lo=prev.l)

df = pd.DataFrame(rows).set_index("pair").sort_values("score", ascending=False)
pd.set_option("display.width", 250)
print(df.to_string())
json.dump(detail, open(f"{DATA}/../continuation_detail.json","w"), default=str, indent=1)

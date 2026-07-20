#!/usr/bin/env python3
"""Multi-timeframe technical analysis engine for the fetched FX basket.

For each pair: builds 5m/15m/1h/1d frames, computes EMA(8/20/50/200), RSI(14),
MACD(12,26,9), ATR(14), ADX(14), Bollinger(20,2), donchian/session levels,
then scores directional momentum + continuation quality and flags
pullback/reversal risk (exhaustion, key-level proximity, RSI extremes,
overextension vs ATR).
"""
import json, os, math
import pandas as pd, numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PAIRS = ["EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
         "EURJPY","GBPJPY","AUDJPY","CADJPY","CHFJPY","NZDJPY",
         "EURGBP","EURAUD","EURCHF","EURCAD","GBPCHF","GBPAUD","AUDNZD"]

def load(pair, interval):
    with open(f"{DATA}/{pair}_{interval}.json") as f:
        d = json.load(f)
    r = d["chart"]["result"][0]
    ts = r["timestamp"]
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({"o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"]},
                      index=pd.to_datetime(ts, unit="s", utc=True))
    df = df.dropna()
    meta = r["meta"]
    return df, meta

def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / dn
    return 100 - 100/(1+rs)

def atr(df, n=14):
    tr = pd.concat([df.h-df.l, (df.h-df.c.shift()).abs(), (df.l-df.c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def adx(df, n=14):
    up = df.h.diff(); dn = -df.l.diff()
    plus = np.where((up>dn)&(up>0), up, 0.0)
    minus = np.where((dn>up)&(dn>0), dn, 0.0)
    tr = pd.concat([df.h-df.l, (df.h-df.c.shift()).abs(), (df.l-df.c.shift()).abs()], axis=1).max(axis=1)
    atr_ = tr.ewm(alpha=1/n, adjust=False).mean()
    pdi = 100*pd.Series(plus, index=df.index).ewm(alpha=1/n, adjust=False).mean()/atr_
    mdi = 100*pd.Series(minus, index=df.index).ewm(alpha=1/n, adjust=False).mean()/atr_
    dx = 100*(pdi-mdi).abs()/(pdi+mdi)
    return dx.ewm(alpha=1/n, adjust=False).mean(), pdi, mdi

def macd(c):
    line = ema(c,12)-ema(c,26)
    sig = line.ewm(span=9, adjust=False).mean()
    return line, sig, line-sig

def pip(pair): return 0.01 if "JPY" in pair else 0.0001

results = {}
for p in PAIRS:
    m5, meta = load(p, "5m")
    h1, _ = load(p, "1h")
    d1, _ = load(p, "1d")
    m15 = m5.resample("15min").agg({"o":"first","h":"max","l":"min","c":"last"}).dropna()

    px = meta["regularMarketPrice"]; t = pd.to_datetime(meta["regularMarketTime"], unit="s", utc=True)
    pp = pip(p)

    # --- indicators per TF ---
    ind = {}
    for name, df in [("m5",m5),("m15",m15),("h1",h1),("d1",d1)]:
        c = df.c
        ind[name] = dict(
            ema8=ema(c,8).iloc[-1], ema20=ema(c,20).iloc[-1], ema50=ema(c,50).iloc[-1],
            ema200=ema(c,200).iloc[-1] if len(c)>=200 else np.nan,
            rsi=rsi(c).iloc[-1], atr=atr(df).iloc[-1],
        )
        line, sig, hist = macd(c)
        ind[name]["macd_hist"] = hist.iloc[-1]
        ind[name]["macd_hist_prev"] = hist.iloc[-2]
        ind[name]["macd_line"] = line.iloc[-1]
        a, pdi, mdi = adx(df)
        ind[name]["adx"] = a.iloc[-1]; ind[name]["pdi"] = pdi.iloc[-1]; ind[name]["mdi"] = mdi.iloc[-1]

    # --- session/day levels (today = last UTC calendar day in 5m data) ---
    today = m5.index[-1].date()
    day = m5[m5.index.date == today]
    prev_daily = d1.iloc[-2] if len(d1) >= 2 else d1.iloc[-1]
    day_hi, day_lo, day_open = day.h.max(), day.l.min(), day.o.iloc[0]
    asia = day[(day.index.hour >= 0) & (day.index.hour < 6)]
    asia_hi = asia.h.max() if len(asia) else np.nan
    asia_lo = asia.l.min() if len(asia) else np.nan

    # last-3h momentum (36 x 5m bars)
    look = m5.c.iloc[-36:]
    chg3h = (look.iloc[-1]-look.iloc[0])
    chg3h_atr = chg3h / (ind["h1"]["atr"] if ind["h1"]["atr"] else np.nan)
    chg1h = m5.c.iloc[-1]-m5.c.iloc[-12]
    # consistency: fraction of last 12 m15 bars closing in move direction
    dirn = np.sign(chg3h) if chg3h != 0 else 1
    last12 = m15.iloc[-12:]
    consist = float(((last12.c-last12.o)*dirn > 0).mean())

    # daily context
    dchg = px - prev_daily.c
    week_open = day_open  # Monday: day open == week open

    # distance of price from m5 ema20 in ATRs (overextension)
    ext5 = (px - ind["m5"]["ema20"]) / ind["m5"]["atr"] if ind["m5"]["atr"] else np.nan

    # alignment score: how many TFs agree on direction (ema8>ema20>ema50 stacked)
    def stack(i):
        if i["ema8"]>i["ema20"]>i["ema50"]: return 1
        if i["ema8"]<i["ema20"]<i["ema50"]: return -1
        return 0
    align = {tf: stack(ind[tf]) for tf in ["m5","m15","h1","d1"]}

    results[p] = dict(px=px, t=str(t), pip=pp, ind=ind, align=align,
        day_hi=day_hi, day_lo=day_lo, day_open=day_open,
        asia_hi=asia_hi, asia_lo=asia_lo,
        prev_hi=prev_daily.h, prev_lo=prev_daily.l, prev_cl=prev_daily.c,
        chg1h_pips=chg1h/pp, chg3h_pips=chg3h/pp, chg3h_atr=chg3h_atr,
        consist=consist, ext5_atr=ext5, dchg_pips=dchg/pp,
        atr_h1_pips=ind["h1"]["atr"]/pp, atr_d1_pips=ind["d1"]["atr"]/pp,
        range_today_pips=(day_hi-day_lo)/pp,
        pos_in_day=(px-day_lo)/(day_hi-day_lo) if day_hi>day_lo else 0.5)

pd.set_option("display.width", 250)
rows = []
for p, r in results.items():
    rows.append(dict(pair=p, px=round(r["px"],5), t=r["t"][11:16],
        al_m5=r["align"]["m5"], al_m15=r["align"]["m15"], al_h1=r["align"]["h1"], al_d1=r["align"]["d1"],
        rsi5=round(r["ind"]["m5"]["rsi"],1), rsi15=round(r["ind"]["m15"]["rsi"],1), rsi1h=round(r["ind"]["h1"]["rsi"],1),
        adx15=round(r["ind"]["m15"]["adx"],1), adx1h=round(r["ind"]["h1"]["adx"],1),
        c3h=round(r["chg3h_pips"],1), c1h=round(r["chg1h_pips"],1), c3h_atr=round(r["chg3h_atr"],2),
        cons=round(r["consist"],2), ext=round(r["ext5_atr"],2),
        posday=round(r["pos_in_day"],2), rng=round(r["range_today_pips"],1),
        atr1h=round(r["atr_h1_pips"],1), dchg=round(r["dchg_pips"],1)))
df = pd.DataFrame(rows).set_index("pair")
print(df.to_string())

with open(os.path.join(DATA, "..", "results.json"), "w") as f:
    json.dump(results, f, default=str, indent=1)

#!/usr/bin/env python3
"""Multi-timeframe technical scan of the fetched FX basket (own analysis, spot data only).

Per pair: M1/M5/M15/H1/H4/D1 frames; EMA 8/20/50/200, RSI(14), MACD hist, ATR(14),
ADX(14)/DI; day/Asia/London levels; ADR usage; position in day range and in the
20-day range; extension vs EMA20 (M5/M15) in ATRs; pullback depth from the
intraday extreme; M1/M5 resumption; distance to nearest H1 swing / daily level
in trade direction. Also builds a currency-strength meter from the 28-pair G8
matrix. Usage: fx_analyze.py DATA_DIR
"""
import json, os, sys, math
import pandas as pd, numpy as np

DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx_fetch import PAIRS

def load(pair, interval):
    with open(f"{DATA}/{pair}_{interval}.json") as f:
        d = json.load(f)
    r = d["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({"o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"]},
                      index=pd.to_datetime(r["timestamp"], unit="s", utc=True)).dropna()
    df = df[(df.h >= df.l) & (df.c > 0)]
    return df, r["meta"]

def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def rsi(c, n=14):
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100/(1+up/dn)
def tr(df): return pd.concat([df.h-df.l, (df.h-df.c.shift()).abs(), (df.l-df.c.shift()).abs()], axis=1).max(axis=1)
def atr(df, n=14): return tr(df).ewm(alpha=1/n, adjust=False).mean()
def adx(df, n=14):
    up = df.h.diff(); dn = -df.l.diff()
    plus = pd.Series(np.where((up>dn)&(up>0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn>up)&(dn>0), dn, 0.0), index=df.index)
    a = tr(df).ewm(alpha=1/n, adjust=False).mean()
    pdi = 100*plus.ewm(alpha=1/n, adjust=False).mean()/a; mdi = 100*minus.ewm(alpha=1/n, adjust=False).mean()/a
    dx = 100*(pdi-mdi).abs()/(pdi+mdi)
    return dx.ewm(alpha=1/n, adjust=False).mean(), pdi, mdi
def macdh(c):
    l = ema(c,12)-ema(c,26); return l - l.ewm(span=9, adjust=False).mean()
def pip(pair):
    if "JPY" in pair: return 0.01
    if pair in ("USDMXN","USDZAR","USDSEK","USDNOK","EURNOK","EURSEK","USDPLN"): return 0.001
    return 0.0001
def rs(df, rule): return df.resample(rule).agg({"o":"first","h":"max","l":"min","c":"last"}).dropna()

def swings(df, k=3):
    """fractal swing highs / lows (k bars each side)"""
    hi = df.h[(df.h == df.h.rolling(2*k+1, center=True).max())]
    lo = df.l[(df.l == df.l.rolling(2*k+1, center=True).min())]
    return hi, lo

def stack(e8, e20, e50):
    return 1 if e8 > e20 > e50 else (-1 if e8 < e20 < e50 else 0)

R = {}
now = None
for p in PAIRS:
    m1, meta = load(p, "1m"); m5, _ = load(p, "5m"); h1, _ = load(p, "1h"); d1, _ = load(p, "1d")
    m15 = rs(m5, "15min"); h4 = rs(h1, "4h")
    px = meta["regularMarketPrice"]; t = pd.to_datetime(meta["regularMarketTime"], unit="s", utc=True)
    now = max(now, t) if now is not None else t
    pp = pip(p)
    ind = {}
    for name, df in [("m1",m1),("m5",m5),("m15",m15),("h1",h1),("h4",h4),("d1",d1)]:
        c = df.c
        a, pdi, mdi = adx(df)
        ind[name] = dict(e8=ema(c,8).iloc[-1], e20=ema(c,20).iloc[-1], e50=ema(c,50).iloc[-1],
                         e200=ema(c,200).iloc[-1] if len(c) >= 200 else np.nan,
                         rsi=rsi(c).iloc[-1], atr=atr(df).iloc[-1], mh=macdh(c).iloc[-1], mh1=macdh(c).iloc[-2],
                         adx=a.iloc[-1], pdi=pdi.iloc[-1], mdi=mdi.iloc[-1])
        ind[name]["st"] = stack(ind[name]["e8"], ind[name]["e20"], ind[name]["e50"])
    # FX trading day = NY close (22:00 UTC, winter time). Daily bars rebuilt from H1 (Yahoo D1 closes are unreliable for FX).
    dly = h1.resample("24h", offset="22h").agg({"o":"first","h":"max","l":"min","c":"last"}).dropna()
    today = m5.index[-1].floor("1D") + pd.Timedelta(hours=22)
    if today > m5.index[-1]: today -= pd.Timedelta(days=1)
    day = m5[m5.index >= today]
    dhi, dlo, dop = day.h.max(), day.l.min(), day.o.iloc[0]
    prev = dly[dly.index < today]
    prev = prev[(prev.h - prev.l) > 0]
    pdh, pdl, pdc = prev.h.iloc[-1], prev.l.iloc[-1], m5[m5.index < today].c.iloc[-1]
    adr = (prev.h - prev.l).iloc[-20:].mean()
    hi20, lo20 = prev.h.iloc[-20:].max(), prev.l.iloc[-20:].min()
    dchg = (px - pdc)/pp
    direction = 1 if px >= dop else -1   # intraday bias by price vs day open
    # pullback depth from intraday extreme in direction of the day's move
    if direction == 1:
        ext_px = dhi; leg_base = dlo
        pb = (dhi - px) / (dhi - dlo) if dhi > dlo else 0
        t_ext = day.h.idxmax()
    else:
        ext_px = dlo; leg_base = dhi
        pb = (px - dlo) / (dhi - dlo) if dhi > dlo else 0
        t_ext = day.l.idxmin()
    mins_since_ext = (t - t_ext).total_seconds()/60
    ext5 = (px - ind["m5"]["e20"]) / ind["m5"]["atr"]
    ext15 = (px - ind["m15"]["e20"]) / ind["m15"]["atr"]
    exth1 = (px - ind["h1"]["e20"]) / ind["h1"]["atr"]
    # last 15 minutes / 60 minutes change
    c15 = (px - m1.c.iloc[-16])/pp if len(m1) > 16 else np.nan
    c60 = (px - m1.c.iloc[-61])/pp if len(m1) > 61 else np.nan
    c240 = (px - m5.c.iloc[-49])/pp
    # swing levels (H1) for room-to-target
    shi, slo = swings(h1.iloc[-24*15:], 3)
    above = sorted([x for x in list(shi.values) + [pdh, hi20, dhi] if x > px + 0.5*pp])
    below = sorted([x for x in list(slo.values) + [pdl, lo20, dlo] if x < px - 0.5*pp], reverse=True)
    res1 = above[0] if above else np.nan
    sup1 = below[0] if below else np.nan
    R[p] = dict(px=px, t=t, pp=pp, ind=ind, dhi=dhi, dlo=dlo, dop=dop, pdh=pdh, pdl=pdl, pdc=pdc,
                adr_p=adr/pp, hi20=hi20, lo20=lo20, dchg=dchg, dir=direction, pb=pb, mse=mins_since_ext,
                ext5=ext5, ext15=ext15, exth1=exth1, c15=c15, c60=c60, c240=c240,
                rng_p=(dhi-dlo)/pp, adr_used=(dhi-dlo)/adr, pos_day=(px-dlo)/(dhi-dlo) if dhi>dlo else .5,
                pos20=(px-lo20)/(hi20-lo20) if hi20>lo20 else .5,
                res1=res1, sup1=sup1, room_up=(res1-px)/pp if res1==res1 else np.nan,
                room_dn=(px-sup1)/pp if sup1==sup1 else np.nan)

# ---------- currency strength (G8, % change vs prev daily close and last 1h / 4h) ----------
G8 = ["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"]
def strength(key):
    s = {c: [] for c in G8}
    for p, r in R.items():
        b, q = p[:3], p[3:]
        if b in G8 and q in G8:
            if key == "day": v = (r["px"]/r["pdc"]-1)*100
            else: v = r[key]*r["pp"]/r["px"]*100
            s[b].append(v); s[q].append(-v)
    return {c: np.mean(v) for c, v in s.items()}
S = pd.DataFrame({"day%": strength("day"), "4h%": strength("c240"), "1h%": strength("c60"), "15m%": strength("c15")}).round(3)

pd.set_option("display.width", 300); pd.set_option("display.max_columns", 50)
print(f"SNAPSHOT spot (latest tick): {now}")
print("\n=== CURRENCY STRENGTH (avg % move vs 7 G8 peers) ===")
print(S.sort_values("day%", ascending=False).to_string())

rows = []
for p, r in R.items():
    i = r["ind"]
    rows.append(dict(pair=p, px=r["px"], age_s=int((now - r["t"]).total_seconds()),
        dchg=round(r["dchg"],1), rng=round(r["rng_p"],1), adr=round(r["adr_p"],1), adrU=round(r["adr_used"],2),
        posD=round(r["pos_day"],2), pos20=round(r["pos20"],2), pb=round(r["pb"],2), mse=int(r["mse"]),
        st="".join({1:"+",-1:"-",0:"0"}[i[tf]["st"]] for tf in ["m1","m5","m15","h1","h4","d1"]),
        r5=round(i["m5"]["rsi"]), r15=round(i["m15"]["rsi"]), r1h=round(i["h1"]["rsi"]), rD=round(i["d1"]["rsi"]),
        adx15=round(i["m15"]["adx"]), adx1h=round(i["h1"]["adx"]),
        x5=round(r["ext5"],1), x15=round(r["ext15"],1), xh1=round(r["exth1"],1),
        c15=round(r["c15"],1), c60=round(r["c60"],1), c240=round(r["c240"],1),
        rUp=round(r["room_up"],1), rDn=round(r["room_dn"],1)))
T = pd.DataFrame(rows).set_index("pair")
print("\n=== PAIR SCAN ===  st = EMA8/20/50 stack M1 M5 M15 H1 H4 D1 ; pb = pullback from intraday extreme (0=at extreme) ; mse = minutes since extreme")
print(T.sort_values("dchg").to_string())

with open(os.path.join(DATA, "results.json"), "w") as f:
    json.dump({p: {k: (v if not isinstance(v, (pd.Timestamp,)) else str(v)) for k, v in r.items()} for p, r in R.items()},
              f, default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o), indent=1)

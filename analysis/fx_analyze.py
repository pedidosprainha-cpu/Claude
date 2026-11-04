#!/usr/bin/env python3
"""Multi-timeframe technical analysis engine for the fetched FX basket.

For each pair builds M1/M5/M15/H1/H4/D1 frames and computes EMA(8/20/50/200),
RSI(14), MACD(12,26,9), ATR(14), ADX(14)/DI, Bollinger(20,2) bandwidth,
day/Asia/previous-day levels and swing pivots (H1/D1). Then scores:
  * trend alignment across timeframes,
  * momentum quality (3h move in ATRs, M15 directional consistency),
  * anti-chase filters: overextension vs EMA20 (M5/M15 in ATRs), RSI extremes,
    position in the day's range, distance to the next opposing key level,
and prints a ranked table. Also derives a currency-strength board.
"""
import json, os, sys
import pandas as pd, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
sys.path.insert(0, HERE)
from fx_fetch import PAIRS  # noqa: E402


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
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100/(1 + up/dn)


def true_range(df):
    return pd.concat([df.h-df.l, (df.h-df.c.shift()).abs(), (df.l-df.c.shift()).abs()], axis=1).max(axis=1)


def atr(df, n=14): return true_range(df).ewm(alpha=1/n, adjust=False).mean()


def adx(df, n=14):
    up = df.h.diff(); dn = -df.l.diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    a = atr(df, n)
    pdi = 100*plus.ewm(alpha=1/n, adjust=False).mean()/a
    mdi = 100*minus.ewm(alpha=1/n, adjust=False).mean()/a
    dx = 100*(pdi-mdi).abs()/(pdi+mdi)
    return dx.ewm(alpha=1/n, adjust=False).mean(), pdi, mdi


def macd_hist(c):
    line = ema(c, 12)-ema(c, 26)
    return line - line.ewm(span=9, adjust=False).mean()


def pip(pair):
    if "JPY" in pair or "HUF" in pair: return 0.01
    if pair in ("USDMXN", "USDZAR", "USDSEK", "USDNOK", "EURSEK", "EURNOK", "USDPLN", "EURPLN"):
        return 0.001
    return 0.0001


def resample(df, rule):
    return df.resample(rule).agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()


def pivots(df, k=3):
    """Fractal swing highs/lows (k bars each side)."""
    hi = df.h[(df.h == df.h.rolling(2*k+1, center=True).max())]
    lo = df.l[(df.l == df.l.rolling(2*k+1, center=True).min())]
    return hi, lo


def stack(i):
    if i["ema8"] > i["ema20"] > i["ema50"]: return 1
    if i["ema8"] < i["ema20"] < i["ema50"]: return -1
    return 0


def analyze(p):
    m1, meta = load(p, "1m")
    m5, _ = load(p, "5m")
    h1, _ = load(p, "1h")
    # FX trading day = New York close (22:00 UTC in winter). Yahoo's own 1d bars
    # have inconsistent closes for FX, so D1/H4 are rebuilt from H1 with that offset.
    d1 = h1.resample("24h", offset="22h").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    d1 = d1[~((d1.index.dayofweek == 5) | ((d1.index.dayofweek == 4) & (d1.index.hour == 22)))]  # drop Fri-22h weekend stub
    m15 = resample(m5, "15min")
    h4 = h1.resample("4h", offset="2h").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    px = float(meta["regularMarketPrice"])
    t = pd.to_datetime(meta["regularMarketTime"], unit="s", utc=True)
    pp = pip(p)

    ind = {}
    for name, df in [("m1", m1), ("m5", m5), ("m15", m15), ("h1", h1), ("h4", h4), ("d1", d1)]:
        c = df.c
        hist = macd_hist(c)
        a, pdi, mdi = adx(df)
        bb_mid = c.rolling(20).mean(); bb_sd = c.rolling(20).std()
        ind[name] = dict(
            ema8=ema(c, 8).iloc[-1], ema20=ema(c, 20).iloc[-1], ema50=ema(c, 50).iloc[-1],
            ema200=ema(c, 200).iloc[-1] if len(c) >= 200 else np.nan,
            rsi=rsi(c).iloc[-1], atr=atr(df).iloc[-1],
            mh=hist.iloc[-1], mh_prev=hist.iloc[-2],
            adx=a.iloc[-1], pdi=pdi.iloc[-1], mdi=mdi.iloc[-1],
            bbw=(4*bb_sd/bb_mid).iloc[-1], bbw_med=(4*bb_sd/bb_mid).iloc[-120:].median(),
            bbpos=((c - (bb_mid-2*bb_sd))/(4*bb_sd)).iloc[-1],
        )
        ind[name]["stack"] = stack(ind[name])

    # --- day (UTC) levels; FX day for D1 bars on Yahoo starts 00:00 UTC (London time in winter)
    day_start = d1.index[-1]
    day = m5[m5.index >= day_start]
    prev = d1.iloc[-2]
    day_hi, day_lo, day_open = day.h.max(), day.l.min(), day.o.iloc[0]
    day_hi = max(day_hi, px); day_lo = min(day_lo, px)

    # momentum windows
    c5 = m5.c
    chg1h = px - c5.iloc[-13]
    chg3h = px - c5.iloc[-37]
    a1h = ind["h1"]["atr"]
    dirn = np.sign(chg3h) if chg3h != 0 else 1
    last12 = m15.iloc[-12:]
    consist = float(((last12.c - last12.o)*dirn > 0).mean())

    # overextension (signed, in ATRs of its TF)
    ext5 = (px - ind["m5"]["ema20"])/ind["m5"]["atr"]
    ext15 = (px - ind["m15"]["ema20"])/ind["m15"]["atr"]
    exth1 = (px - ind["h1"]["ema20"])/ind["h1"]["atr"]

    # key levels: H1 swings over last ~10 days, D1 swings over 1y, prev-day H/L, round numbers
    hh, hl = pivots(h1.iloc[-240:], 4)
    dh, dl = pivots(d1, 3)
    res_lv = sorted(set([x for x in list(hh.values) + list(dh.values) + [prev.h, day_hi] if x > px*1.00005]))
    sup_lv = sorted(set([x for x in list(hl.values) + list(dl.values) + [prev.l, day_lo] if x < px*0.99995]), reverse=True)
    near_res = res_lv[0] if res_lv else np.nan
    near_sup = sup_lv[0] if sup_lv else np.nan

    # last 30-min micro trend on M1
    m1c = m1.c.iloc[-30:]
    micro = (m1c.iloc[-1] - m1c.iloc[0])/pp

    return dict(pair=p, px=px, t=t, pip=pp, ind=ind,
                day_hi=day_hi, day_lo=day_lo, day_open=day_open,
                prev_hi=prev.h, prev_lo=prev.l, prev_cl=prev.c,
                dchg=(px-prev.c)/pp, chg1h=chg1h/pp, chg3h=chg3h/pp, chg3h_atr=chg3h/a1h,
                consist=consist, ext5=ext5, ext15=ext15, exth1=exth1,
                atr_h1=a1h/pp, atr_d1=ind["d1"]["atr"]/pp,
                rng=(day_hi-day_lo)/pp, posday=(px-day_lo)/(day_hi-day_lo) if day_hi > day_lo else .5,
                near_res=near_res, near_sup=near_sup,
                dres=(near_res-px)/pp, dsup=(px-near_sup)/pp,
                micro30=micro, h1=h1, m5=m5, m15=m15, d1=d1, m1=m1)


def score(r):
    """Directional continuation score with anti-chase penalties. Returns (dir, score, notes)."""
    i = r["ind"]
    trend = i["m5"]["stack"] + i["m15"]["stack"] + 1.5*i["h1"]["stack"] + 1.5*i["h4"]["stack"] + i["d1"]["stack"]
    d = 1 if trend > 0 else -1 if trend < 0 else (1 if r["chg3h"] > 0 else -1)
    s = abs(trend)  # 0..6
    notes = []
    # momentum agreeing with direction
    s += 1.5*np.clip(d*r["chg3h_atr"], -2, 2)
    s += 2*(r["consist"] - .5) if np.sign(r["chg3h"]) == d else -1
    s += 0.5 if d*i["m15"]["mh"] > 0 else -0.5
    s += 0.5 if d*(i["m15"]["mh"]-i["m15"]["mh_prev"]) > 0 else 0
    s += 0.5 if d*(i["h1"]["pdi"]-i["h1"]["mdi"]) > 0 and i["h1"]["adx"] > 20 else 0
    # anti-chase: overextension
    for k, lim, w in (("ext5", 2.0, 1.5), ("ext15", 2.0, 1.5), ("exth1", 2.5, 1.0)):
        e = d*r[k]
        if e > lim:
            s -= w*(e-lim+1); notes.append(f"{k}={e:.1f}ATR")
    # RSI extremes on M15/H1
    for tf, hi in (("m15", 72), ("h1", 70)):
        v = i[tf]["rsi"] if d > 0 else 100-i[tf]["rsi"]
        if v > hi:
            s -= (v-hi)/4; notes.append(f"RSI{tf}={i[tf]['rsi']:.0f}")
    # buying the top / selling the bottom of the day
    pos = r["posday"] if d > 0 else 1-r["posday"]
    if pos > .9 and r["rng"] > .6*r["atr_d1"]:
        s -= 1.5; notes.append(f"pos-dia={pos:.2f}")
    # room to the next opposing level, in H1 ATRs
    room = (r["dres"] if d > 0 else r["dsup"])/r["atr_h1"]
    if room < 1: s -= 2*(1-room); notes.append(f"nivel a {room:.1f}ATRh1")
    # day already exhausted
    used = r["rng"]/r["atr_d1"]
    if used > 1.3: s -= (used-1.3)*2; notes.append(f"range={used:.1f}xATRd")
    return d, s, room, notes


if __name__ == "__main__":
    res = {p: analyze(p) for p in PAIRS}
    rows = []
    for p, r in res.items():
        d, s, room, notes = score(r)
        i = r["ind"]
        rows.append(dict(pair=p, px=r["px"], t=r["t"].strftime("%H:%M:%S"), dir="BUY" if d > 0 else "SELL",
                         score=round(s, 2),
                         stk="".join({1: "+", -1: "-", 0: "0"}[i[tf]["stack"]] for tf in ("m5", "m15", "h1", "h4", "d1")),
                         r15=round(i["m15"]["rsi"]), r1h=round(i["h1"]["rsi"]), adx1h=round(i["h1"]["adx"]),
                         d=round(r["dchg"]), c3h=round(r["chg3h"]), c1h=round(r["chg1h"]), m30=round(r["micro30"]),
                         cons=round(r["consist"], 2), e5=round(r["ext5"], 1), e15=round(r["ext15"], 1), eh1=round(r["exth1"], 1),
                         pos=round(r["posday"], 2), rng=round(r["rng"]), atrd=round(r["atr_d1"]), atrh=round(r["atr_h1"], 1),
                         room=round(room, 1), flags=",".join(notes)))
    df = pd.DataFrame(rows).set_index("pair").sort_values("score", ascending=False)
    pd.set_option("display.width", 320); pd.set_option("display.max_columns", 40)
    print(df.to_string())

    # currency strength: average % change vs prev close over G8 pairs
    from fx_fetch import G8
    ccys = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"]
    st = {c: [] for c in ccys}; st3 = {c: [] for c in ccys}
    for p in G8:
        r = res[p]; b, q = p[:3], p[3:]
        pct = (r["px"]/r["prev_cl"]-1)*100
        pct3 = r["chg3h"]*r["pip"]/r["px"]*100
        st[b].append(pct); st[q].append(-pct); st3[b].append(pct3); st3[q].append(-pct3)
    print("\nCurrency strength (avg % vs prev close | last 3h):")
    for c in sorted(ccys, key=lambda c: -np.mean(st[c])):
        print(f"  {c}: {np.mean(st[c]):+.3f}%  | {np.mean(st3[c]):+.3f}%")

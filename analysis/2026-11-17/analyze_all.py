#!/usr/bin/env python3
"""Systematic multi-timeframe scan of every Forex + Metals symbol on the
RoboForex MT5 ECN terminal (28 FX + XAUUSD, XAGUSD, XAUEUR).

Layers (each scored independently, then combined):
  1. Trend regime  D1 / H4 / H1  - EMA20/50/200 stack, EMA50 slope (ATR-normalised),
                                   price vs EMA50, ADX + DI direction, MACD histogram.
  2. Market structure H4 / H1    - fractal swing pivots, HH/HL vs LH/LL sequence.
  3. Currency strength           - 8-currency meter from the 28-pair matrix, ATR-normalised
                                   returns over 1, 5 and 20 days.
  4. Momentum quality            - RSI zones, MACD acceleration, M15 directional consistency.
  5. Location / risk-reward      - clustered S/R from D1+H4 pivots, prior day/week H/L and
                                   round numbers; technical stop behind last H1/H4 swing,
                                   room to next opposing level -> R:R.
  6. Exhaustion filters          - over-extension vs EMA20 (ATR units), RSI extremes,
                                   Bollinger %B, distance already travelled vs ATR(D1).

usage: analyze_all.py <data_dir> <out_json>
"""
import json, os, sys
import numpy as np, pandas as pd

DATA, OUT = sys.argv[1], sys.argv[2]
FX = ["AUDCAD","AUDCHF","AUDJPY","AUDNZD","AUDUSD","CADCHF","CADJPY","CHFJPY",
      "EURAUD","EURCAD","EURCHF","EURGBP","EURJPY","EURNZD","EURUSD","GBPAUD",
      "GBPCAD","GBPCHF","GBPJPY","GBPNZD","GBPUSD","NZDCAD","NZDCHF","NZDJPY",
      "NZDUSD","USDCAD","USDCHF","USDJPY"]
METALS = ["XAUUSD", "XAGUSD", "XAUEUR"]
CCYS = ["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"]

# ---------------------------------------------------------------- loading
def load(sym, iv):
    with open(f"{DATA}/{sym}_{iv}.json") as f:
        r = json.load(f)["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({"o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"]},
                      index=pd.to_datetime(r["timestamp"], unit="s", utc=True)).dropna()
    df = df[(df.h >= df.l) & (df.c > 0)]
    return df, r["meta"]

def resample(df, rule):
    return df.resample(rule, origin="epoch").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()

def frames(sym):
    if sym == "XAUEUR":
        a, b = frames("XAUUSD"), frames("EURUSD")
        out = {}
        for k in a:
            # feeds stamp bars differently (COMEX vs CCY) -> align each gold bar to the latest EURUSD bar
            j = pd.merge_asof(a[k].add_suffix("_x"), b[k].add_suffix("_e"), left_index=True, right_index=True,
                              direction="backward").dropna()
            out[k] = pd.DataFrame({"o": j.o_x / j.o_e, "h": j.h_x / j.l_e, "l": j.l_x / j.h_e,
                                   "c": j.c_x / j.c_e}, index=j.index)
            out[k]["h"] = out[k][["o", "h", "c"]].max(axis=1)
            out[k]["l"] = out[k][["o", "l", "c"]].min(axis=1)
        return out
    m5, _ = load(sym, "5m"); m15, _ = load(sym, "15m"); h1, _ = load(sym, "1h"); yd, _ = load(sym, "1d")
    # Broker (MT5 server GMT+2) candles roll at 22:00 UTC (NY close, post-DST).
    # Yahoo's FX daily 'close' is unreliable (≈ the day's open), so D1 is rebuilt from H1;
    # older history (needed for EMA200) is spliced from Yahoo daily with close := next open.
    d1h = h1.resample("24h", offset="22h").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    old = yd[yd.index < d1h.index[0] - pd.Timedelta(days=1)].copy()
    old["c"] = old["o"].shift(-1); old = old.dropna()
    d1 = pd.concat([old, d1h])
    h4 = h1.resample("4h", offset="2h").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    return {"m5": m5, "m15": m15, "h1": h1, "h4": h4, "d1": d1}

# ---------------------------------------------------------------- indicators
ema = lambda s, n: s.ewm(span=n, adjust=False).mean()

def rsi(c, n=14):
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)

def tr(df):
    return pd.concat([df.h - df.l, (df.h - df.c.shift()).abs(), (df.l - df.c.shift()).abs()], axis=1).max(axis=1)

def atr(df, n=14): return tr(df).ewm(alpha=1/n, adjust=False).mean()

def adx(df, n=14):
    up, dn = df.h.diff(), -df.l.diff()
    p = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    m = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    a = atr(df, n)
    pdi = 100 * p.ewm(alpha=1/n, adjust=False).mean() / a
    mdi = 100 * m.ewm(alpha=1/n, adjust=False).mean() / a
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi)
    return dx.ewm(alpha=1/n, adjust=False).mean(), pdi, mdi

def macd_hist(c):
    line = ema(c, 12) - ema(c, 26); return line - line.ewm(span=9, adjust=False).mean()

def pivots(df, n):
    """Confirmed fractal swing highs / lows (n bars each side)."""
    h, l = df.h.values, df.l.values
    hi, lo = [], []
    for i in range(n, len(df) - n):
        if h[i] == max(h[i-n:i+n+1]): hi.append((df.index[i], h[i]))
        if l[i] == min(l[i-n:i+n+1]): lo.append((df.index[i], l[i]))
    return hi, lo

def tf_state(df):
    c = df.c; a = atr(df); e20, e50, e200 = ema(c, 20), ema(c, 50), ema(c, 200)
    ad, pdi, mdi = adx(df); mh = macd_hist(c); r = rsi(c)
    mid = c.rolling(20).mean(); sd = c.rolling(20).std()
    px = c.iloc[-1]
    slope50 = (e50.iloc[-1] - e50.iloc[-11]) / a.iloc[-1]          # EMA50 move over 10 bars, in ATRs
    stack = 1 if e20.iloc[-1] > e50.iloc[-1] > e200.iloc[-1] else -1 if e20.iloc[-1] < e50.iloc[-1] < e200.iloc[-1] else 0
    s = dict(px=px, atr=a.iloc[-1], e20=e20.iloc[-1], e50=e50.iloc[-1], e200=e200.iloc[-1],
             adx=ad.iloc[-1], pdi=pdi.iloc[-1], mdi=mdi.iloc[-1], rsi=r.iloc[-1],
             mh=mh.iloc[-1], mh_prev=mh.iloc[-2], stack=stack, slope50=slope50,
             ext20=(px - e20.iloc[-1]) / a.iloc[-1],
             pctb=((px - (mid - 2*sd)) / (4*sd)).iloc[-1],
             atr_pctile=float((a.iloc[-120:] <= a.iloc[-1]).mean()))
    # directional trend score in [-1, 1]
    comp = [stack,
            np.sign(px - s["e50"]),
            np.clip(slope50 / 1.5, -1, 1),
            np.sign(s["pdi"] - s["mdi"]) * min(s["adx"] / 25, 1),
            np.sign(s["mh"])]
    s["trend"] = float(np.mean(comp))
    return s

def structure(df, n):
    hi, lo = pivots(df, n)
    if len(hi) < 2 or len(lo) < 2: return 0, hi, lo
    hh = hi[-1][1] > hi[-2][1]; hl = lo[-1][1] > lo[-2][1]
    st = 1 if (hh and hl) else -1 if (not hh and not hl) else 0
    return st, hi, lo

def strength_meter(closes, atrd):
    """ATR-normalised returns over 1/5/20 D1 bars -> per-currency average."""
    res = {}
    for h in (1, 5, 20):
        sc = {c: [] for c in CCYS}
        for p in FX:
            c = closes[p]; r = (c.iloc[-1] - c.iloc[-1-h]) / atrd[p]
            sc[p[:3]].append(r); sc[p[3:]].append(-r)
        res[h] = {c: float(np.mean(v)) for c, v in sc.items()}
    comb = {c: 0.5*res[1][c] + 0.3*res[5][c] / np.sqrt(5) + 0.2*res[20][c] / np.sqrt(20) for c in CCYS}
    return res, comb

def cluster_levels(levels, tol):
    levels = sorted(levels); out = []
    for v in levels:   # cluster width capped at `tol` from the cluster's first member (no chaining)
        if out and abs(v - out[-1][0]) <= tol: out[-1].append(v)
        else: out.append([v])
    return [(float(np.mean(g)), len(g)) for g in out]

def round_levels(px, step):
    base = np.floor(px / step) * step
    return [base + k*step for k in range(-4, 6)]

# ---------------------------------------------------------------- run
ALL = FX + METALS
F = {s: frames(s) for s in ALL}
closes = {p: F[p]["d1"].c for p in FX}
atrd = {p: atr(F[p]["d1"]).iloc[-1] for p in FX}
sm_raw, sm = strength_meter(closes, atrd)

results = {}
for s in ALL:
    f = F[s]
    st = {tf: tf_state(f[tf]) for tf in ("d1", "h4", "h1", "m15")}
    s_h4, hi4, lo4 = structure(f["h4"], 2)
    s_h1, hi1, lo1 = structure(f["h1"], 3)
    _, hid, lod = structure(f["d1"].iloc[-260:], 3)
    px = f["m5"].c.iloc[-1]
    ad1, ah4, ah1 = st["d1"]["atr"], st["h4"]["atr"], st["h1"]["atr"]

    # currency strength differential (metals: invert quote ccy strength only)
    if s in FX: csd = sm[s[:3]] - sm[s[3:]]
    else: csd = -sm[s[3:]] * 0.5

    # M15 consistency of last 12 bars in direction of H1 trend
    m15 = f["m15"].iloc[-12:]
    dir_h1 = np.sign(st["h1"]["trend"]) or 1
    cons = float((((m15.c - m15.o) * dir_h1) > 0).mean())

    trend_score = 0.40*st["d1"]["trend"] + 0.35*st["h4"]["trend"] + 0.25*st["h1"]["trend"]
    struct_score = 0.6*s_h4 + 0.4*s_h1
    direction = 1 if (trend_score + 0.3*struct_score + 0.4*np.tanh(csd)) > 0 else -1

    # ---- levels
    d1 = f["d1"]; prev = d1.iloc[-2]
    wk = d1.iloc[-8:-1]; lastwk = d1[d1.index < d1.index[-1] - pd.Timedelta(days=d1.index[-1].weekday())].iloc[-5:]
    lv = [v for _, v in hid[-40:]] + [v for _, v in lod[-40:]] + [v for _, v in hi4[-30:]] + [v for _, v in lo4[-30:]]
    lv += [prev.h, prev.l, lastwk.h.max(), lastwk.l.min()]
    step = 0.5 if "JPY" in s else 50 if s.startswith("XAU") else 0.5 if s == "XAGUSD" else 0.005
    lv += round_levels(px, step)
    cl = cluster_levels(lv, 0.15*ad1)

    # ---- technical stop: beyond most recent swing on H1 (fallback H4) against direction
    buf = 0.20*ah1
    if direction == 1:
        sw = [v for _, v in lo1[-6:] if v < px - 0.3*ah1] or [v for _, v in lo4[-6:] if v < px]
        sl = (sw[-1] if sw else px - 1.5*ah4) - buf
        opp = sorted([(v, n) for v, n in cl if v > px + 0.25*ah1])
    else:
        sw = [v for _, v in hi1[-6:] if v > px + 0.3*ah1] or [v for _, v in hi4[-6:] if v > px]
        sl = (sw[-1] if sw else px + 1.5*ah4) + buf
        opp = sorted([(v, n) for v, n in cl if v < px - 0.25*ah1], reverse=True)
    risk = abs(px - sl)
    # first opposing level with >=2 touches is the realistic target; otherwise the first level
    strong = [o for o in opp if o[1] >= 2]
    tgt = (strong[0][0] if strong else opp[0][0]) if opp else px + direction*2*ad1
    first_obstacle = opp[0][0] if opp else tgt
    room = abs(tgt - px); rr = room / risk if risk else 0
    obst_atr = abs(first_obstacle - px) / ad1

    # ---- exhaustion / quality penalties
    pen = 0.0
    r_d1, r_h4, r_h1 = st["d1"]["rsi"], st["h4"]["rsi"], st["h1"]["rsi"]
    if direction == 1:
        pen += max(0, r_d1 - 70)/10 + max(0, r_h4 - 72)/10 + max(0, r_h1 - 75)/10
    else:
        pen += max(0, 30 - r_d1)/10 + max(0, 28 - r_h4)/10 + max(0, 25 - r_h1)/10
    ext = direction * st["h4"]["ext20"]
    pen += max(0, ext - 2.0) * 0.5
    today_move = direction * (px - prev.c) / ad1
    pen += max(0, today_move - 0.8) * 0.6                       # most of the day's range already spent
    pen += 0.4 if risk / ad1 > 0.9 else 0                       # stop too wide relative to daily range
    pen += 0.3 if st["h4"]["adx"] < 15 and st["d1"]["adx"] < 15 else 0
    mom_ok = (np.sign(st["h1"]["mh"]) == direction) + (np.sign(st["m15"]["mh"]) == direction) \
             + (direction*(st["h1"]["mh"] - st["h1"]["mh_prev"]) > 0)

    score = (direction*trend_score) * 3.0 + (direction*struct_score) * 1.0 \
            + np.tanh(direction*csd) * 1.5 + (mom_ok/3) * 1.0 + (cons - 0.5) * 1.0 \
            + min(rr, 3) / 3 * 1.5 + min(obst_atr, 1.5) / 1.5 * 0.5 - pen

    results[s] = dict(
        symbol=s, px=px, dir="LONG" if direction == 1 else "SHORT", score=round(float(score), 3),
        trend_d1=round(st["d1"]["trend"], 2), trend_h4=round(st["h4"]["trend"], 2), trend_h1=round(st["h1"]["trend"], 2),
        struct_h4=s_h4, struct_h1=s_h1, csd=round(float(csd), 2),
        rsi_d1=round(r_d1, 1), rsi_h4=round(r_h4, 1), rsi_h1=round(r_h1, 1),
        adx_d1=round(st["d1"]["adx"], 1), adx_h4=round(st["h4"]["adx"], 1),
        ext_h4=round(st["h4"]["ext20"], 2), today_atr=round(float((px - prev.c)/ad1), 2),
        cons_m15=round(cons, 2), mom_ok=int(mom_ok),
        atr_d1=ad1, atr_h4=ah4, atr_h1=ah1,
        sl=sl, tgt=tgt, first_obstacle=first_obstacle, risk_atr_d1=round(risk/ad1, 2),
        rr=round(rr, 2), obst_atr=round(obst_atr, 2), penalty=round(pen, 2),
        prev_h=prev.h, prev_l=prev.l, prev_c=prev.c,
        levels_above=sorted([(round(v, 5), n) for v, n in cl if v > px])[:6],
        levels_below=sorted([(round(v, 5), n) for v, n in cl if v < px], reverse=True)[:6],
        swings_h1_hi=[round(v, 5) for _, v in hi1[-5:]], swings_h1_lo=[round(v, 5) for _, v in lo1[-5:]],
        swings_h4_hi=[round(v, 5) for _, v in hi4[-5:]], swings_h4_lo=[round(v, 5) for _, v in lo4[-5:]],
        e20_h4=st["h4"]["e20"], e50_h4=st["h4"]["e50"], e200_d1=st["d1"]["e200"], e50_d1=st["d1"]["e50"],
        last_bar=str(f["m5"].index[-1]))

json.dump(dict(strength=sm, strength_raw=sm_raw, results=results), open(OUT, "w"), default=float, indent=1)

pd.set_option("display.width", 260); pd.set_option("display.max_columns", 40)
print("Currency strength (combined):", {k: round(v, 2) for k, v in sorted(sm.items(), key=lambda x: -x[1])})
for h in (1, 5, 20):
    print(f"  {h:>2}D:", {k: round(v, 2) for k, v in sorted(sm_raw[h].items(), key=lambda x: -x[1])})
cols = ["dir","score","trend_d1","trend_h4","trend_h1","struct_h4","struct_h1","csd","rsi_d1","rsi_h4","rsi_h1",
        "adx_d1","adx_h4","ext_h4","today_atr","cons_m15","mom_ok","risk_atr_d1","rr","obst_atr","penalty"]
df = pd.DataFrame(results).T[cols].sort_values("score", ascending=False)
print(df.to_string())

#!/usr/bin/env python3
"""Multi-timeframe technical engine for XAU/USD (COMEX GC=F, mapped to spot via live basis).

Computes EMA 8/20/50/100/200, RSI(14), MACD(12,26,9), ATR(14), ADX(14)/DI+-,
Bollinger(20,2), Stoch RSI, swing pivots, session ranges, Fibonacci retracements
of the last impulse, plus intermarket correlations (DXY, US10Y, silver, EURUSD).
"""
import json, os
import numpy as np, pandas as pd

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_xau")

def load(k, iv):
    r = json.load(open(f"{D}/{k}_{iv}.json"))["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({"o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"], "v": q.get("volume")},
                      index=pd.to_datetime(r["timestamp"], unit="s", utc=True)).dropna(subset=["c"])
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
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    a = tr(df).ewm(alpha=1/n, adjust=False).mean()
    pdi = 100*plus.ewm(alpha=1/n, adjust=False).mean()/a; mdi = 100*minus.ewm(alpha=1/n, adjust=False).mean()/a
    dx = 100*(pdi-mdi).abs()/(pdi+mdi)
    return dx.ewm(alpha=1/n, adjust=False).mean(), pdi, mdi
def macd(c):
    l = ema(c, 12)-ema(c, 26); s = l.ewm(span=9, adjust=False).mean(); return l, s, l-s
def stochrsi(c, n=14):
    r = rsi(c, n); lo = r.rolling(n).min(); hi = r.rolling(n).max()
    k = 100*(r-lo)/(hi-lo); return k.rolling(3).mean(), k.rolling(3).mean().rolling(3).mean()

def pivots(df, w=3):
    hi = df.h[(df.h == df.h.rolling(2*w+1, center=True).max())]
    lo = df.l[(df.l == df.l.rolling(2*w+1, center=True).min())]
    return hi, lo

gc5, meta = load("GC", "5m"); gc15, _ = load("GC", "15m"); gc1h, _ = load("GC", "1h")
gc1d, _ = load("GC", "1d"); gc1w, _ = load("GC", "1wk")
gc4h = gc1h.resample("4h", offset="2h").agg({"o": "first", "h": "max", "l": "min", "c": "last", "v": "sum"}).dropna()

fut = meta["regularMarketPrice"]; t = pd.to_datetime(meta["regularMarketTime"], unit="s", utc=True)
sq = json.load(open(f"{D}/spot_swissquote.json"))
p0 = sq[0]["spreadProfilePrices"][0]; spot_bid, spot_ask = p0["bid"], p0["ask"]
spot = (spot_bid+spot_ask)/2; sq_t = pd.to_datetime(sq[0]["ts"], unit="ms", utc=True)
basis = fut - spot
print(f"=== SNAPSHOT  fut GC(Dec26)={fut:.1f} @ {t}  | spot XAU/USD bid/ask {spot_bid:.2f}/{spot_ask:.2f} @ {sq_t}  | basis {basis:+.2f}")

def s(x):  # futures -> spot
    return x - basis

print("\n=== INDICADORES POR TIMEFRAME (níveis convertidos p/ spot)")
rows = []
for name, df in [("M5", gc5), ("M15", gc15), ("H1", gc1h), ("H4", gc4h), ("D1", gc1d), ("W1", gc1w)]:
    c = df.c; a, pdi, mdi = adx(df); l, sg, h = macd(c); k, dd = stochrsi(c)
    bb_m = c.rolling(20).mean(); bb_s = c.rolling(20).std()
    e = {n: ema(c, n).iloc[-1] for n in (8, 20, 50, 100, 200)}
    stack = "BULL" if e[8] > e[20] > e[50] else ("BEAR" if e[8] < e[20] < e[50] else "MIX")
    rows.append(dict(tf=name, close=s(c.iloc[-1]), ema8=s(e[8]), ema20=s(e[20]), ema50=s(e[50]),
                     ema100=s(e[100]) if len(c) >= 100 else np.nan, ema200=s(e[200]) if len(c) >= 200 else np.nan,
                     stack=stack, rsi=rsi(c).iloc[-1], stochK=k.iloc[-1], stochD=dd.iloc[-1],
                     macd_h=h.iloc[-1], macd_h_prev=h.iloc[-2], adx=a.iloc[-1], pdi=pdi.iloc[-1], mdi=mdi.iloc[-1],
                     atr=atr(df).iloc[-1], bb_up=s(bb_m.iloc[-1]+2*bb_s.iloc[-1]), bb_lo=s(bb_m.iloc[-1]-2*bb_s.iloc[-1]),
                     ext_ema20_atr=(c.iloc[-1]-e[20])/atr(df).iloc[-1]))
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print(pd.DataFrame(rows).set_index("tf").round(2).to_string())

print("\n=== ESTRUTURA DIÁRIA (spot)")
d = gc1d.copy(); d[["o", "h", "l", "c"]] = d[["o", "h", "l", "c"]] - basis
d["rng"] = d.h-d.l; d["chg"] = d.c.diff()
print(d.tail(12)[["o", "h", "l", "c", "chg", "rng"]].round(1).to_string())
ph, pl = pivots(gc1d, 3)
print("Topos de swing D1 (spot):", [(i.date().isoformat(), round(s(v), 1)) for i, v in ph.tail(8).items()])
print("Fundos de swing D1 (spot):", [(i.date().isoformat(), round(s(v), 1)) for i, v in pl.tail(8).items()])

# Last impulse: swing high 2026-11-09/10 (~4157) -> low 2026-11-12 (3856.7)
recent = gc1d.loc["2026-11-01":]
hi_i = recent.h.idxmax(); lo_i = gc1d.loc[hi_i:].l.idxmin()
H, L = s(gc1d.h[hi_i]), s(gc1d.l[lo_i])
print(f"\n=== FIBO do último impulso baixista {hi_i.date()} {H:.1f} -> {lo_i.date()} {L:.1f}")
for f in (0.236, 0.382, 0.5, 0.618, 0.786): print(f"  {f:.3f}: {L+(H-L)*f:.1f}")

print("\n=== INTRADAY (spot) — sessões")
m5 = gc5.copy(); m5[["o", "h", "l", "c"]] = m5[["o", "h", "l", "c"]] - basis
yday = m5.loc["2026-11-12"]; today = m5.loc["2026-11-13"]
for nm, sl in [("Ásia 12/11 (00-07)", yday.between_time("00:00", "06:59")), ("Londres 12/11 (07-12)", yday.between_time("07:00", "11:59")),
               ("NY 12/11 (12-21)", yday.between_time("12:00", "20:59")), ("Pós-NY 12/11 (21-24)", yday.between_time("21:00", "23:59")),
               ("Ásia 13/11 (até agora)", today)]:
    if len(sl): print(f"  {nm:24s} O {sl.o.iloc[0]:.1f} H {sl.h.max():.1f} L {sl.l.min():.1f} C {sl.c.iloc[-1]:.1f}  rng {sl.h.max()-sl.l.min():.1f}")
print("\nÚltimos 24 candles M5 (spot):")
print(m5.tail(24)[["o", "h", "l", "c", "v"]].round(1).to_string())
h1 = gc1h.copy(); h1[["o", "h", "l", "c"]] = h1[["o", "h", "l", "c"]] - basis
print("\nÚltimos 30 candles H1 (spot):")
print(h1.tail(30)[["o", "h", "l", "c", "v"]].round(1).to_string())

print("\n=== INTERMERCADO")
for k in ("DXY", "TNX", "SI", "EURUSD"):
    x, mm = load(k, "1h"); xd, _ = load(k, "1d")
    j = pd.concat([gc1h.c.pct_change(), x.c.pct_change()], axis=1, join="inner").dropna().tail(120)
    corr = j.corr().iloc[0, 1]
    print(f"  {k:6s} last {mm['regularMarketPrice']:.4f}  1d chg {(xd.c.iloc[-1]/xd.c.iloc[-2]-1)*100:+.2f}%  5d chg {(xd.c.iloc[-1]/xd.c.iloc[-6]-1)*100:+.2f}%"
          f"  20d chg {(xd.c.iloc[-1]/xd.c.iloc[-21]-1)*100:+.2f}%  corr H1(120) c/ ouro {corr:+.2f}  RSI-D1 {rsi(xd.c).iloc[-1]:.1f}")
si, _ = load("SI", "1d"); print(f"  Gold/Silver ratio: {gc1d.c.iloc[-1]/si.c.iloc[-1]:.1f} (20d atrás {gc1d.c.iloc[-21]/si.c.iloc[-21]:.1f})")

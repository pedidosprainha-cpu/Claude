#!/usr/bin/env python3
"""Multi-timeframe technical engine for the 38-pair live spot basket.

Per pair: M1/M5/M15/H1/H4/D1 frames -> EMA(8/21/50/200), RSI(14), MACD(12,26,9),
ATR(14), ADX(14)/DI, stacked-EMA alignment; FX trading day from the 22:00 UTC
NY close; fractal swing levels (H1, D1), prior day/week extremes and round
numbers as S/R; 28-cross currency-strength meter; room-to-level, overextension
and pullback->resumption timing. Output: ranked continuation candidates with
explicit rejection reasons (top-buying / bottom-selling filter).
"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
sys.path.insert(0, HERE)
from fx_fetch import PAIRS  # noqa: E402

MAJ = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"]

def load(p, i):
    r = json.load(open(f"{DATA}/{p}_{i}.json"))["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({"o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"]},
                      index=pd.to_datetime(r["timestamp"], unit="s", utc=True)).dropna()
    df = df[(df.h >= df.l) & (df.c > 0)]
    return df, r["meta"]

def rs(df, rule, offset=None):
    return df.resample(rule, offset=offset).agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()

ema = lambda s, n: s.ewm(span=n, adjust=False).mean()

def rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100/(1 + up/dn)

def tr(df):
    return pd.concat([df.h-df.l, (df.h-df.c.shift()).abs(), (df.l-df.c.shift()).abs()], axis=1).max(axis=1)

atr = lambda df, n=14: tr(df).ewm(alpha=1/n, adjust=False).mean()

def adx(df, n=14):
    up, dn = df.h.diff(), -df.l.diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    a = atr(df, n)
    pdi = 100*plus.ewm(alpha=1/n, adjust=False).mean()/a
    mdi = 100*minus.ewm(alpha=1/n, adjust=False).mean()/a
    dx = 100*(pdi-mdi).abs()/(pdi+mdi)
    return dx.ewm(alpha=1/n, adjust=False).mean(), pdi, mdi

def macd_hist(c):
    line = ema(c, 12) - ema(c, 26)
    return line - line.ewm(span=9, adjust=False).mean()

def fractals(df, k):
    hi, lo = [], []
    H, L = df.h.values, df.l.values
    for i in range(k, len(df)-k):
        if H[i] == H[i-k:i+k+1].max(): hi.append((df.index[i], H[i]))
        if L[i] == L[i-k:i+k+1].min(): lo.append((df.index[i], L[i]))
    return hi, lo

pip = lambda p: 0.01 if p.endswith("JPY") else 0.0001

def tf_ind(df):
    c = df.c
    a, pdi, mdi = adx(df)
    h = macd_hist(c)
    e8, e21, e50 = ema(c, 8), ema(c, 21), ema(c, 50)
    e200 = ema(c, 200) if len(c) >= 200 else pd.Series(np.nan, index=c.index)
    st = 1 if e8.iloc[-1] > e21.iloc[-1] > e50.iloc[-1] else (-1 if e8.iloc[-1] < e21.iloc[-1] < e50.iloc[-1] else 0)
    return dict(e8=e8.iloc[-1], e21=e21.iloc[-1], e50=e50.iloc[-1], e200=e200.iloc[-1],
                rsi=rsi(c).iloc[-1], atr=atr(df).iloc[-1], adx=a.iloc[-1], pdi=pdi.iloc[-1], mdi=mdi.iloc[-1],
                mh=h.iloc[-1], mh1=h.iloc[-2], mh2=h.iloc[-3], stack=st,
                e21_slope=(e21.iloc[-1]-e21.iloc[-4])/atr(df).iloc[-1])

def pullback(m5, td, px):
    """Retracement vs today's impulse + M5 micro-structure (both directions)."""
    out = {}
    hi_t, lo_t = td.h.idxmax(), td.l.idxmin()
    H, L = td.h.max(), td.l.min()
    rng = H - L if H > L else np.nan
    # long view: impulse low = lowest low before the day high
    lo_b = td.loc[:hi_t].l.min(); out["ret_long"] = (H - px)/(H - lo_b) if H > lo_b else np.nan
    hi_b = td.loc[:lo_t].h.max(); out["ret_short"] = (px - L)/(hi_b - L) if hi_b > L else np.nan
    out["bars_since_hi"] = int((m5.index[-1] - hi_t)/pd.Timedelta(minutes=5))
    out["bars_since_lo"] = int((m5.index[-1] - lo_t)/pd.Timedelta(minutes=5))
    last = m5.iloc[-6:]
    out["m5_last3"] = [round(float(x), 6) for x in (last.c - last.o).iloc[-3:]]
    # higher-low / lower-high on last 18 M5 bars
    w = m5.iloc[-18:]
    out["hl"] = bool(w.l.iloc[-6:].min() > w.l.iloc[:12].min())
    out["lh"] = bool(w.h.iloc[-6:].max() < w.h.iloc[:12].max())
    return out

live = json.load(open(f"{DATA}/live_snapshot.json"))
R, frames = {}, {}
for p in PAIRS:
    m1, meta = load(p, "1m"); m5, _ = load(p, "5m"); h1, _ = load(p, "1h"); d1y, _ = load(p, "1d")
    m15 = rs(m5, "15min"); h4 = rs(h1, "4h", offset="2h")           # H4 aligned to 22:00 UTC close
    d1 = d1y if len(d1y) > 200 else rs(h1, "24h", offset="22h")
    frames[p] = dict(m1=m1, m5=m5, m15=m15, h1=h1, h4=h4, d1=d1)
    lv = live.get(p, {})
    bid, ask = lv.get("bid"), lv.get("ask")
    px = (bid+ask)/2 if bid and ask else meta["regularMarketPrice"]
    pp = pip(p)
    ind = {k: tf_ind(v) for k, v in [("m5", m5), ("m15", m15), ("h1", h1), ("h4", h4), ("d1", d1)]}

    # FX trading day: from 22:00 UTC (NY 17:00, post-DST) of previous day
    now = m5.index[-1]
    day_start = (now - pd.Timedelta(hours=22)).normalize() + pd.Timedelta(hours=22)
    if day_start > now: day_start -= pd.Timedelta(days=1)
    td = m5[m5.index >= day_start]
    prev = m5[(m5.index >= day_start - pd.Timedelta(days=1)) & (m5.index < day_start)]
    if len(prev) < 50:   # skip weekend gap
        prev = m5[(m5.index >= day_start - pd.Timedelta(days=3)) & (m5.index < day_start - pd.Timedelta(days=2))]
    dh, dl, dop = max(td.h.max(), px), min(td.l.min(), px), td.o.iloc[0]
    # ADR(20) from H1-built NY-close days
    dny = rs(h1, "24h", offset="22h")
    dny = dny[dny.index.dayofweek < 5]
    adr = (dny.h-dny.l).iloc[-21:-1].mean()

    # weekly
    wk_start = day_start - pd.Timedelta(days=int((day_start + pd.Timedelta(hours=2)).dayofweek))
    wk = h1[h1.index >= wk_start]
    pw = h1[(h1.index >= wk_start - pd.Timedelta(days=7)) & (h1.index < wk_start)]

    # S/R levels
    hfh, hfl = fractals(h1.iloc[-24*15:], 8)
    dfh, dfl = fractals(d1.iloc[-160:], 3)
    levels = [x[1] for x in hfh + hfl + dfh + dfl] + [prev.h.max(), prev.l.min(), pw.h.max(), pw.l.min()]
    rnd = 100*pp if not p.endswith("JPY") else 0.5
    if p in ("USDMXN", "USDZAR", "USDNOK", "USDSEK", "EURNOK", "EURSEK"): rnd = 0.05
    base_r = np.floor(px/rnd)*rnd
    rounds = [base_r + k*rnd for k in range(-3, 5)]
    a15, a1 = ind["m15"]["atr"], ind["h1"]["atr"]
    buf = 0.15*a15
    res_above = sorted([l for l in levels + rounds if l > px + buf])
    sup_below = sorted([l for l in levels + rounds if l < px - buf], reverse=True)
    # strongest structural levels only (not rounds) for room calc
    res_struct = sorted([l for l in levels if l > px + buf])
    sup_struct = sorted([l for l in levels if l < px - buf], reverse=True)

    def chg(df, bars): return (df.c.iloc[-1]/df.c.iloc[-1-bars]-1)*100 if len(df) > bars else np.nan
    R[p] = dict(px=px, bid=bid, ask=ask, spread_pips=(ask-bid)/pp if bid and ask else np.nan, pip=pp,
        t=str(m1.index[-1]), ind=ind, day_hi=dh, day_lo=dl, day_open=dop, adr=adr, adr_pips=adr/pp,
        used_adr=(dh-dl)/adr, pos_day=(px-dl)/(dh-dl) if dh > dl else .5,
        dchg_pips=(px-dop)/pp, dchg_adr=(px-dop)/adr,
        prev_hi=prev.h.max(), prev_lo=prev.l.min(), wk_hi=max(wk.h.max(), px), wk_lo=min(wk.l.min(), px),
        pw_hi=pw.h.max(), pw_lo=pw.l.min(), wk_open=wk.o.iloc[0] if len(wk) else np.nan,
        res=res_above[:4], sup=sup_below[:4], res_s=res_struct[:3], sup_s=sup_struct[:3],
        ch_1h=chg(m5, 12), ch_4h=chg(m5, 48), ch_day=(px/dop-1)*100, ch_24h=chg(m5, 288),
        ext15=(px-ind["m15"]["e21"])/a15, ext1h=(px-ind["h1"]["e21"])/a1, ext5=(px-ind["m5"]["e21"])/ind["m5"]["atr"],
        a5=ind["m5"]["atr"], a15=a15, a1=a1, pb=pullback(m5, td, px))

# ---- currency strength (28 crosses of the 8 majors) ----
cs = {w: {c: [] for c in MAJ} for w in ["ch_1h", "ch_4h", "ch_day", "ch_24h"]}
for p, r in R.items():
    b, q = p[:3], p[3:]
    if b in MAJ and q in MAJ:
        for w in cs:
            cs[w][b].append(r[w]); cs[w][q].append(-r[w])
CS = pd.DataFrame({w: {c: np.nanmean(v) for c, v in d.items()} for w, d in cs.items()}).round(3)
CS["score"] = (CS.ch_1h*1.0 + CS.ch_4h*1.0 + CS.ch_day*1.0 + CS.ch_24h*0.5).round(3)
CS = CS.sort_values("score", ascending=False)

# ---- scoring ----
rows = []
for p, r in R.items():
    I = r["ind"]
    tsc = I["m15"]["stack"]*1 + I["h1"]["stack"]*2 + I["h4"]["stack"]*2 + I["d1"]["stack"]*1
    mom = np.sign(r["ch_4h"]) + np.sign(r["ch_day"]) + np.sign(r["ch_1h"])
    d = 1 if (tsc + mom) > 0 else -1
    b, q = p[:3], p[3:]
    csd = (CS.score.get(b, 0) - CS.score.get(q, 0))*d if (b in MAJ and q in MAJ) else np.nan
    # timing on M5: momentum resuming in trend direction
    m5i = I["m5"]
    mh_turn = (m5i["mh"]*d > 0) and ((m5i["mh"]-m5i["mh1"])*d > 0)
    m5_ok = ((r["px"]-m5i["e8"])*d > 0)
    room_px = (r["res_s"][0]-r["px"]) if d > 0 and r["res_s"] else ((r["px"]-r["sup_s"][0]) if d < 0 and r["sup_s"] else np.nan)
    room_any = (r["res"][0]-r["px"]) if d > 0 and r["res"] else ((r["px"]-r["sup"][0]) if d < 0 and r["sup"] else np.nan)
    pos_dir = r["pos_day"] if d > 0 else 1-r["pos_day"]
    flags = []
    if r["ext15"]*d > 1.6: flags.append("esticado M15")
    if r["ext1h"]*d > 2.2: flags.append("esticado H1")
    if (I["m15"]["rsi"]-50)*d > 22: flags.append("RSI15 extremo")
    if (I["h1"]["rsi"]-50)*d > 22: flags.append("RSI1h extremo")
    if pos_dir > 0.88 and r["used_adr"] > 0.9: flags.append("topo/fundo do dia c/ ADR gasto")
    if room_px / r["a1"] < 1.0: flags.append("S/R estrutural < 1 ATR-H1")
    if r["spread_pips"]*r["pip"] > 0.20*r["a15"]: flags.append("spread alto")
    if abs(tsc) < 3: flags.append("tendência fraca/mista")
    pb = r["pb"]
    ret = pb["ret_long"] if d > 0 else pb["ret_short"]
    struct_ok = pb["hl"] if d > 0 else pb["lh"]
    if ret < 0.12 and pos_dir > 0.85: flags.append("sem pullback (perseguição)")
    if ret > 0.75: flags.append("pullback profundo/possível reversão")
    pb_bonus = (1.0 if 0.25 <= ret <= 0.62 else (0.4 if 0.12 <= ret <= 0.75 else 0)) + (0.5 if struct_ok else 0)
    score = pb_bonus + (abs(tsc)/6*3 + min(max(csd, -1.5), 1.5) if not np.isnan(csd) else abs(tsc)/6*3) \
        + (1 if mh_turn else 0) + (0.5 if m5_ok else 0) + min(room_px/r["a1"], 3)/3*1.5 \
        + (1 if I["h1"]["adx"] > 22 else 0) - 1.2*len(flags)
    rows.append(dict(pair=p, dir="BUY" if d > 0 else "SELL", px=r["px"], spr=round(r["spread_pips"], 1),
        tsc=tsc, st=f'{I["m5"]["stack"]:+d}{I["m15"]["stack"]:+d}{I["h1"]["stack"]:+d}{I["h4"]["stack"]:+d}{I["d1"]["stack"]:+d}',
        csd=round(csd, 2) if not np.isnan(csd) else None, adx1h=round(I["h1"]["adx"], 0), adx15=round(I["m15"]["adx"], 0),
        rsi5=round(I["m5"]["rsi"]), rsi15=round(I["m15"]["rsi"]), rsi1h=round(I["h1"]["rsi"]),
        ext15=round(r["ext15"], 2), ext1h=round(r["ext1h"], 2), posd=round(r["pos_day"], 2), adr_u=round(r["used_adr"], 2),
        d_adr=round(r["dchg_adr"], 2), room=round(room_px/r["a1"], 2), m5t=int(mh_turn), ret=round(ret, 2), hl=int(struct_ok), score=round(score, 2), flags="; ".join(flags)))
T = pd.DataFrame(rows).set_index("pair").sort_values("score", ascending=False)

if __name__ == "__main__":
    pd.set_option("display.width", 260); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 70)
    print("snapshot:", live["fetched_utc"], "UTC | last candle:", R["EURUSD"]["t"])
    print("\n== CURRENCY STRENGTH (% avg vs 7 peers) ==\n", CS.to_string())
    print("\n== RANKING ==\n", T.to_string())
    json.dump({p: {k: v for k, v in r.items()} for p, r in R.items()}, open(f"{HERE}/results.json", "w"), default=str, indent=1)
    T.to_csv(f"{HERE}/ranking.csv")

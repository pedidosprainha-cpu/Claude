#!/usr/bin/env python3
"""Multi-timeframe technical scan of the fetched FX basket (spot data).

Per pair: 1m / 5m / 15m (resampled) / 1h / 4h (resampled) / 1d frames with
EMA(8/20/50/200), RSI(14), MACD(12,26,9) histogram, ATR(14), ADX(14)/DI+-,
plus session levels, currency-strength meter and anti-chase filters:
  * ext5  = distance from EMA20-M5 in M5-ATRs (overextension)
  * posD  = position inside today's range (0=low, 1=high)
  * pos20 = position inside 20-day range
  * room  = distance to next daily swing level in trade direction (in H1 ATRs)
Output: results.json + console table sorted by continuation score.
"""
import json, os, sys
import numpy as np
import pandas as pd

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
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def tr(df):
    return pd.concat([df.h - df.l, (df.h - df.c.shift()).abs(), (df.l - df.c.shift()).abs()],
                     axis=1).max(axis=1)


def atr(df, n=14): return tr(df).ewm(alpha=1 / n, adjust=False).mean()


def adx(df, n=14):
    up, dn = df.h.diff(), -df.l.diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    a = atr(df, n)
    pdi = 100 * plus.ewm(alpha=1 / n, adjust=False).mean() / a
    mdi = 100 * minus.ewm(alpha=1 / n, adjust=False).mean() / a
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi)
    return dx.ewm(alpha=1 / n, adjust=False).mean(), pdi, mdi


def macd_hist(c):
    line = ema(c, 12) - ema(c, 26)
    return line - line.ewm(span=9, adjust=False).mean()


def pip(pair):
    if pair.endswith("JPY") or pair.endswith("HUF"):
        return 0.01
    return 0.0001


def resample(df, rule):
    return df.resample(rule, label="left", closed="left").agg(
        {"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()


def swings(df, k=3):
    """Fractal swing highs / lows (k bars each side)."""
    h, l = df.h.values, df.l.values
    sh, sl = [], []
    for i in range(k, len(df) - k):
        if h[i] == max(h[i - k:i + k + 1]):
            sh.append(h[i])
        if l[i] == min(l[i - k:i + k + 1]):
            sl.append(l[i])
    return sh, sl


def stack(i):
    if i["ema8"] > i["ema20"] > i["ema50"]:
        return 1
    if i["ema8"] < i["ema20"] < i["ema50"]:
        return -1
    return 0


def analyze(p):
    m1, meta = load(p, "1m")
    m5, _ = load(p, "5m")
    meta["regularMarketPrice"] = float(m1.c.iloc[-1]) if m1.index[-1] >= pd.to_datetime(meta["regularMarketTime"], unit="s", utc=True) else meta["regularMarketPrice"]
    h1, _ = load(p, "1h")
    d1, _ = load(p, "1d")
    # Yahoo CCY daily bars carry close ~= open (broken close field): rebuild the
    # close of each completed day from the next day's open, and use the live
    # spot price as the close of today's (forming) bar.
    d1 = d1.copy()
    d1["c"] = d1.o.shift(-1)
    d1.iloc[-1, d1.columns.get_loc("c")] = float(meta["regularMarketPrice"])
    d1["h"] = d1[["h", "c"]].max(axis=1)
    d1["l"] = d1[["l", "c"]].min(axis=1)
    m15 = resample(m5, "15min")
    h4 = resample(h1, "4h")
    px = float(meta["regularMarketPrice"])
    t = pd.to_datetime(meta["regularMarketTime"], unit="s", utc=True)
    pp = pip(p)

    ind = {}
    for name, df in [("m1", m1), ("m5", m5), ("m15", m15), ("h1", h1), ("h4", h4), ("d1", d1)]:
        c = df.c
        a, pdi, mdi = adx(df)
        hist = macd_hist(c)
        ind[name] = dict(
            ema8=ema(c, 8).iloc[-1], ema20=ema(c, 20).iloc[-1], ema50=ema(c, 50).iloc[-1],
            ema200=ema(c, 200).iloc[-1] if len(c) >= 200 else np.nan,
            rsi=rsi(c).iloc[-1], atr=atr(df).iloc[-1], adx=a.iloc[-1],
            pdi=pdi.iloc[-1], mdi=mdi.iloc[-1],
            hist=hist.iloc[-1], hist_prev=hist.iloc[-2], hist_prev2=hist.iloc[-3])
    align = {tf: stack(ind[tf]) for tf in ind}

    # --- today's session (UTC day of last bar) ---
    today = m5.index[-1].normalize()
    day = m5[m5.index >= today]
    if len(day) == 0:
        day = m5.iloc[-12:]
    day_hi, day_lo, day_open = day.h.max(), day.l.min(), day.o.iloc[0]
    # previous completed daily candle (Yahoo daily bars are UTC-midnight based for CCY)
    dprev = d1[d1.index < today]
    prev = dprev.iloc[-1]
    d20 = dprev.iloc[-20:]
    hi20, lo20 = d20.h.max(), d20.l.min()

    # momentum windows
    def chg(df, n):
        return (df.c.iloc[-1] - df.c.iloc[-1 - n]) if len(df) > n else np.nan
    c15m, c1h, c3h = chg(m5, 3), chg(m5, 12), chg(m5, 36)
    c24h = chg(h1, 24)
    dirn = np.sign(c3h) if c3h else 1
    last12 = m15.iloc[-12:]
    consist = float(((last12.c - last12.o) * dirn > 0).mean())

    atr_m5, atr_h1, atr_d1 = ind["m5"]["atr"], ind["h1"]["atr"], ind["d1"]["atr"]
    ext5 = (px - ind["m5"]["ema20"]) / atr_m5
    ext15 = (px - ind["m15"]["ema20"]) / ind["m15"]["atr"]
    ext1h = (px - ind["h1"]["ema20"]) / atr_h1

    # daily swing levels (last 120 sessions) for room-to-target
    sh, sl = swings(d1.iloc[-120:], k=3)
    sh_h1, sl_h1 = swings(h1.iloc[-240:], k=4)
    res_levels = sorted(set([x for x in sh + sh_h1 + [prev.h, hi20] if x > px]))
    sup_levels = sorted(set([x for x in sl + sl_h1 + [prev.l, lo20] if x < px]), reverse=True)
    nxt_res = res_levels[0] if res_levels else np.nan
    nxt_sup = sup_levels[0] if sup_levels else np.nan

    return dict(
        pair=p, px=px, t=str(t), pip=pp, ind=ind, align=align,
        day_open=day_open, day_hi=day_hi, day_lo=day_lo,
        prev_o=prev.o, prev_h=prev.h, prev_l=prev.l, prev_c=prev.c,
        hi20=hi20, lo20=lo20,
        c15m=c15m / pp, c1h=c1h / pp, c3h=c3h / pp, c24h=c24h / pp,
        dchg=(px - prev.c) / pp, dchg_atr=(px - prev.c) / atr_d1,
        consist=consist, ext5=ext5, ext15=ext15, ext1h=ext1h,
        atr_m5=atr_m5 / pp, atr_h1=atr_h1 / pp, atr_d1=atr_d1 / pp,
        rng_today=(day_hi - day_lo) / pp,
        posD=(px - day_lo) / (day_hi - day_lo) if day_hi > day_lo else 0.5,
        pos20=(px - lo20) / (hi20 - lo20) if hi20 > lo20 else 0.5,
        nxt_res=nxt_res, nxt_sup=nxt_sup,
        room_up=(nxt_res - px) / atr_h1 if nxt_res == nxt_res else 9.9,
        room_dn=(px - nxt_sup) / atr_h1 if nxt_sup == nxt_sup else 9.9,
        res_levels=res_levels[:5], sup_levels=sup_levels[:5],
    )


def strength(results):
    """Currency strength from % change vs previous daily close and over last 3h / 24h."""
    ccys = ["EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "JPY"]
    out = {}
    for key in ["d", "3h", "24h"]:
        sc = {c: [] for c in ccys}
        for p, r in results.items():
            b, q = p[:3], p[3:]
            if b not in ccys or q not in ccys:
                continue
            if key == "d":
                v = (r["px"] / r["prev_c"] - 1) * 100
            elif key == "3h":
                v = r["c3h"] * r["pip"] / r["px"] * 100
            else:
                v = r["c24h"] * r["pip"] / r["px"] * 100
            sc[b].append(v)
            sc[q].append(-v)
        out[key] = {c: float(np.mean(v)) for c, v in sc.items()}
    return out


def score(r, s):
    """Continuation score per direction; penalise chasing extremes."""
    b, q = r["pair"][:3], r["pair"][3:]
    res = {}
    for d in (1, -1):
        al = r["align"]
        trend = (al["m5"] + al["m15"] + 1.5 * al["h1"] + 1.5 * al["h4"] + al["d1"]) * d  # max 6
        mom = 0.0
        for tf in ("m5", "m15", "h1"):
            i = ind = r["ind"][tf]
            mom += 0.5 * (np.sign(i["hist"]) == d) + 0.5 * ((i["hist"] - i["hist_prev"]) * d > 0)
            mom += 0.5 * ((ind["pdi"] - ind["mdi"]) * d > 0)
        adxq = min(r["ind"]["h1"]["adx"], 40) / 40 + min(r["ind"]["m15"]["adx"], 40) / 40
        flow = np.sign(r["c3h"]) == d
        cs = 0.0
        if b in s["d"] and q in s["d"]:
            cs = (s["d"][b] - s["d"][q]) * d * 10 + (s["3h"][b] - s["3h"][q]) * d * 10
        # anti-chase penalties
        ext = r["ext5"] * d
        pos = r["posD"] if d == 1 else 1 - r["posD"]
        pos20 = r["pos20"] if d == 1 else 1 - r["pos20"]
        rsi15 = r["ind"]["m15"]["rsi"] if d == 1 else 100 - r["ind"]["m15"]["rsi"]
        rsi1h = r["ind"]["h1"]["rsi"] if d == 1 else 100 - r["ind"]["h1"]["rsi"]
        room = r["room_up"] if d == 1 else r["room_dn"]
        pen = 0.0
        pen += max(0, ext - 1.5) * 1.5
        pen += max(0, pos - 0.85) * 10
        pen += max(0, rsi15 - 68) * 0.15 + max(0, rsi1h - 70) * 0.15
        pen += max(0, pos20 - 0.92) * 15
        pen += max(0, 1.0 - room) * 3
        total = trend + mom + adxq + 1.0 * flow + cs - pen
        res[d] = dict(total=total, trend=trend, mom=mom, adxq=adxq, cs=cs, pen=pen,
                      ext=ext, pos=pos, pos20=pos20, room=room, rsi15=rsi15, rsi1h=rsi1h)
    return res


if __name__ == "__main__":
    results = {}
    for p in PAIRS:
        try:
            results[p] = analyze(p)
        except Exception as e:  # noqa: BLE001
            print("ERR", p, e, file=sys.stderr)
    s = strength(results)
    print("Currency strength (avg % vs prev close | 3h | 24h):")
    for c in sorted(s["d"], key=lambda c: -s["d"][c]):
        print(f"  {c}: {s['d'][c]:+.3f}%  {s['3h'][c]:+.3f}%  {s['24h'][c]:+.3f}%")

    rows = []
    for p, r in results.items():
        sc = score(r, s)
        d = 1 if sc[1]["total"] >= sc[-1]["total"] else -1
        x = sc[d]
        r["score"] = {str(k): v for k, v in sc.items()}
        rows.append(dict(
            pair=p, px=r["px"], t=r["t"][11:19], dir="BUY" if d == 1 else "SELL",
            score=round(x["total"], 2), trend=x["trend"], mom=round(x["mom"], 1),
            cs=round(x["cs"], 2), pen=round(x["pen"], 2),
            al="".join({1: "+", -1: "-", 0: "0"}[r["align"][k]] for k in ("m1", "m5", "m15", "h1", "h4", "d1")),
            rsi5=round(r["ind"]["m5"]["rsi"]), rsi15=round(r["ind"]["m15"]["rsi"]),
            rsi1h=round(r["ind"]["h1"]["rsi"]), adx1h=round(r["ind"]["h1"]["adx"]),
            c1h=round(r["c1h"], 1), c3h=round(r["c3h"], 1), dchg=round(r["dchg"], 1),
            ext5=round(r["ext5"], 2), posD=round(r["posD"], 2), pos20=round(r["pos20"], 2),
            room=round(x["room"], 2), atr1h=round(r["atr_h1"], 1), rng=round(r["rng_today"], 1),
        ))
    df = pd.DataFrame(rows).set_index("pair").sort_values("score", ascending=False)
    pd.set_option("display.width", 300)
    pd.set_option("display.max_columns", 40)
    print(df.to_string())
    with open(os.path.join(HERE, "results.json"), "w") as f:
        json.dump({"strength": s, "pairs": results}, f, default=float, indent=1)

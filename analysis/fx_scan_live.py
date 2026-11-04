#!/usr/bin/env python3
"""Multi-timeframe entry-quality scanner (H1/M30/M15/M5/M1) for the live snapshot
produced by fx_fetch_live.py.

Usage: python3 fx_scan_live.py <snapshot_dir>

For every pair and both directions it computes a 0-100 *entry-quality* score
with fixed, explicit weights (no win-rate claims; it is a ranking device):

  A. Trend alignment H1/M30/M15/M5 (EMA 8>20>50 stack + EMA20 slope) ... 20
  B. Momentum M15/M5 (MACD-hist sign & slope, ADX+DI, RSI zone) ........ 20
  C. Entry location: stretch vs EMA20-M15 in ATR(M15) units ............ 20
  D. Room to next obstacle (swing H/L, day H/L, prev-day H/L, round) ... 15
  E. M1/M5 timing (pullback done, resumption, higher-low/lower-high) ... 10
  F. Absence of exhaustion (RSI extremes, day range vs ADR, day edge) .. 10
  G. Execution cost: spread / ATR(M5) .................................. 5

Executable prices come from the Swissquote BBO feed ("prime" profile);
Yahoo 1-minute spot candles are used only for structure/indicators and are
checked for staleness and for consistency against the executable mid.
"""
import json, os, sys, time
import numpy as np, pandas as pd

SNAP = sys.argv[1] if len(sys.argv) > 1 else "data"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx_fetch_live import PAIRS  # noqa: E402


def pip(p):
    return 0.01 if p.endswith("JPY") else 0.0001


def load(p, interval):
    with open(f"{SNAP}/{p}_{interval}.json") as f:
        r = json.load(f)["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({"o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"]},
                      index=pd.to_datetime(r["timestamp"], unit="s", utc=True)).dropna()
    df = df[(df.h >= df.l) & (df.c > 0)]
    return df, r["meta"]


def rs(df, rule):
    return df.resample(rule, label="left", closed="left").agg(
        {"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def tr(df):
    return pd.concat([df.h - df.l, (df.h - df.c.shift()).abs(), (df.l - df.c.shift()).abs()], axis=1).max(axis=1)


def atr(df, n=14):
    return tr(df).ewm(alpha=1 / n, adjust=False).mean()


def adx(df, n=14):
    up, dn = df.h.diff(), -df.l.diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    mdm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    a = atr(df, n)
    pdi = 100 * pdm.ewm(alpha=1 / n, adjust=False).mean() / a
    mdi = 100 * mdm.ewm(alpha=1 / n, adjust=False).mean() / a
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi)
    return dx.ewm(alpha=1 / n, adjust=False).mean(), pdi, mdi


def macd_hist(c):
    line = ema(c, 12) - ema(c, 26)
    return line - line.ewm(span=9, adjust=False).mean()


def swings(df, k=3):
    """Fractal swing highs/lows (k bars each side), confirmed only."""
    h, l = df.h.values, df.l.values
    sh, sl = [], []
    for i in range(k, len(df) - k):
        if h[i] == max(h[i - k:i + k + 1]):
            sh.append((df.index[i], h[i]))
        if l[i] == min(l[i - k:i + k + 1]):
            sl.append((df.index[i], l[i]))
    return sh, sl


def tf_state(df):
    c = df.c
    e8, e20, e50 = ema(c, 8), ema(c, 20), ema(c, 50)
    a = atr(df)
    ad, pdi, mdi = adx(df)
    mh = macd_hist(c)
    slope = (e20.iloc[-1] - e20.iloc[-4]) / a.iloc[-1]  # EMA20 slope over 3 bars in ATR
    stack = 1 if e8.iloc[-1] > e20.iloc[-1] > e50.iloc[-1] else (-1 if e8.iloc[-1] < e20.iloc[-1] < e50.iloc[-1] else 0)
    return dict(c=c.iloc[-1], e8=e8.iloc[-1], e20=e20.iloc[-1], e50=e50.iloc[-1], atr=a.iloc[-1],
                rsi=rsi(c).iloc[-1], adx=ad.iloc[-1], pdi=pdi.iloc[-1], mdi=mdi.iloc[-1],
                mh=mh.iloc[-1], mh_prev=mh.iloc[-2], mh_prev2=mh.iloc[-3], slope=slope, stack=stack)


def structure(df, k=3):
    sh, sl = swings(df, k)
    out = {"sh": sh[-3:], "sl": sl[-3:]}
    if len(sh) >= 2 and len(sl) >= 2:
        hh, hl = sh[-1][1] > sh[-2][1], sl[-1][1] > sl[-2][1]
        out["bias"] = 1 if (hh and hl) else (-1 if (not hh and not hl) else 0)
        last = df.c.iloc[-1]
        out["bos_up"] = last > sh[-1][1]
        out["bos_dn"] = last < sl[-1][1]
    else:
        out["bias"], out["bos_up"], out["bos_dn"] = 0, False, False
    return out


def clip01(x):
    return float(max(0.0, min(1.0, x)))


def analyse(p, q):
    m1, meta = load(p, "1m")
    h1y, _ = load(p, "1h")
    d1, _ = load(p, "1d")
    now = time.time()
    last_bar = m1.index[-1]
    stale_s = now - (last_bar.timestamp() + 60)
    m5, m15, m30 = rs(m1, "5min"), rs(m1, "15min"), rs(m1, "30min")
    # H1: use the 3-month hourly series (long EMA history) patched with 1m-derived latest bars
    h1m = rs(m1, "1h")
    h1 = pd.concat([h1y[h1y.index < h1m.index[0]], h1m])

    pr = q["profiles"].get("prime") or next(iter(q["profiles"].values()))
    raw = q["profiles"].get("elite", pr)
    bid, ask = pr["bid"], pr["ask"]
    mid = (bid + ask) / 2
    pp = pip(p)
    spread_p = (ask - bid) / pp
    yahoo_vs_live = (m1.c.iloc[-1] - mid) / pp

    S = {n: tf_state(df) for n, df in (("h1", h1), ("m30", m30), ("m15", m15), ("m5", m5), ("m1", m1))}
    st15, st_h1, st5 = structure(m15, 3), structure(h1, 3), structure(m5, 3)

    # Session/day levels (UTC day)
    today = m1[m1.index >= pd.Timestamp(time.strftime("%Y-%m-%d", time.gmtime(now)), tz="UTC")]
    d_hi, d_lo = max(today.h.max(), mid), min(today.l.min(), mid)
    d_open = today.o.iloc[0]
    prev = d1[d1.index < today.index[0].normalize()]
    pd_hi, pd_lo = prev.h.iloc[-1], prev.l.iloc[-1]
    adr = (prev.h - prev.l).iloc[-20:].mean()
    a15, a5 = S["m15"]["atr"], S["m5"]["atr"]

    res = {"pair": p, "bid": bid, "ask": ask, "raw_bid": raw["bid"], "raw_ask": raw["ask"],
           "q_time": time.strftime("%H:%M:%S", time.gmtime(q["ts_ms"] / 1000)),
           "q_lag_s": round(q["fetched_at"] - q["ts_ms"] / 1000, 2), "spread_p": round(spread_p, 1),
           "yahoo_last": str(last_bar), "yahoo_stale_s": round(stale_s), "yahoo_vs_live_p": round(yahoo_vs_live, 1),
           "d_open": d_open, "d_hi": d_hi, "d_lo": d_lo, "pd_hi": pd_hi, "pd_lo": pd_lo,
           "adr_p": round(adr / pp), "day_chg_p": round((mid - d_open) / pp),
           "day_range_p": round((d_hi - d_lo) / pp), "atr15_p": round(a15 / pp, 1), "atr5_p": round(a5 / pp, 1),
           "atrh1_p": round(S["h1"]["atr"] / pp, 1), "S": S, "st15": st15, "st_h1": st_h1, "st5": st5}

    # candidate obstacles (price levels)
    lv = [d_hi, d_lo, pd_hi, pd_lo]
    lv += [x[1] for x in st15["sh"] + st15["sl"] + st_h1["sh"] + st_h1["sl"]]
    step = 50 * pp  # x.x50 / x.x00 round numbers
    base = np.floor(mid / step) * step
    lv += [base - step, base, base + step, base + 2 * step]

    for side, sgn in (("BUY", 1), ("SELL", -1)):
        entry = ask if sgn > 0 else bid
        # A. trend alignment (weights H1 .3, M30 .25, M15 .25, M5 .2)
        A = 0
        for n, w in (("h1", .30), ("m30", .25), ("m15", .25), ("m5", .20)):
            s = S[n]
            part = 0.6 * (1 if s["stack"] == sgn else (0.3 if s["stack"] == 0 and (s["c"] - s["e20"]) * sgn > 0 else 0))
            part += 0.4 * clip01(sgn * s["slope"] / 0.3)
            A += w * part
        struct_bonus = 0.5 * (st15["bias"] == sgn) + 0.5 * (st_h1["bias"] == sgn)
        A = 20 * (0.8 * A + 0.2 * struct_bonus)
        # B. momentum
        B = 0
        for n, w in (("m15", .55), ("m5", .45)):
            s = S[n]
            mh_ok = 1 if s["mh"] * sgn > 0 else 0
            mh_rise = 1 if (s["mh"] - s["mh_prev"]) * sgn > 0 else 0
            di_ok = 1 if (s["pdi"] - s["mdi"]) * sgn > 0 else 0
            adx_q = clip01((s["adx"] - 15) / 15)
            r = s["rsi"] if sgn > 0 else 100 - s["rsi"]
            rsi_q = 1 if 52 <= r <= 68 else (0.6 if 48 <= r < 52 or 68 < r <= 72 else 0.15)
            B += w * (0.25 * mh_ok + 0.2 * mh_rise + 0.2 * di_ok * adx_q + 0.15 * di_ok + 0.2 * rsi_q)
        B *= 20
        # C. entry location: stretch vs EMA20 on M15 (and M5) in ATR units
        z15 = sgn * (entry - S["m15"]["e20"]) / a15
        z5 = sgn * (entry - S["m5"]["e20"]) / a5
        def loc(z):
            if z < -0.5: return 0.1          # wrong side of the mean
            if z <= 1.2: return 1.0          # at/near value
            if z <= 2.0: return 1.0 - (z - 1.2) / 0.8 * 0.6
            return max(0.0, 0.4 - (z - 2.0) * 0.3)
        C = 20 * (0.6 * loc(z15) + 0.4 * loc(z5 * 0.8))
        # D. room to next obstacle in the trade direction (ATR M15 units)
        ahead = [x for x in lv if (x - entry) * sgn > 0.15 * a15]
        room = min(abs(x - entry) for x in ahead) / a15 if ahead else 6.0
        D = 15 * clip01(room / 3.0)
        # E. M1/M5 timing: shallow pullback done and resumed
        m1s, m5s = S["m1"], S["m5"]
        last12 = m1.iloc[-12:]
        if sgn > 0:
            pb = (last12.h.max() - last12.l.iloc[-6:].min()) / a5
            resumed = m1s["c"] > m1s["e8"] and m1s["mh"] > m1s["mh_prev"]
            held = last12.l.iloc[-6:].min() > S["m5"]["e20"] - 0.3 * a5
        else:
            pb = (last12.h.iloc[-6:].max() - last12.l.min()) / a5
            resumed = m1s["c"] < m1s["e8"] and m1s["mh"] < m1s["mh_prev"]
            held = last12.h.iloc[-6:].max() < S["m5"]["e20"] + 0.3 * a5
        E = 10 * (0.45 * resumed + 0.35 * held + 0.2 * (0.2 <= pb <= 1.5))
        # F. absence of exhaustion
        r_h1 = S["h1"]["rsi"] if sgn > 0 else 100 - S["h1"]["rsi"]
        r_15 = S["m15"]["rsi"] if sgn > 0 else 100 - S["m15"]["rsi"]
        day_move = sgn * (mid - d_open) / adr
        edge = (d_hi - entry) / a15 if sgn > 0 else (entry - d_lo) / a15
        F = 10 * (0.3 * (r_h1 < 72) + 0.3 * (r_15 < 72) + 0.2 * (day_move < 1.0) + 0.2 * (edge > 0.5 or room > 2))
        # G. cost
        G = 5 * clip01(1 - (spread_p * pp / a5 - 0.05) / 0.35)
        tot = A + B + C + D + E + F + G
        res[side] = dict(score=round(tot, 1), A=round(A, 1), B=round(B, 1), C=round(C, 1), D=round(D, 1),
                         E=round(E, 1), F=round(F, 1), G=round(G, 1), z15=round(z15, 2), z5=round(z5, 2),
                         room_atr15=round(room, 2), pullback_atr5=round(pb, 2), resumed=bool(resumed), held=bool(held),
                         rsi_h1=round(S["h1"]["rsi"], 1), rsi_m15=round(S["m15"]["rsi"], 1), day_move_adr=round(day_move, 2))
    best = "BUY" if res["BUY"]["score"] >= res["SELL"]["score"] else "SELL"
    res["best"] = best
    return res


def label(s):
    return "Alta" if s >= 72 else ("Média" if s >= 58 else ("Baixa" if s >= 45 else "Evitar"))


def main():
    quotes = json.load(open(f"{SNAP}/quotes.json"))
    out = []
    for p in PAIRS:
        try:
            out.append(analyse(p, quotes[p]))
        except Exception as e:
            print("ERR", p, e, file=sys.stderr)
    out.sort(key=lambda r: -r[r["best"]]["score"])
    print(f"{'pair':7} {'bid':>10} {'ask':>10} {'spr':>5} {'qtime':>8} {'yStale':>6} {'y-l':>5} {'dChg':>5} {'ADR':>4} "
          f"{'side':4} {'score':>5}  A    B    C    D    E    F   G   z15  room  rsiH1 rsi15")
    for r in out:
        b = r[r["best"]]
        print(f"{r['pair']:7} {r['bid']:>10} {r['ask']:>10} {r['spread_p']:>5} {r['q_time']:>8} {r['yahoo_stale_s']:>6} "
              f"{r['yahoo_vs_live_p']:>5} {r['day_chg_p']:>5} {r['adr_p']:>4} {r['best']:4} {b['score']:>5} "
              f"{b['A']:>4} {b['B']:>4} {b['C']:>4} {b['D']:>4} {b['E']:>4} {b['F']:>4} {b['G']:>3} {b['z15']:>5} "
              f"{b['room_atr15']:>5} {b['rsi_h1']:>5} {b['rsi_m15']:>5}")
    slim = []
    for r in out:
        r2 = {k: v for k, v in r.items() if k not in ("S", "st15", "st_h1", "st5")}
        r2["S"] = {n: {k: (round(v, 5) if isinstance(v, float) else v) for k, v in s.items()} for n, s in r["S"].items()}
        r2["st15"] = {k: ([(str(t), v) for t, v in val] if isinstance(val, list) else val) for k, val in r["st15"].items()}
        r2["st_h1"] = {k: ([(str(t), v) for t, v in val] if isinstance(val, list) else val) for k, val in r["st_h1"].items()}
        slim.append(r2)
    with open(f"{SNAP}/scan.json", "w") as f:
        json.dump(slim, f, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""BTC/USD multi-timeframe entry-quality analysis on a btc_fetch_live.py snapshot.

Usage: python3 btc_analyze.py <snapshot_dir>

Same scoring blocks/weights as fx_scan_live.py (A trend 20, B momentum 20,
C location 20, D room 15, E M1/M5 timing 10, F exhaustion 10, G cost 5), plus
crypto-only *measured* microstructure: venue order books (depth/imbalance) and
aggressor-side trade flow (CVD). Structure uses Kraken native candles (they
include the forming bar); Coinbase candles are a cross-check.
"""
import json, os, sys, time
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx_scan_live import ema, rsi, atr, tf_state, structure, swings, clip01  # noqa: E402

SNAP = sys.argv[1] if len(sys.argv) > 1 else "btc_data"


def L(k):
    with open(f"{SNAP}/{k}.json") as f:
        return json.load(f)


def kr_df(i):
    rows = L(f"kr_c{i}")["data"]["result"]["XXBTZUSD"]
    df = pd.DataFrame(rows, columns=["t", "o", "h", "l", "c", "vwap", "v", "n"]).astype(float)
    df.index = pd.to_datetime(df.t, unit="s", utc=True)
    return df[["o", "h", "l", "c", "vwap", "v"]]


def cb_df(g):
    rows = L(f"cb_c{g}")["data"]
    df = pd.DataFrame(rows, columns=["t", "l", "h", "o", "c", "v"]).astype(float)
    df.index = pd.to_datetime(df.t, unit="s", utc=True)
    return df.sort_index()[["o", "h", "l", "c", "v"]]


def fmt_ts(x):
    return time.strftime("%H:%M:%S", time.gmtime(x))


def main():
    now = time.time()
    out = {}
    # ---------------- top of book per venue ----------------
    venues = []
    cb = L("cb_ticker")
    t = pd.Timestamp(cb["data"]["time"]).timestamp()
    venues.append(("Coinbase", float(cb["data"]["bid"]), float(cb["data"]["ask"]), t, cb["recv"]))
    ks = L("kr_spread")
    b, a = float(ks["data"]["result"]["XXBTZUSD"][-1][1]), float(ks["data"]["result"]["XXBTZUSD"][-1][2])
    venues.append(("Kraken", b, a, ks["data"]["result"]["XXBTZUSD"][-1][0], ks["recv"]))
    bs = L("bs_ticker")
    venues.append(("Bitstamp", float(bs["data"]["bid"]), float(bs["data"]["ask"]), float(bs["data"]["timestamp"]), bs["recv"]))
    gm = L("gm_ticker")
    venues.append(("Gemini", float(gm["data"]["bid"]), float(gm["data"]["ask"]), gm["data"]["volume"]["timestamp"] / 1000, gm["recv"]))
    print("== TOP OF BOOK ==")
    for v, b, a, ts, rc in venues:
        print(f"  {v:9} bid {b:>10.2f} ask {a:>10.2f} spread ${a - b:6.2f} ({(a - b) / ((a + b) / 2) * 1e4:4.2f} bp) ts {fmt_ts(ts)} lag {rc - ts:5.2f}s")
    mids = [(b + a) / 2 for _, b, a, _, _ in venues]
    best_bid, best_ask = max(v[1] for v in venues), min(v[2] for v in venues)
    print(f"  cross-venue mid range ${max(mids) - min(mids):.2f}; consolidated best bid {best_bid:.2f} / best ask {best_ask:.2f}")
    cb_bid, cb_ask = venues[0][1], venues[0][2]
    mid = (cb_bid + cb_ask) / 2
    out["venues"] = venues

    # ---------------- candles ----------------
    TF = {"h1": kr_df(60), "m30": kr_df(30), "m15": kr_df(15), "m5": kr_df(5), "m1": kr_df(1)}
    d1 = kr_df(1440)
    S = {n: tf_state(df) for n, df in TF.items()}
    st = {n: structure(TF[n], 3) for n in ("h1", "m15", "m5")}
    cbh = {"m1": cb_df(60), "m5": cb_df(300), "m15": cb_df(900), "h1": cb_df(3600)}
    print("\n== CANDLE CONSISTENCY (Kraken vs Coinbase, last common close) ==")
    for n in ("m5", "m15", "h1"):
        k, c = TF[n], cbh[n]
        common = k.index.intersection(c.index)
        if len(common):
            i = common[-1]
            print(f"  {n}: {i:%H:%M} kraken {k.c[i]:.1f} coinbase {c.c[i]:.1f} diff {k.c[i] - c.c[i]:+.1f}; cb last bar {c.index[-1]:%H:%M}")
    print(f"  kraken last 1m bar {TF['m1'].index[-1]:%H:%M} (forming), age {now - TF['m1'].index[-1].timestamp():.0f}s")

    print("\n== MULTI-TIMEFRAME ==")
    for n in ("h1", "m30", "m15", "m5", "m1"):
        s = S[n]
        print(f"  {n:4} c {s['c']:.1f} e8 {s['e8']:.1f} e20 {s['e20']:.1f} e50 {s['e50']:.1f} rsi {s['rsi']:.1f} adx {s['adx']:.1f} "
              f"+di {s['pdi']:.1f} -di {s['mdi']:.1f} macdH {s['mh']:+.1f} (prev {s['mh_prev']:+.1f}) stack {s['stack']:+d} slope {s['slope']:+.2f} atr {s['atr']:.1f}")
    for n in ("h1", "m15", "m5"):
        print(f"  struct {n}: bias {st[n]['bias']:+d} bosUp {st[n]['bos_up']} bosDn {st[n]['bos_dn']} "
              f"SH {[(f'{x[0]:%d %H:%M}', round(x[1], 1)) for x in st[n]['sh']]} SL {[(f'{x[0]:%d %H:%M}', round(x[1], 1)) for x in st[n]['sl']]}")

    # ---------------- day context ----------------
    day0 = pd.Timestamp(time.strftime("%Y-%m-%d", time.gmtime(now)), tz="UTC")
    today = TF["m5"][TF["m5"].index >= day0]
    dbar = d1[d1.index == day0].iloc[0]
    d_open, d_hi, d_lo = dbar.o, max(dbar.h, today.h.max()), min(dbar.l, today.l.min())
    prev = d1[d1.index < day0]
    adr = (prev.h - prev.l).iloc[-20:].mean()
    pd_hi, pd_lo = prev.h.iloc[-1], prev.l.iloc[-1]
    vwap_day = (today.vwap * today.v).sum() / today.v.sum()
    lo_t = today.l.idxmin()
    aft = today[today.index >= lo_t]
    vwap_lo = (aft.vwap * aft.v).sum() / aft.v.sum()
    hi_t = today.h.idxmax()
    afth = today[today.index >= hi_t]
    vwap_hi = (afth.vwap * afth.v).sum() / afth.v.sum()
    # volume profile today ($100 bins on 1m vwap)
    bins = (today.vwap // 100 * 100)
    prof = today.v.groupby(bins).sum().sort_values(ascending=False)
    print("\n== DAY CONTEXT (00:00 UTC) ==")
    print(f"  open {d_open:.1f} high {d_hi:.1f} ({hi_t:%H:%M}) low {d_lo:.1f} ({lo_t:%H:%M}) range {d_hi - d_lo:.0f} = {(d_hi - d_lo) / adr:.2f} ADR (ADR20 {adr:.0f})")
    print(f"  change {mid - d_open:+.0f} ({(mid / d_open - 1) * 100:+.2f}%), pos in range {(mid - d_lo) / (d_hi - d_lo):.2f}")
    print(f"  prev day H {pd_hi:.1f} L {pd_lo:.1f}; VWAP day {vwap_day:.1f}; AVWAP from low {vwap_lo:.1f}; AVWAP from high {vwap_hi:.1f}")
    print(f"  volume POC bins (top 6): {[(int(k), round(v, 1)) for k, v in prof.head(6).items()]}")
    last7 = d1.iloc[-8:]
    print("  last 8 daily bars (kraken):")
    for t_, r in last7.iterrows():
        print(f"    {t_:%m-%d} o {r.o:.0f} h {r.h:.0f} l {r.l:.0f} c {r.c:.0f} v {r.v:.0f}")

    # levels map from H1 (20d) and D1 (120d) swings + day/prev-day + round numbers
    sh1, sl1 = swings(TF["h1"].iloc[-480:], 3)
    shd, sld = swings(d1.iloc[-120:], 2)
    lv_up = sorted({round(x[1], 1) for x in sh1 + shd if x[1] > mid} | {round(d_hi, 1), round(pd_hi, 1)} - {None})
    lv_dn = sorted({round(x[1], 1) for x in sl1 + sld if x[1] < mid} | {round(d_lo, 1), round(pd_lo, 1)}, reverse=True)
    rn = [k * 500 for k in range(int(mid // 500) - 3, int(mid // 500) + 5)]
    print(f"\n== LEVELS ==\n  above: {[x for x in lv_up if x > mid][:10]}\n  below: {[x for x in lv_dn if x < mid][:10]}\n  round: {[r for r in rn if abs(r - mid) < 2500]}")

    # ---------------- order books ----------------
    print("\n== ORDER BOOK DEPTH (BTC) ==")
    cbb = L("cb_book")["data"]
    krb = L("kr_book")["data"]["result"]["XXBTZUSD"]
    books = {"Coinbase": ([(float(p), float(q)) for p, q, *_ in cbb["bids"]], [(float(p), float(q)) for p, q, *_ in cbb["asks"]]),
             "Kraken": ([(float(p), float(q)) for p, q, _ in krb["bids"]], [(float(p), float(q)) for p, q, _ in krb["asks"]])}
    for v, (bids, asks) in books.items():
        bb, ba = bids[0][0], asks[0][0]
        m = (bb + ba) / 2
        row = []
        for pct in (0.1, 0.25, 0.5, 1.0):
            bq = sum(q for p, q in bids if p >= m * (1 - pct / 100))
            aq = sum(q for p, q in asks if p <= m * (1 + pct / 100))
            row.append(f"±{pct}%: bid {bq:7.1f} ask {aq:7.1f} imb {(bq - aq) / (bq + aq):+.2f}")
        print(f"  {v}: " + " | ".join(row))
        # walls: $100 buckets within 1.5%
        for side, lst in (("bid", bids), ("ask", asks)):
            s = pd.Series({p: q for p, q in lst if abs(p / m - 1) < 0.015})
            if len(s):
                g = s.groupby((s.index // 100) * 100).sum().sort_values(ascending=False).head(5)
                print(f"     top {side} buckets: {[(int(k), round(q, 1)) for k, q in g.items()]}")

    # ---------------- trade flow ----------------
    print("\n== AGGRESSOR FLOW ==")
    kt = pd.DataFrame(L("kr_trades")["data"]["result"]["XXBTZUSD"]).iloc[:, :4]
    kt.columns = ["p", "q", "t", "side"]
    kt = kt.astype({"p": float, "q": float, "t": float})
    kt["sgn"] = np.where(kt.side == "b", 1, -1)
    print(f"  Kraken trades {len(kt)} from {fmt_ts(kt.t.min())} to {fmt_ts(kt.t.max())}")
    tmax = kt.t.max()
    for w in (1, 3, 5, 10, 15, 20):
        x = kt[kt.t >= tmax - w * 60]
        buy, sell = x.q[x.sgn > 0].sum(), x.q[x.sgn < 0].sum()
        print(f"   last {w:>2}m: buy {buy:7.2f} sell {sell:7.2f} delta {buy - sell:+7.2f} BTC ({(buy - sell) / max(buy + sell, 1e-9):+.2f}) "
              f"px {x.p.iloc[0]:.0f}->{x.p.iloc[-1]:.0f}")
    ct = pd.DataFrame(L("cb_trades")["data"])
    ct["p"], ct["q"] = ct.price.astype(float), ct["size"].astype(float)
    ct["sgn"] = np.where(ct.side == "sell", 1, -1)  # Coinbase 'side' = maker side -> taker is opposite
    ct["t"] = pd.to_datetime(ct.time, utc=True).map(lambda x: x.timestamp())
    buy, sell = ct.q[ct.sgn > 0].sum(), ct.q[ct.sgn < 0].sum()
    print(f"  Coinbase last {len(ct)} trades ({fmt_ts(ct.t.min())}-{fmt_ts(ct.t.max())}): buy {buy:.2f} sell {sell:.2f} delta {buy - sell:+.2f} "
          f"({(buy - sell) / (buy + sell):+.2f}) px {ct.p.iloc[-1]:.0f}->{ct.p.iloc[0]:.0f}")
    # per-minute CVD (Kraken) last 30 minutes
    kt["m"] = pd.to_datetime(kt.t, unit="s", utc=True).dt.floor("1min")
    pm = kt[kt.t >= tmax - 20 * 60].groupby("m").apply(lambda g: pd.Series({"delta": (g.q * g.sgn).sum(), "vol": g.q.sum(), "close": g.p.iloc[-1]}), include_groups=False)
    print("  Kraken per-minute (last 20m) delta/vol@close: " + " ".join(f"{i:%H:%M}:{r.delta:+.1f}/{r.vol:.1f}@{r.close:.0f}" for i, r in pm.iterrows()))

    # ---------------- scoring (same blocks as FX scanner) ----------------
    a15, a5 = S["m15"]["atr"], S["m5"]["atr"]
    obst = [x for x in lv_up + lv_dn] + rn
    res = {}
    for side, sgn in (("BUY", 1), ("SELL", -1)):
        entry = cb_ask if sgn > 0 else cb_bid
        A = 0
        for n, w in (("h1", .30), ("m30", .25), ("m15", .25), ("m5", .20)):
            s = S[n]
            part = 0.6 * (1 if s["stack"] == sgn else (0.3 if s["stack"] == 0 and (s["c"] - s["e20"]) * sgn > 0 else 0))
            part += 0.4 * clip01(sgn * s["slope"] / 0.3)
            A += w * part
        A = 20 * (0.8 * A + 0.2 * (0.5 * (st["m15"]["bias"] == sgn) + 0.5 * (st["h1"]["bias"] == sgn)))
        B = 0
        for n, w in (("m15", .55), ("m5", .45)):
            s = S[n]
            adx_q = clip01((s["adx"] - 15) / 15)
            di_ok = 1 if (s["pdi"] - s["mdi"]) * sgn > 0 else 0
            r = s["rsi"] if sgn > 0 else 100 - s["rsi"]
            rsi_q = 1 if 52 <= r <= 68 else (0.6 if 48 <= r < 52 or 68 < r <= 72 else 0.15)
            B += w * (0.25 * (s["mh"] * sgn > 0) + 0.2 * ((s["mh"] - s["mh_prev"]) * sgn > 0) + 0.2 * di_ok * adx_q + 0.15 * di_ok + 0.2 * rsi_q)
        B *= 20
        z15 = sgn * (entry - S["m15"]["e20"]) / a15
        z5 = sgn * (entry - S["m5"]["e20"]) / a5

        def loc(z):
            if z < -0.5: return 0.1
            if z <= 1.2: return 1.0
            if z <= 2.0: return 1.0 - (z - 1.2) / 0.8 * 0.6
            return max(0.0, 0.4 - (z - 2.0) * 0.3)
        C = 20 * (0.6 * loc(z15) + 0.4 * loc(z5 * 0.8))
        ahead = [x for x in obst if (x - entry) * sgn > 0.15 * a15]
        room = min(abs(x - entry) for x in ahead) / a15 if ahead else 6.0
        nxt = min(ahead, key=lambda x: abs(x - entry)) if ahead else None
        D = 15 * clip01(room / 3.0)
        m1 = TF["m1"]
        last12 = m1.iloc[-12:]
        if sgn > 0:
            pb = (last12.h.max() - last12.l.iloc[-6:].min()) / a5
            resumed = S["m1"]["c"] > S["m1"]["e8"] and S["m1"]["mh"] > S["m1"]["mh_prev"]
            held = last12.l.iloc[-6:].min() > S["m5"]["e20"] - 0.3 * a5
        else:
            pb = (last12.h.iloc[-6:].max() - last12.l.min()) / a5
            resumed = S["m1"]["c"] < S["m1"]["e8"] and S["m1"]["mh"] < S["m1"]["mh_prev"]
            held = last12.h.iloc[-6:].max() < S["m5"]["e20"] + 0.3 * a5
        E = 10 * (0.45 * resumed + 0.35 * held + 0.2 * (0.2 <= pb <= 1.5))
        rh = S["h1"]["rsi"] if sgn > 0 else 100 - S["h1"]["rsi"]
        r15 = S["m15"]["rsi"] if sgn > 0 else 100 - S["m15"]["rsi"]
        day_move = sgn * (mid - d_open) / adr
        edge = (d_hi - entry) / a15 if sgn > 0 else (entry - d_lo) / a15
        F = 10 * (0.3 * (rh < 72) + 0.3 * (r15 < 72) + 0.2 * (day_move < 1.0) + 0.2 * (edge > 0.5 or room > 2))
        G = 5 * clip01(1 - ((cb_ask - cb_bid) / a5 - 0.05) / 0.35)
        res[side] = dict(score=round(A + B + C + D + E + F + G, 1), A=round(A, 1), B=round(B, 1), C=round(C, 1), D=round(D, 1),
                         E=round(E, 1), F=round(F, 1), G=round(G, 1), z15=round(z15, 2), z5=round(z5, 2), room_atr15=round(room, 2),
                         next_obstacle=nxt, pullback_atr5=round(pb, 2), resumed=bool(resumed), held=bool(held), day_move_adr=round(day_move, 2))
    print("\n== ENTRY-QUALITY SCORE ==")
    for k, v in res.items():
        print(f"  {k}: {v}")
    print(f"\n  ATR: M1 {S['m1']['atr']:.0f} M5 {a5:.0f} M15 {a15:.0f} H1 {S['h1']['atr']:.0f} D(ADR20) {adr:.0f}")
    print("\n  M15 last 12:")
    for t_, r in TF["m15"].iloc[-12:].iterrows():
        print(f"    {t_:%H:%M} o {r.o:.0f} h {r.h:.0f} l {r.l:.0f} c {r.c:.0f} v {r.v:6.1f}")
    print("  M5 last 12:")
    for t_, r in TF["m5"].iloc[-12:].iterrows():
        print(f"    {t_:%H:%M} o {r.o:.0f} h {r.h:.0f} l {r.l:.0f} c {r.c:.0f} v {r.v:6.1f}")
    print("  M1 last 10:")
    for t_, r in TF["m1"].iloc[-10:].iterrows():
        print(f"    {t_:%H:%M} o {r.o:.0f} h {r.h:.0f} l {r.l:.0f} c {r.c:.0f} v {r.v:5.2f}")
    print("  H1 last 12:")
    for t_, r in TF["h1"].iloc[-12:].iterrows():
        print(f"    {t_:%d %H:%M} o {r.o:.0f} h {r.h:.0f} l {r.l:.0f} c {r.c:.0f} v {r.v:6.1f}")


if __name__ == "__main__":
    main()

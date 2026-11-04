#!/usr/bin/env python3
"""XAU/USD multi-timeframe entry-quality analysis on an xau_fetch_live.py snapshot.

Usage: python3 xau_analyze.py <snapshot_dir> [live_tape.jsonl]

Series = Dukascopy spot (previous days' 1m BID/ASK candles -> mid; today's
hourly bid/ask ticks -> 1m mid bars) + optional live Swissquote tape (1 s polls
of the raw "elite" BBO -> 1m mid bars) for the hour Dukascopy has not published
yet. Gaps are reported, never interpolated. Scoring blocks/weights are the same
as fx_scan_live.py (A20 B20 C20 D15 E10 F10 G5). Tick counts are an activity
proxy only - spot gold has no consolidated traded volume.
"""
import glob, json, lzma, os, struct, sys, time
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx_scan_live import tf_state, structure, swings, clip01  # noqa: E402

SNAP = sys.argv[1] if len(sys.argv) > 1 else "xau_data"
TAPE = sys.argv[2] if len(sys.argv) > 2 else None
PT = 0.001  # Dukascopy XAUUSD point


def candles(path, day0):
    raw = lzma.decompress(open(path, "rb").read())
    rows = [struct.unpack(">IIIIIf", raw[i:i + 24]) for i in range(0, len(raw), 24)]
    df = pd.DataFrame(rows, columns=["s", "o", "c", "l", "h", "v"])
    df.index = day0 + pd.to_timedelta(df.s, unit="s")
    for k in "ochl":
        df[k] = df[k] * PT
    return df[["o", "h", "l", "c", "v"]]


def ticks(path, hour0):
    raw = lzma.decompress(open(path, "rb").read())
    a = np.frombuffer(raw, dtype=">u4").reshape(-1, 5)
    ms, ask, bid = a[:, 0].astype(np.int64), a[:, 1] * PT, a[:, 2] * PT
    df = pd.DataFrame({"bid": bid, "ask": ask}, index=hour0 + pd.to_timedelta(ms, unit="ms"))
    return df


def bars_from_ticks(tk):
    mid = (tk.bid + tk.ask) / 2
    g = mid.resample("1min")
    df = pd.DataFrame({"o": g.first(), "h": g.max(), "l": g.min(), "c": g.last(), "v": g.count()}).dropna()
    return df


def rs(df, rule):
    return df.resample(rule, label="left", closed="left").agg({"o": "first", "h": "max", "l": "min", "c": "last", "v": "sum"}).dropna()


def main():
    now = time.time()
    # ---------------- history ----------------
    prev = []
    for f in sorted(glob.glob(f"{SNAP}/m1_BID_*.bi5")):
        d = f.split("_")[-1][:8]
        day0 = pd.Timestamp(d, tz="UTC")
        fa = f.replace("BID", "ASK")
        b = candles(f, day0)
        if os.path.exists(fa):
            a = candles(fa, day0)
            m = (b[["o", "h", "l", "c"]] + a[["o", "h", "l", "c"]]) / 2
            m["v"] = b.v
        else:
            m = b
        m = m[m.v > 0]  # drop flat weekend/no-trade minutes
        prev.append(m)
    hist = pd.concat(prev).sort_index() if prev else pd.DataFrame()
    tk = []
    for f in sorted(glob.glob(f"{SNAP}/ticks_*.bi5")):
        stem = os.path.basename(f)[6:-4]  # YYYYMMDD_HH
        hour0 = pd.Timestamp(stem[:8], tz="UTC") + pd.Timedelta(hours=int(stem[9:11]))
        tk.append(ticks(f, hour0))
    tk = pd.concat(tk).sort_index()
    today_bars = bars_from_ticks(tk)
    tick_hours = sorted({int(os.path.basename(f)[15:17]) for f in glob.glob(f"{SNAP}/ticks_*.bi5")})
    # ---------------- live tape ----------------
    tape_bars = pd.DataFrame()
    tape_spreads = None
    if TAPE and os.path.exists(TAPE):
        rows = [json.loads(x) for x in open(TAPE)]
        tp = pd.DataFrame([{"t": r["ts"] / 1000, "bid": r["p"]["elite"]["bid"], "ask": r["p"]["elite"]["ask"],
                            "pbid": r["p"]["prime"]["bid"], "pask": r["p"]["prime"]["ask"]} for r in rows])
        tp = tp.drop_duplicates("t")
        tp.index = pd.to_datetime(tp.t, unit="s", utc=True)
        tape_spreads = (tp.pask - tp.pbid)
        tape_bars = bars_from_ticks(tp[["bid", "ask"]])
        tape_bars = tape_bars[tape_bars.index > today_bars.index[-1]]
    m1 = pd.concat([hist, today_bars, tape_bars]).sort_index()
    m1 = m1[~m1.index.duplicated(keep="last")]

    print("== DATA COVERAGE ==")
    print(f"  prev-day 1m candles: {hist.index[0]:%m-%d %H:%M} -> {hist.index[-1]:%m-%d %H:%M} ({len(hist)} bars)")
    print(f"  today ticks: hours {tick_hours}; {len(tk)} ticks; last tick {tk.index[-1]:%H:%M:%S}")
    if len(tape_bars):
        print(f"  live tape (Swissquote raw BBO, ~1 s polls): {tape_bars.index[0]:%H:%M} -> {tape_bars.index[-1]:%H:%M} ({len(tape_bars)} bars)")
    gaps = m1.index.to_series().diff()
    big = gaps[gaps > pd.Timedelta("10min")]
    big = big[big.index > m1.index[-1] - pd.Timedelta("2D")]
    print("  gaps > 10 min (last 2 days): " + ", ".join(f"{(i - g):%m-%d %H:%M}->{i:%H:%M}" for i, g in big.items()))
    # Dukascopy vs Swissquote consistency on overlapping minute(s)
    q = json.load(open(f"{SNAP}/quote.json"))
    feeds = q["data"]
    best = max((f for f in feeds if f["topo"]["platform"].startswith("Swissquote")), key=lambda f: f["ts"])
    prof = {p["spreadProfile"]: p for p in best["spreadProfilePrices"]}
    bid, ask = prof["prime"]["bid"], prof["prime"]["ask"]
    mid = (bid + ask) / 2
    print("\n== EXECUTABLE QUOTE (Swissquote) ==")
    for k in ("premium", "prime", "elite"):
        p = prof[k]
        print(f"  {k:8} bid {p['bid']:.3f} ask {p['ask']:.3f} spread ${p['ask'] - p['bid']:.3f}")
    print(f"  server {best['topo']} ts {time.strftime('%H:%M:%S', time.gmtime(best['ts'] / 1000))}.{best['ts'] % 1000:03d} lag {q['recv'] - best['ts'] / 1000:.2f}s")
    ga = q.get("goldapi", {}).get("data")
    if ga:
        print(f"  gold-api.com cross-check {ga['price']:.3f} updated {ga['updatedAt']} -> diff vs SQ mid {ga['price'] - mid:+.3f}")
    if tape_spreads is not None:
        print(f"  tape prime spread: median ${tape_spreads.median():.3f} max ${tape_spreads.max():.3f} over {len(tape_spreads)} polls")
    hs = (tk.ask - tk.bid).resample("1h").median()
    print("  Dukascopy median spread by hour today: " + " ".join(f"{i:%H}h:{v:.2f}" for i, v in hs.dropna().items()))

    # ---------------- daily ----------------
    d1 = []
    for f in sorted(glob.glob(f"{SNAP}/d1_BID_*.bi5")):
        y = f.split("_")[-1][:4]
        d1.append(candles(f, pd.Timestamp(f"{y}-01-01", tz="UTC")))
    d1 = pd.concat(d1).sort_index() if d1 else pd.DataFrame()
    d1 = d1[d1.v > 0]
    # Dukascopy day candles: index = day start; completed days only
    day0 = pd.Timestamp(time.strftime("%Y-%m-%d", time.gmtime(now)), tz="UTC")
    today = m1[m1.index >= day0]
    d_open, d_hi, d_lo = today.o.iloc[0], max(today.h.max(), mid), min(today.l.min(), mid)
    hi_t, lo_t = today.h.idxmax(), today.l.idxmin()
    prevd = rs(m1[m1.index < day0], "1D")
    prevd = prevd[prevd.v > 0]
    pd_hi, pd_lo, pd_c = prevd.h.iloc[-1], prevd.l.iloc[-1], prevd.c.iloc[-1]
    rng = (d1.h - d1.l) if len(d1) else (prevd.h - prevd.l)
    adr = rng[rng.index < day0].iloc[-20:].mean()
    print("\n== DAY CONTEXT (00:00 UTC; gold session opens 23:00 UTC) ==")
    print(f"  open {d_open:.2f} high {d_hi:.2f} ({hi_t:%H:%M}) low {d_lo:.2f} ({lo_t:%H:%M}) range {d_hi - d_lo:.2f} = {(d_hi - d_lo) / adr:.2f} ADR (ADR20 {adr:.2f})")
    print(f"  change vs open {mid - d_open:+.2f} ({(mid / d_open - 1) * 100:+.2f}%), vs prev close {mid - pd_c:+.2f}; pos in range {(mid - d_lo) / (d_hi - d_lo):.2f}")
    print(f"  prev day H {pd_hi:.2f} L {pd_lo:.2f} C {pd_c:.2f}")
    if len(d1):
        print("  last 10 daily (Dukascopy BID):")
        for t_, r in d1.iloc[-10:].iterrows():
            print(f"    {t_:%m-%d} o {r.o:.2f} h {r.h:.2f} l {r.l:.2f} c {r.c:.2f}")
    # tick-activity profile today ($2 bins)
    prof_ = today.v.groupby((today.c // 2) * 2).sum().sort_values(ascending=False)
    print(f"  tick-activity profile top bins: {[(float(k), int(v)) for k, v in prof_.head(6).items()]}")

    # ---------------- timeframes ----------------
    TF = {"h1": rs(m1, "1h"), "m30": rs(m1, "30min"), "m15": rs(m1, "15min"), "m5": rs(m1, "5min"), "m1": m1}
    S = {n: tf_state(df) for n, df in TF.items()}
    st = {n: structure(TF[n], 3) for n in ("h1", "m15", "m5")}
    print("\n== MULTI-TIMEFRAME ==")
    for n in ("h1", "m30", "m15", "m5", "m1"):
        s = S[n]
        print(f"  {n:4} c {s['c']:.2f} e8 {s['e8']:.2f} e20 {s['e20']:.2f} e50 {s['e50']:.2f} rsi {s['rsi']:.1f} adx {s['adx']:.1f} "
              f"+di {s['pdi']:.1f} -di {s['mdi']:.1f} macdH {s['mh']:+.3f} (prev {s['mh_prev']:+.3f}) stack {s['stack']:+d} slope {s['slope']:+.2f} atr {s['atr']:.2f}")
    for n in ("h1", "m15", "m5"):
        print(f"  struct {n}: bias {st[n]['bias']:+d} bosUp {st[n]['bos_up']} bosDn {st[n]['bos_dn']} "
              f"SH {[(f'{x[0]:%d %H:%M}', round(x[1], 2)) for x in st[n]['sh']]} SL {[(f'{x[0]:%d %H:%M}', round(x[1], 2)) for x in st[n]['sl']]}")

    # levels
    sh1, sl1 = swings(TF["h1"].iloc[-160:], 3)
    shd, sld = (swings(d1.iloc[-120:], 2) if len(d1) > 10 else ([], []))
    ups = sorted({round(x[1], 2) for x in sh1 + shd if x[1] > mid} | {round(d_hi, 2), round(pd_hi, 2)})
    dns = sorted({round(x[1], 2) for x in sl1 + sld if x[1] < mid} | {round(d_lo, 2), round(pd_lo, 2)}, reverse=True)
    rn = [k * 25 for k in range(int(mid // 25) - 4, int(mid // 25) + 6)]
    print(f"\n== LEVELS ==\n  above: {[x for x in ups if x > mid][:10]}\n  below: {[x for x in dns if x < mid][:10]}\n  round(25): {[r for r in rn if abs(r - mid) < 100]}")

    # ---------------- score ----------------
    a15, a5 = S["m15"]["atr"], S["m5"]["atr"]
    obst = ups + dns + rn
    res = {}
    for side, sgn in (("BUY", 1), ("SELL", -1)):
        entry = ask if sgn > 0 else bid
        A = 0
        for n, w in (("h1", .30), ("m30", .25), ("m15", .25), ("m5", .20)):
            s = S[n]
            part = 0.6 * (1 if s["stack"] == sgn else (0.3 if s["stack"] == 0 and (s["c"] - s["e20"]) * sgn > 0 else 0))
            A += w * (part + 0.4 * clip01(sgn * s["slope"] / 0.3))
        A = 20 * (0.8 * A + 0.2 * (0.5 * (st["m15"]["bias"] == sgn) + 0.5 * (st["h1"]["bias"] == sgn)))
        B = 0
        for n, w in (("m15", .55), ("m5", .45)):
            s = S[n]
            di_ok = 1 if (s["pdi"] - s["mdi"]) * sgn > 0 else 0
            r = s["rsi"] if sgn > 0 else 100 - s["rsi"]
            rsi_q = 1 if 52 <= r <= 68 else (0.6 if 48 <= r < 52 or 68 < r <= 72 else 0.15)
            B += w * (0.25 * (s["mh"] * sgn > 0) + 0.2 * ((s["mh"] - s["mh_prev"]) * sgn > 0) + 0.2 * di_ok * clip01((s["adx"] - 15) / 15) + 0.15 * di_ok + 0.2 * rsi_q)
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
        G = 5 * clip01(1 - ((ask - bid) / a5 - 0.05) / 0.35)
        res[side] = dict(score=round(A + B + C + D + E + F + G, 1), A=round(A, 1), B=round(B, 1), C=round(C, 1), D=round(D, 1),
                         E=round(E, 1), F=round(F, 1), G=round(G, 1), z15=round(z15, 2), z5=round(z5, 2), room_atr15=round(room, 2),
                         next_obstacle=nxt, pullback_atr5=round(pb, 2), resumed=bool(resumed), held=bool(held), day_move_adr=round(day_move, 2))
    print("\n== ENTRY-QUALITY SCORE ==")
    for k, v in res.items():
        print(f"  {k}: {v}")
    print(f"\n  ATR: M1 {S['m1']['atr']:.2f} M5 {a5:.2f} M15 {a15:.2f} H1 {S['h1']['atr']:.2f} ADR20 {adr:.2f}")
    for n, k in (("h1", 14), ("m15", 14), ("m5", 14), ("m1", 12)):
        print(f"  {n.upper()} last {k}:")
        for t_, r in TF[n].iloc[-k:].iterrows():
            print(f"    {t_:%d %H:%M} o {r.o:.2f} h {r.h:.2f} l {r.l:.2f} c {r.c:.2f} ticks {int(r.v)}")


if __name__ == "__main__":
    main()

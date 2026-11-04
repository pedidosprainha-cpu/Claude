#!/usr/bin/env python3
"""Render M5 (today) + H1 (10d) candlestick panels with EMAs and S/R for chosen pairs."""
import sys, warnings, io, contextlib
warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
with contextlib.redirect_stdout(io.StringIO()):
    import fx_analyze as A

def candles(ax, df, w):
    for t, r in df.iterrows():
        col = "#1a9850" if r.c >= r.o else "#d73027"
        ax.vlines(t, r.l, r.h, color=col, lw=0.7)
        ax.vlines(t, min(r.o, r.c), max(r.o, r.c), color=col, lw=w)

pairs = sys.argv[1].split(",")
out = sys.argv[2]
fig, axes = plt.subplots(len(pairs), 2, figsize=(22, 4.2*len(pairs)))
for i, p in enumerate(pairs):
    f, r = A.frames[p], A.R[p]
    m5 = f["m5"].iloc[-int(__import__("os").environ.get("NB","150")):]; h1 = f["h1"].iloc[-240:]
    for ax, df, w, ttl in [(axes[i][0], m5, 2.2, "M5"), (axes[i][1], h1, 1.6, "H1")]:
        candles(ax, df, w)
        full = f["m5"] if ttl == "M5" else f["h1"]
        for n, c in [(8, "#999"), (21, "#2166ac"), (50, "#f46d43"), (200, "#762a83")]:
            ax.plot(df.index, A.ema(full.c, n).loc[df.index], lw=0.9, color=c, label=f"EMA{n}")
        for lv in r["res"][:3]: ax.axhline(lv, color="#d73027", ls=":", lw=0.8)
        for lv in r["sup"][:3]: ax.axhline(lv, color="#1a9850", ls=":", lw=0.8)
        ax.axhline(r["px"], color="k", lw=0.8)
        ax.axhline(r["day_open"], color="#fdae61", ls="--", lw=0.8)
        ax.set_title(f"{p} {ttl}  px={r['px']:.5f}  dayH/L={r['day_hi']:.5f}/{r['day_lo']:.5f}  prevH/L={r['prev_hi']:.5f}/{r['prev_lo']:.5f}", fontsize=9)
        ax.grid(alpha=.25); ax.tick_params(labelsize=7)
    axes[i][0].legend(fontsize=6, loc="upper left")
plt.tight_layout(); plt.savefig(out, dpi=70)
print("saved", out)

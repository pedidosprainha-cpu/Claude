import json, sys, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
D = sys.argv[5] if len(sys.argv) > 5 else "data"   # usage: charts.py out.png tf SYM1,SYM2 nbars [data_dir]
def load(s, iv):
    r = json.load(open(f"{D}/{s}_{iv}.json"))["chart"]["result"][0]; q = r["indicators"]["quote"][0]
    df = pd.DataFrame({"o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"]}, index=pd.to_datetime(r["timestamp"], unit="s", utc=True)).dropna()
    return df[(df.h >= df.l)]
def fr(s, tf):
    h1 = load(s, "1h")
    if tf == "h1": return h1
    if tf == "h4": return h1.resample("4h", offset="2h").agg({"o":"first","h":"max","l":"min","c":"last"}).dropna()
    if tf == "d1": return h1.resample("24h", offset="22h").agg({"o":"first","h":"max","l":"min","c":"last"}).dropna()
    if tf == "m15": return load(s, "15m")
ema = lambda c, n: c.ewm(span=n, adjust=False).mean()
def panel(ax, s, tf, n):
    df = fr(s, tf); e20, e50, e200 = ema(df.c,20), ema(df.c,50), ema(df.c,200)
    df = df.iloc[-n:]; x = np.arange(len(df))
    up = df.c >= df.o
    ax.vlines(x, df.l, df.h, color=np.where(up, "#2a9d55", "#d9473b"), lw=0.6)
    ax.vlines(x, df[["o","c"]].min(axis=1), df[["o","c"]].max(axis=1), color=np.where(up, "#2a9d55", "#d9473b"), lw=2.2)
    for e, col in ((e20,"#1f77b4"),(e50,"#ff7f0e"),(e200,"#7b3fa0")): ax.plot(x, e.iloc[-n:].values, color=col, lw=0.9)
    ax.axhline(df.c.iloc[-1], color="k", lw=0.5, ls=":")
    step = max(1, n // 6); ax.set_xticks(x[::step]); ax.set_xticklabels([d.strftime("%m-%d %H") for d in df.index[::step]], fontsize=6)
    ax.tick_params(axis="y", labelsize=6); ax.set_title(f"{s} {tf.upper()}  last {df.c.iloc[-1]:.5g}", fontsize=8); ax.grid(alpha=0.2)
syms = sys.argv[3].split(","); tf = sys.argv[2]; n = int(sys.argv[4])
cols = 3; rows = int(np.ceil(len(syms)/cols))
fig, axs = plt.subplots(rows, cols, figsize=(15, 3.2*rows)); axs = np.atleast_1d(axs).ravel()
for a, s in zip(axs, syms): panel(a, s, tf, n)
for a in axs[len(syms):]: a.axis("off")
plt.tight_layout(); plt.savefig(sys.argv[1], dpi=80)

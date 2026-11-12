"""Does requiring the market-entry side to agree with the H1/H4 trend reduce losses?

    python3 research/trend_filter_study.py   # needs ensemble_oos.pkl and signal_events.pkl

Pre-registered (written before running):
  A  current rule: the side with the highest validated expected R, whatever the trend
  B  only sides that agree with the H1 + H4 trend (sign of trend_h1 + trend_h4)
  C  only sides that agree with the H1, H4 and D1 trends (all three signs)
  metrics per walk-forward block (2..6) for the hour's top-1 candidate and for the
  executable filter (top 2% of the signal model): mean R and share of losing trades
  ADOPT the alignment filter (B, else C) if its loss share is lower than A's in >= 4 of 5
  blocks AND its mean R is not worse than A's by more than 0.005R on average.
  Block 7 (untouched) reported once.
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = "s20|tr10"

oos = pd.read_pickle(os.path.join(ROOT, "research", "data", "ensemble_oos.pkl"))
sig = pd.read_pickle(os.path.join(ROOT, "research", "data", "signal_events.pkl"))[["symbol", "time", "trend_h1", "trend_h4", "d1_trend"]]
for d in (oos, sig):
    d["time"] = pd.to_datetime(d.time, utc=True)
df = oos.merge(sig, on=["symbol", "time"], how="inner")
tr = np.sign(df.trend_h1 + df.trend_h4).replace(0, np.nan)
all3 = (np.sign(df.trend_h1) == np.sign(df.trend_h4)) & (np.sign(df.trend_h4) == np.sign(df.d1_trend.fillna(0)))
rows = []
for d, tag in ((1, "L"), (-1, "S")):
    rows.append(pd.DataFrame({"symbol": df.symbol, "time": df.time, "block": df.block, "d": d,
                              "ev": df.sig_el if d == 1 else df.sig_es, "thr": df.sig_thr2, "r": df[f"{tag}|{G}"],
                              "alignB": (tr == d).to_numpy(), "alignC": (all3 & (np.sign(df.trend_h1) == d)).to_numpy()}))
c = pd.concat(rows, ignore_index=True)
c = c[np.isfinite(c.r)]


def evaluate(v, mask):
    sub = v[mask]
    top1 = sub.loc[sub.groupby("time").ev.idxmax()]
    ex = sub[sub.ev >= sub.thr]
    ex = ex.loc[ex.groupby(["symbol", ex.time.dt.floor("D")]).ev.idxmax()]   # at most one per instrument a day
    return {"top1_r": round(float(top1.r.mean()), 4), "top1_loss": round(float((top1.r < 0).mean()), 4),
            "exec_n": int(len(ex)), "exec_r": round(float(ex.r.mean()), 4) if len(ex) else None,
            "exec_loss": round(float((ex.r < 0).mean()), 4) if len(ex) else None}


res = {}
for name, col in (("A", None), ("B", "alignB"), ("C", "alignC")):
    res[name] = []
    for b in range(2, 8):
        v = c[c.block == b]
        res[name].append({"block": b, **evaluate(v, np.ones(len(v), bool) if col is None else v[col].to_numpy())})
wf = {k: [r for r in v if r["block"] < 7] for k, v in res.items()}
for k in ("A", "B", "C"):
    print(k, " · ".join(f"b{r['block']}: top1 {r['top1_r']:+.3f}R perde {r['top1_loss']*100:.0f}% | exec {r['exec_r'] if r['exec_r'] is None else f'{r[chr(101)+chr(120)+chr(101)+chr(99)+chr(95)+chr(114)]:+.3f}'}R n{r['exec_n']}" for r in res[k]))


def decide(k):
    fewer = sum(x["top1_loss"] < a["top1_loss"] for x, a in zip(wf[k], wf["A"]))
    dr = np.mean([x["top1_r"] - a["top1_r"] for x, a in zip(wf[k], wf["A"])])
    return fewer, dr


adopt = "A"
for k in ("B", "C"):
    fewer, dr = decide(k)
    print(f"{k}: menos perdas em {fewer}/5 blocos · diferença média de R {dr:+.4f}")
    if adopt == "A" and fewer >= 4 and dr >= -0.005:
        adopt = k
print("ADOTADO:", adopt)
print("TESTE (bloco 7):", {k: v[-1] for k, v in res.items()})
json.dump({"adopted": adopt, "results": res}, open(os.path.join(ROOT, "research", "RESULTADOS_FILTRO_TENDENCIA.json"), "w"),
          ensure_ascii=False, indent=1)

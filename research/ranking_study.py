"""Is the #1 of the ranking really the best market entry right now? (cross-sectional study)

    python3 research/ranking_study.py      # needs research/data/ensemble_oos.pkl (ensemble_oos.py)

Every hour all 32 instruments x 2 sides are candidate market entries (plan of the app: stop
2x ATR H1, trailing 1 ATR after +1R, 48 h, spread included). Out-of-sample inputs per
candidate: signal-model expected R (both sides), explosion logit, explosion-direction logit
(research/ensemble_oos.py) and, for the "micro -> macro" ranker, macro features
(fxengine/analysis/macro_features.py: risk appetite, US yields, dollar, oil, copper, gold,
carry, rate trajectory, CFTC positioning) rebuilt from history with release lags.

Pre-registered (written before running):
  M0  random candidate (the average of all candidates of the hour)
  M1  signal model: highest expected R                                   (current app)
  M2  meta-ranker on the model outputs (signal both sides, explosion, direction)
  M3  meta-ranker on model outputs + macro                               ("micro -> macro")
  meta-ranker: gradient-boosted P(R > 0) per candidate, score = p * avg win + (1 - p) * avg loss,
  trained walk-forward on the OOS predictions of the earlier blocks (block b uses blocks 1..b-1)
  primary metric: mean realised R of the hour's top-1 candidate; also top-3, the hour's
  Spearman IC and how often the top-1 beats the median candidate
  ADOPT M3 (else M2) over M1 only if its mean top-1 R over blocks 2..6 is higher AND it is higher
  in at least 4 of the 5 blocks; block 7 (untouched) is reported once
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gbm import GBM  # noqa: E402

from fxengine.analysis import macro_features as mf  # noqa: E402
from fxengine.data import yahoo  # noqa: E402
from fxengine.data.fundamentals import BIS_AREAS, BIS_URL, COT_CODES, COT_URL  # noqa: E402
from fxengine.data.http import Http  # noqa: E402
from fxengine.data.provider import MACRO_TICKERS  # noqa: E402
from fxengine.instruments import UNIVERSE  # noqa: E402

G = "s20|tr10"
MODEL_IN = ["sig_d", "sig_o", "sig_gap", "exp_z", "dir_d"]
META_PARAM = {"n_trees": 150, "depth": 3, "lr": 0.05, "min_leaf": 500}
OUT_MODEL = os.path.join(ROOT, "fxengine", "data", "ranker_model.json")


# ---------------------------------------------------------------- macro history
def macro_history(cache: str):
    http = Http(cache, timeout=60)
    d1 = {}
    for name, tk in MACRO_TICKERS.items():
        try:
            d1[name] = yahoo.candles(http, tk, "1d", "5y", ttl=3 * 24 * 3600)[0]
        except Exception as e:  # noqa: BLE001
            print(f"  macro {name}: {e}")
    table = mf.daily_table(d1)
    raw = http.get(BIS_URL.format(areas="+".join(BIS_AREAS)), params={"startPeriod": "2022-06-01", "format": "csv"},
                   ttl=3 * 24 * 3600, as_json=False)
    rates = {}
    for r in csv.DictReader(io.StringIO(raw)):
        v, ccy = r.get("OBS_VALUE"), BIS_AREAS.get(r.get("REF_AREA", ""))
        if ccy and v not in (None, "", "NaN"):
            rates.setdefault(ccy, {})[pd.Timestamp(r["TIME_PERIOD"], tz="UTC")] = float(v)
    rates = {c: pd.Series(v).sort_index() for c, v in rates.items()}
    codes = ",".join(f"'{c}'" for c in COT_CODES.values())
    rows = http.get(COT_URL, params={
        "$where": f"cftc_contract_market_code in ({codes}) AND report_date_as_yyyy_mm_dd > '2022-06-01T00:00:00.000'",
        "$select": "report_date_as_yyyy_mm_dd,cftc_contract_market_code,noncomm_positions_long_all,"
                   "noncomm_positions_short_all,open_interest_all",
        "$order": "report_date_as_yyyy_mm_dd ASC", "$limit": "20000"}, ttl=3 * 24 * 3600)
    inv = {v: k for k, v in COT_CODES.items()}
    cot = {}
    for r in rows:
        try:
            net = (float(r["noncomm_positions_long_all"]) - float(r["noncomm_positions_short_all"])) / \
                (float(r["open_interest_all"]) or 1.0) * 100
        except (KeyError, ValueError):
            continue
        avail = pd.Timestamp(r["report_date_as_yyyy_mm_dd"][:10], tz="UTC") + pd.Timedelta(days=4)  # Friday release
        cot.setdefault(inv[r["cftc_contract_market_code"]], {})[avail] = net
    cot = {k: pd.Series(v).sort_index() for k, v in cot.items()}
    print(f"macro: {len(table.columns)} séries diárias · juros {len(rates)} moedas · COT {len(cot)} ativos")
    return table, rates, cot


def macro_frame(keys: pd.DataFrame, table, rates, cot) -> pd.DataFrame:
    """Macro features per (symbol, decision day): only data of completed days."""
    days = keys.assign(day=keys.time.dt.normalize() - pd.Timedelta(days=1))[["symbol", "day"]].drop_duplicates()
    out = []
    for r in days.itertuples(index=False):
        inst = UNIVERSE[r.symbol]
        row = table[table.index <= r.day]
        day = row.iloc[-1] if len(row) else None
        rt = {}
        for c, s in rates.items():
            s0 = s[s.index <= r.day]
            if len(s0):
                past = s[s.index <= r.day - pd.Timedelta(days=182)]
                rt[c] = (float(s0.iloc[-1]), float(s0.iloc[-1] - (past.iloc[-1] if len(past) else s0.iloc[0])))
        ct = {a: float(s[s.index <= r.day].iloc[-1]) for a, s in cot.items() if (s.index <= r.day).any()}
        out.append({"symbol": r.symbol, "day": r.day, **mf.pair_features(inst.base, inst.quote, day, rt, ct)})
    return pd.DataFrame(out)


# ---------------------------------------------------------------- candidates
def candidates(df: pd.DataFrame, macro: pd.DataFrame) -> pd.DataFrame:
    df = df.assign(day=df.time.dt.normalize() - pd.Timedelta(days=1)).merge(macro, on=["symbol", "day"], how="left")
    p_up = 1 / (1 + np.exp(-df.dir_z.to_numpy()))
    parts = []
    for d, tag in ((1, "L"), (-1, "S")):
        c = pd.DataFrame({"symbol": df.symbol, "time": df.time, "block": df.block, "d": d,
                          "sig_d": df.sig_el if d == 1 else df.sig_es, "sig_o": df.sig_es if d == 1 else df.sig_el,
                          "exp_z": df.exp_z, "dir_d": p_up if d == 1 else 1 - p_up, "r": df[f"{tag}|{G}"]})
        c["sig_gap"] = c.sig_d - c.sig_o
        for f in mf.SIGNED:
            c[f] = df[f].fillna(0).to_numpy() * d
        for f in mf.UNSIGNED:
            c[f] = df[f].fillna(0).to_numpy()
        parts.append(c)
    out = pd.concat(parts, ignore_index=True)
    return out[np.isfinite(out.r)].reset_index(drop=True)


def fit_meta(tr: pd.DataFrame, cols: list[str]):
    X = np.nan_to_num(tr[cols].to_numpy(float))
    y = (tr.r.to_numpy() > 0).astype(float)
    step = max(1, len(X) // 400_000)
    m = GBM(**META_PARAM).fit(X[::step], y[::step])
    r = tr.r.to_numpy()
    return m, float(r[r > 0].mean()), float(r[r <= 0].mean())


def score(m, win, loss, df, cols) -> np.ndarray:
    p = m.predict(np.nan_to_num(df[cols].to_numpy(float)))
    return p * win + (1 - p) * loss


def hourly(df: pd.DataFrame, s: np.ndarray) -> dict:
    """Cross-sectional metrics: realised R of the top-1 / top-3 per hour, IC, beats-median."""
    d = df.assign(s=s)
    g = d.groupby("time", sort=False)
    d["rk"] = g.s.rank(ascending=False, method="first")
    top1 = d[d.rk == 1]
    top3 = d[d.rk <= 3]
    med = g.r.transform("median")
    ic = g.apply(lambda x: x.s.rank().corr(x.r.rank()) if len(x) > 5 else np.nan, include_groups=False)
    return {"top1": round(float(top1.r.mean()), 4), "top3": round(float(top3.r.mean()), 4),
            "all": round(float(d.r.mean()), 4), "ic": round(float(ic.mean()), 4),
            "beats_median": round(float((top1.r.to_numpy() > med[top1.index].to_numpy()).mean()), 4),
            "top1_win": round(float((top1.r > 0).mean()), 4), "hours": int(len(top1))}


def main() -> int:
    oos = pd.read_pickle(os.path.join(ROOT, "research", "data", "ensemble_oos.pkl"))
    oos["time"] = pd.to_datetime(oos.time, utc=True)
    table, rates, cot = macro_history(os.path.join(ROOT, ".cache", "research"))
    macro = macro_frame(oos[["symbol", "time"]], table, rates, cot)
    cand = candidates(oos, macro)
    print(f"{len(cand)} candidatos ({cand.time.nunique()} horas)", flush=True)
    m2c, m3c = MODEL_IN, MODEL_IN + mf.FEATURES
    res = {k: [] for k in ("M0", "M1", "M2", "M3")}
    for b in range(2, 8):
        tr, va = cand[cand.block < b], cand[cand.block == b]
        m2 = fit_meta(tr, m2c)
        m3 = fit_meta(tr, m3c)
        rows = {"M0": hourly(va, np.random.default_rng(b).random(len(va))), "M1": hourly(va, va.sig_d.to_numpy()),
                "M2": hourly(va, score(*m2, va, m2c)), "M3": hourly(va, score(*m3, va, m3c))}
        for k, v in rows.items():
            res[k].append({"block": b, **v})
        print(f"  bloco {b}: " + " · ".join(f"{k} top1 {v['top1']:+.3f} ic {v['ic']:+.3f}" for k, v in rows.items()),
              flush=True)
    wf = {k: [r for r in v if r["block"] < 7] for k, v in res.items()}
    test = {k: next(r for r in v if r["block"] == 7) for k, v in res.items()}
    mean = {k: float(np.mean([r["top1"] for r in v])) for k, v in wf.items()}

    def beats(k):
        return sum(a["top1"] > b_["top1"] for a, b_ in zip(wf[k], wf["M1"]))

    adopt = "M1"
    if mean["M3"] > mean["M1"] and beats("M3") >= 4:
        adopt = "M3"
    elif mean["M2"] > mean["M1"] and beats("M2") >= 4:
        adopt = "M2"
    print("\nmédia top-1 (blocos 2..6): " + " · ".join(f"{k} {v:+.4f}" for k, v in mean.items()))
    print(f"M3 > M1 em {beats('M3')}/5 blocos · M2 > M1 em {beats('M2')}/5 → ADOTADO: {adopt}")
    print("TESTE (bloco 7): " + " | ".join(f"{k} {v}" for k, v in test.items()))

    report = {"adopted": adopt, "wf_mean_top1": mean, "walk_forward": wf, "test": test,
              "beats_m1": {"M2": beats("M2"), "M3": beats("M3")}}
    if adopt != "M1":
        cols = m3c if adopt == "M3" else m2c
        m, win, loss = fit_meta(cand[cand.block < 7], cols)
        with open(OUT_MODEL, "w", encoding="utf-8") as fh:
            json.dump({"version": 1, "method": adopt, "features": cols, "gbm": m.export(), "win_r": win, "loss_r": loss,
                       "geometry": G, "trained": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                       "wf_mean_top1": mean, "test": test, "walk_forward": wf}, fh, ensure_ascii=False)
        print(f"ranqueador → {OUT_MODEL}")
    with open(os.path.join(ROOT, "research", "RESULTADOS_RANKING.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1, default=float)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

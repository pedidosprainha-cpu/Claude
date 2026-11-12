"""Live track record: the app scores its own predictions on what really happened next.

Backtests can be wrong in ways nobody sees (data, regime, bugs). This module logs, in the
app's private storage, every explosion reading (one per instrument and hour) and every
recommendation the main analysis marks as executable, then, once the horizon has passed,
measures the outcome on the real H1 candles the next scans download anyway:

  explosão   did the price move >= theta x ADR within the horizon? which side first?
  sinal      R of the plan (stop, trailing after +1R, time exit), spread included in the entry

`summary` compares the live hit rates with the validation numbers (drift detection).
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

FILE = "placar.jsonl"
KEEP_DAYS = 120
_LOCK = threading.Lock()


def _path(cache_dir: str) -> str:
    return os.path.join(cache_dir, FILE)


def _load(cache_dir: str) -> list[dict]:
    p = _path(cache_dir)
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue                       # a torn line never breaks the record
    return out


def _save(cache_dir: str, recs: list[dict]) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    cut = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).isoformat()
    tmp = _path(cache_dir) + f".{threading.get_ident()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in recs:
            if r.get("t", "") >= cut:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, _path(cache_dir))


def _iso(t) -> str:
    return pd.Timestamp(t).tz_convert("UTC").isoformat() if pd.Timestamp(t).tzinfo else \
        pd.Timestamp(t).tz_localize("UTC").isoformat()


# ---------------------------------------------------------------------------- recording
def record_explosions(cache_dir: str, alerts: list, theta: float, horizon: int) -> int:
    """One record per instrument and decision hour (repeated scans in the same hour are ignored)."""
    with _LOCK:
        recs = _load(cache_dir)
        keys = {r["key"] for r in recs if "key" in r}
        n = 0
        for a in alerts:
            if a.blocked:
                continue
            t0 = pd.Timestamp(a.until) - pd.Timedelta(hours=horizon)          # close of the decision bar
            key = f"x|{a.symbol}|{_iso(t0)}"
            if key in keys:
                continue
            recs.append({"key": key, "k": "x", "sym": a.symbol, "t": _iso(t0), "p": round(a.p, 4),
                         "alert": bool(a.alert), "level": a.level,
                         "p_up": None if a.p_up is None else round(a.p_up, 4), "conf": bool(a.dir_confident),
                         "adr": a.adr, "theta": theta, "h": horizon, "status": "pendente"})
            keys.add(key)
            n += 1
        if n:
            _save(cache_dir, recs)
        return n


def record_signal(cache_dir: str, o, now: datetime) -> bool:
    """An executable recommendation of the main analysis (at most one per instrument per hour)."""
    if o is None or not o.executable:
        return False
    p = o.plan
    with _LOCK:
        recs = _load(cache_dir)
        key = f"s|{o.symbol}|{pd.Timestamp(now).floor('h').isoformat()}"
        if any(r.get("key") == key for r in recs):
            return False
        recs.append({"key": key, "k": "s", "sym": o.symbol, "t": _iso(now), "d": o.direction,
                     "entry": p.entry, "sl_dist": p.sl_dist, "trail": p.trail_dist,
                     "kind": p.exit_kind, "tp1": p.tp1, "h": p.horizon_h or 48,
                     "p": None if o.signal is None else round(o.signal.p, 4),
                     "ev": None if o.signal is None else round(o.signal.ev_r, 4), "status": "pendente"})
        _save(cache_dir, recs)
        return True


# ---------------------------------------------------------------------------- scoring
def _score_explosion(r: dict, h1: pd.DataFrame) -> bool:
    t0 = pd.Timestamp(r["t"])
    prev = h1[h1.index < t0]
    win = h1[(h1.index >= t0) & (h1.index < t0 + pd.Timedelta(hours=r["h"]))]
    if prev.empty or len(win) < r["h"] - 1 or h1.index[-1] < t0 + pd.Timedelta(hours=r["h"] - 1):
        return False
    c0, adr = float(prev.c.iloc[-1]), float(r["adr"])
    up, dn = (win.h - c0) / adr, (c0 - win.l) / adr
    th = r["theta"]
    ku = int(np.argmax(up.to_numpy() >= th)) if (up >= th).any() else 99
    kd = int(np.argmax(dn.to_numpy() >= th)) if (dn >= th).any() else 99
    r["exc"] = round(float(max(up.max(), dn.max())), 3)
    r["exploded"] = bool(r["exc"] >= th)
    r["first"] = 0 if ku == kd == 99 else (2 if ku == kd else (1 if ku < kd else -1))
    r["status"] = "conferido"
    return True


def _score_signal(r: dict, h1: pd.DataFrame) -> bool:
    t = pd.Timestamp(r["t"])
    bars = h1[h1.index >= t.floor("h") + pd.Timedelta(hours=1)]       # first full bar after the entry
    if bars.empty or bars.index[-1] < t + pd.Timedelta(hours=r["h"]):
        return False
    bars = bars[bars.index < t + pd.Timedelta(hours=r["h"])]
    d, e, risk, trail = r["d"], r["entry"], r["sl_dist"], r.get("trail") or 0.0
    stop, best, res = e - d * risk, 0.0, None
    for _, b in bars.iterrows():
        if (d > 0 and b.l <= stop) or (d < 0 and b.h >= stop):
            res = d * (stop - e) / risk
            break
        fav = (b.h - e) if d > 0 else (e - b.l)
        best = max(best, fav)
        if r.get("kind") == "trail" and best >= risk:
            stop = max(stop, e + best - trail) if d > 0 else min(stop, e - best + trail)
    if res is None:
        res = d * (float(bars.c.iloc[-1]) - e) / risk
    r["r"] = round(float(res), 3)
    r["status"] = "conferido"
    return True


def evaluate(cache_dir: str, h1_by_symbol: dict) -> int:
    """Score every matured record whose instrument has fresh candles in this scan."""
    with _LOCK:
        recs = _load(cache_dir)
        n = 0
        for r in recs:
            if r.get("status") != "pendente" or r.get("sym") not in h1_by_symbol:
                continue
            h1 = h1_by_symbol[r["sym"]]
            if h1 is None or h1.empty:
                continue
            ok = _score_explosion(r, h1) if r["k"] == "x" else _score_signal(r, h1)
            n += ok
        if n:
            _save(cache_dir, recs)
        return n


def summary(cache_dir: str) -> dict:
    recs = _load(cache_dir)
    x = [r for r in recs if r.get("k") == "x" and r.get("status") == "conferido"]
    s = [r for r in recs if r.get("k") == "s" and r.get("status") == "conferido"]
    al = [r for r in x if r.get("alert")]
    no = [r for r in x if not r.get("alert")]
    ex_al = [r for r in al if r.get("first") in (1, -1) and r.get("p_up") is not None]
    hit_dir = [(r["first"] == (1 if r["p_up"] >= 0.5 else -1)) for r in ex_al]
    hit_conf = [(r["first"] == (1 if r["p_up"] >= 0.5 else -1)) for r in ex_al if r.get("conf")]
    rs = [r["r"] for r in s if r.get("r") is not None]
    first = min((r["t"] for r in recs), default=None)

    def rate(v):
        return round(float(np.mean(v)), 4) if v else None

    return {
        "since": first[:10] if first else None,
        "pending": sum(1 for r in recs if r.get("status") == "pendente"),
        "explosion": {"alerts": len(al), "alert_hit": rate([r["exploded"] for r in al]),
                      "others": len(no), "other_hit": rate([r["exploded"] for r in no]),
                      "p_mean_alert": rate([r["p"] for r in al]),
                      "dir_n": len(hit_dir), "dir_hit": rate(hit_dir),
                      "dir_conf_n": len(hit_conf), "dir_conf_hit": rate(hit_conf)},
        "signal": {"n": len(rs), "mean_r": rate(rs), "win": rate([v > 0 for v in rs])},
    }

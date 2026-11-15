"""Portfolio backtest that reuses the live strategy, risk manager and position
management, bar by bar, with spread costs and worst-case intrabar ordering.

Limitations (stated in every report): no swaps, no news filter, no partial
fills, spreads are fixed assumptions rather than recorded history.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np

from . import strategy as st
from .config import asset_class
from .risk import OpenRisk, RiskManager, new_state
from .timeutil import TF_SECONDS, friday_after, from_ts, in_rollover_window, market_open, session_name

# Round-trip cost assumptions (spread + slippage + commission) in pips / price units.
COST_PIPS = {"major": 1.2, "cross": 2.5}
COST_ABS = {"XAUUSD": 0.35, "XAGUSD": 0.035, "XPTUSD": 3.0, "XPDUSD": 6.0}


def cost_of(symbol: str, mult: float = 1.0) -> float:
    if symbol in COST_ABS:
        return COST_ABS[symbol] * mult
    pip = 0.01 if symbol.endswith("JPY") else 0.0001
    return COST_PIPS[asset_class(symbol)] * pip * mult


def load_csv_dir(path: str, symbols: list[str] | None = None) -> dict:
    """Read <SYMBOL>.csv files with a header containing time,open,high,low,close."""
    data = {}
    for p in sorted(Path(path).glob("*.csv")):
        sym = p.stem.upper()
        if symbols and sym not in symbols:
            continue
        cols = {k: [] for k in ("time", "open", "high", "low", "close")}
        with open(p, newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    vals = [float(row[k]) for k in cols]
                except (KeyError, ValueError, TypeError):
                    continue
                for k, v in zip(cols, vals):
                    cols[k].append(v)
        if len(cols["time"]) > 500:
            order = np.argsort(cols["time"], kind="stable")
            data[sym] = {k: np.asarray(v, dtype=float)[order] for k, v in cols.items()}
            data[sym]["time"] = data[sym]["time"].astype(np.int64)
    return data


def prepare(data: dict, cfg: dict, cost_mult: float = 1.0, utc_offset_sec: int = 0) -> dict:
    """Features, signals and the full confluence score for every symbol and bar."""
    sp, tf = cfg["strategy"], cfg["timeframe"]
    entry_sec = TF_SECONDS[tf]
    feats = {s: st.compute_features(b, sp, tf) for s, b in data.items()}
    sigs = {s: st.compute_signals(f, sp) for s, f in feats.items()}

    timeline = np.unique(np.concatenate([f["time"] + entry_sec for f in feats.values()]))
    on_tl = {}
    for s, f in feats.items():
        idx = np.searchsorted(f["time"] + entry_sec, timeline, side="right") - 1
        on_tl[s] = np.where(idx >= 0, f["mom"][np.clip(idx, 0, None)], np.nan)
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            strength = st.currency_strength(on_tl)
    strength = {k: np.nan_to_num(v) for k, v in strength.items()}

    sess_pts = np.array([st.session_score(session_name(from_ts(t - utc_offset_sec))) for t in timeline])
    for s, f in feats.items():
        g = sigs[s]
        pos = np.searchsorted(timeline, f["time"] + entry_sec)
        cost = cost_of(s, cost_mult)
        frac = np.where(g["dist"] > 0, cost / np.where(g["dist"] > 0, g["dist"], 1.0), 1.0)
        cost_pts = np.where(frac <= 0.04, 5.0, np.where(frac <= 0.07, 4.0, np.where(frac <= 0.10, 2.0, 0.0)))
        is_mr = g["setup"] == 3
        if asset_class(s) not in sp["reversion_classes"]:
            g["dir"] = np.where(is_mr, 0, g["dir"])
        strength_pts = np.where(is_mr, 5.0, st.strength_score(st.strength_diff(strength, s)[pos], g["dir"]))
        g["total"] = np.where(g["dir"] != 0, g["score"] + strength_pts + sess_pts[pos] + cost_pts, 0.0)
        g["cost_frac"] = frac
    return {"feats": feats, "sigs": sigs, "timeline": timeline, "entry_sec": entry_sec}


def run(data: dict, cfg: dict, start_equity: float = 10000.0, cost_mult: float = 1.0,
        utc_offset_sec: int = 0, t_from: int | None = None, t_to: int | None = None,
        stop_on_halt: bool = True) -> dict:
    """stop_on_halt=False keeps simulating past the drawdown kill-switch (research only)."""
    prep = prepare(data, cfg, cost_mult, utc_offset_sec)
    feats, sigs, entry_sec = prep["feats"], prep["sigs"], prep["entry_sec"]
    sp, rp, ss = cfg["strategy"], cfg["risk"], cfg["session"]
    rm = RiskManager(rp, new_state())

    events: dict[int, list] = {}
    for s, f in feats.items():
        for i, t in enumerate((f["time"] + entry_sec).tolist()):
            events.setdefault(t, []).append((s, i))

    balance = start_equity
    open_pos: dict[str, dict] = {}
    trades, curve = [], []
    peak, max_dd = start_equity, 0.0

    def close(sym: str, price: float, t: int, reason: str):
        nonlocal balance
        p = open_pos.pop(sym)
        r = p["dir"] * (price - p["entry"]) / p["risk_dist"]
        pnl = r * p["risk_money"]
        balance += pnl
        rm.on_trade_closed(pnl, t - utc_offset_sec)
        trades.append({"symbol": sym, "dir": p["dir"], "setup": p["setup"], "score": round(p["score"], 1),
                       "t_in": p["t_in"], "t_out": t, "entry": p["entry"], "exit": price,
                       "r": round(r, 3), "pnl": round(pnl, 2), "reason": reason, "bars": p["bars"]})

    for t in sorted(events):
        if (t_from and t < t_from) or (t_to and t > t_to):
            continue
        now = from_ts(t - utc_offset_sec)
        closed_bars = dict(events[t])

        # 1) existing positions: stops/targets inside the bar that just closed
        for sym in list(open_pos):
            i = closed_bars.get(sym)
            if i is None:
                continue
            p, f = open_pos[sym], feats[sym]
            o, h, l, c = f["open"][i], f["high"][i], f["low"][i], f["close"][i]
            sprd, d = p["spread"], p["dir"]
            p["bars"] += 1
            # Longs exit on the bid (chart price); shorts exit on the ask (chart + spread).
            adverse = l if d > 0 else h + sprd
            favour = h if d > 0 else l + sprd
            opn = o if d > 0 else o + sprd
            if d * (opn - p["sl"]) <= 0:                      # gapped through the stop
                close(sym, opn, t, "sl_gap")
            elif d * (adverse - p["sl"]) <= 0:                # stop first: worst case
                close(sym, p["sl"], t, "sl" if d * (p["sl"] - p["entry"]) < 0 else "be_or_trail")
            elif p["tp"] and d * (favour - p["tp"]) >= 0:
                close(sym, p["tp"], t, "tp")
            else:
                px = c if d > 0 else c + sprd
                mp = cfg["management"][st.family_of(p["setup"])]
                new_sl, reason = st.manage(d, p["entry"], p["risk_dist"], p["sl"], px, p["bars"], mp)
                p["sl"] = new_sl
                flat = mp["flat_before_weekend"] and friday_after(now, ss["friday_flat_hour_ny"])
                if reason or flat:
                    close(sym, px, t, reason or "weekend_flat")

        # 2) account state
        floating = 0.0
        for sym, p in open_pos.items():
            f = feats[sym]
            i = min(np.searchsorted(f["time"] + entry_sec, t, side="right") - 1, len(f["close"]) - 1)
            px = f["close"][i] + (p["spread"] if p["dir"] < 0 else 0.0)
            floating += p["dir"] * (px - p["entry"]) / p["risk_dist"] * p["risk_money"]
        equity = balance + floating
        rm.on_equity(equity, t - utc_offset_sec)
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak * 100.0)
        curve.append((t, round(equity, 2)))
        if rm.s["halted"] and not stop_on_halt:
            rm.s["halted"] = None
        if rm.s["halted"]:
            for sym in list(open_pos):
                f = feats[sym]
                i = closed_bars.get(sym, len(f["close"]) - 1)
                close(sym, f["close"][i], t, "halt")
            break

        # 3) new entries
        if not market_open(now) or in_rollover_window(now, ss["rollover_block_before_min"],
                                                      ss["rollover_block_after_min"]):
            continue
        if friday_after(now, ss["friday_last_entry_hour_ny"]):
            continue
        cands = []
        for sym, i in closed_bars.items():
            g = sigs[sym]
            if g["dir"][i] != 0 and g["total"][i] >= sp["min_score"] and g["cost_frac"][i] <= rp["max_spread_frac_of_sl"]:
                cands.append((float(g["total"][i]), sym, i))
        for score, sym, i in sorted(cands, reverse=True):
            g, f = sigs[sym], feats[sym]
            d = int(g["dir"][i])
            setup = st.SETUP_NAMES[int(g["setup"][i])]
            risks = [OpenRisk(s2, p2["dir"], max(0.0, p2["dir"] * (p2["entry"] - p2["sl"]) / p2["risk_dist"])
                              * p2["risk_money"]) for s2, p2 in open_pos.items()]
            ok, _ = rm.check_entry(sym, d, risks, equity, t - utc_offset_sec,
                                   st.cooldown_bars_of(setup, sp) * entry_sec)
            if not ok:
                continue
            sprd = cost_of(sym, cost_mult)
            dist = float(g["dist"][i])
            entry = f["close"][i] + (sprd if d > 0 else 0.0)      # long pays the ask
            sl, tp = st.levels(d, f["close"][i], dist, st.tp_r_of(setup, sp))
            risk_dist = abs(entry - sl)
            open_pos[sym] = {"dir": d, "entry": entry, "sl": sl, "tp": tp, "risk_dist": risk_dist,
                             "risk_money": rm.budget(risks, equity), "spread": sprd, "t_in": t, "bars": 0,
                             "setup": setup, "score": score}
            rm.on_entry(sym, t - utc_offset_sec)

    return {"trades": trades, "curve": curve, "stats": stats(trades, start_equity, balance, max_dd),
            "halted": rm.s["halted"]}


def stats(trades: list, start_equity: float, end_equity: float, max_dd: float) -> dict:
    n = len(trades)
    if n == 0:
        return {"trades": 0}
    rs = np.array([t["r"] for t in trades])
    wins, losses = rs[rs > 0], rs[rs < 0]
    span_days = max(1.0, (trades[-1]["t_out"] - trades[0]["t_in"]) / 86400.0)
    out = {
        "trades": n,
        "win_rate_pct": round(100.0 * len(wins) / n, 1),
        "avg_r": round(float(rs.mean()), 3),
        "profit_factor": round(float(wins.sum() / -losses.sum()), 2) if len(losses) and losses.sum() != 0 else None,
        "total_r": round(float(rs.sum()), 1),
        "return_pct": round((end_equity / start_equity - 1.0) * 100.0, 1),
        "max_drawdown_pct": round(max_dd, 1),
        "trades_per_week": round(n / span_days * 7.0, 1),
        "t_stat": round(float(rs.mean() / (rs.std(ddof=1) / math.sqrt(n))), 2) if n > 2 and rs.std(ddof=1) > 0 else None,
        "avg_bars_held": round(float(np.mean([t["bars"] for t in trades])), 1),
    }
    return out


def breakdown(trades: list, key: str) -> dict:
    groups: dict = {}
    for t in trades:
        groups.setdefault(t[key], []).append(t["r"])
    return {k: {"n": len(v), "avg_r": round(float(np.mean(v)), 3), "total_r": round(float(np.sum(v)), 1),
                "win_pct": round(100.0 * sum(1 for x in v if x > 0) / len(v), 0)}
            for k, v in sorted(groups.items(), key=lambda kv: -float(np.sum(kv[1])))}

"""Performance report from the trade journal, and the gate that guards real money."""
from __future__ import annotations

import math

# Evidence required on a demo account before real money is allowed without an override.
GATE_MIN_TRADES = 40
GATE_MIN_AVG_R = 0.03


def _stats(trades: list[dict]) -> dict:
    rs = [t["r"] for t in trades if t.get("r") is not None]
    pnl = [float(t.get("pnl", 0.0)) for t in trades]
    if not trades:
        return {"trades": 0}
    wins = [x for x in pnl if x > 0]
    losses = [x for x in pnl if x < 0]
    out = {"trades": len(trades), "win_rate_pct": round(100.0 * len(wins) / len(trades), 1),
           "net_pnl": round(sum(pnl), 2),
           "profit_factor": round(sum(wins) / -sum(losses), 2) if losses else None,
           "swap": round(sum(float(t.get("swap", 0.0)) for t in trades), 2),
           "commission": round(sum(float(t.get("commission", 0.0)) for t in trades), 2)}
    if rs:
        mean = sum(rs) / len(rs)
        out["avg_r"] = round(mean, 3)
        out["total_r"] = round(sum(rs), 2)
        if len(rs) > 2:
            sd = math.sqrt(sum((x - mean) ** 2 for x in rs) / (len(rs) - 1))
            out["t_stat"] = round(mean / (sd / math.sqrt(len(rs))), 2) if sd > 0 else None
    return out


def _group(trades: list[dict], key: str) -> dict:
    groups: dict = {}
    for t in trades:
        groups.setdefault(str(t.get(key)), []).append(t)
    return {k: _stats(v) for k, v in sorted(groups.items(), key=lambda kv: -len(kv[1]))}


def build(trades: list[dict], days: int | None = None, now_iso: str | None = None) -> dict:
    if days and now_iso:
        from datetime import datetime, timedelta
        cut = (datetime.strptime(now_iso, "%Y-%m-%dT%H:%M:%SZ") - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        trades = [t for t in trades if str(t.get("closed", "")) >= cut]
    return {"overall": _stats(trades), "by_account": _group(trades, "account"), "by_setup": _group(trades, "setup"),
            "by_symbol": _group(trades, "symbol"), "by_exit": _group(trades, "reason"),
            "last_trades": trades[-10:]}


def live_gate(trades: list[dict]) -> dict:
    """Has the strategy earned real money? Judged only on closed demo trades."""
    demo = [t for t in trades if t.get("account") in ("demo", "contest") and t.get("r") is not None]
    s = _stats(demo)
    n, avg = s.get("trades", 0), s.get("avg_r", 0.0) or 0.0
    passed = n >= GATE_MIN_TRADES and avg >= GATE_MIN_AVG_R
    if n < GATE_MIN_TRADES:
        why = f"only {n} closed demo trades; {GATE_MIN_TRADES} are required"
    elif avg < GATE_MIN_AVG_R:
        why = f"demo expectancy is {avg:+.3f}R per trade; at least {GATE_MIN_AVG_R:+.2f}R is required"
    else:
        why = f"{n} demo trades with expectancy {avg:+.3f}R per trade"
    return {"passed": passed, "reason": why, "demo_stats": s,
            "requirements": {"min_trades": GATE_MIN_TRADES, "min_avg_r": GATE_MIN_AVG_R}}

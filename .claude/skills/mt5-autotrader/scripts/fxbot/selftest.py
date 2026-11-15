"""End-to-end self-test: the real engine trading against the simulated broker.

Proves on any machine (no MT5 needed) that the pipeline works and that the
safety invariants hold: every order has a stop, risk stays inside the budget,
position limits are respected, the journal matches the broker's deals.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from .config import deep_merge, load_config
from .engine import Engine
from .simmt5 import SimMT5, synthetic_bars
from .store import Store
from .timeutil import from_ts

SIM_SYMBOLS = {"EURGBP": (0.85, 11), "AUDNZD": (1.08, 12), "EURCHF": (0.95, 13), "AUDCAD": (0.90, 14),
               "GBPUSD": (1.27, 15), "USDCAD": (1.36, 16), "NZDUSD": (0.61, 17), "XAUUSD": (2400.0, 18)}

# Looser thresholds than production so a short simulation still produces trades to check.
SELFTEST_OVERRIDES = {
    "news": {"enabled": False},
    "history_bars": 1500,
    "strategy": {"mr_z": 0.6, "mr_cooldown_bars": 6},
    "management": {"reversion": {"max_hold_bars": 36}},
    "risk": {"max_trades_per_day": 20},
}


def build_sim(n_bars: int = 2400, suffix: str = ".x", **kw) -> SimMT5:
    data = {s: synthetic_bars(n_bars, seed=seed, price=px) for s, (px, seed) in SIM_SYMBOLS.items()}
    return SimMT5(data, suffix=suffix, **kw)


def run_selftest(hours: int = 400, overrides: dict | None = None, home: str | None = None, sim: SimMT5 | None = None) -> dict:
    sim = sim or build_sim()
    tmp = None
    if home is None:
        tmp = tempfile.TemporaryDirectory()
        home = tmp.name
    store = Store(Path(home))
    cfg = load_config(overrides=deep_merge(SELFTEST_OVERRIDES, overrides or {}))
    eng = Engine(sim, cfg, store, clock=lambda: from_ts(sim.now), log=store.logger())
    any_bars = next(iter(sim.data.values()))
    start = max(1300, len(any_bars["time"]) - hours - 1)
    problems, max_open, cycles = [], 0, 0
    rp = cfg["risk"]
    for i in range(start, len(any_bars["time"])):
        sim.set_time(int(any_bars["time"][i]) + 5)          # 5 seconds into each new bar
        try:
            summary = eng.cycle()
        except Exception as exc:                            # a crash is a failed self-test
            problems.append(f"cycle crashed at step {i}: {type(exc).__name__}: {exc}")
            break
        cycles += 1
        equity = summary["account"]["equity"]
        open_now = sim.positions_get()
        max_open = max(max_open, len(open_now))
        if len(open_now) > rp["max_open_positions"]:
            problems.append(f"{len(open_now)} positions open, limit is {rp['max_open_positions']}")
        for p in open_now:
            if not p.sl:
                problems.append(f"position {p.ticket} has no stop-loss")
        for rec in summary["opened"]:
            if rec["risk_pct"] > rp["risk_per_trade_pct"] * rp["min_lot_risk_tolerance"] + 1e-6:
                problems.append(f"{rec['symbol']} risked {rec['risk_pct']}% (budget {rp['risk_per_trade_pct']}%)")
        if equity <= 0:
            problems.append("equity went to zero")
            break
    eng.close_positions(reason="selftest end")
    eng.cycle()
    trades = store.read("trades")
    decisions = store.read("decisions")
    closed_deals = [d for d in sim.deals if d.entry == sim.DEAL_ENTRY_OUT]
    if len(trades) != len(closed_deals):
        problems.append(f"journal has {len(trades)} trades but the broker closed {len(closed_deals)} positions")
    journal_pnl, broker_pnl = sum(t["pnl"] for t in trades), sum(d.profit for d in closed_deals)
    if abs(journal_pnl - broker_pnl) > 0.05 * max(1, len(trades)):
        problems.append(f"journal P&L {journal_pnl:.2f} differs from broker P&L {broker_pnl:.2f}")
    if not trades:
        problems.append("the simulation produced no trades, so nothing was verified")
    result = {"passed": not problems, "problems": problems[:20], "cycles": cycles, "trades": len(trades),
              "decisions_journaled": len(decisions), "max_positions_open": max_open,
              "symbols_mapped": eng.broker.map, "end_balance": round(sim.balance, 2),
              "note": "simulated random-walk prices: this checks the machinery, not profitability"}
    if tmp:
        import logging
        for h in list(logging.getLogger("fxbot").handlers):
            h.close()
            logging.getLogger("fxbot").removeHandler(h)
        tmp.cleanup()
    return result

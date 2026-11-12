from datetime import datetime, timezone

import numpy as np
import pandas as pd

from fxintel import instruments as I
from fxintel.backtest.engine import simulate_portfolio
from fxintel.backtest.walkforward import walk_forward
from fxintel.config import load_settings
from fxintel.data.models import Quote
from fxintel.quant.labeling import simulate
from fxintel.quant.model import ProbabilityModel, evaluate
from fxintel.quant.stats import max_drawdown, probabilistic_sharpe, wilson
from fxintel.risk.manager import RiskManager
from fxintel.risk.sizing import conversion_rate, position_size

NOW = datetime(2026, 11, 12, 14, tzinfo=timezone.utc)


def arr(*rows):
    a = np.array(rows, dtype=float)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def test_trade_stop_first_when_ambiguous():
    # candle de entrada (1) toca stop e alvo: convenção conservadora = stop
    o, h, l, c = arr((1.0, 1.0, 1.0, 1.0), (1.0, 1.03, 0.97, 1.0), (1.0, 1.0, 1.0, 1.0))
    tr = simulate(o, h, l, c, np.zeros(3), 0, 1, sl=0.98, tp1=1.02, tp2=1.04, horizon=5, slip=0.0)
    assert tr.outcome == "sl" and tr.r < 0 and tr.hit_tp1 == 0


def test_trade_partial_then_breakeven():
    o, h, l, c = arr((1.0, 1.0, 1.0, 1.0), (1.0, 1.021, 0.995, 1.02), (1.02, 1.02, 0.999, 1.0), (1.0, 1.0, 1.0, 1.0))
    tr = simulate(o, h, l, c, np.zeros(4), 0, 1, sl=0.99, tp1=1.02, tp2=1.04, horizon=5, slip=0.0)
    assert tr.outcome == "tp1_be" and tr.hit_tp1 == 1
    assert abs(tr.r - 0.5 * 2.0) < 1e-9  # 50% em +2R, restante no zero a zero


def test_trade_costs_reduce_r():
    o, h, l, c = arr((1.0, 1.0, 1.0, 1.0), (1.0, 1.05, 1.0, 1.05), (1.05, 1.05, 1.05, 1.05))
    gross = simulate(o, h, l, c, np.zeros(3), 0, 1, 0.99, 1.02, 1.04, 5, 0.0)
    net = simulate(o, h, l, c, np.full(3, 0.001), 0, 1, 0.99, 1.02, 1.04, 5, 0.0005)
    assert net.r < gross.r and net.cost_r > 0


def test_short_trade_symmetry():
    o, h, l, c = arr((1.0, 1.0, 1.0, 1.0), (1.0, 1.0, 0.95, 0.95), (0.95, 0.95, 0.95, 0.95))
    tr = simulate(o, h, l, c, np.zeros(3), 0, -1, sl=1.01, tp1=0.98, tp2=0.96, horizon=5, slip=0.0)
    assert tr.outcome == "tp1_tp2" and tr.r > 0


def quotes():
    t = NOW
    return {"EURUSD": Quote("EURUSD", 1.1000, 1.1001, t, "t", "estimated"),
            "USDJPY": Quote("USDJPY", 150.00, 150.01, t, "t", "estimated"),
            "XAUUSD": Quote("XAUUSD", 3000.0, 3000.3, t, "t", "estimated")}


def test_conversion_and_sizing():
    q = quotes()
    assert abs(conversion_rate("JPY", "USD", q) - 1 / 150.005) < 1e-9
    cfg = load_settings()["risk"]
    s = position_size(I.get("EURUSD"), 1.1000, 1.0950, 10_000, 0.5, "USD", q, cfg)
    assert s["ok"] and abs(s["risk_amount"] - 50) < 1.0  # 50 pips, US$50 -> 0.10 lote
    assert s["lots"] == 0.1
    s2 = position_size(I.get("XAUUSD"), 3000.0, 2990.0, 10_000, 0.5, "USD", q, cfg)
    assert s2["ok"] and s2["risk_amount"] <= 50.0 + 1e-9  # arredonda para baixo, nunca acima do risco
    s3 = position_size(I.get("XAUUSD"), 3000.0, 2700.0, 1_000, 0.5, "USD", q, cfg)
    assert not s3["ok"]  # lote mínimo excederia o risco permitido


class FakeBroker:
    def __init__(self, positions=None, pnl=0.0):
        self.positions = positions or []
        self.pnl = pnl

    def open_positions(self):
        return self.positions

    def realized_since(self, since):
        return self.pnl


def test_risk_manager_limits():
    st = load_settings()
    q = quotes()
    rm = RiskManager(st, FakeBroker())
    ok = rm.evaluate("EURUSD", 1, 1.1001, 1.0950, q, now=NOW)
    assert ok["approved"], ok["reasons"]
    rm2 = RiskManager(st, FakeBroker(pnl=-0.03 * st["account"]["equity"]))
    assert not rm2.evaluate("EURUSD", 1, 1.1001, 1.0950, q, now=NOW)["approved"]
    pos = [{"symbol": "EURUSD", "direction": 1, "risk_amount": 50}]
    rm3 = RiskManager(st, FakeBroker(positions=pos))
    r3 = rm3.evaluate("EURUSD", 1, 1.1001, 1.0950, q, now=NOW)
    assert not r3["approved"] and any("Já existe" in x for x in r3["reasons"])


def test_wilson_and_stats():
    lo, hi = wilson(30, 100)
    assert lo < 0.3 < hi
    dd, _ = max_drawdown(np.array([100, 110, 99, 120]))
    assert abs(dd - (99 / 110 - 1)) < 1e-12
    rng = np.random.default_rng(0)
    assert probabilistic_sharpe(rng.normal(0.5, 1, 500)) > 0.99
    assert probabilistic_sharpe(rng.normal(-0.5, 1, 500)) < 0.01


def synthetic_dataset(n=3000, informative=True, seed=0):
    rng = np.random.default_rng(seed)
    t = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
    x = rng.normal(size=n)
    p = 1 / (1 + np.exp(-(x * (1.2 if informative else 0.0) - 0.6)))
    y = (rng.random(n) < p).astype(int)
    r = np.where(y == 1, 1.5, -1.0)
    return pd.DataFrame({"decision_time": t, "exit_time": t + pd.Timedelta(hours=20), "resolved": True,
                         "y": y, "r": r, "rr1": 1.5, "cost_r": 0.05, "symbol": "EURUSD", "dir": 1,
                         "x_a": x, "x_b": rng.normal(size=n)})


def test_model_skill_detects_signal_and_noise():
    for informative, expect_skill in ((True, True), (False, False)):
        df = synthetic_dataset(informative=informative)
        tr, te = df.iloc[:2000], df.iloc[2000:]
        m = ProbabilityModel().fit(tr[["x_a", "x_b"]], tr["y"].to_numpy(), tr["r"].to_numpy(), tr["rr1"].to_numpy())
        ev = evaluate(te["y"].to_numpy(), m.predict(te[["x_a", "x_b"]]), m.meta["base_rate"])
        assert (ev["bss"] > 0.02) == expect_skill, ev


def test_walk_forward_purging():
    df = synthetic_dataset(2500)
    st = load_settings()
    oos = walk_forward(df, st, min_train=300, embargo_h=24)
    assert not oos.empty
    for fold, g in oos.groupby("fold"):
        start = g["decision_time"].min().normalize().replace(day=1)
        # nenhum rótulo usado no treino pode ter sido resolvido depois do início do teste - embargo
        assert (g["n_train"] <= (df["exit_time"] < start - pd.Timedelta(hours=24)).sum()).all()


def test_portfolio_respects_limits():
    df = synthetic_dataset(400)
    df["symbol"] = ["EURUSD", "GBPUSD", "AUDUSD", "XAUUSD"] * 100
    res = simulate_portfolio(df, load_settings())
    assert res["trade_metrics"]["n"] > 0
    assert sum(res["rejected"].values()) > 0  # trades simultâneos acima dos limites são recusados

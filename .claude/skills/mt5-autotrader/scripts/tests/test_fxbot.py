"""Test-suite for the MT5 autotrader. Runs anywhere: `python -m unittest discover -s tests`."""
import json
import logging
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fxbot import backtest as bt, indicators as ind, report as rep, strategy as st  # noqa: E402
from fxbot.config import HARD_CAPS, deep_merge, load_config  # noqa: E402
from fxbot.engine import Engine  # noqa: E402
from fxbot.news import NewsCalendar  # noqa: E402
from fxbot.risk import OpenRisk, RiskManager, new_state, size_lots  # noqa: E402
from fxbot.selftest import SELFTEST_OVERRIDES, build_sim, run_selftest  # noqa: E402
from fxbot.simmt5 import SimMT5, synthetic_bars  # noqa: E402
from fxbot.store import Store  # noqa: E402
from fxbot.timeutil import (UTC, friday_after, from_ts, in_rollover_window, market_open, ny_offset_hours,  # noqa: E402
                            trading_day)


logging.getLogger("fxbot-test").addHandler(logging.NullHandler())
logging.getLogger("fxbot-test").propagate = False


def dt(*a):
    return datetime(*a, tzinfo=UTC)


def make_engine(sim, overrides=None, home=None):
    home = home or tempfile.mkdtemp()
    store = Store(Path(home))
    cfg = load_config(overrides=deep_merge(SELFTEST_OVERRIDES, overrides or {}))
    return Engine(sim, cfg, store, clock=lambda: from_ts(sim.now), log=logging.getLogger("fxbot-test")), store


def step(sim, eng, bars, i):
    sim.set_time(int(bars["time"][i]) + 5)
    return eng.cycle()


class TimeTests(unittest.TestCase):
    def test_new_york_dst(self):
        self.assertEqual(ny_offset_hours(dt(2026, 1, 15, 12)), -5)
        self.assertEqual(ny_offset_hours(dt(2026, 7, 15, 12)), -4)
        self.assertEqual(ny_offset_hours(dt(2026, 3, 8, 6, 59)), -5)   # one minute before DST starts
        self.assertEqual(ny_offset_hours(dt(2026, 3, 8, 7, 0)), -4)
        self.assertEqual(ny_offset_hours(dt(2026, 11, 1, 6, 0)), -5)

    def test_market_week(self):
        self.assertFalse(market_open(dt(2026, 11, 14, 12)))            # Saturday
        self.assertFalse(market_open(dt(2026, 11, 15, 21, 59)))        # Sunday before 17:00 NY (EST)
        self.assertTrue(market_open(dt(2026, 11, 15, 22, 1)))
        self.assertTrue(market_open(dt(2026, 11, 13, 21, 59)))         # Friday before the close
        self.assertFalse(market_open(dt(2026, 11, 13, 22, 1)))

    def test_rollover_and_trading_day(self):
        self.assertTrue(in_rollover_window(dt(2026, 11, 11, 21, 45), 30, 75))
        self.assertTrue(in_rollover_window(dt(2026, 11, 11, 23, 10), 30, 75))
        self.assertFalse(in_rollover_window(dt(2026, 11, 11, 23, 20), 30, 75))
        self.assertFalse(in_rollover_window(dt(2026, 11, 11, 15, 0), 30, 75))
        self.assertEqual(trading_day(dt(2026, 11, 11, 21, 59)), "2026-11-11")
        self.assertEqual(trading_day(dt(2026, 11, 11, 22, 1)), "2026-11-12")
        self.assertTrue(friday_after(dt(2026, 11, 13, 17, 30), 12.0))
        self.assertFalse(friday_after(dt(2026, 11, 12, 17, 30), 12.0))


class IndicatorTests(unittest.TestCase):
    def test_ema_and_rolling(self):
        x = np.arange(1, 11, dtype=float)
        e = ind.ema(x, 3)
        self.assertAlmostEqual(e[1], 1.5)
        self.assertAlmostEqual(e[2], 2.25)
        np.testing.assert_allclose(ind.rolling_max(x, 3)[-3:], [8, 9, 10])
        np.testing.assert_allclose(ind.rolling_min(x, 3)[:4], [1, 1, 1, 2])
        np.testing.assert_allclose(ind.shift(x, 2)[:4], [1, 1, 1, 2])

    def test_rsi_and_atr_bounds(self):
        b = synthetic_bars(500, seed=3)
        r = ind.rsi(b["close"])
        self.assertTrue(np.all((r >= 0) & (r <= 100)))
        self.assertTrue(np.all(ind.atr(b["high"], b["low"], b["close"]) > 0))
        self.assertAlmostEqual(ind.rsi(np.arange(1, 60, dtype=float))[-1], 100.0)

    def test_no_lookahead(self):
        """Features/signals at bar i must not change when later bars are appended."""
        sp = load_config(overrides={"strategy": {"enable_pullback": True, "enable_breakout": True}})["strategy"]
        b = synthetic_bars(2600, seed=5)
        full = st.compute_features(b, sp)
        gfull = st.compute_signals(full, sp)
        cut = 2100
        part_b = {k: v[:cut] for k, v in b.items()}
        part = st.compute_features(part_b, sp)
        gpart = st.compute_signals(part, sp)
        for key in ("ema_fast", "atr", "rsi", "t_mid", "t_adx", "b_z", "b_atr", "mom"):
            np.testing.assert_allclose(full[key][:cut], part[key], rtol=1e-9, atol=1e-12, err_msg=key)
        for key in ("dir", "setup", "score", "dist"):
            np.testing.assert_allclose(gfull[key][:cut], gpart[key], rtol=1e-9, atol=1e-12, err_msg=key)


class RiskTests(unittest.TestCase):
    def setUp(self):
        self.rp = load_config(overrides={})["risk"]
        self.rm = RiskManager(self.rp, new_state())
        self.ts = dt(2026, 11, 11, 12).timestamp()
        self.rm.on_equity(10000, self.ts)

    def test_sizing(self):
        self.assertEqual(size_lots(50, 1000, 0.01, 0.01, 100)[0], 0.05)
        self.assertEqual(size_lots(59.9, 1000, 0.01, 0.01, 100)[0], 0.05)      # rounds down, never up
        self.assertEqual(size_lots(8, 1000, 0.01, 0.01, 100, 1.5)[0], 0.01)    # min lot within tolerance
        lots, why = size_lots(5, 1000, 0.01, 0.01, 100, 1.5)                   # min lot would double the risk
        self.assertEqual(lots, 0.0)
        self.assertIn("minimum lot", why)
        self.assertEqual(size_lots(1e9, 1000, 0.01, 0.01, 50)[0], 50)

    def test_budget_and_limits(self):
        self.assertAlmostEqual(self.rm.budget([], 10000), 50.0)
        risks = [OpenRisk("EURGBP", 1, 50), OpenRisk("AUDNZD", 1, 50), OpenRisk("EURCHF", -1, 50)]
        self.assertAlmostEqual(self.rm.budget(risks, 10000), 50.0)
        risks.append(OpenRisk("AUDCAD", 1, 40))
        self.assertEqual(self.rm.budget(risks, 10000), 0.0)                    # 2% total-risk ceiling
        ok, why = self.rm.check_entry("NZDCAD", 1, risks, 10000, self.ts)
        self.assertFalse(ok)

    def test_currency_exposure(self):
        risks = [OpenRisk("EURGBP", 1, 10), OpenRisk("EURCHF", 1, 10)]          # twice long EUR
        ok, why = self.rm.check_entry("EURAUD", 1, risks, 10000, self.ts)
        self.assertFalse(ok)
        self.assertIn("EUR", why)
        self.assertTrue(self.rm.check_entry("EURAUD", -1, risks, 10000, self.ts)[0])   # short EUR offsets
        self.assertFalse(self.rm.check_entry("EURGBP", -1, risks, 10000, self.ts)[0])  # one position per symbol

    def test_daily_loss_lock_is_sticky(self):
        self.rm.on_equity(9790, self.ts + 60)                                   # -2.1% on the day
        self.assertFalse(self.rm.can_trade(self.ts + 60)[0])
        self.rm.on_equity(10100, self.ts + 120)                                 # recovering does not unlock
        self.assertFalse(self.rm.can_trade(self.ts + 120)[0])
        self.rm.on_equity(10100, self.ts + 86400)                               # next trading day does
        self.assertTrue(self.rm.can_trade(self.ts + 86400)[0])

    def test_drawdown_halt_needs_manual_reset(self):
        self.rm.on_equity(9150, self.ts + 86400 * 3)                            # -8.5% from the peak
        self.assertIsNotNone(self.rm.s["halted"])
        self.rm.on_equity(10500, self.ts + 86400 * 9)
        self.assertFalse(self.rm.can_trade(self.ts + 86400 * 9)[0])

    def test_loss_streak_cooldown_and_veto(self):
        for _ in range(self.rp["max_consecutive_losses"]):
            self.rm.on_trade_closed(-10, self.ts)
        self.assertFalse(self.rm.can_trade(self.ts + 3600)[0])
        self.assertTrue(self.rm.can_trade(self.ts + self.rp["cooldown_hours"] * 3600 + 1)[0])
        self.rm.s["vetoes"]["EURGBP"] = {"until": self.ts + 9e5, "reason": "ECB"}
        self.assertFalse(self.rm.check_entry("EURGBP", 1, [], 10000, self.ts + 9e4)[0])

    def test_hard_caps(self):
        cfg = load_config(overrides={"risk": {"risk_per_trade_pct": 25, "max_drawdown_pct": 90, "daily_loss_limit_pct": -3}})
        self.assertEqual(cfg["risk"]["risk_per_trade_pct"], HARD_CAPS["risk_per_trade_pct"])
        self.assertEqual(cfg["risk"]["max_drawdown_pct"], HARD_CAPS["max_drawdown_pct"])
        self.assertGreater(cfg["risk"]["daily_loss_limit_pct"], 0)
        self.assertEqual(len(cfg["_cap_notes"]), 3)


class StrategyTests(unittest.TestCase):
    def test_manage_only_tightens(self):
        mp = {"breakeven_at_r": 1.0, "breakeven_lock_r": 0.1, "trail_start_r": 1.5, "trail_dist_r": 1.0, "max_hold_bars": 10}
        self.assertEqual(st.manage(1, 1.1000, 0.0050, 1.0950, 1.1020, 1, mp), (1.0950, None))
        sl, _ = st.manage(1, 1.1000, 0.0050, 1.0950, 1.1051, 1, mp)
        self.assertAlmostEqual(sl, 1.1005)
        sl, _ = st.manage(1, 1.1000, 0.0050, 1.1005, 1.1100, 1, mp)
        self.assertAlmostEqual(sl, 1.1050)
        self.assertAlmostEqual(st.manage(1, 1.1000, 0.0050, 1.1050, 1.1060, 1, mp)[0], 1.1050)   # never loosens
        sl, _ = st.manage(-1, 1.1000, 0.0050, 1.1050, 1.0940, 1, mp)
        self.assertAlmostEqual(sl, 1.0995)
        self.assertEqual(st.manage(1, 1.1, 0.005, 1.095, 1.1, 10, mp)[1], "time_stop")

    def test_levels_and_strength(self):
        self.assertEqual(st.levels(1, 1.10, 0.01, 2.0), (1.09, 1.12))
        sl, tp = st.levels(-1, 1.10, 0.01, 0.0)
        self.assertAlmostEqual(sl, 1.11)
        self.assertEqual(tp, 0.0)
        s = st.currency_strength({"EURUSD": 1.0, "GBPUSD": -1.0, "EURGBP": 2.0})
        self.assertGreater(s["EUR"], s["USD"])
        self.assertGreater(s["USD"], s["GBP"])

    def test_reversion_fades_a_stretched_move(self):
        sp = load_config(overrides={})["strategy"]
        b = synthetic_bars(2400, seed=9, vol=0.0008)
        up = {k: v.copy() for k, v in b.items()}
        ramp = np.concatenate([np.zeros(2400 - 240), np.linspace(0, 0.06, 240)])   # +6% over the last 10 days
        for k in ("open", "high", "low", "close"):
            up[k] = up[k] * np.exp(ramp)
        g = st.compute_signals(st.compute_features(up, sp), sp)
        self.assertEqual(g["dir"][-1], -1)
        self.assertEqual(st.SETUP_NAMES[int(g["setup"][-1])], "MR")
        self.assertGreater(g["dist"][-1], 0)


class BrokerTests(unittest.TestCase):
    def test_symbol_resolution(self):
        data = {s: synthetic_bars(700, seed=i) for i, s in enumerate(["EURUSD", "EURGBP", "GOLD"])}
        sim = SimMT5(data, suffix="m")
        sim.data["EURUSD.pro"] = sim.data["EURUSDm"]                 # second family: the common suffix wins
        sim.data["EURUSDX24"] = sim.data["EURUSDm"]                  # a different instrument, must be ignored
        eng, _ = make_engine(sim, {"symbols": ["EURUSD", "EURGBP", "XAUUSD", "XPTUSD"]})
        eng.connect()
        self.assertEqual(eng.broker.map, {"EURUSD": "EURUSDm", "EURGBP": "EURGBPm", "XAUUSD": "GOLDm"})
        self.assertEqual(eng.broker.unresolved, ["XPTUSD"])
        sim.data["XAUUSDm"] = sim.data["GOLDm"]                      # both listed: the standard name wins
        eng.broker.resolve_symbols(["XAUUSD"])
        self.assertEqual(eng.broker.map["XAUUSD"], "XAUUSDm")

    def test_closed_bars_exclude_the_forming_bar(self):
        sim = build_sim()
        eng, _ = make_engine(sim)
        eng.connect()
        b = sim.data["EURGBP.x"]
        sim.set_time(int(b["time"][1500]) + 5)
        bars = eng.broker.bars("EURGBP", "H1", 100)
        self.assertEqual(int(bars["time"][-1]), int(b["time"][1499]))
        self.assertEqual(len(bars["time"]), 100)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.sim = build_sim()
        self.bars = next(iter(self.sim.data.values()))

    def run_until_trade(self, eng, start=1400, limit=400):
        for i in range(start, start + limit):
            s = step(self.sim, eng, self.bars, i)
            if s["opened"]:
                return i, s
        self.fail("no trade opened")

    def test_demo_account_trades_with_stop_and_budget(self):
        eng, store = make_engine(self.sim)
        _, s = self.run_until_trade(eng)
        rec = s["opened"][0]
        pos = self.sim.positions_get()[0]
        self.assertEqual(s["mode"], "trade")
        self.assertTrue(pos.sl > 0)
        self.assertEqual(pos.magic, eng.cfg["magic"])
        self.assertLessEqual(rec["risk_pct"], eng.cfg["risk"]["risk_per_trade_pct"] * 1.5)
        self.assertTrue(pos.comment.startswith("fxb:MR:"))
        self.assertEqual(store.read_heartbeat()["status"], "ok")

    def test_real_account_only_observes_until_authorised(self):
        sim = build_sim(real=True)
        eng, store = make_engine(sim)
        for i in range(1400, 1500):
            s = step(sim, eng, self.bars, i)
        self.assertEqual(s["mode"], "observe")
        self.assertEqual(len(sim.positions_get()), 0)
        self.assertEqual(len(sim.deals), 0)
        self.assertTrue(any(d["status"] == "observed" for d in store.read("decisions")))

    def test_real_account_trades_only_with_matching_login(self):
        sim = build_sim(real=True, login=777)
        eng, _ = make_engine(sim, {"live": {"enabled": True, "login": 999}})
        self.assertEqual(step(sim, eng, self.bars, 1400)["mode"], "observe")
        sim2 = build_sim(real=True, login=777)
        eng2, _ = make_engine(sim2, {"live": {"enabled": True, "login": 777}})
        self.assertEqual(step(sim2, eng2, self.bars, 1400)["mode"], "trade")

    def test_algo_trading_off_means_observe(self):
        sim = build_sim(algo_enabled=False)
        eng, _ = make_engine(sim)
        s = step(sim, eng, self.bars, 1400)
        self.assertEqual(s["mode"], "observe")
        self.assertIn("Algo Trading", s["mode_reason"])

    def test_rejected_order_is_journaled_not_fatal(self):
        eng, store = make_engine(self.sim)
        orig = self.sim.order_send
        self.sim.order_send = lambda req: self.sim._result(10019, req, "No money")
        for i in range(1400, 1460):
            step(self.sim, eng, self.bars, i)
        self.sim.order_send = orig
        rej = [d for d in store.read("decisions") if d["status"] == "rejected"]
        self.assertTrue(rej)
        self.assertIn("not enough money", rej[0]["detail"])
        self.assertEqual(len(eng.state["positions"]), 0)

    def test_closed_trades_reach_journal_and_time_stop(self):
        eng, store = make_engine(self.sim)
        i, _ = self.run_until_trade(eng)
        for j in range(i + 1, i + 120):
            step(self.sim, eng, self.bars, j)
        trades = store.read("trades")
        self.assertTrue(trades)
        self.assertTrue(all(t["account"] == "demo" and t["r"] is not None for t in trades))
        self.assertTrue({t["reason"] for t in trades} <= {"time_stop", "sl", "tp"})
        self.assertLessEqual(max(t["bars"] for t in trades), 36)
        closed = sum(1 for d in self.sim.deals if d.entry == 1)
        self.assertEqual(len(trades) + len(eng.state["pending_closed"]), closed)

    def test_pause_veto_and_kill_switch(self):
        eng, store = make_engine(self.sim)
        store.push_command({"op": "pause"})
        for i in range(1400, 1440):
            s = step(self.sim, eng, self.bars, i)
        self.assertTrue(s["risk"]["paused"])
        self.assertEqual(len(self.sim.positions_get()), 0)
        store.push_command({"op": "resume"})
        i, _ = self.run_until_trade(eng, 1440)
        self.assertGreater(len(self.sim.positions_get()), 0)
        closed = eng.close_positions(reason="kill switch")
        self.assertTrue(all(c["ok"] for c in closed))
        self.assertEqual(len(self.sim.positions_get()), 0)

    def test_bot_never_touches_foreign_positions(self):
        eng, _ = make_engine(self.sim)
        eng.connect()
        self.sim.set_time(int(self.bars["time"][1400]) + 5)
        for sym in list(self.sim.data):
            t = self.sim.symbol_info_tick(sym)
            self.sim.order_send({"action": 1, "symbol": sym, "volume": 0.1, "type": 0, "sl": 0.0, "tp": 0.0, "magic": 42})
        for i in range(1401, 1480):
            step(self.sim, eng, self.bars, i)
        mine = [p for p in self.sim.positions_get() if p.magic == eng.cfg["magic"]]
        self.assertEqual(mine, [])                                   # manual trade present -> bot stays out
        eng.close_positions()
        self.assertEqual(len(self.sim.positions_get()), len(self.sim.data))   # and never closes them

    def test_state_survives_restart_and_adopts_orphans(self):
        home = tempfile.mkdtemp()
        eng, store = make_engine(self.sim, home=home)
        i, _ = self.run_until_trade(eng)
        tickets = set(eng.state["positions"])
        eng2, _ = make_engine(self.sim, home=home)                   # restart with saved state
        step(self.sim, eng2, self.bars, i + 1)
        self.assertTrue(tickets <= set(eng2.state["positions"]) | set(eng2.state["pending_closed"]))
        eng3, _ = make_engine(self.sim)                              # state lost: positions are adopted
        step(self.sim, eng3, self.bars, i + 2)
        live = {str(p.ticket) for p in self.sim.positions_get()}
        self.assertEqual(set(eng3.state["positions"]), live)
        self.assertTrue(all(m.get("adopted") for m in eng3.state["positions"].values()))

    def test_broker_refusing_stops_on_entry_still_gets_a_stop(self):
        self.sim.refuse_stops_on_open = True
        eng, _ = make_engine(self.sim)
        self.run_until_trade(eng)
        self.assertTrue(all(p.sl > 0 for p in self.sim.positions_get()))        # attached in a second step

    def test_position_is_closed_if_no_stop_can_be_set(self):
        self.sim.refuse_stops_on_open = True
        self.sim.refuse_stop_changes = True
        eng, store = make_engine(self.sim)
        for i in range(1400, 1460):
            step(self.sim, eng, self.bars, i)
        self.assertEqual(len(self.sim.positions_get()), 0)                      # never left unprotected
        self.assertEqual(eng.state["positions"], {})
        self.assertTrue(any("closed immediately" in d["detail"] for d in store.read("decisions")))

    def test_terminal_glitch_does_not_forget_positions(self):
        eng, _ = make_engine(self.sim)
        i, _ = self.run_until_trade(eng)
        before = dict(eng.state["positions"])
        self.sim.fail_positions = True
        with self.assertRaises(Exception):
            step(self.sim, eng, self.bars, i + 1)
        self.sim.fail_positions = False
        step(self.sim, eng, self.bars, i + 2)
        self.assertEqual(set(eng.state["positions"]), set(before))
        self.assertFalse(any(m.get("adopted") for m in eng.state["positions"].values()))

    def test_connection_loss_recovers(self):
        eng, _ = make_engine(self.sim)
        step(self.sim, eng, self.bars, 1400)
        self.sim.connected = False
        with self.assertRaises(Exception):
            step(self.sim, eng, self.bars, 1401)
        self.sim.connected = True
        self.assertEqual(step(self.sim, eng, self.bars, 1402)["status"], "ok")

    def test_selftest_passes(self):
        res = run_selftest(hours=150)
        self.assertTrue(res["passed"], res["problems"])


class BacktestTests(unittest.TestCase):
    def test_engine_and_backtest_agree(self):
        """The live engine on the simulator must take the same trades as the backtester."""
        sim = build_sim(suffix="")
        sim.spreads = {s: bt.cost_of(s) for s in sim.data}
        eng, store = make_engine(sim)
        bars = next(iter(sim.data.values()))
        start, end = 1400, 2300
        for i in range(start, end):
            step(sim, eng, bars, i)
        cfg = load_config(overrides=SELFTEST_OVERRIDES)
        res = bt.run(dict(sim.data), cfg, t_from=int(bars["time"][start]), t_to=int(bars["time"][end - 1]))
        # The backtest only reports closed trades, so compare closed trades on both sides.
        test = {(t["symbol"], t["dir"], t["t_in"]): t["r"] for t in res["trades"]}
        opened = {d.position_id: d for d in sim.deals if d.entry == 0}
        live = {}
        for t in store.read("trades"):
            d = opened[t["ticket"]]
            live[(d.symbol, 1 if d.type == 0 else -1, d.time - 5)] = t["r"]
        self.assertGreater(len(test), 20)
        common = set(live) & set(test)
        overlap = len(common) / max(len(set(live) | set(test)), 1)
        self.assertGreater(overlap, 0.95, f"live={len(live)} backtest={len(test)} common={len(common)}")
        for k in common:                                           # and the same result, trade by trade
            self.assertAlmostEqual(live[k], test[k], delta=0.02, msg=str(k))

    def test_costs_reduce_results(self):
        data = {s: b for s, b in build_sim(suffix="").data.items()}
        cfg = load_config(overrides=SELFTEST_OVERRIDES)
        cheap = bt.run(data, cfg, cost_mult=0.0, stop_on_halt=False)["stats"]
        dear = bt.run(data, cfg, cost_mult=6.0, stop_on_halt=False)["stats"]
        self.assertGreater(cheap["avg_r"], dear["avg_r"])


class NewsAndReportTests(unittest.TestCase):
    def test_news_blocks_around_high_impact(self):
        now = dt(2026, 11, 11, 13, 20)
        raw = [{"title": "CPI", "country": "USD", "date": "2026-11-11T08:30:00-05:00", "impact": "High"},
               {"title": "Speech", "country": "GBP", "date": "2026-11-11T08:30:00-05:00", "impact": "Low"}]
        ncfg = load_config(overrides={})["news"]
        cal = NewsCalendar(ncfg, Path(tempfile.mkdtemp()) / "n.json", fetch=lambda url: raw)
        cal.refresh(now)
        self.assertTrue(cal.blocked("EURUSD", now)[0])
        self.assertTrue(cal.blocked("XAUUSD", now)[0])                # gold reacts to USD data
        self.assertFalse(cal.blocked("EURGBP", now)[0])               # low impact is ignored
        self.assertFalse(cal.blocked("EURUSD", now + timedelta(hours=2))[0])

    def test_news_failure_modes(self):
        def boom(url):
            raise OSError("offline")
        now = dt(2026, 11, 11, 13, 20)
        ncfg = dict(load_config(overrides={})["news"])
        cal = NewsCalendar(ncfg, Path(tempfile.mkdtemp()) / "n.json", fetch=boom)
        cal.refresh(now)
        self.assertFalse(cal.blocked("EURUSD", now)[0])               # fail_mode=allow
        cal.cfg = dict(ncfg, fail_mode="block")
        self.assertTrue(cal.blocked("EURUSD", now)[0])

    def test_live_gate(self):
        good = [{"account": "demo", "r": 0.2, "pnl": 10.0} for _ in range(40)]
        self.assertTrue(rep.live_gate(good)["passed"])
        self.assertFalse(rep.live_gate(good[:39])["passed"])
        self.assertFalse(rep.live_gate([dict(t, r=-0.1, pnl=-5.0) for t in good])["passed"])
        self.assertFalse(rep.live_gate([dict(t, account="real") for t in good])["passed"])   # real trades do not count
        r = rep.build(good)
        self.assertEqual(r["overall"]["trades"], 40)
        json.dumps(r)


if __name__ == "__main__":
    unittest.main()

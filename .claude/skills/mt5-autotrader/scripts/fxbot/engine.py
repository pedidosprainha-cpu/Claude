"""The trading engine: one `cycle()` = sync account, manage positions, scan, trade.

`run()` repeats the cycle forever. Every order carries a server-side stop-loss,
so open trades stay protected even if this process or the computer dies.
"""
from __future__ import annotations

import os
import time

from . import strategy as st
from .broker import Broker, BrokerError
from .config import asset_class
from .news import NewsCalendar
from .risk import OpenRisk, RiskManager, size_lots
from .store import Store
from .timeutil import (TF_SECONDS, friday_after, in_rollover_window, iso, market_open, session_name, utcnow)

MIN_BARS = 600   # below this the daily indicators are not warmed up


class Engine:
    def __init__(self, mt5, cfg: dict, store: Store, clock=utcnow, news_fetch=None, log=None):
        self.cfg, self.store, self.clock = cfg, store, clock
        self.log = log or store.logger()
        self.broker = Broker(mt5, cfg, self.log)
        self.state = store.load_state()
        self.rm = RiskManager(cfg["risk"], self.state["risk"])
        kw = {"fetch": news_fetch} if news_fetch else {}
        self.news = NewsCalendar(cfg["news"], store.news_path, self.log, **kw)
        self.tf = cfg["timeframe"]
        self.entry_sec = TF_SECONDS[self.tf]
        self.connected = False
        self.errors = 0
        self.last_summary: dict = {}
        self._last_decision: dict = {}     # symbol -> last journaled outcome (to avoid hourly repeats)

    # ------------------------------------------------------------ connection
    def connect(self) -> None:
        self.broker.connect()
        self.broker.resolve_symbols(self.cfg["symbols"])
        if not self.broker.map:
            raise BrokerError("none of the configured symbols exist at this broker")
        self.connected = True

    def ensure_connected(self) -> None:
        if self.connected:
            ok, why = self.broker.healthy()
            if ok:
                return
            self.log.warning("connection lost (%s); reconnecting", why)
            self.broker.shutdown()
            self.connected = False
        self.connect()

    def trade_mode(self, acct: dict, term: dict) -> tuple[str, str]:
        """'trade' or 'observe' (analyse and journal, but never send an order)."""
        if not term.get("trade_allowed", True):
            return "observe", "the Algo Trading button is OFF in the MT5 terminal"
        if term.get("tradeapi_disabled", False):
            return "observe", ("MT5 option 'Disable algo trading via external Python API' is ticked "
                               "(Tools > Options > Expert Advisors)")
        if not acct.get("trade_allowed", True):
            return "observe", "trading is disabled for this login (investor/read-only password?)"
        if not acct.get("trade_expert", True):
            return "observe", "the broker disabled automated trading on this account"
        if acct["mode"] in ("demo", "contest"):
            return "trade", "demo account"
        live = self.cfg["live"]
        if live.get("enabled") and live.get("login") == acct.get("login"):
            return "trade", "REAL account, live trading authorised by the owner"
        return "observe", "REAL account without live authorisation: signals are journaled, no orders are sent"

    # ---------------------------------------------------------------- control
    def reload_config(self, cfg: dict) -> None:
        self.cfg = cfg
        self.rm.rp = cfg["risk"]
        self.news.cfg = cfg["news"]
        self.broker.cfg, self.broker.magic = cfg, int(cfg["magic"])
        self.tf, self.entry_sec = cfg["timeframe"], TF_SECONDS[cfg["timeframe"]]
        if self.connected:
            self.broker.resolve_symbols(cfg["symbols"])

    def apply_commands(self, cmds: list[dict], equity: float | None = None) -> list[str]:
        """Operator instructions queued by the CLI. They can only reduce risk or restore normal operation."""
        done, rs = [], self.rm.s
        for c in cmds:
            op = c.get("op")
            if op == "pause":
                rs["paused"] = True
            elif op == "resume":
                rs["paused"] = False
            elif op == "reset_halt":
                rs["halted"] = None
                if equity:
                    rs["hwm"] = equity          # measure drawdown from here on
            elif op == "veto":
                rs["vetoes"][c["symbol"].upper()] = {"until": float(c["until"]), "reason": c.get("reason", "")}
            elif op == "unveto":
                rs["vetoes"].pop(c["symbol"].upper(), None)
            elif op == "close":
                self.close_positions(symbol=c.get("symbol"), ticket=c.get("ticket"), reason="operator")
            elif op == "reload":
                from .config import load_config
                self.reload_config(load_config(self.store.home))
            else:
                continue
            done.append(op)
            self.log.info("COMMAND %s", c)
        return done

    # ------------------------------------------------------------------ cycle
    def cycle(self) -> dict:
        now = self.clock()
        ts = now.timestamp()
        self.ensure_connected()
        cmds = self.store.pop_commands()
        if cmds:
            self.apply_commands(cmds, float(self.broker.account()["equity"]))
        acct, term = self.broker.account(), self.broker.terminal()
        mode, mode_why = self.trade_mode(acct, term)
        equity = float(acct["equity"])
        self.rm.on_equity(equity, ts)
        self.news.refresh(now)

        positions = self.broker.positions()
        self._sync_closed(positions, ts, acct)
        self._adopt(positions)

        opened, decisions, managed = [], [], []
        new_bars = self._new_bars()
        if new_bars:
            analysis = self._analyse()
            managed = self._manage(positions, analysis, new_bars)
            if managed:
                positions = self.broker.positions()
                self._sync_closed(positions, ts, acct)     # register exits before deciding new entries
            if market_open(now):
                opened, decisions = self._scan(analysis, new_bars, now, acct, positions, mode, mode_why)
            self.state["last_bar"].update(new_bars)
            self.state["last_scan"] = {"time": iso(now), "symbols": len(new_bars), "candidates": len(decisions),
                                       "opened": len(opened)}
        self._weekend_flat(now)

        summary = {
            "status": "ok", "mode": mode, "mode_reason": mode_why,
            "account": {"login": acct.get("login"), "server": acct.get("server"), "type": acct["mode"],
                        "currency": acct.get("currency"), "balance": acct.get("balance"), "equity": equity},
            "risk": {"day_pnl_pct": round(self.rm.day_pnl_pct(equity), 2),
                     "drawdown_pct": round(self.rm.drawdown_pct(equity), 2),
                     "halted": self.rm.s["halted"], "paused": self.rm.s["paused"],
                     "day_locked": self.rm.s["day_locked"], "trades_today": self.rm.s["trades_today"]},
            "open_positions": len(self.state["positions"]),
            "symbols": len(self.broker.map), "unresolved": self.broker.unresolved,
            "market_open": market_open(now), "last_scan": self.state["last_scan"],
            "news": self.news.status(now), "opened": opened, "managed": managed,
        }
        self.last_summary = summary
        self.store.save_state(self.state)
        self.store.write_heartbeat(summary)
        return summary

    # --------------------------------------------------------------- analysis
    def _new_bars(self) -> dict:
        out = {}
        for canon in self.broker.map:
            t = self.broker.last_closed_bar(canon, self.tf)
            if t is not None and t != self.state["last_bar"].get(canon):
                out[canon] = t
        return out

    def _analyse(self) -> dict:
        """Features + signals for every symbol, and the currency-strength table."""
        sp, out = self.cfg["strategy"], {}
        for canon in self.broker.map:
            bars = self.broker.bars(canon, self.tf, int(self.cfg["history_bars"]))
            if bars is None or len(bars["time"]) < MIN_BARS:
                continue
            f = st.compute_features(bars, sp, self.tf)
            out[canon] = {"f": f, "g": st.compute_signals(f, sp)}
        strength = st.currency_strength({c: float(a["f"]["mom"][-1]) for c, a in out.items()}) if out else {}
        for canon, a in out.items():
            a["strength_diff"] = float(st.strength_diff(strength, canon))
        return out

    def snapshot(self) -> list[dict]:
        """Read-only market overview for `scan` / supervision. Sends nothing."""
        self.ensure_connected()
        now, sp, rows = self.clock(), self.cfg["strategy"], []
        for canon, a in self._analyse().items():
            f, g = a["f"], a["g"]
            tick = self.broker.tick(canon)
            d = int(g["dir"][-1])
            setup = st.SETUP_NAMES[int(g["setup"][-1])]
            if st.family_of(setup) == "reversion" and asset_class(canon) not in sp["reversion_classes"]:
                d, setup = 0, ""
            spread = float(tick.ask - tick.bid) if tick else 0.0
            dist = float(g["dist"][-1])
            row = {"symbol": canon, "price": float(f["close"][-1]), "trend": int(g["trend"][-1]),
                   "daily_stretch_z": round(float(f["b_z"][-1]), 2), "rsi": round(float(f["rsi"][-1]), 1),
                   "adx_trend_tf": round(float(f["t_adx"][-1]), 1), "strength_diff": round(a["strength_diff"], 2),
                   "atr": float(f["atr"][-1]), "spread": spread, "signal": d, "setup": setup, "score": 0.0}
            if d:
                row["score"] = round(self._score(a, d, setup, spread, dist, now), 1)
                row["stop_distance"] = dist
                row["news_block"] = self.news.blocked(canon, now)[1]
            rows.append(row)
        return sorted(rows, key=lambda r: (-r["score"], -abs(r["daily_stretch_z"])))

    def min_lot_check(self) -> dict:
        """How many traded instruments can be sized within the risk budget at the broker's minimum lot."""
        sp, rp = self.cfg["strategy"], self.cfg["risk"]
        equity = float(self.broker.account()["equity"])
        budget = equity * rp["risk_per_trade_pct"] / 100.0
        trend_on = sp["enable_pullback"] or sp["enable_breakout"]
        need, tradable = [], 0
        for canon, a in self._analyse().items():
            reversion = sp["enable_reversion"] and asset_class(canon) in sp["reversion_classes"]
            if not (reversion or trend_on):
                continue
            f = a["f"]
            dist = float(sp["mr_sl_atr"] * f["b_atr"][-1]) if reversion else float(sp["sl_atr_min"] * f["atr"][-1])
            tick = self.broker.tick(canon)
            if tick is None or dist <= 0:
                continue
            min_risk = self.broker.loss_per_lot(canon, 1, float(tick.ask), float(tick.ask) - dist) * self.broker.lots_step(canon)[0]
            tradable += min_risk <= budget * rp["min_lot_risk_tolerance"]
            need.append(min_risk / (rp["risk_per_trade_pct"] / 100.0) / rp["min_lot_risk_tolerance"])
        need.sort()
        return {"instruments": len(need), "tradable": int(tradable), "equity": equity,
                "equity_for_half": need[len(need) // 2] if need else 0.0, "equity_for_all": need[-1] if need else 0.0}

    def _score(self, a: dict, d: int, setup: str, spread: float, dist: float, now) -> float:
        pts = float(a["g"]["score"][-1])
        pts += 5.0 if st.family_of(setup) == "reversion" else float(st.strength_score(a["strength_diff"], d))
        return pts + st.session_score(session_name(now)) + st.cost_score(spread, dist)

    # ---------------------------------------------------------------- entries
    def _open_risks(self, positions: list[dict]) -> list[OpenRisk]:
        risks = []
        for p in positions:
            meta = self.state["positions"].get(str(p["ticket"]), {})
            sl = float(p.get("sl") or 0.0)
            if not sl:
                money = float(meta.get("risk_money", 0.0))
            elif p["dir"] * (p["price_open"] - sl) <= 0:
                money = 0.0                                  # stop already locks a profit
            else:
                try:
                    money = self.broker.loss_per_lot(p["canon"], p["dir"], p["price_open"], sl) * float(p["volume"])
                except BrokerError:
                    money = float(meta.get("risk_money", 0.0))
            risks.append(OpenRisk(p["canon"], p["dir"], money))
        return risks

    def _scan(self, analysis, new_bars, now, acct, positions, mode, mode_why):
        sp, ss, ts = self.cfg["strategy"], self.cfg["session"], now.timestamp()
        gate = ""
        if in_rollover_window(now, ss["rollover_block_before_min"], ss["rollover_block_after_min"]):
            gate = "daily rollover window (wide spreads)"
        elif friday_after(now, ss["friday_last_entry_hour_ny"]):
            gate = "no new entries late on Friday"
        else:
            ok, why = self.rm.can_trade(ts)
            if not ok:
                gate = why

        cands = []
        for canon in new_bars:
            a = analysis.get(canon)
            if not a:
                continue
            g = a["g"]
            d = int(g["dir"][-1])
            setup = st.SETUP_NAMES[int(g["setup"][-1])]
            if d == 0 or (st.family_of(setup) == "reversion" and asset_class(canon) not in sp["reversion_classes"]):
                continue
            tick = self.broker.tick(canon)
            if tick is None or tick.bid <= 0:
                continue
            dist = float(g["dist"][-1])
            cands.append({"symbol": canon, "dir": d, "setup": setup, "dist": dist, "bid": float(tick.bid),
                          "ask": float(tick.ask), "bar_time": int(new_bars[canon]), "tick_time": int(tick.time),
                          "score": round(self._score(a, d, setup, float(tick.ask - tick.bid), dist, now), 1)})

        opened, decisions = [], []
        for c in sorted(cands, key=lambda x: -x["score"]):
            status, detail, extra = self._try_enter(c, gate, now, acct, positions, mode, mode_why)
            rec = {"time": iso(now), "symbol": c["symbol"], "dir": c["dir"], "setup": c["setup"], "score": c["score"],
                   "status": status, "detail": detail, **extra}
            decisions.append(rec)
            key = (c["dir"], c["setup"], status, detail)
            if status != "skipped" or self._last_decision.get(c["symbol"]) != key:
                self.store.append("decisions", rec)       # a standing signal is journaled once per outcome
            self._last_decision[c["symbol"]] = key
            if status == "opened":
                opened.append(rec)
                positions = self.broker.positions()
        return opened, decisions

    def _try_enter(self, c, gate, now, acct, positions, mode, mode_why):
        sp, rp, ts = self.cfg["strategy"], self.cfg["risk"], now.timestamp()
        canon, d, setup, dist = c["symbol"], c["dir"], c["setup"], c["dist"]
        if gate:
            return "skipped", gate, {}
        if c["score"] < sp["min_score"]:
            return "skipped", f"score {c['score']} below minimum {sp['min_score']}", {}
        blocked, why = self.news.blocked(canon, now)
        if blocked:
            return "skipped", why, {}
        if self.broker.foreign_position(canon):
            return "skipped", "a position not opened by the bot exists in this symbol; leaving it alone", {}
        spread = c["ask"] - c["bid"]
        if dist <= 0 or spread > rp["max_spread_frac_of_sl"] * dist:
            return "skipped", f"spread {spread:.5f} too wide for a stop of {dist:.5f}", {}
        age = c["tick_time"] - (c["bar_time"] + self.entry_sec)
        if st.family_of(setup) == "trend" and age > self.cfg["execution"]["max_signal_age_sec"]:
            return "skipped", f"signal bar closed {age}s ago; too late to chase", {}

        risks = self._open_risks(positions)
        equity = float(acct["equity"])
        ok, why = self.rm.check_entry(canon, d, risks, equity, ts, st.cooldown_bars_of(setup, sp) * self.entry_sec)
        if not ok:
            return "skipped", why, {}

        entry = c["ask"] if d > 0 else c["bid"]
        sl, tp = st.levels(d, c["bid"], dist, st.tp_r_of(setup, sp))
        info = self.broker.info(canon)
        sl, tp = round(sl, info.digits), (round(tp, info.digits) if tp else 0.0)
        if not self.broker.stops_ok(canon, entry, sl):
            return "skipped", "stop is closer than the broker's minimum distance", {}
        budget = self.rm.budget(risks, equity)
        per_lot = self.broker.loss_per_lot(canon, d, entry, sl)
        vmin, vstep, vmax = self.broker.lots_step(canon)
        lots, why = size_lots(budget, per_lot, vmin, vstep, vmax, rp["min_lot_risk_tolerance"])
        if lots <= 0:
            return "skipped", why, {}
        plan = {"lots": lots, "entry": entry, "sl": sl, "tp": tp, "risk_money": round(lots * per_lot, 2),
                "risk_pct": round(lots * per_lot / equity * 100.0, 3)}
        margin = self._margin_level_after(canon, d, lots, entry, acct)
        if margin is not None and margin < rp["min_margin_level_pct"]:
            return "skipped", f"margin level would fall to {margin:.0f}%", plan
        if mode != "trade":
            return "observed", mode_why, plan

        res = self.broker.open_protected(canon, d, lots, sl, tp, f"fxb:{setup}:{int(c['score'])}",
                                         set(self.state["positions"]))
        if not res.get("ok"):
            self.log.error("order rejected %s: %s", canon, res)
            return "rejected", f"retcode {res.get('retcode')} {res.get('comment', '')} {res.get('hint', '')}".strip(), plan
        ticket = res["ticket"]
        fill = float(res.get("price") or entry)
        self.state["positions"][str(ticket)] = {
            "symbol": canon, "dir": d, "setup": setup, "score": c["score"], "entry": fill, "sl0": sl,
            "risk_dist": abs(fill - sl), "risk_money": plan["risk_money"], "lots": lots, "opened": iso(now),
            "bars": 0, "account": acct["mode"], "login": acct.get("login")}
        self.rm.on_entry(canon, ts)
        self.log.info("OPEN %s %s %.2f lots @ %s sl %s tp %s (%s score %s, risk %.2f)", "BUY" if d > 0 else "SELL",
                      canon, lots, fill, sl, tp, setup, c["score"], plan["risk_money"])
        return "opened", "", dict(plan, ticket=ticket, entry=fill)

    def _margin_level_after(self, canon, d, lots, price, acct):
        mt5 = self.broker.mt5
        try:
            need = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY if d > 0 else mt5.ORDER_TYPE_SELL, self.broker.map[canon],
                                         float(lots), float(price))
        except Exception:
            need = None
        if need is None:
            return None
        used = float(acct.get("margin") or 0.0) + float(need)
        return float(acct["equity"]) / used * 100.0 if used > 0 else None

    # ------------------------------------------------------------- management
    def _manage(self, positions, analysis, new_bars) -> list[dict]:
        actions = []
        for p in positions:
            meta = self.state["positions"].get(str(p["ticket"]))
            canon = p["canon"]
            if not meta or canon not in new_bars or canon not in analysis or meta.get("risk_dist", 0) <= 0:
                continue
            meta["bars"] = int(meta.get("bars", 0)) + 1
            mp = self.cfg["management"][st.family_of(meta["setup"])]
            tick = self.broker.tick(canon)
            spread = float(tick.ask - tick.bid) if tick else 0.0
            px = float(analysis[canon]["f"]["close"][-1]) + (spread if p["dir"] < 0 else 0.0)
            cur_sl = float(p.get("sl") or 0.0) or float(meta["sl0"])
            new_sl, reason = st.manage(p["dir"], meta["entry"], meta["risk_dist"], cur_sl, px, meta["bars"], mp)
            if reason:
                res = self.broker.close(p, "fxbot " + reason)
                actions.append({"ticket": p["ticket"], "symbol": canon, "action": "close", "reason": reason,
                                "ok": res.get("ok"), "detail": res.get("hint") or res.get("comment")})
                if res.get("ok"):
                    meta["exit_reason"] = reason
            elif abs(new_sl - cur_sl) > 1e-12:
                live = float(tick.bid if p["dir"] > 0 else tick.ask)
                if p["dir"] * (live - new_sl) > 0 and self.broker.stops_ok(canon, live, new_sl):
                    res = self.broker.modify_sl(p, new_sl, float(p.get("tp") or 0.0))
                    actions.append({"ticket": p["ticket"], "symbol": canon, "action": "move_stop", "sl": new_sl,
                                    "ok": res.get("ok"), "detail": res.get("hint") or res.get("comment")})
        for a in actions:
            self.log.info("MANAGE %s", a)
        return actions

    def _weekend_flat(self, now) -> None:
        if not (market_open(now) and friday_after(now, self.cfg["session"]["friday_flat_hour_ny"])):
            return
        for p in self.broker.positions():
            meta = self.state["positions"].get(str(p["ticket"]))
            if meta and self.cfg["management"][st.family_of(meta["setup"])]["flat_before_weekend"]:
                if self.broker.close(p, "fxbot weekend").get("ok"):
                    meta["exit_reason"] = "weekend_flat"

    def close_positions(self, symbol: str | None = None, ticket: int | None = None, reason: str = "operator") -> list[dict]:
        """Operator/kill-switch close. Only ever touches the bot's own positions."""
        self.ensure_connected()
        out = []
        for p in self.broker.positions():
            if (symbol and p["canon"] != symbol.upper()) or (ticket and int(p["ticket"]) != int(ticket)):
                continue
            res = self.broker.close(p, "fxbot " + reason)
            meta = self.state["positions"].get(str(p["ticket"]))
            if res.get("ok") and meta:
                meta["exit_reason"] = reason
            out.append({"ticket": p["ticket"], "symbol": p["canon"], "ok": res.get("ok"),
                        "detail": res.get("hint") or res.get("comment")})
        self.store.save_state(self.state)
        return out

    # ---------------------------------------------------------------- history
    def _sync_closed(self, positions, ts, acct) -> None:
        live = {str(p["ticket"]) for p in positions}
        for tk in [k for k in self.state["positions"] if k not in live]:
            self.state["pending_closed"][tk] = self.state["positions"].pop(tk)
        for tk in [k for k in self.state["pending_closed"] if k in live]:      # it was a glitch: still open
            meta = self.state["pending_closed"].pop(tk)
            meta.pop("tries", None)
            self.state["positions"][tk] = meta
        for tk, meta in list(self.state["pending_closed"].items()):
            res = self.broker.position_result(int(tk))
            if res is None:
                meta["tries"] = meta.get("tries", 0) + 1
                if meta["tries"] > 500:
                    self.log.error("no deal history for closed position %s; dropping it", tk)
                    del self.state["pending_closed"][tk]
                continue
            r = res["pnl"] / meta["risk_money"] if meta.get("risk_money", 0) > 0 else None
            reason = meta.get("exit_reason") or res["reason"]
            self.store.append("trades", {
                "ticket": int(tk), "symbol": meta["symbol"], "dir": meta["dir"], "setup": meta["setup"],
                "score": meta.get("score"), "lots": meta.get("lots"), "entry": meta["entry"], "exit": res["exit"],
                "opened": meta.get("opened"), "closed": iso(self.clock()), "bars": meta.get("bars"),
                "pnl": res["pnl"], "swap": res["swap"], "commission": res["commission"],
                "r": round(r, 3) if r is not None else None, "reason": reason,
                "account": meta.get("account", acct["mode"]), "login": meta.get("login", acct.get("login"))})
            self.rm.on_trade_closed(res["pnl"], ts)
            self.log.info("CLOSED %s %s pnl %.2f (%s)", meta["symbol"], tk, res["pnl"], reason)
            del self.state["pending_closed"][tk]

    def _adopt(self, positions) -> None:
        """Rebuild metadata for bot positions we have no record of (e.g. state file lost)."""
        for p in positions:
            tk = str(p["ticket"])
            if tk in self.state["positions"]:
                continue
            parts = str(p.get("comment") or "").split(":")
            setup = parts[1] if len(parts) > 1 and parts[1] in st.FAMILY else "MR"
            sl = float(p.get("sl") or 0.0)
            dist = abs(float(p["price_open"]) - sl) if sl else 0.0
            try:
                money = self.broker.loss_per_lot(p["canon"], p["dir"], p["price_open"], sl) * float(p["volume"]) if sl else 0.0
            except BrokerError:
                money = 0.0
            self.state["positions"][tk] = {
                "symbol": p["canon"], "dir": p["dir"], "setup": setup, "score": None, "entry": float(p["price_open"]),
                "sl0": sl, "risk_dist": dist, "risk_money": round(money, 2), "lots": float(p["volume"]),
                "opened": None, "bars": 0, "adopted": True}
            self.log.warning("adopted untracked bot position %s %s", p["canon"], tk)

    # -------------------------------------------------------------------- run
    def run(self) -> None:
        """Daemon loop. Exits when the STOP file appears."""
        hb = self.store.read_heartbeat()
        if hb and hb.get("pid") != os.getpid() and time.time() - float(hb.get("ts", 0)) < 90 and hb.get("status") != "stopped":
            raise SystemExit(f"another bot instance (pid {hb.get('pid')}) is already running")
        self.store.pid_path.write_text(str(os.getpid()))
        poll = max(5, int(self.cfg["poll_seconds"]))
        self.log.info("bot started (pid %s)", os.getpid())
        while not self.store.stop_requested():
            try:
                self.cycle()
                self.errors = 0
                wait = poll
            except Exception as exc:                       # never die on a transient failure
                self.errors += 1
                self.connected = False
                self.log.exception("cycle failed (%s in a row): %s", self.errors, exc)
                self.store.write_heartbeat({"status": "error", "error": f"{type(exc).__name__}: {exc}",
                                            "errors_in_a_row": self.errors})
                wait = min(300, poll * 2 ** min(self.errors, 4))
            end = time.time() + wait
            while time.time() < end and not self.store.stop_requested():
                time.sleep(1)
        self.store.save_state(self.state)
        self.store.write_heartbeat(dict(self.last_summary, status="stopped"))
        self.broker.shutdown()
        self.log.info("bot stopped")

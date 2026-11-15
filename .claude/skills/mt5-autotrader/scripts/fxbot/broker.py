"""Thin, defensive adapter over the MetaTrader5 Python API.

The `mt5` module is injected, so the exact same code runs against the real
terminal and against the simulator used by the tests (fxbot.simmt5).
"""
from __future__ import annotations

import math
import os
import re
import time
from collections import Counter

import numpy as np

from .config import ALIASES
from .timeutil import TF_SECONDS


class BrokerError(Exception):
    pass


RETCODE_HINTS = {
    10004: "requote", 10006: "request rejected", 10013: "invalid request", 10014: "invalid volume",
    10015: "invalid price", 10016: "invalid stops", 10017: "trading disabled for this symbol/account",
    10018: "market closed", 10019: "not enough money", 10020: "price changed", 10021: "no quotes",
    10024: "too many requests", 10026: "autotrading disabled by server",
    10027: "Algo Trading button is OFF in the MT5 terminal", 10030: "unsupported filling mode",
    10031: "no connection to the trade server", 10033: "pending orders limit", 10034: "volume limit for symbol",
    10040: "positions limit reached", 10044: "only closing allowed", 10045: "FIFO close rule",
}
RETRYABLE = {10004, 10020, 10021, 10024, 10031}


def _d(obj) -> dict:
    return obj._asdict() if hasattr(obj, "_asdict") else dict(obj)


class Broker:
    def __init__(self, mt5, cfg: dict, log):
        self.mt5, self.cfg, self.log = mt5, cfg, log
        self.magic = int(cfg["magic"])
        self.map: dict[str, str] = {}       # canonical -> broker symbol
        self.rev: dict[str, str] = {}       # broker symbol -> canonical
        self.unresolved: list[str] = []

    # ------------------------------------------------------------ connection
    def connect(self) -> None:
        kw = {}
        if self.cfg.get("terminal_path"):
            kw["path"] = self.cfg["terminal_path"]
        # Optional unattended login (VPS). Normally the terminal is already logged in and
        # the bot simply attaches to it, so no password is ever stored by this skill.
        if os.environ.get("MT5_LOGIN") and os.environ.get("MT5_PASSWORD") and os.environ.get("MT5_SERVER"):
            kw.update(login=int(os.environ["MT5_LOGIN"]), password=os.environ["MT5_PASSWORD"],
                      server=os.environ["MT5_SERVER"])
        if not self.mt5.initialize(**kw):
            raise BrokerError(f"could not attach to the MT5 terminal: {self.mt5.last_error()}")
        if self.mt5.account_info() is None:
            raise BrokerError("terminal is running but no trading account is logged in")

    def shutdown(self) -> None:
        try:
            self.mt5.shutdown()
        except Exception:
            pass

    def healthy(self) -> tuple[bool, str]:
        try:
            term, acct = self.mt5.terminal_info(), self.mt5.account_info()
        except Exception as exc:
            return False, f"terminal call failed: {exc}"
        if term is None or acct is None:
            return False, "terminal not reachable"
        if not getattr(term, "connected", False):
            return False, "terminal has no connection to the broker server"
        return True, ""

    def account(self) -> dict:
        a = self.mt5.account_info()
        if a is None:
            raise BrokerError("account_info unavailable")
        a = _d(a)
        a["mode"] = {0: "demo", 1: "contest", 2: "real"}.get(a.get("trade_mode"), "unknown")
        return a

    def terminal(self) -> dict:
        t = self.mt5.terminal_info()
        return _d(t) if t is not None else {}

    # --------------------------------------------------------------- symbols
    def resolve_symbols(self, wanted: list[str]) -> dict[str, str]:
        """Map canonical names (EURUSD, XAUUSD) to this broker's names (EURUSDm, GOLD.a ...)."""
        every = self.mt5.symbols_get() or ()
        by_name = {s.name: s for s in every}
        cands: dict[str, list[tuple[str, str]]] = {}
        for canon in wanted:
            forced = self.cfg.get("symbol_map", {}).get(canon)
            if forced:
                if forced in by_name:
                    cands[canon] = [(forced, "", 0)]
                continue
            roots = [canon] + ALIASES.get(canon, [])
            found = []
            for s in every:
                if getattr(s, "trade_mode", 4) == 0:      # trading disabled
                    continue
                up = s.name.upper()
                for rank, root in enumerate(roots):
                    if up.startswith(root):
                        suffix = up[len(root):]
                        # accept "", "m", ".a", "-ECN", "_i" ... but not another instrument (EURUSDX24)
                        if len(suffix) <= 5 and not re.search(r"\d", suffix):
                            found.append((s.name, suffix, rank))
                        break
            if found:
                cands[canon] = found
        votes = Counter(c[1] for lst in cands.values() for c in lst)
        self.map, self.rev, self.unresolved = {}, {}, []
        for canon in wanted:
            lst = cands.get(canon)
            if not lst:
                self.unresolved.append(canon)
                continue
            # Prefer the suffix most instruments share (the account's own symbol family).
            # ... and the standard name (XAUUSD) over an alias (GOLD) when the broker lists both.
            name = sorted(lst, key=lambda x: (x[2], -votes[x[1]], len(x[0]), x[0]))[0][0]
            if not getattr(by_name[name], "visible", True):
                self.mt5.symbol_select(name, True)
            self.map[canon], self.rev[name] = name, canon
        return self.map

    def info(self, canon: str):
        info = self.mt5.symbol_info(self.map[canon])
        if info is None:
            raise BrokerError(f"no symbol info for {self.map[canon]}")
        return info

    def tick(self, canon: str):
        return self.mt5.symbol_info_tick(self.map[canon])

    def bars(self, canon: str, tf: str, count: int) -> dict | None:
        """Closed bars only, oldest first. None when history is not available yet."""
        rates = self.mt5.copy_rates_from_pos(self.map[canon], getattr(self.mt5, "TIMEFRAME_" + tf), 0, count + 1)
        if rates is None or len(rates) < 3:
            return None
        tick = self.tick(canon)
        last_end = int(rates["time"][-1]) + TF_SECONDS[tf]
        if tick is None or int(tick.time) < last_end:      # last bar is still forming
            rates = rates[:-1]
        return {"time": np.asarray(rates["time"], dtype=np.int64),
                "open": np.asarray(rates["open"], dtype=float), "high": np.asarray(rates["high"], dtype=float),
                "low": np.asarray(rates["low"], dtype=float), "close": np.asarray(rates["close"], dtype=float)}

    def last_closed_bar(self, canon: str, tf: str) -> int | None:
        b = self.bars(canon, tf, 3)
        return int(b["time"][-1]) if b is not None and len(b["time"]) else None

    # ------------------------------------------------------------- positions
    def positions(self) -> list[dict]:
        """Only the bot's own positions (matching magic number)."""
        out = []
        raw = self.mt5.positions_get()
        if raw is None:
            # None means the call failed. Treating it as "flat" would make the bot forget its trades.
            if (self.mt5.positions_total() or 0) > 0:
                raise BrokerError(f"positions_get failed: {self.mt5.last_error()}")
            raw = ()
        for p in raw:
            if int(p.magic) != self.magic:
                continue
            d = _d(p)
            d["canon"] = self.rev.get(p.symbol, p.symbol)
            d["dir"] = 1 if p.type == self.mt5.POSITION_TYPE_BUY else -1
            out.append(d)
        return out

    def foreign_position(self, canon: str) -> bool:
        """True if someone else (manual trade, other EA) holds a position in this symbol."""
        ps = self.mt5.positions_get(symbol=self.map[canon]) or ()
        return any(int(p.magic) != self.magic for p in ps)

    def loss_per_lot(self, canon: str, direction: int, entry: float, sl: float) -> float:
        """Account-currency loss of 1.0 lot if the stop is hit."""
        sym = self.map[canon]
        action = self.mt5.ORDER_TYPE_BUY if direction > 0 else self.mt5.ORDER_TYPE_SELL
        val = self.mt5.order_calc_profit(action, sym, 1.0, entry, sl)
        if val is not None and val < 0:
            return -float(val)
        info = self.info(canon)                       # fallback: tick value
        if info.trade_tick_size > 0 and info.trade_tick_value > 0:
            return abs(entry - sl) / info.trade_tick_size * info.trade_tick_value
        raise BrokerError(f"cannot compute risk per lot for {sym}")

    # ---------------------------------------------------------------- orders
    def _filling_modes(self, info) -> list[int]:
        mt5, flags = self.mt5, int(getattr(info, "filling_mode", 0))
        modes = []
        if flags & 1:
            modes.append(mt5.ORDER_FILLING_FOK)
        if flags & 2:
            modes.append(mt5.ORDER_FILLING_IOC)
        for m in (mt5.ORDER_FILLING_RETURN, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK):
            if m not in modes:
                modes.append(m)
        return modes

    def _send(self, request: dict, info, price_fn=None) -> dict:
        mt5 = self.mt5
        last = None
        for filling in self._filling_modes(info):
            request["type_filling"] = filling
            for attempt in range(int(self.cfg["execution"]["retries"])):
                if price_fn is not None:
                    request["price"] = price_fn()
                res = mt5.order_send(request)
                if res is None:
                    last = {"retcode": -1, "comment": str(mt5.last_error())}
                    time.sleep(0.5)
                    continue
                last = _d(res)
                last.pop("request", None)
                if res.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED, 10010):
                    last["ok"] = True
                    return last
                if res.retcode in RETRYABLE:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                break
            if last and last.get("retcode") != 10030:    # only another filling mode fixes 10030
                break
        last = last or {"retcode": -1, "comment": "no response"}
        last["ok"] = False
        last["hint"] = RETCODE_HINTS.get(last.get("retcode"), "")
        return last

    def open(self, canon: str, direction: int, lots: float, sl: float, tp: float, comment: str) -> dict:
        mt5, info, sym = self.mt5, self.info(canon), self.map[canon]
        buy = direction > 0

        def price():
            t = mt5.symbol_info_tick(sym)
            return t.ask if buy else t.bid

        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": float(lots),
               "type": mt5.ORDER_TYPE_BUY if buy else mt5.ORDER_TYPE_SELL,
               "sl": round(sl, info.digits), "tp": round(tp, info.digits) if tp else 0.0,
               "deviation": int(self.cfg["execution"]["deviation_points"]), "magic": self.magic,
               "comment": comment[:31], "type_time": mt5.ORDER_TIME_GTC}
        return self._send(req, info, price)

    def open_protected(self, canon: str, direction: int, lots: float, sl: float, tp: float, comment: str,
                       known_tickets: set) -> dict:
        """Open a position and guarantee it carries a server-side stop-loss.

        Some market-execution servers refuse stops on the opening deal (retcode 10016). Then the
        position is opened bare and the stop attached immediately; if the broker refuses that as
        well, the position is closed on the spot rather than left unprotected.
        """
        res = self.open(canon, direction, lots, sl, tp, comment)
        if not res.get("ok") and res.get("retcode") == 10016:
            res = self.open(canon, direction, lots, 0.0, 0.0, comment)
            res["two_step"] = True
        if not res.get("ok"):
            return res
        mine = [p for p in self.positions() if p["canon"] == canon and str(p["ticket"]) not in known_tickets]
        if not mine:
            res["ticket"] = int(res.get("order") or res.get("deal") or 0)
            return res
        pos = max(mine, key=lambda p: (p.get("time", 0), p["ticket"]))
        res["ticket"] = int(pos["ticket"])
        if not float(pos.get("sl") or 0.0):
            mod = self.modify_sl(pos, sl, tp)
            if not mod.get("ok"):
                self.close(pos, "fxbot no stop")
                return {"ok": False, "retcode": mod.get("retcode"), "hint": mod.get("hint", ""),
                        "comment": "the broker refused the stop-loss, so the position was closed immediately"}
        return res

    def modify_sl(self, pos: dict, sl: float, tp: float) -> dict:
        info = self.mt5.symbol_info(pos["symbol"])
        req = {"action": self.mt5.TRADE_ACTION_SLTP, "symbol": pos["symbol"], "position": int(pos["ticket"]),
               "sl": round(sl, info.digits), "tp": round(tp, info.digits) if tp else 0.0, "magic": self.magic}
        res = self.mt5.order_send(req)
        out = _d(res) if res is not None else {"retcode": -1, "comment": str(self.mt5.last_error())}
        out.pop("request", None)
        out["ok"] = out.get("retcode") in (self.mt5.TRADE_RETCODE_DONE, 10025)   # 10025 = no changes
        out["hint"] = RETCODE_HINTS.get(out.get("retcode"), "")
        return out

    def close(self, pos: dict, comment: str = "fxbot close") -> dict:
        mt5, sym = self.mt5, pos["symbol"]
        info = mt5.symbol_info(sym)
        buy_to_close = pos["dir"] < 0

        def price():
            t = mt5.symbol_info_tick(sym)
            return t.ask if buy_to_close else t.bid

        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": float(pos["volume"]),
               "type": mt5.ORDER_TYPE_BUY if buy_to_close else mt5.ORDER_TYPE_SELL,
               "position": int(pos["ticket"]), "deviation": int(self.cfg["execution"]["deviation_points"]) * 3,
               "magic": self.magic, "comment": comment[:31], "type_time": mt5.ORDER_TIME_GTC}
        return self._send(req, info, price)

    def stops_ok(self, canon: str, price: float, sl: float) -> bool:
        info = self.info(canon)
        min_dist = max(int(getattr(info, "trade_stops_level", 0)), int(getattr(info, "trade_freeze_level", 0))) * info.point
        return abs(price - sl) > min_dist

    # --------------------------------------------------------------- history
    def position_result(self, ticket: int) -> dict | None:
        """Aggregate the deals of a closed position. None while the history is not ready."""
        deals = self.mt5.history_deals_get(position=int(ticket))
        if not deals:
            return None
        outs = [d for d in deals if d.entry in (self.mt5.DEAL_ENTRY_OUT, getattr(self.mt5, "DEAL_ENTRY_OUT_BY", 3))]
        if not outs:
            return None
        pnl = sum(float(d.profit) + float(d.swap) + float(d.commission) + float(getattr(d, "fee", 0.0)) for d in deals)
        last = max(outs, key=lambda d: d.time)
        reason = {4: "sl", 5: "tp", 6: "stop_out", 3: "bot", 0: "manual", 1: "manual", 2: "manual"}.get(int(last.reason), "other")
        return {"pnl": round(pnl, 2), "exit": float(last.price), "exit_time": int(last.time), "reason": reason,
                "swap": round(sum(float(d.swap) for d in deals), 2),
                "commission": round(sum(float(d.commission) + float(getattr(d, "fee", 0.0)) for d in deals), 2)}

    def lots_step(self, canon: str) -> tuple[float, float, float]:
        i = self.info(canon)
        return float(i.volume_min), float(i.volume_step), float(i.volume_max)

    @staticmethod
    def round_price(info, price: float) -> float:
        return round(price, int(info.digits)) if not math.isnan(price) else price

"""In-memory stand-in for the MetaTrader5 module.

It replays bar data through the same function names, constants and return
shapes the real API uses, so the live engine can be exercised end to end
(orders, stops, history, account) on any machine without a terminal. Used by
the test-suite and by `fxbot.py selftest`; never used for real trading.
"""
from __future__ import annotations

from collections import namedtuple

import numpy as np

from .timeutil import from_ts, market_open

SymbolInfo = namedtuple("SymbolInfo", "name visible trade_mode digits point spread volume_min volume_max volume_step "
                        "trade_stops_level trade_freeze_level filling_mode trade_contract_size trade_tick_value "
                        "trade_tick_size currency_base currency_profit path")
Tick = namedtuple("Tick", "time bid ask last volume")
Account = namedtuple("AccountInfo", "login trade_mode leverage trade_allowed trade_expert margin_mode balance equity "
                     "profit margin margin_free margin_level currency server company name fifo_close")
Terminal = namedtuple("TerminalInfo", "connected trade_allowed name path build company")
Position = namedtuple("TradePosition", "ticket time type magic identifier volume price_open sl tp price_current swap "
                      "profit symbol comment")
Deal = namedtuple("TradeDeal", "ticket order time type entry magic position_id reason volume price commission swap "
                  "profit fee symbol comment")
OrderResult = namedtuple("OrderSendResult", "retcode deal order volume price bid ask comment request_id request")

RATE_DTYPE = np.dtype([("time", "<i8"), ("open", "<f8"), ("high", "<f8"), ("low", "<f8"), ("close", "<f8"),
                       ("tick_volume", "<u8"), ("spread", "<i4"), ("real_volume", "<u8")])


def synthetic_bars(n: int = 3000, seed: int = 1, start: int = 1_700_006_400, price: float = 1.1, vol: float = 0.0012,
                   tf_sec: int = 3600) -> dict:
    """Random walk with slowly switching drift on the real FX calendar (Sun 17:00 - Fri 17:00 New York)."""
    rng = np.random.default_rng(seed)
    t, times = start - start % tf_sec, []
    while len(times) < n:
        if market_open(from_ts(t)) and market_open(from_ts(t + tf_sec - 1)):
            times.append(t)
        t += tf_sec
    drift = np.repeat(rng.normal(0, vol * 0.08, n // 150 + 1), 150)[:n]
    steps = rng.normal(0, vol, n) + drift
    close = price * np.exp(np.cumsum(steps))
    opn = np.concatenate([[price], close[:-1]])
    wick = np.abs(rng.normal(0, vol * 0.5, (2, n))) * close
    return {"time": np.asarray(times, dtype=np.int64), "open": opn, "high": np.maximum(opn, close) + wick[0],
            "low": np.minimum(opn, close) - wick[1], "close": close}


class SimMT5:
    # --- constants mirrored from the real module -------------------------------
    TIMEFRAME_M5, TIMEFRAME_M15, TIMEFRAME_M30, TIMEFRAME_H1, TIMEFRAME_H4, TIMEFRAME_D1 = 5, 15, 30, 16385, 16388, 16408
    ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1
    POSITION_TYPE_BUY, POSITION_TYPE_SELL = 0, 1
    TRADE_ACTION_DEAL, TRADE_ACTION_SLTP = 1, 6
    ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN = 0, 1, 2
    ORDER_TIME_GTC = 0
    TRADE_RETCODE_DONE, TRADE_RETCODE_PLACED = 10009, 10008
    DEAL_ENTRY_IN, DEAL_ENTRY_OUT, DEAL_ENTRY_OUT_BY = 0, 1, 3
    DEAL_REASON_EXPERT, DEAL_REASON_SL, DEAL_REASON_TP = 3, 4, 5
    ACCOUNT_TRADE_MODE_DEMO, ACCOUNT_TRADE_MODE_REAL = 0, 2

    def __init__(self, data: dict, tf_sec: int = 3600, balance: float = 10000.0, real: bool = False, login: int = 5550001,
                 suffix: str = "", spreads: dict | None = None, algo_enabled: bool = True):
        """data: canonical symbol -> bars dict. Symbols are exposed as <canonical><suffix>."""
        self.tf_sec, self.suffix = tf_sec, suffix
        self.data = {k + suffix: v for k, v in data.items()}
        self.spreads = {k + suffix: v for k, v in (spreads or {}).items()}
        self.balance, self.real, self.login, self.algo_enabled = balance, real, login, algo_enabled
        self.now = min(int(b["time"][0]) for b in self.data.values())
        self.connected = True
        self.positions: dict[int, dict] = {}
        self.deals: list = []
        self._ticket = 1000
        self.reject_next: int | None = None       # tests: force a retcode on the next order
        self.fail_positions = False               # tests: make positions_get() fail like a busy terminal
        self.refuse_stops_on_open = False         # tests: market-execution server that rejects stops on entry
        self.refuse_stop_changes = False          # tests: server that rejects every stop modification

    # --- clock ------------------------------------------------------------------
    def set_time(self, t: int) -> None:
        """Move the clock forward, settling stops/targets on every bar that completed on the way."""
        t = int(t)
        for sym, b in self.data.items():
            ends = b["time"] + self.tf_sec
            lo, hi = np.searchsorted(ends, self.now, side="right"), np.searchsorted(ends, t, side="right")
            for i in range(lo, hi):
                self._settle_bar(sym, b, i)
        self.now = t

    def _settle_bar(self, sym: str, b: dict, i: int) -> None:
        sprd = self._spread(sym)
        for tk in [k for k, p in self.positions.items() if p["symbol"] == sym]:
            p = self.positions[tk]
            if p["time"] >= int(b["time"][i]) + self.tf_sec:
                continue
            d = 1 if p["type"] == 0 else -1
            o, h, l = float(b["open"][i]), float(b["high"][i]), float(b["low"][i])
            adverse, favour, opn = (l, h, o) if d > 0 else (h + sprd, l + sprd, o + sprd)
            end = int(b["time"][i]) + self.tf_sec
            started_inside = p["time"] > int(b["time"][i])
            if p["sl"] and not started_inside and d * (opn - p["sl"]) <= 0:
                self._close(tk, opn, end, self.DEAL_REASON_SL)
            elif p["sl"] and d * (adverse - p["sl"]) <= 0:
                self._close(tk, p["sl"], end, self.DEAL_REASON_SL)
            elif p["tp"] and d * (favour - p["tp"]) >= 0:
                self._close(tk, p["tp"], end, self.DEAL_REASON_TP)

    # --- prices -----------------------------------------------------------------
    def _spread(self, sym: str) -> float:
        if sym in self.spreads:
            return self.spreads[sym]
        return 0.00012 * float(self.data[sym]["close"][0])

    def _bid(self, sym: str) -> float:
        b = self.data[sym]
        i = int(np.searchsorted(b["time"], self.now, side="right")) - 1
        if i < 0:
            return float(b["open"][0])
        forming = self.now < int(b["time"][i]) + self.tf_sec
        return float(b["open"][i] if forming else b["close"][i])

    def _digits(self, sym: str) -> int:
        px = float(self.data[sym]["close"][0])
        return 2 if px > 500 else 3 if px > 20 else 5

    def _contract(self, sym: str) -> float:
        root = sym[:6]
        return 100.0 if root.startswith("XAU") else 5000.0 if root.startswith("XAG") else 100000.0

    def _quote_to_account(self, sym: str) -> float:
        quote = sym[3:6]
        if quote == "USD":
            return 1.0
        for name, inv in ((quote + "USD" + self.suffix, False), ("USD" + quote + self.suffix, True)):
            if name in self.data:
                return 1.0 / self._bid(name) if inv else self._bid(name)
        return 1.0

    def _pnl(self, sym: str, typ: int, volume: float, p_open: float, p_close: float) -> float:
        d = 1 if typ == 0 else -1
        return d * (p_close - p_open) * volume * self._contract(sym) * self._quote_to_account(sym)

    # --- API: session -----------------------------------------------------------
    def initialize(self, **kw) -> bool:
        return self.connected

    def shutdown(self) -> None:
        pass

    def last_error(self):
        return (1, "Success") if self.connected else (-10004, "No IPC connection")

    def terminal_info(self):
        return Terminal(self.connected, self.algo_enabled, "SimTerminal", "sim://", 9999, "Simulated Broker")

    def account_info(self):
        if not self.connected:
            return None
        profit = sum(self._pnl(p["symbol"], p["type"], p["volume"], p["price_open"], self._exit_price(p))
                     for p in self.positions.values())
        equity = self.balance + profit
        margin = sum(p["volume"] * self._contract(p["symbol"]) * p["price_open"] * self._quote_to_account(p["symbol"]) / 100.0
                     for p in self.positions.values())
        return Account(self.login, 2 if self.real else 0, 100, True, True, 2, round(self.balance, 2), round(equity, 2),
                       round(profit, 2), round(margin, 2), round(equity - margin, 2),
                       round(equity / margin * 100.0, 1) if margin else 0.0, "USD", "Sim-Server", "Simulated Broker",
                       "Sim Trader", False)

    # --- API: market data --------------------------------------------------------
    def symbols_get(self, *a, **kw):
        return tuple(self.symbol_info(s) for s in self.data)

    def symbol_info(self, sym: str):
        if sym not in self.data:
            return None
        dg = self._digits(sym)
        point = 10.0 ** -dg
        return SymbolInfo(sym, True, 4, dg, point, int(round(self._spread(sym) / point)), 0.01, 100.0, 0.01, 0, 0, 3,
                          self._contract(sym), self._contract(sym) * point * self._quote_to_account(sym), point,
                          sym[:3], sym[3:6], "Sim\\" + sym)

    def symbol_select(self, sym: str, enable: bool = True) -> bool:
        return sym in self.data

    def symbol_info_tick(self, sym: str):
        if sym not in self.data:
            return None
        bid = self._bid(sym)
        return Tick(self.now, bid, bid + self._spread(sym), bid, 0)

    def copy_rates_from_pos(self, sym: str, timeframe: int, start: int, count: int):
        if sym not in self.data or timeframe != self.TIMEFRAME_H1 and self.tf_sec == 3600:
            return None
        b = self.data[sym]
        end = int(np.searchsorted(b["time"], self.now, side="right"))
        end -= start
        lo = max(0, end - count)
        if end <= 0:
            return None
        out = np.zeros(end - lo, dtype=RATE_DTYPE)
        for k in ("time", "open", "high", "low", "close"):
            out[k] = b[k][lo:end]
        if self.now < int(b["time"][end - 1]) + self.tf_sec:      # last bar is still forming: flat at the open
            out["high"][-1] = out["low"][-1] = out["close"][-1] = out["open"][-1]
        return out

    # --- API: trading ------------------------------------------------------------
    def order_calc_profit(self, action: int, sym: str, volume: float, p_open: float, p_close: float):
        return None if sym not in self.data else round(self._pnl(sym, action, volume, p_open, p_close), 2)

    def order_calc_margin(self, action: int, sym: str, volume: float, price: float):
        return None if sym not in self.data else round(volume * self._contract(sym) * price * self._quote_to_account(sym) / 100.0, 2)

    def positions_total(self) -> int:
        return len(self.positions)

    def positions_get(self, symbol: str | None = None, ticket: int | None = None):
        if self.fail_positions:
            return None
        out = []
        for p in self.positions.values():
            if (symbol and p["symbol"] != symbol) or (ticket and p["ticket"] != ticket):
                continue
            cur = self._exit_price(p)
            out.append(Position(p["ticket"], p["time"], p["type"], p["magic"], p["ticket"], p["volume"], p["price_open"],
                                p["sl"], p["tp"], cur,
                                0.0, round(self._pnl(p["symbol"], p["type"], p["volume"], p["price_open"], cur), 2),
                                p["symbol"], p["comment"]))
        return tuple(out)

    def _exit_price(self, p: dict) -> float:
        bid = self._bid(p["symbol"])
        return bid if p["type"] == 0 else bid + self._spread(p["symbol"])

    def _result(self, code: int, req: dict, comment: str = "", order: int = 0, price: float = 0.0):
        t = self.symbol_info_tick(req.get("symbol", "")) if req.get("symbol") in self.data else None
        return OrderResult(code, order, order, req.get("volume", 0.0), price, t.bid if t else 0.0, t.ask if t else 0.0,
                           comment, 1, req)

    def order_send(self, req: dict):
        if not self.connected:
            return None
        if self.reject_next is not None:
            code, self.reject_next = self.reject_next, None
            return self._result(code, req, "forced by test")
        if not self.algo_enabled:
            return self._result(10027, req, "AutoTrading disabled by client")
        sym = req.get("symbol")
        if sym not in self.data:
            return self._result(10013, req, "Invalid request")
        tick = self.symbol_info_tick(sym)
        if req["action"] == self.TRADE_ACTION_SLTP:
            p = self.positions.get(int(req["position"]))
            if p is None:
                return self._result(10013, req, "Position not found")
            if self.refuse_stop_changes:
                return self._result(10016, req, "Invalid stops")
            p["sl"], p["tp"] = float(req.get("sl", 0.0)), float(req.get("tp", 0.0))
            return self._result(10009, req, "Request executed", p["ticket"])
        if req["action"] != self.TRADE_ACTION_DEAL:
            return self._result(10013, req, "Unsupported action")
        vol = float(req["volume"])
        if vol < 0.01 or abs(round(vol * 100) - vol * 100) > 1e-6:
            return self._result(10014, req, "Invalid volume")
        typ = int(req["type"])
        price = tick.ask if typ == 0 else tick.bid
        if req.get("position"):                                    # closing an existing position
            tk = int(req["position"])
            if tk not in self.positions:
                return self._result(10013, req, "Position not found")
            self._close(tk, price, self.now, self.DEAL_REASON_EXPERT)
            return self._result(10009, req, "Request executed", tk, price)
        sl, tp = float(req.get("sl", 0.0)), float(req.get("tp", 0.0))
        d = 1 if typ == 0 else -1
        if (sl and d * (price - sl) <= 0) or (tp and d * (tp - price) <= 0) or (self.refuse_stops_on_open and (sl or tp)):
            return self._result(10016, req, "Invalid stops")
        self._ticket += 1
        tk = self._ticket
        self.positions[tk] = {"ticket": tk, "time": self.now, "type": typ, "magic": int(req.get("magic", 0)),
                              "volume": vol, "price_open": price, "sl": sl, "tp": tp, "symbol": sym,
                              "comment": req.get("comment", "")}
        self.deals.append(Deal(len(self.deals) + 1, tk, self.now, typ, self.DEAL_ENTRY_IN, int(req.get("magic", 0)), tk,
                               self.DEAL_REASON_EXPERT, vol, price, 0.0, 0.0, 0.0, 0.0, sym, req.get("comment", "")))
        return self._result(10009, req, "Request executed", tk, price)

    def _close(self, tk: int, price: float, when: int, reason: int) -> None:
        p = self.positions.pop(tk)
        pnl = self._pnl(p["symbol"], p["type"], p["volume"], p["price_open"], price)
        self.balance += pnl
        self.deals.append(Deal(len(self.deals) + 1, tk, when, 1 - p["type"], self.DEAL_ENTRY_OUT, p["magic"], tk, reason,
                               p["volume"], price, 0.0, 0.0, round(pnl, 2), 0.0, p["symbol"], ""))

    def history_deals_get(self, *args, position: int | None = None, **kw):
        if position is not None:
            return tuple(d for d in self.deals if d.position_id == position)
        if len(args) >= 2:
            lo, hi = (a.timestamp() if hasattr(a, "timestamp") else float(a) for a in args[:2])
            return tuple(d for d in self.deals if lo <= d.time <= hi)
        return tuple(self.deals)

"""Risk management shared by live trading and the backtest.

The RiskManager owns every "may we open a trade?" decision. It keeps its
counters in a plain dict (persisted by the engine) so a restart never forgets
a daily-loss lock or a drawdown halt.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .config import currencies_of
from .timeutil import from_ts, trading_day


@dataclass
class OpenRisk:
    symbol: str          # canonical name, e.g. EURUSD
    direction: int       # +1 long, -1 short
    risk_money: float    # loss if the stop is hit now (0 once the stop locks a profit)


def new_state() -> dict:
    return {
        "hwm": 0.0, "day": None, "day_start_equity": 0.0, "day_locked": False,
        "trades_today": 0, "consecutive_losses": 0, "cooldown_until": 0.0,
        "halted": None, "paused": False, "last_entry": {}, "vetoes": {},
    }


class RiskManager:
    def __init__(self, rp: dict, state: dict):
        self.rp = rp
        self.s = state
        for k, v in new_state().items():
            self.s.setdefault(k, v)

    # ------------------------------------------------------------------ account
    def on_equity(self, equity: float, now_ts: float) -> None:
        """Call on every cycle with current equity (balance + floating P&L)."""
        s = self.s
        day = trading_day(from_ts(now_ts))
        if s["day"] != day:
            s.update(day=day, day_start_equity=equity, day_locked=False, trades_today=0)
        if equity > s["hwm"]:
            s["hwm"] = equity
        if s["day_start_equity"] > 0:
            loss_pct = (s["day_start_equity"] - equity) / s["day_start_equity"] * 100.0
            if loss_pct >= self.rp["daily_loss_limit_pct"]:
                s["day_locked"] = True          # sticky until the next trading day
        if s["hwm"] > 0 and not s["halted"]:
            dd = (s["hwm"] - equity) / s["hwm"] * 100.0
            if dd >= self.rp["max_drawdown_pct"]:
                s["halted"] = (f"drawdown {dd:.1f}% from peak {s['hwm']:.2f} reached the "
                               f"{self.rp['max_drawdown_pct']}% limit")

    def drawdown_pct(self, equity: float) -> float:
        return (self.s["hwm"] - equity) / self.s["hwm"] * 100.0 if self.s["hwm"] > 0 else 0.0

    def day_pnl_pct(self, equity: float) -> float:
        d = self.s["day_start_equity"]
        return (equity - d) / d * 100.0 if d > 0 else 0.0

    # ------------------------------------------------------------------- gates
    def can_trade(self, now_ts: float) -> tuple[bool, str]:
        s = self.s
        if s["halted"]:
            return False, "halted: " + s["halted"]
        if s["paused"]:
            return False, "paused by operator"
        if s["day_locked"]:
            return False, f"daily loss limit of {self.rp['daily_loss_limit_pct']}% hit; resumes next trading day"
        if now_ts < s["cooldown_until"]:
            return False, f"cooldown after {self.rp['max_consecutive_losses']} consecutive losses"
        if s["trades_today"] >= self.rp["max_trades_per_day"]:
            return False, "max trades per day reached"
        return True, ""

    def check_entry(self, symbol: str, direction: int, open_risks: list[OpenRisk], equity: float,
                    now_ts: float, cooldown_sec: float = 0.0) -> tuple[bool, str]:
        ok, why = self.can_trade(now_ts)
        if not ok:
            return False, why
        veto = self.s["vetoes"].get(symbol)
        if veto and now_ts < veto.get("until", 0):
            return False, "vetoed: " + veto.get("reason", "")
        if any(r.symbol == symbol for r in open_risks):
            return False, "already in this symbol"
        if len(open_risks) >= self.rp["max_open_positions"]:
            return False, "max open positions"
        if now_ts - self.s["last_entry"].get(symbol, 0) < cooldown_sec:
            return False, "symbol cooldown"
        base, quote = currencies_of(symbol)
        want = {base: direction, quote: -direction}
        for cur, side in want.items():
            same = 0
            for r in open_risks:
                rb, rq = currencies_of(r.symbol)
                if (rb == cur and r.direction == side) or (rq == cur and -r.direction == side):
                    same += 1
            if same >= self.rp["max_per_currency"]:
                return False, f"currency exposure: already {same} positions {'long' if side > 0 else 'short'} {cur}"
        if self.budget(open_risks, equity) <= 0:
            return False, "total open risk at limit"
        return True, ""

    def budget(self, open_risks: list[OpenRisk], equity: float) -> float:
        """Money we may put at risk on the next trade."""
        per_trade = equity * self.rp["risk_per_trade_pct"] / 100.0
        room = equity * self.rp["max_total_risk_pct"] / 100.0 - sum(r.risk_money for r in open_risks)
        if room < per_trade * 0.5:       # not worth a sliver of a position
            return 0.0
        return max(0.0, min(per_trade, room))

    # ------------------------------------------------------------------ events
    def on_entry(self, symbol: str, now_ts: float) -> None:
        self.s["trades_today"] += 1
        self.s["last_entry"][symbol] = now_ts

    def on_trade_closed(self, pnl_money: float, now_ts: float) -> None:
        s = self.s
        if pnl_money < 0:
            s["consecutive_losses"] += 1
            if s["consecutive_losses"] >= self.rp["max_consecutive_losses"]:
                s["cooldown_until"] = now_ts + self.rp["cooldown_hours"] * 3600.0
                s["consecutive_losses"] = 0
        elif pnl_money > 0:
            s["consecutive_losses"] = 0


def size_lots(risk_money: float, loss_per_lot: float, vol_min: float, vol_step: float, vol_max: float,
              tolerance: float = 1.5) -> tuple[float, str]:
    """Lots so that hitting the stop loses about `risk_money`.

    Rounds down to the broker's step. If even the minimum lot would lose more
    than tolerance x the budget the trade is skipped: the account is too small
    for that stop, and forcing it would silently multiply the risk.
    """
    if risk_money <= 0 or loss_per_lot <= 0 or vol_step <= 0:
        return 0.0, "no risk budget or invalid contract data"
    lots = math.floor(risk_money / loss_per_lot / vol_step + 1e-9) * vol_step
    if lots < vol_min:
        if vol_min * loss_per_lot <= risk_money * tolerance:
            lots = vol_min
        else:
            return 0.0, (f"minimum lot {vol_min} would risk {vol_min * loss_per_lot:.2f}, "
                         f"budget is {risk_money:.2f}")
    lots = min(lots, vol_max)
    decimals = max(0, int(round(-math.log10(vol_step)))) if vol_step < 1 else 0
    return round(lots, decimals), ""

"""Execução de ordens — separada da geração de sinais.

Um *sinal* é uma recomendação analítica. Uma *ordem* só existe quando um adaptador de
corretora autorizado a executa. Este módulo oferece:

- PaperBroker: conta demonstrativa local (simulação com bid/ask, SL/TP, parcial no TP1 e
  stop no preço de entrada), usada para forward-test sem risco financeiro.
- OandaBroker: integração com a API v20 da OANDA (conta demo ou real). Desativada por padrão;
  exige FXI_LIVE_TRADING=1 e confirmação explícita por ordem. NÃO testada contra o servidor
  real neste ambiente (sem credenciais) — valide em conta *practice* antes de qualquer uso.
"""
from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .. import instruments as I
from ..config import secret
from ..data.base import HttpProvider, ProviderError
from ..data.models import Quote
from ..storage import Storage, now_iso


@dataclass
class OrderResult:
    ok: bool
    broker: str
    order_id: str | None
    message: str
    fill_price: float | None = None
    raw: dict | None = None


class BrokerAdapter(ABC):
    name = "abstract"

    @abstractmethod
    def place_market_order(self, symbol: str, direction: int, units: float, sl: float, tp: float,
                           signal_id: str | None = None, **kw) -> OrderResult: ...

    @abstractmethod
    def open_positions(self) -> list[dict]: ...


class PaperBroker(BrokerAdapter):
    name = "paper"

    def __init__(self, storage: Storage):
        self.st = storage

    def place_market_order(self, symbol, direction, units, sl, tp, signal_id=None, quote: Quote | None = None,
                           tp2: float | None = None, risk_amount: float | None = None, **kw) -> OrderResult:
        if quote is None:
            return OrderResult(False, self.name, None, "cotação necessária para execução simulada")
        fill = quote.ask if direction == 1 else quote.bid
        if direction * (fill - sl) <= 0:
            return OrderResult(False, self.name, None, "preço atual já além do stop — ordem rejeitada")
        pid = uuid.uuid4().hex[:12]
        with self.st.tx() as c:
            c.execute("INSERT INTO paper_positions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (pid, signal_id, symbol, direction, units, fill, sl, tp, tp2 or tp, now_iso(), "aberta",
                       1.0, 0.0, risk_amount or 0.0, None, None, json.dumps([{"t": now_iso(), "ev": "abertura",
                                                                             "px": fill}])))
        self.st.log_event("paper_order", f"Ordem demo {symbol} {'BUY' if direction == 1 else 'SELL'} "
                                         f"{units:.0f} @ {fill}", data={"position_id": pid, "signal_id": signal_id})
        return OrderResult(True, self.name, pid, "ordem demo executada", fill)

    def open_positions(self) -> list[dict]:
        return self.st.q("SELECT * FROM paper_positions WHERE status='aberta'")

    def all_positions(self, limit: int = 100) -> list[dict]:
        return self.st.q("SELECT * FROM paper_positions ORDER BY opened_at DESC LIMIT ?", (limit,))

    def update(self, quotes: dict[str, Quote]) -> list[dict]:
        """Verifica SL/TP das posições demo com a cotação corrente."""
        events = []
        for p in self.open_positions():
            q = quotes.get(p["symbol"])
            if not q:
                continue
            d = int(p["direction"])
            px_exit = q.bid if d == 1 else q.ask
            risk = abs(p["entry"] - p["sl"]) or 1e-12
            log = json.loads(p["log"] or "[]")
            remaining, realized, sl = p["remaining"], p["realized"], p["sl"]
            status = "aberta"
            if d * (px_exit - sl) <= 0:
                realized += remaining * d * (px_exit - p["entry"]) / risk
                remaining = 0.0
                status = "fechada"
                log.append({"t": now_iso(), "ev": "stop" if sl != p["entry"] else "breakeven", "px": px_exit})
            elif remaining > 0.99 and d * (px_exit - p["tp1"]) >= 0:
                realized += 0.5 * d * (px_exit - p["entry"]) / risk
                remaining = 0.5
                sl = p["entry"]
                log.append({"t": now_iso(), "ev": "tp1_parcial", "px": px_exit})
            elif remaining < 0.99 and d * (px_exit - p["tp2"]) >= 0:
                realized += remaining * d * (px_exit - p["entry"]) / risk
                remaining = 0.0
                status = "fechada"
                log.append({"t": now_iso(), "ev": "tp2", "px": px_exit})
            if (remaining, realized, sl, status) != (p["remaining"], p["realized"], p["sl"], p["status"]):
                with self.st.tx() as c:
                    c.execute("UPDATE paper_positions SET remaining=?, realized=?, sl=?, status=?, closed_at=?, r=?, log=? "
                              "WHERE id=?", (remaining, realized, sl, status,
                                             now_iso() if status == "fechada" else None,
                                             realized if status == "fechada" else None, json.dumps(log), p["id"]))
                events.append({"position_id": p["id"], "symbol": p["symbol"], "status": status,
                               "realized_r": realized, "event": log[-1]["ev"]})
        return events

    def realized_since(self, since_iso: str) -> float:
        """Resultado realizado (em moeda da conta) das posições fechadas desde `since_iso`."""
        rows = self.st.q("SELECT r, risk_amount FROM paper_positions WHERE status='fechada' AND closed_at>=?",
                         (since_iso,))
        return float(sum((r["r"] or 0) * (r["risk_amount"] or 0) for r in rows))


class OandaBroker(BrokerAdapter, HttpProvider):
    name = "oanda"

    def __init__(self):
        HttpProvider.__init__(self, timeout=15, retries=1)
        self.token = secret("FXI_OANDA_TOKEN")
        self.account = secret("FXI_OANDA_ACCOUNT")
        env = (secret("FXI_OANDA_ENV") or "practice").lower()
        self.base = "https://api-fxtrade.oanda.com" if env == "live" else "https://api-fxpractice.oanda.com"
        self.enabled = secret("FXI_LIVE_TRADING") == "1"

    def _post(self, path: str, body: dict) -> dict:
        r = self._client.post(f"{self.base}{path}", json=body,
                              headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        if r.status_code >= 400:
            raise ProviderError(f"OANDA HTTP {r.status_code}: {r.text[:300]}")
        return r.json()

    def place_market_order(self, symbol, direction, units, sl, tp, signal_id=None, confirm: bool = False,
                           **kw) -> OrderResult:
        if not (self.enabled and self.token and self.account):
            return OrderResult(False, self.name, None,
                               "execução real desativada (requer FXI_LIVE_TRADING=1 e credenciais OANDA)")
        if not confirm:
            return OrderResult(False, self.name, None, "confirmação explícita do usuário é obrigatória")
        inst = I.get(symbol)
        body = {"order": {
            "type": "MARKET", "instrument": inst.oanda, "units": str(int(direction * units)),
            "timeInForce": "FOK", "positionFill": "DEFAULT",
            "stopLossOnFill": {"price": f"{sl:.{inst.digits}f}", "timeInForce": "GTC"},
            "takeProfitOnFill": {"price": f"{tp:.{inst.digits}f}"},
            "clientExtensions": {"id": (signal_id or uuid.uuid4().hex)[:40], "tag": "fxintel"},
        }}
        try:
            d = self._post(f"/v3/accounts/{self.account}/orders", body)
        except ProviderError as exc:
            return OrderResult(False, self.name, None, str(exc))
        fill = d.get("orderFillTransaction")
        if not fill:
            reason = (d.get("orderCancelTransaction") or {}).get("reason", "ordem não executada")
            return OrderResult(False, self.name, None, reason, raw=d)
        return OrderResult(True, self.name, fill.get("id"), "executada", float(fill.get("price", 0)), raw=d)

    def open_positions(self) -> list[dict]:
        if not (self.token and self.account):
            return []
        d = self.get_json(f"{self.base}/v3/accounts/{self.account}/openTrades",
                          headers={"Authorization": f"Bearer {self.token}"})
        return d.get("trades", [])

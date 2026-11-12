"""Gestor de risco: aprova ou bloqueia sinais conforme limites de perda, exposição e correlação."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from .. import instruments as I
from ..data.models import Quote, session_of
from ..quant.correlation import directional_correlation
from .sizing import position_size


def _session_start(now: datetime) -> datetime:
    """Início aproximado da sessão corrente (blocos: 22–07, 07–12, 12–16, 16–22 UTC)."""
    for h in (16, 12, 7):
        if now.hour >= h and now.hour < 22:
            return now.replace(hour=h, minute=0, second=0, microsecond=0)
    base = now if now.hour >= 22 else now - timedelta(days=1)
    return base.replace(hour=22, minute=0, second=0, microsecond=0)


class RiskManager:
    def __init__(self, settings: dict, broker=None):
        self.settings = settings
        self.broker = broker  # PaperBroker (posições demo) — fonte de exposição/PnL

    def state(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        eq = self.settings["account"]["equity"]
        day0 = (now - timedelta(hours=22)).replace(hour=22, minute=0, second=0, microsecond=0)
        if day0 > now:
            day0 -= timedelta(days=1)
        week0 = (day0 - timedelta(days=(day0 + timedelta(hours=2)).weekday()))
        open_pos = self.broker.open_positions() if self.broker else []
        pnl_day = self.broker.realized_since(day0.isoformat()) if self.broker else 0.0
        pnl_week = self.broker.realized_since(week0.isoformat()) if self.broker else 0.0
        pnl_sess = self.broker.realized_since(_session_start(now).isoformat()) if self.broker else 0.0
        return {"equity": eq, "open_positions": open_pos, "pnl_day": pnl_day, "pnl_week": pnl_week,
                "pnl_session": pnl_sess, "session": session_of(now)}

    def evaluate(self, symbol: str, direction: int, entry: float, stop: float, quotes: dict[str, Quote],
                 corr: pd.DataFrame | None = None, slippage: float = 0.0, now: datetime | None = None) -> dict:
        r = self.settings["risk"]
        st = self.state(now)
        eq = st["equity"]
        reasons, checks = [], []

        def check(name, ok, detail):
            checks.append({"check": name, "passed": bool(ok), "detail": detail})
            if not ok:
                reasons.append(detail)

        check("perda_diaria", st["pnl_day"] > -r["max_daily_loss_pct"] / 100 * eq,
              f"Resultado do dia {st['pnl_day']:+.2f} (limite -{r['max_daily_loss_pct']}%)")
        check("perda_semanal", st["pnl_week"] > -r["max_weekly_loss_pct"] / 100 * eq,
              f"Resultado da semana {st['pnl_week']:+.2f} (limite -{r['max_weekly_loss_pct']}%)")
        check("perda_sessao", st["pnl_session"] > -r["max_session_loss_pct"] / 100 * eq,
              f"Resultado da sessão {st['pnl_session']:+.2f} (limite -{r['max_session_loss_pct']}%)")
        opn = st["open_positions"]
        check("max_posicoes", len(opn) < r["max_open_positions"],
              f"{len(opn)} posições abertas (máx. {r['max_open_positions']})")
        check("instrumento_livre", not any(p["symbol"] == symbol for p in opn),
              f"Já existe posição aberta em {symbol}" if any(p["symbol"] == symbol for p in opn)
              else f"Sem posição aberta em {symbol}")
        inst = I.get(symbol)
        exp = {inst.base: direction, inst.quote: -direction}
        rpt = r["risk_per_trade_pct"]
        worst = 0.0
        for cur, sg in exp.items():
            used = 0.0
            for p in opn:
                pi = I.get(p["symbol"])
                pe = {pi.base: p["direction"], pi.quote: -p["direction"]}
                if pe.get(cur) == sg:
                    used += (p.get("risk_amount") or 0) / eq * 100
            worst = max(worst, used + rpt)
        check("exposicao_moeda", worst <= r["max_risk_per_currency_pct"] + 1e-9,
              f"Risco agregado por moeda/direção {worst:.2f}% (máx. {r['max_risk_per_currency_pct']}%)")
        if corr is not None and opn:
            correlated = [p["symbol"] for p in opn
                          if directional_correlation(corr, symbol, direction, p["symbol"], int(p["direction"]))
                          >= r["correlation_threshold"]]
            check("correlacao", len(correlated) < r["max_correlated_positions"],
                  f"Posições correlacionadas (ρ≥{r['correlation_threshold']}): {', '.join(correlated) or 'nenhuma'}")
        else:
            check("correlacao", True, "Sem posições abertas correlacionadas")
        size = position_size(inst, entry, stop, eq, rpt, self.settings["account"]["currency"], quotes, r,
                             self.settings["account"].get("leverage", 30), slippage)
        check("dimensionamento", size.get("ok"), size.get("reason") or
              f"{size.get('lots')} lote(s), risco {size.get('risk_amount')} {size.get('account_currency')}")
        if size.get("ok"):
            check("margem", size["margin"] <= 0.5 * eq, f"Margem estimada {size['margin']:.2f} (máx. 50% do capital)")
        return {"approved": not reasons, "reasons": reasons, "checks": checks, "sizing": size,
                "state": {k: v for k, v in st.items() if k != "open_positions"} | {"open_positions": len(opn)}}

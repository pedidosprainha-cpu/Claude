"""Monitoramento contínuo: acompanhamento de sinais emitidos e alertas de mercado/dados.

- Sinais: cada sinal emitido é acompanhado (forward test) como se executado no preço de
  entrada informado, com a mesma gestão do backtest (TP1 parcial, stop no preço de entrada,
  TP2, horizonte). Usa candles M5 para não perder máximas/mínimas entre consultas.
- Alertas: evento crítico se aproximando, choque de volatilidade, falha/atraso de dados,
  sinal invalidado por deriva de preço, mudanças de status de sinais e posições demo.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from . import instruments as I
from .data.models import market_open, utcnow
from .fundamental.events import relevant_currencies

log = logging.getLogger("fxintel.monitor")


class Monitor:
    def __init__(self, engine):
        self.engine = engine
        self.hub = engine.hub
        self.st = engine.storage
        self.settings = engine.settings

    # ------------------------------------------------------------------ sinais
    def track_signals(self) -> list[dict]:
        out = []
        horizon = timedelta(hours=self.settings["model"]["horizon_bars"])
        for s in self.st.signals(limit=200, status="ativo") + self.st.signals(limit=200, status="tp1"):
            full = self.st.signal(s["id"])
            if not full:
                continue
            sig = full["payload"]
            inst = I.get(s["symbol"])
            d = 1 if s["direction"] == "BUY" else -1
            created = datetime.fromisoformat(s["created_at"])
            try:
                m5 = self.hub.bars(inst.symbol, "M5")
            except Exception as exc:  # noqa: BLE001
                log.warning("tracker sem dados para %s: %s", inst.symbol, exc)
                continue
            if inst.kind == "metal":
                q = self.hub.last_quotes.get(inst.symbol)
                if q:
                    from .data.hub import spot_adjust
                    m5, _ = spot_adjust(inst, m5, q.mid)
            bars = m5[m5.index >= pd.Timestamp(created).floor("5min")]
            entry, sl, tp1, tp2 = s["entry"], s["sl"], s["tp1"], s["tp2"] or s["tp1"]
            risk = abs(entry - sl) or 1e-12
            half = (sig.get("costs") or {}).get("spread_price", 0) / 2
            phase = 2 if s["status"] == "tp1" else 1
            status, r = None, None
            for _, b in bars.iterrows():
                lo, hi = (b.l - half, b.h - half) if d == 1 else (b.l + half, b.h + half)
                stop = entry if phase == 2 else sl
                stop_hit = lo <= stop if d == 1 else hi >= stop
                tgt = tp1 if phase == 1 else tp2
                tgt_hit = hi >= tgt if d == 1 else lo <= tgt
                if stop_hit:
                    status, r = ("stop", -1.0) if phase == 1 else ("breakeven", 0.5 * abs(tp1 - entry) / risk)
                    break
                if tgt_hit:
                    if phase == 1:
                        phase = 2
                        continue
                    status, r = "tp2", 0.5 * abs(tp1 - entry) / risk + 0.5 * abs(tp2 - entry) / risk
                    break
            if status is None and utcnow() - created > horizon:
                last = float(bars["c"].iloc[-1]) if len(bars) else entry
                mtm = d * (last - entry) / risk
                status = "encerrado_horizonte"
                r = (0.5 * abs(tp1 - entry) / risk + 0.5 * mtm) if phase == 2 else mtm
            if status is None and phase == 2 and s["status"] != "tp1":
                status = "tp1"
            if status and status != s["status"]:
                self.st.update_signal(s["id"], status, None if status == "tp1" else round(float(r), 3))
                msg = {"tp1": "atingiu TP1 (50% realizado, stop no preço de entrada)", "tp2": "atingiu TP2",
                       "stop": "foi stopado", "breakeven": "encerrado no preço de entrada após TP1",
                       "encerrado_horizonte": "encerrado por horizonte máximo"}[status]
                sev = "info" if status in ("tp1", "tp2", "breakeven") else "warning"
                self.st.add_alert("sinal_status", sev, f"Sinal {s['direction']} {s['symbol']} {msg}",
                                  s["symbol"], {"signal_id": s["id"], "status": status, "r": r},
                                  dedup=f"sigst:{s['id']}:{status}")
                out.append({"id": s["id"], "status": status, "r": r})
            # invalidação de entrada: preço se afastou além da deriva máxima durante a validade
            q = self.hub.last_quotes.get(inst.symbol)
            if q and status is None and s["status"] == "ativo":
                valid_until = datetime.fromisoformat(s["valid_until"])
                ref = sig["entry"]["price"]
                drift_lim = self.settings["gates"]["max_entry_drift_atr"]
                atr_h1 = None
                for row in (self.engine.last_result or {}).get("market", []):
                    if row["symbol"] == inst.symbol:
                        atr_h1 = row.get("atr_h1")
                if atr_h1 and utcnow() < valid_until and abs(q.mid - ref) > drift_lim * atr_h1 * 2:
                    self.st.add_alert("sinal_invalidado", "warning",
                                      f"Sinal {s['direction']} {s['symbol']}: preço se afastou da entrada "
                                      f"({q.mid:.{inst.digits}f} vs {ref}); entrada não é mais recomendada",
                                      s["symbol"], {"signal_id": s["id"]}, dedup=f"siginv:{s['id']}")
        return out

    # ------------------------------------------------------------------ alertas
    def check_alerts(self) -> int:
        n = 0
        now = utcnow()
        a = self.settings["alerts"]
        universe = self.settings["universe"]
        # eventos críticos se aproximando
        try:
            events = self.hub.calendar.events()
            curs = set()
            for s in universe:
                curs |= relevant_currencies(I.get(s))
            for e in events:
                mins = (e.time - now).total_seconds() / 60
                if e.critical and e.currency in curs and 0 <= mins <= a["event_lead_min"]:
                    n += self.st.add_alert("evento", "warning",
                                           f"Em {mins:.0f} min: {e.currency} {e.title} (impacto {e.impact}). "
                                           "Sinais nos ativos afetados ficam bloqueados.", None,
                                           e.to_dict(), dedup=f"ev:{e.currency}:{e.title}:{e.time.isoformat()}")
        except Exception as exc:  # noqa: BLE001
            n += self.st.add_alert("dados", "warning", f"Calendário econômico indisponível: {exc}", None,
                                   dedup=f"cal:{now.strftime('%Y%m%d%H')}")
        # choque de volatilidade (M5): faixa da última hora vs mediana das faixas horárias de 5 dias
        if market_open(now):
            for s in universe:
                try:
                    m5 = self.hub.bars(s, "M5")
                except Exception:  # noqa: BLE001
                    continue
                if len(m5) < 600:
                    continue
                hr = (m5["h"].rolling(12).max() - m5["l"].rolling(12).min()).iloc[::12]
                ref = float(np.nanmedian(hr.iloc[-120:-1]))
                cur = float(m5["h"].iloc[-12:].max() - m5["l"].iloc[-12:].min())
                if ref > 0 and cur / ref >= a["vol_shock_ratio"]:
                    n += self.st.add_alert("volatilidade", "warning",
                                           f"{s}: choque de volatilidade — faixa da última hora {cur / ref:.1f}× a mediana",
                                           s, {"ratio": cur / ref}, dedup=f"vol:{s}:{now.strftime('%Y%m%d%H')}")
        # saúde dos provedores
        for p in self.hub.health()["providers"]:
            if p["name"] == "oanda" and not self.hub.oanda.configured:
                continue
            if p["circuit_open"] or p["consecutive_failures"] >= 3:
                n += self.st.add_alert("dados", "critical",
                                       f"Provedor {p['name']} com falhas consecutivas: {p['last_error']}", None,
                                       p, dedup=f"prov:{p['name']}:{now.strftime('%Y%m%d%H')}")
        # cotações atrasadas
        stale = [s for s, q in self.hub.last_quotes.items()
                 if q.age_seconds(now) > self.settings["gates"]["max_quote_age_s"] and market_open(now, I.get(s).kind)]
        if stale:
            n += self.st.add_alert("dados", "warning", f"Cotações atrasadas: {', '.join(stale)}", None,
                                   {"symbols": stale}, dedup=f"stale:{now.strftime('%Y%m%d%H%M')[:-1]}")
        return n

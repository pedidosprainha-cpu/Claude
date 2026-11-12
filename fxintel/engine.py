"""Orquestração do comando "ANALISAR MERCADO AGORA".

Fluxo
 1. Cotações spot (bid/ask quando disponível), com horário e latência.
 2. Barras M5/M15/H1 (+H4/D1 derivadas), séries intermercado e calendário econômico.
 3. Por instrumento: quadro técnico MTF, regime, anomalias, qualidade de dados, níveis/zonas,
    viés fundamentalista, risco de eventos e candidatos do(s) último(s) candle(s) H1 fechado(s).
 4. Por candidato: preço de execução atual, níveis, custos, features → probabilidade (modelo),
    probabilidade calibrada OOS com IC, valor esperado, portões de validação e pontuação.
 5. Seleção do melhor candidato elegível, aprovação do gestor de risco e dimensionamento.
 6. Persistência (análise, sinal, eventos) e resposta estruturada.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from . import __version__
from . import instruments as I
from .config import load_settings
from .data.hub import DataHub, derive, spot_adjust
from .data.models import Quote, bar_age_minutes, completed_bars, market_open, session_of, utcnow
from .execution.broker import PaperBroker
from .fundamental.central_banks import load_table, staleness_days
from .fundamental.events import event_risk
from .fundamental.macro import currency_strength, macro_features, macro_snapshot, strength_diff
from .fundamental.score import fundamental_bias
from .quant.anomaly import data_quality, market_anomalies
from .quant.correlation import correlation_matrix, top_pairs
from .quant.features import build_features
from .quant.model import ProbabilityModel
from .quant.regime import StatisticalRegime, rule_regime
from .risk.manager import RiskManager
from .signals import candidates as C
from .storage import Storage
from .technical.levels import cluster_levels, round_levels, supply_demand_zones
from .technical.mtf import alignment_score, build_frame, tf_frame, tf_summary
from .technical.smc import active_zones
from .training import MODEL_PATH

log = logging.getLogger("fxintel.engine")

LIVE_H1_BARS = 2500  # janela H1 usada para o quadro ao vivo (H4/D1 usam todo o histórico)


def _f(x, nd=6):
    try:
        v = float(x)
        return round(v, nd) if np.isfinite(v) else None
    except (TypeError, ValueError):
        return None


class AnalysisEngine:
    def __init__(self, settings: dict | None = None, hub: DataHub | None = None,
                 storage: Storage | None = None):
        self.settings = settings or load_settings()
        self.hub = hub or DataHub(self.settings)
        self.storage = storage or Storage()
        self.broker = PaperBroker(self.storage)
        self.risk = RiskManager(self.settings, self.broker)
        self._model: ProbabilityModel | None = None
        self._model_mtime: float | None = None
        self._lock = threading.Lock()
        self._regimes: dict[str, StatisticalRegime] = {}
        self._frame_cache: dict[tuple, tuple] = {}
        self.last_result: dict | None = None
        self.last_details: dict[str, dict] = {}

    # ------------------------------------------------------------------ modelo
    @property
    def model(self) -> ProbabilityModel | None:
        try:
            mt = MODEL_PATH.stat().st_mtime
        except FileNotFoundError:
            return None
        if self._model is None or self._model_mtime != mt:
            self._model = ProbabilityModel.load(MODEL_PATH)
            self._model_mtime = mt
        return self._model

    def model_status(self) -> dict:
        m = self.model
        if m is None:
            return {"available": False, "validated": False,
                    "message": "Modelo não treinado. Execute: python -m fxintel train"}
        meta = m.meta
        age_h = (utcnow() - datetime.fromisoformat(meta["trained_at"])).total_seconds() / 3600
        return {"available": True, "validated": bool(meta.get("validated")), "kind": m.kind,
                "trained_at": meta.get("trained_at"), "age_hours": round(age_h, 1),
                "stale": age_h > self.settings["model"]["retrain_hours"] * 3,
                "n_train": meta.get("n_train"), "data_start": meta.get("data_start"),
                "data_end": meta.get("data_end"), "oos_metrics": meta.get("oos_metrics"),
                "oos_holdout_metrics": meta.get("oos_holdout_metrics"),
                "validation_rule": meta.get("validation_rule"),
                "calibration_table": meta.get("oos_calibration_table"),
                "top_coefficients": meta.get("coefficients", [])[:10]}

    def calibrated(self, p: float) -> dict:
        """Mapeia p do modelo para a frequência observada fora da amostra na mesma faixa."""
        m = self.model
        table = (m.meta.get("oos_calibration_table") if m else None) or []
        for row in table:
            a, b = row["bin"]
            if (a <= p < b) or (b >= 1 and p >= a):
                return {"p_oos": row["observed"], "ci90": row["ci90"], "n_bin": row["n"],
                        "bin": row["bin"], "mean_p_bin": row["mean_p"]}
        return {"p_oos": None, "ci90": None, "n_bin": 0, "bin": None}

    def confidence(self, cal: dict) -> dict:
        ms = self.model_status()
        om = ms.get("oos_metrics") or {}
        limits = []
        level = "baixa"
        if not ms["available"]:
            limits.append("Modelo indisponível — probabilidade não estimada")
        else:
            if not ms["validated"]:
                limits.append(f"Modelo NÃO validado fora da amostra (BSS {om.get('bss', float('nan')):+.4f}, "
                              f"AUC {om.get('auc', float('nan')):.3f}; regra: {ms.get('validation_rule')}): "
                              "sem evidência suficiente de vantagem preditiva e econômica")
            if cal.get("n_bin", 0) < 50:
                limits.append(f"Faixa de probabilidade com poucas observações OOS (n={cal.get('n_bin', 0)})")
            ci = cal.get("ci90")
            width = (ci[1] - ci[0]) if ci else 1.0
            if ms["validated"] and cal.get("n_bin", 0) >= 50:
                level = "média" if width <= 0.2 else "baixa"
                if (om.get("bss") or 0) >= 0.02 and (om.get("auc") or 0) >= 0.58 and width <= 0.12:
                    level = "alta"
            if ms.get("stale"):
                limits.append("Modelo desatualizado (retreinar)")
        limits.append("Probabilidades históricas não garantem resultados futuros; custos reais podem diferir")
        return {"level": level, "limitations": limits}

    # ------------------------------------------------------------------ análise
    def analyze_now(self, persist: bool = True, trigger: str = "manual") -> dict:
        if not self._lock.acquire(timeout=120):
            raise RuntimeError("análise anterior ainda em execução")
        try:
            return self._analyze(persist, trigger)
        finally:
            self._lock.release()

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    def _analyze(self, persist: bool = True, trigger: str = "manual") -> dict:
        t0 = time.perf_counter()
        now = utcnow()
        st = self.settings
        g = st["gates"]
        universe = [s for s in st["universe"] if s in I.INSTRUMENTS]
        aid = uuid.uuid4().hex[:16]
        self.hub.data_notes = {}
        timings = {}

        quotes = self.hub.quotes(universe)
        timings["quotes_ms"] = round((time.perf_counter() - t0) * 1000)
        t1 = time.perf_counter()
        bars = self.hub.multi(universe, ["M5", "M15", "H1"])
        try:
            from .quant.dataset import load_macro
            macro = load_macro(self.hub)
        except Exception as exc:  # noqa: BLE001
            log.warning("macro indisponível: %s", exc)
            macro = {}
        try:
            events = self.hub.calendar.events()
            cal_ok, cal_err = True, None
        except Exception as exc:  # noqa: BLE001
            events, cal_ok, cal_err = None, False, str(exc)
        timings["data_ms"] = round((time.perf_counter() - t1) * 1000)

        closes = {s: completed_bars(b["H1"], "H1", now)["c"] for s, b in bars.items() if "H1" in b and len(b["H1"])}
        strength = currency_strength(closes) if closes else {}
        corr = correlation_matrix(closes) if len(closes) > 1 else None
        cb = load_table()
        cb_age = staleness_days(cb)

        t2 = time.perf_counter()
        per_inst: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = {s: ex.submit(self._instrument, s, bars.get(s, {}), quotes.get(s), macro, strength,
                                 events, cb, now) for s in universe}
            for s, fu in futs.items():
                try:
                    per_inst[s] = fu.result()
                except Exception as exc:  # noqa: BLE001
                    log.exception("falha ao analisar %s", s)
                    per_inst[s] = {"symbol": s, "error": str(exc), "candidates": []}
        timings["analysis_ms"] = round((time.perf_counter() - t2) * 1000)

        cands = [c for s in universe for c in per_inst[s].get("candidates", [])]
        for c in cands:  # aprovação de risco para candidatos que passaram nos demais portões
            if all(x["passed"] for x in c["gates"]):
                q = quotes[c["instrument"]]
                rv = self.risk.evaluate(c["instrument"], 1 if c["direction"] == "BUY" else -1,
                                        c["entry"]["price"], c["stop_loss"]["price"], quotes, corr,
                                        c["costs"]["slippage_price"], now)
                c["risk"] = rv
                c["gates"].append({"gate": "gestor_de_risco", "passed": rv["approved"],
                                   "detail": "; ".join(rv["reasons"]) or "Aprovado pelos limites de risco"})
            c["eligible"] = all(x["passed"] for x in c["gates"])
        cands.sort(key=lambda c: (c["eligible"], c["score"]), reverse=True)
        best = next((c for c in cands if c["eligible"]), None)

        status = "SINAL" if best else "SEM_OPORTUNIDADE"
        if best:
            best["id"] = uuid.uuid4().hex[:16]
            best["created_at"] = now.isoformat()
            best["execution_note"] = ("Este é um SINAL analítico. A execução efetiva depende de integração "
                                      "autorizada com corretora e da confirmação das condições reais de negociação.")
        reasons_none = []
        if not best:
            if not cands:
                reasons_none.append("Nenhum setup técnico ativo nos últimos candles H1 fechados do universo monitorado.")
            else:
                agg: dict[str, int] = {}
                for c in cands:
                    for gt in c["gates"]:
                        if not gt["passed"]:
                            agg[gt["gate"]] = agg.get(gt["gate"], 0) + 1
                reasons_none = [f"{k}: bloqueou {v} candidato(s)" for k, v in sorted(agg.items(), key=lambda x: -x[1])]

        res = {
            "id": aid, "created_at": now.isoformat(), "engine_version": __version__,
            "status": status,
            "headline": (f"{best['direction']} {best['instrument']} a mercado — score {best['score']:.0f}"
                         if best else "Nenhuma oportunidade suficientemente qualificada no momento"),
            "signal": best,
            "no_signal_reasons": reasons_none,
            "observations": [c for c in cands if c is not best][:5],
            "market": [self._overview_row(per_inst[s], quotes.get(s)) for s in universe],
            "model": self.model_status(),
            "fundamentals": {
                "central_banks_as_of": cb.get("as_of"), "central_banks_age_days": cb_age,
                "central_banks_stale": bool(cb_age is not None and cb_age > 45),
                "macro": macro_snapshot(macro_features(macro, next(iter(closes.values())).index))
                if macro and closes else {},
                "strength_1d": self._strength_now(strength, 24),
                "strength_5d": self._strength_now(strength, 120),
                "calendar_ok": cal_ok, "calendar_error": cal_err,
                "upcoming_events": [e.to_dict() for e in (events or []) if now <= e.time <= now + timedelta(hours=36)
                                    and e.impact in ("High", "Medium")][:15],
            },
            "correlations": top_pairs(corr) if corr is not None else [],
            "data": {"quotes_ok": len(quotes), "universe": len(universe),
                     "notes": self.hub.data_notes, "providers": self.hub.health()},
            "risk_state": self.risk.state(now) | {"open_positions": len(self.broker.open_positions())},
            "timings": timings,
            "disclaimer": ("Análise automatizada para apoio à decisão. Não constitui recomendação de investimento. "
                           "Nenhuma metodologia garante rentabilidade; opere com gestão de risco."),
        }
        res["elapsed_ms"] = round((time.perf_counter() - t0) * 1000)
        res["trigger"] = trigger
        res = _jsonable(res)
        self.last_details = {s: _jsonable({k: v for k, v in per_inst[s].items() if k != "candidates"})
                             for s in universe}
        if not persist:
            return res
        self.storage.save_analysis(res)
        if best:
            self.storage.save_signal(res["signal"], aid)
            self.storage.add_alert("novo_sinal", "info", res["headline"], best["instrument"],
                                   {"signal_id": res["signal"]["id"]}, dedup=f"sig:{res['signal']['id']}")
        self.storage.log_event("analysis", res["headline"], data={"analysis_id": aid, "status": status,
                                                                    "elapsed_ms": res["elapsed_ms"],
                                                                    "candidates": len(cands)})
        self.last_result = res
        return res

    # ------------------------------------------------------------------ por instrumento
    def _instrument(self, sym: str, b: dict, q: Quote | None, macro: dict, strength: dict, events: list,
                    cb: dict, now: datetime) -> dict:
        inst = I.get(sym)
        st = self.settings
        g = st["gates"]
        out: dict = {"symbol": sym, "candidates": []}
        if "H1" not in b or len(b["H1"]) < 600:
            out["error"] = "histórico H1 insuficiente"
            return out
        h1_all = completed_bars(b["H1"], "H1", now)
        spot = q.mid if q else None
        basis = {"method": "none"}
        if inst.kind == "metal" and spot:
            h1_all, basis = spot_adjust(inst, h1_all, spot)
        h1 = h1_all.iloc[-LIVE_H1_BARS:]
        # cache por candle fechado (metais não são cacheados: o ajuste ao spot muda a cada cotação)
        key = (h1_all.index[-1], len(h1_all), inst.kind == "metal" and spot)
        hit = self._frame_cache.get((sym, "H1"))
        if hit and hit[0] == key:
            F, frames = hit[1]
        else:
            F, frames = build_frame(h1, derive(h1_all, "H4").iloc[-1500:], derive(h1_all, "D1"))
            self._frame_cache[(sym, "H1")] = (key, (F, frames))
        summaries = {tf: tf_summary(frames[tf][0], tf) for tf in ("D1", "H4", "H1")}
        for tf in ("M15", "M5"):
            if tf in b and len(b[tf]) > 250:
                df = completed_bars(b[tf], tf, now)
                if inst.kind == "metal" and spot:
                    df, _ = spot_adjust(inst, df, spot)
                k2 = (df.index[-1], len(df), inst.kind == "metal" and spot)
                hit = self._frame_cache.get((sym, tf))
                if hit and hit[0] == k2:
                    ftf = hit[1]
                else:
                    ftf, _ = tf_frame(df.iloc[-800:], tf, with_percentiles=False)
                    self._frame_cache[(sym, tf)] = (k2, ftf)
                summaries[tf] = tf_summary(ftf, tf)
        align = alignment_score(summaries)
        last = F.iloc[-1]
        atr = float(last["atr"])
        regime = rule_regime(last)
        if sym not in self._regimes:
            self._regimes[sym] = StatisticalRegime().fit(F)
        stat_reg = self._regimes[sym].current(F)
        anom = market_anomalies(F, g["max_vol_zscore"])
        age = bar_age_minutes(h1_all, now) - 60  # minutos desde o fechamento do último candle
        dq = data_quality(h1_all, spot, atr, age, g["max_bar_age_min"])
        mf = macro_features(macro, F.index) if macro else pd.DataFrame(index=F.index)
        sd = strength_diff(strength, inst, F.index) if strength else pd.DataFrame(index=F.index)
        fsnap = {k: (float(v) if np.isfinite(v) else None) for k, v in sd.iloc[-1].items()} if len(sd.columns) else {}
        fb = fundamental_bias(inst, macro_snapshot(mf), fsnap, cb)
        if events is None:  # calendário indisponível: conservador, bloqueia por não poder verificar eventos
            ev = {"blocked": True, "reason": "Calendário econômico indisponível: não é possível verificar eventos críticos",
                  "next_critical": None, "upcoming": [], "holidays": [], "minutes_to_next_critical": None}
        else:
            ev = event_risk(inst, events, now, g["event_blackout_before_min"], g["event_blackout_after_min"])
        f4, sw4 = frames["H4"]
        fd, swd = frames["D1"]
        sr = cluster_levels(sw4[-120:] + swd[-60:], float(fd["atr"].iloc[-1]), float(last["c"]), 0.25,
                            last_idx=None)[:8]
        zones = {"H1": active_zones(h1, F["atr"], F[["event"]]),
                 "H4": active_zones(f4[["o", "h", "l", "c"]], f4["atr"], f4[["event"]])}
        sd_zones = supply_demand_zones(h1, F["atr"])
        out.update({
            "price": spot, "quote": q.to_dict(inst.pip) if q else None, "atr_h1": atr,
            "summaries": summaries, "alignment": round(align, 3), "regime": regime,
            "statistical_regime": stat_reg, "anomalies": anom, "data_quality": dq,
            "fundamental": fb, "events": ev, "levels": sr, "zones": zones, "supply_demand": sd_zones,
            "round_levels": round_levels(sym, float(last["c"])), "session_levels": {
                k: _f(last[k]) for k in ("pdh", "pdl", "pwh", "pwl", "asia_h", "asia_l", "day_open")},
            "basis_adjustment": basis, "history_note": inst.history_note,
            "vwap_note": None if summaries["H1"].get("vwap") else "VWAP indisponível: feed spot sem volume real",
        })

        cand = C.generate(F, last_n=2)
        if cand.empty or q is None:
            return out
        X = build_features(inst, F, cand, mf, sd).add_prefix("x_")
        model = self.model
        for t, r in cand.iterrows():
            out["candidates"].append(self._candidate(inst, F, t, r, X.loc[[t]], q, model, out, now))
        return out

    def _candidate(self, inst, F, t, r, X, q: Quote, model, ctx: dict, now: datetime) -> dict:
        st = self.settings
        g = st["gates"]
        d = int(r["dir"])
        f = F.loc[t]
        atr = float(f["atr"])
        entry = q.ask if d == 1 else q.bid
        sl, tp1, tp2 = float(r["sl"]), float(r["tp1"]), float(r["tp2"])
        slip = st["slippage"]["base_pips"] * inst.pip + st["slippage"]["atr_fraction"] * atr
        risk = d * (entry - sl)
        rr1 = d * (tp1 - entry) / risk if risk > 0 else float("nan")
        rr2 = d * (tp2 - entry) / risk if risk > 0 else float("nan")
        cost_r = (q.spread / 2 + slip) / risk if risk > 0 else float("inf")
        rr_net = d * (tp1 - entry) / (risk + slip) if risk > 0 else float("nan")
        drift = d * (entry - float(r["entry_ref"])) / atr

        p = float(model.predict(X)[0]) if model is not None else None
        cal = self.calibrated(p) if p is not None else {"p_oos": None, "ci90": None, "n_bin": 0}
        p_use = cal["p_oos"] if cal.get("p_oos") is not None and cal.get("n_bin", 0) >= 30 else p
        ev_r = float(model.expected_r(np.array([p_use]), np.array([rr1]))[0]) if (model and p_use is not None
                                                                               and np.isfinite(rr1)) else None
        ev_lo = (float(model.expected_r(np.array([cal["ci90"][0]]), np.array([rr1]))[0])
                 if model and cal.get("ci90") and np.isfinite(rr1) else None)
        conf = self.confidence(cal)
        ms = self.model_status()

        gates = []

        def gate(name, ok, detail):
            gates.append({"gate": name, "passed": bool(ok), "detail": detail})

        gate("mercado_aberto", market_open(now, inst.kind), "Mercado aberto" if market_open(now, inst.kind)
             else "Mercado fechado/pausa de negociação")
        gate("cotacao_atual", q.age_seconds(now) <= g["max_quote_age_s"],
             f"Cotação com {q.age_seconds(now):.0f}s de idade (máx. {g['max_quote_age_s']}s), fonte {q.source}")
        gate("qualidade_dados", ctx["data_quality"]["ok"], "; ".join(ctx["data_quality"]["issues"]) or "Dados íntegros")
        chk = q.check or {}
        tfx = chk.get("truefx_pips")
        lim = max(3.0, 2 * q.spread / inst.pip)
        gate("consistencia_cotacao", tfx is None or abs(tfx) <= lim,
             (f"Diferença vs. TrueFX {tfx:+.1f} pips (máx. {lim:.1f})" if tfx is not None
              else "Sem segunda fonte bid/ask para este ativo") + (
                 f"; vs. Yahoo {chk['yahoo_pips']:+.1f} pips" if chk.get("yahoo_pips") is not None else ""))
        if g["block_on_anomaly"]:
            gate("anomalia_mercado", not ctx["anomalies"]["anomalous"],
                 "; ".join(ctx["anomalies"]["flags"]) or "Sem anomalias de preço")
        gate("choque_volatilidade", not ctx["regime"]["vol_shock"] and ctx["regime"]["volatility"] != "extrema",
             ctx["regime"]["label"])
        gate("evento_economico", not ctx["events"]["blocked"], ctx["events"]["reason"] or "Sem evento crítico na janela")
        sp_atr = q.spread / atr
        gate("spread", sp_atr <= g["max_spread_to_atr"],
             f"Spread {q.spread / inst.pip:.1f} pips = {sp_atr:.2f} ATR(H1) (máx. {g['max_spread_to_atr']})"
             + (" [estimado]" if q.spread_source == "estimated" else ""))
        gate("stop_valido", risk > 0, "Preço atual além do stop" if risk <= 0 else f"Risco {risk / inst.pip:.1f} pips")
        gate("custo_em_R", cost_r <= g["max_cost_r"], f"Custo de entrada {cost_r:.3f}R (máx. {g['max_cost_r']})")
        gate("risco_retorno", np.isfinite(rr_net) and rr_net >= g["min_rr_net"],
             f"R:R líquido {rr_net:.2f} (mín. {g['min_rr_net']})")
        gate("deriva_de_entrada", abs(drift) <= g["max_entry_drift_atr"],
             f"Preço {drift:+.2f} ATR do fechamento do sinal (máx. {g['max_entry_drift_atr']})")
        if g["require_model"]:
            gate("modelo_validado", ms["available"] and ms["validated"],
                 "Modelo validado fora da amostra" if ms.get("validated") else
                 (ms.get("message") or "Modelo sem habilidade preditiva comprovada fora da amostra"))
        gate("valor_esperado", ev_r is not None and ev_r >= g["min_ev_r"],
             f"EV {ev_r:+.3f}R (mín. +{g['min_ev_r']}R)" if ev_r is not None else "EV não estimável")

        # ---- pontuação multifatorial (0–100)
        w = st["scoring_weights"]
        tech = np.clip(0.4 * ctx["alignment"] * d + 0.15 * int(r["in_zone"]) + 0.1 * int(r["tp1_structural"])
                       + 0.15 * min(float(r["room_r"]), 3) / 3 + 0.1 * (int(r["trigger_engulf"]) or int(r["trigger_pin"]))
                       + 0.1 * (int(r["n_setups"]) > 1), -1, 1)
        fund = float(ctx["fundamental"]["score"]) * d
        reg = ctx["regime"]
        trend_setups = r["setup"] in ("PULLBACK", "TREND", "BREAKOUT")
        regime_fit = (0.6 if (trend_setups and reg["trend"] == "tendência") or (not trend_setups and reg["trend"] != "tendência")
                      else -0.3) - (0.6 if reg["vol_shock"] or reg["volatility"] == "extrema" else 0)
        cost_c = 1 - 2 * min(cost_r / max(g["max_cost_r"], 1e-9), 1)
        ev_c = float(np.clip((ev_r or -0.5) / 0.5, -1, 1))
        score = 50 + 50 * (w["ev"] * ev_c + w["technical"] * tech + w["fundamental"] * fund
                           + w["regime"] * regime_fit + w["cost"] * cost_c)

        dirtxt = "BUY" if d == 1 else "SELL"
        valid_until = now + timedelta(minutes=g["signal_validity_min"])
        nxt = ctx["events"].get("next_critical")
        if nxt:
            ev_time = datetime.fromisoformat(nxt["time"])
            if ev_time - timedelta(minutes=g["event_blackout_before_min"]) < valid_until:
                valid_until = max(now, ev_time - timedelta(minutes=g["event_blackout_before_min"]))
        just = self._justification(inst, r, f, ctx, d, fund)
        contrib = model.contributions(X)[:8] if model is not None else []
        opp_liq = f["near_lo"] if d == 1 else f["near_hi"]
        return {
            "instrument": inst.symbol, "direction": dirtxt, "setup": r["setup"],
            "setup_name": C.SETUP_PT[r["setup"]], "execution_type": "Entrada imediata a mercado (Market Execution)",
            "signal_bar": t.isoformat(),
            "reference_quote": {"bid": q.bid, "ask": q.ask, "mid": q.mid, "spread_pips": round(q.spread / inst.pip, 2),
                                "spread_source": q.spread_source, "time": q.time.isoformat(), "source": q.source,
                                "age_s": round(q.age_seconds(now), 1)},
            "entry": {"price": inst.round_price(entry), "side": "ASK" if d == 1 else "BID"},
            "stop_loss": {"price": inst.round_price(sl), "pips": round(abs(entry - sl) / inst.pip, 1),
                          "basis": "Além do extremo estrutural do setup + buffer de 0,25 ATR (mín. 1 ATR)"},
            "take_profit": [
                {"label": "TP1 (50%)", "price": inst.round_price(tp1), "pips": round(abs(tp1 - entry) / inst.pip, 1),
                 "rr": _f(rr1, 2), "basis": "Pool de liquidez oposto" if r["tp1_structural"] else "Alvo padrão 1,5R"},
                {"label": "TP2 (restante, stop no preço de entrada)", "price": inst.round_price(tp2),
                 "pips": round(abs(tp2 - entry) / inst.pip, 1), "rr": _f(rr2, 2)},
            ],
            "risk_reward": {"rr_tp1": _f(rr1, 2), "rr_tp2": _f(rr2, 2), "rr_net_tp1": _f(rr_net, 2),
                            "cost_r": _f(cost_r, 3)},
            "costs": {"spread_price": q.spread, "slippage_price": slip, "cost_r": _f(cost_r, 3),
                      "estimated": q.spread_source == "estimated"},
            "probability": {"model_p": _f(p, 3), "calibrated_p": _f(cal.get("p_oos"), 3),
                            "ci90": [_f(x, 3) for x in cal["ci90"]] if cal.get("ci90") else None,
                            "n_oos_bin": cal.get("n_bin"), "event": "TP1 atingido antes do Stop Loss",
                            "method": "Regressão logística (walk-forward) → frequência observada fora da amostra na faixa"},
            "expected_value_r": _f(ev_r, 3), "expected_value_r_ci_low": _f(ev_lo, 3),
            "confidence": conf,
            "score": round(float(score), 1),
            "score_components": {"ev": round(ev_c, 3), "technical": round(float(tech), 3), "fundamental": round(fund, 3),
                                 "regime": round(regime_fit, 3), "cost": round(cost_c, 3), "weights": w},
            "justification": just,
            "model_drivers": contrib,
            "invalidation": [
                f"Fechamento H1 {'abaixo' if d == 1 else 'acima'} de {inst.round_price(sl)} (stop)",
                f"Preço se afastar mais de {g['max_entry_drift_atr']} ATR ({g['max_entry_drift_atr'] * atr / inst.pip:.1f} pips) "
                f"de {inst.round_price(float(r['entry_ref']))} antes da entrada",
                f"CHoCH {'de baixa' if d == 1 else 'de alta'} no H1 antes de atingir o TP1",
                "Evento econômico de alto impacto não previsto / spread acima do limite",
            ] + ([f"Evento crítico: {nxt['currency']} {nxt['title']} às {nxt['time'][11:16]} UTC"] if nxt else []),
            "validity": {"valid_until": valid_until.isoformat(),
                         "minutes": round((valid_until - now).total_seconds() / 60)},
            "scenarios": {
                "principal": f"{'Alta' if d == 1 else 'Baixa'} até {inst.round_price(tp1)} (TP1) e extensão a {inst.round_price(tp2)}",
                "alternativo": (f"Falha do setup: rompimento de {inst.round_price(sl)} abre caminho para a liquidez em "
                                f"{inst.round_price(float(opp_liq)) if np.isfinite(opp_liq) else '—'}"),
                "riscos": [x for x in (
                    ctx["events"]["reason"],
                    "Viés fundamentalista contrário" if fund < -0.2 else None,
                    "Timeframes superiores desalinhados" if ctx["alignment"] * d < 0 else None,
                    f"Regime {ctx['regime']['label']}" if ctx["regime"]["volatility"] in ("alta", "extrema") else None,
                    "Spread estimado (provedor sem bid/ask real)" if q.spread_source == "estimated" else None,
                ) if x],
            },
            "gates": gates,
            "context": {"alignment": ctx["alignment"], "regime": ctx["regime"]["label"],
                        "fundamental_score": ctx["fundamental"]["score"]},
        }

    def _justification(self, inst, r, f, ctx, d, fund) -> dict:
        s = ctx["summaries"]
        tech = [f"Setup: {C.SETUP_PT[r['setup']]}"
                + (f" (confluência de {int(r['n_setups'])} setups)" if int(r["n_setups"]) > 1 else "")]
        for tf in ("D1", "H4", "H1", "M15"):
            if tf in s:
                x = s[tf]
                tech.append(f"{tf}: tendência {x['trend_text']}; último evento {x['last_event']}; RSI {x['rsi']}"
                            + (f"; {x['divergence']}" if x.get("divergence") else ""))
        if r["in_zone"]:
            tech.append("Preço reagiu em zona institucional (FVG/Order Block) a favor do trade")
        if r["at_ema"]:
            tech.append("Recuo testou a EMA50 do H1 (zona de valor)")
        if r["trigger_engulf"]:
            tech.append("Gatilho: candle de engolfo no H1")
        if r["trigger_pin"]:
            tech.append("Gatilho: rejeição (pin bar) no H1")
        if r["pd_sweep"]:
            tech.append("Varredura da máxima/mínima do pregão anterior com fechamento de volta (falso rompimento)")
        tech.append(f"Espaço livre até o obstáculo oposto: {float(r['room_r']):.1f}R; alinhamento MTF {ctx['alignment'] * d:+.2f}")
        fundl = [c["text"] + f" → contribuição {c['contribution'] * d:+.3f}" for c in ctx["fundamental"]["components"]]
        quant = [f"Regime: {ctx['regime']['label']}"]
        if ctx.get("statistical_regime"):
            sr = ctx["statistical_regime"]
            quant.append(f"Regime estatístico (GMM): {sr['state']} há {sr['bars_in_state']} candles")
        quant.append(f"Percentil de volatilidade (ATR): {ctx['regime']['atr_percentile']}")
        return {"technical": tech, "fundamental": fundl or ["Sem componentes fundamentalistas disponíveis"],
                "quantitative": quant, "fundamental_alignment": round(fund, 3)}

    def _overview_row(self, x: dict, q: Quote | None) -> dict:
        s = x.get("summaries", {})
        return {
            "symbol": x["symbol"], "error": x.get("error"),
            "quote": q.to_dict(I.get(x["symbol"]).pip) if q else None,
            "trend": {tf: s[tf]["direction"] for tf in s},
            "alignment": x.get("alignment"),
            "regime": (x.get("regime") or {}).get("label"),
            "fundamental_score": (x.get("fundamental") or {}).get("score"),
            "event_block": (x.get("events") or {}).get("reason"),
            "next_event": (x.get("events") or {}).get("next_critical"),
            "anomalies": (x.get("anomalies") or {}).get("flags"),
            "data_issues": (x.get("data_quality") or {}).get("issues"),
            "candidates": len(x.get("candidates", [])),
            "levels": x.get("levels", [])[:4],
            "atr_h1": x.get("atr_h1"),
        }

    @staticmethod
    def _strength_now(strength: dict, w: int) -> dict:
        st = strength.get(w)
        if st is None or st.empty:
            return {}
        last = st.ffill().iloc[-1]
        return {k: round(float(v), 3) for k, v in last.sort_values(ascending=False).items() if np.isfinite(v)}

    # ------------------------------------------------------------------ dados para gráfico
    def chart(self, symbol: str, tf: str = "H1", bars: int = 150) -> dict:
        inst = I.get(symbol)
        if tf in ("H4", "D1"):
            df = derive(self.hub.bars(symbol, "H1"), tf)
        else:
            df = self.hub.bars(symbol, tf)
        q = self.hub.last_quotes.get(symbol)
        if inst.kind == "metal":
            spot = q.mid if q else None
            if spot is None:
                try:
                    spot = self.hub.goldapi.spot(symbol)["price"]
                except Exception:  # noqa: BLE001
                    spot = None
            if spot:
                df, _ = spot_adjust(inst, df, spot)
        df = df.iloc[-bars:]
        return {"symbol": symbol, "tf": tf, "digits": inst.digits,
                "bars": [{"t": int(ts.timestamp()), "o": _f(r.o), "h": _f(r.h), "l": _f(r.l), "c": _f(r.c)}
                         for ts, r in df.iterrows()]}


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating,)):
        v = float(o)
        return v if np.isfinite(v) else None
    if isinstance(o, float):
        return o if np.isfinite(o) else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (pd.Timestamp, datetime)):
        return o.isoformat()
    return o


__all__ = ["AnalysisEngine", "session_of"]

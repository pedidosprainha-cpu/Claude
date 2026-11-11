"""Entry point used by the Android app (via Chaquopy).

`run()` executes a live scan and returns a self-contained JSON document with
every number already formatted for display, so the UI layer stays dumb.
"""
from __future__ import annotations

import json
import math
import os
import time
import traceback

import numpy as np
from datetime import timedelta
from zoneinfo import ZoneInfo

from . import breakouts as bk
from .analysis import signal_model as sig_mod
from .config import Settings
from .engine import Engine, Opportunity, ScanResult
from .instruments import UNIVERSE


def UNIVERSE_FMT(symbol: str, price: float) -> str:  # noqa: N802 - small formatting helper
    return UNIVERSE[symbol].fmt(price)

DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
COMP = {"technical": "Técnico", "quant": "Quant", "strength": "Força", "fundamental": "Fundamental"}


def _num(x: float | None, nd: int = 2) -> float | None:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return None
    return round(float(x), nd)


def _status(o: Opportunity, min_score: float) -> str:
    if o.executable:
        return "Executável"
    if o.gates:
        return o.gates[0][:1].upper() + o.gates[0][1:]
    return f"Score abaixo do mínimo ({min_score:.0f})"


def order_text(o: Opportunity) -> str:
    p, i = o.plan, o.inst
    lines = [
        f"{o.side} {o.symbol} a mercado",
        f"Entrada: {i.fmt(p.entry)}",
        f"Stop loss: {i.fmt(p.sl)} ({p.sl_pips:.1f} pips)",
    ]
    if p.exit_kind == "trail":
        lines += [f"+1R em {i.fmt(p.tp1)}: ativar stop móvel",
                  f"Saída: {p.exit_rule}"]
    elif p.exit_kind == "partial":
        lines += [f"Alvo 1: {i.fmt(p.tp1)} ({p.rr1:.2f}R) - realizar 50% e stop na entrada",
                  f"Alvo 2: {i.fmt(p.tp2)} ({p.rr2:.2f}R)"]
    else:
        lines += [f"Saída: {p.exit_rule}"]
    lines += [f"Lote: {p.lots:.2f} (risco US$ {p.risk_amount:,.2f})",
              f"Invalidação: {p.invalidation}"]
    if o.signal is not None:
        lines.append(f"Histórico de sinais parecidos: lucro em {o.signal.p * 100:.0f}% · expectativa "
                     f"{o.signal.ev_r:+.2f}R")
    return "\n".join(lines)


def edge_dict(o: Opportunity) -> dict | None:
    """Probability/expectancy shown in the app: calibrated model when loaded, else the old study."""
    sg = o.signal
    if sg is not None:
        m = sig_mod.load_model()
        return {"p": _num(sg.p, 3), "raw": _num(sg.p, 3), "n": int((m.info if m else {}).get("bars", 0)),
                "exp_r": _num(sg.ev_r), "pf": None, "avg_h": None, "source": "modelo", "passes": sg.passes,
                "other_exp_r": _num(sg.other_ev_r)}
    e = o.edge
    if e is None:
        return None
    return {"p": _num(e.p_post, 3), "raw": _num(e.win_rate, 3), "n": e.n, "exp_r": _num(e.exp_post_r),
            "pf": _num(e.profit_factor), "avg_h": _num(e.avg_bars, 0), "source": "estudo"}


def opp_dict(o: Opportunity, tz: ZoneInfo, min_score: float) -> dict:
    p, i = o.plan, o.inst
    return {
        "symbol": o.symbol,
        "name": i.name or f"{i.base}/{i.quote}",
        "is_metal": i.is_metal,
        "direction": o.direction,
        "side": o.side,
        "score": _num(o.score, 1),
        "grade": o.grade,
        "executable": o.executable,
        "status": _status(o, min_score),
        "gates": o.gates,
        "bid": i.fmt(o.bid),
        "ask": i.fmt(o.ask),
        "spread_pips": _num(o.spread_pips, 1),
        "quote_time": o.quote_ts.astimezone(tz).strftime("%H:%M:%S"),
        "quote_source": o.quote_source,
        "entry": i.fmt(p.entry),
        "sl": i.fmt(p.sl),
        "tp1": i.fmt(p.tp1),
        "tp2": i.fmt(p.tp2),
        "sl_pips": _num(p.sl_pips, 1),
        "tp1_pips": _num(p.tp1_pips, 1),
        "tp2_pips": _num(p.tp2_pips, 1),
        "rr1": _num(p.rr1),
        "rr2": _num(p.rr2),
        "lots": _num(p.lots),
        "risk_amount": _num(p.risk_amount),
        "pip_value": _num(p.pip_value_lot),
        "sl_basis": p.sl_basis,
        "tp1_basis": p.tp1_basis,
        "tp2_basis": p.tp2_basis,
        "invalidation": p.invalidation,
        "edge": edge_dict(o),
        "exit_kind": p.exit_kind,
        "exit_rule": p.exit_rule,
        "trail_pips": _num(i.pips(p.trail_dist), 1),
        "horizon_h": p.horizon_h,
        "components": [{"name": COMP[k], "value": _num(v, 0)} for k, v in o.components.items()],
        "multipliers": [{"name": k, "value": _num(v, 2), "note": n} for k, (v, n) in o.multipliers.items()],
        "regime": o.quant.regime,
        "reasons": o.reasons,
        "warnings": o.warnings + o.data_notes,
        "order_text": order_text(o),
    }


def result_dict(r: ScanResult, tz_name: str = "America/Sao_Paulo", elapsed: float = 0.0) -> dict:
    tz = ZoneInfo(tz_name)
    s = r.settings
    loc = r.now.astimezone(tz)
    best, top = r.best, r.top
    if best:
        decision = {"execute": True, "headline": f"{best.side} {best.symbol}",
                    "reason": f"Nota {best.grade} · {best.score:.0f}/100 · passou em todos os filtros"}
    elif top:
        why = top.gates[0] if top.gates else f"score {top.score:.0f} abaixo do mínimo {s.min_score:.0f}"
        decision = {"execute": False, "headline": "Nenhuma entrada agora",
                    "reason": f"Melhor candidato {top.side.lower()} {top.symbol}: {why}"}
    else:
        decision = {"execute": False, "headline": "Sem dados", "reason": "nenhum ativo pôde ser analisado"}

    events = sorted((ev for ev in r.ctx.events if ev.impact == "High"
                     and r.now - timedelta(hours=1) <= ev.time <= r.now + timedelta(hours=48)), key=lambda x: x.time)
    ev_out = []
    for ev in events[:15]:
        mins = (ev.time - r.now).total_seconds() / 60
        t = ev.time.astimezone(tz)
        ev_out.append({"when": f"{DIAS[t.weekday()]} {t:%d/%m %H:%M}", "ccy": ev.ccy, "title": ev.title,
                       "in": (f"em {mins / 60:.1f}h" if mins >= 60 else f"em {mins:.0f} min") if mins >= 0
                       else f"há {-mins:.0f} min",
                       "forecast": ev.forecast, "previous": ev.previous})

    issues = [f"{k}: {v}" for k, v in {**r.ctx.status, **r.errors}.items() if v not in ("ok", "sintético")]
    rates = sorted((r.ctx.rates or {}).values(), key=lambda x: -x.rate)
    return {
        "ok": True,
        "signal_model": sig_mod.model_summary() if s.use_edge else {"available": False},
        "timestamp": loc.strftime("%d/%m/%Y %H:%M"),
        "timestamp_utc": r.now.isoformat(),
        "weekday": DIAS[loc.weekday()],
        "session": r.session.label,
        "fx_open": r.session.fx_open,
        "metals_open": r.session.metals_open,
        "risk": {"value": _num(r.macro.risk), "label": r.macro.risk_label},
        "settings": {"balance": s.balance, "risk_pct": s.risk_pct, "min_score": s.min_score},
        "decision": decision,
        "best": opp_dict(best, tz, s.min_score) if best else None,
        "top": opp_dict(top, tz, s.min_score) if top else None,
        "ranking": [opp_dict(o, tz, s.min_score) for o in r.opportunities],
        "strength": [{"ccy": c, "z": _num(v), "h4": _num(r.strength.by_horizon["4h"][c]),
                      "h24": _num(r.strength.by_horizon["24h"][c]), "d5": _num(r.strength.by_horizon["5d"][c])}
                     for c, v in r.strength.ranking],
        "metals_z": [{"code": k, "z": _num(v)} for k, v in r.strength.metal_z.items()],
        "macro_notes": r.macro.notes,
        "rates": [{"ccy": x.ccy, "rate": _num(x.rate), "chg6m": _num(x.change_6m)} for x in rates],
        "rates_source": rates[0].source if rates else "",
        "cot": [{"asset": c.asset, "net_pct": _num(c.net_pct_oi, 0), "index": _num(c.index_3y, 0)}
                for c in (r.ctx.cot or {}).values()],
        "events": ev_out,
        "headlines": [{"when": h.time.astimezone(tz).strftime("%d/%m %H:%M"), "title": h.title}
                      for h in r.ctx.headlines[:15]],
        "data_issues": issues,
        "elapsed_s": _num(elapsed, 1),
    }


def run(cache_dir: str, balance: float = 10_000.0, risk_pct: float = 1.0, assets: str = "all",
        use_edge: bool = True, use_news: bool = True, tz_name: str = "America/Sao_Paulo",
        listener=None, offline: bool = False) -> str:
    """Run a scan; `listener.onProgress(int, str)` receives progress (Java object or Python)."""
    def progress(pct: float, msg: str) -> None:
        if listener is not None:
            listener.onProgress(int(round(pct)), msg)

    t0 = time.time()
    try:
        s = Settings(balance=float(balance), risk_pct=float(risk_pct), cache_dir=cache_dir,
                     use_edge=bool(use_edge), use_news=bool(use_news), workers=6, offline=bool(offline))
        progress(1, "Iniciando o motor")
        res = Engine(s).scan(None if assets in (None, "", "all") else assets, progress=progress)
        if not res.opportunities:
            issues = {**res.ctx.status, **res.errors}
            return json.dumps({"ok": False, "error": "Nenhum ativo pôde ser analisado. Verifique a internet.",
                               "detail": "; ".join(f"{k}: {v}" for k, v in list(issues.items())[:6])},
                              ensure_ascii=False)
        return json.dumps(result_dict(res, tz_name, time.time() - t0), ensure_ascii=False, default=str)
    except Exception as e:  # noqa: BLE001 - surface any failure to the UI instead of crashing
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}",
                           "detail": traceback.format_exc()[-1500:]}, ensure_ascii=False)


# ---------------------------------------------------------------------------- breakouts

def _entry_line(b: bk.Breakout, tz: ZoneInfo | None = None) -> str:
    p, i = b.plan, b.inst
    until = p.valid_until.astimezone(tz).strftime("%H:%M") if (p.valid_until and tz) else (
        p.valid_until.strftime("%H:%M UTC") if p.valid_until else "")
    if p.entry_type == "limite":
        return f"Ordem LIMITE de {b.side.lower()} em {i.fmt(p.entry)} (reteste do nível) — válida até {until}"
    if p.entry_type == "confirmacao":
        if b.confirm_state == "confirmado" and b.confirmed_at is not None:
            hhmm = b.confirmed_at.astimezone(tz).strftime("%H:%M") if tz else b.confirmed_at.strftime("%H:%M UTC")
            return f"CONFIRMADO às {hhmm}: {b.side.lower()} a mercado agora (~{i.fmt(p.entry)})"
        if b.confirm_state == "nao_confirmou":
            return "não confirmou no fechamento do candle: não entrar"
        return (f"{b.side.capitalize()} a mercado no fechamento do candle {b.tf} das {until} "
                f"se ele fechar a favor (o monitor avisa); referência {i.fmt(p.entry)}")
    return f"{b.side.capitalize()} a mercado em {i.fmt(p.entry)}"


def breakout_order_text(b: bk.Breakout, tz: ZoneInfo | None = None) -> str:
    p, i = b.plan, b.inst
    lines = [
        f"{b.side} {b.symbol} — {bk.STATUS_LABEL[b.status].lower()} ({b.tf})",
        f"Nível: {i.fmt(b.level.price)} ({b.level.label})",
        f"Entrada: {_entry_line(b, tz)}",
        f"Stop loss: {i.fmt(p.sl)} ({p.sl_pips:.1f} pips)",
    ]
    if p.exit_kind == "trail":
        lines += [f"+1R em {i.fmt(p.tp1)}: ativar stop móvel",
                  f"Saída: {p.exit_rule}"]
    elif p.exit_kind == "be":
        lines += [f"+1R em {i.fmt(p.tp1)}: stop para a entrada", f"Alvo: {i.fmt(p.tp2)} ({p.rr2:.2f}R)"]
    elif p.exit_rule:
        lines += [f"Alvo: {i.fmt(p.tp1)} ({p.rr1:.2f}R)"]
    else:
        lines += [f"Alvo 1: {i.fmt(p.tp1)} ({p.rr1:.2f}R) - realizar 50% e stop na entrada",
                  f"Alvo 2: {i.fmt(p.tp2)} ({p.rr2:.2f}R)"]
    lines.append(f"Lote: {p.lots:.2f} (risco US$ {p.risk_amount:,.2f})")
    if b.prob is not None:
        lines.append(f"Histórico de sinais parecidos: {b.prob * 100:.0f}% terminaram no lucro · "
                     f"expectativa {b.ev_r:+.2f}R")
    return "\n".join(lines)


def breakout_dict(b: bk.Breakout, tz: ZoneInfo, now) -> dict:
    p, i = b.plan, b.inst
    age = int((now - b.first_seen).total_seconds() // 60) if b.first_seen else 0
    return {
        "id": f"{b.symbol}|{b.tf}|{b.direction}|{b.status == 'falso'}|{i.fmt(b.level.price)}",
        "symbol": b.symbol,
        "name": i.name or f"{i.base}/{i.quote}",
        "tf": b.tf,
        "direction": b.direction,
        "break_dir": b.break_dir,
        "side": b.side,
        "status": b.status,
        "status_label": bk.STATUS_LABEL[b.status],
        "extended": b.extended,
        "actionable": b.actionable,
        "blocked": b.blocked,
        "headline": b.headline(),
        "level": i.fmt(b.level.price),
        "level_label": b.level.label,
        "level_kind": b.level.kind,
        "bid": i.fmt(b.bid),
        "ask": i.fmt(b.ask),
        "ext_atr": _num(b.ext_atr),
        "ext_pips": _num(i.pips(b.ext_atr * b.atr), 1),
        "bars_since": b.bars_since,
        "broke_at": b.broke_at.tz_convert(tz).strftime("%H:%M") if b.broke_at.tzinfo else str(b.broke_at),
        "first_seen": b.first_seen.astimezone(tz).strftime("%H:%M") if b.first_seen else "",
        "age_min": age,
        "is_new": b.is_new,
        "confirm_state": b.confirm_state,
        "quality": _num(b.quality, 1),
        "grade": b.grade,
        "prob": _num(b.prob, 3),
        "ev_r": _num(b.ev_r, 2),
        "pros": b.pros,
        "cons": b.cons,
        "hist": {"n": b.hist_n, "wins": b.hist_wins, "p": _num(b.hist_p, 3)} if b.hist_n >= 8 else None,
        "plan": {
            "entry_type": p.entry_type, "entry_text": _entry_line(b, tz),
            "valid_until": p.valid_until.astimezone(tz).strftime("%H:%M") if p.valid_until else "",
            "exit_kind": p.exit_kind, "exit_rule": p.exit_rule,
            "trail_pips": _num(i.pips(p.trail), 1) if p.trail else None,
            "entry": i.fmt(p.entry), "sl": i.fmt(p.sl), "tp1": i.fmt(p.tp1), "tp2": i.fmt(p.tp2),
            "sl_pips": _num(p.sl_pips, 1), "tp1_pips": _num(p.tp1_pips, 1), "tp2_pips": _num(p.tp2_pips, 1),
            "rr1": _num(p.rr1), "rr2": _num(p.rr2), "lots": _num(p.lots), "risk_amount": _num(p.risk_amount),
            "sl_basis": p.sl_basis, "tp1_basis": p.tp1_basis, "tp2_basis": p.tp2_basis,
        },
        "order_text": breakout_order_text(b, tz),
    }


def breakouts_result_dict(r: bk.BreakoutScan, tz_name: str = "America/Sao_Paulo", elapsed: float = 0.0) -> dict:
    tz = ZoneInfo(tz_name)
    loc = r.now.astimezone(tz)
    issues = [f"{k}: {v}" for k, v in {**r.status, **r.errors}.items() if v not in ("ok", "sintético")]
    if r.closed:
        issues.append(f"mercado fechado / sem cotação ao vivo: {', '.join(r.closed)}")
    items = [breakout_dict(b, tz, r.now) for b in r.breakouts]
    return {
        "ok": True,
        "timestamp": loc.strftime("%d/%m/%Y %H:%M:%S"),
        "time": loc.strftime("%H:%M:%S"),
        "session": r.session.label,
        "fx_open": r.session.fx_open,
        "metals_open": r.session.metals_open,
        "scanned": r.scanned,
        "new_count": r.new_count,
        "new_actionable": sum(1 for b in r.breakouts if b.is_new and b.actionable),
        "new_unblocked": sum(1 for b in r.breakouts if b.is_new and not b.blocked),
        "breakouts": items,
        "fills": [{"symbol": f["symbol"], "tf": f["tf"], "side": f["side"], "grade": f["grade"],
                   "limit": UNIVERSE_FMT(f["symbol"], f["limit"]), "sl": UNIVERSE_FMT(f["symbol"], f["sl"])}
                  for f in r.fills],
        "confirmations": r.confirmations,
        "profile": r.profile,
        "model": bk.model_summary(r.profile),
        "data_issues": issues,
        "elapsed_s": _num(elapsed, 1),
    }


def scan_breakouts(cache_dir: str, balance: float = 10_000.0, risk_pct: float = 1.0, assets: str = "all",
                   tz_name: str = "America/Sao_Paulo", listener=None, offline: bool = False,
                   plan: str = "mercado") -> str:
    """Light, fast scan for the real-time breakout monitor. Returns JSON."""
    def progress(pct: float, msg: str) -> None:
        if listener is not None:
            listener.onProgress(int(round(pct)), msg)

    t0 = time.time()
    try:
        s = Settings(balance=float(balance), risk_pct=float(risk_pct), cache_dir=cache_dir,
                     workers=6, offline=bool(offline),
                     breakout_plan=plan if plan in bk.MODEL_PATHS else "mercado")
        os.makedirs(cache_dir, exist_ok=True)
        eng = Engine(s)
        res = bk.scan(eng.provider, s, None if assets in (None, "", "all") else assets, eng.now(),
                      state_path=os.path.join(cache_dir, f"breakouts_state_{s.breakout_plan}.json"),
                      progress=progress)
        if res.scanned and not res.breakouts and len(res.errors) >= res.scanned:
            return json.dumps({"ok": False, "error": "Sem dados de mercado. Verifique a internet.",
                               "detail": "; ".join(f"{k}: {v}" for k, v in list(res.errors.items())[:6])},
                              ensure_ascii=False)
        return json.dumps(breakouts_result_dict(res, tz_name, time.time() - t0), ensure_ascii=False, default=str)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}",
                           "detail": traceback.format_exc()[-1500:]}, ensure_ascii=False)


# ---------------------------------------------------------------------------- single instrument

def _bars(df, n: int, digits: int) -> dict:
    sub = df.iloc[-n:]
    return {"t": [int(t.timestamp() * 1000) for t in sub.index],
            "o": [round(float(x), digits) for x in sub.o], "h": [round(float(x), digits) for x in sub.h],
            "l": [round(float(x), digits) for x in sub.l], "c": [round(float(x), digits) for x in sub.c]}


def asset_result_dict(r, tz_name: str = "America/Sao_Paulo", elapsed: float = 0.0) -> dict:
    from .analysis import indicators as ta
    from .analysis.fundamental import headline_sentiment

    tz = ZoneInfo(tz_name)
    inst, d, o = r.inst, r.data, r.opportunity
    loc = r.now.astimezone(tz)
    s = r.settings
    ccys = {inst.base, inst.quote} if not inst.is_metal else {inst.base, "USD"}
    f = d.frames
    h1 = f["H1"]
    atr_h1 = float(ta.atr(h1).iloc[-1])
    out = {
        "ok": True, "kind": "asset",
        "timestamp": loc.strftime("%d/%m/%Y %H:%M"), "weekday": DIAS[loc.weekday()],
        "symbol": inst.symbol, "name": inst.name or f"{inst.base}/{inst.quote}", "is_metal": inst.is_metal,
        "digits": inst.digits, "pip": inst.pip,
        "price": {"bid": inst.fmt(d.bid), "ask": inst.fmt(d.ask), "mid": inst.fmt(d.price),
                  "spread_pips": _num(inst.pips(d.ask - d.bid), 1), "time": d.quote_ts.astimezone(tz).strftime("%H:%M:%S"),
                  "source": d.quote_source},
        "tradeable": d.tradeable, "session": r.session.label, "notes": d.notes,
        "settings": {"balance": s.balance, "risk_pct": s.risk_pct, "plan": s.breakout_plan},
        "elapsed_s": _num(elapsed, 1),
    }
    if o is None:
        out["decision"] = {"execute": False, "headline": "Dados insuficientes", "reason": "histórico curto demais"}
        return out
    out["opportunity"] = opp_dict(o, tz, s.min_score)
    out["decision"] = ({"execute": True, "headline": f"{o.side} {o.symbol} a mercado",
                        "reason": f"Nota {o.grade} · {o.score:.0f}/100 · passou em todos os filtros"}
                       if o.executable else
                       {"execute": False, "headline": f"Não executar {o.symbol} agora",
                        "reason": (o.gates[0] if o.gates else f"score {o.score:.0f} abaixo do mínimo {s.min_score:.0f}")
                        + f" · melhor lado agora: {o.side.lower()}"})
    # multi-timeframe table
    mtf = []
    for tf, v in o.tech.views.items():
        stack = "alta" if v.ema8 > v.ema21 > v.ema50 else ("baixa" if v.ema8 < v.ema21 < v.ema50 else "mista")
        mtf.append({"tf": tf, "trend": _num(v.trend), "momentum": _num(v.momentum), "score": _num(v.score),
                    "rsi": _num(v.rsi, 0), "adx": _num(v.adx, 0), "emas": stack, "supertrend": v.st_dir,
                    "ichimoku": {1: "acima", -1: "abaixo", 0: "dentro"}[v.ichi],
                    "structure": {1: "HH/HL", -1: "LH/LL", 0: "mista"}[v.structure.trend],
                    "bos": v.structure.bos,
                    "candles": [c.name for c in v.candles],
                    "squeeze": None if v.squeeze is None else {"on": v.squeeze.on, "fired": v.squeeze.fired,
                                                                 "pct": _num(v.squeeze.width_pct, 0)},
                    "divergence": v.divergence_desc})
    out["mtf"] = mtf
    # key levels with distances
    lv = []
    for side, items in (("resistência", o.levels.above(d.price)[:4]), ("suporte", o.levels.below(d.price)[:4])):
        for z in items:
            lv.append({"side": side, "price": inst.fmt(z.price), "value": z.price, "strength": _num(z.strength, 1),
                       "labels": z.label(), "dist_pips": _num(inst.pips(abs(z.price - d.price)), 1),
                       "dist_atr": _num(abs(z.price - d.price) / atr_h1, 2)})
    out["levels"] = lv
    # daily context
    d1, w1 = f["D1"], f["W1"]
    adr = float(ta.atr(d1).iloc[-2]) if len(d1) > 15 else float((d1.h - d1.l).mean())
    prev = d1.iloc[-2] if len(d1) >= 2 else d1.iloc[-1]
    piv = (prev.h + prev.l + prev.c) / 3
    today = d1.iloc[-1]
    out["daily"] = {
        "adr_pips": _num(inst.pips(adr), 1), "today_pips": _num(inst.pips(float(today.h - today.l)), 1),
        "adr_used_pct": _num(o.day.get("adr_used", 0) * 100, 0), "move_today_adr": _num(o.day.get("move_today", 0)),
        "day_open": inst.fmt(float(today.o)), "prev_high": inst.fmt(float(prev.h)), "prev_low": inst.fmt(float(prev.l)),
        "prev_close": inst.fmt(float(prev.c)),
        "week_high": inst.fmt(float(w1.iloc[-2].h)) if len(w1) >= 2 else "",
        "week_low": inst.fmt(float(w1.iloc[-2].l)) if len(w1) >= 2 else "",
        "pivots": {"R2": inst.fmt(piv + (prev.h - prev.l)), "R1": inst.fmt(2 * piv - prev.l), "P": inst.fmt(piv),
                   "S1": inst.fmt(2 * piv - prev.h), "S2": inst.fmt(piv - (prev.h - prev.l))},
    }
    q = o.quant
    out["quant"] = {"regime": q.regime, "hurst": _num(q.hurst), "vr": _num(q.vr), "vr_z": _num(q.vr_z, 1),
                    "er": _num(q.er), "tsmom": _num(q.tsmom), "mr_z": _num(q.mr_z, 1),
                    "vol_pct": _num(q.vol_pct, 0), "vol_ann": _num(q.vol_ann, 1)}
    # currency strength and fundamentals
    order = [c for c, _ in r.strength.ranking]
    st = {}
    for c in (inst.base, inst.quote):
        if c in r.strength.scores:
            st[c] = {"z": _num(r.strength.scores[c]), "rank": order.index(c) + 1}
        elif c in r.strength.metal_z:
            st[c] = {"z": _num(r.strength.metal_z[c]), "rank": None}
    out["strength"] = st
    fr = o.fund
    out["fundamental"] = {
        "score": _num(fr.score, 0),
        "components": [{"name": k, "value": _num(v), "fact": fr.facts.get(k, "")} for k, v in fr.components.items()],
        "rates": {c: {"rate": _num(p.rate), "chg6m": _num(p.change_6m)} for c, p in (r.ctx.rates or {}).items()
                  if c in ccys},
        "cot": {c: {"net_pct": _num(x.net_pct_oi, 0), "index": _num(x.index_3y, 0), "chg4w": _num(x.chg_4w_pct, 1)}
                for c, x in (r.ctx.cot or {}).items() if c in ccys},
        "macro": r.fmodel.macro.notes,
    }
    evs = []
    for e in sorted(r.ctx.events or [], key=lambda x: x.time):
        mins = (e.time - r.now).total_seconds() / 60
        if e.ccy in ccys | {"ALL"} and e.impact in ("High", "Medium") and -120 <= mins <= 48 * 60:
            t = e.time.astimezone(tz)
            evs.append({"when": f"{DIAS[t.weekday()]} {t:%d/%m %H:%M}", "ccy": e.ccy, "title": e.title,
                        "impact": e.impact, "in": (f"em {mins / 60:.1f}h" if mins >= 60 else f"em {mins:.0f} min")
                        if mins >= 0 else f"há {-mins:.0f} min", "forecast": e.forecast, "previous": e.previous})
    out["events"] = evs[:12]
    heads = []
    for h in r.ctx.headlines or []:
        sent = headline_sentiment(h.title)
        if sent and set(sent) & ccys:
            # tone for the pair: good news for the base (or bad for the quote) points up
            pair_tone = sent.get(inst.base, 0.0) - sent.get(inst.quote, 0.0)
            heads.append({"when": h.time.astimezone(tz).strftime("%d/%m %H:%M"), "title": h.title,
                          "tone": int(np.sign(pair_tone))})
    out["headlines"] = heads[:8]
    out["breakouts"] = [breakout_dict(b, tz, r.now) for b in o.breakouts]
    # chart data and overlays
    out["chart"] = {"H1": _bars(h1, 120, inst.digits), "M15": _bars(f["M15"], 96, inst.digits)}
    p = o.plan
    out["overlay"] = {
        "levels": [z["value"] for z in lv],
        "plan": {"entry": p.entry, "sl": p.sl, "tp1": p.tp1, "tp2": p.tp2, "direction": o.direction,
                 "show": bool(o.executable), "exit_kind": p.exit_kind},
    }
    issues = [f"{k}: {v}" for k, v in {**r.ctx.status, **r.errors}.items() if v not in ("ok", "sintético")]
    out["data_issues"] = issues[:6]
    out["signal_model"] = sig_mod.model_summary() if s.use_edge else {"available": False}
    return out


def analyze_asset(cache_dir: str, symbol: str, balance: float = 10_000.0, risk_pct: float = 1.0,
                  plan: str = "mercado", tz_name: str = "America/Sao_Paulo", listener=None,
                  offline: bool = False, use_edge: bool = True, use_news: bool = True) -> str:
    """Deep analysis of one currency pair or metal. Returns JSON."""
    def progress(pct: float, msg: str) -> None:
        if listener is not None:
            listener.onProgress(int(round(pct)), msg)

    t0 = time.time()
    try:
        s = Settings(balance=float(balance), risk_pct=float(risk_pct), cache_dir=cache_dir, workers=6,
                     offline=bool(offline), use_edge=bool(use_edge), use_news=bool(use_news),
                     breakout_plan=plan if plan in bk.MODEL_PATHS else "mercado")
        progress(1, "Iniciando o motor")
        res = Engine(s).scan_asset(symbol, progress=progress)
        return json.dumps(asset_result_dict(res, tz_name, time.time() - t0), ensure_ascii=False, default=str)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}",
                           "detail": traceback.format_exc()[-1500:]}, ensure_ascii=False)


# ---------------------------------------------------------------------------- price explosions

LEVEL_LABEL = {"extrema": "EXTREMA", "alta": "ALTA", "elevada": "ELEVADA", "baixa": "NORMAL"}


def explosion_model_summary() -> dict:
    from .analysis import explosion as exm
    m = exm.load_model()
    if m is None:
        return {"available": False}
    i, t = m.info, m.info.get("test", {})
    wf = i.get("walk_forward", [])
    return {
        "available": True, "validated": m.validated, "period": i.get("period", ""), "bars": i.get("bars", 0),
        "instruments": i.get("instruments", 0), "test_period": i.get("test_period", ""),
        "theta": m.theta, "horizon": m.horizon, "alert_pct": round(float(i.get("alert_q", 0.05)) * 100),
        "base_rate": t.get("base"), "test_precision": t.get("prec_alert"), "test_lift": t.get("lift"),
        "test_precision_seasonal": t.get("prec_seasonal_alert"), "test_precision_extreme": t.get("prec_extrema"),
        "test_n_alert": t.get("n_alert"), "test_auc": t.get("auc"), "test_auc_seasonal": t.get("auc_seas"),
        "test_p_mean": t.get("p_mean_alert"), "test_move_alert": t.get("move_median_alert"),
        "test_move_all": t.get("move_median_all"),
        "wf_lift_min": min((r["lift"] for r in wf), default=None),
        "wf_lift_mean": round(float(np.mean([r["lift"] for r in wf])), 2) if wf else None,
        "wf_squeeze_precision": round(float(np.mean([r["prec_squeeze"] for r in wf if r.get("prec_squeeze")])), 3)
        if wf else None,
        "direction_useful": bool(i.get("dir_useful", False)),
        "direction_auc": round(float(np.mean(i.get("dir_auc_wf", [0.5]))), 3),
        "bracket_validated": bool(m.bracket.get("validated", False)),
        "bracket_wf_mean_r": m.bracket.get("wf_mean_r"), "bracket_test": t.get("oco", {}),
    }


def explosion_dict(a, tz: ZoneInfo, now) -> dict:
    i, p = a.inst, a.plan
    mins_left = max(0, int((a.until - now).total_seconds() // 60))
    side = None if a.p_up is None else ("alta" if a.p_up >= 0.5 else "baixa")
    mid = (a.bid + a.ask) / 2
    lo, hi = mid - a.move_median, mid + a.move_median
    order = [f"⚡ {i.symbol}: {a.p * 100:.0f}% de chance de explosão até {a.until.astimezone(tz):%H:%M} "
             f"(nível {LEVEL_LABEL[a.level].lower()})",
             f"Movimento típico ≈ {i.pips(a.move_median):.0f} pips · alcance provável {i.fmt(lo)} – {i.fmt(hi)}",
             "Direção não prevista pelo modelo: aguarde confirmação antes de entrar.",
             f"Preço agora: bid {i.fmt(a.bid)} / ask {i.fmt(a.ask)}"]
    return {
        "symbol": i.symbol, "name": i.name or f"{i.base}/{i.quote}", "is_metal": i.is_metal,
        "p": _num(a.p, 3), "level": a.level, "level_label": LEVEL_LABEL[a.level], "alert": a.alert,
        "p_up": _num(a.p_up, 3), "side": side,
        "adr_pips": _num(i.pips(a.adr), 1), "move_pips": _num(i.pips(a.move_median), 1),
        "move_adr": _num(a.move_median / a.adr, 2),
        "bid": i.fmt(a.bid), "ask": i.fmt(a.ask), "quote_time": a.quote_ts.astimezone(tz).strftime("%H:%M:%S"),
        "tradeable": a.tradeable, "until": a.until.astimezone(tz).strftime("%H:%M"), "minutes_left": mins_left,
        "drivers": a.drivers, "events": a.events,
        "range_low": i.fmt(lo), "range_high": i.fmt(hi),
        "plan": {"buy_stop": i.fmt(p["buy_stop"]), "sell_stop": i.fmt(p["sell_stop"]),
                 "buy_sl": i.fmt(p["buy_sl"]), "sell_sl": i.fmt(p["sell_sl"]),
                 "buy_tp": i.fmt(p["buy_tp"]) if p["buy_tp"] else "", "sell_tp": i.fmt(p["sell_tp"]) if p["sell_tp"] else "",
                 "risk_pips": _num(i.pips(p["risk"]), 1), "lots": _num(p["lots"]), "risk_amount": _num(p["risk_amount"]),
                 "exit_rule": p["exit_rule"], "stop_rule": p["stop_rule"], "hold_h": p["hold_h"],
                 "validated": p["validated"]},
        "order_text": "\n".join(order),
    }


def scan_explosions(cache_dir: str, balance: float = 10_000.0, risk_pct: float = 1.0, assets: str = "all",
                    tz_name: str = "America/Sao_Paulo", listener=None, offline: bool = False) -> str:
    """Probability of a price explosion in the next hours for every instrument. Returns JSON."""
    from . import explosions as xp
    from . import sessions

    def progress(done: int, total: int) -> None:
        if listener is not None:
            listener.onProgress(int(round(5 + 90 * done / max(total, 1))), f"Medindo volatilidade: {done}/{total}")

    t0 = time.time()
    try:
        s = Settings(balance=float(balance), risk_pct=float(risk_pct), cache_dir=cache_dir, workers=6,
                     offline=bool(offline))
        os.makedirs(cache_dir, exist_ok=True)
        alerts, errors, now = xp.scan(s, None if assets in (None, "", "all") else assets, progress=progress)
        if not alerts:
            return json.dumps({"ok": False, "error": "Sem dados de mercado. Verifique a internet.",
                               "detail": "; ".join(f"{k}: {v}" for k, v in list(errors.items())[:6])},
                              ensure_ascii=False)
        tz = ZoneInfo(tz_name)
        loc = now.astimezone(tz)
        sess = sessions.state(now)
        nxt = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).astimezone(tz)
        return json.dumps({
            "ok": True, "kind": "explosions", "timestamp": loc.strftime("%d/%m/%Y %H:%M"),
            "weekday": DIAS[loc.weekday()], "session": sess.label, "fx_open": sess.fx_open,
            "metals_open": sess.metals_open, "scanned": len(alerts),
            "alerts": sum(1 for a in alerts if a.alert),
            "next_update": nxt.strftime("%H:%M"),
            "items": [explosion_dict(a, tz, now) for a in alerts],
            "model": explosion_model_summary(),
            "data_issues": [f"{k}: {v}" for k, v in errors.items()][:6],
            "elapsed_s": round(time.time() - t0, 1),
        }, ensure_ascii=False, default=str)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}",
                           "detail": traceback.format_exc()[-1500:]}, ensure_ascii=False)

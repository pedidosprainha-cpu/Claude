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
from datetime import timedelta
from zoneinfo import ZoneInfo

from . import breakouts as bk
from .config import Settings
from .engine import Engine, Opportunity, ScanResult

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
        f"Alvo 1: {i.fmt(p.tp1)} ({p.rr1:.2f}R) - realizar 50% e stop na entrada",
        f"Alvo 2: {i.fmt(p.tp2)} ({p.rr2:.2f}R)",
        f"Lote: {p.lots:.2f} (risco US$ {p.risk_amount:,.2f})",
        f"Invalidação: {p.invalidation}",
    ]
    return "\n".join(lines)


def opp_dict(o: Opportunity, tz: ZoneInfo, min_score: float) -> dict:
    p, i, e = o.plan, o.inst, o.edge
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
        "edge": None if e is None else {
            "p": _num(e.p_post, 3), "raw": _num(e.win_rate, 3), "n": e.n,
            "exp_r": _num(e.exp_post_r), "pf": _num(e.profit_factor), "avg_h": _num(e.avg_bars, 0),
        },
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

def breakout_order_text(b: bk.Breakout) -> str:
    p, i = b.plan, b.inst
    return "\n".join([
        f"{b.side} {b.symbol} a mercado — {bk.STATUS_LABEL[b.status].lower()} ({b.tf})",
        f"Nível: {i.fmt(b.level.price)} ({b.level.label})",
        f"Entrada: {i.fmt(p.entry)}",
        f"Stop loss: {i.fmt(p.sl)} ({p.sl_pips:.1f} pips)",
        f"Alvo 1: {i.fmt(p.tp1)} ({p.rr1:.2f}R) - realizar 50% e stop na entrada",
        f"Alvo 2: {i.fmt(p.tp2)} ({p.rr2:.2f}R)",
        f"Lote: {p.lots:.2f} (risco US$ {p.risk_amount:,.2f})",
    ])


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
        "quality": _num(b.quality, 1),
        "grade": b.grade,
        "pros": b.pros,
        "cons": b.cons,
        "hist": {"n": b.hist_n, "wins": b.hist_wins, "p": _num(b.hist_p, 3)} if b.hist_n >= 8 else None,
        "plan": {
            "entry": i.fmt(p.entry), "sl": i.fmt(p.sl), "tp1": i.fmt(p.tp1), "tp2": i.fmt(p.tp2),
            "sl_pips": _num(p.sl_pips, 1), "tp1_pips": _num(p.tp1_pips, 1), "tp2_pips": _num(p.tp2_pips, 1),
            "rr1": _num(p.rr1), "rr2": _num(p.rr2), "lots": _num(p.lots), "risk_amount": _num(p.risk_amount),
            "sl_basis": p.sl_basis, "tp1_basis": p.tp1_basis, "tp2_basis": p.tp2_basis,
        },
        "order_text": breakout_order_text(b),
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
        "breakouts": items,
        "data_issues": issues,
        "elapsed_s": _num(elapsed, 1),
    }


def scan_breakouts(cache_dir: str, balance: float = 10_000.0, risk_pct: float = 1.0, assets: str = "all",
                   tz_name: str = "America/Sao_Paulo", listener=None, offline: bool = False) -> str:
    """Light, fast scan for the real-time breakout monitor. Returns JSON."""
    def progress(pct: float, msg: str) -> None:
        if listener is not None:
            listener.onProgress(int(round(pct)), msg)

    t0 = time.time()
    try:
        s = Settings(balance=float(balance), risk_pct=float(risk_pct), cache_dir=cache_dir,
                     workers=6, offline=bool(offline))
        os.makedirs(cache_dir, exist_ok=True)
        eng = Engine(s)
        res = bk.scan(eng.provider, s, None if assets in (None, "", "all") else assets, eng.now(),
                      state_path=os.path.join(cache_dir, "breakouts_state.json"), progress=progress)
        if res.scanned and not res.breakouts and len(res.errors) >= res.scanned:
            return json.dumps({"ok": False, "error": "Sem dados de mercado. Verifique a internet.",
                               "detail": "; ".join(f"{k}: {v}" for k, v in list(res.errors.items())[:6])},
                              ensure_ascii=False)
        return json.dumps(breakouts_result_dict(res, tz_name, time.time() - t0), ensure_ascii=False, default=str)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}",
                           "detail": traceback.format_exc()[-1500:]}, ensure_ascii=False)

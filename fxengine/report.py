"""Human (terminal / Markdown) and machine (JSON) reports — in Portuguese."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .engine import Opportunity, ScanResult

DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
COMP_LABEL = {"technical": "técnico", "quant": "quant", "strength": "força", "fundamental": "fundamental"}
LINE = "═" * 104
THIN = "─" * 104


def _t(dt: datetime, tz: str) -> str:
    loc = dt.astimezone(ZoneInfo(tz))
    return f"{DIAS[dt.weekday()]} {dt:%d/%m/%Y %H:%M} UTC ({loc:%H:%M} {loc.tzname()})"


def _short(dt: datetime, tz: str) -> str:
    loc = dt.astimezone(ZoneInfo(tz))
    return f"{DIAS[dt.weekday()]} {dt:%d/%m %H:%M} UTC ({loc:%H:%M} local)"


def _pct(x: float | None) -> str:
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x * 100:.0f}%"


def _bar(v: float, scale: float = 1.5, width: int = 12) -> str:
    n = int(round(min(abs(v) / scale, 1) * width))
    return ("█" * n).ljust(width) if v >= 0 else ("░" * n).ljust(width)


def _status(o: Opportunity, min_score: float) -> str:
    if o.executable:
        return "✔ executável"
    if o.gates:
        return "✖ " + o.gates[0]
    return f"✖ score < {min_score:.0f}"


def plan_lines(o: Opportunity, tz: str) -> list[str]:
    p, i = o.plan, o.inst
    d = o.direction
    side_px = "compra no ask" if d == 1 else "venda no bid"
    L = [
        f"  Preço spot   bid {i.fmt(o.bid)} / ask {i.fmt(o.ask)}  (spread {o.spread_pips:.1f} pips · "
        f"{o.quote_source} {o.quote_ts:%H:%M:%S} UTC)",
        f"  Entrada      {i.fmt(p.entry)}  ({side_px}, execução imediata a mercado)",
        f"  Stop loss    {i.fmt(p.sl)}  ({-p.sl_pips if d == 1 else p.sl_pips:+.1f} pips · {p.sl_atr_h1:.1f}× ATR H1) — {p.sl_basis}",
        f"  Alvo 1       {i.fmt(p.tp1)}  ({p.tp1_pips * d:+.1f} pips · {p.rr1:.2f}R) — {p.tp1_basis}"
        " → realizar 50% e mover stop p/ entrada",
        f"  Alvo 2       {i.fmt(p.tp2)}  ({p.tp2_pips * d:+.1f} pips · {p.rr2:.2f}R) — {p.tp2_basis}",
        f"  Tamanho      {p.lots:.2f} lote · risco {o_ccy(o)} {p.risk_amount:,.2f} · valor do pip/lote "
        f"{o_ccy(o)} {p.pip_value_lot:,.2f}",
    ]
    if o.edge is not None:
        e = o.edge
        L.append(f"  Edge hist.   P(TP1 antes do SL) ≈ {e.p_post * 100:.0f}% (bruto {e.win_rate * 100:.0f}%, n={e.n} "
                 f"sinais semelhantes em 1 ano H1) · expectativa {e.exp_post_r:+.2f}R · PF {e.profit_factor:.2f}"
                 f" · duração média {e.avg_bars:.0f}h")
    L.append(f"  Invalidação  {p.invalidation}")
    return L


def o_ccy(o: Opportunity) -> str:
    return "US$"


def decomposition(o: Opportunity) -> list[str]:
    comps = " | ".join(f"{COMP_LABEL[k]} {v:+.0f}" for k, v in o.components.items())
    mults = " · ".join(f"{k} ×{v:.2f}" for k, (v, _) in o.multipliers.items())
    return [f"  Score: {comps} → composto {o.composite:+.1f}",
            f"  Ajustes: {mults} → {o.score:.1f}/100 (nota {o.grade})"]


def _tf_table(o: Opportunity) -> list[str]:
    rows = ["  TF    tendência momentum  score   RSI   ADX  EMA8/21/50   ST  Ichimoku  estrutura"]
    for tf, v in o.tech.views.items():
        stack = "▲▲" if v.ema8 > v.ema21 > v.ema50 else ("▼▼" if v.ema8 < v.ema21 < v.ema50 else "~~")
        ichi = {1: "acima", -1: "abaixo", 0: "dentro"}[v.ichi]
        stru = {1: "HH/HL", -1: "LH/LL", 0: "mista"}[v.structure.trend]
        bos = f" BOS{'+' if v.structure.bos > 0 else '−'}" if v.structure.bos else ""
        rows.append(f"  {tf:<4} {v.trend:+9.2f} {v.momentum:+8.2f} {v.score:+6.2f} {v.rsi:5.0f} {v.adx:5.0f}"
                    f"      {stack}      {'+' if v.st_dir > 0 else '−'}   {ichi:<8}  {stru}{bos}")
    return rows


def render_text(r: ScanResult, tz: str = "America/Sao_Paulo", detail: bool = False) -> str:
    s = r.settings
    out = [LINE,
           f" FXENGINE · análise gráfica + quantitativa + fundamentalista em tempo real · {_t(r.now, tz)}",
           f" Sessão: {r.session.label} | Apetite a risco: {r.macro.risk_label} ({r.macro.risk:+.2f}) | "
           f"Ativos analisados: {len(r.opportunities)}",
           LINE]

    best = r.best
    if best:
        out.append(f"▶ MELHOR OPORTUNIDADE AGORA — {best.side} {best.symbol} A MERCADO    "
                   f"Nota {best.grade} ({best.score:.0f}/100)")
        out += plan_lines(best, tz)
    else:
        out.append("▶ NENHUMA ENTRADA A MERCADO RECOMENDADA NESTE INSTANTE")
        top = r.top
        if top:
            why = "; ".join(top.gates) if top.gates else f"score {top.score:.0f} abaixo do mínimo {s.min_score:.0f}"
            out.append(f"  Melhor candidato: {top.side} {top.symbol} (nota {top.grade}, {top.score:.0f}/100) — NÃO executar: {why}")
            out += plan_lines(top, tz)
        best = top
    if best:
        out.append("")
        out.append("  Por que:")
        out += [f"   • {x}" for x in best.reasons[:10]]
        if best.warnings or best.data_notes:
            out.append("  Riscos / atenção:")
            out += [f"   • {x}" for x in (best.warnings + best.data_notes)[:10]]
        out += decomposition(best)
        if detail:
            out.append("")
            out += _tf_table(best)
        alts = [o for o in r.opportunities if o.symbol != best.symbol and o.executable
                and abs(r.correlations.get(o.symbol, 0)) < 0.6][:3]
        if alts:
            out.append("  Alternativas executáveis pouco correlacionadas: " +
                       ", ".join(f"{o.side.lower()} {o.symbol} ({o.score:.0f})" for o in alts))
        dup = [k for k, v in sorted(r.correlations.items(), key=lambda kv: -kv[1]) if v > 0.75][:4]
        if dup:
            out.append("  Exposição equivalente (não somar posições): " + ", ".join(dup))

    out += ["", THIN, f" RANKING (top {s.top_n})", THIN,
            "  #  Ativo   Lado    Score Nota  Téc  Quant Força  Fund  Regime            R:R1  P(TP1)  Status"]
    for k, o in enumerate(r.opportunities[: s.top_n], 1):
        c = o.components
        out.append(f" {k:>2}  {o.symbol:<7} {o.side:<6} {o.score:6.1f}  {o.grade:<3} {c['technical']:+5.0f} {c['quant']:+5.0f}"
                   f" {c['strength']:+5.0f} {c['fundamental']:+5.0f}  {o.quant.regime:<17} {o.plan.rr1:4.2f}"
                   f"  {_pct(o.edge.p_post if o.edge else None):>5}   {_status(o, s.min_score)}")

    out += ["", THIN, " FORÇA RELATIVA DAS MOEDAS (z-score ponderado 4h/24h/5d, 28 cruzamentos)", THIN]
    for c, v in r.strength.ranking:
        h = r.strength.by_horizon
        out.append(f"  {c}  {v:+.2f}  {_bar(v)}   4h {h['4h'][c]:+.2f} · 24h {h['24h'][c]:+.2f} · 5d {h['5d'][c]:+.2f}")
    if r.strength.metal_z:
        out.append("  Metais vs USD: " + " · ".join(f"{k} {v:+.2f}σ" for k, v in r.strength.metal_z.items()))

    out += ["", THIN, " CONTEXTO MACRO / FUNDAMENTAL", THIN]
    out += [f"  • {n}" for n in r.macro.notes]
    if r.ctx.rates:
        src = next(iter(r.ctx.rates.values())).source
        out.append(f"  • Juros de política ({src}): " + " · ".join(
            f"{c} {p.rate:.2f}%{'' if abs(p.change_6m) < 1e-9 else f' ({p.change_6m:+.2f} 6m)'}"
            for c, p in sorted(r.ctx.rates.items(), key=lambda kv: -kv[1].rate)))
    if r.ctx.cot:
        some = next(iter(r.ctx.cot.values()))
        out.append(f"  • COT CFTC ({some.date}), especuladores líquido % OI [índice 3a]: " + " · ".join(
            f"{a} {c.net_pct_oi:+.0f}% [{c.index_3y:.0f}]" for a, c in r.ctx.cot.items()))

    out += ["", THIN, " AGENDA DE ALTO IMPACTO (próximas 48h)", THIN]
    ev = sorted((e for e in r.ctx.events if e.impact == "High"
                 and r.now - timedelta(hours=1) <= e.time <= r.now + timedelta(hours=48)), key=lambda e: e.time)
    if ev:
        for e in ev[:12]:
            mins = (e.time - r.now).total_seconds() / 60
            when = f"em {mins / 60:.1f}h" if mins >= 0 else f"há {-mins:.0f} min"
            extra = " · ".join(x for x in (f"proj {e.forecast}" if e.forecast else "", f"ant {e.previous}" if e.previous else "") if x)
            out.append(f"  {_short(e.time, tz)}  {e.ccy:<4} {e.title[:34]:<34} {when:<10} {extra}")
    else:
        out.append("  (nenhum evento de alto impacto)" if r.ctx.status.get("calendar") in ("ok", "sintético")
                   else f"  agenda indisponível: {r.ctx.status.get('calendar')}")

    if r.ctx.headlines:
        out += ["", THIN, " MANCHETES RECENTES (Investing.com)", THIN]
        for h in r.ctx.headlines[:8]:
            out.append(f"  {h.time:%d/%m %H:%M}  {h.title[:95]}")

    bad = {k: v for k, v in {**r.ctx.status, **r.errors}.items() if v not in ("ok", "sintético")}
    if bad:
        out += ["", " Falhas de dados: " + "; ".join(f"{k}: {v[:80]}" for k, v in list(bad.items())[:8])]
    out += ["", " Fontes: candles Yahoo Finance · bid/ask spot Swissquote · juros BIS · posicionamento CFTC · "
                "agenda ForexFactory · manchetes Investing.com",
            " Aviso: análise automatizada e probabilística — não é recomendação de investimento. Confirme preço,",
            " spread e agenda na sua plataforma antes de executar; respeite o stop. Alavancagem pode gerar perdas > depósito.",
            LINE]
    return "\n".join(out)


def render_markdown(r: ScanResult, tz: str = "America/Sao_Paulo") -> str:
    txt = render_text(r, tz, detail=True)
    head = f"# FXENGINE — Varredura {r.now:%Y-%m-%d %H:%M} UTC\n\n"
    return head + "```text\n" + txt + "\n```\n"


def _opp_dict(o: Opportunity) -> dict:
    p = o.plan
    return {
        "symbol": o.symbol, "side": "buy" if o.direction == 1 else "sell", "score": round(o.score, 2),
        "grade": o.grade, "executable": o.executable, "gates": o.gates,
        "price": {"bid": o.bid, "ask": o.ask, "mid": o.price, "spread_pips": round(o.spread_pips, 2),
                  "ts": o.quote_ts.isoformat(), "source": o.quote_source},
        "plan": {"entry": p.entry, "sl": p.sl, "tp1": p.tp1, "tp2": p.tp2, "rr1": round(p.rr1, 2),
                 "rr2": round(p.rr2, 2), "sl_pips": round(p.sl_pips, 1), "tp1_pips": round(p.tp1_pips, 1),
                 "tp2_pips": round(p.tp2_pips, 1), "lots": p.lots, "risk_amount": p.risk_amount,
                 "sl_basis": p.sl_basis, "tp1_basis": p.tp1_basis, "tp2_basis": p.tp2_basis,
                 "invalidation": p.invalidation},
        "components": {k: round(v, 1) for k, v in o.components.items()},
        "composite": round(o.composite, 2),
        "multipliers": {k: {"value": round(v, 3), "note": n} for k, (v, n) in o.multipliers.items()},
        "regime": o.quant.regime, "hurst": round(o.quant.hurst, 3), "variance_ratio": round(o.quant.vr, 3),
        "edge": None if o.edge is None else {
            "n": o.edge.n, "win_rate": round(o.edge.win_rate, 3), "p_post": round(o.edge.p_post, 3),
            "expectancy_r": round(o.edge.expectancy_r, 3), "exp_post_r": round(o.edge.exp_post_r, 3),
            "profit_factor": round(o.edge.profit_factor, 2) if math.isfinite(o.edge.profit_factor) else None},
        "setups": [{"name": s.name, "direction": s.direction, "quality": round(s.quality, 2)} for s in o.tech.setups],
        "reasons": o.reasons, "warnings": o.warnings, "data_notes": o.data_notes,
    }


def to_json(r: ScanResult) -> str:
    d = {
        "timestamp_utc": r.now.isoformat(),
        "session": r.session.label,
        "risk_sentiment": {"value": round(r.macro.risk, 3), "label": r.macro.risk_label},
        "best": _opp_dict(r.best) if r.best else None,
        "top_candidate": _opp_dict(r.top) if r.top else None,
        "ranking": [_opp_dict(o) for o in r.opportunities],
        "currency_strength": {k: round(v, 3) for k, v in r.strength.ranking},
        "metal_momentum_z": {k: round(v, 3) for k, v in r.strength.metal_z.items()},
        "events_48h": [{"time": e.time.isoformat(), "ccy": e.ccy, "title": e.title, "impact": e.impact,
                        "forecast": e.forecast, "previous": e.previous}
                       for e in r.ctx.events if e.impact == "High" and r.now <= e.time <= r.now + timedelta(hours=48)],
        "headlines": [{"time": h.time.isoformat(), "title": h.title} for h in r.ctx.headlines[:20]],
        "data_status": {**r.ctx.status, **r.errors},
    }
    return json.dumps(d, ensure_ascii=False, indent=1, default=str)

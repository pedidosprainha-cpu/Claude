"""Renderização textual (terminal) do resultado de uma análise."""
from __future__ import annotations


def render_text(res: dict) -> str:
    L = []
    a = L.append
    a("=" * 78)
    a(f"FXINTEL — ANALISAR MERCADO AGORA  |  {res['created_at'][:19]} UTC  |  {res['elapsed_ms']} ms")
    a("=" * 78)
    a(res["headline"])
    s = res.get("signal")
    if s:
        a("")
        rq = s["reference_quote"]
        rows = [
            ("Instrumento", s["instrument"]), ("Direção", s["direction"]), ("Execução", s["execution_type"]),
            ("Cotação", f"bid {rq['bid']} / ask {rq['ask']} ({rq['spread_pips']} pips, {rq['spread_source']}) "
                        f"{rq['time'][11:19]} UTC, {rq['source']}"),
            ("Entrada", f"{s['entry']['price']} ({s['entry']['side']})"),
            ("Stop Loss", f"{s['stop_loss']['price']} ({s['stop_loss']['pips']} pips)"),
            ("Take Profit", " | ".join(f"{t['label']}: {t['price']} ({t['rr']}R)" for t in s["take_profit"])),
            ("Risco-retorno", f"TP1 {s['risk_reward']['rr_tp1']}R; líquido {s['risk_reward']['rr_net_tp1']}R; "
                              f"custo {s['risk_reward']['cost_r']}R"),
            ("Probabilidade", f"{s['probability']['calibrated_p']} (IC90 {s['probability']['ci90']}) — "
                              f"{s['probability']['event']}"),
            ("Valor esperado", f"{s['expected_value_r']} R"),
            ("Confiança", f"{s['confidence']['level']} — " + "; ".join(s["confidence"]["limitations"])),
            ("Validade", f"até {s['validity']['valid_until'][11:16]} UTC ({s['validity']['minutes']} min)"),
            ("Score", s["score"]),
        ]
        for k, v in rows:
            a(f"  {k:15s} {v}")
        sz = (s.get("risk") or {}).get("sizing") or {}
        if sz.get("ok"):
            a(f"  {'Tamanho':15s} {sz['lots']} lote(s) — risco {sz['risk_amount']} {sz['account_currency']} "
              f"({sz['risk_pct']}%)")
        a("\n  Justificativa técnica:")
        for t in s["justification"]["technical"]:
            a(f"   - {t}")
        a("  Justificativa fundamentalista:")
        for t in s["justification"]["fundamental"]:
            a(f"   - {t}")
        a("  Invalidação:")
        for t in s["invalidation"]:
            a(f"   - {t}")
    else:
        a("")
        for r in res.get("no_signal_reasons", []):
            a(f"  • {r}")
    rk = res.get("ranking") or []
    if rk:
        lbl = {"SINAL": "SINAL", "ELEGIVEL": "ELEGÍVEL", "OBSERVACAO": "OBSERVAÇÃO",
               "AGUARDANDO_GATILHO": "AGUARDANDO GATILHO"}
        nan = float("nan")
        a("\nRANKING — 5 melhores oportunidades (nota 0–100):")
        a(f"  {'#':>2} {'Ativo':7} {'Dir':4} {'Nota':>5}  {'Status':19} {'EV':>7} {'Prob':>6} {'R:R':>5}  Entrada / SL / TP1")
        for c in rk:
            p = c["probability"].get("calibrated_p")
            ev = c["expected_value_r"] if c["expected_value_r"] is not None else nan
            rr = c["risk_reward"]["rr_tp1"] if c["risk_reward"]["rr_tp1"] is not None else nan
            a(f"  {c['rank']:>2} {c['instrument']:7} {c['direction']:4} {c['score']:>5.1f}  "
              f"{lbl.get(c['status'], '-'):19} {ev:>+6.2f}R {(p * 100 if p is not None else nan):>5.1f}% {rr:>5.2f}  "
              f"{c['entry']['price']} / {c['stop_loss']['price']} / {c['take_profit'][0]['price']}")
            if c["status"] != "SINAL":
                a(f"      bloqueios: {', '.join(c.get('blocked_by', []))}")
    m = res.get("model", {})
    a(f"\nModelo: {'validado' if m.get('validated') else 'NÃO validado'} | "
      f"OOS {m.get('oos_metrics', {}) and {k: round(v, 4) for k, v in m['oos_metrics'].items() if k in ('bss', 'auc', 'n')}}")
    a("\n" + res["disclaimer"])
    return "\n".join(L)

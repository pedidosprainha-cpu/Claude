"""Viés fundamentalista direcional por instrumento, com decomposição explicável.

O score é uma síntese *heurística* (pesos definidos a priori, não otimizados), em [-1, 1]:
positivo favorece a compra do ativo base. Ele entra na pontuação multifatorial com peso
limitado e é apresentado de forma decomposta para auditoria. Componentes sem série
histórica point-in-time (taxas básicas e viés dos BCs) NÃO entram no modelo estatístico.
"""
from __future__ import annotations

import math

from .. import instruments as I
from .central_banks import carry
from .macro import RISK_BETA


def _t(x: float | None, scale: float = 1.0) -> float:
    if x is None or not math.isfinite(x):
        return 0.0
    return math.tanh(x / scale)


def fundamental_bias(inst: I.Instrument, macro: dict, strength: dict, cb_table: dict) -> dict:
    comps: list[dict] = []

    def add(name: str, value: float, weight: float, text: str):
        comps.append({"factor": name, "value": round(value, 3), "weight": weight,
                      "contribution": round(value * weight, 4), "text": text})

    base, quote = inst.base, inst.quote
    if inst.kind == "fx":
        ci = carry(base, quote, cb_table)
        if ci:
            add("diferencial_juros", _t(ci["diff_pp"], 2.0), 0.22,
                f"Taxa {ci['bank_base']} {ci['rate_base']:.2f}% vs {ci['bank_quote']} "
                f"{ci['rate_quote']:.2f}% (diferencial {ci['diff_pp']:+.2f} p.p.)")
            if ci["stance_diff"]:
                add("viés_política", ci["stance_diff"] / 2, 0.13,
                    "Viés relativo de política monetária "
                    + ("mais hawkish no ativo base" if ci["stance_diff"] > 0 else "mais hawkish na moeda cotada"))
    else:
        d10 = macro.get("us10y_d120")
        add("juros_reais_proxy", -_t(d10, 1.5), 0.25,
            f"Variação de 5 dias do Treasury 10a (z={d10:+.2f}): " if d10 is not None else "Treasury 10a indisponível")
        dx = macro.get("dxy_r120")
        add("dólar", -_t(dx, 1.5), 0.20,
            f"Momento de 5 dias do DXY (z={dx:+.2f}); dólar forte pressiona metais" if dx is not None else "DXY indisponível")

    s1, s5 = strength.get("str_diff_24"), strength.get("str_diff_120")
    if s1 is not None or s5 is not None:
        v = 0.5 * _t(s1, 1.5) + 0.5 * _t(s5, 1.5)
        add("força_relativa", v, 0.25,
            f"Medidor de força relativa base−cotada: 1d z={s1 if s1 is not None else float('nan'):+.2f}, "
            f"5d z={s5 if s5 is not None else float('nan'):+.2f}")

    ro = macro.get("risk_on")
    beta = RISK_BETA.get(base, 0) - RISK_BETA.get(quote, 0)
    if ro is not None and beta:
        add("sentimento_risco", _t(ro, 1.5) * max(-1, min(1, beta / 1.5)), 0.15,
            f"Sentimento de risco {'positivo (risk-on)' if ro > 0 else 'negativo (risk-off)'} "
            f"(índice {ro:+.2f}; VIX {macro.get('vix_lvl') or float('nan'):.1f}); sensibilidade do par {beta:+.1f}")

    if "USD" in (base, quote) and inst.kind == "fx":
        dx = macro.get("dxy_r120")
        y5 = macro.get("us5y_d120")
        if dx is not None:
            sign = 1 if base == "USD" else -1
            v = sign * (0.6 * _t(dx, 1.5) + 0.4 * _t(y5, 1.5))
            add("macro_eua", v, 0.15,
                f"DXY 5d z={dx:+.2f}, Treasury 5a 5d z={(y5 if y5 is not None else 0):+.2f}")

    if "CAD" in (base, quote):
        w = macro.get("wti_r120")
        if w is not None:
            sign = 1 if base == "CAD" else -1
            add("petróleo", sign * _t(w, 1.5), 0.10, f"Petróleo WTI 5d z={w:+.2f} (CAD é moeda de commodity)")

    tot_w = sum(c["weight"] for c in comps) or 1.0
    score = sum(c["contribution"] for c in comps) / tot_w
    return {"score": round(max(-1.0, min(1.0, score)), 3), "components": comps}

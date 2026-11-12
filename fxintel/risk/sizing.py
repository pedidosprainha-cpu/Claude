"""Dimensionamento de posição proporcional ao capital e ao risco máximo autorizado."""
from __future__ import annotations

import math

from .. import instruments as I
from ..data.models import Quote


def conversion_rate(ccy_from: str, ccy_to: str, quotes: dict[str, Quote]) -> float | None:
    """Taxa para converter 1 unidade de ccy_from em ccy_to usando as cotações disponíveis."""
    if ccy_from == ccy_to:
        return 1.0
    direct = f"{ccy_from}{ccy_to}"
    inverse = f"{ccy_to}{ccy_from}"
    if direct in quotes:
        return quotes[direct].mid
    if inverse in quotes and quotes[inverse].mid > 0:
        return 1.0 / quotes[inverse].mid
    # via USD
    if ccy_from != "USD" and ccy_to != "USD":
        a = conversion_rate(ccy_from, "USD", quotes)
        b = conversion_rate("USD", ccy_to, quotes)
        if a and b:
            return a * b
    return None


def position_size(inst: I.Instrument, entry: float, stop: float, equity: float, risk_pct: float,
                  account_ccy: str, quotes: dict[str, Quote], risk_cfg: dict, leverage: float = 30,
                  slippage: float = 0.0) -> dict:
    dist = abs(entry - stop) + slippage
    conv = conversion_rate(inst.quote, account_ccy, quotes)
    if not conv or dist <= 0:
        return {"ok": False, "reason": f"sem taxa de conversão {inst.quote}->{account_ccy}"}
    risk_amt = equity * risk_pct / 100.0
    units = risk_amt / (dist * conv)
    lots_raw = units / inst.contract_size
    step = risk_cfg.get("lot_step", 0.01)
    lots = round(math.floor(lots_raw / step + 1e-9) * step, 8)  # tolerância a erro de ponto flutuante
    lots = min(lots, risk_cfg.get("max_lot", 50.0))
    if lots < risk_cfg.get("min_lot", 0.01):
        return {"ok": False, "reason": (f"posição mínima ({risk_cfg.get('min_lot', 0.01)} lote) excederia o "
                                        f"risco autorizado: lote calculado {lots_raw:.4f}"),
                "lots_raw": lots_raw}
    units_final = lots * inst.contract_size
    actual_risk = units_final * dist * conv
    notional = units_final * entry * conv
    margin = notional / max(leverage, 1)
    pip_value = units_final * inst.pip * conv
    return {
        "ok": True, "lots": round(lots, 2), "units": round(units_final, 2),
        "risk_amount": round(actual_risk, 2), "risk_pct": round(actual_risk / equity * 100, 3),
        "pip_value": round(pip_value, 4), "notional": round(notional, 2), "margin": round(margin, 2),
        "account_currency": account_ccy, "stop_distance_pips": round(dist / inst.pip, 1),
    }

"""Especificações dos instrumentos monitorados.

Spreads "typical_spread" são valores *all-in* conservadores (spread + comissão equivalente)
de contas ECN de varejo em horário líquido. Eles só são usados quando o provedor não
fornece bid/ask reais (ex.: Yahoo). Ajuste-os para a sua corretora em config/settings.json.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Instrument:
    symbol: str
    base: str
    quote: str
    kind: str  # "fx" | "metal"
    pip: float
    digits: int
    contract_size: float  # unidades por 1.00 lote
    typical_spread_pips: float
    yahoo: str  # símbolo de barras históricas no Yahoo
    oanda: str
    history_note: str = ""
    currencies: tuple = field(default=())

    @property
    def typical_spread(self) -> float:
        return self.typical_spread_pips * self.pip

    def round_price(self, p: float) -> float:
        return round(float(p), self.digits)

    def to_pips(self, price_distance: float) -> float:
        return price_distance / self.pip


def _fx(sym: str, spread: float) -> Instrument:
    base, quote = sym[:3], sym[3:]
    jpy = quote == "JPY"
    return Instrument(
        symbol=sym, base=base, quote=quote, kind="fx",
        pip=0.01 if jpy else 0.0001, digits=3 if jpy else 5,
        contract_size=100_000, typical_spread_pips=spread,
        yahoo=f"{sym}=X", oanda=f"{base}_{quote}", currencies=(base, quote),
    )


INSTRUMENTS: dict[str, Instrument] = {
    "XAUUSD": Instrument(
        "XAUUSD", "XAU", "USD", "metal", pip=0.1, digits=2, contract_size=100,
        typical_spread_pips=3.0, yahoo="PAXG-USD", oanda="XAU_USD",
        history_note=("Histórico intradiário via PAXG-USD (token lastreado 1:1 em ouro físico, "
                      "negociado 24/7; barras de fim de semana são descartadas) com ajuste de nível "
                      "multiplicativo para a cotação spot atual. Cotação ao vivo via gold-api.com."),
        currencies=("XAU", "USD"),
    ),
    "XAGUSD": Instrument(
        "XAGUSD", "XAG", "USD", "metal", pip=0.01, digits=3, contract_size=5_000,
        typical_spread_pips=3.0, yahoo="SI=F", oanda="XAG_USD",
        history_note=("Histórico intradiário via futuro contínuo SI=F (COMEX) com reparo de saltos "
                      "de rolagem/intercalação de contratos e ajuste de base para o spot atual. "
                      "Cotação ao vivo via gold-api.com."),
        currencies=("XAG", "USD"),
    ),
    "EURUSD": _fx("EURUSD", 1.0),
    "GBPUSD": _fx("GBPUSD", 1.4),
    "USDJPY": _fx("USDJPY", 1.3),
    "USDCHF": _fx("USDCHF", 1.6),
    "USDCAD": _fx("USDCAD", 1.8),
    "AUDUSD": _fx("AUDUSD", 1.3),
    "NZDUSD": _fx("NZDUSD", 1.8),
    "EURJPY": _fx("EURJPY", 1.9),
    "GBPJPY": _fx("GBPJPY", 2.8),
    "EURGBP": _fx("EURGBP", 1.5),
    "AUDJPY": _fx("AUDJPY", 2.0),
    "CADJPY": _fx("CADJPY", 2.4),
    "EURCHF": _fx("EURCHF", 2.0),
    "EURAUD": _fx("EURAUD", 2.6),
}

DEFAULT_UNIVERSE = list(INSTRUMENTS.keys())

# Ativos intermercado usados pelo módulo fundamentalista/quantitativo (Yahoo).
MACRO_SYMBOLS = {
    "DXY": "DX-Y.NYB",   # índice do dólar
    "US10Y": "^TNX",     # rendimento do Treasury 10 anos (em %)
    "US5Y": "^FVX",      # rendimento do Treasury 5 anos (em %)
    "US3M": "^IRX",      # rendimento do T-Bill 13 semanas (em %)
    "VIX": "^VIX",       # volatilidade implícita S&P 500
    "SPX_FUT": "ES=F",   # futuro do S&P 500 (sentimento de risco)
    "WTI": "CL=F",       # petróleo (CAD, NOK)
    "GOLD_FUT": "GC=F",  # futuro de ouro (checagem cruzada)
}

CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "XAU", "XAG"]


def get(symbol: str) -> Instrument:
    try:
        return INSTRUMENTS[symbol.upper()]
    except KeyError as exc:  # pragma: no cover - mensagem amigável
        raise KeyError(f"Instrumento desconhecido: {symbol}") from exc

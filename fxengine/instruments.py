"""Instrument universe: 28 FX crosses of the 8 majors + 4 precious metals."""
from __future__ import annotations

from dataclasses import dataclass

# Market-convention priority: the higher-ranked currency is the base.
MAJORS = ["EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "JPY"]
METAL_CODES = ["XAU", "XAG", "XPT", "XPD"]


@dataclass(frozen=True)
class Instrument:
    symbol: str          # e.g. "EURUSD"
    base: str            # e.g. "EUR"
    quote: str           # e.g. "USD"
    kind: str            # "fx" | "metal"
    pip: float           # size of one pip in price units
    digits: int          # display precision
    yahoo: str           # Yahoo Finance symbol used for candles
    contract_size: float  # units per 1.00 standard lot
    round_step: float    # psychological round-number spacing
    name: str = ""

    @property
    def is_metal(self) -> bool:
        return self.kind == "metal"

    @property
    def currencies(self) -> tuple[str, str]:
        return self.base, self.quote

    def pips(self, price_diff: float) -> float:
        return price_diff / self.pip

    def fmt(self, price: float) -> str:
        return f"{price:.{self.digits}f}"


def _fx(base: str, quote: str) -> Instrument:
    jpy = quote == "JPY"
    return Instrument(
        symbol=base + quote,
        base=base,
        quote=quote,
        kind="fx",
        pip=0.01 if jpy else 0.0001,
        digits=3 if jpy else 5,
        yahoo=f"{base}{quote}=X",
        contract_size=100_000,
        round_step=0.50 if jpy else 0.0050,
        name=f"{base}/{quote}",
    )


FX_PAIRS: list[Instrument] = [
    _fx(MAJORS[i], MAJORS[j]) for i in range(len(MAJORS)) for j in range(i + 1, len(MAJORS))
]

# Spot metals: candles come from the COMEX/NYMEX front-month future and are
# ratio-adjusted to the live spot quote (see data.provider).
METALS: list[Instrument] = [
    Instrument("XAUUSD", "XAU", "USD", "metal", 0.10, 2, "GC=F", 100, 25.0, "Ouro spot"),
    Instrument("XAGUSD", "XAG", "USD", "metal", 0.01, 3, "SI=F", 5_000, 0.50, "Prata spot"),
    Instrument("XPTUSD", "XPT", "USD", "metal", 0.10, 2, "PL=F", 100, 25.0, "Platina spot"),
    Instrument("XPDUSD", "XPD", "USD", "metal", 0.10, 2, "PA=F", 100, 25.0, "Paládio spot"),
]

UNIVERSE: dict[str, Instrument] = {i.symbol: i for i in FX_PAIRS + METALS}


def get(symbol: str) -> Instrument:
    key = symbol.upper().replace("/", "").replace("-", "").replace("_", "")
    if key not in UNIVERSE:
        raise KeyError(f"Instrumento desconhecido: {symbol}. Disponíveis: {', '.join(UNIVERSE)}")
    return UNIVERSE[key]


def select(spec: str | None) -> list[Instrument]:
    """spec: None/'all', 'fx', 'metals', or comma-separated symbols."""
    if not spec or spec.lower() in ("all", "todos"):
        return list(UNIVERSE.values())
    s = spec.lower()
    if s in ("fx", "forex"):
        return list(FX_PAIRS)
    if s in ("metals", "metais"):
        return list(METALS)
    return [get(x.strip()) for x in spec.split(",") if x.strip()]

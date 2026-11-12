"""Cotação spot de ouro e prata via gold-api.com (gratuito, sem chave, sem bid/ask)."""
from __future__ import annotations

from datetime import datetime

from .base import HttpProvider, ProviderError


class GoldApiProvider(HttpProvider):
    name = "goldapi"
    SYMBOLS = {"XAUUSD": "XAU", "XAGUSD": "XAG"}

    def spot(self, symbol: str) -> dict:
        code = self.SYMBOLS.get(symbol)
        if not code:
            raise ProviderError(f"goldapi não cobre {symbol}")
        d = self.get_json(f"https://api.gold-api.com/price/{code}")
        try:
            t = datetime.fromisoformat(d["updatedAt"].replace("Z", "+00:00"))
            return {"price": float(d["price"]), "time": t}
        except (KeyError, ValueError, TypeError) as exc:
            raise ProviderError(f"goldapi resposta inesperada: {d}") from exc

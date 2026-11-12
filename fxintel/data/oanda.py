"""Provedor OANDA v20 (bid/ask reais e candles BA). Requer token de conta (demo ou real).

Variáveis de ambiente:
    FXI_OANDA_TOKEN    token pessoal de API
    FXI_OANDA_ACCOUNT  ID da conta (ex.: 101-001-1234567-001)
    FXI_OANDA_ENV      "practice" (padrão) ou "live"

Observação: implementado segundo a documentação pública da API v20. Neste ambiente de
desenvolvimento não havia credenciais disponíveis, então o caminho OANDA não foi exercitado
contra o servidor real — os testes automatizados cobrem apenas o parsing das respostas.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from ..config import secret
from .base import HttpProvider, ProviderError
from .models import TF_OANDA, clean_ohlc


def parse_time(s: str) -> datetime:
    # OANDA usa RFC3339 com nanossegundos: 2024-01-02T10:00:00.123456789Z
    s = s.replace("Z", "+00:00")
    if "." in s:
        head, rest = s.split(".", 1)
        frac, tz = rest[:-6], rest[-6:]
        s = f"{head}.{frac[:6]}{tz}"
    return datetime.fromisoformat(s)


class OandaProvider(HttpProvider):
    name = "oanda"

    def __init__(self, timeout: float = 15.0):
        super().__init__(timeout=timeout)
        self.token = secret("FXI_OANDA_TOKEN")
        self.account = secret("FXI_OANDA_ACCOUNT")
        env = (secret("FXI_OANDA_ENV") or "practice").lower()
        self.base = ("https://api-fxtrade.oanda.com" if env == "live"
                     else "https://api-fxpractice.oanda.com")

    @property
    def configured(self) -> bool:
        return bool(self.token and self.account)

    def _headers(self) -> dict:
        if not self.configured:
            raise ProviderError("OANDA não configurado (FXI_OANDA_TOKEN/FXI_OANDA_ACCOUNT)")
        return {"Authorization": f"Bearer {self.token}", "Accept-Datetime-Format": "RFC3339"}

    @staticmethod
    def parse_pricing(d: dict) -> dict[str, dict]:
        out = {}
        for p in d.get("prices", []):
            try:
                bid = float(p["bids"][0]["price"])
                ask = float(p["asks"][0]["price"])
                out[p["instrument"]] = {"bid": bid, "ask": ask, "time": parse_time(p["time"]),
                                        "tradeable": p.get("tradeable", True)}
            except (KeyError, IndexError, ValueError):
                continue
        return out

    def pricing(self, oanda_instruments: list[str]) -> dict[str, dict]:
        d = self.get_json(f"{self.base}/v3/accounts/{self.account}/pricing",
                          params={"instruments": ",".join(oanda_instruments)},
                          headers=self._headers())
        out = self.parse_pricing(d)
        if not out:
            raise ProviderError("OANDA pricing vazio")
        return out

    @staticmethod
    def parse_candles(d: dict) -> pd.DataFrame:
        rows, idx = [], []
        for c in d.get("candles", []):
            b, a = c.get("bid"), c.get("ask")
            if not b or not a:
                continue
            idx.append(parse_time(c["time"]))
            rows.append({
                "o": (float(b["o"]) + float(a["o"])) / 2, "h": (float(b["h"]) + float(a["h"])) / 2,
                "l": (float(b["l"]) + float(a["l"])) / 2, "c": (float(b["c"]) + float(a["c"])) / 2,
                "v": float(c.get("volume", 0)),
                "spread": float(a["c"]) - float(b["c"]),
                "complete": bool(c.get("complete", True)),
            })
        if not rows:
            return pd.DataFrame(columns=["o", "h", "l", "c", "v", "spread"])
        df = pd.DataFrame(rows, index=pd.DatetimeIndex(idx).tz_convert("UTC"))
        return clean_ohlc(df)

    def candles(self, oanda_instrument: str, tf: str, count: int = 2000) -> pd.DataFrame:
        d = self.get_json(f"{self.base}/v3/instruments/{oanda_instrument}/candles",
                          params={"granularity": TF_OANDA[tf], "count": min(count, 5000),
                                  "price": "BA"},
                          headers=self._headers())
        return self.parse_candles(d)

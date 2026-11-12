"""Cotações bid/ask reais de fontes públicas, sem chave de API.

- Swissquote (feed público de cotações BBO da corretora suíça): bid/ask reais com timestamp em
  milissegundos para FX e metais, em vários perfis de spread (premium, prime, elite...).
- TrueFX (feed não autenticado): bid/ask de 10 pares principais, usado como checagem cruzada.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .base import HttpProvider, ProviderError

SQ_URL = "https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/{base}/{quote}"
TRUEFX_URL = "https://webrates.truefx.com/rates/connect.html?f=csv"


class SwissquoteProvider(HttpProvider):
    name = "swissquote"
    min_interval_s = 0.02
    max_concurrency = 8

    def __init__(self, timeout: float = 10.0, profile: str = "premium"):
        super().__init__(timeout=timeout, retries=2)
        self.profile = profile

    @staticmethod
    def parse(data: list, profile: str = "premium") -> dict | None:
        """Escolhe o perfil de spread pedido (ou o mais largo disponível) na primeira plataforma que o tenha."""
        best = None
        for plat in data or []:
            prices = plat.get("spreadProfilePrices") or []
            ts = plat.get("ts")
            for p in prices:
                if p.get("spreadProfile") == profile and p.get("bid") and p.get("ask"):
                    return {"bid": float(p["bid"]), "ask": float(p["ask"]),
                            "time": datetime.fromtimestamp(ts / 1000, tz=timezone.utc),
                            "platform": plat.get("topo", {}).get("platform"), "profile": profile}
            for p in prices:  # fallback: perfil com maior spread (conservador)
                if p.get("bid") and p.get("ask") and ts:
                    sp = float(p["ask"]) - float(p["bid"])
                    if best is None or sp > best["ask"] - best["bid"]:
                        best = {"bid": float(p["bid"]), "ask": float(p["ask"]),
                                "time": datetime.fromtimestamp(ts / 1000, tz=timezone.utc),
                                "platform": plat.get("topo", {}).get("platform"),
                                "profile": p.get("spreadProfile")}
        return best

    def quote(self, base: str, quote: str) -> dict:
        d = self.get_json(SQ_URL.format(base=base, quote=quote))
        q = self.parse(d, self.profile)
        if not q or q["ask"] < q["bid"]:
            raise ProviderError(f"swissquote {base}/{quote}: resposta sem preços válidos")
        return q

    def quotes(self, pairs: list[tuple[str, str]]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as ex:
            futs = {f"{b}{q}": ex.submit(self.quote, b, q) for b, q in pairs}
            for sym, fu in futs.items():
                try:
                    out[sym] = fu.result()
                except ProviderError:
                    continue
        if not out:
            raise ProviderError("swissquote: nenhuma cotação retornada")
        return out


class TrueFxProvider(HttpProvider):
    name = "truefx"

    @staticmethod
    def parse(text: str) -> dict[str, dict]:
        out = {}
        for line in text.strip().splitlines():
            p = line.split(",")
            if len(p) < 6 or "/" not in p[0]:
                continue
            try:
                bid = float(p[2] + p[3])
                ask = float(p[4] + p[5])
                ts = datetime.fromtimestamp(int(p[1]) / 1000, tz=timezone.utc)
            except ValueError:
                continue
            out[p[0].replace("/", "")] = {"bid": bid, "ask": ask, "time": ts}
        return out

    def quotes(self) -> dict[str, dict]:
        if self.health.circuit_open:
            raise ProviderError("truefx: circuito aberto")
        t0 = time.perf_counter()
        try:
            r = self._client.get(TRUEFX_URL)
            r.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            self.health.failure(str(exc))
            raise ProviderError(f"truefx: {exc}") from exc
        out = self.parse(r.text)
        if not out:
            self.health.failure("resposta vazia")
            raise ProviderError("truefx: resposta vazia")
        self.health.success((time.perf_counter() - t0) * 1000)
        return out

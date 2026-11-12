"""Infraestrutura comum dos provedores: HTTP com retry/backoff, circuit breaker e saúde."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from .models import utcnow

log = logging.getLogger("fxintel.data")

# Observação empírica: o Yahoo responde 429 para UAs completos de navegador vindos de
# datacenters, mas aceita o UA genérico abaixo.
UA = "Mozilla/5.0"


class ProviderError(RuntimeError):
    pass


@dataclass
class ProviderHealth:
    name: str
    ok: bool = True
    last_success: str | None = None
    last_error: str | None = None
    last_error_at: str | None = None
    consecutive_failures: int = 0
    circuit_open_until: float = 0.0
    last_latency_ms: float | None = None
    requests: int = 0
    failures: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def success(self, latency_ms: float) -> None:
        with self._lock:
            self.ok = True
            self.consecutive_failures = 0
            self.last_success = utcnow().isoformat()
            self.last_latency_ms = round(latency_ms, 1)
            self.requests += 1

    def failure(self, err: str) -> None:
        with self._lock:
            self.requests += 1
            self.failures += 1
            self.consecutive_failures += 1
            self.last_error = err[:300]
            self.last_error_at = utcnow().isoformat()
            if self.consecutive_failures >= 5:
                # abre o circuito por 60 s para não martelar um provedor indisponível
                self.ok = False
                self.circuit_open_until = time.time() + 60

    @property
    def circuit_open(self) -> bool:
        return time.time() < self.circuit_open_until

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "ok": self.ok and not self.circuit_open,
            "last_success": self.last_success, "last_error": self.last_error,
            "last_error_at": self.last_error_at, "consecutive_failures": self.consecutive_failures,
            "circuit_open": self.circuit_open, "last_latency_ms": self.last_latency_ms,
            "requests": self.requests, "failures": self.failures,
        }


class HttpProvider:
    """Cliente HTTP com retry exponencial, limitação de taxa e circuit breaker."""

    name = "base"

    min_interval_s = 0.0   # espaçamento mínimo entre requisições (rate limiting do cliente)
    max_concurrency = 8

    def __init__(self, timeout: float = 15.0, retries: int = 3):
        self.timeout = timeout
        self.retries = retries
        self._sem = threading.BoundedSemaphore(self.max_concurrency)
        self._pace_lock = threading.Lock()
        self._next_slot = 0.0
        self.health = ProviderHealth(self.name)
        self._client = httpx.Client(timeout=timeout, headers={"User-Agent": UA}, follow_redirects=True)

    def get_json(self, url: str, params: dict | None = None, headers: dict | None = None) -> Any:
        if self.health.circuit_open:
            raise ProviderError(f"{self.name}: circuito aberto após falhas consecutivas")
        last: Exception | None = None
        for attempt in range(self.retries):
            self._pace()
            t0 = time.perf_counter()
            try:
                with self._sem:
                    r = self._client.get(url, params=params, headers=headers)
                if r.status_code == 429:
                    raise ProviderError("429 rate limited")
                if r.status_code >= 500:
                    raise ProviderError(f"HTTP {r.status_code}")
                if r.status_code >= 400:
                    # erro do cliente: não adianta repetir
                    self.health.failure(f"HTTP {r.status_code}: {r.text[:120]}")
                    raise ProviderError(f"{self.name}: HTTP {r.status_code}: {r.text[:200]}")
                data = r.json()
                self.health.success((time.perf_counter() - t0) * 1000)
                return data
            except ProviderError as exc:
                last = exc
                if "HTTP 4" in str(exc) and "429" not in str(exc):
                    raise
            except (httpx.HTTPError, ValueError) as exc:
                last = exc
            backoff = 3.0 if last is not None and "429" in str(last) else 0.6
            time.sleep(backoff * (2 ** attempt))
        self.health.failure(str(last))
        raise ProviderError(f"{self.name}: falha após {self.retries} tentativas: {last}")

    def _pace(self) -> None:
        if self.min_interval_s <= 0:
            return
        with self._pace_lock:
            now = time.monotonic()
            wait = self._next_slot - now
            self._next_slot = max(now, self._next_slot) + self.min_interval_s
        if wait > 0:
            time.sleep(wait)

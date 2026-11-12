"""Benchmark de latência e confiabilidade da API (rodar com o servidor ativo).

Uso: python scripts/benchmark.py [URL] [N]
"""
import json
import statistics
import sys
import time
from pathlib import Path

import httpx

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 5
KEY = (Path(__file__).resolve().parent.parent / "var" / "admin_api_key.txt").read_text().strip()
H = {"X-API-Key": KEY}


def timed(method, path, n):
    out, errors = [], 0
    for _ in range(n):
        t0 = time.perf_counter()
        try:
            r = httpx.request(method, URL + path, headers=H, timeout=180)
            r.raise_for_status()
            out.append((time.perf_counter() - t0) * 1000)
        except Exception:  # noqa: BLE001
            errors += 1
    return {"n": n, "errors": errors, "p50_ms": round(statistics.median(out), 1) if out else None,
            "max_ms": round(max(out), 1) if out else None}


res = {
    "health": timed("GET", "/api/v1/health", 20),
    "quotes": timed("GET", "/api/v1/quotes", 20),
    "chart_H1": timed("GET", "/api/v1/chart/EURUSD?tf=H1&bars=150", 10),
    "analyze": timed("POST", "/api/v1/analyze", N),
}
q = httpx.get(URL + "/api/v1/quotes", headers=H).json()["data"]
res["quote_age_s"] = {s: v["age_s"] for s, v in q.items()}
last = httpx.get(URL + "/api/v1/analysis/latest", headers=H).json()
res["engine_timings_last"] = last["timings"] | {"elapsed_ms": last["elapsed_ms"]}
print(json.dumps(res, indent=1))

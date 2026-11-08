"""HTTP client with retry/backoff and a small TTL disk cache."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


class DataError(RuntimeError):
    pass


class Http:
    def __init__(self, cache_dir: str | None = None, timeout: float = 20.0, retries: int = 3):
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.retries = retries
        self._local = threading.local()
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    @property
    def session(self) -> requests.Session:
        s = getattr(self._local, "s", None)
        if s is None:
            s = requests.Session()
            s.headers.update({"User-Agent": UA, "Accept": "*/*"})
            self._local.s = s
        return s

    def _cache_path(self, url: str, params: dict | None) -> str | None:
        if not self.cache_dir:
            return None
        key = hashlib.sha1((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
        return os.path.join(self.cache_dir, key)

    def get(self, url: str, params: dict | None = None, ttl: float = 0, as_json: bool = True):
        path = self._cache_path(url, params)
        if ttl > 0 and path and os.path.exists(path) and time.time() - os.path.getmtime(path) < ttl:
            with open(path, encoding="utf-8") as f:
                raw = f.read()
            return json.loads(raw) if as_json else raw

        last_err: Exception | None = None
        for attempt in range(self.retries):
            try:
                r = self.session.get(url, params=params, timeout=self.timeout)
                if r.status_code == 429 or r.status_code >= 500:
                    raise DataError(f"HTTP {r.status_code}")
                if r.status_code >= 400:
                    # Client errors (404 unknown symbol, 401 key) will not heal on retry.
                    raise DataError(f"HTTP {r.status_code} em {url}")
                raw = r.text
                data = json.loads(raw) if as_json else raw
                if path and ttl > 0:
                    tmp = f"{path}.{threading.get_ident()}.tmp"
                    with open(tmp, "w", encoding="utf-8") as f:
                        f.write(raw)
                    os.replace(tmp, path)
                return data
            except (requests.RequestException, DataError, ValueError) as e:
                last_err = e
                if isinstance(e, DataError) and "HTTP 4" in str(e) and "429" not in str(e):
                    break
                time.sleep(1.5 * (attempt + 1))
        raise DataError(f"Falha ao obter {url}: {last_err}")

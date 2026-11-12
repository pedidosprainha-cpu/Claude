"""Provedor Yahoo Finance (barras OHLC e último preço). Sem bid/ask: spread é estimado."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .base import HttpProvider, ProviderError
from .models import TF_YAHOO, clean_ohlc, resample

# Alcance máximo de histórico por intervalo no Yahoo
MAX_RANGE = {"1m": "7d", "5m": "60d", "15m": "60d", "1h": "730d", "1d": "10y"}


class YahooProvider(HttpProvider):
    name = "yahoo"
    min_interval_s = 0.12
    max_concurrency = 4

    def __init__(self, hosts: list[str] | None = None, timeout: float = 15.0):
        super().__init__(timeout=timeout)
        self.hosts = hosts or ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]

    def _get(self, path: str, params: dict) -> dict:
        last: Exception | None = None
        for host in self.hosts:
            try:
                return self.get_json(f"https://{host}{path}", params=params)
            except ProviderError as exc:
                last = exc
        raise ProviderError(str(last))

    def bars(self, ysym: str, tf: str, rng: str | None = None) -> tuple[pd.DataFrame, dict]:
        if tf == "H4":
            df, meta = self.bars(ysym, "H1", rng)
            return resample(df, "4h"), meta
        interval = TF_YAHOO[tf]
        rng = rng or MAX_RANGE[interval]
        d = self._get(f"/v8/finance/chart/{ysym}", {"interval": interval, "range": rng,
                                                     "includePrePost": "false"})
        res = (d.get("chart") or {}).get("result")
        if not res:
            err = (d.get("chart") or {}).get("error")
            raise ProviderError(f"yahoo {ysym} {tf}: sem dados ({err})")
        r = res[0]
        ts = r.get("timestamp") or []
        q = (r.get("indicators", {}).get("quote") or [{}])[0]
        if not ts:
            return pd.DataFrame(columns=["o", "h", "l", "c", "v"]), r.get("meta", {})
        df = pd.DataFrame(
            {"o": q.get("open"), "h": q.get("high"), "l": q.get("low"), "c": q.get("close"),
             "v": q.get("volume")},
            index=pd.to_datetime(ts, unit="s", utc=True),
        )
        df = df.apply(pd.to_numeric, errors="coerce")
        if interval in ("1h",):
            df.index = df.index.floor("1h")
        return clean_ohlc(df), r.get("meta", {})

    def last_prices(self, ysyms: list[str]) -> dict[str, dict]:
        """Último preço para vários símbolos em uma chamada (endpoint spark)."""
        out: dict[str, dict] = {}
        for i in range(0, len(ysyms), 20):
            chunk = ysyms[i:i + 20]
            d = self._get("/v7/finance/spark", {"symbols": ",".join(chunk), "range": "1d",
                                                 "interval": "1m"})
            for item in (d.get("spark") or {}).get("result") or []:
                try:
                    resp = item["response"][0]
                    m = resp["meta"]
                    price = m.get("regularMarketPrice")
                    t = m.get("regularMarketTime")
                    if price is None or t is None:
                        continue
                    out[item["symbol"]] = {
                        "price": float(price),
                        "time": datetime.fromtimestamp(int(t), tz=timezone.utc),
                        "prev_close": m.get("previousClose") or m.get("chartPreviousClose"),
                    }
                except (KeyError, IndexError, TypeError):
                    continue
        if not out:
            raise ProviderError("yahoo spark: nenhuma cotação retornada")
        return out

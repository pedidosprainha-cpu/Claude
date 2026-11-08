"""Yahoo Finance chart API: OHLC candles for FX spot, metal futures and macro tickers."""
from __future__ import annotations

import pandas as pd

from .http import DataError, Http

HOSTS = ("query1", "query2")


def candles(http: Http, symbol: str, interval: str, rng: str, ttl: float = 0) -> tuple[pd.DataFrame, dict]:
    """Return (DataFrame[o,h,l,c,v] indexed by UTC timestamp, meta)."""
    last: Exception | None = None
    for host in HOSTS:
        url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{symbol}"
        try:
            d = http.get(url, params={"interval": interval, "range": rng}, ttl=ttl)
            return parse_chart(d)
        except (DataError, KeyError, IndexError, TypeError) as e:
            last = e
    raise DataError(f"Yahoo sem dados para {symbol} {interval}: {last}")


def parse_chart(d: dict) -> tuple[pd.DataFrame, dict]:
    res = d["chart"]["result"]
    if not res:
        raise DataError(str(d["chart"].get("error")))
    r = res[0]
    meta = r.get("meta", {})
    ts = r.get("timestamp") or []
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame(
        {"o": q.get("open"), "h": q.get("high"), "l": q.get("low"), "c": q.get("close"),
         "v": q.get("volume") or [0] * len(ts)},
        index=pd.to_datetime(ts, unit="s", utc=True).as_unit("ns"),
    )
    df = df.dropna(subset=["o", "h", "l", "c"]).astype(float)
    df = df[(df.h >= df.l) & (df.c > 0)]
    df = df[~df.index.duplicated(keep="last")].sort_index()
    if df.empty:
        raise DataError(f"série vazia para {meta.get('symbol')}")
    return df, meta

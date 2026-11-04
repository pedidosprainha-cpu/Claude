#!/usr/bin/env python3
"""Fetch live spot FX data from the Yahoo Finance CCY spot feed for a 44-pair basket.

Timeframes pulled per pair: 1m (1d), 5m (5d), 1h (3mo), 1d (1y).
Requests run concurrently so the whole basket is a single near-simultaneous
snapshot (spot, not delayed). Output: analysis/data/<PAIR>_<interval>.json
"""
import json, time, urllib.request, os, sys
from concurrent.futures import ThreadPoolExecutor

G8 = ["EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "JPY"]  # market-convention priority
# all 28 G8 combinations, quoted in market convention (higher-priority currency is the base)
MAJ_CROSS = [G8[i] + G8[j] for i in range(len(G8)) for j in range(i + 1, len(G8))]
EXOTIC = ["USDMXN", "USDZAR", "USDSGD", "USDNOK", "USDSEK", "EURNOK", "EURSEK",
          "EURPLN", "USDCNH", "USDHKD", "USDTRY", "EURHUF"]
PAIRS = MAJ_CROSS + EXOTIC

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT, exist_ok=True)
FRAMES = [("1m", "1d"), ("5m", "5d"), ("1h", "3mo"), ("1d", "1y")]


def fetch(job):
    pair, interval, rng = job
    host = "query1" if hash(job) % 2 else "query2"
    url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/{pair}=X"
           f"?interval={interval}&range={rng}")
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                d = json.load(r)
            with open(f"{OUT}/{pair}_{interval}.json", "w") as f:
                json.dump(d, f)
            return pair, interval, True
        except Exception as e:  # noqa: BLE001 - retry any network error
            if attempt == 3:
                print(f"FAIL {pair} {interval}: {e}", file=sys.stderr)
                return pair, interval, False
            time.sleep(2 ** (attempt + 1))


if __name__ == "__main__":
    only = sys.argv[1:] or None  # optional: restrict to given intervals, e.g. "1m 5m"
    jobs = [(p, i, r) for p in PAIRS for i, r in FRAMES if not only or i in only]
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=12) as ex:
        res = list(ex.map(fetch, jobs))
    ok = sum(1 for *_, s in res if s)
    print(f"{ok}/{len(jobs)} series fetched for {len(PAIRS)} pairs in {time.time()-t0:.1f}s",
          time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))

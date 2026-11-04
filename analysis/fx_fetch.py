#!/usr/bin/env python3
"""Fetch live spot FX data (1m, 5m, 1h, 1d) from the Yahoo Finance CCY spot feed.

Usage: fx_fetch.py [OUT_DIR]
Parallel fetch so the whole basket is captured within a few seconds (same snapshot).
"""
import json, time, urllib.request, os, sys
from concurrent.futures import ThreadPoolExecutor

PAIRS = ["EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
         "EURJPY","EURGBP","EURAUD","EURCHF","EURCAD","EURNZD",
         "GBPJPY","GBPCHF","GBPAUD","GBPCAD","GBPNZD",
         "AUDJPY","AUDNZD","AUDCAD","AUDCHF",
         "NZDJPY","NZDCAD","NZDCHF","CADJPY","CADCHF","CHFJPY",
         "USDMXN","USDZAR","USDSEK","USDNOK","USDSGD","EURNOK","EURSEK","USDPLN"]
FRAMES = [("1m","2d"), ("5m","5d"), ("1h","3mo"), ("1d","1y")]

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"}
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT, exist_ok=True)

def fetch(job):
    sym, interval, rng = job
    hosts = ["query1", "query2"]
    for attempt in range(4):
        url = f"https://{hosts[attempt % 2]}.finance.yahoo.com/v8/finance/chart/{sym}=X?interval={interval}&range={rng}"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
                d = json.load(r)
            with open(f"{OUT}/{sym}_{interval}.json", "w") as f:
                json.dump(d, f)
            return sym, interval, True
        except Exception as e:
            err = e
            time.sleep(1.5 * (attempt + 1))
    print(f"FAIL {sym} {interval}: {err}", file=sys.stderr)
    return sym, interval, False

if __name__ == "__main__":
    jobs = [(p, i, r) for p in PAIRS for i, r in FRAMES]
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=12) as ex:
        res = list(ex.map(fetch, jobs))
    ok = sum(1 for r in res if r[2])
    print(f"{ok}/{len(jobs)} frames fetched in {time.time()-t0:.1f}s at {time.strftime('%H:%M:%S', time.gmtime())} UTC")

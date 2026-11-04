#!/usr/bin/env python3
"""Fetch live spot FX data from Yahoo Finance for a basket of pairs.

Intervals: 1m (1d), 5m (5d), 1h (3mo), 1d (1y). Requests run in parallel so the
whole basket is snapshotted within a few seconds (keeps prices synchronous).

Usage: fx_fetch.py [PAIR ...]   (no args = full basket)
"""
import json, time, urllib.request, os, sys
from concurrent.futures import ThreadPoolExecutor

# 28 G8 majors/crosses + 10 liquid EM/Scandi/Asia pairs = 38 pairs
G8 = ["EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
      "EURJPY","GBPJPY","AUDJPY","CADJPY","CHFJPY","NZDJPY",
      "EURGBP","EURAUD","EURNZD","EURCHF","EURCAD",
      "GBPCHF","GBPAUD","GBPNZD","GBPCAD",
      "AUDNZD","AUDCAD","AUDCHF","NZDCAD","NZDCHF","CADCHF"]
EXOTIC = ["USDSEK","USDNOK","EURSEK","EURNOK","USDMXN","USDZAR",
          "USDSGD","USDHUF","USDPLN","EURPLN"]
PAIRS = G8 + EXOTIC

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT, exist_ok=True)
SPECS = [("1m", "1d"), ("5m", "5d"), ("1h", "6mo"), ("1d", "1y")]


def fetch(pair, interval, rng):
    host = "query1" if hash((pair, interval)) % 2 else "query2"
    url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{pair}=X?interval={interval}&range={rng}"
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                d = json.load(r)
            with open(f"{OUT}/{pair}_{interval}.json", "w") as f:
                json.dump(d, f)
            return pair, interval, True
        except Exception as e:
            if attempt == 3:
                print(f"FAIL {pair} {interval}: {e}", file=sys.stderr)
                return pair, interval, False
            time.sleep(1.5 * (attempt + 1))


if __name__ == "__main__":
    pairs = sys.argv[1:] or PAIRS
    jobs = [(p, i, r) for p in pairs for i, r in SPECS]
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=12) as ex:
        res = list(ex.map(lambda j: fetch(*j), jobs))
    ok = sum(1 for r in res if r[2])
    print(f"{ok}/{len(jobs)} series fetched for {len(pairs)} pairs in {time.time()-t0:.1f}s")

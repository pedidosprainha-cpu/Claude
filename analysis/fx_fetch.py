#!/usr/bin/env python3
"""Fetch live spot FX data (5m, 15m via resample, 1h, 1d) from Yahoo Finance for a basket of pairs."""
import json, time, urllib.request, os, sys

PAIRS = ["EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
         "EURJPY","GBPJPY","AUDJPY","CADJPY","CHFJPY","NZDJPY",
         "EURGBP","EURAUD","EURCHF","EURCAD","GBPCHF","GBPAUD","AUDNZD"]

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT, exist_ok=True)

def fetch(sym, interval, rng, host="query1"):
    url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{sym}=X?interval={interval}&range={rng}"
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except Exception as e:
            if attempt == 3:
                print(f"FAIL {sym} {interval}: {e}", file=sys.stderr)
                return None
            time.sleep(2 * (attempt + 1))

for p in PAIRS:
    for interval, rng in [("5m","5d"), ("1h","1mo"), ("1d","6mo")]:
        d = fetch(p, interval, rng)
        if d:
            with open(f"{OUT}/{p}_{interval}.json","w") as f:
                json.dump(d, f)
        time.sleep(0.4)
    print(p, "done", flush=True)

#!/usr/bin/env python3
"""Fetch live gold data: COMEX GC=F (5m/1h/1d) + intermarket (DXY, US10Y, silver, EURUSD)
from Yahoo Finance, plus Swissquote spot XAU/USD bid/ask for the futures->spot basis."""
import json, time, urllib.request, os, sys

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_xau")
os.makedirs(OUT, exist_ok=True)

def get(url):
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except Exception as e:
            if attempt == 3:
                print(f"FAIL {url}: {e}", file=sys.stderr); return None
            time.sleep(2 * (attempt + 1))

SYMS = {"GC": "GC=F", "DXY": "DX-Y.NYB", "TNX": "^TNX", "SI": "SI=F", "EURUSD": "EURUSD=X"}
JOBS = {"GC": [("5m","5d"),("15m","1mo"),("1h","3mo"),("1d","2y"),("1wk","5y")],
        "DXY": [("1h","1mo"),("1d","1y")], "TNX": [("1h","1mo"),("1d","1y")],
        "SI": [("1h","1mo"),("1d","1y")], "EURUSD": [("1h","1mo"),("1d","1y")]}
for k, sym in SYMS.items():
    for iv, rng in JOBS[k]:
        d = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={iv}&range={rng}")
        if d:
            json.dump(d, open(f"{OUT}/{k}_{iv}.json", "w"))
        time.sleep(0.3)
    print(k, "ok", flush=True)

sq = get("https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD")
if sq: json.dump(sq, open(f"{OUT}/spot_swissquote.json", "w"))
print("spot ok")

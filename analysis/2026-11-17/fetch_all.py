#!/usr/bin/env python3
"""Fetch multi-timeframe OHLC for every Forex + Metals symbol offered on the
RoboForex MT5 ECN web terminal (28 FX pairs + XAUUSD, XAGUSD, XAUEUR).

Source: Yahoo Finance chart API. FX = spot (CCY feed). Metals have no spot feed
there, so COMEX front-month futures (GC=F, SI=F) are used as proxies; levels are
later re-based to the broker's spot quote by the measured basis.
XAUEUR is built synthetically as GC=F / EURUSD=X.
"""
import json, os, sys, time, urllib.request

FX = ["AUDCAD","AUDCHF","AUDJPY","AUDNZD","AUDUSD","CADCHF","CADJPY","CHFJPY",
      "EURAUD","EURCAD","EURCHF","EURGBP","EURJPY","EURNZD","EURUSD","GBPAUD",
      "GBPCAD","GBPCHF","GBPJPY","GBPNZD","GBPUSD","NZDCAD","NZDCHF","NZDJPY",
      "NZDUSD","USDCAD","USDCHF","USDJPY"]
METALS = {"XAUUSD": "GC=F", "XAGUSD": "SI=F"}
TFS = [("5m", "5d"), ("15m", "1mo"), ("1h", "6mo"), ("1d", "2y")]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
OUT = sys.argv[1] if len(sys.argv) > 1 else "data"
os.makedirs(OUT, exist_ok=True)

def fetch(ysym, interval, rng):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.request.quote(ysym)}?interval={interval}&range={rng}")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                d = json.load(r)
            if d["chart"]["result"]:
                return d
        except Exception as e:
            err = e
        time.sleep(2 * (attempt + 1))
    print(f"FAIL {ysym} {interval}", file=sys.stderr)
    return None

jobs = [(p, p + "=X") for p in FX] + list(METALS.items())
for name, ysym in jobs:
    for interval, rng in TFS:
        d = fetch(ysym, interval, rng)
        if d:
            with open(f"{OUT}/{name}_{interval}.json", "w") as f:
                json.dump(d, f)
        time.sleep(0.3)
    print(name, "ok", flush=True)

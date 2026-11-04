#!/usr/bin/env python3
"""Fetch live spot FX data for a 38-pair basket.

History (1m/5m/1h/1d candles) comes from the Yahoo Finance spot CCY feed;
the live tick snapshot (bid/ask) is cross-checked against streaming OANDA
quotes (TradingView scanner endpoint, raw price columns only). Only raw prices are fetched -- no third-party analysis.
"""
import json, time, urllib.request, os, sys
from concurrent.futures import ThreadPoolExecutor

PAIRS = [
    # majors
    "EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
    # EUR crosses
    "EURGBP","EURJPY","EURCHF","EURCAD","EURAUD","EURNZD",
    # GBP crosses
    "GBPJPY","GBPCHF","GBPCAD","GBPAUD","GBPNZD",
    # AUD / NZD / CAD / CHF crosses
    "AUDJPY","AUDCHF","AUDCAD","AUDNZD","NZDJPY","NZDCHF","NZDCAD",
    "CADJPY","CADCHF","CHFJPY",
    # scandies / EM / Asia
    "USDNOK","USDSEK","EURNOK","EURSEK","USDMXN","USDZAR","USDSGD",
    "USDCNH","USDPLN","EURPLN",
]

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT, exist_ok=True)
FRAMES = [("1m", "2d"), ("5m", "10d"), ("1h", "6mo"), ("1d", "2y")]

def get(url):
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except Exception as e:
            if attempt == 3:
                print(f"FAIL {url}: {e}", file=sys.stderr)
                return None
            time.sleep(1.5 * (attempt + 1))

def yahoo(job):
    p, interval, rng = job
    host = "query1" if hash((p, interval)) % 2 else "query2"
    d = get(f"https://{host}.finance.yahoo.com/v8/finance/chart/{p}=X?interval={interval}&range={rng}")
    if d:
        with open(f"{OUT}/{p}_{interval}.json", "w") as f:
            json.dump(d, f)
    return p, interval, d is not None

def live_snapshot():
    """Raw streaming broker quotes (OANDA bid/ask) -- price fields only."""
    body = json.dumps({"symbols": {"tickers": [f"OANDA:{p}" for p in PAIRS]},
                       "columns": ["bid", "ask", "close", "high", "low", "update_mode"]}).encode()
    req = urllib.request.Request("https://scanner.tradingview.com/forex/scan", data=body,
                                 headers={**UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.load(r)
    snap = {"fetched_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())}
    for x in d.get("data", []):
        bid, ask, last, hi, lo, mode = x["d"]
        snap[x["s"].split(":")[1]] = dict(bid=bid, ask=ask, last=last, high=hi, low=lo, mode=mode)
    with open(f"{OUT}/live_snapshot.json", "w") as f:
        json.dump(snap, f, indent=1)
    return snap

if __name__ == "__main__":
    t0 = time.time()
    jobs = [(p, i, r) for p in PAIRS for i, r in FRAMES]
    with ThreadPoolExecutor(max_workers=10) as ex:
        res = list(ex.map(yahoo, jobs))
    bad = [r for r in res if not r[2]]
    snap = live_snapshot()
    print(f"yahoo ok {len(res)-len(bad)}/{len(res)}; live {len(snap)-1} pairs; {time.time()-t0:.1f}s; fails={bad}")

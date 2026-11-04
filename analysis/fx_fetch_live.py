#!/usr/bin/env python3
"""Live FX snapshot: executable Bid/Ask (Swissquote public BBO feed, cross-checked
with TrueFX) + intraday candles (Yahoo Finance spot FX, 1m/1h/1d) for 32 pairs.

Usage: python3 fx_fetch_live.py <out_dir>
Writes <out_dir>/quotes.json, <out_dir>/truefx.csv and <out_dir>/<PAIR>_<interval>.json.
Raw market data only — no third-party signals or analyses are consumed.
"""
import json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

PAIRS = [
    # majors
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD",
    # EUR crosses
    "EURGBP", "EURJPY", "EURCHF", "EURCAD", "EURAUD", "EURNZD",
    # GBP crosses
    "GBPJPY", "GBPCHF", "GBPCAD", "GBPAUD", "GBPNZD",
    # JPY crosses
    "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY",
    # commodity-bloc crosses
    "AUDCAD", "AUDCHF", "AUDNZD", "NZDCAD", "NZDCHF", "CADCHF",
    # USD vs. secondary/EM
    "USDSEK", "USDNOK", "USDSGD", "USDMXN",
]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"}


def get(url, tries=4, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    for a in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # network hiccup -> backoff
            if a == tries - 1:
                print(f"FAIL {url}: {e}", file=sys.stderr)
                return None
            time.sleep(2 ** (a + 1))


def swissquote(pair):
    raw = get(f"https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/{pair[:3]}/{pair[3:]}")
    t_local = time.time()
    if not raw:
        return pair, None
    feeds = json.loads(raw)
    # prefer the SwissquoteLtd / CapitalMarkets live servers; keep every profile
    best = None
    for f in feeds:
        if f["topo"]["platform"].startswith("Swissquote"):
            if best is None or f["ts"] > best["ts"]:
                best = f
    best = best or feeds[0]
    prof = {p["spreadProfile"]: {"bid": p["bid"], "ask": p["ask"]} for p in best["spreadProfilePrices"]}
    return pair, {"ts_ms": best["ts"], "fetched_at": t_local, "server": best["topo"], "profiles": prof}


def yahoo(job):
    pair, interval, rng = job
    raw = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{pair}=X?interval={interval}&range={rng}")
    return job, raw


def main(out):
    os.makedirs(out, exist_ok=True)
    jobs = [(p, i, r) for p in PAIRS for i, r in (("1m", "5d"), ("1h", "3mo"), ("1d", "1y"))]
    with ThreadPoolExecutor(8) as ex:
        for (p, i, r), raw in ex.map(yahoo, jobs):
            if raw:
                with open(f"{out}/{p}_{i}.json", "wb") as fh:
                    fh.write(raw)
    # quotes last so they are the freshest element of the snapshot
    with ThreadPoolExecutor(8) as ex:
        quotes = dict(ex.map(swissquote, PAIRS))
    with open(f"{out}/quotes.json", "w") as fh:
        json.dump(quotes, fh, indent=1)
    tf = get("https://webrates.truefx.com/rates/connect.html?f=csv")
    if tf:
        with open(f"{out}/truefx.csv", "wb") as fh:
            fh.write(tf)
    print("snapshot done", time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data")

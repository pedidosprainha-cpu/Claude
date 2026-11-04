#!/usr/bin/env python3
"""Live BTC/USD spot snapshot from primary USD spot venues (raw data only).

Usage: python3 btc_fetch_live.py <out_dir>

* Top-of-book Bid/Ask + venue timestamps: Coinbase Exchange, Kraken, Bitstamp, Gemini
* Candles: Coinbase (1m/5m/15m/1h/1d, max 300 each) and Kraken (1m/5m/15m/30m/1h/1d,
  includes the forming candle)
* Order books: Coinbase L2, Kraken depth (500 levels)
* Recent trades with aggressor side: Coinbase (maker side flipped) and Kraken (taker side)
"""
import json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) fx-research/1.0"}
CB = "https://api.exchange.coinbase.com/products/BTC-USD"
KR = "https://api.kraken.com/0/public"


def get(url, tries=4, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    for a in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception as e:
            if a == tries - 1:
                print(f"FAIL {url}: {e}", file=sys.stderr)
                return None
            time.sleep(2 ** (a + 1))


def job(item):
    name, url = item
    t0 = time.time()
    d = get(url)
    return name, {"recv": time.time(), "sent": t0, "data": d}


def main(out):
    os.makedirs(out, exist_ok=True)
    now = int(time.time())
    heavy = [
        *[(f"cb_c{g}", f"{CB}/candles?granularity={g}") for g in (60, 300, 900, 3600, 86400)],
        *[(f"kr_c{i}", f"{KR}/OHLC?pair=XBTUSD&interval={i}") for i in (1, 5, 15, 30, 60, 1440)],
        ("cb_book", f"{CB}/book?level=2"),
        ("kr_book", f"{KR}/Depth?pair=XBTUSD&count=500"),
        ("cb_trades", f"{CB}/trades?limit=1000"),
        ("kr_trades", f"{KR}/Trades?pair=XBTUSD&since={(now - 1200) * 10**9}"),
    ]
    tops = [
        ("cb_ticker", f"{CB}/ticker"),
        ("kr_ticker", f"{KR}/Ticker?pair=XBTUSD"),
        ("kr_spread", f"{KR}/Spread?pair=XBTUSD"),
        ("bs_ticker", "https://www.bitstamp.net/api/v2/ticker/btcusd/"),
        ("gm_ticker", "https://api.gemini.com/v1/pubticker/btcusd"),
    ]
    res = {}
    with ThreadPoolExecutor(8) as ex:
        res.update(dict(ex.map(job, heavy)))
    # Kraken returns 1000 trades per call: paginate forward until (almost) now
    kt = res["kr_trades"]["data"]["result"]
    trades, last = list(kt["XXBTZUSD"]), kt["last"]
    for _ in range(30):
        if not trades or trades[-1][2] >= time.time() - 5:
            break
        time.sleep(1.1)
        d = get(f"{KR}/Trades?pair=XBTUSD&since={last}")
        if not d or not d.get("result"):
            break
        page = d["result"]["XXBTZUSD"]
        if not page:
            break
        trades += page
        last = d["result"]["last"]
    res["kr_trades"]["data"]["result"]["XXBTZUSD"] = trades
    res["kr_trades"]["recv"] = time.time()
    with ThreadPoolExecutor(8) as ex:  # top of book last -> freshest element
        res.update(dict(ex.map(job, tops)))
    for k, v in res.items():
        with open(f"{out}/{k}.json", "w") as f:
            json.dump(v, f)
    print("btc snapshot done", time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "btc_data")

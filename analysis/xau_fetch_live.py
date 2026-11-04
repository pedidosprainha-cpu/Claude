#!/usr/bin/env python3
"""XAU/USD spot snapshot (raw data only).

Usage: python3 xau_fetch_live.py <out_dir> [days_back=7]

* Executable Bid/Ask: Swissquote public BBO feed (all spread profiles, ms timestamps)
* Cross-check: gold-api.com spot price (indicative mid, with update timestamp)
* History: Dukascopy public datafeed (spot XAUUSD, not futures)
    - today's hourly tick files (bid/ask ticks) for every completed hour
    - previous days' 1-minute BID and ASK candles
    - yearly daily BID candles (for ADR and daily levels)
Files are saved raw (.bi5, LZMA); decoding happens in xau_analyze.py.
"""
import datetime as dt, json, os, sys, time, urllib.error, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) fx-research/1.0"}
DK = "https://datafeed.dukascopy.com/datafeed/XAUUSD"


def get(url, tries=8, timeout=25):
    """Returns (status, bytes). Retries transient errors (5xx / resets) with backoff."""
    for a in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, b""
            err = e.code
            if e.code == 429:  # rate limited: back off harder
                time.sleep(15)
        except Exception as e:  # connection reset / timeout
            err = type(e).__name__
        time.sleep(min(2 * (a + 1), 10))
    return err, b""


def have(out, name):
    return os.path.exists(f"{out}/{name}")


def save(out, name, status, data):
    if data:
        with open(f"{out}/{name}", "wb") as f:
            f.write(data)
    return f"{name}: {status} {len(data)}B"


def main(out, days_back=7):
    os.makedirs(out, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    log = []
    # history first (slow), quotes last (freshest)
    for h in range(now.hour):
        if have(out, f"ticks_{now:%Y%m%d}_{h:02d}.bi5"):
            continue
        st, b = get(f"{DK}/{now.year}/{now.month - 1:02d}/{now.day:02d}/{h:02d}h_ticks.bi5")
        log.append(save(out, f"ticks_{now:%Y%m%d}_{h:02d}.bi5", st, b))
        time.sleep(2)
    for k in range(1, days_back + 1):
        d = now - dt.timedelta(days=k)
        for side in ("BID", "ASK"):
            if have(out, f"m1_{side}_{d:%Y%m%d}.bi5"):
                continue
            st, b = get(f"{DK}/{d.year}/{d.month - 1:02d}/{d.day:02d}/{side}_candles_min_1.bi5")
            log.append(save(out, f"m1_{side}_{d:%Y%m%d}.bi5", st, b))
            time.sleep(0.3)
    # hourly candles of the previous two months (current month is not published)
    for k in (1, 2):
        mth = (now.month - 1 - k) % 12
        yr = now.year if now.month - 1 - k >= 0 else now.year - 1
        name = f"h1_BID_{yr}{mth + 1:02d}.bi5"
        if not have(out, name):
            st, b = get(f"{DK}/{yr}/{mth:02d}/BID_candles_hour_1.bi5")
            log.append(save(out, name, st, b))
            time.sleep(1)
    for y in (now.year, now.year - 1):
        if not have(out, f"d1_BID_{y}.bi5"):
            st, b = get(f"{DK}/{y}/BID_candles_day_1.bi5")
            log.append(save(out, f"d1_BID_{y}.bi5", st, b))

    t0 = time.time()
    st, b = get("https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD", tries=4)
    q = {"recv": time.time(), "sent": t0, "data": json.loads(b) if b else None}
    st2, b2 = get("https://api.gold-api.com/price/XAU", tries=4)
    q["goldapi"] = {"recv": time.time(), "data": json.loads(b2) if b2 else None}
    with open(f"{out}/quote.json", "w") as f:
        json.dump(q, f)
    with open(f"{out}/fetch_log.txt", "w") as f:
        f.write("\n".join(log))
    print("\n".join(log))
    print("xau snapshot done", time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "xau_data", int(sys.argv[2]) if len(sys.argv) > 2 else 7)

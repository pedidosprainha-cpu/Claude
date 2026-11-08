"""Fundamental data feeds.

* Economic calendar  - ForexFactory weekly JSON (event risk filter)
* Policy rates       - BIS WS_CBPOL (carry + policy trajectory)
* Positioning        - CFTC Commitments of Traders, legacy futures-only (speculative net)
* Headlines          - Investing.com RSS (forex / commodities / indicators)

Each loader is independent and fail-safe: the engine degrades gracefully if a
feed is unreachable and says so in the report.
"""
from __future__ import annotations

import csv
import io
import json
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .http import DataError, Http

# --------------------------------------------------------------------------- calendar


@dataclass
class Event:
    time: datetime
    ccy: str
    title: str
    impact: str          # High | Medium | Low | Holiday
    forecast: str = ""
    previous: str = ""


CAL_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


def calendar(http: Http) -> list[Event]:
    d = http.get(CAL_URL, ttl=1800)
    out = []
    for e in d:
        try:
            t = datetime.fromisoformat(e["date"]).astimezone(timezone.utc)
        except (KeyError, ValueError):
            continue
        out.append(Event(t, (e.get("country") or "").upper(), e.get("title", ""),
                         e.get("impact", ""), e.get("forecast", ""), e.get("previous", "")))
    out.sort(key=lambda x: x.time)
    return out


# --------------------------------------------------------------------------- policy rates

BIS_AREAS = {"US": "USD", "XM": "EUR", "GB": "GBP", "JP": "JPY", "CH": "CHF",
             "CA": "CAD", "AU": "AUD", "NZ": "NZD"}
BIS_URL = "https://stats.bis.org/api/v1/data/WS_CBPOL/D.{areas}/all"
FALLBACK_RATES = os.path.join(os.path.dirname(__file__), "policy_rates_fallback.json")


@dataclass
class PolicyRate:
    ccy: str
    rate: float
    date: str
    change_6m: float     # rate now minus rate ~182 days ago (policy trajectory)
    source: str


def policy_rates(http: Http, now: datetime) -> dict[str, PolicyRate]:
    start = (now - timedelta(days=200)).strftime("%Y-%m-%d")
    try:
        raw = http.get(BIS_URL.format(areas="+".join(BIS_AREAS)),
                       params={"startPeriod": start, "format": "csv"}, ttl=6 * 3600, as_json=False)
        series: dict[str, list[tuple[str, float]]] = {}
        for r in csv.DictReader(io.StringIO(raw)):
            v = r.get("OBS_VALUE")
            if v in (None, "", "NaN"):
                continue
            series.setdefault(r["REF_AREA"], []).append((r["TIME_PERIOD"], float(v)))
        out = {}
        cutoff = (now - timedelta(days=182)).strftime("%Y-%m-%d")
        for area, obs in series.items():
            obs.sort()
            ccy = BIS_AREAS.get(area)
            if not ccy:
                continue
            past = [v for t, v in obs if t <= cutoff] or [obs[0][1]]
            out[ccy] = PolicyRate(ccy, obs[-1][1], obs[-1][0], obs[-1][1] - past[-1], "BIS")
        if len(out) >= 6:
            return out
    except (DataError, KeyError, ValueError):
        pass
    with open(FALLBACK_RATES, encoding="utf-8") as f:
        fb = json.load(f)
    return {c: PolicyRate(c, v["rate"], fb["as_of"], v.get("change_6m", 0.0), "fallback")
            for c, v in fb["rates"].items()}


# --------------------------------------------------------------------------- COT

COT_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
COT_CODES = {
    "EUR": "099741", "JPY": "097741", "GBP": "096742", "CHF": "092741",
    "CAD": "090741", "AUD": "232741", "NZD": "112741", "USD": "098662",
    "XAU": "088691", "XAG": "084691", "XPT": "076651", "XPD": "075651",
}


@dataclass
class Cot:
    asset: str
    date: str
    net: float
    net_pct_oi: float        # speculative net as % of open interest
    index_3y: float          # 0..100 percentile-range of net over ~3 years
    chg_1w_pct: float        # change of net_pct_oi vs 1 week ago (pp)
    chg_4w_pct: float


def cot(http: Http, now: datetime) -> dict[str, Cot]:
    since = (now - timedelta(days=3 * 365 + 14)).strftime("%Y-%m-%dT00:00:00.000")
    codes = ",".join(f"'{c}'" for c in COT_CODES.values())
    params = {
        "$where": f"cftc_contract_market_code in ({codes}) AND report_date_as_yyyy_mm_dd > '{since}'",
        "$select": ("report_date_as_yyyy_mm_dd,cftc_contract_market_code,"
                    "noncomm_positions_long_all,noncomm_positions_short_all,open_interest_all"),
        "$order": "report_date_as_yyyy_mm_dd ASC",
        "$limit": "10000",
    }
    rows = http.get(COT_URL, params=params, ttl=12 * 3600)
    by_code: dict[str, list[tuple[str, float, float]]] = {}
    for r in rows:
        try:
            lo = float(r["noncomm_positions_long_all"])
            sh = float(r["noncomm_positions_short_all"])
            oi = float(r["open_interest_all"]) or 1.0
        except (KeyError, ValueError):
            continue
        by_code.setdefault(r["cftc_contract_market_code"], []).append(
            (r["report_date_as_yyyy_mm_dd"][:10], lo - sh, (lo - sh) / oi * 100))
    out = {}
    for asset, code in COT_CODES.items():
        obs = by_code.get(code)
        if not obs or len(obs) < 10:
            continue
        nets = [o[1] for o in obs]
        lo, hi = min(nets), max(nets)
        idx = 50.0 if hi == lo else (nets[-1] - lo) / (hi - lo) * 100
        pct = [o[2] for o in obs]
        out[asset] = Cot(asset, obs[-1][0], nets[-1], pct[-1], idx,
                         pct[-1] - pct[-2], pct[-1] - pct[-5] if len(pct) > 5 else 0.0)
    return out


# --------------------------------------------------------------------------- headlines

RSS_FEEDS = {
    "forex": "https://www.investing.com/rss/news_1.rss",
    "commodities": "https://www.investing.com/rss/news_11.rss",
    "indicators": "https://www.investing.com/rss/news_95.rss",
}


@dataclass
class Headline:
    time: datetime
    title: str
    source: str
    feed: str


def headlines(http: Http, max_age_h: float = 36) -> list[Headline]:
    now = datetime.now(timezone.utc)
    seen, out = set(), []
    for feed, url in RSS_FEEDS.items():
        try:
            raw = http.get(url, ttl=600, as_json=False)
            root = ET.fromstring(raw)
        except (DataError, ET.ParseError):
            continue
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            if not title or title in seen:
                continue
            ts = _parse_pub(it.findtext("pubDate") or "")
            if ts is None or (now - ts).total_seconds() > max_age_h * 3600:
                continue
            seen.add(title)
            out.append(Headline(ts, title, (it.findtext("author") or "").strip(), feed))
    out.sort(key=lambda h: h.time, reverse=True)
    return out


def _parse_pub(s: str) -> datetime | None:
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT"):
        try:
            t = datetime.strptime(s, fmt)
            return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)
        except ValueError:
            continue
    return None

"""Market-data facade: candles + live spot quote per instrument, and the macro context.

Real-time handling
------------------
Candles come from Yahoo; the *live executable price* comes from Swissquote's
bid/ask feed. The live mid is injected into every intraday frame (it updates
the forming bar or opens a new one), so every indicator is computed on the
spot price of this instant, not on the last published candle.

Metals: Yahoo has no spot-metal candles, so the front-month future (GC/SI/PL/PA)
is used and ratio-adjusted to the live spot quote (basis removal).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from ..analysis.indicators import ny_daily, resample
from ..config import Settings
from ..instruments import Instrument
from ..sessions import fx_open, metals_open
from . import fundamentals as fd
from . import swissquote, yahoo
from .http import DataError, Http

INTRADAY = {  # name: (yahoo interval, range, cache ttl seconds, pandas freq)
    "M5": ("5m", "5d", 20, "5min"),
    "M15": ("15m", "30d", 45, "15min"),
    "H1": ("1h", "1y", 240, "1h"),
}

# Light profile for the real-time breakout monitor (~70 KB per instrument per cycle,
# H1 mostly served from cache): enough history for 48-bar M15 / 120-bar H1 ranges,
# prior day/week levels and ATRs.
LIGHT = {
    "M15": ("15m", "5d", 50, "15min"),
    "H1": ("1h", "1mo", 600, "1h"),
}

MACRO_TICKERS = {
    "DXY": "DX-Y.NYB", "US10Y": "^TNX", "US5Y": "^FVX", "US3M": "^IRX", "VIX": "^VIX",
    "SPX_FUT": "ES=F", "OIL": "CL=F", "COPPER": "HG=F", "GOLD_FUT": "GC=F",
}

# Typical retail spreads used only when no live quote is available.
FALLBACK_SPREAD_PIPS = {"XAUUSD": 3.0, "XAGUSD": 3.0, "XPTUSD": 40.0, "XPDUSD": 60.0}


@dataclass
class InstrumentData:
    inst: Instrument
    frames: dict[str, pd.DataFrame]
    price: float
    bid: float
    ask: float
    quote_ts: datetime
    quote_source: str
    tradeable: bool
    notes: list[str] = field(default_factory=list)

    @property
    def spread(self) -> float:
        return self.ask - self.bid


@dataclass
class MarketContext:
    now: datetime
    macro: dict[str, pd.DataFrame] = field(default_factory=dict)   # name -> D1 frame
    macro_h1: dict[str, pd.DataFrame] = field(default_factory=dict)
    events: list = field(default_factory=list)
    rates: dict = field(default_factory=dict)
    cot: dict = field(default_factory=dict)
    headlines: list = field(default_factory=list)
    status: dict[str, str] = field(default_factory=dict)


def inject_live(df: pd.DataFrame, ts: datetime, price: float, freq: str) -> pd.DataFrame:
    """Update the forming bar with the live price, or open a new bar."""
    if df.empty:
        return df
    start = pd.Timestamp(ts).floor(freq)
    last = df.index[-1]
    if start < last:
        return df
    if start == last:
        df = df.copy()
        df.loc[last, "c"] = price
        df.loc[last, "h"] = max(df.loc[last, "h"], price)
        df.loc[last, "l"] = min(df.loc[last, "l"], price)
        return df
    row = pd.DataFrame({"o": [price], "h": [price], "l": [price], "c": [price], "v": [0.0]},
                       index=pd.DatetimeIndex([start]))
    return pd.concat([df, row[df.columns.intersection(row.columns)]])


def build_frames(m5: pd.DataFrame | None, m15: pd.DataFrame, h1: pd.DataFrame) -> dict[str, pd.DataFrame]:
    h4 = resample(h1, "4h")
    d1 = ny_daily(h1)
    w1 = resample(d1.assign(v=0.0), "W-FRI")
    out = {"M15": m15, "H1": h1, "H4": h4, "D1": d1, "W1": w1}
    if m5 is not None:
        out["M5"] = m5
    return out


class Provider:
    def __init__(self, settings: Settings):
        self.s = settings
        self.http = Http(settings.cache_dir, timeout=settings.timeout)

    # ------------------------------------------------------------------ instruments
    def load_instrument(self, inst: Instrument, now: datetime, spec: dict | None = None) -> InstrumentData:
        spec = spec or INTRADAY
        fine = next(iter(spec))                 # finest timeframe in the profile
        notes: list[str] = []
        raw, meta = {}, {}
        for name, (iv, rng, ttl, _) in spec.items():
            raw[name], meta[name] = yahoo.candles(self.http, inst.yahoo, iv, rng, ttl=ttl)

        q = None
        try:
            q = swissquote.quote(self.http, inst.base, inst.quote)
        except DataError as e:
            notes.append(f"cotação Swissquote indisponível ({e}); usando último preço Yahoo")

        if inst.is_metal:
            if q is not None:
                ref = raw[fine]
                fut_ref = ref.c.asof(pd.Timestamp(q.ts)) if q.ts >= ref.index[0] else ref.c.iloc[-1]
                ratio = q.mid / float(fut_ref)
                if not 0.9 < ratio < 1.1:
                    notes.append(f"basis spot/futuro anômalo ({ratio:.4f}); ajuste ignorado")
                    ratio = 1.0
                for k in raw:
                    raw[k] = raw[k].copy()
                    raw[k][["o", "h", "l", "c"]] *= ratio
                notes.append(f"candles de {inst.yahoo} ajustados ao spot (fator {ratio:.5f})")
            else:
                notes.append(f"sem spot ao vivo: preços do futuro {inst.yahoo}")

        if q is not None:
            price, bid, ask, qts, src = q.mid, q.bid, q.ask, q.ts, q.source
        else:
            m = meta[fine]
            price = float(m.get("regularMarketPrice") or raw[fine].c.iloc[-1])
            qts = datetime.fromtimestamp(m.get("regularMarketTime", raw[fine].index[-1].timestamp()), tz=timezone.utc)
            half = FALLBACK_SPREAD_PIPS.get(inst.symbol, 1.5 if inst.quote in ("USD",) else 2.5) * inst.pip / 2
            bid, ask, src = price - half, price + half, "Yahoo (spread estimado)"

        frames = {}
        for name, (_, _, _, freq) in spec.items():
            frames[name] = inject_live(raw[name], qts, price, freq)
        frames = build_frames(frames.get("M5"), frames["M15"], frames["H1"])

        open_now = (metals_open(now) if inst.is_metal else fx_open(now))
        age = (now - qts).total_seconds()
        tradeable = open_now and age <= self.s.max_quote_age_s
        if not open_now:
            notes.append("mercado fechado agora")
        elif age > self.s.max_quote_age_s:
            notes.append(f"cotação com {age / 60:.0f} min de atraso")
        return InstrumentData(inst, frames, price, bid, ask, qts, src, tradeable, notes)

    def load_instruments(self, insts: list[Instrument], now: datetime, progress=None,
                         spec: dict | None = None) -> tuple[dict, dict]:
        """progress(done, total) is called from this thread after each instrument."""
        out, errors = {}, {}

        def job(i):
            try:
                return i.symbol, self.load_instrument(i, now, spec), None
            except Exception as e:  # noqa: BLE001 - one bad feed must not kill the scan
                return i.symbol, None, str(e)

        with ThreadPoolExecutor(max_workers=self.s.workers) as ex:
            for k, (sym, data, err) in enumerate(ex.map(job, insts), 1):
                if data is not None:
                    out[sym] = data
                else:
                    errors[sym] = err
                if progress:
                    progress(k, len(insts))
        return out, errors

    # ------------------------------------------------------------------ context
    def load_events(self, now: datetime) -> MarketContext:
        """Calendar only (event-risk gate) — what the real-time monitor needs."""
        ctx = MarketContext(now=now)
        try:
            ctx.events = fd.calendar(self.http)
            ctx.status["calendar"] = "ok"
        except Exception as e:  # noqa: BLE001
            ctx.status["calendar"] = f"falhou: {e}"
        return ctx

    def load_context(self, now: datetime) -> MarketContext:
        ctx = MarketContext(now=now)

        def macro_job(item):
            name, tk = item
            try:
                h1, _ = yahoo.candles(self.http, tk, "1h", "1mo", ttl=300)
                d1, _ = yahoo.candles(self.http, tk, "1d", "1y", ttl=1800)
                return name, h1, d1, None
            except Exception as e:  # noqa: BLE001
                return name, None, None, str(e)

        with ThreadPoolExecutor(max_workers=self.s.workers) as ex:
            futs = {
                "calendar": ex.submit(fd.calendar, self.http),
                "rates": ex.submit(fd.policy_rates, self.http, now),
            }
            if self.s.use_cot:
                futs["cot"] = ex.submit(fd.cot, self.http, now)
            if self.s.use_news:
                futs["headlines"] = ex.submit(fd.headlines, self.http)
            for name, h1, d1, err in ex.map(macro_job, MACRO_TICKERS.items()):
                if err:
                    ctx.status[f"macro:{name}"] = f"falhou: {err}"
                else:
                    ctx.macro[name], ctx.macro_h1[name] = d1, h1
            for key, f in futs.items():
                try:
                    val = f.result()
                    setattr(ctx, "events" if key == "calendar" else key, val)
                    ctx.status[key] = "ok"
                except Exception as e:  # noqa: BLE001
                    ctx.status[key] = f"falhou: {e}"
        if ctx.rates and next(iter(ctx.rates.values())).source == "fallback":
            ctx.status["rates"] = "BIS indisponível — usando tabela local"
        return ctx

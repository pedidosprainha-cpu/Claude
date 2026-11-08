"""Deterministic synthetic market (offline demo + tests).

Currency log-indices are simulated with regime-switching drift, and every FX
pair is derived from them, so cross rates are internally consistent and the
strength meter has a well-defined ground truth.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from ..analysis.indicators import resample
from ..config import Settings
from ..instruments import MAJORS, Instrument
from .fundamentals import Cot, Event, Headline, PolicyRate
from .provider import InstrumentData, MarketContext, build_frames

LEVEL = {"EUR": 1.10, "GBP": 1.30, "AUD": 0.66, "NZD": 0.60, "USD": 1.0,
         "CAD": 1 / 1.38, "CHF": 1 / 0.80, "JPY": 1 / 150.0}
METAL_LEVEL = {"XAU": 4000.0, "XAG": 50.0, "XPT": 1500.0, "XPD": 1000.0}


class SyntheticProvider:
    def __init__(self, settings: Settings, days: int = 365):
        self.s = settings
        rng = np.random.default_rng(settings.seed)
        end = pd.Timestamp("2026-11-04 14:30", tz="UTC")       # a Wednesday, London/NY overlap
        idx = pd.date_range(end - pd.Timedelta(days=days), end, freq="5min")
        idx = idx[idx.dayofweek < 5]
        self.index = idx
        self.now = (idx[-1] + pd.Timedelta(minutes=2)).to_pydatetime()
        n = len(idx)
        self.paths = {}
        for k, ccy in enumerate(MAJORS + list(METAL_LEVEL)):
            vol = 0.00045 if ccy in MAJORS else 0.0011
            regime = np.repeat(rng.normal(0, 1, n // 2000 + 1), 2000)[:n]
            drift = regime * vol * 0.02
            if ccy == "AUD":          # planted ground truth: persistent AUD strength
                drift[-3000:] += vol * 0.06
            if ccy == "JPY":
                drift[-3000:] -= vol * 0.05
            steps = drift + rng.normal(0, vol, n)
            self.paths[ccy] = np.cumsum(steps)
        self.rng = rng

    def _ohlc(self, close: np.ndarray, vol: float) -> pd.DataFrame:
        o = np.concatenate([[close[0]], close[:-1]])
        wick = np.abs(self.rng.normal(0, vol * 0.6, len(close))) * close
        df = pd.DataFrame({"o": o, "h": np.maximum(o, close) + wick,
                           "l": np.minimum(o, close) - wick, "c": close, "v": 0.0}, index=self.index)
        return df

    def series(self, inst: Instrument) -> pd.DataFrame:
        if inst.is_metal:
            close = METAL_LEVEL[inst.base] * np.exp(self.paths[inst.base] - self.paths["USD"] * 0.5)
            return self._ohlc(close, 0.0011)
        lvl = LEVEL[inst.base] / LEVEL[inst.quote]
        close = lvl * np.exp(self.paths[inst.base] - self.paths[inst.quote])
        return self._ohlc(close, 0.00045)

    def load_instrument(self, inst: Instrument, now: datetime) -> InstrumentData:
        m5_all = self.series(inst)
        m5 = m5_all[m5_all.index >= m5_all.index[-1] - pd.Timedelta(days=7)]
        m15 = resample(m5_all[m5_all.index >= m5_all.index[-1] - pd.Timedelta(days=30)], "15min")
        h1 = resample(m5_all, "1h")
        frames = build_frames(m5, m15, h1)
        price = float(m5.c.iloc[-1])
        half = (1.0 if inst.quote == "USD" or inst.base == "USD" else 1.8) * inst.pip / 2
        if inst.is_metal:
            half = {"XAU": 1.5, "XAG": 1.5, "XPT": 20, "XPD": 30}[inst.base] * inst.pip
        return InstrumentData(inst, frames, price, price - half, price + half,
                              m5.index[-1].to_pydatetime(), "sintético", True, ["dados sintéticos (modo offline)"])

    def load_instruments(self, insts, now, progress=None):
        out = {}
        for k, i in enumerate(insts, 1):
            out[i.symbol] = self.load_instrument(i, now)
            if progress:
                progress(k, len(insts))
        return out, {}

    def load_context(self, now: datetime) -> MarketContext:
        rng = np.random.default_rng(self.s.seed + 1)
        ctx = MarketContext(now=now)
        d_idx = pd.date_range(end=pd.Timestamp(now).normalize(), periods=260, freq="B", tz="UTC")
        h_idx = pd.date_range(end=pd.Timestamp(now).floor("h"), periods=24 * 22, freq="h", tz="UTC")
        base = {"DXY": 100.0, "US10Y": 4.5, "US5Y": 4.1, "US3M": 4.0, "VIX": 18.0,
                "SPX_FUT": 6500.0, "OIL": 80.0, "COPPER": 5.0, "GOLD_FUT": 4000.0}
        for name, lvl in base.items():
            for idx, store, vol in ((d_idx, ctx.macro, 0.01), (h_idx, ctx.macro_h1, 0.002)):
                c = lvl * np.exp(np.cumsum(rng.normal(0, vol, len(idx))))
                store[name] = pd.DataFrame({"o": c, "h": c * 1.002, "l": c * 0.998, "c": c, "v": 0.0}, index=idx)
        ctx.events = [
            Event(now + timedelta(hours=3), "USD", "CPI m/m", "High", "0.3%", "0.4%"),
            Event(now + timedelta(minutes=25), "NZD", "Business NZ PMI", "High", "50.1", "49.8"),
            Event(now + timedelta(hours=20), "EUR", "ECB Press Conference", "High"),
        ]
        ctx.rates = {c: PolicyRate(c, r, "2026-11-01", dr, "sintético") for c, r, dr in [
            ("USD", 3.875, 0.25), ("EUR", 2.5, 0.0), ("GBP", 3.75, -0.25), ("JPY", 1.0, 0.25),
            ("CHF", 0.0, 0.0), ("CAD", 2.5, -0.25), ("AUD", 4.1, 0.25), ("NZD", 2.75, -0.5)]}
        ctx.cot = {a: Cot(a, "2026-11-03", 1e4, float(rng.normal(0, 15)), float(rng.uniform(5, 95)),
                          float(rng.normal(0, 2)), float(rng.normal(0, 4)))
                   for a in MAJORS + list(METAL_LEVEL)}
        ctx.headlines = [
            Headline(now - timedelta(hours=1), "Aussie dollar rallies as RBA signals further tightening", "sintético", "forex"),
            Headline(now - timedelta(hours=2), "Yen slides as BOJ keeps policy unchanged", "sintético", "forex"),
            Headline(now - timedelta(hours=5), "Gold steadies ahead of US inflation data", "sintético", "commodities"),
        ]
        ctx.status = {k: "sintético" for k in ("calendar", "rates", "cot", "headlines")}
        return ctx

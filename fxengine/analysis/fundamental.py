"""Fundamental / macro layer.

Drivers (each mapped to a -1..1 bias for the pair):
  carry            policy-rate differential (BIS)
  política         6-month policy trajectory (hiking vs cutting cycle)
  risco            global risk appetite (VIX level/change, S&P futures) x currency risk beta
  juros EUA        US 5y/10y yield momentum (USD; inverted for metals = real-yield proxy)
  dólar (DXY)      metals only
  commodities      oil -> CAD, copper -> AUD/NZD/industrial metals, gold -> AUD
  COT              CFTC speculative positioning trend + crowding (contrarian at extremes)
  notícias         recency-weighted headline sentiment
Plus the economic-calendar gate that blocks entries around high-impact releases.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

from ..data.provider import MarketContext
from ..instruments import Instrument

RISK_BETA = {"AUD": 0.8, "NZD": 0.7, "CAD": 0.45, "GBP": 0.25, "EUR": 0.05, "USD": -0.3,
             "CHF": -0.6, "JPY": -0.9, "XAU": -0.45, "XAG": 0.15, "XPT": 0.45, "XPD": 0.45}
OIL_BETA = {"CAD": 0.6}
COPPER_BETA = {"AUD": 0.5, "NZD": 0.25, "XAG": 0.3, "XPT": 0.3, "XPD": 0.2}
GOLD_BETA = {"AUD": 0.25}

CCY_PATTERNS = [  # order matters: specific "X dollar" phrases are consumed before USD
    ("AUD", r"australian dollar|aussie|\brba\b|australia"),
    ("NZD", r"new zealand dollar|\bkiwi\b|\brbnz\b|new zealand"),
    ("CAD", r"canadian dollar|loonie|bank of canada|\bboc\b|canada"),
    ("USD", r"\bdollar\b|greenback|\bfed\b|fomc|powell|treasur(?:y|ies)|payrolls|\bdxy\b"),
    ("EUR", r"\beuro\b|\becb\b|lagarde|euro ?zone"),
    ("GBP", r"sterling|\bpound\b|bank of england|\bboe\b"),
    ("JPY", r"\byen\b|\bboj\b|bank of japan|ueda"),
    ("CHF", r"swiss franc|\bfranc\b|\bsnb\b"),
    ("XAU", r"\bgold\b|bullion"),
    ("XAG", r"\bsilver\b"),
    ("XPT", r"platinum"),
    ("XPD", r"palladium"),
]
BULL = r"\b(rise[sn]?|rising|gain(?:s|ed)?|climb(?:s|ed)?|jump(?:s|ed)?|surg(?:e|es|ed)|soar(?:s|ed)?|rall(?:y|ies|ied)|" \
       r"strengthen(?:s|ed)?|firm(?:s|er|ed)?|higher|beat(?:s)?|hawkish|hike[sd]?|tighten(?:s|ing)?|strong(?:er)?|" \
       r"record high|advance[sd]?|rebound(?:s|ed)?|best day|boost(?:s|ed)?|tops?|highs)\b"
BEAR = r"\b(fall(?:s|en)?|fell|drop(?:s|ped)?|slide[sd]?|slip(?:s|ped)?|sink(?:s)?|sank|tumble[sd]?|plunge[sd]?|" \
       r"weaken(?:s|ed)?|weak(?:er)?|lower|miss(?:es|ed)?|dovish|cut(?:s)?|slump(?:s|ed)?|loss(?:es)?|" \
       r"retreat(?:s|ed)?|decline[sd]?|ease[sd]?|dip(?:s|ped)?|lows|worst|recession)\b"


def headline_sentiment(title: str) -> dict[str, float]:
    t = title.lower()
    found: list[tuple[int, str]] = []
    for ccy, pat in CCY_PATTERNS:
        m = re.search(pat, t)
        if m:
            found.append((m.start(), ccy))
            t = t[:m.start()] + " " * (m.end() - m.start()) + t[m.end():]
    if not found:
        return {}
    s = len(re.findall(BULL, title.lower())) - len(re.findall(BEAR, title.lower()))
    s = float(np.clip(s, -1, 1))
    if s == 0:
        return {}
    found.sort()
    out = {found[0][1]: s}
    if re.search(r"\b(against|versus|vs\.?)\b", title.lower()):
        for _, c in found[1:]:
            out[c] = -0.5 * s
    return out


def _z_ret(df: pd.DataFrame | None, n: int) -> float:
    if df is None or len(df) < n + 25:
        return 0.0
    lr = np.log(df.c.astype(float))
    sig = lr.diff().iloc[-120:].std()
    if not sig or not np.isfinite(sig):
        return 0.0
    return float((lr.iloc[-1] - lr.iloc[-1 - n]) / (sig * np.sqrt(n)))


def _chg(df: pd.DataFrame | None, n: int) -> float:
    if df is None or len(df) < n + 1:
        return 0.0
    return float(df.c.iloc[-1] - df.c.iloc[-1 - n])


@dataclass
class Macro:
    risk: float                  # -1 risk-off .. +1 risk-on
    risk_label: str
    us_rates: float              # -1..1 (rising yields = +)
    dxy: float                   # -1..1
    oil: float
    copper: float
    gold: float
    vix: float | None
    us10y: float | None
    d10y_5d: float
    notes: list[str] = field(default_factory=list)


def macro_state(ctx: MarketContext) -> Macro:
    m = ctx.macro
    vix = m.get("VIX")
    notes = []
    vix_z = vix_chg = 0.0
    vix_last = None
    if vix is not None and len(vix) > 60:
        lv = np.log(vix.c)
        vix_z = float((lv.iloc[-1] - lv.iloc[-250:].mean()) / lv.iloc[-250:].std())
        vix_chg = float(lv.iloc[-1] - lv.iloc[-6]) / max(float(lv.diff().iloc[-120:].std()) * np.sqrt(5), 1e-6)
        vix_last = float(vix.c.iloc[-1])
    es = m.get("SPX_FUT")
    es_z = 0.6 * _z_ret(es, 5) + 0.4 * _z_ret(es, 1)
    risk = float(np.tanh(-0.45 * vix_z - 0.25 * vix_chg + 0.45 * es_z))
    label = ("risk-on" if risk > 0.25 else "risk-off" if risk < -0.25 else "neutro")
    if vix_last is not None:
        notes.append(f"VIX {vix_last:.1f} (z {vix_z:+.1f} vs 1 ano) | S&P fut z(5d) {_z_ret(es, 5):+.1f} → apetite a risco {label} ({risk:+.2f})")

    t10, t5 = m.get("US10Y"), m.get("US5Y")
    d10_5, d10_1 = _chg(t10, 5), _chg(t10, 1)
    d5_5, d5_1 = _chg(t5, 5), _chg(t5, 1)
    us_rates = float(0.6 * np.tanh((0.5 * d10_5 + 0.5 * d5_5) / 0.15) + 0.4 * np.tanh((0.5 * d10_1 + 0.5 * d5_1) / 0.07))
    us10 = float(t10.c.iloc[-1]) if t10 is not None and len(t10) else None
    if us10 is not None:
        notes.append(f"Treasury 10a {us10:.2f}% (5d {d10_5 * 100:+.0f}bp, 1d {d10_1 * 100:+.0f}bp) → viés juros EUA {us_rates:+.2f}")
    dxy = float(np.tanh((0.6 * _z_ret(m.get("DXY"), 5) + 0.4 * _z_ret(m.get("DXY"), 1)) / 1.5))
    oil = float(np.tanh(_z_ret(m.get("OIL"), 5) / 1.5))
    copper = float(np.tanh(_z_ret(m.get("COPPER"), 5) / 1.5))
    gold = float(np.tanh(_z_ret(m.get("GOLD_FUT"), 5) / 1.5))
    notes.append(f"DXY {dxy:+.2f} | petróleo {oil:+.2f} | cobre {copper:+.2f} | ouro {gold:+.2f} (momentum 5d normalizado)")
    return Macro(risk, label, us_rates, dxy, oil, copper, gold, vix_last, us10, d10_5, notes)


@dataclass
class FundamentalResult:
    score: float                         # -100..100
    components: dict[str, float]         # name -> -1..1 (pair bias, + = base up)
    weights: dict[str, float]
    facts: dict[str, str]                # name -> factual context for the narrative
    warnings: list[str]                  # direction-independent (events, crowding)
    event_block: bool
    event_mult: float
    events_ahead: list = field(default_factory=list)

    def narrative(self, symbol: str, d: int) -> tuple[list[str], list[str]]:
        """Reasons/warnings relative to the trade direction d."""
        reasons, warns = [], []
        ranked = sorted(self.components.items(), key=lambda kv: -abs(kv[1] * self.weights[kv[0]]))
        for k, v in ranked:
            if abs(v) < 0.15:
                continue
            side = "alta" if v > 0 else "baixa"
            fact = f" — {self.facts[k]}" if k in self.facts else ""
            if np.sign(v) == d:
                reasons.append(f"fundamental · {k}: favorece {side} de {symbol} ({v:+.2f}){fact}")
            else:
                warns.append(f"fundamental · {k}: aponta {side} de {symbol} ({v:+.2f}), contra o trade{fact}")
        return reasons, warns


class FundamentalModel:
    def __init__(self, ctx: MarketContext):
        self.ctx = ctx
        self.macro = macro_state(ctx)
        self.news = self._news_scores(ctx.now)
        self.cot_scores = {a: self._cot_score(c) for a, c in (ctx.cot or {}).items()}

    # ------------------------------------------------------------------ helpers
    def _news_scores(self, now: datetime) -> dict[str, float]:
        acc: dict[str, float] = {}
        for h in self.ctx.headlines or []:
            age_h = max((now - h.time).total_seconds() / 3600, 0)
            w = float(np.exp(-age_h / 12))
            for c, s in headline_sentiment(h.title).items():
                acc[c] = acc.get(c, 0.0) + w * s
        return {c: float(np.tanh(v / 1.5)) for c, v in acc.items()}

    @staticmethod
    def _cot_score(c) -> float:
        trend = np.tanh(c.chg_4w_pct / 6)
        crowd = -0.5 if c.index_3y > 90 else (0.5 if c.index_3y < 10 else 0.0)
        return float(np.clip(0.6 * trend + crowd, -1, 1))

    def _ccy_comm(self, c: str) -> float:
        mc = self.macro
        return OIL_BETA.get(c, 0) * mc.oil + COPPER_BETA.get(c, 0) * mc.copper + GOLD_BETA.get(c, 0) * mc.gold

    # ------------------------------------------------------------------ events
    def event_risk(self, inst: Instrument, before_min: int, after_min: int):
        ccys = {inst.base, inst.quote} if not inst.is_metal else {"USD", inst.base}
        ccys_cn = bool(ccys & {"AUD", "NZD"})       # China data moves the antipodeans
        block, mult, notes, ahead = False, 1.0, [], []
        now = self.ctx.now
        for e in self.ctx.events or []:
            relevant = e.ccy in ccys or e.ccy == "ALL" or (ccys_cn and e.ccy == "CNY")
            if not relevant:
                continue
            mins = (e.time - now).total_seconds() / 60
            impact = e.impact
            if e.ccy == "CNY" and impact == "High":
                impact = "Medium"
            if impact == "High":
                if -after_min <= mins <= before_min:
                    block = True
                    notes.append(f"BLOQUEIO: {e.ccy} {e.title} {'em' if mins >= 0 else 'há'} {abs(mins):.0f} min")
                elif before_min < mins <= 240:
                    mult *= 0.9
                    notes.append(f"{e.ccy} {e.title} em {mins / 60:.1f}h — encurtar o trade/alvo antes do dado")
                if 0 <= mins <= 24 * 60:
                    ahead.append(e)
            elif impact == "Medium" and -10 <= mins <= 20:
                mult *= 0.9
                notes.append(f"evento médio impacto {e.ccy} {e.title} em {mins:.0f} min")
            elif impact == "Holiday" and abs(mins) < 12 * 60:
                mult *= 0.92
                notes.append(f"feriado {e.ccy}: {e.title} (liquidez reduzida)")
        return block, mult, notes, ahead

    # ------------------------------------------------------------------ pair score
    def pair(self, inst: Instrument, before_min: int = 45, after_min: int = 20) -> FundamentalResult:
        mc, rates = self.macro, self.ctx.rates or {}
        b, q = inst.base, inst.quote
        comp: dict[str, float] = {}
        w: dict[str, float] = {}
        facts: dict[str, str] = {}
        warns: list[str] = []

        if inst.is_metal:
            usd = rates.get("USD")
            comp["juros EUA (real)"], w["juros EUA (real)"] = -mc.us_rates, 0.22
            comp["dólar (DXY)"], w["dólar (DXY)"] = -mc.dxy, 0.18
            comp["risco"], w["risco"] = float(np.clip(mc.risk * (RISK_BETA[b] - RISK_BETA["USD"]), -1, 1)), 0.14
            if usd:
                comp["política"], w["política"] = float(-np.tanh(usd.change_6m / 0.5)), 0.10
                comp["carry"], w["carry"] = float(np.tanh(-usd.rate / 4) * 0.5), 0.05
            if COPPER_BETA.get(b):
                comp["commodities"], w["commodities"] = float(np.clip(self._ccy_comm(b), -1, 1)), 0.05
        else:
            rb, rq = rates.get(b), rates.get(q)
            if rb and rq:
                diff = rb.rate - rq.rate
                comp["carry"], w["carry"] = float(np.tanh(diff / 2.0)) * (1 - 0.5 * max(0.0, -mc.risk)), 0.18
                comp["política"], w["política"] = float(np.tanh((rb.change_6m - rq.change_6m) / 0.5)), 0.14
                facts["carry"] = f"juros {b} {rb.rate:.2f}% vs {q} {rq.rate:.2f}% ({diff:+.2f} pp)"
                if rb.change_6m or rq.change_6m:
                    facts["política"] = f"6m: {b} {rb.change_6m:+.2f} pp, {q} {rq.change_6m:+.2f} pp"
            comp["risco"], w["risco"] = float(np.clip(mc.risk * (RISK_BETA[b] - RISK_BETA[q]) / 1.2, -1, 1)), 0.18
            if "USD" in (b, q):
                sgn = 1 if b == "USD" else -1
                comp["juros EUA"], w["juros EUA"] = sgn * mc.us_rates, 0.14
            cm = self._ccy_comm(b) - self._ccy_comm(q)
            if any(c in OIL_BETA or c in COPPER_BETA or c in GOLD_BETA for c in (b, q)):
                comp["commodities"], w["commodities"] = float(np.clip(cm, -1, 1)), 0.10

        cb, cq = self.cot_scores.get(b), self.cot_scores.get(q)
        if cb is not None or cq is not None:
            comp["COT"], w["COT"] = float(np.clip((cb or 0) - (cq or 0) if not inst.is_metal else (cb or 0), -1, 1)), 0.14
        nb, nq = self.news.get(b, 0.0), self.news.get(q, 0.0)
        if nb or nq:
            comp["notícias"], w["notícias"] = float(np.clip(nb - nq, -1, 1)), 0.12

        wsum = sum(w.values()) or 1.0
        score = float(np.clip(100 * sum(comp[k] * w[k] for k in comp) / wsum, -100, 100))

        facts["risco"] = f"apetite a risco {mc.risk_label} ({mc.risk:+.2f})"
        us = "juros EUA (real)" if inst.is_metal else "juros EUA"
        if us in comp and mc.us10y is not None:
            facts[us] = f"Treasury 10a {mc.us10y:.2f}%, {mc.d10y_5d * 100:+.0f}bp em 5d"
        if "commodities" in comp:
            facts["commodities"] = f"petróleo {mc.oil:+.2f}, cobre {mc.copper:+.2f}, ouro {mc.gold:+.2f}"
        if "dólar (DXY)" in comp:
            facts["dólar (DXY)"] = f"momentum DXY {mc.dxy:+.2f}"
        cot_txt = [f"{a} {c.net_pct_oi:+.0f}% OI (Δ4s {c.chg_4w_pct:+.1f}pp)"
                   for a in ((b,) if inst.is_metal else (b, q)) if (c := (self.ctx.cot or {}).get(a))]
        if "COT" in comp and cot_txt:
            facts["COT"] = "especuladores " + ", ".join(cot_txt)
        for a in (b, q):
            c = (self.ctx.cot or {}).get(a)
            if c and (c.index_3y > 90 or c.index_3y < 10):
                warns.append(f"COT {a}: especuladores em extremo ({c.index_3y:.0f}/100 em 3 anos) — risco de squeeze")

        block, mult, ev_notes, ahead = self.event_risk(inst, before_min, after_min)
        warns += ev_notes
        return FundamentalResult(score, comp, w, facts, warns, block, mult, ahead)

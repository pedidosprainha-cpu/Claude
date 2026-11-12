"""Data-quality guards run before any model sees the data.

A probability is only as good as its inputs. These checks catch the failure modes of free
data feeds: stale candles, bad ticks (spikes), holes in the history, a live quote that
disagrees with the chart, crossed or abnormal spreads, too little history for the features,
and situations outside what the models saw in training (out-of-distribution inputs).

severity: "ok" (nothing found) · "aviso" (shown, the reading is less reliable) ·
          "bloqueio" (the instrument must not produce a trade or an alert now)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

MIN_H1_BARS = 1500           # features need ~1200 closed bars (EMA 200, 750-bar vol, ADR, seasonality)


@dataclass
class DataCheck:
    issues: list[str] = field(default_factory=list)
    severity: str = "ok"

    def add(self, msg: str, sev: str) -> None:
        self.issues.append(msg)
        order = {"ok": 0, "aviso": 1, "bloqueio": 2}
        if order[sev] > order[self.severity]:
            self.severity = sev

    @property
    def blocked(self) -> bool:
        return self.severity == "bloqueio"


def check_h1(h1: pd.DataFrame | None, now: datetime, market_open: bool, check: DataCheck | None = None) -> DataCheck:
    """Closed-bar H1 history used by the models."""
    c = check or DataCheck()
    if h1 is None or h1.empty:
        c.add("sem candles H1", "bloqueio")
        return c
    if len(h1) < MIN_H1_BARS:
        c.add(f"histórico curto ({len(h1)} barras H1; o modelo precisa de {MIN_H1_BARS})", "bloqueio")
    px = h1[["o", "h", "l", "c"]].to_numpy(float)
    tail = px[-200:]
    if not np.isfinite(tail).all() or (tail <= 0).any():
        c.add("preços inválidos (vazios ou não positivos) nos candles recentes", "bloqueio")
        return c
    if (h1.h.iloc[-200:] < h1.l.iloc[-200:]).any():
        c.add("candles com máxima abaixo da mínima", "bloqueio")
    # stale feed: last closed bar too old while the market trades
    age_h = (pd.Timestamp(now) - (h1.index[-1] + pd.Timedelta(hours=1))).total_seconds() / 3600
    if market_open and age_h > 2.5:
        c.add(f"candles H1 atrasados ({age_h:.0f} h sem barra nova)", "bloqueio")
    # bad ticks: a bar whose range or close-to-close jump is far beyond the recent norm
    rng = (h1.h - h1.l).iloc[-600:]
    med = float(rng.iloc[:-48].median()) if len(rng) > 100 else float(rng.median())
    if med > 0:
        recent = rng.iloc[-48:]
        spikes = recent[recent > 10 * med]
        if len(spikes):
            when = spikes.index[-1].strftime("%d/%m %H:%M")
            late = spikes.index[-1] >= h1.index[-3]
            c.add(f"pico anômalo no candle de {when} UTC ({spikes.iloc[-1] / med:.0f}× o range típico): "
                  "possível erro de dado", "bloqueio" if late else "aviso")
    r = np.log(h1.c).diff().iloc[-600:]
    sd = float(r.iloc[:-48].std()) if len(r) > 100 else float(r.std())
    if sd > 0 and (r.iloc[-48:].abs() > 12 * sd).any():
        c.add("salto de preço entre candles muito acima do normal nas últimas 48 h", "aviso")
    # holes: missing hours in the last 3 trading days (weekends excluded)
    last = h1.index[-1]
    expect = pd.date_range(last - pd.Timedelta(hours=72), last, freq="1h")
    expect = expect[(expect.dayofweek < 5) & ~((expect.dayofweek == 4) & (expect.hour >= 21))]
    missing = len(expect.difference(h1.index))
    if missing > 8:
        c.add(f"{missing} horas faltando nos candles das últimas 72 h", "aviso")
    # frozen feed: many identical consecutive closes
    flat = (h1.c.iloc[-24:].diff() == 0).sum()
    if market_open and flat >= 12:
        c.add("cotação congelada em boa parte das últimas 24 h", "aviso")
    return c


def check_quote(bid: float, ask: float, last_close: float, adr: float | None, typical_spread: float,
                check: DataCheck | None = None) -> DataCheck:
    """Live quote against the chart and the usual spread."""
    c = check or DataCheck()
    if not (np.isfinite(bid) and np.isfinite(ask)) or bid <= 0 or ask <= 0:
        c.add("cotação ao vivo inválida", "bloqueio")
        return c
    if ask < bid:
        c.add("cotação invertida (ask < bid)", "bloqueio")
    spread = ask - bid
    if typical_spread > 0 and spread > 4 * typical_spread:
        c.add(f"spread {spread / typical_spread:.0f}× o normal agora", "aviso")
    mid = (bid + ask) / 2
    if adr and adr > 0 and np.isfinite(last_close) and abs(mid - last_close) > 1.0 * adr:
        c.add("cotação ao vivo distante do último candle (> 1 amplitude diária): dado suspeito", "bloqueio")
    return c


def out_of_range(feats: dict, ranges: dict, max_list: int = 3, margin: float = 0.25) -> list[str]:
    """Features clearly outside what training saw: beyond the 0.5%-99.5% range by more than
    `margin` x its width. (Plain 1% tails would flag ~40% of instruments by chance with ~50 inputs.)"""
    out = []
    for f, (lo, hi) in ranges.items():
        v = feats.get(f)
        if v is None or not np.isfinite(v):
            continue
        w = margin * (hi - lo)
        if v < lo - w or v > hi + w:
            out.append(f)
    return out[:max_list] if len(out) <= max_list else out[:max_list] + [f"+{len(out) - max_list}"]

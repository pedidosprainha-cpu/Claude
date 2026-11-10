"""Real-time breakout recognition.

For every instrument and timeframe (M15 and H1) the detector builds the levels
that matter for a breakout:

  * N-bar ranges (12 h on M15; 24 h and 5 days on H1)
  * tight consolidation boxes (range height small versus ATR)
  * the Asian-session range (M15, from 07:00 UTC)
  * the engine's S/R zones: prior day/week extremes, H1/H4/D1 swings, pivots,
    round numbers

and classifies what price is doing at each level *now*:

  rompendo    live price beyond the level, the bar has not closed yet
  confirmado  a recently closed bar finished beyond the level
  reteste     after the break price came back to the level and is holding
  falso       broke and closed back inside: a trap, traded the other way

Each event gets a 0-100 quality score (level significance, pre-break
compression, breakout-candle strength, higher-timeframe trend, currency
strength, extension, event risk, liquidity, spread and the instrument's own
historical follow-through) and a market-execution plan. A small on-disk
tracker remembers what was already seen, so a monitor loop can alert only on
new events.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from . import sessions
from .analysis import indicators as ta
from .analysis import strength as strength_mod
from .analysis.structure import level_map
from .analysis.technical import analyze_tf
from .config import Settings, grade
from .data.provider import LIGHT, InstrumentData
from .instruments import FX_PAIRS, Instrument, select
from .risk import position_size

TF_SPEC = {
    "M15": {"period": pd.Timedelta(minutes=15), "recent": 6, "pre": 24, "ranges": (48,),
            "htf": "H1", "horizon": 16},
    "H1": {"period": pd.Timedelta(hours=1), "recent": 4, "pre": 24, "ranges": (24, 120),
           "htf": "H4", "horizon": 12},
}
RANGE_NAME = {48: "12h", 24: "24h", 120: "5 dias"}
KIND_RANK = {"box": 3, "session": 2, "range": 1, "zone": 0}
STATUS_LABEL = {"rompendo": "ROMPENDO AGORA", "confirmado": "CONFIRMADO", "reteste": "RETESTE",
                "falso": "FALSO ROMPIMENTO"}


@dataclass
class Level:
    price: float
    labels: list[str]
    kind: str              # range | box | session | zone
    strength: float        # 0..10
    height: float | None = None
    direction: int = 0     # +1 resistance (break up), -1 support (break down), 0 either

    @property
    def label(self) -> str:
        return ", ".join(dict.fromkeys(self.labels))


@dataclass
class BreakoutPlan:
    entry: float
    sl: float
    tp1: float
    tp2: float
    sl_pips: float
    tp1_pips: float
    tp2_pips: float
    rr1: float
    rr2: float
    lots: float
    risk_amount: float
    sl_basis: str
    tp1_basis: str
    tp2_basis: str
    entry_type: str = "mercado"            # mercado | limite | confirmacao
    valid_until: datetime | None = None    # limit / confirmation expiry
    exit_kind: str = "tp"                  # tp | be | trail
    trail: float | None = None             # trailing distance (price units) once +1R is reached
    exit_rule: str = ""


ENTRY_TXT = {"mercado": "a mercado", "limite": "ordem limite", "confirmacao": "a mercado após confirmação"}
STOP_CFG = {"n05": ("level", 0.5), "n10": ("level", 1.0), "a10": ("fill", 1.0), "a15": ("fill", 1.5)}
EXIT_CFG = {"tp15": ("tp", 1.5), "tp2": ("tp", 2.0), "tp3": ("tp", 3.0), "be2": ("be", 2.0), "be3": ("be", 3.0),
            "tr10": ("trail", 1.0), "tr15": ("trail", 1.5)}


@dataclass
class Breakout:
    inst: Instrument
    tf: str
    direction: int          # trade direction: +1 buy, -1 sell
    break_dir: int          # direction price crossed the level (opposite of trade for 'falso')
    status: str             # rompendo | confirmado | reteste | falso
    extended: bool
    level: Level
    price: float
    bid: float
    ask: float
    atr: float
    ext_atr: float          # distance beyond the level, in ATRs, along break_dir
    bars_since: int         # closed bars since the break bar (0 = on the forming bar)
    broke_at: pd.Timestamp
    quality: float = 0.0
    grade: str = "D"
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    plan: BreakoutPlan | None = None
    hist_n: int = 0
    hist_wins: int = 0
    first_seen: datetime | None = None
    is_new: bool = False
    actionable: bool = False     # top tier (grade A or better) and not blocked
    blocked: bool = False        # extended, spread > 30% of the stop or high-impact event window
    features: dict = field(default_factory=dict)   # model inputs (see FEATURES)
    heuristic: float = 0.0       # rule-based score, kept for reference/comparison
    prob: float | None = None    # calibrated P(target 1 before stop), when a model is loaded
    ev_r: float | None = None    # expected R of the plan = prob*rr1 - (1-prob)
    spread_ratio: float = 0.0
    extreme: float = 0.0         # most extreme price since the break (stop anchor for traps)
    ref_close: float = 0.0       # close of the last closed bar at detection (confirmation reference)
    confirm_state: str = ""      # "" | pendente | confirmado | nao_confirmou (confirmation plans)
    confirmed_at: datetime | None = None

    @property
    def symbol(self) -> str:
        return self.inst.symbol

    @property
    def side(self) -> str:
        return "COMPRA" if self.direction == 1 else "VENDA"

    @property
    def hist_p(self) -> float:
        """Follow-through rate with a Beta(5,5) prior (shrinks small samples toward 50%)."""
        return (self.hist_wins + 5) / (self.hist_n + 10)

    def headline(self) -> str:
        i = self.inst
        if self.status == "falso":
            what = "acima" if self.break_dir == 1 else "abaixo"
            return (f"{self.symbol}: falso rompimento {what} de {i.fmt(self.level.price)} "
                    f"({self.level.label}, {self.tf})")
        verb = "rompendo" if self.status == "rompendo" else "rompeu"
        side = "para cima" if self.break_dir == 1 else "para baixo"
        return f"{self.symbol} {verb} {side} {i.fmt(self.level.price)} ({self.level.label}, {self.tf})"


# ---------------------------------------------------------------------------- helpers

def split_forming(df: pd.DataFrame, now: datetime, period: pd.Timedelta):
    """(closed bars, forming bar or None)."""
    if df.index[-1] + period > pd.Timestamp(now):
        return df.iloc[:-1], df.iloc[-1]
    return df, None


def follow_through(closed: pd.DataFrame, n: int, d: int, horizon: int) -> tuple[int, int]:
    """Past closes beyond the n-bar extreme: how often did price go +1 ATR before -1 ATR?"""
    if len(closed) < n + 40:
        return 0, 0
    c, h, l = closed.c.to_numpy(), closed.h.to_numpy(), closed.l.to_numpy()
    a = ta.atr(closed).to_numpy()
    ext = (closed.h if d == 1 else closed.l).rolling(n)
    lvl = (ext.max() if d == 1 else ext.min()).shift(1).to_numpy()
    beyond = d * (c - lvl) > 0
    prev = np.concatenate([[True], beyond[:-1]])
    idx = np.flatnonzero(beyond & ~prev)
    idx = idx[(idx > n + 15) & (idx < len(c) - horizon - 1)]
    total = wins = 0
    last_exit = -1
    for i in idx:
        if i <= last_exit or not np.isfinite(a[i]) or a[i] <= 0:
            continue
        entry = c[i]
        tgt, stp = entry + d * a[i], entry - d * a[i]
        outcome, k = None, i
        for k in range(i + 1, i + 1 + horizon):
            if (l[k] <= stp) if d == 1 else (h[k] >= stp):
                outcome = 0
                break
            if (h[k] >= tgt) if d == 1 else (l[k] <= tgt):
                outcome = 1
                break
        if outcome is None:
            outcome = int(d * (c[k] - entry) > 0)
        wins += outcome
        total += 1
        last_exit = k
    return total, wins


def _merge(levels: list[Level], tol: float) -> list[Level]:
    out: list[Level] = []
    for lv in sorted(levels, key=lambda x: x.price):
        m = next((o for o in out if abs(o.price - lv.price) <= tol
                  and (o.direction == lv.direction or 0 in (o.direction, lv.direction))), None)
        if m is None:
            out.append(Level(lv.price, list(lv.labels), lv.kind, lv.strength, lv.height, lv.direction))
            continue
        m.labels += lv.labels
        if KIND_RANK[lv.kind] > KIND_RANK[m.kind]:
            m.kind, m.price = lv.kind, lv.price
        m.strength = min(10.0, max(m.strength, lv.strength) + 1.5)
        m.height = max(filter(None, (m.height, lv.height)), default=None)
        m.direction = m.direction or lv.direction
    return out


def candidate_levels(tf: str, closed: pd.DataFrame, zones, price: float, a: float,
                     now: datetime) -> list[Level]:
    sp = TF_SPEC[tf]
    R, n = sp["recent"], len(closed)
    out: list[Level] = []
    for N in sp["ranges"]:
        if n < R + N + 5:
            continue
        ref = closed.iloc[-(R + N):-R]
        hi, lo = float(ref.h.max()), float(ref.l.min())
        name = RANGE_NAME.get(N, f"{N} barras")
        out.append(Level(hi, [f"máxima de {name}"], "range", 5.0, hi - lo, 1))
        out.append(Level(lo, [f"mínima de {name}"], "range", 5.0, hi - lo, -1))
    for B, k in ((32, 4.2), (24, 3.6), (16, 3.0)):
        if n < R + B + 5:
            continue
        box = closed.iloc[-(R + B):-R]
        hi, lo = float(box.h.max()), float(box.l.min())
        if hi - lo <= k * a:
            out.append(Level(hi, [f"topo da consolidação de {B} barras"], "box", 6.5, hi - lo, 1))
            out.append(Level(lo, [f"fundo da consolidação de {B} barras"], "box", 6.5, hi - lo, -1))
            break
    t = pd.Timestamp(now)
    if tf == "M15" and t.hour >= 7:
        day0 = t.normalize()
        asia = closed[(closed.index >= day0) & (closed.index < day0 + pd.Timedelta(hours=7))]
        if len(asia) >= 16:
            hi, lo = float(asia.h.max()), float(asia.l.min())
            out.append(Level(hi, ["máxima do range asiático"], "session", 6.0, hi - lo, 1))
            out.append(Level(lo, ["mínima do range asiático"], "session", 6.0, hi - lo, -1))
    for z in (zones.levels if zones is not None else []):
        if abs(z.price - price) <= 3 * a and z.strength >= 3.0:
            out.append(Level(z.price, [z.label()], "zone", float(z.strength), None, 0))
    return _merge(out, 0.3 * a)


def classify(level: Level, closed: pd.DataFrame, forming, price: float, a: float, R: int, pre: int):
    """Return (status, break_dir, break_index, extreme_after) or None."""
    c, h, l = closed.c.to_numpy(), closed.h.to_numpy(), closed.l.to_numpy()
    n = len(c)
    if n < R + pre + 2:
        return None
    L, tol = level.price, 0.05 * a
    dirs = [level.direction] if level.direction else [1, -1]
    for d in dirs:
        before = c[n - R - pre:n - R]
        # the level must have held before the recent window
        if np.mean(d * (before - L) <= tol) < (1.0 if level.direction else 0.75):
            continue
        if d * (c[n - R - 1] - L) > tol:
            continue
        j = next((k for k in range(n - R, n) if d * (c[k] - L) > tol), None)
        f_hi = float(forming.h) if forming is not None else -np.inf
        f_lo = float(forming.l) if forming is not None else np.inf
        if j is None:
            if forming is not None and d * (price - L) > tol:
                return "rompendo", d, n, (f_hi if d == 1 else f_lo)
            continue
        extreme = max(float(h[j:].max()), f_hi) if d == 1 else min(float(l[j:].min()), f_lo)
        closed_back = any(d * (x - L) < -tol for x in c[j + 1:])
        inside_now = d * (price - L) < -tol
        if (closed_back and inside_now) or d * (price - L) < -0.3 * a:
            return "falso", d, j, extreme
        lows = l[j + 1:] if d == 1 else h[j + 1:]
        probe = list(lows) + ([f_lo if d == 1 else f_hi] if forming is not None else [])
        touched = any(d * (x - L) <= 0.3 * a for x in probe)
        return ("reteste" if touched else "confirmado"), d, j, extreme
    return None


# ---------------------------------------------------------------------------- detection

def detect(data: InstrumentData, now: datetime, s: Settings, prices: dict[str, float],
           strength, events: list, sess, cache: dict | None = None,
           model: "BreakoutModel | None" = None) -> list[Breakout]:
    """Find breakouts for one instrument.

    `cache` lets a caller (the historical replay) reuse slow, hour-level work
    (S/R zones, higher-timeframe views) across consecutive M15 steps.
    `model` defaults to the shipped calibrated model (fxengine/data/breakout_model.json).
    """
    inst, frames = data.inst, data.frames
    cache = {} if cache is None else cache
    model = load_model(MODEL_PATHS.get(s.breakout_plan, MODEL_PATH)) if model is None else model
    out: list[Breakout] = []
    ctx_memo: dict[int, dict] = {}
    h1 = frames.get("H1")
    if "zones" not in cache:
        cache["zones"] = (level_map(frames, data.price, inst.round_step, float(ta.atr(h1).iloc[-1]))
                          if h1 is not None and len(h1) > 30 else None)
    zones = cache["zones"]
    if "atr_h1" not in cache:
        cache["atr_h1"] = float(ta.atr(h1).iloc[-1]) if h1 is not None and len(h1) > 30 else None
    for tf, sp in TF_SPEC.items():
        df = frames.get(tf)
        if df is None or len(df) < 80:
            continue
        closed, forming = split_forming(df, now, sp["period"])
        a = float(ta.atr(closed).iloc[-1])
        if not np.isfinite(a) or a <= 0:
            continue
        key = "htf:" + sp["htf"]
        if key not in cache:
            cache[key] = analyze_tf(sp["htf"], frames.get(sp["htf"]))
        htf = cache[key]
        bb_l, bb_m, bb_u = ta.bollinger(closed.c)
        bbw = ((bb_u - bb_l) / bb_m).iloc[-200:]
        tf_ctx = None
        for lv in candidate_levels(tf, closed, zones, data.price, a, now):
            res = classify(lv, closed, forming, data.price, a, sp["recent"], sp["pre"])
            if res is None:
                continue
            if tf_ctx is None:
                tf_ctx = _tf_context(closed, a)
            status, bd, j, extreme = res
            td = -bd if status == "falso" else bd
            ext = bd * (data.price - lv.price) / a
            run = td * (data.price - lv.price) / a          # how far price already went for the trade
            idx = closed.index[j] if j < len(closed) else df.index[-1]
            b = Breakout(inst, tf, td, bd, status, run > 2.2, lv, data.price,
                         data.bid, data.ask, a, ext, max(len(closed) - 1 - j, 0) if j < len(closed) else 0, idx)
            b.extreme = float(extreme)
            b.ref_close = float(closed.c.iloc[-1])
            _score(b, closed, forming, j, bbw, htf, strength, events, sess, now)
            atr_h1 = cache["atr_h1"] or a
            m_tf = _tf_model(model, tf)
            live = m_tf is not None and not m_tf.info.get("disabled")
            if live and m_tf.plan:
                b.plan = _plan_validated(b, s, prices, atr_h1, m_tf.plan, now)
            else:
                b.plan = _plan(b, extreme, zones, s, prices, atr_h1, m_tf.geometry if live else None)
            spread_ratio = (data.ask - data.bid) / (b.plan.sl_pips * inst.pip) if b.plan.sl_pips > 0 else 1.0
            b.spread_ratio = spread_ratio
            if spread_ratio > 0.3:
                b.quality -= 20
                b.cons.append(f"spread consome {spread_ratio * 100:.0f}% do stop — evitar")
            elif spread_ratio > 0.2:
                b.quality -= 10
                b.cons.append(f"spread alto ({spread_ratio * 100:.0f}% do stop)")
            if status != "falso":
                b.hist_n, b.hist_wins = follow_through(closed, sp["ranges"][0], bd, sp["horizon"])
                if b.hist_n >= 8:
                    if b.hist_p >= 0.55:
                        b.quality += 4
                        b.pros.append(f"rompimentos neste ativo/TF costumam seguir ({b.hist_wins}/{b.hist_n})")
                    elif b.hist_p <= 0.42:
                        b.quality -= 5
                        b.cons.append(f"rompimentos neste ativo/TF costumam falhar ({b.hist_wins}/{b.hist_n} seguiram)")
            b.features = _features(b, closed, j, bbw, htf, strength, sess, zones, tf_ctx, sp)
            if b.direction not in ctx_memo:            # per call only: hour/day values must be current
                ctx_memo[b.direction] = context_features(h1, data.price, b.direction, now)
            b.features.update(ctx_memo[b.direction])
            b.heuristic = float(np.clip(b.quality, 0, 100))
            event_block = any(c.startswith("evento de alto impacto") for c in b.cons)
            _finalize(b, _tf_model(model, tf), s, event_block)
            out.append(b)
    # one event per level across timeframes: keep the best-scored one
    kept: list[Breakout] = []
    for b in sorted(out, key=lambda x: x.quality, reverse=True):
        if not any(k.direction == b.direction and (k.status == "falso") == (b.status == "falso")
                   and abs(k.level.price - b.level.price) <= 0.5 * max(k.atr, b.atr) for k in kept):
            kept.append(b)
    # never two actionable signals in opposite directions on the same instrument
    act = sorted((b for b in kept if b.actionable), key=lambda x: (x.ev_r if x.ev_r is not None else x.quality),
                 reverse=True)
    if act:
        lead = act[0].direction
        for b in act[1:]:
            if b.direction != lead:
                b.actionable = False
                b.blocked = True
                b.cons.append("há um sinal mais forte na direção oposta neste ativo")
    return kept


# ---------------------------------------------------------------------------- features / model

FEATURES = [
    "tf_h1", "st_reteste", "st_falso", "st_rompendo", "kind_box", "kind_session", "kind_zone",
    "lvl_strength", "n_refs", "ref_daily", "ext_atr", "run_atr", "bars_since", "bbw_pct",
    "brk_body", "brk_range", "brk_clv", "htf_trend", "htf_mom", "strength_dir", "liq",
    "sess_asia", "sess_overlap", "spread_ratio", "rr1", "room_atr", "touches", "approach",
    "adx", "atr_pct", "hist_p", "is_metal", "is_long",
] + [
    # context (research/augment_features.py computes these offline with the same function)
    "h_london", "h_ny", "h_asia", "h_sin", "h_cos", "dow_mon", "dow_fri",
    "adr_used", "day_pos", "move_today", "d1_trend", "d1_dist", "w1_pos",
]


def context_features(h1: pd.DataFrame, price: float, td: int, now: datetime) -> dict:
    """Time-of-day, daily-range exhaustion and higher-timeframe position, in trade direction.

    Uses only H1 bars up to `now` (the forming bar included), so the live monitor and the
    historical replay compute identical values."""
    t = pd.Timestamp(now)
    hour = t.hour + t.minute / 60
    out = {"h_london": float(7 <= hour < 10), "h_ny": float(12 <= hour < 15),
           "h_asia": float(hour >= 22 or hour < 6),
           "h_sin": float(np.sin(2 * np.pi * hour / 24)), "h_cos": float(np.cos(2 * np.pi * hour / 24)),
           "dow_mon": float(t.dayofweek == 0), "dow_fri": float(t.dayofweek == 4),
           "adr_used": 0.5, "day_pos": 0.0, "move_today": 0.0, "d1_trend": 0.0, "d1_dist": 0.0, "w1_pos": 0.0}
    if h1 is None or len(h1) < 48:
        return out
    d1 = ta.ny_daily(h1)
    if len(d1) < 16:
        return out
    atr_d = float(ta.atr(d1).iloc[-2]) if len(d1) > 15 else float((d1.h - d1.l).mean())
    if not np.isfinite(atr_d) or atr_d <= 0:
        return out
    today = d1.iloc[-1]
    rng = float(today.h - today.l)
    mid = (float(today.h) + float(today.l)) / 2
    ema = ta.ema(d1.c, 20)
    out["adr_used"] = float(np.clip(rng / atr_d, 0, 3))
    out["day_pos"] = float(np.clip(td * (price - mid) / max(rng / 2, 1e-12), -1.5, 1.5))
    out["move_today"] = float(np.clip(td * (price - float(today.o)) / atr_d, -3, 3))
    out["d1_trend"] = float(np.clip(td * (ema.iloc[-1] - ema.iloc[-6]) / (5 * atr_d) * 5, -3, 3))
    out["d1_dist"] = float(np.clip(td * (price - ema.iloc[-1]) / atr_d, -4, 4))
    w1 = ta.resample(d1.assign(v=0.0), "W-FRI")
    if len(w1) >= 2:
        pw = w1.iloc[-2]
        wr = float(pw.h - pw.l)
        if wr > 0:
            out["w1_pos"] = float(np.clip(td * (price - (pw.h + pw.l) / 2) / (wr / 2), -3, 3))
    return out


def _tf_context(closed: pd.DataFrame, a: float) -> dict:
    adx = float(ta.adx(closed)[0].iloc[-1])
    atr_s = ta.atr(closed).iloc[-300:]
    atr_pct = float(atr_s.rank(pct=True).iloc[-1]) if atr_s.notna().sum() > 30 else 0.5
    return {"adx": adx if np.isfinite(adx) else 20.0, "atr_pct": atr_pct}


def _features(b: Breakout, closed: pd.DataFrame, j: int, bbw, htf, strength, sess, zones,
              tf_ctx: dict, sp: dict) -> dict:
    a, td, bd, L = b.atr, b.direction, b.break_dir, b.level.price
    n, R, pre = len(closed), sp["recent"], sp["pre"]
    c, h, l = closed.c.to_numpy(), closed.h.to_numpy(), closed.l.to_numpy()
    k = min(j, n - 1)
    rng = float(h[k] - l[k])
    body = abs(float(c[k] - closed.o.iloc[k]))
    clv = ((c[k] - l[k]) / rng if bd == 1 else (h[k] - c[k]) / rng) if rng > 0 else 0.5
    pos = n - 1 - min(max(j - 1, 0), n - 1)
    bbw_pct = float(bbw.rank(pct=True).iloc[-1 - pos]) if len(bbw) > 30 and pos < len(bbw) else 0.5
    win = slice(max(n - R - pre, 0), n - R)
    ext_arr = h[win] if bd == 1 else l[win]
    touches = int(np.sum(np.abs(ext_arr - L) <= 0.15 * a))
    approach = bd * (c[n - R - 1] - c[max(n - R - pre, 0)]) / (a * np.sqrt(pre)) if n > R + pre else 0.0
    room = 5.0
    if zones is not None:
        opp = zones.above(b.price) if td == 1 else zones.below(b.price)
        far = [td * (z.price - b.price) / a for z in opp if td * (z.price - b.price) > 0.25 * a]
        room = min(far[0], 5.0) if far else 5.0
    ps = strength.pair_score(b.inst.base, b.inst.quote) * td / 100 if (strength is not None and not b.inst.is_metal) else 0.0
    active = set(sess.active)
    labels = set(b.level.labels)
    return {
        "tf_h1": float(b.tf == "H1"),
        "st_reteste": float(b.status == "reteste"),
        "st_falso": float(b.status == "falso"),
        "st_rompendo": float(b.status == "rompendo"),
        "kind_box": float(b.level.kind == "box"),
        "kind_session": float(b.level.kind == "session"),
        "kind_zone": float(b.level.kind == "zone"),
        "lvl_strength": min(b.level.strength, 10.0) / 10,
        "n_refs": min(len(labels), 5) / 5,
        "ref_daily": float(any(("dia anterior" in x) or ("semana anterior" in x) for x in labels)),
        "ext_atr": float(np.clip(b.ext_atr, -3, 3)),
        "run_atr": float(np.clip(td * (b.price - L) / a, -3, 4)),
        "bars_since": min(b.bars_since, R) / R,
        "bbw_pct": bbw_pct,
        "brk_body": body / rng if rng > 0 else 0.0,
        "brk_range": float(np.clip(rng / a, 0, 4)),
        "brk_clv": float(clv),
        "htf_trend": float(htf.trend * td) if htf is not None else 0.0,
        "htf_mom": float(htf.momentum * td) if htf is not None else 0.0,
        "strength_dir": float(ps),
        "liq": sessions.liquidity_factor(sess, b.inst.base, b.inst.quote, b.inst.is_metal)[0],
        "sess_asia": float(bool(active) and not (active & {"Londres", "Nova York"})),
        "sess_overlap": float({"Londres", "Nova York"} <= active),
        "spread_ratio": float(min(b.spread_ratio, 1.0)),
        "rr1": float(min(b.plan.rr1, 4.0)),
        "room_atr": float(room),
        "touches": min(touches, 6) / 6,
        "approach": float(np.clip(approach, -3, 3)),
        "adx": tf_ctx["adx"] / 50,
        "atr_pct": tf_ctx["atr_pct"],
        "hist_p": b.hist_p if b.hist_n >= 8 else 0.5,
        "is_metal": float(b.inst.is_metal),
        "is_long": float(td == 1),
    }


@dataclass
class BreakoutModel:
    """Logistic model P(target 1 before stop) trained on the historical replay (research/)."""
    features: list[str]
    mean: np.ndarray
    std: np.ndarray
    coef: np.ndarray
    intercept: float
    ev_grades: list[tuple[float, str]]     # (min expected R, grade), best first
    ev_actionable: float                   # minimum expected R to be actionable
    p_actionable: float                    # minimum probability to be actionable
    info: dict
    geometry: dict = field(default_factory=dict)   # {"stop_atr_h1": k | None, "tp1_r": m | None}
    exclude_status: list = field(default_factory=list)  # statuses that lost money in validation
    exclude_metals: bool = False
    plan: dict = field(default_factory=dict)        # validated entry/stop/exit (version 2)
    win_r: float = 0.0                              # average R of winning trades (version 2)
    loss_r: float = -1.0                            # average R of losing trades (version 2)
    enabled: bool = True                            # False: timeframe never reaches grade A
    validated: bool = True                          # False: enabled by user choice, not by the validation rule
    mtype: str = "logit"                            # logit | gbm
    gbm: dict = field(default_factory=dict)         # {"base": z0, "trees": [[f, thr, left, right, leaf], ...]}
    platt: tuple = (1.0, 0.0)                       # recalibration applied to the GBM score

    def expected_r(self, p: float, rr1: float) -> float:
        if self.plan:
            return p * self.win_r + (1 - p) * self.loss_r
        return p * rr1 - (1 - p)


    def prob(self, feats: dict) -> float:
        x = np.array([derived_value(f, feats) for f in self.features], dtype=float)
        if self.mtype == "gbm":
            z = float(self.gbm.get("base", 0.0))
            for nodes in self.gbm.get("trees", []):
                i = 0
                while nodes[i][0] >= 0:
                    f, thr, li, ri, _ = nodes[i]
                    i = li if x[int(f)] <= thr else ri
                z += nodes[i][4]
            a, b = self.platt
            return float(1 / (1 + np.exp(-(a * z + b))))
        z = (x - self.mean) / self.std
        return float(1 / (1 + np.exp(-(z @ self.coef + self.intercept))))


class ModelSet:
    """One calibrated model per timeframe (fxengine/data/breakout_model.json, version 2)."""

    def __init__(self, models: dict, info: dict):
        self.models, self.info = models, info

    def for_tf(self, tf: str) -> "BreakoutModel | None":
        return self.models.get(tf) or self.models.get("*")


def derived_value(name: str, feats: dict) -> float:
    """Feature value by name; supports squares ("x^2") and interactions ("a*b")."""
    if name.endswith("^2"):
        v = feats.get(name[:-2], 0.0)
        return v * v
    if "*" in name:
        a, b = name.split("*", 1)
        return feats.get(a, 0.0) * feats.get(b, 0.0)
    return feats.get(name, 0.0)


_MODEL_CACHE: dict = {}
MODEL_PATHS = {
    "mercado": os.path.join(os.path.dirname(__file__), "data", "breakout_model_mercado.json"),
    "limite": os.path.join(os.path.dirname(__file__), "data", "breakout_model_limite.json"),
}
MODEL_PATH = MODEL_PATHS["mercado"]


def _model_from(d: dict, info: dict | None = None) -> BreakoutModel:
    return BreakoutModel(d["features"], np.array(d["mean"]), np.array(d["std"]), np.array(d["coef"]),
                         float(d["intercept"]), [(float(t), g) for t, g in d["ev_grades"]],
                         float(d["ev_actionable"]), float(d.get("p_actionable", 0.0)), info or d.get("info", {}),
                         d.get("geometry") or {}, list(d.get("exclude_status") or []),
                         bool(d.get("exclude_metals", False)), d.get("plan") or {},
                         float(d.get("win_r", 0.0)), float(d.get("loss_r", -1.0)), bool(d.get("enabled", True)),
                         bool(d.get("validated", d.get("enabled", True))),
                         d.get("type", "logit"), d.get("gbm") or {}, tuple(d.get("platt") or (1.0, 0.0)))


def load_model(path: str = MODEL_PATH) -> "ModelSet | BreakoutModel | None":
    """Version 2 file -> ModelSet (one model per timeframe); version 1 -> single BreakoutModel."""
    if path in _MODEL_CACHE:
        return _MODEL_CACHE[path]
    m = None
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("version") == 2:
            m = ModelSet({tf: _model_from(md, d.get("info", {})) for tf, md in d["models"].items()},
                         d.get("info", {}))
        else:
            m = _model_from(d)
    except (OSError, ValueError, KeyError):
        m = None
    _MODEL_CACHE[path] = m
    return m


def model_summary(plan: str) -> dict | None:
    """Validation numbers of a profile, for the app's validation card (read straight from the file)."""
    path = MODEL_PATHS.get(plan, MODEL_PATH)
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    info = d.get("info", {})
    tfs = {}
    for tf, m in d.get("models", {}).items():
        tfs[tf] = {"enabled": m.get("enabled"), "validated": m.get("validated", m.get("enabled")),
                   "plan": m.get("plan"), "test": m.get("test"), "walk_forward": m.get("walk_forward")}
    return {"profile": d.get("profile", plan), "events": info.get("events"), "period": info.get("period"),
            "timeframes": tfs}


def _tf_model(model, tf: str):
    return model.for_tf(tf) if isinstance(model, ModelSet) else model


NO_MODEL = BreakoutModel([], np.zeros(0), np.ones(0), np.zeros(0), 0.0, [], 0.0, 0.0, {"disabled": True})


def _finalize(b: Breakout, model: BreakoutModel | None, s: Settings, event_block: bool) -> None:
    """Turn features into probability, expected R, grade and the actionable flag."""
    hard_block = event_block or b.extended or b.spread_ratio > 0.3
    b.blocked = hard_block
    early = b.status == "rompendo" and b.tf == "M15"     # never seen by the model: pre-alert only
    if model is None or model.info.get("disabled"):
        b.quality = b.heuristic
        b.grade = grade(b.quality)
        b.actionable = b.quality >= s.min_score and not hard_block and b.status != "rompendo"
        return
    p = model.prob(b.features)
    b.prob = p
    b.ev_r = model.expected_r(p, b.plan.rr1)
    b.quality = round(p * 100, 1)
    b.grade = next((g for t, g in model.ev_grades if b.ev_r >= t), "D")
    eligible = (model.enabled and b.status not in model.exclude_status
                and not (b.inst.is_metal and model.exclude_metals))
    if not eligible and b.grade in ("A+", "A"):
        b.grade = "B"
    b.actionable = (eligible and b.ev_r >= model.ev_actionable and p >= model.p_actionable
                    and not hard_block and not early)
    if early:
        b.blocked = True
        b.cons.append("pré-alerta: o alerta sai quando o candle M15 fechar além do nível")
    elif b.status in model.exclude_status:
        b.cons.append("no histórico este tipo de sinal perdeu dinheiro: só informativo, sem alerta")
    elif b.inst.is_metal and model.exclude_metals:
        b.cons.append("rompimentos em metais não tiveram expectativa positiva no histórico: só informativo")
    elif not model.enabled:
        b.cons.append(f"rompimentos {b.tf} não passaram na validação histórica: só informativo, sem alerta")


def _score(b: Breakout, closed, forming, j, bbw, htf, strength, events, sess, now) -> None:
    q, pros, cons = 35.0, b.pros, b.cons
    lv, a, td = b.level, b.atr, b.direction
    q += min(lv.strength, 10.0)
    if lv.kind == "box":
        q += 5
        pros.append("saída de consolidação apertada (energia acumulada)")
    elif lv.kind == "session":
        q += 4
        pros.append("rompimento do range asiático")
    if any(("dia anterior" in x) or ("semana anterior" in x) for x in lv.labels):
        q += 4
        pros.append("nível de referência diário/semanal")
    if len(set(lv.labels)) >= 2:
        q += 3
        pros.append(f"confluência de {len(set(lv.labels))} referências no mesmo nível")

    k = min(max(j - 1, 0), len(closed) - 1)
    pos = len(closed) - 1 - k
    if len(bbw) > 30 and pos < len(bbw):
        pct = float(bbw.rank(pct=True).iloc[-1 - pos]) * 100
        if pct < 25:
            q += 6
            pros.append(f"volatilidade comprimida antes do rompimento (percentil {pct:.0f})")

    if b.status == "falso":
        q += 2
        pros.append("preço voltou para dentro do nível: armadilha para quem entrou no rompimento")
    elif b.status == "rompendo":
        if forming is not None and td * (b.price - float(forming.o)) >= 0.6 * a:
            q += 4
            pros.append("candle atual empurrando forte além do nível")
        cons.append("candle ainda não fechou além do nível")
    else:
        bar = closed.iloc[j]
        rng, body = float(bar.h - bar.l), abs(float(bar.c - bar.o))
        if rng > 0 and body / rng >= 0.6 and rng >= 1.1 * a:
            q += 6
            pros.append("candle de rompimento forte (corpo grande, range acima do ATR)")
        elif rng > 0 and body / rng < 0.35:
            q -= 5
            cons.append("candle de rompimento fraco (muito pavio)")
        if b.status == "reteste":
            q += 6
            pros.append("reteste do nível segurou: rompimento validado")
        else:
            q += 3
            pros.append(f"fechamento confirmado além do nível há {b.bars_since} barra(s)")

    if htf is not None:
        t = htf.trend * td
        if t > 0.3:
            q += 8
            pros.append(f"a favor da tendência {htf.tf}")
        elif t < -0.3:
            q -= 10
            cons.append(f"contra a tendência {htf.tf}")

    if strength is not None and not b.inst.is_metal:
        ps = strength.pair_score(b.inst.base, b.inst.quote) * td
        if ps >= 30:
            q += 4
            pros.append("força relativa das moedas a favor")
        elif ps <= -30:
            q -= 5
            cons.append("força relativa das moedas contra")

    if b.extended:
        q -= 15
        cons.append(f"esticado: preço já andou {abs(b.ext_atr):.1f} ATR desde o nível — melhor esperar reteste")
    elif b.status != "falso" and b.ext_atr > 1.5:
        q -= 5
        cons.append(f"já {b.ext_atr:.1f} ATR além do nível")

    ccys = {b.inst.base, b.inst.quote} if not b.inst.is_metal else {"USD", b.inst.base}
    for e in events or []:
        if e.impact != "High" or not (e.ccy in ccys or e.ccy == "ALL"):
            continue
        mins = (e.time - now).total_seconds() / 60
        if -15 <= mins <= 45:
            q -= 20
            cons.append(f"evento de alto impacto: {e.ccy} {e.title} {'em' if mins >= 0 else 'há'} {abs(mins):.0f} min")
        elif 45 < mins <= 120:
            q -= 5
            cons.append(f"{e.ccy} {e.title} em {mins / 60:.1f}h")

    liq, note = sessions.liquidity_factor(sess, b.inst.base, b.inst.quote, b.inst.is_metal)
    if 0 < liq < 0.8:
        q -= 6
        cons.append(f"liquidez baixa: {note}")
    b.quality = q


def _plan_validated(b: Breakout, s: Settings, prices: dict, atr_h1: float, pcfg: dict,
                    now: datetime) -> BreakoutPlan:
    """Entry/stop/exit exactly as validated in research/entry_exit_lab.py for this timeframe."""
    inst, a, td, L = b.inst, b.atr, b.direction, b.level.price
    half = max(b.ask - b.bid, 0.0) / 2
    market = b.ask if td == 1 else b.bid
    period = TF_SPEC[b.tf]["period"]
    em = pcfg.get("entry", "mercado")
    entry_type, entry, valid_until = "mercado", market, None
    if em in ("reteste", "meio"):
        limit = (L + td * 0.1 * a) if em == "reteste" else (b.price - td * 0.5 * abs(b.price - L))
        if td * (market - limit) > 0:
            entry_type, entry = "limite", limit
            valid_until = pd.Timestamp(now).floor(period).to_pydatetime() + int(pcfg.get("window", 6)) * period
    elif em == "confirmacao":
        entry_type = "confirmacao"
        valid_until = pd.Timestamp(now).floor(period).to_pydatetime() + period
    anchor, m = STOP_CFG.get(pcfg.get("stop", "a15"), ("fill", 1.5))
    trap = b.status == "falso"
    if anchor == "level":
        sl_px = (b.extreme + b.break_dir * m * 0.5 * atr_h1) if trap else (L - td * m * atr_h1)
        sl_d = td * (entry - sl_px)
        sl_basis = (f"além do extremo do falso rompimento ({inst.fmt(b.extreme)})" if trap
                    else f"{m:g} ATR H1 além do nível rompido {inst.fmt(L)}")
    else:
        sl_d = m * atr_h1
        sl_basis = f"{m:g} ATR H1 a partir da entrada"
    floor = max(0.3 * atr_h1, 8 * half)
    if sl_d < floor:
        sl_d, sl_basis = floor, sl_basis + " · distância mínima"
    sl = entry - td * sl_d
    kind, val = EXIT_CFG.get(pcfg.get("exit", "tp2"), ("tp", 2.0))
    trail = None
    if kind == "tp":
        tp1_d = tp2_d = val * sl_d
        tp1_basis = tp2_basis = f"alvo fixo {val:g}R"
        rule = f"saída no alvo de {val:g}R ou no stop"
        rr1 = val
    elif kind == "be":
        tp1_d, tp2_d = sl_d, val * sl_d
        tp1_basis, tp2_basis = "+1R: mova o stop para a entrada", f"alvo final {val:g}R"
        rule = f"em +1R mova o stop para a entrada; alvo final {val:g}R"
        rr1 = val
    else:
        trail = val * atr_h1
        tp1_d, tp2_d = sl_d, 3 * sl_d
        tp1_basis = f"+1R: ative o stop móvel ({inst.pips(trail):.0f} pips atrás do melhor preço)"
        tp2_basis = "referência 3R (sem alvo fixo: o stop móvel decide a saída)"
        rule = (f"sem alvo fixo: ao atingir +1R, mantenha o stop {inst.pips(trail):.0f} pips "
                f"({val:g} ATR H1) atrás do melhor preço, nunca abaixo da entrada")
        rr1 = 1.0
    lots, risk_amount, _ = position_size(inst, sl_d, s.balance, s.risk_pct, prices, s.account_ccy)
    return BreakoutPlan(entry, sl, entry + td * tp1_d, entry + td * tp2_d, inst.pips(sl_d), inst.pips(tp1_d),
                        inst.pips(tp2_d), rr1, tp2_d / sl_d, lots, risk_amount, sl_basis, tp1_basis, tp2_basis,
                        entry_type, valid_until, kind, trail, rule)


def _plan(b: Breakout, extreme: float, zones, s: Settings, prices: dict, atr_h1: float,
          geo: dict | None = None) -> BreakoutPlan:
    inst, a, td, L = b.inst, b.atr, b.direction, b.level.price
    entry = b.ask if td == 1 else b.bid
    spread = max(b.ask - b.bid, 0.0)
    if b.status == "falso":
        sl = extreme + b.break_dir * (0.25 * a + spread)
        sl_basis = f"além do extremo do falso rompimento ({inst.fmt(extreme)})"
    else:
        sl = L - td * (0.35 * a + spread)
        sl_basis = f"de volta para dentro do nível {inst.fmt(L)} (rompimento invalidado)"
    sl_dist = td * (entry - sl)
    min_d = max(0.6 * a, 4 * spread, 0.4 * atr_h1 if b.tf == "M15" else 0.0)
    if sl_dist < min_d:
        sl_dist = min_d
        sl = entry - td * sl_dist
        sl_basis += " · ampliado para a distância mínima (volatilidade/spread)"
    k_sl = (geo or {}).get("stop_atr_h1")
    if k_sl and sl_dist < k_sl * atr_h1:
        sl_dist = k_sl * atr_h1
        sl = entry - td * sl_dist
        sl_basis += f" · {k_sl:g} ATR H1 (geometria validada no histórico)"

    targets = [] if zones is None else (zones.above(entry) if td == 1 else zones.below(entry))
    front = 0.1 * a
    tp1_dist, tp1_basis = None, ""
    for z in targets:
        dist = td * (z.price - entry) - front
        if dist >= sl_dist:
            if dist <= 2.5 * sl_dist:
                tp1_dist, tp1_basis = dist, f"antes da zona {inst.fmt(z.price)} ({z.label()})"
            break
    if tp1_dist is None:
        tp1_dist, tp1_basis = 1.5 * sl_dist, "sem zona relevante antes"
    k_tp = (geo or {}).get("tp1_r")
    if k_tp:
        tp1_dist, tp1_basis = k_tp * sl_dist, f"{k_tp:g}R (geometria validada no histórico)"
    tp2_dist, tp2_basis = None, ""
    if b.status == "falso":
        if b.level.height:
            dist = td * ((L + td * b.level.height) - entry)
            if tp1_dist + 0.5 * sl_dist <= dist <= 5 * sl_dist:
                tp2_dist, tp2_basis = dist, "outro lado do range"
    elif b.level.height:
        dist = td * ((L + td * b.level.height) - entry)
        if tp1_dist + 0.5 * sl_dist <= dist <= 5 * sl_dist:
            tp2_dist, tp2_basis = dist, f"projeção da altura do range ({inst.pips(b.level.height):.0f} pips)"
    if tp2_dist is None:
        tp2_dist, tp2_basis = max(2.5 * sl_dist, tp1_dist + 0.8 * sl_dist), "extensão"
    lots, risk_amount, _ = position_size(inst, sl_dist, s.balance, s.risk_pct, prices, s.account_ccy)
    return BreakoutPlan(entry, sl, entry + td * tp1_dist, entry + td * tp2_dist, inst.pips(sl_dist),
                        inst.pips(tp1_dist), inst.pips(tp2_dist), tp1_dist / sl_dist, tp2_dist / sl_dist,
                        lots, risk_amount, sl_basis, tp1_basis, tp2_basis)


# ---------------------------------------------------------------------------- tracker

class Tracker:
    """Remembers events between scans so only genuinely new ones are flagged."""

    def __init__(self, path: str | None, ttl_hours: float = 8.0):
        self.path, self.ttl = path, timedelta(hours=ttl_hours)
        self.items: list[dict] = []
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self.items = json.load(f)
            except (OSError, ValueError):
                self.items = []

    def mark(self, events: list[Breakout], now: datetime) -> int:
        new = 0
        for b in events:
            trap = b.status == "falso"
            m = next((it for it in self.items if it["sym"] == b.symbol and it["tf"] == b.tf
                      and it["dir"] == b.direction and it["trap"] == trap
                      and abs(it["level"] - b.level.price) <= 0.5 * max(b.atr, it["atr"])), None)
            if m is None:
                m = {"sym": b.symbol, "tf": b.tf, "dir": b.direction, "trap": trap,
                     "first": now.isoformat()}
                self.items.append(m)
                b.is_new = True
                new += 1
            p = b.plan
            if (p is not None and p.entry_type == "confirmacao" and b.actionable and "confirm_at" not in m
                    and p.valid_until is not None):
                # real-time confirmation plan: enter at market when the next bar closes in favour
                m.update(confirm_at=p.valid_until.isoformat(), ref=b.ref_close, sl=p.sl, grade=b.grade,
                         side=b.side, trail=p.trail, period_min=int(TF_SPEC[b.tf]["period"].total_seconds() // 60),
                         cstate="pendente", lvl=b.level.price)
            if (p is not None and p.entry_type == "limite" and b.actionable and "limit" not in m
                    and p.valid_until is not None):
                # remember the suggested pending order so a later scan can say when price reaches it
                m.update(limit=p.entry, valid_until=p.valid_until.isoformat(), sl=p.sl, grade=b.grade,
                         side=b.side, filled=False)
            m.update(level=b.level.price, atr=b.atr, last=now.isoformat())
            b.first_seen = datetime.fromisoformat(m["first"])
            if m.get("cstate"):
                b.confirm_state = m["cstate"]
                if m.get("confirmed_at"):
                    b.confirmed_at = datetime.fromisoformat(m["confirmed_at"])
        cutoff = now - self.ttl
        self.items = [it for it in self.items if datetime.fromisoformat(it["last"]) >= cutoff
                      or (it.get("limit") is not None and not it.get("filled")
                          and datetime.fromisoformat(it["valid_until"]) >= now)
                      or it.get("cstate") == "pendente"]
        self.save()
        return new

    def save(self) -> None:
        if self.path:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.items, f)
            os.replace(tmp, self.path)

    def check_confirmations(self, data: dict, now: datetime, s: Settings, prices: dict) -> list[dict]:
        """Pending confirmation plans whose bar has closed: confirmed (enter now) or not."""
        out = []
        for it in self.items:
            if it.get("cstate") != "pendente":
                continue
            at = pd.Timestamp(it["confirm_at"])
            if pd.Timestamp(now) < at:
                continue
            d = data.get(it["sym"])
            if d is None:
                continue
            if pd.Timestamp(now) - at > pd.Timedelta(minutes=30):
                it["cstate"] = "nao_confirmou"            # too late to act on it
                continue
            df = d.frames.get(it["tf"])
            start = at - pd.Timedelta(minutes=it["period_min"])
            if df is None or start not in df.index:
                continue
            close = float(df.loc[start, "c"])
            td = it["dir"]
            if td * (close - it["ref"]) <= 0:
                it["cstate"] = "nao_confirmou"
                continue
            inst = d.inst
            entry = d.ask if td == 1 else d.bid
            atr_h1 = float(ta.atr(d.frames["H1"]).iloc[-1]) if "H1" in d.frames else abs(entry - it["sl"])
            sl_d = max(td * (entry - it["sl"]), 0.3 * atr_h1, 4 * (d.ask - d.bid))
            sl = entry - td * sl_d
            lots, risk, _ = position_size(inst, sl_d, s.balance, s.risk_pct, prices, s.account_ccy)
            it.update(cstate="confirmado", confirmed_at=pd.Timestamp(now).isoformat())
            out.append({"symbol": it["sym"], "tf": it["tf"], "side": it["side"], "grade": it["grade"],
                        "entry": inst.fmt(entry), "sl": inst.fmt(sl), "sl_pips": round(inst.pips(sl_d), 1),
                        "tp1": inst.fmt(entry + td * sl_d),
                        "trail_pips": round(inst.pips(it["trail"]), 0) if it.get("trail") else None,
                        "lots": lots, "risk": round(risk, 2), "level": inst.fmt(it["lvl"]),
                        "close": inst.fmt(close), "time": pd.Timestamp(now).isoformat()})
        if out or any(it.get("cstate") == "nao_confirmou" for it in self.items):
            self.save()
        return out

    def check_fills(self, data: dict, now: datetime) -> list[dict]:
        """Pending limit entries reached since they were suggested (bid/ask aware, M15 lows/highs)."""
        fills = []
        for it in self.items:
            if it.get("limit") is None or it.get("filled"):
                continue
            first = pd.Timestamp(it["first"])
            if now > datetime.fromisoformat(it["valid_until"]):
                continue
            d = data.get(it["sym"])
            if d is None:
                continue
            half = (d.ask - d.bid) / 2
            m15 = d.frames.get("M15")
            bars = m15[m15.index + pd.Timedelta(minutes=15) > first] if m15 is not None else None
            lo = min([d.ask] + ([float(bars.l.min()) + half] if bars is not None and len(bars) else []))
            hi = max([d.bid] + ([float(bars.h.max()) - half] if bars is not None and len(bars) else []))
            reached = lo <= it["limit"] if it["dir"] == 1 else hi >= it["limit"]
            if reached:
                it["filled"] = True
                fills.append({"symbol": it["sym"], "tf": it["tf"], "direction": it["dir"], "side": it["side"],
                              "limit": it["limit"], "sl": it["sl"], "grade": it["grade"], "time": now.isoformat()})
        if fills:
            self.save()
        return fills


# ---------------------------------------------------------------------------- scan

@dataclass
class BreakoutScan:
    now: datetime
    session: sessions.SessionState
    breakouts: list[Breakout]
    scanned: int
    closed: list[str]
    new_count: int
    status: dict[str, str]
    errors: dict[str, str]
    fills: list = field(default_factory=list)      # suggested limit entries reached since last scan
    confirmations: list = field(default_factory=list)  # confirmation plans confirmed: enter at market now
    profile: str = "mercado"


def scan(provider, s: Settings, spec: str | None, now: datetime, state_path: str | None = None,
         progress=None, model=None) -> BreakoutScan:
    def step(p, msg):
        if progress:
            progress(min(max(p, 0.0), 100.0), msg)

    targets = select(spec)
    need = {i.symbol: i for i in targets}
    if any(not i.is_metal for i in targets):
        for i in FX_PAIRS:                 # full matrix for the strength filter
            need.setdefault(i.symbol, i)
    step(2, "Buscando preços ao vivo")
    data, errors = provider.load_instruments(
        list(need.values()), now, spec=LIGHT,
        progress=lambda k, n: step(3 + 67 * k / n, f"Preços ao vivo {k}/{n}"))
    ctx = provider.load_events(now)
    fx = {k: v.frames["H1"] for k, v in data.items() if not v.inst.is_metal}
    strength = strength_mod.compute(fx) if len(fx) >= 20 else None
    sess = sessions.state(now)
    prices = {k: v.price for k, v in data.items()}

    found: list[Breakout] = []
    closed: list[str] = []
    for k, inst in enumerate(targets):
        d = data.get(inst.symbol)
        if d is None:
            continue
        if not d.tradeable:
            closed.append(inst.symbol)
            continue
        step(72 + 26 * k / max(len(targets), 1), f"Procurando rompimentos em {inst.symbol}")
        try:
            found += detect(d, now, s, prices, strength, ctx.events, sess, model=model)
        except Exception as e:  # noqa: BLE001 - one instrument must not break the monitor
            errors[inst.symbol] = f"erro na detecção: {e}"
    found.sort(key=lambda b: (b.actionable, b.ev_r if b.ev_r is not None else b.quality / 100 - 0.5,
                              -b.bars_since), reverse=True)
    tracker = Tracker(state_path)
    fills = tracker.check_fills(data, now)
    confirmations = tracker.check_confirmations(data, now, s, prices)
    new = tracker.mark(found, now)
    step(100, "Concluído")
    return BreakoutScan(now, sess, found, len(targets), closed, new, ctx.status, errors, fills, confirmations,
                        s.breakout_plan)

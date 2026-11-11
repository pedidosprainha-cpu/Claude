"""Live scan for price explosions (fxengine/analysis/explosion.py + fxengine/data/explosion_model.json).

For every instrument: calibrated probability that the price moves >= theta x ADR within the
next hours, alert level, typical size of the move, direction (only if the direction model
passed validation), the drivers behind the reading, high-impact events in the window and a
bracket (OCO) plan: buy stop above and sell stop below, so the trade does not depend on
guessing the side.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np

from .analysis import explosion as ex
from .analysis.signal_model import closed_bars
from .config import Settings
from .data.provider import LIGHT
from .instruments import Instrument, select
from .risk import position_size

SPEC = {"M15": LIGHT["M15"], "H1": ("1h", "1y", 300, "1h")}


@dataclass
class ExplosionAlert:
    inst: Instrument
    p: float                    # calibrated probability of a move >= theta x ADR within the horizon
    level: str                  # extrema | alta | elevada | baixa
    alert: bool                 # inside the alert filter used in the validation
    p_up: float | None          # probability the move starts upwards (None: no direction model)
    adr: float                  # average daily range (price units)
    move_median: float          # typical size of the move after an alert (price units)
    bid: float
    ask: float
    quote_ts: datetime
    tradeable: bool
    until: datetime             # end of the forecast window
    drivers: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    plan: dict = field(default_factory=dict)
    feats: dict = field(default_factory=dict)
    dir_confident: bool = False # direction among the most confident readings of the validation
    dir_useful: bool = False    # the direction model passed its validation rule

    @property
    def symbol(self) -> str:
        return self.inst.symbol


def drivers(f: dict, horizon: int) -> list[str]:
    """Plain-language reading of the strongest inputs (what the trees look at)."""
    out = []
    if f.get("bbw_pct", 0.5) <= 0.15:
        out.append(f"Bollinger no percentil {f['bbw_pct'] * 100:.0f} das últimas 500 horas: volatilidade comprimida")
    if f.get("squeeze", 0) > 0:
        out.append(f"squeeze (Bollinger dentro de Keltner) há {f.get('sq_len', 0) * 48:.0f} h: energia acumulada")
    if f.get("rng24", 1) <= 0.6:
        out.append(f"as últimas 24 h andaram só {f['rng24']:.2f}× a amplitude diária média")
    sr = f.get("seas_ratio", 0.0)
    if sr >= 0.4:
        out.append(f"as próximas {horizon} h costumam ter {np.exp(sr):.1f}× a atividade das últimas 24 h "
                   "(abertura de sessão / horário típico)")
    if f.get("ewm_ratio", 0) >= 0.25:
        out.append(f"volatilidade de curto prazo acelerando ({np.exp(f['ewm_ratio']):.1f}× a de longo prazo)")
    if f.get("nr_cnt", 0) >= 0.5:
        out.append("várias barras de range estreito seguidas (NR7)")
    if f.get("dist_pd", 9) <= 0.1:
        out.append("preço colado na máxima/mínima do dia anterior (gatilho de rompimento)")
    if f.get("pe24", 1) <= 0.85:
        out.append(f"entropia de permutação baixa ({f['pe24']:.2f}): movimento organizado, menos ruído")
    if f.get("jump24", 0) >= 0.35:
        out.append("saltos recentes no preço (variação bipower): mercado nervoso")
    if f.get("adr_used", 1) <= 0.35:
        out.append(f"o dia usou só {f['adr_used'] * 100:.0f}% da amplitude média")
    return out[:5]


def bracket_plan(inst: Instrument, m: ex.ExplosionModel, bid: float, ask: float, adr: float,
                 s: Settings, prices: dict, until: datetime) -> dict:
    b = m.bracket or {}
    e = float(b.get("offset_adr", 0.1))
    mid = (bid + ask) / 2
    half = (ask - bid) / 2
    buy = mid + e * adr + half
    sell = mid - e * adr - half
    risk = (buy - sell) if b.get("stop") == "opp" else e * adr
    risk = max(risk, 8 * half)
    lots, risk_amount, _ = position_size(inst, risk, s.balance, s.risk_pct, prices, s.account_ccy)
    trail = b.get("exit") == "tr"
    return {
        "buy_stop": buy, "sell_stop": sell,
        "buy_sl": buy - risk, "sell_sl": sell + risk,
        "buy_tp": None if trail else buy + 2 * risk, "sell_tp": None if trail else sell - 2 * risk,
        "risk": risk, "lots": lots, "risk_amount": risk_amount, "trail": trail,
        "exit_rule": ("após +1R, stop móvel 1R atrás do melhor preço" if trail else "alvo em 2R"),
        "valid_until": until, "hold_h": 12, "validated": bool(b.get("validated", False)),
        "wf_mean_r": b.get("wf_mean_r"), "stop_rule": ("o outro lado da OCO" if b.get("stop") == "opp"
                                                       else "volta ao preço atual"),
    }


def _strength_points(data: dict, now) -> tuple:
    """Currency strength on closed H1 bars now, 4 and 24 bars earlier (as in the replay)."""
    from .analysis import strength as strength_mod
    pts = []
    for back in (0, 4, 24):
        fx, met = {}, {}
        for sym, d in data.items():
            h1 = d.frames.get("H1")
            if h1 is None or h1.empty:
                continue
            h1 = closed_bars(h1, now) if now is not None else h1.iloc[:-1]
            h1 = h1.iloc[:len(h1) - back] if back else h1
            (met if d.inst.is_metal else fx)[d.inst.base if d.inst.is_metal else sym] = h1
        try:
            pts.append(strength_mod.compute(fx, met))
        except Exception:  # noqa: BLE001
            pts.append(None)
    return tuple(pts)


def scan(s: Settings | None = None, spec: str | None = None, provider=None, progress=None,
         model: ex.ExplosionModel | None = None) -> tuple[list[ExplosionAlert], dict, datetime]:
    """Returns (alerts sorted by probability, errors, now)."""
    s = s or Settings()
    m = model or ex.load_model()
    if m is None:
        raise RuntimeError("modelo de explosões não encontrado (rode research/train_explosion_model.py)")
    if provider is None:
        if s.offline:
            from .data.synthetic import SyntheticProvider
            provider = SyntheticProvider(s)
        else:
            from .data.provider import Provider
            provider = Provider(s)
    now = getattr(provider, "now", None) or datetime.now(timezone.utc)
    targets = select(spec)
    data, errors = provider.load_instruments(targets, now, progress=progress, spec=SPEC)
    try:
        events = provider.load_events(now).events or []
    except Exception:  # noqa: BLE001
        events = []
    prices = {sym: d.price for sym, d in data.items()}
    st_now, st_4, st_24 = _strength_points(data, now if not s.offline else None)
    out = []
    for inst in targets:
        d = data.get(inst.symbol)
        if d is None:
            continue
        try:
            h1 = closed_bars(d.frames["H1"], now if not s.offline else d.quote_ts)
            sc = lambda st: st.pair_score(inst.base, inst.quote) if st is not None else 0.0  # noqa: E731
            ff = ex.feature_frame(h1.iloc[-3000:], inst.is_metal, m.horizon, sc(st_now),
                                  {"4": sc(st_4), "24": sc(st_24)})
        except Exception as e:  # noqa: BLE001
            errors[inst.symbol] = f"features: {e}"
            continue
        row = ff.iloc[-1]
        cols = dict.fromkeys(ex.FEATURES + ex.DIR_SIGNED + ex.DIR_CONTEXT)
        feats = {k: float(row[k]) for k in cols if np.isfinite(row[k])}
        adr = float(row["adr"]) if np.isfinite(row["adr"]) else float("nan")
        if not np.isfinite(adr) or adr <= 0:
            continue
        p = m.prob(feats)
        last_close = h1.index[-1] + timedelta(hours=1)
        until = (last_close + timedelta(hours=m.horizon)).to_pydatetime()
        ccys = {inst.base, inst.quote} if not inst.is_metal else {"USD"}
        evs = []
        for e in events:
            if e.impact == "High" and e.ccy in ccys | {"ALL"} and now - timedelta(minutes=30) <= e.time <= until:
                mins = (e.time - now).total_seconds() / 60
                evs.append(f"{e.ccy} {e.title} " + (f"em {mins:.0f} min" if mins >= 0 else f"há {-mins:.0f} min"))
        move = float(m.move_q.get("alert_median", m.theta)) * adr if p >= m.alert_p else \
            float(m.move_q.get("all_median", m.theta / 2)) * adr
        pu = m.p_up(feats) if m.direction else None
        out.append(ExplosionAlert(
            inst, p, m.level(p), p >= m.alert_p, pu, adr, move,
            d.bid, d.ask, d.quote_ts, d.tradeable, until, drivers(feats, m.horizon), evs,
            bracket_plan(inst, m, d.bid, d.ask, adr, s, prices, until), feats,
            dir_confident=pu is not None and m.direction_confident(pu), dir_useful=m.direction_useful))
    out.sort(key=lambda a: -a.p)
    return out, errors, now

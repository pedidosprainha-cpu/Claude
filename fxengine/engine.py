"""Orchestrator: load live data, run every analysis layer per instrument, apply
execution gates and rank opportunities for immediate market entry."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from . import sessions
from .analysis import edge as edge_mod
from .analysis import quant as quant_mod
from .analysis import strength as strength_mod
from .analysis import technical as tech_mod
from .analysis.fundamental import FundamentalModel, FundamentalResult, Macro
from .analysis.quant import QuantResult
from .analysis.structure import LevelMap, level_map
from .analysis.technical import TechnicalResult
from .config import Settings
from .data.provider import InstrumentData, MarketContext
from .instruments import FX_PAIRS, Instrument, select
from .risk import TradePlan, build_plan

GRADES = ((65, "A+"), (55, "A"), (45, "B"), (35, "C"), (0, "D"))


def grade(score: float) -> str:
    return next(g for t, g in GRADES if score >= t)


@dataclass
class Opportunity:
    inst: Instrument
    direction: int
    price: float
    bid: float
    ask: float
    quote_ts: datetime
    quote_source: str
    tech: TechnicalResult
    quant: QuantResult
    fund: FundamentalResult
    strength: float
    components: dict[str, float]
    composite: float
    multipliers: dict[str, tuple[float, str]]
    score: float
    grade: str
    plan: TradePlan
    edge: edge_mod.EdgeResult | None
    levels: LevelMap
    gates: list[str]
    reasons: list[str]
    warnings: list[str]
    data_notes: list[str]
    executable: bool = False      # passed every gate and the minimum score

    @property
    def symbol(self) -> str:
        return self.inst.symbol

    @property
    def side(self) -> str:
        return "COMPRA" if self.direction == 1 else "VENDA"

    @property
    def spread_pips(self) -> float:
        return self.inst.pips(self.ask - self.bid)


@dataclass
class ScanResult:
    now: datetime
    session: sessions.SessionState
    opportunities: list[Opportunity]
    best: Opportunity | None
    strength: strength_mod.StrengthResult
    macro: Macro
    ctx: MarketContext
    errors: dict[str, str]
    settings: Settings
    correlations: dict[str, float] = field(default_factory=dict)

    @property
    def top(self) -> Opportunity | None:
        return self.opportunities[0] if self.opportunities else None


def _agree(v: float, d: int, thr: float = 10.0) -> int:
    return 1 if v * d >= thr else (-1 if v * d <= -thr else 0)


def analyze_instrument(data: InstrumentData, strength: strength_mod.StrengthResult, fmodel: FundamentalModel,
                       sess: sessions.SessionState, s: Settings, prices: dict[str, float]) -> Opportunity | None:
    inst, f, px = data.inst, data.frames, data.price
    tech = tech_mod.analyze(f, px, s.tf_weights)
    if "H1" not in tech.views or "M15" not in tech.views:
        return None
    quant = quant_mod.analyze(f)
    st_score = strength.pair_score(inst.base, inst.quote)
    fund = fmodel.pair(inst, s.event_block_before_min, s.event_block_after_min)

    comps = {"technical": tech.score, "quant": quant.score, "strength": st_score, "fundamental": fund.score}
    composite = sum(s.weights[k] * comps[k] for k in comps)
    d = int(np.sign(composite)) or (int(np.sign(tech.score)) or 1)

    timing_mult, timing_notes, t_reasons, t_warns = (tech.timing_mult, tech.timing_notes, [], [])
    if d != (int(np.sign(tech.score)) or 1):
        timing_mult, timing_notes, t_reasons, t_warns = tech_mod.entry_timing(tech.views, px, d)

    v15, v1 = tech.views["M15"], tech.views["H1"]
    atr_d1 = tech.views["D1"].atr if "D1" in tech.views else 4 * v1.atr
    levels = level_map(f, px, inst.round_step, v1.atr)
    plan = build_plan(inst, d, data.bid, data.ask, f, v15.atr, v1.atr, atr_d1, levels,
                      s.balance, s.risk_pct, prices, s.account_ccy)

    ed = None
    if s.use_edge:
        ed = edge_mod.evaluate(f["H1"], d, plan.sl_atr_h1, plan.tp1_atr_h1, data.ask - data.bid,
                               s.edge_max_hold_bars, s.edge_prior_strength)

    # ------------------------------------------------------------------ multipliers
    mult: dict[str, tuple[float, str]] = {}
    mult["timing"] = (timing_mult, "; ".join(timing_notes) or "neutro")

    trend_follow = np.sign(quant.tsmom) == d
    mr_setup = any(st.direction == d and "reversão" in st.name for st in tech.setups)
    if quant.regime == "tendência":
        mult["regime"] = (1.05, "tendência persistente a favor") if trend_follow else (0.82, "contra tendência persistente")
    elif quant.regime == "reversão à média":
        mult["regime"] = (1.02, "fade alinhado ao regime") if mr_setup else (0.88, "regime de reversão: continuação menos confiável")
    else:
        mult["regime"] = (0.96, "regime aleatório")

    votes = [_agree(comps[k], d) for k in comps]
    pos, neg = votes.count(1), votes.count(-1)
    conf = {4: 1.10, 3: 1.0, 2: 0.86}.get(pos, 0.7) * (0.85 if neg >= 2 else 1.0)
    mult["confluência"] = (conf, f"{pos}/4 camadas a favor, {neg} contra")

    if plan.room_r < 0.8:
        mult["espaço"] = (0.65, f"zona oposta a {plan.room_r:.1f}R")
    elif plan.room_r < 1.2:
        mult["espaço"] = (0.85, f"zona oposta a {plan.room_r:.1f}R")
    elif plan.room_r >= 2.0:
        mult["espaço"] = (1.05, f"espaço livre ≥ {plan.room_r:.1f}R")
    else:
        mult["espaço"] = (1.0, f"zona oposta a {plan.room_r:.1f}R")

    if ed is not None and ed.reliable:
        mult["edge"] = (float(np.clip(1 + 0.6 * ed.exp_post_r, 0.75, 1.15)),
                        f"histórico n={ed.n}, acerto {ed.p_post * 100:.0f}%, E={ed.exp_post_r:+.2f}R")
    elif ed is not None:
        mult["edge"] = (0.97, f"amostra histórica pequena (n={ed.n})")

    if plan.spread_ratio > 0.15:
        mult["spread"] = (0.85, f"spread = {plan.spread_ratio * 100:.0f}% do stop")
    elif plan.spread_ratio > 0.10:
        mult["spread"] = (0.93, f"spread = {plan.spread_ratio * 100:.0f}% do stop")

    liq, liq_note = sessions.liquidity_factor(sess, inst.base, inst.quote, inst.is_metal)
    mult["liquidez"] = (max(liq, 0.5) if liq > 0 else 1.0, liq_note)
    if fund.event_mult < 1:
        mult["agenda"] = (fund.event_mult, "evento relevante próximo")
    if quant.vol_pct > 95:
        mult["volatilidade"] = (0.9, f"vol. realizada no percentil {quant.vol_pct:.0f}")

    score = abs(composite)
    for v, _ in mult.values():
        score *= v
    score = float(np.clip(score, 0, 100))

    # ------------------------------------------------------------------ hard gates
    gates: list[str] = []
    if not data.tradeable:
        gates.append("mercado fechado / cotação não ao vivo")
    if liq == 0:
        gates.append("fora do horário de negociação")
    if fund.event_block:
        gates.append("evento de alto impacto na janela de bloqueio")
    if plan.spread_ratio > s.max_spread_to_sl:
        gates.append(f"spread {plan.spread_ratio * 100:.0f}% do stop (> {s.max_spread_to_sl * 100:.0f}%)")
    if tech.score * d < -25:
        gates.append("gráfico (técnico MTF) contra a direção")
    if plan.rr1 < s.min_rr_tp1:
        gates.append(f"R:R TP1 {plan.rr1:.2f} < {s.min_rr_tp1}")
    if ed is not None and ed.reliable and ed.exp_post_r < -0.15:
        gates.append(f"edge histórico negativo ({ed.exp_post_r:+.2f}R)")

    # ------------------------------------------------------------------ narrative
    f_reasons, f_warns = fund.narrative(inst.symbol, d)
    reasons = list(tech.reasons) + t_reasons
    warnings = list(tech.warnings) + t_warns + fund.warnings + f_warns + plan.notes + quant.notes[1:]
    order = [c for c, _ in strength.ranking]
    if not inst.is_metal and inst.base in order and inst.quote in order:
        sb, sq = strength.scores[inst.base], strength.scores[inst.quote]
        txt = (f"força relativa: {inst.base} {sb:+.2f} ({order.index(inst.base) + 1}º) vs "
               f"{inst.quote} {sq:+.2f} ({order.index(inst.quote) + 1}º de 8)")
        (reasons if np.sign(sb - sq) == d else warnings).append(txt)
    elif inst.is_metal:
        mz = strength.metal_z.get(inst.base, 0.0)
        (reasons if np.sign(mz) == d else warnings).append(f"momentum normalizado {inst.base} vs USD {mz:+.2f}σ")
    reasons += quant.notes[:1]
    reasons += f_reasons[:4]
    if ed is not None and ed.reliable and ed.exp_post_r > 0:
        reasons.append(f"edge histórico do setup: {ed.n} sinais semelhantes em 1 ano, TP1 antes do SL em "
                       f"{ed.win_rate * 100:.0f}% (posterior {ed.p_post * 100:.0f}%), expectativa {ed.exp_post_r:+.2f}R")
    for k, val in comps.items():
        if _agree(val, d) == -1:
            label = {"technical": "técnico", "quant": "quant", "strength": "força relativa",
                     "fundamental": "fundamental"}[k]
            warnings.append(f"camada {label} contra a direção ({val:+.0f})")

    opp = Opportunity(inst, d, px, data.bid, data.ask, data.quote_ts, data.quote_source, tech, quant, fund,
                      st_score, comps, float(composite), mult, score, grade(score), plan, ed, levels,
                      gates, reasons, warnings, data.notes)
    opp.executable = not gates and score >= s.min_score
    return opp


def _correlations(best: Opportunity, opps: list[Opportunity], data: dict[str, InstrumentData]) -> dict[str, float]:
    out = {}
    b = data[best.symbol].frames["H1"].c
    rb = np.log(b).diff().iloc[-500:]
    for o in opps:
        if o.symbol == best.symbol:
            continue
        r = np.log(data[o.symbol].frames["H1"].c).diff()
        j = rb.to_frame("a").join(r.rename("b"), how="inner").dropna()
        if len(j) > 50:
            # sign-adjust so that a positive number means "same trade exposure"
            out[o.symbol] = float(j.a.corr(j.b)) * best.direction * o.direction
    return out


class Engine:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or Settings()
        if self.s.offline:
            from .data.synthetic import SyntheticProvider
            self.provider = SyntheticProvider(self.s)
        else:
            from .data.provider import Provider
            self.provider = Provider(self.s)

    def now(self) -> datetime:
        return getattr(self.provider, "now", None) or datetime.now(timezone.utc)

    def scan(self, spec: str | None = None) -> ScanResult:
        now = self.now()
        targets = select(spec)
        need = {i.symbol: i for i in targets}
        for i in FX_PAIRS:                      # strength meter always needs the full FX matrix
            need.setdefault(i.symbol, i)
        data, errors = self.provider.load_instruments(list(need.values()), now)
        ctx = self.provider.load_context(now)

        fx_h1 = {s: d.frames["H1"] for s, d in data.items() if not d.inst.is_metal}
        met_h1 = {d.inst.base: d.frames["H1"] for s, d in data.items() if d.inst.is_metal}
        strength = strength_mod.compute(fx_h1, met_h1)
        fmodel = FundamentalModel(ctx)
        sess = sessions.state(now)
        prices = {s: d.price for s, d in data.items()}

        opps = []
        for inst in targets:
            if inst.symbol not in data:
                continue
            try:
                o = analyze_instrument(data[inst.symbol], strength, fmodel, sess, self.s, prices)
            except Exception as e:  # noqa: BLE001 - isolate per-instrument failures
                errors[inst.symbol] = f"erro na análise: {e}"
                continue
            if o is not None:
                opps.append(o)
        opps.sort(key=lambda o: o.score, reverse=True)
        best = next((o for o in opps if o.executable), None)
        corr = _correlations(best or opps[0], opps, data) if opps else {}
        return ScanResult(now, sess, opps, best, strength, fmodel.macro, ctx, errors, self.s, corr)

"""Orchestrator: load live data, run every analysis layer per instrument, apply
execution gates and rank opportunities for immediate market entry."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from . import sessions
from . import breakouts as bk_mod
from .analysis import edge as edge_mod
from .analysis import signal_model as sig_mod
from .analysis import quant as quant_mod
from .analysis import strength as strength_mod
from .analysis import technical as tech_mod
from .analysis.fundamental import FundamentalModel, FundamentalResult, Macro
from .analysis.quant import QuantResult
from .analysis.structure import LevelMap, level_map
from .analysis.technical import TechnicalResult
from .config import Settings, grade
from .data.provider import InstrumentData, MarketContext
from .data.provider import LIGHT
from .instruments import FX_PAIRS, Instrument, select
from .instruments import get as get_instrument
from .instruments import typical_spread_pips
from .risk import TradePlan, build_plan



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
    day: dict = field(default_factory=dict)          # daily-range context (ADR used, move today, ...)
    breakouts: list = field(default_factory=list)    # breakouts detected on this instrument now
    signal: sig_mod.SignalEval | None = None         # calibrated historical model reading (if loaded)

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
                       sess: sessions.SessionState, s: Settings, prices: dict[str, float],
                       now: datetime | None = None, events: list | None = None,
                       bk_model=None, sig_model: sig_mod.SignalModel | None = None,
                       strength_closed: strength_mod.StrengthResult | None = None) -> Opportunity | None:
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
    now = now or data.quote_ts
    model = sig_model if s.use_edge else None
    plan = build_plan(inst, d, data.bid, data.ask, f, v15.atr, v1.atr, atr_d1, levels,
                      s.balance, s.risk_pct, prices, s.account_ccy,
                      geometry=model.geometry if model is not None else None)

    ed, sig = None, None
    if model is not None:
        try:
            st_model = (strength_closed or strength).pair_score(inst.base, inst.quote)   # as in the replay
            sig = sig_mod.evaluate(model, sig_mod.closed_bars(f["H1"], now), st_model,
                                   typical_spread_pips(inst.symbol) * inst.pip, inst.is_metal, d)
        except Exception:  # noqa: BLE001 - the model is an extra layer; never break the scan
            sig = None
    elif s.use_edge:
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

    if sig is not None:
        _, ev_cut = model.calibrated(model.ev_exec, 0.0)
        mult["histórico"] = (float(np.clip(1 + 1.5 * (sig.ev_r - ev_cut), 0.75, 1.15)),
                             f"modelo histórico: lucro em {sig.p * 100:.0f}% dos casos parecidos, "
                             f"expectativa {sig.ev_r:+.2f}R")
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

    # daily-range context: how much of the average daily range is already used, and in which direction
    day = bk_mod.context_features(f.get("H1"), px, d, now)
    extra_r, extra_w = [], []
    if day["move_today"] > 1.0:
        mult["dia"] = (0.85, f"o dia já andou {day['move_today']:.1f}× a amplitude média a favor")
        extra_w.append(f"o preço já andou {day['move_today']:.1f}× a amplitude diária média a favor hoje: "
                       "risco de exaustão")
    elif day["adr_used"] > 1.3:
        mult["dia"] = (0.92, f"amplitude do dia em {day['adr_used'] * 100:.0f}% da média")
        extra_w.append(f"o dia já usou {day['adr_used'] * 100:.0f}% da amplitude diária média")
    elif day["adr_used"] < 0.5:
        extra_r.append(f"dia ainda com amplitude disponível ({day['adr_used'] * 100:.0f}% da média usada)")

    # confluence with the validated breakout model on the same instrument
    bks = []
    if bk_model is not None:
        try:
            bks = bk_mod.detect(bk_mod.light_view(data), now, s, prices, strength, events or [], sess,
                                model=bk_model)
        except Exception:  # noqa: BLE001 - confluence is optional
            bks = []
        same = [b for b in bks if b.actionable and b.direction == d]
        against = [b for b in bks if b.actionable and b.direction == -d]
        if same:
            b0 = same[0]
            mult["rompimento"] = (1.06, f"rompimento {b0.tf} nota {b0.grade} a favor")
            extra_r.append(f"confluência: rompimento {b0.tf} {bk_mod.STATUS_LABEL[b0.status].lower()} nota "
                           f"{b0.grade} na mesma direção ({b0.level.label})")
        elif against:
            b0 = against[0]
            mult["rompimento"] = (0.9, f"rompimento {b0.tf} nota {b0.grade} contra")
            extra_w.append(f"rompimento {b0.tf} nota {b0.grade} na direção oposta ({b0.level.label})")

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
    if sig is not None and not sig.passes:
        q = float(model.info.get("filter_q", 0.1))
        gates.append(f"histórico desfavorável: expectativa {sig.ev_r:+.2f}R, fora dos "
                     f"{q * 100:.0f}% melhores sinais")

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
    reasons += extra_r
    warnings += extra_w
    if sig is not None:
        if sig.passes:
            reasons.append(f"modelo histórico (2+ anos, 32 ativos): sinal entre os melhores — lucro em "
                           f"{sig.p * 100:.0f}% dos casos parecidos, expectativa {sig.ev_r:+.2f}R")
        if sig.other_ev_r > sig.ev_r + 0.05:
            warnings.append(f"o histórico favorece o lado oposto agora (expectativa {sig.other_ev_r:+.2f}R "
                            f"contra {sig.ev_r:+.2f}R)")
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
    opp.day, opp.breakouts, opp.signal = day, bks, sig
    return opp


def _closed_strength(fx_h1: dict, met_h1: dict, now) -> strength_mod.StrengthResult:
    """Strength meter on closed H1 bars only: the input the signal model saw in the replay."""
    return strength_mod.compute({k: sig_mod.closed_bars(v, now) for k, v in fx_h1.items()},
                                {k: sig_mod.closed_bars(v, now) for k, v in met_h1.items()})


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

    def scan(self, spec: str | None = None, progress=None) -> ScanResult:
        """progress(pct: float, message: str) is optional (used by the Android app)."""
        def step(pct: float, msg: str) -> None:
            if progress:
                progress(min(max(pct, 0.0), 100.0), msg)

        now = self.now()
        targets = select(spec)
        need = {i.symbol: i for i in targets}
        for i in FX_PAIRS:                      # strength meter always needs the full FX matrix
            need.setdefault(i.symbol, i)
        step(2, "Conectando às fontes de dados")
        data, errors = self.provider.load_instruments(
            list(need.values()), now,
            progress=lambda k, n: step(3 + 52 * k / n, f"Preços ao vivo e gráficos {k}/{n}"))
        step(56, "Juros, COT, agenda e manchetes")
        ctx = self.provider.load_context(now)
        step(64, "Força relativa das moedas")

        fx_h1 = {s: d.frames["H1"] for s, d in data.items() if not d.inst.is_metal}
        met_h1 = {d.inst.base: d.frames["H1"] for s, d in data.items() if d.inst.is_metal}
        strength = strength_mod.compute(fx_h1, met_h1)
        st_closed = _closed_strength(fx_h1, met_h1, now) if self.s.use_edge else None
        fmodel = FundamentalModel(ctx)
        sess = sessions.state(now)
        prices = {s: d.price for s, d in data.items()}
        bk_model = bk_mod.load_model(bk_mod.MODEL_PATHS.get(self.s.breakout_plan, bk_mod.MODEL_PATH))
        sig_model = sig_mod.load_model() if self.s.use_edge else None

        opps = []
        for k, inst in enumerate(targets):
            if inst.symbol not in data:
                continue
            step(66 + 32 * k / max(len(targets), 1), f"Analisando {inst.symbol}")
            try:
                o = analyze_instrument(data[inst.symbol], strength, fmodel, sess, self.s, prices,
                                       now=now, events=ctx.events, bk_model=bk_model, sig_model=sig_model,
                                       strength_closed=st_closed)
            except Exception as e:  # noqa: BLE001 - isolate per-instrument failures
                errors[inst.symbol] = f"erro na análise: {e}"
                continue
            if o is not None:
                opps.append(o)
        opps.sort(key=lambda o: o.score, reverse=True)
        best = next((o for o in opps if o.executable), None)
        corr = _correlations(best or opps[0], opps, data) if opps else {}
        step(100, "Concluído")
        return ScanResult(now, sess, opps, best, strength, fmodel.macro, ctx, errors, self.s, corr)

    # ------------------------------------------------------------------ single instrument
    def scan_asset(self, symbol: str, progress=None) -> "AssetResult":
        """Deep analysis of one instrument. The other FX pairs are loaded with the light
        profile (only what the currency-strength meter needs), so it is much faster than a scan."""
        def step(pct: float, msg: str) -> None:
            if progress:
                progress(min(max(pct, 0.0), 100.0), msg)

        inst = get_instrument(symbol)
        now = self.now()
        step(3, f"Preços ao vivo e gráficos de {inst.symbol}")
        data, errors = self.provider.load_instruments([inst], now)
        if inst.symbol not in data:
            raise RuntimeError(f"sem dados para {inst.symbol}: {errors.get(inst.symbol, 'falha de rede')}")
        others = [i for i in FX_PAIRS if i.symbol != inst.symbol]
        rest, err2 = self.provider.load_instruments(
            others, now, spec=LIGHT,
            progress=lambda k, n: step(15 + 50 * k / n, f"Força relativa: pares {k}/{n}"))
        errors.update(err2)
        rest.update(data)
        step(68, "Juros, COT, agenda e manchetes")
        ctx = self.provider.load_context(now)
        step(80, f"Analisando {inst.symbol}")
        fx_h1 = {k: v.frames["H1"] for k, v in rest.items() if not v.inst.is_metal}
        met_h1 = {inst.base: data[inst.symbol].frames["H1"]} if inst.is_metal else {}
        strength = strength_mod.compute(fx_h1, met_h1)
        st_closed = _closed_strength(fx_h1, met_h1, now) if self.s.use_edge else None
        fmodel = FundamentalModel(ctx)
        sess = sessions.state(now)
        prices = {k: v.price for k, v in rest.items()}
        bk_model = bk_mod.load_model(bk_mod.MODEL_PATHS.get(self.s.breakout_plan, bk_mod.MODEL_PATH))
        sig_model = sig_mod.load_model() if self.s.use_edge else None
        opp = analyze_instrument(data[inst.symbol], strength, fmodel, sess, self.s, prices,
                                 now=now, events=ctx.events, bk_model=bk_model, sig_model=sig_model,
                                 strength_closed=st_closed)
        step(100, "Concluído")
        return AssetResult(now, sess, inst, data[inst.symbol], opp, strength, fmodel, ctx, errors, self.s)


@dataclass
class AssetResult:
    now: datetime
    session: sessions.SessionState
    inst: Instrument
    data: InstrumentData
    opportunity: Opportunity | None
    strength: strength_mod.StrengthResult
    fmodel: FundamentalModel
    ctx: MarketContext
    errors: dict[str, str]
    settings: Settings

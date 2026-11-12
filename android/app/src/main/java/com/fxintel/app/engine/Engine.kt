package com.fxintel.app.engine

import com.fxintel.app.data.Analysis
import com.fxintel.app.data.Candidate
import com.fxintel.app.data.Confidence
import com.fxintel.app.data.EconEvent
import com.fxintel.app.data.Fundamentals
import com.fxintel.app.data.Gate
import com.fxintel.app.data.Justification
import com.fxintel.app.data.Level
import com.fxintel.app.data.MarketRow
import com.fxintel.app.data.ModelStatus
import com.fxintel.app.data.NextEvent
import com.fxintel.app.data.OosMetrics
import com.fxintel.app.data.Probability
import com.fxintel.app.data.RefQuote
import com.fxintel.app.data.RiskEval
import com.fxintel.app.data.RiskReward
import com.fxintel.app.data.Scenarios
import com.fxintel.app.data.Sizing
import com.fxintel.app.data.TakeProfit
import com.fxintel.app.data.Validity
import java.time.Instant
import java.util.UUID
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

data class EngineSettings(
    val universe: List<String> = Instruments.ALL.keys.toList(),
    val equity: Double = 10_000.0, val account: String = "USD", val leverage: Double = 30.0,
    val riskPct: Double = 0.5, val maxDailyLossPct: Double = 2.0, val maxWeeklyLossPct: Double = 4.0,
    val maxOpen: Int = 3, val maxRiskPerCurrencyPct: Double = 1.0,
    val maxQuoteAgeS: Double = 180.0, val maxBarAgeMin: Double = 90.0, val maxSpreadAtr: Double = 0.12,
    val maxCostR: Double = 0.15, val minRrNet: Double = 1.2, val minEv: Double = 0.05, val maxDriftAtr: Double = 0.35,
    val maxVolZ: Double = 5.0, val requireModel: Boolean = true, val blackoutBefore: Int = 60, val blackoutAfter: Int = 30,
    val validityMin: Int = 240, val slipPips: Double = 0.2, val slipAtr: Double = 0.02,
)

/** Exposição atual para o gestor de risco local (sinais acompanhados no aparelho). */
data class OpenExposure(val symbol: String, val dir: Int, val riskAmount: Double)
data class RiskState(val open: List<OpenExposure> = emptyList(), val pnlDay: Double = 0.0, val pnlWeek: Double = 0.0)

/**
 * Motor autônomo do aplicativo: executa "ANALISAR MERCADO AGORA" inteiramente no aparelho,
 * com dados públicos (sem chave de API) e a mesma metodologia do motor Python (verificada por testes golden).
 */
class Engine(private val md: MarketData, private val model: LogisticModel?, private val cb: CentralBanks) {

    private fun iso(t: Long) = Instant.ofEpochSecond(t).toString()
    private fun r(v: Double, nd: Int): Double? = if (v.isNaN() || v.isInfinite()) null else Math.round(v * Math.pow(10.0, nd.toDouble())) / Math.pow(10.0, nd.toDouble())

    private class Inst(val sym: String, val market: MarketRow, val cands: MutableList<Candidate>, val atr: Double, val raw: MutableList<Pair<Double, Candidates.Cand>>)

    fun modelStatus(): ModelStatus {
        val m = model ?: return ModelStatus(available = false, validated = false, message = "Modelo não incluído no aplicativo")
        val age = runCatching { (System.currentTimeMillis() / 1000 - Instant.parse(m.meta.trainedAt.replace("+00:00", "Z")).epochSecond) / 3600.0 }.getOrNull()
        return ModelStatus(true, m.meta.validated, m.meta.trainedAt, age?.let { r(it, 1) },
            OosMetrics(r(m.meta.bss, 4), r(m.meta.auc, 3), m.meta.nOos), OosMetrics(r(m.meta.holdoutBss, 4), r(m.meta.holdoutAuc, 3)),
            m.meta.validationRule)
    }

    fun analyze(st: EngineSettings, rs: RiskState): Analysis {
        val t0 = System.nanoTime()
        val now = System.currentTimeMillis() / 1000
        md.notes.clear()
        val universe = st.universe.filter { Instruments.ALL.containsKey(it) }
        val quotes = md.quotes(universe)
        val data = md.parallel(universe) { s ->
            Triple(md.bars(s, "H1"), runCatching { md.bars(s, "M15") }.getOrNull(), runCatching { md.bars(s, "M5") }.getOrNull())
        }
        val macro = md.parallel(Instruments.MACRO.keys.toList()) { md.macro(it) }.mapNotNull { (k, v) -> v.getOrNull()?.let { k to it } }.toMap()
        val events = runCatching { md.calendar() }
        val h1c = data.mapNotNull { (s, v) -> v.getOrNull()?.let { s to BarOps.completed(it.first, 3600, now) } }.toMap()
        val strength = Macro.strength(h1c.filterKeys { Instruments.get(it).kind == "fx" }.mapValues { it.value.tail(3000) })
        val tData = System.nanoTime()

        val results = md.parallel(universe) { s ->
            analyzeInstrument(s, h1c[s], data[s]?.getOrNull(), quotes[s], macro, strength, events.getOrNull(), st, now)
        }
        val per = universe.associateWith { s ->
            results[s]!!.getOrElse { e -> Inst(s, MarketRow(symbol = s, error = e.message ?: "falha"), mutableListOf(), NAN, mutableListOf()) }
        }
        // gestor de risco nos candidatos que passaram nos demais portões
        val mids = quotes.mapValues { it.value.mid }
        val all = per.values.flatMap { it.cands }.map { c ->
            if (c.gates.all { it.passed }) {
                val d = if (c.direction == "BUY") 1 else -1
                val rv = riskCheck(c.instrument, d, c.entry.price, c.stop_loss.price, mids, st, rs)
                c.copy(risk = rv, gates = c.gates + Gate("gestor_de_risco", rv.approved, rv.reasons.joinToString("; ").ifBlank { "Aprovado pelos limites de risco" }))
            } else c
        }.sortedWith(compareByDescending<Candidate> { it.gates.all { g -> g.passed } }.thenByDescending { it.score })
        val bestOrig = all.firstOrNull { it.gates.all { g -> g.passed } }
        val best = bestOrig?.copy(id = UUID.randomUUID().toString().take(16),
            execution_note = "Este é um SINAL analítico. A execução depende da sua corretora e da confirmação das condições reais de negociação.")
        val real = all.filter { it.has_setup }
        val reasons = if (best != null) emptyList() else if (real.isEmpty())
            listOf("Nenhum setup técnico ativo nos últimos candles H1 fechados do universo monitorado.")
        else real.flatMap { c -> c.gates.filter { !it.passed }.map { it.gate } }.groupingBy { it }.eachCount()
            .entries.sortedByDescending { it.value }.map { "${it.key}: bloqueou ${it.value} candidato(s)" }
        val str5 = strength?.byWindow?.get(120)?.mapValues { it.value.lastOk() }?.filterValues { !it.isNaN() }
            ?.entries?.sortedByDescending { it.value }?.associate { it.key to Math.round(it.value * 1000) / 1000.0 } ?: emptyMap()
        val evs = events.getOrNull() ?: emptyList()
        val elapsed = (System.nanoTime() - t0) / 1e6
        return Analysis(
            id = UUID.randomUUID().toString().take(16), created_at = iso(now),
            status = if (best != null) "SINAL" else "SEM_OPORTUNIDADE",
            headline = best?.let { "${it.direction} ${it.instrument} a mercado — score ${"%.0f".format(it.score)}" }
                ?: "Nenhuma oportunidade suficientemente qualificada no momento",
            signal = best, no_signal_reasons = reasons, observations = all.filter { it !== bestOrig && it.has_setup }.take(5),
            ranking = ranking(all, bestOrig, best, mids, st),
            market = universe.map { per[it]!!.market }, model = modelStatus(),
            fundamentals = Fundamentals(str5, evs.filter { it.time in now..(now + 36 * 3600) && it.impact in setOf("High", "Medium") }.take(15)
                .map { EconEvent(it.title, it.currency, iso(it.time), it.impact) }, events.isSuccess, cb.asOf),
            elapsed_ms = elapsed, trigger = "aparelho (dados ${"%.1f".format((tData - t0) / 1e9)} s)",
            disclaimer = "Análise automatizada para apoio à decisão. Não constitui recomendação de investimento. " +
                "Nenhuma metodologia garante rentabilidade; opere com gestão de risco.",
        )
    }

    private fun analyzeInstrument(sym: String, h1All0: Bars?, raw: Triple<Bars, Bars?, Bars?>?, q: Q?, macro: Map<String, Bars>,
                                  strength: Macro.Strength?, events0: List<EconEventK>?, st: EngineSettings, now: Long): Inst {
        val events = events0 ?: emptyList()
        val inst = Instruments.get(sym)
        if (h1All0 == null || h1All0.n < 600) return Inst(sym, MarketRow(symbol = sym, error = "histórico H1 insuficiente"), mutableListOf(), NAN, mutableListOf())
        val spot = q?.mid ?: NAN
        val h1All = if (inst.kind == "metal" && !spot.isNaN()) BarOps.spotAdjust(sym, h1All0, spot) else h1All0
        val h1 = h1All.tail(2500)
        val h4 = BarOps.derive(h1All, "H4").let { it.tail(1500) }
        val mtf = Technical.buildFrame(h1, h4, BarOps.derive(h1All, "D1"))
        val F = mtf.F
        val sums = linkedMapOf("D1" to Technical.summary(mtf.frames["D1"]!!.frame, "D1"), "H4" to Technical.summary(mtf.frames["H4"]!!.frame, "H4"),
            "H1" to Technical.summary(F, "H1"))
        for ((tf, b0, sec) in listOf(Triple("M15", raw?.second, 900L), Triple("M5", raw?.third, 300L))) {
            val b = b0?.let { BarOps.completed(it, sec, now) } ?: continue
            if (b.n < 250) continue
            val bb = if (inst.kind == "metal" && !spot.isNaN()) BarOps.spotAdjust(sym, b, spot) else b
            sums[tf] = Technical.summary(Technical.tfFrame(bb.tail(800), tf, false).frame, tf)
        }
        val align = Technical.alignment(sums)
        val i = F.n - 1
        val atr = F.at("atr", i)
        val regime = Diagnostics.regime(F)
        val anom = Diagnostics.anomalies(F, st.maxVolZ)
        val barAge = (now - h1All.t.last()) / 60.0 - 60
        val dq = Diagnostics.dataQuality(h1All, q?.mid, atr, barAge, st.maxBarAgeMin)
        val mf = Macro.features(macro, F.t)
        val sd = Macro.strengthDiff(strength, inst, F.t)
        val fb = Fundamental.bias(inst, Macro.snapshot(mf), Macro.snapshot(sd), cb)
        val ev = if (events0 == null) EventRisk(true, "Calendário econômico indisponível: não é possível verificar eventos críticos", null, null)
        else Events.risk(inst, events, now, st.blackoutBefore, st.blackoutAfter)
        val market = MarketRow(symbol = sym, trend = sums.mapValues { it.value.direction }, alignment = r(align, 3),
            regime = regime.label, fundamental_score = fb.score, event_block = ev.reason,
            next_event = ev.next?.let { NextEvent(it.currency, it.title, iso(it.time)) })
        val out = Inst(sym, market, mutableListOf(), atr, mutableListOf())
        if (q == null) return out
        val ctx = Ctx(inst, F, sums, align, regime, anom, dq, fb, ev, q, now, st)
        val real = Candidates.generate(F, lastN = 2)
        for (c in real) out.cands.add(candidate(ctx, c, Features.build(inst, F, c, mf, sd)))
        // ranking: plano estrutural nas direções sem gatilho ativo (nunca vira sinal)
        for (d in intArrayOf(1, -1)) {
            if (real.any { it.dir == d }) continue
            Candidates.plan(F, d, q.mid)?.let { out.cands.add(candidate(ctx, it, null)) }
        }
        return Inst(sym, market.copy(candidates = real.size), out.cands, atr, out.raw)
    }

    private class Ctx(val inst: Instruments.Inst, val F: Frame, val sums: Map<String, Technical.TfSummary>, val align: Double,
                      val regime: Regime, val anom: List<String>, val dq: List<String>, val fb: FundBias, val ev: EventRisk,
                      val q: Q, val now: Long, val st: EngineSettings)

    private fun candidate(x: Ctx, c: Candidates.Cand, feats: Map<String, Double>?): Candidate {
        val plan = c.setup == Candidates.PLAN
        val inst = x.inst; val st = x.st; val q = x.q; val d = c.dir
        val atr = c.atr
        val entry = if (d == 1) q.ask else q.bid
        val slip = st.slipPips * inst.pip + st.slipAtr * atr
        val risk = d * (entry - c.sl)
        val rr1 = if (risk > 0) d * (c.tp1 - entry) / risk else NAN
        val rr2 = if (risk > 0) d * (c.tp2 - entry) / risk else NAN
        val costR = if (risk > 0) (q.spread / 2 + slip) / risk else Double.POSITIVE_INFINITY
        val rrNet = if (risk > 0) d * (c.tp1 - entry) / (risk + slip) else NAN
        val drift = d * (entry - c.entryRef) / atr
        val p = if (plan || feats == null) null else model?.predict(feats)
        // sem setup ativo o modelo não se aplica: taxa-base histórica com IC de Wilson
        val cal = if (plan) model?.let { m ->
            val (lo, hi) = Risk.wilson(Math.round(m.meta.baseRate * m.meta.nTrain).toInt(), m.meta.nTrain)
            LogisticModel.CalBin(0.0, 1.0, m.meta.nTrain, m.meta.baseRate, m.meta.baseRate, lo, hi)
        } else p?.let { model!!.calibrated(it) }
        val pUse = if (plan) cal?.observed else if (cal != null && cal.n >= 30) cal.observed else p
        val ev = if (model != null && pUse != null && !rr1.isNaN()) model.expectedR(pUse, rr1) else null
        val evLo = if (model != null && cal != null && !rr1.isNaN()) model.expectedR(cal.ciLo, rr1) else null

        val gates = ArrayList<Gate>()
        fun gate(n: String, ok: Boolean, det: String) = gates.add(Gate(n, ok, det))
        if (plan) gate("setup_ativo", false, "Sem gatilho técnico nos últimos candles H1 fechados — aguardar a formação de um setup")
        val open = Time.marketOpen(x.now, inst.kind)
        gate("mercado_aberto", open, if (open) "Mercado aberto" else "Mercado fechado/pausa de negociação")
        val age = q.ageS(x.now.toDouble())
        gate("cotacao_atual", age <= st.maxQuoteAgeS, "Cotação com ${"%.0f".format(age)}s de idade (máx. ${st.maxQuoteAgeS.toInt()}s), fonte ${q.source}")
        gate("qualidade_dados", x.dq.isEmpty(), x.dq.joinToString("; ").ifBlank { "Dados íntegros" })
        val tfx = q.check["truefx_pips"]; val lim = max(3.0, 2 * q.spread / inst.pip)
        gate("consistencia_cotacao", tfx == null || abs(tfx) <= lim,
            (if (tfx != null) "Diferença vs. TrueFX ${"%+.1f".format(tfx)} pips (máx. ${"%.1f".format(lim)})" else "Sem segunda fonte bid/ask para este ativo") +
                (q.check["yahoo_pips"]?.let { "; vs. Yahoo ${"%+.1f".format(it)} pips" } ?: ""))
        gate("anomalia_mercado", x.anom.isEmpty(), x.anom.joinToString("; ").ifBlank { "Sem anomalias de preço" })
        gate("choque_volatilidade", !x.regime.volShock && x.regime.volatility != "extrema", x.regime.label)
        gate("evento_economico", !x.ev.blocked, x.ev.reason ?: "Sem evento crítico na janela")
        val spAtr = q.spread / atr
        gate("spread", spAtr <= st.maxSpreadAtr, "Spread ${"%.1f".format(q.spread / inst.pip)} pips = ${"%.2f".format(spAtr)} ATR(H1) (máx. ${st.maxSpreadAtr})" +
            if (q.spreadSource == "estimated") " [estimado]" else "")
        gate("stop_valido", risk > 0, if (risk <= 0) "Preço atual além do stop" else "Risco ${"%.1f".format(risk / inst.pip)} pips")
        gate("custo_em_R", costR <= st.maxCostR, "Custo de entrada ${"%.3f".format(costR)}R (máx. ${st.maxCostR})")
        gate("risco_retorno", !rrNet.isNaN() && rrNet >= st.minRrNet, "R:R líquido ${"%.2f".format(rrNet)} (mín. ${st.minRrNet})")
        gate("deriva_de_entrada", abs(drift) <= st.maxDriftAtr, "Preço ${"%+.2f".format(drift)} ATR do fechamento do sinal (máx. ${st.maxDriftAtr})")
        if (st.requireModel) gate("modelo_validado", model?.meta?.validated == true,
            if (model?.meta?.validated == true) "Modelo validado fora da amostra" else "Modelo sem vantagem preditiva e econômica comprovada fora da amostra")
        gate("valor_esperado", ev != null && ev >= st.minEv, if (ev != null) "EV ${"%+.3f".format(ev)}R (mín. +${st.minEv}R)" else "EV não estimável")

        // pontuação multifatorial (mesmos pesos do motor Python)
        val tech = (0.4 * x.align * d + 0.15 * c.inZone + 0.1 * c.tp1Structural + 0.15 * min(c.roomR, 3.0) / 3 +
            0.1 * (if (c.triggerEngulf == 1 || c.triggerPin == 1) 1 else 0) + 0.1 * (if (c.nSetups > 1) 1 else 0)).coerceIn(-1.0, 1.0)
        val fund = x.fb.score * d
        val trendSetups = c.setup in setOf("PULLBACK", "TREND", "BREAKOUT", Candidates.PLAN)
        val regimeFit = (if ((trendSetups && x.regime.trend == "tendência") || (!trendSetups && x.regime.trend != "tendência")) 0.6 else -0.3) -
            (if (x.regime.volShock || x.regime.volatility == "extrema") 0.6 else 0.0)
        val costC = 1 - 2 * min(costR / max(st.maxCostR, 1e-9), 1.0)
        val evC = ((ev ?: -0.5) / 0.5).coerceIn(-1.0, 1.0)
        val score = 50 + 50 * (0.45 * evC + 0.20 * tech + 0.15 * fund + 0.10 * regimeFit + 0.10 * costC)

        var validUntil = x.now + st.validityMin * 60L
        x.ev.next?.let { e -> if (e.time - st.blackoutBefore * 60L < validUntil) validUntil = max(x.now, e.time - st.blackoutBefore * 60L) }
        val limits = ArrayList<String>()
        var level = "baixa"
        if (model == null) limits.add("Modelo indisponível — probabilidade não estimada")
        else {
            if (!model.meta.validated) limits.add("Modelo NÃO validado fora da amostra (BSS ${"%+.4f".format(model.meta.bss)}, AUC ${"%.3f".format(model.meta.auc)}; " +
                "regra: ${model.meta.validationRule}): sem evidência suficiente de vantagem preditiva e econômica")
            if ((cal?.n ?: 0) < 50) limits.add("Faixa de probabilidade com poucas observações OOS (n=${cal?.n ?: 0})")
            val width = cal?.let { it.ciHi - it.ciLo } ?: 1.0
            if (model.meta.validated && (cal?.n ?: 0) >= 50) {
                level = if (width <= 0.2) "média" else "baixa"
                if (model.meta.bss >= 0.02 && model.meta.auc >= 0.58 && width <= 0.12) level = "alta"
            }
        }
        if (plan) { level = "baixa"; limits.add(0, "Sem setup ativo: probabilidade = taxa-base histórica de todos os setups (o modelo só avalia setups formados)") }
        limits.add("Probabilidades históricas não garantem resultados futuros; custos reais podem diferir")
        val dirTxt = if (d == 1) "BUY" else "SELL"
        val tech1 = ArrayList<String>()
        tech1.add("Setup: ${Candidates.SETUP_PT[c.setup]}" + if (c.nSetups > 1) " (confluência de ${c.nSetups} setups)" else "")
        for (tf in listOf("D1", "H4", "H1", "M15")) x.sums[tf]?.let { tech1.add("$tf: tendência ${it.trendText}; último evento ${it.lastEvent}; RSI ${"%.1f".format(it.rsi)}") }
        if (c.inZone == 1) tech1.add("Preço reagiu em zona institucional (FVG/Order Block) a favor do trade")
        if (c.atEma == 1) tech1.add("Recuo testou a EMA50 do H1 (zona de valor)")
        if (c.triggerEngulf == 1) tech1.add("Gatilho: candle de engolfo no H1")
        if (c.triggerPin == 1) tech1.add("Gatilho: rejeição (pin bar) no H1")
        if (c.pdSweep == 1) tech1.add("Varredura da máxima/mínima do pregão anterior com fechamento de volta (falso rompimento)")
        tech1.add("Espaço livre até o obstáculo oposto: ${"%.1f".format(c.roomR)}R; alinhamento MTF ${"%+.2f".format(x.align * d)}")
        val fundL = x.fb.components.map { "${it.text} → contribuição ${"%+.3f".format(it.contribution * d)}" }.ifEmpty { listOf("Sem componentes fundamentalistas disponíveis") }
        val quant = listOf("Regime: ${x.regime.label}", "Percentil de volatilidade (ATR): ${r(x.regime.atrPct, 3)}") +
            (feats?.let { f -> model?.contributions(f) }?.take(5)?.map { "Modelo: ${it.first} contribui ${"%+.3f".format(it.second)} ao log-odds" } ?: emptyList())
        val opp = x.F.at(if (d == 1) "near_lo" else "near_hi", c.i)
        val nxt = x.ev.next
        return Candidate(
            instrument = inst.symbol, direction = dirTxt, setup = c.setup, setup_name = Candidates.SETUP_PT[c.setup] ?: c.setup,
            execution_type = "Entrada imediata a mercado (Market Execution)",
            reference_quote = RefQuote(q.bid, q.ask, q.mid, r(q.spread / inst.pip, 2), q.spreadSource, iso(q.time.toLong()), q.source, r(age, 1)),
            entry = Level(inst.roundPrice(entry), side = if (d == 1) "ASK" else "BID"),
            stop_loss = Level(inst.roundPrice(c.sl), r(abs(entry - c.sl) / inst.pip, 1), if (plan) "Além do último swing protegido + 0,25 ATR (entre 1 e 2,5 ATR do preço atual)" else "Além do extremo estrutural do setup + buffer de 0,25 ATR (mín. 1 ATR)"),
            take_profit = listOf(
                TakeProfit("TP1 (50%)", inst.roundPrice(c.tp1), r(abs(c.tp1 - entry) / inst.pip, 1), r(rr1, 2), if (c.tp1Structural == 1) "Pool de liquidez oposto" else "Alvo padrão 1,5R"),
                TakeProfit("TP2 (restante, stop no preço de entrada)", inst.roundPrice(c.tp2), r(abs(c.tp2 - entry) / inst.pip, 1), r(rr2, 2))),
            risk_reward = RiskReward(r(rr1, 2), r(rr2, 2), r(rrNet, 2), r(costR, 3)),
            probability = Probability(p?.let { r(it, 3) }, cal?.let { r(it.observed, 3) }, cal?.let { listOf(r(it.ciLo, 3), r(it.ciHi, 3)) },
                cal?.n, "TP1 atingido antes do Stop Loss",
                if (plan) "Taxa-base histórica (sem setup ativo; IC de Wilson)" else "Regressão logística (walk-forward) → frequência observada fora da amostra na faixa"),
            expected_value_r = ev?.let { r(it, 3) }, expected_value_r_ci_low = evLo?.let { r(it, 3) },
            confidence = Confidence(level, limits), score = Math.round(score * 10) / 10.0,
            justification = Justification(tech1, fundL, quant),
            invalidation = listOf(
                "Fechamento H1 ${if (d == 1) "abaixo" else "acima"} de ${inst.roundPrice(c.sl)} (stop)",
                "Preço se afastar mais de ${st.maxDriftAtr} ATR (${"%.1f".format(st.maxDriftAtr * atr / inst.pip)} pips) de ${inst.roundPrice(c.entryRef)} antes da entrada",
                "CHoCH ${if (d == 1) "de baixa" else "de alta"} no H1 antes de atingir o TP1",
                "Evento econômico de alto impacto não previsto / spread acima do limite",
            ) + (nxt?.let { listOf("Evento crítico: ${it.currency} ${it.title} às ${iso(it.time).substring(11, 16)} UTC") } ?: emptyList()),
            validity = Validity(iso(validUntil), ((validUntil - x.now) / 60).toInt()),
            scenarios = Scenarios("${if (d == 1) "Alta" else "Baixa"} até ${inst.roundPrice(c.tp1)} (TP1) e extensão a ${inst.roundPrice(c.tp2)}",
                "Falha do setup: rompimento de ${inst.roundPrice(c.sl)} abre caminho para a liquidez em ${if (opp.isNaN()) "—" else inst.roundPrice(opp)}",
                listOfNotNull(x.ev.reason, if (fund < -0.2) "Viés fundamentalista contrário" else null,
                    if (x.align * d < 0) "Timeframes superiores desalinhados" else null,
                    if (x.regime.volatility in setOf("alta", "extrema")) "Regime ${x.regime.label}" else null,
                    if (q.spreadSource == "estimated") "Spread estimado (fonte sem bid/ask)" else null)),
            gates = gates, has_setup = !plan,
        )
    }

    /** Top-5 por nota: uma oportunidade por instrumento (direção de maior nota), com status explícito. */
    private fun ranking(all: List<Candidate>, bestOrig: Candidate?, best: Candidate?, mids: Map<String, Double>,
                        st: EngineSettings, k: Int = 5): List<Candidate> {
        val byInst = LinkedHashMap<String, Candidate>()
        for (c in all) {
            val cur = byInst[c.instrument]
            if (cur == null || c === bestOrig || (cur !== bestOrig && c.score > cur.score)) byInst[c.instrument] = c
        }
        return byInst.values.sortedByDescending { it.score }.take(k).mapIndexed { i, c0 ->
            val c = if (c0 === bestOrig && best != null) best else c0
            val failed = c.gates.filter { !it.passed }.map { it.gate }
            val (stt, txt) = when {
                c0 === bestOrig -> "SINAL" to "Sinal emitido: todos os portões aprovados"
                c.gates.all { it.passed } -> "ELEGIVEL" to "Aprovada em todos os portões (apenas um sinal é emitido por análise)"
                !c.has_setup -> "AGUARDANDO_GATILHO" to "Sem setup ativo: acompanhar e aguardar o gatilho técnico"
                else -> "OBSERVACAO" to "Não recomendada: bloqueada por ${failed.joinToString(", ")}"
            }
            val risk = c.risk ?: run {  // dimensionamento informativo
                val sz = Risk.size(Instruments.get(c.instrument), c.entry.price, c.stop_loss.price, st.equity, st.riskPct, st.account, mids, st.leverage)
                RiskEval(false, emptyList(), Sizing(sz.ok, sz.lots, sz.riskAmount, sz.riskPct, st.account, sz.margin, sz.reason))
            }
            c.copy(rank = i + 1, status = stt, status_text = txt, blocked_by = failed, risk = risk)
        }
    }

    private fun riskCheck(sym: String, d: Int, entry: Double, stop: Double, mids: Map<String, Double>, st: EngineSettings, rs: RiskState): RiskEval {
        val reasons = ArrayList<String>()
        val eq = st.equity
        if (rs.pnlDay <= -st.maxDailyLossPct / 100 * eq) reasons.add("Limite de perda diária atingido (${"%.2f".format(rs.pnlDay)})")
        if (rs.pnlWeek <= -st.maxWeeklyLossPct / 100 * eq) reasons.add("Limite de perda semanal atingido (${"%.2f".format(rs.pnlWeek)})")
        if (rs.open.size >= st.maxOpen) reasons.add("${rs.open.size} sinais ativos (máx. ${st.maxOpen})")
        if (rs.open.any { it.symbol == sym }) reasons.add("Já existe sinal ativo em $sym")
        val inst = Instruments.get(sym)
        val exp = mapOf(inst.base to d, inst.quote to -d)
        for ((cur, sg) in exp) {
            val used = rs.open.sumOf { o ->
                val oi = Instruments.get(o.symbol)
                val pe = mapOf(oi.base to o.dir, oi.quote to -o.dir)
                if (pe[cur] == sg) o.riskAmount / eq * 100 else 0.0
            }
            if (used + st.riskPct > st.maxRiskPerCurrencyPct + 1e-9) reasons.add("Risco agregado em $cur ${"%.2f".format(used + st.riskPct)}% (máx. ${st.maxRiskPerCurrencyPct}%)")
        }
        val sz = Risk.size(inst, entry, stop, eq, st.riskPct, st.account, mids, st.leverage)
        if (!sz.ok) reasons.add(sz.reason ?: "dimensionamento inválido")
        else if (sz.margin > 0.5 * eq) reasons.add("Margem estimada ${sz.margin} acima de 50% do capital")
        return RiskEval(reasons.isEmpty(), reasons, Sizing(sz.ok, sz.lots, sz.riskAmount, sz.riskPct, st.account, sz.margin, sz.reason))
    }
}

package com.fxintel.app.engine

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.temporal.ChronoUnit
import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min
import kotlin.math.tanh

/** Fundamentos (bancos centrais, viés), eventos econômicos, regime, anomalias, qualidade e risco. */

data class Bank(val ccy: String, val bank: String, val rate: Double, val stance: Int, val nextMeeting: String?)

class CentralBanks(val asOf: String?, val banks: Map<String, Bank>) {
    fun ageDays(today: LocalDate = LocalDate.now()): Long? = asOf?.let { ChronoUnit.DAYS.between(LocalDate.parse(it), today) }

    companion object {
        fun parse(text: String): CentralBanks {
            val o = Json.parseToJsonElement(text).jsonObject
            val banks = o["banks"]?.jsonObject?.mapValues { (k, v) ->
                val b = v.jsonObject
                Bank(k, (b["bank"] as JsonPrimitive).content, (b["rate"] as JsonPrimitive).doubleOrNull ?: NAN,
                    (b["stance"] as? JsonPrimitive)?.intOrNull ?: 0, (b["next_meeting"] as? JsonPrimitive)?.contentOrNull)
            } ?: emptyMap()
            return CentralBanks((o["as_of"] as? JsonPrimitive)?.contentOrNull, banks)
        }
    }
}

data class Component(val factor: String, val value: Double, val weight: Double, val contribution: Double, val text: String)
data class FundBias(val score: Double, val components: List<Component>)

object Fundamental {
    private fun t(x: Double?, scale: Double = 1.0) = if (x == null || x.isNaN()) 0.0 else tanh(x / scale)
    private fun fmt(x: Double?, p: String = "%+.2f") = if (x == null || x.isNaN()) "—" else p.format(x)

    fun bias(inst: Instruments.Inst, macro: Map<String, Double>, str: Map<String, Double>, cb: CentralBanks): FundBias {
        val comps = ArrayList<Component>()
        fun add(name: String, v: Double, w: Double, text: String) = comps.add(Component(name, v, w, v * w, text))
        val b = inst.base; val q = inst.quote
        if (inst.kind == "fx") {
            val bb = cb.banks[b]; val bq = cb.banks[q]
            if (bb != null && bq != null) {
                val diff = bb.rate - bq.rate
                add("diferencial_juros", t(diff, 2.0), 0.22, "Taxa ${bb.bank} ${"%.2f".format(bb.rate)}% vs ${bq.bank} ${"%.2f".format(bq.rate)}% (diferencial ${"%+.2f".format(diff)} p.p.)")
                val sd = bb.stance - bq.stance
                if (sd != 0) add("viés_política", sd / 2.0, 0.13, "Viés relativo de política monetária " +
                    if (sd > 0) "mais hawkish no ativo base" else "mais hawkish na moeda cotada")
            }
        } else {
            val d10 = macro["us10y_d120"]
            add("juros_reais_proxy", -t(d10, 1.5), 0.25, "Variação de 5 dias do Treasury 10a (z=${fmt(d10)})")
            val dx = macro["dxy_r120"]
            add("dólar", -t(dx, 1.5), 0.20, "Momento de 5 dias do DXY (z=${fmt(dx)}); dólar forte pressiona metais")
        }
        val s1 = str["str_diff_24"]; val s5 = str["str_diff_120"]
        if ((s1 != null && !s1.isNaN()) || (s5 != null && !s5.isNaN()))
            add("força_relativa", 0.5 * t(s1, 1.5) + 0.5 * t(s5, 1.5), 0.25, "Força relativa base−cotada: 1d z=${fmt(s1)}, 5d z=${fmt(s5)}")
        val ro = macro["risk_on"]
        val beta = (Macro.RISK_BETA[b] ?: 0.0) - (Macro.RISK_BETA[q] ?: 0.0)
        if (ro != null && !ro.isNaN() && beta != 0.0)
            add("sentimento_risco", t(ro, 1.5) * max(-1.0, min(1.0, beta / 1.5)), 0.15,
                "Sentimento de risco ${if (ro > 0) "positivo (risk-on)" else "negativo (risk-off)"} (índice ${fmt(ro)}; VIX ${fmt(macro["vix_lvl"], "%.1f")}); sensibilidade do par ${"%+.1f".format(beta)}")
        if ((b == "USD" || q == "USD") && inst.kind == "fx") {
            val dx = macro["dxy_r120"]; val y5 = macro["us5y_d120"]
            if (dx != null && !dx.isNaN()) {
                val sg = if (b == "USD") 1.0 else -1.0
                add("macro_eua", sg * (0.6 * t(dx, 1.5) + 0.4 * t(y5, 1.5)), 0.15, "DXY 5d z=${fmt(dx)}, Treasury 5a 5d z=${fmt(y5)}")
            }
        }
        if (b == "CAD" || q == "CAD") {
            val w = macro["wti_r120"]
            if (w != null && !w.isNaN()) add("petróleo", (if (b == "CAD") 1.0 else -1.0) * t(w, 1.5), 0.10, "Petróleo WTI 5d z=${fmt(w)} (CAD é moeda de commodity)")
        }
        val tw = comps.sumOf { it.weight }.let { if (it == 0.0) 1.0 else it }
        val score = (comps.sumOf { it.contribution } / tw).coerceIn(-1.0, 1.0)
        return FundBias(Math.round(score * 1000) / 1000.0, comps)
    }
}

data class EconEventK(val title: String, val currency: String, val time: Long, val impact: String) {
    val critical: Boolean get() = impact == "High" || (impact == "Medium" && CRIT.any { title.lowercase().contains(it.lowercase()) })
    companion object {
        val CRIT = listOf("Non-Farm", "CPI", "Rate Decision", "Interest Rate", "FOMC", "Cash Rate", "Monetary Policy",
            "Press Conference", "GDP", "Employment Change", "Unemployment Rate", "Retail Sales", "PCE", "Powell", "Lagarde", "Bailey", "Ueda")
        fun parse(text: String): List<EconEventK> = Json.parseToJsonElement(text).let { el ->
            (el as? kotlinx.serialization.json.JsonArray)?.mapNotNull { x ->
                val o = x.jsonObject
                val ts = (o["date"] as? JsonPrimitive)?.contentOrNull ?: return@mapNotNull null
                val t = runCatching { OffsetDateTime.parse(ts).toEpochSecond() }.getOrNull() ?: return@mapNotNull null
                EconEventK((o["title"] as? JsonPrimitive)?.contentOrNull ?: "", ((o["country"] as? JsonPrimitive)?.contentOrNull ?: "").uppercase(),
                    t, (o["impact"] as? JsonPrimitive)?.contentOrNull ?: "Low")
            }?.sortedBy { it.time } ?: emptyList()
        }
    }
}

data class EventRisk(val blocked: Boolean, val reason: String?, val next: EconEventK?, val minutesToNext: Double?)

object Events {
    fun relevant(inst: Instruments.Inst): Set<String> {
        val s = setOf(inst.base, inst.quote) - setOf("XAU", "XAG")
        return if (inst.kind == "metal") s + "USD" else s
    }

    fun risk(inst: Instruments.Inst, events: List<EconEventK>, now: Long, beforeMin: Int = 60, afterMin: Int = 30): EventRisk {
        val cur = relevant(inst)
        val rel = events.filter { it.currency in cur && it.impact != "Holiday" }
        val nxt = rel.firstOrNull { it.time >= now && it.time <= now + 24 * 3600 && it.critical }
        var reason: String? = null
        if (nxt != null && nxt.time - now <= beforeMin * 60L)
            reason = "Evento de alto impacto em ${(nxt.time - now) / 60} min: ${nxt.currency} ${nxt.title}"
        val recent = rel.lastOrNull { it.critical && it.time < now && now - it.time <= afterMin * 60L }
        if (recent != null && reason == null)
            reason = "Janela pós-evento (${(now - recent.time) / 60} min após ${recent.currency} ${recent.title}): volatilidade e spreads anormais"
        return EventRisk(reason != null, reason, nxt, nxt?.let { (it.time - now) / 60.0 })
    }
}

data class Regime(val volatility: String, val trend: String, val volShock: Boolean, val atrPct: Double, val label: String)

object Diagnostics {
    fun regime(F: Frame): Regime {
        val i = F.n - 1
        val pct = F.at("atr_pct", i); val adx = F.at("adx", i); val er = F.at("er", i)
        val slow = F.at("atr_slow", i); val shock = if (slow > 0) F.at("atr_fast", i) / slow else NAN
        val vol = when { pct.isNaN() -> "desconhecida"; pct >= 0.95 -> "extrema"; pct >= 0.75 -> "alta"; pct <= 0.25 -> "baixa"; else -> "normal" }
        val tr = when { adx >= 22 && er >= 0.30 -> "tendência"; adx < 18 && er < 0.20 -> "lateral"; else -> "transição" }
        val shocked = !shock.isNaN() && shock >= 2.0
        return Regime(vol, tr, shocked, pct, "$tr / volatilidade $vol" + if (shocked) " / CHOQUE de volatilidade" else "")
    }

    private fun robustZLast(x: DoubleArray, n: Int = 500): DoubleArray {
        val med = S.rollingMedian(x, n, max(50, n / 5))
        val dev = DoubleArray(x.size) { abs(x[it] - med[it]) }
        val mad = S.rollingMedian(dev, n, max(50, n / 5))
        return DoubleArray(x.size) { (x[it] - med[it]) / (1.4826 * S.zeroToNaN(mad[it])) }
    }

    fun anomalies(F: Frame, maxZ: Double): List<String> {
        val n = F.n; val st = max(0, n - 520)
        val sub = Frame(F.t.copyOfRange(st, n))
        val h = F["h"].copyOfRange(st, n); val l = F["l"].copyOfRange(st, n); val c = F["c"].copyOfRange(st, n)
        val ret = F["ret1"].copyOfRange(st, n)
        val zr = robustZLast(DoubleArray(sub.n) { (h[it] - l[it]) / c[it] })
        val zret = robustZLast(DoubleArray(sub.n) { abs(ret[it]) })
        val flags = ArrayList<String>()
        val a = zr.last(); val b = zret.last()
        if (a > maxZ) flags.add("Faixa do último candle H1 anormal (z robusto ${"%.1f".format(a)})")
        if (b > maxZ) flags.add("Retorno do último candle H1 anormal (z robusto ${"%.1f".format(b)})")
        val recent = zr.takeLast(6).filter { !it.isNaN() }.maxOrNull()
        if (recent != null && recent > maxZ * 1.4) flags.add("Pico de volatilidade nas últimas 6 horas (z ${"%.1f".format(recent)})")
        return flags
    }

    fun dataQuality(h1: Bars, quoteMid: Double?, atr: Double, barAgeMin: Double, maxBarAgeMin: Double): List<String> {
        val issues = ArrayList<String>()
        if (barAgeMin > maxBarAgeMin) issues.add("Último candle H1 com ${"%.0f".format(barAgeMin)} min de idade (limite ${maxBarAgeMin.toInt()})")
        val tail = h1.tail(24)
        val flat = (0 until tail.n).count { tail.h[it] - tail.l[it] <= 0 }.toDouble() / max(1, tail.n)
        if (flat > 0.3) issues.add("${"%.0f".format(flat * 100)}% dos últimos candles sem variação (feed congelado?)")
        if (quoteMid != null && atr > 0) {
            val gap = abs(quoteMid - h1.c[h1.n - 1]) / atr
            if (gap > 3) issues.add("Divergência cotação vs. último fechamento de ${"%.1f".format(gap)} ATR")
        }
        return issues
    }
}

/** Dimensionamento por risco e gestor de risco local (exposição = sinais ativos acompanhados no aparelho). */
object Risk {
    data class Sizing(val ok: Boolean, val lots: Double = 0.0, val riskAmount: Double = 0.0, val riskPct: Double = 0.0,
                      val margin: Double = 0.0, val reason: String? = null)

    /** Intervalo de Wilson (90%) para uma proporção. */
    fun wilson(k: Int, n: Int, z: Double = 1.645): Pair<Double, Double> {
        if (n <= 0) return 0.0 to 1.0
        val p = k.toDouble() / n
        val den = 1 + z * z / n
        val c = (p + z * z / (2 * n)) / den
        val h = z * Math.sqrt(p * (1 - p) / n + z * z / (4.0 * n * n)) / den
        return maxOf(0.0, c - h) to minOf(1.0, c + h)
    }

    fun conversion(from: String, to: String, mids: Map<String, Double>): Double? {
        if (from == to) return 1.0
        mids["$from$to"]?.let { return it }
        mids["$to$from"]?.let { if (it > 0) return 1.0 / it }
        if (from != "USD" && to != "USD") {
            val a = conversion(from, "USD", mids); val b = conversion("USD", to, mids)
            if (a != null && b != null) return a * b
        }
        return null
    }

    fun size(inst: Instruments.Inst, entry: Double, stop: Double, equity: Double, riskPct: Double, account: String,
             mids: Map<String, Double>, leverage: Double = 30.0, slip: Double = 0.0, minLot: Double = 0.01, step: Double = 0.01): Sizing {
        val dist = abs(entry - stop) + slip
        val conv = conversion(inst.quote, account, mids) ?: return Sizing(false, reason = "sem taxa de conversão ${inst.quote}->$account")
        if (dist <= 0) return Sizing(false, reason = "distância de stop inválida")
        val units = equity * riskPct / 100 / (dist * conv)
        val raw = units / inst.contractSize
        val lots = Math.round(floor(raw / step + 1e-9) * step * 1e8) / 1e8
        if (lots < minLot) return Sizing(false, reason = "posição mínima ($minLot lote) excederia o risco autorizado (lote calculado ${"%.4f".format(raw)})")
        val u = lots * inst.contractSize
        val risk = u * dist * conv
        return Sizing(true, lots, Math.round(risk * 100) / 100.0, Math.round(risk / equity * 100 * 1000) / 1000.0,
            Math.round(u * entry * conv / leverage * 100) / 100.0)
    }
}

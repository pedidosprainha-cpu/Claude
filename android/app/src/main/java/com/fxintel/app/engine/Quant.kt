package com.fxintel.app.engine

import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.ln1p
import kotlin.math.min

/** Intermercados, força relativa, features e modelo probabilístico — porte de fundamental/macro.py, quant/features.py. */
object Macro {
    val RISK_BETA = mapOf("AUD" to 1.0, "NZD" to 1.0, "CAD" to 0.5, "GBP" to 0.3, "EUR" to 0.1, "USD" to -0.3,
        "CHF" to -0.7, "JPY" to -1.0, "XAU" to -0.5, "XAG" to 0.2)

    /** merge_asof por horário de conclusão (H1) com tolerância de 80 h. */
    fun align(src: Bars, index: LongArray, maxGapH: Int = 80): DoubleArray {
        val out = nanArray(index.size)
        var j = -1
        for (i in index.indices) {
            val lt = index[i] + 3600
            while (j + 1 < src.n && src.t[j + 1] + 3600 <= lt) j++
            if (j >= 0 && lt - (src.t[j] + 3600) <= maxGapH * 3600L) out[i] = src.c[j]
        }
        return out
    }

    private fun z(x: DoubleArray, n: Int = 500): DoubleArray {
        val sd = S.rollingStd(x, n, 100, 1)
        return S.clip(DoubleArray(x.size) { x[it] / S.zeroToNaN(sd[it]) }, -4.0, 4.0)
    }

    private fun logArr(x: DoubleArray) = DoubleArray(x.size) { if (x[it].isNaN()) NAN else ln(x[it]) }

    fun features(macro: Map<String, Bars>, index: LongArray): Frame {
        val out = Frame(index)
        val closes = macro.filterValues { it.n > 0 }.mapValues { align(it.value, index) }
        closes["DXY"]?.let { val lc = logArr(it); out["dxy_r24"] = z(S.diff(lc, 24)); out["dxy_r120"] = z(S.diff(lc, 120)) }
        for ((k, col) in listOf("US10Y" to "us10y", "US5Y" to "us5y")) closes[k]?.let {
            out["${col}_d24"] = z(S.diff(it, 24)); out["${col}_d120"] = z(S.diff(it, 120))
        }
        if (closes.containsKey("US10Y") && closes.containsKey("US3M")) {
            val a = closes["US10Y"]!!; val b = closes["US3M"]!!
            out["curve_10y3m"] = DoubleArray(index.size) { a[it] - b[it] }
        }
        closes["VIX"]?.let { v -> out["vix_lvl"] = v; out["vix_d24"] = z(S.diff(v, 24)); out["vix_pct"] = S.rollingRankPct(v, 1500, 200) }
        closes["SPX_FUT"]?.let { val lc = logArr(it); out["es_r24"] = z(S.diff(lc, 24)); out["es_r120"] = z(S.diff(lc, 120)) }
        closes["WTI"]?.let { val lc = logArr(it); out["wti_r24"] = z(S.diff(lc, 24)); out["wti_r120"] = z(S.diff(lc, 120)) }
        if (out.has("es_r24") || out.has("vix_d24")) {
            val es = if (out.has("es_r24")) out["es_r24"] else DoubleArray(index.size)
            val vx = if (out.has("vix_d24")) out["vix_d24"] else DoubleArray(index.size)
            out["risk_on"] = S.clip(DoubleArray(index.size) { (es[it] - vx[it]) / 2 }, -3.0, 3.0)
        }
        return out
    }

    /** Medidor de força relativa: retorna, por janela, (índice, moeda -> série centrada). */
    class Strength(val t: LongArray, val byWindow: Map<Int, Map<String, DoubleArray>>)

    fun strength(closes: Map<String, Bars>, windows: IntArray = intArrayOf(24, 120)): Strength? {
        val fx = closes.filterKeys { Instruments.get(it).kind == "fx" }
        if (fx.isEmpty()) return null
        val idx = fx.values.flatMap { it.t.toList() }.toSortedSet().toLongArray()
        val syms = fx.keys.toList()
        val lc = syms.associateWith { s ->
            val b = fx[s]!!; val out = nanArray(idx.size); var j = -1
            for (i in idx.indices) { while (j + 1 < b.n && b.t[j + 1] <= idx[i]) j++; if (j >= 0) out[i] = ln(b.c[j]) }
            // reindex(idx).ffill(): antes da primeira barra do par, NaN
            for (i in idx.indices) if (b.n == 0 || idx[i] < b.t[0]) out[i] = NAN
            out
        }
        val currencies = (syms.map { Instruments.get(it).base } + syms.map { Instruments.get(it).quote }).toSortedSet().toList()
        val res = HashMap<Int, Map<String, DoubleArray>>()
        for (w in windows) {
            val r = syms.associateWith { s ->
                val d = S.diff(lc[s]!!, w); val sd = S.rollingStd(d, 500, 100, 1)
                DoubleArray(idx.size) { d[it] / S.zeroToNaN(sd[it]) }
            }
            val st = LinkedHashMap<String, DoubleArray>()
            for (cur in currencies) {
                val terms = syms.mapNotNull { s ->
                    val ins = Instruments.get(s)
                    when (cur) { ins.base -> r[s]!! to 1.0; ins.quote -> r[s]!! to -1.0; else -> null }
                }
                st[cur] = DoubleArray(idx.size) { i ->
                    var sum = 0.0; var k = 0
                    for ((arr, sg) in terms) { val v = arr[i]; if (!v.isNaN()) { sum += sg * v; k++ } }
                    if (k == 0) NAN else sum / k
                }
            }
            val centered = st.mapValues { (_, arr) ->
                DoubleArray(idx.size) { i ->
                    var sum = 0.0; var k = 0
                    for (a in st.values) { val v = a[i]; if (!v.isNaN()) { sum += v; k++ } }
                    if (k == 0) NAN else arr[i] - sum / k
                }
            }
            res[w] = centered
        }
        return Strength(idx, res)
    }

    /** reindex(method="ffill") da força para o índice do instrumento: base − cotada (metais: −USD). */
    fun strengthDiff(st: Strength?, inst: Instruments.Inst, index: LongArray): Frame {
        val out = Frame(index)
        if (st == null) return out
        for ((w, m) in st.byWindow) {
            val b = if (inst.kind == "metal") null else m[inst.base]
            val q = m[inst.quote]
            if (b == null && q == null && inst.kind != "metal") { out["str_diff_$w"] = nanArray(index.size); continue }
            val arr = nanArray(index.size); var j = -1
            for (i in index.indices) {
                while (j + 1 < st.t.size && st.t[j + 1] <= index[i]) j++
                if (j < 0) continue
                val bv = b?.get(j) ?: 0.0; val qv = q?.get(j) ?: 0.0
                arr[i] = bv - qv
            }
            out["str_diff_$w"] = arr
        }
        return out
    }

    fun snapshot(f: Frame): Map<String, Double> = f.cols.mapValues { (_, a) -> a.lastOk() }
}

object Features {
    val NAMES = listOf("setup_pullback", "setup_breakout", "setup_sweep", "setup_trend", "n_setups",
        "d1_align", "h4_align", "h1_align", "d1_stack", "h4_stack", "h1_stack",
        "adx_h1", "adx_h4", "adx_d1", "di_h1", "rsi_h1", "rsi_h4", "rsi_d1",
        "macd_h1", "macd_h4", "ext20", "ext50", "ext_d1", "atr_pct", "er", "compression",
        "risk_atr", "rr1", "room_r", "tp1_structural", "day_pos", "pd_dist", "rsi_div",
        "close_pos", "since_event", "in_zone", "at_ema", "trigger_engulf", "trigger_pin", "pd_sweep",
        "sess_asia", "sess_london", "sess_overlap", "sess_ny",
        "usd_dxy24", "usd_dxy120", "usd_y5", "risk_beta_ro", "vix_pct", "oil_cad",
        "str24", "str120", "is_metal", "is_jpy")

    private fun clip(v: Double, lo: Double, hi: Double) = if (v.isNaN()) NAN else v.coerceIn(lo, hi)
    private fun inf2nan(v: Double) = if (v.isInfinite()) NAN else v

    fun usdExposure(inst: Instruments.Inst, d: Int) = when { inst.base == "USD" -> d; inst.quote == "USD" -> -d; else -> 0 }

    fun build(inst: Instruments.Inst, F: Frame, c: Candidates.Cand, macro: Frame?, str: Frame?): Map<String, Double> {
        val i = c.i; val d = c.dir.toDouble()
        fun f(k: String) = F.at(k, i)
        val atr = f("atr")
        val x = LinkedHashMap<String, Double>()
        x["setup_pullback"] = if (c.setup == "PULLBACK") 1.0 else 0.0
        x["setup_breakout"] = if (c.setup == "BREAKOUT") 1.0 else 0.0
        x["setup_sweep"] = if (c.setup == "SWEEP") 1.0 else 0.0
        x["setup_trend"] = if (c.setup == "TREND") 1.0 else 0.0
        x["n_setups"] = c.nSetups.toDouble()
        x["d1_align"] = c.d1Dir * d
        x["h4_align"] = S.fill0(f("h4_trend")) * d
        x["h1_align"] = f("trend") * d
        x["d1_stack"] = S.fill0(f("d1_ema_stack")) * d
        x["h4_stack"] = S.fill0(f("h4_ema_stack")) * d
        x["h1_stack"] = f("ema_stack") * d
        x["adx_h1"] = f("adx") / 50; x["adx_h4"] = f("h4_adx") / 50; x["adx_d1"] = f("d1_adx") / 50
        x["di_h1"] = d * (f("pdi") - f("mdi")) / S.zeroToNaN(f("pdi") + f("mdi"))
        x["rsi_h1"] = d * (f("rsi") - 50) / 50; x["rsi_h4"] = d * (f("h4_rsi") - 50) / 50; x["rsi_d1"] = d * (f("d1_rsi") - 50) / 50
        x["macd_h1"] = clip(d * f("macd_hist") / atr, -3.0, 3.0)
        x["macd_h4"] = clip(d * f("h4_macd_hist") / f("h4_atr"), -3.0, 3.0)
        x["ext20"] = clip(d * (f("c") - f("ema20")) / atr, -5.0, 5.0)
        x["ext50"] = clip(d * (f("c") - f("ema50")) / atr, -8.0, 8.0)
        x["ext_d1"] = clip(d * (f("c") - f("d1_ema50")) / f("d1_atr"), -6.0, 6.0)
        x["atr_pct"] = f("atr_pct"); x["er"] = f("er"); x["compression"] = clip(f("compression"), 0.0, 3.0)
        x["risk_atr"] = c.riskAtr; x["rr1"] = c.rr1; x["room_r"] = c.roomR; x["tp1_structural"] = c.tp1Structural.toDouble()
        val pos = (f("c") - f("day_l")) / S.zeroToNaN(f("day_h") - f("day_l"))
        x["day_pos"] = if (d > 0) pos else 1 - pos
        val pdLevel = if (d > 0) f("pdh") else f("pdl")
        x["pd_dist"] = clip(d * (pdLevel - f("c")) / atr, -6.0, 6.0)
        x["rsi_div"] = f("rsi_div") * d
        x["close_pos"] = if (d > 0) f("close_pos") else 1 - f("close_pos")
        x["since_event"] = ln1p(min(f("since_event"), 500.0))
        x["in_zone"] = c.inZone.toDouble(); x["at_ema"] = c.atEma.toDouble(); x["trigger_engulf"] = c.triggerEngulf.toDouble()
        x["trigger_pin"] = c.triggerPin.toDouble(); x["pd_sweep"] = c.pdSweep.toDouble()
        val sess = Time.sessionOf(c.t)
        x["sess_asia"] = if (sess == "asia") 1.0 else 0.0; x["sess_london"] = if (sess == "london") 1.0 else 0.0
        x["sess_overlap"] = if (sess == "overlap") 1.0 else 0.0; x["sess_ny"] = if (sess == "newyork" || sess == "late") 1.0 else 0.0
        val ux = usdExposure(inst, c.dir).toDouble()
        fun m(k: String): Double { val j = macro?.indexOf(c.t) ?: -1; return if (j >= 0 && macro!!.has(k)) macro[k][j] else NAN }
        x["usd_dxy24"] = ux * S.fill0(m("dxy_r24")); x["usd_dxy120"] = ux * S.fill0(m("dxy_r120")); x["usd_y5"] = ux * S.fill0(m("us5y_d120"))
        val beta = (Macro.RISK_BETA[inst.base] ?: 0.0) - (Macro.RISK_BETA[inst.quote] ?: 0.0)
        x["risk_beta_ro"] = d * beta * S.fill0(m("risk_on"))
        x["vix_pct"] = m("vix_pct").let { if (it.isNaN()) 0.5 else it }
        val cad = if (inst.base == "CAD") 1.0 else if (inst.quote == "CAD") -1.0 else 0.0
        x["oil_cad"] = d * cad * S.fill0(m("wti_r120"))
        fun s(k: String): Double {
            if (str == null || !str.has(k)) return 0.0  // Python: coluna ausente -> 0.0
            val j = str.indexOf(c.t)
            return if (j >= 0) str[k][j] else NAN
        }
        x["str24"] = d * s("str_diff_24"); x["str120"] = d * s("str_diff_120")
        x["is_metal"] = if (inst.kind == "metal") 1.0 else 0.0
        x["is_jpy"] = if (inst.base == "JPY" || inst.quote == "JPY") 1.0 else 0.0
        return x.mapValues { inf2nan(it.value) }
    }
}

/** Regressão logística exportada pelo treino Python (imputação pela mediana → padronização → logit). */
class LogisticModel(
    val features: List<String>, val median: DoubleArray, val mean: DoubleArray, val scale: DoubleArray,
    val coef: DoubleArray, val intercept: Double, val meta: ModelMeta,
) {
    fun predict(x: Map<String, Double>): Double {
        var z = intercept
        for (k in features.indices) {
            val raw = x[features[k].removePrefix("x_")] ?: NAN
            val v = if (raw.isNaN()) median[k] else raw
            z += coef[k] * (v - mean[k]) / scale[k]
        }
        return 1.0 / (1.0 + exp(-z))
    }

    /** Contribuições (coef × valor padronizado), maiores em módulo primeiro. */
    fun contributions(x: Map<String, Double>): List<Pair<String, Double>> = features.indices.map { k ->
        val name = features[k].removePrefix("x_")
        val raw = x[name] ?: NAN
        val v = if (raw.isNaN()) median[k] else raw
        name to coef[k] * (v - mean[k]) / scale[k]
    }.sortedByDescending { abs(it.second) }

    fun expectedR(p: Double, rr1: Double) = p * meta.kWin * rr1 + (1 - p) * meta.rLoss

    data class CalBin(val lo: Double, val hi: Double, val n: Int, val meanP: Double, val observed: Double, val ciLo: Double, val ciHi: Double)
    data class ModelMeta(
        val trainedAt: String, val nTrain: Int, val baseRate: Double, val kWin: Double, val rLoss: Double,
        val validated: Boolean, val validationRule: String, val bss: Double, val auc: Double, val nOos: Int,
        val holdoutBss: Double, val holdoutAuc: Double, val table: List<CalBin>, val dataStart: String, val dataEnd: String,
    )

    fun calibrated(p: Double): CalBin? = meta.table.firstOrNull { (p >= it.lo && p < it.hi) || (it.hi >= 1.0 && p >= it.lo) }
}

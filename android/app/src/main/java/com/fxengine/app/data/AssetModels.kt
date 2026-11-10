package com.fxengine.app.data

import org.json.JSONArray
import org.json.JSONObject

/** One instrument of the engine's universe (mirrors fxengine/instruments.py). */
data class InstrumentInfo(val symbol: String, val name: String, val group: String)

object Catalog {
    private val MAJORS = listOf("EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "JPY")
    private val MAJOR_PAIRS = setOf("EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD")
    private val CCY_NAME = mapOf(
        "EUR" to "Euro", "GBP" to "Libra", "AUD" to "Dólar australiano", "NZD" to "Dólar neozelandês",
        "USD" to "Dólar americano", "CAD" to "Dólar canadense", "CHF" to "Franco suíço", "JPY" to "Iene",
    )

    val all: List<InstrumentInfo> = buildList {
        for (i in MAJORS.indices) for (j in i + 1 until MAJORS.size) {
            val sym = MAJORS[i] + MAJORS[j]
            add(InstrumentInfo(sym, "${CCY_NAME[MAJORS[i]]} / ${CCY_NAME[MAJORS[j]]}",
                if (sym in MAJOR_PAIRS) "Principais" else "Cruzamentos"))
        }
        add(InstrumentInfo("XAUUSD", "Ouro", "Metais"))
        add(InstrumentInfo("XAGUSD", "Prata", "Metais"))
        add(InstrumentInfo("XPTUSD", "Platina", "Metais"))
        add(InstrumentInfo("XPDUSD", "Paládio", "Metais"))
    }

    val groups = listOf("Principais", "Cruzamentos", "Metais")

    fun name(symbol: String) = all.firstOrNull { it.symbol == symbol }?.name ?: symbol

    /** Settings value for the assets option: "all" | "fx" | "metais" | "EURUSD,XAUUSD,…". */
    fun parseList(v: String): List<String> =
        if (v in setOf("all", "fx", "metais")) emptyList() else v.split(",").map { it.trim() }.filter { it.isNotEmpty() }
}

data class Bars(val t: LongArray, val o: DoubleArray, val h: DoubleArray, val l: DoubleArray, val c: DoubleArray) {
    val size get() = c.size
}

data class MtfRow(
    val tf: String, val trend: Double, val momentum: Double, val score: Double, val rsi: Double, val adx: Double,
    val emas: String, val supertrend: Int, val ichimoku: String, val structure: String, val bos: Int,
    val candles: List<String>, val squeezeOn: Boolean, val squeezeFired: Int, val divergence: String,
)

data class LevelRow(val side: String, val price: String, val value: Double, val strength: Double, val labels: String,
                    val distPips: Double, val distAtr: Double)

data class DailyInfo(
    val adrPips: Double, val todayPips: Double, val adrUsedPct: Double, val moveTodayAdr: Double,
    val dayOpen: String, val prevHigh: String, val prevLow: String, val prevClose: String,
    val weekHigh: String, val weekLow: String, val pivots: List<Pair<String, String>>,
)

data class QuantInfo(val regime: String, val hurst: Double, val vr: Double, val er: Double, val tsmom: Double,
                     val mrZ: Double, val volPct: Double, val volAnn: Double)

data class FundRow(val name: String, val value: Double, val fact: String)
data class AssetEvent(val whenLocal: String, val ccy: String, val title: String, val impact: String,
                      val inText: String, val forecast: String, val previous: String)
data class AssetHeadline(val whenLocal: String, val title: String, val tone: Int)

data class PlanOverlay(val entry: Double, val sl: Double, val tp1: Double, val tp2: Double, val direction: Int,
                       val show: Boolean)

data class AssetResult(
    val symbol: String, val name: String, val isMetal: Boolean, val digits: Int,
    val timestamp: String, val weekday: String,
    val bid: String, val ask: String, val mid: String, val spreadPips: Double, val quoteTime: String,
    val quoteSource: String, val tradeable: Boolean, val session: String, val notes: List<String>,
    val decision: Decision, val opportunity: Opportunity?,
    val mtf: List<MtfRow>, val levels: List<LevelRow>, val daily: DailyInfo?, val quant: QuantInfo?,
    val strength: List<Triple<String, Double, Int?>>,
    val fundScore: Double, val fundComponents: List<FundRow>, val rates: List<Rate>, val cot: List<CotRow>,
    val macro: List<String>, val events: List<AssetEvent>, val headlines: List<AssetHeadline>,
    val breakouts: List<BreakoutItem>, val chartH1: Bars?, val chartM15: Bars?,
    val overlayLevels: List<Double>, val plan: PlanOverlay?, val dataIssues: List<String>, val elapsedS: Double,
)

sealed interface AssetOutput {
    data class Ok(val result: AssetResult, val raw: String) : AssetOutput
    data class Failed(val message: String, val detail: String) : AssetOutput
}

private fun JSONObject.jd(key: String, def: Double = 0.0): Double =
    if (isNull(key)) def else optDouble(key, def).let { if (it.isNaN()) def else it }

private fun JSONObject.js(key: String): String = if (isNull(key)) "" else optString(key, "")

private fun JSONArray?.jstrings(): List<String> = if (this == null) emptyList() else List(length()) { optString(it) }

private inline fun <T> JSONArray?.jobjs(f: (JSONObject) -> T): List<T> =
    if (this == null) emptyList() else List(length()) { f(getJSONObject(it)) }

private fun JSONArray?.doubles(): DoubleArray =
    if (this == null) DoubleArray(0) else DoubleArray(length()) { optDouble(it) }

private fun parseBars(o: JSONObject?): Bars? {
    if (o == null) return null
    val t = o.optJSONArray("t") ?: return null
    return Bars(LongArray(t.length()) { t.optLong(it) }, o.optJSONArray("o").doubles(),
        o.optJSONArray("h").doubles(), o.optJSONArray("l").doubles(), o.optJSONArray("c").doubles())
}

fun parseAsset(raw: String): AssetOutput = try {
    val j = JSONObject(raw)
    if (!j.optBoolean("ok", false)) {
        AssetOutput.Failed(j.optString("error", "Erro desconhecido"), j.optString("detail", ""))
    } else {
        val p = j.getJSONObject("price")
        val dec = j.getJSONObject("decision")
        val dl = j.optJSONObject("daily")
        val q = j.optJSONObject("quant")
        val fund = j.optJSONObject("fundamental")
        val chart = j.optJSONObject("chart")
        val ov = j.optJSONObject("overlay")
        val pl = ov?.optJSONObject("plan")
        AssetOutput.Ok(
            AssetResult(
                symbol = j.js("symbol"), name = j.js("name"), isMetal = j.optBoolean("is_metal"),
                digits = j.optInt("digits", 5), timestamp = j.js("timestamp"), weekday = j.js("weekday"),
                bid = p.js("bid"), ask = p.js("ask"), mid = p.js("mid"), spreadPips = p.jd("spread_pips"),
                quoteTime = p.js("time"), quoteSource = p.js("source"), tradeable = j.optBoolean("tradeable"),
                session = j.js("session"), notes = j.optJSONArray("notes").jstrings(),
                decision = Decision(dec.optBoolean("execute"), dec.js("headline"), dec.js("reason")),
                opportunity = j.optJSONObject("opportunity")?.let(::parseOpp),
                mtf = j.optJSONArray("mtf").jobjs {
                    val sq = it.optJSONObject("squeeze")
                    MtfRow(it.js("tf"), it.jd("trend"), it.jd("momentum"), it.jd("score"), it.jd("rsi"), it.jd("adx"),
                        it.js("emas"), it.optInt("supertrend"), it.js("ichimoku"), it.js("structure"), it.optInt("bos"),
                        it.optJSONArray("candles").jstrings(), sq?.optBoolean("on") ?: false, sq?.optInt("fired") ?: 0,
                        it.js("divergence"))
                },
                levels = j.optJSONArray("levels").jobjs {
                    LevelRow(it.js("side"), it.js("price"), it.jd("value"), it.jd("strength"), it.js("labels"),
                        it.jd("dist_pips"), it.jd("dist_atr"))
                },
                daily = dl?.let {
                    val pv = it.optJSONObject("pivots")
                    DailyInfo(it.jd("adr_pips"), it.jd("today_pips"), it.jd("adr_used_pct"), it.jd("move_today_adr"),
                        it.js("day_open"), it.js("prev_high"), it.js("prev_low"), it.js("prev_close"),
                        it.js("week_high"), it.js("week_low"),
                        listOf("R2", "R1", "P", "S1", "S2").map { k -> k to (pv?.optString(k) ?: "") })
                },
                quant = q?.let {
                    QuantInfo(it.js("regime"), it.jd("hurst"), it.jd("vr"), it.jd("er"), it.jd("tsmom"), it.jd("mr_z"),
                        it.jd("vol_pct"), it.jd("vol_ann"))
                },
                strength = j.optJSONObject("strength")?.let { st ->
                    st.keys().asSequence().map { k ->
                        val o = st.getJSONObject(k)
                        Triple(k, o.jd("z"), if (o.isNull("rank")) null else o.optInt("rank"))
                    }.toList()
                } ?: emptyList(),
                fundScore = fund?.jd("score") ?: 0.0,
                fundComponents = fund?.optJSONArray("components").jobjs { FundRow(it.js("name"), it.jd("value"), it.js("fact")) },
                rates = fund?.optJSONObject("rates")?.let { r ->
                    r.keys().asSequence().map { k -> Rate(k, r.getJSONObject(k).jd("rate"), r.getJSONObject(k).jd("chg6m")) }.toList()
                } ?: emptyList(),
                cot = fund?.optJSONObject("cot")?.let { c ->
                    c.keys().asSequence().map { k -> CotRow(k, c.getJSONObject(k).jd("net_pct"), c.getJSONObject(k).jd("index")) }.toList()
                } ?: emptyList(),
                macro = fund?.optJSONArray("macro").jstrings(),
                events = j.optJSONArray("events").jobjs {
                    AssetEvent(it.js("when"), it.js("ccy"), it.js("title"), it.js("impact"), it.js("in"),
                        it.js("forecast"), it.js("previous"))
                },
                headlines = j.optJSONArray("headlines").jobjs { AssetHeadline(it.js("when"), it.js("title"), it.optInt("tone")) },
                breakouts = j.optJSONArray("breakouts").jobjs(::parseItem),
                chartH1 = parseBars(chart?.optJSONObject("H1")), chartM15 = parseBars(chart?.optJSONObject("M15")),
                overlayLevels = ov?.optJSONArray("levels").let { a -> if (a == null) emptyList() else List(a.length()) { a.optDouble(it) } },
                plan = pl?.let { PlanOverlay(it.jd("entry"), it.jd("sl"), it.jd("tp1"), it.jd("tp2"), it.optInt("direction", 1), it.optBoolean("show")) },
                dataIssues = j.optJSONArray("data_issues").jstrings(), elapsedS = j.jd("elapsed_s"),
            ),
            raw,
        )
    }
} catch (e: Exception) {
    AssetOutput.Failed("Resposta inválida do motor", e.toString())
}

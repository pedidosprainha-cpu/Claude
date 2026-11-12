package com.fxengine.app.data

import org.json.JSONArray
import org.json.JSONObject

/** Mirrors fxengine/app_api.py `result_dict()`. All prices arrive pre-formatted. */
data class ScanResult(
    val timestamp: String,
    val timestampUtc: String,
    val weekday: String,
    val session: String,
    val fxOpen: Boolean,
    val metalsOpen: Boolean,
    val riskValue: Double,
    val riskLabel: String,
    val balance: Double,
    val riskPct: Double,
    val minScore: Double,
    val decision: Decision,
    val best: Opportunity?,
    val top: Opportunity?,
    val ranking: List<Opportunity>,
    val strength: List<Strength>,
    val metals: List<Pair<String, Double>>,
    val macroNotes: List<String>,
    val rates: List<Rate>,
    val ratesSource: String,
    val cot: List<CotRow>,
    val events: List<EventRow>,
    val headlines: List<Pair<String, String>>,
    val dataIssues: List<String>,
    val elapsedS: Double,
    val signalModel: SignalModelInfo? = null,
    val track: TrackInfo? = null,
)

data class Decision(val execute: Boolean, val headline: String, val reason: String)

data class Edge(
    val p: Double, val raw: Double, val n: Int, val expR: Double, val pf: Double?, val avgH: Double,
    val fromModel: Boolean = false, val passes: Boolean = false, val otherExpR: Double? = null,
)

/** Validation of the main-signal model (fxengine/data/signal_model.json), shown as a card. */
data class SignalModelInfo(
    val validated: Boolean, val period: String, val instruments: Int, val bars: Int, val testPeriod: String,
    val filterPct: Int, val geometry: String, val wfMeanR: Double, val wfWorstR: Double, val wfPosShare: Double,
    val testN: Int, val testMeanR: Double, val testWin: Double, val baselineTestMeanR: Double,
    val pMean: Double, val winReal: Double,
    val oldTestMeanR: Double? = null, val oldTestWin: Double? = null,
)

data class Named(val name: String, val value: Double, val note: String = "")

/** Explosion detector reading for the instrument of an opportunity (next hours). */
data class ExplosionBrief(val p: Double, val level: String, val alert: Boolean, val side: String, val pSide: Double,
                          val conf: Boolean, val movePips: Double, val horizon: Int)

data class Opportunity(
    val symbol: String,
    val name: String,
    val isMetal: Boolean,
    val direction: Int,
    val side: String,
    val score: Double,
    val grade: String,
    val executable: Boolean,
    val status: String,
    val gates: List<String>,
    val bid: String,
    val ask: String,
    val spreadPips: Double,
    val quoteTime: String,
    val quoteSource: String,
    val entry: String,
    val sl: String,
    val tp1: String,
    val tp2: String,
    val slPips: Double,
    val tp1Pips: Double,
    val tp2Pips: Double,
    val rr1: Double,
    val rr2: Double,
    val lots: Double,
    val riskAmount: Double,
    val pipValue: Double?,
    val slBasis: String,
    val tp1Basis: String,
    val tp2Basis: String,
    val invalidation: String,
    val edge: Edge?,
    val explosion: ExplosionBrief? = null,
    val exitKind: String = "partial",
    val exitRule: String = "",
    val horizonH: Int = 0,
    val components: List<Named>,
    val multipliers: List<Named>,
    val regime: String,
    val reasons: List<String>,
    val warnings: List<String>,
    val orderText: String,
) {
    val isBuy get() = direction > 0
}

data class Strength(val ccy: String, val z: Double, val h4: Double, val h24: Double, val d5: Double)
data class Rate(val ccy: String, val rate: Double, val chg6m: Double)
data class CotRow(val asset: String, val netPct: Double, val index: Double)
data class EventRow(val whenLocal: String, val ccy: String, val title: String, val inText: String,
                    val forecast: String, val previous: String)

sealed interface EngineOutput {
    data class Ok(val result: ScanResult, val raw: String) : EngineOutput
    data class Failed(val message: String, val detail: String) : EngineOutput
}

// ------------------------------------------------------------------ parsing

private fun JSONObject.d(key: String, def: Double = 0.0): Double =
    if (isNull(key)) def else optDouble(key, def).let { if (it.isNaN()) def else it }

private fun JSONObject.s(key: String): String = if (isNull(key)) "" else optString(key, "")

private fun JSONArray?.strings(): List<String> =
    if (this == null) emptyList() else List(length()) { optString(it) }

private inline fun <T> JSONArray?.objects(f: (JSONObject) -> T): List<T> =
    if (this == null) emptyList() else List(length()) { f(getJSONObject(it)) }

private fun JSONObject.named(): Named = Named(s("name"), d("value"), s("note"))

internal fun parseOpp(o: JSONObject): Opportunity {
    val e = o.optJSONObject("edge")
    return Opportunity(
        symbol = o.s("symbol"), name = o.s("name"), isMetal = o.optBoolean("is_metal"),
        direction = o.optInt("direction", 1), side = o.s("side"), score = o.d("score"),
        grade = o.s("grade"), executable = o.optBoolean("executable"), status = o.s("status"),
        gates = o.optJSONArray("gates").strings(), bid = o.s("bid"), ask = o.s("ask"),
        spreadPips = o.d("spread_pips"), quoteTime = o.s("quote_time"), quoteSource = o.s("quote_source"),
        entry = o.s("entry"), sl = o.s("sl"), tp1 = o.s("tp1"), tp2 = o.s("tp2"),
        slPips = o.d("sl_pips"), tp1Pips = o.d("tp1_pips"), tp2Pips = o.d("tp2_pips"),
        rr1 = o.d("rr1"), rr2 = o.d("rr2"), lots = o.d("lots"), riskAmount = o.d("risk_amount"),
        pipValue = if (o.isNull("pip_value")) null else o.d("pip_value"),
        slBasis = o.s("sl_basis"), tp1Basis = o.s("tp1_basis"), tp2Basis = o.s("tp2_basis"),
        invalidation = o.s("invalidation"),
        edge = e?.let {
            Edge(it.d("p"), it.d("raw"), it.optInt("n"), it.d("exp_r"),
                if (it.isNull("pf")) null else it.d("pf"), it.d("avg_h"),
                fromModel = it.s("source") == "modelo", passes = it.optBoolean("passes"),
                otherExpR = if (it.isNull("other_exp_r") || !it.has("other_exp_r")) null else it.d("other_exp_r"))
        },
        explosion = o.optJSONObject("explosion")?.let {
            ExplosionBrief(it.d("p"), it.s("level"), it.optBoolean("alert"), it.s("side"), it.d("p_side", 0.5),
                it.optBoolean("conf"), it.d("move_pips"), it.optInt("horizon", 4))
        },
        exitKind = o.s("exit_kind").ifBlank { "partial" },
        exitRule = o.s("exit_rule"),
        horizonH = o.optInt("horizon_h", 0),
        components = o.optJSONArray("components").objects { it.named() },
        multipliers = o.optJSONArray("multipliers").objects { it.named() },
        regime = o.s("regime"),
        reasons = o.optJSONArray("reasons").strings(),
        warnings = o.optJSONArray("warnings").strings(),
        orderText = o.s("order_text"),
    )
}

fun parseEngineOutput(raw: String): EngineOutput {
    return try {
        val j = JSONObject(raw)
        if (!j.optBoolean("ok", false)) {
            EngineOutput.Failed(j.optString("error", "Erro desconhecido"), j.optString("detail", ""))
        } else {
            val st = j.getJSONObject("settings")
            val risk = j.getJSONObject("risk")
            val dec = j.getJSONObject("decision")
            EngineOutput.Ok(
                ScanResult(
                    timestamp = j.s("timestamp"), timestampUtc = j.s("timestamp_utc"), weekday = j.s("weekday"),
                    session = j.s("session"), fxOpen = j.optBoolean("fx_open"), metalsOpen = j.optBoolean("metals_open"),
                    riskValue = risk.d("value"), riskLabel = risk.s("label"),
                    balance = st.d("balance"), riskPct = st.d("risk_pct"), minScore = st.d("min_score"),
                    decision = Decision(dec.optBoolean("execute"), dec.s("headline"), dec.s("reason")),
                    best = j.optJSONObject("best")?.let(::parseOpp),
                    top = j.optJSONObject("top")?.let(::parseOpp),
                    ranking = j.optJSONArray("ranking").objects(::parseOpp),
                    strength = j.optJSONArray("strength").objects {
                        Strength(it.s("ccy"), it.d("z"), it.d("h4"), it.d("h24"), it.d("d5"))
                    },
                    metals = j.optJSONArray("metals_z").objects { it.s("code") to it.d("z") },
                    macroNotes = j.optJSONArray("macro_notes").strings(),
                    rates = j.optJSONArray("rates").objects { Rate(it.s("ccy"), it.d("rate"), it.d("chg6m")) },
                    ratesSource = j.s("rates_source"),
                    cot = j.optJSONArray("cot").objects { CotRow(it.s("asset"), it.d("net_pct"), it.d("index")) },
                    events = j.optJSONArray("events").objects {
                        EventRow(it.s("when"), it.s("ccy"), it.s("title"), it.s("in"), it.s("forecast"), it.s("previous"))
                    },
                    headlines = j.optJSONArray("headlines").objects { it.s("when") to it.s("title") },
                    dataIssues = j.optJSONArray("data_issues").strings(),
                    elapsedS = j.d("elapsed_s"),
                    signalModel = parseSignalModel(j.optJSONObject("signal_model")),
                    track = parseTrack(j.optJSONObject("track")),
                ),
                raw,
            )
        }
    } catch (e: Exception) {
        EngineOutput.Failed("Resposta inválida do motor", e.toString())
    }
}

internal fun parseSignalModel(m: JSONObject?): SignalModelInfo? {
    if (m == null || !m.optBoolean("available", false)) return null
    return SignalModelInfo(
        validated = m.optBoolean("validated"), period = m.s("period"), instruments = m.optInt("instruments"),
        bars = m.optInt("bars"), testPeriod = m.s("test_period"), filterPct = m.optInt("filter_pct", 10),
        geometry = m.s("geometry"), wfMeanR = m.d("wf_mean_r"), wfWorstR = m.d("wf_worst_r"),
        wfPosShare = m.d("wf_pos_share"), testN = m.optInt("test_n"), testMeanR = m.d("test_mean_r"),
        testWin = m.d("test_win"), baselineTestMeanR = m.d("baseline_test_mean_r"),
        pMean = m.d("p_mean"), winReal = m.d("win_real"),
        oldTestMeanR = if (m.isNull("old_test_mean_r") || !m.has("old_test_mean_r")) null else m.d("old_test_mean_r"),
        oldTestWin = if (m.isNull("old_test_win") || !m.has("old_test_win")) null else m.d("old_test_win"),
    )
}

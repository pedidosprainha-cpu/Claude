package com.fxengine.app.data

import org.json.JSONArray
import org.json.JSONObject

/** Bracket (OCO) plan: buy stop above and sell stop below, the first to trigger cancels the other. */
data class ExplosionPlan(
    val buyStop: String, val sellStop: String, val buySl: String, val sellSl: String,
    val buyTp: String, val sellTp: String, val riskPips: Double, val lots: Double, val riskAmount: Double,
    val exitRule: String, val stopRule: String, val holdH: Int, val validated: Boolean,
)

data class ExplosionItem(
    val symbol: String, val name: String, val isMetal: Boolean,
    val p: Double, val level: String, val levelLabel: String, val alert: Boolean,
    val pUp: Double?, val side: String?,
    val adrPips: Double, val movePips: Double, val moveAdr: Double,
    val bid: String, val ask: String, val quoteTime: String, val tradeable: Boolean,
    val until: String, val minutesLeft: Int,
    val drivers: List<String>, val events: List<String>, val plan: ExplosionPlan, val orderText: String,
    val rangeLow: String = "", val rangeHigh: String = "",
    val pSide: Double? = null, val dirConfident: Boolean = false, val dirUseful: Boolean = false,
    val dataIssues: List<String> = emptyList(), val blocked: Boolean = false, val ood: List<String> = emptyList(),
)

data class ExplosionModelInfo(
    val validated: Boolean, val period: String, val bars: Int, val instruments: Int, val testPeriod: String,
    val theta: Double, val horizon: Int, val alertPct: Int, val baseRate: Double, val testPrecision: Double,
    val testLift: Double, val testAlerts: Int, val testAuc: Double, val testAucSeasonal: Double,
    val testMoveAlert: Double, val testMoveAll: Double, val wfLiftMin: Double, val wfLiftMean: Double,
    val squeezePrecision: Double, val directionUseful: Boolean, val directionAuc: Double,
    val bracketValidated: Boolean, val bracketWfMeanR: Double?, val bracketTestMeanR: Double?, val bracketTestN: Int,
    val testPrecisionSeasonal: Double = 0.0, val testPrecisionExtreme: Double = 0.0,
    val dirWfAcc: Double = 0.5, val dirWfAccConf: Double = 0.5, val dirWfAccMin: Double = 0.5,
    val dirTestAcc: Double = 0.5, val dirTestAccConf: Double = 0.5,
    val dirTradeWfMeanR: Double? = null, val dirTradeTestMeanR: Double? = null, val dirTradeValidated: Boolean = false,
)

data class ExplosionResult(
    val timestamp: String, val weekday: String, val session: String, val fxOpen: Boolean,
    val scanned: Int, val alerts: Int, val nextUpdate: String, val items: List<ExplosionItem>,
    val model: ExplosionModelInfo?, val dataIssues: List<String>, val elapsedS: Double,
    val track: TrackInfo? = null,
)

sealed interface ExplosionOutput {
    data class Ok(val result: ExplosionResult, val raw: String) : ExplosionOutput
    data class Failed(val message: String, val detail: String) : ExplosionOutput
}

private fun JSONObject.xd(key: String, def: Double = 0.0): Double =
    if (!has(key) || isNull(key)) def else optDouble(key, def).let { if (it.isNaN()) def else it }

private fun JSONObject.xdn(key: String): Double? = if (!has(key) || isNull(key)) null else optDouble(key).takeIf { !it.isNaN() }

private fun JSONObject.xs(key: String): String = if (!has(key) || isNull(key)) "" else optString(key, "")

private fun JSONArray?.xstrings(): List<String> = if (this == null) emptyList() else List(length()) { optString(it) }

private fun parseExplosionItem(o: JSONObject): ExplosionItem {
    val p = o.optJSONObject("plan") ?: JSONObject()
    return ExplosionItem(
        symbol = o.xs("symbol"), name = o.xs("name"), isMetal = o.optBoolean("is_metal"),
        p = o.xd("p"), level = o.xs("level"), levelLabel = o.xs("level_label"), alert = o.optBoolean("alert"),
        pUp = o.xdn("p_up"), side = o.xs("side").ifBlank { null },
        adrPips = o.xd("adr_pips"), movePips = o.xd("move_pips"), moveAdr = o.xd("move_adr"),
        bid = o.xs("bid"), ask = o.xs("ask"), quoteTime = o.xs("quote_time"), tradeable = o.optBoolean("tradeable"),
        until = o.xs("until"), minutesLeft = o.optInt("minutes_left"),
        drivers = o.optJSONArray("drivers").xstrings(), events = o.optJSONArray("events").xstrings(),
        plan = ExplosionPlan(
            p.xs("buy_stop"), p.xs("sell_stop"), p.xs("buy_sl"), p.xs("sell_sl"), p.xs("buy_tp"), p.xs("sell_tp"),
            p.xd("risk_pips"), p.xd("lots"), p.xd("risk_amount"), p.xs("exit_rule"), p.xs("stop_rule"),
            p.optInt("hold_h", 12), p.optBoolean("validated"),
        ),
        orderText = o.xs("order_text"), rangeLow = o.xs("range_low"), rangeHigh = o.xs("range_high"),
        pSide = o.xdn("p_side"), dirConfident = o.optBoolean("dir_confident"), dirUseful = o.optBoolean("dir_useful"),
        dataIssues = o.optJSONArray("data_issues").xstrings(), blocked = o.optBoolean("blocked"),
        ood = o.optJSONArray("ood").xstrings(),
    )
}

private fun parseExplosionModel(m: JSONObject?): ExplosionModelInfo? {
    if (m == null || !m.optBoolean("available")) return null
    val bt = m.optJSONObject("bracket_test") ?: JSONObject()
    return ExplosionModelInfo(
        validated = m.optBoolean("validated"), period = m.xs("period"), bars = m.optInt("bars"),
        instruments = m.optInt("instruments"), testPeriod = m.xs("test_period"), theta = m.xd("theta", 0.5),
        horizon = m.optInt("horizon", 4), alertPct = m.optInt("alert_pct", 5), baseRate = m.xd("base_rate"),
        testPrecision = m.xd("test_precision"), testLift = m.xd("test_lift"), testAlerts = m.optInt("test_n_alert"),
        testAuc = m.xd("test_auc"), testAucSeasonal = m.xd("test_auc_seasonal"),
        testMoveAlert = m.xd("test_move_alert"), testMoveAll = m.xd("test_move_all"),
        wfLiftMin = m.xd("wf_lift_min"), wfLiftMean = m.xd("wf_lift_mean"),
        squeezePrecision = m.xd("wf_squeeze_precision"), directionUseful = m.optBoolean("direction_useful"),
        directionAuc = m.xd("direction_auc", 0.5), bracketValidated = m.optBoolean("bracket_validated"),
        bracketWfMeanR = m.xdn("bracket_wf_mean_r"), bracketTestMeanR = bt.xdn("mean_r"), bracketTestN = bt.optInt("n"),
        testPrecisionSeasonal = m.xd("test_precision_seasonal"), testPrecisionExtreme = m.xd("test_precision_extreme"),
        dirWfAcc = m.xd("direction_wf_acc", 0.5), dirWfAccConf = m.xd("direction_wf_acc_conf", 0.5),
        dirWfAccMin = m.xd("direction_wf_acc_min", 0.5),
        dirTestAcc = (m.optJSONObject("direction_test") ?: JSONObject()).xd("acc_alert", 0.5),
        dirTestAccConf = (m.optJSONObject("direction_test") ?: JSONObject()).xd("acc_conf", 0.5),
        dirTradeWfMeanR = (m.optJSONObject("direction_trade") ?: JSONObject()).xdn("wf_mean_r"),
        dirTradeTestMeanR = ((m.optJSONObject("direction_test") ?: JSONObject()).optJSONObject("trade") ?: JSONObject()).xdn("mean_r"),
        dirTradeValidated = (m.optJSONObject("direction_trade") ?: JSONObject()).optBoolean("validated"),
    )
}

fun parseExplosions(raw: String): ExplosionOutput = try {
    val j = JSONObject(raw)
    if (!j.optBoolean("ok", false)) {
        ExplosionOutput.Failed(j.xs("error").ifBlank { "Falha na análise" }, j.xs("detail"))
    } else {
        val arr = j.optJSONArray("items") ?: JSONArray()
        ExplosionOutput.Ok(
            ExplosionResult(
                timestamp = j.xs("timestamp"), weekday = j.xs("weekday"), session = j.xs("session"),
                fxOpen = j.optBoolean("fx_open"), scanned = j.optInt("scanned"), alerts = j.optInt("alerts"),
                nextUpdate = j.xs("next_update"), items = List(arr.length()) { parseExplosionItem(arr.getJSONObject(it)) },
                model = parseExplosionModel(j.optJSONObject("model")), dataIssues = j.optJSONArray("data_issues").xstrings(),
                elapsedS = j.xd("elapsed_s"), track = parseTrack(j.optJSONObject("track")),
            ),
            raw,
        )
    }
} catch (e: Exception) {
    ExplosionOutput.Failed("Resposta inválida do motor", e.toString())
}

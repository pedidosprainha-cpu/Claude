package com.fxengine.app.data

import org.json.JSONArray
import org.json.JSONObject

/** Mirrors fxengine/app_api.py `breakouts_result_dict()`. */
data class BreakoutResult(
    val timestamp: String,
    val time: String,
    val session: String,
    val fxOpen: Boolean,
    val scanned: Int,
    val newCount: Int,
    val newActionable: Int,
    val items: List<BreakoutItem>,
    val dataIssues: List<String>,
    val elapsedS: Double,
)

data class BreakoutPlanUi(
    val entry: String, val sl: String, val tp1: String, val tp2: String,
    val slPips: Double, val tp1Pips: Double, val tp2Pips: Double,
    val rr1: Double, val rr2: Double, val lots: Double, val riskAmount: Double,
    val slBasis: String, val tp1Basis: String, val tp2Basis: String,
)

data class BreakoutItem(
    val id: String,
    val symbol: String,
    val name: String,
    val tf: String,
    val direction: Int,
    val breakDir: Int,
    val side: String,
    val status: String,
    val statusLabel: String,
    val extended: Boolean,
    val actionable: Boolean,
    val headline: String,
    val level: String,
    val levelLabel: String,
    val bid: String,
    val ask: String,
    val extPips: Double,
    val extAtr: Double,
    val brokeAt: String,
    val firstSeen: String,
    val ageMin: Int,
    val isNew: Boolean,
    val quality: Double,
    val grade: String,
    val pros: List<String>,
    val cons: List<String>,
    val histN: Int,
    val histWins: Int,
    val histP: Double,
    val plan: BreakoutPlanUi,
    val orderText: String,
) {
    val isBuy get() = direction > 0
    val isTrap get() = status == "falso"
}

sealed interface BreakoutOutput {
    data class Ok(val result: BreakoutResult, val raw: String) : BreakoutOutput
    data class Failed(val message: String, val detail: String) : BreakoutOutput
}

private fun JSONObject.d(key: String, def: Double = 0.0): Double =
    if (isNull(key)) def else optDouble(key, def).let { if (it.isNaN()) def else it }

private fun JSONObject.s(key: String): String = if (isNull(key)) "" else optString(key, "")

private fun JSONArray?.strings(): List<String> =
    if (this == null) emptyList() else List(length()) { optString(it) }

private fun parseItem(o: JSONObject): BreakoutItem {
    val p = o.getJSONObject("plan")
    val h = o.optJSONObject("hist")
    return BreakoutItem(
        id = o.s("id"), symbol = o.s("symbol"), name = o.s("name"), tf = o.s("tf"),
        direction = o.optInt("direction", 1), breakDir = o.optInt("break_dir", 1), side = o.s("side"),
        status = o.s("status"), statusLabel = o.s("status_label"), extended = o.optBoolean("extended"),
        actionable = o.optBoolean("actionable"), headline = o.s("headline"), level = o.s("level"),
        levelLabel = o.s("level_label"), bid = o.s("bid"), ask = o.s("ask"),
        extPips = o.d("ext_pips"), extAtr = o.d("ext_atr"), brokeAt = o.s("broke_at"),
        firstSeen = o.s("first_seen"), ageMin = o.optInt("age_min"), isNew = o.optBoolean("is_new"),
        quality = o.d("quality"), grade = o.s("grade"),
        pros = o.optJSONArray("pros").strings(), cons = o.optJSONArray("cons").strings(),
        histN = h?.optInt("n") ?: 0, histWins = h?.optInt("wins") ?: 0, histP = h?.d("p") ?: 0.0,
        plan = BreakoutPlanUi(
            p.s("entry"), p.s("sl"), p.s("tp1"), p.s("tp2"), p.d("sl_pips"), p.d("tp1_pips"), p.d("tp2_pips"),
            p.d("rr1"), p.d("rr2"), p.d("lots"), p.d("risk_amount"), p.s("sl_basis"), p.s("tp1_basis"),
            p.s("tp2_basis"),
        ),
        orderText = o.s("order_text"),
    )
}

fun parseBreakouts(raw: String): BreakoutOutput = try {
    val j = JSONObject(raw)
    if (!j.optBoolean("ok", false)) {
        BreakoutOutput.Failed(j.optString("error", "Erro desconhecido"), j.optString("detail", ""))
    } else {
        val arr = j.optJSONArray("breakouts")
        BreakoutOutput.Ok(
            BreakoutResult(
                timestamp = j.s("timestamp"), time = j.s("time"), session = j.s("session"),
                fxOpen = j.optBoolean("fx_open"), scanned = j.optInt("scanned"),
                newCount = j.optInt("new_count"), newActionable = j.optInt("new_actionable"),
                items = if (arr == null) emptyList() else List(arr.length()) { parseItem(arr.getJSONObject(it)) },
                dataIssues = j.optJSONArray("data_issues").strings(), elapsedS = j.d("elapsed_s"),
            ),
            raw,
        )
    }
} catch (e: Exception) {
    BreakoutOutput.Failed("Resposta inválida do motor", e.toString())
}

private val GRADE_ORDER = listOf("D", "C", "B", "A", "A+")

fun gradeAtLeast(grade: String, min: String): Boolean =
    GRADE_ORDER.indexOf(grade) >= GRADE_ORDER.indexOf(min).coerceAtLeast(0)

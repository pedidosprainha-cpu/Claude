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
    val model: ModelInfo? = null,
    val fills: List<FillEvent> = emptyList(),
    val confirmations: List<ConfirmEvent> = emptyList(),
    val profile: String = "mercado",
)

/** A real-time confirmation plan whose candle closed in favour: enter at market now. */
data class ConfirmEvent(
    val symbol: String, val tf: String, val side: String, val grade: String, val entry: String,
    val sl: String, val slPips: Double, val tp1: String, val trailPips: Double?, val lots: Double,
)

/** Out-of-sample validation of the probability model (from the historical replay). */
data class ModelInfo(
    val events: Int,
    val periodFrom: String,
    val periodTo: String,
    val oldHit: Double,
    val oldR: Double,
    val newHit: Double,
    val newR: Double,
    val stopAtrH1: Double?,
    val label: String = "",          // which timeframe/plan the numbers refer to
    val trades: Int = 0,
    val wfR: Double? = null,         // walk-forward mean R (several periods)
    val validated: Boolean = true,   // false: enabled by user choice, not positive in validation
)

data class BreakoutPlanUi(
    val entry: String, val sl: String, val tp1: String, val tp2: String,
    val slPips: Double, val tp1Pips: Double, val tp2Pips: Double,
    val rr1: Double, val rr2: Double, val lots: Double, val riskAmount: Double,
    val slBasis: String, val tp1Basis: String, val tp2Basis: String,
    val entryType: String = "mercado",     // mercado | limite | confirmacao
    val entryText: String = "",
    val validUntil: String = "",
    val exitKind: String = "tp",           // tp | be | trail
    val exitRule: String = "",
    val trailPips: Double? = null,
) {
    val isLimit get() = entryType == "limite"
}

/** A suggested limit entry that price has reached since the alert. */
data class FillEvent(val symbol: String, val tf: String, val side: String, val grade: String,
                     val limit: String, val sl: String)

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
    val blocked: Boolean,
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
    val confirmState: String = "",   // "" | pendente | confirmado | nao_confirmou
    val quality: Double,
    val grade: String,
    val prob: Double?,          // calibrated P(target 1 before stop)
    val evR: Double?,           // expected R of the plan
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

internal fun parseItem(o: JSONObject): BreakoutItem {
    val p = o.getJSONObject("plan")
    val h = o.optJSONObject("hist")
    return BreakoutItem(
        id = o.s("id"), symbol = o.s("symbol"), name = o.s("name"), tf = o.s("tf"),
        direction = o.optInt("direction", 1), breakDir = o.optInt("break_dir", 1), side = o.s("side"),
        status = o.s("status"), statusLabel = o.s("status_label"), extended = o.optBoolean("extended"),
        actionable = o.optBoolean("actionable"), blocked = o.optBoolean("blocked"),
        headline = o.s("headline"), level = o.s("level"),
        levelLabel = o.s("level_label"), bid = o.s("bid"), ask = o.s("ask"),
        extPips = o.d("ext_pips"), extAtr = o.d("ext_atr"), brokeAt = o.s("broke_at"),
        firstSeen = o.s("first_seen"), ageMin = o.optInt("age_min"), isNew = o.optBoolean("is_new"),
        confirmState = o.s("confirm_state"),
        quality = o.d("quality"), grade = o.s("grade"),
        prob = if (o.isNull("prob")) null else o.d("prob"),
        evR = if (o.isNull("ev_r")) null else o.d("ev_r"),
        pros = o.optJSONArray("pros").strings(), cons = o.optJSONArray("cons").strings(),
        histN = h?.optInt("n") ?: 0, histWins = h?.optInt("wins") ?: 0, histP = h?.d("p") ?: 0.0,
        plan = BreakoutPlanUi(
            p.s("entry"), p.s("sl"), p.s("tp1"), p.s("tp2"), p.d("sl_pips"), p.d("tp1_pips"), p.d("tp2_pips"),
            p.d("rr1"), p.d("rr2"), p.d("lots"), p.d("risk_amount"), p.s("sl_basis"), p.s("tp1_basis"),
            p.s("tp2_basis"),
            entryType = p.s("entry_type").ifBlank { "mercado" }, entryText = p.s("entry_text"),
            validUntil = p.s("valid_until"), exitKind = p.s("exit_kind").ifBlank { "tp" },
            exitRule = p.s("exit_rule"), trailPips = if (p.isNull("trail_pips")) null else p.d("trail_pips"),
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
                model = j.optJSONObject("model")?.let { m -> parseModelInfo(m) },
                profile = j.s("profile").ifBlank { "mercado" },
                confirmations = j.optJSONArray("confirmations").let { arr ->
                    if (arr == null) emptyList() else List(arr.length()) {
                        val c = arr.getJSONObject(it)
                        ConfirmEvent(c.s("symbol"), c.s("tf"), c.s("side"), c.s("grade"), c.s("entry"), c.s("sl"),
                            c.d("sl_pips"), c.s("tp1"), if (c.isNull("trail_pips")) null else c.d("trail_pips"),
                            c.d("lots"))
                    }
                },
                fills = j.optJSONArray("fills").let { arr ->
                    if (arr == null) emptyList() else List(arr.length()) {
                        val f = arr.getJSONObject(it)
                        FillEvent(f.s("symbol"), f.s("tf"), f.s("side"), f.s("grade"), f.s("limit"), f.s("sl"))
                    }
                },
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

private fun parseModelInfo(m: JSONObject): ModelInfo? {
    m.optJSONObject("timeframes")?.let { tfs ->
        val per = m.optJSONArray("period")
        val tf = if (tfs.has("H1")) "H1" else tfs.keys().asSequence().firstOrNull() ?: return null
        val sec = tfs.getJSONObject(tf)
        val test = sec.optJSONObject("test") ?: return null
        val old = test.optJSONObject("referencia_app_1_2") ?: return null
        val new = test.optJSONObject("plano_com_filtro_A") ?: return null
        val wf = sec.optJSONObject("walk_forward")
        return ModelInfo(
            m.optInt("events"), per?.optString(0)?.take(10) ?: "", per?.optString(1)?.take(10) ?: "",
            old.d("acerto"), old.d("r"), new.d("acerto"), new.d("r"), null, tf, new.optInt("n"),
            wfR = wf?.d("media"), validated = sec.optBoolean("validated", true),
        )
    }
    val t = m.optJSONObject("test") ?: return null
    val per = m.optJSONArray("period")
    val from = per?.optString(0)?.take(10) ?: ""
    val to = per?.optString(1)?.take(10) ?: ""
    // version 1: single model
    t.optJSONObject("acionaveis_regra_antiga")?.let { old ->
        val new = t.optJSONObject("acionaveis_modelo_novo") ?: return null
        val geo = m.optJSONObject("geometry")
        return ModelInfo(m.optInt("events"), from, to, old.d("acerto"), old.d("r"), new.d("acerto"), new.d("r"),
            if (geo == null || geo.isNull("stop_atr_h1")) null else geo.d("stop_atr_h1"), "", new.optInt("n"))
    }
    // version 2: one test section per timeframe; show the H1 one (the validated, enabled setup)
    val tf = if (t.has("H1")) "H1" else t.keys().asSequence().firstOrNull() ?: return null
    val sec = t.getJSONObject(tf)
    val old = sec.optJSONObject("referencia_app_1_2") ?: return null
    val new = sec.optJSONObject("plano_com_filtro_A") ?: return null
    return ModelInfo(m.optInt("events"), from, to, old.d("acerto"), old.d("r"), new.d("acerto"), new.d("r"),
        null, tf, new.optInt("n"))
}

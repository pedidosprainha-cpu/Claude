package com.fxintel.app.engine

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** Leitura do modelo exportado pelo treino Python (assets/model.json). */
object ModelIO {
    private fun d(o: JsonObject?, k: String) = (o?.get(k) as? JsonPrimitive)?.doubleOrNull ?: NAN
    private fun arr(o: JsonObject, k: String) = o[k]!!.jsonArray.map { it.jsonPrimitive.doubleOrNull ?: NAN }.toDoubleArray()

    fun parse(text: String): LogisticModel {
        val o = Json.parseToJsonElement(text).jsonObject
        val meta = o["meta"]?.jsonObject
        val oos = meta?.get("oos_metrics") as? JsonObject
        val ho = meta?.get("oos_holdout_metrics") as? JsonObject
        val table = (meta?.get("oos_calibration_table") as? JsonArray)?.map { el ->
            val r = el.jsonObject
            val bin = r["bin"]!!.jsonArray.map { it.jsonPrimitive.doubleOrNull ?: NAN }
            val ci = r["ci90"]!!.jsonArray.map { it.jsonPrimitive.doubleOrNull ?: NAN }
            LogisticModel.CalBin(bin[0], bin[1], r["n"]!!.jsonPrimitive.intOrNull ?: 0, d(r, "mean_p"), d(r, "observed"), ci[0], ci[1])
        } ?: emptyList()
        val m = LogisticModel.ModelMeta(
            trainedAt = (meta?.get("trained_at") as? JsonPrimitive)?.contentOrNull ?: "",
            nTrain = (meta?.get("n_train") as? JsonPrimitive)?.intOrNull ?: 0,
            baseRate = d(meta, "base_rate"), kWin = d(meta, "k_win").let { if (it.isNaN()) 0.75 else it },
            rLoss = d(meta, "r_loss").let { if (it.isNaN()) -1.0 else it },
            validated = (meta?.get("validated") as? JsonPrimitive)?.booleanOrNull ?: false,
            validationRule = (meta?.get("validation_rule") as? JsonPrimitive)?.contentOrNull ?: "",
            bss = d(oos, "bss"), auc = d(oos, "auc"), nOos = (oos?.get("n") as? JsonPrimitive)?.intOrNull ?: 0,
            holdoutBss = d(ho, "bss"), holdoutAuc = d(ho, "auc"), table = table,
            dataStart = (meta?.get("data_start") as? JsonPrimitive)?.contentOrNull ?: "",
            dataEnd = (meta?.get("data_end") as? JsonPrimitive)?.contentOrNull ?: "",
        )
        return LogisticModel(o["features"]!!.jsonArray.map { it.jsonPrimitive.content }, arr(o, "impute_median"),
            arr(o, "scaler_mean"), arr(o, "scaler_scale"), arr(o, "coef"), d(o, "intercept"), m)
    }
}

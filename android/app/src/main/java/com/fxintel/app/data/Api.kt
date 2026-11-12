package com.fxintel.app.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.io.IOException
import java.util.concurrent.TimeUnit

val JsonCfg = Json {
    ignoreUnknownKeys = true
    coerceInputValues = true
    explicitNulls = false
    isLenient = true
}

class ApiException(val code: Int, message: String) : IOException(message)

/** Cliente da API REST/WebSocket do backend FXIntel. */
class FxApi(baseUrl: String, private val apiKey: String) {
    private val base = baseUrl.trim().trimEnd('/')

    val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(150, TimeUnit.SECONDS)  // a análise completa pode levar dezenas de segundos
        .writeTimeout(30, TimeUnit.SECONDS)
        .pingInterval(25, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    val valid: Boolean get() = base.toHttpUrlOrNull() != null

    private fun req(path: String) = Request.Builder().url("$base$path").apply {
        if (apiKey.isNotBlank()) header("X-API-Key", apiKey)  // chave é opcional
    }

    private suspend fun call(r: Request): String = withContext(Dispatchers.IO) {
        client.newCall(r).execute().use { resp ->
            val body = resp.body?.string() ?: ""
            if (!resp.isSuccessful) {
                val detail = runCatching {
                    (JsonCfg.parseToJsonElement(body) as JsonObject)["detail"]?.toString()?.trim('"')
                }.getOrNull()
                throw ApiException(resp.code, detail ?: "HTTP ${resp.code}")
            }
            body
        }
    }

    private suspend inline fun <reified T> get(path: String): T = JsonCfg.decodeFromString(call(req(path).get().build()))

    private val jsonType = "application/json".toMediaType()

    suspend fun health(): Health = JsonCfg.decodeFromString(call(Request.Builder().url("$base/api/v1/health").build()))
    suspend fun quotes(): QuotesResp = get("/api/v1/quotes")
    suspend fun latest(): Analysis = get("/api/v1/analysis/latest")
    suspend fun analysis(id: String): Analysis = get("/api/v1/analyses/$id")
    suspend fun analyses(): List<AnalysisRow> = get("/api/v1/analyses?limit=100")
    suspend fun signals(): SignalsResp = get("/api/v1/signals?limit=200")
    suspend fun alerts(sinceId: Long = 0): List<AlertItem> = get("/api/v1/alerts?since_id=$sinceId&limit=100")
    suspend fun chart(symbol: String, tf: String): ChartResp = get("/api/v1/chart/$symbol?tf=$tf&bars=120")
    suspend fun settings(): JsonObject = get("/api/v1/settings")

    suspend fun analyze(): Analysis =
        JsonCfg.decodeFromString(call(req("/api/v1/analyze").post("".toRequestBody(jsonType)).build()))

    suspend fun putSettings(patch: JsonObject): JsonObject =
        JsonCfg.decodeFromString(call(req("/api/v1/settings").put(patch.toString().toRequestBody(jsonType)).build()))

    suspend fun paperExecute(signalId: String): String {
        val body = buildJsonObject { put("signal_id", signalId) }.toString().toRequestBody(jsonType)
        return call(req("/api/v1/paper/execute").post(body).build())
    }

    fun openSocket(listener: WebSocketListener): WebSocket {
        val wsUrl = base.replaceFirst("https://", "wss://").replaceFirst("http://", "ws://") +
            "/api/v1/ws" + if (apiKey.isNotBlank()) "?api_key=" + java.net.URLEncoder.encode(apiKey, "UTF-8") else ""
        return client.newWebSocket(Request.Builder().url(wsUrl).build(), listener)
    }
}

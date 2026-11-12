package com.fxintel.app.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject

/** Fonte única para a interface: motor no aparelho (padrão) ou servidor próprio (opcional). */
interface Backend {
    val local: Boolean
    suspend fun quotes(): QuotesResp
    suspend fun latest(): Analysis?
    suspend fun analysis(id: String): Analysis?
    suspend fun analyses(): List<AnalysisRow>
    suspend fun signals(): SignalsResp
    suspend fun alerts(sinceId: Long): List<AlertItem>
    suspend fun chart(symbol: String, tf: String): ChartResp
    suspend fun settings(): JsonObject
    suspend fun putSettings(patch: JsonObject): JsonObject
    suspend fun analyze(): Analysis
    suspend fun health(): Health
}

class LocalBackend(private val repo: LocalRepo) : Backend {
    override val local = true
    private suspend fun <T> io(f: () -> T): T = withContext(Dispatchers.IO) { f() }
    override suspend fun quotes() = io { repo.quotes() }
    override suspend fun latest() = io { repo.latest() }
    override suspend fun analysis(id: String) = io { repo.analysis(id) }
    override suspend fun analyses() = io { repo.analyses() }
    override suspend fun signals() = io { repo.signals() }
    override suspend fun alerts(sinceId: Long) = io { repo.alerts(sinceId) }
    override suspend fun chart(symbol: String, tf: String) = io { repo.chart(symbol, tf) }
    override suspend fun settings() = io { repo.settings.toJson() }
    override suspend fun putSettings(patch: JsonObject) = io { repo.saveSettings(patch) }
    override suspend fun analyze() = withContext(Dispatchers.Default) { repo.analyze() }
    override suspend fun health() = io { repo.health() }
}

class ServerBackend(val api: FxApi) : Backend {
    override val local = false
    override suspend fun quotes() = api.quotes()
    override suspend fun latest(): Analysis? = runCatching { api.latest() }.getOrNull()
    override suspend fun analysis(id: String): Analysis? = api.analysis(id)
    override suspend fun analyses() = api.analyses()
    override suspend fun signals() = api.signals()
    override suspend fun alerts(sinceId: Long) = api.alerts(sinceId)
    override suspend fun chart(symbol: String, tf: String) = api.chart(symbol, tf)
    override suspend fun settings() = api.settings()
    override suspend fun putSettings(patch: JsonObject) = api.putSettings(patch)
    override suspend fun analyze() = api.analyze()
    override suspend fun health() = api.health()
}

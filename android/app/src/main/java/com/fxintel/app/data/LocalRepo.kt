package com.fxintel.app.data

import android.content.Context
import com.fxintel.app.engine.BarOps
import com.fxintel.app.engine.CentralBanks
import com.fxintel.app.engine.Engine
import com.fxintel.app.engine.EngineSettings
import com.fxintel.app.engine.Instruments
import com.fxintel.app.engine.LogisticModel
import com.fxintel.app.engine.MarketData
import com.fxintel.app.engine.ModelIO
import com.fxintel.app.engine.OpenExposure
import com.fxintel.app.engine.RiskState
import com.fxintel.app.engine.Time
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import kotlinx.serialization.json.putJsonObject
import java.io.File
import java.time.Instant
import java.time.ZoneOffset
import kotlin.math.abs

/** Configurações do modo autônomo (gravadas no aparelho). */
@Serializable
data class LocalSettings(
    val universe: List<String> = Instruments.ALL.keys.toList(),
    val equity: Double = 10_000.0, val riskPct: Double = 0.5, val maxDailyLossPct: Double = 2.0,
    val maxOpen: Int = 3, val minEv: Double = 0.05, val minRrNet: Double = 1.2, val requireModel: Boolean = true,
) {
    fun engine() = EngineSettings(universe = universe, equity = equity, riskPct = riskPct, maxDailyLossPct = maxDailyLossPct,
        maxOpen = maxOpen, minEv = minEv, minRrNet = minRrNet, requireModel = requireModel)

    fun toJson(): JsonObject = buildJsonObject {
        putJsonArray("universe") { universe.forEach { add(JsonPrimitive(it)) } }
        putJsonObject("account") { put("equity", equity) }
        putJsonObject("risk") { put("risk_per_trade_pct", riskPct); put("max_daily_loss_pct", maxDailyLossPct); put("max_open_positions", maxOpen) }
        putJsonObject("gates") { put("min_ev_r", minEv); put("min_rr_net", minRrNet); put("require_model", requireModel) }
    }

    fun patch(p: JsonObject): LocalSettings {
        fun num(sec: String, k: String) = p[sec]?.jsonObject?.get(k)?.jsonPrimitive?.doubleOrNull
        val rp = num("risk", "risk_per_trade_pct")
        require(rp == null || (rp > 0 && rp <= 2.0)) { "Risco por trade deve estar entre 0 e 2%" }
        val uni = p["universe"]?.jsonArray?.map { it.jsonPrimitive.content }?.filter { Instruments.ALL.containsKey(it) }
        require(uni == null || uni.isNotEmpty()) { "Selecione ao menos um instrumento" }
        return copy(universe = uni ?: universe, equity = num("account", "equity") ?: equity, riskPct = rp ?: riskPct,
            maxDailyLossPct = num("risk", "max_daily_loss_pct") ?: maxDailyLossPct,
            maxOpen = num("risk", "max_open_positions")?.toInt() ?: maxOpen, minEv = num("gates", "min_ev_r") ?: minEv,
            minRrNet = num("gates", "min_rr_net") ?: minRrNet,
            requireModel = p["gates"]?.jsonObject?.get("require_model")?.jsonPrimitive?.booleanOrNull ?: requireModel)
    }
}

@Serializable
data class StoredSignal(val row: SignalRow, val candidate: Candidate, val riskAmount: Double, val spread: Double)

@Serializable
private data class Store(
    val analyses: List<AnalysisRow> = emptyList(), val signals: List<StoredSignal> = emptyList(),
    val alerts: List<AlertItem> = emptyList(), val settings: LocalSettings = LocalSettings(), val nextAlertId: Long = 1,
    val notifiedEvents: List<String> = emptyList(),
)

/**
 * Repositório do MODO AUTÔNOMO: motor, dados e histórico inteiramente no aparelho.
 * Sem servidor e sem chave de API (fontes públicas: Swissquote, TrueFX, Yahoo, gold-api, ForexFactory).
 */
class LocalRepo(private val dir: File, modelJson: String?, cbJson: String) {
    init { dir.mkdirs() }
    val md = MarketData(File(dir, "md"))
    private val model: LogisticModel? = modelJson?.let { runCatching { ModelIO.parse(it) }.getOrNull() }
    private val cb = CentralBanks.parse(cbJson)
    private val engine = Engine(md, model, cb)
    private val file = File(dir, "store.json")
    private val started = System.currentTimeMillis()
    @Volatile private var store: Store = load()
    @Volatile private var quotesAt: String? = null

    private fun load(): Store = runCatching { JsonCfg.decodeFromString<Store>(file.readText()) }.getOrDefault(Store())

    @Synchronized private fun save(s: Store) {
        store = s
        val tmp = File(file.path + ".tmp"); tmp.writeText(JsonCfg.encodeToString(Store.serializer(), s)); tmp.renameTo(file)
    }

    private fun analysisFile(id: String) = File(dir, "analysis_$id.json")
    private fun nowIso() = Instant.now().toString()

    val settings: LocalSettings get() = store.settings
    fun saveSettings(patch: JsonObject): JsonObject { save(store.copy(settings = store.settings.patch(patch))); return store.settings.toJson() }

    @Synchronized fun addAlert(kind: String, severity: String, message: String, symbol: String? = null): AlertItem {
        val a = AlertItem(store.nextAlertId, nowIso(), kind, severity, symbol, message)
        save(store.copy(alerts = (listOf(a) + store.alerts).take(300), nextAlertId = store.nextAlertId + 1))
        return a
    }

    // ------------------------------------------------------------------ API equivalente à do servidor
    fun quotes(): QuotesResp {
        val qs = md.quotes(store.settings.universe)
        val now = System.currentTimeMillis() / 1000.0
        quotesAt = nowIso()
        return QuotesResp(quotesAt, Time.marketOpen(now.toLong()), qs.mapValues { (s, q) ->
            val pip = Instruments.get(s).pip
            Quote(s, q.bid, q.ask, q.mid, Math.round(q.spread / pip * 100) / 100.0, q.spreadSource,
                Instant.ofEpochMilli((q.time * 1000).toLong()).toString(), q.source, Math.round(q.ageS(now) * 10) / 10.0,
                q.prevClose?.let { (q.mid / it - 1) * 100 })
        })
    }

    fun analyze(): Analysis {
        val st = store.settings
        val active = store.signals.filter { it.row.status in setOf("ativo", "tp1") }
        val dayStart = Instant.now().atZone(ZoneOffset.UTC).toLocalDate().atStartOfDay(ZoneOffset.UTC).toInstant().toString()
        val weekStart = Instant.now().atZone(ZoneOffset.UTC).toLocalDate().let { it.minusDays(it.dayOfWeek.value - 1L) }
            .atStartOfDay(ZoneOffset.UTC).toInstant().toString()
        fun pnlSince(iso: String) = store.signals.filter { it.row.outcome_r != null && (it.row.created_at >= iso) }
            .sumOf { (it.row.outcome_r ?: 0.0) * it.riskAmount }
        val rs = RiskState(active.map { OpenExposure(it.row.symbol, if (it.row.direction == "BUY") 1 else -1, it.riskAmount) },
            pnlSince(dayStart), pnlSince(weekStart))
        val a = engine.analyze(st.engine(), rs)
        analysisFile(a.id).writeText(JsonCfg.encodeToString(Analysis.serializer(), a))
        val row = AnalysisRow(a.id, a.created_at, a.status, a.signal?.instrument, a.signal?.direction, a.signal?.score, a.elapsed_ms)
        var s = store.copy(analyses = (listOf(row) + store.analyses).take(200))
        // limpa análises antigas
        store.analyses.drop(60).forEach { analysisFile(it.id).delete() }
        a.signal?.let { sig ->
            val sr = SignalRow(sig.id ?: a.id, a.created_at, sig.instrument, sig.direction, sig.entry.price, sig.stop_loss.price,
                sig.take_profit[0].price, sig.take_profit.getOrNull(1)?.price, sig.validity.valid_until, "ativo", null)
            s = s.copy(signals = (listOf(StoredSignal(sr, sig, sig.risk?.sizing?.risk_amount ?: st.equity * st.riskPct / 100,
                abs(sig.reference_quote.ask - sig.reference_quote.bid))) + s.signals).take(500))
        }
        save(s)
        a.signal?.let { addAlert("novo_sinal", "info", a.headline, it.instrument) }
        return a
    }

    fun latest(): Analysis? = store.analyses.firstOrNull()?.let { analysis(it.id) }
    fun analysis(id: String): Analysis? = runCatching { JsonCfg.decodeFromString<Analysis>(analysisFile(id).readText()) }.getOrNull()
    fun analyses(): List<AnalysisRow> = store.analyses

    fun signals(): SignalsResp {
        val rows = store.signals.map { it.row }
        val closed = rows.filter { it.outcome_r != null }
        return SignalsResp(SignalStats(rows.size, rows.count { it.status in setOf("ativo", "tp1") }, closed.size,
            if (closed.isEmpty()) null else closed.mapNotNull { it.outcome_r }.average()), rows)
    }

    fun alerts(sinceId: Long = 0): List<AlertItem> = store.alerts.filter { it.id > sinceId }

    fun chart(symbol: String, tf: String): ChartResp {
        val inst = Instruments.get(symbol)
        var b = when (tf) { "H4", "D1" -> BarOps.derive(md.bars(symbol, "H1"), tf); else -> md.bars(symbol, tf) }
        if (inst.kind == "metal") (md.lastQuotes[symbol]?.mid ?: runCatching { md.quotes(listOf(symbol))[symbol]?.mid }.getOrNull())
            ?.let { b = BarOps.spotAdjust(symbol, b, it) }
        b = b.tail(120)
        return ChartResp(symbol, tf, inst.digits, (0 until b.n).map { Bar(b.t[it], b.o[it], b.h[it], b.l[it], b.c[it]) })
    }

    fun health(): Health {
        val ms = engine.modelStatus()
        val prov = md.health.values.map { ProviderHealth(it.name, it.ok, it.lastLatencyMs, it.requests, it.failures, it.lastError) }
        return Health(if (prov.all { it.ok }) "ok" else "degradado", "1.1.0 (autônomo)", (System.currentTimeMillis() - started) / 1000.0,
            Time.marketOpen(System.currentTimeMillis() / 1000), quotesAt, true, prov.filter { !it.ok }.map { it.name },
            Providers(prov, false), HealthModel(ms.available, ms.validated, ms.age_hours))
    }

    // ------------------------------------------------------------------ acompanhamento dos sinais + alertas
    /** Mesma lógica do monitor do servidor: TP1 parcial, stop no preço de entrada, TP2, horizonte de 36h. */
    fun trackSignals(): List<AlertItem> {
        val out = ArrayList<AlertItem>()
        val horizon = 36 * 3600L
        val updated = store.signals.map { ss ->
            val s = ss.row
            if (s.status !in setOf("ativo", "tp1")) return@map ss
            val created = Instant.parse(s.created_at).epochSecond
            val d = if (s.direction == "BUY") 1 else -1
            var m5 = runCatching { md.bars(s.symbol, "M5") }.getOrNull() ?: return@map ss
            if (Instruments.get(s.symbol).kind == "metal") md.lastQuotes[s.symbol]?.let { m5 = BarOps.spotAdjust(s.symbol, m5, it.mid) }
            val entry = s.entry ?: return@map ss; val sl = s.sl ?: return@map ss; val tp1 = s.tp1 ?: return@map ss; val tp2 = s.tp2 ?: tp1
            val risk = abs(entry - sl).takeIf { it > 0 } ?: 1e-12
            val half = ss.spread / 2
            var phase = if (s.status == "tp1") 2 else 1
            var status: String? = null; var r: Double? = null
            for (i in 0 until m5.n) {
                if (m5.t[i] < BarOps.floorTo(created, 300)) continue
                val lo = if (d == 1) m5.l[i] - half else m5.l[i] + half
                val hi = if (d == 1) m5.h[i] - half else m5.h[i] + half
                val stop = if (phase == 2) entry else sl
                val stopHit = if (d == 1) lo <= stop else hi >= stop
                val tgt = if (phase == 1) tp1 else tp2
                val tgtHit = if (d == 1) hi >= tgt else lo <= tgt
                if (stopHit) { if (phase == 1) { status = "stop"; r = -1.0 } else { status = "breakeven"; r = 0.5 * abs(tp1 - entry) / risk }; break }
                if (tgtHit) { if (phase == 1) { phase = 2; continue }; status = "tp2"; r = 0.5 * abs(tp1 - entry) / risk + 0.5 * abs(tp2 - entry) / risk; break }
            }
            if (status == null && System.currentTimeMillis() / 1000 - created > horizon) {
                val last = if (m5.n > 0) m5.c[m5.n - 1] else entry
                val mtm = d * (last - entry) / risk
                status = "encerrado_horizonte"; r = if (phase == 2) 0.5 * abs(tp1 - entry) / risk + 0.5 * mtm else mtm
            }
            if (status == null && phase == 2 && s.status != "tp1") status = "tp1"
            if (status != null && status != s.status) {
                val msg = mapOf("tp1" to "atingiu TP1 (50% realizado, stop no preço de entrada)", "tp2" to "atingiu TP2",
                    "stop" to "foi stopado", "breakeven" to "encerrado no preço de entrada após TP1",
                    "encerrado_horizonte" to "encerrado por horizonte máximo")[status]
                out.add(AlertItem(0, nowIso(), "sinal_status", if (status in setOf("tp1", "tp2", "breakeven")) "info" else "warning",
                    s.symbol, "Sinal ${s.direction} ${s.symbol} $msg"))
                ss.copy(row = s.copy(status = status, outcome_r = if (status == "tp1") null else r?.let { Math.round(it * 1000) / 1000.0 }))
            } else ss
        }
        save(store.copy(signals = updated))
        return out.map { addAlert(it.kind, it.severity, it.message, it.symbol) }
    }

    fun eventAlerts(leadMin: Int = 30): List<AlertItem> {
        val evs = runCatching { md.calendar() }.getOrNull() ?: return emptyList()
        val now = System.currentTimeMillis() / 1000
        val curs = store.settings.universe.flatMap { com.fxintel.app.engine.Events.relevant(Instruments.get(it)) }.toSet()
        val out = ArrayList<AlertItem>()
        var notified = store.notifiedEvents
        for (e in evs) {
            val mins = (e.time - now) / 60.0
            val key = "${e.currency}|${e.title}|${e.time}"
            if (e.critical && e.currency in curs && mins in 0.0..leadMin.toDouble() && key !in notified) {
                notified = (notified + key).takeLast(200)
                save(store.copy(notifiedEvents = notified))
                out.add(addAlert("evento", "warning", "Em ${mins.toInt()} min: ${e.currency} ${e.title} (impacto ${e.impact}). Sinais nos ativos afetados ficam bloqueados."))
            }
        }
        return out
    }

    companion object {
        @Volatile private var inst: LocalRepo? = null
        fun get(ctx: Context): LocalRepo = inst ?: synchronized(this) {
            inst ?: LocalRepo(File(ctx.applicationContext.filesDir, "fxintel"),
                runCatching { ctx.assets.open("model.json").bufferedReader().readText() }.getOrNull(),
                ctx.assets.open("central_banks.json").bufferedReader().readText()).also { inst = it }
        }
    }
}

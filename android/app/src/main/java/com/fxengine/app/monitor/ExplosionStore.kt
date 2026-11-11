package com.fxengine.app.monitor

import android.content.Context
import com.fxengine.app.data.ExplosionItem
import com.fxengine.app.data.ExplosionOutput
import com.fxengine.app.data.ExplosionResult
import com.fxengine.app.data.Prefs
import com.fxengine.app.data.parseExplosions
import com.fxengine.app.engine.EngineRunner
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.withContext
import java.util.Calendar

data class ExplosionState(
    val result: ExplosionResult? = null,
    val resultAtMillis: Long = 0L,
    val scanning: Boolean = false,
    val progress: Int = 0,
    val step: String = "",
    val error: String? = null,
)

/** Last explosion scan, shared by the Explosões tab and the monitor service. */
object ExplosionStore {
    private val _state = MutableStateFlow(ExplosionState())
    val state: StateFlow<ExplosionState> = _state.asStateFlow()
    private val lock = Mutex()
    private val notified = mutableSetOf<String>()
    @Volatile private var loaded = false
    @Volatile private var lastHourKey = -1L

    fun restore(context: Context) {
        if (loaded) return
        loaded = true
        val saved = Prefs(context).loadExplosions() ?: return
        (parseExplosions(saved.first) as? ExplosionOutput.Ok)?.let { ok ->
            _state.update { if (it.result == null) it.copy(result = ok.result, resultAtMillis = saved.second) else it }
        }
    }

    suspend fun scanOnce(context: Context): ExplosionResult? {
        if (!lock.tryLock()) return null
        try {
            val app = context.applicationContext
            val prefs = Prefs(app)
            _state.update { it.copy(scanning = true, progress = 0, step = "Iniciando o motor", error = null) }
            val raw = withContext(Dispatchers.Default) {
                runCatching {
                    EngineRunner(app).scanExplosions(prefs.load()) { pct, msg ->
                        _state.update { s -> s.copy(progress = maxOf(s.progress, pct), step = msg) }
                    }
                }.getOrElse { e -> """{"ok": false, "error": ${org.json.JSONObject.quote(e.message ?: e.toString())}}""" }
            }
            return when (val out = parseExplosions(raw)) {
                is ExplosionOutput.Ok -> {
                    prefs.saveExplosions(out.raw)
                    _state.update {
                        it.copy(scanning = false, progress = 100, result = out.result,
                            resultAtMillis = System.currentTimeMillis())
                    }
                    out.result
                }
                is ExplosionOutput.Failed -> {
                    _state.update { it.copy(scanning = false, error = out.message) }
                    null
                }
            }
        } finally {
            lock.unlock()
        }
    }

    /**
     * Monitor hook: the model reads closed H1 bars, so a new reading exists once per hour.
     * Runs at most one scan per hour (from minute 2, when the closed bar is published) and
     * returns the alerts not notified before.
     */
    suspend fun hourlyAlerts(context: Context): List<ExplosionItem> {
        val cal = Calendar.getInstance()
        if (cal.get(Calendar.MINUTE) < 2) return emptyList()
        val key = System.currentTimeMillis() / 3_600_000L
        if (key == lastHourKey) return emptyList()
        val res = scanOnce(context) ?: return emptyList()
        lastHourKey = key
        val fresh = res.items.filter { it.alert && it.level in setOf("alta", "extrema") && it.tradeable }
            .filter { notified.add("${it.symbol}|${it.until}") }
        if (notified.size > 500) notified.clear()
        return fresh
    }
}

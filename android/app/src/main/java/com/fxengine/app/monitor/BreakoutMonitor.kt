package com.fxengine.app.monitor

import android.content.Context
import com.fxengine.app.data.BreakoutOutput
import com.fxengine.app.data.BreakoutResult
import com.fxengine.app.data.Prefs
import com.fxengine.app.data.parseBreakouts
import com.fxengine.app.engine.EngineRunner
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.withContext
import org.json.JSONObject

data class MonitorState(
    val active: Boolean = false,      // background monitor service running
    val scanning: Boolean = false,
    val progress: Int = 0,
    val step: String = "",
    val result: BreakoutResult? = null,
    val resultAtMillis: Long = 0L,
    val nextAtMillis: Long = 0L,
    val error: String? = null,
    val cycles: Int = 0,
)

/**
 * Process-wide breakout state shared by the screen and the monitor service.
 * Only one scan runs at a time; a request while scanning is ignored.
 */
object BreakoutMonitor {
    private val _state = MutableStateFlow(MonitorState())
    val state: StateFlow<MonitorState> = _state.asStateFlow()
    private val lock = Mutex()
    @Volatile private var loaded = false

    /** Restores the last saved scan so the screen is never empty after a restart. */
    fun restore(context: Context) {
        if (loaded) return
        loaded = true
        val saved = Prefs(context).loadBreakouts() ?: return
        (parseBreakouts(saved.first) as? BreakoutOutput.Ok)?.let { ok ->
            _state.update { if (it.result == null) it.copy(result = ok.result, resultAtMillis = saved.second) else it }
        }
    }

    fun setActive(active: Boolean) = _state.update { it.copy(active = active, nextAtMillis = if (active) it.nextAtMillis else 0L) }

    fun setNext(at: Long) = _state.update { it.copy(nextAtMillis = at) }

    /** Runs one light scan; returns the result, or null if another scan is running or it failed. */
    suspend fun scanOnce(context: Context): BreakoutResult? {
        if (!lock.tryLock()) return null
        try {
            val app = context.applicationContext
            val prefs = Prefs(app)
            _state.update { it.copy(scanning = true, progress = 0, step = "Iniciando o motor", error = null) }
            val raw = withContext(Dispatchers.Default) {
                runCatching {
                    EngineRunner(app).scanBreakouts(prefs.load()) { pct, msg ->
                        _state.update { s -> s.copy(progress = maxOf(s.progress, pct), step = msg) }
                    }
                }.getOrElse { e -> """{"ok": false, "error": ${JSONObject.quote(e.message ?: e.toString())}}""" }
            }
            return when (val out = parseBreakouts(raw)) {
                is BreakoutOutput.Ok -> {
                    prefs.saveBreakouts(out.raw)
                    _state.update {
                        it.copy(scanning = false, progress = 100, result = out.result,
                            resultAtMillis = System.currentTimeMillis(), cycles = it.cycles + 1)
                    }
                    out.result
                }
                is BreakoutOutput.Failed -> {
                    _state.update { it.copy(scanning = false, error = out.message) }
                    null
                }
            }
        } finally {
            lock.unlock()
        }
    }
}

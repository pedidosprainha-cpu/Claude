package com.fxengine.app.ui

import android.app.Application
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.fxengine.app.data.AppSettings
import com.fxengine.app.data.EngineOutput
import com.fxengine.app.data.Prefs
import com.fxengine.app.data.ScanResult
import com.fxengine.app.data.parseEngineOutput
import com.fxengine.app.engine.EngineRunner
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class UiState(
    val running: Boolean = false,
    val progress: Int = 0,
    val step: String = "",
    val result: ScanResult? = null,
    val resultAtMillis: Long = 0L,
    val error: String? = null,
    val errorDetail: String = "",
    val settings: AppSettings = AppSettings(),
    val engineReady: Boolean = false,
    val showDisclaimer: Boolean = false,
    val justFinished: Long = 0L,
)

class MainViewModel(app: Application) : AndroidViewModel(app) {
    private val prefs = Prefs(app)
    private val runner = EngineRunner(app)
    private val _state = MutableStateFlow(UiState(settings = prefs.load(), showDisclaimer = !prefs.disclaimerAccepted))
    val state: StateFlow<UiState> = _state.asStateFlow()

    init {
        prefs.loadLast()?.let { raw ->
            (parseEngineOutput(raw) as? EngineOutput.Ok)?.let { ok ->
                _state.update { it.copy(result = ok.result, resultAtMillis = lastResultTime()) }
            }
        }
        viewModelScope.launch(Dispatchers.Default) {
            runCatching { runner.warmUp() }
            _state.update { it.copy(engineReady = true) }
        }
    }

    private fun lastResultTime(): Long =
        getApplication<Application>().filesDir.resolve("ultima_analise.json").lastModified()

    fun acceptDisclaimer() {
        prefs.disclaimerAccepted = true
        _state.update { it.copy(showDisclaimer = false) }
    }

    fun updateSettings(s: AppSettings) {
        prefs.save(s)
        _state.update { it.copy(settings = s) }
    }

    private fun online(): Boolean {
        val cm = getApplication<Application>().getSystemService(ConnectivityManager::class.java) ?: return true
        val caps = cm.getNetworkCapabilities(cm.activeNetwork) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    fun analyze() {
        if (_state.value.running) return
        if (!online()) {
            _state.update { it.copy(error = "Sem conexão com a internet", errorDetail = "Conecte-se e toque em Analisar de novo.") }
            return
        }
        _state.update { it.copy(running = true, progress = 0, step = "Iniciando o motor", error = null, errorDetail = "") }
        viewModelScope.launch {
            val raw = withContext(Dispatchers.Default) {
                runCatching {
                    runner.run(_state.value.settings) { pct, msg ->
                        _state.update { s -> s.copy(progress = maxOf(s.progress, pct), step = msg) }
                    }
                }.getOrElse { e -> """{"ok": false, "error": ${org.json.JSONObject.quote(e.message ?: e.toString())}}""" }
            }
            when (val out = parseEngineOutput(raw)) {
                is EngineOutput.Ok -> {
                    prefs.saveLast(out.raw)
                    _state.update {
                        it.copy(running = false, progress = 100, result = out.result,
                            resultAtMillis = System.currentTimeMillis(), justFinished = System.currentTimeMillis())
                    }
                }
                is EngineOutput.Failed -> _state.update {
                    it.copy(running = false, error = out.message, errorDetail = out.detail)
                }
            }
        }
    }

    fun dismissError() = _state.update { it.copy(error = null, errorDetail = "") }
}

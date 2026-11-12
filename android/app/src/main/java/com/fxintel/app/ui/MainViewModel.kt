package com.fxintel.app.ui

import android.app.Application
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.fxintel.app.data.AlertItem
import com.fxintel.app.data.Analysis
import com.fxintel.app.data.AnalysisRow
import com.fxintel.app.data.ApiException
import com.fxintel.app.data.AppPrefs
import com.fxintel.app.data.Backend
import com.fxintel.app.data.Candidate
import com.fxintel.app.data.ChartResp
import com.fxintel.app.data.FxApi
import com.fxintel.app.data.Health
import com.fxintel.app.data.JsonCfg
import com.fxintel.app.data.LocalBackend
import com.fxintel.app.data.LocalRepo
import com.fxintel.app.data.Prefs
import com.fxintel.app.data.Quote
import com.fxintel.app.data.ServerBackend
import com.fxintel.app.data.SignalsResp
import com.fxintel.app.data.WsMessage
import com.fxintel.app.work.notifyAlert
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.decodeFromJsonElement
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

enum class Link { OFFLINE, CONNECTING, POLLING, LIVE }

data class UiState(
    val prefs: AppPrefs = AppPrefs(),
    val configured: Boolean = true,
    val localMode: Boolean = true,
    val networkOnline: Boolean = true,
    val link: Link = Link.CONNECTING,
    val serverOk: Boolean? = null,
    val quotes: Map<String, Quote> = emptyMap(),
    val quotesAt: String? = null,
    val analysis: Analysis? = null,
    val analyzing: Boolean = false,
    val analyzeMs: Long? = null,
    val error: String? = null,
    val selected: Candidate? = null,
    val chartSymbol: String = "XAUUSD",
    val chartTf: String = "H1",
    val chart: ChartResp? = null,
    val signals: SignalsResp? = null,
    val analyses: List<AnalysisRow> = emptyList(),
    val alerts: List<AlertItem> = emptyList(),
    val unread: Int = 0,
    val health: Health? = null,
    val settings: JsonObject? = null,
    val toast: String? = null,
)

class MainViewModel(app: Application) : AndroidViewModel(app) {
    private val prefs = Prefs(app)
    private val _ui = MutableStateFlow(UiState())
    val ui: StateFlow<UiState> = _ui
    private var backend: Backend? = null
    private var api: FxApi? = null
    private var ws: WebSocket? = null
    private var wsJob: Job? = null
    private var pollJob: Job? = null
    private var wsGen = 0
    private var foreground = true
    private var firstPrefs = true

    init {
        viewModelScope.launch {
            prefs.flow.collect { p ->
                val old = _ui.value.prefs
                val changed = firstPrefs || p.mode != old.mode || p.serverUrl != old.serverUrl || p.apiKey != old.apiKey
                firstPrefs = false
                val local = p.mode != "server"
                _ui.update { it.copy(prefs = p, localMode = local, configured = local || p.serverUrl.isNotBlank()) }
                if (changed) connect()
            }
        }
        watchNetwork()
    }

    private fun watchNetwork() {
        val cm = getApplication<Application>().getSystemService(ConnectivityManager::class.java)
        val online = cm.getNetworkCapabilities(cm.activeNetwork)?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) == true
        _ui.update { it.copy(networkOnline = online) }
        cm.registerDefaultNetworkCallback(object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                _ui.update { it.copy(networkOnline = true) }
                if (!_ui.value.localMode && ws == null) connect()
            }
            override fun onLost(network: Network) { _ui.update { it.copy(networkOnline = false, link = Link.OFFLINE) } }
        })
    }

    private fun connect() {
        val p = _ui.value.prefs
        wsGen++
        ws?.cancel(); ws = null
        wsJob?.cancel(); pollJob?.cancel()
        _ui.update { it.copy(analysis = null, selected = null, chart = null, quotes = emptyMap(), health = null, settings = null) }
        if (p.mode == "server") {
            if (p.serverUrl.isBlank()) { backend = null; return }
            val a = FxApi(p.serverUrl, p.apiKey)
            if (!a.valid) { _ui.update { it.copy(error = "URL do servidor inválida") }; backend = null; return }
            api = a; backend = ServerBackend(a)
            openWs()
        } else {
            api = null; backend = LocalBackend(LocalRepo.get(getApplication()))
        }
        viewModelScope.launch { refreshQuotes(); loadLatest(); refreshHealth() }
        pollJob = viewModelScope.launch {
            var n = 0
            while (isActive) {
                delay(10_000)
                n++
                if (foreground && (_ui.value.localMode || _ui.value.link != Link.LIVE)) refreshQuotes()
                if (n % 3 == 0) refreshHealth()
            }
        }
    }

    private fun openWs(attempt: Int = 0) {
        val a = api ?: return
        val gen = ++wsGen
        _ui.update { it.copy(link = if (it.networkOnline) Link.CONNECTING else Link.OFFLINE) }
        ws = a.openSocket(object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) { _ui.update { it.copy(link = Link.LIVE) } }
            override fun onMessage(webSocket: WebSocket, text: String) {
                val m = runCatching { JsonCfg.decodeFromString<WsMessage>(text) }.getOrNull() ?: return
                when (m.type) {
                    "hello" -> m.quotes?.let { q -> _ui.update { it.copy(quotes = q, quotesAt = m.at) } }
                    "quotes" -> m.data?.let { d ->
                        runCatching { JsonCfg.decodeFromJsonElement<Map<String, Quote>>(d) }.getOrNull()
                            ?.let { q -> _ui.update { it.copy(quotes = q, quotesAt = m.at) } }
                    }
                    "alert" -> m.data?.let { d ->
                        val al = runCatching { JsonCfg.decodeFromJsonElement<AlertItem>(d) }.getOrNull() ?: return
                        onAlert(al)
                    }
                }
            }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) = retry()
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) = retry()
            private fun retry() {
                if (ws == null || gen != wsGen) return
                _ui.update { it.copy(link = if (it.networkOnline) Link.POLLING else Link.OFFLINE) }
                wsJob?.cancel()
                wsJob = viewModelScope.launch {
                    delay(minOf(30_000L, 1000L shl minOf(attempt, 5)))
                    if (api != null && gen == wsGen) openWs(attempt + 1)
                }
            }
        })
    }

    private fun onAlert(al: AlertItem) {
        _ui.update { it.copy(alerts = listOf(al) + it.alerts, unread = it.unread + 1) }
        if (_ui.value.prefs.notifications) notifyAlert(getApplication(), al)
        viewModelScope.launch { prefs.setLastAlertId(maxOf(al.id, _ui.value.prefs.lastAlertId)) }
    }

    private fun msg(e: Throwable): String = when (e) {
        is ApiException -> if (e.code == 401) "O servidor exige chave de API (FXI_REQUIRE_API_KEY=1)" else (e.message ?: "Erro ${e.code}")
        is IllegalArgumentException -> e.message ?: "Valor inválido"
        else -> if (_ui.value.localMode) "Falha ao obter dados de mercado (${e.message ?: e.javaClass.simpleName})"
        else "Sem conexão com o servidor (${e.javaClass.simpleName})"
    }

    fun refreshQuotes() = viewModelScope.launch {
        val b = backend ?: return@launch
        runCatching { b.quotes() }
            .onSuccess { q -> _ui.update { it.copy(quotes = q.data, quotesAt = q.at, serverOk = true, link = if (b.local) Link.LIVE else it.link) } }
            .onFailure { e -> _ui.update { it.copy(serverOk = false, error = msg(e), link = if (b.local) Link.POLLING else it.link) } }
    }

    fun refreshHealth() = viewModelScope.launch {
        val b = backend ?: return@launch
        runCatching { b.health() }.onSuccess { h -> _ui.update { it.copy(health = h, serverOk = true) } }
            .onFailure { _ui.update { s -> s.copy(serverOk = false) } }
    }

    private fun loadLatest() = viewModelScope.launch {
        val b = backend ?: return@launch
        runCatching { b.latest() }.getOrNull()?.let { setAnalysis(it) } ?: loadChart()
    }

    private fun setAnalysis(r: Analysis) {
        val sel = r.signal ?: r.ranking.firstOrNull() ?: r.observations.firstOrNull()
        _ui.update { it.copy(analysis = r, selected = sel, chartSymbol = sel?.instrument ?: it.chartSymbol) }
        loadChart()
    }

    fun analyze() {
        val b = backend ?: run { _ui.update { it.copy(error = "Configure a fonte de dados em Ajustes") }; return }
        if (_ui.value.analyzing) return
        _ui.update { it.copy(analyzing = true, error = null) }
        viewModelScope.launch {
            val t0 = System.currentTimeMillis()
            runCatching { b.analyze() }
                .onSuccess { r ->
                    setAnalysis(r); _ui.update { it.copy(analyzeMs = System.currentTimeMillis() - t0) }
                    if (b.local && r.signal != null) runCatching { b.alerts(_ui.value.prefs.lastAlertId) }.getOrNull()?.forEach { onAlert(it) }
                }
                .onFailure { e -> _ui.update { it.copy(error = msg(e)) } }
            _ui.update { it.copy(analyzing = false) }
        }
    }

    fun select(c: Candidate?) { _ui.update { it.copy(selected = c, chartSymbol = c?.instrument ?: it.chartSymbol) }; loadChart() }
    fun chartSymbol(s: String) { _ui.update { it.copy(chartSymbol = s, selected = it.selected?.takeIf { c -> c.instrument == s }) }; loadChart() }
    fun chartTf(tf: String) { _ui.update { it.copy(chartTf = tf) }; loadChart() }

    fun loadChart() = viewModelScope.launch {
        val b = backend ?: return@launch
        val s = _ui.value
        runCatching { b.chart(s.chartSymbol, s.chartTf) }.onSuccess { c -> _ui.update { it.copy(chart = c) } }
    }

    fun loadHistory() = viewModelScope.launch {
        val b = backend ?: return@launch
        runCatching { b.signals() }.onSuccess { s -> _ui.update { it.copy(signals = s) } }
        runCatching { b.analyses() }.onSuccess { s -> _ui.update { it.copy(analyses = s) } }
    }

    fun openAnalysis(id: String) = viewModelScope.launch {
        val b = backend ?: return@launch
        runCatching { b.analysis(id) }.onSuccess { a -> a?.let { setAnalysis(it) } }.onFailure { e -> _ui.update { it.copy(error = msg(e)) } }
    }

    fun loadAlerts() = viewModelScope.launch {
        val b = backend ?: return@launch
        runCatching { b.alerts(0) }.onSuccess { l ->
            _ui.update { it.copy(alerts = l, unread = 0) }
            l.maxOfOrNull { it.id }?.let { prefs.setLastAlertId(it) }
        }
    }

    fun loadSettings() = viewModelScope.launch {
        val b = backend ?: return@launch
        runCatching { b.settings() }.onSuccess { s -> _ui.update { it.copy(settings = s) } }
            .onFailure { e -> _ui.update { it.copy(error = msg(e)) } }
    }

    fun saveSettings(patch: JsonObject) = viewModelScope.launch {
        val b = backend ?: return@launch
        runCatching { b.putSettings(patch) }
            .onSuccess { s -> _ui.update { it.copy(settings = s, toast = "Configurações salvas") } }
            .onFailure { e -> _ui.update { it.copy(toast = msg(e)) } }
    }

    fun useLocal() = viewModelScope.launch { prefs.setMode("local"); _ui.update { it.copy(toast = "Modo autônomo: análise no aparelho, sem servidor e sem chave") } }

    fun saveServer(url: String, key: String) = viewModelScope.launch {
        prefs.saveServer(url, key)
        _ui.update { it.copy(toast = "Servidor salvo — conectando…", error = null) }
    }

    fun testServer(url: String, key: String) = viewModelScope.launch {
        val t = FxApi(url, key)
        if (!t.valid) { _ui.update { it.copy(toast = "URL inválida (use http:// ou https://)") }; return@launch }
        runCatching { t.health(); t.quotes() }
            .onSuccess { _ui.update { it.copy(toast = "Conexão OK com o servidor") } }
            .onFailure { e -> _ui.update { it.copy(toast = "Falha: ${msg(e)}") } }
    }

    fun setNotifications(on: Boolean) = viewModelScope.launch { prefs.setNotifications(on) }

    fun paperExecute(id: String) = viewModelScope.launch {
        val a = api ?: run { _ui.update { it.copy(toast = "Conta demo disponível apenas no modo servidor") }; return@launch }
        runCatching { a.paperExecute(id) }
            .onSuccess { _ui.update { it.copy(toast = "Ordem executada na conta demo") } }
            .onFailure { e -> _ui.update { it.copy(toast = "Demo: ${msg(e)}") } }
    }

    fun clearToast() = _ui.update { it.copy(toast = null) }
    fun clearError() = _ui.update { it.copy(error = null) }

    fun onForeground(fg: Boolean) {
        foreground = fg
        if (fg && ws == null && api != null) openWs()
        if (fg) refreshQuotes()
    }

    override fun onCleared() { ws?.cancel(); super.onCleared() }
}

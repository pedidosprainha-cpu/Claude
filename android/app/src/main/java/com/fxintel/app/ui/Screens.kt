package com.fxintel.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.fxintel.app.data.Quote
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

private val ALL = listOf("XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD",
    "NZDUSD", "EURJPY", "GBPJPY", "EURGBP", "AUDJPY", "CADJPY", "EURCHF", "EURAUD")

private fun digitsOf(s: String) = when { s == "XAUUSD" -> 2; s == "XAGUSD" -> 3; s.endsWith("JPY") -> 3; else -> 5 }

// --------------------------------------------------------------------------- Painel
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun DashboardScreen(vm: MainViewModel, s: UiState, pad: PaddingValues) {
    val fx = LocalFx.current
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = pad.calculateTopPadding() + 4.dp,
        bottom = pad.calculateBottomPadding() + 12.dp)) {
        if (!s.configured) item {
            SectionCard("Bem-vindo") {
                Text("Configure o endereço do servidor FXIntel e a chave de API na aba Ajustes para começar.", fontSize = 14.sp)
            }
        }
        item {
            Column(Modifier.fillMaxWidth().padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Button(onClick = { vm.analyze() }, enabled = !s.analyzing && s.configured,
                    modifier = Modifier.fillMaxWidth().height(64.dp), shape = RoundedCornerShape(16.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)) {
                    if (s.analyzing) {
                        CircularProgressIndicator(Modifier.size(22.dp), color = Color.White, strokeWidth = 2.dp)
                        Spacer(Modifier.width(10.dp)); Text("ANALISANDO…", fontWeight = FontWeight.ExtraBold, fontSize = 17.sp)
                    } else Text("ANALISAR MERCADO AGORA", fontWeight = FontWeight.ExtraBold, fontSize = 17.sp)
                }
                val sub = when {
                    s.analyzing -> "Cotações, multi-timeframe, intermercados, calendário e modelos…"
                    s.error != null -> s.error
                    s.analyzeMs != null -> "Concluído em ${f(s.analyzeMs / 1000.0, 1)} s"
                    else -> null
                }
                if (sub != null) Text(sub, fontSize = 12.sp, color = if (s.error != null) fx.sell else fx.muted,
                    textAlign = TextAlign.Center, modifier = Modifier.padding(top = 6.dp))
            }
        }
        s.analysis?.let { a ->
            item {
                SectionCard("Resultado · ${dateTime(a.created_at)} UTC") {
                    if (a.signal != null) SignalDetails(a.signal, true) { vm.paperExecute(it) }
                    else {
                        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(fx.warnBg).padding(12.dp)) {
                            Text(a.headline, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                            Spacer(Modifier.height(6.dp)); Bullets(a.no_signal_reasons)
                            Text("O motor não emite recomendação sem dados confiáveis, condições adequadas e evidência estatística suficiente.",
                                fontSize = 11.sp, color = fx.muted, modifier = Modifier.padding(top = 6.dp))
                        }
                    }
                }
            }
            if (a.observations.isNotEmpty()) item {
                SectionCard("Observações (não recomendadas)") {
                    a.observations.forEach { c ->
                        var open by remember(c.instrument, c.setup, a.id) { mutableStateOf(false) }
                        Column(Modifier.fillMaxWidth().clickable { open = !open; if (open) vm.select(c) }.padding(vertical = 6.dp)) {
                            Text("${c.direction} ${c.instrument} · ${c.setup_name}", fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                            Text("score ${f(c.score, 0)} · EV ${f(c.expected_value_r, 3)}R · bloqueado por: " +
                                c.gates.filter { !it.passed }.joinToString { it.gate }, fontSize = 12.sp, color = fx.muted)
                            if (open) SignalDetails(c, false)
                        }
                        HorizontalDivider(color = fx.grid)
                    }
                }
            }
        }
        item {
            SectionCard("Gráfico · ${s.chartSymbol} · ${s.chartTf}") {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    listOf("M15", "H1", "H4", "D1").forEach { tf ->
                        FilterChip(selected = s.chartTf == tf, onClick = { vm.chartTf(tf) }, label = { Text(tf) })
                    }
                }
                s.chart?.let { CandleChart(it, s.selected, MaterialTheme.colorScheme.onSurfaceVariant) }
                    ?: Text("Sem dados de gráfico.", color = fx.muted, fontSize = 12.sp)
                if (s.selected == null || s.selected.instrument != s.chartSymbol)
                    Text("Toque em um sinal/observação para ver Entrada, Stop e Alvos.", fontSize = 11.sp, color = fx.muted)
            }
        }
        item {
            SectionCard("Cotações spot", trailing = { Text("${hhmm(s.quotesAt)} UTC", fontSize = 11.sp, color = fx.muted) }) {
                s.quotes.values.sortedBy { it.symbol }.forEach { q -> QuoteRow(q) { vm.chartSymbol(q.symbol) } }
                Text("* spread estimado (provedor sem bid/ask real)", fontSize = 11.sp, color = fx.muted)
            }
        }
        s.analysis?.let { a ->
            if (a.market.isNotEmpty()) item {
                SectionCard("Visão do mercado") {
                    Row { listOf("Ativo" to 70, "D1" to 30, "H4" to 30, "H1" to 30, "Fund." to 48).forEach { (t, w) ->
                        Text(t, Modifier.width(w.dp), fontSize = 11.sp, color = fx.muted) }
                        Text("Regime", fontSize = 11.sp, color = fx.muted) }
                    a.market.forEach { m ->
                        Row(Modifier.fillMaxWidth().clickable { vm.chartSymbol(m.symbol) }.padding(vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically) {
                            Text(m.symbol, Modifier.width(70.dp), fontWeight = FontWeight.SemiBold, fontSize = 12.sp)
                            listOf("D1", "H4", "H1").forEach { tf -> Arrow(m.trend[tf] ?: 0) }
                            val fs = m.fundamental_score ?: 0.0
                            Text(f(m.fundamental_score), Modifier.width(48.dp), fontSize = 12.sp,
                                color = if (fs > 0.1) fx.buy else if (fs < -0.1) fx.sell else fx.muted)
                            Text((m.regime ?: m.error ?: "").substringBefore(" /") + if (m.event_block != null) " · evento" else "",
                                fontSize = 11.sp, color = fx.muted, maxLines = 1)
                        }
                    }
                }
            }
            a.fundamentals?.let { fu ->
                if (fu.strength_5d.isNotEmpty()) item {
                    SectionCard("Força relativa das moedas (5 dias)") {
                        val mx = maxOf(0.5, fu.strength_5d.values.maxOf { kotlin.math.abs(it) })
                        fu.strength_5d.forEach { (cur, v) -> StrengthRow(cur, v, mx) }
                    }
                }
                item {
                    SectionCard("Próximos eventos") {
                        if (fu.upcoming_events.isEmpty()) Text("Sem eventos de impacto nas próximas 36 h.", fontSize = 12.sp, color = fx.muted)
                        fu.upcoming_events.forEach { e ->
                            Row(Modifier.padding(vertical = 3.dp)) {
                                Text(dateTime(e.time), Modifier.width(92.dp), fontSize = 12.sp)
                                Text(e.currency, Modifier.width(40.dp), fontWeight = FontWeight.Bold, fontSize = 12.sp)
                                Text(e.title, Modifier.weight(1f), fontSize = 12.sp)
                                Text(e.impact, fontSize = 11.sp, color = if (e.impact == "High") fx.sell else fx.muted)
                            }
                        }
                    }
                }
            }
            item { Text(a.disclaimer, Modifier.padding(16.dp), fontSize = 11.sp, color = fx.muted, textAlign = TextAlign.Center) }
        }
    }
}

@Composable
private fun Arrow(v: Int) {
    val fx = LocalFx.current
    Text(when { v > 0 -> "▲"; v < 0 -> "▼"; else -> "■" }, Modifier.width(30.dp), fontSize = 12.sp,
        color = when { v > 0 -> fx.buy; v < 0 -> fx.sell; else -> fx.muted })
}

@Composable
private fun StrengthRow(cur: String, v: Double, mx: Double) {
    val fx = LocalFx.current
    Row(Modifier.fillMaxWidth().padding(vertical = 2.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(cur, Modifier.width(40.dp), fontSize = 12.sp, fontWeight = FontWeight.Bold)
        Row(Modifier.weight(1f).height(12.dp)) {
            val frac = (kotlin.math.abs(v) / mx).toFloat().coerceIn(0f, 1f)
            Box(Modifier.weight(1f).height(12.dp), contentAlignment = Alignment.CenterEnd) {
                if (v < 0) Box(Modifier.fillMaxWidth(frac).height(12.dp).background(fx.sell, RoundedCornerShape(3.dp)))
            }
            Box(Modifier.width(1.dp).height(12.dp).background(fx.muted))
            Box(Modifier.weight(1f).height(12.dp), contentAlignment = Alignment.CenterStart) {
                if (v > 0) Box(Modifier.fillMaxWidth(frac).height(12.dp).background(fx.buy, RoundedCornerShape(3.dp)))
            }
        }
        Text((if (v > 0) "+" else "") + f(v), Modifier.width(48.dp).padding(start = 6.dp), fontSize = 11.sp)
    }
}

@Composable
private fun QuoteRow(q: Quote, onClick: () -> Unit) {
    val fx = LocalFx.current
    val d = digitsOf(q.symbol)
    Row(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(q.symbol, Modifier.width(72.dp), fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
        Text("${f(q.bid, d)} / ${f(q.ask, d)}", Modifier.weight(1f), fontSize = 13.sp)
        Text(f(q.spread_pips, 1) + if (q.spread_source == "estimated") "*" else "", Modifier.width(40.dp), fontSize = 11.sp, color = fx.muted)
        val ch = q.change_pct
        Text(if (ch == null) "—" else (if (ch > 0) "+" else "") + f(ch) + "%", Modifier.width(62.dp), fontSize = 12.sp,
            textAlign = TextAlign.End, color = if (ch == null) fx.muted else if (ch > 0) fx.buy else if (ch < 0) fx.sell else fx.muted)
    }
}

// --------------------------------------------------------------------------- Histórico
@Composable
fun HistoryScreen(vm: MainViewModel, s: UiState, pad: PaddingValues, onOpen: () -> Unit) {
    val fx = LocalFx.current
    LaunchedEffect(Unit) { vm.loadHistory() }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = pad) {
        item {
            val st = s.signals?.stats
            SectionCard("Sinais emitidos") {
                Text(if (st == null) "Carregando…" else "${st.total} sinais · ${st.active} ativos · ${st.closed} encerrados · R médio ${f(st.avg_r)}",
                    fontSize = 12.sp, color = fx.muted)
                Text("Cada sinal é acompanhado como se executado no preço de entrada (forward test).", fontSize = 11.sp, color = fx.muted)
            }
        }
        items(s.signals?.items ?: emptyList()) { r ->
            SectionCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(r.direction, color = if (r.direction == "BUY") fx.buy else fx.sell, fontWeight = FontWeight.Bold)
                    Text("  ${r.symbol}", fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                    Chip(r.status, MaterialTheme.colorScheme.surfaceVariant)
                }
                Text("${dateTime(r.created_at)} · entrada ${r.entry} · SL ${r.sl} · TP1 ${r.tp1} · TP2 ${r.tp2 ?: "—"}", fontSize = 12.sp)
                r.outcome_r?.let { Text("Resultado: ${f(it)} R", fontSize = 12.sp, color = if (it > 0) fx.buy else fx.sell) }
            }
        }
        item { SectionCard("Análises") { Text("Toque para reabrir no Painel.", fontSize = 11.sp, color = fx.muted) } }
        items(s.analyses) { a ->
            Row(Modifier.fillMaxWidth().clickable { vm.openAnalysis(a.id); onOpen() }.padding(horizontal = 24.dp, vertical = 8.dp)) {
                Text(dateTime(a.created_at), Modifier.width(100.dp), fontSize = 12.sp)
                Text(if (a.status == "SINAL") "${a.direction} ${a.symbol}" else "sem oportunidade", Modifier.weight(1f), fontSize = 12.sp,
                    fontWeight = if (a.status == "SINAL") FontWeight.Bold else FontWeight.Normal)
                Text("${f((a.elapsed_ms ?: 0.0) / 1000, 1)} s", fontSize = 11.sp, color = fx.muted)
            }
        }
    }
}

// --------------------------------------------------------------------------- Alertas
@Composable
fun AlertsScreen(vm: MainViewModel, s: UiState, pad: PaddingValues) {
    val fx = LocalFx.current
    LaunchedEffect(Unit) { vm.loadAlerts() }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = pad) {
        if (s.alerts.isEmpty()) item { SectionCard("Alertas") { Text("Sem alertas.", color = fx.muted) } }
        items(s.alerts) { a ->
            val col = when (a.severity) { "critical" -> fx.sell; "warning" -> fx.warn; else -> fx.entry }
            SectionCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(10.dp).clip(RoundedCornerShape(5.dp)).background(col))
                    Text("  ${a.kind}", fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                    Text(dateTime(a.ts), fontSize = 11.sp, color = fx.muted)
                }
                Text(a.message, fontSize = 13.sp, modifier = Modifier.padding(top = 4.dp))
            }
        }
    }
}

// --------------------------------------------------------------------------- Ajustes
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SettingsScreen(vm: MainViewModel, s: UiState, pad: PaddingValues, onAskNotif: () -> Unit) {
    val fx = LocalFx.current
    var url by remember(s.prefs.serverUrl) { mutableStateOf(s.prefs.serverUrl) }
    var key by remember(s.prefs.apiKey) { mutableStateOf(s.prefs.apiKey) }
    LaunchedEffect(s.configured) { if (s.configured) { vm.loadSettings(); vm.refreshHealth() } }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = pad) {
        item {
            SectionCard("Servidor") {
                OutlinedTextField(url, { url = it }, label = { Text("URL (ex.: https://fxintel.seudominio.com)") },
                    singleLine = true, modifier = Modifier.fillMaxWidth(), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri))
                OutlinedTextField(key, { key = it }, label = { Text("Chave de API") }, singleLine = true,
                    visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth().padding(top = 6.dp))
                Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { vm.saveServer(url, key) }) { Text("Salvar") }
                    OutlinedButton(onClick = { vm.testServer(url, key) }) { Text("Testar conexão") }
                }
                Text("Use HTTPS em redes públicas. HTTP é aceito apenas para servidores na rede local.", fontSize = 11.sp, color = fx.muted)
            }
        }
        item {
            SectionCard("Notificações") {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Alertas de sinais, eventos, volatilidade e dados", Modifier.weight(1f), fontSize = 13.sp)
                    Switch(s.prefs.notifications, { vm.setNotifications(it); if (it) onAskNotif() })
                }
                Text("Em segundo plano o app consulta o servidor a cada 15 min; com o app aberto, os alertas chegam em tempo real.",
                    fontSize = 11.sp, color = fx.muted)
            }
        }
        s.settings?.let { cfg -> item { RemoteSettings(cfg) { vm.saveSettings(it) } } }
        item { SystemCard(s) }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun RemoteSettings(cfg: JsonObject, onSave: (JsonObject) -> Unit) {
    val universe0 = cfg["universe"]?.jsonArray?.map { it.jsonPrimitive.content } ?: emptyList()
    var universe by remember(cfg) { mutableStateOf(universe0.toSet()) }
    fun num(sec: String, k: String) = cfg[sec]?.jsonObject?.get(k)?.jsonPrimitive?.doubleOrNull?.toString() ?: ""
    var equity by remember(cfg) { mutableStateOf(num("account", "equity")) }
    var riskPct by remember(cfg) { mutableStateOf(num("risk", "risk_per_trade_pct")) }
    var daily by remember(cfg) { mutableStateOf(num("risk", "max_daily_loss_pct")) }
    var maxPos by remember(cfg) { mutableStateOf(num("risk", "max_open_positions")) }
    var minEv by remember(cfg) { mutableStateOf(num("gates", "min_ev_r")) }
    var minRr by remember(cfg) { mutableStateOf(num("gates", "min_rr_net")) }
    var reqModel by remember(cfg) {
        mutableStateOf(cfg["gates"]?.jsonObject?.get("require_model")?.jsonPrimitive?.booleanOrNull ?: true)
    }
    SectionCard("Instrumentos e risco (servidor)") {
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            ALL.forEach { sym ->
                FilterChip(selected = sym in universe, onClick = {
                    universe = if (sym in universe) universe - sym else universe + sym
                }, label = { Text(sym, fontSize = 12.sp) })
            }
        }
        @Composable
        fun field(label: String, v: String, set: (String) -> Unit) = OutlinedTextField(v, set, label = { Text(label) },
            singleLine = true, modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
        field("Capital da conta", equity) { equity = it }
        field("Risco por trade (%) — máx. 2", riskPct) { riskPct = it }
        field("Perda máxima diária (%)", daily) { daily = it }
        field("Máx. posições abertas", maxPos) { maxPos = it }
        field("EV mínimo (R)", minEv) { minEv = it }
        field("R:R líquido mínimo", minRr) { minRr = it }
        Row(Modifier.padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("Exigir modelo validado (recomendado)", Modifier.weight(1f), fontSize = 13.sp)
            Switch(reqModel, { reqModel = it })
        }
        Button(onClick = {
            onSave(buildJsonObject {
                putJsonArray("universe") { ALL.filter { it in universe }.forEach { add(JsonPrimitive(it)) } }
                putJsonObject("account") { equity.toDoubleOrNull()?.let { put("equity", it) } }
                putJsonObject("risk") {
                    riskPct.toDoubleOrNull()?.let { put("risk_per_trade_pct", it) }
                    daily.toDoubleOrNull()?.let { put("max_daily_loss_pct", it) }
                    maxPos.toDoubleOrNull()?.let { put("max_open_positions", it.toInt()) }
                }
                putJsonObject("gates") {
                    minEv.toDoubleOrNull()?.let { put("min_ev_r", it) }
                    minRr.toDoubleOrNull()?.let { put("min_rr_net", it) }
                    put("require_model", reqModel)
                }
            })
        }, Modifier.padding(top = 10.dp)) { Text("Salvar no servidor") }
    }
}

@Composable
private fun SystemCard(s: UiState) {
    val fx = LocalFx.current
    val h = s.health
    SectionCard("Conectividade e integridade") {
        KV("Rede do aparelho", if (s.networkOnline) "conectada" else "sem conexão")
        KV("Canal de dados", when (s.link) { Link.LIVE -> "tempo real (WebSocket)"; Link.POLLING -> "consulta periódica";
            Link.CONNECTING -> "conectando…"; Link.OFFLINE -> "offline" })
        KV("Servidor", when (s.serverOk) { true -> "acessível"; false -> "inacessível"; null -> "—" })
        if (h != null) {
            KV("Status", h.status + if (h.degraded.isNotEmpty()) " (${h.degraded.joinToString()})" else "", true)
            KV("Versão / uptime", "${h.version} · ${f(h.uptime_s / 60, 0)} min")
            KV("Mercado", if (h.market_open) "aberto" else "fechado")
            KV("Última cotação", "${hhmm(h.quotes_at)} UTC")
            KV("Banco de dados", if (h.database) "ok" else "falha")
            KV("Modelo", when { h.model.available != true -> "não treinado"; h.model.validated == true -> "validado";
                else -> "NÃO validado (sinais bloqueados)" } + " · idade ${f(h.model.age_hours, 1)} h")
            h.providers.providers.forEach { p ->
                val st = if (p.name == "oanda" && !h.providers.oanda_configured) "não configurado" else if (p.ok) "ok" else "falha"
                KV("Provedor ${p.name}", "$st · ${f(p.last_latency_ms, 0)} ms · ${p.requests} req / ${p.failures} falhas")
            }
        } else Text("Sem dados de saúde do servidor.", fontSize = 12.sp, color = fx.muted)
    }
}

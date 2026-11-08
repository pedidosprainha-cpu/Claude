@file:OptIn(ExperimentalMaterial3Api::class)

package com.fxengine.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.fxengine.app.data.AppSettings
import com.fxengine.app.data.Opportunity
import com.fxengine.app.data.ScanResult
import com.fxengine.app.ui.theme.Fx
import kotlin.math.roundToInt

@Composable
fun EmptyHint(text: String) {
    Box(Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
        Text(text, color = Fx.Muted, fontSize = 15.sp)
    }
}

@Composable
fun ScreenTitle(title: String, subtitle: String = "") {
    Column(Modifier.fillMaxWidth().padding(top = 12.dp, bottom = 8.dp)) {
        Text(title, style = MaterialTheme.typography.headlineMedium, color = Fx.Text)
        if (subtitle.isNotBlank()) Text(subtitle, color = Fx.Muted, fontSize = 13.sp)
    }
}

// ------------------------------------------------------------------ ranking

@Composable
fun RankingScreen(result: ScanResult?) {
    if (result == null) return EmptyHint("Faça uma análise para ver o ranking.")
    var onlyExec by remember { mutableStateOf(false) }
    var selected by remember { mutableStateOf<Opportunity?>(null) }
    val list = if (onlyExec) result.ranking.filter { it.executable } else result.ranking

    LazyColumn(
        Modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        contentPadding = PaddingValues(bottom = 24.dp),
    ) {
        item {
            ScreenTitle("Ranking", "${result.ranking.size} ativos · ${result.weekday} ${result.timestamp}")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(selected = !onlyExec, onClick = { onlyExec = false }, label = { Text("Todos") })
                FilterChip(
                    selected = onlyExec, onClick = { onlyExec = true },
                    label = { Text("Executáveis (${result.ranking.count { it.executable }})") },
                )
            }
            Spacer(Modifier.height(4.dp))
        }
        if (list.isEmpty()) {
            item { Text("Nenhum ativo passou nos filtros agora.", color = Fx.Muted, modifier = Modifier.padding(16.dp)) }
        }
        itemsIndexed(list) { i, o -> OpportunityRow(i + 1, o) { selected = o } }
    }

    selected?.let { o ->
        val sheet = rememberModalBottomSheetState(skipPartiallyExpanded = true)
        ModalBottomSheet(onDismissRequest = { selected = null }, sheetState = sheet, containerColor = Fx.Bg) {
            Column(Modifier.verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp)) {
                OpportunityDetail(o, referenceOnly = !o.executable)
                Spacer(Modifier.height(32.dp))
            }
        }
    }
}

// ------------------------------------------------------------------ market

@Composable
fun MarketScreen(result: ScanResult?) {
    if (result == null) return EmptyHint("Faça uma análise para ver o mercado.")
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        ScreenTitle("Mercado", result.session)

        SectionCard("Força das moedas") {
            Text("Mais forte no topo · retornos normalizados em 4h, 24h e 5 dias", color = Fx.Muted, fontSize = 12.sp)
            Spacer(Modifier.height(8.dp))
            result.strength.forEach { s ->
                Row(Modifier.fillMaxWidth().padding(vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(s.ccy, color = Fx.Text, fontWeight = FontWeight.Bold, modifier = Modifier.width(48.dp))
                    ScoreBar(s.z, max = 2.0, modifier = Modifier.weight(1f))
                    Text(
                        (if (s.z > 0) "+" else "") + s.z.f(), color = if (s.z >= 0) Fx.Buy else Fx.Sell,
                        fontSize = 13.sp, modifier = Modifier.width(56.dp).padding(start = 8.dp),
                    )
                }
            }
            if (result.metals.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Text(
                    "Metais vs USD: " + result.metals.joinToString(" · ") { "${it.first} ${if (it.second > 0) "+" else ""}${it.second.f()}σ" },
                    color = Fx.Muted, fontSize = 12.sp,
                )
            }
        }

        SectionCard("Macro e risco") { Bullets(result.macroNotes, Fx.Blue, 6) }

        if (result.rates.isNotEmpty()) {
            SectionCard("Juros dos bancos centrais (${result.ratesSource})") {
                result.rates.forEach { r ->
                    Row(Modifier.fillMaxWidth().padding(vertical = 3.dp)) {
                        Text(r.ccy, color = Fx.Text, fontWeight = FontWeight.Bold, modifier = Modifier.width(56.dp))
                        Text("${r.rate.f()}%", color = Fx.Text, modifier = Modifier.weight(1f))
                        if (r.chg6m != 0.0) {
                            Text(
                                "${if (r.chg6m > 0) "+" else ""}${r.chg6m.f()} em 6m",
                                color = if (r.chg6m > 0) Fx.Buy else Fx.Sell, fontSize = 13.sp,
                            )
                        }
                    }
                }
            }
        }

        SectionCard("Agenda de alto impacto (48h)") {
            if (result.events.isEmpty()) Text("Nenhum evento de alto impacto.", color = Fx.Muted)
            result.events.forEach { e ->
                Column(Modifier.padding(vertical = 5.dp)) {
                    Row {
                        Text(e.ccy, color = Fx.Gold, fontWeight = FontWeight.Bold, modifier = Modifier.width(48.dp))
                        Text(e.title, color = Fx.Text, modifier = Modifier.weight(1f))
                    }
                    Text(
                        "${e.whenLocal} · ${e.inText}" +
                            (if (e.forecast.isNotBlank()) " · proj ${e.forecast}" else "") +
                            (if (e.previous.isNotBlank()) " · ant ${e.previous}" else ""),
                        color = Fx.Muted, fontSize = 12.sp, modifier = Modifier.padding(start = 48.dp),
                    )
                }
            }
        }

        if (result.cot.isNotEmpty()) {
            SectionCard("Posicionamento dos especuladores (COT)") {
                Text("Líquido em % do open interest · [índice 0–100 em 3 anos]", color = Fx.Muted, fontSize = 12.sp)
                Spacer(Modifier.height(6.dp))
                result.cot.chunked(2).forEach { pair ->
                    Row(Modifier.fillMaxWidth().padding(vertical = 3.dp)) {
                        pair.forEach { c ->
                            Text(
                                "${c.asset}  ${if (c.netPct > 0) "+" else ""}${c.netPct.roundToInt()}%  [${c.index.roundToInt()}]",
                                color = if (c.index >= 90 || c.index <= 10) Fx.Warn else Fx.Text,
                                fontSize = 13.sp, modifier = Modifier.weight(1f),
                            )
                        }
                    }
                }
            }
        }

        if (result.headlines.isNotEmpty()) {
            SectionCard("Manchetes recentes") {
                result.headlines.take(10).forEach { (w, t) ->
                    Column(Modifier.padding(vertical = 5.dp)) {
                        Text(t, color = Fx.Text, fontSize = 14.sp, lineHeight = 18.sp)
                        Text(w, color = Fx.Muted, fontSize = 11.sp)
                    }
                }
            }
        }

        if (result.dataIssues.isNotEmpty()) {
            SectionCard("Falhas de dados nesta análise", accent = Fx.Warn) { Bullets(result.dataIssues, Fx.Warn, 5) }
        }
        Spacer(Modifier.height(24.dp))
    }
}

// ------------------------------------------------------------------ settings

@Composable
fun SettingsScreen(settings: AppSettings, onChange: (AppSettings) -> Unit) {
    var balanceText by remember(settings.balance) { mutableStateOf(settings.balance.roundToInt().toString()) }
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        ScreenTitle("Ajustes", "Usados para calcular o lote de cada trade")

        SectionCard("Saldo da conta (US$)") {
            OutlinedTextField(
                value = balanceText,
                onValueChange = { t ->
                    balanceText = t.filter { it.isDigit() }.take(9)
                    balanceText.toDoubleOrNull()?.takeIf { it > 0 }?.let { onChange(settings.copy(balance = it)) }
                },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth(),
            )
        }

        SectionCard("Risco por trade") {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("${settings.riskPct.f(2)}%", color = Fx.Text, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.width(12.dp))
                Text("= ${money(settings.balance * settings.riskPct / 100)} se o stop for atingido", color = Fx.Muted, fontSize = 13.sp)
            }
            Slider(
                value = settings.riskPct.toFloat(),
                onValueChange = { v -> onChange(settings.copy(riskPct = (v * 4).roundToInt() / 4.0)) },
                valueRange = 0.25f..3f,
                steps = 10,
            )
            Text("Recomendado: entre 0,5% e 1%.", color = Fx.Muted, fontSize = 12.sp)
        }

        SectionCard("Ativos analisados") {
            val opts = listOf("all" to "Todos", "fx" to "Forex", "metais" to "Metais")
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                opts.forEachIndexed { i, (key, label) ->
                    SegmentedButton(
                        selected = settings.assets == key,
                        onClick = { onChange(settings.copy(assets = key)) },
                        shape = SegmentedButtonDefaults.itemShape(i, opts.size),
                    ) { Text(label) }
                }
            }
        }

        SectionCard("Precisão x velocidade") {
            ToggleRow(
                "Estudo de edge histórico",
                "Testa o setup em 1 ano de dados para estimar a probabilidade. Mais preciso, um pouco mais lento.",
                settings.useEdge,
            ) { onChange(settings.copy(useEdge = it)) }
            ToggleRow(
                "Manchetes de notícias",
                "Inclui o sentimento das manchetes recentes na análise fundamental.",
                settings.useNews,
            ) { onChange(settings.copy(useNews = it)) }
        }

        SectionCard("Sobre") {
            Text(
                "O FX Engine combina análise gráfica em 5 timeframes, modelos quantitativos, força relativa das " +
                    "moedas e fundamentos (juros, risco, COT, agenda e notícias). Preços spot ao vivo da " +
                    "Swissquote; gráficos do Yahoo Finance; juros do BIS; posicionamento da CFTC; agenda da ForexFactory.",
                color = Fx.Muted, fontSize = 13.sp, lineHeight = 18.sp,
            )
            Spacer(Modifier.height(8.dp))
            Text(
                "Aviso: análise automatizada e probabilística, não é recomendação de investimento. Confira preço e " +
                    "spread na sua corretora antes de executar e sempre use o stop.",
                color = Fx.Warn, fontSize = 12.sp, lineHeight = 16.sp,
            )
        }
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun ToggleRow(title: String, desc: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f).padding(end = 12.dp)) {
            Text(title, color = Fx.Text, fontSize = 15.sp)
            Text(desc, color = Fx.Muted, fontSize = 12.sp, lineHeight = 16.sp)
        }
        Switch(checked = checked, onCheckedChange = onChange)
    }
}

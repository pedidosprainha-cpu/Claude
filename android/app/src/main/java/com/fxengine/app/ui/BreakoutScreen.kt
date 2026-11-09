@file:OptIn(ExperimentalMaterial3Api::class)

package com.fxengine.app.ui

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.fxengine.app.data.AppSettings
import com.fxengine.app.data.BreakoutItem
import com.fxengine.app.monitor.BreakoutMonitor
import com.fxengine.app.monitor.MonitorService
import com.fxengine.app.monitor.MonitorState
import com.fxengine.app.monitor.Notifications
import com.fxengine.app.ui.theme.Fx
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private val Trap = Color(0xFFB794F6)

fun statusColor(b: BreakoutItem): Color = when (b.status) {
    "rompendo" -> Fx.Blue
    "reteste" -> Fx.Gold
    "falso" -> Trap
    else -> Fx.side(b.isBuy)
}

/** Wires the screen to the process-wide monitor and the foreground service. */
@Composable
fun BreakoutScreen(settings: AppSettings, onSettings: (AppSettings) -> Unit) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    val mon by BreakoutMonitor.state.collectAsStateWithLifecycle()
    LaunchedEffect(Unit) { BreakoutMonitor.restore(ctx) }
    val askNotif = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        MonitorService.start(ctx)
    }
    BreakoutContent(
        mon = mon,
        settings = settings,
        notificationsAllowed = Notifications.canPost(ctx),
        onScanNow = { scope.launch { BreakoutMonitor.scanOnce(ctx) } },
        onToggleMonitor = {
            if (mon.active) {
                MonitorService.stop(ctx)
            } else if (Build.VERSION.SDK_INT >= 33 && !Notifications.canPost(ctx)) {
                askNotif.launch(Manifest.permission.POST_NOTIFICATIONS)
            } else {
                MonitorService.start(ctx)
            }
        },
        onSettings = onSettings,
    )
}

@Composable
fun BreakoutContent(
    mon: MonitorState,
    settings: AppSettings,
    notificationsAllowed: Boolean,
    onScanNow: () -> Unit,
    onToggleMonitor: () -> Unit,
    onSettings: (AppSettings) -> Unit,
) {
    val haptic = LocalHapticFeedback.current
    var filter by remember { mutableStateOf(0) }       // 0 acionáveis · 1 todos · 2 falsos
    var selected by remember { mutableStateOf<BreakoutItem?>(null) }
    val result = mon.result
    LaunchedEffect(mon.cycles) {
        if ((result?.newActionable ?: 0) > 0) haptic.performHapticFeedback(HapticFeedbackType.LongPress)
    }
    val all = result?.items ?: emptyList()
    val shown = when (filter) {
        0 -> all.filter { it.actionable }
        2 -> all.filter { it.isTrap }
        else -> all
    }

    LazyColumn(
        Modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
        contentPadding = PaddingValues(bottom = 24.dp),
    ) {
        item { ScreenTitle("Rompimentos", "Detecção em tempo real · M15 e H1 · ${assetsLabel(settings.assets)}") }
        item { MonitorCard(mon, settings, notificationsAllowed, onScanNow, onToggleMonitor, onSettings) }
        result?.model?.let { m -> item { ValidationCard(m) } }
        if (result != null) {
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(filter == 0, { filter = 0 }, label = { Text("Melhores A/A+ (${all.count { it.actionable }})") })
                    FilterChip(filter == 1, { filter = 1 }, label = { Text("Todos (${all.size})") })
                    FilterChip(filter == 2, { filter = 2 }, label = { Text("Falsos (${all.count { it.isTrap }})") })
                }
            }
            if (shown.isEmpty()) {
                item {
                    Text(
                        if (filter == 0) "Nenhum rompimento com nota A ou A+ agora. Com o monitor ligado você recebe um alerta assim que surgir."
                        else "Nada nesta categoria agora.",
                        color = Fx.Muted, fontSize = 14.sp, modifier = Modifier.padding(vertical = 16.dp),
                    )
                }
            }
            items(shown, key = { it.id }) { b -> BreakoutCard(b) { selected = b } }
            item {
                Text(
                    "Varredura das ${result.time} · ${result.scanned} ativos em ${result.elapsedS.f(1)} s · ${result.session}",
                    color = Fx.Muted, fontSize = 11.sp, modifier = Modifier.padding(top = 6.dp),
                )
                result.dataIssues.take(3).forEach { Text(it, color = Fx.Warn, fontSize = 11.sp) }
            }
        } else if (!mon.scanning) {
            item {
                EmptyHint("Toque em \"Escanear\" ou ligue o monitor.")
            }
        }
    }

    selected?.let { b ->
        val sheet = rememberModalBottomSheetState(skipPartiallyExpanded = true)
        ModalBottomSheet(onDismissRequest = { selected = null }, sheetState = sheet, containerColor = Fx.Bg) {
            Column(Modifier.verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp)) {
                BreakoutDetail(b)
                Spacer(Modifier.height(32.dp))
            }
        }
    }
}

@Composable
private fun MonitorCard(
    mon: MonitorState,
    settings: AppSettings,
    notificationsAllowed: Boolean,
    onScanNow: () -> Unit,
    onToggle: () -> Unit,
    onSettings: (AppSettings) -> Unit,
) {
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    val static = LocalStaticUi.current
    LaunchedEffect(mon.active, static) {
        while (mon.active && !static) {
            now = System.currentTimeMillis(); delay(1000)
        }
    }
    SectionCard(accent = if (mon.active) Fx.Buy else null) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(10.dp).clip(CircleShape).background(if (mon.active) Fx.Buy else Fx.Muted))
            Spacer(Modifier.width(8.dp))
            Text(
                if (mon.active) "Monitor ligado" else "Monitor desligado",
                color = Fx.Text, fontWeight = FontWeight.Bold, fontSize = 16.sp,
            )
        }
        Spacer(Modifier.height(4.dp))
        val secs = ((mon.nextAtMillis - now) / 1000).coerceAtLeast(0)
        Text(
            when {
                mon.scanning -> mon.step
                mon.active && mon.nextAtMillis > 0 -> "Próximo ciclo em ${secs}s · alerta para nota ${settings.alertMinGrade} ou melhor"
                mon.active -> "Preparando o primeiro ciclo…"
                else -> "Ligue para varrer a cada ${settings.monitorIntervalSec / 60} min e receber alerta no celular, mesmo com a tela apagada."
            },
            color = Fx.Muted, fontSize = 13.sp, lineHeight = 17.sp,
        )
        if (mon.scanning) {
            Spacer(Modifier.height(8.dp))
            LinearProgressIndicator(progress = { mon.progress / 100f }, modifier = Modifier.fillMaxWidth(), color = Fx.Blue)
        }
        if (mon.active && !notificationsAllowed) {
            Spacer(Modifier.height(6.dp))
            Text("Notificações bloqueadas: libere nas configurações do Android para receber os alertas.",
                color = Fx.Warn, fontSize = 12.sp)
        }
        mon.error?.let {
            Spacer(Modifier.height(6.dp))
            Text("Último ciclo falhou: $it", color = Fx.Sell, fontSize = 12.sp)
        }
        Spacer(Modifier.height(12.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Button(
                onClick = onToggle,
                colors = ButtonDefaults.buttonColors(containerColor = if (mon.active) Fx.Sell else Fx.Buy),
                modifier = Modifier.weight(1f),
            ) {
                if (!mon.active) Icon(Icons.Filled.PlayArrow, null, Modifier.size(18.dp))
                Spacer(Modifier.width(4.dp))
                Text(if (mon.active) "Parar monitor" else "Monitorar ao vivo", fontWeight = FontWeight.Bold)
            }
            OutlinedButton(onClick = onScanNow, enabled = !mon.scanning, modifier = Modifier.weight(1f)) {
                Icon(Icons.Filled.Refresh, null, Modifier.size(18.dp))
                Spacer(Modifier.width(4.dp))
                Text("Escanear")
            }
        }
        Spacer(Modifier.height(14.dp))
        Text("Frequência", color = Fx.Muted, fontSize = 12.sp)
        val intervals = listOf(60 to "1 min", 120 to "2 min", 300 to "5 min")
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            intervals.forEachIndexed { i, (sec, label) ->
                SegmentedButton(
                    selected = settings.monitorIntervalSec == sec,
                    onClick = { onSettings(settings.copy(monitorIntervalSec = sec)) },
                    shape = SegmentedButtonDefaults.itemShape(i, intervals.size),
                ) { Text(label) }
            }
        }
        Text(
            "Consumo aproximado: " + when (settings.monitorIntervalSec) {
                60 -> "70 MB/h"
                120 -> "35 MB/h"
                else -> "15 MB/h"
            } + " (prefira Wi-Fi para 1 min)",
            color = Fx.Muted, fontSize = 11.sp, modifier = Modifier.padding(top = 4.dp),
        )
        Spacer(Modifier.height(10.dp))
        Text("Alertar a partir da nota", color = Fx.Muted, fontSize = 12.sp)
        val grades = listOf("A+", "A", "B")
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            grades.forEachIndexed { i, g ->
                SegmentedButton(
                    selected = settings.alertMinGrade == g,
                    onClick = { onSettings(settings.copy(alertMinGrade = g)) },
                    shape = SegmentedButtonDefaults.itemShape(i, grades.size),
                ) { Text(g) }
            }
        }
    }
}

@Composable
private fun ValidationCard(m: com.fxengine.app.data.ModelInfo) {
    SectionCard("Precisão validada no histórico") {
        Text(
            "${"%,d".format(m.events).replace(',', '.')} rompimentos reconstituídos (${m.periodFrom} a ${m.periodTo}), " +
                "com spread, avaliados em dias que o modelo não viu:",
            color = Fx.Muted, fontSize = 12.sp, lineHeight = 16.sp,
        )
        Spacer(Modifier.height(8.dp))
        Row(Modifier.fillMaxWidth()) {
            Column(Modifier.weight(1f)) {
                Text("Antes", color = Fx.Muted, fontSize = 12.sp)
                Text("${(m.oldHit * 100).toInt()}% no alvo 1", color = Fx.Text, fontWeight = FontWeight.Bold)
                Text("${if (m.oldR >= 0) "+" else ""}${m.oldR.f()}R por trade", color = Fx.Sell, fontSize = 13.sp)
            }
            Column(Modifier.weight(1f)) {
                Text("Agora (nota A/A+)", color = Fx.Muted, fontSize = 12.sp)
                Text("${(m.newHit * 100).toInt()}% no alvo 1", color = Fx.Buy, fontWeight = FontWeight.Bold)
                Text("${if (m.newR >= 0) "+" else ""}${m.newR.f()}R por trade",
                    color = if (m.newR >= 0) Fx.Buy else Fx.Warn, fontSize = 13.sp)
            }
        }
        Spacer(Modifier.height(8.dp))
        Text(
            "A precisão subiu muito, mas a expectativa ainda fica perto de zero depois do spread: use os alertas " +
                "como oportunidade a confirmar no gráfico, não como ordem automática.",
            color = Fx.Warn, fontSize = 12.sp, lineHeight = 16.sp,
        )
    }
}

@Composable
private fun StatusPill(text: String, color: Color) {
    Box(
        Modifier.clip(RoundedCornerShape(6.dp)).background(color.copy(alpha = 0.16f))
            .border(1.dp, color.copy(alpha = 0.7f), RoundedCornerShape(6.dp))
            .padding(horizontal = 7.dp, vertical = 2.dp),
    ) { Text(text, color = color, fontSize = 11.sp, fontWeight = FontWeight.Bold) }
}

@Composable
fun BreakoutCard(b: BreakoutItem, onClick: () -> Unit) {
    val sc = statusColor(b)
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Fx.Surface),
        border = if (b.isNew) androidx.compose.foundation.BorderStroke(1.5.dp, Fx.Gold.copy(alpha = 0.8f)) else null,
    ) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    StatusPill(b.statusLabel, sc)
                    if (b.isNew) StatusPill("NOVO", Fx.Gold)
                    if (b.extended) StatusPill("ESTICADO", Fx.Warn)
                }
                Spacer(Modifier.height(6.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(b.symbol, color = Fx.Text, fontWeight = FontWeight.Bold, fontSize = 17.sp)
                    Text("  ${b.tf}", color = Fx.Muted, fontSize = 13.sp)
                    Spacer(Modifier.width(8.dp))
                    SideChip(b.side, b.isBuy)
                }
                Spacer(Modifier.height(4.dp))
                Text(
                    (if (b.isTrap) "Falso rompimento de " else "Nível ") + "${b.level} · ${b.levelLabel}",
                    color = Fx.Text.copy(alpha = 0.9f), fontSize = 13.sp, lineHeight = 17.sp, maxLines = 2,
                )
                if (b.prob != null && b.evR != null) {
                    Text(
                        "Alvo 1 antes do stop: ${(b.prob * 100).toInt()}% · expectativa ${if (b.evR >= 0) "+" else ""}${b.evR.f()}R",
                        color = if (b.evR >= 0.1) Fx.Buy else if (b.evR >= 0) Fx.Text else Fx.Warn,
                        fontSize = 12.sp, fontWeight = FontWeight.SemiBold,
                    )
                }
                Text(
                    "${if (b.extPips >= 0) "+" else ""}${b.extPips.f(1)} pips do nível · detectado ${b.firstSeen}" +
                        if (b.ageMin > 0) " (há ${b.ageMin} min)" else " (agora)",
                    color = Fx.Muted, fontSize = 12.sp,
                )
            }
            GradeBadge(b.grade, b.quality, 48)
        }
    }
}

@Composable
fun BreakoutDetail(b: BreakoutItem) {
    val ctx = LocalContext.current
    val sc = statusColor(b)
    val p = b.plan
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SectionCard(accent = if (b.actionable) Fx.side(b.isBuy) else Fx.Outline) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    StatusPill(b.statusLabel, sc)
                    Spacer(Modifier.height(6.dp))
                    Text("${b.symbol} · ${b.tf}", color = Fx.Text, fontSize = 24.sp, fontWeight = FontWeight.Bold)
                    Text(b.headline, color = Fx.Muted, fontSize = 13.sp, lineHeight = 17.sp)
                    Spacer(Modifier.height(6.dp))
                    SideChip(b.side, b.isBuy, big = true)
                }
                GradeBadge(b.grade, b.quality, 62)
            }
            if (b.blocked) {
                Spacer(Modifier.height(8.dp))
                Text("Bloqueado agora (veja os pontos de atenção): não gera alerta.", color = Fx.Warn, fontSize = 13.sp)
            } else if (!b.actionable) {
                Spacer(Modifier.height(8.dp))
                Text("Fora dos melhores 10% do histórico (nota abaixo de A).", color = Fx.Muted, fontSize = 13.sp)
            }
            Spacer(Modifier.height(8.dp))
            HorizontalDivider(color = Fx.Outline)
            PlanRow("Nível", b.level, b.levelLabel)
            PlanRow("Entrada", p.entry, (if (b.isBuy) "compra no ask" else "venda no bid") + " · bid ${b.bid} / ask ${b.ask}")
            PlanRow("Stop", p.sl, "${p.slPips.f(1)} pips · ${p.slBasis}", Fx.Sell)
            PlanRow("Alvo 1", p.tp1, "${p.tp1Pips.f(1)} pips · ${p.rr1.f()}R · ${p.tp1Basis} · realizar 50%", Fx.Buy)
            PlanRow("Alvo 2", p.tp2, "${p.tp2Pips.f(1)} pips · ${p.rr2.f()}R · ${p.tp2Basis}", Fx.Buy)
            PlanRow("Lote", p.lots.f(2), "risco ${money(p.riskAmount)}")
            if (b.prob != null && b.evR != null) {
                PlanRow(
                    "Prob. alvo 1", "${(b.prob * 100).toInt()}%",
                    "probabilidade calibrada em rompimentos históricos parecidos · expectativa " +
                        "${if (b.evR >= 0) "+" else ""}${b.evR.f()}R por trade",
                    if (b.evR >= 0.1) Fx.Buy else if (b.evR >= 0) Fx.Text else Fx.Warn,
                )
            }
            if (b.histN >= 8) {
                PlanRow(
                    "Histórico", "${(b.histP * 100).toInt()}%",
                    "${b.histWins} de ${b.histN} rompimentos parecidos neste ativo seguiram +1 ATR antes de voltar −1 ATR",
                    if (b.histP >= 0.5) Fx.Buy else Fx.Warn,
                )
            }
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Button(
                    onClick = { copyText(ctx, "ordem", b.orderText) },
                    colors = ButtonDefaults.buttonColors(containerColor = Fx.side(b.isBuy)),
                    modifier = Modifier.weight(1f),
                ) { Text("Copiar ordem", fontWeight = FontWeight.Bold) }
                OutlinedButton(onClick = { shareText(ctx, b.orderText) }, modifier = Modifier.weight(1f)) {
                    Icon(Icons.Filled.Share, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Compartilhar")
                }
            }
        }
        if (b.pros.isNotEmpty()) SectionCard("A favor") { Bullets(b.pros, Fx.Buy, 6) }
        if (b.cons.isNotEmpty()) SectionCard("Atenção") { Bullets(b.cons, Fx.Warn, 6) }
        SectionCard("Como ler") {
            Text(
                "A probabilidade vem de um modelo calibrado em dezenas de milhares de rompimentos reconstituídos no " +
                    "histórico (com spread): é a chance real de o alvo 1 vir antes do stop. A nota é relativa: " +
                    "A+ = melhores 3% dos rompimentos, A = melhores 10%, B = 25%, C = 50%. " +
                    "ROMPENDO AGORA (pré-alerta): o preço passou do nível e o candle ainda não fechou — o alerta sai no fechamento. CONFIRMADO: um candle fechou além " +
                    "do nível. RETESTE: depois de romper, o preço voltou ao nível e segurou. FALSO ROMPIMENTO: rompeu e " +
                    "fechou de volta — o trade é na direção contrária (armadilha). ESTICADO: o preço já se afastou demais; " +
                    "melhor esperar um reteste.",
                color = Fx.Muted, fontSize = 12.sp, lineHeight = 17.sp,
            )
        }
    }
}

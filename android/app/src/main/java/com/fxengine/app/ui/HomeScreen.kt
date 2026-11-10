package com.fxengine.app.ui

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.fxengine.app.data.ScanResult
import com.fxengine.app.ui.theme.Fx
import kotlinx.coroutines.delay

/** True in screenshot tests: disables infinite animations and the "há X min" ticker. */
val LocalStaticUi = staticCompositionLocalOf { false }

@Composable
fun HomeScreen(
    state: UiState,
    onAnalyze: () -> Unit,
    onDismissError: () -> Unit,
    onSettings: (com.fxengine.app.data.AppSettings) -> Unit = {},
) {
    val haptic = LocalHapticFeedback.current
    var picking by remember { mutableStateOf(false) }
    val single = state.settings.homeMode == "asset"
    val view = LocalView.current
    val scroll = rememberScrollState()

    // Keep the screen awake while the engine works; buzz when it finishes.
    LaunchedEffect(state.running) { view.keepScreenOn = state.running }
    LaunchedEffect(state.justFinished) {
        if (state.justFinished > 0) {
            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
            scroll.animateScrollTo(520)
        }
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(scroll).padding(horizontal = 16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.height(12.dp))
        Header(state)
        Spacer(Modifier.height(14.dp))
        ModeSelector(state.settings, enabled = !state.running, onSettings = onSettings, onPick = { picking = true })
        Spacer(Modifier.height(18.dp))
        AnalyzeButton(state.running, state.progress, label = if (single) state.settings.focusSymbol else "ANALISAR",
            onClick = {
            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
            onAnalyze()
        })
        Spacer(Modifier.height(18.dp))
        if (state.running) {
            Text(state.step, color = Fx.Text, fontSize = 15.sp, textAlign = TextAlign.Center)
            Spacer(Modifier.height(4.dp))
            Text(if (single) "Leva cerca de 10 a 20 s. Mantenha o app aberto."
                 else "Leva de 30 s a 1 min. Mantenha o app aberto.", color = Fx.Muted, fontSize = 12.sp)
        } else {
            val s = state.settings
            Text(
                if (single) "Toque para a análise completa de ${s.focusSymbol} (${com.fxengine.app.data.Catalog.name(s.focusSymbol)})"
                else "Toque para analisar ${assetsLabel(s.assets)} agora",
                color = Fx.Text, fontSize = 15.sp, textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                "Conta ${money(s.balance)} · risco ${s.riskPct.f(2)}% por trade" +
                    if (!state.engineReady) " · preparando o motor…" else "",
                color = Fx.Muted, fontSize = 12.sp,
            )
        }
        Spacer(Modifier.height(24.dp))

        state.error?.let { err ->
            SectionCard("Não foi possível analisar", accent = Fx.Sell) {
                Text(err, color = Fx.Text)
                if (state.errorDetail.isNotBlank()) {
                    Spacer(Modifier.height(6.dp))
                    Text(state.errorDetail.take(400), color = Fx.Muted, fontSize = 12.sp)
                }
                Spacer(Modifier.height(10.dp))
                OutlinedButton(onClick = { onDismissError(); onAnalyze() }) {
                    Icon(Icons.Filled.Refresh, null)
                    Spacer(Modifier.width(6.dp))
                    Text("Tentar de novo")
                }
            }
            Spacer(Modifier.height(12.dp))
        }

        if (single) {
            state.asset?.takeIf { it.symbol == state.settings.focusSymbol }?.let { a -> AssetDetail(a) }
        } else {
            state.result?.let { r ->
                ResultBlock(r, state.resultAtMillis, running = state.running)
            }
        }
        Spacer(Modifier.height(24.dp))
    }

    if (picking) {
        AssetPickerSheet(
            title = "Escolha o ativo", selected = setOf(state.settings.focusSymbol), multi = false,
            onDismiss = { picking = false },
            onConfirm = { list ->
                picking = false
                list.firstOrNull()?.let { onSettings(state.settings.copy(homeMode = "asset", focusSymbol = it)) }
            },
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ModeSelector(
    settings: com.fxengine.app.data.AppSettings,
    enabled: Boolean,
    onSettings: (com.fxengine.app.data.AppSettings) -> Unit,
    onPick: () -> Unit,
) {
    val opts = listOf("all" to "Todos os ativos", "asset" to "Um ativo")
    SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
        opts.forEachIndexed { i, (key, label) ->
            SegmentedButton(
                selected = settings.homeMode == key,
                onClick = { onSettings(settings.copy(homeMode = key)) },
                enabled = enabled,
                shape = SegmentedButtonDefaults.itemShape(i, opts.size),
            ) { Text(label) }
        }
    }
    if (settings.homeMode == "asset") {
        Spacer(Modifier.height(10.dp))
        Row(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(Fx.Surface)
                .clickable(enabled = enabled, onClick = onPick).padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text("Ativo", color = Fx.Muted, fontSize = 11.sp)
                Text(settings.focusSymbol, color = Fx.Text, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                Text(com.fxengine.app.data.Catalog.name(settings.focusSymbol), color = Fx.Muted, fontSize = 12.sp)
            }
            Text("Trocar ▾", color = Fx.Blue, fontWeight = FontWeight.SemiBold)
        }
    }
}

fun assetsLabel(a: String) = when (a) {
    "fx" -> "os 28 pares de Forex"
    "metais" -> "os 4 metais"
    "all" -> "Forex e metais (32 ativos)"
    else -> com.fxengine.app.data.Catalog.parseList(a).let { l ->
        if (l.size <= 3) l.joinToString(", ") else "${l.size} ativos escolhidos"
    }
}

@Composable
private fun Header(state: UiState) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text("FX Engine", style = MaterialTheme.typography.headlineMedium, color = Fx.Text)
            Text("Análise gráfica, quantitativa e fundamental", color = Fx.Muted, fontSize = 13.sp)
        }
        val r = state.result
        val (label, color) = when {
            r == null -> "pronto" to Fx.Muted
            r.fxOpen -> "mercado aberto" to Fx.Buy
            else -> "mercado fechado" to Fx.Warn
        }
        Row(
            Modifier.clip(RoundedCornerShape(50)).background(color.copy(alpha = 0.14f))
                .padding(horizontal = 10.dp, vertical = 5.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(Modifier.size(8.dp).clip(CircleShape).background(color))
            Spacer(Modifier.width(6.dp))
            Text(label, color = color, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
        }
    }
}

@Composable
private fun AnalyzeButton(running: Boolean, progress: Int, label: String = "ANALISAR", onClick: () -> Unit) {
    val static = LocalStaticUi.current
    val glow = if (static) 1f else {
        val pulse = rememberInfiniteTransition(label = "pulse")
        pulse.animateFloat(
            initialValue = 1f, targetValue = 1.05f,
            animationSpec = infiniteRepeatable(tween(1400), RepeatMode.Reverse), label = "glow",
        ).value
    }
    val animated by animateFloatAsState(progress / 100f, tween(400), label = "progress")
    Box(Modifier.size(220.dp), contentAlignment = Alignment.Center) {
        if (running) {
            CircularProgressIndicator(
                progress = { animated },
                modifier = Modifier.size(220.dp),
                strokeWidth = 10.dp,
                color = Fx.Blue,
                trackColor = Fx.SurfaceHigh,
            )
        }
        Box(
            Modifier
                .size(180.dp)
                .scale(if (running) 1f else glow)
                .clip(CircleShape)
                .background(
                    Brush.linearGradient(
                        if (running) listOf(Fx.SurfaceHigh, Fx.Surface)
                        else listOf(Color(0xFF4F8CFF), Color(0xFF2B5FD9)),
                    ),
                )
                .border(2.dp, if (running) Fx.Outline else Color(0x664F8CFF), CircleShape)
                .clickable(enabled = !running, onClick = onClick),
            contentAlignment = Alignment.Center,
        ) {
            if (running) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("$progress%", color = Fx.Text, fontSize = 40.sp, fontWeight = FontWeight.Bold)
                    Text("analisando", color = Fx.Muted, fontSize = 13.sp)
                }
            } else {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(Icons.Filled.PlayArrow, null, tint = Color.White, modifier = Modifier.size(56.dp))
                    Text(label, color = Color.White, fontSize = if (label.length > 8) 20.sp else 22.sp,
                        fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
private fun ResultBlock(r: ScanResult, atMillis: Long, running: Boolean) {
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    val static = LocalStaticUi.current
    LaunchedEffect(atMillis, static) {
        while (!static) {
            now = System.currentTimeMillis(); delay(30_000)
        }
    }
    val ageMin = ((now - atMillis) / 60_000).coerceAtLeast(0)
    val stale = ageMin >= 5

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(
            "Análise de ${r.weekday} ${r.timestamp}" + if (ageMin < 1) " · agora" else " · há $ageMin min",
            color = if (stale) Fx.Warn else Fx.Muted, fontSize = 12.sp,
            modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Center,
        )
        if (stale && !running) {
            Text(
                "Os preços já mudaram. Toque em ANALISAR antes de operar.",
                color = Fx.Warn, fontSize = 13.sp, modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Center,
            )
        }
        DecisionBanner(r)
        val o = r.best ?: r.top
        if (o != null) OpportunityDetail(o, referenceOnly = r.best == null)
        SectionCard {
            Text(r.session, color = Fx.Muted, fontSize = 12.sp)
            Text(
                "Apetite a risco: ${r.riskLabel} (${r.riskValue.f()}) · ${r.ranking.size} ativos em ${r.elapsedS.f(0)} s",
                color = Fx.Muted, fontSize = 12.sp,
            )
        }
    }
}

@Composable
private fun DecisionBanner(r: ScanResult) {
    val d = r.decision
    val best = r.best
    val color = when {
        best != null -> Fx.side(best.isBuy)
        else -> Fx.Warn
    }
    Box(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp))
            .background(Brush.horizontalGradient(listOf(color.copy(alpha = 0.28f), color.copy(alpha = 0.10f))))
            .border(1.5.dp, color.copy(alpha = 0.8f), RoundedCornerShape(20.dp))
            .padding(18.dp),
    ) {
        Column {
            Text(
                if (d.execute) "EXECUTAR AGORA" else "NÃO EXECUTAR AGORA",
                color = color, fontWeight = FontWeight.Black, fontSize = 14.sp, letterSpacing = 1.5.sp,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                if (best != null) "${best.side} ${best.symbol} a mercado" else d.headline,
                color = Fx.Text, fontSize = 26.sp, fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.height(4.dp))
            Text(d.reason, color = Fx.Text.copy(alpha = 0.85f), fontSize = 14.sp, lineHeight = 19.sp)
        }
    }
}

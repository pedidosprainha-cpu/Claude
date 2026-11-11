package com.fxengine.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.addPathNodes
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.fxengine.app.data.ExplosionItem
import com.fxengine.app.data.ExplosionModelInfo
import com.fxengine.app.monitor.ExplosionState
import com.fxengine.app.monitor.ExplosionStore
import com.fxengine.app.ui.theme.Fx
import kotlinx.coroutines.launch

/** Lightning bolt (material "bolt" path), drawn here to avoid the extended icon set. */
val BoltIcon: ImageVector = ImageVector.Builder("Bolt", 24.dp, 24.dp, 24f, 24f)
    .addPath(
        pathData = addPathNodes(
            "M11,21h-1l1,-7H7.5c-0.88,0 -0.33,-0.75 -0.31,-0.78C8.48,10.94 10.42,7.54 13.01,3h1l-1,7h3.51" +
                "c0.4,0 0.62,0.19 0.4,0.66C12.97,17.55 11,21 11,21z",
        ),
        fill = SolidColor(Color.White),
    ).build()

fun levelColor(level: String): Color = when (level) {
    "extrema" -> Fx.Sell
    "alta" -> Fx.Warn
    "elevada" -> Fx.Gold
    else -> Fx.Muted
}

private fun pct(p: Double) = "${(p * 100).toInt()}%"

@Composable
fun ExplosionScreen(onOpenAsset: (String) -> Unit = {}) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    val st by ExplosionStore.state.collectAsStateWithLifecycle()
    LaunchedEffect(Unit) { ExplosionStore.restore(ctx) }
    ExplosionContent(st, onScan = { scope.launch { ExplosionStore.scanOnce(ctx) } }, onOpenAsset = onOpenAsset)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ExplosionContent(st: ExplosionState, onScan: () -> Unit, onOpenAsset: (String) -> Unit = {}) {
    var selected by remember { mutableStateOf<ExplosionItem?>(null) }
    var showAll by remember { mutableStateOf(false) }
    val r = st.result
    val alerts = r?.items?.filter { it.alert } ?: emptyList()
    val rest = r?.items?.filter { !it.alert } ?: emptyList()
    LazyColumn(
        Modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
        contentPadding = PaddingValues(bottom = 24.dp),
    ) {
        item {
            ScreenTitle("Explosões", "Probabilidade de um movimento forte do preço nas próximas horas")
        }
        item { ScanCard(st, onScan) }
        if (r != null) {
            item {
                Text(
                    if (alerts.isEmpty()) "Nenhum ativo em alerta agora · ${r.scanned} medidos"
                    else "${alerts.size} em alerta (${r.model?.alertPct ?: 5}% das horas mais explosivas do histórico)",
                    color = if (alerts.isEmpty()) Fx.Muted else Fx.Warn, fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
                )
            }
            items(alerts, key = { "a" + it.symbol }) { x -> ExplosionCard(x, r.model?.dirWfAccConf) { selected = x } }
            if (rest.isNotEmpty()) {
                item {
                    Text("Demais ativos", color = Fx.Muted, fontSize = 13.sp, modifier = Modifier.padding(top = 6.dp))
                }
                items(if (showAll) rest else rest.take(8), key = { "r" + it.symbol }) { x -> CompactRow(x) { selected = x } }
                if (!showAll && rest.size > 8) {
                    item {
                        Text("Ver todos (${rest.size})", color = Fx.Blue, fontSize = 13.sp,
                            modifier = Modifier.clickable { showAll = true }.padding(vertical = 6.dp))
                    }
                }
            }
            r.model?.let { m -> item { ExplosionValidationCard(m) } }
            if (r.dataIssues.isNotEmpty()) {
                item { SectionCard("Falhas de dados", accent = Fx.Warn) { Bullets(r.dataIssues, Fx.Warn, 3) } }
            }
        }
    }
    selected?.let { x ->
        val sheet = rememberModalBottomSheetState(skipPartiallyExpanded = true)
        ModalBottomSheet(onDismissRequest = { selected = null }, sheetState = sheet, containerColor = Fx.Bg) {
            Column(Modifier.verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp)) {
                ExplosionDetail(x, r?.model, onOpenAsset = { selected = null; onOpenAsset(it) })
                Spacer(Modifier.height(32.dp))
            }
        }
    }
}

@Composable
private fun ScanCard(st: ExplosionState, onScan: () -> Unit) {
    SectionCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(42.dp).clip(RoundedCornerShape(12.dp)).background(Fx.Warn.copy(alpha = 0.18f)),
                contentAlignment = Alignment.Center) {
                Icon(BoltIcon, null, tint = Fx.Warn, modifier = Modifier.size(26.dp))
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text("Detector de explosões", color = Fx.Text, fontWeight = FontWeight.Bold)
                Text(
                    st.result?.let { "Leitura ${it.weekday} ${it.timestamp} · próxima às ${it.nextUpdate}" }
                        ?: "Mede compressão, aceleração da volatilidade e horário em 32 ativos",
                    color = Fx.Muted, fontSize = 12.sp,
                )
            }
        }
        Spacer(Modifier.height(12.dp))
        if (st.scanning) {
            LinearProgressIndicator(progress = { st.progress / 100f }, modifier = Modifier.fillMaxWidth(),
                color = Fx.Warn, trackColor = Fx.SurfaceHigh)
            Spacer(Modifier.height(6.dp))
            Text(st.step, color = Fx.Muted, fontSize = 12.sp)
        } else {
            Button(
                onClick = onScan, modifier = Modifier.fillMaxWidth().height(50.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Fx.Warn, contentColor = Color(0xFF1A1200)),
                shape = RoundedCornerShape(14.dp),
            ) {
                Icon(BoltIcon, null, Modifier.size(20.dp))
                Spacer(Modifier.width(6.dp))
                Text(if (st.result == null) "DETECTAR EXPLOSÕES" else "ATUALIZAR", fontWeight = FontWeight.Bold)
            }
        }
        st.error?.let {
            Spacer(Modifier.height(6.dp))
            Text(it, color = Fx.Sell, fontSize = 12.sp)
        }
        Spacer(Modifier.height(8.dp))
        Text(
            "A leitura usa barras H1 fechadas: muda a cada hora cheia. Com o monitor de rompimentos ligado, " +
                "o app avisa quando um ativo entra em alerta alto ou extremo.",
            color = Fx.Muted, fontSize = 11.sp, lineHeight = 15.sp,
        )
    }
}

@Composable
private fun LevelPill(x: ExplosionItem) {
    val c = levelColor(x.level)
    Box(
        Modifier.clip(RoundedCornerShape(6.dp)).background(c.copy(alpha = 0.16f))
            .border(1.dp, c.copy(alpha = 0.7f), RoundedCornerShape(6.dp)).padding(horizontal = 7.dp, vertical = 2.dp),
    ) { Text(x.levelLabel, color = c, fontSize = 11.sp, fontWeight = FontWeight.Bold) }
}

@Composable
private fun ProbBar(p: Double, color: Color) {
    Box(Modifier.fillMaxWidth().height(8.dp).clip(RoundedCornerShape(4.dp)).background(Fx.SurfaceHigh)) {
        Box(Modifier.fillMaxWidth(p.coerceIn(0.0, 1.0).toFloat()).fillMaxHeight().background(color))
    }
}

private fun directionText(x: ExplosionItem): String = when {
    x.pUp == null -> "direção indefinida (confirme antes de entrar)"
    x.pUp >= 0.5 -> "se explodir: alta ${pct(x.pUp)}"
    else -> "se explodir: baixa ${pct(1 - x.pUp)}"
}

/** Probable side of the explosion: arrow, calibrated probability and confidence. */
@Composable
private fun DirectionStrip(x: ExplosionItem, accConf: Double? = null) {
    val up = x.pUp ?: return
    val isUp = up >= 0.5
    val col = if (!x.dirConfident) Fx.Muted else if (isUp) Fx.Buy else Fx.Sell
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(col.copy(alpha = 0.12f))
            .padding(horizontal = 10.dp, vertical = 7.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(if (isUp) "▲" else "▼", color = col, fontSize = 18.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.width(8.dp))
        Column(Modifier.weight(1f)) {
            Text("Se explodir: ${if (isUp) "ALTA" else "BAIXA"} ${pct(x.pSide ?: maxOf(up, 1 - up))}",
                color = if (x.dirConfident) col else Fx.Text, fontWeight = FontWeight.Bold, fontSize = 14.sp)
            Text(if (x.dirConfident) "leitura de alta confiança" + (accConf?.let { " (acerto histórico ≈ ${pct(it)})" } ?: "")
                else "confiança baixa (perto de 50/50)", color = Fx.Muted, fontSize = 11.sp)
        }
    }
}

@Composable
fun ExplosionCard(x: ExplosionItem, accConf: Double? = null, onClick: () -> Unit) {
    val c = levelColor(x.level)
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Fx.Surface),
        border = androidx.compose.foundation.BorderStroke(1.dp, c.copy(alpha = 0.45f)),
    ) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(x.symbol, color = Fx.Text, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.width(8.dp))
                        LevelPill(x)
                    }
                    Text(x.name, color = Fx.Muted, fontSize = 12.sp)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(pct(x.p), color = c, fontSize = 26.sp, fontWeight = FontWeight.Bold)
                    Text("até ${x.until}", color = Fx.Muted, fontSize = 11.sp)
                }
            }
            Spacer(Modifier.height(8.dp))
            ProbBar(x.p, c)
            Spacer(Modifier.height(8.dp))
            if (x.pUp != null) {
                DirectionStrip(x, accConf)
                Spacer(Modifier.height(6.dp))
            }
            Text("Movimento típico ≈ ${x.movePips.f(0)} pips (${x.moveAdr.f(2)}× ADR)",
                color = Fx.Text, fontSize = 13.sp, lineHeight = 17.sp)
            x.drivers.take(2).forEach {
                Text("• $it", color = Fx.Muted, fontSize = 12.sp, lineHeight = 16.sp)
            }
            if (x.events.isNotEmpty()) {
                Spacer(Modifier.height(4.dp))
                Text("Agenda: ${x.events.joinToString(" · ")}", color = Fx.Warn, fontSize = 12.sp)
            }
        }
    }
}

@Composable
private fun CompactRow(x: ExplosionItem, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(Fx.Surface).clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 9.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(x.symbol, color = Fx.Text, fontWeight = FontWeight.SemiBold, modifier = Modifier.width(76.dp))
        Box(Modifier.weight(1f)) { ProbBar(x.p, levelColor(x.level)) }
        Text(pct(x.p), color = levelColor(x.level), fontSize = 13.sp, modifier = Modifier.width(48.dp).padding(start = 8.dp))
    }
}

@Composable
fun ExplosionDetail(x: ExplosionItem, m: ExplosionModelInfo?, onOpenAsset: (String) -> Unit = {}) {
    val ctx = LocalContext.current
    val c = levelColor(x.level)
    val theta = m?.theta ?: 0.5
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SectionCard {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(x.symbol, color = Fx.Text, fontSize = 24.sp, fontWeight = FontWeight.Bold)
                    Text("${x.name} · bid ${x.bid} / ask ${x.ask} · ${x.quoteTime}", color = Fx.Muted, fontSize = 12.sp)
                }
                LevelPill(x)
            }
            Spacer(Modifier.height(10.dp))
            Text(pct(x.p), color = c, fontSize = 40.sp, fontWeight = FontWeight.Bold)
            Text(
                "de chance de o preço andar pelo menos ${(theta * x.adrPips).f(0)} pips (${theta.f(1)}× a amplitude " +
                    "diária média de ${x.adrPips.f(0)} pips) para qualquer lado até ${x.until}. " +
                    "Em horas comuns isso acontece ${m?.baseRate?.let { pct(it) } ?: "≈13%"} das vezes.",
                color = Fx.Text, fontSize = 13.sp, lineHeight = 18.sp,
            )
            Spacer(Modifier.height(8.dp))
            Text("Movimento típico depois de um alerta: ${x.movePips.f(0)} pips · ${directionText(x)}",
                color = Fx.Muted, fontSize = 12.sp)
        }
        if (x.pUp != null) {
            SectionCard("Direção provável") {
                DirectionStrip(x, m?.dirWfAccConf)
                Spacer(Modifier.height(8.dp))
                Text(
                    "Probabilidade calibrada de o preço andar ${((m?.theta ?: 0.5) * x.adrPips).f(0)} pips primeiro para " +
                        "esse lado, se a explosão acontecer. Vem de um segundo modelo (força relativa das moedas e sua " +
                        "aceleração, retornos de 1 h e 4 h, posição no range e nas máximas/mínimas do dia anterior, " +
                        "tendência e horário). No histórico acertou o lado em ${pct(m?.dirWfAcc ?: 0.56)} das " +
                        "explosões (${pct(m?.dirWfAccConf ?: 0.58)} nas leituras de alta confiança).",
                    color = Fx.Muted, fontSize = 12.sp, lineHeight = 16.sp,
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    "É uma vantagem pequena: entrar a mercado nesse lado não deu lucro comprovado depois do spread " +
                        "(${m?.dirTradeWfMeanR?.let { "${it.f(2)}R" } ?: "negativo"} por trade nos períodos de validação). " +
                        "Use como viés, junto com a confirmação das abas Rompimentos e Analisar.",
                    color = Fx.Warn, fontSize = 12.sp, lineHeight = 16.sp,
                )
            }
        }
        if (x.drivers.isNotEmpty()) SectionCard("O que o modelo está vendo") { Bullets(x.drivers, Fx.Warn, 6) }
        if (x.events.isNotEmpty()) {
            SectionCard("Agenda de alto impacto na janela", accent = Fx.Warn) {
                Bullets(x.events, Fx.Warn, 4)
                Text("Eventos não entram no modelo (não há histórico confiável): a chance real tende a ser maior.",
                    color = Fx.Muted, fontSize = 11.sp)
            }
        }
        SectionCard("Como usar") {
            if (x.rangeLow.isNotBlank()) {
                PlanRow("Alcance provável", "${x.rangeLow} – ${x.rangeHigh}", "preço atual ± movimento típico até ${x.until}")
            }
            Bullets(
                listOf(
                    "Gestão de risco: stops menores que ≈${x.movePips.f(0)} pips tendem a ser atingidos nas próximas " +
                        "horas; reduza o lote ou espere.",
                    "Direção: viés modesto (acerto ≈ ${pct(m?.dirWfAcc ?: 0.56)}); prefira entrar só quando a leitura " +
                        "for de alta confiança e outra aba confirmar o mesmo lado.",
                    "Ordens OCO dos dois lados perderam em média no histórico (" +
                        "${m?.bracketWfMeanR?.let { "${it.f(2)}R" } ?: "negativo"} por trade; muitas explosões acionam " +
                        "um lado e voltam): não use como entrada automática.",
                ),
                Fx.Blue, 3,
            )
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Button(onClick = { copyText(ctx, "alerta de explosão", x.orderText) }, modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = Fx.Warn, contentColor = Color(0xFF1A1200))) {
                    Text("Copiar alerta", fontWeight = FontWeight.Bold)
                }
                OutlinedButton(onClick = { shareText(ctx, x.orderText) }, modifier = Modifier.weight(1f)) {
                    Icon(Icons.Filled.Share, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Compartilhar")
                }
            }
        }
        OutlinedButton(onClick = { onOpenAsset(x.symbol) }, modifier = Modifier.fillMaxWidth()) {
            Text("Análise completa de ${x.symbol}")
        }
    }
}

@Composable
fun ExplosionValidationCard(m: ExplosionModelInfo) {
    SectionCard("Precisão validada no histórico") {
        Text(
            "${"%,d".format(m.bars).replace(',', '.')} horas de ${m.instruments} ativos (${m.period}). Explosão = " +
                "andar ≥ ${m.theta.f(1)}× a amplitude diária média em até ${m.horizon} h. Teste final em meses que o " +
                "modelo não viu (${m.testPeriod}):",
            color = Fx.Muted, fontSize = 12.sp, lineHeight = 16.sp,
        )
        Spacer(Modifier.height(8.dp))
        Row(Modifier.fillMaxWidth()) {
            Column(Modifier.weight(1f)) {
                Text("Hora qualquer", color = Fx.Muted, fontSize = 12.sp)
                Text(pct(m.baseRate), color = Fx.Text, fontWeight = FontWeight.Bold, fontSize = 20.sp)
                Text("explodem", color = Fx.Muted, fontSize = 12.sp)
            }
            Column(Modifier.weight(1f)) {
                Text("Com alerta do app", color = Fx.Muted, fontSize = 12.sp)
                Text(pct(m.testPrecision), color = Fx.Buy, fontWeight = FontWeight.Bold, fontSize = 20.sp)
                Text("${m.testLift.f(1)}× mais · ${m.testAlerts} alertas", color = Fx.Muted, fontSize = 12.sp)
            }
            Column(Modifier.weight(1f)) {
                Text("Nível extremo", color = Fx.Muted, fontSize = 12.sp)
                Text(pct(m.testPrecisionExtreme), color = Fx.Buy, fontWeight = FontWeight.Bold, fontSize = 20.sp)
                Text("1% mais fortes", color = Fx.Muted, fontSize = 12.sp)
            }
        }
        Spacer(Modifier.height(6.dp))
        Text(
            "Comparação no mesmo filtro: só o horário acerta ${pct(m.testPrecisionSeasonal)}; o squeeze clássico " +
                "(Bollinger dentro de Keltner) acerta ${pct(m.squeezePrecision)}, menos que uma hora qualquer.",
            color = Fx.Muted, fontSize = 12.sp, lineHeight = 16.sp,
        )
        Spacer(Modifier.height(8.dp))
        Text(
            "Walk-forward: alertas acertaram de ${m.wfLiftMin.f(1)}× a taxa base para cima em todos os períodos " +
                "(média ${m.wfLiftMean.f(1)}×). Movimento mediano após alerta: ${m.testMoveAlert.f(2)}× ADR, contra " +
                "${m.testMoveAll.f(2)}× numa hora qualquer. AUC ${m.testAuc.f(2)} (só o horário: ${m.testAucSeasonal.f(2)}).",
            color = Fx.Muted, fontSize = 12.sp, lineHeight = 16.sp,
        )
        Spacer(Modifier.height(6.dp))
        Text(
            "Os ativos explodem juntos (abertura de Nova York concentra os alertas), então o acerto varia muito de " +
                "uma hora para outra; os números acima são a média de muitas horas. " +
                (if (m.validated) "Detecção validada pela regra definida antes do teste. " else "Detecção NÃO validada pela regra. ") +
                (if (m.directionUseful) "A direção tem algum poder preditivo (AUC ${m.directionAuc.f(2)})."
                else "Direção: o lado previsto saiu primeiro em ${pct(m.dirWfAcc)} das explosões nos períodos de " +
                    "validação (mínimo ${pct(m.dirWfAccMin)}; ${pct(m.dirWfAccConf)} nas leituras de alta confiança; " +
                    "teste ${pct(m.dirTestAcc)} e ${pct(m.dirTestAccConf)}), mas não passou na regra de validação " +
                    "(AUC ${m.directionAuc.f(2)} < 0,55) e entrar a mercado nesse lado não deu lucro comprovado.") +
                (if (m.bracketValidated) " Ordens OCO tiveram expectativa positiva validada."
                else " Ordens OCO dos dois lados perderam dinheiro depois do spread: use o alerta para risco e atenção, " +
                    "não como entrada automática."),
            color = Fx.Warn, fontSize = 12.sp, lineHeight = 16.sp,
        )
    }
}

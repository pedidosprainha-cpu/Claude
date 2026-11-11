package com.fxengine.app.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.widget.Toast
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.fxengine.app.data.Opportunity
import com.fxengine.app.ui.theme.Fx
import com.fxengine.app.ui.theme.Mono
import java.util.Locale

private val PT_BR: Locale = Locale.forLanguageTag("pt-BR")

fun Double.f(nd: Int = 2): String = String.format(PT_BR, "%.${nd}f", this)

fun money(v: Double): String = "US$ " + String.format(PT_BR, "%,.2f", v)

@Composable
fun SectionCard(
    title: String? = null,
    modifier: Modifier = Modifier,
    accent: Color? = null,
    content: @Composable () -> Unit,
) {
    Card(
        modifier = modifier.fillMaxWidth().animateContentSize(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = Fx.Surface),
        border = accent?.let { androidx.compose.foundation.BorderStroke(1.5.dp, it.copy(alpha = 0.6f)) },
    ) {
        Column(Modifier.padding(16.dp)) {
            if (title != null) {
                Text(title, style = MaterialTheme.typography.titleMedium, color = Fx.Text)
                Spacer(Modifier.height(10.dp))
            }
            content()
        }
    }
}

@Composable
fun SideChip(side: String, isBuy: Boolean, big: Boolean = false) {
    val c = Fx.side(isBuy)
    Box(
        Modifier
            .clip(RoundedCornerShape(50))
            .background(c.copy(alpha = 0.16f))
            .border(1.dp, c.copy(alpha = 0.7f), RoundedCornerShape(50))
            .padding(horizontal = if (big) 14.dp else 10.dp, vertical = if (big) 6.dp else 3.dp),
    ) {
        Text(
            (if (isBuy) "▲ " else "▼ ") + side,
            color = c, fontWeight = FontWeight.Bold, fontSize = if (big) 15.sp else 12.sp,
        )
    }
}

@Composable
fun GradeBadge(grade: String, score: Double, size: Int = 54) {
    val c = Fx.grade(grade)
    Box(
        Modifier.size(size.dp).clip(CircleShape).background(c.copy(alpha = 0.15f))
            .border(2.dp, c, CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(grade, color = c, fontWeight = FontWeight.Bold, fontSize = (size / 3).sp)
            Text("${score.toInt()}", color = Fx.Muted, fontSize = (size / 5).sp)
        }
    }
}

@Composable
fun PlanRow(label: String, value: String, sub: String = "", valueColor: Color = Fx.Text) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 7.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label, color = Fx.Muted, modifier = Modifier.width(96.dp), fontSize = 14.sp)
        Column(Modifier.weight(1f)) {
            Text(value, style = Mono, color = valueColor)
            if (sub.isNotBlank()) Text(sub, color = Fx.Muted, fontSize = 12.sp, lineHeight = 15.sp)
        }
    }
}

@Composable
fun Bullets(items: List<String>, dot: Color, initial: Int = 4) {
    var expanded by remember(items) { mutableStateOf(false) }
    val shown = if (expanded) items else items.take(initial)
    Column {
        shown.forEach { t ->
            Row(Modifier.padding(vertical = 4.dp)) {
                Box(Modifier.padding(top = 7.dp).size(7.dp).clip(CircleShape).background(dot))
                Spacer(Modifier.width(10.dp))
                Text(t, color = Fx.Text, fontSize = 14.sp, lineHeight = 19.sp)
            }
        }
        if (items.size > initial) {
            TextButton(onClick = { expanded = !expanded }) {
                Text(if (expanded) "Mostrar menos" else "Ver mais ${items.size - initial}")
            }
        }
    }
}

@Composable
fun ScoreBar(value: Double, max: Double = 100.0, modifier: Modifier = Modifier, centered: Boolean = true) {
    // Centered bar: negative to the left (red), positive to the right (green).
    val frac = (kotlin.math.abs(value) / max).coerceIn(0.0, 1.0).toFloat()
    val c = if (value >= 0) Fx.Buy else Fx.Sell
    Box(modifier.height(8.dp).fillMaxWidth().clip(RoundedCornerShape(4.dp)).background(Fx.SurfaceHigh)) {
        if (centered) {
            Row(Modifier.fillMaxWidth()) {
                Box(Modifier.weight(1f)) {
                    if (value < 0) Box(Modifier.align(Alignment.CenterEnd).fillMaxWidth(frac).height(8.dp).background(c))
                }
                Box(Modifier.weight(1f)) {
                    if (value >= 0) Box(Modifier.fillMaxWidth(frac).height(8.dp).background(c))
                }
            }
        } else {
            Box(Modifier.fillMaxWidth(frac).height(8.dp).background(c))
        }
    }
}

fun copyText(context: Context, label: String, text: String) {
    val cm = context.getSystemService(ClipboardManager::class.java)
    cm?.setPrimaryClip(ClipData.newPlainText(label, text))
    Toast.makeText(context, "Ordem copiada", Toast.LENGTH_SHORT).show()
}

fun shareText(context: Context, text: String) {
    val i = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(Intent.EXTRA_TEXT, text)
    }
    context.startActivity(Intent.createChooser(i, "Compartilhar análise"))
}

/** Full trade card: header, plan, probability, reasons, risks and actions. */
@Composable
fun OpportunityDetail(o: Opportunity, referenceOnly: Boolean, showActions: Boolean = true) {
    val ctx = LocalContext.current
    val sideColor = Fx.side(o.isBuy)
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SectionCard(accent = if (referenceOnly) Fx.Outline else sideColor) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(o.symbol, style = MaterialTheme.typography.headlineMedium, color = Fx.Text)
                    Text(o.name + " · " + o.regime, color = Fx.Muted, fontSize = 13.sp)
                    Spacer(Modifier.height(6.dp))
                    SideChip(o.side, o.isBuy, big = true)
                }
                GradeBadge(o.grade, o.score, 62)
            }
            if (referenceOnly) {
                Spacer(Modifier.height(10.dp))
                Text(
                    "Somente referência — não executar: ${o.status.replaceFirstChar { it.lowercase() }}",
                    color = Fx.Warn, fontSize = 13.sp,
                )
            }
            Spacer(Modifier.height(8.dp))
            HorizontalDivider(color = Fx.Outline)
            Spacer(Modifier.height(4.dp))
            PlanRow("Entrada", o.entry, (if (o.isBuy) "compra no ask" else "venda no bid") + " · bid ${o.bid} / ask ${o.ask} · ${o.quoteTime}")
            PlanRow("Stop", o.sl, "${o.slPips.f(1)} pips · ${o.slBasis}", Fx.Sell)
            val timeStop = if (o.horizonH > 0) " · ainda aberto após ${o.horizonH} h: encerrar a mercado" else ""
            when (o.exitKind) {
                "trail" -> {
                    PlanRow("+1R", o.tp1, "${o.tp1Pips.f(1)} pips · a partir daqui o stop vira móvel", Fx.Buy)
                    PlanRow("Saída", "stop móvel", o.exitRule + timeStop)
                }
                "partial" -> {
                    PlanRow("Alvo 1", o.tp1, "${(o.tp1Pips).f(1)} pips · ${o.rr1.f()}R · realizar 50% e stop na entrada", Fx.Buy)
                    PlanRow("Alvo 2", o.tp2, "${(o.tp2Pips).f(1)} pips · ${o.rr2.f()}R", Fx.Buy)
                }
                else -> PlanRow("Alvo", o.tp1, "${o.tp1Pips.f(1)} pips · ${o.rr1.f()}R · ${o.exitRule}$timeStop", Fx.Buy)
            }
            PlanRow("Lote", o.lots.f(2), "risco ${money(o.riskAmount)} · spread ${o.spreadPips.f(1)} pips")
            o.edge?.let { e ->
                val ev = "${if (e.expR >= 0) "+" else ""}${e.expR.f()}R"
                if (e.fromModel) {
                    PlanRow(
                        "Prob. de lucro", "${(e.p * 100).toInt()}%",
                        "expectativa $ev por trade em sinais parecidos (modelo histórico, ${"%,d".format(e.n).replace(',', '.')} " +
                            "barras de 32 ativos)" + (if (e.passes) " · entre os melhores sinais" else " · fora dos melhores sinais"),
                        if (e.passes && e.expR >= 0) Fx.Buy else Fx.Warn,
                    )
                } else {
                    PlanRow(
                        "Prob. TP1", "${(e.p * 100).toInt()}%",
                        "${e.n} sinais parecidos em 1 ano · expectativa $ev por trade",
                        if (e.expR >= 0) Fx.Buy else Fx.Warn,
                    )
                }
            }
            Spacer(Modifier.height(4.dp))
            Text("Invalidação: ${o.invalidation}", color = Fx.Muted, fontSize = 12.sp, lineHeight = 16.sp)
            if (showActions && !referenceOnly) {
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Button(
                        onClick = { copyText(ctx, "ordem", o.orderText) },
                        colors = ButtonDefaults.buttonColors(containerColor = sideColor),
                        modifier = Modifier.weight(1f),
                    ) { Text("Copiar ordem", fontWeight = FontWeight.Bold) }
                    OutlinedButton(onClick = { shareText(ctx, o.orderText) }, modifier = Modifier.weight(1f)) {
                        Icon(Icons.Filled.Share, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("Compartilhar")
                    }
                }
            }
        }
        if (o.reasons.isNotEmpty()) {
            SectionCard("Por que") { Bullets(o.reasons, Fx.Buy) }
        }
        if (o.warnings.isNotEmpty()) {
            SectionCard("Riscos e atenção") { Bullets(o.warnings, Fx.Warn, 3) }
        }
        SectionCard("Como o score foi formado") {
            o.components.forEach { c ->
                Row(Modifier.fillMaxWidth().padding(vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(c.name, color = Fx.Muted, fontSize = 13.sp, modifier = Modifier.width(92.dp))
                    ScoreBar(c.value, modifier = Modifier.weight(1f))
                    Text(
                        (if (c.value > 0) "+" else "") + c.value.toInt(),
                        color = Fx.Text, fontSize = 13.sp, modifier = Modifier.width(44.dp).padding(start = 8.dp),
                    )
                }
            }
            Spacer(Modifier.height(6.dp))
            Text(
                o.multipliers.joinToString("  ·  ") { "${it.name} ×${it.value.f()}" },
                color = Fx.Muted, fontSize = 12.sp, lineHeight = 16.sp,
            )
        }
    }
}

@Composable
fun OpportunityRow(rank: Int, o: Opportunity, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Fx.Surface),
    ) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("$rank", color = Fx.Muted, fontWeight = FontWeight.Bold, modifier = Modifier.width(26.dp))
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(o.symbol, color = Fx.Text, fontWeight = FontWeight.Bold, fontSize = 17.sp)
                    Spacer(Modifier.width(8.dp))
                    SideChip(o.side, o.isBuy)
                }
                Spacer(Modifier.height(4.dp))
                Text(
                    (if (o.executable) "✔ " else "✖ ") + o.status,
                    color = if (o.executable) Fx.Buy else Fx.Muted, fontSize = 12.sp,
                    maxLines = 1, overflow = TextOverflow.Ellipsis,
                )
            }
            GradeBadge(o.grade, o.score, 46)
        }
    }
}

/** How the main analysis performed on the historical replay (research/train_signal_model.py). */
@Composable
fun SignalModelCard(m: com.fxengine.app.data.SignalModelInfo) {
    fun r(v: Double) = "${if (v >= 0) "+" else ""}${v.f(2)}R"
    SectionCard("Validação histórica da análise") {
        Text(
            "${"%,d".format(m.bars).replace(',', '.')} horas de mercado de ${m.instruments} ativos (${m.period}) " +
                "reconstituídas sem olhar o futuro, entrada a mercado com spread, avaliadas em meses que o modelo " +
                "não viu. Plano: ${m.geometry}.",
            color = Fx.Muted, fontSize = 12.sp, lineHeight = 16.sp,
        )
        Spacer(Modifier.height(8.dp))
        Row(Modifier.fillMaxWidth()) {
            Column(Modifier.weight(1f)) {
                Text("Antes", color = Fx.Muted, fontSize = 12.sp)
                Text("${r(m.oldTestMeanR ?: m.baselineTestMeanR)} por trade", color = Fx.Sell, fontWeight = FontWeight.Bold)
                m.oldTestWin?.let {
                    Text("${(it * 100).toInt()}% no lucro", color = Fx.Muted, fontSize = 12.sp)
                }
            }
            Column(Modifier.weight(1f)) {
                Text("Agora (${m.filterPct}% melhores)", color = Fx.Muted, fontSize = 12.sp)
                Text("${r(m.testMeanR)} por trade", color = if (m.testMeanR >= 0) Fx.Buy else Fx.Warn,
                    fontWeight = FontWeight.Bold)
                Text("${(m.testWin * 100).toInt()}% no lucro · ${m.testN} trades", color = Fx.Muted, fontSize = 12.sp)
            }
        }
        Text("Teste final (meses que o modelo não viu): ${m.testPeriod}", color = Fx.Muted, fontSize = 11.sp)
        Spacer(Modifier.height(8.dp))
        Text(
            "Em vários períodos (walk-forward): média ${r(m.wfMeanR)} por trade, pior período ${r(m.wfWorstR)}, " +
                "${(m.wfPosShare * 100).toInt()}% dos períodos positivos. Probabilidade prevista ${(m.pMean * 100).toInt()}% " +
                "× real ${(m.winReal * 100).toInt()}% no teste.",
            color = Fx.Muted, fontSize = 12.sp, lineHeight = 16.sp,
        )
        Spacer(Modifier.height(6.dp))
        Text(
            if (m.validated) {
                "Resultado positivo validado em vários períodos e no teste final, simulado com spreads típicos. " +
                    "Passado não garante futuro: use risco pequeno."
            } else {
                "Nenhuma regra de entrada a mercado teve vantagem comprovada em todos os períodos depois do spread. " +
                    "A análise agora evita os piores trades e mostra a probabilidade real, mas a expectativa dos " +
                    "melhores sinais fica perto de zero. Use risco pequeno."
            },
            color = Fx.Warn, fontSize = 12.sp, lineHeight = 16.sp,
        )
    }
}

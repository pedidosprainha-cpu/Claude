@file:OptIn(ExperimentalMaterial3Api::class)

package com.fxengine.app.ui

import androidx.compose.foundation.background
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.fxengine.app.data.AssetResult
import com.fxengine.app.data.BreakoutItem
import com.fxengine.app.ui.theme.Fx

/** Everything the engine knows about one instrument, top-down: decision, chart, breakouts, layers. */
@Composable
fun AssetDetail(r: AssetResult) {
    var tf by remember { mutableStateOf("H1") }
    var selectedBk by remember { mutableStateOf<BreakoutItem?>(null) }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        // header
        SectionCard {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(r.symbol, color = Fx.Text, fontSize = 26.sp, fontWeight = FontWeight.Bold)
                    Text(r.name, color = Fx.Muted, fontSize = 13.sp)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(r.mid, color = Fx.Text, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                    Text("bid ${r.bid} · ask ${r.ask}", color = Fx.Muted, fontSize = 11.sp)
                    Text("spread ${r.spreadPips.f(1)} pips · ${r.quoteTime}", color = Fx.Muted, fontSize = 11.sp)
                }
            }
            Spacer(Modifier.height(6.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                val c = if (r.tradeable) Fx.Buy else Fx.Warn
                Box(Modifier.size(8.dp).clip(CircleShape).background(c))
                Spacer(Modifier.width(6.dp))
                Text((if (r.tradeable) "mercado aberto · " else "mercado fechado/sem cotação ao vivo · ") + r.session,
                    color = Fx.Muted, fontSize = 12.sp)
            }
        }

        // decision
        val o = r.opportunity
        val col = if (r.decision.execute && o != null) Fx.side(o.isBuy) else Fx.Warn
        Box(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(col.copy(alpha = 0.15f)).padding(16.dp),
        ) {
            Column {
                Text(if (r.decision.execute) "EXECUTAR AGORA" else "NÃO EXECUTAR AGORA", color = col,
                    fontWeight = FontWeight.Black, fontSize = 13.sp, letterSpacing = 1.5.sp)
                Text(r.decision.headline, color = Fx.Text, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                Text(r.decision.reason, color = Fx.Text.copy(alpha = 0.85f), fontSize = 13.sp, lineHeight = 18.sp)
            }
        }

        // chart
        SectionCard("Gráfico") {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(tf == "H1", { tf = "H1" }, label = { Text("H1 · 5 dias") })
                FilterChip(tf == "M15", { tf = "M15" }, label = { Text("M15 · 24h") })
            }
            Spacer(Modifier.height(6.dp))
            val bars = if (tf == "H1") r.chartH1 else r.chartM15
            if (bars != null && bars.size > 1) {
                CandleChart(bars, r.digits, r.overlayLevels, r.plan, intraday = tf == "M15")
                Text(
                    "Tracejado = suportes/resistências do motor" +
                        if (r.plan?.show == true) " · linhas do plano: entrada (azul), stop (vermelho), alvos (verde)" else "",
                    color = Fx.Muted, fontSize = 11.sp,
                )
            } else {
                Text("Sem dados de gráfico.", color = Fx.Muted)
            }
        }

        if (o != null) OpportunityDetail(o, referenceOnly = !o.executable)
        r.signalModel?.let { SignalModelCard(it) }

        // breakouts of this instrument
        SectionCard("Rompimentos neste ativo") {
            if (r.breakouts.isEmpty()) {
                Text("Nenhum rompimento em M15/H1 neste momento.", color = Fx.Muted, fontSize = 13.sp)
            }
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                r.breakouts.forEach { b -> BreakoutCard(b) { selectedBk = b } }
            }
        }

        // multi-timeframe table
        SectionCard("Leitura por timeframe") {
            Row(Modifier.fillMaxWidth()) {
                listOf("TF" to 0.6f, "viés" to 1f, "RSI" to 0.7f, "ADX" to 0.7f, "médias" to 1f, "estrutura" to 1.1f).forEach { (h, w) ->
                    Text(h, color = Fx.Muted, fontSize = 11.sp, modifier = Modifier.weight(w))
                }
            }
            r.mtf.forEach { m ->
                Row(Modifier.fillMaxWidth().padding(vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(m.tf, color = Fx.Text, fontWeight = FontWeight.Bold, fontSize = 13.sp, modifier = Modifier.weight(0.6f))
                    Text(
                        (if (m.score > 0.1) "▲ " else if (m.score < -0.1) "▼ " else "• ") + "${(m.score * 100).toInt()}",
                        color = if (m.score > 0.1) Fx.Buy else if (m.score < -0.1) Fx.Sell else Fx.Muted,
                        fontSize = 13.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f),
                    )
                    Text("${m.rsi.toInt()}", color = Fx.Text, fontSize = 13.sp, modifier = Modifier.weight(0.7f))
                    Text("${m.adx.toInt()}", color = Fx.Text, fontSize = 13.sp, modifier = Modifier.weight(0.7f))
                    Text(m.emas, color = Fx.Text, fontSize = 13.sp, modifier = Modifier.weight(1f))
                    Text(m.structure + if (m.bos != 0) " BOS" else "", color = Fx.Text, fontSize = 13.sp,
                        modifier = Modifier.weight(1.1f))
                }
                val extras = m.candles + listOfNotNull(
                    if (m.squeezeOn) "volatilidade comprimida" else null,
                    if (m.squeezeFired != 0) "squeeze liberado ${if (m.squeezeFired > 0) "para cima" else "para baixo"}" else null,
                    m.divergence.takeIf { it.isNotBlank() },
                )
                if (extras.isNotEmpty()) Text("   " + extras.joinToString(" · "), color = Fx.Muted, fontSize = 11.sp)
            }
        }

        // levels + daily
        SectionCard("Níveis-chave") {
            r.levels.sortedByDescending { it.value }.forEach { lv ->
                Row(Modifier.fillMaxWidth().padding(vertical = 3.dp)) {
                    Text(lv.price, color = if (lv.side == "resistência") Fx.Sell else Fx.Buy,
                        fontWeight = FontWeight.Bold, fontSize = 14.sp, modifier = Modifier.width(92.dp))
                    Column(Modifier.weight(1f)) {
                        Text("${lv.side} · ${lv.distPips.f(1)} pips (${lv.distAtr.f(1)} ATR H1) · força ${lv.strength.f(1)}",
                            color = Fx.Text, fontSize = 12.sp)
                        Text(lv.labels, color = Fx.Muted, fontSize = 11.sp, maxLines = 2)
                    }
                }
            }
            r.daily?.let { d ->
                Spacer(Modifier.height(8.dp))
                Text("Amplitude diária média (ADR): ${d.adrPips.f(1)} pips · hoje ${d.todayPips.f(1)} pips " +
                    "(${d.adrUsedPct.toInt()}% usado)", color = Fx.Text, fontSize = 13.sp)
                Text("Ontem: máx. ${d.prevHigh} · mín. ${d.prevLow} · fech. ${d.prevClose} · abertura de hoje ${d.dayOpen}",
                    color = Fx.Muted, fontSize = 12.sp)
                if (d.weekHigh.isNotBlank()) {
                    Text("Semana anterior: máx. ${d.weekHigh} · mín. ${d.weekLow}", color = Fx.Muted, fontSize = 12.sp)
                }
                Text("Pivôs: " + d.pivots.joinToString("  ") { (k, v) -> "$k $v" }, color = Fx.Muted, fontSize = 12.sp)
            }
        }

        // quant + strength + fundamentals
        SectionCard("Quant, força e fundamentos") {
            r.quant?.let { q ->
                Text("Regime: ${q.regime} · Hurst ${q.hurst.f()} · razão de variância ${q.vr.f()} · eficiência ${q.er.f()}",
                    color = Fx.Text, fontSize = 13.sp)
                Text("Momentum (séries) ${q.tsmom.f()} · distância da média ${q.mrZ.f(1)}σ · volatilidade " +
                    "${q.volAnn.f(1)}% a.a. (percentil ${q.volPct.toInt()})", color = Fx.Muted, fontSize = 12.sp)
                Spacer(Modifier.height(8.dp))
            }
            r.strength.forEach { (c, z, rank) ->
                Row(Modifier.fillMaxWidth().padding(vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(c, color = Fx.Text, fontWeight = FontWeight.Bold, modifier = Modifier.width(48.dp))
                    ScoreBar(z, max = 2.0, modifier = Modifier.weight(1f))
                    Text("${if (z > 0) "+" else ""}${z.f()}" + (rank?.let { " (${it}º)" } ?: ""), color = Fx.Text,
                        fontSize = 12.sp, modifier = Modifier.width(84.dp).padding(start = 8.dp))
                }
            }
            Spacer(Modifier.height(8.dp))
            Text("Fundamental: ${if (r.fundScore > 0) "+" else ""}${r.fundScore.toInt()} (positivo favorece alta de ${r.symbol})",
                color = Fx.Text, fontSize = 13.sp)
            r.fundComponents.forEach { c ->
                Row(Modifier.fillMaxWidth().padding(vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(c.name, color = Fx.Muted, fontSize = 12.sp, modifier = Modifier.width(110.dp))
                    ScoreBar(c.value, max = 1.0, modifier = Modifier.weight(1f))
                    Text("${if (c.value > 0) "+" else ""}${c.value.f()}", color = Fx.Text, fontSize = 12.sp,
                        modifier = Modifier.width(48.dp).padding(start = 8.dp))
                }
                if (c.fact.isNotBlank()) Text("   ${c.fact}", color = Fx.Muted, fontSize = 11.sp)
            }
            if (r.rates.isNotEmpty()) {
                Text("Juros: " + r.rates.joinToString(" · ") { "${it.ccy} ${it.rate.f()}%" }, color = Fx.Muted, fontSize = 12.sp)
            }
            if (r.cot.isNotEmpty()) {
                Text("COT: " + r.cot.joinToString(" · ") { "${it.asset} ${it.netPct.toInt()}% OI [${it.index.toInt()}]" },
                    color = Fx.Muted, fontSize = 12.sp)
            }
        }

        SectionCard("Agenda das moedas deste ativo (48h)") {
            if (r.events.isEmpty()) Text("Nada relevante na agenda.", color = Fx.Muted, fontSize = 13.sp)
            r.events.forEach { e ->
                Column(Modifier.padding(vertical = 4.dp)) {
                    Row {
                        Text(e.ccy, color = if (e.impact == "High") Fx.Sell else Fx.Gold, fontWeight = FontWeight.Bold,
                            modifier = Modifier.width(48.dp))
                        Text(e.title, color = Fx.Text, fontSize = 13.sp, modifier = Modifier.weight(1f))
                    }
                    Text("${e.whenLocal} · ${e.inText}" + (if (e.forecast.isNotBlank()) " · proj ${e.forecast}" else ""),
                        color = Fx.Muted, fontSize = 11.sp, modifier = Modifier.padding(start = 48.dp))
                }
            }
        }

        if (r.headlines.isNotEmpty()) {
            SectionCard("Manchetes sobre estas moedas") {
                r.headlines.forEach { h ->
                    Column(Modifier.padding(vertical = 4.dp)) {
                        Text((if (h.tone > 0) "▲ " else if (h.tone < 0) "▼ " else "") + h.title, color = Fx.Text,
                            fontSize = 13.sp, lineHeight = 17.sp)
                        Text(h.whenLocal, color = Fx.Muted, fontSize = 11.sp)
                    }
                }
            }
        }
        if (r.dataIssues.isNotEmpty()) {
            SectionCard("Falhas de dados", accent = Fx.Warn) { Bullets(r.dataIssues, Fx.Warn, 4) }
        }
        Text("Análise de ${r.weekday} ${r.timestamp} em ${r.elapsedS.f(1)} s", color = Fx.Muted, fontSize = 11.sp)
    }

    selectedBk?.let { b ->
        val sheet = rememberModalBottomSheetState(skipPartiallyExpanded = true)
        ModalBottomSheet(onDismissRequest = { selectedBk = null }, sheetState = sheet, containerColor = Fx.Bg) {
            Column(Modifier.verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp)) {
                BreakoutDetail(b)
                Spacer(Modifier.height(32.dp))
            }
        }
    }
}

package com.fxintel.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.fxintel.app.data.Candidate

fun statusLabel(s: String?) = when (s) {
    "SINAL" -> "Sinal"
    "ELEGIVEL" -> "Elegível"
    "OBSERVACAO" -> "Observação"
    "AGUARDANDO_GATILHO" -> "Aguardando gatilho"
    else -> "—"
}

/** Ranking das 5 melhores oportunidades por nota (0–100), com status explícito de cada uma. */
@Composable
fun RankingCard(items: List<Candidate>, analysisId: String, onSelect: (Candidate) -> Unit, onPaper: ((String) -> Unit)?) {
    val fx = LocalFx.current
    SectionCard("Ranking — 5 melhores oportunidades", trailing = { Text("por nota 0–100", fontSize = 11.sp, color = fx.muted) }) {
        if (items.isEmpty()) {
            Text("Sem dados suficientes para montar o ranking.", fontSize = 12.sp, color = fx.muted)
            return@SectionCard
        }
        items.forEachIndexed { idx, c ->
            var open by remember(analysisId, c.instrument, c.direction) { mutableStateOf(false) }
            val (stBg, stFg) = when (c.status) {
                "SINAL", "ELEGIVEL" -> fx.goodBg to MaterialTheme.colorScheme.onSurface
                "OBSERVACAO" -> fx.warnBg to MaterialTheme.colorScheme.onSurface
                else -> MaterialTheme.colorScheme.surfaceVariant to MaterialTheme.colorScheme.onSurfaceVariant
            }
            Column(Modifier.fillMaxWidth().clickable { open = !open; if (open) onSelect(c) }.padding(vertical = 8.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("${c.rank ?: idx + 1}", Modifier.width(26.dp), fontWeight = FontWeight.ExtraBold, fontSize = 18.sp,
                        color = MaterialTheme.colorScheme.primary)
                    Text(c.direction, Modifier.clip(RoundedCornerShape(6.dp))
                        .background(if (c.direction == "BUY") fx.buy else fx.sell).padding(horizontal = 6.dp, vertical = 2.dp),
                        color = Color.White, fontWeight = FontWeight.Bold, fontSize = 11.sp)
                    Spacer(Modifier.width(8.dp))
                    Column(Modifier.weight(1f)) {
                        Text(c.instrument, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                        Text(c.setup_name, fontSize = 11.sp, color = fx.muted, maxLines = 1)
                    }
                    Column(horizontalAlignment = Alignment.End) {
                        Text(f(c.score, 0), fontWeight = FontWeight.ExtraBold, fontSize = 22.sp)
                        Text("nota", fontSize = 10.sp, color = fx.muted)
                    }
                }
                // barra da nota
                Box(Modifier.padding(start = 26.dp, top = 4.dp).fillMaxWidth().height(6.dp).clip(RoundedCornerShape(3.dp))
                    .background(MaterialTheme.colorScheme.surfaceVariant)) {
                    Box(Modifier.fillMaxWidth((c.score / 100.0).toFloat().coerceIn(0f, 1f)).height(6.dp)
                        .background(MaterialTheme.colorScheme.primary))
                }
                Row(Modifier.padding(start = 26.dp, top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                    Chip(statusLabel(c.status), stBg, stFg)
                    Spacer(Modifier.width(6.dp))
                    Text("EV ${f(c.expected_value_r, 2)}R · p ${pct(c.probability.calibrated_p)} · R:R ${f(c.risk_reward.rr_tp1)}",
                        fontSize = 11.sp, color = fx.muted)
                }
                if (c.status != "SINAL" && c.blocked_by.isNotEmpty())
                    Text("Bloqueios: " + c.blocked_by.joinToString { it.replace('_', ' ') }, fontSize = 11.sp, color = fx.muted,
                        modifier = Modifier.padding(start = 26.dp, top = 2.dp))
                if (open) {
                    Spacer(Modifier.height(8.dp))
                    SignalDetails(c, c.status == "SINAL", if (c.status == "SINAL") onPaper else null)
                } else Text("Toque para ver entrada, stop, alvos e justificativas", fontSize = 10.sp, color = fx.muted,
                    textAlign = TextAlign.Start, modifier = Modifier.padding(start = 26.dp, top = 2.dp))
            }
            if (idx < items.size - 1) HorizontalDivider(color = fx.grid)
        }
        Text("A nota combina valor esperado (45%), técnica (20%), fundamentos (15%), regime (10%) e custo (10%). " +
            "Somente itens com status \"Sinal\" passaram em todos os portões de qualidade e risco.",
            fontSize = 10.sp, color = fx.muted, modifier = Modifier.padding(top = 8.dp))
    }
}

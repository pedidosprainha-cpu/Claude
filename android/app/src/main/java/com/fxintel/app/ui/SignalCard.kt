package com.fxintel.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.fxintel.app.data.Candidate

/** Cartão completo de um sinal/observação, com a estrutura obrigatória do sinal operacional. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SignalDetails(c: Candidate, isSignal: Boolean, onPaper: ((String) -> Unit)? = null) {
    val fx = LocalFx.current
    val d = if (c.instrument.endsWith("JPY")) 3 else if (c.instrument == "XAUUSD") 2 else if (c.instrument == "XAGUSD") 3 else 5
    val q = c.reference_quote
    Column {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(c.direction, Modifier.clip(RoundedCornerShape(10.dp))
                .background(if (c.direction == "BUY") fx.buy else fx.sell).padding(horizontal = 12.dp, vertical = 4.dp),
                color = Color.White, fontWeight = FontWeight.ExtraBold, fontSize = 20.sp)
            Spacer(Modifier.width(10.dp))
            Column {
                Text(c.instrument, fontWeight = FontWeight.Bold, fontSize = 20.sp)
                Text(c.setup_name, fontSize = 12.sp, color = fx.muted)
            }
        }
        FlowRow(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Chip("score ${f(c.score, 0)}", MaterialTheme.colorScheme.surfaceVariant)
            Chip("confiança ${c.confidence.level}", MaterialTheme.colorScheme.surfaceVariant)
            if (!isSignal) Chip("observação — não recomendada", fx.badBg)
        }
        SubHeader("Sinal operacional")
        KV("Instrumento", c.instrument, true)
        KV("Direção", if (c.direction == "BUY") "Compra (BUY)" else "Venda (SELL)", true)
        KV("Execução", c.execution_type)
        KV("Cotação ref.", "bid ${f(q.bid, d)} / ask ${f(q.ask, d)} · spread ${f(q.spread_pips, 1)} pips" +
            (if (q.spread_source == "estimated") " (estimado)" else "") + " · ${hhmm(q.time)} UTC · ${q.source}")
        KV("Entrada", "${f(c.entry.price, d)} (${c.entry.side ?: ""})", true)
        KV("Stop Loss", "${f(c.stop_loss.price, d)} (${f(c.stop_loss.pips, 1)} pips)", true)
        c.take_profit.forEach { KV(it.label.substringBefore(" "), "${f(it.price, d)} (${f(it.pips, 1)} pips · ${f(it.rr)}R)", true) }
        KV("Risco-retorno", "TP1 ${f(c.risk_reward.rr_tp1)}R · líquido ${f(c.risk_reward.rr_net_tp1)}R · custo ${f(c.risk_reward.cost_r, 3)}R")
        Row(Modifier.padding(vertical = 4.dp)) {
            Text("Probabilidade", Modifier.width(118.dp), fontSize = 12.sp, color = fx.muted)
            ProbabilityBar(c.probability)
        }
        KV("Valor esperado", "${f(c.expected_value_r, 3)} R" + (c.expected_value_r_ci_low?.let { " (lim. inf. ${f(it, 3)} R)" } ?: ""))
        KV("Confiança", c.confidence.level, true)
        KV("Validade", "até ${hhmm(c.validity.valid_until)} UTC (${c.validity.minutes} min)")
        c.risk?.sizing?.takeIf { it.ok }?.let { s ->
            KV("Tamanho", "${f(s.lots)} lote(s) · risco ${f(s.risk_amount)} ${s.account_currency} (${f(s.risk_pct)}%)")
        }
        SubHeader("Limitações do modelo")
        Bullets(c.confidence.limitations)

        var open by remember { mutableStateOf(isSignal) }
        Text(if (open) "▲ ocultar justificativas" else "▼ ver justificativas, invalidação e portões",
            Modifier.padding(top = 10.dp).clickable { open = !open }, color = MaterialTheme.colorScheme.primary, fontSize = 13.sp)
        if (open) {
            SubHeader("Justificativa técnica"); Bullets(c.justification.technical)
            SubHeader("Justificativa fundamentalista"); Bullets(c.justification.fundamental)
            SubHeader("Justificativa quantitativa"); Bullets(c.justification.quantitative)
            SubHeader("Invalidação"); Bullets(c.invalidation)
            SubHeader("Cenários")
            Bullets(listOf("Principal: ${c.scenarios.principal}", "Alternativo: ${c.scenarios.alternativo}") +
                c.scenarios.riscos.map { "Risco: $it" })
            SubHeader("Portões de validação")
            c.gates.forEach { g ->
                Column(Modifier.fillMaxWidth().padding(vertical = 2.dp).clip(RoundedCornerShape(8.dp))
                    .background(if (g.passed) fx.goodBg else fx.badBg).padding(8.dp)) {
                    Text((if (g.passed) "✔ " else "✖ ") + g.gate.replace('_', ' '), fontWeight = FontWeight.SemiBold, fontSize = 12.sp)
                    Text(g.detail, fontSize = 12.sp)
                }
            }
        }
        if (isSignal && onPaper != null && c.id != null) {
            Button(onClick = { onPaper(c.id) }, Modifier.padding(top = 10.dp)) { Text("Executar em conta demo") }
            Text(c.execution_note ?: "", fontSize = 11.sp, color = fx.muted)
        }
    }
}

package com.fxintel.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.fxintel.app.data.Probability
import java.util.Locale

fun f(v: Double?, d: Int = 2): String = if (v == null || v.isNaN()) "—" else String.format(Locale.US, "%.${d}f", v)
fun pct(v: Double?, d: Int = 1): String = if (v == null) "—" else String.format(Locale.US, "%.${d}f%%", v * 100)
fun hhmm(iso: String?): String = if (iso.isNullOrBlank() || iso.length < 16) "—" else iso.substring(11, 16)
fun dateTime(iso: String?): String = if (iso.isNullOrBlank() || iso.length < 16) "—" else iso.substring(5, 16).replace("T", " ")

@Composable
fun SectionCard(title: String? = null, modifier: Modifier = Modifier, trailing: @Composable (() -> Unit)? = null,
                content: @Composable () -> Unit) {
    Card(
        modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 6.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = RoundedCornerShape(14.dp),
    ) {
        Column(Modifier.padding(14.dp)) {
            if (title != null) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(title, fontWeight = FontWeight.SemiBold, fontSize = 15.sp)
                    trailing?.invoke()
                }
                Box(Modifier.height(8.dp))
            }
            content()
        }
    }
}

@Composable
fun Chip(text: String, bg: Color, fg: Color = MaterialTheme.colorScheme.onSurface) {
    Text(text, Modifier.clip(RoundedCornerShape(50)).background(bg).padding(horizontal = 9.dp, vertical = 3.dp),
        fontSize = 11.sp, color = fg)
}

@Composable
fun KV(k: String, v: String, bold: Boolean = false) {
    Row(Modifier.fillMaxWidth().padding(vertical = 3.dp)) {
        Text(k, Modifier.width(118.dp), fontSize = 12.sp, color = LocalFx.current.muted)
        Text(v, Modifier.weight(1f), fontSize = 13.sp, fontWeight = if (bold) FontWeight.SemiBold else FontWeight.Normal)
    }
}

@Composable
fun Bullets(items: List<String>) {
    Column {
        items.forEach { Text("•  $it", fontSize = 13.sp, modifier = Modifier.padding(vertical = 2.dp)) }
    }
}

@Composable
fun SubHeader(t: String) {
    Text(t.uppercase(), fontSize = 11.sp, fontWeight = FontWeight.SemiBold, letterSpacing = 0.5.sp,
        color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 12.dp, bottom = 4.dp))
}

/** Barra de probabilidade calibrada com o intervalo de confiança de 90%. */
@Composable
fun ProbabilityBar(p: Probability) {
    val fx = LocalFx.current
    val cp = p.calibrated_p
    if (cp == null) { Text("não disponível", fontSize = 13.sp, color = fx.muted); return }
    val lo = p.ci90?.getOrNull(0) ?: cp
    val hi = p.ci90?.getOrNull(1) ?: cp
    Column {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.width(180.dp).height(10.dp).clip(RoundedCornerShape(6.dp)).background(MaterialTheme.colorScheme.surfaceVariant)) {
                Box(Modifier.offset(x = (180 * lo).dp).width((180 * (hi - lo)).coerceAtLeast(2.0).dp).height(10.dp)
                    .background(fx.entry.copy(alpha = 0.35f)))
                Box(Modifier.offset(x = (180 * cp - 2).dp).width(4.dp).height(10.dp).background(fx.entry))
            }
            Text("  ${pct(cp)}", fontWeight = FontWeight.Bold, fontSize = 14.sp)
        }
        Text("IC90% ${pct(lo)}–${pct(hi)} · n=${p.n_oos_bin ?: 0} · modelo ${f(p.model_p, 3)}", fontSize = 11.sp, color = fx.muted)
        Text(p.event, fontSize = 11.sp, color = fx.muted)
    }
}

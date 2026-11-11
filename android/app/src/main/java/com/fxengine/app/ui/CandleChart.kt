package com.fxengine.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.fxengine.app.data.Bars
import com.fxengine.app.data.PlanOverlay
import com.fxengine.app.ui.theme.Fx
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import kotlin.math.max
import kotlin.math.min

/**
 * Candlestick chart with key S/R levels (dashed) and, when there is a trade, the plan:
 * entry (blue), stop (red) and targets (green). Prices on the right axis, times at the bottom.
 */
@Composable
fun CandleChart(
    bars: Bars,
    digits: Int,
    levels: List<Double>,
    plan: PlanOverlay?,
    intraday: Boolean,
    modifier: Modifier = Modifier,
) {
    val measurer = rememberTextMeasurer()
    val labelStyle = TextStyle(color = Fx.Muted, fontSize = 9.sp)
    val fmt = SimpleDateFormat(if (intraday) "HH:mm" else "dd/MM HH'h'", Locale.forLanguageTag("pt-BR"))
        .apply { timeZone = TimeZone.getTimeZone("America/Sao_Paulo") }
    Canvas(modifier.fillMaxWidth().height(260.dp)) {
        val n = bars.size
        if (n < 2) return@Canvas
        val axisW = 54.dp.toPx()
        val bottomH = 16.dp.toPx()
        val w = size.width - axisW
        val h = size.height - bottomH
        var lo = bars.l.min()
        var hi = bars.h.max()
        val span0 = hi - lo
        // keep overlays visible when they are close to the price range
        val extra = (levels + (plan?.takeIf { it.show }?.let { listOf(it.entry, it.sl, it.tp1) } ?: emptyList()))
            .filter { it > lo - span0 * 0.6 && it < hi + span0 * 0.6 }
        extra.forEach { lo = min(lo, it); hi = max(hi, it) }
        val pad = (hi - lo) * 0.05
        lo -= pad; hi += pad
        fun y(p: Double) = (h * (1 - (p - lo) / (hi - lo))).toFloat()
        val step = w / n
        val body = max(step * 0.62f, 1f)

        // grid + price axis
        for (k in 0..4) {
            val p = lo + (hi - lo) * k / 4
            val yy = y(p)
            drawLine(Fx.Outline.copy(alpha = 0.5f), Offset(0f, yy), Offset(w, yy), 1f)
            val lbl = measurer.measure(String.format(Locale.US, "%.${digits}f", p), labelStyle)
            // centred on its line; the bottom one sits fully above it so it never touches the time axis
            val top = when (k) {
                0 -> yy - lbl.size.height - 2f
                4 -> yy + 2f
                else -> yy - lbl.size.height / 2f
            }
            drawText(lbl, topLeft = Offset(w + 4f, top))
        }
        // levels
        val dash = PathEffect.dashPathEffect(floatArrayOf(10f, 8f))
        levels.filter { it in lo..hi }.forEach {
            drawLine(Fx.Muted.copy(alpha = 0.55f), Offset(0f, y(it)), Offset(w, y(it)), 1.5f, pathEffect = dash)
        }
        // candles
        for (i in 0 until n) {
            val x = step * i + step / 2
            val up = bars.c[i] >= bars.o[i]
            val col = if (up) Fx.Buy else Fx.Sell
            drawLine(col, Offset(x, y(bars.h[i])), Offset(x, y(bars.l[i])), 1.2f)
            val top = y(max(bars.o[i], bars.c[i]))
            val bot = y(min(bars.o[i], bars.c[i]))
            drawRect(col, Offset(x - body / 2, top), Size(body, max(bot - top, 1f)))
        }
        // plan
        plan?.takeIf { it.show }?.let { p ->
            val trail = p.exitKind == "trail"
            val lines = listOf(
                Triple(p.entry, Fx.Blue, "entrada"), Triple(p.sl, Fx.Sell, "stop"),
                Triple(p.tp1, Fx.Buy, if (trail) "+1R: stop móvel" else "alvo 1"),
                Triple(p.tp2, Fx.Buy.copy(alpha = 0.7f), if (trail) "ref. 3R" else "alvo 2"),
            ).filter { it.first in lo..hi }.sortedBy { y(it.first) }
            // labels go above their line unless that would overlap the label placed just before
            var lastBottom = Float.NEGATIVE_INFINITY
            lines.forEach { (price, color, label) ->
                val yy = y(price)
                drawLine(color, Offset(0f, yy), Offset(w, yy), 2f)
                val lbl = measurer.measure(label, TextStyle(color = color, fontSize = 9.sp))
                val above = yy - lbl.size.height - 1f
                val top = if (above >= lastBottom) above else yy + 1f
                drawText(lbl, topLeft = Offset(4f, top))
                lastBottom = top + lbl.size.height
            }
        }
        // last price
        val last = bars.c[n - 1]
        drawLine(Fx.Gold, Offset(0f, y(last)), Offset(w, y(last)), 1f)
        val lastLbl = measurer.measure(String.format(Locale.US, "%.${digits}f", last), TextStyle(color = Fx.Gold, fontSize = 9.sp))
        drawText(lastLbl, topLeft = Offset(w + 4f, y(last) - lastLbl.size.height / 2f))
        // time axis: labels stay inside the plot area (the price axis owns the right margin)
        for (k in listOf(0, n / 3, 2 * n / 3, n - 1)) {
            val lbl = measurer.measure(fmt.format(Date(bars.t[k])), labelStyle)
            val x = (step * k + step / 2 - lbl.size.width / 2f).coerceIn(0f, w - lbl.size.width)
            drawText(lbl, topLeft = Offset(x, h + 3f))
        }
    }
}

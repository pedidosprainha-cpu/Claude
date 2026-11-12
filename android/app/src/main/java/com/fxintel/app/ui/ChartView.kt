package com.fxintel.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.unit.dp
import com.fxintel.app.data.Candidate
import com.fxintel.app.data.ChartResp
import kotlin.math.max
import kotlin.math.min

/** Gráfico de candles em Canvas com linhas de Entrada, Stop Loss e Take Profit. */
@Composable
fun CandleChart(chart: ChartResp, sel: Candidate?, textColor: Color, modifier: Modifier = Modifier) {
    val fx = LocalFx.current
    val bars = chart.bars
    if (bars.isEmpty()) return
    data class Line(val price: Double, val color: Color, val label: String, val dashed: Boolean)
    val lines = buildList {
        if (sel != null && sel.instrument == chart.symbol) {
            add(Line(sel.entry.price, fx.entry, "Entrada", false))
            add(Line(sel.stop_loss.price, fx.sl, "SL", true))
            sel.take_profit.forEachIndexed { i, t -> add(Line(t.price, fx.tp, if (i == 0) "TP1" else "TP2", i > 0)) }
        }
    }
    var hi = bars.maxOf { it.h }
    var lo = bars.minOf { it.l }
    lines.forEach { hi = max(hi, it.price); lo = min(lo, it.price) }
    val pad = (hi - lo) * 0.05
    hi += pad; lo -= pad
    val digits = chart.digits
    Canvas(modifier.fillMaxWidth().height(260.dp)) {
        val axisW = 64.dp.toPx()
        val w = size.width - axisW
        val h = size.height
        fun y(p: Double) = ((hi - p) / (hi - lo) * h).toFloat()
        val paint = android.graphics.Paint().apply {
            color = textColor.toArgb(); textSize = 10.dp.toPx(); isAntiAlias = true
        }
        val minGap = 14.dp.toPx()
        for (k in 0..4) {
            val p = lo + (hi - lo) * k / 4
            drawLine(fx.grid, Offset(0f, y(p)), Offset(w, y(p)), 1f)
            // omite o rótulo da grade se colidir com o rótulo de uma linha de nível
            if (lines.none { kotlin.math.abs(y(it.price) - y(p)) < minGap })
                drawContext.canvas.nativeCanvas.drawText(String.format("%.${digits}f", p), w + 4.dp.toPx(), y(p) + 4.dp.toPx(), paint)
        }
        val step = w / bars.size
        val bw = max(1f, step * 0.65f)
        bars.forEachIndexed { i, b ->
            val x = i * step + step / 2
            val col = if (b.c >= b.o) fx.buy else fx.sell
            drawLine(col, Offset(x, y(b.h)), Offset(x, y(b.l)), max(1f, step * 0.12f))
            val top = y(max(b.o, b.c)); val bot = y(min(b.o, b.c))
            drawRect(col, Offset(x - bw / 2, top), Size(bw, max(1f, bot - top)))
        }
        lines.forEach { ln ->
            drawLine(ln.color, Offset(0f, y(ln.price)), Offset(w, y(ln.price)), 2.dp.toPx(),
                pathEffect = if (ln.dashed) PathEffect.dashPathEffect(floatArrayOf(12f, 8f)) else null)
            val lp = android.graphics.Paint(paint).apply { color = ln.color.toArgb(); isFakeBoldText = true }
            drawContext.canvas.nativeCanvas.drawText(ln.label, 4.dp.toPx(), y(ln.price) - 3.dp.toPx(), lp)
            drawContext.canvas.nativeCanvas.drawText(String.format("%.${digits}f", ln.price), w + 4.dp.toPx(), y(ln.price) + 4.dp.toPx(), lp)
        }
        val last = bars.last()
        drawLine(textColor.copy(alpha = 0.4f), Offset(0f, y(last.c)), Offset(w, y(last.c)), 1f,
            pathEffect = PathEffect.dashPathEffect(floatArrayOf(4f, 6f)))
    }
}

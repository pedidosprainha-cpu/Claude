package com.fxengine.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

object Fx {
    val Bg = Color(0xFF0B1220)
    val Surface = Color(0xFF111A2E)
    val SurfaceHigh = Color(0xFF18243D)
    val Outline = Color(0xFF26334F)
    val Text = Color(0xFFE6EBF5)
    val Muted = Color(0xFF93A1BC)
    val Blue = Color(0xFF4F8CFF)
    val Buy = Color(0xFF22C55E)
    val Sell = Color(0xFFF05A5A)
    val Warn = Color(0xFFF5A524)
    val Gold = Color(0xFFFBBF24)

    fun side(isBuy: Boolean) = if (isBuy) Buy else Sell

    fun grade(g: String) = when (g) {
        "A+", "A" -> Buy
        "B" -> Blue
        "C" -> Warn
        else -> Muted
    }
}

private val scheme = darkColorScheme(
    primary = Fx.Blue,
    onPrimary = Color.White,
    secondary = Fx.Gold,
    background = Fx.Bg,
    onBackground = Fx.Text,
    surface = Fx.Surface,
    onSurface = Fx.Text,
    surfaceVariant = Fx.SurfaceHigh,
    onSurfaceVariant = Fx.Muted,
    surfaceContainer = Fx.Surface,
    surfaceContainerHigh = Fx.SurfaceHigh,
    surfaceContainerLow = Fx.Surface,
    outline = Fx.Outline,
    outlineVariant = Fx.Outline,
    error = Fx.Sell,
)

private val base = Typography()
private val typography = Typography(
    headlineLarge = base.headlineLarge.copy(fontWeight = FontWeight.Bold),
    headlineMedium = base.headlineMedium.copy(fontWeight = FontWeight.Bold),
    titleLarge = base.titleLarge.copy(fontWeight = FontWeight.SemiBold),
    titleMedium = base.titleMedium.copy(fontWeight = FontWeight.SemiBold),
)

val Mono = TextStyle(fontFamily = FontFamily.Monospace, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)

@Composable
fun FxTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = scheme, typography = typography, content = content)
}

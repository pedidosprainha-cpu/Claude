package com.fxintel.app.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

data class FxColors(
    val buy: Color, val sell: Color, val warn: Color, val tp: Color, val sl: Color, val entry: Color,
    val goodBg: Color, val badBg: Color, val warnBg: Color, val muted: Color, val grid: Color,
)

val LightFx = FxColors(
    buy = Color(0xFF0CA30C), sell = Color(0xFFD03B3B), warn = Color(0xFFB47800), tp = Color(0xFF1BAF7A),
    sl = Color(0xFFD03B3B), entry = Color(0xFF2A78D6), goodBg = Color(0xFFE6F5E6), badBg = Color(0xFFFBE9E9),
    warnBg = Color(0xFFFDF3DC), muted = Color(0xFF7A7974), grid = Color(0xFFE2E1DC),
)
val DarkFx = FxColors(
    buy = Color(0xFF2FBF2F), sell = Color(0xFFE66767), warn = Color(0xFFFAB219), tp = Color(0xFF199E70),
    sl = Color(0xFFE66767), entry = Color(0xFF3987E5), goodBg = Color(0xFF16301A), badBg = Color(0xFF3A1C1C),
    warnBg = Color(0xFF3A2F14), muted = Color(0xFF8F8E86), grid = Color(0xFF33332F),
)

val LocalFx = staticCompositionLocalOf { LightFx }

private val LightScheme = lightColorScheme(
    primary = Color(0xFF2A78D6), onPrimary = Color.White, background = Color(0xFFF4F4F1),
    surface = Color(0xFFFCFCFB), surfaceVariant = Color(0xFFF0EFEC), onSurface = Color(0xFF0B0B0B),
    onSurfaceVariant = Color(0xFF52514E), outline = Color(0xFFE2E1DC),
)
private val DarkScheme = darkColorScheme(
    primary = Color(0xFF3987E5), onPrimary = Color.White, background = Color(0xFF121211),
    surface = Color(0xFF1A1A19), surfaceVariant = Color(0xFF232321), onSurface = Color(0xFFF0EFEC),
    onSurfaceVariant = Color(0xFFC3C2B7), outline = Color(0xFF33332F),
)

@Composable
fun FxTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    androidx.compose.runtime.CompositionLocalProvider(LocalFx provides if (dark) DarkFx else LightFx) {
        MaterialTheme(colorScheme = if (dark) DarkScheme else LightScheme, content = content)
    }
}

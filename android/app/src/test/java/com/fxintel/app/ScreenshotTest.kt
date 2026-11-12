package com.fxintel.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.Modifier
import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import com.android.resources.NightMode
import com.fxintel.app.data.Analysis
import com.fxintel.app.data.ChartResp
import com.fxintel.app.data.JsonCfg
import com.fxintel.app.ui.CandleChart
import com.fxintel.app.ui.FxTheme
import com.fxintel.app.ui.SectionCard
import com.fxintel.app.ui.SignalDetails
import org.junit.Rule
import org.junit.Test

/** Renderização JVM (sem emulador) dos principais componentes com dados reais do backend. */
class ScreenshotTest {
    @get:Rule
    val paparazzi = Paparazzi(deviceConfig = DeviceConfig.PIXEL_6.copy(screenHeight = 3200, nightMode = NightMode.NIGHT),
        theme = "android:Theme.Material.NoActionBar")

    private fun res(name: String) = javaClass.classLoader!!.getResource(name)!!.readText()

    @Test fun signalCard() {
        val a = JsonCfg.decodeFromString<Analysis>(res("analysis_signal.json"))
        val s = a.signal!!
        val chart = JsonCfg.decodeFromString<ChartResp>(res("chart.json")).let { c ->
            // usa o gráfico do mesmo instrumento do sinal quando disponível
            if (c.symbol == s.instrument) c else c.copy(symbol = s.instrument)
        }
        paparazzi.snapshot {
            FxTheme {
                Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).verticalScroll(rememberScrollState())) {
                    SectionCard("Resultado") { SignalDetails(s, true) { } }
                }
            }
        }
    }

    @Test fun chartWithLevels() {
        val a = JsonCfg.decodeFromString<Analysis>(res("analysis_signal.json"))
        val c = JsonCfg.decodeFromString<ChartResp>(res("chart_signal.json"))
        paparazzi.snapshot {
            FxTheme {
                Column(Modifier.background(MaterialTheme.colorScheme.background)) {
                    SectionCard("Gráfico · ${c.symbol} · H1") {
                        CandleChart(c, a.signal, MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }

    @Test fun rankingCard() {
        val a = JsonCfg.decodeFromString<Analysis>(res("analysis_ranking.json"))
        paparazzi.snapshot {
            FxTheme {
                Column(Modifier.background(MaterialTheme.colorScheme.background)) {
                    com.fxintel.app.ui.RankingCard(a.ranking, a.id, onSelect = {}, onPaper = null)
                }
            }
        }
    }
}

package com.fxengine.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import com.fxengine.app.data.AppSettings
import com.fxengine.app.data.EngineOutput
import com.fxengine.app.data.ScanResult
import com.fxengine.app.data.parseEngineOutput
import com.fxengine.app.ui.HomeScreen
import com.fxengine.app.ui.LocalStaticUi
import com.fxengine.app.ui.MarketScreen
import com.fxengine.app.ui.OpportunityDetail
import com.fxengine.app.ui.RankingScreen
import com.fxengine.app.ui.SettingsScreen
import com.fxengine.app.ui.UiState
import com.fxengine.app.ui.theme.Fx
import com.fxengine.app.ui.theme.FxTheme
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Renders every screen with real engine output (fixtures in src/test/resources).
 * Record: ./gradlew recordRoborazziDebug (PNGs land in app/build/outputs/roborazzi)
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [36], qualifiers = "w400dp-h1800dp-xxhdpi")
class ScreensTest {
    private fun shot(name: String, content: @Composable () -> Unit) =
        captureRoboImage("build/outputs/roborazzi/$name.png") { content() }

    private fun load(name: String): ScanResult {
        val raw = javaClass.getResource("/$name")!!.readText()
        val out = parseEngineOutput(raw)
        assertTrue("fixture $name must parse", out is EngineOutput.Ok)
        return (out as EngineOutput.Ok).result
    }

    @Composable
    private fun Frame(content: @Composable () -> Unit) = FxTheme {
        CompositionLocalProvider(LocalStaticUi provides true) {
            Box(Modifier.fillMaxSize().background(Fx.Bg)) { content() }
        }
    }

    @Test
    fun parsesFixtures() {
        val live = load("sample_live.json")
        assertEquals(32, live.ranking.size)
        assertEquals(false, live.decision.execute)
        val exec = load("sample_exec.json")
        assertTrue(exec.decision.execute && exec.best != null)
    }

    @Test
    fun home_idle() = shot("home_idle") {
        Frame { HomeScreen(UiState(engineReady = true), {}, {}) }
    }

    @Test
    fun home_running() = shot("home_running") {
        Frame { HomeScreen(UiState(running = true, progress = 42, step = "Preços ao vivo e gráficos 14/32"), {}, {}) }
    }

    @Test
    fun home_execute() = shot("home_execute") {
        Frame {
            HomeScreen(UiState(result = load("sample_exec.json"), resultAtMillis = System.currentTimeMillis(),
                engineReady = true), {}, {})
        }
    }

    @Test
    fun home_no_trade() = shot("home_no_trade") {
        Frame {
            HomeScreen(UiState(result = load("sample_live.json"), resultAtMillis = System.currentTimeMillis(),
                engineReady = true), {}, {})
        }
    }

    @Test
    fun home_error() = shot("home_error") {
        Frame { HomeScreen(UiState(error = "Sem conexão com a internet", errorDetail = "Conecte-se e toque em Analisar de novo."), {}, {}) }
    }

    @Test
    fun ranking() = shot("ranking") { Frame { RankingScreen(load("sample_live.json")) } }

    @Test
    fun market() = shot("market") { Frame { MarketScreen(load("sample_live.json")) } }

    @Test
    fun settings() = shot("settings") { Frame { SettingsScreen(AppSettings(), {}) } }

    @Test
    fun detail_reference() = shot("detail_reference") {
        Frame { OpportunityDetail(load("sample_live.json").ranking[1], referenceOnly = true) }
    }
}

package com.fxengine.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import com.fxengine.app.ui.SignalModelCard
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import com.fxengine.app.data.AppSettings
import com.fxengine.app.data.BreakoutOutput
import com.fxengine.app.data.BreakoutResult
import com.fxengine.app.data.parseBreakouts
import com.fxengine.app.monitor.MonitorState
import com.fxengine.app.data.AssetOutput
import com.fxengine.app.data.parseAsset
import com.fxengine.app.ui.AssetDetail
import com.fxengine.app.ui.AssetPickerContent
import com.fxengine.app.ui.BottomBar
import com.fxengine.app.ui.BreakoutContent
import com.fxengine.app.ui.BreakoutDetail
import com.fxengine.app.ui.CandleChart
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

    private fun breakouts(): BreakoutResult {
        val out = parseBreakouts(javaClass.getResource("/sample_breakouts.json")!!.readText())
        assertTrue("breakout fixture must parse", out is BreakoutOutput.Ok)
        return (out as BreakoutOutput.Ok).result
    }

    @Test
    fun parsesBreakoutFixture() {
        val r = breakouts()
        assertTrue(r.items.isNotEmpty() && r.scanned == 32)
    }

    @Test
    fun breakouts_monitor_on() = shot("breakouts_monitor_on") {
        Frame {
            BreakoutContent(
                MonitorState(active = true, result = breakouts(), resultAtMillis = System.currentTimeMillis(),
                    nextAtMillis = System.currentTimeMillis() + 74_000, cycles = 3),
                AppSettings(), notificationsAllowed = true, {}, {}, {},
            )
        }
    }

    @Test
    fun breakouts_scanning_off() = shot("breakouts_scanning_off") {
        Frame {
            BreakoutContent(
                MonitorState(scanning = true, progress = 37, step = "Preços ao vivo 12/32"),
                AppSettings(), notificationsAllowed = true, {}, {}, {},
            )
        }
    }

    @Test
    fun breakout_detail() = shot("breakout_detail") {
        Frame { BreakoutDetail(breakouts().items.first()) }
    }

    private fun asset() = (parseAsset(javaClass.getResource("/sample_asset.json")!!.readText()) as AssetOutput.Ok).result

    @Test
    fun parsesAssetFixture() {
        val a = asset()
        assertEquals("EURUSD", a.symbol)
        assertTrue(a.mtf.size == 5 && a.levels.isNotEmpty() && (a.chartH1?.size ?: 0) > 50)
    }

    @Test
    fun asset_detail() = shot("asset_detail") { Frame { AssetDetail(asset()) } }

    /** Full-length render of the asset analysis (MTF, levels, quant, fundamentals, agenda). */
    @Test
    @Config(qualifiers = "w400dp-h5600dp-xxhdpi")
    fun asset_detail_full() = shot("asset_detail_full") { Frame { AssetDetail(asset()) } }

    /** Chart with the trade plan drawn (entry, stop, targets) on top of candles and levels. */
    @Test
    fun candle_chart_plan() = shot("candle_chart_plan") {
        val r = asset()
        Frame {
            CandleChart(r.chartM15!!, r.digits, r.overlayLevels,
                r.plan?.copy(show = true), intraday = true)
        }
    }

    @Test
    fun home_asset_mode() = shot("home_asset_mode") {
        Frame {
            HomeScreen(UiState(engineReady = true, settings = AppSettings(homeMode = "asset", focusSymbol = "EURUSD"),
                asset = asset(), assetAtMillis = System.currentTimeMillis()), {}, {})
        }
    }

    @Test
    fun asset_picker() = shot("asset_picker") {
        Frame { AssetPickerContent("Escolha o ativo", setOf("EURUSD"), multi = false, onDismiss = {}, onConfirm = {}) }
    }

    @Test
    fun bottom_bar() = shot("bottom_bar") {
        Frame { BottomBar(1) {} }
    }

    @Test
    fun parsesFixtures() {
        val live = load("sample_live.json")
        assertEquals(32, live.ranking.size)
        assertEquals(false, live.decision.execute)
        val top = live.ranking.first()
        assertTrue("model probability", top.edge?.fromModel == true && top.exitKind == "trail")
        val m = live.signalModel
        assertTrue("model card", m != null && m.bars > 100_000 && m.testN > 0)
        val exec = load("sample_exec.json")
        assertTrue(exec.decision.execute && exec.best != null)
        assertTrue("old fixtures still parse", exec.best?.exitKind == "partial" && exec.signalModel == null)
    }

    @Test
    fun signal_model_card() = shot("signal_model_card") {
        Frame { Column(Modifier.padding(16.dp)) { SignalModelCard(load("sample_live.json").signalModel!!) } }
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

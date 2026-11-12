package com.fxintel.app

import com.fxintel.app.engine.CentralBanks
import com.fxintel.app.engine.Engine
import com.fxintel.app.engine.EngineSettings
import com.fxintel.app.engine.MarketData
import com.fxintel.app.engine.ModelIO
import com.fxintel.app.engine.RiskState
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File

/**
 * Execução real do motor autônomo (o mesmo código que roda no celular) com dados públicos, sem chave
 * de API e sem servidor. Requer internet: ative com -Dfxintel.live=true (ou FXI_LIVE_TEST=1).
 */
class LiveEngineTest {
    @Test fun analyzeNowStandalone() {
        assumeTrue(System.getProperty("fxintel.live") == "true" || System.getenv("FXI_LIVE_TEST") == "1")
        val cache = File(System.getProperty("java.io.tmpdir"), "fxintel-live-cache").apply { mkdirs() }
        val md = MarketData(cache)
        val engine = Engine(md, ModelIO.parse(File("src/main/assets/model.json").readText()),
            CentralBanks.parse(File("src/main/assets/central_banks.json").readText()))
        repeat(2) { round ->
            val t0 = System.currentTimeMillis()
            val a = engine.analyze(EngineSettings(), RiskState())
            val ms = System.currentTimeMillis() - t0
            println("rodada ${round + 1}: ${a.status} | ${a.headline} | ${ms} ms | ${a.trigger}")
            println("  motivos: ${a.no_signal_reasons}")
            a.market.forEach { println("  ${it.symbol} trend=${it.trend} align=${it.alignment} regime=${it.regime} fund=${it.fundamental_score} cand=${it.candidates} err=${it.error}") }
            println("  RANKING (top 5 por nota):")
            a.ranking.forEach { c -> println("   #${c.rank} ${c.instrument} ${c.direction} nota=${c.score} ${c.status} setup=${c.setup} EV=${c.expected_value_r} bloqueios=${c.blocked_by}") }
            assertTrue(a.ranking.size == 5 && a.ranking.zipWithNext().all { (x, y) -> x.score >= y.score })
            (listOfNotNull(a.signal) + a.observations).forEach { c ->
                println("  ${c.direction} ${c.instrument} ${c.setup} entrada=${c.entry.price} sl=${c.stop_loss.price} tp1=${c.take_profit[0].price} " +
                    "p=${c.probability.calibrated_p} ev=${c.expected_value_r} score=${c.score} falhas=${c.gates.filter { !it.passed }.map { it.gate }}")
            }
            assertTrue(a.market.size == 16)
            assertTrue(a.market.count { it.error == null } >= 14)
        }
        md.health.values.forEach { println("  fonte ${it.name}: ok=${it.ok} req=${it.requests} falhas=${it.failures} lat=${it.lastLatencyMs}") }
        println("  cotações: " + md.lastQuotes.values.joinToString { "${it.symbol}=${it.bid}/${it.ask}(${it.source})" })
    }
}

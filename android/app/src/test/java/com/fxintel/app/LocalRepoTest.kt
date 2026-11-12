package com.fxintel.app

import com.fxintel.app.data.LocalRepo
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

/** Modo autônomo de ponta a ponta (sem Android, sem servidor, sem chave): cotações, análise, persistência,
 *  histórico, gráfico, saúde, configurações, acompanhamento de sinais e alertas. Requer internet (FXI_LIVE_TEST=1). */
class LocalRepoTest {
    @Test fun standaloneEndToEnd() {
        assumeTrue(System.getenv("FXI_LIVE_TEST") == "1")
        val dir = Files.createTempDirectory("fxintel-repo").toFile()
        val repo = LocalRepo(dir, File("src/main/assets/model.json").readText(), File("src/main/assets/central_banks.json").readText())
        val q = repo.quotes()
        println("cotações: ${q.data.size} às ${q.at}; exemplo ${q.data["XAUUSD"]}")
        assertTrue(q.data.size >= 14)
        assertTrue(q.data.values.all { it.ask >= it.bid })
        val a = repo.analyze()
        println("análise: ${a.status} | ${a.headline} | ${a.elapsed_ms} ms | ${a.no_signal_reasons}")
        assertEquals(a.id, repo.latest()?.id)
        assertEquals(1, repo.analyses().size)
        val c = repo.chart("XAUUSD", "H1")
        println("gráfico XAUUSD H1: ${c.bars.size} barras, último fechamento ${c.bars.last().c} vs spot ${q.data["XAUUSD"]?.mid}")
        assertTrue(c.bars.size >= 100)
        val h = repo.health()
        println("saúde: ${h.status} fontes=${h.providers.providers.map { "${it.name}:${it.ok}" }} modelo=${h.model}")
        val s = repo.saveSettings(buildJsonObject { putJsonObject("risk") { put("risk_per_trade_pct", 0.25) } })
        assertEquals(0.25, repo.settings.riskPct, 1e-12)
        println("config: $s")
        val bad = runCatching { repo.saveSettings(buildJsonObject { putJsonObject("risk") { put("risk_per_trade_pct", 5.0) } }) }
        assertTrue(bad.isFailure)
        println("rastreamento: ${repo.trackSignals()} eventos: ${repo.eventAlerts()} alertas=${repo.alerts(0).size}")
        // reabre o repositório: estado persistido em disco
        val repo2 = LocalRepo(dir, File("src/main/assets/model.json").readText(), File("src/main/assets/central_banks.json").readText())
        assertEquals(a.id, repo2.latest()?.id)
        assertEquals(0.25, repo2.settings.riskPct, 1e-12)
    }
}

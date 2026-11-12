package com.fxintel.app

import com.fxintel.app.data.AlertItem
import com.fxintel.app.data.Analysis
import com.fxintel.app.data.AnalysisRow
import com.fxintel.app.data.ChartResp
import com.fxintel.app.data.Health
import com.fxintel.app.data.JsonCfg
import com.fxintel.app.data.QuotesResp
import com.fxintel.app.data.SignalsResp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Decodifica respostas reais capturadas do backend (fixtures) com os modelos do app. */
class ApiParsingTest {
    private fun res(name: String) = javaClass.classLoader!!.getResource(name)!!.readText()

    @Test fun health() {
        val h = JsonCfg.decodeFromString<Health>(res("health.json"))
        assertTrue(h.version.isNotBlank())
        assertTrue(h.providers.providers.isNotEmpty())
    }

    @Test fun quotes() {
        val q = JsonCfg.decodeFromString<QuotesResp>(res("quotes.json"))
        assertTrue(q.data.size >= 10)
        assertTrue(q.data.values.all { it.ask >= it.bid })
    }

    @Test fun analysisWithoutSignal() {
        val a = JsonCfg.decodeFromString<Analysis>(res("analysis.json"))
        assertTrue(a.id.isNotBlank())
        assertTrue(a.market.isNotEmpty())
        assertNotNull(a.model)
    }

    @Test fun analysisWithSignal() {
        val a = JsonCfg.decodeFromString<Analysis>(res("analysis_signal.json"))
        val s = a.signal!!
        assertTrue(s.take_profit.size == 2)
        assertTrue(s.gates.isNotEmpty())
        assertTrue(s.justification.technical.isNotEmpty())
        assertEquals(true, s.risk?.sizing?.ok)
    }

    @Test fun chartSignalsAlerts() {
        val c = JsonCfg.decodeFromString<ChartResp>(res("chart.json"))
        assertTrue(c.bars.size == 30)
        JsonCfg.decodeFromString<SignalsResp>(res("signals.json"))
        JsonCfg.decodeFromString<List<AlertItem>>(res("alerts.json"))
        JsonCfg.decodeFromString<List<AnalysisRow>>(res("analyses.json"))
    }
}

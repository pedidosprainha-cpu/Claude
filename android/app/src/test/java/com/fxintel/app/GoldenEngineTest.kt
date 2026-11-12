package com.fxintel.app

import com.fxintel.app.engine.BarOps
import com.fxintel.app.engine.Bars
import com.fxintel.app.engine.Candidates
import com.fxintel.app.engine.Features
import com.fxintel.app.engine.Instruments
import com.fxintel.app.engine.Macro
import com.fxintel.app.engine.ModelIO
import com.fxintel.app.engine.Technical
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs
import kotlin.math.max

/**
 * Verifica que o motor Kotlin reproduz o motor Python (mesmas entradas → mesmas saídas):
 * quadro MTF, candidatos, features e probabilidades. Fixture gerado por scripts/export_golden.py.
 */
class GoldenEngineTest {
    private val root: JsonObject by lazy {
        Json.parseToJsonElement(javaClass.classLoader!!.getResource("golden.json")!!.readText()).jsonObject
    }

    private fun nums(a: JsonArray) = a.map { (it as? JsonPrimitive)?.doubleOrNull ?: Double.NaN }.toDoubleArray()
    private fun times(a: JsonArray) = a.map { it.jsonPrimitive.longOrNull!! }.toLongArray()

    private fun bars(o: JsonObject): Bars {
        val t = times(o["t"]!!.jsonArray)
        if (!o.containsKey("o")) { val c = nums(o["c"]!!.jsonArray); return Bars(t, c, c, c, c) }
        return Bars(t, nums(o["o"]!!.jsonArray), nums(o["h"]!!.jsonArray), nums(o["l"]!!.jsonArray), nums(o["c"]!!.jsonArray))
    }

    private fun close(a: Double, b: Double, rel: Double = 1e-6): Boolean {
        if (a.isNaN() || b.isNaN()) return a.isNaN() && b.isNaN()
        return abs(a - b) <= rel * max(1.0, max(abs(a), abs(b)))
    }

    @Test fun engineMatchesPython() {
        val macro = root["macro"]!!.jsonObject.mapValues { bars(it.value.jsonObject) }
        val basket = root["basket"]!!.jsonObject.mapValues { bars(it.value.jsonObject) }
        val strength = Macro.strength(basket)
        val model = ModelIO.parse(root["model"]!!.toString())
        val report = StringBuilder()
        var mismatches = 0
        for ((sym, el) in root["symbols"]!!.jsonObject) {
            val g = el.jsonObject
            val h1 = bars(g["bars"]!!.jsonObject)
            val mtf = Technical.buildFrame(h1, BarOps.derive(h1, "H4"), BarOps.derive(h1, "D1"))
            val F = mtf.F
            // 1) colunas do quadro nas últimas 400 barras
            val tail = g["frame_tail"]!!.jsonObject
            val tt = times(tail["t"]!!.jsonArray)
            for ((col, v) in tail) {
                if (col == "t") continue
                val exp = nums(v.jsonArray)
                var bad = 0
                for (k in tt.indices) {
                    val i = F.indexOf(tt[k])
                    if (i < 0 || !close(F.at(col, i), exp[k])) bad++
                }
                if (bad > 0) { mismatches++; report.append("$sym frame.$col: $bad/${tt.size} divergentes\n") }
            }
            // 2) candidatos
            val cands = Candidates.generate(F)
            val expC = g["candidates"]!!.jsonArray.map { it.jsonObject }
            if (cands.size != expC.size) { mismatches++; report.append("$sym candidatos: kotlin=${cands.size} python=${expC.size}\n") }
            val byT = cands.associateBy { it.t }
            var badC = 0
            for (e in expC) {
                val c = byT[e["t"]!!.jsonPrimitive.longOrNull!!]
                if (c == null || c.dir != e["dir"]!!.jsonPrimitive.content.toInt() || c.setup != e["setup"]!!.jsonPrimitive.content ||
                    !close(c.sl, e["sl"]!!.jsonPrimitive.doubleOrNull!!) || !close(c.tp1, e["tp1"]!!.jsonPrimitive.doubleOrNull!!) ||
                    !close(c.tp2, e["tp2"]!!.jsonPrimitive.doubleOrNull!!) || !close(c.roomR, e["room_r"]!!.jsonPrimitive.doubleOrNull!!)) badC++
            }
            if (badC > 0) { mismatches++; report.append("$sym candidatos divergentes: $badC\n") }
            // 3) features e probabilidades
            val inst = Instruments.get(sym)
            val mf = Macro.features(macro, F.t)
            val sd = Macro.strengthDiff(strength, inst, F.t)
            val names = g["feature_names"]!!.jsonArray.map { it.jsonPrimitive.content }
            val feats = g["features"]!!.jsonObject
            val expP = nums(g["p"]!!.jsonArray)
            var badF = 0; var badP = 0; var k = 0
            val badNames = HashMap<String, Int>()
            for (e in expC) {
                val t = e["t"]!!.jsonPrimitive.longOrNull!!
                val c = byT[t]
                val ex = nums(feats[t.toString()]!!.jsonArray)
                if (c != null) {
                    val x = Features.build(inst, F, c, mf, sd)
                    names.forEachIndexed { j, n -> if (!close(x[n] ?: Double.NaN, ex[j], 1e-5)) { badF++; badNames[n] = (badNames[n] ?: 0) + 1 } }
                    if (!close(model.predict(x), expP[k], 1e-5)) badP++
                }
                k++
            }
            if (badF > 0) { mismatches++; report.append("$sym features divergentes: $badF $badNames\n") }
            if (badP > 0) { mismatches++; report.append("$sym probabilidades divergentes: $badP/${expP.size}\n") }
            // 4) planos estruturais do ranking (último candle, ambas as direções)
            val plans = g["plans"]!!.jsonArray.map { it.jsonObject }
            var badPl = 0
            for (e in plans) {
                val d = e["dir"]!!.jsonPrimitive.content.toDouble().toInt()
                val px = (e["price"] as? JsonPrimitive)?.doubleOrNull
                val pl = Candidates.plan(F, d, px)
                fun ex(k: String) = e[k]!!.jsonPrimitive.doubleOrNull!!
                if (pl == null || !close(pl.sl, ex("sl")) || !close(pl.tp1, ex("tp1")) || !close(pl.tp2, ex("tp2")) ||
                    !close(pl.rr1, ex("rr1")) || !close(pl.roomR, ex("room_r")) || !close(pl.riskAtr, ex("risk_atr")) ||
                    pl.inZone.toDouble() != ex("in_zone") || pl.atEma.toDouble() != ex("at_ema") ||
                    pl.pdSweep.toDouble() != ex("pd_sweep") || pl.d1Dir != ex("d1_dir") || pl.tp1Structural.toDouble() != ex("tp1_structural")) badPl++
            }
            if (badPl > 0 || plans.isEmpty()) { mismatches++; report.append("$sym planos divergentes: $badPl/${plans.size}\n") }
            report.append("$sym OK-check: barras=${h1.n} candidatos=${cands.size} planos=${plans.size}\n")
        }
        println(report)
        assertTrue(report.toString(), mismatches == 0)
        assertEquals(0, mismatches)
    }
}

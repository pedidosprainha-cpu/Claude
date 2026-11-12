package com.fxintel.app.engine

import kotlin.math.round

object Instruments {
    data class Inst(
        val symbol: String, val base: String, val quote: String, val kind: String, val pip: Double, val digits: Int,
        val contractSize: Double, val typicalSpreadPips: Double, val yahoo: String,
    ) {
        fun roundPrice(p: Double): Double { val m = Math.pow(10.0, digits.toDouble()); return round(p * m) / m }
    }

    private fun fx(sym: String, spread: Double): Inst {
        val jpy = sym.endsWith("JPY")
        return Inst(sym, sym.substring(0, 3), sym.substring(3), "fx", if (jpy) 0.01 else 0.0001, if (jpy) 3 else 5,
            100_000.0, spread, "$sym=X")
    }

    val ALL: LinkedHashMap<String, Inst> = linkedMapOf(
        "XAUUSD" to Inst("XAUUSD", "XAU", "USD", "metal", 0.1, 2, 100.0, 3.0, "PAXG-USD"),
        "XAGUSD" to Inst("XAGUSD", "XAG", "USD", "metal", 0.01, 3, 5000.0, 3.0, "SI=F"),
        "EURUSD" to fx("EURUSD", 1.0), "GBPUSD" to fx("GBPUSD", 1.4), "USDJPY" to fx("USDJPY", 1.3),
        "USDCHF" to fx("USDCHF", 1.6), "USDCAD" to fx("USDCAD", 1.8), "AUDUSD" to fx("AUDUSD", 1.3),
        "NZDUSD" to fx("NZDUSD", 1.8), "EURJPY" to fx("EURJPY", 1.9), "GBPJPY" to fx("GBPJPY", 2.8),
        "EURGBP" to fx("EURGBP", 1.5), "AUDJPY" to fx("AUDJPY", 2.0), "CADJPY" to fx("CADJPY", 2.4),
        "EURCHF" to fx("EURCHF", 2.0), "EURAUD" to fx("EURAUD", 2.6),
    )

    val MACRO = linkedMapOf("DXY" to "DX-Y.NYB", "US10Y" to "^TNX", "US5Y" to "^FVX", "US3M" to "^IRX",
        "VIX" to "^VIX", "SPX_FUT" to "ES=F", "WTI" to "CL=F")

    val SESSION_MULT = mapOf("rollover" to 3.0, "asia" to 1.3, "london" to 1.0, "overlap" to 1.0, "newyork" to 1.1, "late" to 1.6)

    fun get(s: String): Inst = ALL[s.uppercase()] ?: error("Instrumento desconhecido: $s")

    fun estimatedSpread(inst: Inst, t: Long) = inst.typicalSpreadPips * inst.pip * (SESSION_MULT[Time.sessionOf(t)] ?: 1.0)
}

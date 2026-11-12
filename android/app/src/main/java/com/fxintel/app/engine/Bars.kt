package com.fxintel.app.engine

import java.time.Instant
import java.time.ZoneOffset
import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min

/** Barras OHLCV (tempo = início da barra, segundos UTC). */
class Bars(val t: LongArray, val o: DoubleArray, val h: DoubleArray, val l: DoubleArray, val c: DoubleArray,
           val v: DoubleArray = DoubleArray(t.size)) {
    val n get() = t.size

    fun slice(from: Int, to: Int = n): Bars {
        val a = max(0, from); val b = min(n, to)
        return Bars(t.copyOfRange(a, b), o.copyOfRange(a, b), h.copyOfRange(a, b), l.copyOfRange(a, b),
            c.copyOfRange(a, b), v.copyOfRange(a, b))
    }

    fun tail(k: Int) = slice(n - k)

    fun filter(keep: (Int) -> Boolean): Bars {
        val idx = (0 until n).filter(keep)
        return Bars(LongArray(idx.size) { t[idx[it]] }, DoubleArray(idx.size) { o[idx[it]] },
            DoubleArray(idx.size) { h[idx[it]] }, DoubleArray(idx.size) { l[idx[it]] },
            DoubleArray(idx.size) { c[idx[it]] }, DoubleArray(idx.size) { v[idx[it]] })
    }

    fun map(f: (Double) -> Double) = Bars(t, DoubleArray(n) { f(o[it]) }, DoubleArray(n) { f(h[it]) },
        DoubleArray(n) { f(l[it]) }, DoubleArray(n) { f(c[it]) }, v)

    fun frame(): Frame = Frame(t).also { it["o"] = o; it["h"] = h; it["l"] = l; it["c"] = c; it["v"] = v }

    companion object {
        /** Remove NaN/valores não positivos, ordena, deduplica (mantém a última) e corrige h/l. */
        fun clean(t: LongArray, o: DoubleArray, h: DoubleArray, l: DoubleArray, c: DoubleArray, v: DoubleArray): Bars {
            val map = java.util.TreeMap<Long, Int>()
            for (i in t.indices) {
                if (o[i].isNaN() || h[i].isNaN() || l[i].isNaN() || c[i].isNaN()) continue
                if (o[i] <= 0 || h[i] <= 0 || l[i] <= 0 || c[i] <= 0) continue
                map[t[i]] = i
            }
            val idx = map.values.toIntArray()
            val tt = LongArray(idx.size) { t[idx[it]] }
            val oo = DoubleArray(idx.size) { o[idx[it]] }
            val cc = DoubleArray(idx.size) { c[idx[it]] }
            val hh = DoubleArray(idx.size) { max(max(o[idx[it]], h[idx[it]]), c[idx[it]]) }
            val ll = DoubleArray(idx.size) { min(min(o[idx[it]], l[idx[it]]), c[idx[it]]) }
            val vv = DoubleArray(idx.size) { val x = v[idx[it]]; if (x.isNaN()) 0.0 else x }
            return Bars(tt, oo, hh, ll, cc, vv)
        }

        fun merge(old: Bars, new: Bars): Bars {
            val m = java.util.TreeMap<Long, DoubleArray>()
            for (i in 0 until old.n) m[old.t[i]] = doubleArrayOf(old.o[i], old.h[i], old.l[i], old.c[i], old.v[i])
            for (i in 0 until new.n) m[new.t[i]] = doubleArrayOf(new.o[i], new.h[i], new.l[i], new.c[i], new.v[i])
            val keys = m.keys.toLongArray()
            val vals = m.values.toList()
            return Bars(keys, DoubleArray(keys.size) { vals[it][0] }, DoubleArray(keys.size) { vals[it][1] },
                DoubleArray(keys.size) { vals[it][2] }, DoubleArray(keys.size) { vals[it][3] }, DoubleArray(keys.size) { vals[it][4] })
        }
    }
}

object Time {
    fun weekday(t: Long): Int = Instant.ofEpochSecond(t).atOffset(ZoneOffset.UTC).dayOfWeek.value - 1 // seg=0
    fun hour(t: Long): Int = (Math.floorMod(t, 86400L) / 3600).toInt()

    fun sessionOf(t: Long): String {
        val h = hour(t); val wd = weekday(t)
        if (wd == 4 && h >= 19) return "late"
        if (h in 21..22) return "rollover"
        if (h >= 23 || h < 7) return "asia"
        if (h in 7..11) return "london"
        if (h in 12..15) return "overlap"
        return "newyork"
    }

    fun marketOpen(t: Long, kind: String = "fx"): Boolean {
        val wd = weekday(t); val h = hour(t)
        if (wd == 5) return false
        if (wd == 4 && h >= 21) return false
        if (wd == 6 && h < 21) return false
        if (kind == "metal" && h == 21) return false
        return true
    }
}

object BarOps {
    const val H1 = 3600L

    /** Barras fechadas: início + duração <= agora. */
    fun completed(b: Bars, tfSec: Long, now: Long): Bars = b.filter { b.t[it] + tfSec <= now }

    /** Remove barras fora da janela de negociação de balcão (proxies 24/7). */
    fun dropWeekend(b: Bars): Bars = b.filter {
        val wd = Time.weekday(b.t[it]); val h = Time.hour(b.t[it])
        !(wd == 5 || (wd == 4 && h >= 21) || (wd == 6 && h < 22))
    }

    /** Reparo de saltos artificiais de futuros contínuos (mesma lógica do Python). */
    fun repairLevelShifts(b: Bars, tfSec: Long, relThreshold: Double = 0.004): Pair<Bars, Int> {
        if (b.n < 3) return b to 0
        val off = DoubleArray(b.n)
        var count = 0
        val gaps = DoubleArray(b.n)
        for (i in 1 until b.n) {
            val dt = b.t[i] - b.t[i - 1]
            val gap = b.o[i] - b.c[i - 1]
            gaps[i] = gap
            if (dt <= tfSec * 1.5 && abs(gap) / max(b.c[i], 1e-12) > relThreshold) {
                count++
                for (j in 0 until i) off[j] += gap
            }
        }
        if (count == 0) return b to 0
        val o = DoubleArray(b.n) { b.o[it] + off[it] }
        val h = DoubleArray(b.n) { b.h[it] + off[it] }
        val l = DoubleArray(b.n) { b.l[it] + off[it] }
        val c = DoubleArray(b.n) { b.c[it] + off[it] }
        val rng = DoubleArray(b.n) { h[it] - l[it] }.filter { it > 0 }
        if (rng.isNotEmpty()) {
            val med = S.median(rng.toDoubleArray(), rng.size)
            val cap = 8 * med
            for (i in 0 until b.n) {
                h[i] = min(h[i], max(o[i], c[i]) + cap)
                l[i] = max(l[i], min(o[i], c[i]) - cap)
            }
        }
        val out = Bars(b.t, o, h, l, c, b.v).filter { o[it] > 0 && h[it] > 0 && l[it] > 0 && c[it] > 0 }
        return out to count
    }

    private fun resampleOffset(b: Bars, periodSec: Long, offsetSec: Long, labelShift: Long = 0): Bars {
        val keys = ArrayList<Long>(); val o = ArrayList<Double>(); val h = ArrayList<Double>()
        val l = ArrayList<Double>(); val c = ArrayList<Double>(); val v = ArrayList<Double>()
        for (i in 0 until b.n) {
            val k = Math.floorDiv(b.t[i] - offsetSec, periodSec) * periodSec + offsetSec
            if (keys.isEmpty() || keys.last() != k) {
                keys.add(k); o.add(b.o[i]); h.add(b.h[i]); l.add(b.l[i]); c.add(b.c[i]); v.add(b.v[i])
            } else {
                val j = keys.size - 1
                h[j] = max(h[j], b.h[i]); l[j] = min(l[j], b.l[i]); c[j] = b.c[i]; v[j] = v[j] + b.v[i]
            }
        }
        return Bars(LongArray(keys.size) { keys[it] + labelShift }, o.toDoubleArray(), h.toDoubleArray(),
            l.toDoubleArray(), c.toDoubleArray(), v.toDoubleArray())
    }

    /** H4/D1 derivados de H1, alinhados ao fechamento de Nova York (22:00 UTC). */
    fun derive(h1: Bars, tf: String): Bars = when (tf) {
        "H4" -> resampleOffset(h1, 4 * 3600, 2 * 3600)
        "D1" -> resampleOffset(h1, 86400, 22 * 3600, 2 * 3600).let { d -> d.filter { Time.weekday(d.t[it]) < 5 } }
        else -> error("tf $tf")
    }

    fun completionTimes(t: LongArray, tf: String): LongArray = when (tf) {
        "D1" -> LongArray(t.size) { t[it] + 22 * 3600 }
        "H4" -> LongArray(t.size) { t[it] + 4 * 3600 }
        "M15" -> LongArray(t.size) { t[it] + 900 }
        "M5" -> LongArray(t.size) { t[it] + 300 }
        else -> LongArray(t.size) { t[it] + 3600 }
    }

    /** Ajuste do proxy de metal ao spot: XAU multiplicativo (PAXG), XAG aditivo (base do futuro). */
    fun spotAdjust(symbol: String, b: Bars, spot: Double): Bars {
        if (b.n == 0 || spot.isNaN()) return b
        val last = b.c[b.n - 1]
        return if (symbol == "XAUUSD") { val r = spot / last; b.map { it * r } }
        else if (symbol == "XAGUSD") { val basis = last - spot; b.map { it - basis } }
        else b
    }

    fun floorTo(t: Long, sec: Long) = floor(t.toDouble() / sec).toLong() * sec
}

package com.fxintel.app.engine

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/**
 * Operações de séries temporais com a MESMA semântica do pandas usada no motor Python
 * (ewm adjust=False/ignore_na=False, rolling com min_periods e NaN ignorados, etc.).
 * A equivalência é verificada por testes "golden" contra saídas do motor Python.
 */
const val NAN = Double.NaN

fun Double.ok() = !this.isNaN()
fun DoubleArray.copyNaN() = DoubleArray(size) { NAN }
fun nanArray(n: Int) = DoubleArray(n) { NAN }
fun DoubleArray.lastOk(): Double = this.lastOrNull { !it.isNaN() } ?: NAN

object S {
    /** pandas ewm(alpha, adjust=False, ignore_na=False, min_periods).mean() */
    fun ewm(x: DoubleArray, alpha: Double, minPeriods: Int): DoubleArray {
        val n = x.size
        val out = nanArray(n)
        if (n == 0) return out
        val oldFactor = 1.0 - alpha
        var weighted = x[0]
        var nobs = if (weighted.isNaN()) 0 else 1
        var oldWt = 1.0
        out[0] = if (nobs >= minPeriods) weighted else NAN
        for (i in 1 until n) {
            val cur = x[i]
            val isObs = !cur.isNaN()
            if (isObs) nobs++
            if (!weighted.isNaN()) {
                oldWt *= oldFactor
                if (isObs) {
                    if (weighted != cur) {
                        weighted = (oldWt * weighted + alpha * cur) / (oldWt + alpha)
                    }
                    oldWt = 1.0
                }
            } else if (isObs) {
                weighted = cur
            }
            out[i] = if (nobs >= minPeriods) weighted else NAN
        }
        return out
    }

    fun ema(x: DoubleArray, span: Int) = ewm(x, 2.0 / (span + 1), span)
    fun wilder(x: DoubleArray, n: Int) = ewm(x, 1.0 / n, n)

    fun diff(x: DoubleArray, k: Int = 1) = DoubleArray(x.size) { i -> if (i >= k) x[i] - x[i - k] else NAN }
    fun shift(x: DoubleArray, k: Int = 1) = DoubleArray(x.size) { i -> if (i - k in x.indices) x[i - k] else NAN }

    private inline fun rolling(x: DoubleArray, w: Int, minP: Int, f: (DoubleArray, Int) -> Double): DoubleArray {
        val n = x.size
        val out = nanArray(n)
        val buf = DoubleArray(w)
        for (i in 0 until n) {
            var k = 0
            for (j in max(0, i - w + 1)..i) if (!x[j].isNaN()) { buf[k++] = x[j] }
            if (k >= minP && k > 0) out[i] = f(buf, k)
        }
        return out
    }

    fun rollingMean(x: DoubleArray, w: Int, minP: Int = w) = rolling(x, w, minP) { b, k -> var s = 0.0; for (i in 0 until k) s += b[i]; s / k }
    fun rollingSum(x: DoubleArray, w: Int, minP: Int = w) = rolling(x, w, minP) { b, k -> var s = 0.0; for (i in 0 until k) s += b[i]; s }
    fun rollingMax(x: DoubleArray, w: Int, minP: Int = w) = rolling(x, w, minP) { b, k -> var m = b[0]; for (i in 1 until k) m = max(m, b[i]); m }
    fun rollingMin(x: DoubleArray, w: Int, minP: Int = w) = rolling(x, w, minP) { b, k -> var m = b[0]; for (i in 1 until k) m = min(m, b[i]); m }
    fun rollingStd(x: DoubleArray, w: Int, minP: Int = w, ddof: Int = 1) = rolling(x, w, minP) { b, k ->
        if (k - ddof <= 0) NAN else {
            var s = 0.0; for (i in 0 until k) s += b[i]
            val m = s / k
            var ss = 0.0; for (i in 0 until k) ss += (b[i] - m) * (b[i] - m)
            sqrt(ss / (k - ddof))
        }
    }
    fun rollingMedian(x: DoubleArray, w: Int, minP: Int = w) = rolling(x, w, minP) { b, k -> median(b, k) }

    fun median(b: DoubleArray, k: Int): Double {
        val a = b.copyOf(k); a.sort()
        return if (k % 2 == 1) a[k / 2] else (a[k / 2 - 1] + a[k / 2]) / 2
    }

    /** rolling(n, min_periods).apply(lambda x: (x[:-1] < x[-1]).mean(), raw=True) — NaN entram na janela. */
    fun rollingPctBelowLast(x: DoubleArray, w: Int, minP: Int): DoubleArray {
        val out = nanArray(x.size)
        for (i in x.indices) {
            val s = max(0, i - w + 1)
            var cnt = 0
            for (j in s..i) if (!x[j].isNaN()) cnt++
            if (cnt < minP) continue
            val len = i - s + 1
            if (len <= 1) { out[i] = NAN; continue }
            val last = x[i]
            var below = 0
            for (j in s until i) if (x[j] < last) below++
            out[i] = below.toDouble() / (len - 1)
        }
        return out
    }

    /** rolling(n, min_periods).rank(pct=True) com média para empates. */
    fun rollingRankPct(x: DoubleArray, w: Int, minP: Int): DoubleArray {
        val out = nanArray(x.size)
        for (i in x.indices) {
            val cur = x[i]
            if (cur.isNaN()) continue
            var cnt = 0; var less = 0; var eq = 0
            for (j in max(0, i - w + 1)..i) {
                val v = x[j]
                if (v.isNaN()) continue
                cnt++
                if (v < cur) less++ else if (v == cur) eq++
            }
            if (cnt < minP) continue
            out[i] = (less + (eq + 1) / 2.0) / cnt
        }
        return out
    }

    fun clip(x: DoubleArray, lo: Double, hi: Double) = DoubleArray(x.size) { i -> val v = x[i]; if (v.isNaN()) NAN else min(hi, max(lo, v)) }
    fun sign(v: Double): Double = if (v.isNaN()) NAN else if (v > 0) 1.0 else if (v < 0) -1.0 else 0.0
    fun fill0(v: Double) = if (v.isNaN()) 0.0 else v
    fun zeroToNaN(v: Double) = if (v == 0.0) NAN else v
    fun absd(v: Double) = abs(v)
}

/** Quadro colunar estilo DataFrame: índice temporal (segundos UTC) e colunas Double (NaN = ausente). */
class Frame(val t: LongArray) {
    val cols = LinkedHashMap<String, DoubleArray>()
    val n: Int get() = t.size
    operator fun get(name: String): DoubleArray = cols[name] ?: nanArray(n)
    operator fun set(name: String, v: DoubleArray) { cols[name] = v }
    fun has(name: String) = cols.containsKey(name)
    fun at(name: String, i: Int): Double = cols[name]?.get(i) ?: NAN
    fun indexOf(time: Long): Int = t.binarySearch(time).let { if (it >= 0) it else -1 }
}

fun boolArr(n: Int, f: (Int) -> Boolean) = DoubleArray(n) { if (f(it)) 1.0 else 0.0 }

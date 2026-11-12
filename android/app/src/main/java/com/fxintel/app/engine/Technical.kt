package com.fxintel.app.engine

import kotlin.math.abs
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.min

/** Indicadores, estrutura (BOS/CHoCH), SMC, padrões, níveis de sessão e quadro MTF — porte fiel do Python. */
object Technical {

    // ------------------------------------------------------------------ indicadores
    fun trueRange(h: DoubleArray, l: DoubleArray, c: DoubleArray) = DoubleArray(h.size) { i ->
        val a = h[i] - l[i]
        if (i == 0) a else max(a, max(abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    }

    fun atr(h: DoubleArray, l: DoubleArray, c: DoubleArray, n: Int = 14) = S.wilder(trueRange(h, l, c), n)

    fun rsi(c: DoubleArray, n: Int = 14): DoubleArray {
        val d = S.diff(c)
        val up = S.wilder(DoubleArray(c.size) { if (d[it].isNaN()) NAN else max(d[it], 0.0) }, n)
        val dn = S.wilder(DoubleArray(c.size) { if (d[it].isNaN()) NAN else max(-d[it], 0.0) }, n)
        return DoubleArray(c.size) { i ->
            if (dn[i].isNaN()) NAN else {
                val rs = up[i] / S.zeroToNaN(dn[i])
                if (rs.isNaN()) 100.0 else 100 - 100 / (1 + rs)
            }
        }
    }

    fun computeBasic(f: Frame) {
        val o = f["o"]; val h = f["h"]; val l = f["l"]; val c = f["c"]; val n = f.n
        for (k in intArrayOf(8, 20, 50, 200)) f["ema$k"] = S.ema(c, k)
        f["atr"] = atr(h, l, c, 14)
        f["rsi"] = rsi(c, 14)
        val e12 = S.ema(c, 12); val e26 = S.ema(c, 26)
        val line = DoubleArray(n) { e12[it] - e26[it] }
        val sig = S.ewm(line, 2.0 / 10, 9)
        f["macd"] = line; f["macd_sig"] = sig; f["macd_hist"] = DoubleArray(n) { line[it] - sig[it] }
        // ADX / DI
        val up = S.diff(h); val dnv = DoubleArray(n) { if (it == 0) NAN else -(l[it] - l[it - 1]) }
        val plus = DoubleArray(n) { if (up[it] > dnv[it] && up[it] > 0) up[it] else 0.0 }
        val minus = DoubleArray(n) { if (dnv[it] > up[it] && dnv[it] > 0) dnv[it] else 0.0 }
        val a = f["atr"]
        val pw = S.wilder(plus, 14); val mw = S.wilder(minus, 14)
        val pdi = DoubleArray(n) { 100 * pw[it] / a[it] }
        val mdi = DoubleArray(n) { 100 * mw[it] / a[it] }
        val dx = DoubleArray(n) { 100 * abs(pdi[it] - mdi[it]) / S.zeroToNaN(pdi[it] + mdi[it]) }
        f["adx"] = S.wilder(dx, 14); f["pdi"] = pdi; f["mdi"] = mdi
        val m = S.rollingMean(c, 20, 20); val sd = S.rollingStd(c, 20, 20, 0)
        f["bb_mid"] = m
        f["bb_up"] = DoubleArray(n) { m[it] + 2 * sd[it] }
        f["bb_lo"] = DoubleArray(n) { m[it] - 2 * sd[it] }
        f["bb_width"] = DoubleArray(n) { (4 * sd[it]) / m[it] }
        val net = DoubleArray(n) { if (it >= 20) abs(c[it] - c[it - 20]) else NAN }
        val path = S.rollingSum(DoubleArray(n) { if (it == 0) NAN else abs(c[it] - c[it - 1]) }, 20, 20)
        f["er"] = DoubleArray(n) { net[it] / S.zeroToNaN(path[it]) }
        val lo14 = S.rollingMin(l, 14, 14); val hi14 = S.rollingMax(h, 14, 14)
        val k = DoubleArray(n) { 100 * (c[it] - lo14[it]) / S.zeroToNaN(hi14[it] - lo14[it]) }
        f["stoch_k"] = k; f["stoch_d"] = S.rollingMean(k, 3, 3)
        f["atr_fast"] = atr(h, l, c, 5)
        f["atr_slow"] = atr(h, l, c, 50)
        f["vwap"] = nanArray(n)  // FX spot sem volume real: VWAP não aplicável
        check(o.size == n)
    }

    // ------------------------------------------------------------------ estrutura
    class Swing(val idx: Int, val confirm: Int, val time: Long, val price: Double, val kind: Char) {
        var label = ""; var equal = false
    }

    fun findSwings(h: DoubleArray, l: DoubleArray, t: LongArray, left: Int, right: Int): List<Swing> {
        val out = ArrayList<Swing>()
        val n = h.size
        for (i in left until n - right) {
            var mx = h[i - left]; for (j in i - left..i + right) mx = max(mx, h[j])
            var hiOk = h[i] == mx
            if (hiOk) for (j in i + 1..i + right) if (!(h[i] > h[j])) { hiOk = false; break }
            if (hiOk) out.add(Swing(i, i + right, t[i], h[i], 'H'))
            var mn = l[i - left]; for (j in i - left..i + right) mn = min(mn, l[j])
            var loOk = l[i] == mn
            if (loOk) for (j in i + 1..i + right) if (!(l[i] < l[j])) { loOk = false; break }
            if (loOk) out.add(Swing(i, i + right, t[i], l[i], 'L'))
        }
        return out.sortedWith(compareBy({ it.confirm }, { it.idx }))
    }

    fun marketStructure(f: Frame, left: Int, right: Int, eqTolAtr: Double = 0.15, maxActive: Int = 40): List<Swing> {
        val h = f["h"]; val lo = f["l"]; val c = f["c"]; val a = f["atr"]; val n = f.n
        val swings = findSwings(h, lo, f.t, left, right)
        val byConfirm = swings.groupBy { it.confirm }
        val trend = DoubleArray(n); val event = DoubleArray(n); val lastEvent = DoubleArray(n)
        val since = DoubleArray(n) { 9999.0 }
        val lastSh = nanArray(n); val lastSl = nanArray(n); val nearHi = nanArray(n); val nearLo = nanArray(n)
        val nearHiEq = DoubleArray(n); val nearLoEq = DoubleArray(n)
        val sweepHi = nanArray(n); val sweepLo = nanArray(n); val sweepHiEq = DoubleArray(n); val sweepLoEq = DoubleArray(n)
        val bias = DoubleArray(n); val originLoArr = nanArray(n); val originHiArr = nanArray(n)
        var state = 0
        var shPrice = NAN; var slPrice = NAN; var shBroken = true; var slBroken = true
        var prevSh: Swing? = null; var prevSl: Swing? = null
        var labH = ""; var labL = ""
        var actHi = ArrayList<DoubleArray>()  // [price, idx, equal]
        var actLo = ArrayList<DoubleArray>()
        var evLast = 0; var evAt = -10_000
        var originLo = NAN; var originHi = NAN
        var recentLows = ArrayList<Double>(); var recentHighs = ArrayList<Double>()
        for (t in 0 until n) {
            val tol = (if (a[t].isNaN()) 0.0 else a[t]) * eqTolAtr
            for (s in byConfirm[t] ?: emptyList()) {
                if (s.kind == 'H') {
                    prevSh?.let { s.label = if (s.price > it.price) "HH" else "LH" }
                    labH = s.label; prevSh = s; shPrice = s.price; shBroken = false
                    var eq = false
                    for (lv in actHi) if (abs(lv[0] - s.price) <= tol) { lv[2] = 1.0; eq = true }
                    s.equal = eq
                    actHi.add(doubleArrayOf(s.price, s.idx.toDouble(), if (eq) 1.0 else 0.0))
                    recentHighs.add(s.price)
                } else {
                    prevSl?.let { s.label = if (s.price > it.price) "HL" else "LL" }
                    labL = s.label; prevSl = s; slPrice = s.price; slBroken = false
                    var eq = false
                    for (lv in actLo) if (abs(lv[0] - s.price) <= tol) { lv[2] = 1.0; eq = true }
                    s.equal = eq
                    actLo.add(doubleArrayOf(s.price, s.idx.toDouble(), if (eq) 1.0 else 0.0))
                    recentLows.add(s.price)
                }
            }
            if (actHi.size > maxActive) actHi = ArrayList(actHi.subList(actHi.size - maxActive, actHi.size))
            if (actLo.size > maxActive) actLo = ArrayList(actLo.subList(actLo.size - maxActive, actLo.size))
            if (recentLows.size > 5) recentLows = ArrayList(recentLows.subList(recentLows.size - 5, recentLows.size))
            if (recentHighs.size > 5) recentHighs = ArrayList(recentHighs.subList(recentHighs.size - 5, recentHighs.size))

            val sweptH = actHi.filter { h[t] > it[0] }
            if (sweptH.isNotEmpty()) {
                val best = sweptH.maxByOrNull { it[0] }!!
                if (c[t] < best[0]) { sweepHi[t] = best[0]; sweepHiEq[t] = if (sweptH.any { it[2] > 0 }) 1.0 else 0.0 }
                actHi = ArrayList(actHi.filter { h[t] <= it[0] })
            }
            val sweptL = actLo.filter { lo[t] < it[0] }
            if (sweptL.isNotEmpty()) {
                val best = sweptL.minByOrNull { it[0] }!!
                if (c[t] > best[0]) { sweepLo[t] = best[0]; sweepLoEq[t] = if (sweptL.any { it[2] > 0 }) 1.0 else 0.0 }
                actLo = ArrayList(actLo.filter { lo[t] >= it[0] })
            }
            var ev = 0
            if (!shBroken && c[t] > shPrice) {
                ev = if (state == 1) 1 else 2; state = 1; shBroken = true
                originLo = if (recentLows.isNotEmpty()) recentLows.last() else lo[t]
            }
            if (!slBroken && c[t] < slPrice) {
                ev = if (state == -1) -1 else -2; state = -1; slBroken = true
                originHi = if (recentHighs.isNotEmpty()) recentHighs.last() else h[t]
            }
            if (ev != 0) { evLast = ev; evAt = t }
            trend[t] = state.toDouble(); event[t] = ev.toDouble(); lastEvent[t] = evLast.toDouble()
            since[t] = if (evAt >= 0) (t - evAt).toDouble() else 9999.0
            lastSh[t] = shPrice; lastSl[t] = slPrice; originLoArr[t] = originLo; originHiArr[t] = originHi
            actHi.minByOrNull { it[0] }?.let { nearHi[t] = it[0]; nearHiEq[t] = it[2] }
            actLo.maxByOrNull { it[0] }?.let { nearLo[t] = it[0]; nearLoEq[t] = it[2] }
            bias[t] = if (labH == "HH" && labL == "HL") 1.0 else if (labH == "LH" && labL == "LL") -1.0 else 0.0
        }
        f["trend"] = trend; f["event"] = event; f["last_event"] = lastEvent; f["since_event"] = since
        f["last_sh"] = lastSh; f["last_sl"] = lastSl; f["near_hi"] = nearHi; f["near_lo"] = nearLo
        f["near_hi_eq"] = nearHiEq; f["near_lo_eq"] = nearLoEq; f["sweep_hi"] = sweepHi; f["sweep_lo"] = sweepLo
        f["sweep_hi_eq"] = sweepHiEq; f["sweep_lo_eq"] = sweepLoEq; f["swing_bias"] = bias
        f["leg_origin_lo"] = originLoArr; f["leg_origin_hi"] = originHiArr
        return swings
    }

    // ------------------------------------------------------------------ SMC
    fun smc(f: Frame, minFvgAtr: Double = 0.15, dispAtr: Double = 1.2, maxZones: Int = 25) {
        val o = f["o"]; val h = f["h"]; val lo = f["l"]; val c = f["c"]; val a = f["atr"]; val ev = f["event"]; val n = f.n
        val names = listOf("fvg_bull_top", "fvg_bull_bot", "fvg_bear_top", "fvg_bear_bot", "ob_bull_top", "ob_bull_bot", "ob_bear_top", "ob_bear_bot")
        val cols = names.associateWith { nanArray(n) }
        val inFvgBull = DoubleArray(n); val inFvgBear = DoubleArray(n); val inObBull = DoubleArray(n); val inObBear = DoubleArray(n)
        val newFvg = DoubleArray(n); val disp = DoubleArray(n)
        var fb = ArrayList<DoubleArray>(); var fs = ArrayList<DoubleArray>(); var ob = ArrayList<DoubleArray>(); var os = ArrayList<DoubleArray>()
        for (t in 0 until n) {
            val at = a[t]
            if (t >= 2 && !at.isNaN()) {
                if (lo[t] > h[t - 2] && (lo[t] - h[t - 2]) >= minFvgAtr * at) { fb.add(doubleArrayOf(lo[t], h[t - 2])); newFvg[t] = 1.0 }
                else if (h[t] < lo[t - 2] && (lo[t - 2] - h[t]) >= minFvgAtr * at) { fs.add(doubleArrayOf(lo[t - 2], h[t])); newFvg[t] = -1.0 }
                val body = abs(c[t] - o[t]); val rng = h[t] - lo[t]
                if (rng > 0 && body >= dispAtr * at && body / rng >= 0.6) disp[t] = if (c[t] > o[t]) 1.0 else -1.0
            }
            if (ev[t] > 0) {
                var j = t - 1
                while (j >= max(t - 12, 0)) { if (c[j] < o[j]) { ob.add(doubleArrayOf(h[j], lo[j])); break }; j-- }
            } else if (ev[t] < 0) {
                var j = t - 1
                while (j >= max(t - 12, 0)) { if (c[j] > o[j]) { os.add(doubleArrayOf(h[j], lo[j])); break }; j-- }
            }
            var keep = ArrayList<DoubleArray>()
            for (z in fb) { if (lo[t] <= z[1]) continue; if (lo[t] <= z[0] && c[t] >= z[1]) inFvgBull[t] = 1.0; keep.add(z) }
            fb = tail(keep, maxZones)
            keep = ArrayList()
            for (z in fs) { if (h[t] >= z[0]) continue; if (h[t] >= z[1] && c[t] <= z[0]) inFvgBear[t] = 1.0; keep.add(z) }
            fs = tail(keep, maxZones)
            keep = ArrayList()
            for (z in ob) { if (c[t] < z[1]) continue; if (lo[t] <= z[0]) inObBull[t] = 1.0; keep.add(z) }
            ob = tail(keep, maxZones)
            keep = ArrayList()
            for (z in os) { if (c[t] > z[0]) continue; if (h[t] >= z[1]) inObBear[t] = 1.0; keep.add(z) }
            os = tail(keep, maxZones)
            fb.filter { it[1] <= c[t] }.maxByOrNull { it[0] }?.let { cols["fvg_bull_top"]!![t] = it[0]; cols["fvg_bull_bot"]!![t] = it[1] }
            fs.filter { it[0] >= c[t] }.minByOrNull { it[1] }?.let { cols["fvg_bear_top"]!![t] = it[0]; cols["fvg_bear_bot"]!![t] = it[1] }
            ob.filter { it[1] <= c[t] }.maxByOrNull { it[0] }?.let { cols["ob_bull_top"]!![t] = it[0]; cols["ob_bull_bot"]!![t] = it[1] }
            os.filter { it[0] >= c[t] }.minByOrNull { it[1] }?.let { cols["ob_bear_top"]!![t] = it[0]; cols["ob_bear_bot"]!![t] = it[1] }
        }
        for ((k, v) in cols) f[k] = v
        f["in_fvg_bull"] = inFvgBull; f["in_fvg_bear"] = inFvgBear; f["in_ob_bull"] = inObBull; f["in_ob_bear"] = inObBear
        f["new_fvg"] = newFvg; f["displacement"] = disp
    }

    private fun tail(l: ArrayList<DoubleArray>, k: Int) = if (l.size > k) ArrayList(l.subList(l.size - k, l.size)) else l

    // ------------------------------------------------------------------ padrões
    fun patterns(f: Frame) {
        val o = f["o"]; val h = f["h"]; val l = f["l"]; val c = f["c"]; val a = f["atr"]; val n = f.n
        val body = DoubleArray(n) { abs(c[it] - o[it]) }
        val rng = DoubleArray(n) { S.zeroToNaN(h[it] - l[it]) }
        val upper = DoubleArray(n) { h[it] - max(o[it], c[it]) }
        val lower = DoubleArray(n) { min(o[it], c[it]) - l[it] }
        val bodyRatio = DoubleArray(n) { body[it] / rng[it] }
        val upperRatio = DoubleArray(n) { upper[it] / rng[it] }
        val lowerRatio = DoubleArray(n) { lower[it] / rng[it] }
        f["bull_engulf"] = boolArr(n) { it > 0 && c[it] > o[it] && c[it - 1] < o[it - 1] && c[it] >= o[it - 1] && o[it] <= c[it - 1] && body[it] > 0.5 * a[it] }
        f["bear_engulf"] = boolArr(n) { it > 0 && c[it] < o[it] && c[it - 1] > o[it - 1] && c[it] <= o[it - 1] && o[it] >= c[it - 1] && body[it] > 0.5 * a[it] }
        f["bull_pin"] = boolArr(n) { lower[it] >= 2 * body[it] && lowerRatio[it] >= 0.55 && rng[it] >= 0.6 * a[it] }
        f["bear_pin"] = boolArr(n) { upper[it] >= 2 * body[it] && upperRatio[it] >= 0.55 && rng[it] >= 0.6 * a[it] }
        f["inside"] = boolArr(n) { it > 0 && h[it] <= h[it - 1] && l[it] >= l[it - 1] }
        f["doji"] = boolArr(n) { bodyRatio[it] <= 0.1 }
        val r = DoubleArray(n) { h[it] - l[it] }
        val m5 = S.rollingMean(r, 5, 5); val m50 = S.rollingMean(r, 50, 50)
        f["compression"] = DoubleArray(n) { m5[it] / m50[it] }
        f["close_pos"] = DoubleArray(n) { (c[it] - l[it]) / rng[it] }
        // rompimentos de Donchian (20) e falsos rompimentos
        val hi = S.shift(S.rollingMax(h, 20, 20)); val lo = S.shift(S.rollingMin(l, 20, 20))
        val up = boolArr(n) { c[it] > hi[it] }; val dn = boolArr(n) { c[it] < lo[it] }
        val recentUp = S.shift(S.rollingMax(up, 3, 1)).map { if (it.isNaN()) 0.0 else it }.toDoubleArray()
        val recentDn = S.shift(S.rollingMax(dn, 3, 1)).map { if (it.isNaN()) 0.0 else it }.toDoubleArray()
        f["brk_up"] = up; f["brk_dn"] = dn
        f["fail_up"] = boolArr(n) { recentUp[it] > 0 && c[it] < hi[it] }
        f["fail_dn"] = boolArr(n) { recentDn[it] > 0 && c[it] > lo[it] }
        f["don_hi"] = hi; f["don_lo"] = lo
    }

    fun rsiDivergence(swings: List<Swing>, rsi: DoubleArray, persist: Int = 10): DoubleArray {
        val out = DoubleArray(rsi.size)
        val lows = swings.filter { it.kind == 'L' }; val highs = swings.filter { it.kind == 'H' }
        for ((seq, sign) in listOf(lows to 1, highs to -1)) {
            for (k in 0 until seq.size - 1) {
                val a = seq[k]; val b = seq[k + 1]
                if (b.idx - a.idx > 60 || rsi[a.idx].isNaN() || rsi[b.idx].isNaN()) continue
                if (sign == 1 && b.price < a.price && rsi[b.idx] > rsi[a.idx] + 2)
                    for (j in b.confirm until min(rsi.size, b.confirm + persist)) out[j] = 1.0
                if (sign == -1 && b.price > a.price && rsi[b.idx] < rsi[a.idx] - 2)
                    for (j in b.confirm until min(rsi.size, b.confirm + persist)) out[j] = -1.0
            }
        }
        return out
    }

    // ------------------------------------------------------------------ níveis de sessão
    fun sessionLevels(f: Frame) {
        val t = f.t; val h = f["h"]; val l = f["l"]; val o = f["o"]; val n = f.n
        val day = LongArray(n) { Math.floorDiv(t[it] + 7200, 86400L) }
        val dayHigh = LinkedHashMap<Long, Double>(); val dayLow = LinkedHashMap<Long, Double>()
        for (i in 0 until n) {
            dayHigh[day[i]] = max(dayHigh[day[i]] ?: Double.NEGATIVE_INFINITY, h[i])
            dayLow[day[i]] = min(dayLow[day[i]] ?: Double.POSITIVE_INFINITY, l[i])
        }
        val days = dayHigh.keys.toList()
        val prevH = HashMap<Long, Double>(); val prevL = HashMap<Long, Double>()
        for (k in days.indices) { prevH[days[k]] = if (k > 0) dayHigh[days[k - 1]]!! else NAN; prevL[days[k]] = if (k > 0) dayLow[days[k - 1]]!! else NAN }
        val week = LongArray(n) { val d = day[it]; d - Time.weekday(d * 86400) }
        val wkH = LinkedHashMap<Long, Double>(); val wkL = LinkedHashMap<Long, Double>()
        for (i in 0 until n) { wkH[week[i]] = max(wkH[week[i]] ?: Double.NEGATIVE_INFINITY, h[i]); wkL[week[i]] = min(wkL[week[i]] ?: Double.POSITIVE_INFINITY, l[i]) }
        val weeks = wkH.keys.toList()
        val pwH = HashMap<Long, Double>(); val pwL = HashMap<Long, Double>()
        for (k in weeks.indices) { pwH[weeks[k]] = if (k > 0) wkH[weeks[k - 1]]!! else NAN; pwL[weeks[k]] = if (k > 0) wkL[weeks[k - 1]]!! else NAN }
        val pdh = nanArray(n); val pdl = nanArray(n); val pwh = nanArray(n); val pwl = nanArray(n)
        val ah = nanArray(n); val al = nanArray(n); val dh = nanArray(n); val dl = nanArray(n); val dOpen = nanArray(n)
        var curDay = Long.MIN_VALUE; var runAh = NAN; var runAl = NAN; var runDh = NAN; var runDl = NAN; var openD = NAN
        for (i in 0 until n) {
            if (day[i] != curDay) { curDay = day[i]; runAh = NAN; runAl = NAN; runDh = NAN; runDl = NAN; openD = o[i] }
            pdh[i] = prevH[day[i]]!!; pdl[i] = prevL[day[i]]!!; pwh[i] = pwH[week[i]]!!; pwl[i] = pwL[week[i]]!!
            val hr = Time.hour(t[i])
            if (hr >= 22 || hr < 7) {
                runAh = if (runAh.isNaN()) h[i] else max(runAh, h[i])
                runAl = if (runAl.isNaN()) l[i] else min(runAl, l[i])
            }
            ah[i] = runAh; al[i] = runAl
            runDh = if (runDh.isNaN()) h[i] else max(runDh, h[i]); runDl = if (runDl.isNaN()) l[i] else min(runDl, l[i])
            dh[i] = runDh; dl[i] = runDl; dOpen[i] = openD
        }
        f["pdh"] = pdh; f["pdl"] = pdl; f["pwh"] = pwh; f["pwl"] = pwl; f["asia_h"] = ah; f["asia_l"] = al
        f["day_h"] = dh; f["day_l"] = dl; f["day_open"] = dOpen
    }

    // ------------------------------------------------------------------ quadro por TF e MTF
    val SWING = mapOf("M5" to (3 to 3), "M15" to (3 to 3), "H1" to (3 to 3), "H4" to (2 to 2), "D1" to (2 to 2))

    class TfResult(val frame: Frame, val swings: List<Swing>)

    fun tfFrame(b: Bars, tf: String, withPercentiles: Boolean = true): TfResult {
        val f = b.frame()
        computeBasic(f)
        val (le, ri) = SWING[tf] ?: (3 to 3)
        val sw = marketStructure(f, le, ri)
        smc(f)
        patterns(f)
        val n = f.n
        f["rsi_div"] = rsiDivergence(sw, f["rsi"])
        val e8 = f["ema8"]; val e20 = f["ema20"]; val e50 = f["ema50"]; val c = f["c"]
        f["ema_stack"] = DoubleArray(n) { if (e8[it] > e20[it] && e20[it] > e50[it]) 1.0 else if (e8[it] < e20[it] && e20[it] < e50[it]) -1.0 else 0.0 }
        val e200 = f["ema200"]
        f["above_ema200"] = DoubleArray(n) { S.fill0(S.sign(c[it] - e200[it])) }
        f["macd_slope"] = S.diff(f["macd_hist"])
        f["ret1"] = DoubleArray(n) { if (it == 0) NAN else ln(c[it]) - ln(c[it - 1]) }
        if (withPercentiles) {
            val a = f["atr"]
            f["atr_pct"] = S.rollingPctBelowLast(DoubleArray(n) { a[it] / c[it] }, 500, 100)
        }
        return TfResult(f, sw)
    }

    val HTF_COLS = listOf("c", "ema20", "ema50", "ema200", "atr", "rsi", "adx", "pdi", "mdi", "macd_hist",
        "macd_slope", "trend", "last_event", "since_event", "swing_bias", "ema_stack", "above_ema200", "last_sh",
        "last_sl", "near_hi", "near_lo", "er", "bb_width", "in_fvg_bull", "in_fvg_bear", "in_ob_bull", "in_ob_bear",
        "fvg_bull_top", "fvg_bull_bot", "fvg_bear_top", "fvg_bear_bot", "ob_bull_top", "ob_bull_bot", "ob_bear_top",
        "ob_bear_bot", "rsi_div")

    /** merge_asof (backward) pelos horários de conclusão — sem informação futura. */
    fun alignHtf(base: Frame, baseTf: String, htf: Frame, tf: String, prefix: String) {
        val left = BarOps.completionTimes(base.t, baseTf)
        val right = BarOps.completionTimes(htf.t, tf)
        val idx = IntArray(base.n)
        var j = -1
        for (i in 0 until base.n) {
            while (j + 1 < right.size && right[j + 1] <= left[i]) j++
            idx[i] = j
        }
        for (col in HTF_COLS) {
            if (!htf.has(col)) continue
            val src = htf[col]
            base["$prefix$col"] = DoubleArray(base.n) { if (idx[it] >= 0) src[idx[it]] else NAN }
        }
    }

    class Mtf(val F: Frame, val frames: Map<String, TfResult>)

    fun buildFrame(h1: Bars, h4: Bars, d1: Bars): Mtf {
        val f1 = tfFrame(h1, "H1")
        val f4 = tfFrame(h4, "H4", false)
        val fd = tfFrame(d1, "D1", false)
        val F = f1.frame
        sessionLevels(F)
        alignHtf(F, "H1", f4.frame, "H4", "h4_")
        alignHtf(F, "H1", fd.frame, "D1", "d1_")
        return Mtf(F, mapOf("H1" to f1, "H4" to f4, "D1" to fd))
    }

    // ------------------------------------------------------------------ resumo legível
    data class TfSummary(val tf: String, val direction: Int, val trendText: String, val lastEvent: String,
                         val adx: Double, val rsi: Double, val close: Double)

    fun summary(f: Frame, tf: String): TfSummary {
        val i = f.n - 1
        val adx = f.at("adx", i).let { if (it.isNaN()) 0.0 else it }
        val dirRaw = 0.45 * f.at("trend", i) + 0.25 * f.at("ema_stack", i) + 0.15 * f.at("swing_bias", i) +
            0.15 * (if (f.at("pdi", i) > f.at("mdi", i)) 1 else -1)
        val dir = S.sign(dirRaw).let { if (it.isNaN()) 0 else it.toInt() }
        val base = when (f.at("trend", i).toInt()) { 1 -> "alta"; -1 -> "baixa"; else -> "indefinida" }
        val force = if (adx >= 25) "forte" else if (adx >= 18) "moderada" else "fraca"
        val seq = when (f.at("swing_bias", i).toInt()) { 1 -> "topos e fundos ascendentes"; -1 -> "topos e fundos descendentes"; else -> "sequência mista" }
        val ev = when (f.at("last_event", i).toInt()) { 1 -> "BOS de alta"; 2 -> "CHoCH de alta"; -1 -> "BOS de baixa"; -2 -> "CHoCH de baixa"; else -> "—" }
        return TfSummary(tf, dir, "$base ($force, ADX ${"%.0f".format(adx)}; $seq)", ev, adx, f.at("rsi", i), f.at("c", i))
    }

    fun alignment(s: Map<String, TfSummary>): Double {
        val w = mapOf("D1" to 0.30, "H4" to 0.30, "H1" to 0.20, "M15" to 0.12, "M5" to 0.08)
        val tot = s.keys.sumOf { w[it] ?: 0.0 }
        return if (tot == 0.0) 0.0 else s.entries.sumOf { (w[it.key] ?: 0.0) * it.value.direction } / tot
    }
}

package com.fxintel.app.engine

import kotlin.math.max
import kotlin.math.min

/** Geração de candidatos (PULLBACK, BREAKOUT, SWEEP, TREND) e alvos — porte fiel de signals/candidates.py. */
object Candidates {
    val SETUP_PT = mapOf(
        "PULLBACK" to "Pullback em tendência",
        "BREAKOUT" to "Rompimento de estrutura com deslocamento",
        "SWEEP" to "Varredura de liquidez / falso rompimento",
        "TREND" to "Momentum de série temporal (BOS de continuação alinhado D1/H4/H1)",
    )
    const val MIN_RISK_ATR = 1.0
    const val MAX_RISK_ATR = 2.5
    const val MIN_TP1_R = 1.3
    const val MAX_TP1_R = 3.0
    const val DEFAULT_TP1_R = 1.5

    data class Cand(
        val i: Int, val t: Long, val dir: Int, val setup: String, val entryRef: Double, val sl: Double,
        val tp1: Double, val tp2: Double, val risk: Double, val riskAtr: Double, val rr1: Double, val rr2: Double,
        val roomR: Double, val tp1Structural: Int, val nSetups: Int, val inZone: Int, val atEma: Int,
        val triggerEngulf: Int, val triggerPin: Int, val pdSweep: Int, val d1Dir: Double, val atr: Double,
    )

    private data class Raw(val i: Int, val dir: Int, val setup: String, val sl: Double, val nSetups: Int, val d1Dir: Double,
                           val inZone: Int, val atEma: Int, val engulf: Int, val pin: Int, val pdSweep: Int)

    private fun side(d: Int) = if (d == 1) mapOf(
        "in_fvg" to "in_fvg_bull", "in_ob" to "in_ob_bull", "engulf" to "bull_engulf", "pin" to "bull_pin",
        "sweep" to "sweep_lo", "sweep_eq" to "sweep_lo_eq", "near_t" to "near_hi", "h4_near_t" to "h4_near_hi",
        "pd_t" to "pdh", "pw_t" to "pwh", "opp_fvg" to "fvg_bear_bot", "opp_ob" to "ob_bear_bot",
        "h4_in_fvg" to "h4_in_fvg_bull", "h4_in_ob" to "h4_in_ob_bull", "h4_sh" to "h4_last_sh",
    ) else mapOf(
        "in_fvg" to "in_fvg_bear", "in_ob" to "in_ob_bear", "engulf" to "bear_engulf", "pin" to "bear_pin",
        "sweep" to "sweep_hi", "sweep_eq" to "sweep_hi_eq", "near_t" to "near_lo", "h4_near_t" to "h4_near_lo",
        "pd_t" to "pdl", "pw_t" to "pwl", "opp_fvg" to "fvg_bull_top", "opp_ob" to "ob_bull_top",
        "h4_in_fvg" to "h4_in_fvg_bear", "h4_in_ob" to "h4_in_ob_bear", "h4_sh" to "h4_last_sl",
    )

    private fun dirFrame(F: Frame, d: Int, from: Int): List<Raw> {
        val s = side(d); val n = F.n
        val c = F["c"]; val o = F["o"]; val h = F["h"]; val lo = F["l"]; val atr = F["atr"]
        val d1Trend = F["d1_trend"]; val d1Stack = F["d1_ema_stack"]; val d1Above = F["d1_above_ema200"]
        val h4TrendRaw = F["h4_trend"]; val h4AdxRaw = F["h4_adx"]; val d1AdxRaw = F["d1_adx"]
        val ema20 = F["ema20"]; val ema50 = F["ema50"]; val rsi = F["rsi"]; val event = F["event"]
        val closePos = F["close_pos"]; val disp = F["displacement"]; val newFvg = F["new_fvg"]
        val inFvgMax = S.rollingMax(F[s["in_fvg"]!!], 3, 1); val inObMax = S.rollingMax(F[s["in_ob"]!!], 3, 1)
        val h4InFvg = F[s["h4_in_fvg"]!!]; val h4InOb = F[s["h4_in_ob"]!!]
        val engulf = F[s["engulf"]!!]; val pin = F[s["pin"]!!]
        val sweepLv = F[s["sweep"]!!]; val sweepEq = F[s["sweep_eq"]!!]
        val pdl = F["pdl"]; val pdh = F["pdh"]; val h4Sl = F["h4_last_sl"]; val h4Sh = F["h4_last_sh"]
        val lastSl = F["last_sl"]; val lastSh = F["last_sh"]
        val lo3 = S.rollingMin(lo, 3, 1); val hi3 = S.rollingMax(h, 3, 1)
        val lo6 = S.rollingMin(lo, 6, 1); val hi6 = S.rollingMax(h, 6, 1)
        val rsiMin6 = S.rollingMin(rsi, 6, 1); val rsiMax6 = S.rollingMax(rsi, 6, 1)
        val out = ArrayList<Raw>()
        for (i in from until n) {
            val d1Dir = S.sign(0.5 * S.fill0(d1Trend[i]) + 0.3 * S.fill0(d1Stack[i]) + 0.2 * S.fill0(d1Above[i]))
            val h4Trend = S.fill0(h4TrendRaw[i]); val h4Adx = S.fill0(h4AdxRaw[i]); val d1Adx = S.fill0(d1AdxRaw[i])
            val ext20 = d * (c[i] - ema20[i]) / atr[i]
            val rsiDirPrev = if (i > 0) d * (rsi[i - 1] - 50) else NAN
            val inZone = inFvgMax[i] > 0 || inObMax[i] > 0 || S.fill0(h4InFvg[i]) > 0 || S.fill0(h4InOb[i]) > 0
            val atEma: Boolean; val momentum: Boolean; val pulled: Boolean; val swingExt: Double
            if (d == 1) {
                atEma = lo3[i] <= ema50[i] + 0.3 * atr[i]
                momentum = i > 0 && c[i] > h[i - 1] && closePos[i] > 0.6 && c[i] > o[i]
                pulled = rsiMin6[i] < 45; swingExt = lo6[i]
            } else {
                atEma = hi3[i] >= ema50[i] - 0.3 * atr[i]
                momentum = i > 0 && c[i] < lo[i - 1] && closePos[i] < 0.4 && c[i] < o[i]
                pulled = rsiMax6[i] > 55; swingExt = hi6[i]
            }
            val evSign = S.sign(event[i])
            val trigger = engulf[i] > 0 || pin[i] > 0 || momentum || evSign == d.toDouble()
            val pullback = h4Trend == d.toDouble() && d1Dir != -d.toDouble() && pulled && (atEma || inZone) && trigger && ext20 < 1.5
            val structBreak = evSign == d.toDouble()
            val dsp = disp[i] == d.toDouble() || (i > 0 && disp[i - 1] == d.toDouble())
            val fvg = newFvg[i] == d.toDouble() || (i > 0 && newFvg[i - 1] == d.toDouble())
            val breakout = structBreak && dsp && fvg && h4Trend != -d.toDouble() && !(d1Dir == -d.toDouble() && d1Adx > 25) && ext20 < 2.2
            val eqSweep = !sweepLv[i].isNaN() && sweepEq[i] > 0
            val pdSweep: Boolean; val h4Sweep: Boolean; val wickOk: Boolean
            if (d == 1) {
                pdSweep = lo[i] < pdl[i] && c[i] > pdl[i]; h4Sweep = lo[i] < h4Sl[i] && c[i] > h4Sl[i]; wickOk = closePos[i] >= 0.55
            } else {
                pdSweep = h[i] > pdh[i] && c[i] < pdh[i]; h4Sweep = h[i] > h4Sh[i] && c[i] < h4Sh[i]; wickOk = closePos[i] <= 0.45
            }
            val sweep = (eqSweep || pdSweep || h4Sweep) && wickOk && (d1Dir != -d.toDouble() || rsiDirPrev < -15) &&
                !(h4Trend == -d.toDouble() && h4Adx > 30)
            val trendMom = evSign == d.toDouble() && F["trend"][i] == d.toDouble() && h4Trend == d.toDouble() &&
                d1Dir == d.toDouble() && d1Adx >= 20 && ext20 < 1.2
            val buf = 0.25 * atr[i]
            var setup = ""; var stop = NAN
            if (trendMom) { setup = "TREND"; stop = (if (d == 1) lastSl[i] else lastSh[i]) - d * buf }
            if (breakout) { setup = "BREAKOUT"; stop = (if (d == 1) lo3[i] else hi3[i]) - d * 0.2 * atr[i] }
            if (pullback) { setup = "PULLBACK"; stop = swingExt - d * buf }
            if (sweep) { setup = "SWEEP"; stop = (if (d == 1) lo[i] else h[i]) - d * buf }
            if (setup.isEmpty()) continue
            val nSet = listOf(pullback, breakout, sweep, trendMom).count { it }
            out.add(Raw(i, d, setup, stop, nSet, d1Dir, if (inZone) 1 else 0, if (atEma) 1 else 0,
                engulf[i].toInt(), pin[i].toInt(), if (pdSweep) 1 else 0))
        }
        return out
    }

    /** Candidatos causais; `lastN` restringe às últimas N barras (modo ao vivo). */
    fun generate(F: Frame, cooldown: Int = 3, lastN: Int? = null): List<Cand> {
        val from = if (lastN != null) max(0, F.n - (lastN + cooldown + 2)) else 0
        val raw = (dirFrame(F, 1, from) + dirFrame(F, -1, from)).sortedBy { it.i }
        val counts = raw.groupingBy { it.i }.eachCount()
        val uniq = raw.filter { counts[it.i] == 1 }
        val lastAt = mutableMapOf(1 to -10_000, -1 to -10_000)
        val kept = ArrayList<Raw>()
        for (r in uniq) {
            val pos = r.i - from
            if (pos - lastAt[r.dir]!! > cooldown) { kept.add(r); lastAt[r.dir] = pos }
        }
        val sel = if (lastN != null) kept.filter { it.i >= F.n - lastN } else kept
        return sel.mapNotNull { targets(F, it) }
    }

    private fun targets(F: Frame, r: Raw): Cand? {
        val d = r.dir; val s = side(d); val i = r.i
        val entry = F["c"][i]; val atr = F["atr"][i]
        if (atr.isNaN() || atr <= 0) return null
        var sl = r.sl
        var risk = d * (entry - sl)
        if (risk < MIN_RISK_ATR * atr) { sl = entry - d * MIN_RISK_ATR * atr; risk = MIN_RISK_ATR * atr }
        if (risk > MAX_RISK_ATR * atr || risk <= 0) return null
        val levels = ArrayList<Double>()
        for (k in listOf("near_t", "h4_near_t", "pd_t", "pw_t", "h4_sh")) {
            val v = F.at(s[k]!!, i)
            if (!v.isNaN() && d * (v - entry) > 0) levels.add(v)
        }
        val sortedLv = levels.sortedBy { d * (it - entry) }
        val obstacles = listOf(F.at(s["opp_fvg"]!!, i), F.at(s["opp_ob"]!!, i)).filter { !it.isNaN() && d * (it - entry) > 0 } +
            sortedLv.take(1)
        val room = (obstacles.minOfOrNull { d * (it - entry) } ?: (5 * risk)) / risk
        var tp1 = NAN
        for (v in sortedLv) {
            val rr = d * (v - entry) / risk
            if (rr in MIN_TP1_R..MAX_TP1_R) { tp1 = v - d * 0.05 * atr; break }
        }
        val struct = !tp1.isNaN()
        if (!struct) tp1 = entry + d * DEFAULT_TP1_R * risk
        val rr1 = d * (tp1 - entry) / risk
        var tp2 = NAN
        for (v in sortedLv) {
            val rr = d * (v - entry) / risk
            if (rr >= rr1 + 0.8 && rr <= 5.0) { tp2 = v - d * 0.05 * atr; break }
        }
        if (tp2.isNaN()) tp2 = entry + d * max(2.5, rr1 + 1.0) * risk
        return Cand(i, F.t[i], d, r.setup, entry, sl, tp1, tp2, risk, risk / atr, rr1, d * (tp2 - entry) / risk,
            min(room, 5.0), if (struct) 1 else 0, r.nSetups, r.inZone, r.atEma, r.engulf, r.pin, r.pdSweep, r.d1Dir, atr)
    }
}

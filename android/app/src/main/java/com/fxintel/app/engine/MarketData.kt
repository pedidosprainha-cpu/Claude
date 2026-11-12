package com.fxintel.app.engine

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.File
import java.io.IOException
import java.util.concurrent.Callable
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/** Cotação com bid/ask, horário (s UTC), fonte e checagens cruzadas. */
data class Q(
    val symbol: String, val bid: Double, val ask: Double, val time: Double, val source: String,
    val spreadSource: String, var prevClose: Double? = null, val check: MutableMap<String, Double> = mutableMapOf(),
) {
    val mid get() = (bid + ask) / 2
    val spread get() = ask - bid
    fun ageS(now: Double) = maxOf(0.0, now - time)
}

data class SourceHealth(val name: String, var ok: Boolean = true, var lastLatencyMs: Double? = null, var requests: Int = 0,
                        var failures: Int = 0, var lastError: String? = null)

/**
 * Dados de mercado SEM CHAVE DE API, direto do aparelho:
 *  - Swissquote (feed público BBO): bid/ask reais de FX e metais;
 *  - TrueFX (feed não autenticado): checagem cruzada de 10 pares;
 *  - Yahoo Finance (gráficos públicos): histórico H1/M15/M5 e intermercados, com cache local;
 *  - gold-api.com: spot de ouro/prata (contingência);
 *  - ForexFactory/FairEconomy: calendário econômico.
 */
class MarketData(private val cacheDir: File) {
    private val http = OkHttpClient.Builder().connectTimeout(15, TimeUnit.SECONDS).readTimeout(40, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true).build()
    private val pool = Executors.newFixedThreadPool(6)
    private val mem = ConcurrentHashMap<String, Pair<Long, Bars>>()
    val health = ConcurrentHashMap<String, SourceHealth>()
    @Volatile var lastQuotes: Map<String, Q> = emptyMap()
    private var calCache: Pair<Long, List<EconEventK>>? = null
    @Volatile var notes = ConcurrentHashMap<String, MutableList<String>>()

    init { cacheDir.mkdirs() }

    private fun h(name: String) = health.getOrPut(name) { SourceHealth(name) }

    private fun get(url: String, source: String, retries: Int = 3): String {
        var last: Exception? = null
        for (a in 0 until retries) {
            val t0 = System.nanoTime()
            try {
                http.newCall(Request.Builder().url(url).header("User-Agent", "Mozilla/5.0").build()).execute().use { r ->
                    val body = r.body?.string() ?: ""
                    if (r.code == 429 || r.code >= 500) throw IOException("HTTP ${r.code}")
                    if (!r.isSuccessful) { h(source).apply { failures++; requests++; lastError = "HTTP ${r.code}" }; throw IOException("$source HTTP ${r.code}") }
                    h(source).apply { ok = true; requests++; lastLatencyMs = (System.nanoTime() - t0) / 1e6 }
                    return body
                }
            } catch (e: IOException) {
                last = e
                if (e.message?.contains("HTTP 4") == true && e.message?.contains("429") != true) break
                Thread.sleep(((if (e.message?.contains("429") == true) 2500L else 500L) shl a))
            }
        }
        h(source).apply { failures++; requests++; ok = false; lastError = last?.message }
        throw IOException("$source: ${last?.message}")
    }

    // ------------------------------------------------------------------ Yahoo (histórico)
    private fun yahooChart(sym: String, interval: String, range: String): Bars {
        var lastErr: Exception? = null
        for (host in listOf("query1.finance.yahoo.com", "query2.finance.yahoo.com")) {
            try {
                val url = "https://$host/v8/finance/chart/".toHttpUrl().newBuilder().addPathSegment(sym)
                    .addQueryParameter("interval", interval).addQueryParameter("range", range).build().toString()
                val o = Json.parseToJsonElement(get(url, "yahoo")).jsonObject
                val res = (o["chart"]?.jsonObject?.get("result") as? JsonArray)?.firstOrNull()?.jsonObject
                    ?: throw IOException("yahoo $sym: sem dados")
                val ts = (res["timestamp"] as? JsonArray)?.map { it.jsonPrimitive.longOrNull ?: 0L }?.toLongArray() ?: LongArray(0)
                val q = res["indicators"]!!.jsonObject["quote"]!!.jsonArray[0].jsonObject
                fun col(k: String) = (q[k] as? JsonArray)?.map { (it as? JsonPrimitive)?.doubleOrNull ?: NAN }?.toDoubleArray() ?: nanArray(ts.size)
                val t = if (interval == "1h") LongArray(ts.size) { BarOps.floorTo(ts[it], 3600) } else ts
                return Bars.clean(t, col("open"), col("high"), col("low"), col("close"), col("volume"))
            } catch (e: Exception) { lastErr = e }
        }
        throw IOException(lastErr?.message ?: "yahoo falhou")
    }

    private fun cacheFile(sym: String, tf: String) = File(cacheDir, "bars_${sym.replace(Regex("[^A-Za-z0-9]"), "_")}_$tf.bin")

    private fun save(f: File, b: Bars) {
        val tmp = File(f.path + ".tmp")
        DataOutputStream(tmp.outputStream().buffered()).use { out ->
            out.writeInt(b.n)
            for (i in 0 until b.n) { out.writeLong(b.t[i]); out.writeDouble(b.o[i]); out.writeDouble(b.h[i]); out.writeDouble(b.l[i]); out.writeDouble(b.c[i]); out.writeDouble(b.v[i]) }
        }
        tmp.renameTo(f)
    }

    private fun load(f: File): Bars? = try {
        DataInputStream(f.inputStream().buffered()).use { inp ->
            val n = inp.readInt()
            val t = LongArray(n); val o = DoubleArray(n); val h = DoubleArray(n); val l = DoubleArray(n); val c = DoubleArray(n); val v = DoubleArray(n)
            for (i in 0 until n) { t[i] = inp.readLong(); o[i] = inp.readDouble(); h[i] = inp.readDouble(); l[i] = inp.readDouble(); c[i] = inp.readDouble(); v[i] = inp.readDouble() }
            Bars(t, o, h, l, c, v)
        }
    } catch (e: Exception) { null }

    private val ttl = mapOf("M5" to 45_000L, "M15" to 90_000L, "H1" to 240_000L)
    private val full = mapOf("M5" to "5d", "M15" to "10d", "H1" to "730d")
    private val keepDays = mapOf("M5" to 6L, "M15" to 12L, "H1" to 760L)

    /** Barras brutas do Yahoo com cache em arquivo e atualização incremental. */
    fun raw(ysym: String, tf: String): Bars {
        val key = "$ysym|$tf"
        val now = System.currentTimeMillis()
        mem[key]?.let { if (now - it.first < ttl[tf]!!) return it.second }
        val f = cacheFile(ysym, tf)
        val cached = load(f)
        val interval = mapOf("M5" to "5m", "M15" to "15m", "H1" to "1h")[tf]!!
        val fresh = cached != null && cached.n > 0 && (now / 1000 - cached.t[cached.n - 1]) < 4 * 86400
        var b = if (fresh) Bars.merge(cached!!, yahooChart(ysym, interval, "5d")) else yahooChart(ysym, interval, full[tf]!!)
        val cut = b.t.last() - keepDays[tf]!! * 86400
        b = b.filter { b.t[it] >= cut }
        save(f, b)
        mem[key] = now to b
        return b
    }

    /** Barras processadas do instrumento (proxies de metais tratados), sem ajuste ao spot. */
    fun bars(symbol: String, tf: String): Bars {
        val inst = Instruments.get(symbol)
        val b = raw(inst.yahoo, tf)
        return when (symbol) {
            "XAUUSD" -> BarOps.dropWeekend(b)
            "XAGUSD" -> BarOps.repairLevelShifts(b, mapOf("M5" to 300L, "M15" to 900L, "H1" to 3600L)[tf]!!).also { (_, k) ->
                if (k > 0) notes.getOrPut(symbol) { mutableListOf() }.add("$tf: $k saltos de rolagem reparados")
            }.first
            else -> b
        }
    }

    fun macro(name: String): Bars {
        val b = raw(Instruments.MACRO[name]!!, "H1")
        return if (name in setOf("WTI", "SPX_FUT")) BarOps.repairLevelShifts(b, 3600).first else b
    }

    fun <T> parallel(keys: List<String>, f: (String) -> T): Map<String, Result<T>> {
        val futs = keys.associateWith { k -> pool.submit(Callable { f(k) }) }
        return futs.mapValues { (_, fu) -> runCatching { fu.get(90, TimeUnit.SECONDS) } }
    }

    // ------------------------------------------------------------------ cotações
    private fun swissquote(inst: Instruments.Inst, profile: String = "premium"): Q? {
        val txt = get("https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/${inst.base}/${inst.quote}", "swissquote", 2)
        val arr = Json.parseToJsonElement(txt) as? JsonArray ?: return null
        var best: Q? = null
        for (p in arr) {
            val o = p.jsonObject
            val ts = (o["ts"] as? JsonPrimitive)?.longOrNull ?: continue
            for (sp in (o["spreadProfilePrices"] as? JsonArray) ?: continue) {
                val s = sp.jsonObject
                val bid = (s["bid"] as? JsonPrimitive)?.doubleOrNull ?: continue
                val ask = (s["ask"] as? JsonPrimitive)?.doubleOrNull ?: continue
                if ((s["spreadProfile"] as? JsonPrimitive)?.contentOrNull == profile) return Q(inst.symbol, bid, ask, ts / 1000.0, "swissquote", "provider")
                if (best == null || ask - bid > best.spread) best = Q(inst.symbol, bid, ask, ts / 1000.0, "swissquote", "provider")
            }
        }
        return best
    }

    private fun truefx(): Map<String, Pair<Double, Double>> = try {
        get("https://webrates.truefx.com/rates/connect.html?f=csv", "truefx", 1).trim().lines().mapNotNull { line ->
            val p = line.split(",")
            if (p.size < 6 || !p[0].contains("/")) null
            else runCatching { p[0].replace("/", "") to ((p[2] + p[3]).toDouble() to (p[4] + p[5]).toDouble()) }.getOrNull()
        }.toMap()
    } catch (e: Exception) { emptyMap() }

    private fun yahooSpark(syms: List<String>): Map<String, Triple<Double, Double, Double?>> {
        val url = "https://query1.finance.yahoo.com/v7/finance/spark".toHttpUrl().newBuilder()
            .addQueryParameter("symbols", syms.joinToString(",")).addQueryParameter("range", "1d")
            .addQueryParameter("interval", "1m").build().toString()
        val o = Json.parseToJsonElement(get(url, "yahoo")).jsonObject
        val out = HashMap<String, Triple<Double, Double, Double?>>()
        for (r in (o["spark"]?.jsonObject?.get("result") as? JsonArray) ?: JsonArray(emptyList())) {
            val ro = r.jsonObject
            val m = ro["response"]?.jsonArray?.firstOrNull()?.jsonObject?.get("meta")?.jsonObject ?: continue
            val px = (m["regularMarketPrice"] as? JsonPrimitive)?.doubleOrNull ?: continue
            val t = (m["regularMarketTime"] as? JsonPrimitive)?.doubleOrNull ?: continue
            val prev = (m["previousClose"] as? JsonPrimitive)?.doubleOrNull ?: (m["chartPreviousClose"] as? JsonPrimitive)?.doubleOrNull
            out[(ro["symbol"] as JsonPrimitive).content] = Triple(px, t, prev)
        }
        return out
    }

    private fun goldApi(symbol: String): Pair<Double, Double>? {
        val code = mapOf("XAUUSD" to "XAU", "XAGUSD" to "XAG")[symbol] ?: return null
        val o = Json.parseToJsonElement(get("https://api.gold-api.com/price/$code", "goldapi", 2)).jsonObject
        val px = (o["price"] as? JsonPrimitive)?.doubleOrNull ?: return null
        val t = runCatching { java.time.Instant.parse((o["updatedAt"] as JsonPrimitive).content).epochSecond.toDouble() }.getOrNull()
            ?: (System.currentTimeMillis() / 1000.0)
        return px to t
    }

    fun quotes(symbols: List<String>): Map<String, Q> {
        val now = System.currentTimeMillis() / 1000.0
        val out = ConcurrentHashMap<String, Q>()
        parallel(symbols) { s -> swissquote(Instruments.get(s)) }.forEach { (s, r) -> r.getOrNull()?.let { out[s] = it } }
        val fx = symbols.filter { Instruments.get(it).kind == "fx" }
        runCatching { yahooSpark(fx.map { Instruments.get(it).yahoo }) }.getOrNull()?.let { sp ->
            for (s in fx) {
                val inst = Instruments.get(s); val y = sp[inst.yahoo] ?: continue
                val q = out[s]
                if (q != null) { q.prevClose = y.third; q.check["yahoo_pips"] = Math.round((q.mid - y.first) / inst.pip * 10) / 10.0 }
                else {
                    val spd = Instruments.estimatedSpread(inst, now.toLong())
                    out[s] = Q(s, y.first - spd / 2, y.first + spd / 2, y.second, "yahoo", "estimated", y.third)
                }
            }
        }
        for (s in symbols.filter { Instruments.get(it).kind == "metal" }) {
            if (out[s] == null) runCatching { goldApi(s) }.getOrNull()?.let { (px, t) ->
                val spd = Instruments.estimatedSpread(Instruments.get(s), now.toLong())
                out[s] = Q(s, px - spd / 2, px + spd / 2, t, "goldapi", "estimated")
            }
            out[s]?.let { q -> q.prevClose = runCatching { metalPrevClose(s, q.mid) }.getOrNull() }
        }
        for ((s, p) in truefx()) {
            val q = out[s] ?: continue
            q.check["truefx_pips"] = Math.round((q.mid - (p.first + p.second) / 2) / Instruments.get(s).pip * 10) / 10.0
        }
        lastQuotes = HashMap(lastQuotes).apply { putAll(out) }
        return out
    }

    private fun metalPrevClose(symbol: String, spot: Double): Double? {
        val d1 = BarOps.derive(bars(symbol, "H1"), "D1")
        if (d1.n < 2) return null
        return BarOps.spotAdjust(symbol, d1, spot).c[d1.n - 2]
    }

    // ------------------------------------------------------------------ calendário
    fun calendar(): List<EconEventK> {
        val now = System.currentTimeMillis()
        calCache?.let { if (now - it.first < 3_600_000) return it.second }
        val f = File(cacheDir, "calendar.json")
        return try {
            val txt = get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", "calendar", 4)  // feed limita taxa (429)
            f.writeText(txt)
            EconEventK.parse(txt).also { calCache = now to it }
        } catch (e: Exception) {
            if (f.exists()) EconEventK.parse(f.readText()).also { calCache = now to it } else throw e
        }
    }

    fun shutdown() = pool.shutdown()
}

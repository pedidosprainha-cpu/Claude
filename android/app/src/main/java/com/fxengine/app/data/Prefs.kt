package com.fxengine.app.data

import android.content.Context
import java.io.File

data class AppSettings(
    val balance: Double = 10_000.0,
    val riskPct: Double = 1.0,
    val assets: String = "all",      // "all" | "fx" | "metais"
    val useEdge: Boolean = true,
    val useNews: Boolean = true,
    val monitorIntervalSec: Int = 120,   // breakout monitor cycle
    val alertMinGrade: String = "A",     // notify only breakouts with this grade or better
)

class Prefs(context: Context) {
    private val sp = context.getSharedPreferences("fxengine", Context.MODE_PRIVATE)
    private val lastFile = File(context.filesDir, "ultima_analise.json")

    fun load(): AppSettings = AppSettings(
        balance = sp.getFloat("balance", 10_000f).toDouble(),
        riskPct = sp.getFloat("risk_pct", 1f).toDouble(),
        assets = sp.getString("assets", "all") ?: "all",
        useEdge = sp.getBoolean("use_edge", true),
        useNews = sp.getBoolean("use_news", true),
        monitorIntervalSec = sp.getInt("monitor_interval", 120),
        alertMinGrade = sp.getString("alert_min_grade", "A") ?: "A",
    )

    fun save(s: AppSettings) {
        sp.edit()
            .putFloat("balance", s.balance.toFloat())
            .putFloat("risk_pct", s.riskPct.toFloat())
            .putString("assets", s.assets)
            .putBoolean("use_edge", s.useEdge)
            .putBoolean("use_news", s.useNews)
            .putInt("monitor_interval", s.monitorIntervalSec)
            .putString("alert_min_grade", s.alertMinGrade)
            .apply()
    }

    var disclaimerAccepted: Boolean
        get() = sp.getBoolean("disclaimer_ok", false)
        set(v) = sp.edit().putBoolean("disclaimer_ok", v).apply()

    fun saveLast(raw: String) = runCatching { lastFile.writeText(raw) }

    fun loadLast(): String? = runCatching { if (lastFile.exists()) lastFile.readText() else null }.getOrNull()

    private val lastBreakouts = File(context.filesDir, "ultimos_rompimentos.json")

    fun saveBreakouts(raw: String) = runCatching { lastBreakouts.writeText(raw) }

    fun loadBreakouts(): Pair<String, Long>? = runCatching {
        if (lastBreakouts.exists()) lastBreakouts.readText() to lastBreakouts.lastModified() else null
    }.getOrNull()
}

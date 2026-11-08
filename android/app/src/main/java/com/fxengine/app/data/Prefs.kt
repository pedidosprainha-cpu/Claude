package com.fxengine.app.data

import android.content.Context
import java.io.File

data class AppSettings(
    val balance: Double = 10_000.0,
    val riskPct: Double = 1.0,
    val assets: String = "all",      // "all" | "fx" | "metais"
    val useEdge: Boolean = true,
    val useNews: Boolean = true,
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
    )

    fun save(s: AppSettings) {
        sp.edit()
            .putFloat("balance", s.balance.toFloat())
            .putFloat("risk_pct", s.riskPct.toFloat())
            .putString("assets", s.assets)
            .putBoolean("use_edge", s.useEdge)
            .putBoolean("use_news", s.useNews)
            .apply()
    }

    var disclaimerAccepted: Boolean
        get() = sp.getBoolean("disclaimer_ok", false)
        set(v) = sp.edit().putBoolean("disclaimer_ok", v).apply()

    fun saveLast(raw: String) = runCatching { lastFile.writeText(raw) }

    fun loadLast(): String? = runCatching { if (lastFile.exists()) lastFile.readText() else null }.getOrNull()
}

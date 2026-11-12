package com.fxengine.app.engine

import android.content.Context
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.fxengine.app.data.AppSettings
import java.io.File

/** Called from Python (via Chaquopy) while the scan runs. Must stay a plain Java-style interface. */
interface ProgressListener {
    fun onProgress(pct: Int, msg: String)
}

/** Public, named implementation so Python can always resolve `onProgress` by reflection. */
class LambdaProgressListener(private val cb: (Int, String) -> Unit) : ProgressListener {
    override fun onProgress(pct: Int, msg: String) = cb(pct, msg)
}

/** Process-wide Python runtime: started exactly once, whoever asks first (UI or monitor service). */
object PythonHost {
    @Synchronized
    fun get(context: Context): Python {
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(context.applicationContext))
        }
        return Python.getInstance()
    }
}

/**
 * Runs the embedded Python engine (fxengine/app_api.py). Blocking: call it off the main thread.
 */
class EngineRunner(context: Context) {
    private val app = context.applicationContext

    private fun api() = PythonHost.get(app).getModule("fxengine.app_api")

    private fun cacheDir(): String = File(app.cacheDir, "fxengine").apply { mkdirs() }.absolutePath

    /** Extracts the runtime and imports numpy/pandas/engine so the first scan starts faster. */
    fun warmUp() {
        api()
    }

    fun run(settings: AppSettings, onProgress: (Int, String) -> Unit): String =
        api().callAttr(
            "run",
            cacheDir(),
            settings.balance,
            settings.riskPct,
            settings.assets,
            settings.useEdge,
            settings.useNews,
            TZ,
            LambdaProgressListener(onProgress),
            false,
            settings.trendFilter,
        ).toString()

    /** Light real-time breakout scan (fxengine/breakouts.py). */
    fun scanBreakouts(settings: AppSettings, onProgress: (Int, String) -> Unit): String =
        api().callAttr(
            "scan_breakouts",
            cacheDir(),
            settings.balance,
            settings.riskPct,
            settings.assets,
            TZ,
            LambdaProgressListener(onProgress),
            false,
            settings.breakoutPlan,
        ).toString()

    /** Probability of a price explosion per instrument (fxengine/app_api.py scan_explosions). */
    fun scanExplosions(settings: AppSettings, onProgress: (Int, String) -> Unit): String =
        api().callAttr(
            "scan_explosions",
            cacheDir(),
            settings.balance,
            settings.riskPct,
            settings.assets,
            TZ,
            LambdaProgressListener(onProgress),
            false,
        ).toString()

    /** Deep analysis of one instrument (fxengine/app_api.py analyze_asset). */
    fun analyzeAsset(settings: AppSettings, symbol: String, onProgress: (Int, String) -> Unit): String =
        api().callAttr(
            "analyze_asset",
            cacheDir(),
            symbol,
            settings.balance,
            settings.riskPct,
            settings.breakoutPlan,
            TZ,
            LambdaProgressListener(onProgress),
            false,
            settings.useEdge,
            settings.useNews,
            settings.trendFilter,
        ).toString()

    companion object {
        const val TZ = "America/Sao_Paulo"
    }
}

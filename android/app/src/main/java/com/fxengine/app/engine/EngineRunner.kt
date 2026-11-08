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

/**
 * Runs the embedded Python engine (fxengine/app_api.py). Blocking: call it off the main thread.
 */
class EngineRunner(private val context: Context) {

    // Python.start() must run exactly once even if warm-up and the first tap race.
    @Synchronized
    private fun python(): Python {
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(context.applicationContext))
        }
        return Python.getInstance()
    }

    /** Extracts the runtime and imports numpy/pandas/engine so the first scan starts faster. */
    fun warmUp() {
        python().getModule("fxengine.app_api")
    }

    fun run(settings: AppSettings, onProgress: (Int, String) -> Unit): String {
        val cache = File(context.cacheDir, "fxengine").apply { mkdirs() }
        val api = python().getModule("fxengine.app_api")
        return api.callAttr(
            "run",
            cache.absolutePath,
            settings.balance,
            settings.riskPct,
            settings.assets,
            settings.useEdge,
            settings.useNews,
            "America/Sao_Paulo",
            LambdaProgressListener(onProgress),
        ).toString()
    }
}

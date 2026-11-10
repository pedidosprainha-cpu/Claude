package com.fxengine.app.monitor

import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import com.fxengine.app.data.Prefs
import com.fxengine.app.data.gradeAtLeast
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Foreground service that keeps scanning for breakouts while the screen is off and
 * posts a notification for every new actionable breakout at or above the alert grade.
 */
class MonitorService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var loop: Job? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private val hhmm = SimpleDateFormat("HH:mm", Locale.forLanguageTag("pt-BR"))

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        Notifications.ensureChannels(this)
        ServiceCompat.startForeground(
            this, Notifications.ONGOING_ID, Notifications.ongoing(this, "Iniciando…"),
            if (Build.VERSION.SDK_INT >= 34) ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE else 0,
        )
        if (wakeLock == null) {
            wakeLock = getSystemService(PowerManager::class.java)
                ?.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "fxengine:monitor")
                ?.apply { setReferenceCounted(false) }
        }
        if (loop?.isActive != true) loop = scope.launch { runLoop() }
        BreakoutMonitor.setActive(true)
        return START_STICKY
    }

    private suspend fun runLoop() {
        BreakoutMonitor.restore(this)
        while (scope.isActive) {
            val settings = Prefs(this).load()
            val interval = settings.monitorIntervalSec.coerceIn(60, 900) * 1000L
            // Keep the CPU awake for this cycle and the wait until the next one.
            wakeLock?.acquire(interval + 120_000L)
            val res = BreakoutMonitor.scanOnce(this)
            if (res != null) {
                res.items
                    .filter { it.isNew && !it.blocked && gradeAtLeast(it.grade, settings.alertMinGrade) }
                    .take(5)
                    .forEach { Notifications.alert(this, it) }
                res.fills.take(5).forEach { Notifications.fill(this, it) }
            }
            val next = System.currentTimeMillis() + interval
            BreakoutMonitor.setNext(next)
            val st = BreakoutMonitor.state.value
            val actionable = st.result?.items?.count { it.actionable } ?: 0   // grade A or better
            val text = if (st.error != null && res == null) "Falha no último ciclo: ${st.error} · nova tentativa às ${hhmm.format(Date(next))}"
            else "Último ciclo ${hhmm.format(Date())} · $actionable com nota A/A+ · próximo às ${hhmm.format(Date(next))}"
            Notifications.updateOngoing(this, text)
            delay(interval)
        }
    }

    override fun onDestroy() {
        loop?.cancel()
        scope.cancel()
        runCatching { if (wakeLock?.isHeld == true) wakeLock?.release() }
        BreakoutMonitor.setActive(false)
        super.onDestroy()
    }

    companion object {
        const val ACTION_STOP = "com.fxengine.app.STOP_MONITOR"

        fun start(ctx: Context) {
            ContextCompat.startForegroundService(ctx, Intent(ctx, MonitorService::class.java))
        }

        fun stop(ctx: Context) {
            ctx.stopService(Intent(ctx, MonitorService::class.java))
        }
    }
}

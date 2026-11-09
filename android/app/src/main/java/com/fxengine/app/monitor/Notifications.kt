package com.fxengine.app.monitor

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.fxengine.app.MainActivity
import com.fxengine.app.R
import com.fxengine.app.data.BreakoutItem

object Notifications {
    const val CH_MONITOR = "monitor"
    const val CH_ALERTS = "rompimentos"
    const val ONGOING_ID = 1001
    const val EXTRA_TAB = "open_tab"
    const val TAB_BREAKOUTS = "rompimentos"

    fun ensureChannels(ctx: Context) {
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return
        nm.createNotificationChannel(
            NotificationChannel(CH_MONITOR, "Monitor em execução", NotificationManager.IMPORTANCE_LOW).apply {
                description = "Aviso fixo enquanto o monitor de rompimentos está ligado"
                setShowBadge(false)
            },
        )
        nm.createNotificationChannel(
            NotificationChannel(CH_ALERTS, "Alertas de rompimento", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "Novo rompimento acionável detectado"
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 250, 120, 250)
            },
        )
    }

    fun canPost(ctx: Context): Boolean =
        Build.VERSION.SDK_INT < 33 ||
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

    private fun openApp(ctx: Context, requestCode: Int): PendingIntent {
        val i = Intent(ctx, MainActivity::class.java)
            .putExtra(EXTRA_TAB, TAB_BREAKOUTS)
            .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        return PendingIntent.getActivity(ctx, requestCode, i,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }

    fun ongoing(ctx: Context, text: String): android.app.Notification {
        val stop = PendingIntent.getService(
            ctx, 2, Intent(ctx, MonitorService::class.java).setAction(MonitorService.ACTION_STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(ctx, CH_MONITOR)
            .setSmallIcon(R.drawable.ic_stat_breakout)
            .setContentTitle("Monitorando rompimentos")
            .setContentText(text)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(openApp(ctx, 1))
            .addAction(0, "Parar", stop)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .build()
    }

    fun updateOngoing(ctx: Context, text: String) {
        if (!canPost(ctx)) return
        try {
            NotificationManagerCompat.from(ctx).notify(ONGOING_ID, ongoing(ctx, text))
        } catch (_: SecurityException) {
        }
    }

    fun alert(ctx: Context, b: BreakoutItem) {
        if (!canPost(ctx)) return
        val arrow = if (b.isBuy) "▲" else "▼"
        val title = "$arrow ${b.side} ${b.symbol} · ${b.statusLabel.lowercase()} (${b.tf}) · nota ${b.grade}"
        val odds = if (b.prob != null && b.evR != null)
            "\nAlvo 1 antes do stop: ${(b.prob * 100).toInt()}% · expectativa ${"%+.2f".format(b.evR)}R" else ""
        val body = "${b.headline}\nEntrada ${b.plan.entry} · stop ${b.plan.sl} · alvo ${b.plan.tp1} (${"%.1f".format(b.plan.rr1)}R)$odds"
        val n = NotificationCompat.Builder(ctx, CH_ALERTS)
            .setSmallIcon(R.drawable.ic_stat_breakout)
            .setContentTitle(title)
            .setContentText(b.headline)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_RECOMMENDATION)
            .setAutoCancel(true)
            .setContentIntent(openApp(ctx, b.id.hashCode()))
            .build()
        try {
            NotificationManagerCompat.from(ctx).notify(b.id.hashCode(), n)
        } catch (_: SecurityException) {
        }
    }
}

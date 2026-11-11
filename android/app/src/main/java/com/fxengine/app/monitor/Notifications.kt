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
    const val TAB_EXPLOSIONS = "explosoes"

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

    private fun openApp(ctx: Context, requestCode: Int, tab: String = TAB_BREAKOUTS): PendingIntent {
        val i = Intent(ctx, MainActivity::class.java)
            .putExtra(EXTRA_TAB, tab)
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

    fun confirmed(ctx: Context, c: com.fxengine.app.data.ConfirmEvent) {
        if (!canPost(ctx)) return
        val trail = c.trailPips?.let { " · +1R ${c.tp1} → stop móvel ${it.toInt()} pips" } ?: ""
        val id = ("conf" + c.symbol + c.entry).hashCode()
        val n = NotificationCompat.Builder(ctx, CH_ALERTS)
            .setSmallIcon(R.drawable.ic_stat_breakout)
            .setContentTitle("✅ ${c.side} ${c.symbol} AGORA a mercado (${c.tf}, nota ${c.grade})")
            .setContentText("Rompimento confirmado. Entrada ~${c.entry} · stop ${c.sl}")
            .setStyle(NotificationCompat.BigTextStyle().bigText(
                "Rompimento confirmado no fechamento do candle ${c.tf}.\nEntrada a mercado ~${c.entry} · " +
                    "stop ${c.sl} (${c.slPips.toInt()} pips)$trail · lote ${"%.2f".format(c.lots)}"))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_RECOMMENDATION)
            .setAutoCancel(true)
            .setContentIntent(openApp(ctx, id))
            .build()
        try {
            NotificationManagerCompat.from(ctx).notify(id, n)
        } catch (_: SecurityException) {
        }
    }

    fun fill(ctx: Context, f: com.fxengine.app.data.FillEvent) {
        if (!canPost(ctx)) return
        val n = NotificationCompat.Builder(ctx, CH_ALERTS)
            .setSmallIcon(R.drawable.ic_stat_breakout)
            .setContentTitle("✅ Entrada atingida: ${f.side} ${f.symbol} em ${f.limit}")
            .setContentText("O preço chegou na ordem limite sugerida (${f.tf}, nota ${f.grade}). Stop ${f.sl}.")
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(openApp(ctx, ("fill" + f.symbol + f.limit).hashCode()))
            .build()
        try {
            NotificationManagerCompat.from(ctx).notify(("fill" + f.symbol + f.limit).hashCode(), n)
        } catch (_: SecurityException) {
        }
    }

    fun alert(ctx: Context, b: BreakoutItem) {
        if (!canPost(ctx)) return
        val arrow = if (b.isBuy) "▲" else "▼"
        val title = "$arrow ${b.side} ${b.symbol} · ${b.statusLabel.lowercase()} (${b.tf}) · nota ${b.grade}"
        val odds = if (b.prob != null && b.evR != null)
            "\nNo lucro em ${(b.prob * 100).toInt()}% dos casos parecidos · expectativa ${"%+.2f".format(b.evR)}R" else ""
        val entry = if (b.plan.isLimit) "Ordem limite em ${b.plan.entry} (até ${b.plan.validUntil})" else "Entrada ${b.plan.entry}"
        val exit = if (b.plan.exitKind == "trail") "+1R ${b.plan.tp1} → stop móvel" else "alvo ${b.plan.tp1} (${"%.1f".format(b.plan.rr1)}R)"
        val body = "${b.headline}\n$entry · stop ${b.plan.sl} · $exit$odds"
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

    fun explosion(ctx: Context, x: com.fxengine.app.data.ExplosionItem) {
        if (!canPost(ctx)) return
        val title = "⚡ ${x.symbol}: explosão ${x.levelLabel.lowercase()} · ${(x.p * 100).toInt()}% até ${x.until}"
        val conf = if (x.dirConfident) ", alta confiança" else ""
        val dir = when {
            x.pUp == null -> "direção indefinida"
            x.pUp >= 0.5 -> "se explodir: ▲ alta ${(x.pUp * 100).toInt()}%$conf"
            else -> "se explodir: ▼ baixa ${((1 - x.pUp) * 100).toInt()}%$conf"
        }
        val body = "Movimento típico ≈ ${x.movePips.toInt()} pips ($dir)\n" +
            "Alcance provável ${x.rangeLow} – ${x.rangeHigh} · confirme a direção antes de entrar" +
            (if (x.events.isNotEmpty()) "\nAgenda: ${x.events.first()}" else "")
        val n = NotificationCompat.Builder(ctx, CH_ALERTS)
            .setSmallIcon(R.drawable.ic_stat_breakout)
            .setContentTitle(title)
            .setContentText("Movimento típico ≈ ${x.movePips.toInt()} pips · $dir")
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_RECOMMENDATION)
            .setAutoCancel(true)
            .setContentIntent(openApp(ctx, ("x" + x.symbol + x.until).hashCode(), TAB_EXPLOSIONS))
            .build()
        try {
            NotificationManagerCompat.from(ctx).notify(("x" + x.symbol + x.until).hashCode(), n)
        } catch (_: SecurityException) {
        }
    }
}

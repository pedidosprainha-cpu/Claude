package com.fxintel.app.work

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
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.fxintel.app.MainActivity
import com.fxintel.app.data.AlertItem
import com.fxintel.app.data.FxApi
import com.fxintel.app.data.LocalRepo
import com.fxintel.app.data.Prefs
import java.util.concurrent.TimeUnit

const val CHANNEL_ID = "fxintel_alerts"

fun ensureChannel(ctx: Context) {
    val nm = ctx.getSystemService(NotificationManager::class.java)
    if (nm.getNotificationChannel(CHANNEL_ID) == null) {
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "Alertas de mercado", NotificationManager.IMPORTANCE_DEFAULT).apply {
                description = "Novos sinais, eventos econômicos, volatilidade e integridade dos dados"
            }
        )
    }
}

fun notifyAlert(ctx: Context, a: AlertItem) {
    if (Build.VERSION.SDK_INT >= 33 &&
        ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
    ) return
    ensureChannel(ctx)
    val pi = PendingIntent.getActivity(
        ctx, 0, Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
    )
    val title = when (a.kind) {
        "novo_sinal" -> "Novo sinal"
        "evento" -> "Evento econômico"
        "volatilidade" -> "Volatilidade"
        "dados" -> "Integridade dos dados"
        "sinal_status" -> "Sinal atualizado"
        "sinal_invalidado" -> "Sinal invalidado"
        else -> "FXIntel"
    }
    val n = NotificationCompat.Builder(ctx, CHANNEL_ID)
        .setSmallIcon(android.R.drawable.stat_notify_more)
        .setContentTitle(title)
        .setContentText(a.message)
        .setStyle(NotificationCompat.BigTextStyle().bigText(a.message))
        .setContentIntent(pi)
        .setAutoCancel(true)
        .build()
    try {
        NotificationManagerCompat.from(ctx).notify(a.id.toInt(), n)
    } catch (_: SecurityException) {
    }
}

/** Consulta periódica de alertas (a cada 15 min, mínimo permitido pelo Android) em segundo plano. */
class AlertWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result {
        val prefs = Prefs(applicationContext)
        val p = prefs.current()
        if (!p.notifications) return Result.success()
        if (p.mode != "server") {
            // modo autônomo: acompanha os sinais e o calendário diretamente no aparelho (sem servidor/chave)
            return try {
                val repo = LocalRepo.get(applicationContext)
                (repo.trackSignals() + repo.eventAlerts()).takeLast(5).forEach { notifyAlert(applicationContext, it) }
                repo.alerts(0).maxOfOrNull { it.id }?.let { prefs.setLastAlertId(it) }
                Result.success()
            } catch (e: Exception) { Result.retry() }
        }
        if (p.serverUrl.isBlank()) return Result.success()
        return try {
            val api = FxApi(p.serverUrl, p.apiKey)
            val alerts = api.alerts(p.lastAlertId)
            if (p.lastAlertId > 0) alerts.sortedBy { it.id }.takeLast(5).forEach { notifyAlert(applicationContext, it) }
            alerts.maxOfOrNull { it.id }?.let { prefs.setLastAlertId(it) }
            Result.success()
        } catch (e: Exception) {
            Result.retry()
        }
    }

    companion object {
        fun schedule(ctx: Context) {
            val req = PeriodicWorkRequestBuilder<AlertWorker>(15, TimeUnit.MINUTES)
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .build()
            WorkManager.getInstance(ctx).enqueueUniquePeriodicWork("fxintel-alerts", ExistingPeriodicWorkPolicy.KEEP, req)
        }
    }
}

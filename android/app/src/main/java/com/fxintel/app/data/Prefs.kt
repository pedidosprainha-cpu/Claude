package com.fxintel.app.data

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "fxintel")

data class AppPrefs(
    val serverUrl: String = "",
    val apiKey: String = "",
    val notifications: Boolean = true,
    val lastAlertId: Long = 0,
)

class Prefs(private val ctx: Context) {
    private val kUrl = stringPreferencesKey("server_url")
    private val kKey = stringPreferencesKey("api_key")
    private val kNotif = booleanPreferencesKey("notifications")
    private val kLastAlert = longPreferencesKey("last_alert_id")

    val flow: Flow<AppPrefs> = ctx.dataStore.data.map {
        AppPrefs(it[kUrl] ?: "", it[kKey] ?: "", it[kNotif] ?: true, it[kLastAlert] ?: 0L)
    }

    suspend fun current(): AppPrefs = flow.first()

    suspend fun saveServer(url: String, key: String) = ctx.dataStore.edit {
        it[kUrl] = url.trim().trimEnd('/')
        it[kKey] = key.trim()
    }

    suspend fun setNotifications(on: Boolean) = ctx.dataStore.edit { it[kNotif] = on }
    suspend fun setLastAlertId(id: Long) = ctx.dataStore.edit { it[kLastAlert] = id }
}

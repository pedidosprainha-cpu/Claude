package com.fxintel.app.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppRoot(vm: MainViewModel, onAskNotif: () -> Unit) {
    val s by vm.ui.collectAsState()
    var tab by remember { mutableIntStateOf(if (s.configured) 0 else 3) }
    val snack = remember { SnackbarHostState() }
    val fx = LocalFx.current
    LaunchedEffect(s.toast) { s.toast?.let { snack.showSnackbar(it); vm.clearToast() } }
    LaunchedEffect(Unit) { if (!vm.ui.value.configured) tab = 3 }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("◆ FXIntel", fontWeight = FontWeight.Bold, fontSize = 19.sp)
                        Text("Forex & Metais", fontSize = 11.sp, color = fx.muted)
                    }
                },
                actions = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        val (label, bg) = when {
                            !s.networkOnline -> "sem rede" to fx.badBg
                            s.link == Link.LIVE -> "● ao vivo" to fx.goodBg
                            s.serverOk == false -> "servidor offline" to fx.badBg
                            s.link == Link.POLLING -> "● consulta" to fx.warnBg
                            else -> "conectando" to fx.warnBg
                        }
                        Chip(label, bg)
                        Spacer(Modifier.width(6.dp))
                        s.health?.let { h ->
                            Chip(if (h.model.validated == true) "modelo ok" else "modelo não validado",
                                if (h.model.validated == true) fx.goodBg else fx.badBg)
                        }
                        Spacer(Modifier.width(8.dp))
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.surface),
            )
        },
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                NavigationBarItem(tab == 0, { tab = 0 }, { Icon(Icons.Filled.Home, null) }, label = { Text("Painel") })
                NavigationBarItem(tab == 1, { tab = 1 }, { Icon(Icons.Filled.List, null) }, label = { Text("Histórico") })
                NavigationBarItem(tab == 2, { tab = 2 }, {
                    BadgedBox(badge = { if (s.unread > 0) Badge { Text("${s.unread}") } }) { Icon(Icons.Filled.Notifications, null) }
                }, label = { Text("Alertas") })
                NavigationBarItem(tab == 3, { tab = 3 }, { Icon(Icons.Filled.Settings, null) }, label = { Text("Ajustes") })
            }
        },
        snackbarHost = { SnackbarHost(snack) },
        containerColor = MaterialTheme.colorScheme.background,
    ) { pad ->
        when (tab) {
            0 -> DashboardScreen(vm, s, pad)
            1 -> HistoryScreen(vm, s, pad) { tab = 0 }
            2 -> AlertsScreen(vm, s, pad)
            else -> SettingsScreen(vm, s, pad, onAskNotif)
        }
    }
}

package com.fxengine.app.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.fxengine.app.ui.theme.Fx

private data class Tab(val label: String, val icon: ImageVector)

private val TABS = listOf(
    Tab("Analisar", Icons.Filled.PlayArrow),
    Tab("Rompimentos", Icons.Filled.Notifications),
    Tab("Ranking", Icons.AutoMirrored.Filled.List),
    Tab("Mercado", Icons.Filled.Info),
    Tab("Ajustes", Icons.Filled.Settings),
)

const val TAB_BREAKOUTS = 1

/** @param openTab tab requested from outside (e.g. tapping a breakout alert); consumed once. */
@Composable
fun FxApp(vm: MainViewModel, openTab: Int? = null, onTabOpened: () -> Unit = {}) {
    val state by vm.state.collectAsStateWithLifecycle()
    var tab by rememberSaveable { mutableIntStateOf(0) }
    LaunchedEffect(openTab) {
        if (openTab != null) {
            tab = openTab
            onTabOpened()
        }
    }

    Scaffold(
        containerColor = Fx.Bg,
        bottomBar = { BottomBar(tab) { tab = it } },
    ) { pad ->
        Box(Modifier.fillMaxSize().padding(pad)) {
            when (tab) {
                0 -> HomeScreen(state, onAnalyze = vm::analyze, onDismissError = vm::dismissError)
                TAB_BREAKOUTS -> BreakoutScreen(state.settings, vm::updateSettings)
                2 -> RankingScreen(state.result)
                3 -> MarketScreen(state.result)
                else -> SettingsScreen(state.settings, vm::updateSettings)
            }
        }
    }

    if (state.showDisclaimer) {
        AlertDialog(
            onDismissRequest = {},
            title = { Text("Antes de começar") },
            text = {
                Text(
                    "O FX Engine faz uma análise automatizada e probabilística de Forex e metais. " +
                        "Ele não garante resultados e não é recomendação de investimento. Operar alavancado " +
                        "pode gerar perdas maiores que o depósito. Sempre confira preço e spread na sua " +
                        "corretora e use o stop indicado.",
                )
            },
            confirmButton = { Button(onClick = vm::acceptDisclaimer) { Text("Entendi") } },
        )
    }
}

@Composable
fun BottomBar(tab: Int, onTab: (Int) -> Unit) {
    NavigationBar(containerColor = Fx.Surface) {
        TABS.forEachIndexed { i, t ->
            NavigationBarItem(
                selected = tab == i,
                onClick = { onTab(i) },
                icon = { Icon(t.icon, contentDescription = t.label) },
                label = { Text(t.label, maxLines = 1, softWrap = false, fontSize = 11.sp) },
                colors = NavigationBarItemDefaults.colors(
                    selectedIconColor = Fx.Blue, selectedTextColor = Fx.Blue,
                    indicatorColor = Fx.SurfaceHigh, unselectedIconColor = Fx.Muted,
                    unselectedTextColor = Fx.Muted,
                ),
            )
        }
    }
}

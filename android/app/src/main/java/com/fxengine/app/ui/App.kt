package com.fxengine.app.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Info
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.fxengine.app.ui.theme.Fx

private data class Tab(val label: String, val icon: ImageVector)

private val TABS = listOf(
    Tab("Analisar", Icons.Filled.PlayArrow),
    Tab("Ranking", Icons.AutoMirrored.Filled.List),
    Tab("Mercado", Icons.Filled.Info),
    Tab("Ajustes", Icons.Filled.Settings),
)

@Composable
fun FxApp(vm: MainViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    var tab by rememberSaveable { mutableIntStateOf(0) }

    Scaffold(
        containerColor = Fx.Bg,
        bottomBar = {
            NavigationBar(containerColor = Fx.Surface) {
                TABS.forEachIndexed { i, t ->
                    NavigationBarItem(
                        selected = tab == i,
                        onClick = { tab = i },
                        icon = { Icon(t.icon, contentDescription = t.label) },
                        label = { Text(t.label) },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = Fx.Blue, selectedTextColor = Fx.Blue,
                            indicatorColor = Fx.SurfaceHigh, unselectedIconColor = Fx.Muted,
                            unselectedTextColor = Fx.Muted,
                        ),
                    )
                }
            }
        },
    ) { pad ->
        Box(Modifier.fillMaxSize().padding(pad)) {
            when (tab) {
                0 -> HomeScreen(state, onAnalyze = vm::analyze, onDismissError = vm::dismissError)
                1 -> RankingScreen(state.result)
                2 -> MarketScreen(state.result)
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

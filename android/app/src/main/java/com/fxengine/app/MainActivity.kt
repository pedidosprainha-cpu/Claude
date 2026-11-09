package com.fxengine.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.runtime.mutableStateOf
import com.fxengine.app.monitor.BreakoutMonitor
import com.fxengine.app.monitor.Notifications
import com.fxengine.app.ui.FxApp
import com.fxengine.app.ui.MainViewModel
import com.fxengine.app.ui.TAB_BREAKOUTS
import com.fxengine.app.ui.theme.FxTheme

class MainActivity : ComponentActivity() {
    private val vm: MainViewModel by viewModels()
    private val openTab = mutableStateOf<Int?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        BreakoutMonitor.restore(this)
        handle(intent)
        setContent { FxTheme { FxApp(vm, openTab.value) { openTab.value = null } } }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handle(intent)
    }

    private fun handle(intent: Intent?) {
        if (intent?.getStringExtra(Notifications.EXTRA_TAB) == Notifications.TAB_BREAKOUTS) {
            openTab.value = TAB_BREAKOUTS
        }
    }
}

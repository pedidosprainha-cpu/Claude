package com.fxintel.app

import android.Manifest
import android.app.Application
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import com.fxintel.app.ui.AppRoot
import com.fxintel.app.ui.FxTheme
import com.fxintel.app.ui.MainViewModel
import com.fxintel.app.work.AlertWorker
import com.fxintel.app.work.ensureChannel

class FxIntelApp : Application() {
    override fun onCreate() {
        super.onCreate()
        ensureChannel(this)
        AlertWorker.schedule(this)
    }
}

class MainActivity : ComponentActivity() {
    private val vm: MainViewModel by viewModels()
    private val notifPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    private fun askNotif() {
        if (Build.VERSION.SDK_INT >= 33) notifPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        askNotif()
        setContent { FxTheme { AppRoot(vm, ::askNotif) } }
    }

    override fun onStart() { super.onStart(); vm.onForeground(true) }
    override fun onStop() { super.onStop(); vm.onForeground(false) }
}

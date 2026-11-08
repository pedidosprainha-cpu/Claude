package com.fxengine.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import com.fxengine.app.ui.FxApp
import com.fxengine.app.ui.MainViewModel
import com.fxengine.app.ui.theme.FxTheme

class MainActivity : ComponentActivity() {
    private val vm: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { FxTheme { FxApp(vm) } }
    }
}

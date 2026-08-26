package dev.dde.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import dev.dde.android.ui.DdeTheme
import dev.dde.android.ui.OperatorScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            DdeTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    OperatorScreen()
                }
            }
        }
    }
}

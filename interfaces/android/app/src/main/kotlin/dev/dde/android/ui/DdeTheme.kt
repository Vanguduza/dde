package dev.dde.android.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Token-aligned with schemas/design/tokens.json ColorPalette (DDE-052).
private val Bg = Color(0xFF1E1E1E)
private val Card = Color(0xFF252526)
private val Fg = Color(0xFFE6E6E6)
private val Muted = Color(0xFFB0B0B0)
private val Accent = Color(0xFF1177BB)
private val Err = Color(0xFFF85149)

private val DarkColors =
    darkColorScheme(
        primary = Accent,
        onPrimary = Color.White,
        background = Bg,
        onBackground = Fg,
        surface = Card,
        onSurface = Fg,
        onSurfaceVariant = Muted,
        error = Err,
    )

private val LightColors =
    lightColorScheme(
        primary = Accent,
        onPrimary = Color.White,
    )

@Composable
fun DdeTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    MaterialTheme(
        colorScheme = if (dark) DarkColors else LightColors,
        content = content,
    )
}

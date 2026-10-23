package com.bitora.android.foundation.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

object BitoraColors {
    val Arena = Color(0xFFD2B89A)
    val ArenaDark = Color(0xFFC3A381)
    val ArenaLight = Color(0xFFE4D3BF)
    val Ink = Color(0xFF071923)
    val Surface = Color(0xFFF5F8F8)
    val Card = Color(0xFFFFFFFF)
    val Border = Color(0xFFD8E1E4)
    val Success = Color(0xFF0C8F72)
    val Warning = Color(0xFFB9812C)
    val Error = Color(0xFFC9332B)
    val Offline = Color(0xFF697882)
}

private val BitoraLightScheme: ColorScheme = lightColorScheme(
    primary = BitoraColors.Success,
    secondary = BitoraColors.ArenaDark,
    tertiary = BitoraColors.Arena,
    background = BitoraColors.Surface,
    surface = BitoraColors.Card,
    error = BitoraColors.Error,
    onPrimary = Color.White,
    onSecondary = BitoraColors.Ink,
    onTertiary = BitoraColors.Ink,
    onBackground = BitoraColors.Ink,
    onSurface = BitoraColors.Ink,
)

@Composable
fun BitoraTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = BitoraLightScheme,
        typography = BitoraTypography,
        content = content,
    )
}

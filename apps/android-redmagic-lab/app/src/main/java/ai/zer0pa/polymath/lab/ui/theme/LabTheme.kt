package ai.zer0pa.polymath.lab.ui.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

object LabColors {
    val Black = Color(0xFF000000)
    val Shell = Color(0xFF080A0A)
    val Panel = Color(0xFF151515)
    val PanelAlt = Color(0xFF242424)
    val Stroke = Color(0xFF4A4A4A)
    val StrokeHot = Color(0xFFD8D8D8)
    val TextMain = Color(0xFFF2F0EA)
    val TextSoft = Color(0xFFB8B8B8)
    val TextMuted = Color(0xFF737373)
}

val LabColorScheme: ColorScheme = darkColorScheme(
    primary = LabColors.TextMain,
    onPrimary = LabColors.Black,
    secondary = LabColors.TextSoft,
    onSecondary = LabColors.Black,
    background = LabColors.Black,
    onBackground = LabColors.TextMain,
    surface = LabColors.Panel,
    onSurface = LabColors.TextMain,
    surfaceVariant = LabColors.PanelAlt,
    onSurfaceVariant = LabColors.TextSoft,
    outline = LabColors.Stroke
)

object LabType {
    val Display = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.SemiBold,
        letterSpacing = 0.sp
    )
    val Mono = FontFamily.Monospace
}

@Composable
fun PolymathLabTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = LabColorScheme,
        content = content
    )
}

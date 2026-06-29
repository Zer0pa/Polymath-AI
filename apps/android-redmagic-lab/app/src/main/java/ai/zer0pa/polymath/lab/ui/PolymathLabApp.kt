package ai.zer0pa.polymath.lab.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import ai.zer0pa.polymath.lab.LabAppContainer
import ai.zer0pa.polymath.lab.ui.screens.LabConsoleScreen
import ai.zer0pa.polymath.lab.ui.theme.PolymathLabTheme

@Composable
fun PolymathLabApp(container: LabAppContainer) {
    val controller = remember { LabController(container) }
    LaunchedEffect(Unit) {
        controller.refreshGameMode()
        controller.refreshLatestReport()
    }
    PolymathLabTheme {
        LabConsoleScreen(controller = controller)
    }
}

package ai.zer0pa.polymath.lab.ui

import ai.zer0pa.polymath.lab.domain.GateResultState
import ai.zer0pa.polymath.lab.domain.NativeConnectionState
import ai.zer0pa.polymath.lab.domain.Phase1RuntimeSnapshot
import ai.zer0pa.polymath.lab.domain.PhaseId
import ai.zer0pa.polymath.lab.domain.SourceMode
import ai.zer0pa.polymath.lab.domain.TermuxBaselines

const val PHASE1_SOURCE_SHA256 = "829da5e89cf2c787dd6e1e2f984e3f604216633900d6d5896c27260e8711adcb"
const val PHASE1_GBT1_SHA256 = "5887e29db2618b21fd9db1358c7f6db5bb7efffab54c16ba0643b46d7f3714ae"
const val PHASE1_DELIVERED_PIE_SHA256 = "855c8392d627e1510a02b3bef43fe28dfc05c01837961d0451c27885d258a9fe"

enum class LabTab(val label: String) {
    LAB("Lab"),
    RUNS("Runs"),
    CORPUS("Corpus"),
    SETTINGS("Settings")
}

data class MetricTileState(
    val label: String,
    val value: String,
    val detail: String
)

data class PhaseTileState(
    val phaseId: PhaseId,
    val state: String
)

data class LabUiState(
    val selectedTab: LabTab = LabTab.LAB,
    val sourceMode: SourceMode = SourceMode.MEGASCIENCE,
    val gateState: GateResultState = GateResultState.PROBE,
    val nativeConnectionState: NativeConnectionState = NativeConnectionState.NOT_CONNECTED,
    val gameMode: String = "NOT QUERIED",
    val latestReportRoot: String? = null,
    val latestMessage: String = "Phase 1 exact-artifact runtime ready. Stage an authority batch or refresh latest report.",
    val busy: Boolean = false,
    val runtimeSnapshot: Phase1RuntimeSnapshot? = null,
    val metrics: List<MetricTileState> = defaultMetrics(),
    val phases: List<PhaseTileState> = defaultPhases()
)

fun defaultMetrics(): List<MetricTileState> {
    val million = TermuxBaselines.phase1Selected.last()
    return listOf(
        MetricTileState("TOKEN IDS/S", "%.2fM REF".format(million.tokenIdsPerSec / 1_000_000.0), "Termux authority baseline"),
        MetricTileState("MATERIAL", "NO RUN", "No staged APK report"),
        MetricTileState("PROFILE", "UNKNOWN", "Frequency evidence missing"),
        MetricTileState("GATE", "PROBE", "No final promotion")
    )
}

fun defaultPhases(): List<PhaseTileState> {
    return PhaseId.values().map { phase ->
        val state = if (phase == PhaseId.P1) "IDLE" else "LOCKED"
        PhaseTileState(phaseId = phase, state = state)
    }
}

package ai.zer0pa.polymath.lab.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import ai.zer0pa.polymath.lab.LabAppContainer
import ai.zer0pa.polymath.lab.data.newUtcRunId
import ai.zer0pa.polymath.lab.domain.Phase1RunRequest
import ai.zer0pa.polymath.lab.domain.Phase1RuntimeSnapshot
import ai.zer0pa.polymath.lab.domain.PhaseId
import ai.zer0pa.polymath.lab.domain.SourceMode
import ai.zer0pa.polymath.lab.domain.TermuxBaselines

class LabController(private val container: LabAppContainer) {
    var state by mutableStateOf(LabUiState())
        private set

    fun selectTab(tab: LabTab) {
        state = state.copy(selectedTab = tab)
    }

    fun setSourceMode(mode: SourceMode) {
        state = state.copy(sourceMode = mode)
    }

    fun refreshGameMode() {
        val snapshot = container.gameAuthorityController.currentGameMode()
        state = state.copy(gameMode = snapshot.modeName)
    }

    fun refreshLatestReport() {
        applySnapshot(container.phase1ReportReader.latest())
    }

    suspend fun writeProbeReport() {
        state = state.copy(
            busy = true,
            latestMessage = "Native run active. GameState benchmark flag is set until report write completes.",
            phases = activePhases("NATIVE RUN")
        )
        val request = Phase1RunRequest(
            runId = newUtcRunId(),
            sourceMode = state.sourceMode,
            requestedRecords = null,
            tokenizerDir = null,
            gbt1Path = null,
            batchListPath = null,
            qai1Path = null,
            bpeAlgorithm = "heap",
            workerCount = 0,
            batchHint = 0
        )
        runCatching { container.phase1TokenizerEngine.runTokenizer(request) }
            .onSuccess { result ->
                val snapshot = container.phase1ReportReader.read(result.runId)
                applySnapshot(snapshot)
                state = state.copy(
                    busy = false,
                    gateState = result.state,
                    nativeConnectionState = snapshot?.nativeConnectionState ?: result.nativeConnectionState,
                    latestReportRoot = result.reportRoot.deviceRelativePath,
                    latestMessage = snapshot?.message ?: result.message
                )
            }
            .onFailure { error ->
                state = state.copy(
                    busy = false,
                    gateState = ai.zer0pa.polymath.lab.domain.GateResultState.FAIL,
                    latestMessage = "Native run failed: ${error.message ?: error::class.java.simpleName}",
                    phases = activePhases("ERROR")
                )
            }
    }

    private fun applySnapshot(snapshot: Phase1RuntimeSnapshot?) {
        if (snapshot == null) {
            state = state.copy(metrics = defaultMetrics(), phases = defaultPhases())
            return
        }
        state = state.copy(
            runtimeSnapshot = snapshot,
            nativeConnectionState = snapshot.nativeConnectionState,
            gameMode = snapshot.gameMode ?: state.gameMode,
            latestReportRoot = snapshot.reportRoot,
            latestMessage = snapshot.message,
            metrics = metrics(snapshot),
            phases = activePhases(snapshot.runPhase.compactPhase())
        )
    }

    private fun metrics(snapshot: Phase1RuntimeSnapshot): List<MetricTileState> {
        val million = TermuxBaselines.phase1Selected.last()
        val bestRate = snapshot.bestTrialTokenIdsPerSec ?: snapshot.appTokenIdsPerSec
        val ratio = bestRate?.let { it / million.tokenIdsPerSec }
        return listOf(
            MetricTileState(
                label = "TOKEN IDS/S",
                value = bestRate?.millions() ?: "NO RATE",
                detail = ratio?.let { "%.3f vs Termux".format(it) } ?: "No completed native batch"
            ),
            MetricTileState(
                label = "MATERIAL",
                value = snapshot.materialState.compactMaterial(),
                detail = snapshot.materialHash?.take(12) ?: "No material hash"
            ),
            MetricTileState(
                label = "PROFILE",
                value = snapshot.oemProfile.compactProfile(),
                detail = snapshot.cpuFrequencyEvidence.compactFrequency()
            ),
            MetricTileState(
                label = "GATE",
                value = "PROBE",
                detail = "Forbidden scan ${snapshot.forbiddenPayloadState}"
            )
        )
    }

    private fun activePhases(p1State: String): List<PhaseTileState> {
        return PhaseId.values().map { phase ->
            PhaseTileState(phaseId = phase, state = if (phase == PhaseId.P1) p1State else "LOCKED")
        }
    }

    private fun Double.millions(): String {
        return "%.2fM".format(this / 1_000_000.0)
    }

    private fun String.compactMaterial(): String {
        return if (startsWith("EXACT ")) removeSuffix(" MATERIAL") else this
    }

    private fun String.compactProfile(): String {
        return when {
            startsWith("HIGH-CLASS RATE") -> "HIGH RATE"
            startsWith("HIGH-FREQUENCY") -> "HIGH-FREQUENCY"
            startsWith("STANDARD APK") -> "STANDARD APK"
            else -> this
        }
    }

    private fun String.compactFrequency(): String {
        return if (startsWith("missing")) "frequency evidence missing" else this
    }

    private fun String.compactPhase(): String {
        return when {
            startsWith("complete", ignoreCase = true) -> "COMPLETE"
            startsWith("idle", ignoreCase = true) -> "IDLE"
            else -> uppercase()
        }
    }
}

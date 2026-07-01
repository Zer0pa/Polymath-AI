package ai.zer0pa.polymath.lab.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import ai.zer0pa.polymath.lab.LabAppContainer
import ai.zer0pa.polymath.lab.data.newUtcRunId
import ai.zer0pa.polymath.lab.domain.Phase1RunRequest
import ai.zer0pa.polymath.lab.domain.Phase1RuntimeSnapshot
import ai.zer0pa.polymath.lab.domain.SourceMode

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
            phases = waveBPhases()
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
                    phases = waveBPhases()
                )
            }
    }

    private fun applySnapshot(snapshot: Phase1RuntimeSnapshot?) {
        if (snapshot == null) {
            state = state.copy(
                metrics = waveBMetrics(state.waveBStatus),
                phases = waveBPhases()
            )
            return
        }
        state = state.copy(
            runtimeSnapshot = snapshot,
            nativeConnectionState = snapshot.nativeConnectionState,
            gameMode = snapshot.gameMode ?: state.gameMode,
            latestReportRoot = snapshot.reportRoot,
            latestMessage = snapshot.message,
            metrics = waveBMetrics(state.waveBStatus),
            phases = waveBPhases()
        )
    }
}

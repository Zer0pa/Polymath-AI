package ai.zer0pa.polymath.lab.ui

import ai.zer0pa.polymath.lab.domain.GateResultState
import ai.zer0pa.polymath.lab.domain.NativeConnectionState
import ai.zer0pa.polymath.lab.domain.Phase1RuntimeSnapshot
import ai.zer0pa.polymath.lab.domain.PhaseId
import ai.zer0pa.polymath.lab.domain.SourceMode

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

data class WaveBPhaseState(
    val phase: String,
    val phase1Status: String,
    val records: Long,
    val tokenIds: Long,
    val phase2Status: String,
    val packets: Long,
    val pjp1Bytes: Long,
    val pjp1Sha256: String,
    val phase34Status: String,
    val htpStatus: String,
    val phase4Status: String,
    val phase4LineageStatus: String,
    val consumedOutputCausesUpdate: Boolean,
    val adapterChanged: Boolean
)

data class WaveBStatusState(
    val runLabel: String,
    val currentGate: String,
    val statusClassification: String,
    val finalReportPath: String,
    val finalReportSha256: String,
    val proofRoot: String,
    val proofSummarySha256: String,
    val proofCustodyCommit: String,
    val centralStatePath: String,
    val centralStateSha256: String,
    val headline: String,
    val badges: List<String>,
    val phases: List<WaveBPhaseState>,
    val rawBoundary: List<String>,
    val firstMissingGreenField: String
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
    val waveBStatus: WaveBStatusState = waveBStatus(),
    val metrics: List<MetricTileState> = waveBMetrics(waveBStatus),
    val phases: List<PhaseTileState> = waveBPhases()
)

fun defaultMetrics(): List<MetricTileState> {
    return waveBMetrics(waveBStatus())
}

fun defaultPhases(): List<PhaseTileState> {
    return waveBPhases()
}

fun waveBMetrics(status: WaveBStatusState): List<MetricTileState> {
    val totalRecords = status.phases.sumOf { it.records }
    val totalTokens = status.phases.sumOf { it.tokenIds }
    val totalPjp1Bytes = status.phases.sumOf { it.pjp1Bytes }
    return listOf(
        MetricTileState("PHASE1-4", "GREEN", "Development-cycle mechanics"),
        MetricTileState("RECORDS", "%,d".format(totalRecords), "%,d token IDs".format(totalTokens)),
        MetricTileState("LINEAGE", "FROZEN", status.proofCustodyCommit.take(12)),
        MetricTileState("PENDING", "C5/COMET", "No authority or learning claim")
    )
}

fun waveBPhases(): List<PhaseTileState> {
    return PhaseId.values().map { phase ->
        val state = when (phase) {
            PhaseId.P1 -> "PASS"
            PhaseId.P2 -> "PASS"
            PhaseId.P3 -> "LINEAGE CLEAN"
            PhaseId.P4 -> "LINEAGE CLEAN"
            PhaseId.P5 -> "C5 PENDING"
            PhaseId.P6 -> "COMET PENDING"
        }
        PhaseTileState(phaseId = phase, state = state)
    }
}

private fun waveBStatus(): WaveBStatusState {
    return WaveBStatusState(
        runLabel = "c1_c4_waveB_rerun_20260630T230411Z",
        currentGate = "phase34_lineage_clean_proof_validated",
        statusClassification = "PASS_FOR_DEVELOPMENT_CYCLE_PHASE34_LINEAGE_CLEAN_PROOF",
        finalReportPath = "/Users/Zer0pa/Polymat AI/Polymath-AI/runtime/reports/integrated_c1_c4_execution/c1_c4_waveB_rerun_20260630T230411Z/final_integrated_metadata_report.json",
        finalReportSha256 = "53c2b3a2d3a80c1418674633db89691cbe80766ca32535535a5845e49ca11b60",
        proofRoot = "/Users/Zer0pa/Polymat AI/Polymath-AI/runtime/reports/integrated_c1_c4_execution/c1_c4_waveB_rerun_20260630T230411Z/phase34_lineage_repair",
        proofSummarySha256 = "1348895a1d5ca8e7e5276de1ab2022d9f64a300b288aa7169550263b27a0e304",
        proofCustodyCommit = "c08a8f1474f8e3b0989051d29258dae3db4ebed3",
        centralStatePath = "/Users/Zer0pa/Polymat AI/Polymath-AI/runtime/reports/orchestration/EXECUTIVE_DELIVERY_STATE.json",
        centralStateSha256 = "899b2297b0785994e0deb44946c9d5bbe9d4eb9a22e846895d103e14a45a55a7",
        headline = "C1-C4 Wave B ran through Phase1->Phase4. Phase3/4 lineage-clean proof validated for development-cycle evidence. C5 eval and Comet logging remain pending.",
        badges = listOf(
            "C5 PENDING",
            "COMET PENDING",
            "NOT 100K/1M AUTHORITY",
            "NO LEARNING/MODEL-QUALITY CLAIM",
            "NO PHASE3 READINESS CLAIM",
            "NO PHASE4 READINESS CLAIM"
        ),
        phases = listOf(
            WaveBPhaseState("C1", "pass", 5_180, 216_924, "pass", 5_180, 46_914_176, "a9e191c1e9ec0f7110fabe5991033f3176cf60c152dcc78b54e2e786a66604bc", "lineage_clean_proof_validated", "pass", "pass", "validated_development_cycle", true, true),
            WaveBPhaseState("C2", "pass", 3_198, 149_896, "pass", 3_198, 28_965_184, "073c142e8109996eaef2f26044781ab68362a3594af7b34d859335c17d5f6408", "lineage_clean_proof_validated", "pass", "pass", "validated_development_cycle", true, true),
            WaveBPhaseState("C2_5", "pass", 20, 1_326, "pass", 20, 185_216, "5c3278864d33d6e97ceb79b720d6c4f95ba456c8187c2d4b7c750a24171a85bb", "lineage_clean_proof_validated", "pass", "pass", "validated_development_cycle", true, true),
            WaveBPhaseState("C3", "pass", 56_138, 27_792_304, "pass", 247_500, 2_241_364_096, "28bdbdcbef4d30240747b2cb1f1697859cc4f1e7c178b82ee201c7712a09f80b", "lineage_clean_proof_validated", "pass", "pass", "validated_development_cycle", true, true),
            WaveBPhaseState("C4", "pass", 12_487, 1_445_274, "pass", 15_341, 138_932_192, "3b0012b7d18ba5d5cbf8a3f744c4ff0d7e38f01cb569ae89ea69163f4d4c03c0", "lineage_clean_proof_validated", "pass", "pass", "validated_development_cycle", true, true)
        ),
        rawBoundary = listOf(
            "compact metadata only in repo",
            "raw PJP1 remains under Termux home outside git",
            "raw HTP output remains device/Termux/outside git",
            "raw OpenCL tensors and adapters remain device/Termux/outside git"
        ),
        firstMissingGreenField = "C5 eval pass packet"
    )
}

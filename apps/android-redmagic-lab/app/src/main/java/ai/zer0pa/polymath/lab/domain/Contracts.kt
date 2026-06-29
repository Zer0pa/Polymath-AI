package ai.zer0pa.polymath.lab.domain

@JvmInline
value class RunId(val value: String)

enum class PhaseId(val shortLabel: String, val title: String) {
    P1("P1", "Tokenizer"),
    P2("P2", "Packetize"),
    P3("P3", "NPU Read"),
    P4("P4", "GPU Optimize"),
    P5("P5", "Checkpoint"),
    P6("P6", "Control")
}

enum class GateResultState {
    PASS,
    FAIL,
    BLOCKED,
    PROBE
}

enum class NativeConnectionState {
    NOT_CONNECTED,
    PROBE,
    BLOCKED,
    CONNECTED
}

enum class SourceMode(val wireName: String) {
    DICTIONARY("dictionary"),
    MEGASCIENCE("megascience")
}

data class PrepareRequest(val runId: RunId)
data class PrepareResult(val state: GateResultState, val message: String)
data class RunRequest(val runId: RunId, val sourceMode: SourceMode)
data class CancelResult(val runId: RunId, val cancelled: Boolean, val message: String)

data class NativeEngineInfo(
    val abiVersion: Int,
    val buildId: String,
    val gitSha: String,
    val engineName: String,
    val connectionState: NativeConnectionState,
    val phase1CoreLinked: Boolean
)

data class TableVerifyRequest(val tablePath: String, val expectedSha256: String?)
data class TableVerifyResult(
    val state: GateResultState,
    val tablePath: String,
    val observedSha256: String?,
    val message: String
)

data class Phase1RunRequest(
    val runId: RunId,
    val sourceMode: SourceMode,
    val requestedRecords: Long?,
    val tokenizerDir: String?,
    val gbt1Path: String?,
    val batchListPath: String?,
    val qai1Path: String?,
    val bpeAlgorithm: String,
    val workerCount: Int,
    val batchHint: Int,
    val phase1ExecPath: String? = null,
    val flags: Int = 0
)

data class Phase1RunResult(
    val runId: RunId,
    val state: GateResultState,
    val nativeConnectionState: NativeConnectionState,
    val records: Long,
    val tokenIds: Long,
    val message: String,
    val reportRoot: ArtifactRoot,
    val artifacts: List<ArtifactRef>,
    val nativeEngineInfo: NativeEngineInfo
)

data class Phase1RuntimeSnapshot(
    val runId: String,
    val reportRoot: String,
    val runPhase: String,
    val packageName: String,
    val apkSha256: String?,
    val appCategory: String?,
    val nativeConnectionState: NativeConnectionState,
    val phase1ExecPath: String?,
    val phase1ExecSha256: String?,
    val flags: Int,
    val childExecEnabled: Boolean?,
    val childExecErrno: Int?,
    val materialState: String,
    val materialHash: String?,
    val records: Long?,
    val tokenIds: Long?,
    val appTokenIdsPerSec: Double?,
    val bestTrialTokenIdsPerSec: Double?,
    val meanTrialTokenIdsPerSec: Double?,
    val warmupCount: Int,
    val trialCount: Int,
    val cpuset: String?,
    val cpusAllowedList: String?,
    val cgroupSummary: String?,
    val schedulerPolicy: Int?,
    val schedulerPriority: String?,
    val uclampMax: String?,
    val cpuFrequencyEvidence: String,
    val oemProfile: String,
    val gameMode: String?,
    val forbiddenPayloadState: String,
    val settingsRestoredState: String,
    val message: String
)

data class GameModeSnapshot(
    val apiLevel: Int,
    val modeCode: Int?,
    val modeName: String,
    val supported: Boolean,
    val message: String
)

data class TelemetrySession(val runId: RunId, val samplePeriodMs: Long)
data class TelemetrySummary(
    val runId: RunId,
    val sampleCount: Int,
    val thermalStatus: String,
    val message: String
)

data class ArtifactRoot(
    val runId: RunId,
    val absolutePath: String,
    val deviceRelativePath: String
)

data class ArtifactRef(
    val name: String,
    val absolutePath: String,
    val sha256: String,
    val byteCount: Long
)

data class ArtifactManifest(
    val runId: RunId,
    val root: ArtifactRoot,
    val artifacts: List<ArtifactRef>
)

data class ExportTicket(
    val runId: RunId,
    val state: GateResultState,
    val message: String
)

interface PhaseEngine {
    val phaseId: PhaseId
    suspend fun prepare(request: PrepareRequest): PrepareResult
    suspend fun run(request: RunRequest): Phase1RunResult
    suspend fun cancel(runId: RunId): CancelResult
}

interface Phase1TokenizerEngine : PhaseEngine {
    suspend fun verifyTable(request: TableVerifyRequest): TableVerifyResult
    suspend fun runTokenizer(request: Phase1RunRequest): Phase1RunResult
}

interface TelemetryCollector {
    fun start(runId: RunId, samplePeriodMs: Long): TelemetrySession
    suspend fun stop(session: TelemetrySession): TelemetrySummary
}

interface GameAuthorityController {
    fun currentGameMode(): GameModeSnapshot
    fun setLoading(isLoading: Boolean)
    fun setBenchmarkActive(active: Boolean)
}

interface ArtifactStore {
    suspend fun createRunDirectory(runId: RunId): ArtifactRoot
    suspend fun writeReport(root: ArtifactRoot, name: String, bytes: ByteArray): ArtifactRef
    suspend fun manifest(runId: RunId): ArtifactManifest
}

interface Phase1ReportReader {
    fun latest(): Phase1RuntimeSnapshot?
    fun read(runId: RunId): Phase1RuntimeSnapshot?
}

interface CometExportQueue {
    suspend fun enqueue(runId: RunId, manifest: ArtifactManifest): ExportTicket
}

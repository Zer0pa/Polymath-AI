package ai.zer0pa.polymath.lab.data

import android.content.Context
import ai.zer0pa.polymath.lab.bridge.NativePhase1Bridge
import ai.zer0pa.polymath.lab.domain.ArtifactRef
import ai.zer0pa.polymath.lab.domain.ArtifactStore
import ai.zer0pa.polymath.lab.domain.CancelResult
import ai.zer0pa.polymath.lab.domain.GameAuthorityController
import ai.zer0pa.polymath.lab.domain.GateResultState
import ai.zer0pa.polymath.lab.domain.NativeConnectionState
import ai.zer0pa.polymath.lab.domain.NativeEngineInfo
import ai.zer0pa.polymath.lab.domain.Phase1RunRequest
import ai.zer0pa.polymath.lab.domain.Phase1RunResult
import ai.zer0pa.polymath.lab.domain.Phase1TokenizerEngine
import ai.zer0pa.polymath.lab.domain.PhaseId
import ai.zer0pa.polymath.lab.domain.PrepareRequest
import ai.zer0pa.polymath.lab.domain.PrepareResult
import ai.zer0pa.polymath.lab.domain.RunId
import ai.zer0pa.polymath.lab.domain.RunRequest
import ai.zer0pa.polymath.lab.domain.TableVerifyRequest
import ai.zer0pa.polymath.lab.domain.TableVerifyResult
import org.json.JSONObject
import java.io.File

class Phase1NativeTokenizerEngine(
    private val context: Context,
    private val bridge: NativePhase1Bridge,
    private val artifactStore: ArtifactStore,
    private val apkIdentityReader: ApkIdentityReader,
    private val gameAuthorityController: GameAuthorityController,
    private val reportFactory: JsonReportFactory = JsonReportFactory()
) : Phase1TokenizerEngine {
    override val phaseId: PhaseId = PhaseId.P1

    override suspend fun prepare(request: PrepareRequest): PrepareResult {
        val info = parseNativeInfo(bridge.engineInfo(context.filesDir.absolutePath))
        return PrepareResult(
            state = GateResultState.PROBE,
            message = "Native bridge loaded=${bridge.libraryLoaded()} state=${info.connectionState} run=${request.runId.value}"
        )
    }

    override suspend fun run(request: RunRequest): Phase1RunResult {
        return runTokenizer(
            Phase1RunRequest(
                runId = request.runId,
                sourceMode = request.sourceMode,
                requestedRecords = null,
                tokenizerDir = null,
                gbt1Path = null,
                batchListPath = null,
                qai1Path = null,
                bpeAlgorithm = "heap",
                workerCount = 0,
                batchHint = 0
            )
        )
    }

    override suspend fun cancel(runId: RunId): CancelResult {
        gameAuthorityController.setBenchmarkActive(false)
        return CancelResult(runId = runId, cancelled = false, message = "No active native Phase 1 run to cancel.")
    }

    override suspend fun verifyTable(request: TableVerifyRequest): TableVerifyResult {
        val path = request.tablePath
        if (path.isBlank()) {
            return TableVerifyResult(
                state = GateResultState.BLOCKED,
                tablePath = path,
                observedSha256 = null,
                message = "GBT1 path is not staged in app-private storage."
            )
        }
        val file = File(path)
        if (!file.isFile) {
            return TableVerifyResult(
                state = GateResultState.BLOCKED,
                tablePath = path,
                observedSha256 = null,
                message = "GBT1 file does not exist at staged path."
            )
        }
        val sha = file.sha256Hex()
        val matches = request.expectedSha256 == null || request.expectedSha256 == sha
        return TableVerifyResult(
            state = if (matches) GateResultState.PROBE else GateResultState.FAIL,
            tablePath = path,
            observedSha256 = sha,
            message = if (matches) "GBT1 hash observed for native run." else "GBT1 hash mismatch."
        )
    }

    override suspend fun runTokenizer(request: Phase1RunRequest): Phase1RunResult {
        gameAuthorityController.setLoading(true)
        gameAuthorityController.setBenchmarkActive(true)
        return try {
            val root = artifactStore.createRunDirectory(request.runId)
            val nativeInfoJson = JSONObject(bridge.engineInfo(context.filesDir.absolutePath))
            val outputDir = File(
                context.getExternalFilesDir(null) ?: context.filesDir,
                "staged/phase1_outputs/${request.runId.value}"
            )
            outputDir.mkdirs()
            val pqa1OutputPath = "${outputDir.absolutePath}/phase1_app_output.pqa1"
            val childExecPath = request.phase1ExecPath
                ?: File(context.applicationInfo.nativeLibraryDir, "libphase1_qa_stream_exec.so").absolutePath
            val nativeProbeJson = JSONObject(
                bridge.probe(
                    appFilesDir = context.filesDir.absolutePath,
                    reportOutputPath = root.absolutePath,
                    tokenizerDir = request.tokenizerDir.orEmpty(),
                    tokenizerTablePath = request.gbt1Path.orEmpty(),
                    batchListPath = request.batchListPath.orEmpty(),
                    qai1Path = request.qai1Path.orEmpty(),
                    pqa1OutputPath = pqa1OutputPath,
                    bpeAlgorithm = request.bpeAlgorithm.ifBlank { "heap" },
                    phase1ExecPath = childExecPath,
                    workerCount = request.workerCount,
                    flags = request.flags
                )
            )
            val pqa1OutputSummary = outputMaterialSummary(request, pqa1OutputPath)
            val nativeInfo = parseNativeInfo(nativeInfoJson.toString())
            val nativeRunState = parseNativeInfo(nativeProbeJson.toString()).connectionState
            val gameMode = gameAuthorityController.currentGameMode()
            val appRunResultJson = appRunResult(request, nativeProbeJson, pqa1OutputSummary)

            val artifacts = mutableListOf<ArtifactRef>()
            artifacts += artifactStore.writeReport(root, "apk_identity.json", apkIdentityReader.readIdentity().toBytes())
            artifacts += artifactStore.writeReport(root, "native_engine_info.json", nativeInfoJson.toBytes())
            artifacts += artifactStore.writeReport(root, "native_probe_result.json", nativeProbeJson.toBytes())
            artifacts += artifactStore.writeReport(root, "phase1_app_run_config.json", reportFactory.runConfig(request).toBytes())
            artifacts += artifactStore.writeReport(root, "phase1_app_run_result.json", appRunResultJson.toBytes())
            artifacts += artifactStore.writeReport(root, "phase1_correctness_summary.json", reportFactory.correctnessSummary(appRunResultJson).toBytes())
            artifacts += artifactStore.writeReport(root, "phase1_android_game_authority.json", reportFactory.gameAuthority(gameMode).toBytes())
            artifacts += artifactStore.writeReport(root, "phase1_redmagic_operator_attestation.md", operatorAttestation().encodeToByteArray())
            artifacts += artifactStore.writeReport(root, "phase1_telemetry_summary.json", reportFactory.telemetrySummary().toBytes())
            artifacts += artifactStore.writeReport(root, "phase1_termux_baseline_comparison.json", reportFactory.termuxBaselineComparison(nativeProbeJson).toBytes())
            artifacts += artifactStore.writeReport(root, "phase1_ab_matrix.json", reportFactory.abMatrix().toBytes())
            artifacts += artifactStore.writeReport(root, "phase1_comet_logging_plan.json", reportFactory.cometPlan().toBytes())
            artifacts += artifactStore.writeReport(root, "commands.json", commandsJson().toBytes())
            artifacts += artifactStore.writeReport(root, "gate_result.json", reportFactory.gateResult(nativeInfoJson, nativeProbeJson, appRunResultJson, root.deviceRelativePath).toBytes())

            val manifestBeforeScan = artifactStore.manifest(request.runId)
            artifacts += artifactStore.writeReport(root, "phase1_forbidden_payload_scan.json", reportFactory.forbiddenPayloadScan(manifestBeforeScan).toBytes())
            val finalManifest = artifactStore.manifest(request.runId)
            artifacts += artifactStore.writeReport(root, "MANIFEST.md", reportFactory.manifestMarkdown(finalManifest).encodeToByteArray())

            Phase1RunResult(
                runId = request.runId,
                state = GateResultState.PROBE,
                nativeConnectionState = nativeRunState,
                records = nativeProbeJson.optLong("records", 0),
                tokenIds = nativeProbeJson.optLong("token_ids", 0),
                message = "APK-owned native report written. Native run state: $nativeRunState.",
                reportRoot = root,
                artifacts = artifacts,
                nativeEngineInfo = nativeInfo
            )
        } finally {
            gameAuthorityController.setLoading(false)
            gameAuthorityController.setBenchmarkActive(false)
        }
    }

    private fun appRunResult(
        request: Phase1RunRequest,
        nativeProbe: JSONObject,
        outputSummary: JSONObject
    ): JSONObject {
        return JSONObject()
            .put("schema_version", "phase1_app_run_result_v1")
            .put("run_id", request.runId.value)
            .put("status", nativeProbe.optString("gate_result", "probe"))
            .put("promotion_eligible", false)
            .put("records", nativeProbe.optLong("records", 0))
            .put("token_ids", nativeProbe.optLong("token_ids", 0))
            .put("wall_sec", nativeProbe.optDouble("wall_sec", 0.0))
            .put("input_bytes", nativeProbe.optLong("input_bytes", 0))
            .put("output_bytes", nativeProbe.optLong("output_bytes", 0))
            .put("input_mb_per_sec", nativeProbe.optDouble("input_mb_per_sec", 0.0))
            .put("token_ids_per_sec", nativeProbe.optDouble("token_ids_per_sec", 0.0))
            .put("records_per_sec", nativeProbe.optDouble("records_per_sec", 0.0))
            .put("latency_ms_per_record", nativeProbe.optDouble("latency_ms_per_record", 0.0))
            .put("latency_ms_per_prompt", nativeProbe.optDouble("latency_ms_per_prompt", 0.0))
            .put("pss_kb", nativeProbe.optLong("pss_kb", 0))
            .put("rss_kb", nativeProbe.optLong("rss_kb", 0))
            .put("peak_rss_kb", nativeProbe.optLong("peak_rss_kb", 0))
            .put("cpuset_before", nativeProbe.optString("cpuset_before", ""))
            .put("cpuset_after", nativeProbe.optString("cpuset_after", ""))
            .put("cpus_allowed_list_before", nativeProbe.optString("cpus_allowed_list_before", ""))
            .put("cpus_allowed_list_after", nativeProbe.optString("cpus_allowed_list_after", ""))
            .put("job_count", nativeProbe.optInt("job_count", 0))
            .put("thread_count", nativeProbe.optInt("thread_count", request.workerCount))
            .put("flags", request.flags)
            .put("phase1_exec_path", nativeProbe.optString("phase1_exec_path", request.phase1ExecPath.orEmpty()).ifBlank { JSONObject.NULL })
            .put("bpe_algorithm", nativeProbe.optString("bpe_algorithm", request.bpeAlgorithm))
            .put("run_interface", nativeProbe.optString("run_interface", if (request.batchListPath.isNullOrBlank()) "single-input" else "batch-list"))
            .put("parity_state", nativeProbe.optString("parity_state", "not_checked_in_apk_run"))
            .put("hot_loop_allocations", nativeProbe.optLong("hot_loop_allocations", 0))
            .put("span_errors", nativeProbe.optLong("span_errors", 0))
            .put("parity_mismatches", nativeProbe.optLong("parity_mismatches", 0))
            .put("material_hash_hex", outputSummary.opt("material_hash_hex") ?: JSONObject.NULL)
            .put("pqa1_output_summary", outputSummary)
            .put("native_probe", nativeProbe)
            .put("message", "Native tokenizer probe executed only if staged QAI1/tokenizer paths were supplied; parity must be checked before promotion.")
    }

    private fun outputMaterialSummary(request: Phase1RunRequest, singlePqa1OutputPath: String): JSONObject {
        val outputPaths = pqa1OutputPaths(request.batchListPath, singlePqa1OutputPath)
        val outputs = org.json.JSONArray()
        val hashes = mutableListOf<String>()
        outputPaths.forEach { path ->
            val file = File(path)
            val row = JSONObject()
                .put("path", path)
                .put("exists", file.isFile)
            if (file.isFile) {
                val sha = file.sha256Hex()
                hashes += sha
                row.put("sha256", sha)
                    .put("byte_count", file.length())
            }
            outputs.put(row)
        }
        val materialHash = if (hashes.isNotEmpty()) {
            hashes.sorted().joinToString(separator = "").encodeToByteArray().sha256Hex()
        } else {
            null
        }
        return JSONObject()
            .put("schema_version", "phase1_pqa1_output_material_summary_v1")
            .put("batch_list_path", request.batchListPath ?: JSONObject.NULL)
            .put("pqa1_output_count", outputPaths.size)
            .put("pqa1_outputs", outputs)
            .put("material_hash_hex", materialHash ?: JSONObject.NULL)
    }

    private fun pqa1OutputPaths(batchListPath: String?, singlePqa1OutputPath: String): List<String> {
        if (batchListPath.isNullOrBlank()) {
            return listOf(singlePqa1OutputPath)
        }
        val batchList = File(batchListPath)
        if (!batchList.isFile) {
            return emptyList()
        }
        return batchList.readLines()
            .mapNotNull { line ->
                val fields = line.trimEnd('\r').split('\t')
                fields.getOrNull(1)?.takeIf { it.isNotBlank() }
            }
    }

    private fun commandsJson(): JSONObject {
        return JSONObject()
            .put("schema_version", "phase1_app_commands_v1")
            .put("commands", org.json.JSONArray())
            .put("status", "probe")
            .put("message", "ADB command evidence is host-owned and has not been captured by the APK.")
    }

    private fun operatorAttestation(): String {
        return """
            |# REDMAGIC Operator Attestation
            |
            |Status: not captured.
            |
            |No Game Space, Rise, Diablo, fan, charge separation, or thermal regime state is asserted by this app-side probe.
            |The host ADB authority harness must pair operator-visible state with measured throughput before any claim.
            |
        """.trimMargin()
    }

    private fun parseNativeInfo(json: String): NativeEngineInfo {
        val value = JSONObject(json)
        val connection = runCatching {
            NativeConnectionState.valueOf(value.optString("connection_state", "NOT_CONNECTED"))
        }.getOrDefault(NativeConnectionState.NOT_CONNECTED)
        return NativeEngineInfo(
            abiVersion = value.optInt("abi_version", 0),
            buildId = value.optString("build_id", "unknown"),
            gitSha = value.optString("git_sha", "not_embedded"),
            engineName = value.optString("engine_name", "unknown"),
            connectionState = connection,
            phase1CoreLinked = value.optBoolean("phase1_core_linked", false)
        )
    }

    private fun JSONObject.toBytes(): ByteArray = toString(2).encodeToByteArray()
}

package ai.zer0pa.polymath.lab.data

import android.content.Context
import ai.zer0pa.polymath.lab.domain.NativeConnectionState
import ai.zer0pa.polymath.lab.domain.Phase1ReportReader
import ai.zer0pa.polymath.lab.domain.Phase1RuntimeSnapshot
import ai.zer0pa.polymath.lab.domain.RunId
import ai.zer0pa.polymath.lab.domain.TermuxBaselines
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

class LocalPhase1ReportReader(private val context: Context) : Phase1ReportReader {
    private val reportBase: File
        get() = File(context.getExternalFilesDir(null) ?: context.filesDir, "reports/phase1")

    override fun latest(): Phase1RuntimeSnapshot? {
        val latestDir = reportBase.listFiles()
            ?.filter { it.isDirectory }
            ?.maxByOrNull { it.name }
            ?: return null
        return read(RunId(latestDir.name))
    }

    override fun read(runId: RunId): Phase1RuntimeSnapshot? {
        val root = File(reportBase, runId.value)
        if (!root.isDirectory) {
            return null
        }
        val app = root.jsonObject("phase1_app_run_result.json")
        val native = root.jsonObject("native_phase1_metrics.json")
        val probe = root.jsonObject("native_probe_result.json")
        val identity = root.jsonObject("apk_identity.json")
        val authority = root.jsonObject("phase1_android_game_authority.json")
        val forbidden = root.jsonObject("phase1_forbidden_payload_scan.json")
        val warmSequence = root.jsonObject("native_warm_sequence_metrics.json")
        val records = app.optLongOrNull("records")
        val tokenIds = app.optLongOrNull("token_ids")
        val trialRates = root.trialRates(tokenIds)
        val materialHash = app.optStringOrNull("material_hash_hex")
        val materialState = materialState(records, tokenIds, materialHash)
        val connectionState = nativeConnection(app, native, probe)
        val sampler = native.optJSONObject("cpu_frequency_sampler")
        val frequencyEvidence = frequencyEvidence(sampler)
        return Phase1RuntimeSnapshot(
            runId = runId.value,
            reportRoot = "/sdcard/Android/data/${context.packageName}/files/reports/phase1/${runId.value}",
            runPhase = runPhase(app, native, warmSequence),
            packageName = identity.optString("package_name", context.packageName),
            apkSha256 = identity.optStringOrNull("apk_sha256"),
            appCategory = identity.optStringOrNull("application_category_name"),
            nativeConnectionState = connectionState,
            phase1ExecPath = app.optStringOrNull("phase1_exec_path") ?: probe.optStringOrNull("phase1_exec_path") ?: identity.optStringOrNull("phase1_exec_path"),
            phase1ExecSha256 = identity.optStringOrNull("phase1_exec_sha256"),
            flags = app.optInt("flags", 0),
            childExecEnabled = native.optBooleanOrNull("child_exec_enabled"),
            childExecErrno = native.optIntOrNull("child_exec_errno"),
            materialState = materialState,
            materialHash = materialHash,
            records = records,
            tokenIds = tokenIds,
            appTokenIdsPerSec = app.optDoubleOrNull("token_ids_per_sec"),
            bestTrialTokenIdsPerSec = trialRates.maxOrNull(),
            meanTrialTokenIdsPerSec = trialRates.takeIf { it.isNotEmpty() }?.average(),
            warmupCount = warmSequence.countLabels("warmup"),
            trialCount = warmSequence.countLabels("trial"),
            cpuset = app.optStringOrNull("cpuset_before") ?: native.optStringOrNull("cpuset_before"),
            cpusAllowedList = app.optStringOrNull("cpus_allowed_list_before") ?: native.optStringOrNull("cpus_allowed_list_before"),
            cgroupSummary = native.optStringOrNull("cgroup_before")?.lineSequence()?.firstOrNull { it.contains("cpuset") },
            schedulerPolicy = native.optIntOrNull("sched_policy_before"),
            schedulerPriority = native.optStringOrNull("sched_excerpt_before")?.lineValue("prio"),
            uclampMax = native.optStringOrNull("sched_excerpt_before")?.lineValue("effective uclamp.max"),
            cpuFrequencyEvidence = frequencyEvidence,
            oemProfile = oemProfile(sampler, trialRates.maxOrNull()),
            gameMode = authority.optStringOrNull("app_side_game_mode"),
            forbiddenPayloadState = forbidden.optString("status", "not_captured"),
            settingsRestoredState = "host high profile required",
            message = message(materialState, connectionState, frequencyEvidence)
        )
    }

    private fun File.jsonObject(name: String): JSONObject {
        val file = File(this, name)
        if (!file.isFile) {
            return JSONObject()
        }
        return runCatching { JSONObject(file.readText()) }.getOrDefault(JSONObject())
    }

    private fun File.trialRates(tokenIds: Long?): List<Double> {
        val tokens = tokenIds ?: return emptyList()
        return listFiles()
            ?.filter { it.isFile && it.name.startsWith("native_batch_metrics_trial") && it.name.endsWith(".json") }
            ?.mapNotNull { file ->
                val elapsedNs = jsonObject(file.name).optLong("elapsed_ns", 0L)
                if (elapsedNs > 0L) tokens.toDouble() / (elapsedNs.toDouble() / 1_000_000_000.0) else null
            }
            .orEmpty()
    }

    private fun materialState(records: Long?, tokenIds: Long?, materialHash: String?): String {
        if (records == null || records <= 0L) {
            return "NO STAGED MATERIAL"
        }
        val baseline = TermuxBaselines.phase1Selected.firstOrNull {
            it.records == records && it.tokenIds == tokenIds && it.materialHash == materialHash
        }
        return if (baseline != null) "EXACT ${baseline.scale} MATERIAL" else "UNVERIFIED MATERIAL"
    }

    private fun nativeConnection(app: JSONObject, native: JSONObject, probe: JSONObject): NativeConnectionState {
        val raw = probe.optString(
            "connection_state",
            native.optString("connection_state", app.optString("native_connection_state", ""))
        )
        return runCatching { NativeConnectionState.valueOf(raw) }.getOrDefault(NativeConnectionState.NOT_CONNECTED)
    }

    private fun runPhase(app: JSONObject, native: JSONObject, warmSequence: JSONObject): String {
        if (native.optInt("return_code", -1) != 0 && native.has("return_code")) {
            return "error"
        }
        if (app.optLong("records", 0L) > 0L && warmSequence.optInt("run_count", 0) > 0) {
            return "complete: warmups/trials recorded"
        }
        if (app.optLong("records", 0L) > 0L) {
            return "complete: single native run"
        }
        return "idle: no staged batch run"
    }

    private fun frequencyEvidence(sampler: JSONObject?): String {
        if (sampler == null || !sampler.optBoolean("enabled", false)) {
            return "missing; run sampler or host process sampler"
        }
        val cpus = sampler.optJSONArray("cpus") ?: JSONArray()
        val maxByCpu = (0 until cpus.length()).mapNotNull { index ->
            cpus.optJSONObject(index)?.let { cpu ->
                "cpu${cpu.optInt("cpu")} ${cpu.optLong("max_khz") / 1000}MHz"
            }
        }
        return maxByCpu.joinToString(", ").ifBlank { "sampler enabled; no CPU rows" }
    }

    private fun oemProfile(sampler: JSONObject?, bestTrialRate: Double?): String {
        val cpus = sampler?.optJSONArray("cpus")
        if (cpus != null && cpus.maxKHz() >= 4_000_000L) {
            return "HIGH-FREQUENCY EVIDENCED"
        }
        if (bestTrialRate != null && bestTrialRate >= 58_000_000.0) {
            return "HIGH-CLASS RATE; FREQUENCY UNSAMPLED"
        }
        if (bestTrialRate != null && bestTrialRate >= 50_000_000.0) {
            return "STANDARD APK WARMED CLASS"
        }
        return "UNKNOWN PROFILE"
    }

    private fun message(materialState: String, connectionState: NativeConnectionState, frequencyEvidence: String): String {
        val frequencyWarning = if (frequencyEvidence.startsWith("missing")) {
            " Frequency/profile evidence is missing for this app-side report."
        } else {
            ""
        }
        return "Latest report: $materialState, native=$connectionState.$frequencyWarning"
    }

    private fun JSONObject.optStringOrNull(name: String): String? {
        if (!has(name) || isNull(name)) {
            return null
        }
        return optString(name).takeIf { it.isNotBlank() && it != "unavailable" }
    }

    private fun JSONObject.optLongOrNull(name: String): Long? {
        if (!has(name) || isNull(name)) {
            return null
        }
        return optLong(name)
    }

    private fun JSONObject.optIntOrNull(name: String): Int? {
        if (!has(name) || isNull(name)) {
            return null
        }
        return optInt(name)
    }

    private fun JSONObject.optDoubleOrNull(name: String): Double? {
        if (!has(name) || isNull(name)) {
            return null
        }
        return optDouble(name)
    }

    private fun JSONObject.optBooleanOrNull(name: String): Boolean? {
        if (!has(name) || isNull(name)) {
            return null
        }
        return optBoolean(name)
    }

    private fun JSONObject.countLabels(prefix: String): Int {
        val runs = optJSONArray("runs") ?: return 0
        return (0 until runs.length()).count { index ->
            runs.optJSONObject(index)?.optString("label", "")?.startsWith(prefix) == true
        }
    }

    private fun JSONArray.maxKHz(): Long {
        return (0 until length()).maxOfOrNull { index ->
            optJSONObject(index)?.optLong("max_khz", 0L) ?: 0L
        } ?: 0L
    }

    private fun String.lineValue(key: String): String? {
        return lineSequence()
            .firstOrNull { it.trimStart().startsWith(key) }
            ?.substringAfter(":")
            ?.trim()
    }

}

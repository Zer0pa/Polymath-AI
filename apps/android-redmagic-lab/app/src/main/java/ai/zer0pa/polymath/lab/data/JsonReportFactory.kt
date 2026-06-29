package ai.zer0pa.polymath.lab.data

import ai.zer0pa.polymath.lab.domain.ArtifactManifest
import ai.zer0pa.polymath.lab.domain.GameModeSnapshot
import ai.zer0pa.polymath.lab.domain.Phase1RunRequest
import ai.zer0pa.polymath.lab.domain.TermuxBaselines
import org.json.JSONArray
import org.json.JSONObject

class JsonReportFactory {
    fun runConfig(request: Phase1RunRequest): JSONObject {
        return JSONObject()
            .put("schema_version", "phase1_app_run_config_v1")
            .put("run_id", request.runId.value)
            .put("source_mode", request.sourceMode.wireName)
            .put("requested_records", request.requestedRecords ?: JSONObject.NULL)
            .put("tokenizer_dir", request.tokenizerDir ?: JSONObject.NULL)
            .put("gbt1_path", request.gbt1Path ?: JSONObject.NULL)
            .put("batch_list_path", request.batchListPath ?: JSONObject.NULL)
            .put("qai1_path", request.qai1Path ?: JSONObject.NULL)
            .put("bpe_algorithm", request.bpeAlgorithm)
            .put("worker_count", request.workerCount)
            .put("batch_hint", request.batchHint)
            .put("phase1_exec_path", request.phase1ExecPath ?: JSONObject.NULL)
            .put("flags", request.flags)
            .put("phase1_core_bridge", "jni_canonical_zig_export")
    }

    fun correctnessSummary(appRunResult: JSONObject): JSONObject {
        val records = appRunResult.optLong("records", 0L)
        val tokenIds = appRunResult.optLong("token_ids", 0L)
        val materialHash = appRunResult.optString("material_hash_hex", "")
        val matchingBaseline = TermuxBaselines.phase1Selected.firstOrNull { baseline ->
            baseline.records == records && baseline.tokenIds == tokenIds && baseline.materialHash == materialHash
        }
        val materialState = when {
            matchingBaseline != null -> "exact_${matchingBaseline.scale.lowercase()}_material"
            records > 0L -> "material_hash_unrecognized"
            else -> "no_staged_material"
        }
        return JSONObject()
            .put("schema_version", "phase1_correctness_summary_v1")
            .put("status", if (records > 0L) "probe" else "blocked")
            .put("material_state", materialState)
            .put("matched_baseline", matchingBaseline?.scale ?: JSONObject.NULL)
            .put("records", records)
            .put("token_ids", tokenIds)
            .put("material_hash_hex", materialHash.ifBlank { JSONObject.NULL })
            .put("span_integrity", appRunResult.optLong("span_errors", 0L).let { if (it == 0L && records > 0L) "no_errors_reported" else "not_verified" })
            .put("pqa1_roundtrip", if (matchingBaseline != null) "output_hash_material_match" else "not_promoted")
            .put("repeat_hash", "not_repeated_in_app_report")
            .put("hot_loop_allocations", appRunResult.optLong("hot_loop_allocations", 0L))
            .put("message", "This is app-side material evidence for the staged exact fixture when present; final promotion still requires the host authority gate.")
    }

    fun gameAuthority(snapshot: GameModeSnapshot): JSONObject {
        return JSONObject()
            .put("schema_version", "phase1_android_game_authority_v1")
            .put("status", "probe")
            .put("package_identity", "ai.zer0pa.polymath.lab")
            .put("manifest_app_category", "game")
            .put("app_side_game_mode", snapshot.modeName)
            .put("api_level", snapshot.apiLevel)
            .put("adb_cmd_game", "not_captured")
            .put("adb_dumpsys_game", "not_captured")
            .put("redmagic_operator_attestation", "not_captured")
            .put("claim", "No Game Mode, Game Space, Rise, Diablo, or ADPF benefit claimed.")
    }

    fun telemetrySummary(): JSONObject {
        return JSONObject()
            .put("schema_version", "phase1_telemetry_summary_v1")
            .put("status", "probe")
            .put("sample_count", 0)
            .put("thermal", "not_sampled")
            .put("message", "Telemetry authority requires Mac-side ADB and REDMAGIC operator state.")
    }

    fun termuxBaselineComparison(nativeProbe: JSONObject? = null): JSONObject {
        val baselines = JSONArray()
        TermuxBaselines.phase1Selected.forEach { baseline ->
            baselines.put(
                JSONObject()
                    .put("scale", baseline.scale)
                    .put("variant", baseline.variant)
                    .put("records", baseline.records)
                    .put("token_ids", baseline.tokenIds)
                    .put("token_ids_per_sec", baseline.tokenIdsPerSec)
                    .put("records_per_sec", baseline.recordsPerSec)
                    .put("material_hash", baseline.materialHash)
            )
        }
        val apkTokenRate = nativeProbe?.optDouble("token_ids_per_sec", 0.0) ?: 0.0
        val apkRecords = nativeProbe?.optLong("records", 0) ?: 0L
        val millionBaseline = TermuxBaselines.phase1Selected.last()
        val ratio1m = if (apkTokenRate > 0.0) apkTokenRate / millionBaseline.tokenIdsPerSec else JSONObject.NULL
        return JSONObject()
            .put("schema_version", "phase1_termux_baseline_comparison_v1")
            .put("status", if (apkTokenRate > 0.0) "probe" else "blocked")
            .put("apk_standard_mode_result", nativeProbe ?: "not_run")
            .put("apk_records", apkRecords)
            .put("apk_token_ids_per_sec", if (apkTokenRate > 0.0) apkTokenRate else JSONObject.NULL)
            .put("apk_input_mb_per_sec", nativeProbe?.optDouble("input_mb_per_sec", 0.0) ?: JSONObject.NULL)
            .put("ratio_vs_termux_selected_1m_token_ids_per_sec", ratio1m)
            .put("below_80_percent_1m_floor", if (apkTokenRate > 0.0) apkTokenRate < millionBaseline.tokenIdsPerSec * 0.8 else JSONObject.NULL)
            .put("minimum_acceptance_ratio_1m", 0.8)
            .put("termux_selected_baselines", baselines)
    }

    fun abMatrix(): JSONObject {
        val arms = JSONArray()
        listOf("A0_TERMUX_BASELINE", "B0_APK_STANDARD", "B1_ANDROID_GAME_MODE", "B2_REDMAGIC_RISE", "B3_REDMAGIC_DIABLO").forEach { arm ->
            arms.put(JSONObject().put("arm", arm).put("status", "not_run"))
        }
        return JSONObject()
            .put("schema_version", "phase1_ab_matrix_v1")
            .put("status", "blocked")
            .put("arms", arms)
            .put("claim_threshold_met", false)
    }

    fun cometPlan(): JSONObject {
        return JSONObject()
            .put("schema_version", "phase1_comet_logging_plan_v1")
            .put("status", "planned")
            .put("workspace", "zer0pa")
            .put("project_name", "mobile-polymath-ai-training")
            .put("api_key_policy", "COMET_API_KEY must come from host environment only; never APK, report, log, or screenshot.")
            .put("host_script", "scripts/android_lab/log_phase1_android_game_authority_to_comet.py")
    }

    fun forbiddenPayloadScan(manifest: ArtifactManifest): JSONObject {
        val forbidden = listOf(".qai1", ".pqa1", ".jsonl", ".safetensors", ".bin", ".pt", ".pth", ".onnx", ".tflite", ".apk", ".aab")
        val findings = manifest.artifacts
            .filter { artifact -> forbidden.any { artifact.name.endsWith(it) } }
            .map { artifact -> JSONObject().put("name", artifact.name).put("sha256", artifact.sha256) }
        return JSONObject()
            .put("schema_version", "phase1_forbidden_payload_scan_v1")
            .put("status", if (findings.isEmpty()) "pass" else "fail")
            .put("findings_count", findings.size)
            .put("findings", JSONArray(findings))
    }

    fun gateResult(nativeInfo: JSONObject, nativeProbe: JSONObject, appRunResult: JSONObject, reportRoot: String): JSONObject {
        val records = appRunResult.optLong("records", 0L)
        val materialHash = appRunResult.optString("material_hash_hex", "")
        val matchedMaterial = TermuxBaselines.phase1Selected.any { baseline ->
            baseline.records == records &&
                baseline.tokenIds == appRunResult.optLong("token_ids", 0L) &&
                baseline.materialHash == materialHash
        }
        return JSONObject()
            .put("schema_version", "phase1_android_lab_gate_result_v1")
            .put("status", "probe")
            .put("promotion_eligible", false)
            .put("native_connection_state", nativeInfo.optString("connection_state", "NOT_CONNECTED"))
            .put("phase1_core_linked", nativeInfo.optBoolean("phase1_core_linked", false))
            .put("native_return_code", nativeProbe.optInt("return_code", -1))
            .put("exact_material_observed", matchedMaterial)
            .put("authority_blocker", "Final APK promotion remains blocked until host authority evidence includes matched exact material, enforced high-performance profile state, frequency/profile evidence, and no forbidden payloads.")
            .put("report_root", reportRoot)
            .put("nonclaims", JSONArray(listOf("no_phase1_apk_pass", "no_game_mode_benefit", "no_redmagic_rise_or_diablo_benefit", "no_comet_run")))
    }

    fun manifestMarkdown(manifest: ArtifactManifest): String {
        val files = manifest.artifacts.joinToString(separator = "\n") { artifact ->
            "- `${artifact.name}` ${artifact.byteCount} bytes sha256=${artifact.sha256}"
        }
        return """
            |# Polymath Lab Phase 1 App Probe Manifest
            |
            |Run ID: `${manifest.runId.value}`
            |Device report root: `${manifest.root.deviceRelativePath}`
            |Gate state: `probe`
            |
            |This is an APK-owned probe artifact set. It may include exact-material evidence
            |when staged by the host harness, but it does not by itself prove final Phase 1
            |promotion, Game Mode benefit, REDMAGIC Game Space, Rise, Diablo, ADPF, or Comet success.
            |
            |## Files
            |
            |$files
            |
        """.trimMargin()
    }
}

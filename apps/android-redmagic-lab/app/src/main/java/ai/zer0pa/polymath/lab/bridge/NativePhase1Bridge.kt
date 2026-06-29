package ai.zer0pa.polymath.lab.bridge

import org.json.JSONObject

class NativePhase1Bridge {
    fun engineInfo(appFilesDir: String): String {
        return if (libraryLoadResult.isSuccess) {
            nativeEngineInfo(appFilesDir)
        } else {
            fallbackNativeJson("native_engine_info_v1")
        }
    }

    fun probe(
        appFilesDir: String,
        reportOutputPath: String,
        tokenizerDir: String,
        tokenizerTablePath: String,
        batchListPath: String,
        qai1Path: String,
        pqa1OutputPath: String,
        bpeAlgorithm: String,
        phase1ExecPath: String,
        workerCount: Int,
        flags: Int
    ): String {
        return if (libraryLoadResult.isSuccess) {
            nativeProbe(
                appFilesDir,
                reportOutputPath,
                tokenizerDir,
                tokenizerTablePath,
                batchListPath,
                qai1Path,
                pqa1OutputPath,
                bpeAlgorithm,
                phase1ExecPath,
                workerCount,
                flags
            )
        } else {
            fallbackNativeJson("native_probe_result_v1")
        }
    }

    fun libraryLoaded(): Boolean = libraryLoadResult.isSuccess

    fun loadError(): String? = libraryLoadResult.exceptionOrNull()?.message

    private fun fallbackNativeJson(schemaVersion: String): String {
        return JSONObject()
            .put("schema_version", schemaVersion)
            .put("abi_version", 0)
            .put("build_id", "library_load_failed")
            .put("git_sha", "not_embedded")
            .put("engine_name", "polymath_phase1_jni_placeholder")
            .put("connection_state", "BLOCKED")
            .put("probe_state", "PROBE")
            .put("phase1_core_linked", false)
            .put("error_message", loadError() ?: "System.loadLibrary failed")
            .toString()
    }

    private external fun nativeEngineInfo(appFilesDir: String): String
    private external fun nativeProbe(
        appFilesDir: String,
        reportOutputPath: String,
        tokenizerDir: String,
        tokenizerTablePath: String,
        batchListPath: String,
        qai1Path: String,
        pqa1OutputPath: String,
        bpeAlgorithm: String,
        phase1ExecPath: String,
        workerCount: Int,
        flags: Int
    ): String

    companion object {
        private val libraryLoadResult = runCatching {
            System.loadLibrary("polymath_lab_native")
        }
    }
}

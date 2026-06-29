package ai.zer0pa.polymath.lab.data

import android.content.Context
import ai.zer0pa.polymath.lab.domain.ArtifactManifest
import ai.zer0pa.polymath.lab.domain.ArtifactRef
import ai.zer0pa.polymath.lab.domain.ArtifactRoot
import ai.zer0pa.polymath.lab.domain.ArtifactStore
import ai.zer0pa.polymath.lab.domain.RunId
import java.io.File

class LocalArtifactStore(private val context: Context) : ArtifactStore {
    private val reportBase: File
        get() {
            val external = context.getExternalFilesDir(null)
            return File(external ?: context.filesDir, "reports/phase1")
        }

    override suspend fun createRunDirectory(runId: RunId): ArtifactRoot {
        val root = File(reportBase, runId.value)
        require(root.mkdirs() || root.isDirectory) {
            "Unable to create report directory: ${root.absolutePath}"
        }
        return ArtifactRoot(
            runId = runId,
            absolutePath = root.absolutePath,
            deviceRelativePath = "/sdcard/Android/data/${context.packageName}/files/reports/phase1/${runId.value}"
        )
    }

    override suspend fun writeReport(root: ArtifactRoot, name: String, bytes: ByteArray): ArtifactRef {
        require(!name.contains("/") && !name.contains("\\")) {
            "Report name must be a single file name: $name"
        }
        val file = File(root.absolutePath, name)
        file.parentFile?.mkdirs()
        file.writeBytes(bytes)
        return ArtifactRef(
            name = name,
            absolutePath = file.absolutePath,
            sha256 = file.sha256Hex(),
            byteCount = file.length()
        )
    }

    override suspend fun manifest(runId: RunId): ArtifactManifest {
        val rootFile = File(reportBase, runId.value)
        val root = ArtifactRoot(
            runId = runId,
            absolutePath = rootFile.absolutePath,
            deviceRelativePath = "/sdcard/Android/data/${context.packageName}/files/reports/phase1/${runId.value}"
        )
        val artifacts = rootFile.listFiles()
            ?.filter { it.isFile }
            ?.sortedBy { it.name }
            ?.map { file ->
                ArtifactRef(
                    name = file.name,
                    absolutePath = file.absolutePath,
                    sha256 = file.sha256Hex(),
                    byteCount = file.length()
                )
            }
            .orEmpty()
        return ArtifactManifest(runId = runId, root = root, artifacts = artifacts)
    }
}

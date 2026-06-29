package ai.zer0pa.polymath.lab.data

import ai.zer0pa.polymath.lab.domain.ArtifactManifest
import ai.zer0pa.polymath.lab.domain.CometExportQueue
import ai.zer0pa.polymath.lab.domain.ExportTicket
import ai.zer0pa.polymath.lab.domain.GateResultState
import ai.zer0pa.polymath.lab.domain.RunId

class FileCometExportQueue : CometExportQueue {
    override suspend fun enqueue(runId: RunId, manifest: ArtifactManifest): ExportTicket {
        return ExportTicket(
            runId = runId,
            state = GateResultState.PROBE,
            message = "Queued for host-side Comet script only; no COMET_API_KEY is stored in the APK. artifacts=${manifest.artifacts.size}"
        )
    }
}

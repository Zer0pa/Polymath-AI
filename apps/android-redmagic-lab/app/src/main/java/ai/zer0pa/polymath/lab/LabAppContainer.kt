package ai.zer0pa.polymath.lab

import android.app.Activity
import ai.zer0pa.polymath.lab.bridge.NativePhase1Bridge
import ai.zer0pa.polymath.lab.data.AndroidGameAuthorityController
import ai.zer0pa.polymath.lab.data.ApkIdentityReader
import ai.zer0pa.polymath.lab.data.FileCometExportQueue
import ai.zer0pa.polymath.lab.data.LocalArtifactStore
import ai.zer0pa.polymath.lab.data.LocalPhase1ReportReader
import ai.zer0pa.polymath.lab.data.LocalTelemetryCollector
import ai.zer0pa.polymath.lab.data.Phase1NativeTokenizerEngine
import ai.zer0pa.polymath.lab.domain.CometExportQueue
import ai.zer0pa.polymath.lab.domain.GameAuthorityController
import ai.zer0pa.polymath.lab.domain.Phase1ReportReader
import ai.zer0pa.polymath.lab.domain.Phase1TokenizerEngine
import ai.zer0pa.polymath.lab.domain.TelemetryCollector

class LabAppContainer(activity: Activity) {
    val gameAuthorityController: GameAuthorityController = AndroidGameAuthorityController(activity)
    val telemetryCollector: TelemetryCollector = LocalTelemetryCollector()
    val cometExportQueue: CometExportQueue = FileCometExportQueue()
    val phase1ReportReader: Phase1ReportReader = LocalPhase1ReportReader(activity.applicationContext)

    private val artifactStore = LocalArtifactStore(activity.applicationContext)
    private val nativeBridge = NativePhase1Bridge()
    private val apkIdentityReader = ApkIdentityReader(activity.applicationContext)

    val phase1TokenizerEngine: Phase1TokenizerEngine = Phase1NativeTokenizerEngine(
        context = activity.applicationContext,
        bridge = nativeBridge,
        artifactStore = artifactStore,
        apkIdentityReader = apkIdentityReader,
        gameAuthorityController = gameAuthorityController
    )
}

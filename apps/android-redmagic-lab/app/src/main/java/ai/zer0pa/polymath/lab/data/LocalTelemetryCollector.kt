package ai.zer0pa.polymath.lab.data

import ai.zer0pa.polymath.lab.domain.RunId
import ai.zer0pa.polymath.lab.domain.TelemetryCollector
import ai.zer0pa.polymath.lab.domain.TelemetrySession
import ai.zer0pa.polymath.lab.domain.TelemetrySummary

class LocalTelemetryCollector : TelemetryCollector {
    override fun start(runId: RunId, samplePeriodMs: Long): TelemetrySession {
        return TelemetrySession(runId = runId, samplePeriodMs = samplePeriodMs)
    }

    override suspend fun stop(session: TelemetrySession): TelemetrySummary {
        return TelemetrySummary(
            runId = session.runId,
            sampleCount = 0,
            thermalStatus = "NOT_SAMPLED",
            message = "App-side telemetry is a placeholder until REDMAGIC ADB authority run."
        )
    }
}

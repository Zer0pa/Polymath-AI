package ai.zer0pa.polymath.lab.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ai.zer0pa.polymath.lab.domain.Phase1RuntimeSnapshot
import ai.zer0pa.polymath.lab.domain.SourceMode
import ai.zer0pa.polymath.lab.domain.TermuxBaselines
import ai.zer0pa.polymath.lab.ui.LabController
import ai.zer0pa.polymath.lab.ui.LabTab
import ai.zer0pa.polymath.lab.ui.PHASE1_DELIVERED_PIE_SHA256
import ai.zer0pa.polymath.lab.ui.PHASE1_GBT1_SHA256
import ai.zer0pa.polymath.lab.ui.PHASE1_SOURCE_SHA256
import ai.zer0pa.polymath.lab.ui.components.BottomNav
import ai.zer0pa.polymath.lab.ui.components.EvidenceStrip
import ai.zer0pa.polymath.lab.ui.components.LabCommandButton
import ai.zer0pa.polymath.lab.ui.components.MetricRail
import ai.zer0pa.polymath.lab.ui.components.PhasePipeline
import ai.zer0pa.polymath.lab.ui.components.SectionPanel
import ai.zer0pa.polymath.lab.ui.components.SegmentModeToggle
import ai.zer0pa.polymath.lab.ui.theme.LabColors
import ai.zer0pa.polymath.lab.ui.theme.LabType

@Composable
fun LabConsoleScreen(controller: LabController) {
    val state = controller.state

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(LabColors.Black)
            .systemBarsPadding()
            .padding(12.dp)
    ) {
        MetricRail(metrics = state.metrics)
        Spacer(modifier = Modifier.height(10.dp))
        PhasePipeline(phases = state.phases)
        Spacer(modifier = Modifier.height(10.dp))

        Column(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
        ) {
            when (state.selectedTab) {
                LabTab.LAB -> Phase1TokenizerLab(
                    sourceMode = state.sourceMode,
                    busy = state.busy,
                    gameMode = state.gameMode,
                    latestMessage = state.latestMessage,
                    latestReportRoot = state.latestReportRoot,
                    snapshot = state.runtimeSnapshot,
                    onSourceModeChanged = controller::setSourceMode,
                    onRefreshEvidence = controller::refreshLatestReport
                )
                LabTab.RUNS -> RunsPanel(latestReportRoot = state.latestReportRoot, snapshot = state.runtimeSnapshot)
                LabTab.CORPUS -> CorpusPanel(snapshot = state.runtimeSnapshot)
                LabTab.SETTINGS -> SettingsPanel(gameMode = state.gameMode, snapshot = state.runtimeSnapshot)
            }
        }

        Spacer(modifier = Modifier.height(10.dp))
        EvidenceStrip(
            items = listOf(
                "Gate" to state.gateState.name,
                "Native" to state.nativeConnectionState.name,
                "Game" to state.gameMode,
                "Profile" to compactProfileLabel(state.runtimeSnapshot?.oemProfile ?: "UNKNOWN")
            )
        )
        Spacer(modifier = Modifier.height(10.dp))
        BottomNav(selectedTab = state.selectedTab, onSelected = controller::selectTab)
    }
}

@Composable
private fun Phase1TokenizerLab(
    sourceMode: SourceMode,
    busy: Boolean,
    gameMode: String,
    latestMessage: String,
    latestReportRoot: String?,
    snapshot: Phase1RuntimeSnapshot?,
    onSourceModeChanged: (SourceMode) -> Unit,
    onRefreshEvidence: () -> Unit
) {
    BoxWithConstraints(modifier = Modifier.fillMaxWidth()) {
        val wide = maxWidth > 840.dp
        if (wide) {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                SourcePanel(sourceMode, snapshot, onSourceModeChanged, modifier = Modifier.weight(1.0f))
                TokenizerPanel(snapshot, busy, onRefreshEvidence, modifier = Modifier.weight(1.35f))
                EvidencePanel(gameMode, latestMessage, latestReportRoot, snapshot, modifier = Modifier.weight(1.15f))
            }
        } else {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                SourcePanel(sourceMode, snapshot, onSourceModeChanged)
                TokenizerPanel(snapshot, busy, onRefreshEvidence)
                EvidencePanel(gameMode, latestMessage, latestReportRoot, snapshot)
            }
        }
    }
}

@Composable
private fun SourcePanel(
    sourceMode: SourceMode,
    snapshot: Phase1RuntimeSnapshot?,
    onSourceModeChanged: (SourceMode) -> Unit,
    modifier: Modifier = Modifier
) {
    SectionPanel(title = "Artifact Identity", modifier = modifier, minHeight = 280.dp) {
        SegmentModeToggle(selected = sourceMode, onSelected = onSourceModeChanged)
        Spacer(modifier = Modifier.height(16.dp))
        LabelValue("source sha", PHASE1_SOURCE_SHA256.shortHash())
        LabelValue("gbt1 sha", PHASE1_GBT1_SHA256.shortHash())
        LabelValue("delivered pie sha", snapshot?.phase1ExecSha256?.shortHash() ?: PHASE1_DELIVERED_PIE_SHA256.shortHash())
        LabelValue("apk sha", snapshot?.apkSha256?.shortHash() ?: "not captured")
        LabelValue("material", snapshot?.materialState ?: "no staged APK report")
        LabelValue("material hash", snapshot?.materialHash?.shortHash() ?: "not captured")
        Spacer(modifier = Modifier.height(12.dp))
        BodyText("Raw QAI1/PQA1 payloads stay in host temp storage and device staging. The app surface reports hashes and process evidence only.")
    }
}

@Composable
private fun TokenizerPanel(
    snapshot: Phase1RuntimeSnapshot?,
    busy: Boolean,
    onRefreshEvidence: () -> Unit,
    modifier: Modifier = Modifier
) {
    SectionPanel(title = "Phase 1 Native Run", modifier = modifier, minHeight = 280.dp) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            LaneBlock("MODE", runMode(snapshot), modifier = Modifier.weight(1f))
            LaneBlock("WARMUPS", snapshot?.warmupCount?.toString() ?: "0", modifier = Modifier.weight(1f))
            LaneBlock("TRIALS", snapshot?.trialCount?.toString() ?: "0", modifier = Modifier.weight(1f))
        }
        Spacer(modifier = Modifier.height(14.dp))
        LabelValue("run phase", if (busy) "native run active" else snapshot?.runPhase ?: "idle")
        LabelValue("latest throughput", snapshot?.appTokenIdsPerSec?.millionRate() ?: "not measured")
        LabelValue("best trial throughput", snapshot?.bestTrialTokenIdsPerSec?.millionRate() ?: "not measured")
        LabelValue("mean trial throughput", snapshot?.meanTrialTokenIdsPerSec?.millionRate() ?: "not measured")
        Spacer(modifier = Modifier.height(10.dp))
        BaselineTable()
        Spacer(modifier = Modifier.height(14.dp))
        LabCommandButton(
            label = "refresh evidence",
            enabled = !busy,
            onClick = onRefreshEvidence,
            modifier = Modifier.fillMaxWidth()
        )
    }
}

@Composable
private fun EvidencePanel(
    gameMode: String,
    latestMessage: String,
    latestReportRoot: String?,
    snapshot: Phase1RuntimeSnapshot?,
    modifier: Modifier = Modifier
) {
    SectionPanel(title = "Evidence Inspector", modifier = modifier, minHeight = 280.dp) {
        LabelValue("app package", snapshot?.packageName ?: "ai.zer0pa.polymath.lab")
        LabelValue("manifest", "appCategory=${snapshot?.appCategory ?: "game"}")
        LabelValue("game mode", gameMode)
        LabelValue("native", snapshot?.nativeConnectionState?.name ?: "not sampled")
        LabelValue("child exec", childExecState(snapshot))
        LabelValue("cpuset", snapshot?.cpuset ?: "not captured")
        LabelValue("cpus allowed", snapshot?.cpusAllowedList ?: "not captured")
        LabelValue("uclamp max", snapshot?.uclampMax ?: "not captured")
        LabelValue("profile", snapshot?.oemProfile ?: "unknown")
        LabelValue("frequency", snapshot?.cpuFrequencyEvidence ?: "not captured")
        LabelValue("forbidden scan", snapshot?.forbiddenPayloadState ?: "not captured")
        LabelValue("profile policy", snapshot?.settingsRestoredState ?: "host high profile required")
        LabelValue("report root", latestReportRoot ?: "not written")
        Spacer(modifier = Modifier.height(12.dp))
        BodyText(latestMessage)
    }
}

@Composable
private fun BaselineTable() {
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        TermuxBaselines.phase1Selected.forEach { baseline ->
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                MonoText(baseline.scale.uppercase(), modifier = Modifier.weight(0.45f))
                MonoText("%.2fM tok/s".format(baseline.tokenIdsPerSec / 1_000_000.0), modifier = Modifier.weight(1f))
                MonoText(baseline.variant, modifier = Modifier.weight(1.6f))
            }
        }
    }
}

@Composable
private fun LaneBlock(label: String, value: String, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .background(LabColors.Shell)
            .padding(9.dp)
    ) {
        Text(
            text = label,
            color = LabColors.TextMuted,
            style = LabType.Display.copy(fontSize = 11.sp, fontWeight = FontWeight.SemiBold),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
        Text(
            text = value.uppercase(),
            color = LabColors.TextMain,
            style = TextStyle(fontFamily = LabType.Mono, fontSize = 12.sp, letterSpacing = 0.sp),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}

@Composable
private fun RunsPanel(
    latestReportRoot: String?,
    snapshot: Phase1RuntimeSnapshot?
) {
    SectionPanel(title = "Runs", minHeight = 280.dp) {
        LabelValue("latest report", latestReportRoot ?: "none")
        LabelValue("run id", snapshot?.runId ?: "none")
        LabelValue("run phase", snapshot?.runPhase ?: "idle")
        LabelValue("run mode", runMode(snapshot))
        LabelValue("records", snapshot?.records?.toString() ?: "not measured")
        LabelValue("token ids", snapshot?.tokenIds?.toString() ?: "not measured")
        LabelValue("best trial", snapshot?.bestTrialTokenIdsPerSec?.millionRate() ?: "not measured")
        LabelValue("native child errno", snapshot?.childExecErrno?.toString() ?: "not captured")
        BodyText("Authority runs use the REDMAGIC high-performance profile by default. Standard APK mode is not an active product path.")
    }
}

@Composable
private fun CorpusPanel(snapshot: Phase1RuntimeSnapshot?) {
    SectionPanel(title = "Corpus", minHeight = 280.dp) {
        LabelValue("GBT1", PHASE1_GBT1_SHA256.shortHash())
        LabelValue("source material", snapshot?.materialState ?: "no staged APK report")
        LabelValue("records", snapshot?.records?.toString() ?: "not captured")
        LabelValue("token ids", snapshot?.tokenIds?.toString() ?: "not captured")
        LabelValue("material hash", snapshot?.materialHash?.shortHash() ?: "not captured")
        BodyText("Corpus staging is intentionally ADB-owned for authority runs. The app reports material hashes and counts; raw QAI1/PQA1 payloads must not enter git.")
    }
}

@Composable
private fun SettingsPanel(
    gameMode: String,
    snapshot: Phase1RuntimeSnapshot?
) {
    SectionPanel(title = "Settings", minHeight = 280.dp) {
        LabelValue("game mode", gameMode)
        LabelValue("oem profile", snapshot?.oemProfile ?: "unknown")
        LabelValue("frequency evidence", snapshot?.cpuFrequencyEvidence ?: "not captured")
        LabelValue("scheduler policy", snapshot?.schedulerPolicy?.toString() ?: "not captured")
        LabelValue("scheduler prio", snapshot?.schedulerPriority ?: "not captured")
        LabelValue("cgroup", snapshot?.cgroupSummary ?: "not captured")
        LabelValue("comet", "host-side only")
        BodyText("No API keys are stored in the APK. Host authority scripts enforce the Nubia high-performance profile before and after exact child-exec runs.")
    }
}

@Composable
private fun LabelValue(label: String, value: String) {
    Column(modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp)) {
        Text(
            text = label.uppercase(),
            color = LabColors.TextMuted,
            style = LabType.Display.copy(fontSize = 11.sp, fontWeight = FontWeight.SemiBold),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
        MonoText(value, modifier = Modifier.fillMaxWidth())
    }
}

@Composable
private fun BodyText(text: String) {
    Text(
        text = text,
        color = LabColors.TextSoft,
        style = LabType.Display.copy(fontSize = 13.sp, fontWeight = FontWeight.Normal),
        lineHeight = 17.sp
    )
}

@Composable
private fun MonoText(text: String, modifier: Modifier = Modifier) {
    Text(
        text = text,
        color = LabColors.TextMain,
        style = TextStyle(fontFamily = LabType.Mono, fontSize = 12.sp, letterSpacing = 0.sp),
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
        modifier = modifier
    )
}

private fun String.shortHash(): String {
    return if (length > 16) "${take(12)}...${takeLast(4)}" else this
}

private fun Double.millionRate(): String {
    return "%.2fM token IDs/sec".format(this / 1_000_000.0)
}

private fun runMode(snapshot: Phase1RuntimeSnapshot?): String {
    if (snapshot == null) {
        return "not run"
    }
    if (snapshot.childExecEnabled == true) {
        return "exact PIE child exec"
    }
    return when {
        (snapshot.flags and 8) != 0 -> "direct entry diagnostic"
        snapshot.phase1ExecPath != null -> "shared object wrapper"
        else -> "native bridge"
    }
}

private fun childExecState(snapshot: Phase1RuntimeSnapshot?): String {
    if (snapshot == null) {
        return "not captured"
    }
    val enabled = if (snapshot.childExecEnabled == true) "enabled" else "disabled"
    val errno = snapshot.childExecErrno?.toString() ?: "n/a"
    return "$enabled errno=$errno"
}

private fun compactProfileLabel(value: String): String {
    return when {
        value.startsWith("HIGH-CLASS RATE") -> "HIGH RATE"
        value.startsWith("HIGH-FREQUENCY") -> "HIGH-FREQUENCY"
        value.startsWith("STANDARD APK") -> "STANDARD APK"
        else -> value
    }
}

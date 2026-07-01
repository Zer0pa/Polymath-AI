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
import ai.zer0pa.polymath.lab.ui.LabController
import ai.zer0pa.polymath.lab.ui.LabTab
import ai.zer0pa.polymath.lab.ui.WaveBPhaseState
import ai.zer0pa.polymath.lab.ui.WaveBStatusState
import ai.zer0pa.polymath.lab.ui.components.BottomNav
import ai.zer0pa.polymath.lab.ui.components.EvidenceStrip
import ai.zer0pa.polymath.lab.ui.components.MetricRail
import ai.zer0pa.polymath.lab.ui.components.PhasePipeline
import ai.zer0pa.polymath.lab.ui.components.SectionPanel
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
                LabTab.LAB -> WaveBStatusPanel(status = state.waveBStatus)
                LabTab.RUNS -> WaveBRunsPanel(status = state.waveBStatus)
                LabTab.CORPUS -> WaveBCorpusPanel(status = state.waveBStatus)
                LabTab.SETTINGS -> WaveBClaimsPanel(status = state.waveBStatus)
            }
        }

        Spacer(modifier = Modifier.height(10.dp))
        EvidenceStrip(
            items = listOf(
                "Gate" to "C5 PENDING",
                "Lineage" to "FROZEN",
                "C5" to "PENDING",
                "Comet" to "PENDING"
            )
        )
        Spacer(modifier = Modifier.height(10.dp))
        BottomNav(selectedTab = state.selectedTab, onSelected = controller::selectTab)
    }
}

@Composable
private fun WaveBStatusPanel(status: WaveBStatusState) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
        SectionPanel(title = "Wave B Status", minHeight = 170.dp) {
            BodyText(status.headline)
            Spacer(modifier = Modifier.height(12.dp))
            LabelValue("current gate", status.currentGate)
            LabelValue("classification", status.statusClassification)
            LabelValue("first missing green field", status.firstMissingGreenField)
        }
        SectionPanel(title = "Pending And Nonclaims", minHeight = 150.dp) {
            status.badges.forEach { badge ->
                LabelValue("badge", badge)
            }
        }
        BoxWithConstraints(modifier = Modifier.fillMaxWidth()) {
            val wide = maxWidth > 840.dp
            if (wide) {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                    status.phases.take(3).forEach { phase ->
                        WaveBPhaseCard(phase = phase, modifier = Modifier.weight(1f))
                    }
                }
                Spacer(modifier = Modifier.height(10.dp))
            } else {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                    status.phases.forEach { phase ->
                        WaveBPhaseCard(phase = phase)
                    }
                }
            }
        }
        if (status.phases.size > 3) {
            BoxWithConstraints(modifier = Modifier.fillMaxWidth()) {
                val wide = maxWidth > 840.dp
                if (wide) {
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                        status.phases.drop(3).forEach { phase ->
                            WaveBPhaseCard(phase = phase, modifier = Modifier.weight(1f))
                        }
                        Spacer(modifier = Modifier.weight(1f))
                    }
                }
            }
        }
    }
}

@Composable
private fun WaveBPhaseCard(phase: WaveBPhaseState, modifier: Modifier = Modifier) {
    SectionPanel(title = phase.phase, modifier = modifier, minHeight = 210.dp) {
        LabelValue("phase1", "${phase.phase1Status}  ${"%,d".format(phase.records)} records")
        LabelValue("tokens", "%,d".format(phase.tokenIds))
        LabelValue("phase2", "${phase.phase2Status}  ${"%,d".format(phase.packets)} packets")
        LabelValue("pjp1", "${"%,d".format(phase.pjp1Bytes)} bytes  ${phase.pjp1Sha256.shortHash()}")
        LabelValue("phase3/4 mechanics", phase.phase34Status)
        LabelValue("phase4 lineage", phase.phase4LineageStatus)
        LabelValue("update", "consumed=${phase.consumedOutputCausesUpdate} adapter_changed=${phase.adapterChanged}")
    }
}

@Composable
private fun WaveBRunsPanel(status: WaveBStatusState) {
    SectionPanel(title = "Evidence Identity", minHeight = 280.dp) {
        LabelValue("run label", status.runLabel)
        LabelValue("final report sha", status.finalReportSha256)
        LabelValue("lineage proof sha", status.proofSummarySha256)
        LabelValue("lineage proof commit", status.proofCustodyCommit)
        LabelValue("central state sha", status.centralStateSha256)
        LabelValue("final report", status.finalReportPath)
        LabelValue("proof root", status.proofRoot)
        LabelValue("central state", status.centralStatePath)
        LabelValue("proof custody", "frozen")
    }
}

@Composable
private fun WaveBCorpusPanel(status: WaveBStatusState) {
    SectionPanel(title = "C1-C4 Runtime Material", minHeight = 280.dp) {
        status.phases.forEach { phase ->
            LabelValue(
                phase.phase,
                "%,d records / %,d token IDs / %,d packets".format(
                    phase.records,
                    phase.tokenIds,
                    phase.packets
                )
            )
        }
    }
}

@Composable
private fun WaveBClaimsPanel(status: WaveBStatusState) {
    SectionPanel(title = "Boundaries", minHeight = 280.dp) {
        status.rawBoundary.forEach { boundary ->
            LabelValue("raw boundary", boundary)
        }
        BodyText("Phase3/4 lineage-clean proof is validated and frozen for development-cycle evidence. This does not create Phase3 readiness, Phase4 readiness, learning, or model-quality claims.")
        Spacer(modifier = Modifier.height(12.dp))
        LabelValue("lineage-clean evidence", "validated and frozen development-cycle proof")
        status.badges.forEach { badge ->
            LabelValue("nonclaim", badge)
        }
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

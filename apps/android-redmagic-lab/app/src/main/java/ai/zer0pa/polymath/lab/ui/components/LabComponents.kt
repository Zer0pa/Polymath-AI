package ai.zer0pa.polymath.lab.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ai.zer0pa.polymath.lab.domain.PhaseId
import ai.zer0pa.polymath.lab.domain.SourceMode
import ai.zer0pa.polymath.lab.ui.LabTab
import ai.zer0pa.polymath.lab.ui.MetricTileState
import ai.zer0pa.polymath.lab.ui.PhaseTileState
import ai.zer0pa.polymath.lab.ui.theme.LabColors
import ai.zer0pa.polymath.lab.ui.theme.LabType

@Composable
fun MetricRail(metrics: List<MetricTileState>, modifier: Modifier = Modifier) {
    BoxWithConstraints(modifier = modifier.fillMaxWidth()) {
        if (maxWidth > 720.dp) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                metrics.forEach { metric ->
                    RailTile(metric = metric, modifier = Modifier.weight(1f))
                }
            }
        } else {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                metrics.chunked(2).forEach { row ->
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                        row.forEach { metric ->
                            RailTile(metric = metric, modifier = Modifier.weight(1f))
                        }
                        if (row.size == 1) {
                            Spacer(modifier = Modifier.weight(1f))
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun PhasePipeline(phases: List<PhaseTileState>, modifier: Modifier = Modifier) {
    BoxWithConstraints(modifier = modifier.fillMaxWidth()) {
        if (maxWidth > 860.dp) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                phases.forEachIndexed { index, phase ->
                    PhaseTile(phase = phase, modifier = Modifier.weight(1f))
                    if (index < phases.lastIndex) {
                        Box(
                            modifier = Modifier
                                .width(8.dp)
                                .height(1.dp)
                                .background(LabColors.Stroke)
                        )
                    }
                }
            }
        } else {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.fillMaxWidth()) {
                phases.chunked(3).forEach { row ->
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.fillMaxWidth()) {
                        row.forEach { phase ->
                            PhaseTile(phase = phase, modifier = Modifier.weight(1f))
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun SectionPanel(
    title: String,
    modifier: Modifier = Modifier,
    minHeight: Dp = 120.dp,
    content: @Composable () -> Unit
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .heightIn(min = minHeight)
            .background(LabColors.Panel)
            .border(BorderStroke(1.dp, LabColors.Stroke), RoundedCornerShape(2.dp))
            .padding(12.dp)
    ) {
        Text(
            text = title.uppercase(),
            color = LabColors.TextSoft,
            style = LabType.Display.copy(fontSize = 13.sp, fontWeight = FontWeight.SemiBold),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
        Spacer(modifier = Modifier.height(10.dp))
        content()
    }
}

@Composable
fun SegmentModeToggle(
    selected: SourceMode,
    onSelected: (SourceMode) -> Unit,
    modifier: Modifier = Modifier
) {
    Row(
        modifier = modifier
            .border(BorderStroke(1.dp, LabColors.Stroke), RoundedCornerShape(2.dp))
            .padding(2.dp),
        horizontalArrangement = Arrangement.spacedBy(2.dp)
    ) {
        SourceMode.values().forEach { mode ->
            val active = mode == selected
            Text(
                text = mode.wireName.uppercase(),
                color = if (active) LabColors.Black else LabColors.TextSoft,
                style = LabType.Display.copy(fontSize = 12.sp, fontWeight = FontWeight.SemiBold),
                modifier = Modifier
                    .clip(RoundedCornerShape(1.dp))
                    .background(if (active) LabColors.TextMain else Color.Transparent)
                    .clickable { onSelected(mode) }
                    .padding(horizontal = 10.dp, vertical = 7.dp),
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}

@Composable
fun LabCommandButton(
    label: String,
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val foreground = if (enabled) LabColors.Black else LabColors.TextMuted
    val background = if (enabled) LabColors.TextMain else LabColors.PanelAlt
    Text(
        text = label.uppercase(),
        color = foreground,
        style = LabType.Display.copy(fontSize = 13.sp, fontWeight = FontWeight.Bold),
        modifier = modifier
            .clip(RoundedCornerShape(2.dp))
            .background(background)
            .clickable(enabled = enabled, onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 10.dp),
        maxLines = 1,
        overflow = TextOverflow.Ellipsis
    )
}

@Composable
fun EvidenceStrip(items: List<Pair<String, String>>, modifier: Modifier = Modifier) {
    BoxWithConstraints(
        modifier = modifier
            .fillMaxWidth()
            .background(LabColors.Shell)
            .border(BorderStroke(1.dp, LabColors.Stroke), RoundedCornerShape(2.dp))
            .padding(horizontal = 10.dp, vertical = 8.dp)
    ) {
        if (maxWidth > 760.dp) {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                items.forEach { item ->
                    EvidenceItem(item = item, modifier = Modifier.weight(1f))
                }
            }
        } else {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                items.chunked(2).forEach { row ->
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                        row.forEach { item ->
                            EvidenceItem(item = item, modifier = Modifier.weight(1f))
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun EvidenceItem(item: Pair<String, String>, modifier: Modifier = Modifier) {
    Column(modifier = modifier) {
        Text(
            text = item.first.uppercase(),
            color = LabColors.TextMuted,
            style = LabType.Display.copy(fontSize = 11.sp),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
        Text(
            text = item.second,
            color = LabColors.TextMain,
            style = TextStyle(
                fontFamily = LabType.Mono,
                fontSize = 12.sp,
                letterSpacing = 0.sp
            ),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}

@Composable
fun BottomNav(
    selectedTab: LabTab,
    onSelected: (LabTab) -> Unit,
    modifier: Modifier = Modifier
) {
    Surface(
        color = LabColors.Black,
        modifier = modifier.fillMaxWidth()
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(4.dp),
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier
                .border(BorderStroke(1.dp, LabColors.Stroke), RoundedCornerShape(2.dp))
                .padding(4.dp)
        ) {
            LabTab.values().forEach { tab ->
                val selected = tab == selectedTab
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier
                        .weight(1f)
                        .clip(RoundedCornerShape(1.dp))
                        .background(if (selected) LabColors.PanelAlt else Color.Transparent)
                        .clickable { onSelected(tab) }
                        .padding(vertical = 8.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .size(width = 22.dp, height = 3.dp)
                            .background(if (selected) LabColors.TextMain else LabColors.Stroke)
                    )
                    Spacer(modifier = Modifier.height(5.dp))
                    Text(
                        text = tab.label.uppercase(),
                        color = if (selected) LabColors.TextMain else LabColors.TextMuted,
                        style = LabType.Display.copy(fontSize = 12.sp, fontWeight = FontWeight.SemiBold),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
        }
    }
}

@Composable
private fun RailTile(metric: MetricTileState, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .height(74.dp)
            .background(LabColors.Panel)
            .border(BorderStroke(1.dp, LabColors.Stroke), RoundedCornerShape(2.dp))
            .padding(9.dp),
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = metric.label,
            color = LabColors.TextMuted,
            style = LabType.Display.copy(fontSize = 11.sp, fontWeight = FontWeight.SemiBold),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
        Text(
            text = metric.value,
            color = LabColors.TextMain,
            style = LabType.Display.copy(fontSize = 18.sp, fontWeight = FontWeight.Bold),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
        Text(
            text = metric.detail,
            color = LabColors.TextSoft,
            style = TextStyle(fontFamily = LabType.Mono, fontSize = 10.sp, letterSpacing = 0.sp),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}

@Composable
private fun PhaseTile(phase: PhaseTileState, modifier: Modifier = Modifier) {
    val selected = phase.phaseId == PhaseId.P1
    Column(
        modifier = modifier
            .height(54.dp)
            .background(if (selected) LabColors.PanelAlt else LabColors.Shell)
            .border(
                BorderStroke(1.dp, if (selected) LabColors.StrokeHot else LabColors.Stroke),
                RoundedCornerShape(2.dp)
            )
            .padding(7.dp),
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = "${phase.phaseId.shortLabel} ${phase.phaseId.title}".uppercase(),
            color = LabColors.TextMain,
            style = LabType.Display.copy(fontSize = 12.sp, fontWeight = FontWeight.SemiBold),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
        Text(
            text = phase.state,
            color = if (selected) LabColors.TextSoft else LabColors.TextMuted,
            style = TextStyle(fontFamily = LabType.Mono, fontSize = 10.sp, letterSpacing = 0.sp),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}

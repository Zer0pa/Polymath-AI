"""Phase 0C export truth-table runner.

Sweeps ``(model, graph_scope, target)`` triples and records:
  * compile result (ok | failed | unsupported)
  * delegate percentage (when LiteRT / QNN reports it)
  * unsupported ops list
  * log path

Output: per-row ``ExportProbeRecord`` JSON, plus a top-level summary file
with a markdown truth table for the executor handoff.

The runner is designed so the host can dry-run with MacSim adapters and
populate the table shape; the phone fills the real LiteRT / QNN rows when
attached. Both paths emit envelope-shaped records.
"""
from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Tuple

from polymath_ai._version import SCHEMA_VERSION
from polymath_ai.boundary.text import boundary_envelope
from polymath_ai.dispatch.adapters import AcceleratorAdapter, MacSimAdapter, FallbackAdapter
from polymath_ai.utils.canonical import canonical_json, utc_now_iso


PROBE_SCOPES: Tuple[str, ...] = (
    "tiny_block",
    "qwen_block",
    "qwen_frozen_subgraph",
    "smollm3_block",
    "smollm3_frozen_subgraph",
)

PROBE_TARGETS: Tuple[str, ...] = (
    "cpu",
    "vulkan_gpu",
    "litert_gpu",
    "litert_qnn_sm8650",
    "litert_qnn_sm8750",
    "litert_qnn_sm8850",
)


@dataclasses.dataclass(frozen=True)
class ExportProbeSpec:
    model_id: str
    graph_scope: str
    target: str
    notes: Optional[str] = None


@dataclasses.dataclass
class ExportProbeRecord:
    schema_version: str
    boundary: dict
    recorded_at: str
    spec: dict
    backend: str
    result: str  # ok | failed | unsupported | skipped
    delegate_pct: Optional[float]
    unsupported_ops: List[str]
    log_path: Optional[str]
    fallback_used: Optional[str]


def _record_for(spec: ExportProbeSpec, adapter: AcceleratorAdapter) -> ExportProbeRecord:
    probe = adapter.probe()
    if not probe.available:
        return ExportProbeRecord(
            schema_version=SCHEMA_VERSION,
            boundary=boundary_envelope(),
            recorded_at=utc_now_iso(),
            spec=dataclasses.asdict(spec),
            backend=adapter.name,
            result="skipped",
            delegate_pct=None,
            unsupported_ops=[],
            log_path=None,
            fallback_used=adapter.fallback_reason(),
        )
    cr = adapter.compile(model_ref=spec.model_id, graph_scope=spec.graph_scope, target=spec.target)
    return ExportProbeRecord(
        schema_version=SCHEMA_VERSION,
        boundary=boundary_envelope(),
        recorded_at=utc_now_iso(),
        spec=dataclasses.asdict(spec),
        backend=adapter.name,
        result=cr.result,
        delegate_pct=cr.delegate_pct,
        unsupported_ops=list(cr.unsupported_ops),
        log_path=cr.log_path,
        fallback_used=adapter.fallback_reason(),
    )


def run_export_probe(
    specs: Iterable[ExportProbeSpec],
    *,
    adapters: Optional[Sequence[AcceleratorAdapter]] = None,
    out_dir: str | os.PathLike[str] = "runtime/reports/export_probe",
) -> dict:
    """Run an export probe sweep and write rows to ``out_dir``.

    Returns a summary dict with per-spec result.
    """
    if adapters is None:
        adapters = (MacSimAdapter(), FallbackAdapter())

    out = Path(out_dir) / utc_now_iso().replace(":", "")
    out.mkdir(parents=True, exist_ok=True)

    rows: List[dict] = []
    for spec in specs:
        # Pick the adapter whose name matches the target prefix; else MacSim.
        chosen: AcceleratorAdapter = MacSimAdapter()
        for a in adapters:
            if a.name == "mac_sim" and spec.target == "cpu":
                chosen = a
                break
            if a.name == "fallback" and spec.target == "cpu":
                chosen = a
                break
            if spec.target.startswith(a.name):
                chosen = a
                break
        record = _record_for(spec, chosen)
        rows.append(dataclasses.asdict(record))

    summary = {
        "schema_version": SCHEMA_VERSION,
        "boundary": boundary_envelope(),
        "recorded_at": utc_now_iso(),
        "specs_count": len(rows),
        "rows": rows,
    }
    (out / "summary.json").write_text(canonical_json(summary))
    _write_markdown_truth_table(rows, out / "truth_table.md")
    return summary


def _write_markdown_truth_table(rows: List[dict], path: Path) -> None:
    lines: List[str] = []
    lines.append("# Export truth table\n")
    lines.append("Boundary: see polymath_ai.boundary.text.\n")
    lines.append(
        "Stage column distinguishes a *dry-run stub* (host MacSim adapter, "
        "no real compile happened) from a *measured* row (real LiteRT / "
        "QNN / Vulkan compile log). Stub rows do NOT satisfy "
        "qnn_exact_path_unproven; they only show the matrix shape.\n"
    )
    lines.append("| Model | Scope | Target | Backend | Stage | Result | Delegate % | Unsupported ops |")
    lines.append("|---|---|---|---|---|---|---:|---|")
    for r in rows:
        spec = r["spec"]
        ops = ", ".join(r.get("unsupported_ops", [])) or "-"
        dpct = (
            f"{r['delegate_pct']*100:.0f}%" if r.get("delegate_pct") is not None else "-"
        )
        stage = "stub" if r["backend"] in ("mac_sim", "fallback") else "measured"
        lines.append(
            f"| {spec['model_id']} | {spec['graph_scope']} | {spec['target']} | {r['backend']} | {stage} | {r['result']} | {dpct} | {ops} |"
        )
    path.write_text("\n".join(lines) + "\n")

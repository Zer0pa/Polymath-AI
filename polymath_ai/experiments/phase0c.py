"""Phase 0C - export truth table runner."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from polymath_ai.audit.chain import AuditWriter
from polymath_ai.dispatch.export_probe import (
    ExportProbeSpec,
    PROBE_SCOPES,
    PROBE_TARGETS,
    run_export_probe,
)
from polymath_ai.dispatch.adapters import MacSimAdapter, FallbackAdapter
from polymath_ai.utils.canonical import canonical_json


def run(*, config: Mapping[str, Any], run_id: str, run_dir: Path, audit: AuditWriter) -> int:
    models = config.get(
        "models",
        [
            {"model_id": "Qwen/Qwen2.5-1.5B", "scopes": ["tiny_block", "qwen_block", "qwen_frozen_subgraph"]},
            {"model_id": "HuggingFaceTB/SmolLM3-3B", "scopes": ["smollm3_block", "smollm3_frozen_subgraph"]},
        ],
    )
    targets = config.get("targets", list(PROBE_TARGETS))

    specs = []
    for m in models:
        for scope in m["scopes"]:
            for target in targets:
                specs.append(ExportProbeSpec(model_id=m["model_id"], graph_scope=scope, target=target))

    adapters = [MacSimAdapter(), FallbackAdapter()]

    audit.append(event_type="phase_gate", payload={"gate": "phase0c_started", "n_specs": len(specs)})
    summary = run_export_probe(specs, adapters=adapters, out_dir=run_dir / "export_probe")
    audit.append(event_type="export_probe", payload={"specs_count": summary["specs_count"]})
    (run_dir / "summary.json").write_text(canonical_json(summary))
    return 0

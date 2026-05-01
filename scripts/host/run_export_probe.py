#!/usr/bin/env python3
"""Host-side dry-run of the Phase 0C export truth table.

Without a phone or QNN tooling installed, this enumerates the
``(model, scope, target)`` matrix and runs the MacSim adapter to produce a
truth-table skeleton with ``backend=mac_sim`` and ``fallback=fallback``
rows. Real LiteRT / QNN compile rows are filled by the on-phone runner
when Phase 0D / 0G fire.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polymath_ai.dispatch import (
    ExportProbeSpec,
    PROBE_SCOPES,
    PROBE_TARGETS,
    run_export_probe,
)
from polymath_ai.dispatch.adapters import MacSimAdapter, FallbackAdapter


def main():
    specs = []
    models = (
        ("Qwen/Qwen2.5-1.5B", ("tiny_block", "qwen_block", "qwen_frozen_subgraph")),
        ("HuggingFaceTB/SmolLM3-3B", ("smollm3_block", "smollm3_frozen_subgraph")),
        ("tiny.qwen.shape", ("tiny_block",)),
    )
    for mid, scopes in models:
        for scope in scopes:
            for target in PROBE_TARGETS:
                specs.append(
                    ExportProbeSpec(
                        model_id=mid,
                        graph_scope=scope,
                        target=target,
                        notes="host dry-run; real compile pending phone attach + QNN tooling",
                    )
                )

    summary = run_export_probe(specs, adapters=(MacSimAdapter(), FallbackAdapter()))
    print(f"wrote {summary['specs_count']} rows to runtime/reports/export_probe/")


if __name__ == "__main__":
    main()

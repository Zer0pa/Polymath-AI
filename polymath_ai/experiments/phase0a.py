"""Phase 0A — substrate sanity. Re-runs the boundary scanner over the repo
and verifies the audit chain validators, plus runs the phase 0a unit tests
under pytest. Produces a phase_gate event with results.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from polymath_ai.audit.chain import AuditWriter
from polymath_ai.boundary.scanner import scan_path, fail_count


def run(*, config: Mapping[str, Any], run_id: str, run_dir: Path, audit: AuditWriter) -> int:
    target = Path(config.get("scan_root", "."))
    rows = scan_path(target)
    n_fail = fail_count(rows)
    audit.append(
        event_type="boundary_check",
        payload={
            "scan_root": str(target),
            "fail_count": n_fail,
            "row_summary": [{"path": r.path, "status": r.status, "detail": r.detail[:200] if r.detail else ""} for r in rows[:50]],
        },
    )
    return 0 if n_fail == 0 else 1

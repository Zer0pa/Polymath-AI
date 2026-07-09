#!/usr/bin/env python3
"""Build a Phase 3/4 polar-NLL correlation report from aggregate observations."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from polymath_ai.polar.task_aligned_projection import (  # noqa: E402
    build_projection_correlation_report,
    load_json,
    validate_projection_correlation_report,
    write_json,
)


def main() -> int:
    args = parse_args()
    payload = load_json(args.input)
    report = build_projection_correlation_report(
        stage_id=str(payload.get("stage_id")),
        observations=payload.get("observations", []),
        no_update_delta_per_token=payload.get("no_update_delta_per_token"),
        incumbent_candidate_id=str(payload.get("incumbent_candidate_id", "h0_rademacher")),
        run_id=payload.get("run_id"),
        profile=str(payload.get("profile", args.profile)),
    )
    validation_blockers = validate_projection_correlation_report(report)
    if validation_blockers:
        report["status"] = "blocked_fail_closed"
        report["first_missing_green_field"] = validation_blockers[0]
        report["blockers"] = list(dict.fromkeys([*report.get("blockers", []), *validation_blockers]))
    write_json(args.output, report)
    return 0 if report["status"] == "phase34_projection_correlation_pass" else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--profile", default="phase34", choices=("phase34", "phase34b"))
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())

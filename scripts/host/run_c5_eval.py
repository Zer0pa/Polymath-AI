#!/usr/bin/env python3
"""Build a fail-closed metadata-only C5 evaluation report.

This is the canonical host command surface for C5 readiness. It does not run
phone gates, read secrets, call Comet, or copy raw payloads. A C5 pass is
possible only when an executed local metrics JSON satisfying the C5 metric
vocabulary is supplied.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from polymath_ai.polar.c5_eval import (  # noqa: E402
    EVAL_POINTS,
    build_c5_eval_report,
    capture_git_identity,
    expected_identity_schemas,
    load_optional_json_identity,
    load_json,
    report_file_identity,
    sha256_file,
    validate_checkpoint_identity,
    validate_eval_split_identity,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-label")
    parser.add_argument("--eval-point", choices=EVAL_POINTS)
    parser.add_argument("--eval-split", type=Path)
    parser.add_argument("--checkpoint-identity", type=Path)
    parser.add_argument("--stable-baseline-identity", type=Path)
    parser.add_argument("--phase1-report", type=Path)
    parser.add_argument("--phase2-report", type=Path)
    parser.add_argument("--phase34-report", type=Path)
    parser.add_argument("--metrics-json", type=Path, help="Executed local C5 metrics JSON. Required for any C5 pass.")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--print-identity-schema",
        action="store_true",
        help="Print the expected identity schema and exit without writing a report.",
    )
    return parser.parse_args()


def safe_label(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "c5_eval"


def load_and_validate_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []

    eval_split_payload, eval_split_blockers = load_optional_json_identity(args.eval_split, "eval_split")
    blockers.extend(eval_split_blockers)
    eval_split_identity = None
    if eval_split_payload is not None:
        eval_split_identity, identity_blockers = validate_eval_split_identity(eval_split_payload)
        blockers.extend(identity_blockers)

    checkpoint_payload, checkpoint_path_blockers = load_optional_json_identity(
        args.checkpoint_identity,
        "checkpoint_identity",
    )
    blockers.extend(checkpoint_path_blockers)
    checkpoint_identity = None
    if checkpoint_payload is not None:
        checkpoint_identity, identity_blockers = validate_checkpoint_identity(checkpoint_payload, role="candidate")
        blockers.extend(identity_blockers)

    baseline_payload, baseline_path_blockers = load_optional_json_identity(
        args.stable_baseline_identity,
        "stable_baseline_identity",
    )
    blockers.extend(baseline_path_blockers)
    stable_baseline_identity = None
    if baseline_payload is not None:
        stable_baseline_identity, identity_blockers = validate_checkpoint_identity(baseline_payload, role="stable_baseline")
        blockers.extend(identity_blockers)

    phase_report_identities: dict[str, dict[str, Any] | None] = {}
    for label, path in (
        ("phase1_report", args.phase1_report),
        ("phase2_report", args.phase2_report),
        ("phase34_report", args.phase34_report),
    ):
        identity, report_blockers = report_file_identity(path, label)
        blockers.extend(report_blockers)
        phase_report_identities[label] = identity

    executed_metrics = None
    if args.metrics_json is not None:
        identity, metrics_file_blockers = report_file_identity(args.metrics_json, "metrics_json")
        blockers.extend(metrics_file_blockers)
        if identity is not None:
            try:
                executed_metrics = load_json(args.metrics_json)
                executed_metrics["_identity_file"] = identity
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                blockers.append(f"metrics_json_invalid_{type(exc).__name__}")

    return {
        "eval_split_identity": eval_split_identity,
        "checkpoint_identity": checkpoint_identity,
        "stable_baseline_identity": stable_baseline_identity,
        "phase_report_identities": phase_report_identities,
        "executed_metrics": executed_metrics,
    }, blockers


def main() -> int:
    args = parse_args()
    if args.print_identity_schema:
        print(json.dumps(expected_identity_schemas(), indent=2, sort_keys=True))
        return 0

    missing_required_args = [
        name
        for name in ("run_label", "eval_point", "output_dir")
        if getattr(args, name) in (None, "")
    ]
    if missing_required_args:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "blockers": [f"argument_missing_{name}" for name in missing_required_args],
                    "expected_identity_schemas": expected_identity_schemas(),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"c5_eval_{safe_label(args.eval_point)}_{safe_label(args.run_label)}.json"

    loaded, blockers = load_and_validate_inputs(args)
    report = build_c5_eval_report(
        run_label=args.run_label,
        eval_point=args.eval_point,
        eval_split_identity=loaded["eval_split_identity"],
        checkpoint_identity=loaded["checkpoint_identity"],
        stable_baseline_identity=loaded["stable_baseline_identity"],
        phase_report_identities=loaded["phase_report_identities"],
        executed_metrics=loaded["executed_metrics"],
        code_identity=capture_git_identity(REPO_ROOT),
        output_path=output_path,
        blockers=blockers,
    )
    write_json(output_path, report)

    print(
        json.dumps(
            {
                "report_path": str(output_path),
                "report_sha256": sha256_file(output_path),
                "status": report["pass_fail"]["status"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["pass_fail"]["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())

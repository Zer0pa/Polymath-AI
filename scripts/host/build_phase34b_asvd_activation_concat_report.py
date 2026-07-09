#!/usr/bin/env python3
"""Concatenate completed Phase34B ASVD activation captures outside git."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from polymath_ai.polar.asvd_calibration import build_activation_capture_concat_report  # noqa: E402
from polymath_ai.polar.task_aligned_projection import load_json, write_json  # noqa: E402


def main() -> int:
    args = parse_args()
    pull_report = load_json(args.pull_report)
    report = build_activation_capture_concat_report(
        pull_report=pull_report,
        output_capture_f32=args.output_capture_f32,
        repo_root=ROOT,
        expected_chunk_count=args.expected_chunk_count,
        expected_output_sha256=args.expected_output_sha256,
    )
    write_json(args.output_report, report)
    return 0 if report["status"] == "pass" else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pull-report", required=True, type=Path)
    parser.add_argument("--output-capture-f32", required=True, type=Path)
    parser.add_argument("--output-report", required=True, type=Path)
    parser.add_argument("--expected-chunk-count", type=int, default=16)
    parser.add_argument("--expected-output-sha256", default="")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())

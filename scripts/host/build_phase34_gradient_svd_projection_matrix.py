#!/usr/bin/env python3
"""Build a Phase34B H2R Gradient-SVD projection matrix from a gradient surface."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from polymath_ai.polar.gradient_source import build_gradient_svd_projection_report  # noqa: E402
from polymath_ai.polar.task_aligned_projection import load_json, write_json  # noqa: E402


def main() -> int:
    args = parse_args()
    source_report = load_json(args.gradient_source_report)
    report = build_gradient_svd_projection_report(
        gradient_matrix_path=args.gradient_matrix_f32,
        output_matrix_path=args.output_matrix_f32,
        gradient_source_report=source_report,
        repo_root=ROOT,
    )
    write_json(args.output_report, report)
    return 0 if report["status"] == "phase34_projection_matrix_static_contract_pass" else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gradient-matrix-f32", required=True, type=Path)
    parser.add_argument("--gradient-source-report", required=True, type=Path)
    parser.add_argument("--output-matrix-f32", required=True, type=Path)
    parser.add_argument("--output-report", required=True, type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())

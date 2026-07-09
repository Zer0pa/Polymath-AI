#!/usr/bin/env python3
"""Build a metadata-only Phase34B layer-24 gradient source report."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from polymath_ai.polar.gradient_source import build_gradient_source_report  # noqa: E402
from polymath_ai.polar.task_aligned_projection import write_json  # noqa: E402


def main() -> int:
    args = parse_args()
    report = build_gradient_source_report(
        gradient_matrix_path=args.gradient_matrix_f32,
        gradient_matrix_sha256=args.gradient_matrix_sha256,
        row_count=args.row_count,
        dtype=args.dtype,
        model_identity_sha256=args.model_identity_sha256,
        tokenizer_identity_sha256=args.tokenizer_identity_sha256,
        calibration_corpus_identity_sha256=args.calibration_corpus_identity_sha256,
        heldout_overlap_count=args.heldout_overlap_count,
        repo_root=ROOT,
        run_id=args.run_id,
        source_method=args.source_method,
    )
    write_json(args.output, report)
    return 0 if report["status"] == "pass" else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gradient-matrix-f32", required=True, type=Path)
    parser.add_argument("--gradient-matrix-sha256", default="")
    parser.add_argument("--row-count", type=int)
    parser.add_argument("--dtype", default="float32")
    parser.add_argument("--model-identity-sha256", required=True)
    parser.add_argument("--tokenizer-identity-sha256", required=True)
    parser.add_argument("--calibration-corpus-identity-sha256", required=True)
    parser.add_argument("--heldout-overlap-count", type=int, default=0)
    parser.add_argument("--source-method", default="offline_autograd_gradient_calibration")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())

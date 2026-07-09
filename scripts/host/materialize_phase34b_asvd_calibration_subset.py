#!/usr/bin/env python3
"""Build a Phase34B stratified ASVD calibration subset without embedding raw rows."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from polymath_ai.polar.asvd_calibration import build_stratified_asvd_calibration_from_qa_jsonl  # noqa: E402
from polymath_ai.polar.task_aligned_projection import write_json  # noqa: E402


def main() -> int:
    args = parse_args()
    report = build_stratified_asvd_calibration_from_qa_jsonl(
        source_qa_jsonl=args.source_qa_jsonl,
        selected_raw_jsonl=args.selected_raw_jsonl,
        run_id=args.run_id,
        target_record_count=args.target_record_count,
        repo_root=ROOT,
        source_dataset_lineage=args.source_dataset_lineage,
        heldout_qa_jsonl=args.heldout_qa_jsonl,
        expected_source_sha256=args.expected_source_sha256,
        selection_seed=args.selection_seed,
    )
    write_json(args.output, report)
    return 0 if report["status"] == "pass" else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-qa-jsonl", required=True, type=Path)
    parser.add_argument("--selected-raw-jsonl", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target-record-count", type=int, default=128)
    parser.add_argument("--source-dataset-lineage", default="")
    parser.add_argument("--heldout-qa-jsonl", type=Path)
    parser.add_argument("--expected-source-sha256", default="")
    parser.add_argument("--selection-seed", default="phase34b_asvd_stratified_v1")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())

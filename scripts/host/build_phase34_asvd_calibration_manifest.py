#!/usr/bin/env python3
"""Build a metadata-only Phase34B richer-ASVD calibration manifest report."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from polymath_ai.polar.asvd_calibration import build_asvd_calibration_manifest  # noqa: E402
from polymath_ai.polar.task_aligned_projection import load_json, write_json  # noqa: E402


def main() -> int:
    args = parse_args()
    payload = load_json(args.input)
    report = build_asvd_calibration_manifest(
        records=payload.get("records", []),
        run_id=payload.get("run_id"),
        target_record_count=args.target_record_count,
    )
    write_json(args.output, report)
    return 0 if report["status"] == "pass" else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target-record-count", type=int, default=128)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())

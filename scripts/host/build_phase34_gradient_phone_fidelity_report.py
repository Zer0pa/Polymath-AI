#!/usr/bin/env python3
"""Build a Phase34B phone-fidelity report for offline gradient directions."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from polymath_ai.polar.gradient_source import build_gradient_phone_fidelity_report  # noqa: E402
from polymath_ai.polar.task_aligned_projection import load_json, write_json  # noqa: E402


def main() -> int:
    args = parse_args()
    payload = load_json(args.input)
    report = build_gradient_phone_fidelity_report(
        observations=payload.get("observations", []),
        no_update_delta_per_token=payload.get("no_update_delta_per_token"),
        run_id=payload.get("run_id"),
    )
    write_json(args.output, report)
    return 0 if report["status"] == "pass" else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())

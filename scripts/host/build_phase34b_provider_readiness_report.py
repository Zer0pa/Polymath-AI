#!/usr/bin/env python3
"""Build a metadata-only Phase34B provider readiness report."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from polymath_ai.polar.phase34b_provider_readiness import (  # noqa: E402
    build_provider_readiness_report,
    env_names_present_from_process,
)
from polymath_ai.polar.task_aligned_projection import load_json, write_json  # noqa: E402


def main() -> int:
    args = parse_args()
    safe_checks = load_json(args.safe_checks) if args.safe_checks else {}
    present = args.env_name_present or env_names_present_from_process()
    report = build_provider_readiness_report(
        env_names_present=present,
        safe_checks=safe_checks,
        comet_workspace=args.comet_workspace,
        comet_project_name=args.comet_project_name,
        run_id=args.run_id,
    )
    write_json(args.output, report)
    return 0 if report["status"] == "pass" else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--safe-checks", type=Path)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--env-name-present", action="append", default=[])
    parser.add_argument("--comet-workspace", default="zer0pa-imc")
    parser.add_argument("--comet-project-name", default="mobile-polymath-ai-training")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())

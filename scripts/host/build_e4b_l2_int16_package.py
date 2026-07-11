#!/usr/bin/env python3
"""Build the frozen INT16 context gate or atomic package variant."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polymath_ai.frontier.e4b_l2_int16_package import (  # noqa: E402
    build_int16_context_gate,
    materialize_int16_variant,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    gate = commands.add_parser("context-gate")
    gate.add_argument("--fp16-falsification-gate", type=Path, required=True)
    gate.add_argument("--int16-prereg-dir", type=Path, required=True)
    gate.add_argument("--output", type=Path, required=True)
    gate.add_argument("--source-revision", required=True)
    gate.add_argument("--parent-capsule-sha256", required=True)
    gate.add_argument("--frontier-selector-sha256", required=True)
    variant = commands.add_parser("variant")
    variant.add_argument("--base-package-dir", type=Path, required=True)
    variant.add_argument("--fp16-falsification-gate", type=Path, required=True)
    variant.add_argument("--int16-prereg-dir", type=Path, required=True)
    variant.add_argument("--context-gate", type=Path, required=True)
    variant.add_argument("--output-dir", type=Path, required=True)
    variant.add_argument("--source-revision", required=True)
    variant.add_argument("--parent-capsule-sha256", required=True)
    variant.add_argument("--frontier-selector-sha256", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "context-gate":
        result = build_int16_context_gate(
            fp16_falsification_gate=args.fp16_falsification_gate,
            int16_prereg_dir=args.int16_prereg_dir,
            output_path=args.output,
            source_revision=args.source_revision,
            parent_capsule_sha256=args.parent_capsule_sha256,
            frontier_selector_sha256=args.frontier_selector_sha256,
        )
    else:
        result = materialize_int16_variant(
            base_package_dir=args.base_package_dir,
            fp16_falsification_gate=args.fp16_falsification_gate,
            int16_prereg_dir=args.int16_prereg_dir,
            context_gate=args.context_gate,
            output_dir=args.output_dir,
            source_revision=args.source_revision,
            parent_capsule_sha256=args.parent_capsule_sha256,
            frontier_selector_sha256=args.frontier_selector_sha256,
        )
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

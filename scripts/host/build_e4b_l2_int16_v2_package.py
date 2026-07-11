#!/usr/bin/env python3
"""Build the oracle-gated S16 v2 context gate or atomic provider package."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polymath_ai.frontier.e4b_l2_int16_v2_package import (  # noqa: E402
    build_int16_v2_context_gate,
    materialize_int16_v2_variant,
)
from polymath_ai.frontier.e4b_l2_projection_gate import canonical_json  # noqa: E402


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--fp16-falsification-gate", type=Path, required=True)
    parser.add_argument("--int16-v2-prereg-dir", type=Path, required=True)
    parser.add_argument("--int16-v2-oracle-gate", type=Path, required=True)
    parser.add_argument("--int16-v2-verification-receipt", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--parent-capsule-sha256", required=True)
    parser.add_argument("--frontier-selector-sha256", required=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    gate = commands.add_parser("context-gate")
    _common(gate)
    gate.add_argument("--provider-original-scale", type=Path, required=True)
    gate.add_argument("--output", type=Path, required=True)

    variant = commands.add_parser("variant")
    _common(variant)
    variant.add_argument("--base-package-dir", type=Path, required=True)
    variant.add_argument("--context-gate", type=Path, required=True)
    variant.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    common = {
        "fp16_falsification_gate": args.fp16_falsification_gate,
        "int16_v2_prereg_dir": args.int16_v2_prereg_dir,
        "int16_v2_oracle_gate": args.int16_v2_oracle_gate,
        "int16_v2_verification_receipt": args.int16_v2_verification_receipt,
        "source_revision": args.source_revision,
        "parent_capsule_sha256": args.parent_capsule_sha256,
        "frontier_selector_sha256": args.frontier_selector_sha256,
    }
    if args.command == "context-gate":
        result = build_int16_v2_context_gate(
            provider_original_scale=args.provider_original_scale,
            output_path=args.output,
            **common,
        )
    else:
        result = materialize_int16_v2_variant(
            base_package_dir=args.base_package_dir,
            context_gate=args.context_gate,
            output_dir=args.output_dir,
            **common,
        )
    print(canonical_json(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

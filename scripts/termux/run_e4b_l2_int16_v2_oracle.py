#!/usr/bin/env python3
"""Phone-native preregistration, exact-dot oracle, and independent verifier."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polymath_ai.frontier.e4b_l2_int16_v2 import (  # noqa: E402
    ORACLE_ROW_BLOCK_SIZE,
    build_int16_v2_preregistration,
    run_int16_v2_exact_dot_oracle,
)
from polymath_ai.frontier.e4b_l2_int16_v2_verifier import (  # noqa: E402
    verify_int16_v2_phone_oracle,
)
from polymath_ai.frontier.e4b_l2_projection_gate import canonical_json  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    preregister = commands.add_parser("preregister")
    preregister.add_argument("--parent-int16-prereg-dir", type=Path, required=True)
    preregister.add_argument("--frontier-selector", type=Path, required=True)
    preregister.add_argument("--parent-capsule", type=Path, required=True)
    preregister.add_argument("--access-receipt", type=Path, required=True)
    preregister.add_argument("--phone-runtime-root", type=Path, required=True)
    preregister.add_argument("--original-scale", type=Path, required=True)
    preregister.add_argument("--output-dir", type=Path, required=True)
    preregister.add_argument("--created-at-utc", required=True)
    preregister.add_argument("--source-revision", required=True)

    oracle = commands.add_parser("oracle")
    oracle.add_argument("--prereg-dir", type=Path, required=True)
    oracle.add_argument("--packed-weight", type=Path, required=True)
    oracle.add_argument("--authority-root", type=Path, required=True)
    oracle.add_argument("--phone-runtime-root", type=Path, required=True)
    oracle.add_argument("--output-dir", type=Path, required=True)
    oracle.add_argument("--run-id", required=True)

    verify = commands.add_parser("verify")
    verify.add_argument("--prereg-dir", type=Path, required=True)
    verify.add_argument("--oracle-gate", type=Path, required=True)
    verify.add_argument("--packed-weight", type=Path, required=True)
    verify.add_argument("--authority-root", type=Path, required=True)
    verify.add_argument("--phone-runtime-root", type=Path, required=True)
    verify.add_argument("--output", type=Path, required=True)
    verify.add_argument("--run-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "preregister":
        result = build_int16_v2_preregistration(
            parent_int16_prereg_dir=args.parent_int16_prereg_dir,
            frontier_selector=args.frontier_selector,
            parent_capsule=args.parent_capsule,
            access_receipt=args.access_receipt,
            phone_runtime_root=args.phone_runtime_root,
            original_scale_path=args.original_scale,
            output_dir=args.output_dir,
            created_at_utc=args.created_at_utc,
            source_revision=args.source_revision,
        )
    elif args.command == "oracle":
        result = run_int16_v2_exact_dot_oracle(
            prereg_dir=args.prereg_dir,
            packed_weight_path=args.packed_weight,
            authority_root=args.authority_root,
            phone_runtime_root=args.phone_runtime_root,
            output_dir=args.output_dir,
            run_id=args.run_id,
            row_block_size=ORACLE_ROW_BLOCK_SIZE,
        )
    else:
        result = verify_int16_v2_phone_oracle(
            prereg_dir=args.prereg_dir,
            oracle_gate_path=args.oracle_gate,
            packed_weight_path=args.packed_weight,
            authority_root=args.authority_root,
            phone_runtime_root=args.phone_runtime_root,
            output_path=args.output,
            run_id=args.run_id,
        )
    print(canonical_json(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

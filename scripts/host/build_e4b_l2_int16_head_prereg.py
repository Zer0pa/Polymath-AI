#!/usr/bin/env python3
"""Freeze the full-width V79 INT16 LM-head replacement candidate."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polymath_ai.frontier.e4b_l2_int16_head import build_int16_preregistration  # noqa: E402
from polymath_ai.frontier.e4b_l2_projection_gate import canonical_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-prereg-dir", type=Path, required=True)
    parser.add_argument("--fp16-falsification-gate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--created-at-utc", required=True)
    args = parser.parse_args()
    result = build_int16_preregistration(
        parent_prereg_dir=args.parent_prereg_dir,
        fp16_falsification_gate=args.fp16_falsification_gate,
        output_dir=args.output_dir,
        created_at_utc=args.created_at_utc,
    )
    print(canonical_json(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

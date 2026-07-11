#!/usr/bin/env python3
"""Generate exact W4/W2 direct-QNN F5 probe sources from the pinned checkpoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from polymath_ai.frontier.e4b_f5_qnn_exporter import build_probe_package


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--safetensors", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_probe_package(
        safetensors_path=args.safetensors,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

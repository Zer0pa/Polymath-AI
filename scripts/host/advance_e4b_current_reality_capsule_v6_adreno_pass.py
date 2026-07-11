#!/usr/bin/env python3
"""Execute the exact Gemma 4 E4B capsule-v6 Adreno-pass CAS."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polymath_ai.frontier.e4b_capsule_cas import (  # noqa: E402
    CapsuleTransitionError,
    advance_capsule_v6_adreno_pass,
)


DEFAULT_CAPSULE = (
    ROOT / "docs" / "APEX-CURRENT-REALITY-CAPSULE-GEMMA4-E4B-QNN-CELL-2026-07-10.yaml"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Atomically advance the exact governing capsule v6 through the "
            "bounded Adreno pass."
        )
    )
    parser.add_argument("--transition-spec", type=Path, required=True)
    parser.add_argument("--capsule", type=Path, default=DEFAULT_CAPSULE)
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = advance_capsule_v6_adreno_pass(
            canonical_path=args.capsule,
            transition_spec_path=args.transition_spec,
            repository_root=args.repository_root,
        )
    except CapsuleTransitionError as error:
        print(
            json.dumps(
                {"status": "failed_closed", "error": error.code},
                allow_nan=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

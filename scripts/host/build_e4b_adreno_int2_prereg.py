#!/usr/bin/env python3
"""Freeze the phone-native Adreno direct-packed INT2 LM-head experiment."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTRACT_PATH = ROOT / "polymath_ai/frontier/e4b_adreno_int2_lm_head.py"
SPEC = importlib.util.spec_from_file_location(
    "_e4b_adreno_int2_contract", CONTRACT_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load Adreno preregistration contract")
contract = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = contract
SPEC.loader.exec_module(contract)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontier-selector", type=Path, required=True)
    parser.add_argument("--s16-falsification", type=Path, required=True)
    parser.add_argument("--opencl-evidence-report", type=Path, required=True)
    parser.add_argument("--opencl-contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--created-at-utc", required=True)
    args = parser.parse_args()
    result = contract.build_preregistration(
        repository_root=ROOT,
        frontier_selector_path=args.frontier_selector,
        s16_falsification_path=args.s16_falsification,
        opencl_evidence_report_path=args.opencl_evidence_report,
        opencl_contract_path=args.opencl_contract,
        output_dir=args.output_dir,
        created_at_utc=args.created_at_utc,
    )
    print(contract.canonical_json(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

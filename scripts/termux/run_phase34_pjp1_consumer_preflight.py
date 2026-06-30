#!/usr/bin/env python3
"""Inspect PJP1 output shape for Phase 3/4 NPU/GPU consumer scaffolding."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from polymath_ai.polar import PJP1Error, inspect_pjp1
from polymath_ai.polar.pjp1 import write_contract_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pjp1", required=True, type=Path, help="Phone-local or host-local PJP1 file")
    parser.add_argument("--output", required=True, type=Path, help="JSON report path")
    parser.add_argument("--label", default="phase34_pjp1_consumer_preflight")
    parser.add_argument(
        "--authority-material",
        choices=["c1_smoke", "synthetic_proxy", "real_100k", "real_1m", "real_100k_1m"],
        default="c1_smoke",
    )
    parser.add_argument("--metadata-samples", type=int, default=5)
    return parser.parse_args()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    contract = inspect_pjp1(args.pjp1, metadata_samples=args.metadata_samples)
    contract_payload = contract.to_dict()
    validation = contract_payload["validation"]
    real_gate_material = args.authority_material in {"real_100k", "real_1m", "real_100k_1m"}
    return {
        "schema_version": "polar_phase34_pjp1_consumer_preflight_v1",
        "label": args.label,
        "created_at_utc": utc_now(),
        "status": validation["status"],
        "authority_material": args.authority_material,
        "phase3_ready_claim": False,
        "phase3_unlock_component": bool(real_gate_material and validation["status"] == "pass"),
        "nonclaims": [
            "no_npu_htp_execution",
            "no_gpu_optimizer_execution",
            "no_phase3_readiness_claim",
            "no_learning_claim",
            "no_model_quality_claim",
        ],
        "consumer_contract": contract_payload,
        "copy_count_model": copy_count_model(contract_payload),
        "next_required_real_gate": [
            "100k_and_1m_real_PQA1_to_PJP1_pass",
            "PJP1_readback_pass",
            "stratified_oracle_pass",
            "collision_margin_hamming_pass",
            "real_label_k_projection_decision",
            "NPU_app_consumer_preflight_repeated_on_real_PJP1",
            "separate_Phase3_PRD_authorization",
        ],
    }


def copy_count_model(contract_payload: dict[str, Any]) -> dict[str, Any]:
    shape = contract_payload["phase3_shape"]
    input_bytes = int(shape["direct_bitpacked_input_bytes"])
    target_bytes = int(shape["direct_bitpacked_target_bytes"])
    int8_bytes = int(shape["unpack_expansion"]["int8_sign_bytes"])
    return {
        "direct_bitpacked_reader": {
            "cpu_unpack_copies": 0,
            "accelerator_staging_copies_assumed_until_proven": 1,
            "input_staging_bytes": input_bytes,
            "target_staging_bytes": target_bytes,
            "rule": "Can be promoted only if the NPU/GPU consumer accepts uint8 bitpacks directly.",
        },
        "unpacked_int8_reader": {
            "cpu_unpack_copies": 1,
            "accelerator_staging_copies_assumed_until_proven": 1,
            "input_staging_bytes": int8_bytes,
            "target_staging_bytes": int8_bytes,
            "expansion_vs_direct_bitpack": 8,
            "rule": "Must justify the 8x byte expansion with a measured consumer speedup or NPU requirement.",
        },
        "promotion_falsifier": (
            "Any NPU/GPU claim that omits unpack expansion, staging copies, or consumed-output status fails."
        ),
    }


def main() -> int:
    args = parse_args()
    try:
        payload = build_payload(args)
    except (OSError, PJP1Error) as exc:
        payload = {
            "schema_version": "polar_phase34_pjp1_consumer_preflight_v1",
            "label": args.label,
            "created_at_utc": utc_now(),
            "status": "fail",
            "error": str(exc),
            "phase3_ready_claim": False,
        }
    write_contract_json(args.output, payload)
    print(json.dumps({"status": payload["status"], "output": str(args.output)}))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

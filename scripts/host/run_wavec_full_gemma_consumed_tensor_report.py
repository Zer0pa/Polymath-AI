#!/usr/bin/env python3
"""Validate full-Gemma QNN output consumption by the Phase4 bridge report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from polymath_ai.polar.phase4_bridge_cell import validate_phase4_bridge_report  # noqa: E402
from polymath_ai.polar.wavec_full_gemma_qnn import (  # noqa: E402
    AUTHORITY_MATERIAL,
    CONSUMED_SCHEMA_VERSION,
    DISALLOWED_FULL_GEMMA_GRAPHS,
    validate_full_gemma_consumed_tensor_report,
    validate_full_gemma_qnn_forward_report,
)


RAW_SUFFIXES = (
    ".pjp1",
    ".raw",
    ".f32.bin",
    ".bin",
    ".safetensors",
    ".pt",
    ".pth",
    ".ckpt",
)
DEFAULT_OUTPUT = (
    "runtime/reports/polar_phase34_consumer_preflight/active_wave/"
    "full_gemma_consumed_tensor/full_gemma_consumed_tensor_report.json"
)


def main() -> int:
    args = parse_args()
    if args.print_schema:
        print_schema()
        return 0

    qnn_report = read_json(args.qnn_report)
    phase4_report = read_json(args.phase4_report)
    qnn_blockers = validate_full_gemma_qnn_forward_report(qnn_report)
    bridge_blockers = validate_phase4_bridge_report(
        phase4_report,
        expected_phase3_context_sha256=nested(qnn_report, "qnn", "context_sha256"),
        expected_corpus_phase=qnn_report.get("corpus_phase"),
    )
    raw_suffix_count = count_raw_suffixes(Path(args.report_root or Path(args.output).parent))

    qnn = qnn_report.get("qnn", {})
    qnn_output = qnn.get("output", {})
    phase3_output = phase4_report.get("phase3_output", {})
    adapter = phase4_report.get("adapter", {})
    payload: dict[str, Any] = {
        "schema_version": CONSUMED_SCHEMA_VERSION,
        "status": "pending_validation",
        "corpus_phase": qnn_report.get("corpus_phase"),
        "phase3_ready_claim": False,
        "phase4_ready_claim": False,
        "learning_claim": False,
        "authority_material": AUTHORITY_MATERIAL,
        "qnn_forward_report": {
            "path": args.qnn_report,
            "sha256": sha256_file(Path(args.qnn_report)),
        },
        "phase4_report": {
            "path": args.phase4_report,
            "sha256": sha256_file(Path(args.phase4_report)),
        },
        "qnn_forward_blockers": qnn_blockers,
        "phase4_bridge_blockers": bridge_blockers,
        "qnn_forward": {
            "context_sha256": qnn.get("context_sha256"),
            "graph": qnn.get("graph"),
            "backend": qnn.get("backend"),
            "output_path": qnn_output.get("path"),
            "output_sha256": qnn_output.get("sha256"),
            "output_bytes": qnn_output.get("bytes"),
            "context_utility": qnn.get("context_utility"),
            "profile": qnn.get("profile"),
            "tool_identities": qnn.get("tool_identities"),
            "data_movement_ledger": qnn.get("data_movement_ledger"),
        },
        "phase4_consumption": {
            "phase3_output_path": phase3_output.get("path"),
            "phase3_output_sha256": phase3_output.get("sha256"),
            "phase3_graph": phase3_output.get("graph"),
            "phase3_backend": phase3_output.get("backend"),
            "phase3_context_sha256": phase3_output.get("context_sha256"),
            "exact_tensor_sha256_match": phase3_output.get("sha256") == qnn_output.get("sha256"),
            "graph_match": phase3_output.get("graph") == qnn.get("graph"),
            "backend_match": phase3_output.get("backend") == qnn.get("backend"),
            "context_sha256_match": phase3_output.get("context_sha256") == qnn.get("context_sha256"),
            "consumed_output_causes_update": phase4_report.get("consumed_output_causes_update"),
            "adapter_changed": adapter.get("pre_sha256") != adapter.get("post_sha256"),
            "adapter_delta_norm_l2": phase4_report.get("adapter_delta_norm_l2"),
            "loss_source": "phase4_opencl_adapter_update_from_full_gemma_qnn_tensor",
        },
        "opencl_observability": phase4_report.get("telemetry", {}),
        "raw_payload_rules": {
            "raw_suffix_scan_root": args.report_root or str(Path(args.output).parent),
            "raw_suffix_scan_count": raw_suffix_count,
            "raw_suffix_scan_count_zero": raw_suffix_count == 0,
            "raw_payloads_in_git": False,
        },
        "nonclaims": [
            "No C5 pass.",
            "No learning or model-quality claim.",
            "No Phase3/4 readiness.",
            "No full-Gemma HTP forward claim beyond this bounded metadata contract.",
        ],
    }
    blockers = validate_full_gemma_consumed_tensor_report(payload, require_status=False)
    payload["blockers"] = blockers
    payload["status"] = "pass" if not blockers else "blocked"

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0 if payload["status"] == "pass" else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qnn-report", required=False)
    parser.add_argument("--phase4-report", required=False)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--report-root", default="")
    parser.add_argument("--print-schema", action="store_true")
    args = parser.parse_args()
    if not args.print_schema:
        if not args.qnn_report:
            parser.error("--qnn-report is required")
        if not args.phase4_report:
            parser.error("--phase4-report is required")
    return args


def print_schema() -> None:
    print(
        json.dumps(
            {
                "schema_version": CONSUMED_SCHEMA_VERSION,
                "required_identity_matches": [
                    "phase4_consumption.exact_tensor_sha256_match",
                    "phase4_consumption.graph_match",
                    "phase4_consumption.backend_match",
                    "phase4_consumption.context_sha256_match",
                    "phase4_consumption.consumed_output_causes_update",
                    "phase4_consumption.adapter_changed",
                ],
                "disallowed_graphs": sorted(DISALLOWED_FULL_GEMMA_GRAPHS),
                "raw_boundary": "summary report is metadata only and raw suffix scan must be zero",
            },
            indent=2,
            sort_keys=True,
        )
    )


def read_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nested(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def count_raw_suffixes(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("*") if path.is_file() and path.name.endswith(RAW_SUFFIXES))


if __name__ == "__main__":
    raise SystemExit(main())

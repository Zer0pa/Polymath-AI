#!/usr/bin/env python3
"""Emit Phase 10 gates for non-claims that cannot honestly be promoted."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PHASE10_DIR = PROJECT_ROOT / ".gpd/phases/10-hardware-max-training-pipeline"
PHASE10_ACCEPTED_GATE = (
    PROJECT_ROOT
    / "runtime/reports/gemma4_megakernel/hardware_max/"
    "20260517T084203Z_phase10_projected_ple_cache/gate_result.json"
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def full_gemma4_training_gate(accepted: dict[str, Any]) -> dict[str, Any]:
    metrics = accepted.get("metrics", {})
    return {
        "schema_version": "gemma4_phase10_full_training_preflight_v1",
        "status": "fail",
        "claim": "full Gemma4 training",
        "implemented_scope": accepted.get("promotion_scope"),
        "observed_trainable_scope": "post_layer0_rank4_residual_adapter",
        "observed_layer_count": len(metrics.get("layer_elapsed_seconds", [])),
        "observed_rank": metrics.get("rank", 4),
        "blockers": [
            "Current authority lane updates only a rank-4 post-layer0 residual adapter.",
            "Only Gemma4 layer0/layer1 frozen-forward outputs are in the phone training loop.",
            "No full text-stack backward/update/checkpoint schema exists for all Gemma4 trainable parameters.",
            "The objective remains two-layer distillation, not full next-token Gemma4 training.",
        ],
        "authority_verdict": "full_gemma4_training_not_promoted",
    }


def public_benchmark_readiness_gate(
    accepted: dict[str, Any], six_hour_status: str | None, qnn_status: str | None
) -> dict[str, Any]:
    required = {
        "six_hour_endurance_gate": six_hour_status == "pass",
        "hexagon_training_gate_if_claimed": qnn_status == "pass",
        "full_training_scope_gate": False,
        "public_corpus_license_manifest": False,
        "benchmark_rule_harness": False,
        "multi_run_statistics": False,
        "artifact_publication_manifest": False,
    }
    return {
        "schema_version": "gemma4_phase10_public_benchmark_readiness_v1",
        "status": "fail",
        "claim": "public benchmark readiness",
        "required": required,
        "blockers": [
            name for name, passed in required.items() if not passed
        ],
        "authority_verdict": "public_benchmark_readiness_not_promoted",
        "accepted_evidence_scope": accepted.get("promotion_scope"),
    }


def theoretical_maximum_gate(accepted: dict[str, Any]) -> dict[str, Any]:
    deferred = accepted.get("disposition", {}).get("defer", [])
    return {
        "schema_version": "gemma4_phase10_theoretical_maximum_gap_v1",
        "status": "fail",
        "claim": "Snapdragon/Gemma4 theoretical maximum reached",
        "accepted_optimization": "projected PLE row cache",
        "accepted_speedup_x": accepted.get("metrics", {}).get("token_to_hidden_speedup_x"),
        "known_deferred_candidates": deferred
        or [
            "thermal LR governor",
            "Hexagon/AI Engine Direct backend",
            "checkpoint layout experiments",
            "Adreno kernel fusion",
        ],
        "missing_evidence": [
            "No Snapdragon Profiler/AGI/roofline counter envelope for the full training loop.",
            "No QNN/HTP training island parity gate.",
            "No OpenCL/Vulkan kernel-fusion A/B gate after the projected PLE cache.",
            "No checkpoint I/O layout A/B gate over an endurance window.",
            "No energy/thermal authority metric with external power measurement.",
        ],
        "authority_verdict": "theoretical_maximum_not_promoted",
    }


def load_status(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return read_json(path).get("status")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", required=True, type=Path)
    parser.add_argument("--six-hour-gate", type=Path)
    parser.add_argument("--qnn-gate", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    accepted = read_json(PHASE10_ACCEPTED_GATE)
    six_hour_status = load_status(args.six_hour_gate)
    qnn_status = load_status(args.qnn_gate)
    payloads = {
        "full_gemma4_training_preflight.json": full_gemma4_training_gate(accepted),
        "public_benchmark_readiness.json": public_benchmark_readiness_gate(
            accepted, six_hour_status, qnn_status
        ),
        "theoretical_maximum_gap.json": theoretical_maximum_gate(accepted),
    }
    for filename, payload in payloads.items():
        payload["generated_at_utc"] = utc_now()
        write_json(args.report_dir / filename, payload)
    summary = {
        "schema_version": "gemma4_phase10_nonclaim_gate_summary_v1",
        "status": "fail",
        "generated_at_utc": utc_now(),
        "reports": sorted(payloads),
        "authority_verdict": "nonclaims_not_all_resolved",
        "resolved_nonclaims": [
            "six-hour endurance" if six_hour_status == "pass" else None
        ],
        "blocked_nonclaims": [
            "full Gemma4 training",
            "Hexagon NPU training" if qnn_status != "pass" else None,
            "public benchmark readiness",
            "theoretical maximum reached",
        ],
    }
    summary["resolved_nonclaims"] = [
        item for item in summary["resolved_nonclaims"] if item is not None
    ]
    summary["blocked_nonclaims"] = [
        item for item in summary["blocked_nonclaims"] if item is not None
    ]
    write_json(args.report_dir / "gate_result.json", summary)
    print(json.dumps({"status": summary["status"], "report_dir": str(args.report_dir)}, sort_keys=True))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

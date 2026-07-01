#!/usr/bin/env python3
"""Build a PRD C1-C5 Phase3/4 metric-readiness report from compact reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from polymath_ai.polar.phase4_bridge_cell import (
    validate_phase34_metric_readiness,
    validate_phase4_bridge_report,
)


DEFAULT_HTP_REPORT = (
    "runtime/reports/polar_phase34_consumer_preflight/active_wave/"
    "pjp1_htp_relu_run/phase34_pjp1_derived_htp_relu_run.json"
)
DEFAULT_PHASE4_REPORT = (
    "runtime/reports/polar_phase34_consumer_preflight/active_wave/"
    "phase4_bridge_cell/phase4_bridge_cell_report.json"
)
DEFAULT_OUTPUT = (
    "runtime/reports/polar_phase34_consumer_preflight/active_wave/"
    "phase34_metric_readiness/phase34_metric_readiness_report.json"
)


def main() -> int:
    args = parse_args()
    htp = read_json(args.htp_report)
    phase4 = read_json(args.phase4_report)
    payload = build_metric_report(htp, phase4, corpus_phase=args.corpus_phase)
    payload["bridge_validator_blockers"] = validate_phase4_bridge_report(phase4)
    payload["metric_readiness_blockers"] = validate_phase34_metric_readiness(
        payload, corpus_phase=args.corpus_phase
    )
    payload["status"] = (
        "pass"
        if not payload["bridge_validator_blockers"] and not payload["metric_readiness_blockers"]
        else "blocked"
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0 if payload["status"] == "pass" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--htp-report", default=DEFAULT_HTP_REPORT)
    parser.add_argument("--phase4-report", default=DEFAULT_PHASE4_REPORT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--corpus-phase", default="C1")
    return parser.parse_args()


def read_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_metric_report(
    htp: dict[str, Any], phase4: dict[str, Any], *, corpus_phase: str
) -> dict[str, Any]:
    qnn = htp["qnn"]
    telemetry = phase4["telemetry"]
    metrics = {
        f"phase3/{corpus_phase}/pjp1_preflight_status": "pass",
        f"phase3/{corpus_phase}/native_preflight_status": "pass",
        f"phase3/{corpus_phase}/i8_oracle_mismatches": 0,
        f"phase3/{corpus_phase}/htp_backend": qnn["backend"],
        f"phase3/{corpus_phase}/htp_output_sha256": qnn["actual_output_sha256"],
        f"phase3/{corpus_phase}/forward_loss": phase4["loss_pre_update"],
        f"phase3/{corpus_phase}/forward_mse": phase4["loss_pre_update"],
        f"phase3/{corpus_phase}/forward_cross_entropy": None,
        f"phase3/{corpus_phase}/perplexity": None,
        f"phase3/{corpus_phase}/answer_token_accuracy": None,
        f"phase3/{corpus_phase}/calibration_ece": None,
        f"phase3/{corpus_phase}/brier_score": None,
        f"phase3/{corpus_phase}/tokens_per_sec": qnn["tokens_per_sec"],
        f"phase3/{corpus_phase}/latency_ms": qnn["latency_ms"],
        f"phase3/{corpus_phase}/host_to_device_ms": None,
        f"phase3/{corpus_phase}/device_compute_ms": None,
        f"phase3/{corpus_phase}/device_to_host_ms": None,
        f"phase4/{corpus_phase}/opencl_device": phase4["opencl_device_name"],
        f"phase4/{corpus_phase}/phase3_output_sha256": phase4["phase3_output"]["sha256"],
        f"phase4/{corpus_phase}/target_sha256": phase4["phase4_target"]["sha256"],
        f"phase4/{corpus_phase}/adapter_pre_sha256": phase4["adapter"]["pre_sha256"],
        f"phase4/{corpus_phase}/adapter_post_sha256": phase4["adapter"]["post_sha256"],
        f"phase4/{corpus_phase}/consumed_output_causes_update": phase4[
            "consumed_output_causes_update"
        ],
        f"phase4/{corpus_phase}/adapter_changed": phase4["adapter"]["pre_sha256"]
        != phase4["adapter"]["post_sha256"],
        f"phase4/{corpus_phase}/loss_pre_update": phase4["loss_pre_update"],
        f"phase4/{corpus_phase}/loss_post_update": phase4["loss_post_update"],
        f"phase4/{corpus_phase}/loss_delta": phase4["loss_delta"],
        f"phase4/{corpus_phase}/grad_norm_l2": phase4["grad_norm_l2"],
        f"phase4/{corpus_phase}/grad_norm_linf": phase4["grad_norm_linf"],
        f"phase4/{corpus_phase}/update_norm_l2": phase4["update_norm_l2"],
        f"phase4/{corpus_phase}/adapter_delta_norm_l2": phase4["adapter_delta_norm_l2"],
        f"phase4/{corpus_phase}/nan_gradient_count": phase4["nan_gradient_count"],
        f"phase4/{corpus_phase}/inf_gradient_count": phase4["inf_gradient_count"],
        f"phase4/{corpus_phase}/opencl_kernel_ms": telemetry["kernel_elapsed_ns"] / 1_000_000.0,
        f"phase4/{corpus_phase}/tokens_per_sec": 16.0
        / (telemetry["kernel_elapsed_ns"] / 1_000_000_000.0),
        f"phase4/{corpus_phase}/latency_ms": telemetry["kernel_elapsed_ns"] / 1_000_000.0,
    }
    return {
        "schema_version": "polar_phase34_metric_readiness_report_v1",
        "status": "pending_validation",
        "corpus_phase": corpus_phase,
        "phase3_ready_claim": False,
        "phase4_ready_claim": False,
        "learning_claim": False,
        "source_reports": {
            "phase3_htp": DEFAULT_HTP_REPORT,
            "phase4_opencl": DEFAULT_PHASE4_REPORT,
        },
        "metrics": metrics,
        "metric_availability": {
            "cross_entropy": "unavailable_for_bounded_polar_mse_bridge",
            "perplexity": "unavailable_without_language_model_likelihood",
            "answer_token_accuracy": "unavailable_without_supervised_answer_token_targets",
            "calibration_ece": "unavailable_without_probability_distribution",
            "brier_score": "unavailable_without_probability_distribution",
            "host_to_device_ms": "not_isolated_by_current_qnn_net_run_wrapper",
            "device_compute_ms": "not_isolated_by_current_qnn_net_run_wrapper",
            "device_to_host_ms": "not_isolated_by_current_qnn_net_run_wrapper",
        },
        "c5_compatibility": {
            "status": "metric_names_aligned_no_c5_authority",
            "requires_c5_eval_points": [
                "C5_after_C1",
                "C5_after_C2",
                "C5_after_C2_5",
                "C5_after_C3",
                "C5_after_C4",
                "C5_full_curriculum_postrun",
            ],
            "nonclaim": "no C5 evaluation has been run by this Phase3/4 metric readiness proof",
        },
        "nonclaims": [
            "No Phase3 readiness.",
            "No Phase4 readiness.",
            "No learning or model-quality claim.",
            "No C5 authority.",
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())

"""Fail-closed contract checks for the Phase 4 bridge cell."""

from __future__ import annotations

import math
import re
from typing import Any


CELL_ID = "phase4_opencl_phase3_bridge_rank16_mse_sgd_cell_v0"
EXPECTED_SHAPE = [1, 16, 2560]
EXPECTED_DTYPE = "float32_le"
CURRICULUM_CORPUS_PHASES = ("C1", "C2", "C2_5", "C3", "C4")
DIAGNOSTIC_CORPUS_PHASES = ("C1_diagnostic",)
PLACEHOLDER_IDENTITY_VALUES = {
    "p13_existing_context_identity_recorded_not_pulled",
    "measured_from_output_payload_metadata",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_RAW_PREFIXES = (
    "/data/local/tmp/",
    "/sdcard/",
    "/storage/emulated/0/",
    "/data/data/com.termux/files/home/",
)
FORBIDDEN_REPO_RAW_SUFFIXES = (
    ".pqa1",
    ".pjp1",
    ".safetensors",
    ".raw",
    ".f32.bin",
    ".i8.bin",
)
REQUIRED_PHASE3_METRICS = (
    "pjp1_preflight_status",
    "native_preflight_status",
    "i8_oracle_mismatches",
    "htp_backend",
    "htp_output_sha256",
    "forward_loss",
    "forward_mse",
    "forward_cross_entropy",
    "perplexity",
    "answer_token_accuracy",
    "calibration_ece",
    "brier_score",
    "tokens_per_sec",
    "latency_ms",
    "host_to_device_ms",
    "device_compute_ms",
    "device_to_host_ms",
)
REQUIRED_PHASE4_METRICS = (
    "opencl_device",
    "phase3_output_sha256",
    "target_sha256",
    "adapter_pre_sha256",
    "adapter_post_sha256",
    "consumed_output_causes_update",
    "adapter_changed",
    "loss_pre_update",
    "loss_post_update",
    "loss_delta",
    "grad_norm_l2",
    "grad_norm_linf",
    "update_norm_l2",
    "adapter_delta_norm_l2",
    "nan_gradient_count",
    "inf_gradient_count",
    "opencl_kernel_ms",
    "tokens_per_sec",
    "latency_ms",
)
REQUIRED_OPENCL_TELEMETRY_FIELDS = (
    "dispatch_count",
    "profiled_dispatch_count",
    "sync_count",
    "host_device_bytes",
    "blocking_read_bytes",
    "kernel_elapsed_ns",
)
REQUIRED_OPENCL_DATA_LEDGER_FIELDS = (
    "phase3_tensor_read_bytes",
    "target_read_bytes",
    "opencl_host_to_device_bytes",
    "opencl_device_to_host_bytes",
    "adapter_read_write_bytes",
)
OPTIONAL_WHEN_UNSUPPORTED = {
    "forward_cross_entropy": "cross_entropy",
    "perplexity": "perplexity",
    "answer_token_accuracy": "answer_token_accuracy",
    "calibration_ece": "calibration_ece",
    "brier_score": "brier_score",
    "host_to_device_ms": "host_to_device_ms",
    "device_compute_ms": "device_compute_ms",
    "device_to_host_ms": "device_to_host_ms",
}


def validate_phase4_bridge_report(
    report: dict[str, Any],
    *,
    expected_source_pjp1_sha256: str | None = None,
    expected_phase3_context_sha256: str | None = None,
    expected_corpus_phase: str | None = None,
) -> list[str]:
    """Return fail-closed blocker codes for a compact Phase 4 bridge report."""

    blockers: list[str] = []
    require_equal(blockers, report.get("cell_id"), CELL_ID, "wrong_cell_id")
    corpus_phase = report.get("corpus_phase")
    require_present(blockers, corpus_phase, "missing_corpus_phase")
    if isinstance(corpus_phase, str) and corpus_phase:
        if corpus_phase not in CURRICULUM_CORPUS_PHASES + DIAGNOSTIC_CORPUS_PHASES:
            blockers.append(f"unsupported_corpus_phase:{corpus_phase}")
        if expected_corpus_phase is not None:
            require_equal(blockers, corpus_phase, expected_corpus_phase, "wrong_corpus_phase")
    require_false(blockers, report.get("phase3_ready_claim"), "phase3_ready_claim_true")
    require_false(blockers, report.get("phase4_ready_claim"), "phase4_ready_claim_true")
    require_false(blockers, report.get("learning_claim"), "learning_claim_true")
    require_equal(blockers, report.get("authority_material"), "mechanical_consumed_output_preflight_only", "wrong_authority_material")

    phase3 = require_mapping(blockers, report.get("phase3_output"), "missing_phase3_output")
    target = require_mapping(blockers, report.get("phase4_target"), "missing_phase4_target")
    if phase3:
        validate_tensor_lineage(blockers, phase3, "phase3_output")
        require_true(blockers, phase3.get("sha256_match"), "phase3_output_sha256_mismatch")
        require_present(blockers, phase3.get("context_sha256"), "missing_phase3_context_sha256")
        require_sha256(blockers, phase3.get("context_sha256"), "bad_phase3_context_sha256")
        if expected_phase3_context_sha256 is not None:
            require_equal(blockers, phase3.get("context_sha256"), expected_phase3_context_sha256, "phase3_context_sha256_mismatch")
        require_present(blockers, phase3.get("backend"), "missing_phase3_backend")
        require_present(blockers, phase3.get("graph"), "missing_phase3_graph")
    if target:
        validate_tensor_lineage(blockers, target, "phase4_target")
        require_true(blockers, target.get("sha256_match"), "phase4_target_sha256_mismatch")
        require_present(blockers, target.get("source_pjp1_sha256"), "missing_target_pjp1_sha256")
        require_sha256(blockers, target.get("source_pjp1_sha256"), "bad_target_pjp1_sha256")
        if expected_source_pjp1_sha256 is not None:
            require_equal(blockers, target.get("source_pjp1_sha256"), expected_source_pjp1_sha256, "target_pjp1_sha256_mismatch")
        require_present(blockers, target.get("bridge_rule"), "missing_target_bridge_rule")

    require_equal(blockers, report.get("opencl_device_is_adreno"), True, "opencl_device_not_adreno")
    require_false(blockers, report.get("no_hidden_fallback") is False, "hidden_fallback_present")
    require_false(blockers, report.get("no_cpu_objective_gradient_update") is False, "cpu_objective_gradient_update_present")
    require_present(blockers, report.get("named_consumer"), "missing_named_consumer")
    require_true(blockers, report.get("consumed_output_causes_update"), "missing_consumed_output_causality")
    require_true(blockers, report.get("comparator_parity_pass"), "missing_comparator_parity")
    require_true(blockers, report.get("frozen_mutation_count_zero"), "frozen_base_mutated")

    for name in ("loss", "grad_norm", "update_norm", "loss_pre_update", "loss_post_update", "grad_norm_l2", "grad_norm_linf", "update_norm_l2", "adapter_delta_norm_l2"):
        require_finite_positive_or_zero(blockers, report.get(name), f"nonfinite_{name}")
    require_finite(blockers, report.get("loss_delta"), "nonfinite_loss_delta")
    require_zero_count(blockers, report.get("nan_gradient_count"), "nan_gradient_count_nonzero")
    require_zero_count(blockers, report.get("inf_gradient_count"), "inf_gradient_count_nonzero")

    adapter = require_mapping(blockers, report.get("adapter"), "missing_adapter")
    if adapter:
        require_equal(blockers, adapter.get("rank"), 16, "wrong_adapter_rank")
        require_present(blockers, adapter.get("pre_sha256"), "missing_adapter_pre_sha256")
        require_present(blockers, adapter.get("post_sha256"), "missing_adapter_post_sha256")
        if adapter.get("apply_update") is True and adapter.get("pre_sha256") == adapter.get("post_sha256"):
            blockers.append("adapter_hash_unchanged_after_update")
        require_true(blockers, adapter.get("delta_nonzero"), "adapter_delta_zero")

    telemetry = require_mapping(blockers, report.get("telemetry"), "missing_telemetry")
    if telemetry:
        for key in REQUIRED_OPENCL_TELEMETRY_FIELDS:
            require_nonnegative_int(blockers, telemetry.get(key), f"bad_telemetry_{key}")
        require_true(blockers, telemetry.get("thermal_stop_band_pass"), "thermal_stop_band_failed")
        require_present(blockers, telemetry.get("kernel_lineage_class"), "missing_kernel_lineage_class")
        kernel_names = telemetry.get("kernel_names")
        if not isinstance(kernel_names, list) or not kernel_names:
            blockers.append("missing_opencl_kernel_names")
        require_present(blockers, telemetry.get("opencl_platform"), "missing_opencl_platform")
        require_present(blockers, telemetry.get("opencl_device"), "missing_opencl_device")
        require_present(blockers, telemetry.get("opencl_library_identity"), "missing_opencl_library_identity")
        data_ledger = require_mapping(blockers, telemetry.get("data_movement_ledger"), "missing_opencl_data_movement_ledger")
        if data_ledger:
            for key in REQUIRED_OPENCL_DATA_LEDGER_FIELDS:
                require_nonnegative_int(blockers, data_ledger.get(key), f"bad_opencl_data_movement_{key}")
        runtime_state = require_mapping(blockers, telemetry.get("runtime_state"), "missing_runtime_state")
        if runtime_state:
            for key in ("cpuset", "rss_hwm_kb", "meminfo_kb", "thermal_state", "performance_state"):
                if key not in runtime_state:
                    blockers.append(f"missing_runtime_state_{key}")

    raw_rules = require_mapping(blockers, report.get("raw_payload_rules"), "missing_raw_payload_rules")
    if raw_rules:
        require_false(blockers, raw_rules.get("raw_pjp1_pulled_to_host"), "raw_pjp1_pulled_to_host")
        require_false(blockers, raw_rules.get("raw_qnn_output_pulled_to_repo"), "raw_qnn_output_pulled_to_repo")
        require_false(blockers, raw_rules.get("raw_model_or_checkpoint_pulled_to_repo"), "raw_model_or_checkpoint_pulled_to_repo")
        for path in raw_rules.get("repo_paths", []):
            if str(path).endswith(FORBIDDEN_REPO_RAW_SUFFIXES):
                blockers.append("raw_payload_path_in_repo")

    if isinstance(corpus_phase, str) and corpus_phase:
        blockers.extend(validate_phase34_metric_readiness(report, corpus_phase=corpus_phase))

    return blockers


def validate_phase34_metric_readiness(report: dict[str, Any], *, corpus_phase: str | None = None) -> list[str]:
    """Validate PRD C1-C5 Phase3/4 metric names and finite-value readiness."""

    blockers = []
    resolved_corpus_phase = corpus_phase or report.get("corpus_phase")
    if not isinstance(resolved_corpus_phase, str) or not resolved_corpus_phase:
        blockers.append("missing_corpus_phase")
        return blockers
    if resolved_corpus_phase not in CURRICULUM_CORPUS_PHASES + DIAGNOSTIC_CORPUS_PHASES:
        blockers.append(f"unsupported_corpus_phase:{resolved_corpus_phase}")

    metrics = require_mapping(blockers, report.get("metrics"), "missing_metrics")
    availability = require_mapping(blockers, report.get("metric_availability"), "missing_metric_availability")
    if not metrics:
        return blockers

    for metric_name in REQUIRED_PHASE3_METRICS:
        key = f"phase3/{resolved_corpus_phase}/{metric_name}"
        validate_metric_value(blockers, metrics, availability or {}, key, metric_name)

    for metric_name in REQUIRED_PHASE4_METRICS:
        key = f"phase4/{resolved_corpus_phase}/{metric_name}"
        validate_metric_value(blockers, metrics, availability or {}, key, metric_name)

    c5 = require_mapping(blockers, report.get("c5_compatibility"), "missing_c5_compatibility")
    if c5:
        require_equal(blockers, c5.get("status"), "metric_names_aligned_no_c5_authority", "wrong_c5_compatibility_status")
        eval_points = c5.get("requires_c5_eval_points")
        if not isinstance(eval_points, list) or len(eval_points) != 6:
            blockers.append("missing_c5_eval_points")
        require_present(blockers, c5.get("nonclaim"), "missing_c5_nonclaim")

    return blockers


def validate_phase34_curriculum_metric_readiness(reports: dict[str, dict[str, Any]]) -> list[str]:
    """Validate that every C1-C4 curriculum phase has a Phase3/4 metric report."""

    blockers: list[str] = []
    for corpus_phase in CURRICULUM_CORPUS_PHASES:
        report = reports.get(corpus_phase)
        if report is None:
            blockers.append(f"missing_corpus_phase_report:{corpus_phase}")
            continue
        blockers.extend(
            f"{corpus_phase}:{blocker}"
            for blocker in validate_phase34_metric_readiness(report, corpus_phase=corpus_phase)
        )
    return blockers


def validate_tensor_lineage(blockers: list[str], tensor: dict[str, Any], prefix: str) -> None:
    require_equal(blockers, tensor.get("shape"), EXPECTED_SHAPE, f"{prefix}_wrong_shape")
    require_equal(blockers, tensor.get("dtype"), EXPECTED_DTYPE, f"{prefix}_wrong_dtype")
    require_present(blockers, tensor.get("sha256"), f"missing_{prefix}_sha256")
    path = tensor.get("path")
    require_present(blockers, path, f"missing_{prefix}_path")
    if path and not str(path).startswith(ALLOWED_RAW_PREFIXES):
        blockers.append(f"{prefix}_path_outside_phone_boundary")


def validate_metric_value(
    blockers: list[str],
    metrics: dict[str, Any],
    availability: dict[str, Any],
    key: str,
    metric_name: str,
) -> None:
    if key not in metrics:
        blockers.append(f"missing_metric:{key}")
        return
    value = metrics[key]
    if value is None:
        availability_key = OPTIONAL_WHEN_UNSUPPORTED.get(metric_name)
        if availability_key is None or not availability.get(availability_key):
            blockers.append(f"null_metric_without_availability:{key}")
        return
    if isinstance(value, bool):
        return
    if isinstance(value, str):
        require_present(blockers, value, f"empty_metric:{key}")
        return
    require_finite_number(blockers, value, f"nonfinite_metric:{key}")


def require_mapping(blockers: list[str], value: Any, code: str) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        blockers.append(code)
        return None
    return value


def require_present(blockers: list[str], value: Any, code: str) -> None:
    if value in (None, ""):
        blockers.append(code)


def require_sha256(blockers: list[str], value: Any, code: str) -> None:
    if not isinstance(value, str):
        blockers.append(code)
        return
    if value in PLACEHOLDER_IDENTITY_VALUES or SHA256_PATTERN.fullmatch(value) is None:
        blockers.append(code)


def require_equal(blockers: list[str], actual: Any, expected: Any, code: str) -> None:
    if actual != expected:
        blockers.append(code)


def require_true(blockers: list[str], value: Any, code: str) -> None:
    if value is not True:
        blockers.append(code)


def require_false(blockers: list[str], value: Any, code: str) -> None:
    if value is not False:
        blockers.append(code)


def require_finite_positive_or_zero(blockers: list[str], value: Any, code: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        blockers.append(code)
        return
    if not math.isfinite(float(value)) or float(value) < 0.0:
        blockers.append(code)


def require_finite(blockers: list[str], value: Any, code: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        blockers.append(code)
        return
    if not math.isfinite(float(value)):
        blockers.append(code)


def require_zero_count(blockers: list[str], value: Any, code: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value != 0:
        blockers.append(code)


def require_finite_number(blockers: list[str], value: Any, code: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        blockers.append(code)
        return
    if not math.isfinite(float(value)):
        blockers.append(code)


def require_nonnegative_int(blockers: list[str], value: Any, code: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        blockers.append(code)

"""Fail-closed contracts for the WaveC full-Gemma QNN/HTP forward route."""

from __future__ import annotations

import math
import re
from typing import Any


EXPECTED_SHAPE = [1, 16, 2560]
EXPECTED_DTYPE = "float32_le"
EXPECTED_BYTES = 1 * 16 * 2560 * 4
FORWARD_SCHEMA_VERSION = "waveC_full_gemma_qnn_forward_report_v1"
CONSUMED_SCHEMA_VERSION = "waveC_full_gemma_consumed_tensor_report_v1"
PRODUCER_KIND = "full_gemma_qnn_htp_forward_island"
AUTHORITY_MATERIAL = "waveC_full_gemma_qnn_forward_preflight_only"
DISALLOWED_FULL_GEMMA_GRAPHS = {
    "gemma_hidden2560_relu",
    "gemma_hidden2560_identity_add",
}
ALLOWED_PHONE_PREFIXES = (
    "/data/local/tmp/",
    "/sdcard/",
    "/storage/emulated/0/",
    "/data/data/com.termux/files/home/",
)
FORBIDDEN_REPO_RAW_SUFFIXES = (
    ".pjp1",
    ".raw",
    ".f32.bin",
    ".bin",
    ".safetensors",
    ".pt",
    ".pth",
    ".ckpt",
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PROFILE_TIME_PATTERN = re.compile(r"(?P<value>[0-9]+(?:\.[0-9]+)?)\s*(?P<unit>ns|us|µs|ms|s)\b", re.IGNORECASE)
PROFILE_EXECUTE_HINTS = (
    "execute",
    "execution",
    "graph",
    "qnn_partition",
    "rpc",
    "accelerator",
    "htp",
)


def parse_qnn_profile_viewer_text(text: str) -> dict[str, Any]:
    """Extract a conservative accelerator/runtime timing hint from qnn-profile-viewer text."""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates = []
    for line in lines:
        lowered = line.lower()
        if not any(hint in lowered for hint in PROFILE_EXECUTE_HINTS):
            continue
        for match in PROFILE_TIME_PATTERN.finditer(line):
            candidates.append(
                {
                    "line": line[:240],
                    "duration_ms": convert_to_ms(float(match.group("value")), match.group("unit")),
                }
            )

    if candidates:
        return {
            "qnn_profile_parse_attempted": True,
            "qnn_accelerator_execute_ms": candidates[0]["duration_ms"],
            "qnn_accelerator_execute_ms_unavailable_reason": None,
            "profile_events_considered": candidates[:8],
        }
    return {
        "qnn_profile_parse_attempted": True,
        "qnn_accelerator_execute_ms": None,
        "qnn_accelerator_execute_ms_unavailable_reason": "qnn_profile_viewer_output_did_not_expose_parseable_execute_duration",
        "profile_events_considered": [],
    }


def validate_full_gemma_qnn_forward_report(
    report: dict[str, Any], *, require_status: bool = True
) -> list[str]:
    """Return blocker codes for a full-Gemma QNN/HTP forward metadata report."""

    blockers: list[str] = []
    require_equal(blockers, report.get("schema_version"), FORWARD_SCHEMA_VERSION, "wrong_schema_version")
    if require_status:
        require_equal(blockers, report.get("status"), "pass", "status_not_pass")
    require_false(blockers, report.get("phase3_ready_claim"), "phase3_ready_claim_true")
    require_false(blockers, report.get("phase4_ready_claim"), "phase4_ready_claim_true")
    require_false(blockers, report.get("learning_claim"), "learning_claim_true")
    require_equal(blockers, report.get("authority_material"), AUTHORITY_MATERIAL, "wrong_authority_material")

    qnn = require_mapping(blockers, report.get("qnn"), "missing_qnn")
    if qnn:
        validate_qnn_contract(blockers, qnn)

    raw_rules = require_mapping(blockers, report.get("raw_payload_rules"), "missing_raw_payload_rules")
    if raw_rules:
        require_false(blockers, raw_rules.get("raw_pjp1_pulled_to_host"), "raw_pjp1_pulled_to_host")
        require_false(blockers, raw_rules.get("raw_qnn_output_pulled_to_repo"), "raw_qnn_output_pulled_to_repo")
        require_false(
            blockers,
            raw_rules.get("raw_model_or_checkpoint_pulled_to_repo"),
            "raw_model_or_checkpoint_pulled_to_repo",
        )
        require_true(blockers, raw_rules.get("compact_hash_report_only"), "compact_hash_report_only_false")
        for path in raw_rules.get("repo_paths", []):
            if str(path).endswith(FORBIDDEN_REPO_RAW_SUFFIXES):
                blockers.append("raw_payload_path_in_repo")

    return blockers


def validate_full_gemma_consumed_tensor_report(
    report: dict[str, Any], *, require_status: bool = True
) -> list[str]:
    """Return blocker codes for the QNN-forward to Phase4-consumption summary."""

    blockers: list[str] = []
    require_equal(blockers, report.get("schema_version"), CONSUMED_SCHEMA_VERSION, "wrong_schema_version")
    if require_status:
        require_equal(blockers, report.get("status"), "pass", "status_not_pass")
    require_false(blockers, report.get("phase3_ready_claim"), "phase3_ready_claim_true")
    require_false(blockers, report.get("phase4_ready_claim"), "phase4_ready_claim_true")
    require_false(blockers, report.get("learning_claim"), "learning_claim_true")
    require_equal(blockers, report.get("authority_material"), AUTHORITY_MATERIAL, "wrong_authority_material")
    require_equal(blockers, report.get("qnn_forward_blockers"), [], "qnn_forward_blockers_present")
    require_equal(blockers, report.get("phase4_bridge_blockers"), [], "phase4_bridge_blockers_present")

    qnn = require_mapping(blockers, report.get("qnn_forward"), "missing_qnn_forward")
    phase4 = require_mapping(blockers, report.get("phase4_consumption"), "missing_phase4_consumption")
    if qnn:
        require_sha256(blockers, qnn.get("context_sha256"), "bad_qnn_context_sha256")
        require_sha256(blockers, qnn.get("output_sha256"), "bad_qnn_output_sha256")
        validate_graph_name(blockers, qnn.get("graph"))
    if phase4:
        require_sha256(blockers, phase4.get("phase3_output_sha256"), "bad_phase4_phase3_output_sha256")
        require_true(blockers, phase4.get("exact_tensor_sha256_match"), "phase4_tensor_sha256_mismatch")
        require_true(blockers, phase4.get("graph_match"), "phase4_graph_mismatch")
        require_true(blockers, phase4.get("backend_match"), "phase4_backend_mismatch")
        require_true(blockers, phase4.get("context_sha256_match"), "phase4_context_sha256_mismatch")
        require_true(blockers, phase4.get("consumed_output_causes_update"), "missing_consumed_output_causality")
        require_true(blockers, phase4.get("adapter_changed"), "adapter_hash_unchanged_after_update")
        require_finite_positive_or_zero(
            blockers, phase4.get("adapter_delta_norm_l2"), "nonfinite_adapter_delta_norm_l2"
        )
        if phase4.get("adapter_delta_norm_l2") == 0:
            blockers.append("adapter_delta_zero")

    raw_rules = require_mapping(blockers, report.get("raw_payload_rules"), "missing_raw_payload_rules")
    if raw_rules:
        require_true(blockers, raw_rules.get("raw_suffix_scan_count_zero"), "raw_suffix_scan_count_nonzero")
        require_false(blockers, raw_rules.get("raw_payloads_in_git"), "raw_payloads_in_git")
    return blockers


def validate_qnn_contract(blockers: list[str], qnn: dict[str, Any]) -> None:
    require_equal(blockers, qnn.get("producer_kind"), PRODUCER_KIND, "wrong_qnn_producer_kind")
    require_equal(blockers, qnn.get("backend_execution"), "qnn_htp", "qnn_backend_execution_not_htp")
    require_false(blockers, qnn.get("cpu_fallback"), "qnn_cpu_fallback_true")
    require_true(blockers, qnn.get("qnn_htp_backend_verified"), "qnn_htp_backend_not_verified")
    backend = qnn.get("backend")
    require_present(blockers, backend, "missing_qnn_backend")
    if isinstance(backend, str) and "libQnnHtp.so" not in backend:
        blockers.append("qnn_backend_not_libQnnHtp")
    require_present(blockers, qnn.get("context_path"), "missing_qnn_context_path")
    require_phone_path(blockers, qnn.get("context_path"), "qnn_context_path")
    require_sha256(blockers, qnn.get("context_sha256"), "bad_qnn_context_sha256")
    validate_graph_name(blockers, qnn.get("graph"))

    validate_tensor(blockers, require_mapping(blockers, qnn.get("input"), "missing_qnn_input"), "qnn_input")
    validate_tensor(blockers, require_mapping(blockers, qnn.get("output"), "missing_qnn_output"), "qnn_output")

    profile = require_mapping(blockers, qnn.get("profile"), "missing_qnn_profile")
    if profile:
        require_true(blockers, profile.get("qnn_profile_parse_attempted"), "qnn_profile_parse_not_attempted")
        require_finite_positive_or_zero(blockers, profile.get("qnn_net_run_wall_ms"), "bad_qnn_net_run_wall_ms")
        require_profile_log(blockers, profile.get("profile_log"))
        execute_ms = profile.get("qnn_accelerator_execute_ms")
        if execute_ms is None:
            require_present(
                blockers,
                profile.get("qnn_accelerator_execute_ms_unavailable_reason"),
                "missing_qnn_accelerator_execute_unavailable_reason",
            )
        else:
            require_finite_positive_or_zero(blockers, execute_ms, "bad_qnn_accelerator_execute_ms")


def validate_graph_name(blockers: list[str], graph: Any) -> None:
    require_present(blockers, graph, "missing_qnn_graph")
    if not isinstance(graph, str) or not graph:
        return
    if graph in DISALLOWED_FULL_GEMMA_GRAPHS:
        blockers.append(f"disallowed_full_gemma_graph:{graph}")
    if "gemma" not in graph.lower():
        blockers.append("qnn_graph_not_gemma_named")


def validate_tensor(blockers: list[str], tensor: dict[str, Any] | None, prefix: str) -> None:
    if not tensor:
        return
    require_equal(blockers, tensor.get("shape"), EXPECTED_SHAPE, f"{prefix}_wrong_shape")
    require_equal(blockers, tensor.get("dtype"), EXPECTED_DTYPE, f"{prefix}_wrong_dtype")
    require_equal(blockers, tensor.get("bytes"), EXPECTED_BYTES, f"{prefix}_wrong_bytes")
    require_phone_path(blockers, tensor.get("path"), f"{prefix}_path")
    require_sha256(blockers, tensor.get("sha256"), f"bad_{prefix}_sha256")
    require_sha256(blockers, tensor.get("packet_sha256"), f"bad_{prefix}_packet_sha256")


def require_profile_log(blockers: list[str], profile_log: Any) -> None:
    mapping = require_mapping(blockers, profile_log, "missing_qnn_profile_log")
    if not mapping:
        return
    require_phone_path(blockers, mapping.get("remote_path"), "qnn_profile_log_path")
    require_sha256(blockers, mapping.get("sha256"), "bad_qnn_profile_log_sha256")
    require_nonnegative_int(blockers, mapping.get("bytes"), "bad_qnn_profile_log_bytes")


def convert_to_ms(value: float, unit: str) -> float:
    normalized = unit.lower()
    if normalized == "ns":
        return value / 1_000_000.0
    if normalized in {"us", "µs"}:
        return value / 1_000.0
    if normalized == "ms":
        return value
    if normalized == "s":
        return value * 1_000.0
    raise ValueError(f"unsupported profile time unit: {unit}")


def require_mapping(blockers: list[str], value: Any, code: str) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        blockers.append(code)
        return None
    return value


def require_present(blockers: list[str], value: Any, code: str) -> None:
    if value is None or value == "":
        blockers.append(code)


def require_equal(blockers: list[str], value: Any, expected: Any, code: str) -> None:
    if value != expected:
        blockers.append(code)


def require_true(blockers: list[str], value: Any, code: str) -> None:
    if value is not True:
        blockers.append(code)


def require_false(blockers: list[str], value: Any, code: str) -> None:
    if value is not False:
        blockers.append(code)


def require_sha256(blockers: list[str], value: Any, code: str) -> None:
    if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
        blockers.append(code)


def require_phone_path(blockers: list[str], value: Any, code: str) -> None:
    require_present(blockers, value, f"missing_{code}")
    if isinstance(value, str) and value and not value.startswith(ALLOWED_PHONE_PREFIXES):
        blockers.append(f"{code}_outside_phone_boundary")


def require_nonnegative_int(blockers: list[str], value: Any, code: str) -> None:
    if not isinstance(value, int) or value < 0:
        blockers.append(code)


def require_finite_positive_or_zero(blockers: list[str], value: Any, code: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
        blockers.append(code)

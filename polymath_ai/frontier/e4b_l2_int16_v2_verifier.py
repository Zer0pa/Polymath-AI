"""Independent phone-local exact-dot verifier and sanitized provider receipt.

This module is intentionally separate from the oracle implementation.  It
recomputes every full-width INT32 dot on the phone, compares the resulting S16
bins byte-for-byte with the phone-private oracle outputs, and emits only a
sanitized hash/metric receipt.  Provider code consumes that receipt; it never
opens or transfers phone-private authority or candidate tensors.
"""

from __future__ import annotations

import math
from pathlib import Path
import platform
import struct
import sys
import time
from typing import Any

from .e4b_l2_int16_v2 import (
    ACCESS_RECEIPT_SHA256,
    FROZEN_CASES,
    FRONTIER_SELECTOR_SHA256,
    FULL_WIDTH_DOT_PRODUCTS_PER_CASE,
    INPUT_FEATURES,
    INPUT_SCALE,
    MAX_ORACLE_WALL_SECONDS,
    NUMERIC_THRESHOLD_SUBSET_SHA256,
    ORACLE_NUMPY_VERSION,
    ORACLE_PYTHON_VERSION,
    ORACLE_ROW_BLOCK_SIZE,
    OUTPUT_FEATURES,
    OUTPUT_SCALE,
    PACKED_WEIGHT_BYTES,
    PACKED_WEIGHT_SHA256,
    PARENT_CAPSULE_SHA256,
    REPOSITORY_ROOT,
    RESOURCE_SLICE,
    SHA256,
    SIGNED_WEIGHT_SHIFT,
    V2_CANDIDATE_ID,
    V2_ORACLE_SCHEMA,
    _hash_regular_file,
    _numeric_thresholds,
    _read_regular,
    _regular_file_identity,
    _strict_load_canonical,
    _validate_phone_runtime_paths,
    _verify_sidecar,
    enforce_phone_resource_envelope,
    execution_envelope,
    oracle_output_relative_path,
    sanitized_resource_snapshots,
    sanitized_runtime_binding,
    validate_resource_snapshots,
    validate_sanitized_oracle_case,
    validate_sanitized_run_id,
    validate_sanitized_runtime_binding,
    validate_int16_v2_preregistration,
    validate_int16_v2_preregistration_metadata,
    validate_passed_int16_v2_oracle_local,
)
from .e4b_l2_projection_gate import (
    TOP_K,
    ProjectionGateError,
    adjudicate_metrics,
    canonical_json,
    sha256_bytes,
    sha256_path,
    write_hashed_json,
)


VERIFICATION_SCHEMA = "gemma4_e4b_l2_int16_v2_phone_exact_dot_verification_v1"
VERIFICATION_ROW_BLOCK_SIZE = ORACLE_ROW_BLOCK_SIZE


def _unpack_rows_independent(packed_rows: Any) -> Any:
    import numpy as np

    if packed_rows.ndim != 2 or packed_rows.shape[1] != INPUT_FEATURES // 4:
        raise ProjectionGateError("independent verifier packed-row shape mismatch")
    rows = packed_rows.shape[0]
    unpacked = np.empty((rows, INPUT_FEATURES), dtype=np.int32)
    for byte_index in range(packed_rows.shape[1]):
        byte = packed_rows[:, byte_index].astype(np.uint8, copy=False)
        base = byte_index * 4
        unpacked[:, base] = (byte & 0x03).astype(np.int32) + SIGNED_WEIGHT_SHIFT
        unpacked[:, base + 1] = ((byte >> 2) & 0x03).astype(
            np.int32
        ) + SIGNED_WEIGHT_SHIFT
        unpacked[:, base + 2] = ((byte >> 4) & 0x03).astype(
            np.int32
        ) + SIGNED_WEIGHT_SHIFT
        unpacked[:, base + 3] = ((byte >> 6) & 0x03).astype(
            np.int32
        ) + SIGNED_WEIGHT_SHIFT
    return unpacked


def _verification_root(case_records: list[dict[str, Any]]) -> str:
    return sha256_bytes(canonical_json(case_records))


def _decode_bf16_independent(payload: bytes) -> list[float]:
    if len(payload) != OUTPUT_FEATURES * 2:
        raise ProjectionGateError("independent verifier authority width mismatch")
    return [
        struct.unpack("<f", struct.pack("<I", value << 16))[0]
        for (value,) in struct.iter_unpack("<H", payload)
    ]


def _top_k_independent(values: list[float]) -> list[int]:
    return sorted(range(len(values)), key=lambda index: (-values[index], index))[:TOP_K]


def _metrics_independent(
    reference: list[float], candidate: list[float]
) -> dict[str, Any]:
    if len(reference) != OUTPUT_FEATURES or len(candidate) != OUTPUT_FEATURES:
        raise ProjectionGateError("independent verifier metric width mismatch")
    if any(not math.isfinite(value) for value in reference + candidate):
        raise ProjectionGateError("independent verifier received non-finite output")
    errors = [right - left for left, right in zip(reference, candidate, strict=True)]
    squared_error = math.fsum(value * value for value in errors)
    squared_reference = math.fsum(value * value for value in reference)
    squared_candidate = math.fsum(value * value for value in candidate)
    dot = math.fsum(
        left * right for left, right in zip(reference, candidate, strict=True)
    )
    reference_top = _top_k_independent(reference)
    candidate_top = _top_k_independent(candidate)

    def probabilities(values: list[float]) -> list[float]:
        maximum = max(values)
        exponentials = [math.exp(value - maximum) for value in values]
        denominator = math.fsum(exponentials)
        return [value / denominator for value in exponentials]

    left_probabilities = probabilities(reference)
    right_probabilities = probabilities(candidate)
    js_terms = []
    for left, right in zip(left_probabilities, right_probabilities, strict=True):
        midpoint = 0.5 * (left + right)
        term = 0.0
        if left:
            term += 0.5 * left * math.log(left / midpoint)
        if right:
            term += 0.5 * right * math.log(right / midpoint)
        js_terms.append(term)
    return {
        "count": OUTPUT_FEATURES,
        "max_abs": max(abs(value) for value in errors),
        "rms": math.sqrt(squared_error / OUTPUT_FEATURES),
        "relative_l2": math.sqrt(squared_error / squared_reference)
        if squared_reference
        else math.inf,
        "cosine": (
            dot / math.sqrt(squared_reference * squared_candidate)
            if squared_reference and squared_candidate
            else 0.0
        ),
        "top_k": TOP_K,
        "top_k_set_overlap": len(set(reference_top) & set(candidate_top)) / TOP_K,
        "top_1_equal": reference_top[0] == candidate_top[0],
        "reference_top_k": reference_top,
        "candidate_top_k": candidate_top,
        "softmax_js_divergence": math.fsum(js_terms),
    }


def verify_int16_v2_phone_oracle(
    *,
    prereg_dir: Path,
    oracle_gate_path: Path,
    packed_weight_path: Path,
    authority_root: Path,
    phone_runtime_root: Path,
    output_path: Path,
    run_id: str,
) -> dict[str, Any]:
    """Rerun all exact dots phone-locally and publish a sanitized receipt."""

    import numpy as np

    if (
        output_path.exists()
        or output_path.with_suffix(output_path.suffix + ".sha256").exists()
    ):
        raise ProjectionGateError(f"verification output already exists: {output_path}")
    validate_sanitized_run_id(run_id)
    if platform.python_version() != ORACLE_PYTHON_VERSION:
        raise ProjectionGateError(
            f"independent verifier Python drift: {platform.python_version()}"
        )
    if np.__version__ != ORACLE_NUMPY_VERSION:
        raise ProjectionGateError(f"independent verifier NumPy drift: {np.__version__}")
    runtime_binding = _validate_phone_runtime_paths(
        phone_runtime_root=phone_runtime_root,
        existing_inputs=(
            prereg_dir,
            oracle_gate_path,
            packed_weight_path,
            authority_root,
            REPOSITORY_ROOT,
        ),
        output_path=output_path,
    )
    prereg, prereg_sha256 = validate_int16_v2_preregistration(prereg_dir)
    _, _, gate, gate_sha256 = validate_passed_int16_v2_oracle_local(
        prereg_dir=prereg_dir,
        oracle_gate_path=oracle_gate_path,
        authority_root=authority_root,
    )
    for gate_case, frozen in zip(gate["case_records"], FROZEN_CASES, strict=True):
        validate_sanitized_oracle_case(gate_case, frozen)
    packed_identity, packed_sha256 = _hash_regular_file(packed_weight_path)
    if (
        packed_identity[2] != PACKED_WEIGHT_BYTES
        or packed_sha256 != PACKED_WEIGHT_SHA256
    ):
        raise ProjectionGateError("independent verifier packed INT2 identity mismatch")

    inputs = []
    expected_outputs = []
    input_artifacts: list[tuple[Path, tuple[int, int, int, int, int]]] = []
    authority_artifacts: list[tuple[Path, tuple[int, int, int, int, int]]] = []
    output_artifacts: list[tuple[Path, tuple[int, int, int, int, int]]] = []
    authority_payloads: list[bytes] = []
    for case in prereg["cases"]:
        input_path = prereg_dir / case["s16_input_relative_path"]
        input_identity, input_sha256 = _hash_regular_file(input_path)
        if (
            input_identity[2] != case["s16_input_bytes"]
            or input_sha256 != case["s16_input_sha256"]
        ):
            raise ProjectionGateError("independent verifier input identity mismatch")
        input_payload = _read_regular(input_path)
        values = np.frombuffer(input_payload, dtype="<i2").astype(np.int32)
        if values.size != INPUT_FEATURES:
            raise ProjectionGateError("independent verifier input width mismatch")
        inputs.append(values)
        input_artifacts.append((input_path, input_identity))
        output_path_for_case = oracle_gate_path.parent / oracle_output_relative_path(
            case["case_id"]
        )
        output_identity, output_sha256 = _hash_regular_file(output_path_for_case)
        gate_case = next(
            record
            for record in gate["case_records"]
            if record["case_id"] == case["case_id"]
        )
        if gate_case["candidate_output"][
            "relative_path"
        ] != oracle_output_relative_path(case["case_id"]):
            raise ProjectionGateError(
                "independent verifier candidate output locator mismatch"
            )
        if (
            output_identity[2] != OUTPUT_FEATURES * 2
            or output_sha256 != gate_case["candidate_output"]["sha256"]
        ):
            raise ProjectionGateError(
                "independent verifier candidate output identity mismatch"
            )
        expected_outputs.append(
            np.memmap(
                output_path_for_case, dtype="<i2", mode="r", shape=(OUTPUT_FEATURES,)
            )
        )
        output_artifacts.append((output_path_for_case, output_identity))
        authority = case["authority_output"]
        authority_path = authority_root / authority["provider_relative_path"]
        authority_identity, authority_sha256 = _hash_regular_file(authority_path)
        if (
            authority_identity[2] != authority["bytes"]
            or authority_sha256 != authority["sha256"]
        ):
            raise ProjectionGateError(
                "independent verifier authority identity mismatch"
            )
        authority_payloads.append(_read_regular(authority_path))
        authority_artifacts.append((authority_path, authority_identity))
    input_matrix = np.stack(inputs, axis=0).astype(np.int32, copy=False)
    scale_contract = prereg["candidate_contract"]
    scale_path = prereg_dir / scale_contract["transformed_scale_relative_path"]
    scale_identity, scale_sha256 = _hash_regular_file(scale_path)
    if (
        scale_identity[2] != scale_contract["transformed_scale_bytes"]
        or scale_sha256 != scale_contract["transformed_scale_sha256"]
    ):
        raise ProjectionGateError("independent verifier scale identity mismatch")
    scales = np.frombuffer(_read_regular(scale_path), dtype="<f4")
    if (
        scales.size != OUTPUT_FEATURES
        or not np.all(np.isfinite(scales))
        or not np.all(scales > 0)
        or np.any(scales.view(np.uint32) & np.uint32(0xFFFF))
    ):
        raise ProjectionGateError("independent verifier scale width mismatch")
    packed = np.memmap(
        packed_weight_path,
        dtype=np.uint8,
        mode="r",
        shape=(OUTPUT_FEATURES, INPUT_FEATURES // 4),
    )
    started = time.monotonic()
    resource_snapshots = [
        enforce_phone_resource_envelope(
            output_root=output_path.parent,
            started=started,
            checkpoint="independent_before_first_row_block",
        )
    ]
    for start in range(0, OUTPUT_FEATURES, VERIFICATION_ROW_BLOCK_SIZE):
        end = min(start + VERIFICATION_ROW_BLOCK_SIZE, OUTPUT_FEATURES)
        weights = _unpack_rows_independent(np.asarray(packed[start:end]))
        dots = input_matrix @ weights.T
        if dots.dtype != np.int32:
            raise ProjectionGateError(
                "independent verifier did not accumulate in INT32"
            )
        quantized = np.clip(
            np.rint(
                dots.astype(np.float64)
                * (INPUT_SCALE / OUTPUT_SCALE)
                * scales[start:end]
            ),
            np.iinfo(np.int16).min,
            np.iinfo(np.int16).max,
        ).astype(np.int16)
        for case_index, expected in enumerate(expected_outputs):
            if not np.array_equal(
                quantized[case_index], np.asarray(expected[start:end])
            ):
                raise ProjectionGateError(
                    f"independent exact-dot mismatch: {prereg['cases'][case_index]['case_id']} rows {start}:{end}"
                )
        if end < OUTPUT_FEATURES:
            resource_snapshots.append(
                enforce_phone_resource_envelope(
                    output_root=output_path.parent,
                    started=started,
                    checkpoint=f"independent_after_rows_{start}_{end}",
                )
            )
    del packed
    case_records = []
    limits = _numeric_thresholds()
    for gate_case, frozen, authority_payload, expected in zip(
        gate["case_records"],
        FROZEN_CASES,
        authority_payloads,
        expected_outputs,
        strict=True,
    ):
        candidate = (np.asarray(expected).astype(np.float64) * OUTPUT_SCALE).tolist()
        metrics = _metrics_independent(
            _decode_bf16_independent(authority_payload), candidate
        )
        if metrics != gate_case["metrics"]:
            raise ProjectionGateError(
                "independent verifier metric recomputation mismatch"
            )
        passed, failures = adjudicate_metrics(metrics, limits)
        if not passed or failures:
            raise ProjectionGateError("independent verifier metric adjudication failed")
        case_records.append(
            {
                "case_id": frozen["case_id"],
                "input_sha256": frozen["s16_input_sha256"],
                "authority_output_sha256": frozen["authority_output"]["sha256"],
                "candidate_output_sha256": gate_case["candidate_output"]["sha256"],
                "metrics_sha256": sha256_bytes(canonical_json(metrics)),
                "exact_int32_dot_output_match": True,
                "unchanged_metrics_recomputed_from_phone_local_raw": True,
                "passed": True,
            }
        )
    del expected_outputs
    for artifact_path, identity in (
        (packed_weight_path, packed_identity),
        (scale_path, scale_identity),
        *input_artifacts,
        *authority_artifacts,
        *output_artifacts,
    ):
        if _regular_file_identity(artifact_path) != identity:
            raise ProjectionGateError(
                f"phone-local independent-verification artifact identity changed: {artifact_path.name}"
            )
    receipt = {
        "schema_version": VERIFICATION_SCHEMA,
        "status": "passed_scope",
        "scope": "independent_phone_native_full_width_exact_INT32_dot_and_metric_recomputation",
        "run_id": run_id,
        "candidate_id": V2_CANDIDATE_ID,
        "source_revision": prereg["source_revision"],
        "candidate_module_sha256": prereg["implementation_module_sha256"],
        "verifier_module_sha256": sha256_path(Path(__file__)),
        "parent_capsule_sha256": PARENT_CAPSULE_SHA256,
        "access_receipt_sha256": ACCESS_RECEIPT_SHA256,
        "frontier_selector_sha256": FRONTIER_SELECTOR_SHA256,
        "resource_slice": RESOURCE_SLICE,
        "phone_execution_envelope": execution_envelope(),
        "preregistration_sha256": prereg_sha256,
        "oracle_gate_sha256": gate_sha256,
        "packed_weight_sha256": PACKED_WEIGHT_SHA256,
        "transformed_scale_sha256": prereg["candidate_contract"][
            "transformed_scale_sha256"
        ],
        "numeric_and_ranking_threshold_subset_sha256": NUMERIC_THRESHOLD_SUBSET_SHA256,
        "case_records": case_records,
        "verification_evidence_root_sha256": _verification_root(case_records),
        "phone_native_exact_oracle_execution_count": 1,
        "phone_native_independent_verification_count": 1,
        "phone_qnn_execution_count": 0,
        "every_case_passed": True,
        "provider_build_allowed": True,
        "python_version": ORACLE_PYTHON_VERSION,
        "python_executable_sha256": sha256_path(Path(sys.executable)),
        "numpy_version": ORACLE_NUMPY_VERSION,
        "wall_time_seconds": time.monotonic() - started,
        "runtime_binding": sanitized_runtime_binding(runtime_binding),
        "resource_snapshots": sanitized_resource_snapshots(resource_snapshots),
        "custody": {
            "raw_authority_and_candidate_outputs": "phone_private_not_in_receipt",
            "raw_artifact_egress_count": 0,
            "raw_phone_private_upload": False,
            "sanitized_hash_metric_receipt_only": True,
        },
    }
    receipt_sha256 = write_hashed_json(output_path, receipt)
    return {
        "status": "passed_scope",
        "verification_receipt_sha256": receipt_sha256,
        "verification_evidence_root_sha256": receipt[
            "verification_evidence_root_sha256"
        ],
        "provider_build_allowed": True,
    }


def validate_sanitized_phone_authorization(
    *,
    prereg_metadata_dir: Path,
    oracle_gate_path: Path,
    verification_receipt_path: Path,
) -> tuple[dict[str, Any], str, dict[str, Any], str, dict[str, Any], str]:
    """Validate sanitized phone evidence without opening any raw tensor."""

    prereg, prereg_sha256 = validate_int16_v2_preregistration_metadata(
        prereg_metadata_dir
    )
    gate = _strict_load_canonical(oracle_gate_path)
    gate_sha256 = sha256_path(oracle_gate_path)
    _verify_sidecar(oracle_gate_path, gate_sha256)
    receipt = _strict_load_canonical(verification_receipt_path)
    receipt_sha256 = sha256_path(verification_receipt_path)
    _verify_sidecar(verification_receipt_path, receipt_sha256)
    exact_gate_keys = {
        "schema_version",
        "status",
        "scope",
        "run_id",
        "candidate_id",
        "frontier_selector_sha256",
        "parent_capsule_sha256",
        "access_receipt_sha256",
        "resource_slice",
        "phone_execution_envelope",
        "source_revision",
        "implementation_module_sha256",
        "preregistration_sha256",
        "threshold_policy_sha256",
        "numeric_and_ranking_threshold_subset_sha256",
        "packed_weight_sha256",
        "transformed_scale_sha256",
        "scale_transform",
        "input_scale",
        "output_scale",
        "oracle_execution_count",
        "full_width_dot_products_total",
        "case_records",
        "every_case_passed",
        "provider_build_allowed",
        "qnn_execution_count",
        "phone_qnn_execution_count",
        "phone_native_exact_oracle_execution_count",
        "wall_time_seconds",
        "python_version",
        "python_executable_sha256",
        "numpy_version",
        "runtime_binding",
        "resource_snapshots",
        "custody",
        "failure_rule",
        "claim_boundary",
    }
    if set(gate) != exact_gate_keys:
        raise ProjectionGateError("sanitized phone oracle gate structure mismatch")
    gate_required = {
        "schema_version": V2_ORACLE_SCHEMA,
        "status": "passed_scope",
        "scope": "full_width_exact_INT32_dot_pre_provider_falsifier",
        "candidate_id": V2_CANDIDATE_ID,
        "source_revision": prereg["source_revision"],
        "implementation_module_sha256": prereg["implementation_module_sha256"],
        "preregistration_sha256": prereg_sha256,
        "threshold_policy_sha256": prereg["threshold_policy_sha256"],
        "parent_capsule_sha256": PARENT_CAPSULE_SHA256,
        "access_receipt_sha256": ACCESS_RECEIPT_SHA256,
        "frontier_selector_sha256": FRONTIER_SELECTOR_SHA256,
        "resource_slice": RESOURCE_SLICE,
        "phone_execution_envelope": execution_envelope(),
        "numeric_and_ranking_threshold_subset_sha256": NUMERIC_THRESHOLD_SUBSET_SHA256,
        "packed_weight_sha256": PACKED_WEIGHT_SHA256,
        "transformed_scale_sha256": prereg["candidate_contract"][
            "transformed_scale_sha256"
        ],
        "scale_transform": "float32_to_bfloat16_RNE_then_exact_float32_storage",
        "input_scale": INPUT_SCALE,
        "output_scale": OUTPUT_SCALE,
        "oracle_execution_count": 3,
        "full_width_dot_products_total": FULL_WIDTH_DOT_PRODUCTS_PER_CASE * 3,
        "qnn_execution_count": 0,
        "phone_native_exact_oracle_execution_count": 1,
        "phone_qnn_execution_count": 0,
        "every_case_passed": True,
        "provider_build_allowed": True,
        "python_version": ORACLE_PYTHON_VERSION,
        "numpy_version": ORACLE_NUMPY_VERSION,
    }
    for name, expected in gate_required.items():
        if gate.get(name) != expected:
            raise ProjectionGateError(f"sanitized phone oracle gate mismatch: {name}")
    validate_sanitized_run_id(gate.get("run_id"))
    validate_sanitized_runtime_binding(gate.get("runtime_binding"))
    wall_time = gate.get("wall_time_seconds")
    if (
        not isinstance(wall_time, (int, float))
        or isinstance(wall_time, bool)
        or not math.isfinite(float(wall_time))
        or not 0 <= float(wall_time) < MAX_ORACLE_WALL_SECONDS
    ):
        raise ProjectionGateError("sanitized phone oracle wall time is invalid")
    if not SHA256.fullmatch(str(gate.get("python_executable_sha256", ""))):
        raise ProjectionGateError("sanitized phone oracle Python digest is invalid")
    expected_gate_custody = {
        "raw_candidate_outputs": "phone_private",
        "raw_authority_outputs": "phone_private",
        "raw_output_egress": False,
        "sanitized_gate_egress_allowed": True,
        "qnn_phone_execution_is_distinct": True,
    }
    if gate.get("custody") != expected_gate_custody:
        raise ProjectionGateError("sanitized phone oracle custody mismatch")
    if (
        gate.get("failure_rule")
        != ("provider_build_forbidden_unless_status_passed_scope_and_every_case_passed")
        or gate.get("claim_boundary")
        != "exact_quantized_oracle_only_no_provider_or_phone_execution"
    ):
        raise ProjectionGateError(
            "sanitized phone oracle claim/failure boundary mismatch"
        )
    exact_receipt_keys = {
        "schema_version",
        "status",
        "scope",
        "run_id",
        "candidate_id",
        "source_revision",
        "candidate_module_sha256",
        "verifier_module_sha256",
        "parent_capsule_sha256",
        "access_receipt_sha256",
        "frontier_selector_sha256",
        "resource_slice",
        "phone_execution_envelope",
        "preregistration_sha256",
        "oracle_gate_sha256",
        "packed_weight_sha256",
        "transformed_scale_sha256",
        "numeric_and_ranking_threshold_subset_sha256",
        "case_records",
        "verification_evidence_root_sha256",
        "phone_native_exact_oracle_execution_count",
        "phone_native_independent_verification_count",
        "phone_qnn_execution_count",
        "every_case_passed",
        "provider_build_allowed",
        "python_version",
        "python_executable_sha256",
        "numpy_version",
        "wall_time_seconds",
        "runtime_binding",
        "resource_snapshots",
        "custody",
    }
    if set(receipt) != exact_receipt_keys:
        raise ProjectionGateError(
            "sanitized phone verification receipt structure mismatch"
        )
    receipt_required = {
        "schema_version": VERIFICATION_SCHEMA,
        "status": "passed_scope",
        "scope": "independent_phone_native_full_width_exact_INT32_dot_and_metric_recomputation",
        "candidate_id": V2_CANDIDATE_ID,
        "source_revision": prereg["source_revision"],
        "candidate_module_sha256": prereg["implementation_module_sha256"],
        "verifier_module_sha256": sha256_path(Path(__file__)),
        "parent_capsule_sha256": PARENT_CAPSULE_SHA256,
        "access_receipt_sha256": ACCESS_RECEIPT_SHA256,
        "frontier_selector_sha256": FRONTIER_SELECTOR_SHA256,
        "resource_slice": RESOURCE_SLICE,
        "phone_execution_envelope": execution_envelope(),
        "preregistration_sha256": prereg_sha256,
        "oracle_gate_sha256": gate_sha256,
        "packed_weight_sha256": PACKED_WEIGHT_SHA256,
        "transformed_scale_sha256": prereg["candidate_contract"][
            "transformed_scale_sha256"
        ],
        "numeric_and_ranking_threshold_subset_sha256": NUMERIC_THRESHOLD_SUBSET_SHA256,
        "phone_native_exact_oracle_execution_count": 1,
        "phone_native_independent_verification_count": 1,
        "phone_qnn_execution_count": 0,
        "every_case_passed": True,
        "provider_build_allowed": True,
        "python_version": ORACLE_PYTHON_VERSION,
        "numpy_version": ORACLE_NUMPY_VERSION,
    }
    for name, expected in receipt_required.items():
        if receipt.get(name) != expected:
            raise ProjectionGateError(
                f"sanitized phone verification receipt mismatch: {name}"
            )
    validate_sanitized_run_id(receipt.get("run_id"))
    validate_sanitized_runtime_binding(receipt.get("runtime_binding"))
    receipt_wall_time = receipt.get("wall_time_seconds")
    if (
        not isinstance(receipt_wall_time, (int, float))
        or isinstance(receipt_wall_time, bool)
        or not math.isfinite(float(receipt_wall_time))
        or not 0 <= float(receipt_wall_time) < MAX_ORACLE_WALL_SECONDS
    ):
        raise ProjectionGateError("sanitized phone verification wall time is invalid")
    if not SHA256.fullmatch(str(receipt.get("python_executable_sha256", ""))):
        raise ProjectionGateError(
            "sanitized phone verification Python digest is invalid"
        )
    validate_resource_snapshots(gate.get("resource_snapshots"))
    validate_resource_snapshots(receipt.get("resource_snapshots"), independent=True)
    expected_cases = []
    gate_cases = gate.get("case_records")
    receipt_cases = receipt.get("case_records")
    if not isinstance(gate_cases, list) or len(gate_cases) != 3:
        raise ProjectionGateError("sanitized phone oracle case set mismatch")
    for gate_case, frozen in zip(gate_cases, FROZEN_CASES, strict=True):
        validate_sanitized_oracle_case(gate_case, frozen)
        expected_cases.append(
            {
                "case_id": frozen["case_id"],
                "input_sha256": frozen["s16_input_sha256"],
                "authority_output_sha256": frozen["authority_output"]["sha256"],
                "candidate_output_sha256": gate_case["candidate_output"]["sha256"],
                "metrics_sha256": sha256_bytes(canonical_json(gate_case["metrics"])),
                "exact_int32_dot_output_match": True,
                "unchanged_metrics_recomputed_from_phone_local_raw": True,
                "passed": True,
            }
        )
    if receipt_cases != expected_cases or receipt.get(
        "verification_evidence_root_sha256"
    ) != _verification_root(expected_cases):
        raise ProjectionGateError("sanitized phone verification evidence root mismatch")
    expected_receipt_custody = {
        "raw_authority_and_candidate_outputs": "phone_private_not_in_receipt",
        "raw_artifact_egress_count": 0,
        "raw_phone_private_upload": False,
        "sanitized_hash_metric_receipt_only": True,
    }
    if receipt.get("custody") != expected_receipt_custody:
        raise ProjectionGateError(
            "sanitized phone verification receipt violates custody"
        )
    return prereg, prereg_sha256, gate, gate_sha256, receipt, receipt_sha256

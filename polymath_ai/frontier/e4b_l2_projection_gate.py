"""Frozen numerical gate for the full-width E4B W4 and W2 projections.

This module deliberately separates preregistration from observation.  The
first phase writes deterministic full-dimensional inputs and the numerical
policy without reading model outputs.  A provider-side framework oracle may
then consume that immutable bundle.  Passing this gate can admit the two
projection graphs to a phone execution attempt; it cannot pass L1 or L2 for
the decoder.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct
from typing import Any, Iterable, Sequence

from .e4b_f5_probe import (
    LM_HEAD,
    QAT_MODEL_SHA256,
    QAT_REPOSITORY,
    QAT_REVISION,
    Q_PROJ,
    TRANSFORMERS_COMMIT,
)
from .e4b_f5_qnn_exporter import LM_HEAD_GRAPH, Q_PROJ_GRAPH


SCHEMA_VERSION = "gemma4_e4b_l2_projection_preregistration_v1"
POLICY_SCHEMA_VERSION = "gemma4_e4b_l2_projection_threshold_policy_v1"
REFERENCE_GATE_SCHEMA_VERSION = "gemma4_e4b_f5_reference_gate_v1"
FIXTURE_CLASS = "synthetic_mechanical"
INPUT_FORMAT_VERSION = "little_endian_raw_tensor_v1"
TOP_K = 32


class ProjectionGateError(ValueError):
    """Raised when the projection gate cannot preserve its frozen contract."""


@dataclass(frozen=True)
class InputCase:
    graph_name: str
    case_id: str
    dtype: str
    shape: tuple[int, ...]
    payload: bytes

    @property
    def filename(self) -> str:
        suffix = "s8" if self.dtype == "int8" else "bf16"
        return f"{self.graph_name}.{self.case_id}.{suffix}.raw"


def canonical_json(value: object) -> bytes:
    """Return the only JSON encoding admitted by this gate."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _write_exclusive(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, mode)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError(f"short write to {path}")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_hashed_json(path: Path, value: object) -> str:
    encoded = canonical_json(value)
    _write_exclusive(path, encoded)
    digest = sha256_bytes(encoded)
    _write_exclusive(
        path.with_suffix(path.suffix + ".sha256"),
        f"{digest}  {path.name}\n".encode("ascii"),
    )
    return digest


def _splitmix64(state: int) -> int:
    value = (state + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    return value ^ (value >> 31)


def _float_to_bf16_bits(value: float) -> int:
    bits = struct.unpack("<I", struct.pack("<f", value))[0]
    exponent = bits & 0x7F800000
    if exponent == 0x7F800000:
        raise ProjectionGateError("non-finite BF16 fixture value is forbidden")
    rounded = bits + 0x7FFF + ((bits >> 16) & 1)
    return (rounded >> 16) & 0xFFFF


def bf16_bits_to_float(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", (bits & 0xFFFF) << 16))[0]


def bf16_payload_to_floats(payload: bytes) -> list[float]:
    if len(payload) % 2:
        raise ProjectionGateError("BF16 payload has an odd byte count")
    return [
        bf16_bits_to_float(bits)
        for (bits,) in struct.iter_unpack("<H", payload)
    ]


def bf16_payload_to_fp16(payload: bytes) -> bytes:
    result = bytearray()
    for value in bf16_payload_to_floats(payload):
        try:
            result.extend(struct.pack("<e", value))
        except OverflowError as exc:
            raise ProjectionGateError("BF16 fixture is not representable in FP16") from exc
    roundtrip = [
        _float_to_bf16_bits(value)
        for (value,) in struct.iter_unpack("<e", bytes(result))
    ]
    original = [bits for (bits,) in struct.iter_unpack("<H", payload)]
    if roundtrip != original:
        raise ProjectionGateError("BF16-to-FP16 fixture cast is not bit-exact")
    return bytes(result)


def _pack_bf16(values: Iterable[float]) -> bytes:
    result = bytearray()
    for value in values:
        result.extend(struct.pack("<H", _float_to_bf16_bits(float(value))))
    return bytes(result)


def _w4_cases() -> tuple[InputCase, ...]:
    width = Q_PROJ.input_features
    signed_ramp = bytes((index & 0xFF) for index in range(width))
    boundary = (-128, 127, -1, 0, 1, -64, 64, -127, 126, -2, 2)
    boundary_payload = bytes(boundary[index % len(boundary)] & 0xFF for index in range(width))
    state = 0xE4B04A17D19C2F31
    hashed = bytearray()
    for index in range(width):
        state = _splitmix64(state ^ index)
        hashed.append((state >> 56) & 0xFF)
    return (
        InputCase(Q_PROJ_GRAPH, "signed_ramp", "int8", (1, 1, width), signed_ramp),
        InputCase(Q_PROJ_GRAPH, "boundary_alternating", "int8", (1, 1, width), boundary_payload),
        InputCase(Q_PROJ_GRAPH, "splitmix64", "int8", (1, 1, width), bytes(hashed)),
    )


def _w2_cases() -> tuple[InputCase, ...]:
    width = LM_HEAD.input_features
    structured_values = (
        -8.0,
        -4.0,
        -2.0,
        -1.0,
        -0.5,
        -0.125,
        -0.015625,
        0.0,
        0.015625,
        0.125,
        0.5,
        1.0,
        2.0,
        4.0,
        8.0,
    )
    structured = _pack_bf16(structured_values[index % len(structured_values)] for index in range(width))

    def hashed_payload(seed: int, denominator: int, span: int) -> bytes:
        state = seed
        values = []
        for index in range(width):
            state = _splitmix64(state ^ index)
            numerator = int(state % (2 * span + 1)) - span
            values.append(numerator / denominator)
        return _pack_bf16(values)

    return (
        InputCase(LM_HEAD_GRAPH, "structured_dynamic", "bfloat16", (1, 1, width), structured),
        InputCase(
            LM_HEAD_GRAPH,
            "balanced_splitmix64",
            "bfloat16",
            (1, 1, width),
            hashed_payload(0xE4B02A17B16F51D3, 128, 1024),
        ),
        InputCase(
            LM_HEAD_GRAPH,
            "low_amplitude_splitmix64",
            "bfloat16",
            (1, 1, width),
            hashed_payload(0xE4B02A17C001D00D, 512, 256),
        ),
    )


def input_cases() -> tuple[InputCase, ...]:
    return _w4_cases() + _w2_cases()


def threshold_policy() -> dict[str, Any]:
    """Return the frozen-before-observation numerical policy.

    Absolute limits are expressed in pre-softcap logit units.  Relative L2,
    cosine, Jensen-Shannon divergence and top-k constraints prevent an
    apparently small aggregate error from hiding decision-changing drift.
    """

    return {
        "schema_version": POLICY_SCHEMA_VERSION,
        "state": "frozen_before_observation",
        "authority_order": "quality_and_numerical_fidelity_before_performance",
        "fixture_class": FIXTURE_CLASS,
        "top_k": TOP_K,
        "adjudication": "every_metric_and_every_case_must_pass",
        "edges": {
            "w4_qat_to_qnn": {
                "reference_dtype": "int8_exact_output_bin",
                "candidate_dtype": "int8_native_qnn",
                "max_abs_integer": 1.0,
                "rms_integer": 0.25,
                "cosine_min": 0.99999,
                "nonzero_reference_required": True,
            },
            "w2_bf16_to_fp16_framework": {
                "reference_dtype": "bfloat16_qat",
                "candidate_dtype": "float16_qat_same_packed_weights",
                "input_cast_max_abs": 0.0,
                "max_abs": 0.125,
                "rms": 0.02,
                "relative_l2": 0.005,
                "cosine_min": 0.99999,
                "softmax_js_divergence_max": 1.0e-6,
                "top_k_set_overlap_min": 0.96875,
                "top_1_equal": True,
            },
            "w2_fp16_framework_to_qnn": {
                "reference_dtype": "float16_qat_same_packed_weights",
                "candidate_dtype": "float16_native_qnn",
                "max_abs": 0.0625,
                "rms": 0.01,
                "relative_l2": 0.0025,
                "cosine_min": 0.999995,
                "softmax_js_divergence_max": 5.0e-7,
                "top_k_set_overlap_min": 0.96875,
                "top_1_equal": True,
            },
            "w2_bf16_qat_to_qnn_combined": {
                "reference_dtype": "bfloat16_qat",
                "candidate_dtype": "float16_native_qnn",
                "max_abs": 0.1875,
                "rms": 0.03,
                "relative_l2": 0.0075,
                "cosine_min": 0.99998,
                "softmax_js_divergence_max": 2.0e-6,
                "top_k_set_overlap_min": 0.9375,
                "top_1_equal": True,
            },
        },
        "failure_rule": "kill_or_rebuild_projection_candidate_without_relaxing_observed_thresholds",
        "nonclaims": [
            "not_L1_phone_graph_feasibility",
            "not_full_L2_decoder_fidelity",
            "not_target_corpus_readiness",
            "not_learning_or_authority_quality",
        ],
    }


def _case_record(case: InputCase) -> dict[str, Any]:
    return {
        "graph_name": case.graph_name,
        "case_id": case.case_id,
        "dtype": case.dtype,
        "shape": list(case.shape),
        "format": INPUT_FORMAT_VERSION,
        "relative_path": f"inputs/{case.filename}",
        "bytes": len(case.payload),
        "sha256": sha256_bytes(case.payload),
    }


def build_preregistration(output_dir: Path, *, created_at_utc: str) -> dict[str, Any]:
    """Create a no-replace preregistration directory without model outputs."""

    if output_dir.exists():
        raise ProjectionGateError(f"output already exists: {output_dir}")
    output_dir.mkdir(mode=0o700, parents=True)
    inputs_dir = output_dir / "inputs"
    inputs_dir.mkdir(mode=0o700)

    policy = threshold_policy()
    policy_sha256 = write_hashed_json(output_dir / "threshold_policy.json", policy)
    cases = input_cases()
    for case in cases:
        _write_exclusive(inputs_dir / case.filename, case.payload)
        if case.dtype == "bfloat16":
            fp16_payload = bf16_payload_to_fp16(case.payload)
            _write_exclusive(
                inputs_dir / case.filename.replace(".bf16.raw", ".f16.raw"),
                fp16_payload,
            )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "state": "frozen_unobserved",
        "created_at_utc": created_at_utc,
        "fixture_class": FIXTURE_CLASS,
        "input_format": INPUT_FORMAT_VERSION,
        "model": {
            "repository": QAT_REPOSITORY,
            "revision": QAT_REVISION,
            "sha256": QAT_MODEL_SHA256,
        },
        "framework": {
            "transformers_commit": TRANSFORMERS_COMMIT,
            "required_module": "transformers.integrations.gemma_quant.QuantizedLinear",
        },
        "threshold_policy_sha256": policy_sha256,
        "graphs": {
            Q_PROJ_GRAPH: {
                "weight_tensor": Q_PROJ.weight.name,
                "weight_sha256": Q_PROJ.weight.data_sha256,
                "weight_bits": Q_PROJ.num_bits,
                "input_features": Q_PROJ.input_features,
                "output_features": Q_PROJ.output_features,
                "qnn_input_dtype": "QNN_DATATYPE_SFIXED_POINT_8",
                "qnn_output_dtype": "QNN_DATATYPE_SFIXED_POINT_8",
            },
            LM_HEAD_GRAPH: {
                "weight_tensor": LM_HEAD.weight.name,
                "weight_sha256": LM_HEAD.weight.data_sha256,
                "weight_bits": LM_HEAD.num_bits,
                "input_features": LM_HEAD.input_features,
                "output_features": LM_HEAD.output_features,
                "qnn_input_dtype": "QNN_DATATYPE_FLOAT_16",
                "qnn_output_dtype": "QNN_DATATYPE_FLOAT_16",
                "surface": "full_pre_softcap_logits",
            },
        },
        "cases": [_case_record(case) for case in cases],
        "required_observations": [
            "deterministic_qat_bfloat16_replay",
            "deterministic_same_weight_fp16_replay",
            "w2_bfloat16_to_fp16_framework_adjudication",
            "phone_qnn_output_adjudication_before_projection_admission",
        ],
        "output_files_present": False,
        "claim_boundary": "full_width_projection_reference_preregistration_only",
        "nonclaims": policy["nonclaims"],
    }
    prereg_sha256 = write_hashed_json(output_dir / "preregistration.json", manifest)
    return {
        "preregistration_sha256": prereg_sha256,
        "threshold_policy_sha256": policy_sha256,
        "case_count": len(cases),
    }


def validate_preregistration(root: Path) -> dict[str, Any]:
    manifest_path = root / "preregistration.json"
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    if canonical_json(manifest) != raw:
        raise ProjectionGateError("preregistration is not canonical JSON")
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("state") != "frozen_unobserved":
        raise ProjectionGateError("preregistration schema or state mismatch")
    policy_raw = (root / "threshold_policy.json").read_bytes()
    policy = json.loads(policy_raw)
    if canonical_json(policy) != policy_raw or policy != threshold_policy():
        raise ProjectionGateError("threshold policy bytes do not match source policy")
    policy_digest = sha256_bytes(policy_raw)
    if manifest.get("threshold_policy_sha256") != policy_digest:
        raise ProjectionGateError("threshold policy digest mismatch")
    expected_cases = {(case.graph_name, case.case_id): case for case in input_cases()}
    observed_records = manifest.get("cases")
    if not isinstance(observed_records, list) or len(observed_records) != len(expected_cases):
        raise ProjectionGateError("preregistration case set mismatch")
    for record in observed_records:
        if not isinstance(record, dict):
            raise ProjectionGateError("invalid preregistration case record")
        key = (record.get("graph_name"), record.get("case_id"))
        case = expected_cases.pop(key, None)
        if case is None or record != _case_record(case):
            raise ProjectionGateError(f"input case contract mismatch: {key}")
        path = root / str(record["relative_path"])
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ProjectionGateError(f"input is not a regular file: {path}")
        if path.read_bytes() != case.payload:
            raise ProjectionGateError(f"input payload drift: {path}")
        if case.dtype == "bfloat16":
            fp16 = path.with_name(path.name.replace(".bf16.raw", ".f16.raw"))
            if fp16.read_bytes() != bf16_payload_to_fp16(case.payload):
                raise ProjectionGateError(f"derived FP16 input drift: {fp16}")
    if expected_cases:
        raise ProjectionGateError("preregistration omitted input cases")
    return manifest


def _top_k_indices(values: Sequence[float], k: int) -> list[int]:
    if k <= 0 or k > len(values):
        raise ProjectionGateError("invalid top-k")
    return sorted(range(len(values)), key=lambda index: (-values[index], index))[:k]


def vector_metrics(reference: Sequence[float], candidate: Sequence[float], *, top_k: int = TOP_K) -> dict[str, Any]:
    """Compute deterministic full-vector projection metrics in FP64."""

    if len(reference) != len(candidate) or not reference:
        raise ProjectionGateError("metric vectors must have equal nonzero length")
    if any(not math.isfinite(value) for value in reference) or any(
        not math.isfinite(value) for value in candidate
    ):
        raise ProjectionGateError("non-finite projection output")
    errors = [right - left for left, right in zip(reference, candidate, strict=True)]
    max_abs = max(abs(value) for value in errors)
    squared_error = math.fsum(value * value for value in errors)
    squared_reference = math.fsum(value * value for value in reference)
    squared_candidate = math.fsum(value * value for value in candidate)
    dot = math.fsum(left * right for left, right in zip(reference, candidate, strict=True))
    rms = math.sqrt(squared_error / len(errors))
    relative_l2 = math.sqrt(squared_error / squared_reference) if squared_reference else math.inf
    cosine = dot / math.sqrt(squared_reference * squared_candidate) if squared_reference and squared_candidate else 0.0
    reference_top = _top_k_indices(reference, top_k)
    candidate_top = _top_k_indices(candidate, top_k)
    overlap = len(set(reference_top) & set(candidate_top)) / top_k
    return {
        "count": len(reference),
        "max_abs": max_abs,
        "rms": rms,
        "relative_l2": relative_l2,
        "cosine": cosine,
        "top_k": top_k,
        "top_k_set_overlap": overlap,
        "top_1_equal": reference_top[0] == candidate_top[0],
        "reference_top_k": reference_top,
        "candidate_top_k": candidate_top,
    }


def softmax_js_divergence(reference: Sequence[float], candidate: Sequence[float]) -> float:
    if len(reference) != len(candidate) or not reference:
        raise ProjectionGateError("JSD vectors must have equal nonzero length")

    def probabilities(values: Sequence[float]) -> list[float]:
        maximum = max(values)
        exponentials = [math.exp(value - maximum) for value in values]
        denominator = math.fsum(exponentials)
        return [value / denominator for value in exponentials]

    left = probabilities(reference)
    right = probabilities(candidate)
    terms = []
    for left_value, right_value in zip(left, right, strict=True):
        midpoint = 0.5 * (left_value + right_value)
        term = 0.0
        if left_value:
            term += 0.5 * left_value * math.log(left_value / midpoint)
        if right_value:
            term += 0.5 * right_value * math.log(right_value / midpoint)
        terms.append(term)
    return math.fsum(terms)


def adjudicate_metrics(metrics: dict[str, Any], limits: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    upper = {
        "max_abs": "max_abs",
        "rms": "rms",
        "relative_l2": "relative_l2",
        "softmax_js_divergence_max": "softmax_js_divergence",
        "max_abs_integer": "max_abs",
        "rms_integer": "rms",
    }
    lower = {
        "cosine_min": "cosine",
        "top_k_set_overlap_min": "top_k_set_overlap",
    }
    for limit_name, metric_name in upper.items():
        if limit_name in limits and float(metrics[metric_name]) > float(limits[limit_name]):
            failures.append(f"{metric_name}_above_{limits[limit_name]}")
    for limit_name, metric_name in lower.items():
        if limit_name in limits and float(metrics[metric_name]) < float(limits[limit_name]):
            failures.append(f"{metric_name}_below_{limits[limit_name]}")
    if limits.get("top_1_equal") and not metrics.get("top_1_equal"):
        failures.append("top_1_changed")
    if limits.get("nonzero_reference_required") and not metrics.get("reference_nonzero", True):
        failures.append("reference_is_zero")
    return not failures, failures

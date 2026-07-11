"""V79 INT16 replacement candidate for the falsified FP16 E4B LM head.

QAIRT 2.44 documents BF16 HTP runtime only for Windows V81 and newer, so a
BF16 MatMul is not an admissible SM8750/V79 rescue.  The same HTP supplement
does document SFixedPoint16 activations and outputs with static low-bit
SFixedPoint8 weights.  This module freezes that distinct candidate without
relaxing the already-observed combined QAT-to-QNN limits.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import struct
from typing import Any

from .e4b_f5_probe import LM_HEAD, QAT_MODEL_SHA256, TRANSFORMERS_COMMIT
from .e4b_f5_qnn_exporter import LM_HEAD_GRAPH, render_direct_qnn_cpp
from .e4b_l2_projection_gate import (
    POLICY_SCHEMA_VERSION,
    ProjectionGateError,
    bf16_payload_to_floats,
    canonical_json,
    input_cases,
    sha256_bytes,
    sha256_path,
    threshold_policy,
    validate_preregistration,
    write_hashed_json,
)


INT16_CANDIDATE_ID = "w2_s16_activation_bw2_weight_s16_output_v1"
INT16_POLICY_SCHEMA = "gemma4_e4b_l2_int16_head_policy_v1"
INT16_PREREG_SCHEMA = "gemma4_e4b_l2_int16_head_preregistration_v1"
FP16_FALSIFICATION_GATE_SHA256 = "965697efe3e3f9e65ac9aa726e0247fd83c1fdaa942bc1c0bc8954aabe784acd"
PARENT_POLICY_SHA256 = "97140d3d1d90de149f2a81ab84d315efd4186b9c3e75c715d7790e316c440c37"
HTP_BACKEND_DOC_SHA256 = "391b905c4f92d2309e5dc91e00e7497f06ff55a54b134b8f4afa9a8466362dff"
HTP_OPDEF_SUPPLEMENT_SHA256 = "f3f447b4f2f871236d1187db7d216828232f9b16a8561e878f3b40434fab4f37"
INPUT_SCALE = 1.0 / 512.0
OUTPUT_SCALE = 1.0 / 256.0
LOGIT_SOFTCAP = 30.0
DESCRIPTIVE_EDGE_KEYS = frozenset({"reference_dtype", "candidate_dtype"})


def _write_exclusive(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(payload)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                raise OSError(f"short write to {path}")
            view = view[count:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def quantize_bf16_input_to_s16(payload: bytes) -> bytes:
    """Quantize the frozen BF16 fixture with an exact power-of-two scale."""

    result = bytearray()
    for value in bf16_payload_to_floats(payload):
        scaled = value / INPUT_SCALE
        quantized = round(scaled)
        if quantized < -32768 or quantized > 32767:
            raise ProjectionGateError(f"INT16 input scale clips fixture value: {value}")
        restored = quantized * INPUT_SCALE
        if restored != value:
            raise ProjectionGateError(f"INT16 input scale is not exact for fixture value: {value}")
        result.extend(struct.pack("<h", quantized))
    return bytes(result)


def int16_candidate_policy() -> dict[str, Any]:
    parent = threshold_policy()
    if sha256_bytes(canonical_json(parent)) != PARENT_POLICY_SHA256:
        raise ProjectionGateError("parent projection policy drift")
    combined = parent["edges"]["w2_bf16_qat_to_qnn_combined"]
    parent_descriptive = {
        key: combined[key]
        for key in sorted(DESCRIPTIVE_EDGE_KEYS)
    }
    numeric_ranking_thresholds = {
        key: value
        for key, value in combined.items()
        if key not in DESCRIPTIVE_EDGE_KEYS
    }
    threshold_subset_sha256 = sha256_bytes(canonical_json(numeric_ranking_thresholds))
    return {
        "schema_version": INT16_POLICY_SCHEMA,
        "state": "frozen_before_int16_candidate_output",
        "candidate_id": INT16_CANDIDATE_ID,
        "parent_policy_schema": POLICY_SCHEMA_VERSION,
        "parent_policy_sha256": PARENT_POLICY_SHA256,
        "authority_edge": {
            "name": "w2_bf16_qat_to_qnn_combined",
            "parent_descriptive_dtype_metadata": parent_descriptive,
            "candidate_descriptive_dtype_metadata": {
                "reference_dtype": "bfloat16_qat",
                "candidate_storage_dtype": "QNN_DATATYPE_SFIXED_POINT_16",
                "candidate_observation_dtype": "float64_after_exact_s16_scale_dequantization",
                "candidate_dequantization_scale": OUTPUT_SCALE,
            },
            "numeric_and_ranking_thresholds": numeric_ranking_thresholds,
            "threshold_equality_proof": {
                "parent_numeric_and_ranking_subset_sha256": threshold_subset_sha256,
                "candidate_numeric_and_ranking_subset_sha256": threshold_subset_sha256,
                "subsets_equal": True,
                "values_changed_from_parent": False,
                "excluded_descriptive_keys": sorted(DESCRIPTIVE_EDGE_KEYS),
            },
            "every_metric_and_every_case_must_pass": True,
        },
        "input_quantization": {
            "dtype": "QNN_DATATYPE_SFIXED_POINT_16",
            "encoding": "QNN_QUANTIZATION_ENCODING_SCALE_OFFSET",
            "scale": INPUT_SCALE,
            "offset": 0,
            "fixture_roundtrip_max_abs": 0.0,
            "representable_range": [-32768 * INPUT_SCALE, 32767 * INPUT_SCALE],
        },
        "weight_quantization": {
            "dtype": "QNN_DATATYPE_SFIXED_POINT_8",
            "storage_bitwidth": 2,
            "encoding": "QNN_QUANTIZATION_ENCODING_BW_AXIS_SCALE_OFFSET",
            "axis": 0,
            "packed_weight_sha256": LM_HEAD.weight.data_sha256,
            "per_channel_scale_sha256": LM_HEAD.weight_scale.data_sha256,
            "transpose_in1": True,
        },
        "output_quantization": {
            "dtype": "QNN_DATATYPE_SFIXED_POINT_16",
            "encoding": "QNN_QUANTIZATION_ENCODING_SCALE_OFFSET",
            "scale": OUTPUT_SCALE,
            "offset": 0,
            "representable_range": [-32768 * OUTPUT_SCALE, 32767 * OUTPUT_SCALE],
            "selection_basis": "power_of_two_scale_and_more_than_four_times_the_frozen_logit_softcap",
            "logit_softcap": LOGIT_SOFTCAP,
            "selection_used_candidate_output": False,
        },
        "platform_evidence": {
            "target": "SM8750_V79_Android",
            "htp_backend_doc_sha256": HTP_BACKEND_DOC_SHA256,
            "htp_backend_bf16_boundary": "Windows_V81_and_newer_only",
            "htp_opdef_supplement_sha256": HTP_OPDEF_SUPPLEMENT_SHA256,
            "matmul_documented_configuration": "SFixedPoint16_x_SFixedPoint8_to_SFixedPoint16",
            "two_bit_weight_minimum_arch": "V73",
        },
        "failure_rule": "kill_or_rebuild_INT16_candidate_without_relaxing_parent_limits",
        "nonclaims": [
            "no_provider_context_acceptance",
            "no_phone_execution",
            "no_QAT_to_QNN_fidelity",
            "no_L1_or_L2_pass",
            "no_learning_or_authority_quality",
        ],
    }


def _load_fp16_falsification(path: Path) -> dict[str, Any]:
    if sha256_path(path) != FP16_FALSIFICATION_GATE_SHA256:
        raise ProjectionGateError("FP16 falsification gate digest mismatch")
    raw = path.read_bytes()
    gate = json.loads(raw)
    if canonical_json(gate) != raw:
        raise ProjectionGateError("FP16 falsification gate is not canonical JSON")
    required = {
        "schema_version": "gemma4_e4b_f5_reference_gate_v1",
        "status": "falsified_scope",
        "l2_threshold_policy_sha256": PARENT_POLICY_SHA256,
        "qat_model_sha256": QAT_MODEL_SHA256,
        "transformers_commit": TRANSFORMERS_COMMIT,
        "phone_execution_count": 0,
        "qnn_output_observed": False,
        "full_L2_passed": False,
    }
    for name, expected in required.items():
        if gate.get(name) != expected:
            raise ProjectionGateError(f"FP16 falsification contract mismatch: {name}")
    return gate


def _authority_outputs(gate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    outputs: dict[str, dict[str, Any]] = {}
    for record in gate.get("case_records", []):
        if record.get("graph_name") != LM_HEAD_GRAPH:
            continue
        case_id = record.get("case_id")
        authority = record.get("qat_bf16_output")
        if not isinstance(case_id, str) or not isinstance(authority, dict):
            raise ProjectionGateError("invalid W2 authority output record")
        outputs[case_id] = {
            "bytes": authority.get("bytes"),
            "sha256": authority.get("sha256"),
            "dtype": authority.get("dtype"),
            "shape": authority.get("shape"),
            "provider_relative_path": authority.get("relative_path"),
        }
    if len(outputs) != 3:
        raise ProjectionGateError("expected three frozen W2 authority outputs")
    return outputs


def build_int16_preregistration(
    *,
    parent_prereg_dir: Path,
    fp16_falsification_gate: Path,
    output_dir: Path,
    created_at_utc: str,
) -> dict[str, Any]:
    """Freeze the replacement candidate before any INT16/QNN output exists."""

    if output_dir.exists():
        raise ProjectionGateError(f"output already exists: {output_dir}")
    parent = validate_preregistration(parent_prereg_dir)
    parent_sha256 = sha256_path(parent_prereg_dir / "preregistration.json")
    gate = _load_fp16_falsification(fp16_falsification_gate)
    authority_outputs = _authority_outputs(gate)
    policy = int16_candidate_policy()

    output_dir.mkdir(mode=0o700, parents=True)
    inputs_dir = output_dir / "inputs"
    inputs_dir.mkdir(mode=0o700)
    policy_sha256 = write_hashed_json(output_dir / "threshold_policy.json", policy)
    cases = []
    for case in input_cases():
        if case.graph_name != LM_HEAD_GRAPH:
            continue
        source = parent_prereg_dir / "inputs" / case.filename
        if source.read_bytes() != case.payload:
            raise ProjectionGateError(f"parent BF16 fixture drift: {case.case_id}")
        payload = quantize_bf16_input_to_s16(case.payload)
        filename = f"{LM_HEAD_GRAPH}.{case.case_id}.s16.raw"
        _write_exclusive(inputs_dir / filename, payload)
        cases.append(
            {
                "case_id": case.case_id,
                "bf16_input_sha256": sha256_bytes(case.payload),
                "s16_input_relative_path": f"inputs/{filename}",
                "s16_input_bytes": len(payload),
                "s16_input_sha256": sha256_bytes(payload),
                "input_roundtrip_max_abs": 0.0,
                "authority_output": authority_outputs[case.case_id],
                "candidate_output_present": False,
            }
        )

    manifest = {
        "schema_version": INT16_PREREG_SCHEMA,
        "state": "frozen_unobserved",
        "created_at_utc": created_at_utc,
        "candidate_id": INT16_CANDIDATE_ID,
        "parent_projection_preregistration_sha256": parent_sha256,
        "parent_projection_policy_sha256": PARENT_POLICY_SHA256,
        "fp16_falsification_gate_sha256": FP16_FALSIFICATION_GATE_SHA256,
        "threshold_policy_sha256": policy_sha256,
        "model_sha256": QAT_MODEL_SHA256,
        "graph_name": LM_HEAD_GRAPH,
        "input_features": LM_HEAD.input_features,
        "output_features": LM_HEAD.output_features,
        "cases": cases,
        "candidate_output_files_present": False,
        "scale_selection_used_candidate_output": False,
        "claim_boundary": "new_full_width_INT16_head_candidate_preregistration_only",
        "nonclaims": policy["nonclaims"],
        "parent_fixture_manifest_state": parent["state"],
    }
    manifest_sha256 = write_hashed_json(output_dir / "preregistration.json", manifest)
    return {
        "preregistration_sha256": manifest_sha256,
        "threshold_policy_sha256": policy_sha256,
        "case_count": len(cases),
    }


def render_int16_head_cpp() -> str:
    """Transform the exact two-graph source into the distinct INT16 W2 ABI."""

    source = render_direct_qnn_cpp()
    old = '''    GraphSpec headSpec{
        "gemma4_e4b_f5_w2_lm_head",
        "lm_head_input_f16",
        "lm_head_weight_s8_bw2",
        "lm_head_output_f16_pre_softcap",
        "lm_head_matmul",
        2560,
        262144,
        2,
        QNN_DATATYPE_FLOAT_16,
        undefinedQuantization(),
        undefinedQuantization(),
    };'''
    new = f'''    GraphSpec headSpec{{
        "gemma4_e4b_f5_w2_lm_head",
        "lm_head_input_s16",
        "lm_head_weight_s8_bw2",
        "lm_head_output_s16_pre_softcap",
        "lm_head_matmul",
        2560,
        262144,
        2,
        QNN_DATATYPE_SFIXED_POINT_16,
        scaleOffsetQuantization({INPUT_SCALE:.9f}f),
        scaleOffsetQuantization({OUTPUT_SCALE:.9f}f),
    }};'''
    if source.count(old) != 1:
        raise ProjectionGateError("cannot identify exact FP16 head graph block")
    transformed = source.replace(old, new)
    forbidden = ("lm_head_input_f16", "lm_head_output_f16_pre_softcap")
    if any(fragment in transformed for fragment in forbidden):
        raise ProjectionGateError("FP16 head ABI survived INT16 transformation")
    return transformed

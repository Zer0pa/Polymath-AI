from __future__ import annotations

import io
import json
import struct

import pytest

from polymath_ai.frontier.e4b_f5_probe import (
    LM_HEAD,
    PROJECTIONS,
    QAT_MODEL_BYTES,
    QAT_MODEL_SHA256,
    Q_PROJ,
    ProbeContractError,
    build_probe_plan,
    read_safetensors_header,
    validate_pinned_header,
)


def _exact_header():
    header = {"__metadata__": {"format": "pt"}}
    for projection in PROJECTIONS:
        for tensor in (
            projection.weight,
            projection.weight_scale,
            projection.input_activation_scale,
            projection.output_activation_scale,
        ):
            header[tensor.name] = {
                "dtype": tensor.dtype,
                "shape": list(tensor.shape),
                "data_offsets": list(tensor.offsets),
            }
    return header


def test_pinned_probe_dimensions_and_packing_are_not_toy_shapes():
    assert Q_PROJ.weight.shape == (2_048, 1_280)
    assert Q_PROJ.input_features == 2_560
    assert Q_PROJ.output_features == 2_048
    assert Q_PROJ.expected_packed_bytes == 2_621_440

    assert LM_HEAD.weight.shape == (262_144, 640)
    assert LM_HEAD.input_features == 2_560
    assert LM_HEAD.output_features == 262_144
    assert LM_HEAD.expected_packed_bytes == 167_772_160


def test_exact_header_contract_passes():
    validate_pinned_header(_exact_header())


@pytest.mark.parametrize("field,replacement", [("dtype", "I8"), ("shape", [1, 1]), ("data_offsets", [0, 1])])
def test_header_contract_rejects_identity_drift(field, replacement):
    header = _exact_header()
    header[Q_PROJ.weight.name][field] = replacement
    with pytest.raises(ProbeContractError):
        validate_pinned_header(header)


def test_safetensors_header_reader_rejects_nonfinite_json():
    raw = b'{"x":NaN}'
    carrier = io.BytesIO(struct.pack("<Q", len(raw)) + raw)
    with pytest.raises(ProbeContractError, match="non-finite"):
        read_safetensors_header(carrier)


def test_safetensors_header_reader_rejects_duplicate_keys():
    raw = b'{"x":1,"x":2}'
    carrier = io.BytesIO(struct.pack("<Q", len(raw)) + raw)
    with pytest.raises(ProbeContractError, match="duplicate JSON key"):
        read_safetensors_header(carrier)


def test_plan_marks_literal_bitwise_gap_and_exact_dense_costs():
    plan = build_probe_plan(
        supported_onnx_ops={"Cast", "Round", "Clip", "Where", "Gemm", "MatMul"},
        carrier_bytes=2_415_919_104,
        full_artifact_sha256=None,
    )
    assert plan["artifact"]["full_provider_identity_green"] is False
    q_proj, head = plan["probes"]
    assert q_proj["literal_transformers_export"]["unsupported_critical_nodes_in_qairt_2_44"] == [
        "BitShift",
        "BitwiseAnd",
    ]
    assert q_proj["memory"]["dense_bfloat16_weight_bytes"] == 10_485_760
    assert q_proj["memory"]["dense_float32_weight_bytes"] == 20_971_520
    assert head["memory"]["dense_bfloat16_weight_bytes"] == 1_342_177_280
    assert head["memory"]["dense_float32_weight_bytes"] == 2_684_354_560


def test_w4_matmul_nbits_is_exactly_shaped_but_w2_is_hard_rejected():
    plan = build_probe_plan(
        supported_onnx_ops=set(),
        carrier_bytes=QAT_MODEL_BYTES,
        full_artifact_sha256=QAT_MODEL_SHA256,
    )
    q_proj, head = plan["probes"]
    assert q_proj["onnx_matmul_nbits"]["attributes"] == {
        "K": 2_560,
        "N": 2_048,
        "bits": 4,
        "block_size": 2_560,
    }
    assert q_proj["onnx_matmul_nbits"]["B_shape"] == [2_048, 1, 1_280]
    assert q_proj["onnx_matmul_nbits"]["zero_point_byte"] == "0x88"
    assert head["onnx_matmul_nbits"]["status"] == "hard_reject_by_qairt_2_44_importer"


def test_direct_qnn_contract_preserves_packed_source_and_uses_documented_htp_abi():
    plan = build_probe_plan(
        supported_onnx_ops=set(),
        carrier_bytes=QAT_MODEL_BYTES,
        full_artifact_sha256=QAT_MODEL_SHA256,
    )
    q_proj, head = (probe["direct_qnn_low_bit"] for probe in plan["probes"])
    assert q_proj["source_packed_weight"]["data_sha256"] == Q_PROJ.weight.data_sha256
    assert q_proj["weight_data_type"] == "QNN_DATATYPE_SFIXED_POINT_8"
    assert q_proj["weight_quantization"]["bitwidth"] == 4
    assert q_proj["weight_quantization"]["offsets"] is None
    assert q_proj["deterministic_host_lowering"]["signed_shift"] == -8
    assert q_proj["transpose_in1"] is True
    assert q_proj["input_abi"]["data_type"] == "QNN_DATATYPE_SFIXED_POINT_8"
    assert head["weight_data_type"] == "QNN_DATATYPE_SFIXED_POINT_8"
    assert head["weight_quantization"]["bitwidth"] == 2
    assert head["deterministic_host_lowering"]["signed_shift"] == -2
    assert head["source_packed_weight"]["shape_bytes"] == [262_144, 640]
    assert head["input_abi"]["data_type"] == "QNN_DATATYPE_FLOAT_16"


def test_plan_is_strict_json_serializable():
    plan = build_probe_plan(
        supported_onnx_ops=set(),
        carrier_bytes=None,
        full_artifact_sha256=None,
    )
    assert json.loads(json.dumps(plan, allow_nan=False))["promotion"]["capsule_advance_allowed"] is False

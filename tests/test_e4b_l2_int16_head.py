from __future__ import annotations

import json
from pathlib import Path

from polymath_ai.frontier import e4b_l2_int16_head as int16_head
from polymath_ai.frontier.e4b_f5_probe import QAT_MODEL_SHA256, TRANSFORMERS_COMMIT
from polymath_ai.frontier.e4b_f5_qnn_exporter import LM_HEAD_GRAPH
from polymath_ai.frontier.e4b_l2_projection_gate import (
    build_preregistration,
    canonical_json,
    input_cases,
    sha256_bytes,
    threshold_policy,
)


EXPECTED_S16 = {
    "structured_dynamic": "360e7c9f22a0dbb0c135b3a1b696d206e66d02b57b6320eb3e8210d1e880e236",
    "balanced_splitmix64": "8ac246d9328dca16ae2c182906bdb11b8080f0dc71161d28838291eb27f1bf90",
    "low_amplitude_splitmix64": "05b0526761aa7a5c83156a6bcdf3954a784b23d8b97ffc864e3acc963a3b490a",
}


def test_int16_policy_reuses_parent_combined_limits_without_relaxation():
    policy = int16_head.int16_candidate_policy()
    parent = threshold_policy()["edges"]["w2_bf16_qat_to_qnn_combined"]
    thresholds = policy["authority_edge"]["numeric_and_ranking_thresholds"]
    assert thresholds == {
        key: value
        for key, value in parent.items()
        if key not in int16_head.DESCRIPTIVE_EDGE_KEYS
    }
    assert policy["authority_edge"]["parent_descriptive_dtype_metadata"] == {
        "candidate_dtype": "float16_native_qnn",
        "reference_dtype": "bfloat16_qat",
    }
    candidate_dtype = policy["authority_edge"]["candidate_descriptive_dtype_metadata"]
    assert candidate_dtype["candidate_storage_dtype"] == "QNN_DATATYPE_SFIXED_POINT_16"
    assert candidate_dtype["candidate_observation_dtype"] == (
        "float64_after_exact_s16_scale_dequantization"
    )
    proof = policy["authority_edge"]["threshold_equality_proof"]
    assert proof["subsets_equal"] is True
    assert proof["values_changed_from_parent"] is False
    assert proof["parent_numeric_and_ranking_subset_sha256"] == (
        proof["candidate_numeric_and_ranking_subset_sha256"]
    )
    assert proof["parent_numeric_and_ranking_subset_sha256"] == (
        "30704ef1cb88042a1451f46b5c516b815cbb440a7227b9013893ee7b42cdd914"
    )
    assert proof["excluded_descriptive_keys"] == ["candidate_dtype", "reference_dtype"]
    assert policy["input_quantization"]["scale"] == 1.0 / 512.0
    assert policy["output_quantization"]["scale"] == 1.0 / 256.0
    assert policy["output_quantization"]["selection_used_candidate_output"] is False
    assert "candidate_dtype" not in thresholds
    assert "reference_dtype" not in thresholds
    assert sha256_bytes(canonical_json(policy)) == (
        "36d4689f6c59f8ce8d9d99c6dc4085d7e63089a6448c20517fd0fcc74964ad05"
    )


def test_all_frozen_bf16_inputs_roundtrip_exactly_through_s16():
    observed = {}
    for case in input_cases():
        if case.graph_name != LM_HEAD_GRAPH:
            continue
        payload = int16_head.quantize_bf16_input_to_s16(case.payload)
        observed[case.case_id] = sha256_bytes(payload)
        assert len(payload) == 5120
    assert observed == EXPECTED_S16


def test_rendered_head_uses_documented_v79_int16_lowbit_configuration():
    source = int16_head.render_int16_head_cpp()
    required = [
        '"lm_head_input_s16"',
        '"lm_head_weight_s8_bw2"',
        '"lm_head_output_s16_pre_softcap"',
        "QNN_DATATYPE_SFIXED_POINT_16",
        "scaleOffsetQuantization(0.001953125f)",
        "scaleOffsetQuantization(0.003906250f)",
        "weightQuantization(spec.weightBits",
    ]
    for fragment in required:
        assert fragment in source
    assert "lm_head_input_f16" not in source
    assert "lm_head_output_f16_pre_softcap" not in source
    assert sha256_bytes(source.encode("utf-8")) == (
        "4757e20cc723a1b5a69683ff5f080b8c15805bff0f26c28305d81c4bf1530f8a"
    )


def test_int16_preregistration_binds_prior_authority_without_candidate_output(
    tmp_path: Path,
    monkeypatch,
):
    parent = tmp_path / "parent"
    build_preregistration(parent, created_at_utc="2026-07-11T01:40:00Z")
    gate = {
        "schema_version": "gemma4_e4b_f5_reference_gate_v1",
        "status": "falsified_scope",
        "l2_threshold_policy_sha256": int16_head.PARENT_POLICY_SHA256,
        "qat_model_sha256": QAT_MODEL_SHA256,
        "transformers_commit": TRANSFORMERS_COMMIT,
        "phone_execution_count": 0,
        "qnn_output_observed": False,
        "full_L2_passed": False,
        "case_records": [
            {
                "graph_name": LM_HEAD_GRAPH,
                "case_id": case_id,
                "qat_bf16_output": {
                    "relative_path": f"references/{case_id}.bf16.raw",
                    "bytes": 524288,
                    "sha256": sha256_bytes(case_id.encode("utf-8")),
                    "dtype": "bfloat16",
                    "shape": [1, 1, 262144],
                },
            }
            for case_id in EXPECTED_S16
        ],
    }
    gate_path = tmp_path / "gate.json"
    gate_path.write_bytes(canonical_json(gate))
    monkeypatch.setattr(
        int16_head,
        "FP16_FALSIFICATION_GATE_SHA256",
        sha256_bytes(gate_path.read_bytes()),
    )
    output = tmp_path / "int16"
    result = int16_head.build_int16_preregistration(
        parent_prereg_dir=parent,
        fp16_falsification_gate=gate_path,
        output_dir=output,
        created_at_utc="2026-07-11T02:00:00Z",
    )
    manifest = json.loads((output / "preregistration.json").read_bytes())
    assert result["case_count"] == 3
    assert manifest["candidate_output_files_present"] is False
    assert manifest["scale_selection_used_candidate_output"] is False
    assert all(not record["candidate_output_present"] for record in manifest["cases"])
    assert sorted(path.name for path in (output / "inputs").iterdir()) == sorted(
        f"{LM_HEAD_GRAPH}.{case_id}.s16.raw" for case_id in EXPECTED_S16
    )

from __future__ import annotations

from pathlib import Path

import pytest

from polymath_ai.frontier.e4b_f5_qnn_exporter import LM_HEAD_GRAPH, Q_PROJ_GRAPH
from polymath_ai.frontier.e4b_l2_projection_gate import (
    ProjectionGateError,
    adjudicate_metrics,
    bf16_payload_to_fp16,
    build_preregistration,
    canonical_json,
    input_cases,
    sha256_bytes,
    softmax_js_divergence,
    threshold_policy,
    validate_preregistration,
    vector_metrics,
)


EXPECTED_INPUTS = {
    (Q_PROJ_GRAPH, "signed_ramp"): (2560, "e392378f849d67bbb1a7bbec84f1098ae3faa751049c009a850130ce6073d91a"),
    (Q_PROJ_GRAPH, "boundary_alternating"): (
        2560,
        "1254973c520a012bfe26ed46e33fed34aff2024b64358e2fd85d9519f27e064e",
    ),
    (Q_PROJ_GRAPH, "splitmix64"): (2560, "5ed7ce06064b065bf51da065621b8ba687ed9a19ff909b93bc64f40124a43244"),
    (LM_HEAD_GRAPH, "structured_dynamic"): (
        5120,
        "5cca991319c94de485360d2b05b87a80b9b88bc3fe636c8a478ccda9461bada8",
    ),
    (LM_HEAD_GRAPH, "balanced_splitmix64"): (
        5120,
        "2065c350db9e1b835193f7b369b4561bae099eb20931562bede7687727af16aa",
    ),
    (LM_HEAD_GRAPH, "low_amplitude_splitmix64"): (
        5120,
        "0d0d93d4562b91ee90d129e0e7c277654659e27a7a87cbc4e4a62276e61dcbe3",
    ),
}

EXPECTED_FP16 = {
    "structured_dynamic": "31978f4b4e9135b25da09f4cf443fc51416b06698fbf550112049facaa30fa8b",
    "balanced_splitmix64": "95c5d8840eaddf2d43c4b6a1eab34d2b9f3ac24ef91d243549af2f0c411b5694",
    "low_amplitude_splitmix64": "2f2cbf41779af5c070fcc4036e18a66c12a2fc26eb06d42bbcd73503225c254f",
}


def test_full_width_fixture_bytes_and_policy_are_pinned():
    cases = input_cases()
    assert len(cases) == 6
    for case in cases:
        expected_bytes, expected_sha = EXPECTED_INPUTS[(case.graph_name, case.case_id)]
        assert len(case.payload) == expected_bytes
        assert sha256_bytes(case.payload) == expected_sha
        if case.dtype == "bfloat16":
            assert sha256_bytes(bf16_payload_to_fp16(case.payload)) == EXPECTED_FP16[case.case_id]
    assert sha256_bytes(canonical_json(threshold_policy())) == (
        "97140d3d1d90de149f2a81ab84d315efd4186b9c3e75c715d7790e316c440c37"
    )


def test_preregistration_contains_no_observed_output_and_validates(tmp_path: Path):
    root = tmp_path / "frozen"
    result = build_preregistration(root, created_at_utc="2026-07-11T03:00:00Z")
    manifest = validate_preregistration(root)
    assert result["case_count"] == 6
    assert manifest["state"] == "frozen_unobserved"
    assert manifest["output_files_present"] is False
    assert not (root / "references").exists()
    assert sorted(path.name for path in (root / "inputs").iterdir()) == sorted(
        [case.filename for case in input_cases()]
        + [
            case.filename.replace(".bf16.raw", ".f16.raw")
            for case in input_cases()
            if case.dtype == "bfloat16"
        ]
    )


def test_preregistration_fails_closed_on_input_mutation(tmp_path: Path):
    root = tmp_path / "frozen"
    build_preregistration(root, created_at_utc="2026-07-11T03:00:00Z")
    case = input_cases()[0]
    path = root / "inputs" / case.filename
    path.write_bytes(b"\x00" * len(case.payload))
    with pytest.raises(ProjectionGateError, match="input payload drift"):
        validate_preregistration(root)


def test_vector_metrics_and_adjudication_cover_rank_and_distribution():
    reference = [float(index) for index in range(32)]
    identical = vector_metrics(reference, reference)
    identical["softmax_js_divergence"] = softmax_js_divergence(reference, reference)
    assert identical["max_abs"] == 0.0
    assert identical["rms"] == 0.0
    assert identical["relative_l2"] == 0.0
    assert identical["cosine"] == pytest.approx(1.0)
    assert identical["top_k_set_overlap"] == 1.0
    assert identical["top_1_equal"] is True
    assert identical["softmax_js_divergence"] == 0.0
    passed, failures = adjudicate_metrics(
        identical,
        threshold_policy()["edges"]["w2_fp16_framework_to_qnn"],
    )
    assert passed
    assert failures == []


def test_adjudication_does_not_allow_cosine_to_hide_decision_change():
    metrics = {
        "max_abs": 0.01,
        "rms": 0.001,
        "relative_l2": 0.001,
        "cosine": 0.999999,
        "softmax_js_divergence": 1.0e-8,
        "top_k_set_overlap": 1.0,
        "top_1_equal": False,
    }
    passed, failures = adjudicate_metrics(
        metrics,
        threshold_policy()["edges"]["w2_fp16_framework_to_qnn"],
    )
    assert not passed
    assert failures == ["top_1_changed"]


def test_phone_verifier_source_uses_same_frozen_w2_limits():
    source = Path("native/e4b_l2_projection_verifier.c").read_text(encoding="utf-8")
    required = [
        "w2_passes(cast_edge, 0.125, 0.02, 0.005, 0.99999, 1.0e-6, 0.96875)",
        "w2_passes(conversion_edge, 0.0625, 0.01, 0.0025, 0.999995, 5.0e-7, 0.96875)",
        "w2_passes(combined_edge, 0.1875, 0.03, 0.0075, 0.99998, 2.0e-6, 0.9375)",
        "metrics.max_abs <= 1.0 && metrics.rms <= 0.25",
    ]
    for fragment in required:
        assert fragment in source


def test_reference_runner_hashes_scalar_tensors_without_zero_dimensional_view():
    source = Path("scripts/host/run_e4b_l2_projection_reference.py").read_text(encoding="utf-8")
    assert source.count(".contiguous().reshape(-1).view(torch.uint8).numpy()") == 2
    assert ".contiguous().view(torch.uint8).numpy()" not in source

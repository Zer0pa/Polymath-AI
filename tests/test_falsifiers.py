"""Falsifier registry coverage tests.

Every falsifier ID in the PRD §Falsifier Registry must have a registered
evaluator with positive and negative fixtures.
"""
from __future__ import annotations

from typing import Any, Mapping

import pytest

from polymath_ai.falsifiers.registry import (
    FALSIFIERS,
    evaluate,
    list_ids,
    summary_report,
)


PRD_FALSIFIER_IDS = {
    "boundary_violation",
    "device_soc_mismatch",
    "qnn_exact_path_unproven",
    "qnn_unsupported_op",
    "smollm3_export_unproven",
    "checkpoint_hash_mismatch",
    "tokenizer_fertility_high",
    "oom_or_memory_pressure",
    "thermal_throttle",
    "battery_heat_risk",
    "charge_bypass_unproven",
    "throughput_floor_fail",
    "energy_budget_exceeded",
    "catastrophic_forgetting",
    "cross_model_disagreement_high",
    "method_disagreement_high",
    "license_drift",
    "ocr_damage_high",
    "overclaim",
}


def test_all_prd_falsifiers_registered():
    missing = PRD_FALSIFIER_IDS - set(FALSIFIERS.keys())
    assert not missing, f"missing falsifiers: {missing}"


def test_unknown_id_raises():
    with pytest.raises(KeyError):
        evaluate("nope", {})


# ---------- positive (pass) fixtures ----------


@pytest.mark.parametrize(
    "fid,evidence",
    [
        ("boundary_violation", {"scan_failures": []}),
        ("device_soc_mismatch", {"soc_reported": "SM8650", "soc_target": "SM8650"}),
        (
            "qnn_exact_path_unproven",
            {
                "qnn_compile_records": [
                    {"graph_scope": "tiny_block", "result": "ok"},
                    {"graph_scope": "real_block", "result": "ok"},
                ]
            },
        ),
        ("qnn_unsupported_op", {"delegate_pct": 0.95, "delegate_threshold": 0.5}),
        ("smollm3_export_unproven", {"experiment_2_status": "pass"}),
        ("checkpoint_hash_mismatch", {"expected_sha256": "sha256:abc", "actual_sha256": "sha256:abc"}),
        (
            "tokenizer_fertility_high",
            {"per_language": {"en": {"ratio_vs_english": 1.0}, "fr": {"ratio_vs_english": 1.3}}},
        ),
        ("oom_or_memory_pressure", {"oom": False, "peak_ram_gb": 10.5}),
        ("thermal_throttle", {"gpu_clock_below_600_pct": 0.02}),
        ("battery_heat_risk", {"battery_temp_samples_c": [{"temp_c": 35} for _ in range(60)]}),
        ("charge_bypass_unproven", {"battery_pct_drift_per_hour": 0.5}),
        ("throughput_floor_fail", {"tokens_per_hour": 1_500_000}),
        (
            "energy_budget_exceeded",
            {"joules_per_token": 0.42, "joules_per_token_baseline": 0.40, "quality_gain_pct": 0.0},
        ),
        ("catastrophic_forgetting", {"english_anchor_drop_pp": 0.3}),
        ("cross_model_disagreement_high", {"disagreement_metric": 0.10}),
        ("method_disagreement_high", {"elo_qlora_spearman_rho": 0.85}),
        (
            "license_drift",
            {
                "corpus_sources": [
                    {"source_id": "s1", "license_class": "A"},
                    {"source_id": "s2", "license_class": "B"},
                ]
            },
        ),
        ("ocr_damage_high", {"ocr_damage_score": 0.05}),
        ("overclaim", {"unsupported_claims": []}),
    ],
)
def test_positive_fixtures_pass(fid, evidence):
    res = evaluate(fid, evidence)
    assert res.result == "pass", f"{fid} produced {res.result}: {res.detail}"


# ---------- negative (fail) fixtures ----------


@pytest.mark.parametrize(
    "fid,evidence,expected_result",
    [
        (
            "boundary_violation",
            {"scan_failures": [{"path": "x", "status": "MISSING"}]},
            "fail",
        ),
        ("device_soc_mismatch", {"soc_reported": "SM8650", "soc_target": "SM8850"}, "fail"),
        ("qnn_exact_path_unproven", {"qnn_compile_records": []}, "blocked"),
        (
            "qnn_unsupported_op",
            {"delegate_pct": 0.30, "delegate_threshold": 0.50, "unsupported_ops": ["GatherND"]},
            "fail",
        ),
        ("smollm3_export_unproven", {"experiment_2_status": "fail"}, "blocked"),
        (
            "checkpoint_hash_mismatch",
            {"expected_sha256": "sha256:a", "actual_sha256": "sha256:b"},
            "fail",
        ),
        (
            "tokenizer_fertility_high",
            {"per_language": {"sw": {"ratio_vs_english": 3.5}}},
            "fail",
        ),
        ("oom_or_memory_pressure", {"oom": True}, "fail"),
        ("thermal_throttle", {"gpu_clock_below_600_pct": 0.30}, "fail"),
        (
            "battery_heat_risk",
            {"battery_temp_samples_c": [{"temp_c": 43} for _ in range(120)]},
            "fail",
        ),
        ("charge_bypass_unproven", {"battery_pct_drift_per_hour": 5.0}, "fail"),
        ("throughput_floor_fail", {"tokens_per_hour": 50_000}, "fail"),
        (
            "energy_budget_exceeded",
            {"joules_per_token": 0.60, "joules_per_token_baseline": 0.40, "quality_gain_pct": 0.0},
            "fail",
        ),
        ("catastrophic_forgetting", {"english_anchor_drop_pp": 2.5}, "fail"),
        (
            "license_drift",
            {
                "corpus_sources": [
                    {"source_id": "ambiguous", "license_class": "D"},
                ]
            },
            "fail",
        ),
        ("ocr_damage_high", {"ocr_damage_score": 0.50}, "fail"),
        ("overclaim", {"unsupported_claims": ["claim X has no evidence"]}, "fail"),
    ],
)
def test_negative_fixtures_fail(fid, evidence, expected_result):
    res = evaluate(fid, evidence)
    assert res.result == expected_result, f"{fid} produced {res.result}: {res.detail}"


def test_blocking_default_propagation():
    # boundary_violation is blocking_default=True
    res = evaluate("boundary_violation", {"scan_failures": [{"path": "x", "status": "MISSING"}]})
    assert res.result == "fail"
    assert res.blocking is True


def test_summary_report_aggregates():
    results = [
        evaluate("oom_or_memory_pressure", {"oom": False, "peak_ram_gb": 5.0}),
        evaluate("thermal_throttle", {"gpu_clock_below_600_pct": 0.02}),
        evaluate("license_drift", {"corpus_sources": [{"source_id": "x", "license_class": "D"}]}),
    ]
    rep = summary_report(results)
    assert rep["counts"]["pass"] == 2
    assert rep["counts"]["fail"] == 1
    assert rep["overall"] == "blocked"
    assert "license_drift" in rep["blocking_failures"]


def test_skipped_when_evidence_missing():
    res = evaluate("oom_or_memory_pressure", {})  # no peak_ram_gb, no oom
    assert res.result == "skipped"

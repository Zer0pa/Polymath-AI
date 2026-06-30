from __future__ import annotations

from polymath_ai.polar.phase4_bridge_cell import (
    CELL_ID,
    CURRICULUM_CORPUS_PHASES,
    validate_phase34_curriculum_metric_readiness,
    validate_phase34_metric_readiness,
    validate_phase4_bridge_report,
)


def valid_report() -> dict:
    return {
        "cell_id": CELL_ID,
        "corpus_phase": "C1_diagnostic",
        "authority_material": "mechanical_consumed_output_preflight_only",
        "phase3_ready_claim": False,
        "phase4_ready_claim": False,
        "learning_claim": False,
        "phase3_output": {
            "path": "/sdcard/Download/polymath_phase34/active_wave/pjp1_htp_relu_input/htp_relu_run/run/Result_0/gemma_hidden_relu_out.raw",
            "shape": [1, 16, 2560],
            "dtype": "float32_le",
            "sha256": "d29e8cf2a034ade4185ae7a5d1130becb0137395c912825b29ac8c50de3351c6",
            "sha256_match": True,
            "context_sha256": "context",
            "backend": "/data/local/tmp/qairt-2.44/lib/aarch64-android/libQnnHtp.so",
            "graph": "gemma_hidden2560_relu",
        },
        "phase4_target": {
            "path": "/sdcard/Download/polymath_phase34/active_wave/pjp1_htp_relu_input/pjp1_packet0_tokens16_phase4_target.f32.bin",
            "shape": [1, 16, 2560],
            "dtype": "float32_le",
            "sha256": "704ffdab04f3b1b585b6246957ad576027a847b2c43367a927a23ef63ee55db7",
            "sha256_match": True,
            "source_pjp1_sha256": "e347676432fa7a76489f402f3c3e38ab492b6554f71930f14bc7d36ed1b3ecf5",
            "bridge_rule": "target hidden[h] = +1.0 if target_polar[token,h%256] bit is 1 else -1.0",
        },
        "opencl_device_is_adreno": True,
        "no_hidden_fallback": True,
        "no_cpu_objective_gradient_update": True,
        "named_consumer": "phase4_opencl_phase3_bridge_rank16_mse_sgd_cell_v0",
        "consumed_output_causes_update": True,
        "comparator_parity_pass": True,
        "frozen_mutation_count_zero": True,
        "loss": 1.0,
        "loss_pre_update": 1.0,
        "loss_post_update": 0.9,
        "loss_delta": -0.1,
        "grad_norm": 0.25,
        "grad_norm_l2": 0.25,
        "grad_norm_linf": 0.02,
        "update_norm": 0.001,
        "update_norm_l2": 0.001,
        "adapter_delta_norm_l2": 0.001,
        "nan_gradient_count": 0,
        "inf_gradient_count": 0,
        "adapter": {
            "rank": 16,
            "apply_update": True,
            "pre_sha256": "pre",
            "post_sha256": "post",
            "delta_nonzero": True,
        },
        "telemetry": {
            "dispatch_count": 8,
            "profiled_dispatch_count": 8,
            "sync_count": 1,
            "host_device_bytes": 327680,
            "blocking_read_bytes": 1024,
            "kernel_elapsed_ns": 1200000,
            "thermal_stop_band_pass": True,
            "kernel_lineage_class": "fork_and_own_opencl_bridge_cell",
        },
        "raw_payload_rules": {
            "raw_pjp1_pulled_to_host": False,
            "raw_qnn_output_pulled_to_repo": False,
            "raw_model_or_checkpoint_pulled_to_repo": False,
            "repo_paths": ["runtime/reports/polar_phase34_consumer_preflight/active_wave/report.json"],
        },
        "metrics": {
            "phase3/C1_diagnostic/pjp1_preflight_status": "pass",
            "phase3/C1_diagnostic/native_preflight_status": "pass",
            "phase3/C1_diagnostic/i8_oracle_mismatches": 0,
            "phase3/C1_diagnostic/htp_backend": "/data/local/tmp/qairt-2.44/lib/aarch64-android/libQnnHtp.so",
            "phase3/C1_diagnostic/htp_output_sha256": "d29e8cf2a034ade4185ae7a5d1130becb0137395c912825b29ac8c50de3351c6",
            "phase3/C1_diagnostic/forward_loss": 1.0,
            "phase3/C1_diagnostic/forward_mse": 1.0,
            "phase3/C1_diagnostic/forward_cross_entropy": None,
            "phase3/C1_diagnostic/perplexity": None,
            "phase3/C1_diagnostic/answer_token_accuracy": None,
            "phase3/C1_diagnostic/calibration_ece": None,
            "phase3/C1_diagnostic/brier_score": None,
            "phase3/C1_diagnostic/tokens_per_sec": 8000.0,
            "phase3/C1_diagnostic/latency_ms": 2.0,
            "phase3/C1_diagnostic/host_to_device_ms": None,
            "phase3/C1_diagnostic/device_compute_ms": 2.0,
            "phase3/C1_diagnostic/device_to_host_ms": None,
            "phase4/C1_diagnostic/opencl_device": "QUALCOMM Adreno(TM) 830",
            "phase4/C1_diagnostic/phase3_output_sha256": "d29e8cf2a034ade4185ae7a5d1130becb0137395c912825b29ac8c50de3351c6",
            "phase4/C1_diagnostic/target_sha256": "704ffdab04f3b1b585b6246957ad576027a847b2c43367a927a23ef63ee55db7",
            "phase4/C1_diagnostic/adapter_pre_sha256": "pre",
            "phase4/C1_diagnostic/adapter_post_sha256": "post",
            "phase4/C1_diagnostic/consumed_output_causes_update": True,
            "phase4/C1_diagnostic/adapter_changed": True,
            "phase4/C1_diagnostic/loss_pre_update": 1.0,
            "phase4/C1_diagnostic/loss_post_update": 0.99,
            "phase4/C1_diagnostic/loss_delta": -0.01,
            "phase4/C1_diagnostic/grad_norm_l2": 0.25,
            "phase4/C1_diagnostic/grad_norm_linf": 0.02,
            "phase4/C1_diagnostic/update_norm_l2": 0.001,
            "phase4/C1_diagnostic/adapter_delta_norm_l2": 0.001,
            "phase4/C1_diagnostic/nan_gradient_count": 0,
            "phase4/C1_diagnostic/inf_gradient_count": 0,
            "phase4/C1_diagnostic/opencl_kernel_ms": 2.0,
            "phase4/C1_diagnostic/tokens_per_sec": 8000.0,
            "phase4/C1_diagnostic/latency_ms": 2.0,
        },
        "metric_availability": {
            "cross_entropy": "unavailable_for_bounded_polar_mse_bridge",
            "perplexity": "unavailable_without_language_model_likelihood",
            "answer_token_accuracy": "unavailable_without_supervised_answer_token_targets",
            "calibration_ece": "unavailable_without_probability_distribution",
            "brier_score": "unavailable_without_probability_distribution",
            "host_to_device_ms": "not_isolated_in_current_htp_qnn_smoke_report",
            "device_to_host_ms": "not_isolated_in_current_htp_qnn_smoke_report",
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
            "nonclaim": "no C5 evaluation has been run by this Phase3/4 bridge proof",
        },
    }


def report_for_phase(corpus_phase: str) -> dict:
    report = valid_report()
    report["corpus_phase"] = corpus_phase
    rewritten = {}
    for key, value in report["metrics"].items():
        rewritten[key.replace("C1_diagnostic", corpus_phase)] = value
    report["metrics"] = rewritten
    return report


def test_valid_report_passes() -> None:
    assert validate_phase4_bridge_report(valid_report()) == []


def test_rejects_readiness_and_learning_claims() -> None:
    report = valid_report()
    report["phase3_ready_claim"] = True
    report["phase4_ready_claim"] = True
    report["learning_claim"] = True

    blockers = validate_phase4_bridge_report(report)

    assert "phase3_ready_claim_true" in blockers
    assert "phase4_ready_claim_true" in blockers
    assert "learning_claim_true" in blockers


def test_rejects_missing_consumed_output_causality() -> None:
    report = valid_report()
    report["consumed_output_causes_update"] = False

    assert "missing_consumed_output_causality" in validate_phase4_bridge_report(report)


def test_rejects_cpu_update_and_missing_phase3_lineage() -> None:
    report = valid_report()
    report["no_cpu_objective_gradient_update"] = False
    report["phase3_output"].pop("context_sha256")

    blockers = validate_phase4_bridge_report(report)

    assert "cpu_objective_gradient_update_present" in blockers
    assert "missing_phase3_context_sha256" in blockers


def test_rejects_nonfinite_metrics() -> None:
    report = valid_report()
    report["loss"] = float("nan")
    report["grad_norm"] = float("inf")
    report["update_norm"] = -1.0
    report["loss_delta"] = float("nan")

    blockers = validate_phase4_bridge_report(report)

    assert "nonfinite_loss" in blockers
    assert "nonfinite_grad_norm" in blockers
    assert "nonfinite_update_norm" in blockers
    assert "nonfinite_loss_delta" in blockers


def test_rejects_nan_or_inf_gradient_counts() -> None:
    report = valid_report()
    report["nan_gradient_count"] = 1
    report["inf_gradient_count"] = 2

    blockers = validate_phase4_bridge_report(report)

    assert "nan_gradient_count_nonzero" in blockers
    assert "inf_gradient_count_nonzero" in blockers


def test_rejects_raw_payloads_in_repo() -> None:
    report = valid_report()
    report["raw_payload_rules"]["repo_paths"] = ["runtime/reports/bad_output.raw"]

    assert "raw_payload_path_in_repo" in validate_phase4_bridge_report(report)


def test_rejects_unchanged_adapter_after_update() -> None:
    report = valid_report()
    report["adapter"]["post_sha256"] = report["adapter"]["pre_sha256"]

    assert "adapter_hash_unchanged_after_update" in validate_phase4_bridge_report(report)


def test_metric_readiness_accepts_complete_metric_surface() -> None:
    assert validate_phase34_metric_readiness(valid_report()) == []


def test_metric_readiness_accepts_c2_5_metric_namespace() -> None:
    report = report_for_phase("C2_5")

    assert validate_phase34_metric_readiness(report) == []


def test_metric_readiness_rejects_missing_required_metric() -> None:
    report = valid_report()
    del report["metrics"]["phase4/C1_diagnostic/grad_norm_l2"]

    assert "missing_metric:phase4/C1_diagnostic/grad_norm_l2" in validate_phase34_metric_readiness(report)


def test_metric_readiness_requires_availability_for_null_metrics() -> None:
    report = valid_report()
    del report["metric_availability"]["perplexity"]

    blockers = validate_phase34_metric_readiness(report)

    assert "null_metric_without_availability:phase3/C1_diagnostic/perplexity" in blockers


def test_metric_readiness_rejects_unsupported_corpus_phase() -> None:
    report = report_for_phase("C6")

    assert "unsupported_corpus_phase:C6" in validate_phase34_metric_readiness(report)


def test_curriculum_metric_readiness_requires_all_c1_c4_phases() -> None:
    reports = {phase: report_for_phase(phase) for phase in CURRICULUM_CORPUS_PHASES}
    assert validate_phase34_curriculum_metric_readiness(reports) == []

    del reports["C4"]
    assert "missing_corpus_phase_report:C4" in validate_phase34_curriculum_metric_readiness(reports)

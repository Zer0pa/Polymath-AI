from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

from polymath_ai.polar.metrics_contract import flatten_numeric_metrics, metric_report


ROOT = Path(__file__).resolve().parents[1]


def test_flatten_numeric_metrics_skips_strings_bools_and_nulls() -> None:
    payload = {
        "loss": 1.25,
        "nested": {"tokens_per_sec": 42, "status": "pass", "flag": True, "missing": None},
    }

    assert flatten_numeric_metrics("phase4/C1", payload) == {
        "phase4/C1/loss": 1.25,
        "phase4/C1/nested/tokens_per_sec": 42.0,
    }


def test_metric_report_marks_blockers_partial_and_comet_ready() -> None:
    report = metric_report(
        schema_version="test_v1",
        phase_family="phase2",
        corpus_phase="C3",
        metrics={"collision_rate": 0.002, "pjp1_sha256": "abc"},
        blockers=["collision_rate_above_0_001"],
        nonclaims=["diagnostic_only"],
    )

    assert report["status"] == "partial"
    assert report["comet_metric_prefix"] == "phase2/C3"
    assert report["comet_metrics"] == {"phase2/C3/collision_rate": 0.002}
    assert report["nonclaims"] == ["diagnostic_only"]


def test_phase1_metrics_report_job_quantiles_without_claiming_per_record_quantiles() -> None:
    runner = _load_phase1_runner()
    args = argparse.Namespace(corpus_phase="C1")
    records = [
        {"record_id": "r1", "source_kind": "dictionary", "question": "alpha", "answer": "one"},
        {"record_id": "r2", "source_kind": "dictionary", "question": "beta", "answer": "two"},
    ]
    source_identity = {
        "normalized_source_kind_counts": {"dictionary": 2},
        "source_kind_mapping_applied": {"lexatlas": "dictionary"},
    }

    report = runner.build_phase1_metrics(
        args,
        records,
        source_identity,
        app_result={"token_ids": 10, "token_ids_per_sec": 100.0, "records_per_sec": 20.0, "wall_sec": 0.5},
        native_batch_metrics={
            "job_count": 2,
            "elapsed_ns": 250_000_000,
            "token_ids": 10,
            "job_results": [
                {"records": 1, "token_ids": 4},
                {"records": 1, "token_ids": 6},
            ],
        },
    )

    metrics = report["metrics"]
    assert report["status"] == "partial"
    assert metrics["record_count"] == 2
    assert metrics["token_ids_total"] == 10
    assert metrics["tokens_per_record_mean"] == 5.0
    assert metrics["tokens_per_record_p50"] is None
    assert metrics["tokens_per_record_job_p50"] == 4.0
    assert metrics["native_batch_token_ids_per_sec"] == 40.0
    assert metrics["metric_measurement_status"]["tokens_per_record_quantiles"] == "requires_phase1_app_per_record_token_counts"
    assert "per_record_token_distribution_not_reported_by_phase1_app" in report["blockers"]


def test_phase1_metrics_accept_native_true_tokenizer_distribution() -> None:
    runner = _load_phase1_runner()
    args = argparse.Namespace(corpus_phase="C1")
    records = [
        {"record_id": "r1", "source_kind": "dictionary", "question": "alpha", "answer": "one"},
        {"record_id": "r2", "source_kind": "dictionary", "question": "beta", "answer": "two"},
    ]
    source_identity = {"normalized_source_kind_counts": {"dictionary": 2}, "source_kind_mapping_applied": {}}

    report = runner.build_phase1_metrics(
        args,
        records,
        source_identity,
        native_phase1_metrics={
            "records": 2,
            "token_ids": 10,
            "distinct_token_ids": 7,
            "vocab_size": 262144,
            "vocab_coverage_ratio": 7 / 262144,
            "tokens_per_record_mean": 5.0,
            "tokens_per_record_p50": 4.0,
            "tokens_per_record_p95": 6.0,
            "tokens_per_record_p99": 6.0,
            "tokens_per_record_distribution_source": "pqa1_record_headers",
            "wall_sec": 0.25,
            "token_ids_per_sec": 40.0,
            "records_per_sec": 8.0,
        },
    )

    assert report["status"] == "pass"
    assert report["blockers"] == []
    assert report["metrics"]["distinct_token_ids"] == 7
    assert report["metrics"]["vocab_coverage_ratio"] == 7 / 262144
    assert report["metrics"]["tokens_per_record_p95"] == 6.0
    assert report["metrics"]["metric_measurement_status"]["tokens_per_record_quantiles"] == "measured_true_per_record"


def test_phase2_metrics_accept_native_jl_distortion_quality() -> None:
    runner = _load_phase2_runner()
    args = argparse.Namespace(
        corpus_phase="C1",
        dry_run=False,
        packetizer_bin=ROOT / "native/polar_phase2_packetizer/bin/phase2b_native_packetizer",
    )

    report = runner.build_phase2_metrics(
        args,
        native_summary={
            "pqa1_files_consumed": 1,
            "source_record_count": 2,
            "source_real_token_count": 10,
            "packet_count": 2,
            "slot_count": 256,
            "pjp1_bytes": 4096,
            "timing_sec": {"total": 0.5},
            "throughput": {"records_per_sec": 4.0, "real_tokens_per_sec": 20.0, "output_MB_per_sec": 0.01},
            "geometry_quality": {
                "sample_pair_count": 4,
                "jl_distance_distortion_mean": 0.03,
                "jl_distance_distortion_p95": 0.05,
                "measurement_status": "measured_from_original_embedding_rows_and_projected_polar_vectors",
            },
        },
        pjp1_output={"bytes": 4096, "sha256": "a" * 64},
        geometry={
            "status": "pass",
            "blockers": [],
            "collision_rate": 0.0,
            "collision_count": 0,
            "projected_vector_norm_mean": 16.0,
            "projected_vector_norm_p95": 16.0,
            "hamming_distance_mean": 128.0,
            "hamming_distance_p05": 120.0,
            "hamming_distance_p50": 128.0,
            "hamming_distance_p95": 136.0,
            "metric_measurement_status": {"collision_rate": "measured"},
        },
    )

    assert report["status"] == "pass"
    assert report["blockers"] == []
    assert report["metrics"]["jl_distance_distortion_mean"] == 0.03
    assert report["metrics"]["jl_distance_distortion_p95"] == 0.05
    assert report["metrics"]["metric_measurement_status"]["jl_distance_distortion"] == (
        "measured_from_native_packetizer_original_embedding_and_projected_distances"
    )


def _load_phase1_runner():
    path = ROOT / "scripts/android_lab/run_phase1_c1_pipeline_smoke.py"
    spec = importlib.util.spec_from_file_location("phase1_c1_runner_for_tests", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_phase2_runner():
    path = ROOT / "scripts/termux/run_phase2_c1_smoke.py"
    spec = importlib.util.spec_from_file_location("phase2_c1_runner_for_tests", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from polymath_ai.polar.c5_eval import (
    EXECUTED_METRICS_SCHEMA_VERSION,
    build_c5_eval_report,
    capture_git_identity,
    load_json,
    required_metric_names,
    validate_checkpoint_identity,
    validate_eval_split_identity,
)


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/host/run_c5_eval.py"
CHECKPOINT_SHA = "a" * 64
BASELINE_SHA = "b" * 64
EVAL_SPLIT_SHA = "c" * 64


def test_c5_report_blocks_when_checkpoint_identity_missing(tmp_path: Path) -> None:
    report = build_c5_eval_report(
        run_label="unit",
        eval_point="C5_after_C1",
        eval_split_identity=None,
        checkpoint_identity=None,
        stable_baseline_identity=None,
        phase_report_identities={"phase1_report": None, "phase2_report": None, "phase34_report": None},
        executed_metrics=None,
        code_identity=capture_git_identity(ROOT),
        output_path=tmp_path / "c5.json",
        blockers=["checkpoint_identity_path_missing"],
    )

    assert report["pass_fail"]["status"] == "blocked"
    assert report["pass_fail"]["first_missing_or_failing_field"] == "checkpoint_identity_path_missing"
    assert report["expected_identity_schemas"]["checkpoint_identity"]["checkpoint_sha256"] == "<sha256>"
    assert "no_c5_pass_without_executed_local_json" in report["nonclaims"]


def test_checkpoint_identity_rejects_raw_payload_suffix() -> None:
    identity, blockers = validate_checkpoint_identity(
        {
            "checkpoint_role": "candidate",
            "checkpoint_sha256": CHECKPOINT_SHA,
            "checkpoint_payload_location": "outside_git",
            "checkpoint_path": "/tmp/raw_checkpoint.bin",
        },
        role="candidate",
    )

    assert identity is None
    assert "candidate_identity_forbidden_raw_suffix" in blockers


def test_eval_split_identity_allows_hashed_immutable_hf_jsonl_metadata_path() -> None:
    identity, blockers = validate_eval_split_identity(
        {
            "schema_version": "polymath_c5_eval_split_identity_v1",
            "hf_repo_id": "Zer0pa/polymat-gemmalit-c1-c4-commercial-corpus",
            "hf_revision": "1" * 40,
            "hf_revision_is_immutable": True,
            "eval_split_hf_uri": (
                "hf://datasets/Zer0pa/polymat-gemmalit-c1-c4-commercial-corpus/"
                "packages/C1/qa_bridge/phase_C1_test.qa.jsonl"
            ),
            "eval_split_path": "packages/C1/qa_bridge/phase_C1_test.qa.jsonl",
            "eval_split_sha256": EVAL_SPLIT_SHA,
            "material_id": (
                "Zer0pa/polymat-gemmalit-c1-c4-commercial-corpus@"
                "1111111111111111111111111111111111111111:"
                "packages/C1/qa_bridge/phase_C1_test.qa.jsonl"
            ),
            "record_count": 53,
            "sha_stream": [
                {
                    "remote_path": "packages/C1/qa_bridge/phase_C1_test.qa.jsonl",
                    "sha256": EVAL_SPLIT_SHA,
                    "record_count": 53,
                    "status": "pass",
                },
            ],
        },
    )

    assert blockers == []
    assert identity is not None
    assert identity["eval_split_path"].endswith(".jsonl")
    assert identity["hf_revision_is_immutable"] is True


def test_eval_split_identity_rejects_unscoped_raw_jsonl_path() -> None:
    identity, blockers = validate_eval_split_identity(
        {
            "schema_version": "polymath_c5_eval_split_identity_v1",
            "hf_repo_id": "Zer0pa/polymat-gemmalit-c1-c4-commercial-corpus",
            "hf_revision": "1" * 40,
            "hf_revision_is_immutable": True,
            "eval_split_path": "packages/C1/qa_bridge/phase_C1_test.qa.jsonl",
            "eval_split_sha256": EVAL_SPLIT_SHA,
            "record_count": 53,
            "debug_payload_copy": "/tmp/phase_C1_test.qa.jsonl",
        },
    )

    assert identity is None
    assert "c5_material_identity_forbidden_raw_suffix" in blockers


def test_c5_runner_fails_closed_without_executed_metrics_json(tmp_path: Path) -> None:
    inputs = _write_required_inputs(tmp_path)
    output_dir = tmp_path / "out"

    result = subprocess.run(
        [
            "python3.11",
            str(RUNNER),
            "--run-label",
            "unit",
            "--eval-point",
            "C5_after_C1",
            "--eval-split",
            str(inputs["eval_split"]),
            "--checkpoint-identity",
            str(inputs["checkpoint"]),
            "--stable-baseline-identity",
            str(inputs["baseline"]),
            "--phase1-report",
            str(inputs["phase1_report"]),
            "--phase2-report",
            str(inputs["phase2_report"]),
            "--phase34-report",
            str(inputs["phase34_report"]),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    runner_stdout = json.loads(result.stdout)
    report = load_json(Path(runner_stdout["report_path"]))
    assert report["pass_fail"]["status"] == "blocked"
    assert "executed_c5_metrics_json_missing" in report["blockers"]


def test_c5_runner_prints_identity_schema_without_run_arguments() -> None:
    result = subprocess.run(
        ["python3.11", str(RUNNER), "--print-identity-schema"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    schema = json.loads(result.stdout)
    assert schema["checkpoint_identity"]["checkpoint_sha256"] == "<sha256>"
    assert schema["stable_baseline_identity"]["stable_checkpoint_baseline_sha256"] == "<sha256>"


def test_c5_runner_comet_metric_names_match_executed_local_json(tmp_path: Path) -> None:
    inputs = _write_required_inputs(tmp_path)
    metrics_path = tmp_path / "executed_metrics.json"
    metric_names = required_metric_names("C5_after_C1")
    metrics = {name: 0.0 for name in metric_names}
    metrics["c5/C5_after_C1/checkpoint_sha256"] = CHECKPOINT_SHA
    metrics["c5/C5_after_C1/stable_checkpoint_baseline_sha256"] = BASELINE_SHA
    metrics["c5/C5_after_C1/accuracy"] = 1.0
    metrics["c5/C5_after_C1/answer_exact_match"] = 1.0
    metrics["c5/C5_after_C1/answer_token_f1"] = 1.0
    _write_json(metrics_path, {
        "schema_version": EXECUTED_METRICS_SCHEMA_VERSION,
        "executed_local_json": True,
        "metrics": metrics,
    })

    output_dir = tmp_path / "out"
    result = subprocess.run(
        [
            "python3.11",
            str(RUNNER),
            "--run-label",
            "unit",
            "--eval-point",
            "C5_after_C1",
            "--eval-split",
            str(inputs["eval_split"]),
            "--checkpoint-identity",
            str(inputs["checkpoint"]),
            "--stable-baseline-identity",
            str(inputs["baseline"]),
            "--phase1-report",
            str(inputs["phase1_report"]),
            "--phase2-report",
            str(inputs["phase2_report"]),
            "--phase34-report",
            str(inputs["phase34_report"]),
            "--metrics-json",
            str(metrics_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    runner_stdout = json.loads(result.stdout)
    report = load_json(Path(runner_stdout["report_path"]))
    assert report["pass_fail"]["status"] == "pass"
    assert report["comet_identity"]["authorized"] is False
    assert report["comet_identity"]["remote_comet_called"] is False
    assert report["comet_identity"]["metric_names_match_local_json"] is True
    assert report["comet_identity"]["metric_names"] == sorted(metric_names)


def test_c5_runner_blocks_mismatched_checkpoint_metric(tmp_path: Path) -> None:
    inputs = _write_required_inputs(tmp_path)
    metrics_path = tmp_path / "executed_metrics.json"
    metrics = {name: 0.0 for name in required_metric_names("C5_after_C1")}
    metrics["c5/C5_after_C1/checkpoint_sha256"] = "d" * 64
    metrics["c5/C5_after_C1/stable_checkpoint_baseline_sha256"] = BASELINE_SHA
    _write_json(metrics_path, {
        "schema_version": EXECUTED_METRICS_SCHEMA_VERSION,
        "executed_local_json": True,
        "metrics": metrics,
    })

    output_dir = tmp_path / "out"
    result = subprocess.run(
        [
            "python3.11",
            str(RUNNER),
            "--run-label",
            "unit",
            "--eval-point",
            "C5_after_C1",
            "--eval-split",
            str(inputs["eval_split"]),
            "--checkpoint-identity",
            str(inputs["checkpoint"]),
            "--stable-baseline-identity",
            str(inputs["baseline"]),
            "--phase1-report",
            str(inputs["phase1_report"]),
            "--phase2-report",
            str(inputs["phase2_report"]),
            "--phase34-report",
            str(inputs["phase34_report"]),
            "--metrics-json",
            str(metrics_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    report = load_json(Path(json.loads(result.stdout)["report_path"]))
    assert report["pass_fail"]["status"] == "blocked"
    assert "executed_metric_checkpoint_sha256_mismatch" in report["blockers"]


def _write_required_inputs(tmp_path: Path) -> dict[str, Path]:
    eval_split = tmp_path / "eval_split.json"
    checkpoint = tmp_path / "checkpoint_identity.json"
    baseline = tmp_path / "baseline_identity.json"
    phase1_report = tmp_path / "phase1_report.json"
    phase2_report = tmp_path / "phase2_report.json"
    phase34_report = tmp_path / "phase34_report.json"

    _write_json(eval_split, {
        "schema_version": "polymath_c5_eval_split_identity_v1",
        "hf_repo_id": "Zer0pa/polymat-gemmalit-c1-c4-commercial-corpus",
        "hf_revision": "1" * 40,
        "hf_revision_is_immutable": True,
        "eval_split_hf_uri": (
            "hf://datasets/Zer0pa/polymat-gemmalit-c1-c4-commercial-corpus/"
            "packages/C1/qa_bridge/phase_C1_test.qa.jsonl"
        ),
        "eval_split_path": "packages/C1/qa_bridge/phase_C1_test.qa.jsonl",
        "eval_split_sha256": EVAL_SPLIT_SHA,
        "material_id": (
            "Zer0pa/polymat-gemmalit-c1-c4-commercial-corpus@"
            "1111111111111111111111111111111111111111:"
            "packages/C1/qa_bridge/phase_C1_test.qa.jsonl"
        ),
        "record_count": 3,
        "sha_stream": [
            {
                "remote_path": "packages/C1/qa_bridge/phase_C1_test.qa.jsonl",
                "sha256": EVAL_SPLIT_SHA,
                "record_count": 3,
                "status": "pass",
            },
        ],
    })
    _write_json(checkpoint, {
        "schema_version": "polymath_checkpoint_identity_v1",
        "checkpoint_role": "candidate",
        "checkpoint_sha256": CHECKPOINT_SHA,
        "checkpoint_payload_location": "outside_git",
        "produced_by_phase": "C1",
    })
    _write_json(baseline, {
        "schema_version": "polymath_checkpoint_identity_v1",
        "checkpoint_role": "stable_baseline",
        "stable_checkpoint_baseline_sha256": BASELINE_SHA,
        "checkpoint_payload_location": "outside_git",
    })
    for path in (phase1_report, phase2_report, phase34_report):
        _write_json(path, {"schema_version": "unit_phase_report_v1", "status": "pass"})
    return {
        "eval_split": eval_split,
        "checkpoint": checkpoint,
        "baseline": baseline,
        "phase1_report": phase1_report,
        "phase2_report": phase2_report,
        "phase34_report": phase34_report,
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

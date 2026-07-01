from __future__ import annotations

import json
import subprocess
from pathlib import Path

from polymath_ai.polar.c5_eval import load_json, required_metric_names, scan_forbidden_raw_suffixes, sha256_file


ROOT = Path(__file__).resolve().parents[1]
HELDOUT_RUNNER = ROOT / "scripts/host/run_c5_heldout_eval.py"
C5_REPORT_RUNNER = ROOT / "scripts/host/run_c5_eval.py"
CHECKPOINT_SHA = "a" * 64
BASELINE_SHA = "b" * 64


def test_c5_heldout_runner_produces_validator_compatible_executed_metrics(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    output_dir = tmp_path / "metrics_out"

    result = subprocess.run(
        [
            "python3.11",
            str(HELDOUT_RUNNER),
            "--run-label",
            "unit",
            "--eval-point",
            "C5_after_C1",
            "--eval-split-identity",
            str(inputs["eval_split_identity"]),
            "--checkpoint-identity",
            str(inputs["checkpoint_identity"]),
            "--stable-baseline-identity",
            str(inputs["baseline_identity"]),
            "--heldout-qa-jsonl",
            str(inputs["heldout"]),
            "--candidate-predictions-jsonl",
            str(inputs["candidate_predictions"]),
            "--stable-baseline-predictions-jsonl",
            str(inputs["baseline_predictions"]),
            "--candidate-train-loss",
            "0.55",
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

    assert result.returncode == 0, result.stderr
    stdout = json.loads(result.stdout)
    metrics_path = Path(stdout["output_path"])
    metrics_payload = load_json(metrics_path)
    assert metrics_payload["schema_version"] == "polymath_c5_executed_metrics_v1"
    assert metrics_payload["executed_local_json"] is True
    assert sorted(metrics_payload["metrics"]) == sorted(required_metric_names("C5_after_C1"))
    assert metrics_payload["metrics"]["c5/C5_after_C1/checkpoint_sha256"] == CHECKPOINT_SHA
    assert metrics_payload["metrics"]["c5/C5_after_C1/stable_checkpoint_baseline_sha256"] == BASELINE_SHA
    assert metrics_payload["metrics"]["c5/C5_after_C1/loss_delta_vs_last_stable"] < 0.0
    assert scan_forbidden_raw_suffixes(metrics_payload) == []

    report_dir = tmp_path / "c5_report"
    report_result = subprocess.run(
        [
            "python3.11",
            str(C5_REPORT_RUNNER),
            "--run-label",
            "unit",
            "--eval-point",
            "C5_after_C1",
            "--eval-split",
            str(inputs["eval_split_identity"]),
            "--checkpoint-identity",
            str(inputs["checkpoint_identity"]),
            "--stable-baseline-identity",
            str(inputs["baseline_identity"]),
            "--phase1-report",
            str(inputs["phase1_report"]),
            "--phase2-report",
            str(inputs["phase2_report"]),
            "--phase34-report",
            str(inputs["phase34_report"]),
            "--metrics-json",
            str(metrics_path),
            "--output-dir",
            str(report_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert report_result.returncode == 0, report_result.stderr
    report = load_json(Path(json.loads(report_result.stdout)["report_path"]))
    assert report["pass_fail"]["status"] == "pass"
    assert report["comet_identity"]["metric_names_match_local_json"] is True


def test_c5_heldout_runner_fails_closed_when_prediction_loss_missing(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path, candidate_missing_loss=True)
    output_dir = tmp_path / "metrics_out"

    result = subprocess.run(
        [
            "python3.11",
            str(HELDOUT_RUNNER),
            "--run-label",
            "unit",
            "--eval-point",
            "C5_after_C1",
            "--eval-split-identity",
            str(inputs["eval_split_identity"]),
            "--checkpoint-identity",
            str(inputs["checkpoint_identity"]),
            "--stable-baseline-identity",
            str(inputs["baseline_identity"]),
            "--heldout-qa-jsonl",
            str(inputs["heldout"]),
            "--candidate-predictions-jsonl",
            str(inputs["candidate_predictions"]),
            "--stable-baseline-predictions-jsonl",
            str(inputs["baseline_predictions"]),
            "--candidate-train-loss",
            "0.55",
            "--grad-norm-max-observed",
            "0.01",
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    stdout = json.loads(result.stdout)
    blocker = load_json(Path(stdout["output_path"]))
    assert blocker["status"] == "blocked"
    assert blocker["executed_metrics_json_written"] is False
    assert any("candidate_predictions_loss_missing_or_nonfinite" in item for item in blocker["blockers"])
    assert scan_forbidden_raw_suffixes(blocker) == []


def test_c5_heldout_runner_rejects_raw_input_inside_repo(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    repo_raw = ROOT / "runtime/reports/c5_heldout_eval_unit_raw_predictions.jsonl"
    repo_raw.write_text(
        json.dumps({"record_id": "r1", "prediction": "alpha beta", "loss": 0.2, "confidence": 0.9}) + "\n",
        encoding="utf-8",
    )
    try:
        result = subprocess.run(
            [
                "python3.11",
                str(HELDOUT_RUNNER),
                "--run-label",
                "unit",
                "--eval-point",
                "C5_after_C1",
                "--eval-split-identity",
                str(inputs["eval_split_identity"]),
                "--checkpoint-identity",
                str(inputs["checkpoint_identity"]),
                "--stable-baseline-identity",
                str(inputs["baseline_identity"]),
                "--heldout-qa-jsonl",
                str(inputs["heldout"]),
                "--candidate-predictions-jsonl",
                str(repo_raw),
                "--stable-baseline-predictions-jsonl",
                str(inputs["baseline_predictions"]),
                "--candidate-train-loss",
                "0.55",
                "--grad-norm-max-observed",
                "0.01",
                "--output-dir",
                str(tmp_path / "metrics_out"),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        repo_raw.unlink(missing_ok=True)

    assert result.returncode == 2
    blocker = load_json(Path(json.loads(result.stdout)["output_path"]))
    assert any("candidate_predictions_raw_payload_path_inside_repo" in item for item in blocker["blockers"])


def _write_inputs(tmp_path: Path, *, candidate_missing_loss: bool = False) -> dict[str, Path]:
    heldout = tmp_path / "phase_C1_test.qa.jsonl"
    _write_jsonl(
        heldout,
        [
            {"record_id": "r1", "question": "Q1", "answer": "alpha beta"},
            {"record_id": "r2", "question": "Q2", "answer": "gamma"},
            {"record_id": "r3", "question": "Q3", "answer": "delta"},
        ],
    )
    heldout_sha = sha256_file(heldout)

    candidate_rows = [
        {"record_id": "r1", "prediction": "alpha beta", "loss": 0.2, "confidence": 0.9, "token_count": 2},
        {"record_id": "r2", "prediction": "gamma", "loss": 0.3, "confidence": 0.8, "token_count": 1},
        {"record_id": "r3", "prediction": "wrong", "loss": 1.2, "confidence": 0.4, "token_count": 1},
    ]
    if candidate_missing_loss:
        candidate_rows[0].pop("loss")

    candidate_predictions = tmp_path / "candidate_predictions.jsonl"
    baseline_predictions = tmp_path / "baseline_predictions.jsonl"
    _write_jsonl(candidate_predictions, candidate_rows)
    _write_jsonl(
        baseline_predictions,
        [
            {"record_id": "r1", "prediction": "alpha", "loss": 0.8, "confidence": 0.5, "token_count": 2},
            {"record_id": "r2", "prediction": "wrong", "loss": 0.9, "confidence": 0.6, "token_count": 1},
            {"record_id": "r3", "prediction": "wrong", "loss": 1.6, "confidence": 0.5, "token_count": 1},
        ],
    )

    eval_split_identity = tmp_path / "eval_split_identity.json"
    checkpoint_identity = tmp_path / "checkpoint_identity.json"
    baseline_identity = tmp_path / "baseline_identity.json"
    phase1_report = tmp_path / "phase1_report.json"
    phase2_report = tmp_path / "phase2_report.json"
    phase34_report = tmp_path / "phase34_report.json"

    _write_json(
        eval_split_identity,
        {
            "schema_version": "polymath_c5_eval_split_identity_v1",
            "hf_repo_id": "Zer0pa/polymat-gemmalit-c1-c4-commercial-corpus",
            "hf_revision": "1" * 40,
            "hf_revision_is_immutable": True,
            "eval_split_path": "packages/C1/qa_bridge/phase_C1_test.qa.jsonl",
            "eval_split_sha256": heldout_sha,
            "record_count": 3,
        },
    )
    _write_json(
        checkpoint_identity,
        {
            "schema_version": "polymath_checkpoint_identity_v1",
            "checkpoint_role": "candidate",
            "checkpoint_sha256": CHECKPOINT_SHA,
            "checkpoint_payload_location": "outside_git",
            "produced_by_phase": "C1",
        },
    )
    _write_json(
        baseline_identity,
        {
            "schema_version": "polymath_checkpoint_identity_v1",
            "checkpoint_role": "stable_baseline",
            "stable_checkpoint_baseline_sha256": BASELINE_SHA,
            "checkpoint_payload_location": "outside_git",
        },
    )
    _write_json(phase1_report, {"schema_version": "unit_phase_report_v1", "status": "pass"})
    _write_json(phase2_report, {"schema_version": "unit_phase_report_v1", "status": "pass"})
    _write_json(phase34_report, {"schema_version": "unit_phase34_report_v1", "grad_norm_l2": 0.01})

    return {
        "heldout": heldout,
        "candidate_predictions": candidate_predictions,
        "baseline_predictions": baseline_predictions,
        "eval_split_identity": eval_split_identity,
        "checkpoint_identity": checkpoint_identity,
        "baseline_identity": baseline_identity,
        "phase1_report": phase1_report,
        "phase2_report": phase2_report,
        "phase34_report": phase34_report,
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")

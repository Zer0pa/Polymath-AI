from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

from polymath_ai.polar.c5_eval import load_json, sha256_file


ROOT = Path(__file__).resolve().parents[1]
PREDICTION_RUNNER = ROOT / "scripts/host/run_c5_prediction_payloads.py"
SCORER_RUNNER = ROOT / "scripts/host/run_c5_heldout_eval.py"


def test_c5_prediction_contract_prints_without_run_arguments() -> None:
    result = subprocess.run(
        ["python3.11", str(PREDICTION_RUNNER), "--print-contract"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    contract = json.loads(result.stdout)
    assert contract["schema_version"] == "polymath_c5_prediction_payload_producer_contract_v1"
    assert contract["producer_command_protocol"]["required_prediction_jsonl_row_schema"]["required_fields"]["loss"]


def test_c5_prediction_contract_only_fails_closed(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            "python3.11",
            str(PREDICTION_RUNNER),
            "--run-label",
            "unit",
            "--eval-point",
            "C5_after_C1",
            "--metadata-output-dir",
            str(tmp_path / "metadata"),
            "--contract-only",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    stdout = json.loads(result.stdout)
    report = load_json(Path(stdout["report_path"]))
    assert report["status"] == "blocked"
    assert report["first_missing_green_field"] == "producer_runtime_not_requested_contract_only"
    assert "producer_runtime_not_requested_contract_only" in report["blockers"]


def test_c5_prediction_payload_runner_generates_valid_scorer_inputs(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    producer = _write_stub_producer(tmp_path)
    prediction_root = tmp_path / "predictions"
    metadata_dir = tmp_path / "metadata"

    result = subprocess.run(
        [
            "python3.11",
            str(PREDICTION_RUNNER),
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
            "--candidate-checkpoint-payload",
            str(inputs["candidate_payload"]),
            "--stable-baseline-checkpoint-payload",
            str(inputs["baseline_payload"]),
            "--prediction-output-root",
            str(prediction_root),
            "--metadata-output-dir",
            str(metadata_dir),
            "--producer-command",
            f"python3.11 {producer}",
            "--candidate-train-loss",
            "0.4",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    stdout = json.loads(result.stdout)
    report = load_json(Path(stdout["report_path"]))
    assert report["status"] == "pass"
    assert report["prediction_output_validation"]["candidate_prediction_count"] == 3
    assert report["prediction_output_validation"]["stable_baseline_prediction_count"] == 3
    assert report["candidate_payload_identity"]["sha256"] == inputs["candidate_sha"]
    assert report["stable_baseline_payload_identity"]["sha256"] == inputs["baseline_sha"]

    scorer_dir = tmp_path / "scorer"
    scorer = subprocess.run(
        [
            "python3.11",
            str(SCORER_RUNNER),
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
            str(prediction_root / "candidate_predictions.jsonl"),
            "--stable-baseline-predictions-jsonl",
            str(prediction_root / "stable_baseline_predictions.jsonl"),
            "--candidate-train-loss",
            "0.4",
            "--grad-norm-max-observed",
            "0.01",
            "--output-dir",
            str(scorer_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert scorer.returncode == 0, scorer.stderr
    metrics = load_json(Path(json.loads(scorer.stdout)["output_path"]))
    assert metrics["metrics"]["c5/C5_after_C1/loss_delta_vs_last_stable"] < 0.0
    assert metrics["metrics"]["c5/C5_after_C1/learning_score"] > 0.0


def test_c5_prediction_payload_runner_rejects_missing_candidate_record_ids_before_scorer(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path)
    producer = _write_candidate_first_row_only_producer(tmp_path)

    result = subprocess.run(
        [
            "python3.11",
            str(PREDICTION_RUNNER),
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
            "--candidate-checkpoint-payload",
            str(inputs["candidate_payload"]),
            "--stable-baseline-checkpoint-payload",
            str(inputs["baseline_payload"]),
            "--prediction-output-root",
            str(tmp_path / "predictions"),
            "--metadata-output-dir",
            str(tmp_path / "metadata"),
            "--producer-command",
            f"python3.11 {producer}",
            "--candidate-train-loss",
            "0.4",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    report = load_json(Path(json.loads(result.stdout)["report_path"]))
    assert report["status"] == "blocked"
    assert report["first_missing_green_field"] == "ValueError:candidate_predictions_missing_record_ids"
    assert "ValueError:candidate_predictions_missing_record_ids" in report["blockers"]
    assert report["prediction_output_validation"] is None


def test_native_c5_runtime_iterates_heldout_records_for_prediction_payloads() -> None:
    source = (
        ROOT
        / "integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/backends/c5_full_decoder_runtime.cpp"
    ).read_text(encoding="utf-8")
    header = (
        ROOT
        / "integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/include/polymath/gemma4/c5_full_decoder_runtime.h"
    ).read_text(encoding="utf-8")
    inference_source = (
        ROOT
        / "integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/backends/c5_qa_inference.cpp"
    ).read_text(encoding="utf-8")

    assert "read_qa_jsonl_records" in source
    assert "first_nonempty_jsonl_line" not in source
    assert "for (const QaRecord& record : qa_records)" in source
    assert "c5_full_decoder_prediction_jsonl_record_count_mismatch" in source
    assert "prediction_record_count" in header
    assert "prediction_record_count_matches_heldout" in inference_source


def test_c5_prediction_payload_runner_rejects_checkpoint_hash_mismatch(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    producer = _write_stub_producer(tmp_path)
    inputs["candidate_payload"].write_text("drifted", encoding="utf-8")

    result = subprocess.run(
        [
            "python3.11",
            str(PREDICTION_RUNNER),
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
            "--candidate-checkpoint-payload",
            str(inputs["candidate_payload"]),
            "--stable-baseline-checkpoint-payload",
            str(inputs["baseline_payload"]),
            "--prediction-output-root",
            str(tmp_path / "predictions"),
            "--metadata-output-dir",
            str(tmp_path / "metadata"),
            "--producer-command",
            f"python3.11 {producer}",
            "--candidate-train-loss",
            "0.4",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    report = load_json(Path(json.loads(result.stdout)["report_path"]))
    assert report["status"] == "blocked"
    assert any("candidate_checkpoint_payload_sha256_mismatch" in item for item in report["blockers"])


def _write_inputs(tmp_path: Path) -> dict[str, object]:
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

    candidate_payload = tmp_path / "candidate_adapter_payload.raw"
    baseline_payload = tmp_path / "stable_baseline_adapter_payload.raw"
    candidate_payload.write_text("candidate", encoding="utf-8")
    baseline_payload.write_text("stable", encoding="utf-8")
    candidate_sha = sha256_file(candidate_payload)
    baseline_sha = sha256_file(baseline_payload)

    eval_split_identity = tmp_path / "eval_split_identity.json"
    checkpoint_identity = tmp_path / "checkpoint_identity.json"
    baseline_identity = tmp_path / "baseline_identity.json"
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
            "checkpoint_sha256": candidate_sha,
            "checkpoint_payload_location": "outside_git",
            "produced_by_phase": "C1",
        },
    )
    _write_json(
        baseline_identity,
        {
            "schema_version": "polymath_checkpoint_identity_v1",
            "checkpoint_role": "stable_baseline",
            "stable_checkpoint_baseline_sha256": baseline_sha,
            "checkpoint_payload_location": "outside_git",
        },
    )
    return {
        "heldout": heldout,
        "candidate_payload": candidate_payload,
        "baseline_payload": baseline_payload,
        "candidate_sha": candidate_sha,
        "baseline_sha": baseline_sha,
        "eval_split_identity": eval_split_identity,
        "checkpoint_identity": checkpoint_identity,
        "baseline_identity": baseline_identity,
    }


def _write_stub_producer(tmp_path: Path) -> Path:
    script = tmp_path / "stub_c5_prediction_producer.py"
    script.write_text(
        textwrap.dedent(
            """\
            import argparse
            import json

            parser = argparse.ArgumentParser()
            parser.add_argument("--run-label")
            parser.add_argument("--eval-point")
            parser.add_argument("--checkpoint-role")
            parser.add_argument("--checkpoint-payload")
            parser.add_argument("--checkpoint-sha256")
            parser.add_argument("--heldout-qa-jsonl")
            parser.add_argument("--output-jsonl")
            args = parser.parse_args()

            with open(args.heldout_qa_jsonl, "r", encoding="utf-8") as handle:
                rows = [json.loads(line) for line in handle if line.strip()]
            with open(args.output_jsonl, "w", encoding="utf-8") as handle:
                for row in rows:
                    if args.checkpoint_role == "candidate":
                        prediction = row["answer"]
                        loss = 0.2
                        confidence = 0.9
                    else:
                        prediction = "incorrect"
                        loss = 0.9
                        confidence = 0.2
                    handle.write(json.dumps({
                        "record_id": row["record_id"],
                        "prediction": prediction,
                        "loss": loss,
                        "confidence": confidence,
                        "token_count": max(1, len(row["answer"].split())),
                    }, sort_keys=True) + "\\n")
            """
        ),
        encoding="utf-8",
    )
    return script


def _write_candidate_first_row_only_producer(tmp_path: Path) -> Path:
    script = tmp_path / "candidate_first_row_only_c5_prediction_producer.py"
    script.write_text(
        textwrap.dedent(
            """\
            import argparse
            import json

            parser = argparse.ArgumentParser()
            parser.add_argument("--run-label")
            parser.add_argument("--eval-point")
            parser.add_argument("--checkpoint-role")
            parser.add_argument("--checkpoint-payload")
            parser.add_argument("--checkpoint-sha256")
            parser.add_argument("--heldout-qa-jsonl")
            parser.add_argument("--output-jsonl")
            args = parser.parse_args()

            with open(args.heldout_qa_jsonl, "r", encoding="utf-8") as handle:
                rows = [json.loads(line) for line in handle if line.strip()]
            if args.checkpoint_role == "candidate":
                rows = rows[:1]
            with open(args.output_jsonl, "w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps({
                        "record_id": row["record_id"],
                        "prediction": row["answer"],
                        "loss": 0.2,
                        "confidence": 0.9,
                        "token_count": max(1, len(row["answer"].split())),
                    }, sort_keys=True) + "\\n")
            """
        ),
        encoding="utf-8",
    )
    return script


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")

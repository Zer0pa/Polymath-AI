from __future__ import annotations

import hashlib
import json
import subprocess
import textwrap
from pathlib import Path

from polymath_ai.polar.c5_eval import sha256_file


ROOT = Path(__file__).resolve().parents[1]
PRODUCER = ROOT / "scripts/host/run_c5_phase34_qa_inference_producer.py"


def test_phase34_qa_producer_prints_wrapper_compatible_contract() -> None:
    result = subprocess.run(
        ["python3.11", str(PRODUCER), "--print-contract"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    contract = json.loads(result.stdout)
    assert contract["schema_version"] == "polymath_c5_phase34_qa_inference_producer_report_v1"
    assert "--checkpoint-payload" in contract["wrapper_appended_args"]
    assert "lm_head_or_unembedding_missing" in contract["fail_closed_missing_runtime_fields"]


def test_phase34_qa_producer_fails_closed_when_native_runtime_blocks(tmp_path: Path) -> None:
    runner = _write_blocking_native_runner(tmp_path)
    heldout = tmp_path / "phase_C1_test.qa.jsonl"
    heldout.write_text(
        json.dumps({"record_id": "r1", "question": "q", "answer": "a"}) + "\n",
        encoding="utf-8",
    )
    checkpoint = tmp_path / "adapter_post_rank16.f32.bin"
    checkpoint.write_bytes(b"candidate-adapter")
    output_jsonl = tmp_path / "predictions/candidate_predictions.jsonl"

    result = subprocess.run(
        [
            "python3.11",
            str(PRODUCER),
            "--gemma4-runner",
            str(runner),
            "--run-label",
            "unit",
            "--eval-point",
            "C5_after_C1",
            "--checkpoint-role",
            "candidate",
            "--checkpoint-payload",
            str(checkpoint),
            "--checkpoint-sha256",
            sha256_file(checkpoint),
            "--heldout-qa-jsonl",
            str(heldout),
            "--output-jsonl",
            str(output_jsonl),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 13
    stdout = json.loads(result.stdout)
    assert stdout["status"] == "blocked"
    assert stdout["first_missing_green_field"] == "tokenizer_dir_missing"
    assert not output_jsonl.exists()

    report = json.loads(
        output_jsonl.with_name(
            f"{output_jsonl.name}.phase34_qa_producer_report.json"
        ).read_text(encoding="utf-8")
    )
    assert report["first_missing_green_field"] == "tokenizer_dir_missing"
    assert report["native_report"]["raw_boundary_proof"]["prediction_jsonl_written"] is False
    assert report["checkpoint_payload_identity"]["actual_sha256"] == sha256_file(checkpoint)


def test_phase34_qa_producer_rejects_checkpoint_hash_before_native_run(tmp_path: Path) -> None:
    runner = _write_blocking_native_runner(tmp_path)
    heldout = tmp_path / "phase_C1_test.qa.jsonl"
    heldout.write_text(
        json.dumps({"record_id": "r1", "question": "q", "answer": "a"}) + "\n",
        encoding="utf-8",
    )
    checkpoint = tmp_path / "adapter_post_rank16.f32.bin"
    checkpoint.write_bytes(b"candidate-adapter")
    output_jsonl = tmp_path / "predictions/candidate_predictions.jsonl"

    result = subprocess.run(
        [
            "python3.11",
            str(PRODUCER),
            "--gemma4-runner",
            str(runner),
            "--run-label",
            "unit",
            "--eval-point",
            "C5_after_C1",
            "--checkpoint-role",
            "candidate",
            "--checkpoint-payload",
            str(checkpoint),
            "--checkpoint-sha256",
            "not-a-sha",
            "--heldout-qa-jsonl",
            str(heldout),
            "--output-jsonl",
            str(output_jsonl),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["first_missing_green_field"] == "checkpoint_sha256_invalid"
    assert not (tmp_path / "native_invoked").exists()


def test_phase34_qa_producer_rejects_invalid_runtime_component_paths_before_native_run(
    tmp_path: Path,
) -> None:
    runner = _write_blocking_native_runner(tmp_path)
    heldout = tmp_path / "phase_C1_test.qa.jsonl"
    heldout.write_text(
        json.dumps({"record_id": "r1", "question": "q", "answer": "a"}) + "\n",
        encoding="utf-8",
    )
    checkpoint = tmp_path / "adapter_post_rank16.f32.bin"
    checkpoint.write_bytes(b"candidate-adapter")
    output_jsonl = tmp_path / "predictions/candidate_predictions.jsonl"

    result = subprocess.run(
        [
            "python3.11",
            str(PRODUCER),
            "--gemma4-runner",
            str(runner),
            "--tokenizer-dir",
            str(tmp_path / "missing_tokenizer"),
            "--run-label",
            "unit",
            "--eval-point",
            "C5_after_C1",
            "--checkpoint-role",
            "candidate",
            "--checkpoint-payload",
            str(checkpoint),
            "--checkpoint-sha256",
            sha256_file(checkpoint),
            "--heldout-qa-jsonl",
            str(heldout),
            "--output-jsonl",
            str(output_jsonl),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["first_missing_green_field"] == "tokenizer_dir_path_not_found"
    assert not output_jsonl.exists()
    assert not (tmp_path / "native_invoked").exists()


def _write_blocking_native_runner(tmp_path: Path) -> Path:
    runner = tmp_path / "gemma4_layer_runner_stub.py"
    runner.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import hashlib
            import json
            import sys
            from pathlib import Path

            Path(sys.argv[0]).with_name("native_invoked").write_text("1", encoding="utf-8")
            args = sys.argv[1:]
            assert args[0] == "--run-c5-qa-predict"
            values = {}
            index = 1
            while index < len(args):
                values[args[index]] = args[index + 1]
                index += 2
            checkpoint = Path(values["--checkpoint-payload"])
            heldout = Path(values["--heldout-qa-jsonl"])
            report = {
                "schema_version": "polymath_c5_qa_inference_native_report_v1",
                "status": "blocked",
                "first_missing_green_field": "tokenizer_dir_missing",
                "blockers": [
                    "tokenizer_dir_missing",
                    "decoder_manifest_missing",
                    "lm_head_or_unembedding_missing",
                    "adapter_site_policy_missing",
                ],
                "checkpoint_payload_identity": {
                    "actual_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                    "path_redacted": True,
                },
                "heldout_qa_identity": {
                    "sha256": hashlib.sha256(heldout.read_bytes()).hexdigest(),
                    "path_redacted": True,
                },
                "raw_boundary_proof": {
                    "raw_payload_bytes_in_report": False,
                    "prediction_jsonl_written": False,
                    "checkpoint_payload_copied_to_repo": False,
                },
            }
            print(json.dumps(report, sort_keys=True))
            sys.exit(13)
            """
        ),
        encoding="utf-8",
    )
    runner.chmod(0o755)
    return runner

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


def test_phase34_qa_producer_rejects_two_layer_decoder_manifest_before_native_run(
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
    tokenizer = tmp_path / "tokenizer"
    tokenizer.mkdir()
    (tokenizer / "vocab.hex.tsv").write_text("61\t1\n", encoding="utf-8")
    (tokenizer / "merges.hex.tsv").write_text("", encoding="utf-8")
    decoder_manifest = tmp_path / "decoder_manifest.json"
    decoder_manifest.write_text(
        json.dumps(
            {
                "schema_version": "layer_bundle_v1",
                "model_id": "google/gemma-4-E4B",
                "decoder": {"num_hidden_layers": 2},
            }
        ),
        encoding="utf-8",
    )
    adapter_policy = _write_valid_adapter_policy(tmp_path)
    lm_head = tmp_path / "lm_head.bf16"
    lm_head.write_bytes(b"lm-head-placeholder")

    result = subprocess.run(
        [
            "python3.11",
            str(PRODUCER),
            "--gemma4-runner",
            str(runner),
            "--tokenizer-dir",
            str(tokenizer),
            "--decoder-manifest",
            str(decoder_manifest),
            "--lm-head",
            str(lm_head),
            "--adapter-site-policy",
            str(adapter_policy),
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
    first_missing = json.loads(result.stdout)["first_missing_green_field"]
    assert first_missing == "decoder_manifest_schema_version_mismatch"
    assert not output_jsonl.exists()
    assert not (tmp_path / "native_invoked").exists()


def _write_valid_adapter_policy(tmp_path: Path) -> Path:
    path = tmp_path / "adapter_policy.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "polymath_c5_adapter_site_policy_v1",
                "model_id": "google/gemma-4-E4B",
                "adapter_rank": 16,
                "decoder_layer_index": 1,
                "adapter_site": "post_layer1_residual",
                "input_shape": [1, 16, 2560],
                "output_shape": [1, 16, 2560],
                "candidate_adapter_sha256": "1ba7faed815cec7e802bb297d4056934f81eae51be93f38a98f915fbaa94d78f",
                "stable_baseline_adapter_sha256": "e0d1c66ac876c2b6fbbe9e88f1b02dd37201d8ffba10afcd44f1c558fc32f7c9",
                "bridge_mse_is_c5_loss": False,
            }
        ),
        encoding="utf-8",
    )
    return path


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

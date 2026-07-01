"""C5 prediction-payload producer contract.

The C5 scorer needs candidate and stable-baseline prediction JSONL. This module
does not infer from metadata and does not implement a model. It validates the
runtime contract for a real producer command, executes it when supplied, and
fails closed when checkpoint payloads or producer runtime are absent.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

from polymath_ai.polar.c5_eval import (
    EVAL_POINTS,
    FORBIDDEN_RAW_SUFFIXES,
    NONCLAIMS,
    is_finite_number,
    is_sha256,
    require_eval_point,
    sha256_file,
)
from polymath_ai.polar.c5_heldout_eval import (
    assert_prediction_coverage,
    load_heldout_records,
    load_prediction_records,
    load_validated_identity_inputs,
    safe_label,
    write_json,
)


PREDICTION_PRODUCER_REPORT_SCHEMA = "polymath_c5_prediction_payload_producer_report_v1"
PREDICTION_PRODUCER_CONTRACT_SCHEMA = "polymath_c5_prediction_payload_producer_contract_v1"
PREDICTION_ROW_SCHEMA = "polymath_c5_prediction_jsonl_row_v1"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def path_string_digest(path: Path) -> str:
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()


def producer_contract() -> dict[str, Any]:
    return {
        "schema_version": PREDICTION_PRODUCER_CONTRACT_SCHEMA,
        "producer_command_protocol": {
            "description": "The configured producer command is invoked once for candidate and once for stable_baseline.",
            "argv_appended_by_wrapper": [
                "--run-label",
                "<run_label>",
                "--eval-point",
                "<C5_eval_point>",
                "--checkpoint-role",
                "candidate|stable_baseline",
                "--checkpoint-payload",
                "<outside_git_raw_payload_path>",
                "--checkpoint-sha256",
                "<identity_sha256>",
                "--heldout-qa-jsonl",
                "<outside_git_heldout_qa_jsonl>",
                "--output-jsonl",
                "<outside_git_prediction_jsonl>",
            ],
            "required_prediction_jsonl_row_schema": {
                "schema_version": PREDICTION_ROW_SCHEMA,
                "required_fields": {
                    "record_id": "Must exactly match a heldout QA record_id.",
                    "prediction": "Predicted answer text. Aliases accepted by scorer: predicted_answer, answer.",
                    "loss": "Finite non-negative per-record NLL or equivalent answer-token loss.",
                    "confidence": "Finite probability in [0, 1] for answer correctness.",
                },
                "optional_fields": {
                    "loss_weight": "Positive weight, usually answer token count. Aliases: token_count, answer_token_count.",
                },
            },
            "candidate_train_loss": "Must be supplied as a finite numeric --candidate-train-loss for C5 overfit-gap reporting.",
        },
        "raw_boundary": {
            "prediction_jsonl_output_root_must_be_outside_git": True,
            "checkpoint_payloads_must_be_outside_git": True,
            "repo_metadata_reports_must_not_contain_raw_payload_bytes": True,
        },
    }


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def require_outside_git(path: Path, repo_root: Path, label: str) -> None:
    if is_under(path, repo_root):
        raise ValueError(f"{label}_inside_git_worktree")


def require_existing_path(path: Path, label: str) -> None:
    if not path.exists():
        raise ValueError(f"{label}_path_not_found")


def require_raw_payload_hash(path: Path, expected_sha256: str, label: str) -> dict[str, Any]:
    require_existing_path(path, label)
    if not is_sha256(expected_sha256):
        raise ValueError(f"{label}_expected_sha256_invalid")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ValueError(f"{label}_sha256_mismatch")
    return {
        "sha256": actual,
        "size_bytes": path.stat().st_size,
        "path_string_sha256": path_string_digest(path),
        "path_redacted": True,
    }


def prediction_paths(output_root: Path) -> dict[str, Path]:
    return {
        "candidate": output_root / "candidate_predictions.jsonl",
        "stable_baseline": output_root / "stable_baseline_predictions.jsonl",
    }


def metadata_output_path(metadata_output_dir: Path, run_label: str, eval_point: str) -> Path:
    return metadata_output_dir / f"c5_prediction_payloads_{safe_label(eval_point)}_{safe_label(run_label)}.json"


def split_producer_command(command: str | None) -> list[str] | None:
    if command is None or not command.strip():
        return None
    parsed = shlex.split(command)
    if not parsed:
        return None
    return parsed


def command_digest(command: list[str] | None) -> str | None:
    if command is None:
        return None
    return hashlib.sha256(json.dumps(command, sort_keys=True).encode("utf-8")).hexdigest()


def run_prediction_producer(
    *,
    producer_command: list[str],
    run_label: str,
    eval_point: str,
    role: str,
    checkpoint_payload: Path,
    checkpoint_sha256: str,
    heldout_qa_jsonl: Path,
    output_jsonl: Path,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    argv = [
        *producer_command,
        "--run-label",
        run_label,
        "--eval-point",
        eval_point,
        "--checkpoint-role",
        role,
        "--checkpoint-payload",
        str(checkpoint_payload),
        "--checkpoint-sha256",
        checkpoint_sha256,
        "--heldout-qa-jsonl",
        str(heldout_qa_jsonl),
        "--output-jsonl",
        str(output_jsonl),
    ]
    return subprocess.run(argv, text=True, capture_output=True, timeout=timeout_seconds, check=False)


def validate_prediction_outputs(
    *,
    heldout_qa_jsonl: Path,
    eval_split_identity: dict[str, Any],
    candidate_predictions_jsonl: Path,
    stable_baseline_predictions_jsonl: Path,
) -> dict[str, Any]:
    heldout = load_heldout_records(heldout_qa_jsonl)
    heldout_sha = sha256_file(heldout_qa_jsonl)
    if heldout_sha != eval_split_identity["eval_split_sha256"]:
        raise ValueError("heldout_qa_sha256_mismatch_eval_split_identity")
    if len(heldout) != eval_split_identity["record_count"]:
        raise ValueError("heldout_qa_record_count_mismatch_eval_split_identity")

    candidate = load_prediction_records(candidate_predictions_jsonl, "candidate_predictions")
    stable = load_prediction_records(stable_baseline_predictions_jsonl, "stable_baseline_predictions")
    assert_prediction_coverage(heldout, candidate, "candidate_predictions")
    assert_prediction_coverage(heldout, stable, "stable_baseline_predictions")
    return {
        "heldout_record_count": len(heldout),
        "candidate_prediction_count": len(candidate),
        "stable_baseline_prediction_count": len(stable),
        "heldout_qa_sha256": heldout_sha,
        "candidate_predictions_sha256": sha256_file(candidate_predictions_jsonl),
        "stable_baseline_predictions_sha256": sha256_file(stable_baseline_predictions_jsonl),
    }


def validate_candidate_train_loss(value: float | None) -> float:
    if not is_finite_number(value):
        raise ValueError("candidate_train_loss_missing_or_nonfinite")
    if float(value) < 0.0:
        raise ValueError("candidate_train_loss_negative")
    return float(value)


def build_prediction_payload_report(
    *,
    run_label: str,
    eval_point: str,
    status: str,
    first_missing_green_field: str | None,
    blockers: list[str],
    eval_split_identity: dict[str, Any] | None,
    checkpoint_identity: dict[str, Any] | None,
    stable_baseline_identity: dict[str, Any] | None,
    candidate_payload_identity: dict[str, Any] | None,
    stable_payload_identity: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    candidate_train_loss: float | None,
    producer_command_sha256: str | None,
    prediction_output_root: Path | None,
) -> dict[str, Any]:
    require_eval_point(eval_point)
    output_paths = None
    if prediction_output_root is not None:
        output_paths = {
            "prediction_output_root": str(prediction_output_root),
            "candidate_predictions_filename": "candidate_predictions.jsonl",
            "stable_baseline_predictions_filename": "stable_baseline_predictions.jsonl",
            "exact_paths_are_raw_payload_metadata_only": True,
        }
    return {
        "schema_version": PREDICTION_PRODUCER_REPORT_SCHEMA,
        "created_at_utc": utc_now(),
        "run_label": run_label,
        "eval_point": eval_point,
        "status": status,
        "first_missing_green_field": first_missing_green_field,
        "blockers": blockers,
        "producer_contract": producer_contract(),
        "producer_command_sha256": producer_command_sha256,
        "eval_split_identity": eval_split_identity,
        "checkpoint_identity": checkpoint_identity,
        "stable_baseline_identity": stable_baseline_identity,
        "candidate_payload_identity": candidate_payload_identity,
        "stable_baseline_payload_identity": stable_payload_identity,
        "prediction_output_contract": output_paths,
        "prediction_output_validation": validation,
        "candidate_train_loss": candidate_train_loss,
        "raw_boundary_proof": {
            "raw_payload_bytes_in_report": False,
            "checkpoint_payloads_copied_to_git": False,
            "prediction_jsonl_copied_to_git": False,
            "prediction_output_root_must_be_outside_git": True,
            "raw_suffix_policy": list(FORBIDDEN_RAW_SUFFIXES),
        },
        "nonclaims": list(NONCLAIMS),
    }


def first_blocker(blockers: list[str]) -> str | None:
    return blockers[0] if blockers else None


def execute_prediction_payload_contract(
    *,
    run_label: str,
    eval_point: str,
    eval_split_identity_path: Path | None,
    checkpoint_identity_path: Path | None,
    stable_baseline_identity_path: Path | None,
    heldout_qa_jsonl: Path | None,
    candidate_checkpoint_payload: Path | None,
    stable_baseline_checkpoint_payload: Path | None,
    prediction_output_root: Path | None,
    metadata_output_dir: Path,
    producer_command_text: str | None,
    candidate_train_loss_value: float | None,
    timeout_seconds: int,
    repo_root: Path,
    contract_only: bool,
) -> tuple[Path, dict[str, Any]]:
    require_eval_point(eval_point)
    metadata_output_dir.mkdir(parents=True, exist_ok=True)
    report_path = metadata_output_path(metadata_output_dir, run_label, eval_point)
    producer_command = split_producer_command(producer_command_text)
    blockers: list[str] = []

    if contract_only:
        report = build_prediction_payload_report(
            run_label=run_label,
            eval_point=eval_point,
            status="blocked",
            first_missing_green_field="producer_runtime_not_requested_contract_only",
            blockers=["producer_runtime_not_requested_contract_only"],
            eval_split_identity=None,
            checkpoint_identity=None,
            stable_baseline_identity=None,
            candidate_payload_identity=None,
            stable_payload_identity=None,
            validation=None,
            candidate_train_loss=None,
            producer_command_sha256=command_digest(producer_command),
            prediction_output_root=prediction_output_root,
        )
        write_json(report_path, report)
        return report_path, report

    required_paths = {
        "eval_split_identity": eval_split_identity_path,
        "checkpoint_identity": checkpoint_identity_path,
        "stable_baseline_identity": stable_baseline_identity_path,
        "heldout_qa_jsonl": heldout_qa_jsonl,
        "candidate_checkpoint_payload": candidate_checkpoint_payload,
        "stable_baseline_checkpoint_payload": stable_baseline_checkpoint_payload,
        "prediction_output_root": prediction_output_root,
    }
    for label, path in required_paths.items():
        if path is None:
            blockers.append(f"{label}_missing")
    if producer_command is None:
        blockers.append("producer_command_missing")

    eval_split_identity = None
    checkpoint_identity = None
    stable_baseline_identity = None
    candidate_payload_identity = None
    stable_payload_identity = None
    validation = None
    candidate_train_loss = None

    if not blockers:
        assert eval_split_identity_path is not None
        assert checkpoint_identity_path is not None
        assert stable_baseline_identity_path is not None
        assert heldout_qa_jsonl is not None
        assert candidate_checkpoint_payload is not None
        assert stable_baseline_checkpoint_payload is not None
        assert prediction_output_root is not None
        assert producer_command is not None

        try:
            require_existing_path(heldout_qa_jsonl, "heldout_qa_jsonl")
            require_outside_git(heldout_qa_jsonl, repo_root, "heldout_qa_jsonl")
            require_outside_git(candidate_checkpoint_payload, repo_root, "candidate_checkpoint_payload")
            require_outside_git(stable_baseline_checkpoint_payload, repo_root, "stable_baseline_checkpoint_payload")
            require_outside_git(prediction_output_root, repo_root, "prediction_output_root")
            candidate_train_loss = validate_candidate_train_loss(candidate_train_loss_value)
            eval_split_identity, checkpoint_identity, stable_baseline_identity = load_validated_identity_inputs(
                eval_split_identity_path=eval_split_identity_path,
                checkpoint_identity_path=checkpoint_identity_path,
                stable_baseline_identity_path=stable_baseline_identity_path,
            )
            candidate_payload_identity = require_raw_payload_hash(
                candidate_checkpoint_payload,
                checkpoint_identity["checkpoint_sha256"],
                "candidate_checkpoint_payload",
            )
            stable_payload_identity = require_raw_payload_hash(
                stable_baseline_checkpoint_payload,
                stable_baseline_identity["stable_checkpoint_baseline_sha256"],
                "stable_baseline_checkpoint_payload",
            )
            paths = prediction_paths(prediction_output_root)
            candidate_result = run_prediction_producer(
                producer_command=producer_command,
                run_label=run_label,
                eval_point=eval_point,
                role="candidate",
                checkpoint_payload=candidate_checkpoint_payload,
                checkpoint_sha256=checkpoint_identity["checkpoint_sha256"],
                heldout_qa_jsonl=heldout_qa_jsonl,
                output_jsonl=paths["candidate"],
                timeout_seconds=timeout_seconds,
            )
            if candidate_result.returncode != 0:
                blockers.append("candidate_prediction_producer_failed")
            stable_result = run_prediction_producer(
                producer_command=producer_command,
                run_label=run_label,
                eval_point=eval_point,
                role="stable_baseline",
                checkpoint_payload=stable_baseline_checkpoint_payload,
                checkpoint_sha256=stable_baseline_identity["stable_checkpoint_baseline_sha256"],
                heldout_qa_jsonl=heldout_qa_jsonl,
                output_jsonl=paths["stable_baseline"],
                timeout_seconds=timeout_seconds,
            )
            if stable_result.returncode != 0:
                blockers.append("stable_baseline_prediction_producer_failed")
            if not blockers:
                validation = validate_prediction_outputs(
                    heldout_qa_jsonl=heldout_qa_jsonl,
                    eval_split_identity=eval_split_identity,
                    candidate_predictions_jsonl=paths["candidate"],
                    stable_baseline_predictions_jsonl=paths["stable_baseline"],
                )
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            blockers.append(f"{type(exc).__name__}:{exc}")

    status = "pass" if not blockers else "blocked"
    first_missing = first_blocker(blockers)
    report = build_prediction_payload_report(
        run_label=run_label,
        eval_point=eval_point,
        status=status,
        first_missing_green_field=first_missing,
        blockers=blockers,
        eval_split_identity=eval_split_identity,
        checkpoint_identity=checkpoint_identity,
        stable_baseline_identity=stable_baseline_identity,
        candidate_payload_identity=candidate_payload_identity,
        stable_payload_identity=stable_payload_identity,
        validation=validation,
        candidate_train_loss=candidate_train_loss,
        producer_command_sha256=command_digest(producer_command),
        prediction_output_root=prediction_output_root,
    )
    write_json(report_path, report)
    return report_path, report

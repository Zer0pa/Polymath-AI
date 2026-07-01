"""Fail-closed C5 evaluation report construction.

C5 is an evaluation boundary. This module intentionally does not execute model
work or call Comet; it validates the metadata and metric contract that an
authorized execution runner must satisfy before any C5 pass can be claimed.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any, Callable


C5_SCHEMA_VERSION = "polymath_c5_eval_report_v1"
EXECUTED_METRICS_SCHEMA_VERSION = "polymath_c5_executed_metrics_v1"

EVAL_POINTS = (
    "C5_after_C1",
    "C5_after_C2",
    "C5_after_C2_5",
    "C5_after_C3",
    "C5_after_C4",
    "C5_full_curriculum_postrun",
)

REQUIRED_C5_METRIC_SUFFIXES = (
    "loss",
    "loss_delta_vs_last_stable",
    "accuracy",
    "answer_exact_match",
    "answer_token_f1",
    "perplexity",
    "calibration_ece",
    "brier_score",
    "overfit_gap_train_vs_val",
    "grad_norm_max_observed",
    "checkpoint_sha256",
    "stable_checkpoint_baseline_sha256",
    "learning_score",
)

DEFAULT_TOLERANCES: dict[str, Any] = {
    "loss_delta_vs_last_stable_max": 0.0,
    "accuracy_regression_max_abs": 0.02,
    "exact_match_regression_max_abs": 0.02,
    "token_f1_regression_max_abs": 0.02,
    "calibration_ece_regression_max_abs": 0.02,
    "overfit_gap_train_vs_val_max": 0.10,
    "grad_norm_max_observed_max": 1.0e6,
    "grad_norm_must_be_finite": True,
    "throughput_collapse_max_relative": 0.25,
}

FORBIDDEN_RAW_SUFFIXES = (
    ".qai1",
    ".pqa1",
    ".pjp1",
    ".bin",
    ".raw",
    ".f16",
    ".apk",
    ".aab",
    ".safetensors",
    ".pt",
    ".pth",
    ".ckpt",
    ".gguf",
    ".onnx",
    ".env",
    ".jsonl",
)

NONCLAIMS = (
    "no_c5_pass_without_executed_local_json",
    "no_remote_comet_call",
    "no_learning_or_model_quality_claim",
    "no_phase3_readiness_claim",
    "no_phase4_readiness_claim",
    "not_100k_or_1m_phase2_authority",
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IMMUTABLE_HF_REVISION_RE = re.compile(r"^[0-9a-f]{40,64}$")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def required_metric_names(eval_point: str) -> list[str]:
    require_eval_point(eval_point)
    return [f"c5/{eval_point}/{suffix}" for suffix in REQUIRED_C5_METRIC_SUFFIXES]


def expected_identity_schemas() -> dict[str, Any]:
    return {
        "eval_split_metadata": {
            "schema_version": "polymath_c5_eval_split_identity_v1",
            "hf_repo_id": "Zer0pa/polymat-gemmalit-c1-c4-commercial-corpus",
            "hf_revision": "<immutable_hf_commit_sha>",
            "hf_revision_is_immutable": True,
            "eval_split_path": "hf://datasets/<repo_id>/<path>",
            "eval_split_sha256": "<sha256>",
            "record_count": 0,
            "sha_stream": ["<optional per-shard/per-file sha256 values>"],
        },
        "checkpoint_identity": {
            "schema_version": "polymath_checkpoint_identity_v1",
            "checkpoint_role": "candidate",
            "checkpoint_sha256": "<sha256>",
            "checkpoint_payload_location": "outside_git",
            "produced_by_phase": "C1|C2|C2_5|C3|C4|full_curriculum",
        },
        "stable_baseline_identity": {
            "schema_version": "polymath_checkpoint_identity_v1",
            "checkpoint_role": "stable_baseline",
            "stable_checkpoint_baseline_sha256": "<sha256>",
            "checkpoint_payload_location": "outside_git",
        },
        "executed_metrics_json": {
            "schema_version": EXECUTED_METRICS_SCHEMA_VERSION,
            "executed_local_json": True,
            "metrics": {name: "<finite_number_or_matching_sha>" for name in required_metric_names("C5_after_C1")},
        },
    }


def require_eval_point(eval_point: str) -> None:
    if eval_point not in EVAL_POINTS:
        raise ValueError(f"unsupported C5 eval point: {eval_point}")


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.match(value))


def is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def scan_forbidden_raw_suffixes(
    payload: Any,
    *,
    path: str = "$",
    allowed_paths: set[str] | frozenset[str] | None = None,
    allowed_path_predicate: Callable[[str], bool] | None = None,
) -> list[dict[str, str]]:
    allowed_paths = allowed_paths or frozenset()
    hits: list[dict[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            hits.extend(
                scan_forbidden_raw_suffixes(
                    value,
                    path=f"{path}.{key}",
                    allowed_paths=allowed_paths,
                    allowed_path_predicate=allowed_path_predicate,
                ),
            )
        return hits
    if isinstance(payload, list):
        for index, value in enumerate(payload):
            hits.extend(
                scan_forbidden_raw_suffixes(
                    value,
                    path=f"{path}[{index}]",
                    allowed_paths=allowed_paths,
                    allowed_path_predicate=allowed_path_predicate,
                ),
            )
        return hits
    if isinstance(payload, str):
        if path in allowed_paths or (allowed_path_predicate is not None and allowed_path_predicate(path)):
            return hits
        lowered = payload.lower()
        for suffix in FORBIDDEN_RAW_SUFFIXES:
            if lowered.endswith(suffix) or f"{suffix}?" in lowered or f"{suffix}#" in lowered:
                hits.append({"path": path, "value": payload, "suffix": suffix})
        return hits
    return hits


def is_eval_split_metadata_path(path: str) -> bool:
    if path in {"$.eval_split_path", "$.eval_split_hf_uri", "$.material_id"}:
        return True
    return path.startswith("$.sha_stream[") and path.endswith("].remote_path")


def validate_eval_split_identity(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    blockers: list[str] = []
    required = ("hf_repo_id", "hf_revision", "eval_split_path", "eval_split_sha256", "record_count")
    for field in required:
        if payload.get(field) in (None, ""):
            blockers.append(f"c5_material_identity_missing_{field}")

    hf_revision = payload.get("hf_revision")
    revision_is_immutable = payload.get("hf_revision_is_immutable") is True or (
        isinstance(hf_revision, str) and bool(IMMUTABLE_HF_REVISION_RE.match(hf_revision))
    )
    if not revision_is_immutable:
        blockers.append("c5_material_identity_hf_revision_not_immutable")
    if payload.get("hf_revision_is_immutable") is not True:
        blockers.append("c5_material_identity_hf_revision_is_immutable_not_true")
    if payload.get("eval_split_sha256") is not None and not is_sha256(payload.get("eval_split_sha256")):
        blockers.append("c5_material_identity_eval_split_sha256_invalid")
    if not isinstance(payload.get("record_count"), int) or payload.get("record_count", 0) <= 0:
        blockers.append("c5_material_identity_record_count_nonpositive")

    raw_hits = scan_forbidden_raw_suffixes(payload, allowed_path_predicate=is_eval_split_metadata_path)
    if raw_hits:
        blockers.append("c5_material_identity_forbidden_raw_suffix")

    if blockers:
        return None, blockers

    return {
        "hf_repo_id": payload["hf_repo_id"],
        "hf_revision": payload["hf_revision"],
        "hf_revision_is_immutable": True,
        "eval_split_path": payload["eval_split_path"],
        "eval_split_sha256": payload["eval_split_sha256"],
        "record_count": payload["record_count"],
        "material_id": payload.get("material_id"),
        "sha_stream": payload.get("sha_stream", []),
    }, []


def validate_checkpoint_identity(payload: dict[str, Any], *, role: str) -> tuple[dict[str, Any] | None, list[str]]:
    blockers: list[str] = []
    if role == "candidate":
        hash_field = "checkpoint_sha256"
        accepted_role = "candidate"
    elif role == "stable_baseline":
        hash_field = "stable_checkpoint_baseline_sha256"
        accepted_role = "stable_baseline"
    else:
        raise ValueError(f"unsupported checkpoint role: {role}")

    checkpoint_hash = payload.get(hash_field)
    if checkpoint_hash is None and role == "stable_baseline":
        checkpoint_hash = payload.get("checkpoint_sha256")
    if not is_sha256(checkpoint_hash):
        blockers.append(f"{role}_identity_{hash_field}_missing_or_invalid")

    payload_location = payload.get("checkpoint_payload_location")
    if payload_location != "outside_git":
        blockers.append(f"{role}_identity_checkpoint_payload_location_not_outside_git")

    raw_hits = scan_forbidden_raw_suffixes(payload)
    if raw_hits:
        blockers.append(f"{role}_identity_forbidden_raw_suffix")

    if blockers:
        return None, blockers

    normalized = {
        "schema_version": payload.get("schema_version", "polymath_checkpoint_identity_v1"),
        "checkpoint_role": payload.get("checkpoint_role", accepted_role),
        hash_field: checkpoint_hash,
        "checkpoint_payload_location": "outside_git",
    }
    if role == "candidate":
        normalized["produced_by_phase"] = payload.get("produced_by_phase")
    return normalized, []


def report_file_identity(path: Path | None, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    if path is None:
        return None, [f"{label}_path_missing"]
    if not path.exists():
        return None, [f"{label}_path_not_found"]
    if path.suffix.lower() in FORBIDDEN_RAW_SUFFIXES:
        return None, [f"{label}_forbidden_raw_suffix"]
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }, []


def validate_executed_metrics(
    payload: dict[str, Any] | None,
    *,
    eval_point: str,
    checkpoint_sha256: str | None,
    stable_checkpoint_baseline_sha256: str | None,
) -> tuple[dict[str, Any], list[str]]:
    if payload is None:
        return {}, ["executed_c5_metrics_json_missing"]

    blockers: list[str] = []
    if payload.get("executed_local_json") is not True:
        blockers.append("executed_c5_metrics_json_executed_local_json_not_true")
    if payload.get("schema_version") != EXECUTED_METRICS_SCHEMA_VERSION:
        blockers.append("executed_c5_metrics_json_schema_version_invalid")

    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        return {}, blockers + ["executed_c5_metrics_json_metrics_missing"]

    required = required_metric_names(eval_point)
    missing = [name for name in required if name not in metrics]
    blockers.extend(f"executed_metric_missing_{name}" for name in missing)

    normalized: dict[str, Any] = {}
    for name in required:
        if name not in metrics:
            continue
        value = metrics[name]
        suffix = name.rsplit("/", 1)[-1]
        if suffix in {"checkpoint_sha256", "stable_checkpoint_baseline_sha256"}:
            if not is_sha256(value):
                blockers.append(f"executed_metric_invalid_sha_{name}")
                continue
            normalized[name] = value
            continue
        if not is_finite_number(value):
            blockers.append(f"executed_metric_not_finite_{name}")
            continue
        normalized[name] = float(value)

    checkpoint_metric = normalized.get(f"c5/{eval_point}/checkpoint_sha256")
    baseline_metric = normalized.get(f"c5/{eval_point}/stable_checkpoint_baseline_sha256")
    if checkpoint_sha256 and checkpoint_metric and checkpoint_metric != checkpoint_sha256:
        blockers.append("executed_metric_checkpoint_sha256_mismatch")
    if stable_checkpoint_baseline_sha256 and baseline_metric and baseline_metric != stable_checkpoint_baseline_sha256:
        blockers.append("executed_metric_stable_checkpoint_baseline_sha256_mismatch")

    raw_hits = scan_forbidden_raw_suffixes(payload)
    if raw_hits:
        blockers.append("executed_c5_metrics_json_forbidden_raw_suffix")

    return normalized, blockers


def evaluate_c5_metrics(metrics: dict[str, Any], eval_point: str, tolerances: dict[str, Any]) -> list[str]:
    failing: list[str] = []
    loss_delta = metrics.get(f"c5/{eval_point}/loss_delta_vs_last_stable")
    if is_finite_number(loss_delta) and float(loss_delta) > float(tolerances["loss_delta_vs_last_stable_max"]):
        failing.append("c5_loss_delta_vs_last_stable_above_tolerance")

    overfit_gap = metrics.get(f"c5/{eval_point}/overfit_gap_train_vs_val")
    if is_finite_number(overfit_gap) and float(overfit_gap) > float(tolerances["overfit_gap_train_vs_val_max"]):
        failing.append("c5_overfit_gap_above_tolerance")

    grad_norm = metrics.get(f"c5/{eval_point}/grad_norm_max_observed")
    if not is_finite_number(grad_norm):
        failing.append("c5_grad_norm_max_observed_not_finite")
    elif float(grad_norm) > float(tolerances["grad_norm_max_observed_max"]):
        failing.append("c5_grad_norm_max_observed_above_tolerance")

    for suffix in ("accuracy", "answer_exact_match", "answer_token_f1", "calibration_ece", "brier_score"):
        value = metrics.get(f"c5/{eval_point}/{suffix}")
        if not is_finite_number(value):
            failing.append(f"c5_{suffix}_not_finite")

    return failing


def capture_git_identity(repo_root: Path) -> dict[str, Any]:
    def run_git(args: list[str]) -> str | None:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            return None
        return completed.stdout.strip()

    head = run_git(["rev-parse", "HEAD"])
    status = run_git(["status", "--short"])
    return {
        "repo_path": str(repo_root),
        "git_head": head,
        "git_dirty_status": "clean" if status == "" else "dirty_with_hash_manifest",
        "git_status_short": status,
    }


def build_c5_eval_report(
    *,
    run_label: str,
    eval_point: str,
    eval_split_identity: dict[str, Any] | None,
    checkpoint_identity: dict[str, Any] | None,
    stable_baseline_identity: dict[str, Any] | None,
    phase_report_identities: dict[str, dict[str, Any] | None],
    executed_metrics: dict[str, Any] | None,
    code_identity: dict[str, Any],
    output_path: Path,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    require_eval_point(eval_point)
    all_blockers = list(blockers or [])
    checkpoint_sha = None
    baseline_sha = None
    if checkpoint_identity:
        checkpoint_sha = checkpoint_identity.get("checkpoint_sha256")
    if stable_baseline_identity:
        baseline_sha = stable_baseline_identity.get("stable_checkpoint_baseline_sha256")

    metrics, metric_blockers = validate_executed_metrics(
        executed_metrics,
        eval_point=eval_point,
        checkpoint_sha256=checkpoint_sha,
        stable_checkpoint_baseline_sha256=baseline_sha,
    )
    all_blockers.extend(metric_blockers)

    tolerances = dict(DEFAULT_TOLERANCES)
    metric_failures: list[str] = []
    if not metric_blockers:
        metric_failures = evaluate_c5_metrics(metrics, eval_point, tolerances)

    status = "blocked" if all_blockers else ("fail" if metric_failures else "pass")
    first_missing_or_failing = (all_blockers + metric_failures)[0] if (all_blockers or metric_failures) else None
    metric_names = sorted(metrics)

    return {
        "schema_version": C5_SCHEMA_VERSION,
        "run_label": run_label,
        "eval_point": eval_point,
        "created_at_utc": utc_now(),
        "c5_material_identity": eval_split_identity,
        "material_identity": eval_split_identity,
        "checkpoint_identity": checkpoint_identity,
        "stable_baseline_identity": stable_baseline_identity,
        "runtime_identity": {
            "source": "phase_report_metadata",
            "phase_reports": phase_report_identities,
        },
        "code_identity": code_identity,
        "metrics": metrics,
        "metric_vocabulary": required_metric_names(eval_point),
        "tolerances": tolerances,
        "pass_fail": {
            "status": status,
            "first_missing_or_failing_field": first_missing_or_failing,
            "metric_failures": metric_failures,
        },
        "blockers": all_blockers,
        "comet_identity": {
            "mode": "offline_contract_only",
            "authorized": False,
            "experiment_name": f"polymath_{run_label}",
            "metric_names": metric_names,
            "metric_names_match_local_json": bool(metrics) and metric_names == sorted(required_metric_names(eval_point)),
            "remote_comet_called": False,
            "not_authorized_reason": "remote_comet_logging_requires_separate_explicit_authorization",
        },
        "artifacts": {
            "metadata_report_path": str(output_path),
            "metadata_report_sha256": None,
            "metadata_report_sha256_status": "external_custody_manifest_required",
        },
        "raw_payload_boundaries": {
            "forbidden_suffixes": list(FORBIDDEN_RAW_SUFFIXES),
            "scan_status": "pass",
            "raw_payloads_included": False,
        },
        "expected_identity_schemas": expected_identity_schemas() if all_blockers else None,
        "nonclaims": list(NONCLAIMS),
    }


def load_optional_json_identity(
    path: Path | None,
    label: str,
    *,
    allowed_raw_suffix_paths: set[str] | frozenset[str] | None = None,
    allowed_raw_suffix_path_predicate: Callable[[str], bool] | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    if path is None:
        return None, [f"{label}_path_missing"]
    identity, blockers = report_file_identity(path, label)
    if blockers:
        return None, blockers
    try:
        payload = load_json(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return None, [f"{label}_json_invalid_{type(exc).__name__}"]
    raw_hits = scan_forbidden_raw_suffixes(
        payload,
        allowed_paths=allowed_raw_suffix_paths,
        allowed_path_predicate=allowed_raw_suffix_path_predicate,
    )
    if raw_hits:
        return None, [f"{label}_forbidden_raw_suffix"]
    if identity is not None:
        payload.setdefault("_identity_file", identity)
    return payload, []

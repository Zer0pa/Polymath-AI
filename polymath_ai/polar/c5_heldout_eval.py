"""Heldout QA scoring for C5 executed metrics.

This module computes metadata-only C5 metrics from an accepted heldout QA
split plus candidate and stable-baseline prediction JSONL files. It does not
run model inference, call remote services, or copy raw payloads into reports.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polymath_ai.polar.c5_eval import (
    EXECUTED_METRICS_SCHEMA_VERSION,
    FORBIDDEN_RAW_SUFFIXES,
    NONCLAIMS,
    is_finite_number,
    is_sha256,
    required_metric_names,
    scan_forbidden_raw_suffixes,
    sha256_file,
    validate_checkpoint_identity,
    validate_eval_split_identity,
)


HELDOUT_METRICS_SOURCE = "polymath_c5_heldout_qa_scorer_v1"
PREDICTION_TEXT_FIELDS = ("prediction", "predicted_answer", "answer")
LOSS_FIELDS = ("loss", "negative_log_likelihood", "nll")
CONFIDENCE_FIELDS = ("confidence", "answer_confidence", "probability")
LOSS_WEIGHT_FIELDS = ("loss_weight", "token_count", "answer_token_count")


@dataclass(frozen=True)
class HeldoutRecord:
    record_id: str
    answer: str


@dataclass(frozen=True)
class PredictionRecord:
    record_id: str
    prediction: str
    loss: float
    confidence: float
    loss_weight: float


@dataclass(frozen=True)
class ScoredRecord:
    record_id: str
    exact_match: float
    token_f1: float
    loss: float
    confidence: float
    loss_weight: float


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_label(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "c5"


def path_string_digest(path: Path) -> str:
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()


def load_jsonl_objects(path: Path, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{label}_line_{line_number}_invalid_json") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"{label}_line_{line_number}_not_json_object")
            rows.append(payload)
    return rows


def require_external_raw_input(path: Path, repo_root: Path, label: str) -> None:
    if not path.exists():
        raise ValueError(f"{label}_path_not_found")
    if path.suffix.lower() not in FORBIDDEN_RAW_SUFFIXES:
        return
    try:
        path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return
    raise ValueError(f"{label}_raw_payload_path_inside_repo")


def load_heldout_records(path: Path) -> dict[str, HeldoutRecord]:
    records: dict[str, HeldoutRecord] = {}
    for payload in load_jsonl_objects(path, "heldout_qa"):
        record_id = require_nonempty_string(payload.get("record_id"), "heldout_record_id")
        answer = require_nonempty_string(payload.get("answer"), "heldout_answer")
        if record_id in records:
            raise ValueError("heldout_duplicate_record_id")
        records[record_id] = HeldoutRecord(record_id=record_id, answer=answer)
    if not records:
        raise ValueError("heldout_record_count_zero")
    return records


def load_prediction_records(path: Path, label: str) -> dict[str, PredictionRecord]:
    records: dict[str, PredictionRecord] = {}
    for payload in load_jsonl_objects(path, label):
        record_id = require_nonempty_string(payload.get("record_id"), f"{label}_record_id")
        prediction = first_nonempty_string(payload, PREDICTION_TEXT_FIELDS, f"{label}_prediction")
        loss = first_finite_number(payload, LOSS_FIELDS, f"{label}_loss")
        if loss < 0.0:
            raise ValueError(f"{label}_loss_negative")
        confidence = first_finite_number(payload, CONFIDENCE_FIELDS, f"{label}_confidence")
        if confidence < 0.0 or confidence > 1.0:
            raise ValueError(f"{label}_confidence_out_of_range")
        loss_weight = first_optional_positive_number(payload, LOSS_WEIGHT_FIELDS, default=1.0)
        if record_id in records:
            raise ValueError(f"{label}_duplicate_record_id")
        records[record_id] = PredictionRecord(
            record_id=record_id,
            prediction=prediction,
            loss=float(loss),
            confidence=float(confidence),
            loss_weight=float(loss_weight),
        )
    if not records:
        raise ValueError(f"{label}_record_count_zero")
    return records


def require_nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}_missing_or_empty")
    return value


def first_nonempty_string(payload: dict[str, Any], fields: tuple[str, ...], label: str) -> str:
    for field in fields:
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            return value
    raise ValueError(f"{label}_missing_or_empty")


def first_finite_number(payload: dict[str, Any], fields: tuple[str, ...], label: str) -> float:
    for field in fields:
        value = payload.get(field)
        if is_finite_number(value):
            return float(value)
    raise ValueError(f"{label}_missing_or_nonfinite")


def first_optional_positive_number(payload: dict[str, Any], fields: tuple[str, ...], *, default: float) -> float:
    for field in fields:
        value = payload.get(field)
        if value is None:
            continue
        if not is_finite_number(value) or float(value) <= 0.0:
            raise ValueError(f"{field}_not_positive")
        return float(value)
    return default


def normalize_answer(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def answer_tokens(value: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", normalize_answer(value))


def token_f1(prediction: str, answer: str) -> float:
    pred_tokens = answer_tokens(prediction)
    answer_tokens_ = answer_tokens(answer)
    if not pred_tokens and not answer_tokens_:
        return 1.0
    if not pred_tokens or not answer_tokens_:
        return 0.0
    counts: dict[str, int] = {}
    for token in answer_tokens_:
        counts[token] = counts.get(token, 0) + 1
    overlap = 0
    for token in pred_tokens:
        remaining = counts.get(token, 0)
        if remaining <= 0:
            continue
        overlap += 1
        counts[token] = remaining - 1
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred_tokens)
    recall = overlap / len(answer_tokens_)
    return 2.0 * precision * recall / (precision + recall)


def assert_prediction_coverage(
    heldout: dict[str, HeldoutRecord],
    predictions: dict[str, PredictionRecord],
    label: str,
) -> None:
    heldout_ids = set(heldout)
    prediction_ids = set(predictions)
    missing = heldout_ids - prediction_ids
    extra = prediction_ids - heldout_ids
    if missing:
        raise ValueError(f"{label}_missing_record_ids")
    if extra:
        raise ValueError(f"{label}_extra_record_ids")


def score_predictions(
    heldout: dict[str, HeldoutRecord],
    predictions: dict[str, PredictionRecord],
) -> list[ScoredRecord]:
    scored: list[ScoredRecord] = []
    for record_id in heldout:
        target = heldout[record_id].answer
        prediction = predictions[record_id]
        exact = 1.0 if normalize_answer(prediction.prediction) == normalize_answer(target) else 0.0
        scored.append(
            ScoredRecord(
                record_id=record_id,
                exact_match=exact,
                token_f1=token_f1(prediction.prediction, target),
                loss=prediction.loss,
                confidence=prediction.confidence,
                loss_weight=prediction.loss_weight,
            ),
        )
    return scored


def weighted_mean_loss(records: list[ScoredRecord]) -> float:
    total_weight = sum(record.loss_weight for record in records)
    if total_weight <= 0.0:
        raise ValueError("loss_weight_total_nonpositive")
    return sum(record.loss * record.loss_weight for record in records) / total_weight


def mean(values: list[float]) -> float:
    if not values:
        raise ValueError("mean_input_empty")
    return sum(values) / len(values)


def safe_perplexity(loss: float) -> float:
    if loss > 700.0:
        raise ValueError("loss_too_large_for_finite_perplexity")
    value = math.exp(loss)
    if not math.isfinite(value):
        raise ValueError("perplexity_not_finite")
    return value


def calibration_ece(records: list[ScoredRecord], bins: int) -> float:
    if bins <= 0:
        raise ValueError("ece_bins_nonpositive")
    buckets = [{"count": 0, "confidence": 0.0, "correct": 0.0} for _ in range(bins)]
    for record in records:
        index = min(bins - 1, int(record.confidence * bins))
        buckets[index]["count"] += 1
        buckets[index]["confidence"] += record.confidence
        buckets[index]["correct"] += record.exact_match
    total = len(records)
    ece = 0.0
    for bucket in buckets:
        count = bucket["count"]
        if count == 0:
            continue
        accuracy = bucket["correct"] / count
        avg_confidence = bucket["confidence"] / count
        ece += (count / total) * abs(accuracy - avg_confidence)
    return ece


def brier_score(records: list[ScoredRecord]) -> float:
    return mean([(record.confidence - record.exact_match) ** 2 for record in records])


def summarize_scores(records: list[ScoredRecord], *, ece_bins: int) -> dict[str, float]:
    loss = weighted_mean_loss(records)
    return {
        "loss": loss,
        "accuracy": mean([record.exact_match for record in records]),
        "answer_exact_match": mean([record.exact_match for record in records]),
        "answer_token_f1": mean([record.token_f1 for record in records]),
        "perplexity": safe_perplexity(loss),
        "calibration_ece": calibration_ece(records, ece_bins),
        "brier_score": brier_score(records),
    }


def validate_metric_payload_for_raw_boundaries(payload: dict[str, Any]) -> None:
    raw_hits = scan_forbidden_raw_suffixes(payload)
    if raw_hits:
        raise ValueError("executed_metrics_payload_contains_forbidden_raw_suffix")


def file_identity_without_path(path: Path, *, record_count: int | None = None) -> dict[str, Any]:
    identity: dict[str, Any] = {
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
        "path_string_sha256": path_string_digest(path),
        "path_redacted": True,
    }
    if record_count is not None:
        identity["record_count"] = record_count
    return identity


def load_validated_identity_inputs(
    *,
    eval_split_identity_path: Path,
    checkpoint_identity_path: Path,
    stable_baseline_identity_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    eval_split_payload = load_json(eval_split_identity_path)
    eval_split_identity, eval_split_blockers = validate_eval_split_identity(eval_split_payload)
    if eval_split_blockers or eval_split_identity is None:
        raise ValueError(f"eval_split_identity_invalid:{','.join(eval_split_blockers)}")

    checkpoint_payload = load_json(checkpoint_identity_path)
    checkpoint_identity, checkpoint_blockers = validate_checkpoint_identity(checkpoint_payload, role="candidate")
    if checkpoint_blockers or checkpoint_identity is None:
        raise ValueError(f"checkpoint_identity_invalid:{','.join(checkpoint_blockers)}")

    baseline_payload = load_json(stable_baseline_identity_path)
    baseline_identity, baseline_blockers = validate_checkpoint_identity(baseline_payload, role="stable_baseline")
    if baseline_blockers or baseline_identity is None:
        raise ValueError(f"stable_baseline_identity_invalid:{','.join(baseline_blockers)}")

    return eval_split_identity, checkpoint_identity, baseline_identity


def extract_grad_norm_max_observed(phase34_report: dict[str, Any] | None, eval_point: str) -> float | None:
    if phase34_report is None:
        return None
    corpus_phase = eval_point.removeprefix("C5_after_")
    candidates = [
        phase34_report.get("grad_norm_max_observed"),
        phase34_report.get("grad_norm_l2"),
        phase34_report.get("grad_norm"),
        phase34_report.get("metrics", {}).get(f"phase4/{corpus_phase}/grad_norm_l2"),
        phase34_report.get("metrics", {}).get(f"phase4/{corpus_phase}/grad_norm_linf"),
    ]
    finite = [float(value) for value in candidates if is_finite_number(value)]
    if not finite:
        return None
    return max(abs(value) for value in finite)


def build_executed_metrics_payload(
    *,
    run_label: str,
    eval_point: str,
    eval_split_identity: dict[str, Any],
    checkpoint_identity: dict[str, Any],
    stable_baseline_identity: dict[str, Any],
    heldout_qa_path: Path,
    candidate_predictions_path: Path,
    baseline_predictions_path: Path,
    candidate_train_loss: float,
    grad_norm_max_observed: float,
    ece_bins: int,
    repo_root: Path,
) -> dict[str, Any]:
    for label, path in (
        ("heldout_qa", heldout_qa_path),
        ("candidate_predictions", candidate_predictions_path),
        ("stable_baseline_predictions", baseline_predictions_path),
    ):
        require_external_raw_input(path, repo_root, label)

    if not is_finite_number(candidate_train_loss):
        raise ValueError("candidate_train_loss_nonfinite")
    if not is_finite_number(grad_norm_max_observed):
        raise ValueError("grad_norm_max_observed_nonfinite")

    heldout = load_heldout_records(heldout_qa_path)
    candidate_predictions = load_prediction_records(candidate_predictions_path, "candidate_predictions")
    baseline_predictions = load_prediction_records(baseline_predictions_path, "stable_baseline_predictions")
    assert_prediction_coverage(heldout, candidate_predictions, "candidate_predictions")
    assert_prediction_coverage(heldout, baseline_predictions, "stable_baseline_predictions")

    heldout_sha = sha256_file(heldout_qa_path)
    if heldout_sha != eval_split_identity["eval_split_sha256"]:
        raise ValueError("heldout_qa_sha256_mismatch_eval_split_identity")
    if len(heldout) != eval_split_identity["record_count"]:
        raise ValueError("heldout_qa_record_count_mismatch_eval_split_identity")

    candidate_scores = score_predictions(heldout, candidate_predictions)
    baseline_scores = score_predictions(heldout, baseline_predictions)
    candidate_summary = summarize_scores(candidate_scores, ece_bins=ece_bins)
    baseline_summary = summarize_scores(baseline_scores, ece_bins=ece_bins)

    checkpoint_sha = checkpoint_identity["checkpoint_sha256"]
    baseline_sha = stable_baseline_identity["stable_checkpoint_baseline_sha256"]
    if not is_sha256(checkpoint_sha) or not is_sha256(baseline_sha):
        raise ValueError("checkpoint_identity_sha_invalid")

    prefix = f"c5/{eval_point}"
    loss_delta = candidate_summary["loss"] - baseline_summary["loss"]
    learning_score = baseline_summary["loss"] - candidate_summary["loss"]
    metrics = {
        f"{prefix}/loss": candidate_summary["loss"],
        f"{prefix}/loss_delta_vs_last_stable": loss_delta,
        f"{prefix}/accuracy": candidate_summary["accuracy"],
        f"{prefix}/answer_exact_match": candidate_summary["answer_exact_match"],
        f"{prefix}/answer_token_f1": candidate_summary["answer_token_f1"],
        f"{prefix}/perplexity": candidate_summary["perplexity"],
        f"{prefix}/calibration_ece": candidate_summary["calibration_ece"],
        f"{prefix}/brier_score": candidate_summary["brier_score"],
        f"{prefix}/overfit_gap_train_vs_val": abs(float(candidate_train_loss) - candidate_summary["loss"]),
        f"{prefix}/grad_norm_max_observed": abs(float(grad_norm_max_observed)),
        f"{prefix}/checkpoint_sha256": checkpoint_sha,
        f"{prefix}/stable_checkpoint_baseline_sha256": baseline_sha,
        f"{prefix}/learning_score": learning_score,
    }

    required = set(required_metric_names(eval_point))
    if set(metrics) != required:
        raise ValueError("executed_metric_name_set_mismatch")

    payload = {
        "schema_version": EXECUTED_METRICS_SCHEMA_VERSION,
        "executed_local_json": True,
        "metrics_source": HELDOUT_METRICS_SOURCE,
        "created_at_utc": utc_now(),
        "run_label": run_label,
        "eval_point": eval_point,
        "metrics": metrics,
        "metric_details": {
            "record_count": len(heldout),
            "candidate": candidate_summary,
            "stable_baseline": baseline_summary,
            "candidate_train_loss": float(candidate_train_loss),
            "loss_delta_direction": "candidate_minus_stable_baseline",
            "learning_score_direction": "stable_baseline_loss_minus_candidate_loss",
            "ece_bins": ece_bins,
        },
        "split_identity": {
            "hf_repo_id": eval_split_identity["hf_repo_id"],
            "hf_revision": eval_split_identity["hf_revision"],
            "hf_revision_is_immutable": True,
            "eval_split_sha256": eval_split_identity["eval_split_sha256"],
            "record_count": eval_split_identity["record_count"],
            "eval_split_path_redacted": True,
        },
        "checkpoint_identity": {
            "checkpoint_sha256": checkpoint_sha,
            "stable_checkpoint_baseline_sha256": baseline_sha,
            "candidate_payload_location": checkpoint_identity["checkpoint_payload_location"],
            "stable_baseline_payload_location": stable_baseline_identity["checkpoint_payload_location"],
        },
        "input_identities": {
            "heldout_qa": file_identity_without_path(heldout_qa_path, record_count=len(heldout)),
            "candidate_predictions": file_identity_without_path(
                candidate_predictions_path,
                record_count=len(candidate_predictions),
            ),
            "stable_baseline_predictions": file_identity_without_path(
                baseline_predictions_path,
                record_count=len(baseline_predictions),
            ),
        },
        "provenance": {
            "runner": "scripts/host/run_c5_heldout_eval.py",
            "path_arguments_redacted": True,
            "raw_input_path_sha256_only": True,
            "remote_services_called": False,
            "model_inference_performed_by_this_runner": False,
        },
        "raw_boundary_proof": {
            "metadata_only": True,
            "raw_payloads_included": False,
            "raw_input_paths_omitted": True,
            "forbidden_suffix_values_omitted": True,
        },
        "nonclaims": list(NONCLAIMS),
    }
    validate_metric_payload_for_raw_boundaries(payload)
    return payload


def build_blocker_report(
    *,
    run_label: str,
    eval_point: str,
    blockers: list[str],
    output_path: Path,
    input_paths: list[Path],
) -> dict[str, Any]:
    return {
        "schema_version": "polymath_c5_heldout_eval_blocker_v1",
        "created_at_utc": utc_now(),
        "run_label": run_label,
        "eval_point": eval_point,
        "status": "blocked",
        "blockers": blockers,
        "output_path": str(output_path),
        "input_path_string_sha256": [path_string_digest(path) for path in input_paths],
        "path_arguments_redacted": True,
        "raw_payloads_included": False,
        "executed_metrics_json_written": False,
        "nonclaims": list(NONCLAIMS),
    }

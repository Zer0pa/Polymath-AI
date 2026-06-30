#!/usr/bin/env python3
"""Run accepted C1 QA source through the Android Phase 1 authority path.

This is a pipeline smoke runner, not a corpus-scale authority gate. Raw QAI1
and PQA1 payloads stay in /tmp, app staging, or explicit device transfer
locations. The repository report tree must contain only JSON/text metadata.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
WORKSPACE_ROOT = REPO_ROOT.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from polymath_ai.polar.metrics_contract import metric_report  # noqa: E402
from run_phase1_apk_benchmark import (  # noqa: E402
    ADB_REPORT_ROOT,
    INTERNAL_FILES_ROOT,
    PACKAGE_NAME,
    STAGED_ROOT,
    adb,
    ensure_gbt1,
    internal_relative,
    launch_and_wait,
    pull_run_report,
    run_as,
    scan_forbidden,
    select_serial,
    sha256_file,
    shard_records,
    shell_quote,
    stage_batch,
    write_json,
)
from run_phase1_nubia_whitelist_probe import (  # noqa: E402
    RUNTIME_SAMPLER_FLAG,
    apply_settings,
    current_game_mode,
    frequency_snapshot,
    set_game_mode,
    snapshot_settings,
    target_settings,
)


C1_ROOT = WORKSPACE_ROOT / "corpus_packages/commercial/20260629T100304Z/phase_C1_lexatlas_frontier_gpt_enriched_scale_v1"
DEFAULT_TRAIN_QA = C1_ROOT / "qa_bridge/phase_C1_train.qa.jsonl"
DEFAULT_FULL_QA = C1_ROOT / "qa_bridge/phase_C1_full.qa.jsonl"

PHASE1_SOURCE_KINDS = {"dictionary", "megascience", "synthetic_stress", "user_supplied"}
DEFAULT_SOURCE_KIND_MAP = {"lexatlas": "dictionary"}
CHILD_EXEC_FLAG = 16
NATIVE_WARM_SEQUENCE_FLAG = 2
NATIVE_EXTENDED_WARM_SEQUENCE_FLAG = 4
ACCEPTED_ENRICHMENT_FIELDS = [
    "formal_definition",
    "related_terms",
    "usage_example",
    "register",
    "domain",
    "collocations",
    "sentiment_potential",
    "word_family",
    "pragmatic_note",
    "frame",
]
QUARANTINED_FIELDS = ["cultural_note", "scenario", "poetic_example"]
FORBIDDEN_REPORT_SUFFIXES = (
    ".qai1",
    ".pqa1",
    ".pjp1",
    ".jsonl",
    ".safetensors",
    ".bin",
    ".pt",
    ".pth",
    ".onnx",
    ".tflite",
    ".apk",
    ".aab",
)


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def parse_kind_map(values: list[str]) -> dict[str, str]:
    mapping = dict(DEFAULT_SOURCE_KIND_MAP)
    for value in values:
        if "=" not in value:
            raise SystemExit(f"source-kind mapping must be RAW=PHASE1_ENUM, got {value!r}")
        raw, normalized = value.split("=", 1)
        raw = raw.strip()
        normalized = normalized.strip()
        if not raw or normalized not in PHASE1_SOURCE_KINDS:
            raise SystemExit(f"invalid source-kind mapping: {value!r}")
        mapping[raw] = normalized
    return mapping


def resolve_input_path(args: argparse.Namespace) -> Path:
    if args.input_path:
        return args.input_path.resolve()
    if args.full:
        return DEFAULT_FULL_QA
    return DEFAULT_TRAIN_QA


def infer_package_root(input_path: Path) -> Path:
    if input_path.parent.name == "qa_bridge":
        return input_path.parent.parent
    return input_path.parent


def resolve_package_root(args: argparse.Namespace, input_path: Path) -> Path:
    if args.package_root:
        return args.package_root.resolve()
    return infer_package_root(input_path).resolve()


def resolve_package_manifest(args: argparse.Namespace, package_root: Path) -> Path:
    if args.package_manifest:
        return args.package_manifest.resolve()
    return package_root / "phase_C1_build_manifest.json"


def sanitize_label(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")
    return cleaned or "c1"


def validate_text_field(record_id: str, field: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{record_id}: missing non-empty {field}")
    encoded = value.encode("utf-8")
    if len(encoded) > 65_536:
        raise ValueError(f"{record_id}: {field} exceeds 65536 bytes")
    return value


def normalize_source_kind(record_id: str, raw_kind: Any, kind_map: dict[str, str]) -> tuple[str, str | None]:
    if not isinstance(raw_kind, str) or not raw_kind.strip():
        raise ValueError(f"{record_id}: missing source_kind")
    if raw_kind in PHASE1_SOURCE_KINDS:
        return raw_kind, None
    if raw_kind in kind_map:
        return kind_map[raw_kind], raw_kind
    raise ValueError(f"{record_id}: unsupported source_kind {raw_kind!r}")


def percentile(values: list[int | float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return float(ordered[index])


def summarize_text_distribution(records: list[dict[str, str]]) -> dict[str, Any]:
    question_bytes = [len(record["question"].encode("utf-8")) for record in records]
    answer_bytes = [len(record["answer"].encode("utf-8")) for record in records]
    combined_bytes = [question + answer for question, answer in zip(question_bytes, answer_bytes)]
    whitespace_token_estimates = [
        len((record["question"] + " " + record["answer"]).split()) for record in records
    ]
    return {
        "question_bytes_total": sum(question_bytes),
        "answer_bytes_total": sum(answer_bytes),
        "combined_bytes_total": sum(combined_bytes),
        "combined_bytes_mean": (sum(combined_bytes) / len(combined_bytes)) if combined_bytes else None,
        "combined_bytes_p50": percentile(combined_bytes, 0.50),
        "combined_bytes_p95": percentile(combined_bytes, 0.95),
        "combined_bytes_p99": percentile(combined_bytes, 0.99),
        "source_text_whitespace_tokens_mean": (
            sum(whitespace_token_estimates) / len(whitespace_token_estimates)
        )
        if whitespace_token_estimates
        else None,
        "source_text_whitespace_tokens_p95": percentile(whitespace_token_estimates, 0.95),
    }


def load_json_file_if_present(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def numeric_token_sequence(payload: dict[str, Any]) -> list[float]:
    for key in ("token_ids_per_record", "tokens_per_record", "record_token_counts"):
        values = payload.get(key)
        if not isinstance(values, list):
            continue
        out: list[float] = []
        for value in values:
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
                out.append(float(value))
            else:
                return []
        return out
    return []


def first_numeric(*values: Any) -> float | int | None:
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    return None


def summarize_native_batch_token_distribution(native_batch_metrics: dict[str, Any] | None) -> dict[str, Any]:
    if not native_batch_metrics:
        return {
            "job_count": None,
            "tokens_per_record_job_mean": None,
            "tokens_per_record_job_p50": None,
            "tokens_per_record_job_p95": None,
            "tokens_per_record_job_p99": None,
            "native_batch_elapsed_ms": None,
            "native_batch_token_ids_per_sec": None,
        }

    job_ratios: list[float] = []
    for job in native_batch_metrics.get("job_results", []):
        if not isinstance(job, dict):
            continue
        records = job.get("records")
        token_ids = job.get("token_ids")
        if (
            isinstance(records, (int, float))
            and isinstance(token_ids, (int, float))
            and not isinstance(records, bool)
            and not isinstance(token_ids, bool)
            and records > 0
        ):
            job_ratios.append(float(token_ids) / float(records))

    elapsed_ns = native_batch_metrics.get("elapsed_ns")
    token_ids_total = native_batch_metrics.get("token_ids")
    elapsed_ms = float(elapsed_ns) / 1_000_000.0 if isinstance(elapsed_ns, (int, float)) else None
    token_rate = None
    if elapsed_ms and isinstance(token_ids_total, (int, float)):
        token_rate = float(token_ids_total) / (elapsed_ms / 1000.0)

    return {
        "job_count": native_batch_metrics.get("job_count"),
        "tokens_per_record_job_mean": (sum(job_ratios) / len(job_ratios)) if job_ratios else None,
        "tokens_per_record_job_p50": percentile(job_ratios, 0.50),
        "tokens_per_record_job_p95": percentile(job_ratios, 0.95),
        "tokens_per_record_job_p99": percentile(job_ratios, 0.99),
        "native_batch_elapsed_ms": elapsed_ms,
        "native_batch_token_ids_per_sec": token_rate,
    }


def build_phase1_metrics(
    args: argparse.Namespace,
    records: list[dict[str, str]],
    source_identity: dict[str, Any],
    *,
    app_result: dict[str, Any] | None = None,
    native_phase1_metrics: dict[str, Any] | None = None,
    native_batch_metrics: dict[str, Any] | None = None,
    pqa1_all_outputs_present: bool | None = None,
) -> dict[str, Any]:
    app_result = app_result or {}
    native_phase1_metrics = native_phase1_metrics or {}
    native_batch_metrics = native_batch_metrics or {}
    native_probe = app_result.get("native_probe") if isinstance(app_result.get("native_probe"), dict) else {}
    token_counts = numeric_token_sequence(app_result)
    if not token_counts:
        token_counts = numeric_token_sequence(native_phase1_metrics)
    token_ids = app_result.get("token_ids")
    if token_ids is None:
        token_ids = native_phase1_metrics.get("token_ids")
    if token_ids is None and token_counts:
        token_ids = sum(token_counts)
    wall_sec = first_numeric(app_result.get("wall_sec"), native_phase1_metrics.get("wall_sec"))
    text_distribution = summarize_text_distribution(records)
    batch_distribution = summarize_native_batch_token_distribution(native_batch_metrics)
    token_mean = (float(token_ids) / float(len(records))) if isinstance(token_ids, (int, float)) and records else None
    if token_counts:
        token_mean = sum(token_counts) / len(token_counts)
    token_mean = first_numeric(app_result.get("tokens_per_record_mean"), native_phase1_metrics.get("tokens_per_record_mean"), token_mean)

    distinct_token_ids = app_result.get("distinct_token_ids")
    if distinct_token_ids is None:
        distinct_token_ids = native_phase1_metrics.get("distinct_token_ids")
    if distinct_token_ids is None:
        distinct_token_ids = native_batch_metrics.get("distinct_token_ids")
    vocab_size = app_result.get("vocab_size") or native_phase1_metrics.get("vocab_size") or native_batch_metrics.get("vocab_size")
    vocab_coverage_ratio = None
    if isinstance(app_result.get("vocab_coverage_ratio"), (int, float)):
        vocab_coverage_ratio = float(app_result["vocab_coverage_ratio"])
    elif isinstance(native_phase1_metrics.get("vocab_coverage_ratio"), (int, float)):
        vocab_coverage_ratio = float(native_phase1_metrics["vocab_coverage_ratio"])
    if isinstance(distinct_token_ids, (int, float)) and isinstance(vocab_size, (int, float)) and vocab_size > 0:
        vocab_coverage_ratio = float(distinct_token_ids) / float(vocab_size)

    per_record_p50 = first_numeric(app_result.get("tokens_per_record_p50"), native_phase1_metrics.get("tokens_per_record_p50"), percentile(token_counts, 0.50))
    per_record_p95 = first_numeric(app_result.get("tokens_per_record_p95"), native_phase1_metrics.get("tokens_per_record_p95"), percentile(token_counts, 0.95))
    per_record_p99 = first_numeric(app_result.get("tokens_per_record_p99"), native_phase1_metrics.get("tokens_per_record_p99"), percentile(token_counts, 0.99))
    per_record_distribution_measured = per_record_p50 is not None and per_record_p95 is not None and per_record_p99 is not None

    metrics = {
        "record_count": len(records),
        "question_bytes_total": text_distribution["question_bytes_total"],
        "answer_bytes_total": text_distribution["answer_bytes_total"],
        "token_ids_total": token_ids,
        "distinct_token_ids": distinct_token_ids,
        "vocab_size": vocab_size,
        "vocab_coverage_ratio": vocab_coverage_ratio,
        "tokens_per_record_mean": token_mean,
        "tokens_per_record_p50": per_record_p50,
        "tokens_per_record_p95": per_record_p95,
        "tokens_per_record_p99": per_record_p99,
        "tokens_per_record_distribution_source": app_result.get(
            "tokens_per_record_distribution_source",
            native_phase1_metrics.get("tokens_per_record_distribution_source"),
        ),
        "tokens_per_record_job_mean": batch_distribution["tokens_per_record_job_mean"],
        "tokens_per_record_job_p50": batch_distribution["tokens_per_record_job_p50"],
        "tokens_per_record_job_p95": batch_distribution["tokens_per_record_job_p95"],
        "tokens_per_record_job_p99": batch_distribution["tokens_per_record_job_p99"],
        "source_kind_counts": source_identity.get("normalized_source_kind_counts", {}),
        "source_kind_mapping": source_identity.get("source_kind_mapping_applied", {}),
        "invalid_record_count": 0,
        "duplicate_record_id_count": 0,
        "token_ids_per_sec": app_result.get("token_ids_per_sec"),
        "records_per_sec": app_result.get("records_per_sec"),
        "latency_ms": (float(wall_sec) * 1000.0) if isinstance(wall_sec, (int, float)) else None,
        "native_batch_job_count": batch_distribution["job_count"],
        "native_batch_elapsed_ms": batch_distribution["native_batch_elapsed_ms"],
        "native_batch_token_ids_per_sec": batch_distribution["native_batch_token_ids_per_sec"],
        "native_return_code": first_numeric(native_probe.get("return_code"), native_phase1_metrics.get("return_code")),
        "native_gate_result": native_probe.get("gate_result") or app_result.get("status"),
        "native_connection_state": native_probe.get("connection_state"),
        "pqa1_all_outputs_present": pqa1_all_outputs_present,
        "source_text_distribution": text_distribution,
        "metric_measurement_status": {
            "token_ids_total": "measured_by_phase1_app" if token_ids is not None else "missing",
            "distinct_token_ids": "measured" if distinct_token_ids is not None else "requires_phase1_app_or_native_distinct_counter",
            "vocab_coverage_ratio": "measured" if vocab_coverage_ratio is not None else "requires_distinct_token_ids_and_vocab_size",
            "tokens_per_record_quantiles": "measured_true_per_record" if per_record_distribution_measured else "requires_phase1_app_per_record_token_counts",
            "tokens_per_record_job_quantiles": "measured_from_native_batch_jobs_not_per_record" if batch_distribution["tokens_per_record_job_p50"] is not None else "unavailable",
        },
    }
    blockers: list[str] = []
    native_return_code = metrics["native_return_code"]
    native_gate_result = str(metrics["native_gate_result"] or "").lower()
    app_status = str(app_result.get("status") or "").lower()
    if native_return_code is not None and int(native_return_code) != 0:
        blockers.append(f"phase1_native_return_code_nonzero_{int(native_return_code)}")
    if native_gate_result in {"blocked", "fail", "failed"}:
        blockers.append(f"phase1_native_gate_result_{native_gate_result}")
    if app_status in {"blocked", "fail", "failed"}:
        blockers.append(f"phase1_app_status_{app_status}")
    if pqa1_all_outputs_present is False:
        blockers.append("phase1_pqa1_outputs_missing")
    if token_ids is None:
        blockers.append("app_tokenizer_token_ids_total_missing")
    elif records and float(token_ids) <= 0.0:
        blockers.append("app_tokenizer_token_ids_total_nonpositive")
    if distinct_token_ids is None:
        blockers.append("distinct_token_ids_not_reported_by_phase1_app_or_native")
    elif records and float(distinct_token_ids) <= 0.0:
        blockers.append("distinct_token_ids_nonpositive")
    if not per_record_distribution_measured:
        blockers.append("per_record_token_distribution_not_reported_by_phase1_app")
    elif records and any(float(value) <= 0.0 for value in (token_mean, per_record_p50, per_record_p95, per_record_p99) if value is not None):
        blockers.append("per_record_token_distribution_nonpositive")
    if vocab_coverage_ratio is None:
        blockers.append("vocab_coverage_unavailable_without_distinct_token_ids_and_vocab_size")
    elif records and float(vocab_coverage_ratio) <= 0.0:
        blockers.append("vocab_coverage_ratio_nonpositive")
    if metrics["latency_ms"] is None:
        blockers.append("phase1_wall_latency_missing")
    elif records and float(metrics["latency_ms"]) <= 0.0:
        blockers.append("phase1_wall_latency_nonpositive")

    return metric_report(
        schema_version="phase1_c1_metric_contract_v1",
        phase_family="phase1",
        corpus_phase=args.corpus_phase,
        metrics=metrics,
        blockers=sorted(set(blockers)),
        nonclaims=[
            "phase1_metrics_do_not_claim_learning",
            "phase1_metrics_do_not_claim_phase2_or_phase3_readiness",
        ],
    )


def load_c1_records(input_path: Path, *, limit: int | None, kind_map: dict[str, str]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if not input_path.is_file():
        raise SystemExit(f"C1 input path not found: {input_path}")

    selected: list[dict[str, str]] = []
    seen: set[str] = set()
    raw_kind_counts: dict[str, int] = {}
    normalized_kind_counts: dict[str, int] = {}
    applied_mappings: dict[str, str] = {}
    record_hashes: list[str] = []
    record_id_stream = hashlib.sha256()
    source_stream = hashlib.sha256()
    total_rows = 0

    with input_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            total_rows += 1
            if limit is not None and len(selected) >= limit:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{input_path}:{line_number}: bad JSON: {exc}") from exc

            record_id = obj.get("record_id")
            if not isinstance(record_id, str) or not record_id.strip():
                raise ValueError(f"{input_path}:{line_number}: missing record_id")
            if record_id in seen:
                raise ValueError(f"duplicate selected record_id: {record_id}")
            seen.add(record_id)

            question = validate_text_field(record_id, "question", obj.get("question"))
            answer = validate_text_field(record_id, "answer", obj.get("answer"))
            normalized_kind, mapped_from = normalize_source_kind(record_id, obj.get("source_kind"), kind_map)
            raw_kind = str(obj.get("source_kind"))
            raw_kind_counts[raw_kind] = raw_kind_counts.get(raw_kind, 0) + 1
            normalized_kind_counts[normalized_kind] = normalized_kind_counts.get(normalized_kind, 0) + 1
            if mapped_from:
                applied_mappings[mapped_from] = normalized_kind

            source_identity = {
                "answer": answer,
                "metadata": obj.get("metadata"),
                "question": question,
                "record_id": record_id,
                "relation_type": obj.get("relation_type"),
                "source_kind": raw_kind,
                "source_ref": obj.get("source_ref"),
            }
            record_hash = sha256_json(source_identity)
            record_hashes.append(record_hash)
            record_id_stream.update(record_id.encode("utf-8"))
            record_id_stream.update(b"\n")
            source_stream.update(record_hash.encode("ascii"))
            source_stream.update(b"\n")

            selected.append(
                {
                    "record_id": record_id,
                    "source_kind": normalized_kind,
                    "question": question,
                    "answer": answer,
                }
            )

    if not selected:
        raise ValueError("no C1 records selected")

    identity = {
        "input_path": str(input_path),
        "input_sha256": sha256_file(input_path),
        "input_total_rows": total_rows,
        "selected_records": len(selected),
        "selection_policy": "first_n_in_file_order",
        "selected_record_id_sha256_stream": record_id_stream.hexdigest(),
        "selected_source_sha256_stream": source_stream.hexdigest(),
        "first_record_ids": [record["record_id"] for record in selected[:5]],
        "last_record_ids": [record["record_id"] for record in selected[-5:]],
        "selected_record_source_sha256s": record_hashes,
        "raw_source_kind_counts": raw_kind_counts,
        "normalized_source_kind_counts": normalized_kind_counts,
        "source_kind_mapping_applied": applied_mappings,
    }
    return selected, identity


def planned_pqa1_outputs(remote_dir: str, records: list[dict[str, str]], scheduler: str, workers: int, chunk_size: int) -> list[dict[str, Any]]:
    shards = shard_records(records, scheduler=scheduler, workers=workers, chunk_size=chunk_size)
    outputs = []
    for index, shard in enumerate(shards):
        outputs.append(
            {
                "index": index,
                "record_count": len(shard),
                "input_qai1_path": f"{remote_dir}/inputs/in_{index:04d}.qai1",
                "output_pqa1_path": f"{remote_dir}/outputs/out_{index:04d}.pqa1",
                "writer_report_path": f"{remote_dir}/outputs/writer_{index:04d}.json",
                "bpe_report_path": f"{remote_dir}/outputs/bpe_{index:04d}.json",
            }
        )
    return outputs


def remote_stat_command(path: str) -> str:
    quoted = shell_quote(path)
    return (
        f"if [ -f {quoted} ]; then "
        f"bytes=$(wc -c < {quoted}); sha=$(sha256sum {quoted} | awk '{{print $1}}'); "
        "printf '%s\\t%s\\n' \"$bytes\" \"$sha\"; "
        "else printf 'missing\\tmissing\\n'; fi"
    )


def collect_remote_pqa1_stats(serial: str, outputs: list[dict[str, Any]], staging: str) -> list[dict[str, Any]]:
    rows = []
    for output in outputs:
        path = str(output["output_pqa1_path"])
        if staging == "internal":
            proc = run_as(serial, remote_stat_command(internal_relative(path)), timeout=120, check=False)
        else:
            proc = adb(serial, "shell", remote_stat_command(path), timeout=120, check=False)
        parts = proc.stdout.strip().split()
        rows.append(
            {
                "path": path,
                "returncode": proc.returncode,
                "bytes": int(parts[0]) if len(parts) >= 2 and parts[0].isdigit() else None,
                "sha256": parts[1] if len(parts) >= 2 and parts[1] != "missing" else None,
                "stderr_tail": proc.stderr[-2000:],
            }
        )
    return rows


def report_suffix_findings(root: Path) -> list[str]:
    findings = []
    if not root.exists():
        return findings
    for path in root.rglob("*"):
        if path.is_file() and path.name.endswith(FORBIDDEN_REPORT_SUFFIXES):
            findings.append(str(path))
    return findings


def build_source_manifest(
    *,
    args: argparse.Namespace,
    records: list[dict[str, str]],
    source_identity: dict[str, Any],
    report_root: Path,
    run_label: str,
) -> dict[str, Any]:
    package_manifest_sha = sha256_file(args.package_manifest) if args.package_manifest and args.package_manifest.is_file() else None
    payload = {
        "schema_version": "phase1_c1_source_manifest_v1",
        "run_label": run_label,
        "corpus": args.corpus_id,
        "input_identity": source_identity,
        "package_root": str(args.package_root),
        "package_manifest": str(args.package_manifest) if args.package_manifest else None,
        "package_manifest_sha256": package_manifest_sha,
        "phase1_record_shape": ["record_id", "source_kind", "question", "answer"],
        "accepted_enrichment_fields": ACCEPTED_ENRICHMENT_FIELDS,
        "quarantined_fields": QUARANTINED_FIELDS,
        "raw_payload_policy": "C1 JSONL remains outside the repository; QAI1/PQA1 never enter repo reports",
        "report_root": str(report_root),
        "records_selected": len(records),
        "source_text_distribution": summarize_text_distribution(records),
        "nonclaims": [
            "c1_is_source_material_not_pqa1",
            "c1_smoke_is_not_100k_or_1m_authority_gate",
            "no_phase2_or_phase3_promotion_claim",
        ],
    }
    payload["source_manifest_sha256"] = sha256_json(payload)
    return payload


def build_generation_manifest(
    *,
    local_dir: Path,
    remote_dir: str,
    batch_path: str | None,
    tokenizer_dir: str,
    gbt1_path: str | None,
    outputs: list[dict[str, Any]],
    args: argparse.Namespace,
    run_label: str,
) -> dict[str, Any]:
    qai1_files = sorted((local_dir / "inputs").glob("*.qai1")) if (local_dir / "inputs").is_dir() else []
    payload = {
        "schema_version": "phase1_c1_qai1_generation_manifest_v1",
        "run_label": run_label,
        "local_tmp_dir": str(local_dir),
        "remote_dir": remote_dir,
        "staging": args.staging,
        "scheduler": args.scheduler,
        "workers": args.workers,
        "chunk_size": args.chunk_size,
        "batch_list_path": batch_path,
        "tokenizer_dir": tokenizer_dir,
        "gbt1_path": gbt1_path,
        "run_flags": run_flags_for(args),
        "run_flag_policy": {
            "linked_native_engine_default": True,
            "child_exec_enabled": args.child_exec,
            "child_exec_requires_explicit_phase1_exec_path": True,
            "native_warm_sequence_enabled": args.native_warm_sequence or args.native_extended_warm_sequence,
            "native_extended_warm_sequence_enabled": args.native_extended_warm_sequence,
            "runtime_sampler_enabled": args.runtime_sampler,
            "full_c1_default": "single linked-native pass; warm sequences and child exec are opt-in diagnostics",
        },
        "planned_pqa1_outputs": outputs,
        "qai1_file_count": len(qai1_files),
        "qai1_total_bytes": sum(path.stat().st_size for path in qai1_files),
        "qai1_file_names": [path.name for path in qai1_files],
        "raw_payload_policy": "raw QAI1 generated under /tmp and staged to device only; do not import to git",
    }
    payload["generation_manifest_sha256"] = sha256_json(payload)
    return payload


def phase2_staging_contract(run_label: str, outputs: list[dict[str, Any]]) -> dict[str, Any]:
    termux_root = f"/data/data/com.termux/files/home/Polymath-AI/runtime/gpd_tmp/phase1_c1_pqa1/{run_label}"
    sdcard_bridge_root = f"/sdcard/Download/polymath/polar_phase1_c1/{run_label}"
    return {
        "schema_version": "phase1_c1_to_phase2_staging_contract_v1",
        "phase1_app_outputs_are_not_phase2_contract": True,
        "phase1_app_output_paths": [row["output_pqa1_path"] for row in outputs],
        "preferred_termux_private_pqa1_root": f"{termux_root}/pqa1",
        "preferred_termux_pqa1_list": f"{termux_root}/c1_pqa1_list.txt",
        "sdcard_bridge_root_if_needed": sdcard_bridge_root,
        "bridge_policy": "Execution may bridge raw PQA1 via ADB /tmp or Termux SSH; repo reports contain only path/hash/list metadata.",
        "raw_payload_policy": "raw PQA1 is forbidden in git and Comet assets",
    }


def run_flags_for(args: argparse.Namespace) -> int:
    flags = CHILD_EXEC_FLAG if args.child_exec else 0
    if args.native_warm_sequence or args.native_extended_warm_sequence:
        flags |= NATIVE_WARM_SEQUENCE_FLAG
    if args.native_extended_warm_sequence:
        flags |= NATIVE_EXTENDED_WARM_SEQUENCE_FLAG
    if args.runtime_sampler:
        flags |= RUNTIME_SAMPLER_FLAG
    return flags


def dry_run(args: argparse.Namespace, records: list[dict[str, str]], source_manifest: dict[str, Any], outputs: list[dict[str, Any]], report_root: Path) -> dict[str, Any]:
    report_root.mkdir(parents=True, exist_ok=True)
    write_json(report_root / "phase1_c1_source_manifest.json", source_manifest)
    phase1_metrics = build_phase1_metrics(args, records, source_manifest["input_identity"])
    write_json(report_root / "phase1_c1_metrics_contract.json", phase1_metrics)
    contract = phase2_staging_contract(str(source_manifest["run_label"]), outputs)
    write_json(report_root / "phase1_c1_to_phase2_staging_contract.json", contract)
    findings = report_suffix_findings(report_root)
    write_json(
        report_root / "phase1_c1_dry_run_forbidden_payload_scan.json",
        {"schema_version": "phase1_c1_forbidden_payload_scan_v1", "status": "pass" if not findings else "fail", "findings": findings},
    )
    summary = {
        "schema_version": "phase1_c1_dry_run_summary_v1",
        "status": "dry_run_pass" if not findings else "dry_run_failed",
        "records_selected": len(records),
        "report_root": str(report_root),
        "source_manifest_sha256": source_manifest["source_manifest_sha256"],
        "phase1_metrics_file": str(report_root / "phase1_c1_metrics_contract.json"),
        "phase1_metrics_status": phase1_metrics["status"],
        "phase1_metric_blockers": phase1_metrics["blockers"],
        "phase2_staging_contract": contract,
        "nonclaims": [
            "no_adb_execution",
            "no_qai1_generated",
            "no_pqa1_generated",
            "no_phase2_or_phase3_claim",
        ],
    }
    write_json(report_root / "phase1_c1_dry_run_summary.json", summary)
    return summary


def run_phase1(args: argparse.Namespace, records: list[dict[str, str]], source_manifest: dict[str, Any], outputs: list[dict[str, Any]], report_root: Path, run_label: str) -> dict[str, Any]:
    serial = select_serial()
    local_dir = Path("/tmp") / f"polymath_phase1_c1_{run_label}"
    local_dir.mkdir(parents=True, exist_ok=True)
    remote_dir = (
        f"{INTERNAL_FILES_ROOT}/staged/phase1/c1_{run_label}"
        if args.staging == "internal"
        else f"{STAGED_ROOT}/c1_{run_label}"
    )
    outputs[:] = planned_pqa1_outputs(remote_dir, records, args.scheduler, args.workers, args.chunk_size)

    report_root.mkdir(parents=True, exist_ok=True)
    write_json(report_root / "phase1_c1_source_manifest.json", source_manifest)

    batch_path = stage_batch(local_dir, remote_dir, serial, records, args.scheduler, args.workers, args.chunk_size, args.staging)
    tokenizer_dir = f"{remote_dir}/tokenizer"
    gbt1_path = ensure_gbt1(serial, remote_dir, args.staging)
    generation = build_generation_manifest(
        local_dir=local_dir,
        remote_dir=remote_dir,
        batch_path=batch_path,
        tokenizer_dir=tokenizer_dir,
        gbt1_path=gbt1_path,
        outputs=outputs,
        args=args,
        run_label=run_label,
    )
    write_json(report_root / "phase1_c1_qai1_generation_manifest.json", generation)
    write_json(report_root / "phase1_c1_to_phase2_staging_contract.json", phase2_staging_contract(run_label, outputs))

    settings_original = snapshot_settings(serial)
    settings_target = target_settings()
    game_mode_before = current_game_mode(serial)
    frequency_before = frequency_snapshot(serial)
    flags = run_flags_for(args)
    run_id = ""
    settings_applied: dict[str, str] = {}
    settings_after_run: dict[str, str] = {}
    settings_final: dict[str, str] = {}
    game_mode_target: dict[str, Any] = {}
    frequency_after_apply: dict[str, Any] = {}
    frequency_after_final_apply: dict[str, Any] = {}

    try:
        apply_settings(serial, settings_target)
        settings_applied = snapshot_settings(serial)
        game_mode_target = set_game_mode(serial, "standard")
        frequency_after_apply = frequency_snapshot(serial)
        run_id = launch_and_wait(
            serial,
            tokenizer_dir,
            gbt1_path,
            batch_path,
            args.workers,
            "heap",
            args.timeout_sec,
            run_flags=flags,
            phase1_exec_path=str(args.phase1_exec_path) if args.phase1_exec_path else None,
        )
        settings_after_run = snapshot_settings(serial)
    finally:
        apply_settings(serial, settings_target)
        frequency_after_final_apply = frequency_snapshot(serial)
        settings_final = snapshot_settings(serial)
        write_json(
            report_root / "phase1_c1_settings_profile_evidence.json",
            {
                "schema_version": "phase1_c1_settings_profile_evidence_v1",
                "previous": settings_original,
                "target": settings_target,
                "applied": settings_applied,
                "after_run_before_reapply": settings_after_run,
                "final": settings_final,
                "final_match_target": settings_final == settings_target,
                "game_mode_before": game_mode_before,
                "game_mode_target": game_mode_target,
                "frequency_before": frequency_before,
                "frequency_after_apply": frequency_after_apply,
                "frequency_after_final_apply": frequency_after_final_apply,
                "policy": "high_performance_profile_is_authority_default_no_restore",
                "run_flags": flags,
                "native_warm_sequence_enabled": args.native_warm_sequence or args.native_extended_warm_sequence,
                "native_extended_warm_sequence_enabled": args.native_extended_warm_sequence,
            },
        )

    if not run_id:
        raise SystemExit("Phase 1 app did not produce a report run_id.")

    pulled = pull_run_report(serial, run_id, report_root)
    pqa1_stats = collect_remote_pqa1_stats(serial, outputs, args.staging)
    all_pqa1_outputs_present = all(row.get("sha256") and row.get("bytes") for row in pqa1_stats)
    write_json(
        report_root / "phase1_c1_remote_pqa1_manifest.json",
        {
            "schema_version": "phase1_c1_remote_pqa1_manifest_v1",
            "run_label": run_label,
            "staging": args.staging,
            "remote_dir": remote_dir,
            "pqa1_outputs": pqa1_stats,
            "all_outputs_present": all_pqa1_outputs_present,
            "raw_payload_policy": "remote PQA1 paths and hashes only; raw PQA1 is not pulled into repo reports",
        },
    )

    findings = scan_forbidden(report_root)
    findings.extend(report_suffix_findings(report_root))
    findings = sorted(set(findings))
    write_json(
        report_root / "phase1_c1_forbidden_payload_scan.json",
        {"schema_version": "phase1_c1_forbidden_payload_scan_v1", "status": "pass" if not findings else "fail", "findings": findings},
    )
    if findings:
        raise SystemExit(f"Forbidden payloads were found in report tree: {findings[:3]}")

    app_result_path = pulled / "phase1_app_run_result.json"
    app_result = json.loads(app_result_path.read_text(encoding="utf-8")) if app_result_path.is_file() else {}
    native_phase1_metrics = load_json_file_if_present(pulled / "native_phase1_metrics.json")
    native_batch_metrics = load_json_file_if_present(pulled / "native_batch_metrics.json")
    phase1_metrics = build_phase1_metrics(
        args,
        records,
        source_manifest["input_identity"],
        app_result=app_result,
        native_phase1_metrics=native_phase1_metrics,
        native_batch_metrics=native_batch_metrics,
        pqa1_all_outputs_present=all_pqa1_outputs_present,
    )
    write_json(report_root / "phase1_c1_metrics_contract.json", phase1_metrics)
    summary = {
        "schema_version": "phase1_c1_pipeline_smoke_summary_v1",
        "status": "phase1_c1_smoke_complete" if phase1_metrics["status"] == "pass" else "phase1_c1_runtime_failed",
        "run_label": run_label,
        "serial": serial,
        "package": PACKAGE_NAME,
        "app_report_run_id": run_id,
        "app_report_root": f"{ADB_REPORT_ROOT}/{run_id}",
        "host_report_root": str(report_root),
        "records_selected": len(records),
        "source_manifest_sha256": source_manifest["source_manifest_sha256"],
        "generation_manifest_sha256": generation["generation_manifest_sha256"],
        "token_ids": app_result.get("token_ids"),
        "token_ids_per_sec": app_result.get("token_ids_per_sec"),
        "records_per_sec": app_result.get("records_per_sec"),
        "phase1_metrics_file": str(report_root / "phase1_c1_metrics_contract.json"),
        "phase1_metrics_status": phase1_metrics["status"],
        "phase1_metric_blockers": phase1_metrics["blockers"],
        "material_hash_hex": app_result.get("material_hash_hex"),
        "parity_state": app_result.get("parity_state"),
        "settings_final_match_target": settings_final == settings_target,
        "remote_pqa1_all_outputs_present": all_pqa1_outputs_present,
        "phase2_staging_contract_file": str(report_root / "phase1_c1_to_phase2_staging_contract.json"),
        "forbidden_payload_scan": "pass",
        "nonclaims": [
            "c1_smoke_not_100k_or_1m_authority_gate",
            "no_phase2_pass_claim",
            "no_phase3_authorization",
            "no_standard_profile_product_fallback",
        ],
    }
    write_json(report_root / "phase1_c1_pipeline_smoke_summary.json", summary)
    if phase1_metrics["status"] != "pass":
        raise SystemExit(f"Phase 1 runtime metrics failed: {phase1_metrics['blockers']}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-path", type=Path, default=None, help="C1 QA bridge JSONL. Defaults to train split or full split with --full.")
    parser.add_argument("--full", action="store_true", help="Use the steward-approved full C1 QA bridge input.")
    parser.add_argument("--limit", type=int, default=64, help="Number of records to select. Use 0 for all rows in the selected input.")
    parser.add_argument("--package-root", type=Path, default=None, help="C1 package root. Defaults to the parent of qa_bridge for --input-path.")
    parser.add_argument("--package-manifest", type=Path, default=None, help="C1 package manifest. Defaults to <package-root>/phase_C1_build_manifest.json.")
    parser.add_argument("--corpus-id", default=None, help="Report corpus identity. Defaults to the package root directory name.")
    parser.add_argument("--corpus-phase", default="C1", help="Metric namespace corpus phase, e.g. C1, C2, C2.5, C3, C4.")
    parser.add_argument("--source-kind-map", action="append", default=[], help="Map raw source_kind to Phase 1 enum, e.g. lexis=dictionary.")
    parser.add_argument("--scheduler", choices=["byte_greedy", "dynamic"], default="byte_greedy")
    parser.add_argument("--chunk-size", type=int, default=8192)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--staging", choices=["internal", "external"], default="external")
    parser.add_argument("--out-dir", type=Path, default=Path("runtime/reports/polar_phase1_c1_pipeline"))
    parser.add_argument("--timeout-sec", type=int, default=1800)
    parser.add_argument("--runtime-sampler", action="store_true")
    parser.add_argument("--native-warm-sequence", action="store_true", help="Opt-in warmup/trial sequence for small diagnostics; disabled by default for full C1 completion.")
    parser.add_argument("--native-extended-warm-sequence", action="store_true", help="Opt-in extended warm sequence; implies --native-warm-sequence and is not for full C1 completion.")
    parser.add_argument("--child-exec", action="store_true", help="Opt into executing a separate Phase 1 PIE. Default uses the linked APK-native engine.")
    parser.add_argument("--phase1-exec-path", default=None, help="Explicit device path for --child-exec. Required when --child-exec is used.")
    parser.add_argument("--dry-run", action="store_true", help="Validate C1 and write safe manifests without ADB or QAI1/PQA1 generation.")
    parser.add_argument("--run-label", default=None)
    args = parser.parse_args()

    if args.limit is not None and args.limit < 0:
        raise SystemExit("--limit must be >= 0")
    if args.phase1_exec_path and not args.child_exec:
        raise SystemExit("--phase1-exec-path is only valid with --child-exec")
    if args.child_exec and not args.phase1_exec_path:
        raise SystemExit("--child-exec requires --phase1-exec-path to prevent drifting to an unverified APK lib path")

    input_path = resolve_input_path(args)
    args.package_root = resolve_package_root(args, input_path)
    args.package_manifest = resolve_package_manifest(args, args.package_root)
    args.corpus_id = args.corpus_id or args.package_root.name
    limit = None if args.limit == 0 else args.limit
    kind_map = parse_kind_map(args.source_kind_map)
    records, source_identity = load_c1_records(input_path, limit=limit, kind_map=kind_map)
    stamp = utc_stamp()
    mode = "full" if args.full and limit is None else f"{len(records)}rec"
    run_label = sanitize_label(args.run_label or f"{stamp}_c1_{mode}")
    report_root = args.out_dir / f"{run_label}_phase1_c1_pipeline_smoke"

    remote_dir = (
        f"{INTERNAL_FILES_ROOT}/staged/phase1/c1_{run_label}"
        if args.staging == "internal"
        else f"{STAGED_ROOT}/c1_{run_label}"
    )
    outputs = planned_pqa1_outputs(remote_dir, records, args.scheduler, args.workers, args.chunk_size)
    source_manifest = build_source_manifest(
        args=args,
        records=records,
        source_identity=source_identity,
        report_root=report_root,
        run_label=run_label,
    )

    if args.dry_run:
        summary = dry_run(args, records, source_manifest, outputs, report_root)
    else:
        summary = run_phase1(args, records, source_manifest, outputs, report_root, run_label)

    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

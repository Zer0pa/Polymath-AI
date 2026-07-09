"""Phase34B richer ASVD calibration metadata reports."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from polymath_ai.polar.task_aligned_projection import (
    BLOCKED_STATUS,
    FLOAT32_BYTES,
    HIDDEN_DIM,
    PROJECTION_DIM,
    default_raw_boundary,
    finite_number,
    is_sha256,
    repo_contains,
    report_secret_blockers,
    sha256_canonical_json,
    sha256_file,
    sha256_text,
    utc_stamp,
)


MANIFEST_SCHEMA_VERSION = "phase34b_asvd_calibration_manifest_v1"
RANK_TREND_SCHEMA_VERSION = "phase34b_activation_rank_trend_v1"
CONCAT_SCHEMA_VERSION = "phase34b_asvd_activation_concat_v1"
PASS_STATUS = "pass"


def build_asvd_calibration_manifest(
    *,
    records: Sequence[Mapping[str, Any]],
    run_id: str | None = None,
    target_record_count: int = 128,
    source_identity: Mapping[str, Any] | None = None,
    selection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    record_ids = [str(row.get("record_id", "")) for row in records if row.get("record_id")]
    if len(record_ids) != len(records):
        blockers.append("record_id_missing")
    if len(set(record_ids)) != len(record_ids):
        blockers.append("record_id_not_unique")
    if len(record_ids) < target_record_count:
        blockers.append("calibration_record_count_below_target")

    source_counts = _count_bucket(records, "source_bucket")
    length_counts = _count_bucket(records, "length_bucket")
    answer_counts = _count_bucket(records, "answer_bearing_bucket")
    position_counts = _count_bucket(records, "token_position_bucket")
    for name, counts in {
        "source_bucket": source_counts,
        "length_bucket": length_counts,
        "token_position_bucket": position_counts,
    }.items():
        if len(counts) < 2:
            blockers.append(f"{name}_not_stratified")

    report = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": PASS_STATUS if not blockers else BLOCKED_STATUS,
        "first_missing_green_field": "none" if not blockers else blockers[0],
        "blockers": _dedupe(blockers),
        "created_utc": utc_stamp(),
        "run_id": run_id,
        "target_record_count": target_record_count,
        "record_count": len(record_ids),
        "record_id_set_sha256": sha256_text("\n".join(sorted(record_ids))),
        "source_bucket_counts": source_counts,
        "length_bucket_counts": length_counts,
        "answer_bearing_bucket_counts": answer_counts,
        "token_position_bucket_counts": position_counts,
        "baseline_nll_bucket_counts": _count_bucket(records, "baseline_nll_bucket"),
        "selected_position_policy_sha256": sha256_canonical_json(position_counts),
        "source_identity": dict(source_identity or {}),
        "selection": dict(selection or {}),
        "raw_boundary": default_raw_boundary(),
        "nonclaims": [
            "calibration manifest contains metadata only",
            "calibration manifest does not authorize matrix construction until capture and rank trend pass",
        ],
    }
    secret_blockers = report_secret_blockers(report)
    if secret_blockers:
        report["status"] = BLOCKED_STATUS
        report["first_missing_green_field"] = secret_blockers[0]
        report["blockers"] = _dedupe([*report["blockers"], *secret_blockers])
    return report


def build_stratified_asvd_calibration_from_qa_jsonl(
    *,
    source_qa_jsonl: str | Path,
    selected_raw_jsonl: str | Path,
    run_id: str | None = None,
    target_record_count: int = 128,
    repo_root: str | Path | None = None,
    source_dataset_lineage: str = "",
    heldout_qa_jsonl: str | Path | None = None,
    expected_source_sha256: str = "",
    selection_seed: str = "phase34b_asvd_stratified_v1",
) -> dict[str, Any]:
    source_path = Path(source_qa_jsonl)
    selected_path = Path(selected_raw_jsonl)
    heldout_path = Path(heldout_qa_jsonl) if heldout_qa_jsonl else None
    blockers: list[str] = []
    if not source_path.is_file():
        blockers.append("source_qa_jsonl_absent")
    if repo_root is not None and repo_contains(source_path, repo_root):
        blockers.append("source_qa_jsonl_inside_repo")
    if repo_root is not None and repo_contains(selected_path, repo_root):
        blockers.append("selected_raw_jsonl_inside_repo")

    source_sha = sha256_file(source_path) if source_path.is_file() else ""
    if expected_source_sha256 and source_sha != expected_source_sha256:
        blockers.append("source_qa_jsonl_sha256_mismatch")

    source_records: list[dict[str, Any]] = []
    source_raw_lines: list[str] = []
    if source_path.is_file() and not blockers:
        source_records, source_raw_lines, parse_blockers = _metadata_records_from_qa_jsonl(source_path)
        blockers.extend(parse_blockers)
    if len(source_records) < target_record_count:
        blockers.append("source_record_count_below_target")

    selected_records: list[dict[str, Any]] = []
    selected_indices: list[int] = []
    if not blockers:
        selected_records, selected_indices = _select_stratified_records(
            source_records,
            target_record_count=target_record_count,
            selection_seed=selection_seed,
        )
        if len(selected_records) < target_record_count:
            blockers.append("selected_record_count_below_target")

    selected_bytes = 0
    selected_sha = ""
    selected_line_hash_set_sha = ""
    if not blockers:
        selected_path.parent.mkdir(parents=True, exist_ok=True)
        with selected_path.open("w", encoding="utf-8") as handle:
            for index in selected_indices:
                handle.write(source_raw_lines[index])
        selected_bytes = selected_path.stat().st_size
        selected_sha = sha256_file(selected_path)
        selected_line_hash_set_sha = _line_hash_set_sha(selected_path)

    heldout_overlap = {
        "heldout_present": False,
        "heldout_sha256": "",
        "exact_line_hash_overlap_with_heldout": None,
        "record_id_hash_overlap_with_heldout": None,
        "heldout_line_hash_set_sha256": "",
    }
    if heldout_path is not None:
        if not heldout_path.is_file():
            blockers.append("heldout_qa_jsonl_absent")
        elif repo_root is not None and repo_contains(heldout_path, repo_root):
            blockers.append("heldout_qa_jsonl_inside_repo")
        else:
            heldout_records, _, heldout_blockers = _metadata_records_from_qa_jsonl(heldout_path)
            blockers.extend(f"heldout_{blocker}" for blocker in heldout_blockers)
            selected_line_hashes = set(_line_hashes(selected_path)) if selected_path.is_file() else set()
            heldout_line_hashes = set(_line_hashes(heldout_path))
            selected_record_hashes = {str(record["record_id"]) for record in selected_records}
            heldout_record_hashes = {str(record["record_id"]) for record in heldout_records}
            heldout_overlap = {
                "heldout_present": True,
                "heldout_sha256": sha256_file(heldout_path),
                "exact_line_hash_overlap_with_heldout": len(selected_line_hashes.intersection(heldout_line_hashes)),
                "record_id_hash_overlap_with_heldout": len(selected_record_hashes.intersection(heldout_record_hashes)),
                "heldout_line_hash_set_sha256": sha256_text("\n".join(sorted(heldout_line_hashes))),
            }
            if heldout_overlap["exact_line_hash_overlap_with_heldout"]:
                blockers.append("selected_exact_line_overlap_with_heldout")
            if heldout_overlap["record_id_hash_overlap_with_heldout"]:
                blockers.append("selected_record_id_overlap_with_heldout")

    source_identity = {
        "dataset_lineage": source_dataset_lineage,
        "source_qa_jsonl_sha256": source_sha,
        "source_qa_jsonl_path_sha256": sha256_text(str(source_path)),
        "source_record_count": len(source_records),
        "source_line_hash_set_sha256": _line_hash_set_sha(source_path) if source_path.is_file() else "",
        "expected_source_sha256": expected_source_sha256,
        **heldout_overlap,
    }
    selection = {
        "algorithm": "deterministic_round_robin_over_source_length_position_buckets",
        "selection_seed_sha256": sha256_text(selection_seed),
        "target_record_count": target_record_count,
        "selected_record_count": len(selected_records),
        "selected_raw_jsonl_sha256": selected_sha,
        "selected_raw_jsonl_bytes": selected_bytes,
        "selected_raw_jsonl_path_sha256": sha256_text(str(selected_path)),
        "selected_line_hash_set_sha256": selected_line_hash_set_sha,
        "raw_selected_path_redacted": True,
        "raw_rows_embedded": False,
    }
    report = build_asvd_calibration_manifest(
        records=selected_records,
        run_id=run_id,
        target_record_count=target_record_count,
        source_identity=source_identity,
        selection=selection,
    )
    if blockers:
        report["status"] = BLOCKED_STATUS
        report["first_missing_green_field"] = blockers[0]
        report["blockers"] = _dedupe([*blockers, *report.get("blockers", [])])
    return report


def build_activation_rank_trend_report(
    *,
    chunks: Sequence[Mapping[str, Any]],
    repo_root: str | Path | None = None,
    run_id: str | None = None,
    rank_threshold: int = PROJECTION_DIM,
) -> dict[str, Any]:
    blockers: list[str] = []
    matrices = []
    chunk_reports: list[dict[str, Any]] = []
    total_records = 0
    total_rows = 0
    try:
        import numpy as np  # type: ignore[import-not-found]
    except ImportError:
        np = None  # type: ignore[assignment]
        blockers.append("numpy_unavailable_for_rank_trend")

    if np is not None:
        for index, chunk in enumerate(chunks):
            path = Path(str(chunk.get("activation_capture_f32", "")))
            record_count = int(chunk.get("record_count") or 0)
            expected_sha = str(chunk.get("sha256") or "")
            chunk_blockers: list[str] = []
            if not path.is_file():
                chunk_blockers.append("activation_chunk_file_absent")
                byte_count = 0
                row_count = 0
                actual_sha = ""
            else:
                byte_count = path.stat().st_size
                row_bytes = HIDDEN_DIM * FLOAT32_BYTES
                row_count = byte_count // row_bytes
                actual_sha = sha256_file(path)
                if byte_count % row_bytes:
                    chunk_blockers.append("activation_chunk_byte_count_not_row_aligned")
                if expected_sha and actual_sha != expected_sha:
                    chunk_blockers.append("activation_chunk_sha256_mismatch")
                if repo_root is not None and repo_contains(path, repo_root):
                    chunk_blockers.append("raw_activation_chunk_inside_repo")
                if not chunk_blockers:
                    values = np.memmap(path, dtype="<f4", mode="r", shape=(row_count, HIDDEN_DIM))
                    arr = np.asarray(values, dtype=np.float64)
                    if not bool(np.isfinite(arr).all()):
                        chunk_blockers.append("activation_chunk_nonfinite_values")
                    matrices.append(arr)
            total_records += record_count
            total_rows += row_count
            chunk_reports.append(
                {
                    "chunk_index": index,
                    "record_count": record_count,
                    "row_count": row_count,
                    "capture_sha256": actual_sha,
                    "capture_path_sha256": sha256_text(str(path)),
                    "bytes": byte_count,
                    "blockers": chunk_blockers,
                }
            )
            blockers.extend(chunk_blockers)

    trend: list[dict[str, Any]] = []
    final_stats: dict[str, Any] = {}
    if np is not None and matrices and not blockers:
        cumulative = []
        for index, matrix in enumerate(matrices):
            cumulative.append(matrix)
            stacked = np.vstack(cumulative)
            stats = _rank_stats(stacked)
            trend.append({"chunk_index": index, "cumulative_rows": int(stacked.shape[0]), **stats})
        final_stats = trend[-1]
        if int(final_stats["centered_rank_estimate"]) < rank_threshold:
            blockers.append("activation_capture_rank_below_projection_dim")
        if int(final_stats["effective_rank"]) < 128:
            blockers.append("activation_effective_rank_below_min")
    elif not matrices and "numpy_unavailable_for_rank_trend" not in blockers:
        blockers.append("activation_chunks_absent")

    report = {
        "schema_version": RANK_TREND_SCHEMA_VERSION,
        "status": PASS_STATUS if not blockers else BLOCKED_STATUS,
        "first_missing_green_field": "none" if not blockers else blockers[0],
        "blockers": _dedupe(blockers),
        "created_utc": utc_stamp(),
        "run_id": run_id,
        "chunk_count": len(chunks),
        "calibration_record_count": total_records,
        "calibration_row_count": total_rows,
        "rank_threshold": rank_threshold,
        "chunk_reports": chunk_reports,
        "rank_trend": trend,
        "final_stats": final_stats,
        "raw_boundary": default_raw_boundary(),
        "nonclaims": [
            "rank trend report is a Stage 0 surface gate",
            "rank trend pass is not correlation or Gate E evidence",
            "raw activation rows remain outside git",
        ],
    }
    secret_blockers = report_secret_blockers(report)
    if secret_blockers:
        report["status"] = BLOCKED_STATUS
        report["first_missing_green_field"] = secret_blockers[0]
        report["blockers"] = _dedupe([*report["blockers"], *secret_blockers])
    return report


def build_activation_capture_concat_report(
    *,
    pull_report: Mapping[str, Any],
    output_capture_f32: str | Path,
    repo_root: str | Path | None = None,
    expected_chunk_count: int | None = None,
    expected_output_sha256: str = "",
) -> dict[str, Any]:
    """Concatenate completed Phase34B activation chunks outside git.

    The returned report deliberately records only metadata and hashes. The raw
    `.f32` activation chunks and concatenated output remain in scratch storage.
    """

    blockers: list[str] = []
    output_path = Path(output_capture_f32)
    row_bytes = HIDDEN_DIM * FLOAT32_BYTES
    expected_count = int(expected_chunk_count or pull_report.get("expected_chunk_count") or 0)
    if expected_count <= 0:
        blockers.append("expected_chunk_count_missing")
    if repo_root is not None and repo_contains(output_path, repo_root):
        blockers.append("output_capture_inside_repo")

    chunk_reports_raw = pull_report.get("chunk_reports")
    if not isinstance(chunk_reports_raw, list):
        chunk_reports_raw = []
        blockers.append("chunk_reports_missing")

    completed_reports = [
        chunk
        for chunk in chunk_reports_raw
        if isinstance(chunk, Mapping) and chunk.get("rc") == 0
    ]
    failed_reports = [
        chunk
        for chunk in chunk_reports_raw
        if isinstance(chunk, Mapping) and chunk.get("rc") not in (None, 0)
    ]
    if failed_reports:
        blockers.append("one_or_more_chunks_failed")
    if expected_count and len(completed_reports) != expected_count:
        blockers.append("capture_chain_incomplete")
    if expected_count and len(chunk_reports_raw) < expected_count:
        blockers.append("capture_chunk_count_observed_below_expected")

    rank_input_path = Path(str(pull_report.get("rank_trend_input_path") or ""))
    rank_chunks: list[Mapping[str, Any]] = []
    if not rank_input_path.is_file():
        blockers.append("rank_trend_input_absent")
    else:
        try:
            payload = json.loads(rank_input_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
            blockers.append("rank_trend_input_json_invalid")
        if isinstance(payload, Mapping) and isinstance(payload.get("chunks"), list):
            rank_chunks = [chunk for chunk in payload["chunks"] if isinstance(chunk, Mapping)]
        else:
            blockers.append("rank_trend_input_chunks_missing")

    rank_path_by_label: dict[str, Path] = {}
    for chunk in rank_chunks:
        path = Path(str(chunk.get("activation_capture_f32") or ""))
        label = _label_from_capture_path(path)
        if label:
            rank_path_by_label[label] = path

    chunk_reports: list[dict[str, Any]] = []
    concat_plan: list[tuple[str, Path, int, str]] = []
    for index, chunk in enumerate(sorted(completed_reports, key=lambda item: str(item.get("label") or ""))):
        label = str(chunk.get("label") or "")
        chunk_blockers: list[str] = []
        capture_path = rank_path_by_label.get(label)
        expected_sha = str(chunk.get("capture_sha256") or "")
        expected_bytes = int(chunk.get("capture_bytes") or 0)
        record_count = int(chunk.get("record_count") or 0)
        actual_sha = ""
        actual_bytes = 0
        row_count = 0
        if not label:
            chunk_blockers.append("chunk_label_missing")
        if chunk.get("capture_pulled_to_host_scratch") is not True:
            chunk_blockers.append("capture_not_pulled_to_host_scratch")
        if not is_sha256(expected_sha):
            chunk_blockers.append("capture_sha256_missing_or_invalid")
        if expected_bytes <= 0:
            chunk_blockers.append("capture_bytes_missing")
        if expected_bytes and expected_bytes % row_bytes:
            chunk_blockers.append("capture_byte_count_not_row_aligned")
        if capture_path is None:
            chunk_blockers.append("capture_path_missing_from_rank_trend_input")
        elif not capture_path.is_file():
            chunk_blockers.append("capture_file_absent")
        else:
            actual_bytes = capture_path.stat().st_size
            row_count = actual_bytes // row_bytes
            actual_sha = sha256_file(capture_path)
            if repo_root is not None and repo_contains(capture_path, repo_root):
                chunk_blockers.append("raw_activation_chunk_inside_repo")
            if actual_bytes != expected_bytes:
                chunk_blockers.append("capture_byte_count_mismatch")
            if actual_bytes % row_bytes:
                chunk_blockers.append("capture_byte_count_not_row_aligned")
            if expected_sha and actual_sha != expected_sha:
                chunk_blockers.append("capture_sha256_mismatch")
        if not chunk_blockers and capture_path is not None:
            concat_plan.append((label, capture_path, actual_bytes, actual_sha))
        chunk_reports.append(
            {
                "chunk_index": index,
                "label": label,
                "record_count": record_count,
                "row_count": row_count,
                "bytes": actual_bytes or expected_bytes,
                "capture_sha256": actual_sha or expected_sha,
                "capture_path_sha256": sha256_text(str(capture_path)) if capture_path is not None else "",
                "blockers": chunk_blockers,
            }
        )
        blockers.extend(chunk_blockers)

    output_bytes = 0
    output_sha = ""
    output_row_count = 0
    calibration_record_count = sum(int(chunk.get("record_count") or 0) for chunk in chunk_reports)
    if not blockers:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as out_handle:
            for _, capture_path, _, _ in concat_plan:
                with capture_path.open("rb") as in_handle:
                    for block in iter(lambda: in_handle.read(1024 * 1024), b""):
                        out_handle.write(block)
        output_bytes = output_path.stat().st_size
        output_sha = sha256_file(output_path)
        output_row_count = output_bytes // row_bytes
        if output_bytes != sum(item[2] for item in concat_plan):
            blockers.append("output_capture_byte_count_mismatch")
        if output_bytes % row_bytes:
            blockers.append("output_capture_byte_count_not_row_aligned")
        if expected_output_sha256 and output_sha != expected_output_sha256:
            blockers.append("output_capture_sha256_mismatch")

    report = {
        "schema_version": CONCAT_SCHEMA_VERSION,
        "status": PASS_STATUS if not blockers else BLOCKED_STATUS,
        "first_missing_green_field": "none" if not blockers else blockers[0],
        "blockers": _dedupe(blockers),
        "created_utc": utc_stamp(),
        "run_id": pull_report.get("run_id"),
        "expected_chunk_count": expected_count,
        "chunk_count_observed": int(pull_report.get("chunk_count_observed") or len(chunk_reports_raw)),
        "chunk_count_complete": len(completed_reports),
        "chunk_count_concatenated": len(concat_plan) if not blockers else 0,
        "calibration_record_count": calibration_record_count,
        "output_capture_bytes": output_bytes,
        "output_capture_sha256": output_sha,
        "output_capture_path_sha256": sha256_text(str(output_path)),
        "output_row_count": output_row_count,
        "hidden_dim": HIDDEN_DIM,
        "dtype": "float32",
        "row_bytes": row_bytes,
        "rank_trend_input_sha256": sha256_file(rank_input_path) if rank_input_path.is_file() else "",
        "rank_trend_input_path_sha256": sha256_text(str(rank_input_path)) if str(rank_input_path) else "",
        "chunk_reports": chunk_reports,
        "raw_boundary": default_raw_boundary(),
        "nonclaims": [
            "activation concat is a custody/materialization step, not a rank pass",
            "activation concat is not correlation evidence",
            "activation concat is not Gate E evidence",
            "raw activation rows remain outside git and are not embedded",
        ],
    }
    secret_blockers = report_secret_blockers(report)
    if secret_blockers:
        report["status"] = BLOCKED_STATUS
        report["first_missing_green_field"] = secret_blockers[0]
        report["blockers"] = _dedupe([*report["blockers"], *secret_blockers])
    return report


def _rank_stats(matrix: Any) -> dict[str, Any]:
    import numpy as np  # type: ignore[import-not-found]

    centered = matrix - matrix.mean(axis=0, keepdims=True)
    _, singular_values, _ = np.linalg.svd(centered, full_matrices=False)
    tolerance = float(np.finfo(np.float64).eps * max(centered.shape) * singular_values[0])
    rank = int(np.sum(singular_values > tolerance))
    energy = np.square(singular_values)
    probabilities = energy / energy.sum() if float(energy.sum()) > 0.0 else energy
    nonzero = probabilities[probabilities > 0.0]
    effective_rank = float(np.exp(-np.sum(nonzero * np.log(nonzero)))) if len(nonzero) else 0.0
    return {
        "centered_rank_estimate": rank,
        "effective_rank": effective_rank,
        "top256_energy_ratio": float(energy[:PROJECTION_DIM].sum() / energy.sum()) if float(energy.sum()) > 0.0 else None,
        "singular_value_1": float(singular_values[0]),
        "singular_value_256": float(singular_values[PROJECTION_DIM - 1]) if len(singular_values) >= PROJECTION_DIM else None,
        "singular_value_last": float(singular_values[-1]),
    }


def _label_from_capture_path(path: Path) -> str:
    name = path.name
    if name.startswith("layer24_") and name.endswith("_capture.f32"):
        return name.removeprefix("layer24_").removesuffix("_capture.f32")
    return ""


def _metadata_records_from_qa_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    records: list[dict[str, Any]] = []
    raw_lines: list[str] = []
    blockers: list[str] = []
    seen_ids: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_index, line in enumerate(handle):
            raw_lines.append(line)
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                blockers.append("source_json_decode_error")
                continue
            if not isinstance(payload, dict):
                blockers.append("source_row_not_object")
                continue
            record_id = str(payload.get("record_id") or "")
            if not record_id:
                blockers.append("source_record_id_missing")
                record_hash = sha256_text(f"line_index:{line_index}")
            else:
                record_hash = sha256_text(record_id)
            if record_hash in seen_ids:
                blockers.append("source_record_id_hash_not_unique")
            seen_ids.add(record_hash)
            question = str(payload.get("question") or "")
            answer = str(payload.get("answer") or "")
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            enrichment = metadata.get("enrichment") if isinstance(metadata.get("enrichment"), dict) else {}
            domain = _safe_bucket(enrichment.get("domain") or metadata.get("runtime_source_kind") or payload.get("source_kind"))
            register = _safe_bucket(enrichment.get("register") or metadata.get("corpus_subtype"))
            frame_hash_bin = sha256_text(str(enrichment.get("frame") or "missing"))[:2]
            answer_word_count = _wordish_count(answer)
            records.append(
                {
                    "record_id": record_hash,
                    "source_bucket": f"domain:{domain}|register:{register}|frame_bin:{frame_hash_bin}",
                    "length_bucket": "",
                    "answer_bearing_bucket": _answer_length_bucket(answer_word_count),
                    "token_position_bucket": "",
                    "baseline_nll_bucket": "not_measured_stage0",
                    "_total_char_count": len(question) + len(answer),
                    "_answer_word_count": answer_word_count,
                }
            )
    _assign_quantile_buckets(records, source_key="_total_char_count", output_key="length_bucket", prefix="chars")
    _assign_quantile_buckets(records, source_key="_answer_word_count", output_key="token_position_bucket", prefix="answer_words")
    return records, raw_lines, _dedupe(blockers)


def _select_stratified_records(
    records: Sequence[Mapping[str, Any]],
    *,
    target_record_count: int,
    selection_seed: str,
) -> tuple[list[dict[str, Any]], list[int]]:
    groups: dict[tuple[str, str, str], list[tuple[int, Mapping[str, Any]]]] = defaultdict(list)
    for index, record in enumerate(records):
        key = (
            str(record.get("source_bucket")),
            str(record.get("length_bucket")),
            str(record.get("token_position_bucket")),
        )
        groups[key].append((index, record))
    queues: dict[tuple[str, str, str], deque[tuple[int, Mapping[str, Any]]]] = {}
    for key, values in groups.items():
        sorted_values = sorted(
            values,
            key=lambda item: sha256_text(f"{selection_seed}:{item[1].get('record_id')}"),
        )
        queues[key] = deque(sorted_values)

    selected_records: list[dict[str, Any]] = []
    selected_indices: list[int] = []
    active_keys = sorted(queues, key=lambda key: sha256_text(f"{selection_seed}:{key}"))
    while len(selected_records) < target_record_count and active_keys:
        next_keys: list[tuple[str, str, str]] = []
        for key in active_keys:
            queue = queues[key]
            if not queue:
                continue
            index, record = queue.popleft()
            selected_indices.append(index)
            selected_records.append(dict(record))
            if len(selected_records) >= target_record_count:
                break
            if queue:
                next_keys.append(key)
        active_keys = next_keys
    return selected_records, selected_indices


def _line_hashes(path: Path) -> Iterable[str]:
    with path.open("rb") as handle:
        for line in handle:
            yield sha256_text(line.decode("utf-8", errors="replace").rstrip("\n"))


def _line_hash_set_sha(path: Path) -> str:
    return sha256_text("\n".join(sorted(_line_hashes(path))))


def _safe_bucket(value: Any) -> str:
    text = str(value or "missing").strip().lower()
    return "".join(ch if ch.isalnum() else "_" for ch in text).strip("_") or "missing"


def _wordish_count(text: str) -> int:
    return len([part for part in text.replace("\n", " ").split(" ") if part.strip()])


def _assign_quantile_buckets(
    records: list[dict[str, Any]],
    *,
    source_key: str,
    output_key: str,
    prefix: str,
    bucket_count: int = 4,
) -> None:
    if not records:
        return
    values = sorted(int(record.get(source_key) or 0) for record in records)
    thresholds = [values[max(0, min(len(values) - 1, (len(values) * q) // bucket_count))] for q in range(1, bucket_count)]
    for record in records:
        value = int(record.get(source_key) or 0)
        bucket_index = 0
        for threshold in thresholds:
            if value > threshold:
                bucket_index += 1
        record[output_key] = f"{prefix}_q{bucket_index + 1:02d}_of_{bucket_count:02d}"


def _char_length_bucket(length: int) -> str:
    if length < 256:
        return "chars_0000_0255"
    if length < 512:
        return "chars_0256_0511"
    if length < 1024:
        return "chars_0512_1023"
    return "chars_1024_plus"


def _answer_length_bucket(word_count: int) -> str:
    if word_count <= 8:
        return "answer_words_000_008"
    if word_count <= 24:
        return "answer_words_009_024"
    if word_count <= 48:
        return "answer_words_025_048"
    return "answer_words_049_plus"


def _token_position_bucket(word_count: int) -> str:
    if word_count <= 4:
        return "expected_answer_positions_early"
    if word_count <= 16:
        return "expected_answer_positions_early_mid"
    if word_count <= 40:
        return "expected_answer_positions_mid_late"
    return "expected_answer_positions_late"


def _count_bucket(records: Sequence[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts = Counter(str(row.get(key, "missing")) for row in records)
    return dict(sorted(counts.items()))


def _dedupe(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))

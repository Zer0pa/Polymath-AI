from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

from polymath_ai.polar.asvd_calibration import build_activation_capture_concat_report
from polymath_ai.polar.task_aligned_projection import FLOAT32_BYTES, HIDDEN_DIM, sha256_file


def test_activation_capture_concat_passes_metadata_only(tmp_path: Path) -> None:
    scratch = tmp_path / "outside"
    pull_report = _write_pull_surface(scratch, chunk_count=2)
    output = scratch / "concat" / "layer24_concat.f32"

    report = build_activation_capture_concat_report(
        pull_report=pull_report,
        output_capture_f32=output,
        repo_root=tmp_path / "repo",
        expected_chunk_count=2,
    )

    assert report["status"] == "pass"
    assert report["schema_version"] == "phase34b_asvd_activation_concat_v1"
    assert report["chunk_count_concatenated"] == 2
    assert report["output_capture_bytes"] == 3 * HIDDEN_DIM * FLOAT32_BYTES
    assert report["output_row_count"] == 3
    assert report["calibration_record_count"] == 16
    assert report["output_capture_sha256"] == sha256_file(output)
    assert str(output) not in json.dumps(report)
    assert report["raw_boundary"]["raw_tensors_embedded"] is False


def test_activation_capture_concat_blocks_incomplete_chain(tmp_path: Path) -> None:
    scratch = tmp_path / "outside"
    pull_report = _write_pull_surface(scratch, chunk_count=1)

    report = build_activation_capture_concat_report(
        pull_report=pull_report,
        output_capture_f32=scratch / "concat.f32",
        repo_root=tmp_path / "repo",
        expected_chunk_count=2,
    )

    assert report["status"] == "blocked_fail_closed"
    assert report["first_missing_green_field"] == "capture_chain_incomplete"
    assert "capture_chunk_count_observed_below_expected" in report["blockers"]


def test_activation_capture_concat_blocks_sha_mismatch(tmp_path: Path) -> None:
    scratch = tmp_path / "outside"
    pull_report = _write_pull_surface(scratch, chunk_count=1)
    pull_report["chunk_reports"][0]["capture_sha256"] = "0" * 64

    report = build_activation_capture_concat_report(
        pull_report=pull_report,
        output_capture_f32=scratch / "concat.f32",
        repo_root=tmp_path / "repo",
        expected_chunk_count=1,
    )

    assert report["status"] == "blocked_fail_closed"
    assert "capture_sha256_mismatch" in report["blockers"]


def test_activation_capture_concat_blocks_output_inside_repo(tmp_path: Path) -> None:
    scratch = tmp_path / "outside"
    repo = tmp_path / "repo"
    repo.mkdir()
    pull_report = _write_pull_surface(scratch, chunk_count=1)

    report = build_activation_capture_concat_report(
        pull_report=pull_report,
        output_capture_f32=repo / "concat.f32",
        repo_root=repo,
        expected_chunk_count=1,
    )

    assert report["status"] == "blocked_fail_closed"
    assert report["first_missing_green_field"] == "output_capture_inside_repo"


def _write_pull_surface(scratch: Path, *, chunk_count: int) -> dict:
    captures = scratch / "activation_captures"
    metadata = scratch / "pulled_metadata"
    captures.mkdir(parents=True)
    metadata.mkdir(parents=True)
    chunks = []
    rank_chunks = []
    for index in range(chunk_count):
        label = f"chunk{index:02d}"
        path = captures / f"layer24_{label}_capture.f32"
        rows = index + 1
        _write_capture(path, rows=rows, offset=index * 1000.0)
        capture_sha = sha256_file(path)
        chunks.append(
            {
                "label": label,
                "rc": 0,
                "record_count": 8,
                "capture_pulled_to_host_scratch": True,
                "capture_sha256": capture_sha,
                "capture_bytes": path.stat().st_size,
            }
        )
        rank_chunks.append(
            {
                "activation_capture_f32": str(path),
                "record_count": 8,
                "sha256": capture_sha,
            }
        )
    rank_input = metadata / "phase34b_rank_trend_input.json"
    rank_input.write_text(json.dumps({"run_id": "unit", "chunks": rank_chunks}), encoding="utf-8")
    return {
        "run_id": "unit",
        "expected_chunk_count": chunk_count,
        "chunk_count_observed": chunk_count,
        "chunk_count_complete": chunk_count,
        "rank_trend_input_path": str(rank_input),
        "chunk_reports": chunks,
    }


def _write_capture(path: Path, *, rows: int, offset: float) -> None:
    pack = struct.Struct("<f").pack
    with path.open("wb") as handle:
        for row in range(rows):
            for col in range(HIDDEN_DIM):
                handle.write(pack(offset + row + (col / HIDDEN_DIM)))

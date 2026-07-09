from __future__ import annotations

import json

from polymath_ai.polar.asvd_calibration import (
    build_asvd_calibration_manifest,
    build_stratified_asvd_calibration_from_qa_jsonl,
)


def test_asvd_calibration_manifest_passes_with_strata() -> None:
    records = [
        {
            "record_id": f"r{i:03d}",
            "source_bucket": "qa" if i % 2 else "math",
            "length_bucket": "short" if i % 3 else "long",
            "answer_bearing_bucket": "answer" if i % 2 else "context",
            "token_position_bucket": "early" if i % 2 else "late",
        }
        for i in range(128)
    ]

    report = build_asvd_calibration_manifest(records=records)

    assert report["status"] == "pass"
    assert report["record_count"] == 128
    assert report["source_bucket_counts"]["math"] == 64
    assert report["raw_boundary"]["raw_rows_embedded"] is False


def test_asvd_calibration_manifest_blocks_unstratified_records() -> None:
    records = [
        {
            "record_id": f"r{i:03d}",
            "source_bucket": "same",
            "length_bucket": "short",
            "answer_bearing_bucket": "answer",
            "token_position_bucket": "early",
        }
        for i in range(4)
    ]

    report = build_asvd_calibration_manifest(records=records)

    assert report["status"] == "blocked_fail_closed"
    assert "calibration_record_count_below_target" in report["blockers"]
    assert "source_bucket_not_stratified" in report["blockers"]


def test_stratified_subset_materializer_writes_raw_outside_repo_and_report_is_metadata_only(tmp_path) -> None:
    source = tmp_path / "source.qa.jsonl"
    selected = tmp_path / "selected.qa.jsonl"
    rows = []
    domains = ["scientific", "technical", "everyday", "legal"]
    registers = ["formal", "neutral"]
    for index in range(64):
        answer = " ".join(["definition"] * (4 + index % 32))
        rows.append(
            {
                "record_id": f"record-{index:03d}",
                "question": f"What is concept {index}?",
                "answer": answer,
                "source_kind": "vocab_expansion",
                "relation_type": "definition",
                "metadata": {
                    "enrichment": {
                        "domain": domains[index % len(domains)],
                        "register": registers[index % len(registers)],
                    }
                },
            }
        )
    source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    report = build_stratified_asvd_calibration_from_qa_jsonl(
        source_qa_jsonl=source,
        selected_raw_jsonl=selected,
        target_record_count=32,
        repo_root=tmp_path / "repo",
        source_dataset_lineage="synthetic",
    )

    assert report["status"] == "pass"
    assert selected.exists()
    assert report["record_count"] == 32
    assert report["selection"]["raw_selected_path_redacted"] is True
    assert report["selection"]["selected_raw_jsonl_path_sha256"]
    assert "concept" not in json.dumps(report)
    assert "definition definition" not in json.dumps(report)

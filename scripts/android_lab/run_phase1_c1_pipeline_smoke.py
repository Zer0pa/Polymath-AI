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
sys.path.insert(0, str(SCRIPT_DIR))

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
    CHILD_EXEC_WARM_FLAGS,
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
DEFAULT_PACKAGE_MANIFEST = C1_ROOT / "phase_C1_build_manifest.json"

PHASE1_SOURCE_KINDS = {"dictionary", "megascience", "synthetic_stress", "user_supplied"}
DEFAULT_SOURCE_KIND_MAP = {"lexatlas": "dictionary"}
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
        "corpus": "C1_lexatlas_frontier_gpt_enriched_scale_v1",
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


def dry_run(args: argparse.Namespace, records: list[dict[str, str]], source_manifest: dict[str, Any], outputs: list[dict[str, Any]], report_root: Path) -> dict[str, Any]:
    report_root.mkdir(parents=True, exist_ok=True)
    write_json(report_root / "phase1_c1_source_manifest.json", source_manifest)
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
    flags = CHILD_EXEC_WARM_FLAGS | (RUNTIME_SAMPLER_FLAG if args.runtime_sampler else 0)
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
            },
        )

    if not run_id:
        raise SystemExit("Phase 1 app did not produce a report run_id.")

    pulled = pull_run_report(serial, run_id, report_root)
    pqa1_stats = collect_remote_pqa1_stats(serial, outputs, args.staging)
    write_json(
        report_root / "phase1_c1_remote_pqa1_manifest.json",
        {
            "schema_version": "phase1_c1_remote_pqa1_manifest_v1",
            "run_label": run_label,
            "staging": args.staging,
            "remote_dir": remote_dir,
            "pqa1_outputs": pqa1_stats,
            "all_outputs_present": all(row.get("sha256") and row.get("bytes") for row in pqa1_stats),
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
    summary = {
        "schema_version": "phase1_c1_pipeline_smoke_summary_v1",
        "status": "phase1_c1_smoke_complete",
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
        "material_hash_hex": app_result.get("material_hash_hex"),
        "parity_state": app_result.get("parity_state"),
        "settings_final_match_target": settings_final == settings_target,
        "remote_pqa1_all_outputs_present": all(row.get("sha256") and row.get("bytes") for row in pqa1_stats),
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
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-path", type=Path, default=None, help="C1 QA bridge JSONL. Defaults to train split or full split with --full.")
    parser.add_argument("--full", action="store_true", help="Use the steward-approved full C1 QA bridge input.")
    parser.add_argument("--limit", type=int, default=64, help="Number of records to select. Use 0 with --full for all rows.")
    parser.add_argument("--package-root", type=Path, default=C1_ROOT)
    parser.add_argument("--package-manifest", type=Path, default=DEFAULT_PACKAGE_MANIFEST)
    parser.add_argument("--source-kind-map", action="append", default=[], help="Map raw source_kind to Phase 1 enum, e.g. lexis=dictionary.")
    parser.add_argument("--scheduler", choices=["byte_greedy", "dynamic"], default="byte_greedy")
    parser.add_argument("--chunk-size", type=int, default=8192)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--staging", choices=["internal", "external"], default="external")
    parser.add_argument("--out-dir", type=Path, default=Path("runtime/reports/polar_phase1_c1_pipeline"))
    parser.add_argument("--timeout-sec", type=int, default=1800)
    parser.add_argument("--runtime-sampler", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Validate C1 and write safe manifests without ADB or QAI1/PQA1 generation.")
    parser.add_argument("--run-label", default=None)
    args = parser.parse_args()

    if args.limit is not None and args.limit < 0:
        raise SystemExit("--limit must be >= 0")

    input_path = resolve_input_path(args)
    limit = None if args.full and args.limit == 0 else args.limit
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

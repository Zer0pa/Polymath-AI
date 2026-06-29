#!/usr/bin/env python3
"""Run exact Phase 1 closure material through standalone and APK paths.

The export contains raw QAI1/PQA1 benchmark material. This runner keeps raw
payloads in /tmp and on-device staging only. Repository report output is limited
to JSON/Markdown authority evidence and never pulls QAI1/PQA1 payloads.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from run_phase1_apk_benchmark import (  # noqa: E402
    ADB_REPORT_ROOT,
    GBT1_SHA256,
    INTERNAL_FILES_ROOT,
    PACKAGE_NAME,
    STAGED_ROOT,
    TERMUX_BASELINES,
    adb,
    internal_relative,
    launch_and_wait,
    pull_run_report,
    run_as,
    scan_forbidden,
    select_serial,
    shell_quote,
    sha256_file,
    write_json,
)


DEFAULT_EXPORT_ROOT = Path("/tmp/polymath_android_lab_phase1_exact_closure_material_export/android_lab_phase1_exact_closure_material_export")
VOCAB_SHA256 = "0e43bafc96037bed92fabea31282eb10ad094ec921748a58f6be10dbf9796f74"
MERGES_SHA256 = "6c99efe1bfe6b70092d531cad0a57278182652a2380aa5fb33e99d4e4eeb905f"
PROMOTED_TRIALS = {
    "10k": "tenk_heap_dyn_c512_trial2",
    "100k": "hundredk_heap_static_bg8_trial2",
    "1m": "million_heap_dyn_c8192_trial0",
}
EXPECTED_MATERIAL_HASHES = {
    "10k": "c13b0ce3ee132871ca59d6d580965dfad56108a057456542e8db33be7bb9a652",
    "100k": "f9647ebfc3261e236ad66edd4379272379e2fb25ede64248965b0bf08185f38e",
    "1m": "9fe1b93ddb5f6485eadaf784a42943419b7dc6a6161fc9d7509e29061efada08",
}
FORBIDDEN_SUFFIXES = (".qai1", ".pqa1", ".jsonl", ".safetensors", ".bin", ".pt", ".pth", ".onnx", ".tflite", ".apk", ".aab")


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def run(argv: list[str], *, timeout: int = 60, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed {proc.returncode}: {' '.join(argv)}\n{proc.stdout[-2000:]}\n{proc.stderr[-4000:]}")
    return proc


def read_batch_rows(batch_path: Path) -> list[tuple[str, str, str, str]]:
    rows = []
    for line in batch_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            raise ValueError(f"expected four-column batch row in {batch_path}: {line[:160]}")
        rows.append((parts[0], parts[1], parts[2], parts[3]))
    return rows


def parse_pqa1_summary(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 144 or data[:4] != b"PQA1":
        raise ValueError(f"bad PQA1 header: {path}")
    records = int.from_bytes(data[8:16], "little")
    offset = 144
    token_total = 0
    seen = 0
    while seen < records:
        if offset + 15 > len(data):
            raise ValueError(f"truncated PQA1 record at {seen}: {path}")
        offset += 9
        token_count = int.from_bytes(data[offset : offset + 4], "little")
        offset += 4
        segment_count = int.from_bytes(data[offset : offset + 2], "little")
        offset += 2
        token_total += token_count
        offset += token_count * 4 + segment_count * 18
        seen += 1
    if offset != len(data):
        raise ValueError(f"PQA1 trailing bytes in {path}: offset={offset} len={len(data)}")
    return {
        "records": records,
        "token_ids": token_total,
        "bytes": len(data),
        "sha256": sha256_file(path),
    }


def summarize_trial_material(trial_dir: Path) -> dict[str, Any]:
    rows = read_batch_rows(trial_dir / "batch.tsv")
    input_bytes = 0
    output_bytes = 0
    records = 0
    token_ids = 0
    output_hashes = []
    for index, _row in enumerate(rows):
        local_input = trial_dir / f"in_{index:04d}.qai1"
        local_output = trial_dir / f"out_{index:04d}.pqa1"
        if not local_input.is_file() or not local_output.is_file():
            raise FileNotFoundError(f"missing exact material pair for job {index} in {trial_dir}")
        input_bytes += local_input.stat().st_size
        pqa = parse_pqa1_summary(local_output)
        output_bytes += int(pqa["bytes"])
        records += int(pqa["records"])
        token_ids += int(pqa["token_ids"])
        output_hashes.append(str(pqa["sha256"]))
    material_hash = hashlib.sha256("".join(sorted(output_hashes)).encode("utf-8")).hexdigest()
    return {
        "trial": trial_dir.name,
        "job_count": len(rows),
        "input_bytes": input_bytes,
        "output_bytes": output_bytes,
        "records": records,
        "token_ids": token_ids,
        "material_hash_hex": material_hash,
        "output_sha256s": output_hashes,
    }


def make_input_link_dir(trial_dir: Path, work_dir: Path) -> Path:
    input_dir = work_dir / "inputs"
    if input_dir.exists():
        shutil.rmtree(input_dir)
    input_dir.mkdir(parents=True)
    for source in sorted(trial_dir.glob("in_*.qai1")):
        target = input_dir / source.name
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)
    return input_dir


def build_remote_batch(trial_dir: Path, local_batch: Path, remote_dir: str) -> str:
    rows = read_batch_rows(trial_dir / "batch.tsv")
    lines = []
    for index, _row in enumerate(rows):
        lines.append(
            "\t".join(
                [
                    f"{remote_dir}/inputs/in_{index:04d}.qai1",
                    f"{remote_dir}/outputs/out_{index:04d}.pqa1",
                    f"{remote_dir}/outputs/writer_{index:04d}.json",
                    f"{remote_dir}/outputs/bpe_{index:04d}.json",
                ]
            )
            + "\n"
        )
    local_batch.write_text("".join(lines), encoding="utf-8")
    return f"{remote_dir}/batch.tsv"


def ensure_internal_table(serial: str, table_path: Path, remote_dir: str) -> str:
    observed = sha256_file(table_path)
    if observed != GBT1_SHA256:
        raise SystemExit(f"GBT1 hash mismatch in exact export: {observed}")
    tmp_dir = f"/data/local/tmp/polymath_phase1_exact_table_{utc_stamp()}"
    tmp_path = f"{tmp_dir}/gemma4_bpe.gbt1"
    remote_path = f"{remote_dir}/tokenizer/gemma4_bpe.gbt1"
    adb(serial, "shell", "rm", "-rf", tmp_dir, timeout=30, check=False)
    adb(serial, "shell", "mkdir", "-p", tmp_dir, timeout=20)
    adb(serial, "push", str(table_path), tmp_path, timeout=300)
    run_as(serial, f"mkdir -p {shell_quote(internal_relative(remote_path).rsplit('/', 1)[0])}", timeout=30)
    run_as(serial, f"cp {shell_quote(tmp_path)} {shell_quote(internal_relative(remote_path))}", timeout=300)
    device_sha = run_as(serial, f"sha256sum {shell_quote(internal_relative(remote_path))}", timeout=120).stdout.split()[0]
    adb(serial, "shell", "rm", "-rf", tmp_dir, timeout=30, check=False)
    if device_sha != GBT1_SHA256:
        raise SystemExit(f"Device GBT1 hash mismatch: {device_sha}")
    return remote_path


def stage_trial_internal(serial: str, trial_dir: Path, local_work_dir: Path, remote_dir: str) -> str:
    input_dir = make_input_link_dir(trial_dir, local_work_dir)
    local_batch = local_work_dir / "batch.tsv"
    batch_path = build_remote_batch(trial_dir, local_batch, remote_dir)
    tmp_dir = f"/data/local/tmp/polymath_phase1_exact_stage_{utc_stamp()}"
    adb(serial, "shell", "rm", "-rf", tmp_dir, timeout=30, check=False)
    adb(serial, "shell", "mkdir", "-p", tmp_dir, timeout=20)
    adb(serial, "push", str(input_dir), f"{tmp_dir}/", timeout=1200)
    adb(serial, "push", str(local_batch), f"{tmp_dir}/batch.tsv", timeout=120)
    rel_dir = internal_relative(remote_dir)
    run_as(serial, f"rm -rf {shell_quote(rel_dir)} && mkdir -p {shell_quote(rel_dir)}", timeout=120)
    run_as(serial, f"cp -R {shell_quote(tmp_dir + '/inputs')} {shell_quote(rel_dir + '/inputs')}", timeout=1200)
    run_as(serial, f"mkdir -p {shell_quote(rel_dir + '/outputs')} && cp {shell_quote(tmp_dir + '/batch.tsv')} {shell_quote(rel_dir + '/batch.tsv')}", timeout=120)
    adb(serial, "shell", "rm", "-rf", tmp_dir, timeout=30, check=False)
    return batch_path


def ensure_external_table(serial: str, table_path: Path, remote_dir: str) -> str:
    observed = sha256_file(table_path)
    if observed != GBT1_SHA256:
        raise SystemExit(f"GBT1 hash mismatch in exact export: {observed}")
    remote_path = f"{remote_dir}/tokenizer/gemma4_bpe.gbt1"
    adb(serial, "shell", "mkdir", "-p", f"{remote_dir}/tokenizer", timeout=20)
    adb(serial, "push", str(table_path), remote_path, timeout=300)
    device_sha = adb(serial, "shell", "sha256sum", remote_path, timeout=120).stdout.split()[0]
    if device_sha != GBT1_SHA256:
        raise SystemExit(f"Device GBT1 hash mismatch: {device_sha}")
    return remote_path


def stage_trial_external(serial: str, trial_dir: Path, local_work_dir: Path, remote_dir: str) -> str:
    input_dir = make_input_link_dir(trial_dir, local_work_dir)
    local_batch = local_work_dir / "batch.tsv"
    batch_path = build_remote_batch(trial_dir, local_batch, remote_dir)
    adb(serial, "shell", "rm", "-rf", remote_dir, timeout=120, check=False)
    adb(serial, "shell", "mkdir", "-p", f"{remote_dir}/inputs", f"{remote_dir}/outputs", timeout=30)
    adb(serial, "push", str(input_dir), f"{remote_dir}/", timeout=1200)
    adb(serial, "push", str(local_batch), f"{remote_dir}/batch.tsv", timeout=120)
    return batch_path


def set_game_mode(serial: str, mode: str) -> dict[str, Any]:
    if mode == "leave":
        return {"requested_mode": mode, "set_command": None}
    before = adb(serial, "shell", "cmd", "game", "list-modes", PACKAGE_NAME, timeout=20, check=False)
    set_result = adb(serial, "shell", "cmd", "game", "mode", mode, PACKAGE_NAME, timeout=20, check=False)
    after = adb(serial, "shell", "cmd", "game", "list-modes", PACKAGE_NAME, timeout=20, check=False)
    return {
        "requested_mode": mode,
        "before": before.stdout.strip(),
        "set_returncode": set_result.returncode,
        "set_stdout": set_result.stdout.strip(),
        "set_stderr": set_result.stderr.strip(),
        "after": after.stdout.strip(),
    }


def app_benchmark(
    *,
    serial: str,
    export_root: Path,
    trial_key: str,
    trial_dir: Path,
    expected: dict[str, Any],
    report_dir: Path,
    game_mode: str,
    staging: str,
    timeout_sec: int,
    run_flags: int,
) -> dict[str, Any]:
    stamp = utc_stamp()
    remote_dir = (
        f"{INTERNAL_FILES_ROOT}/staged/phase1/exact_{stamp}_{trial_dir.name}"
        if staging == "internal"
        else f"{STAGED_ROOT}/exact_{stamp}_{trial_dir.name}"
    )
    local_work_dir = Path("/tmp") / f"polymath_phase1_exact_apk_{stamp}_{trial_dir.name}"
    local_work_dir.mkdir(parents=True, exist_ok=True)
    batch_path = (
        stage_trial_internal(serial, trial_dir, local_work_dir, remote_dir)
        if staging == "internal"
        else stage_trial_external(serial, trial_dir, local_work_dir, remote_dir)
    )
    tokenizer_dir = f"{remote_dir}/tokenizer"
    gbt1_path = (
        ensure_internal_table(serial, export_root / "tokenizer/packed/gemma4_bpe.gbt1", remote_dir)
        if staging == "internal"
        else ensure_external_table(serial, export_root / "tokenizer/packed/gemma4_bpe.gbt1", remote_dir)
    )
    mode_evidence = set_game_mode(serial, game_mode)
    run_id = launch_and_wait(serial, tokenizer_dir, gbt1_path, batch_path, 8, "heap", timeout_sec, run_flags=run_flags)
    pulled = pull_run_report(serial, run_id, report_dir)
    findings = scan_forbidden(report_dir)
    app_result = json.loads((pulled / "phase1_app_run_result.json").read_text(encoding="utf-8"))
    exact_material_pass = app_result.get("material_hash_hex") == expected["material_hash_hex"]
    token_pass = int(app_result.get("token_ids", -1)) == int(expected["token_ids"])
    record_pass = int(app_result.get("records", -1)) == int(expected["records"])
    wall_sec = float(app_result.get("wall_sec", 0.0))
    decimal_mb_per_sec = (float(expected["input_bytes"]) / 1_000_000.0) / wall_sec if wall_sec > 0 else 0.0
    baseline = TERMUX_BASELINES[trial_key]
    summary = {
        "schema_version": "phase1_exact_closure_apk_benchmark_summary_v1",
        "status": "probe",
        "trial_key": trial_key,
        "trial": trial_dir.name,
        "run_id": run_id,
        "expected": {key: value for key, value in expected.items() if key != "output_sha256s"},
        "app_result": app_result,
        "exact_material_parity": "pass" if exact_material_pass and token_pass and record_pass else "fail",
        "record_count_parity": record_pass,
        "token_count_parity": token_pass,
        "material_hash_parity": exact_material_pass,
        "input_decimal_mb_per_sec": decimal_mb_per_sec,
        "termux_baseline": baseline,
        "ratio_vs_termux_token_ids_per_sec": float(app_result.get("token_ids_per_sec", 0.0)) / float(baseline["token_ids_per_sec"]),
        "ratio_vs_termux_records_per_sec": float(app_result.get("records_per_sec", 0.0)) / float(baseline["records_per_sec"]),
        "game_mode_evidence": mode_evidence,
        "staging": staging,
        "run_flags": run_flags,
        "forbidden_payload_scan": {"status": "pass" if not findings else "fail", "findings": findings},
        "artifact_hashes": {
            "export_manifest_sha256": sha256_file(export_root / "EXPORT_MANIFEST.json"),
            "gbt1_sha256": sha256_file(export_root / "tokenizer/packed/gemma4_bpe.gbt1"),
            "phase1_source_sha256": sha256_file(export_root / "source/native/polar_phase1_zig/phase1_qa_stream.zig"),
        },
        "raw_payload_policy": "raw QAI1/PQA1 stayed in /tmp and device staging; repository report forbids raw payload suffixes",
        "nonclaims": [
            "no_game_mode_benefit_claim",
            "no_redmagic_rise_or_diablo_claim",
            "no_public_corpus_claim",
        ],
    }
    write_json(report_dir / "phase1_exact_closure_apk_benchmark_summary.json", summary)
    write_json(report_dir / "phase1_exact_closure_forbidden_payload_scan.json", summary["forbidden_payload_scan"])
    if findings:
        raise SystemExit("Forbidden payloads were pulled into the report tree; refusing to continue.")
    return summary


def stage_standalone_trial(serial: str, export_root: Path, trial_dir: Path, local_work_dir: Path, remote_dir: str) -> str:
    input_dir = make_input_link_dir(trial_dir, local_work_dir)
    local_batch = local_work_dir / "batch.tsv"
    batch_path = build_remote_batch(trial_dir, local_batch, remote_dir)
    adb(serial, "shell", "rm", "-rf", remote_dir, timeout=60, check=False)
    adb(serial, "shell", "mkdir", "-p", f"{remote_dir}/inputs", f"{remote_dir}/outputs", f"{remote_dir}/tokenizer", timeout=30)
    adb(serial, "push", str(input_dir), f"{remote_dir}/", timeout=1200)
    adb(serial, "push", str(local_batch), f"{remote_dir}/batch.tsv", timeout=120)
    adb(serial, "push", str(export_root / "tokenizer/packed/gemma4_bpe.gbt1"), f"{remote_dir}/tokenizer/gemma4_bpe.gbt1", timeout=300)
    adb(serial, "push", str(export_root / "bin/phase1_qa_stream"), f"{remote_dir}/phase1_qa_stream", timeout=120)
    adb(serial, "shell", "chmod", "755", f"{remote_dir}/phase1_qa_stream", timeout=30)
    table_sha = adb(serial, "shell", "sha256sum", f"{remote_dir}/tokenizer/gemma4_bpe.gbt1", timeout=120).stdout.split()[0]
    binary_sha = adb(serial, "shell", "sha256sum", f"{remote_dir}/phase1_qa_stream", timeout=120).stdout.split()[0]
    if table_sha != GBT1_SHA256:
        raise SystemExit(f"standalone staged GBT1 hash mismatch: {table_sha}")
    if binary_sha != "855c8392d627e1510a02b3bef43fe28dfc05c01837961d0451c27885d258a9fe":
        raise SystemExit(f"standalone binary hash mismatch: {binary_sha}")
    return batch_path


def device_output_material_hash(serial: str, remote_output_dir: str, expected_count: int) -> dict[str, Any]:
    command = f"cd {shell_quote(remote_output_dir)} && sha256sum out_*.pqa1"
    proc = adb(serial, "shell", command, timeout=300)
    hashes = []
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts:
            hashes.append(parts[0])
    material_hash = hashlib.sha256("".join(sorted(hashes)).encode("utf-8")).hexdigest()
    return {
        "output_count": len(hashes),
        "expected_output_count": expected_count,
        "material_hash_hex": material_hash,
        "output_sha256s": hashes,
    }


def standalone_benchmark(
    *,
    serial: str,
    export_root: Path,
    trial_key: str,
    trial_dir: Path,
    expected: dict[str, Any],
    report_dir: Path,
    timeout_sec: int,
) -> dict[str, Any]:
    stamp = utc_stamp()
    remote_dir = f"/data/local/tmp/polymath_phase1_exact_{stamp}_{trial_dir.name}"
    local_work_dir = Path("/tmp") / f"polymath_phase1_exact_standalone_{stamp}_{trial_dir.name}"
    local_work_dir.mkdir(parents=True, exist_ok=True)
    batch_path = stage_standalone_trial(serial, export_root, trial_dir, local_work_dir, remote_dir)
    cmd = (
        f"cd {shell_quote(remote_dir)} && ./phase1_qa_stream "
        f"--batch-list {shell_quote(batch_path)} "
        f"--tokenizer-dir {shell_quote(remote_dir + '/tokenizer')} "
        f"--vocab-sha256 {shell_quote(VOCAB_SHA256)} "
        f"--merges-sha256 {shell_quote(MERGES_SHA256)} "
        f"--table-format packed-mmap "
        f"--tokenizer-table {shell_quote(remote_dir + '/tokenizer/gemma4_bpe.gbt1')} "
        f"--bpe-algorithm heap "
        f"--batch-workers 8 "
        f"--batch-metrics {shell_quote(remote_dir + '/outputs/batch_metrics.json')}"
    )
    start = time.perf_counter()
    proc = adb(serial, "shell", cmd, timeout=timeout_sec, check=False)
    host_wall_sec = time.perf_counter() - start
    material = device_output_material_hash(serial, f"{remote_dir}/outputs", int(expected["job_count"])) if proc.returncode == 0 else {"material_hash_hex": None, "output_count": 0}
    batch_metrics_text = adb(serial, "shell", "cat", f"{remote_dir}/outputs/batch_metrics.json", timeout=60, check=False).stdout
    batch_metrics = json.loads(batch_metrics_text) if batch_metrics_text.strip().startswith("{") else {}
    native_elapsed_sec = float(batch_metrics.get("elapsed_ns", 0)) / 1_000_000_000.0 if batch_metrics else None
    exact_material_pass = material.get("material_hash_hex") == expected["material_hash_hex"]
    baseline = TERMUX_BASELINES[trial_key]
    host_token_rate = float(expected["token_ids"]) / host_wall_sec if host_wall_sec > 0 and exact_material_pass else None
    native_token_rate = float(expected["token_ids"]) / native_elapsed_sec if native_elapsed_sec and exact_material_pass else None
    summary = {
        "schema_version": "phase1_exact_closure_standalone_benchmark_summary_v1",
        "status": "probe" if proc.returncode == 0 else "fail",
        "trial_key": trial_key,
        "trial": trial_dir.name,
        "expected": {key: value for key, value in expected.items() if key != "output_sha256s"},
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
        "host_wall_sec": host_wall_sec,
        "native_batch_elapsed_sec": native_elapsed_sec,
        "host_token_ids_per_sec": host_token_rate,
        "native_batch_token_ids_per_sec": native_token_rate,
        "host_records_per_sec": float(expected["records"]) / host_wall_sec if host_wall_sec > 0 and exact_material_pass else None,
        "native_batch_records_per_sec": float(expected["records"]) / native_elapsed_sec if native_elapsed_sec and exact_material_pass else None,
        "host_input_decimal_mb_per_sec": (float(expected["input_bytes"]) / 1_000_000.0) / host_wall_sec if host_wall_sec > 0 and exact_material_pass else None,
        "native_batch_input_decimal_mb_per_sec": (float(expected["input_bytes"]) / 1_000_000.0) / native_elapsed_sec if native_elapsed_sec and exact_material_pass else None,
        "device_output_material": {key: value for key, value in material.items() if key != "output_sha256s"},
        "exact_material_parity": "pass" if exact_material_pass else "fail",
        "termux_baseline": baseline,
        "ratio_vs_termux_token_ids_per_sec_host_wall": (host_token_rate / float(baseline["token_ids_per_sec"])) if host_token_rate else None,
        "ratio_vs_termux_token_ids_per_sec_native_batch": (native_token_rate / float(baseline["token_ids_per_sec"])) if native_token_rate else None,
        "batch_metrics": batch_metrics,
        "raw_payload_policy": "raw standalone outputs stayed on device; only hashes/metrics are in repository reports",
        "nonclaims": [
            "no_apk_package_identity_claim",
            "no_game_mode_claim",
            "no_public_corpus_claim",
        ],
    }
    write_json(report_dir / "phase1_exact_closure_standalone_benchmark_summary.json", summary)
    adb(serial, "pull", f"{remote_dir}/outputs/batch_metrics.json", str(report_dir / "standalone_batch_metrics.json"), timeout=120, check=False)
    findings = scan_forbidden(report_dir)
    write_json(report_dir / "phase1_exact_closure_standalone_forbidden_payload_scan.json", {"status": "pass" if not findings else "fail", "findings": findings})
    if findings:
        raise SystemExit("Forbidden payloads were pulled into the report tree; refusing to continue.")
    return summary


def validate_export(export_root: Path) -> dict[str, Any]:
    if not export_root.is_dir():
        raise SystemExit(f"exact closure export root not found: {export_root}")
    manifest = export_root / "EXPORT_MANIFEST.json"
    sha_file = export_root / "SHA256SUMS.txt"
    if not manifest.is_file() or not sha_file.is_file():
        raise SystemExit(f"missing manifest or SHA256SUMS in {export_root}")
    manifest_sha = sha256_file(manifest)
    if manifest_sha != "4f1720f804b28c56493769ffcfe80ad824c18c5fc95a7fd143d9d7165a19ae71":
        raise SystemExit(f"unexpected exact export manifest hash: {manifest_sha}")
    return {
        "manifest_sha256": manifest_sha,
        "sha256sums_sha256": sha256_file(sha_file),
        "manifest": json.loads(manifest.read_text(encoding="utf-8")),
    }


def run_trial(args: argparse.Namespace, serial: str, export_root: Path, trial_key: str) -> dict[str, Any]:
    trial_dir = export_root / "benchmarks" / PROMOTED_TRIALS[trial_key]
    if not trial_dir.is_dir():
        raise SystemExit(f"missing promoted trial dir: {trial_dir}")
    expected = summarize_trial_material(trial_dir)
    expected_hash = EXPECTED_MATERIAL_HASHES[trial_key]
    if expected["material_hash_hex"] != expected_hash:
        raise SystemExit(f"{trial_dir.name} material hash mismatch: {expected['material_hash_hex']} != {expected_hash}")
    report_dir = args.out_dir / f"{utc_stamp()}_exact_{trial_dir.name}_{args.mode}_{args.game_mode}"
    report_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        report_dir / "phase1_exact_closure_input_manifest.json",
        {
            "schema_version": "phase1_exact_closure_input_manifest_v1",
            "trial_key": trial_key,
            "trial": trial_dir.name,
            "expected": {key: value for key, value in expected.items() if key != "output_sha256s"},
            "export_manifest_sha256": sha256_file(export_root / "EXPORT_MANIFEST.json"),
            "raw_payload_policy": "raw exact closure files are read from /tmp export and must not be committed",
        },
    )
    standalone = None
    apk = None
    if args.mode in {"standalone", "both"}:
        standalone = standalone_benchmark(
            serial=serial,
            export_root=export_root,
            trial_key=trial_key,
            trial_dir=trial_dir,
            expected=expected,
            report_dir=report_dir,
            timeout_sec=args.timeout_sec,
        )
    if args.mode in {"apk", "both"}:
        apk = app_benchmark(
            serial=serial,
            export_root=export_root,
            trial_key=trial_key,
            trial_dir=trial_dir,
            expected=expected,
            report_dir=report_dir,
            game_mode=args.game_mode,
            staging=args.staging,
            timeout_sec=args.timeout_sec,
            run_flags=1 if args.runtime_sampler else 0,
        )
    combined = {
        "schema_version": "phase1_exact_closure_combined_benchmark_summary_v1",
        "trial_key": trial_key,
        "trial": trial_dir.name,
        "report_dir": str(report_dir),
        "standalone": standalone,
        "apk": apk,
        "status": "probe",
        "promotion_gate": "pass" if apk and apk.get("exact_material_parity") == "pass" and apk.get("ratio_vs_termux_token_ids_per_sec", 0) >= args.min_ratio else "fail",
        "min_ratio": args.min_ratio,
        "nonclaims": [
            "no_public_corpus_claim",
            "no_game_mode_benefit_claim_without_matched_arms",
            "no_comet_upload",
        ],
    }
    write_json(report_dir / "phase1_exact_closure_combined_benchmark_summary.json", combined)
    print(
        json.dumps(
            {
                "trial": trial_dir.name,
                "report_dir": str(report_dir),
                "standalone_token_ids_per_sec": standalone.get("native_batch_token_ids_per_sec") if standalone else None,
                "apk_token_ids_per_sec": apk.get("app_result", {}).get("token_ids_per_sec") if apk else None,
                "apk_ratio_vs_termux": apk.get("ratio_vs_termux_token_ids_per_sec") if apk else None,
                "promotion_gate": combined["promotion_gate"],
            },
            sort_keys=True,
        )
    )
    return combined


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--trial", choices=["10k", "100k", "1m", "all"], default="10k")
    parser.add_argument("--mode", choices=["standalone", "apk", "both"], default="apk")
    parser.add_argument("--game-mode", choices=["standard", "custom", "performance", "leave"], default="standard")
    parser.add_argument("--staging", choices=["internal", "external"], default="internal")
    parser.add_argument("--timeout-sec", type=int, default=1800)
    parser.add_argument("--min-ratio", type=float, default=0.85)
    parser.add_argument("--out-dir", type=Path, default=Path("runtime/reports/polar_phase1_android_game_authority"))
    parser.add_argument("--runtime-sampler", action="store_true", help="Enable native CPU-frequency sampler diagnostics during the APK Phase 1 call.")
    args = parser.parse_args()

    export_root = args.export_root.resolve()
    export_identity = validate_export(export_root)
    serial = select_serial()
    trials = ["10k", "100k", "1m"] if args.trial == "all" else [args.trial]
    results = []
    for trial_key in trials:
        results.append(run_trial(args, serial, export_root, trial_key))
    aggregate_dir = args.out_dir / f"{utc_stamp()}_exact_closure_aggregate_{args.mode}_{args.trial}"
    write_json(
        aggregate_dir / "phase1_exact_closure_aggregate_summary.json",
        {
            "schema_version": "phase1_exact_closure_aggregate_summary_v1",
            "export_identity": {
                "manifest_sha256": export_identity["manifest_sha256"],
                "sha256sums_sha256": export_identity["sha256sums_sha256"],
                "sha256sums_status": export_identity["manifest"].get("sha256sums_status"),
                "file_count": export_identity["manifest"].get("file_count"),
                "total_bytes": export_identity["manifest"].get("total_bytes"),
            },
            "results": [{"trial": result["trial"], "report_dir": result["report_dir"], "promotion_gate": result["promotion_gate"]} for result in results],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

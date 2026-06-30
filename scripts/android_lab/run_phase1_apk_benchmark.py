#!/usr/bin/env python3
"""Run canonical Phase 1 APK benchmarks on a connected REDMAGIC.

Raw QAI1/PQA1 payloads are generated under /tmp and staged only on-device.
Only safe JSON/Markdown report artifacts are pulled into the repository.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


PACKAGE_NAME = "ai.zer0pa.polymath.lab"
ADB_REPORT_ROOT = f"/sdcard/Android/data/{PACKAGE_NAME}/files/reports/phase1"
STAGED_ROOT = f"/sdcard/Android/data/{PACKAGE_NAME}/files/staged/phase1"
INTERNAL_FILES_ROOT = f"/data/user/0/{PACKAGE_NAME}/files"
GBT1_SOURCE = Path("/tmp/polymath_android_lab_phase1_artifact_export/android_lab_phase1_artifact_export/tokenizer/packed/gemma4_bpe.gbt1")
GBT1_SHA256 = "5887e29db2618b21fd9db1358c7f6db5bb7efffab54c16ba0643b46d7f3714ae"
TERMUX_BASELINES = {
    "10k": {
        "records": 10_000,
        "token_ids": 242_340,
        "token_ids_per_sec": 16_402_897.617679182,
        "records_per_sec": 676_854.7337492441,
        "memory_pss_kb": 29_236,
    },
    "100k": {
        "records": 100_000,
        "token_ids": 2_616_577,
        "token_ids_per_sec": 49_068_772.590122126,
        "records_per_sec": 1_875_303.97882891,
        "memory_pss_kb": 44_257,
    },
    "1m": {
        "records": 1_000_000,
        "token_ids": 28_161_180,
        "token_ids_per_sec": 62_634_625.42881929,
        "records_per_sec": 2_224_147.7604567455,
        "memory_pss_kb": 244_233,
    },
}
FORBIDDEN_SUFFIXES = (".qai1", ".pqa1", ".jsonl", ".safetensors", ".bin", ".pt", ".pth", ".onnx", ".tflite", ".apk", ".aab")


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(argv: list[str], *, timeout: int = 60, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed {proc.returncode}: {' '.join(argv)}\n{proc.stdout[-2000:]}\n{proc.stderr[-4000:]}")
    return proc


def adb(serial: str, *args: str, timeout: int = 60, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["adb", "-s", serial, *args], timeout=timeout, check=check)


def select_serial() -> str:
    serial = os.environ.get("SERIAL")
    if serial:
        state = run(["adb", "-s", serial, "get-state"], timeout=10)
        if state.stdout.strip() != "device":
            raise SystemExit(f"SERIAL={serial} is not an attached adb device.")
        return serial
    devices = run(["adb", "devices"], timeout=10).stdout.splitlines()
    attached = [line.split()[0] for line in devices if len(line.split()) >= 2 and line.split()[1] == "device"]
    if len(attached) != 1:
        raise SystemExit(f"Expected one attached adb device or SERIAL=<serial>; found {len(attached)}.")
    return attached[0]


def run_as(serial: str, command: str, *, timeout: int = 60, check: bool = True) -> subprocess.CompletedProcess[str]:
    return adb(serial, "shell", f"run-as {PACKAGE_NAME} sh -c {shell_quote(command)}", timeout=timeout, check=check)


def keep_device_awake_for_phase1(serial: str, *, persistent: bool = False) -> None:
    """Keep long APK Phase 1 runs from being starved behind keyguard/sleep."""

    adb(serial, "shell", "input", "keyevent", "KEYCODE_WAKEUP", timeout=10, check=False)
    if persistent:
        adb(serial, "shell", "svc", "power", "stayon", "true", timeout=10, check=False)
        adb(serial, "shell", "settings", "put", "global", "stay_on_while_plugged_in", "3", timeout=10, check=False)
    adb(serial, "shell", "wm", "dismiss-keyguard", timeout=10, check=False)
    adb(serial, "shell", "input", "keyevent", "KEYCODE_MENU", timeout=10, check=False)


def window_state_excerpt(serial: str) -> str:
    proc = adb(
        serial,
        "shell",
        "dumpsys window | grep -E 'mDreamingLockscreen|mCurrentFocus|mFocusedApp|mScreenOn|mAwake' | head -40",
        timeout=10,
        check=False,
    )
    return (proc.stdout or proc.stderr).strip()


def compact_text(text: str, *, max_lines: int = 40, max_chars: int = 4000) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    compact = "\n".join(lines[:max_lines])
    if len(compact) > max_chars:
        compact = compact[:max_chars] + "...<truncated>"
    if len(lines) > max_lines:
        compact += "\n...<truncated>"
    return compact


def safe_adb_evidence(serial: str, *args: str, timeout: int = 10) -> dict[str, Any]:
    try:
        proc = adb(serial, *args, timeout=timeout, check=False)
    except Exception as exc:  # pragma: no cover - defensive timeout evidence path.
        return {"error": f"{type(exc).__name__}: {exc}"}
    return {
        "returncode": proc.returncode,
        "stdout": compact_text(proc.stdout),
        "stderr": compact_text(proc.stderr),
    }


def phase1_marker_timeout_evidence(serial: str, before_report_ids: set[str]) -> dict[str, Any]:
    current_report_ids = set(report_run_ids(serial))
    new_report_ids = sorted(current_report_ids - before_report_ids)
    report_file_listing: dict[str, dict[str, Any]] = {}
    for run_id in new_report_ids[:5]:
        report_file_listing[run_id] = safe_adb_evidence(
            serial,
            "shell",
            f"find {shell_quote(f'{ADB_REPORT_ROOT}/{run_id}')} -maxdepth 1 -type f | sort | head -80",
        )
    return {
        "schema_version": "phase1_marker_timeout_evidence_v1",
        "status": "timeout",
        "package": PACKAGE_NAME,
        "drift_deleted_by_patch": "device_sleep_keyguard_report_marker_starvation_during_long_phase1_waits",
        "raw_payload_policy": "metadata_only_no_qai1_pqa1_pjp1_bin_payloads",
        "wake_guard_policy": "KEYCODE_WAKEUP_and_keyguard_dismiss_before_launch_and_during_wait",
        "window_state": safe_adb_evidence(
            serial,
            "shell",
            "dumpsys window | grep -E 'mDreamingLockscreen|mCurrentFocus|mFocusedApp|mScreenOn|mAwake' | head -40",
        ),
        "app_process": {
            "pidof": safe_adb_evidence(serial, "shell", f"pidof {PACKAGE_NAME}"),
            "ps": safe_adb_evidence(serial, "shell", f"ps -A | grep {shell_quote(PACKAGE_NAME)} | head -20"),
        },
        "report_root": ADB_REPORT_ROOT,
        "before_report_ids_tail": sorted(before_report_ids)[-20:],
        "current_report_ids_tail": sorted(current_report_ids)[-20:],
        "new_report_ids": new_report_ids,
        "new_report_file_listing": report_file_listing,
    }


def ensure_gbt1(serial: str, remote_dir: str, staging: str) -> str:
    if not GBT1_SOURCE.is_file():
        raise SystemExit(f"GBT1 source missing: {GBT1_SOURCE}")
    observed = sha256_file(GBT1_SOURCE)
    if observed != GBT1_SHA256:
        raise SystemExit(f"GBT1 source hash mismatch: {observed}")
    if staging == "internal":
        tmp_dir = f"/data/local/tmp/polymath_phase1_gbt1_{utc_stamp()}"
        tmp_path = f"{tmp_dir}/gemma4_bpe.gbt1"
        remote_path = f"{remote_dir}/tokenizer/gemma4_bpe.gbt1"
        adb(serial, "shell", "rm", "-rf", tmp_dir, timeout=30, check=False)
        adb(serial, "shell", "mkdir", "-p", tmp_dir, timeout=20)
        adb(serial, "push", str(GBT1_SOURCE), tmp_path, timeout=300)
        run_as(serial, f"mkdir -p {shell_quote(internal_relative(remote_path).rsplit('/', 1)[0])}", timeout=30)
        run_as(serial, f"cp {shell_quote(tmp_path)} {shell_quote(internal_relative(remote_path))}", timeout=300)
        device_sha = run_as(serial, f"sha256sum {shell_quote(internal_relative(remote_path))}", timeout=120).stdout.split()[0]
        adb(serial, "shell", "rm", "-rf", tmp_dir, timeout=30, check=False)
    else:
        remote_path = f"{remote_dir}/tokenizer/gemma4_bpe.gbt1"
        adb(serial, "shell", "mkdir", "-p", f"{remote_dir}/tokenizer", timeout=20)
        adb(serial, "push", str(GBT1_SOURCE), remote_path, timeout=300)
        device_sha = adb(serial, "shell", "sha256sum", remote_path, timeout=120).stdout.split()[0]
    if device_sha != GBT1_SHA256:
        raise SystemExit(f"Device GBT1 hash mismatch: {device_sha}")
    return remote_path


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def internal_relative(path: str) -> str:
    prefix = INTERNAL_FILES_ROOT + "/"
    if not path.startswith(prefix):
        raise ValueError(f"path is not under internal files root: {path}")
    return "files/" + path[len(prefix) :]


def stress_records(count: int) -> list[dict[str, str]]:
    terms = ["entropy", "vector", "gradient", "kernel", "phonon", "orbit", "tensor", "charge", "mass", "phase"]
    concepts = ["symmetry", "curvature", "basis", "energy", "signal", "loss", "rank", "span", "field", "update"]
    adjectives = ["reversible", "sparse", "bounded", "noisy", "binary", "polar", "stable", "local"]
    records = []
    for index in range(count):
        term = terms[index % len(terms)]
        concept = concepts[(index * 7) % len(concepts)]
        adjective = adjectives[(index * 13) % len(adjectives)]
        records.append(
            {
                "record_id": f"stress:{index:08d}",
                "source_kind": "synthetic_stress",
                "question": f"What links {term} case {index % 997} to {concept}?",
                "answer": f"{term} maps to {concept} through {adjective} polar steps with checksum {index % 10007}.",
            }
        )
    return records


def download_wikitext_parquet(cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / "wikitext-103-raw-v1-train-00000-of-00002.parquet"
    if target.is_file():
        return target
    url = "https://huggingface.co/datasets/Salesforce/wikitext/resolve/refs%2Fconvert%2Fparquet/wikitext-103-raw-v1/train/0000.parquet"
    token = os.environ.get("HF_TOKEN")
    request = urllib.request.Request(url)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    return target


def wikitext_records(cache_dir: Path, target_bytes: int) -> list[dict[str, str]]:
    import pyarrow.parquet as pq  # type: ignore

    parquet = download_wikitext_parquet(cache_dir)
    table = pq.read_table(parquet, columns=["text"])
    records: list[dict[str, str]] = []
    total = 0
    for value in table.column("text").to_pylist():
        text = str(value).strip()
        if len(text) < 64 or text.startswith("="):
            continue
        answer = text[:60_000]
        total += len(answer.encode("utf-8"))
        records.append(
            {
                "record_id": f"wikitext103:{len(records):08d}",
                "source_kind": "megascience",
                "question": "Continue the verified Wikipedia article text.",
                "answer": answer,
            }
        )
        if total >= target_bytes:
            break
    if not records:
        raise SystemExit("No WikiText records were produced.")
    return records


def record_weight(record: dict[str, str]) -> int:
    return sum(len(record[key].encode("utf-8")) for key in ["record_id", "question", "answer"])


def shard_records(records: list[dict[str, str]], scheduler: str, workers: int, chunk_size: int) -> list[list[dict[str, str]]]:
    if scheduler == "dynamic":
        return [records[index : index + chunk_size] for index in range(0, len(records), chunk_size)]
    shards: list[list[dict[str, str]]] = [[] for _ in range(workers)]
    loads = [0 for _ in range(workers)]
    order = {id(record): index for index, record in enumerate(records)}
    for record in sorted(records, key=record_weight, reverse=True):
        target = min(range(workers), key=lambda worker: loads[worker])
        shards[target].append(record)
        loads[target] += record_weight(record)
    for shard in shards:
        shard.sort(key=lambda record: order[id(record)])
    return shards


def write_qai1(path: Path, records: list[dict[str, str]]) -> None:
    kinds = {"dictionary": 1, "megascience": 2, "synthetic_stress": 3, "user_supplied": 4}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(b"QAI1")
        handle.write(struct.pack("<Q", len(records)))
        for record in records:
            rid = record["record_id"].encode("utf-8")
            question = record["question"].encode("utf-8")
            answer = record["answer"].encode("utf-8")
            if len(question) > 65_536 or len(answer) > 65_536:
                raise ValueError(f"record too large: {record['record_id']}")
            handle.write(struct.pack("<B H I I", kinds[record["source_kind"]], len(rid), len(question), len(answer)))
            handle.write(rid)
            handle.write(question)
            handle.write(answer)


def stage_batch(local_dir: Path, remote_dir: str, serial: str, records: list[dict[str, str]], scheduler: str, workers: int, chunk_size: int, staging: str) -> str:
    local_inputs = local_dir / "inputs"
    local_outputs = local_dir / "outputs"
    local_outputs.mkdir(parents=True, exist_ok=True)
    shards = shard_records(records, scheduler=scheduler, workers=workers, chunk_size=chunk_size)
    batch_lines = []
    for index, shard in enumerate(shards):
        input_path = local_inputs / f"in_{index:04d}.qai1"
        write_qai1(input_path, shard)
        remote_input = f"{remote_dir}/inputs/in_{index:04d}.qai1"
        remote_output = f"{remote_dir}/outputs/out_{index:04d}.pqa1"
        remote_writer = f"{remote_dir}/outputs/writer_{index:04d}.json"
        remote_bpe = f"{remote_dir}/outputs/bpe_{index:04d}.json"
        batch_lines.append(f"{remote_input}\t{remote_output}\t{remote_writer}\t{remote_bpe}\n")
    local_batch = local_dir / "batch.tsv"
    local_batch.write_text("".join(batch_lines), encoding="utf-8")
    if staging == "internal":
        tmp_dir = f"/data/local/tmp/polymath_phase1_bench_{utc_stamp()}"
        adb(serial, "shell", "rm", "-rf", tmp_dir, timeout=30, check=False)
        adb(serial, "shell", "mkdir", "-p", tmp_dir, timeout=20)
        adb(serial, "push", str(local_inputs), f"{tmp_dir}/", timeout=900)
        adb(serial, "push", str(local_batch), f"{tmp_dir}/batch.tsv", timeout=120)
        rel_dir = internal_relative(remote_dir)
        run_as(serial, f"rm -rf {shell_quote(rel_dir)} && mkdir -p {shell_quote(rel_dir)}", timeout=120)
        run_as(serial, f"cp -R {shell_quote(tmp_dir + '/inputs')} {shell_quote(rel_dir + '/inputs')}", timeout=900)
        run_as(serial, f"mkdir -p {shell_quote(rel_dir + '/outputs')} && cp {shell_quote(tmp_dir + '/batch.tsv')} {shell_quote(rel_dir + '/batch.tsv')}", timeout=120)
        adb(serial, "shell", "rm", "-rf", tmp_dir, timeout=30, check=False)
    else:
        adb(serial, "shell", "rm", "-rf", remote_dir, timeout=120)
        adb(serial, "shell", "mkdir", "-p", f"{remote_dir}/inputs", f"{remote_dir}/outputs", timeout=30)
        adb(serial, "push", str(local_inputs), f"{remote_dir}/", timeout=900)
        adb(serial, "push", str(local_batch), f"{remote_dir}/batch.tsv", timeout=120)
    return f"{remote_dir}/batch.tsv"


def set_game_mode(serial: str, package: str, mode: str) -> dict[str, Any]:
    if mode == "leave":
        return {"requested_mode": mode, "set_command": None}
    before = adb(serial, "shell", "cmd", "game", "list-modes", package, timeout=20, check=False)
    set_result = adb(serial, "shell", "cmd", "game", "mode", mode, package, timeout=20, check=False)
    after = adb(serial, "shell", "cmd", "game", "list-modes", package, timeout=20, check=False)
    return {
        "requested_mode": mode,
        "before": before.stdout.strip(),
        "set_returncode": set_result.returncode,
        "set_stdout": set_result.stdout.strip(),
        "set_stderr": set_result.stderr.strip(),
        "after": after.stdout.strip(),
    }


def launch_and_wait(
    serial: str,
    tokenizer_dir: str,
    gbt1_path: str,
    batch_list_path: str,
    workers: int,
    bpe_algorithm: str,
    timeout_sec: int,
    run_flags: int = 0,
    phase1_exec_path: str | None = None,
    timeout_evidence_path: Path | None = None,
) -> str:
    adb(serial, "logcat", "-c", timeout=10, check=False)
    keep_device_awake_for_phase1(serial, persistent=True)
    adb(serial, "shell", "am", "force-stop", PACKAGE_NAME, timeout=20)
    before_dirs = set(report_run_ids(serial))
    start_args = [
        "shell",
        "am",
        "start",
        "-W",
        "-n",
        f"{PACKAGE_NAME}/.MainActivity",
        "-a",
        f"{PACKAGE_NAME}.WRITE_PROBE_REPORT",
        "--es",
        "tokenizer_dir",
        tokenizer_dir,
        "--es",
        "gbt1_path",
        gbt1_path,
        "--es",
        "batch_list_path",
        batch_list_path,
        "--es",
        "bpe_algorithm",
        bpe_algorithm,
        "--ei",
        "worker_count",
        str(workers),
        "--ei",
        "flags",
        str(run_flags),
    ]
    if phase1_exec_path:
        start_args.extend(["--es", "phase1_exec_path", phase1_exec_path])
    keep_device_awake_for_phase1(serial, persistent=True)
    adb(serial, *start_args, timeout=60)
    deadline = time.time() + timeout_sec
    next_wake = 0.0
    while time.time() < deadline:
        now = time.time()
        if now >= next_wake:
            keep_device_awake_for_phase1(serial)
            next_wake = now + 15.0
        logs = adb(serial, "logcat", "-d", "-s", "PolymathLabActivity", timeout=10, check=False).stdout
        for line in reversed(logs.splitlines()):
            marker = "adb_probe_report_written run_id="
            if marker in line:
                tail = line.split(marker, 1)[1]
                return tail.split()[0]
        new_reports = [run_id for run_id in report_run_ids(serial) if run_id not in before_dirs]
        for run_id in sorted(new_reports, reverse=True):
            probe = adb(serial, "shell", "test", "-f", f"{ADB_REPORT_ROOT}/{run_id}/gate_result.json", timeout=10, check=False)
            if probe.returncode == 0:
                return run_id
        time.sleep(2.0)
    evidence = phase1_marker_timeout_evidence(serial, before_dirs)
    if timeout_evidence_path:
        write_json(timeout_evidence_path, evidence)
    evidence_text = json.dumps(evidence, sort_keys=True)
    raise TimeoutError(f"Timed out waiting for app benchmark report marker. timeout_evidence={evidence_text}")


def report_run_ids(serial: str) -> list[str]:
    listing = adb(serial, "shell", "find", ADB_REPORT_ROOT, "-maxdepth", "1", "-type", "d", timeout=20, check=False)
    run_ids = []
    for line in listing.stdout.splitlines():
        leaf = line.rstrip("/").split("/")[-1]
        if leaf and leaf != "phase1":
            run_ids.append(leaf)
    return run_ids


def pull_run_report(serial: str, run_id: str, out_dir: Path) -> Path:
    remote = f"{ADB_REPORT_ROOT}/{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    adb(serial, "pull", remote, str(out_dir), timeout=300)
    pulled = out_dir / run_id
    if not pulled.is_dir():
        raise RuntimeError(f"Pulled report directory not found: {pulled}")
    return pulled


def scan_forbidden(root: Path) -> list[str]:
    findings = []
    for path in root.rglob("*"):
        if path.is_file() and path.name.endswith(FORBIDDEN_SUFFIXES):
            findings.append(str(path))
    return findings


def summarize(
    *,
    pulled: Path,
    dataset_name: str,
    record_count: int,
    input_bytes: int,
    local_generation_sha: str,
    game_mode_evidence: dict[str, Any],
    out_dir: Path,
) -> dict[str, Any]:
    app_result = json.loads((pulled / "phase1_app_run_result.json").read_text(encoding="utf-8"))
    native_result = json.loads((pulled / "native_probe_result.json").read_text(encoding="utf-8"))
    baseline = TERMUX_BASELINES["100k"] if record_count <= 150_000 else TERMUX_BASELINES["1m"]
    wall_sec = float(app_result["wall_sec"])
    decimal_mb_per_sec = (float(input_bytes) / 1_000_000.0) / wall_sec if wall_sec > 0 else 0.0
    latency_ms_per_record = (wall_sec * 1000.0) / record_count if record_count else 0.0
    summary = {
        "schema_version": "phase1_apk_benchmark_summary_v1",
        "status": "probe",
        "dataset": dataset_name,
        "records": record_count,
        "input_bytes": input_bytes,
        "input_decimal_mb_per_sec": decimal_mb_per_sec,
        "input_mib_per_sec_from_app": app_result.get("input_mb_per_sec"),
        "token_ids": app_result.get("token_ids"),
        "token_ids_per_sec": app_result.get("token_ids_per_sec"),
        "records_per_sec": app_result.get("records_per_sec"),
        "latency_ms_per_record": latency_ms_per_record,
        "latency_ms_per_prompt": latency_ms_per_record,
        "pss_kb": app_result.get("pss_kb"),
        "rss_kb": app_result.get("rss_kb"),
        "peak_rss_kb": app_result.get("peak_rss_kb"),
        "thread_count": app_result.get("thread_count"),
        "job_count": app_result.get("job_count"),
        "parity_state": app_result.get("parity_state"),
        "material_hash_hex": app_result.get("material_hash_hex"),
        "local_generation_sha256": local_generation_sha,
        "gbt1_sha256": GBT1_SHA256,
        "game_mode_evidence": game_mode_evidence,
        "termux_baseline_used": baseline,
        "ratio_vs_termux_token_ids_per_sec": (float(app_result.get("token_ids_per_sec", 0.0)) / baseline["token_ids_per_sec"]) if baseline["token_ids_per_sec"] else None,
        "ratio_vs_termux_records_per_sec": (float(app_result.get("records_per_sec", 0.0)) / baseline["records_per_sec"]) if baseline["records_per_sec"] else None,
        "public_context": {
            "huggingface_tokenizers_server_claim_mb_per_sec_class": 50,
            "tiktoken_claim": "3-6x faster than a comparable open-source GPT-2 tokenizer benchmark",
            "fastokens_claim": "9.1x average speedup over Hugging Face, up to 40% faster TTFT in reported long-context workloads",
            "comparison_warning": "These are not equivalent model-family or pipeline benchmarks; use MB/s only as external context.",
        },
        "native_probe_result": native_result,
        "nonclaims": [
            "no_promoted_phase1_apk_pass",
            "no_public_tokenizer_equivalence_claim",
            "no_game_mode_benefit_claim",
            "no_redmagic_rise_or_diablo_claim",
        ],
    }
    write_json(out_dir / "phase1_apk_benchmark_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["stress", "wikitext"], default="stress")
    parser.add_argument("--records", type=int, default=100_000)
    parser.add_argument("--target-public-mb", type=float, default=100.0)
    parser.add_argument("--scheduler", choices=["byte_greedy", "dynamic"], default="byte_greedy")
    parser.add_argument("--chunk-size", type=int, default=8192)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--game-mode", choices=["standard", "custom", "performance", "leave"], default="standard")
    parser.add_argument("--staging", choices=["internal", "external"], default="internal")
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--timeout-sec", type=int, default=1800)
    parser.add_argument("--runtime-sampler", action="store_true", help="Enable native CPU-frequency sampler diagnostics during the Phase 1 call.")
    args = parser.parse_args()

    serial = select_serial()
    stamp = utc_stamp()
    local_dir = Path("/tmp") / f"polymath_phase1_apk_benchmark_{stamp}_{args.dataset}"
    local_dir.mkdir(parents=True, exist_ok=True)
    report_dir = args.out_dir or Path("runtime/reports/polar_phase1_android_game_authority") / f"{stamp}_apk_benchmark_{args.dataset}"
    remote_dir = (
        f"{INTERNAL_FILES_ROOT}/staged/phase1/benchmark_{stamp}_{args.dataset}"
        if args.staging == "internal"
        else f"{STAGED_ROOT}/benchmark_{stamp}_{args.dataset}"
    )

    if args.dataset == "stress":
        records = stress_records(args.records)
        dataset_name = f"synthetic_stress_{args.records}"
    else:
        records = wikitext_records(local_dir / "hf_cache", int(args.target_public_mb * 1_000_000))
        dataset_name = f"Salesforce_wikitext_103_raw_v1_train_{args.target_public_mb:g}MB"

    batch_path = stage_batch(local_dir, remote_dir, serial, records, args.scheduler, args.workers, args.chunk_size, args.staging)
    tokenizer_dir = f"{remote_dir}/tokenizer"
    gbt1_path = ensure_gbt1(serial, remote_dir, args.staging)
    generation_manifest = {
        "schema_version": "phase1_apk_benchmark_generation_v1",
        "dataset": dataset_name,
        "record_count": len(records),
        "local_dir": str(local_dir),
        "remote_dir": remote_dir,
        "staging": args.staging,
        "scheduler": args.scheduler,
        "workers": args.workers,
        "chunk_size": args.chunk_size,
        "qai1_files": sorted(str(path.name) for path in (local_dir / "inputs").glob("*.qai1")),
        "qai1_total_bytes": sum(path.stat().st_size for path in (local_dir / "inputs").glob("*.qai1")),
        "raw_payload_policy": "not_imported_to_git",
    }
    manifest_bytes = json.dumps(generation_manifest, sort_keys=True).encode("utf-8")
    generation_sha = hashlib.sha256(manifest_bytes).hexdigest()
    write_json(report_dir / "phase1_apk_benchmark_generation_manifest.json", {**generation_manifest, "generation_manifest_sha256": generation_sha})

    mode_evidence = set_game_mode(serial, PACKAGE_NAME, args.game_mode)
    run_id = launch_and_wait(
        serial,
        tokenizer_dir,
        gbt1_path,
        batch_path,
        args.workers,
        "heap",
        args.timeout_sec,
        run_flags=1 if args.runtime_sampler else 0,
        timeout_evidence_path=report_dir / "phase1_marker_timeout_evidence.json",
    )
    pulled = pull_run_report(serial, run_id, report_dir)
    findings = scan_forbidden(report_dir)
    write_json(
        report_dir / "phase1_apk_benchmark_forbidden_payload_scan.json",
        {"schema_version": "phase1_apk_benchmark_forbidden_payload_scan_v1", "status": "pass" if not findings else "fail", "findings": findings},
    )
    if findings:
        raise SystemExit("Forbidden payloads were pulled into the report tree; refusing to summarize.")
    summary = summarize(
        pulled=pulled,
        dataset_name=dataset_name,
        record_count=len(records),
        input_bytes=generation_manifest["qai1_total_bytes"],
        local_generation_sha=generation_sha,
        game_mode_evidence=mode_evidence,
        out_dir=report_dir,
    )
    print(json.dumps({"status": summary["status"], "report_dir": str(report_dir), "run_id": run_id, "dataset": dataset_name, "token_ids_per_sec": summary["token_ids_per_sec"], "input_decimal_mb_per_sec": summary["input_decimal_mb_per_sec"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

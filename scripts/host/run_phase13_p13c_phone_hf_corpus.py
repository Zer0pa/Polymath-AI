#!/usr/bin/env python3
"""Run Phase 13 P13-C phone-native HF corpus scale gate."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shlex
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE13_ROOT = REPO_ROOT / "runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous"
ACTIVE_RUN = PHASE13_ROOT / "active_phase13_run.json"

DEFAULT_SERIAL = "FY25013101C8"
DEFAULT_PHONE_ROOT = "/data/local/tmp/polymath_gemma4_gate"
DEFAULT_LAYER_RUNNER = Path("/tmp/gemma4_phase13_android/gemma4_layer_runner")
DEFAULT_RUNPOD_HOST = "38.80.152.147"
DEFAULT_RUNPOD_PORT = "31002"
DEFAULT_RUNPOD_KEY = "~/.ssh/id_ed25519"
DEFAULT_RUNPOD_PYTHON = "/workspace/Polymath-AI/.venv/bin/python"
DEFAULT_RUNPOD_MODEL = "/workspace/models/gemma4_e4b/snapshot"

MODEL_ID = "google/gemma-4-E4B"
MODEL_REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
TOKENIZER_REL = "tokenizer/gemma4_e4b_bpe_v1"
SEQ = 128
TRAIN_SEQUENCES = 8192
HELDOUT_SEQUENCES = 1024
SPOT_ROWS = 3
LINE_COMPACT_CHARS = 384

DATASET_ID = "databricks/databricks-dolly-15k"
DATASET_REVISION = "bdd27f4d94b9c1f951818a7da7fd7aeea5dbff1a"
DATASET_FILE = "databricks-dolly-15k.jsonl"
DATASET_URL = (
    "https://huggingface.co/datasets/databricks/databricks-dolly-15k/resolve/"
    f"{DATASET_REVISION}/{DATASET_FILE}"
)
DATASET_CARD_URL = "https://huggingface.co/datasets/databricks/databricks-dolly-15k"
DATASET_API_URL = "https://huggingface.co/api/datasets/databricks/databricks-dolly-15k"
DATASET_LICENSE = "cc-by-sa-3.0"
DATASET_ROWS = 15010
DATASET_LAST_MODIFIED = "2023-06-30T18:34:13.000Z"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def q(value: str) -> str:
    return shlex.quote(value)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_u32(values: list[int]) -> str:
    return sha256_bytes(struct.pack("<" + ("I" * len(values)), *values))


def sha256_u8(values: list[int]) -> str:
    return sha256_bytes(bytes(values))


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def phone_path(root: str, child: str) -> str:
    if child.startswith("/"):
        return child
    return root.rstrip("/") + "/" + child.lstrip("/")


def run_command(
    command: list[str],
    *,
    check: bool = False,
    text: bool = True,
    input_data: bytes | None = None,
) -> subprocess.CompletedProcess[Any]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=text,
        input=input_data,
        capture_output=True,
    )
    if check and completed.returncode != 0:
        joined = " ".join(q(part) for part in command)
        stdout = completed.stdout if isinstance(completed.stdout, str) else completed.stdout.decode("utf-8", "replace")
        stderr = completed.stderr if isinstance(completed.stderr, str) else completed.stderr.decode("utf-8", "replace")
        raise RuntimeError(
            f"command failed ({completed.returncode}): {joined}\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )
    return completed


def adb(serial: str, args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return run_command(["adb", "-s", serial, *args], check=check)


def adb_shell(serial: str, command: str, *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return adb(serial, ["shell", command], check=check)


def adb_pull(serial: str, remote: str, local: Path, *, check: bool = False) -> bool:
    local.parent.mkdir(parents=True, exist_ok=True)
    completed = adb(serial, ["pull", remote, str(local)], check=False)
    if check and completed.returncode != 0:
        raise RuntimeError(f"adb pull failed: {remote}\n{completed.stderr}")
    return completed.returncode == 0


def adb_push(serial: str, local: Path, remote: str) -> None:
    adb(serial, ["push", str(local), remote], check=True)


def adb_exec_out(serial: str, command: str, *, check: bool = True) -> bytes:
    completed = run_command(
        ["adb", "-s", serial, "exec-out", command],
        check=False,
        text=False,
    )
    if check and completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace")
        raise RuntimeError(f"adb exec-out failed ({completed.returncode}): {command}\n{stderr}")
    return completed.stdout


def active_run_root() -> Path:
    active = load_json(ACTIVE_RUN)
    return REPO_ROOT / active["run_root"]


def source_commit() -> str:
    return run_command(["git", "rev-parse", "HEAD"], check=True).stdout.strip()


def source_dirty() -> bool:
    return bool(run_command(["git", "status", "--porcelain=v1"], check=True).stdout.strip())


def command_log_entry(name: str, result: subprocess.CompletedProcess[Any]) -> dict[str, Any]:
    stdout = result.stdout if isinstance(result.stdout, str) else result.stdout.decode("utf-8", "replace")
    stderr = result.stderr if isinstance(result.stderr, str) else result.stderr.decode("utf-8", "replace")
    return {
        "name": name,
        "returncode": result.returncode,
        "stdout_first_4096": stdout[:4096],
        "stderr_first_4096": stderr[:4096],
    }


def deploy_layer_runner(serial: str, phone_gate_root: str, layer_runner: Path) -> dict[str, Any]:
    if not layer_runner.exists():
        raise FileNotFoundError(f"missing Android gemma4_layer_runner binary: {layer_runner}")
    remote_bin = f"{phone_gate_root}/bin"
    adb_shell(serial, f"rm -rf {q(remote_bin)} && mkdir -p {q(remote_bin)}", check=True)
    adb_push(serial, layer_runner, f"{remote_bin}/gemma4_layer_runner")
    adb_shell(serial, f"chmod 755 {q(remote_bin + '/gemma4_layer_runner')}", check=True)
    phone_sha = adb_shell(serial, f"sha256sum {q(remote_bin + '/gemma4_layer_runner')}", check=False)
    return {
        "phone_bin": remote_bin,
        "local_gemma4_layer_runner": str(layer_runner),
        "local_gemma4_layer_runner_sha256": sha256_file(layer_runner),
        "phone_sha256sum_stdout": phone_sha.stdout.strip(),
        "phone_sha256sum_returncode": phone_sha.returncode,
    }


def prepare_phone_corpus(
    *,
    serial: str,
    phone_gate_root: str,
    phone_root: str,
    layer_runner: str,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    raw_dir = f"{phone_gate_root}/raw"
    cache_dir = f"{phone_gate_root}/token_caches"
    full_raw = f"{raw_dir}/dolly_full.jsonl"
    train_raw_full = f"{raw_dir}/dolly_train_000001_008192.full.jsonl"
    heldout_raw_full = f"{raw_dir}/dolly_heldout_008193_009216.full.jsonl"
    train_raw = f"{raw_dir}/dolly_train_000001_008192.max{LINE_COMPACT_CHARS}.jsonl"
    heldout_raw = f"{raw_dir}/dolly_heldout_008193_009216.max{LINE_COMPACT_CHARS}.jsonl"
    train_cache = f"{cache_dir}/dolly_train_seq{TRAIN_SEQUENCES}_seq{SEQ}"
    heldout_cache = f"{cache_dir}/dolly_heldout_seq{HELDOUT_SEQUENCES}_seq{SEQ}"
    tokenizer = phone_path(phone_root, TOKENIZER_REL)

    fetch_script = (
        "set -eu\n"
        f"rm -rf {q(raw_dir)} {q(cache_dir)}\n"
        f"mkdir -p {q(raw_dir)} {q(cache_dir)}\n"
        f"curl -L --fail --silent --show-error --retry 3 --connect-timeout 30 --max-time 600 {q(DATASET_URL)} > {q(full_raw)}\n"
        f"full_lines=$(wc -l < {q(full_raw)} | tr -d ' ')\n"
        f"if [ \"$full_lines\" -lt {TRAIN_SEQUENCES + HELDOUT_SEQUENCES} ]; then echo \"too_few_lines=$full_lines\" >&2; exit 7; fi\n"
        f"sed -n '1,{TRAIN_SEQUENCES}p' {q(full_raw)} > {q(train_raw_full)}\n"
        f"sed -n '{TRAIN_SEQUENCES + 1},{TRAIN_SEQUENCES + HELDOUT_SEQUENCES}p' {q(full_raw)} > {q(heldout_raw_full)}\n"
        f"cut -c 1-{LINE_COMPACT_CHARS} {q(train_raw_full)} > {q(train_raw)}\n"
        f"cut -c 1-{LINE_COMPACT_CHARS} {q(heldout_raw_full)} > {q(heldout_raw)}\n"
        "echo \"full_lines=$full_lines\"\n"
        f"echo \"train_lines=$(wc -l < {q(train_raw)} | tr -d ' ')\"\n"
        f"echo \"heldout_lines=$(wc -l < {q(heldout_raw)} | tr -d ' ')\"\n"
        f"echo \"phone_line_compaction_chars={LINE_COMPACT_CHARS}\"\n"
        f"sha256sum {q(full_raw)} {q(train_raw_full)} {q(heldout_raw_full)} {q(train_raw)} {q(heldout_raw)}\n"
    )
    fetch = adb_shell(serial, fetch_script, check=False)

    commands = [command_log_entry("phone curl HF dataset and split train/heldout", fetch)]
    if fetch.returncode != 0:
        return {
            "raw_dir": raw_dir,
            "cache_dir": cache_dir,
            "full_raw": full_raw,
            "train_raw_full": train_raw_full,
            "heldout_raw_full": heldout_raw_full,
            "train_raw": train_raw,
            "heldout_raw": heldout_raw,
            "train_cache": train_cache,
            "heldout_cache": heldout_cache,
            "tokenizer": tokenizer,
        }, commands

    train = adb_shell(
        serial,
        (
            f"{q(layer_runner)} --tokenize-pack {q(tokenizer)} {q(train_raw)} "
            f"{q(train_cache)} {SEQ} {TRAIN_SEQUENCES} "
            f"{q(DATASET_URL + f'#split=train:1-8192;phone_cut_chars={LINE_COMPACT_CHARS}')}"
        ),
        check=False,
    )
    heldout = adb_shell(
        serial,
        (
            f"{q(layer_runner)} --tokenize-pack {q(tokenizer)} {q(heldout_raw)} "
            f"{q(heldout_cache)} {SEQ} {HELDOUT_SEQUENCES} "
            f"{q(DATASET_URL + f'#split=heldout:8193-9216;phone_cut_chars={LINE_COMPACT_CHARS}')}"
        ),
        check=False,
    )
    commands.append(command_log_entry("phone native C++ tokenizer train cache", train))
    commands.append(command_log_entry("phone native C++ tokenizer heldout cache", heldout))
    return {
        "raw_dir": raw_dir,
        "cache_dir": cache_dir,
        "full_raw": full_raw,
        "train_raw_full": train_raw_full,
        "heldout_raw_full": heldout_raw_full,
        "train_raw": train_raw,
        "heldout_raw": heldout_raw,
        "train_cache": train_cache,
        "heldout_cache": heldout_cache,
        "tokenizer": tokenizer,
    }, commands


def pull_cache_manifests(serial: str, paths: dict[str, str], report_dir: Path) -> dict[str, dict[str, Any]]:
    pulled: dict[str, dict[str, Any]] = {}
    manifest_targets = {
        "train": paths["train_cache"],
        "heldout": paths["heldout_cache"],
    }
    for split, remote_cache in manifest_targets.items():
        local = report_dir / "cache_manifests" / f"{split}_manifest.json"
        if adb_pull(serial, f"{remote_cache}/manifest.json", local, check=False):
            pulled[split] = load_json(local)
    return pulled


def audit_phone_cache_files(
    *,
    serial: str,
    paths: dict[str, str],
    report_dir: Path,
) -> dict[str, Any]:
    files = [
        "input_ids.u32.bin",
        "attention_mask.u8.bin",
        "labels.u32.bin",
        "loss_mask.u8.bin",
        "position_ids.u32.bin",
        "manifest.json",
        "selected_text.txt",
    ]
    audits: dict[str, Any] = {"schema_version": "phase13_p13c_cache_file_audit_v1", "splits": {}}
    for split, cache_key in (("train", "train_cache"), ("heldout", "heldout_cache")):
        cache = paths[cache_key]
        script = "set -eu\n" + "\n".join(
            f"wc -c {q(cache + '/' + name)}; sha256sum {q(cache + '/' + name)}" for name in files
        )
        completed = adb_shell(serial, script, check=False)
        records: list[dict[str, Any]] = []
        if completed.returncode == 0:
            lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
            for index in range(0, len(lines), 2):
                size_fields = lines[index].split()
                sha_fields = lines[index + 1].split()
                records.append(
                    {
                        "file": Path(size_fields[1]).name,
                        "phone_path": size_fields[1],
                        "bytes": int(size_fields[0]),
                        "sha256": sha_fields[0],
                    }
                )
        audits["splits"][split] = {
            "cache": cache,
            "returncode": completed.returncode,
            "stderr_first_2048": completed.stderr[:2048],
            "files": records,
        }
    write_json(report_dir / "cache_file_audit.json", audits)
    return audits


def read_phone_spot_rows(serial: str, cache: str, rows: int) -> dict[str, Any]:
    ids_count = rows * SEQ
    input_ids_bytes = adb_exec_out(
        serial,
        f"dd if={q(cache + '/input_ids.u32.bin')} bs=4 count={ids_count} 2>/dev/null",
    )
    mask_bytes = adb_exec_out(
        serial,
        f"dd if={q(cache + '/attention_mask.u8.bin')} bs=1 count={ids_count} 2>/dev/null",
    )
    text_bytes = adb_exec_out(serial, f"head -n {rows} {q(cache + '/selected_text.txt')}")
    if len(input_ids_bytes) != ids_count * 4:
        raise RuntimeError(f"short phone input_ids spot read: {len(input_ids_bytes)} bytes")
    if len(mask_bytes) != ids_count:
        raise RuntimeError(f"short phone attention_mask spot read: {len(mask_bytes)} bytes")
    values = list(struct.unpack("<" + ("I" * ids_count), input_ids_bytes))
    masks = list(mask_bytes)
    texts = text_bytes.decode("utf-8").splitlines()
    if len(texts) < rows:
        raise RuntimeError(f"short phone selected_text spot read: {len(texts)} rows")
    return {
        "texts": texts[:rows],
        "input_ids": [values[index * SEQ : (index + 1) * SEQ] for index in range(rows)],
        "attention_mask": [masks[index * SEQ : (index + 1) * SEQ] for index in range(rows)],
    }


def ssh_base(args: argparse.Namespace) -> list[str]:
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=20",
        "-o",
        "StrictHostKeyChecking=no",
        "-p",
        args.runpod_port,
        "-i",
        str(Path(args.runpod_key).expanduser()),
        f"root@{args.runpod_host}",
    ]


def scp_to(args: argparse.Namespace, local: Path, remote: str) -> None:
    run_command(
        [
            "scp",
            "-P",
            args.runpod_port,
            "-i",
            str(Path(args.runpod_key).expanduser()),
            str(local),
            f"root@{args.runpod_host}:{remote}",
        ],
        check=True,
    )


def scp_from(args: argparse.Namespace, remote: str, local: Path) -> None:
    local.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            "scp",
            "-P",
            args.runpod_port,
            "-i",
            str(Path(args.runpod_key).expanduser()),
            f"root@{args.runpod_host}:{remote}",
            str(local),
        ],
        check=True,
    )


def ssh_command(args: argparse.Namespace, command: str, *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return run_command([*ssh_base(args), command], check=check)


def write_runpod_parity_script(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import hashlib
import json
import struct
import sys

from transformers import AutoTokenizer
import transformers


def sha_u32(values):
    return hashlib.sha256(struct.pack("<" + ("I" * len(values)), *values)).hexdigest()


def sha_u8(values):
    return hashlib.sha256(bytes(values)).hexdigest()


def main():
    spot_path, out_path, model_path = sys.argv[1:4]
    with open(spot_path, "r", encoding="utf-8") as handle:
        spot = json.load(handle)
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    rows = []
    total_input_mismatches = 0
    total_mask_mismatches = 0
    seq = spot["sequence_length"]
    for index, text in enumerate(spot["texts"]):
        ids = tokenizer(text, add_special_tokens=True).input_ids[:seq]
        packed = [0] * (seq - len(ids)) + ids
        mask = [0] * (seq - len(ids)) + [1] * len(ids)
        phone_ids = spot["phone_input_ids"][index]
        phone_mask = spot["phone_attention_mask"][index]
        input_mismatches = [col for col, (left, right) in enumerate(zip(phone_ids, packed)) if left != right]
        mask_mismatches = [col for col, (left, right) in enumerate(zip(phone_mask, mask)) if left != right]
        total_input_mismatches += len(input_mismatches)
        total_mask_mismatches += len(mask_mismatches)
        rows.append({
            "row": index,
            "line_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "phone_input_ids_sha256": sha_u32(phone_ids),
            "runpod_transformers_input_ids_sha256": sha_u32(packed),
            "phone_attention_mask_sha256": sha_u8(phone_mask),
            "runpod_transformers_attention_mask_sha256": sha_u8(mask),
            "input_id_mismatch_count": len(input_mismatches),
            "attention_mask_mismatch_count": len(mask_mismatches),
            "first_input_id_mismatch_col": None if not input_mismatches else input_mismatches[0],
            "first_attention_mask_mismatch_col": None if not mask_mismatches else mask_mismatches[0],
        })
    payload = {
        "schema_version": "phase13_p13c_runpod_transformers_tokenizer_parity_v1",
        "status": "pass" if total_input_mismatches == 0 and total_mask_mismatches == 0 else "fail",
        "model_id": "google/gemma-4-E4B",
        "revision": "7aa32e6889efd6300124851b164f8b364314c3d8",
        "runpod_model_snapshot": model_path,
        "runpod_transformers_version": transformers.__version__,
        "sequence_length": seq,
        "spot_rows": len(rows),
        "total_input_id_mismatch_count": total_input_mismatches,
        "total_attention_mask_mismatch_count": total_mask_mismatches,
        "rows": rows,
        "raw_text_materialized_in_report": False,
        "full_token_payload_materialized_in_report": False,
    }
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\\n")


if __name__ == "__main__":
    main()
""",
        encoding="utf-8",
    )


def run_tokenizer_parity(
    *,
    args: argparse.Namespace,
    serial: str,
    paths: dict[str, str],
    report_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    commands: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="phase13_p13c_parity_") as tmp_name:
        tmp = Path(tmp_name)
        spot = read_phone_spot_rows(serial, paths["train_cache"], SPOT_ROWS)
        spot_payload = {
            "schema_version": "phase13_p13c_phone_spot_rows_for_runpod_oracle_v1",
            "model_id": MODEL_ID,
            "revision": MODEL_REVISION,
            "sequence_length": SEQ,
            "spot_rows": SPOT_ROWS,
            "texts": spot["texts"],
            "phone_input_ids": spot["input_ids"],
            "phone_attention_mask": spot["attention_mask"],
            "report_policy": "temporary_transfer_only_not_committed",
        }
        spot_path = tmp / "phone_spot_rows.json"
        script_path = tmp / "runpod_tokenizer_parity.py"
        write_json(spot_path, spot_payload)
        write_runpod_parity_script(script_path)

        remote_root = f"/tmp/polymath_phase13_p13c_{os.getpid()}"
        mkdir = ssh_command(args, f"rm -rf {q(remote_root)} && mkdir -p {q(remote_root)}", check=False)
        commands.append(command_log_entry("runpod create parity temp dir", mkdir))
        if mkdir.returncode != 0:
            raise RuntimeError("RunPod parity temp dir creation failed")
        scp_to(args, spot_path, f"{remote_root}/phone_spot_rows.json")
        scp_to(args, script_path, f"{remote_root}/runpod_tokenizer_parity.py")
        parity_cmd = (
            f"{q(args.runpod_python)} {q(remote_root + '/runpod_tokenizer_parity.py')} "
            f"{q(remote_root + '/phone_spot_rows.json')} {q(remote_root + '/parity.json')} "
            f"{q(args.runpod_model)}"
        )
        parity = ssh_command(args, parity_cmd, check=False)
        commands.append(command_log_entry("runpod Transformers tokenizer parity", parity))
        if parity.returncode != 0:
            raise RuntimeError(f"RunPod tokenizer parity failed: {parity.stderr}")
        local_parity = report_dir / "tokenizer_parity_spotcheck.json"
        scp_from(args, f"{remote_root}/parity.json", local_parity)
        cleanup = ssh_command(args, f"rm -rf {q(remote_root)}", check=False)
        commands.append(command_log_entry("runpod cleanup parity temp dir", cleanup))
    parity_payload = load_json(report_dir / "tokenizer_parity_spotcheck.json")
    return parity_payload, commands


def validate_gate(
    *,
    manifests: dict[str, dict[str, Any]],
    parity: dict[str, Any] | None,
    fetch_commands: list[dict[str, Any]],
    report_dir: Path,
) -> list[str]:
    blockers: list[str] = []
    if len(manifests) != 2:
        blockers.append("train and heldout cache manifests were not both pulled")
    expected = {
        "train": TRAIN_SEQUENCES,
        "heldout": HELDOUT_SEQUENCES,
    }
    for split, sequence_count in expected.items():
        manifest = manifests.get(split)
        if not manifest:
            continue
        checks = {
            "model_id": MODEL_ID,
            "revision": MODEL_REVISION,
            "tokenizer": "native_cpp_bpe_from_tokenizer_json_tables",
            "sequence_length": SEQ,
            "sequence_count": sequence_count,
        }
        for key, wanted in checks.items():
            if manifest.get(key) != wanted:
                blockers.append(f"{split} manifest {key} mismatch: {manifest.get(key)!r} != {wanted!r}")
        for key in (
            "raw_text_sha256",
            "vocab_sha256",
            "merges_sha256",
            "input_ids_sha256",
            "attention_mask_sha256",
            "labels_sha256",
            "loss_mask_sha256",
            "position_ids_sha256",
            "selected_text_sha256",
        ):
            if not manifest.get(key):
                blockers.append(f"{split} manifest missing {key}")
        if int(manifest.get("loss_tokens", 0) or 0) <= 0:
            blockers.append(f"{split} cache has no loss tokens")
    if parity is None:
        blockers.append("RunPod Transformers tokenizer parity artifact missing")
    elif parity.get("status") != "pass":
        blockers.append("RunPod Transformers tokenizer parity failed")
    for entry in fetch_commands:
        if entry["returncode"] != 0:
            blockers.append(f"command failed: {entry['name']} returncode={entry['returncode']}")
    forbidden_names = []
    for path in report_dir.rglob("*"):
        if path.is_file() and (
            path.suffix in {".bin", ".jsonl", ".txt"}
            or path.name in {"selected_text.txt", "input_ids.u32.bin", "labels.u32.bin"}
        ):
            if path.name not in {"blockers.md", "falsifier_report.md"}:
                forbidden_names.append(rel(path))
    if forbidden_names:
        blockers.append(f"raw/token payload files appeared in report dir: {forbidden_names}")
    return blockers


def write_artifact_manifest(report_dir: Path) -> None:
    entries: list[dict[str, Any]] = []
    for path in sorted(report_dir.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            entries.append({"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_json(
        report_dir / "artifact_manifest.json",
        {
            "schema_version": "phase13_p13c_artifact_manifest_v1",
            "created_at_utc": utc_now(),
            "artifacts": entries,
        },
    )


def update_phase13_status(run_root: Path, status: str, gate_result_path: Path) -> None:
    status_path = run_root / "phase13_gate_status.json"
    phase_status = load_json(status_path)
    phase_status["gate_status"]["P13-C"] = status
    phase_status["current_gate"] = "P13-D" if status == "pass" else "P13-C"
    phase_status["latest_gate_result"] = rel(gate_result_path)
    phase_status["updated_at_utc"] = utc_now()
    write_json(status_path, phase_status)

    active = load_json(ACTIVE_RUN)
    active["current_gate"] = phase_status["current_gate"]
    active["updated_at_utc"] = utc_now()
    write_json(ACTIVE_RUN, active)


def update_gpd_state(status: str, gate_result_path: Path, train_loss_tokens: int | None, heldout_loss_tokens: int | None) -> None:
    if status != "pass":
        return
    gate_rel = rel(gate_result_path)
    state_path = REPO_ROOT / ".gpd/state.json"
    state = load_json(state_path)
    desc = (
        f"P13-C scaled phone-native HF corpus gate passed at {gate_rel}. "
        f"The phone streamed {DATASET_ID} at revision {DATASET_REVISION}, split "
        f"{TRAIN_SEQUENCES} train / {HELDOUT_SEQUENCES} heldout seq{SEQ} rows, tokenized with "
        "native C++ Gemma BPE on-device, and RunPod Transformers parity passed for "
        f"{SPOT_ROWS} spot rows. Loss-token counts: train={train_loss_tokens}, heldout={heldout_loss_tokens}."
    )
    state["position"]["last_activity"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    state["position"]["last_activity_desc"] = desc
    state["position"]["last_activity_description"] = desc
    state["position"]["status"] = "Phase 13 execution in progress; P13-A through P13-C passed; next gate is P13-D expanded gradient parity"
    state["session"]["stopped_at"] = (
        "P13-C scaled phone-native HF corpus passed; continue with P13-D expanded gradient parity. "
        "Do not run P13-H until P13-D through P13-G also have exact pass/fail/fallback artifacts."
    )
    todos = [
        item for item in state.get("pending_todos", [])
        if "P13-C" not in item and "phone-native HF-streamed Gemma corpus cache" not in item
    ]
    next_todo = (
        "Execute P13-D next: run seeded expanded gradient parity over at least 64 adapter A/B coordinates "
        "and multiple iterations, or record an exact blocker."
    )
    if next_todo not in todos:
        todos.insert(0, next_todo)
    state["pending_todos"] = todos
    result = (
        f"P13-C scaled phone-native HF corpus passed: {gate_rel}. Phone-native curl fetched "
        f"{DATASET_ID}@{DATASET_REVISION}; phone C++ Gemma tokenizer built {TRAIN_SEQUENCES}/"
        f"{HELDOUT_SEQUENCES} seq{SEQ} train/heldout caches; RunPod Transformers parity passed on "
        f"{SPOT_ROWS} rows; host minibatch serving remained false."
    )
    if result not in state.setdefault("intermediate_results", []):
        state["intermediate_results"].append(result)
    state["_synced_at"] = utc_now()
    write_json(state_path, state)

    state_md = REPO_ROOT / ".gpd/STATE.md"
    text = state_md.read_text(encoding="utf-8")
    text = text.replace(
        "**Status:** Phase 13 execution in progress; P13-A and P13-B passed; next gate is P13-C scaled phone-native HF corpus cache",
        "**Status:** Phase 13 execution in progress; P13-A through P13-C passed; next gate is P13-D expanded gradient parity",
    )
    old_last = (
        "**Last Activity Description:** P13-B identity/kernel-lineage gate passed at "
        "`runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous/20260524T210920Z_phase13_gemma4_only_heterogeneous/P13-B-identity-kernel-lineage/gate_result.json`. "
        "The rebuilt phone runner emitted Gemma identity, hidden size 2560, source commit, runner binary SHA, and "
        "`residual_adapter_opencl_training` lineage telemetry, then rejected a deliberate Qwen hidden-size-1536 config before training."
    )
    new_last = f"**Last Activity Description:** {desc}"
    if old_last in text:
        text = text.replace(old_last, new_last)
    marker = "\n## Session Continuity\n"
    entry = (
        f"- P13-C scaled phone-native HF corpus passed: `{gate_rel}`. The phone streamed "
        f"`{DATASET_ID}` revision `{DATASET_REVISION}`, built `{TRAIN_SEQUENCES}` train / "
        f"`{HELDOUT_SEQUENCES}` heldout seq`{SEQ}` caches with native C++ Gemma BPE, and "
        f"RunPod Transformers parity passed on `{SPOT_ROWS}` rows. Host minibatch serving "
        "remained false.\n"
    )
    if entry not in text and marker in text:
        text = text.replace(marker, entry + marker)
    text = text.replace(
        "- Execute P13-C next: build or verify a minimum `8192/1024` train/heldout\n"
        "  seq128 phone-native HF-streamed Gemma corpus cache with parity/provenance.\n",
        "- Execute P13-D next: run seeded expanded gradient parity over at least `64`\n"
        "  adapter A/B coordinates and multiple iterations, or record an exact blocker.\n",
    )
    text = text.replace(
        "**Stopped at:** P13-B identity/kernel-lineage instrumentation passed; continue\n"
        "with P13-C scaled phone-native HF corpus. Do not run P13-H until P13-C through\n"
        "P13-G have exact pass/fail/fallback artifacts.",
        "**Stopped at:** P13-C scaled phone-native HF corpus passed; continue with P13-D\n"
        "expanded gradient parity. Do not run P13-H until P13-D through P13-G have exact\n"
        "pass/fail/fallback artifacts.",
    )
    state_md.write_text(text, encoding="utf-8")

    runlog = REPO_ROOT / ".gpd/runlog.jsonl"
    event = {
        "ts": utc_now(),
        "event": "phase13_p13c_phone_native_hf_corpus_passed",
        "project": "polymath-gemma4-snapdragon-megakernel",
        "status": "pass",
        "branch": "gemma4-megakernel-native-training",
        "evidence": gate_rel,
        "note": (
            f"P13-C built {TRAIN_SEQUENCES}/{HELDOUT_SEQUENCES} seq{SEQ} phone-native caches from "
            f"{DATASET_ID}@{DATASET_REVISION} using phone curl plus native C++ Gemma BPE; "
            f"RunPod Transformers parity passed on {SPOT_ROWS} rows; no host minibatch serving or raw token payload artifacts were promoted."
        ),
    }
    with runlog.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", default=DEFAULT_SERIAL)
    parser.add_argument("--phone-root", default=DEFAULT_PHONE_ROOT)
    parser.add_argument("--layer-runner", type=Path, default=DEFAULT_LAYER_RUNNER)
    parser.add_argument("--runpod-host", default=DEFAULT_RUNPOD_HOST)
    parser.add_argument("--runpod-port", default=DEFAULT_RUNPOD_PORT)
    parser.add_argument("--runpod-key", default=DEFAULT_RUNPOD_KEY)
    parser.add_argument("--runpod-python", default=DEFAULT_RUNPOD_PYTHON)
    parser.add_argument("--runpod-model", default=DEFAULT_RUNPOD_MODEL)
    args = parser.parse_args()

    run_root = active_run_root()
    run_id = load_json(ACTIVE_RUN)["run_id"]
    report_dir = run_root / "P13-C-phone-native-hf-corpus"
    report_dir.mkdir(parents=True, exist_ok=True)
    phone_gate_root = f"{args.phone_root}/phase13/{run_id}/p13c"

    commands: list[dict[str, Any]] = []
    blockers: list[str] = []
    paths: dict[str, str] = {}
    manifests: dict[str, dict[str, Any]] = {}
    parity: dict[str, Any] | None = None
    deploy: dict[str, Any] = {}
    cache_audit: dict[str, Any] = {}

    required_phone = [
        phone_path(args.phone_root, TOKENIZER_REL),
    ]
    for path in required_phone:
        if adb_shell(args.serial, f"test -e {q(path)}", check=False).returncode != 0:
            blockers.append(f"missing phone path: {path}")

    if not blockers:
        try:
            deploy = deploy_layer_runner(args.serial, phone_gate_root, args.layer_runner)
            write_json(report_dir / "binary_deploy_manifest.json", deploy)
            paths, corpus_commands = prepare_phone_corpus(
                serial=args.serial,
                phone_gate_root=phone_gate_root,
                phone_root=args.phone_root,
                layer_runner=f"{phone_gate_root}/bin/gemma4_layer_runner",
            )
            commands.extend(corpus_commands)
            manifests = pull_cache_manifests(args.serial, paths, report_dir)
            cache_audit = audit_phone_cache_files(serial=args.serial, paths=paths, report_dir=report_dir)
            parity, parity_commands = run_tokenizer_parity(
                args=args,
                serial=args.serial,
                paths=paths,
                report_dir=report_dir,
            )
            commands.extend(parity_commands)
        except Exception as error:  # noqa: BLE001
            blockers.append(str(error))

    source_provenance = {
        "schema_version": "phase13_p13c_source_provenance_v1",
        "dataset_id": DATASET_ID,
        "dataset_revision": DATASET_REVISION,
        "dataset_file": DATASET_FILE,
        "source_url": DATASET_URL,
        "dataset_card_url": DATASET_CARD_URL,
        "dataset_api_url": DATASET_API_URL,
        "declared_license": DATASET_LICENSE,
        "declared_rows": DATASET_ROWS,
        "last_modified_utc": DATASET_LAST_MODIFIED,
        "source_summary": "Databricks Dolly 15k instruction-following JSONL corpus on Hugging Face.",
        "license_note": "Hugging Face dataset card declares cc-by-sa-3.0 and permits academic/commercial use under CC BY-SA 3.0.",
        "phone_side_line_compaction": {
            "enabled": True,
            "max_chars_per_line": LINE_COMPACT_CHARS,
            "reason": "The C++ tokenizer truncates to seq128 after BPE, so phone-side cut removes text that cannot enter the cache while keeping streaming and tokenization on-device.",
        },
    }
    write_json(report_dir / "source_provenance.json", source_provenance)

    train_loss_tokens = None
    heldout_loss_tokens = None
    if manifests.get("train"):
        train_loss_tokens = int(manifests["train"].get("loss_tokens", 0) or 0)
    if manifests.get("heldout"):
        heldout_loss_tokens = int(manifests["heldout"].get("loss_tokens", 0) or 0)

    corpus_manifest = {
        "schema_version": "phase13_p13c_corpus_manifest_v1",
        "created_at_utc": utc_now(),
        "run_id": run_id,
        "phone_gate_root": phone_gate_root,
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "sequence_length": SEQ,
        "minimum_floor": {"train_sequences": TRAIN_SEQUENCES, "heldout_sequences": HELDOUT_SEQUENCES},
        "stretch_65536_train_status": "not_feasible_without_repetition_for_selected_15010_row_dataset",
        "phone_native_streaming": True,
        "phone_native_tokenization": True,
        "phone_side_line_compaction_chars": LINE_COMPACT_CHARS,
        "host_minibatch_serving": False,
        "runtime_boundary": "phone_curl_to_phone_raw_jsonl_then_phone_cpp_gemma_bpe_to_ufs_cache",
        "paths": paths,
        "source_provenance": source_provenance,
        "cache_manifests": manifests,
        "cache_file_audit": cache_audit,
        "tokenizer_parity_spotcheck": None if parity is None else rel(report_dir / "tokenizer_parity_spotcheck.json"),
        "raw_payload_policy": "raw text, selected text, and token payload binaries remain on phone or temporary parity transfer only",
        "source_commit": source_commit(),
        "source_tree_dirty": source_dirty(),
    }
    write_json(report_dir / "corpus_manifest.json", corpus_manifest)

    blockers.extend(
        validate_gate(
            manifests=manifests,
            parity=parity,
            fetch_commands=commands,
            report_dir=report_dir,
        )
    )

    status = "pass" if not blockers else "fail"
    gate = {
        "schema_version": "phase13_p13c_gate_result_v1",
        "gate": "P13-C-phone-native-hf-corpus-scale",
        "run_id": run_id,
        "status": status,
        "started_at_utc": utc_now(),
        "ended_at_utc": utc_now(),
        "blockers": blockers,
        "phone_gate_root": phone_gate_root,
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "dataset_id": DATASET_ID,
        "dataset_revision": DATASET_REVISION,
        "declared_license": DATASET_LICENSE,
        "train_sequence_count": manifests.get("train", {}).get("sequence_count"),
        "heldout_sequence_count": manifests.get("heldout", {}).get("sequence_count"),
        "train_loss_tokens": train_loss_tokens,
        "heldout_loss_tokens": heldout_loss_tokens,
        "tokenizer": manifests.get("train", {}).get("tokenizer"),
        "runpod_transformers_parity_status": None if parity is None else parity.get("status"),
        "phone_native_streaming": True,
        "phone_native_tokenization": True,
        "phone_side_line_compaction_chars": LINE_COMPACT_CHARS,
        "host_minibatch_serving": False,
        "raw_token_payloads_promoted": False,
        "promoted_claims": [
            f"Phone-native HF stream and Gemma tokenizer cache floor met at {TRAIN_SEQUENCES}/{HELDOUT_SEQUENCES} seq{SEQ}.",
            f"RunPod Transformers tokenizer parity passed for {SPOT_ROWS} train spot rows.",
        ]
        if status == "pass"
        else [],
        "nonclaims": [
            "P13-C does not claim learning improvement.",
            "P13-C does not claim 65536 train sequences; selected dataset has 15010 rows and repetition was rejected.",
            "P13-C does not claim full-line Dolly JSONL tokenization; phone-side line compaction was used before native tokenization.",
            "P13-C does not claim heterogeneous or HTP training.",
        ],
    }
    write_json(report_dir / "gate_result.json", gate)
    write_text(report_dir / "blockers.md", "- None.\n" if not blockers else "".join(f"- {item}\n" for item in blockers))
    write_text(
        report_dir / "falsifier_report.md",
        "# P13-C Falsifier Report\n\n"
        f"- Gate status: {status}.\n"
        f"- Minimum corpus floor: {'pass' if manifests.get('train', {}).get('sequence_count') == TRAIN_SEQUENCES and manifests.get('heldout', {}).get('sequence_count') == HELDOUT_SEQUENCES else 'fail'}.\n"
        f"- Phone-native tokenization: {'pass' if manifests.get('train', {}).get('tokenizer') == 'native_cpp_bpe_from_tokenizer_json_tables' else 'fail'}.\n"
        f"- RunPod Transformers tokenizer parity: {None if parity is None else parity.get('status')}.\n"
        "- Host minibatch serving: false; host pulled only manifests and compact parity hashes.\n"
        "- Raw token payload promotion: false; token binaries remain on phone or temporary parity transfer only.\n",
    )
    write_text(report_dir / "commands.log", "\n".join(json.dumps(item, sort_keys=True) for item in commands) + "\n")
    write_artifact_manifest(report_dir)
    update_phase13_status(run_root, status, report_dir / "gate_result.json")
    update_gpd_state(status, report_dir / "gate_result.json", train_loss_tokens, heldout_loss_tokens)

    print(json.dumps({"status": status, "gate_result": rel(report_dir / "gate_result.json")}, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Launch Phase 13 P13-H phone-local long run."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE13_ROOT = REPO_ROOT / "runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous"
ACTIVE_RUN = PHASE13_ROOT / "active_phase13_run.json"

DEFAULT_SERIAL = "FY25013101C8"
DEFAULT_PHONE_ROOT = "/data/local/tmp/polymath_gemma4_gate"
DEFAULT_PHASE11_RUNNER = Path("/tmp/gemma4_phase13_p13h_android/phase11_runner")
DEFAULT_LAYER_RUNNER = Path("/tmp/gemma4_phase13_p13h_android/gemma4_layer_runner")
DEFAULT_ASSET_DIR = "streamed_assets/g8_layer01_20260517T071405Z"
DEFAULT_LAYER0_PACK = "layer_pack/gemma4_e4b_layer0_seq128_v0"
DEFAULT_LAYER1_PACK = "layer_pack/gemma4_e4b_layer1_seq128_v0"
PHASE12_LR3E4_FINAL_CHECKPOINT = (
    "/data/local/tmp/polymath_gemma4_gate/phase12/runs/"
    "20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_train/"
    "Phase12-long-native-lr/iterations/iter_000023/checkpoint"
)

MODEL_ID = "google/gemma-4-E4B"
MODEL_REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
HIDDEN = 2560
SEQ = 128
SHARD_CASES = 8
TOP_K = 8
VOCAB_SIZE = 262144
TRAIN_ITERATIONS = 5000
LEARNING_RATE = 0.0003
ADAPTER_RANK = 16
GATE_DIR_NAME = "P13-H-overnight-phone-local-long-run"
OBJECTIVE_NAME = "label_contrastive_topk_kl_v1"
OBJECTIVE_CONTRACT = "p13c_label_onehot_topk_over_phone_native_corpus_labels_no_runtime_teacher_service"
TEACHER_PROVENANCE = "phone_native_p13c_labels_to_host_deterministic_onehot_topk_precompute"
TEACHER_SCOPE = "p13c_next_token_label_onehot_plus_deterministic_negatives"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compact_utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def q(value: str) -> str:
    return shlex.quote(value)


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


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


def active_run_root() -> Path:
    return REPO_ROOT / load_json(ACTIVE_RUN)["run_root"]


def run_command(
    command: list[str],
    *,
    check: bool = False,
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if check and completed.returncode != 0:
        joined = " ".join(q(part) for part in command)
        raise RuntimeError(
            f"command failed ({completed.returncode}): {joined}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def command_log_entry(name: str, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "name": name,
        "returncode": result.returncode,
        "stdout_first_4096": result.stdout[:4096],
        "stderr_first_4096": result.stderr[:4096],
    }


def adb(serial: str, args: list[str], *, check: bool = False, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return run_command(["adb", "-s", serial, *args], check=check, timeout=timeout)


def adb_shell(serial: str, command: str, *, check: bool = False, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return adb(serial, ["shell", command], check=check, timeout=timeout)


def adb_push(serial: str, local: Path, remote: str, *, timeout: int = 600) -> None:
    adb(serial, ["push", str(local), remote], check=True, timeout=timeout)


def adb_pull(serial: str, remote: str, local: Path, *, check: bool = False, timeout: int = 600) -> bool:
    local.parent.mkdir(parents=True, exist_ok=True)
    completed = adb(serial, ["pull", remote, str(local)], check=False, timeout=timeout)
    if check and completed.returncode != 0:
        raise RuntimeError(f"adb pull failed: {remote}\n{completed.stderr}")
    return completed.returncode == 0


def phone_path(phone_root: str, relative_or_absolute: str) -> str:
    if relative_or_absolute.startswith("/"):
        return relative_or_absolute
    return f"{phone_root.rstrip('/')}/{relative_or_absolute.strip('/')}"


def file_entry(path: Path, base: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(base)),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def pull_p13c_cache(serial: str, phone_cache: str, local_cache: Path) -> None:
    local_cache.mkdir(parents=True, exist_ok=True)
    for name in (
        "input_ids.u32.bin",
        "attention_mask.u8.bin",
        "labels.u32.bin",
        "loss_mask.u8.bin",
        "position_ids.u32.bin",
        "manifest.json",
    ):
        adb_pull(serial, f"{phone_cache}/{name}", local_cache / name, check=True, timeout=600)


def read_cache_arrays(cache_dir: Path) -> dict[str, np.ndarray]:
    arrays = {
        "input_ids": np.fromfile(cache_dir / "input_ids.u32.bin", dtype="<u4"),
        "attention_mask": np.fromfile(cache_dir / "attention_mask.u8.bin", dtype="u1"),
        "labels": np.fromfile(cache_dir / "labels.u32.bin", dtype="<u4"),
        "loss_mask": np.fromfile(cache_dir / "loss_mask.u8.bin", dtype="u1"),
        "position_ids": np.fromfile(cache_dir / "position_ids.u32.bin", dtype="<u4"),
    }
    token_count = arrays["input_ids"].size
    if token_count % SEQ != 0:
        raise ValueError(f"{cache_dir} token count is not divisible by seq{SEQ}")
    for name, array in arrays.items():
        if array.size != token_count:
            raise ValueError(f"{name} has {array.size} values; expected {token_count}")
    return arrays


def deterministic_topk_from_labels(labels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    flat_labels = labels.astype("<u4", copy=False).reshape(-1)
    token_ids = np.empty((flat_labels.size, TOP_K), dtype="<u4")
    probabilities = np.zeros((flat_labels.size, TOP_K), dtype="<f4")
    token_ids[:, 0] = flat_labels % VOCAB_SIZE
    probabilities[:, 0] = 1.0
    for item in range(1, TOP_K):
        token_ids[:, item] = (flat_labels + item) % VOCAB_SIZE
    return token_ids, probabilities


def write_sharded_split(
    *,
    split: str,
    cache_dir: Path,
    package_root: Path,
    phone_shard_root: str,
) -> dict[str, Any]:
    arrays = read_cache_arrays(cache_dir)
    full_manifest = load_json(cache_dir / "manifest.json")
    case_count = arrays["input_ids"].size // SEQ
    if case_count % SHARD_CASES != 0:
        raise ValueError(f"{split} case count {case_count} is not divisible by {SHARD_CASES}")
    shard_count = case_count // SHARD_CASES
    token_shards_phone: list[str] = []
    teacher_shards_phone: list[str] = []
    local_split_root = package_root / split
    token_root = local_split_root / "token_caches"
    teacher_root = local_split_root / "teacher_shards"
    token_root.mkdir(parents=True, exist_ok=True)
    teacher_root.mkdir(parents=True, exist_ok=True)
    shard_summaries: list[dict[str, Any]] = []
    shard_tokens = SHARD_CASES * SEQ
    for shard_index in range(shard_count):
        token_start = shard_index * shard_tokens
        token_end = token_start + shard_tokens
        shard_name = f"shard_{shard_index:04d}"
        token_dir = token_root / shard_name
        teacher_dir = teacher_root / shard_name
        token_dir.mkdir(parents=True, exist_ok=True)
        teacher_dir.mkdir(parents=True, exist_ok=True)

        input_ids = arrays["input_ids"][token_start:token_end]
        attention_mask = arrays["attention_mask"][token_start:token_end]
        labels = arrays["labels"][token_start:token_end]
        loss_mask = arrays["loss_mask"][token_start:token_end]
        position_ids = arrays["position_ids"][token_start:token_end]
        input_ids.astype("<u4", copy=False).tofile(token_dir / "input_ids.u32.bin")
        attention_mask.astype("u1", copy=False).tofile(token_dir / "attention_mask.u8.bin")
        labels.astype("<u4", copy=False).tofile(token_dir / "labels.u32.bin")
        loss_mask.astype("u1", copy=False).tofile(token_dir / "loss_mask.u8.bin")
        position_ids.astype("<u4", copy=False).tofile(token_dir / "position_ids.u32.bin")

        token_ids, probabilities = deterministic_topk_from_labels(labels)
        token_ids.tofile(teacher_dir / "topk_token_ids.u32.bin")
        probabilities.tofile(teacher_dir / "topk_probabilities.f32.bin")
        loss_mask.astype("u1", copy=False).tofile(teacher_dir / "loss_mask.u8.bin")
        labels.astype("<u4", copy=False).tofile(teacher_dir / "labels.u32.bin")

        token_manifest = {
            "schema_version": "phase13_p13h_token_cache_shard_v1",
            "split": split,
            "shard_index": shard_index,
            "source_cache_manifest": full_manifest,
            "sequence_length": SEQ,
            "sequence_count": SHARD_CASES,
            "loss_tokens": int(loss_mask.sum()),
            "files": [file_entry(path, token_dir) for path in sorted(token_dir.iterdir()) if path.is_file()],
        }
        write_json(token_dir / "manifest.json", token_manifest)
        teacher_manifest = {
            "schema_version": "phase13_p13h_label_contrastive_topk_teacher_v1",
            "telemetry_objective": OBJECTIVE_NAME,
            "objective_contract": OBJECTIVE_CONTRACT,
            "teacher_provenance": TEACHER_PROVENANCE,
            "teacher_scope": TEACHER_SCOPE,
            "model_id": MODEL_ID,
            "revision": MODEL_REVISION,
            "split": split,
            "shard_index": shard_index,
            "top_k": TOP_K,
            "sequence_length": SEQ,
            "sequence_count": SHARD_CASES,
            "token_count": shard_tokens,
            "loss_tokens": int(loss_mask.sum()),
            "source_token_cache_shard": str(token_dir.relative_to(package_root)),
            "files": [file_entry(path, teacher_dir) for path in sorted(teacher_dir.iterdir()) if path.is_file()],
        }
        write_json(teacher_dir / "manifest.json", teacher_manifest)

        phone_token = f"{phone_shard_root}/{split}/token_caches/{shard_name}"
        phone_teacher = f"{phone_shard_root}/{split}/teacher_shards/{shard_name}"
        token_shards_phone.append(phone_token)
        teacher_shards_phone.append(phone_teacher)
        if shard_index < 3 or shard_index + 1 == shard_count:
            shard_summaries.append(
                {
                    "shard_index": shard_index,
                    "loss_tokens": int(loss_mask.sum()),
                    "token_cache_phone": phone_token,
                    "teacher_shard_phone": phone_teacher,
                }
            )
    manifest = {
        "schema_version": "phase13_p13h_sharded_split_manifest_v1",
        "split": split,
        "source_cache": str(cache_dir),
        "phone_shard_root": phone_shard_root,
        "sequence_count": case_count,
        "shard_cases": SHARD_CASES,
        "shard_count": shard_count,
        "token_shards_phone": token_shards_phone,
        "teacher_shards_phone": teacher_shards_phone,
        "summary_shards": shard_summaries,
    }
    write_json(local_split_root / "shard_manifest.json", manifest)
    return manifest


def create_shard_package(
    *,
    serial: str,
    run_root: Path,
    report_dir: Path,
    phone_root: str,
    tmp: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    commands: list[dict[str, Any]] = []
    corpus_manifest = load_json(run_root / "P13-C-phone-native-hf-corpus/corpus_manifest.json")
    train_cache_phone = corpus_manifest["paths"]["train_cache"]
    heldout_cache_phone = corpus_manifest["paths"]["heldout_cache"]
    local_cache_root = tmp / "p13c_caches"
    pull_p13c_cache(serial, train_cache_phone, local_cache_root / "train")
    pull_p13c_cache(serial, heldout_cache_phone, local_cache_root / "heldout")

    phone_p13h_root = f"{phone_root.rstrip('/')}/phase13/{run_root.name}/p13h"
    phone_shard_root = f"{phone_p13h_root}/shards"
    package_root = tmp / "p13h_shard_package"
    package_root.mkdir(parents=True, exist_ok=True)
    train_manifest = write_sharded_split(
        split="train",
        cache_dir=local_cache_root / "train",
        package_root=package_root,
        phone_shard_root=phone_shard_root,
    )
    heldout_manifest = write_sharded_split(
        split="heldout",
        cache_dir=local_cache_root / "heldout",
        package_root=package_root,
        phone_shard_root=phone_shard_root,
    )
    package_manifest = {
        "schema_version": "phase13_p13h_label_contrastive_shard_package_v1",
        "created_at_utc": utc_now(),
        "objective": OBJECTIVE_NAME,
        "objective_contract": OBJECTIVE_CONTRACT,
        "teacher_provenance": TEACHER_PROVENANCE,
        "teacher_scope": TEACHER_SCOPE,
        "phone_shard_root": phone_shard_root,
        "train": train_manifest,
        "heldout": heldout_manifest,
    }
    write_json(package_root / "package_manifest.json", package_manifest)
    tar_path = tmp / "p13h_label_contrastive_shards.tar.gz"
    with tarfile.open(tar_path, "w:gz") as archive:
        archive.add(package_root, arcname=".")
    local_manifest_dir = report_dir / "shard_package_manifests"
    local_manifest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(package_root / "package_manifest.json", local_manifest_dir / "package_manifest.json")
    shutil.copy2(package_root / "train/shard_manifest.json", local_manifest_dir / "train_shard_manifest.json")
    shutil.copy2(package_root / "heldout/shard_manifest.json", local_manifest_dir / "heldout_shard_manifest.json")

    adb_shell(serial, f"rm -rf {q(phone_shard_root)} && mkdir -p {q(phone_shard_root)}", check=True)
    remote_tar = f"{phone_p13h_root}/p13h_label_contrastive_shards.tar.gz"
    adb_push(serial, tar_path, remote_tar, timeout=900)
    extract = adb_shell(
        serial,
        f"cd {q(phone_shard_root)} && tar -xzf {q(remote_tar)} && "
        f"find {q(phone_shard_root)} -name manifest.json | wc -l",
        check=False,
        timeout=900,
    )
    commands.append(command_log_entry("phone_extract_p13h_label_contrastive_shards", extract))
    if extract.returncode != 0:
        raise RuntimeError(f"P13-H shard extraction failed on phone:\n{extract.stderr}")
    package_manifest["tar_local_path"] = str(tar_path)
    package_manifest["tar_bytes"] = tar_path.stat().st_size
    package_manifest["tar_sha256"] = sha256_file(tar_path)
    package_manifest["phone_tar"] = remote_tar
    package_manifest["phone_extract_returncode"] = extract.returncode
    package_manifest["phone_extract_stdout"] = extract.stdout
    write_json(report_dir / "shard_package_manifest.json", package_manifest)
    return package_manifest, commands


def deploy_binaries(
    *,
    serial: str,
    phone_p13h_root: str,
    phase11_runner: Path,
    layer_runner: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not phase11_runner.exists():
        raise FileNotFoundError(f"phase11_runner not found: {phase11_runner}")
    if not layer_runner.exists():
        raise FileNotFoundError(f"gemma4_layer_runner not found: {layer_runner}")
    commands: list[dict[str, Any]] = []
    phone_bin = f"{phone_p13h_root}/bin"
    prep = adb_shell(serial, f"rm -rf {q(phone_bin)} && mkdir -p {q(phone_bin)}", check=False)
    commands.append(command_log_entry("phone_prepare_p13h_bin", prep))
    adb_push(serial, phase11_runner, f"{phone_bin}/phase11_runner")
    adb_push(serial, layer_runner, f"{phone_bin}/gemma4_layer_runner")
    chmod = adb_shell(serial, f"chmod 755 {q(phone_bin)}/* && sha256sum {q(phone_bin)}/*", check=False)
    commands.append(command_log_entry("phone_hash_p13h_binaries", chmod))
    return {
        "schema_version": "phase13_p13h_binary_deploy_v1",
        "phone_bin": phone_bin,
        "local_phase11_runner": str(phase11_runner),
        "local_phase11_runner_sha256": sha256_file(phase11_runner),
        "local_gemma4_layer_runner": str(layer_runner),
        "local_gemma4_layer_runner_sha256": sha256_file(layer_runner),
        "phone_sha256sum_stdout": chmod.stdout,
        "status": "pass" if chmod.returncode == 0 else "fail",
    }, commands


def queue_config(
    *,
    run_id: str,
    arm: str,
    token_caches: list[str],
    teacher_shards: list[str],
    checkpoint: str,
    iterations: int,
    learning_rate: float,
    apply_update: bool,
    phone_root: str,
) -> dict[str, Any]:
    return {
        "schema_version": "phase13_p13h_phone_long_run_arm_config_v1",
        "run_id": f"{run_id}_{arm}",
        "gate_name": "P13-H-phone-local-long-run",
        "gate_dir_name": GATE_DIR_NAME,
        "objective": "topk_embedding_kl",
        "objective_contract": OBJECTIVE_CONTRACT,
        "token_caches": token_caches,
        "teacher_shards": teacher_shards,
        "asset_dir": phone_path(phone_root, DEFAULT_ASSET_DIR),
        "layer0_pack": phone_path(phone_root, DEFAULT_LAYER0_PACK),
        "layer1_pack": phone_path(phone_root, DEFAULT_LAYER1_PACK),
        "initial_checkpoint": checkpoint,
        "iteration_count": iterations,
        "sample_every": max(iterations + 1, 1),
        "learning_rate": learning_rate,
        "adapter_rank": ADAPTER_RANK,
        "apply_update": apply_update,
        "optimizer": "adamw",
        "weight_decay": 0.01,
        "beta1": 0.9,
        "beta2": 0.999,
        "optimizer_epsilon": 1.0e-8,
        "grad_clip_l2": 1.0,
        "require_disconnect_marker": False,
        "marker_wait_seconds": 0,
        "disconnect_hold_seconds": 0,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "hidden_size": HIDDEN,
        "source_commit": run_command(["git", "rev-parse", "HEAD"], check=True).stdout.strip(),
        "kernel_lineage_class": "residual_adapter_opencl_training",
        "runtime_backend": "phone_cpu_token_to_hidden_plus_opencl_layers_and_adapter",
        "teacher_provenance": TEACHER_PROVENANCE,
        "hidden_state_fixtures_consumed": False,
    }


def write_queue_files(
    *,
    tmp: Path,
    phone_p13h_root: str,
    run_id: str,
    package_manifest: dict[str, Any],
    phone_root: str,
) -> dict[str, dict[str, Any]]:
    train_final_checkpoint = (
        f"{phone_p13h_root}/runs/{run_id}_train/{GATE_DIR_NAME}/"
        f"iterations/iter_{TRAIN_ITERATIONS - 1:06d}/checkpoint"
    )
    arm_specs = {
        "baseline_eval": {
            "token_caches": package_manifest["heldout"]["token_shards_phone"],
            "teacher_shards": package_manifest["heldout"]["teacher_shards_phone"],
            "checkpoint": PHASE12_LR3E4_FINAL_CHECKPOINT,
            "iterations": 1,
            "learning_rate": 0.0,
            "apply_update": False,
        },
        "train": {
            "token_caches": package_manifest["train"]["token_shards_phone"],
            "teacher_shards": package_manifest["train"]["teacher_shards_phone"],
            "checkpoint": PHASE12_LR3E4_FINAL_CHECKPOINT,
            "iterations": TRAIN_ITERATIONS,
            "learning_rate": LEARNING_RATE,
            "apply_update": True,
        },
        "trained_eval": {
            "token_caches": package_manifest["heldout"]["token_shards_phone"],
            "teacher_shards": package_manifest["heldout"]["teacher_shards_phone"],
            "checkpoint": train_final_checkpoint,
            "iterations": 1,
            "learning_rate": 0.0,
            "apply_update": False,
        },
    }
    queue_dir = tmp / "queue"
    queue_dir.mkdir(parents=True, exist_ok=True)
    arms: dict[str, dict[str, Any]] = {}
    for arm, spec in arm_specs.items():
        config_name = f"p13h_{arm}_config.json"
        queue_name = f"p13h_{arm}_queue.jsonl"
        config_path = queue_dir / config_name
        queue_path = queue_dir / queue_name
        config = queue_config(run_id=run_id, arm=arm, phone_root=phone_root, **spec)
        write_json(config_path, config)
        queue_path.write_text(
            json.dumps(
                {
                    "id": f"p13h_{arm}",
                    "gate": "H11-F",
                    "config": f"{phone_p13h_root}/queue/{config_name}",
                    "depends_on": [],
                    "resume": "fresh",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        arms[arm] = {
            "arm": arm,
            "run_id": f"{run_id}_{arm}",
            "queue_name": queue_name,
            "config_name": config_name,
            "local_queue": str(queue_path),
            "local_config": str(config_path),
            "state_path": f"{phone_p13h_root}/p13h_{arm}_state.json",
            "heartbeat_path": f"{phone_p13h_root}/p13h_{arm}_heartbeat.json",
            "stop_path": f"{phone_p13h_root}/STOP_p13h_{arm}",
            "phone_gate_dir": f"{phone_p13h_root}/runs/{run_id}_{arm}/{GATE_DIR_NAME}",
            "final_checkpoint": (
                f"{phone_p13h_root}/runs/{run_id}_{arm}/{GATE_DIR_NAME}/"
                f"iterations/iter_{spec['iterations'] - 1:06d}/checkpoint"
            ),
            "iterations": spec["iterations"],
            "apply_update": spec["apply_update"],
        }
    return arms


def run_objective_preflight(
    *,
    serial: str,
    phone_root: str,
    phone_p13h_root: str,
    binary_manifest: dict[str, Any],
    package_manifest: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    commands: list[dict[str, Any]] = []
    out = f"{phone_p13h_root}/preflight/objective_one_shot"
    train_token0 = package_manifest["train"]["token_shards_phone"][0]
    train_teacher0 = package_manifest["train"]["teacher_shards_phone"][0]
    layer_runner = f"{binary_manifest['phone_bin']}/gemma4_layer_runner"
    command = (
        f"rm -rf {q(out)} && "
        f"{q(layer_runner)} --run-h11f-topk-kl-compact "
        f"{q(train_token0)} {q(phone_path(phone_root, DEFAULT_ASSET_DIR))} "
        f"{q(phone_path(phone_root, DEFAULT_LAYER0_PACK))} "
        f"{q(phone_path(phone_root, DEFAULT_LAYER1_PACK))} "
        f"{q(PHASE12_LR3E4_FINAL_CHECKPOINT)} {q(train_teacher0)} {q(out)} 0.0 {ADAPTER_RANK} 0"
    )
    completed = adb_shell(serial, command, check=False, timeout=900)
    commands.append(command_log_entry("phone_p13h_label_contrastive_objective_preflight", completed))
    local = Path(tempfile.mkdtemp(prefix="p13h_preflight_pull_"))
    adb_pull(serial, f"{out}/telemetry.json", local / "telemetry.json", check=False)
    adb_pull(serial, f"{out}/checkpoint/manifest.json", local / "checkpoint_manifest.json", check=False)
    telemetry = load_json(local / "telemetry.json") if (local / "telemetry.json").exists() else {}
    checkpoint_manifest = (
        load_json(local / "checkpoint_manifest.json")
        if (local / "checkpoint_manifest.json").exists()
        else {}
    )
    return {
        "schema_version": "phase13_p13h_objective_preflight_v1",
        "status": (
            "pass"
            if completed.returncode == 0
            and telemetry.get("objective") == OBJECTIVE_NAME
            and telemetry.get("teacher_provenance") == TEACHER_PROVENANCE
            else "fail"
        ),
        "phone_output_dir": out,
        "returncode": completed.returncode,
        "telemetry": telemetry,
        "checkpoint_manifest": checkpoint_manifest,
    }, commands


def write_chain_script(
    *,
    script_path: Path,
    phone_p13h_root: str,
    run_id: str,
    phone_root: str,
    binary_manifest: dict[str, Any],
    arms: dict[str, dict[str, Any]],
) -> None:
    runner = f"{binary_manifest['phone_bin']}/phase11_runner"
    layer_runner = f"{binary_manifest['phone_bin']}/gemma4_layer_runner"
    safety_log = f"{phone_p13h_root}/p13h_{run_id}_safety.jsonl"
    lines = [
        "#!/system/bin/sh",
        "set -u",
        f"ROOT={q(phone_p13h_root)}",
        f"RUN_ID={q(run_id)}",
        f"RUNNER={q(runner)}",
        f"LAYER_RUNNER={q(layer_runner)}",
        f"SAFETY_LOG={q(safety_log)}",
        'LOG="$ROOT/p13h_${RUN_ID}_chain.log"',
        'EVENTS="$ROOT/p13h_${RUN_ID}_chain_events.jsonl"',
        'STATE="$ROOT/p13h_${RUN_ID}_chain_state.json"',
        'STOP="$ROOT/STOP_p13h_chain_${RUN_ID}"',
        'BOOTSTRAP="$ROOT/p13h_${RUN_ID}_chain.bootstrap.log"',
        'write_state() { printf \'{"schema_version":"phase13_p13h_detached_chain_state_v1","run_id":"%s","status":"%s","step":"%s","updated_at_epoch":%s}\\n\' "$RUN_ID" "$1" "$2" "$(date +%s)" > "$STATE"; }',
        'thermal_monitor() { while true; do TS="$(date +%s)"; BAT="$(dumpsys battery 2>/dev/null | awk \'/temperature:/ {print $2; exit}\')"; MAX=0; MAXTYPE=unknown; for z in /sys/class/thermal/thermal_zone*; do [ -r "$z/temp" ] || continue; T="$(cat "$z/temp" 2>/dev/null)"; Y="$(cat "$z/type" 2>/dev/null)"; case "$T" in -*) continue;; ""|*[!0-9]*) continue;; esac; if [ "$T" -gt "$MAX" ]; then MAX="$T"; MAXTYPE="$Y"; fi; done; printf \'{"ts":%s,"battery_tenth_c":"%s","max_zone_millideg_c":%s,"max_zone_type":"%s"}\\n\' "$TS" "$BAT" "$MAX" "$MAXTYPE" >> "$SAFETY_LOG"; if [ -n "$BAT" ] && [ "$BAT" -ge 460 ]; then touch "$STOP" "$ROOT"/STOP_p13h_*; exit 0; fi; if [ "$MAX" -ge 92000 ]; then touch "$STOP" "$ROOT"/STOP_p13h_*; exit 0; fi; sleep 30; done; }',
        'run_step() { STEP="$1"; shift; if [ -f "$STOP" ]; then write_state stopped "$STEP"; printf \'{"schema_version":"phase13_p13h_chain_event_v1","step":"%s","status":"stopped","returncode":130,"updated_at_epoch":%s}\\n\' "$STEP" "$(date +%s)" >> "$EVENTS"; exit 130; fi; write_state running "$STEP"; "$@" >> "$LOG" 2>&1; RC="$?"; if [ "$RC" -eq 0 ]; then STATUS=pass; else STATUS=fail; fi; printf \'{"schema_version":"phase13_p13h_chain_event_v1","step":"%s","status":"%s","returncode":%s,"updated_at_epoch":%s}\\n\' "$STEP" "$STATUS" "$RC" "$(date +%s)" >> "$EVENTS"; if [ "$RC" -ne 0 ]; then write_state failed "$STEP"; exit "$RC"; fi; }',
        'rm -f "$EVENTS" "$LOG" "$STATE" "$BOOTSTRAP" "$SAFETY_LOG" "$STOP"',
        'rm -f "$ROOT"/STOP_p13h_baseline_eval "$ROOT"/STOP_p13h_train "$ROOT"/STOP_p13h_trained_eval',
        'mkdir -p "$ROOT/runs"',
        "write_state running preflight",
        "thermal_monitor & MONITOR_PID=$!",
        "run_step g1_layer0_opencl_smoke \"$LAYER_RUNNER\" --run-opencl "
        f"{q(phone_path(phone_root, DEFAULT_LAYER0_PACK))} "
        "\"$ROOT/preflight/g1_layer0_opencl_smoke\"",
        "run_step g3_two_layer_opencl_stack_smoke \"$LAYER_RUNNER\" --run-opencl-stack "
        f"{q(phone_path(phone_root, DEFAULT_LAYER0_PACK))} "
        f"{q(phone_path(phone_root, DEFAULT_LAYER1_PACK))} "
        "\"$ROOT/preflight/g3_two_layer_opencl_stack_smoke\"",
    ]
    for arm in ("baseline_eval", "train", "trained_eval"):
        record = arms[arm]
        lines.append(
            f"run_step {arm} sh -c "
            + q(
                f"cd {phone_p13h_root}; {runner} --queue queue/{record['queue_name']} "
                f"--run-root runs --heartbeat {record['heartbeat_path']} "
                f"--state {record['state_path']} --stop-file {record['stop_path']}"
            )
        )
    lines.extend(
        [
            'kill "$MONITOR_PID" 2>/dev/null || true',
            "write_state completed done",
            "exit 0",
        ]
    )
    write_text(script_path, "\n".join(lines) + "\n")


def launch_chain(
    *,
    serial: str,
    phone_p13h_root: str,
    run_id: str,
    chain_script: Path,
) -> dict[str, Any]:
    remote_script = f"{phone_p13h_root}/{chain_script.name}"
    adb_push(serial, chain_script, remote_script)
    adb_shell(serial, f"chmod 755 {q(remote_script)}", check=True)
    pid_path = f"{phone_p13h_root}/p13h_{run_id}_chain.pid"
    bootstrap = f"{phone_p13h_root}/p13h_{run_id}_chain.bootstrap.log"
    launch = adb_shell(
        serial,
        f"cd {q(phone_p13h_root)}; rm -f {q(pid_path)} {q(bootstrap)}; "
        f"(nohup sh {q(remote_script)} > {q(bootstrap)} 2>&1 < /dev/null & echo $! > {q(pid_path)})",
        check=False,
    )
    pid_read = adb_shell(serial, f"cat {q(pid_path)} 2>/dev/null || true", check=False)
    return {
        "schema_version": "phase13_p13h_detached_launch_v1",
        "status": "launched" if launch.returncode == 0 and pid_read.stdout.strip() else "launch_failed",
        "phone_chain_script": remote_script,
        "phone_chain_pid_path": pid_path,
        "phone_chain_pid": pid_read.stdout.strip(),
        "phone_chain_state": f"{phone_p13h_root}/p13h_{run_id}_chain_state.json",
        "phone_chain_events": f"{phone_p13h_root}/p13h_{run_id}_chain_events.jsonl",
        "phone_chain_log": f"{phone_p13h_root}/p13h_{run_id}_chain.log",
        "phone_chain_bootstrap": bootstrap,
        "launch_returncode": launch.returncode,
        "launch_stdout": launch.stdout,
        "launch_stderr": launch.stderr,
    }


def write_artifact_manifest(report_dir: Path) -> None:
    entries: list[dict[str, Any]] = []
    for path in sorted(report_dir.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            entries.append({"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_json(
        report_dir / "artifact_manifest.json",
        {
            "schema_version": "phase13_p13h_artifact_manifest_v1",
            "created_at_utc": utc_now(),
            "artifacts": entries,
        },
    )


def update_phase13_status(run_root: Path, gate_result_path: Path, launch_status: str) -> None:
    status_path = run_root / "phase13_gate_status.json"
    phase_status = load_json(status_path)
    phase_status["gate_status"]["P13-H"] = (
        "running_detached" if launch_status == "launched" else "launch_failed"
    )
    phase_status["current_gate"] = "P13-H"
    phase_status["latest_gate_result"] = rel(gate_result_path)
    phase_status["updated_at_utc"] = utc_now()
    write_json(status_path, phase_status)
    active = load_json(ACTIVE_RUN)
    active["current_gate"] = "P13-H"
    active["updated_at_utc"] = utc_now()
    write_json(ACTIVE_RUN, active)


def update_gpd_state(gate_result_path: Path, launch: dict[str, Any]) -> None:
    gate_rel = rel(gate_result_path)
    state_path = REPO_ROOT / ".gpd/state.json"
    state = load_json(state_path)
    desc = (
        f"P13-H launched at {gate_rel}: detached phone-local chain uses scaled P13-C "
        f"8192/1024 caches with {OBJECTIVE_NAME}, {TRAIN_ITERATIONS} train updates, and thermal stop files."
    )
    state["position"]["last_activity"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    state["position"]["last_activity_desc"] = desc
    state["position"]["last_activity_description"] = desc
    state["position"]["status"] = "Phase 13 execution in progress; P13-H detached phone-local long run is running"
    state["session"]["stopped_at"] = (
        "P13-H detached run launched; monitor chain_state/events and collect after completion before P13-I."
    )
    todos = [
        item for item in state.get("pending_todos", []) if "P13-H" not in item and "phone-local long run" not in item
    ]
    next_todo = "Monitor and collect P13-H detached phone-local long run; only then execute P13-I exact claims."
    if next_todo not in todos:
        todos.insert(0, next_todo)
    state["pending_todos"] = todos
    result = (
        f"P13-H detached launch: {gate_rel}. Phone PID {launch.get('phone_chain_pid')} is running the "
        f"{TRAIN_ITERATIONS}-update chain over scaled P13-C shards with label-contrastive objective."
    )
    if result not in state.setdefault("intermediate_results", []):
        state["intermediate_results"].append(result)
    state["_synced_at"] = utc_now()
    write_json(state_path, state)
    with (REPO_ROOT / ".gpd/runlog.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "ts": utc_now(),
                    "event": "phase13_p13h_detached_phone_long_run_launched",
                    "project": "polymath-gemma4-snapdragon-megakernel",
                    "status": launch.get("status"),
                    "branch": "gemma4-megakernel-native-training",
                    "evidence": gate_rel,
                    "note": (
                        f"Detached phone-local P13-H chain launched with PID {launch.get('phone_chain_pid')}; "
                        f"objective={OBJECTIVE_NAME}, train_updates={TRAIN_ITERATIONS}."
                    ),
                },
                sort_keys=True,
            )
            + "\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", default=DEFAULT_SERIAL)
    parser.add_argument("--phone-root", default=DEFAULT_PHONE_ROOT)
    parser.add_argument("--phase11-runner", default=str(DEFAULT_PHASE11_RUNNER))
    parser.add_argument("--layer-runner", default=str(DEFAULT_LAYER_RUNNER))
    args = parser.parse_args()

    run_root = active_run_root()
    run_id = f"{run_root.name}_p13h_{compact_utc_now()}"
    report_dir = run_root / "P13-H-overnight-phone-local-long-run"
    report_dir.mkdir(parents=True, exist_ok=True)
    phone_p13h_root = f"{args.phone_root.rstrip('/')}/phase13/{run_root.name}/p13h"
    started_at = utc_now()
    commands: list[dict[str, Any]] = []

    p13g = load_json(run_root / "P13-G-heterogeneous-vs-adreno-baseline/gate_result.json")
    if p13g.get("status") != "fallback_adreno_only":
        raise RuntimeError("P13-H requires P13-G exact fallback artifact before launch")

    with tempfile.TemporaryDirectory(prefix="p13h_launch_") as tmp_name:
        tmp = Path(tmp_name)
        package_manifest, package_commands = create_shard_package(
            serial=args.serial,
            run_root=run_root,
            report_dir=report_dir,
            phone_root=args.phone_root,
            tmp=tmp,
        )
        commands.extend(package_commands)
        binary_manifest, binary_commands = deploy_binaries(
            serial=args.serial,
            phone_p13h_root=phone_p13h_root,
            phase11_runner=Path(args.phase11_runner),
            layer_runner=Path(args.layer_runner),
        )
        commands.extend(binary_commands)
        write_json(report_dir / "binary_deploy_manifest.json", binary_manifest)

        preflight, preflight_commands = run_objective_preflight(
            serial=args.serial,
            phone_root=args.phone_root,
            phone_p13h_root=phone_p13h_root,
            binary_manifest=binary_manifest,
            package_manifest=package_manifest,
        )
        commands.extend(preflight_commands)
        write_json(report_dir / "objective_preflight.json", preflight)
        if preflight["status"] != "pass":
            raise RuntimeError("P13-H objective preflight failed; refusing to launch invalid long run")

        arms = write_queue_files(
            tmp=tmp,
            phone_p13h_root=phone_p13h_root,
            run_id=run_id,
            package_manifest=package_manifest,
            phone_root=args.phone_root,
        )
        local_control = report_dir / "detached_chain" / "control"
        local_control.mkdir(parents=True, exist_ok=True)
        remote_queue_dir = f"{phone_p13h_root}/queue"
        adb_shell(args.serial, f"rm -rf {q(remote_queue_dir)} && mkdir -p {q(remote_queue_dir)}", check=True)
        for arm in arms.values():
            local_queue = Path(arm["local_queue"])
            local_config = Path(arm["local_config"])
            shutil.copy2(local_queue, local_control / local_queue.name)
            shutil.copy2(local_config, local_control / local_config.name)
            adb_push(args.serial, local_queue, f"{remote_queue_dir}/{local_queue.name}")
            adb_push(args.serial, local_config, f"{remote_queue_dir}/{local_config.name}")

        chain_script = tmp / f"p13h_{run_id}_chain.sh"
        write_chain_script(
            script_path=chain_script,
            phone_p13h_root=phone_p13h_root,
            run_id=run_id,
            phone_root=args.phone_root,
            binary_manifest=binary_manifest,
            arms=arms,
        )
        shutil.copy2(chain_script, report_dir / "detached_chain" / chain_script.name)
        launch = launch_chain(
            serial=args.serial,
            phone_p13h_root=phone_p13h_root,
            run_id=run_id,
            chain_script=chain_script,
        )

    detached_manifest = {
        "schema_version": "phase13_p13h_detached_manifest_v1",
        "run_id": run_id,
        "status": launch["status"],
        "started_at_utc": started_at,
        "phone_p13h_root": phone_p13h_root,
        "objective": OBJECTIVE_NAME,
        "objective_contract": OBJECTIVE_CONTRACT,
        "teacher_provenance": TEACHER_PROVENANCE,
        "train_iterations": TRAIN_ITERATIONS,
        "acceptance": {
            "minimum_updates": 5000,
            "minimum_wall_hours": 4,
            "active_wall_floor": 0.85,
            "heldout_gate": "trained_eval label_contrastive_topk_kl improves versus baseline_eval",
        },
        "arms": arms,
        "launch": launch,
    }
    write_json(report_dir / "detached_launch.json", detached_manifest)
    gate_status = "running_detached" if launch["status"] == "launched" else "launch_failed"
    blockers = [] if launch["status"] == "launched" else ["detached phone-local chain launch failed"]
    gate_result_path = report_dir / "gate_result.json"
    gate = {
        "schema_version": "phase13_p13h_phone_local_long_run_v1",
        "gate": "P13-H overnight phone-local long run",
        "status": gate_status,
        "started_at_utc": started_at,
        "ended_at_utc": None,
        "run_id": run_id,
        "authority_device": args.serial,
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "train_iterations": TRAIN_ITERATIONS,
        "objective": OBJECTIVE_NAME,
        "objective_contract": OBJECTIVE_CONTRACT,
        "teacher_provenance": TEACHER_PROVENANCE,
        "selected_trainable_scope": "post_layer0_rank16_residual_adapter",
        "selected_learning_rate": LEARNING_RATE,
        "phone_chain_state": launch.get("phone_chain_state"),
        "phone_chain_events": launch.get("phone_chain_events"),
        "phone_chain_pid": launch.get("phone_chain_pid"),
        "detached_launch": rel(report_dir / "detached_launch.json"),
        "shard_package_manifest": rel(report_dir / "shard_package_manifest.json"),
        "objective_preflight": rel(report_dir / "objective_preflight.json"),
        "promoted_claims": {
            "phone_local_chain_launched": launch["status"] == "launched",
            "scaled_p13c_train_cache_used": True,
            "scaled_p13c_heldout_cache_used": True,
            "full_gemma_teacher_topk_used": False,
            "label_contrastive_fallback_objective": True,
            "htp_training": False,
        },
        "nonclaims": [
            "P13-H launch does not yet prove completion or heldout improvement; collection is required.",
            "The label-contrastive objective is not full Gemma teacher distillation.",
            "No HTP output is consumed by this training loop.",
        ],
        "blockers": blockers,
    }
    write_json(gate_result_path, gate)
    write_text(report_dir / "blockers.md", "\n".join(f"- {item}" for item in blockers) + ("\n" if blockers else "- none\n"))
    write_text(
        report_dir / "falsifier_report.md",
        "# P13-H Launch Falsifier Report\n\n"
        "- Full Gemma teacher generation on the available RunPod CPU was benchmarked and rejected as a setup blocker for immediate launch.\n"
        f"- The launched objective is explicitly `{OBJECTIVE_NAME}`, derived from P13-C next-token labels, not full-teacher distillation.\n"
        "- P13-H remains pending until detached phone artifacts are collected and heldout metrics are adjudicated.\n",
    )
    write_text(report_dir / "commands.log", json.dumps({"commands": commands}, indent=2, sort_keys=True) + "\n")
    write_artifact_manifest(report_dir)
    update_phase13_status(run_root, gate_result_path, launch["status"])
    if launch["status"] == "launched":
        update_gpd_state(gate_result_path, launch)
    print(json.dumps({"status": gate_status, "gate_result": rel(gate_result_path), "pid": launch.get("phone_chain_pid")}, sort_keys=True))
    return 0 if launch["status"] == "launched" else 1


if __name__ == "__main__":
    raise SystemExit(main())

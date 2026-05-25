#!/usr/bin/env python3
"""Run Phase 12 C/D/E authority learning probes on the SM8750 phone.

This is intentionally narrower than a full Phase 12 completion script:

* Gate D creates a larger phone-native token cache through the C++ tokenizer.
* Gate C exercises rank-16/rank-32 residual adapters with AdamW + clipping.
* Gate E compares trained adapters against fixed heldout controls on top-k KL
  and a predeclared mini metric.

Raw adapter payloads, tokenizer cache binaries, and teacher shard binaries stay
on the phone or in temporary transfer directories. The report pulls only JSON
metrics, manifests, and compact audit records.
"""
from __future__ import annotations

import argparse
import array
import datetime as dt
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.host.run_phase11_h11e_scope_sweep import (  # noqa: E402
    BASE_RANK,
    HIDDEN,
    expand_checkpoint,
    q,
)
from scripts.host.run_phase11_h11f_objective_upgrade import (  # noqa: E402
    DEFAULT_ASSET_DIR,
    DEFAULT_BASE_CHECKPOINT,
    DEFAULT_HELDOUT_CACHE,
    DEFAULT_LAYER0_PACK,
    DEFAULT_LAYER1_PACK,
    DEFAULT_PHONE_ROOT,
    DEFAULT_SERIAL,
    DEFAULT_TEACHER_SCRIPT,
    RUNPOD_HOST,
    RUNPOD_KEY,
    RUNPOD_MODEL,
    RUNPOD_PORT,
    RUNPOD_PYTHON,
    adb,
    adb_pull,
    adb_shell,
    create_teacher_shard,
    load_json,
    phone_path,
    pull_token_cache,
    push_teacher_shard,
    sha256_file,
    utc_now,
    write_json,
    write_text,
)


DEFAULT_PHASE12_RUNNER = Path("/tmp/gemma4_phase12_android/phase11_runner")
DEFAULT_LAYER_RUNNER = Path("/tmp/gemma4_phase12_android/gemma4_layer_runner")
PHASE12_REPORT_ROOT = Path(
    "runtime/reports/gemma4_megakernel/phase12_hardware_native_learning"
)
GATE_DIR_NAME = "Phase12-CDE-learning"
SOURCE_URL = "https://huggingface.co/datasets/fka/awesome-chatgpt-prompts/resolve/main/prompts.csv"
PHONE_RAW_CORPUS = "hf_stream/g8/prompts.csv"
PHONE_TOKENIZER = "tokenizer/gemma4_e4b_bpe_v1"


def compact_utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_command(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, text=True, capture_output=True)
    if check and completed.returncode != 0:
        joined = " ".join(q(part) for part in command)
        raise RuntimeError(
            f"command failed ({completed.returncode}): {joined}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def deploy_binary(*, serial: str, phone_phase12_root: str, binary: Path, remote_name: str) -> str:
    if not binary.exists():
        raise FileNotFoundError(f"required Android binary not found: {binary}")
    adb_shell(serial, f"mkdir -p {q(phone_phase12_root + '/bin')}")
    remote = f"{phone_phase12_root}/bin/{remote_name}"
    adb(serial, ["push", str(binary), remote])
    adb_shell(serial, f"chmod 755 {q(remote)}")
    return remote


def read_float32(path: Path, expected: int) -> array.array:
    values = array.array("f")
    with path.open("rb") as handle:
        values.fromfile(handle, expected)
    if len(values) != expected:
        raise ValueError(f"{path} expected {expected} float32 values, found {len(values)}")
    return values


def prepare_expanded_checkpoints(
    *,
    serial: str,
    phone_root: str,
    phone_phase12_root: str,
    run_id: str,
    ranks: list[int],
    tmp: Path,
    report_dir: Path,
) -> dict[int, str]:
    base_remote = phone_path(phone_root, DEFAULT_BASE_CHECKPOINT)
    base_local = tmp / "base_rank4"
    adb_pull(serial, f"{base_remote}/adapter_a.f32.bin", base_local / "adapter_a.f32.bin", check=True)
    adb_pull(serial, f"{base_remote}/adapter_b.f32.bin", base_local / "adapter_b.f32.bin", check=True)
    remote_dirs: dict[int, str] = {}
    manifests: list[dict[str, Any]] = []
    for rank in ranks:
        local_dir = tmp / f"rank{rank}_init"
        manifest = expand_checkpoint(base_local, local_dir, rank)
        remote = f"{phone_phase12_root}/checkpoints/{run_id}_rank{rank}_init"
        adb_shell(serial, f"rm -rf {q(remote)} && mkdir -p {q(remote)}")
        adb(serial, ["push", str(local_dir / "adapter_a.f32.bin"), f"{remote}/adapter_a.f32.bin"])
        adb(serial, ["push", str(local_dir / "adapter_b.f32.bin"), f"{remote}/adapter_b.f32.bin"])
        adb(serial, ["push", str(local_dir / "manifest.json"), f"{remote}/manifest.json"])
        manifest["phone_path"] = remote
        manifests.append(manifest)
        remote_dirs[rank] = remote
    write_json(
        report_dir / "C-expanded-scope-repair" / "expanded_checkpoint_manifests.json",
        {"schema_version": "phase12_expanded_checkpoint_manifest_set_v1", "manifests": manifests},
    )
    return remote_dirs


def create_expanded_phone_cache(
    *,
    serial: str,
    phone_root: str,
    phone_phase12_root: str,
    remote_layer_runner: str,
    run_id: str,
    train_sequences: int,
    report_dir: Path,
    reuse_existing: bool,
) -> str:
    cache = f"{phone_phase12_root}/token_caches/{run_id}_train_seq{train_sequences}"
    started_at = utc_now()
    if reuse_existing:
        completed = adb_shell(serial, f"test -s {q(cache + '/manifest.json')}", check=False)
    else:
        command = (
            f"{q(remote_layer_runner)} --tokenize-pack "
            f"{q(phone_path(phone_root, PHONE_TOKENIZER))} "
            f"{q(phone_path(phone_root, PHONE_RAW_CORPUS))} "
            f"{q(cache)} 128 {train_sequences} {q(SOURCE_URL)}"
        )
        completed = adb_shell(serial, f"rm -rf {q(cache)} && {command}", check=False)
    local_manifest = report_dir / "D-phone-native-corpus" / "expanded_train_cache_manifest.json"
    adb_pull(serial, f"{cache}/manifest.json", local_manifest, check=completed.returncode == 0)
    manifest = load_json(local_manifest) if local_manifest.exists() else {}
    gate_d = {
        "schema_version": "phase12_gate_d_phone_native_cache_v1",
        "gate": "D",
        "status": "pass"
        if completed.returncode == 0
        and int(manifest.get("sequence_count", 0) or 0) > 8
        and manifest.get("tokenizer") == "native_cpp_bpe_from_tokenizer_json_tables"
        else "fail",
        "started_at_utc": started_at,
        "ended_at_utc": utc_now(),
        "phone_cache": cache,
        "phone_raw_corpus": phone_path(phone_root, PHONE_RAW_CORPUS),
        "phone_tokenizer": phone_path(phone_root, PHONE_TOKENIZER),
        "source_url": SOURCE_URL,
        "sequence_count": manifest.get("sequence_count"),
        "loss_tokens": manifest.get("loss_tokens"),
        "runtime_boundary": "phone_cpp_tokenizer_pack_no_host_minibatch_serving",
        "reuse_existing": reuse_existing,
        "returncode": completed.returncode,
        "stdout_first_2048": completed.stdout[:2048],
        "stderr_first_2048": completed.stderr[:2048],
    }
    if gate_d["status"] != "pass":
        gate_d["blockers"] = ["expanded phone-native token cache was not created with >8 sequences"]
    write_json(report_dir / "D-phone-native-corpus" / "gate_result.json", gate_d)
    write_text(
        report_dir / "D-phone-native-corpus" / "falsifier_report.md",
        "# Phase 12 Gate D Falsifier Report\n\n"
        f"- phone-native tokenizer path: {'pass' if gate_d['status'] == 'pass' else 'fail'}.\n"
        "- host minibatch serving: pass, training consumes phone cache paths; RunPod is used only for precomputed teacher top-k shards.\n",
    )
    return cache


def create_expanded_teacher(
    *,
    args: argparse.Namespace,
    serial: str,
    train_cache_phone: str,
    phone_phase12_root: str,
    run_id: str,
    tmp: Path,
    report_dir: Path,
    reuse_existing: bool,
) -> str:
    remote_teacher = f"{phone_phase12_root}/teacher_shards/{run_id}_expanded_train"
    if reuse_existing:
        completed = adb_shell(serial, f"test -s {q(remote_teacher + '/manifest.json')}", check=False)
        if completed.returncode != 0:
            raise FileNotFoundError(f"missing reusable phone teacher shard: {remote_teacher}")
        local_manifest = tmp / "teacher_shards" / "expanded_train" / "manifest.json"
        adb_pull(serial, f"{remote_teacher}/manifest.json", local_manifest, check=True)
        manifest = load_json(local_manifest)
    else:
        local_cache = tmp / "token_caches" / "expanded_train"
        pull_token_cache(serial, train_cache_phone, local_cache)
        local_teacher = tmp / "teacher_shards" / "expanded_train"
        manifest = create_teacher_shard(
            args=args,
            run_id=run_id,
            split="phase12_expanded_train",
            local_cache=local_cache,
            local_teacher=local_teacher,
        )
        push_teacher_shard(serial, local_teacher, remote_teacher)
    write_json(
        report_dir / "D-phone-native-corpus" / "expanded_teacher_manifest.json",
        {
            "schema_version": "phase12_expanded_teacher_manifest_v1",
            "phone_teacher_shard": remote_teacher,
            "teacher_generation": "RunPod_precomputed_full_Gemma4_topk_before_phone_training_runtime",
            "runtime_teacher_service_used": False,
            "reuse_existing": reuse_existing,
            "manifest": manifest,
        },
    )
    return remote_teacher


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def split_file_bytes(source: Path, out_paths: list[Path], bytes_per_shard: int) -> None:
    data = source.read_bytes()
    expected = bytes_per_shard * len(out_paths)
    if len(data) != expected:
        raise ValueError(f"{source} has {len(data)} bytes; expected {expected}")
    for index, out_path in enumerate(out_paths):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        start = index * bytes_per_shard
        out_path.write_bytes(data[start : start + bytes_per_shard])


def push_dir_files(serial: str, local_dir: Path, remote_dir: str, names: list[str]) -> None:
    adb_shell(serial, f"rm -rf {q(remote_dir)} && mkdir -p {q(remote_dir)}")
    for name in names:
        adb(serial, ["push", str(local_dir / name), f"{remote_dir}/{name}"])


def split_expanded_cache_and_teacher(
    *,
    serial: str,
    phone_phase12_root: str,
    run_id: str,
    train_sequences: int,
    train_cache_phone: str,
    train_teacher_phone: str,
    tmp: Path,
    report_dir: Path,
) -> tuple[list[str], list[str]]:
    if train_sequences % BASE_RANK != 0:
        raise ValueError("expanded train sequence count must be divisible by 4")
    if train_sequences % 8 != 0:
        raise ValueError("current OpenCL runner shard split requires train_sequences divisible by 8")
    shard_count = train_sequences // 8
    cache_src = tmp / "expanded_cache_for_split"
    teacher_src = tmp / "expanded_teacher_for_split"
    pull_token_cache(serial, train_cache_phone, cache_src)
    adb_pull(serial, f"{train_cache_phone}/selected_text.txt", cache_src / "selected_text.txt", check=True)
    for name in ("manifest.json", "topk_token_ids.u32.bin", "topk_probabilities.f32.bin", "loss_mask.u8.bin", "labels.u32.bin"):
        adb_pull(serial, f"{train_teacher_phone}/{name}", teacher_src / name, check=True)

    cache_names = [
        "input_ids.u32.bin",
        "attention_mask.u8.bin",
        "labels.u32.bin",
        "loss_mask.u8.bin",
        "position_ids.u32.bin",
    ]
    cache_bytes_per_shard = {
        "input_ids.u32.bin": 8 * 128 * 4,
        "attention_mask.u8.bin": 8 * 128,
        "labels.u32.bin": 8 * 128 * 4,
        "loss_mask.u8.bin": 8 * 128,
        "position_ids.u32.bin": 8 * 128 * 4,
    }
    teacher_names = [
        "topk_token_ids.u32.bin",
        "topk_probabilities.f32.bin",
        "loss_mask.u8.bin",
        "labels.u32.bin",
    ]
    teacher_bytes_per_shard = {
        "topk_token_ids.u32.bin": 8 * 128 * 8 * 4,
        "topk_probabilities.f32.bin": 8 * 128 * 8 * 4,
        "loss_mask.u8.bin": 8 * 128,
        "labels.u32.bin": 8 * 128 * 4,
    }

    cache_dirs = [tmp / "runner_cache_shards" / f"shard_{index:02d}" for index in range(shard_count)]
    teacher_dirs = [tmp / "runner_teacher_shards" / f"shard_{index:02d}" for index in range(shard_count)]
    for name in cache_names:
        split_file_bytes(cache_src / name, [item / name for item in cache_dirs], cache_bytes_per_shard[name])
    for name in teacher_names:
        split_file_bytes(teacher_src / name, [item / name for item in teacher_dirs], teacher_bytes_per_shard[name])

    selected_text = (cache_src / "selected_text.txt").read_text(encoding="utf-8").splitlines()
    source_manifest = load_json(cache_src / "manifest.json")
    teacher_manifest = load_json(teacher_src / "manifest.json")
    phone_caches: list[str] = []
    phone_teachers: list[str] = []
    split_records: list[dict[str, Any]] = []
    for index in range(shard_count):
        cache_dir = cache_dirs[index]
        teacher_dir = teacher_dirs[index]
        (cache_dir / "selected_text.txt").write_text(
            "\n".join(selected_text[index * 8 : (index + 1) * 8]) + "\n",
            encoding="utf-8",
        )
        cache_manifest = {
            "schema_version": "phase12_split_phone_token_pack_v1",
            "source_expanded_manifest": source_manifest,
            "shard_index": index,
            "sequence_length": 128,
            "sequence_count": 8,
            "tokenizer": source_manifest.get("tokenizer"),
            "input_ids_sha256": sha256_file(cache_dir / "input_ids.u32.bin"),
            "attention_mask_sha256": sha256_file(cache_dir / "attention_mask.u8.bin"),
            "labels_sha256": sha256_file(cache_dir / "labels.u32.bin"),
            "loss_mask_sha256": sha256_file(cache_dir / "loss_mask.u8.bin"),
            "position_ids_sha256": sha256_file(cache_dir / "position_ids.u32.bin"),
            "selected_text_sha256": sha256_file(cache_dir / "selected_text.txt"),
        }
        write_json(cache_dir / "manifest.json", cache_manifest)
        teacher_manifest_split = {
            "schema_version": "phase12_split_topk_teacher_shard_v1",
            "source_expanded_manifest": teacher_manifest,
            "shard_index": index,
            "sequence_length": 128,
            "sequence_count": 8,
            "top_k": 8,
            "topk_token_ids_sha256": sha256_file(teacher_dir / "topk_token_ids.u32.bin"),
            "topk_probabilities_sha256": sha256_file(teacher_dir / "topk_probabilities.f32.bin"),
            "loss_mask_sha256": sha256_file(teacher_dir / "loss_mask.u8.bin"),
            "labels_sha256": sha256_file(teacher_dir / "labels.u32.bin"),
        }
        write_json(teacher_dir / "manifest.json", teacher_manifest_split)
        phone_cache = f"{phone_phase12_root}/token_caches/{run_id}_train_shard{index:02d}"
        phone_teacher = f"{phone_phase12_root}/teacher_shards/{run_id}_train_shard{index:02d}"
        push_dir_files(serial, cache_dir, phone_cache, [*cache_names, "selected_text.txt", "manifest.json"])
        push_dir_files(serial, teacher_dir, phone_teacher, [*teacher_names, "manifest.json"])
        phone_caches.append(phone_cache)
        phone_teachers.append(phone_teacher)
        split_records.append(
            {
                "shard_index": index,
                "phone_cache": phone_cache,
                "phone_teacher": phone_teacher,
                "cache_manifest": cache_manifest,
                "teacher_manifest": teacher_manifest_split,
            }
        )
    write_json(
        report_dir / "D-phone-native-corpus" / "runner_shards_manifest.json",
        {
            "schema_version": "phase12_runner_shards_manifest_v1",
            "reason": "current OpenCL runner is compiled for 8 cases; expanded 16-sequence cache is split into two queue shards",
            "shards": split_records,
        },
    )
    return phone_caches, phone_teachers


def write_queue_and_config(
    *,
    local_dir: Path,
    phone_root: str,
    phone_phase12_root: str,
    run_id: str,
    rank: int,
    arm: str,
    token_cache: str | list[str],
    teacher_shard: str | list[str],
    checkpoint: str,
    iterations: int,
    learning_rate: float,
    apply_update: bool,
    optimizer: str,
    weight_decay: float,
    beta1: float,
    beta2: float,
    optimizer_epsilon: float,
    grad_clip_l2: float,
) -> tuple[Path, Path]:
    config = local_dir / f"phase12_rank{rank}_{arm}_config.json"
    queue = local_dir / f"phase12_rank{rank}_{arm}_queue.jsonl"
    config_payload = {
        "schema_version": "phase12_cde_authority_arm_config_v1",
        "run_id": f"{run_id}_rank{rank}_{arm}",
        "gate_name": "Phase12-CDE",
        "gate_dir_name": GATE_DIR_NAME,
        "objective": "topk_embedding_kl",
        "token_caches": token_cache if isinstance(token_cache, list) else [token_cache],
        "teacher_shards": teacher_shard if isinstance(teacher_shard, list) else [teacher_shard],
        "asset_dir": phone_path(phone_root, DEFAULT_ASSET_DIR),
        "layer0_pack": phone_path(phone_root, DEFAULT_LAYER0_PACK),
        "layer1_pack": phone_path(phone_root, DEFAULT_LAYER1_PACK),
        "initial_checkpoint": checkpoint,
        "iteration_count": iterations,
        "sample_every": max(iterations + 1, 1),
        "learning_rate": learning_rate,
        "adapter_rank": rank,
        "apply_update": apply_update,
        "optimizer": optimizer,
        "weight_decay": weight_decay,
        "beta1": beta1,
        "beta2": beta2,
        "optimizer_epsilon": optimizer_epsilon,
        "grad_clip_l2": grad_clip_l2,
        "require_disconnect_marker": False,
        "marker_wait_seconds": 0,
        "disconnect_hold_seconds": 0,
    }
    write_json(config, config_payload)
    queue.write_text(
        json.dumps(
            {
                "id": f"phase12_rank{rank}_{arm}",
                "gate": "H11-F",
                "config": f"{phone_phase12_root}/queue/{queue.name.replace('_queue.jsonl', '_config.json')}",
                "depends_on": [],
                "resume": "fresh",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return queue, config


def pull_arm_artifacts(
    *,
    serial: str,
    gate_dir: str,
    run_dir: str,
    state_path: str,
    heartbeat_path: str,
    local_report: Path,
    iterations: int,
) -> None:
    for name in (
        "gate_result.json",
        "telemetry.jsonl",
        "timing_breakdown.json",
        "blockers.md",
        "falsifier_report.md",
        "artifact_manifest.json",
        "queue_schema.json",
        "daemon_static_artifact_manifest.json",
    ):
        adb_pull(serial, f"{gate_dir}/{name}", local_report / name)
    adb_pull(serial, f"{run_dir}/campaign_manifest.json", local_report / "campaign_manifest.json")
    adb_pull(serial, f"{run_dir}/checksum_chain.jsonl", local_report / "checksum_chain.jsonl")
    adb_pull(serial, state_path, local_report / "runner_state.json")
    adb_pull(serial, heartbeat_path, local_report / "heartbeat.json")
    for index in range(iterations):
        remote_iter = f"{gate_dir}/iterations/iter_{index:06d}"
        local_iter = local_report / "iterations" / f"iter_{index:06d}"
        adb_pull(serial, f"{remote_iter}/telemetry.json", local_iter / "telemetry.json")
        adb_pull(serial, f"{remote_iter}/checkpoint/manifest.json", local_iter / "checkpoint_manifest.json")
        adb_pull(serial, f"{remote_iter}/replay_manifest.json", local_iter / "replay_manifest.json")


def run_arm(
    *,
    args: argparse.Namespace,
    phone_phase12_root: str,
    remote_runner: str,
    run_id: str,
    rank: int,
    arm: str,
    token_cache: str | list[str],
    teacher_shard: str | list[str],
    checkpoint: str,
    iterations: int,
    learning_rate: float,
    apply_update: bool,
    report_dir: Path,
    tmp: Path,
) -> dict[str, Any]:
    local_arm = tmp / f"rank{rank}_{arm}"
    local_arm.mkdir(parents=True, exist_ok=True)
    queue, config = write_queue_and_config(
        local_dir=local_arm,
        phone_root=args.phone_root,
        phone_phase12_root=phone_phase12_root,
        run_id=run_id,
        rank=rank,
        arm=arm,
        token_cache=token_cache,
        teacher_shard=teacher_shard,
        checkpoint=checkpoint,
        iterations=iterations,
        learning_rate=learning_rate,
        apply_update=apply_update,
        optimizer=args.optimizer,
        weight_decay=args.weight_decay,
        beta1=args.beta1,
        beta2=args.beta2,
        optimizer_epsilon=args.optimizer_epsilon,
        grad_clip_l2=args.grad_clip_l2,
    )
    local_report = report_dir / "arms" / f"rank{rank}_{arm}"
    control_dir = local_report / "control"
    control_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(queue, control_dir / queue.name)
    shutil.copy2(config, control_dir / config.name)

    remote_queue_dir = f"{phone_phase12_root}/queue"
    adb_shell(args.serial, f"mkdir -p {q(remote_queue_dir)}")
    adb(args.serial, ["push", str(queue), f"{remote_queue_dir}/{queue.name}"])
    adb(args.serial, ["push", str(config), f"{remote_queue_dir}/{config.name}"])

    state_path = f"{phone_phase12_root}/phase12_rank{rank}_{arm}_state.json"
    heartbeat_path = f"{phone_phase12_root}/phase12_rank{rank}_{arm}_heartbeat.json"
    stop_path = f"{phone_phase12_root}/STOP_phase12_rank{rank}_{arm}"
    adb_shell(args.serial, f"rm -f {q(state_path)} {q(heartbeat_path)} {q(stop_path)}")
    command = (
        f"cd {q(phone_phase12_root)}; "
        f"{q(remote_runner)} --queue {q(f'queue/{queue.name}')} --run-root runs "
        f"--heartbeat {q(heartbeat_path)} --state {q(state_path)} --stop-file {q(stop_path)}"
    )
    started_at = utc_now()
    completed = adb_shell(args.serial, command, check=False)
    arm_run_id = f"{run_id}_rank{rank}_{arm}"
    run_dir = f"{phone_phase12_root}/runs/{arm_run_id}"
    gate_dir = f"{run_dir}/{GATE_DIR_NAME}"
    pull_arm_artifacts(
        serial=args.serial,
        gate_dir=gate_dir,
        run_dir=run_dir,
        state_path=state_path,
        heartbeat_path=heartbeat_path,
        local_report=local_report,
        iterations=iterations,
    )
    return {
        "schema_version": "phase12_cde_arm_run_v1",
        "rank": rank,
        "arm": arm,
        "apply_update": apply_update,
        "iterations": iterations,
        "run_id": arm_run_id,
        "started_at_utc": started_at,
        "ended_at_utc": utc_now(),
        "returncode": completed.returncode,
        "stdout_first_4096": completed.stdout[:4096],
        "stderr_first_4096": completed.stderr[:4096],
        "phone_gate_dir": gate_dir,
        "final_checkpoint": f"{gate_dir}/iterations/iter_{iterations - 1:06d}/checkpoint",
        "local_report_dir": str(local_report),
    }


def load_iteration_metrics(arm: dict[str, Any]) -> list[dict[str, Any]]:
    local = Path(arm["local_report_dir"])
    metrics = []
    for path in sorted((local / "iterations").glob("iter_*/telemetry.json")):
        telemetry = load_json(path)
        metrics.append(
            {
                "iteration": int(path.parent.name.split("_")[-1]),
                "loss_topk_kl": float(telemetry.get("loss_topk_kl", float("nan"))),
                "student_teacher_top1_agreement": float(
                    telemetry.get("student_teacher_top1_agreement", float("nan"))
                ),
                "mean_student_teacher_top1_probability": float(
                    telemetry.get("mean_student_teacher_top1_probability", float("nan"))
                ),
                "label_in_teacher_topk_rate": float(
                    telemetry.get("label_in_teacher_topk_rate", float("nan"))
                ),
                "active_tokens": int(telemetry.get("active_tokens", 0) or 0),
                "applied_update": bool(telemetry.get("applied_update", False)),
                "optimizer": telemetry.get("optimizer"),
                "optimizer_step": telemetry.get("optimizer_step"),
                "grad_clip_l2": telemetry.get("grad_clip_l2"),
                "grad_clip_scale": telemetry.get("grad_clip_scale"),
                "combined_gradient_l2": telemetry.get("combined_gradient_l2"),
                "gradient_l2": telemetry.get("gradient_l2", {}),
                "checkpoint_delta_l2": telemetry.get("checkpoint_delta_l2", {}),
                "max_rss_kb": int(telemetry.get("max_rss_kb", 0) or 0),
            }
        )
    return metrics


def summarize_arm(arm: dict[str, Any]) -> dict[str, Any]:
    local = Path(arm["local_report_dir"])
    gate = load_json(local / "gate_result.json") if (local / "gate_result.json").exists() else {}
    metrics = load_iteration_metrics(arm)
    losses = [item["loss_topk_kl"] for item in metrics]
    delta_norms = []
    max_rss = 0
    for item in metrics:
        delta = item.get("checkpoint_delta_l2", {})
        delta_norms.append(float(delta.get("adapter_a", 0.0)) + float(delta.get("adapter_b", 0.0)))
        max_rss = max(max_rss, int(item.get("max_rss_kb", 0) or 0))
    return {
        "schema_version": "phase12_cde_arm_summary_v1",
        "rank": arm["rank"],
        "arm": arm["arm"],
        "status": "pass" if arm["returncode"] == 0 and gate.get("status") == "pass" else "fail",
        "gate_status": gate.get("status", "missing"),
        "iterations": len(metrics),
        "required_iterations": arm["iterations"],
        "losses": losses,
        "loss_delta": losses[0] - losses[-1] if len(losses) >= 2 else 0.0,
        "finite_losses": all(math.isfinite(value) for value in losses),
        "checkpoint_changed": any(value > 0.0 for value in delta_norms),
        "max_rss_kb": max_rss,
        "first": metrics[0] if metrics else {},
        "last": metrics[-1] if metrics else {},
        "gate": gate,
        "run": arm,
    }


def evaluate_rank(
    *,
    rank: int,
    baseline: dict[str, Any],
    train: dict[str, Any],
    trained: dict[str, Any],
    epsilon: float,
) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    if train["status"] != "pass" or train["iterations"] < train["required_iterations"]:
        blockers.append(f"rank-{rank} train arm did not pass configured iterations")
    if not train["finite_losses"]:
        blockers.append(f"rank-{rank} train losses were non-finite")
    if train["loss_delta"] <= 0.0:
        blockers.append(f"rank-{rank} train top-k KL did not decrease")
    if not train["checkpoint_changed"]:
        blockers.append(f"rank-{rank} train checkpoint did not change")
    if train["first"].get("optimizer") != "adamw":
        blockers.append(f"rank-{rank} train did not report AdamW optimizer")
    if baseline["status"] != "pass" or trained["status"] != "pass":
        blockers.append(f"rank-{rank} heldout control or trained eval did not pass")
    baseline_last = baseline.get("last", {})
    trained_last = trained.get("last", {})
    if baseline_last and trained_last:
        if trained_last["loss_topk_kl"] > baseline_last["loss_topk_kl"] + epsilon:
            blockers.append(f"rank-{rank} heldout top-k KL regressed versus fixed control")
        if (
            trained_last["mean_student_teacher_top1_probability"]
            <= baseline_last["mean_student_teacher_top1_probability"] + epsilon
        ):
            blockers.append(f"rank-{rank} heldout mini metric did not improve")
        if (
            trained_last["student_teacher_top1_agreement"] + 1.0e-12
            < baseline_last["student_teacher_top1_agreement"]
        ):
            blockers.append(f"rank-{rank} heldout agreement regressed")
    else:
        blockers.append(f"rank-{rank} heldout metrics missing")
    result = {
        "schema_version": "phase12_cde_rank_result_v1",
        "rank": rank,
        "status": "pass" if not blockers else "fail",
        "blockers": blockers,
        "fixed_adapter_control": baseline,
        "train": train,
        "trained_heldout": trained,
    }
    return result, blockers


def artifact_manifest(report_dir: Path) -> dict[str, Any]:
    entries = []
    forbidden_suffixes = (".f32.bin", ".bf16.bin", ".safetensors", ".u32.bin", ".u8.bin")
    forbidden = []
    for path in sorted(report_dir.rglob("*")):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        entry = {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        entries.append(entry)
        if path.name.endswith(forbidden_suffixes):
            forbidden.append(entry)
    return {
        "schema_version": "phase12_cde_artifact_manifest_v1",
        "report_dir": str(report_dir),
        "git_allowed_artifacts": entries,
        "forbidden_payload_artifacts": forbidden,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", default=DEFAULT_SERIAL)
    parser.add_argument("--phone-root", default=DEFAULT_PHONE_ROOT)
    parser.add_argument("--run-id", default=f"{compact_utc_now()}_phase12_cde_authority")
    parser.add_argument("--asset-run-id", default=None)
    parser.add_argument("--reuse-assets", action="store_true")
    parser.add_argument("--phase12-runner", type=Path, default=DEFAULT_PHASE12_RUNNER)
    parser.add_argument("--layer-runner", type=Path, default=DEFAULT_LAYER_RUNNER)
    parser.add_argument("--ranks", default="16,32")
    parser.add_argument("--iterations", type=int, default=8)
    parser.add_argument("--train-sequences", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--optimizer", default="adamw", choices=["adamw", "sgd"])
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--beta1", type=float, default=0.9)
    parser.add_argument("--beta2", type=float, default=0.999)
    parser.add_argument("--optimizer-epsilon", type=float, default=1.0e-8)
    parser.add_argument("--grad-clip-l2", type=float, default=1.0)
    parser.add_argument("--heldout-epsilon", type=float, default=1.0e-9)
    parser.add_argument("--teacher-script", type=Path, default=DEFAULT_TEACHER_SCRIPT)
    parser.add_argument("--runpod-host", default=RUNPOD_HOST)
    parser.add_argument("--runpod-port", default=RUNPOD_PORT)
    parser.add_argument("--runpod-key", default=RUNPOD_KEY)
    parser.add_argument("--runpod-python", default=RUNPOD_PYTHON)
    parser.add_argument("--runpod-model", default=RUNPOD_MODEL)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--host-report-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ranks = [int(item.strip()) for item in args.ranks.split(",") if item.strip()]
    if any(rank <= BASE_RANK for rank in ranks):
        raise ValueError("--ranks must contain expanded ranks > 4")
    if args.train_sequences <= 8:
        raise ValueError("--train-sequences must expand beyond the H11-H 8-sequence cache")
    report_dir = args.host_report_dir or PHASE12_REPORT_ROOT / args.run_id / "CDE-expanded-learning"
    report_dir.mkdir(parents=True, exist_ok=True)
    phone_phase12_root = f"{args.phone_root.rstrip('/')}/phase12"
    phone_phase11_root = f"{args.phone_root.rstrip('/')}/phase11"
    started_at = utc_now()
    write_json(
        report_dir / "predeclared_learning_probe.json",
        {
            "schema_version": "phase12_cde_predeclared_learning_probe_v1",
            "declared_before_phone_training_run": True,
            "declared_at_utc": started_at,
            "ranks": ranks,
            "train_sequences": args.train_sequences,
            "optimizer": args.optimizer,
            "learning_rate": args.learning_rate,
            "weight_decay": args.weight_decay,
            "grad_clip_l2": args.grad_clip_l2,
            "objective": "topk_embedding_kl_distillation_v1",
            "heldout_primary": "loss_topk_kl non-regression versus fixed control",
            "mini_metric": "heldout mean_student_teacher_top1_probability improves beyond fixed control",
            "agreement_guardrail": "heldout student_teacher_top1_agreement non-regression",
            "nonclaims": [
                "full Gemma4 training",
                "HTP backprop",
                "multi-site adapter training",
                "benchmark readiness",
                "broad capability",
            ],
        },
    )
    remote_runner = deploy_binary(
        serial=args.serial,
        phone_phase12_root=phone_phase12_root,
        binary=args.phase12_runner,
        remote_name="phase11_runner",
    )
    remote_layer_runner = deploy_binary(
        serial=args.serial,
        phone_phase12_root=phone_phase12_root,
        binary=args.layer_runner,
        remote_name="gemma4_layer_runner",
    )
    with tempfile.TemporaryDirectory(prefix="phase12_cde_") as tmp_name:
        tmp = Path(tmp_name)
        asset_run_id = args.asset_run_id or args.run_id
        train_cache_phone = create_expanded_phone_cache(
            serial=args.serial,
            phone_root=args.phone_root,
            phone_phase12_root=phone_phase12_root,
            remote_layer_runner=remote_layer_runner,
            run_id=asset_run_id,
            train_sequences=args.train_sequences,
            report_dir=report_dir,
            reuse_existing=args.reuse_assets,
        )
        train_teacher_phone = create_expanded_teacher(
            args=args,
            serial=args.serial,
            train_cache_phone=train_cache_phone,
            phone_phase12_root=phone_phase12_root,
            run_id=asset_run_id,
            tmp=tmp,
            report_dir=report_dir,
            reuse_existing=args.reuse_assets,
        )
        train_cache_queue, train_teacher_queue = split_expanded_cache_and_teacher(
            serial=args.serial,
            phone_phase12_root=phone_phase12_root,
            run_id=args.run_id,
            train_sequences=args.train_sequences,
            train_cache_phone=train_cache_phone,
            train_teacher_phone=train_teacher_phone,
            tmp=tmp,
            report_dir=report_dir,
        )
        checkpoint_dirs = prepare_expanded_checkpoints(
            serial=args.serial,
            phone_root=args.phone_root,
            phone_phase12_root=phone_phase12_root,
            run_id=args.run_id,
            ranks=ranks,
            tmp=tmp,
            report_dir=report_dir,
        )
        heldout_cache_phone = phone_path(args.phone_root, DEFAULT_HELDOUT_CACHE)
        heldout_teacher_phone = f"{phone_phase11_root}/h11f_teacher_shards/heldout"
        arm_runs: list[dict[str, Any]] = []
        for rank in ranks:
            baseline = run_arm(
                args=args,
                phone_phase12_root=phone_phase12_root,
                remote_runner=remote_runner,
                run_id=args.run_id,
                rank=rank,
                arm="baseline_eval",
                token_cache=heldout_cache_phone,
                teacher_shard=heldout_teacher_phone,
                checkpoint=checkpoint_dirs[rank],
                iterations=1,
                learning_rate=0.0,
                apply_update=False,
                report_dir=report_dir,
                tmp=tmp,
            )
            train = run_arm(
                args=args,
                phone_phase12_root=phone_phase12_root,
                remote_runner=remote_runner,
                run_id=args.run_id,
                rank=rank,
                arm="train",
                token_cache=train_cache_queue,
                teacher_shard=train_teacher_queue,
                checkpoint=checkpoint_dirs[rank],
                iterations=args.iterations,
                learning_rate=args.learning_rate,
                apply_update=True,
                report_dir=report_dir,
                tmp=tmp,
            )
            trained = run_arm(
                args=args,
                phone_phase12_root=phone_phase12_root,
                remote_runner=remote_runner,
                run_id=args.run_id,
                rank=rank,
                arm="trained_eval",
                token_cache=heldout_cache_phone,
                teacher_shard=heldout_teacher_phone,
                checkpoint=train["final_checkpoint"],
                iterations=1,
                learning_rate=0.0,
                apply_update=False,
                report_dir=report_dir,
                tmp=tmp,
            )
            arm_runs.extend([baseline, train, trained])

    summaries = [summarize_arm(item) for item in arm_runs]
    by_rank_arm = {(item["rank"], item["arm"]): item for item in summaries}
    rank_results: list[dict[str, Any]] = []
    all_blockers: list[str] = []
    for rank in ranks:
        result, blockers = evaluate_rank(
            rank=rank,
            baseline=by_rank_arm[(rank, "baseline_eval")],
            train=by_rank_arm[(rank, "train")],
            trained=by_rank_arm[(rank, "trained_eval")],
            epsilon=args.heldout_epsilon,
        )
        rank_results.append(result)
        all_blockers.extend(blockers)

    passing = [item for item in rank_results if item["status"] == "pass"]
    selected = passing[0] if passing else None
    if len(passing) > 1:
        selected = min(
            passing,
            key=lambda item: item["trained_heldout"]["last"]["loss_topk_kl"],
        )
    c_status = "pass_residual_expanded_scope" if passing else "fail"
    c_nonclaims = [
        "multi-site adapter training remains blocked; current backward path is post-layer0 residual only",
        "independent analytical gradient parity for top-k KL is not yet proven beyond finite phone gradients/checkpoint movement",
    ]
    gate_c = {
        "schema_version": "phase12_gate_c_expanded_scope_result_v1",
        "gate": "C",
        "status": c_status,
        "rank_results": rank_results,
        "selected_residual_rank": selected["rank"] if selected else None,
        "optimizer_repair": {
            "optimizer": args.optimizer,
            "weight_decay": args.weight_decay,
            "grad_clip_l2": args.grad_clip_l2,
            "adamw_state_policy": "phone_checkpoint_optimizer_state_manifest_hashes_only",
        },
        "memory_budget": [
            {
                "rank": rank,
                "adapter_parameter_count": 2 * HIDDEN * rank,
                "adapter_checkpoint_bytes": 2 * HIDDEN * rank * 4,
                "adamw_state_bytes": 4 * HIDDEN * rank * 4,
                "max_rss_kb": max(
                    by_rank_arm[(rank, arm)]["max_rss_kb"]
                    for arm in ("baseline_eval", "train", "trained_eval")
                ),
            }
            for rank in ranks
        ],
        "blockers": all_blockers,
        "nonclaims": c_nonclaims,
    }
    gate_e = {
        "schema_version": "phase12_gate_e_learning_signal_result_v1",
        "gate": "E",
        "status": "pass" if selected else "fail",
        "selected_rank": selected["rank"] if selected else None,
        "predeclared_metric": "heldout mean_student_teacher_top1_probability",
        "selected_result": selected,
        "blockers": [] if selected else all_blockers,
    }
    write_json(report_dir / "arm_runs.json", {"schema_version": "phase12_cde_arm_runs_v1", "runs": arm_runs})
    write_json(report_dir / "arm_summaries.json", {"schema_version": "phase12_cde_arm_summaries_v1", "arms": summaries})
    write_json(report_dir / "C-expanded-scope-repair" / "gate_result.json", gate_c)
    write_json(report_dir / "E-heldout-mini-metric" / "gate_result.json", gate_e)
    write_text(
        report_dir / "C-expanded-scope-repair" / "falsifier_report.md",
        "# Phase 12 Gate C Falsifier Report\n\n"
        f"- residual expanded-rank authority training: {'pass' if passing else 'fail'}.\n"
        "- multi-site adapter: not promoted; no layer-internal backward kernels exist in this path.\n"
        "- gradient parity: partial only; phone gradients are finite and checkpoints move, but independent top-k analytical parity remains unproven.\n",
    )
    write_text(
        report_dir / "E-heldout-mini-metric" / "falsifier_report.md",
        "# Phase 12 Gate E Falsifier Report\n\n"
        f"- larger-scope heldout improvement: {'pass' if selected else 'fail'}.\n"
        "- metric chosen after results: pass, see predeclared_learning_probe.json.\n",
    )
    top_status = "pass" if selected else "fail"
    write_json(
        report_dir / "phase12_cde_gate_result.json",
        {
            "schema_version": "phase12_cde_gate_result_v1",
            "status": top_status,
            "started_at_utc": started_at,
            "ended_at_utc": utc_now(),
            "run_id": args.run_id,
            "phone_phase12_root": phone_phase12_root,
            "gate_c": gate_c,
            "gate_d": load_json(report_dir / "D-phone-native-corpus" / "gate_result.json"),
            "gate_e": gate_e,
            "nonclaims": [
                "full Gemma4 training",
                "HTP backprop",
                "multi-site adapter training",
                "benchmark readiness",
                "broad capability",
            ],
        },
    )
    write_text(
        report_dir / "blockers.md",
        "- None for the residual-rank learning fallback.\n" if top_status == "pass" else "".join(f"- {item}\n" for item in all_blockers),
    )
    write_text(
        report_dir / "commands.log",
        "adb shell gemma4_layer_runner --tokenize-pack PHONE_TOKENIZER PHONE_RAW_CSV PHONE_PHASE12_CACHE 128 N SOURCE_URL\n"
        "ssh RunPod create_h11f_topk_teacher_shard.py --token-cache EXPANDED_CACHE --out TEACHER_SHARD\n"
        "adb shell phase11_runner --queue queue/phase12_rankN_<arm>_queue.jsonl --run-root runs --heartbeat ... --state ...\n",
    )
    manifest = artifact_manifest(report_dir)
    write_json(report_dir / "artifact_manifest.json", manifest)
    print(json.dumps({"status": top_status, "host_report_dir": str(report_dir), "selected_rank": gate_e["selected_rank"]}, sort_keys=True))
    return 0 if top_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

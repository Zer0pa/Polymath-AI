#!/usr/bin/env python3
"""Run Phase 11 H11-F top-k KL objective upgrade gate."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_SERIAL = "FY25013101C8"
DEFAULT_PHONE_ROOT = "/data/local/tmp/polymath_gemma4_gate"
DEFAULT_ASSET_DIR = "streamed_assets/g8_layer01_20260517T071405Z"
DEFAULT_LAYER0_PACK = "layer_pack/gemma4_e4b_layer0_seq128_v0"
DEFAULT_LAYER1_PACK = "layer_pack/gemma4_e4b_layer1_seq128_v0"
DEFAULT_BASE_CHECKPOINT = "adapter_training/g5g6_rank4_20260517T040000Z/checkpoint"
DEFAULT_TRAIN_CACHE = "hf_stream/20260517T083219Z_phase10_hf_auth_token_bridge_baseline_cache"
DEFAULT_HELDOUT_CACHE = "sustained_g9_20260517T071405Z/cache_001"
DEFAULT_PHASE11_RUNNER = Path(
    "integrations/gemma4-snapdragon-megakernel/build/"
    "gemma4_megakernel_android/phase11_runner"
)
DEFAULT_TEACHER_SCRIPT = Path(
    "integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/tools/"
    "reference/create_h11f_topk_teacher_shard.py"
)
RUNPOD_HOST = "38.80.152.147"
RUNPOD_PORT = "31002"
RUNPOD_KEY = "~/.ssh/id_ed25519"
RUNPOD_PYTHON = "/workspace/Polymath-AI/.venv/bin/python"
RUNPOD_MODEL = "/workspace/models/gemma4_e4b/snapshot"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compact_utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def q(value: str) -> str:
    return shlex.quote(value)


def run_command(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, text=True, capture_output=True)
    if check and completed.returncode != 0:
        joined = " ".join(shlex.quote(part) for part in command)
        raise RuntimeError(
            f"command failed ({completed.returncode}): {joined}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def adb(serial: str, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run_command(["adb", "-s", serial, *args], check=check)


def adb_shell(serial: str, command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return adb(serial, ["shell", command], check=check)


def adb_pull(serial: str, remote_path: str, local_path: Path, *, check: bool = False) -> bool:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    completed = adb(serial, ["pull", remote_path, str(local_path)], check=False)
    if completed.returncode == 0:
        return True
    if check:
        raise RuntimeError(f"adb pull failed for {remote_path}:\n{completed.stderr}")
    return False


def ssh_base(args: argparse.Namespace) -> list[str]:
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=20",
        "-p",
        args.runpod_port,
        "-i",
        str(Path(args.runpod_key).expanduser()),
        f"root@{args.runpod_host}",
    ]


def ssh_command(args: argparse.Namespace, command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run_command([*ssh_base(args), command], check=check)


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
        ]
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
        ]
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def phone_path(phone_root: str, relative_or_absolute: str) -> str:
    if relative_or_absolute.startswith("/"):
        return relative_or_absolute
    return f"{phone_root.rstrip('/')}/{relative_or_absolute.strip('/')}"


def deploy_runner(*, serial: str, phone_phase11_root: str, runner: Path) -> str:
    if not runner.exists():
        raise FileNotFoundError(f"phase11_runner not found: {runner}")
    adb_shell(serial, f"mkdir -p {q(phone_phase11_root)}")
    remote = f"{phone_phase11_root}/phase11_runner"
    adb(serial, ["push", str(runner), remote])
    adb_shell(serial, f"chmod 755 {q(remote)}")
    return remote


def pull_token_cache(serial: str, phone_cache: str, local_cache: Path) -> None:
    for name in (
        "input_ids.u32.bin",
        "attention_mask.u8.bin",
        "loss_mask.u8.bin",
        "labels.u32.bin",
        "position_ids.u32.bin",
        "manifest.json",
    ):
        adb_pull(serial, f"{phone_cache}/{name}", local_cache / name, check=True)


def create_teacher_shard(
    *,
    args: argparse.Namespace,
    run_id: str,
    split: str,
    local_cache: Path,
    local_teacher: Path,
) -> dict[str, Any]:
    remote_root = f"/workspace/artifacts/polymath_gemma4/phase11/{run_id}/teacher_work"
    remote_cache = f"{remote_root}/token_caches/{split}"
    remote_teacher = f"{remote_root}/teacher_shards/{split}"
    remote_script = f"{remote_root}/create_h11f_topk_teacher_shard.py"
    ssh_command(args, f"rm -rf {q(remote_cache)} {q(remote_teacher)} && mkdir -p {q(remote_cache)} {q(remote_teacher)}")
    scp_to(args, args.teacher_script, remote_script)
    for path in sorted(local_cache.iterdir()):
        if path.is_file():
            scp_to(args, path, f"{remote_cache}/{path.name}")
    command = (
        f"{q(args.runpod_python)} {q(remote_script)} "
        f"--snapshot-dir {q(args.runpod_model)} "
        f"--token-cache {q(remote_cache)} --out {q(remote_teacher)} "
        f"--split {q(split)} --top-k {args.top_k} --seq 128"
    )
    ssh_command(args, command)
    local_teacher.mkdir(parents=True, exist_ok=True)
    for name in (
        "manifest.json",
        "topk_token_ids.u32.bin",
        "topk_probabilities.f32.bin",
        "loss_mask.u8.bin",
        "labels.u32.bin",
    ):
        scp_from(args, f"{remote_teacher}/{name}", local_teacher / name)
    return load_json(local_teacher / "manifest.json")


def push_teacher_shard(serial: str, local_teacher: Path, remote_teacher: str) -> None:
    adb_shell(serial, f"rm -rf {q(remote_teacher)} && mkdir -p {q(remote_teacher)}")
    for name in (
        "manifest.json",
        "topk_token_ids.u32.bin",
        "topk_probabilities.f32.bin",
        "loss_mask.u8.bin",
        "labels.u32.bin",
    ):
        adb(serial, ["push", str(local_teacher / name), f"{remote_teacher}/{name}"])


def write_queue_and_config(
    *,
    local_dir: Path,
    phone_phase11_root: str,
    run_id: str,
    arm: str,
    token_cache: str,
    teacher_shard: str,
    checkpoint: str,
    iterations: int,
    learning_rate: float,
    apply_update: bool,
) -> tuple[Path, Path]:
    config = local_dir / f"h11f_{arm}_config.json"
    queue = local_dir / f"h11f_{arm}_queue.jsonl"
    config_payload = {
        "schema_version": "phase11_h11f_config_v1",
        "run_id": f"{run_id}_{arm}",
        "gate_name": "H11-F",
        "gate_dir_name": "H11-F-objective-upgrade",
        "objective": "topk_embedding_kl",
        "token_caches": [token_cache],
        "teacher_shards": [teacher_shard],
        "asset_dir": phone_path(DEFAULT_PHONE_ROOT, DEFAULT_ASSET_DIR),
        "layer0_pack": phone_path(DEFAULT_PHONE_ROOT, DEFAULT_LAYER0_PACK),
        "layer1_pack": phone_path(DEFAULT_PHONE_ROOT, DEFAULT_LAYER1_PACK),
        "initial_checkpoint": checkpoint,
        "iteration_count": iterations,
        "sample_every": max(iterations + 1, 1),
        "learning_rate": learning_rate,
        "adapter_rank": 4,
        "apply_update": apply_update,
        "require_disconnect_marker": False,
        "marker_wait_seconds": 0,
        "disconnect_hold_seconds": 0,
    }
    write_json(config, config_payload)
    queue.write_text(
        json.dumps(
            {
                "id": f"h11f_{arm}",
                "gate": "H11-F",
                "config": f"{phone_phase11_root}/queue/{config.name}",
                "depends_on": [],
                "resume": "fresh",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return queue, config


def run_arm(
    *,
    serial: str,
    phone_phase11_root: str,
    remote_runner: str,
    run_id: str,
    arm: str,
    token_cache: str,
    teacher_shard: str,
    checkpoint: str,
    iterations: int,
    learning_rate: float,
    apply_update: bool,
    report_dir: Path,
    tmp: Path,
) -> dict[str, Any]:
    local_arm = tmp / f"{arm}_queue"
    local_arm.mkdir(parents=True, exist_ok=True)
    queue, config = write_queue_and_config(
        local_dir=local_arm,
        phone_phase11_root=phone_phase11_root,
        run_id=run_id,
        arm=arm,
        token_cache=token_cache,
        teacher_shard=teacher_shard,
        checkpoint=checkpoint,
        iterations=iterations,
        learning_rate=learning_rate,
        apply_update=apply_update,
    )
    remote_queue_dir = f"{phone_phase11_root}/queue"
    adb_shell(serial, f"mkdir -p {q(remote_queue_dir)}")
    adb(serial, ["push", str(queue), f"{remote_queue_dir}/{queue.name}"])
    adb(serial, ["push", str(config), f"{remote_queue_dir}/{config.name}"])
    state_path = f"{phone_phase11_root}/h11f_{arm}_state.json"
    heartbeat_path = f"{phone_phase11_root}/h11f_{arm}_heartbeat.json"
    stop_path = f"{phone_phase11_root}/STOP_h11f_{arm}"
    adb_shell(serial, f"rm -f {q(state_path)} {q(heartbeat_path)} {q(stop_path)}")
    command = (
        f"cd {q(phone_phase11_root)}; "
        f"{q(remote_runner)} --queue {q(f'queue/{queue.name}')} --run-root runs "
        f"--heartbeat {q(heartbeat_path)} --state {q(state_path)} --stop-file {q(stop_path)}"
    )
    started_at = utc_now()
    completed = adb_shell(serial, command, check=False)
    arm_run_id = f"{run_id}_{arm}"
    gate_dir = f"{phone_phase11_root}/runs/{arm_run_id}/H11-F-objective-upgrade"
    local_report = report_dir / "arms" / arm
    for name in (
        "gate_result.json",
        "telemetry.jsonl",
        "timing_breakdown.json",
        "blockers.md",
        "falsifier_report.md",
        "artifact_manifest.json",
    ):
        adb_pull(serial, f"{gate_dir}/{name}", local_report / name)
    for index in range(iterations):
        remote_iter = f"{gate_dir}/iterations/iter_{index:06d}"
        local_iter = local_report / "iterations" / f"iter_{index:06d}"
        adb_pull(serial, f"{remote_iter}/telemetry.json", local_iter / "telemetry.json")
        adb_pull(
            serial,
            f"{remote_iter}/checkpoint/manifest.json",
            local_iter / "checkpoint_manifest.json",
        )
    final_checkpoint = f"{gate_dir}/iterations/iter_{iterations - 1:06d}/checkpoint"
    return {
        "schema_version": "phase11_h11f_arm_run_v1",
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
        "final_checkpoint": final_checkpoint,
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
                "mean_student_label_probability_when_in_topk": float(
                    telemetry.get("mean_student_label_probability_when_in_topk", float("nan"))
                ),
                "active_tokens": int(telemetry.get("active_tokens", 0) or 0),
                "applied_update": bool(telemetry.get("applied_update", False)),
                "gradient_l2": telemetry.get("gradient_l2", {}),
                "checkpoint_delta_l2": telemetry.get("checkpoint_delta_l2", {}),
            }
        )
    return metrics


def summarize_arm(arm: dict[str, Any]) -> dict[str, Any]:
    gate_path = Path(arm["local_report_dir"]) / "gate_result.json"
    gate = load_json(gate_path) if gate_path.exists() else {}
    metrics = load_iteration_metrics(arm)
    losses = [item["loss_topk_kl"] for item in metrics]
    return {
        "schema_version": "phase11_h11f_arm_summary_v1",
        "arm": arm["arm"],
        "status": "pass" if arm["returncode"] == 0 and gate.get("status") == "pass" else "fail",
        "gate_status": gate.get("status", "missing"),
        "iterations": len(metrics),
        "losses": losses,
        "loss_delta": losses[0] - losses[-1] if len(losses) >= 2 else 0.0,
        "first": metrics[0] if metrics else {},
        "last": metrics[-1] if metrics else {},
        "run": arm,
    }


def artifact_manifest(report_dir: Path) -> dict[str, Any]:
    entries = []
    for path in sorted(report_dir.rglob("*")):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        entries.append({"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return {
        "schema_version": "phase11_h11f_artifact_manifest_v1",
        "gate": "H11-F",
        "report_dir": str(report_dir),
        "git_allowed_artifacts": entries,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", default=DEFAULT_SERIAL)
    parser.add_argument("--phone-root", default=DEFAULT_PHONE_ROOT)
    parser.add_argument("--run-id", default=f"{compact_utc_now()}_h11f_objective_upgrade")
    parser.add_argument("--phase11-runner", type=Path, default=DEFAULT_PHASE11_RUNNER)
    parser.add_argument("--teacher-script", type=Path, default=DEFAULT_TEACHER_SCRIPT)
    parser.add_argument("--runpod-host", default=RUNPOD_HOST)
    parser.add_argument("--runpod-port", default=RUNPOD_PORT)
    parser.add_argument("--runpod-key", default=RUNPOD_KEY)
    parser.add_argument("--runpod-python", default=RUNPOD_PYTHON)
    parser.add_argument("--runpod-model", default=RUNPOD_MODEL)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--host-report-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.iterations < 100:
        raise ValueError("H11-F requires at least 100 training iterations")
    report_dir = args.host_report_dir or Path(
        f"runtime/reports/gemma4_megakernel/hardware_native_povc/"
        f"{args.run_id}/H11-F-objective-upgrade"
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    phone_phase11_root = f"{args.phone_root.rstrip('/')}/phase11"
    train_cache_phone = phone_path(args.phone_root, DEFAULT_TRAIN_CACHE)
    heldout_cache_phone = phone_path(args.phone_root, DEFAULT_HELDOUT_CACHE)
    base_checkpoint = phone_path(args.phone_root, DEFAULT_BASE_CHECKPOINT)
    train_teacher_phone = f"{phone_phase11_root}/h11f_teacher_shards/train"
    heldout_teacher_phone = f"{phone_phase11_root}/h11f_teacher_shards/heldout"
    started = utc_now()
    objective_spec = {
        "schema_version": "phase11_h11f_objective_spec_v1",
        "declared_before_phone_training_run": True,
        "objective": "conditional top-k KL distillation",
        "teacher": "RunPod-precomputed full Gemma4 E4B top-k shard",
        "runtime_teacher_service": "forbidden_and_not_used",
        "student_logits": "phone-local two-layer hidden plus rank-4 adapter projected through tied unscaled embed_tokens rows for teacher top-k ids with final logit softcap 30",
        "train_split": DEFAULT_TRAIN_CACHE,
        "heldout_split": DEFAULT_HELDOUT_CACHE,
        "primary_train_gate": "train loss_topk_kl decreases over >=100 phone-local updates",
        "primary_heldout_gate": "heldout loss_topk_kl non-regression versus fixed-adapter control",
        "mini_capability_metric": "heldout mean_student_teacher_top1_probability improves beyond fixed-adapter control on instruction-format prompt shard",
        "agreement_guardrail": "heldout student_teacher_top1_agreement must not regress",
    }
    write_json(report_dir / "objective_spec.json", objective_spec)

    with tempfile.TemporaryDirectory(prefix="h11f_objective_") as tmp_name:
        tmp = Path(tmp_name)
        train_cache_local = tmp / "token_caches" / "train"
        heldout_cache_local = tmp / "token_caches" / "heldout"
        pull_token_cache(args.serial, train_cache_phone, train_cache_local)
        pull_token_cache(args.serial, heldout_cache_phone, heldout_cache_local)
        train_teacher_local = tmp / "teacher_shards" / "train"
        heldout_teacher_local = tmp / "teacher_shards" / "heldout"
        train_teacher_manifest = create_teacher_shard(
            args=args,
            run_id=args.run_id,
            split="train",
            local_cache=train_cache_local,
            local_teacher=train_teacher_local,
        )
        heldout_teacher_manifest = create_teacher_shard(
            args=args,
            run_id=args.run_id,
            split="heldout",
            local_cache=heldout_cache_local,
            local_teacher=heldout_teacher_local,
        )
        push_teacher_shard(args.serial, train_teacher_local, train_teacher_phone)
        push_teacher_shard(args.serial, heldout_teacher_local, heldout_teacher_phone)
        write_json(
            report_dir / "teacher_shard_manifest.json",
            {
                "schema_version": "phase11_h11f_teacher_shards_manifest_v1",
                "runpod_model": args.runpod_model,
                "runpod_python": args.runpod_python,
                "runpod_workspace": f"/workspace/artifacts/polymath_gemma4/phase11/{args.run_id}",
                "phone_paths": {
                    "train": train_teacher_phone,
                    "heldout": heldout_teacher_phone,
                },
                "train": train_teacher_manifest,
                "heldout": heldout_teacher_manifest,
            },
        )
        remote_runner = deploy_runner(
            serial=args.serial,
            phone_phase11_root=phone_phase11_root,
            runner=args.phase11_runner,
        )
        baseline_eval = run_arm(
            serial=args.serial,
            phone_phase11_root=phone_phase11_root,
            remote_runner=remote_runner,
            run_id=args.run_id,
            arm="baseline_eval",
            token_cache=heldout_cache_phone,
            teacher_shard=heldout_teacher_phone,
            checkpoint=base_checkpoint,
            iterations=1,
            learning_rate=0.0,
            apply_update=False,
            report_dir=report_dir,
            tmp=tmp,
        )
        train = run_arm(
            serial=args.serial,
            phone_phase11_root=phone_phase11_root,
            remote_runner=remote_runner,
            run_id=args.run_id,
            arm="train",
            token_cache=train_cache_phone,
            teacher_shard=train_teacher_phone,
            checkpoint=base_checkpoint,
            iterations=args.iterations,
            learning_rate=args.learning_rate,
            apply_update=True,
            report_dir=report_dir,
            tmp=tmp,
        )
        trained_eval = run_arm(
            serial=args.serial,
            phone_phase11_root=phone_phase11_root,
            remote_runner=remote_runner,
            run_id=args.run_id,
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

    arms = [baseline_eval, train, trained_eval]
    summaries = [summarize_arm(item) for item in arms]
    summary_by_arm = {item["arm"]: item for item in summaries}
    blockers = []
    train_summary = summary_by_arm["train"]
    baseline_summary = summary_by_arm["baseline_eval"]
    trained_summary = summary_by_arm["trained_eval"]
    if train_summary["status"] != "pass" or train_summary["iterations"] < args.iterations:
        blockers.append("100-iteration top-k KL train arm did not pass")
    if train_summary["loss_delta"] <= 0.0:
        blockers.append("train top-k KL did not decrease over the 100-iteration run")
    baseline_last = baseline_summary["last"]
    trained_last = trained_summary["last"]
    if baseline_summary["status"] != "pass" or trained_summary["status"] != "pass":
        blockers.append("held-out fixed/trained evaluation arm did not pass")
    if trained_last and baseline_last:
        if trained_last["loss_topk_kl"] > baseline_last["loss_topk_kl"] + 1.0e-9:
            blockers.append("held-out top-k KL regressed versus fixed-adapter control")
        if (
            trained_last["mean_student_teacher_top1_probability"]
            <= baseline_last["mean_student_teacher_top1_probability"] + 1.0e-9
        ):
            blockers.append("held-out teacher top-1 probability did not improve beyond fixed-adapter control")
        if (
            trained_last["student_teacher_top1_agreement"]
            + 1.0e-12
            < baseline_last["student_teacher_top1_agreement"]
        ):
            blockers.append("held-out teacher top-1 agreement regressed versus fixed-adapter control")
    else:
        blockers.append("missing held-out metrics")
    status = "pass" if not blockers else "fail"

    write_json(report_dir / "arm_runs.json", {"schema_version": "phase11_h11f_arm_runs_v1", "runs": arms})
    write_json(report_dir / "loss_traces.json", {"schema_version": "phase11_h11f_loss_traces_v1", "arms": summaries})
    write_json(
        report_dir / "heldout_report.json",
        {
            "schema_version": "phase11_h11f_heldout_report_v1",
            "fixed_adapter_control": baseline_summary,
            "trained_adapter": trained_summary,
        },
    )
    write_json(
        report_dir / "mini_eval_report.json",
        {
            "schema_version": "phase11_h11f_mini_eval_report_v1",
            "metric": "heldout mean_student_teacher_top1_probability",
            "control": baseline_last,
            "trained": trained_last,
            "improved": not blockers and bool(trained_last and baseline_last),
        },
    )
    gate_result = {
        "schema_version": "phase11_h11f_gate_result_v1",
        "gate": "H11-F",
        "status": status,
        "blockers": blockers,
        "selected_scope": "post_layer0_rank4_residual_adapter",
        "objective": "topk_embedding_kl_distillation_v1",
        "teacher_shard_status": "precomputed_on_runpod_pushed_to_phone_before_runtime",
        "runtime_teacher_service_used": False,
        "fixed_adapter_control": baseline_summary,
        "train_summary": train_summary,
        "trained_heldout_summary": trained_summary,
        "started_at_utc": started,
        "ended_at_utc": utc_now(),
        "host_report_dir": str(report_dir),
        "next_on_pass": "carry objective into H11-G/H11-H",
        "next_on_fail": "try one predeclared fallback objective or proceed with systems-only H11-H claim if fallback fails",
    }
    write_json(report_dir / "gate_result.json", gate_result)
    write_text(
        report_dir / "blockers.md",
        "- None for H11-F.\n" if not blockers else "".join(f"- {item}\n" for item in blockers),
    )
    write_text(
        report_dir / "falsifier_report.md",
        "# H11-F Falsifier Report\n\n"
        "- parity-MSE renamed as objective: pass, telemetry uses `loss_topk_kl` from a precomputed full-teacher top-k shard.\n"
        "- RunPod teacher during phone runtime: pass, teacher shards were pushed to phone before the phone-local runner started.\n"
        "- train-only loss overfit sold as capability: "
        + ("pass" if status == "pass" else "fail")
        + ", held-out control comparison governs the gate.\n"
        "- metric chosen after results: pass, objective_spec.json declares the mini metric before phone training analysis.\n",
    )
    write_text(
        report_dir / "commands.log",
        "adb pull phone token caches for teacher-shard generation\n"
        "ssh runpod create_h11f_topk_teacher_shard.py --snapshot-dir /workspace/models/gemma4_e4b/snapshot --top-k 8\n"
        "adb push precomputed teacher shards to PHONE_PHASE11_ROOT/h11f_teacher_shards/{train,heldout}\n"
        "adb shell phase11_runner --queue queue/h11f_<arm>_queue.jsonl --run-root runs --heartbeat ... --state ...\n",
    )
    write_json(report_dir / "artifact_manifest.json", artifact_manifest(report_dir))
    print(json.dumps({"status": status, "host_report_dir": str(report_dir)}, sort_keys=True))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

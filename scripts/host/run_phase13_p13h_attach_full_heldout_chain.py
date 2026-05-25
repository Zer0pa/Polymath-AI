#!/usr/bin/env python3
"""Attach a post-training full-heldout P13-H evaluation chain to the phone."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE13_ROOT = REPO_ROOT / "runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous"
ACTIVE_RUN = PHASE13_ROOT / "active_phase13_run.json"

DEFAULT_SERIAL = "FY25013101C8"
DEFAULT_PHONE_ROOT = "/data/local/tmp/polymath_gemma4_gate"
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
LEARNING_RATE = 0.0
ADAPTER_RANK = 16
GATE_DIR_NAME = "P13-H-overnight-phone-local-long-run"
OBJECTIVE_NAME = "label_contrastive_topk_kl_v1"
OBJECTIVE_CONTRACT = "p13c_label_onehot_topk_over_phone_native_corpus_labels_no_runtime_teacher_service"
TEACHER_PROVENANCE = "phone_native_p13c_labels_to_host_deterministic_onehot_topk_precompute"
ATTACH_DIR_NAME = "full_heldout_chain"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def run_command(command: list[str], *, check: bool = False, timeout: int = 600) -> subprocess.CompletedProcess[str]:
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


def adb(serial: str, args: list[str], *, check: bool = False, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return run_command(["adb", "-s", serial, *args], check=check, timeout=timeout)


def adb_shell(serial: str, command: str, *, check: bool = False, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return adb(serial, ["shell", command], check=check, timeout=timeout)


def adb_push(serial: str, local: Path, remote: str, *, timeout: int = 600) -> None:
    adb(serial, ["push", str(local), remote], check=True, timeout=timeout)


def phone_path(phone_root: str, relative_or_absolute: str) -> str:
    if relative_or_absolute.startswith("/"):
        return relative_or_absolute
    return f"{phone_root.rstrip('/')}/{relative_or_absolute.strip('/')}"


def command_log_entry(name: str, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "name": name,
        "returncode": result.returncode,
        "stdout_first_4096": result.stdout[:4096],
        "stderr_first_4096": result.stderr[:4096],
    }


def queue_config(
    *,
    run_id: str,
    arm: str,
    token_caches: list[str],
    teacher_shards: list[str],
    checkpoint: str,
    phone_root: str,
) -> dict[str, Any]:
    iteration_count = len(token_caches)
    return {
        "schema_version": "phase13_p13h_phone_full_heldout_eval_arm_config_v1",
        "run_id": f"{run_id}_{arm}",
        "gate_name": "P13-H-full-heldout-eval",
        "gate_dir_name": GATE_DIR_NAME,
        "objective": "topk_embedding_kl",
        "objective_contract": OBJECTIVE_CONTRACT,
        "token_caches": token_caches,
        "teacher_shards": teacher_shards,
        "asset_dir": phone_path(phone_root, DEFAULT_ASSET_DIR),
        "layer0_pack": phone_path(phone_root, DEFAULT_LAYER0_PACK),
        "layer1_pack": phone_path(phone_root, DEFAULT_LAYER1_PACK),
        "initial_checkpoint": checkpoint,
        "iteration_count": iteration_count,
        "sample_every": iteration_count + 1,
        "learning_rate": LEARNING_RATE,
        "adapter_rank": ADAPTER_RANK,
        "apply_update": False,
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


def write_queue_pair(
    *,
    control_dir: Path,
    phone_p13h_root: str,
    run_id: str,
    arm: str,
    token_caches: list[str],
    teacher_shards: list[str],
    checkpoint: str,
    phone_root: str,
) -> dict[str, Any]:
    config_name = f"p13h_{arm}_config.json"
    queue_name = f"p13h_{arm}_queue.jsonl"
    config_path = control_dir / config_name
    queue_path = control_dir / queue_name
    config = queue_config(
        run_id=run_id,
        arm=arm,
        token_caches=token_caches,
        teacher_shards=teacher_shards,
        checkpoint=checkpoint,
        phone_root=phone_root,
    )
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
    return {
        "arm": arm,
        "run_id": f"{run_id}_{arm}",
        "queue_name": queue_name,
        "config_name": config_name,
        "local_queue": rel(queue_path),
        "local_config": rel(config_path),
        "state_path": f"{phone_p13h_root}/p13h_{arm}_state.json",
        "heartbeat_path": f"{phone_p13h_root}/p13h_{arm}_heartbeat.json",
        "stop_path": f"{phone_p13h_root}/STOP_p13h_{arm}",
        "phone_gate_dir": f"{phone_p13h_root}/runs/{run_id}_{arm}/{GATE_DIR_NAME}",
        "iterations": len(token_caches),
        "checkpoint": checkpoint,
    }


def write_chain_script(
    *,
    script_path: Path,
    phone_root: str,
    phone_p13h_root: str,
    base_run_id: str,
    attach_run_id: str,
    original_chain_state: str,
    original_chain_events: str,
    train_final_checkpoint: str,
    phone_bin: str,
    arms: dict[str, dict[str, Any]],
) -> None:
    runner = f"{phone_bin}/phase11_runner"
    layer_runner = f"{phone_bin}/gemma4_layer_runner"
    safety_log = f"{phone_p13h_root}/p13h_{attach_run_id}_safety.jsonl"
    lines = [
        "#!/system/bin/sh",
        "set -u",
        f"ROOT={q(phone_p13h_root)}",
        f"BASE_RUN_ID={q(base_run_id)}",
        f"RUN_ID={q(attach_run_id)}",
        f"RUNNER={q(runner)}",
        f"LAYER_RUNNER={q(layer_runner)}",
        f"ORIGINAL_STATE={q(original_chain_state)}",
        f"ORIGINAL_EVENTS={q(original_chain_events)}",
        f"TRAIN_FINAL_MANIFEST={q(train_final_checkpoint + '/manifest.json')}",
        f"SAFETY_LOG={q(safety_log)}",
        'LOG="$ROOT/p13h_${RUN_ID}_full_heldout_chain.log"',
        'EVENTS="$ROOT/p13h_${RUN_ID}_full_heldout_chain_events.jsonl"',
        'STATE="$ROOT/p13h_${RUN_ID}_full_heldout_chain_state.json"',
        'STOP="$ROOT/STOP_p13h_full_heldout_chain_${RUN_ID}"',
        'BOOTSTRAP="$ROOT/p13h_${RUN_ID}_full_heldout_chain.bootstrap.log"',
        'write_state() { printf \'{"schema_version":"phase13_p13h_full_heldout_chain_state_v1","run_id":"%s","status":"%s","step":"%s","updated_at_epoch":%s}\\n\' "$RUN_ID" "$1" "$2" "$(date +%s)" > "$STATE"; }',
        'write_event() { printf \'{"schema_version":"phase13_p13h_full_heldout_chain_event_v1","step":"%s","status":"%s","returncode":%s,"updated_at_epoch":%s}\\n\' "$1" "$2" "$3" "$(date +%s)" >> "$EVENTS"; }',
        'thermal_monitor() { while true; do TS="$(date +%s)"; BAT="$(dumpsys battery 2>/dev/null | awk \'/temperature:/ {print $2; exit}\')"; MAX=0; MAXTYPE=unknown; for z in /sys/class/thermal/thermal_zone*; do [ -r "$z/temp" ] || continue; T="$(cat "$z/temp" 2>/dev/null)"; Y="$(cat "$z/type" 2>/dev/null)"; case "$T" in -*) continue;; ""|*[!0-9]*) continue;; esac; if [ "$T" -gt "$MAX" ]; then MAX="$T"; MAXTYPE="$Y"; fi; done; printf \'{"ts":%s,"battery_tenth_c":"%s","max_zone_millideg_c":%s,"max_zone_type":"%s"}\\n\' "$TS" "$BAT" "$MAX" "$MAXTYPE" >> "$SAFETY_LOG"; if [ -n "$BAT" ] && [ "$BAT" -ge 460 ]; then touch "$STOP" "$ROOT"/STOP_p13h_full_*; exit 0; fi; if [ "$MAX" -ge 92000 ]; then touch "$STOP" "$ROOT"/STOP_p13h_full_*; exit 0; fi; sleep 30; done; }',
        'wait_for_training() { write_state waiting original_train_completion; while true; do if [ -f "$STOP" ]; then write_state stopped wait_for_training; write_event wait_for_training stopped 130; exit 130; fi; if [ -f "$TRAIN_FINAL_MANIFEST" ]; then if grep -q \'"status":"completed"\' "$ORIGINAL_STATE" 2>/dev/null; then write_event wait_for_training pass 0; return 0; fi; if grep -q \'"status":"failed"\' "$ORIGINAL_STATE" 2>/dev/null; then write_event wait_for_training original_failed_after_checkpoint 0; return 0; fi; fi; if grep -q \'"status":"failed"\' "$ORIGINAL_STATE" 2>/dev/null && [ ! -f "$TRAIN_FINAL_MANIFEST" ]; then write_state failed original_failed_before_train_checkpoint; write_event wait_for_training failed 1; exit 1; fi; if grep -q \'"status":"stopped"\' "$ORIGINAL_STATE" 2>/dev/null; then write_state stopped original_stopped; write_event wait_for_training stopped 130; exit 130; fi; sleep 300; done; }',
        'run_step() { STEP="$1"; shift; if [ -f "$STOP" ]; then write_state stopped "$STEP"; write_event "$STEP" stopped 130; exit 130; fi; write_state running "$STEP"; "$@" >> "$LOG" 2>&1; RC="$?"; if [ "$RC" -eq 0 ]; then STATUS=pass; else STATUS=fail; fi; write_event "$STEP" "$STATUS" "$RC"; if [ "$RC" -ne 0 ]; then write_state failed "$STEP"; exit "$RC"; fi; }',
        'rm -f "$EVENTS" "$LOG" "$STATE" "$BOOTSTRAP" "$SAFETY_LOG" "$STOP"',
        'rm -f "$ROOT"/STOP_p13h_heldout_full_baseline "$ROOT"/STOP_p13h_heldout_full_trained',
        "thermal_monitor & MONITOR_PID=$!",
        "wait_for_training",
        "run_step post_train_g1_layer0_opencl_smoke \"$LAYER_RUNNER\" --run-opencl "
        f"{q(phone_path(phone_root, DEFAULT_LAYER0_PACK))} "
        "\"$ROOT/preflight/full_heldout_g1_layer0_opencl_smoke\"",
        "run_step post_train_g3_two_layer_opencl_stack_smoke \"$LAYER_RUNNER\" --run-opencl-stack "
        f"{q(phone_path(phone_root, DEFAULT_LAYER0_PACK))} "
        f"{q(phone_path(phone_root, DEFAULT_LAYER1_PACK))} "
        "\"$ROOT/preflight/full_heldout_g3_two_layer_opencl_stack_smoke\"",
    ]
    for arm in ("heldout_full_baseline", "heldout_full_trained"):
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


def launch_chain(serial: str, phone_p13h_root: str, chain_script: Path, attach_run_id: str) -> dict[str, Any]:
    remote_script = f"{phone_p13h_root}/{chain_script.name}"
    adb_push(serial, chain_script, remote_script)
    adb_shell(serial, f"chmod 755 {q(remote_script)}", check=True)
    pid_path = f"{phone_p13h_root}/p13h_{attach_run_id}_full_heldout_chain.pid"
    bootstrap = f"{phone_p13h_root}/p13h_{attach_run_id}_full_heldout_chain.bootstrap.log"
    launch = adb_shell(
        serial,
        f"cd {q(phone_p13h_root)}; rm -f {q(pid_path)} {q(bootstrap)}; "
        f"(nohup sh {q(remote_script)} > {q(bootstrap)} 2>&1 < /dev/null & echo $! > {q(pid_path)})",
        check=False,
    )
    pid_read = adb_shell(serial, f"cat {q(pid_path)} 2>/dev/null || true", check=False)
    return {
        "schema_version": "phase13_p13h_full_heldout_detached_launch_v1",
        "status": "launched" if launch.returncode == 0 and pid_read.stdout.strip() else "launch_failed",
        "phone_chain_script": remote_script,
        "phone_chain_pid_path": pid_path,
        "phone_chain_pid": pid_read.stdout.strip(),
        "phone_chain_state": f"{phone_p13h_root}/p13h_{attach_run_id}_full_heldout_chain_state.json",
        "phone_chain_events": f"{phone_p13h_root}/p13h_{attach_run_id}_full_heldout_chain_events.jsonl",
        "phone_chain_log": f"{phone_p13h_root}/p13h_{attach_run_id}_full_heldout_chain.log",
        "phone_chain_bootstrap": bootstrap,
        "launch_returncode": launch.returncode,
        "launch_stdout": launch.stdout,
        "launch_stderr": launch.stderr,
    }


def update_artifact_manifest(report_dir: Path) -> None:
    entries: list[dict[str, Any]] = []
    for path in sorted(report_dir.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            entries.append({"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_json(
        report_dir / "artifact_manifest.json",
        {
            "schema_version": "phase13_p13h_artifact_manifest_v2",
            "created_at_utc": utc_now(),
            "artifacts": entries,
        },
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", default=DEFAULT_SERIAL)
    parser.add_argument("--phone-root", default=DEFAULT_PHONE_ROOT)
    args = parser.parse_args()

    run_root = active_run_root()
    report_dir = run_root / GATE_DIR_NAME
    detached = load_json(report_dir / "detached_launch.json")
    gate = load_json(report_dir / "gate_result.json")
    package = load_json(report_dir / "shard_package_manifest.json")
    binary = load_json(report_dir / "binary_deploy_manifest.json")
    base_run_id = detached["run_id"]
    attach_run_id = f"{base_run_id}_fullheldout"
    phone_p13h_root = detached["phone_p13h_root"]
    train_final_checkpoint = detached["arms"]["train"]["final_checkpoint"]
    heldout_tokens = package["heldout"]["token_shards_phone"]
    heldout_teachers = package["heldout"]["teacher_shards_phone"]
    if len(heldout_tokens) != len(heldout_teachers):
        raise RuntimeError("heldout token/teacher shard count mismatch")
    if len(heldout_tokens) < 128:
        raise RuntimeError(f"full heldout evaluation requires 128 shards; found {len(heldout_tokens)}")

    attach_dir = report_dir / ATTACH_DIR_NAME
    control_dir = attach_dir / "control"
    control_dir.mkdir(parents=True, exist_ok=True)
    commands: list[dict[str, Any]] = []
    arms = {
        "heldout_full_baseline": write_queue_pair(
            control_dir=control_dir,
            phone_p13h_root=phone_p13h_root,
            run_id=attach_run_id,
            arm="heldout_full_baseline",
            token_caches=heldout_tokens,
            teacher_shards=heldout_teachers,
            checkpoint=PHASE12_LR3E4_FINAL_CHECKPOINT,
            phone_root=args.phone_root,
        ),
        "heldout_full_trained": write_queue_pair(
            control_dir=control_dir,
            phone_p13h_root=phone_p13h_root,
            run_id=attach_run_id,
            arm="heldout_full_trained",
            token_caches=heldout_tokens,
            teacher_shards=heldout_teachers,
            checkpoint=train_final_checkpoint,
            phone_root=args.phone_root,
        ),
    }

    remote_queue_dir = f"{phone_p13h_root}/queue"
    prep = adb_shell(args.serial, f"mkdir -p {q(remote_queue_dir)}", check=False)
    commands.append(command_log_entry("phone_prepare_queue_dir", prep))
    for arm in arms.values():
        local_queue = REPO_ROOT / arm["local_queue"]
        local_config = REPO_ROOT / arm["local_config"]
        adb_push(args.serial, local_queue, f"{remote_queue_dir}/{local_queue.name}")
        adb_push(args.serial, local_config, f"{remote_queue_dir}/{local_config.name}")

    chain_script = attach_dir / f"p13h_{attach_run_id}_full_heldout_chain.sh"
    write_chain_script(
        script_path=chain_script,
        phone_root=args.phone_root,
        phone_p13h_root=phone_p13h_root,
        base_run_id=base_run_id,
        attach_run_id=attach_run_id,
        original_chain_state=detached["launch"]["phone_chain_state"],
        original_chain_events=detached["launch"]["phone_chain_events"],
        train_final_checkpoint=train_final_checkpoint,
        phone_bin=binary["phone_bin"],
        arms=arms,
    )
    launch = launch_chain(args.serial, phone_p13h_root, chain_script, attach_run_id)
    attached = {
        "schema_version": "phase13_p13h_full_heldout_attachment_v1",
        "created_at_utc": utc_now(),
        "base_run_id": base_run_id,
        "attach_run_id": attach_run_id,
        "status": launch["status"],
        "objective": OBJECTIVE_NAME,
        "objective_contract": OBJECTIVE_CONTRACT,
        "heldout_shard_count": len(heldout_tokens),
        "train_final_checkpoint": train_final_checkpoint,
        "arms": arms,
        "launch": launch,
        "commands": commands,
    }
    write_json(attach_dir / "attach_manifest.json", attached)
    detached["full_heldout_attachment"] = rel(attach_dir / "attach_manifest.json")
    detached["full_heldout_attachment_status"] = launch["status"]
    write_json(report_dir / "detached_launch.json", detached)
    gate["full_heldout_attachment"] = rel(attach_dir / "attach_manifest.json")
    gate["full_heldout_attachment_status"] = launch["status"]
    gate["acceptance_heldout_scope"] = "128 heldout shards x 8 sequences, evaluated baseline and trained checkpoints after the 5000-update phone-local train chain"
    gate.setdefault("nonclaims", [])
    missing = "P13-H is not promotable until the full-heldout attachment completes and improves versus baseline."
    if missing not in gate["nonclaims"]:
        gate["nonclaims"].append(missing)
    write_json(report_dir / "gate_result.json", gate)
    update_artifact_manifest(report_dir)
    print(
        json.dumps(
            {
                "status": launch["status"],
                "attach_manifest": rel(attach_dir / "attach_manifest.json"),
                "pid": launch.get("phone_chain_pid"),
                "heldout_shards": len(heldout_tokens),
            },
            sort_keys=True,
        )
    )
    return 0 if launch["status"] == "launched" else 1


if __name__ == "__main__":
    raise SystemExit(main())

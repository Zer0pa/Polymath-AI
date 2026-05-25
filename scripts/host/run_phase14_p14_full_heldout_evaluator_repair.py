#!/usr/bin/env python3
"""Prepare and validate the Phase 14 full-heldout evaluator path.

This script repairs the P13-H evaluator coupling that made full-heldout eval wait
for a specific 5000-update train-final checkpoint. It creates a reusable
baseline/candidate full-heldout eval plan that is independent of any train chain.
Launching is opt-in and still eval-only: both arms force apply_update=false.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import shlex
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE13_ROOT = REPO_ROOT / "runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous"
PHASE14_ROOT = REPO_ROOT / "runtime/reports/gemma4_megakernel/phase14_drift_cleanup"
ACTIVE_PHASE13_RUN = PHASE13_ROOT / "active_phase13_run.json"

DEFAULT_SERIAL = "FY25013101C8"
DEFAULT_PHONE_ROOT = "/data/local/tmp/polymath_gemma4_gate"
DEFAULT_PHONE_EVAL_ROOT = "/data/local/tmp/polymath_gemma4_gate/phase14/p14_full_heldout_eval"
DEFAULT_ASSET_DIR = "streamed_assets/g8_layer01_20260517T071405Z"
DEFAULT_LAYER0_PACK = "layer_pack/gemma4_e4b_layer0_seq128_v0"
DEFAULT_LAYER1_PACK = "layer_pack/gemma4_e4b_layer1_seq128_v0"
PHASE12_LR3E4_FINAL_CHECKPOINT = (
    "/data/local/tmp/polymath_gemma4_gate/phase12/runs/"
    "20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_train/"
    "Phase12-long-native-lr/iterations/iter_000023/checkpoint"
)
P13H_PARTIAL_TRAINED_CHECKPOINT = (
    "/data/local/tmp/polymath_gemma4_gate/phase13/"
    "20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h/runs/"
    "20260524T210920Z_phase13_gemma4_only_heterogeneous_p13h_20260524T232423Z_train/"
    "P13-H-overnight-phone-local-long-run/iterations/iter_001741/checkpoint"
)

P14_GATE_DIR_NAME = "P14-4-full-heldout-evaluator-repair"
MODEL_ID = "google/gemma-4-E4B"
MODEL_REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
HIDDEN = 2560
ADAPTER_RANK = 16
OBJECTIVE_NAME = "label_contrastive_topk_kl_v1"
OBJECTIVE_CONTRACT = "p13c_label_onehot_topk_over_phone_native_corpus_labels_no_runtime_teacher_service"
TEACHER_PROVENANCE = "phone_native_p13c_labels_to_host_deterministic_onehot_topk_precompute"


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


def command_log_entry(name: str, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "name": name,
        "returncode": result.returncode,
        "stdout_first_4096": result.stdout[:4096],
        "stderr_first_4096": result.stderr[:4096],
    }


def latest_phase14_run_root() -> Path:
    roots = sorted(path for path in PHASE14_ROOT.iterdir() if path.is_dir())
    if not roots:
        raise RuntimeError(f"no Phase 14 report roots found under {PHASE14_ROOT}")
    return roots[-1]


def default_shard_package() -> Path:
    active = load_json(ACTIVE_PHASE13_RUN)
    run_root = REPO_ROOT / active["run_root"]
    return run_root / "P13-H-overnight-phone-local-long-run/shard_package_manifest.json"


def default_fixture_arm_dir() -> Path:
    active = load_json(ACTIVE_PHASE13_RUN)
    run_root = REPO_ROOT / active["run_root"]
    return run_root / "P13-H-overnight-phone-local-long-run/collection/arms/baseline_eval"


def phone_path(phone_root: str, relative_or_absolute: str) -> str:
    if relative_or_absolute.startswith("/"):
        return relative_or_absolute
    return f"{phone_root.rstrip('/')}/{relative_or_absolute.strip('/')}"


def source_commit() -> str:
    return run_command(["git", "rev-parse", "HEAD"], check=True).stdout.strip()


def require_shards(package: dict[str, Any], shard_count: int) -> tuple[list[str], list[str]]:
    heldout = package.get("heldout", {})
    tokens = list(heldout.get("token_shards_phone", []))
    teachers = list(heldout.get("teacher_shards_phone", []))
    if len(tokens) != len(teachers):
        raise RuntimeError(f"heldout token/teacher shard count mismatch: {len(tokens)} != {len(teachers)}")
    if len(tokens) < shard_count:
        raise RuntimeError(f"requested {shard_count} heldout shards, found {len(tokens)}")
    return tokens[:shard_count], teachers[:shard_count]


def build_eval_config(
    *,
    run_id: str,
    arm: str,
    token_caches: list[str],
    teacher_shards: list[str],
    checkpoint: str,
    phone_root: str,
) -> dict[str, Any]:
    shard_count = len(token_caches)
    return {
        "schema_version": "phase14_full_heldout_eval_arm_config_v1",
        "run_id": f"{run_id}_{arm}",
        "gate_name": "P14-4-full-heldout-eval",
        "gate_dir_name": P14_GATE_DIR_NAME,
        "objective": "topk_embedding_kl",
        "objective_contract": OBJECTIVE_CONTRACT,
        "token_caches": token_caches,
        "teacher_shards": teacher_shards,
        "asset_dir": phone_path(phone_root, DEFAULT_ASSET_DIR),
        "layer0_pack": phone_path(phone_root, DEFAULT_LAYER0_PACK),
        "layer1_pack": phone_path(phone_root, DEFAULT_LAYER1_PACK),
        "initial_checkpoint": checkpoint,
        "iteration_count": shard_count,
        "sample_every": shard_count + 1,
        "learning_rate": 0.0,
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
        "source_commit": source_commit(),
        "kernel_lineage_class": "residual_adapter_opencl_training",
        "runtime_backend": "phone_cpu_token_to_hidden_plus_opencl_layers_and_adapter",
        "teacher_provenance": TEACHER_PROVENANCE,
        "hidden_state_fixtures_consumed": False,
    }


def write_arm_files(
    *,
    control_dir: Path,
    phone_eval_root: str,
    run_id: str,
    arm: str,
    token_caches: list[str],
    teacher_shards: list[str],
    checkpoint: str,
    phone_root: str,
) -> dict[str, Any]:
    config_name = f"p14_{arm}_config.json"
    queue_name = f"p14_{arm}_queue.jsonl"
    config_path = control_dir / config_name
    queue_path = control_dir / queue_name
    config = build_eval_config(
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
                "id": f"p14_{arm}",
                "gate": "P14-4",
                "config": f"{phone_eval_root}/queue/{config_name}",
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
        "state_path": f"{phone_eval_root}/p14_{arm}_state.json",
        "heartbeat_path": f"{phone_eval_root}/p14_{arm}_heartbeat.json",
        "stop_path": f"{phone_eval_root}/STOP_p14_{arm}",
        "phone_gate_dir": f"{phone_eval_root}/runs/{run_id}_{arm}/{P14_GATE_DIR_NAME}",
        "iterations": len(token_caches),
        "checkpoint": checkpoint,
        "apply_update": False,
    }


def write_chain_script(
    *,
    script_path: Path,
    phone_eval_root: str,
    run_id: str,
    phone_bin: str,
    arms: dict[str, dict[str, Any]],
) -> None:
    runner = f"{phone_bin}/phase11_runner"
    safety_log = f"{phone_eval_root}/p14_{run_id}_safety.jsonl"
    lines = [
        "#!/system/bin/sh",
        "set -u",
        f"ROOT={q(phone_eval_root)}",
        f"RUN_ID={q(run_id)}",
        f"RUNNER={q(runner)}",
        f"SAFETY_LOG={q(safety_log)}",
        'LOG="$ROOT/p14_${RUN_ID}_full_heldout_eval.log"',
        'EVENTS="$ROOT/p14_${RUN_ID}_full_heldout_eval_events.jsonl"',
        'STATE="$ROOT/p14_${RUN_ID}_full_heldout_eval_state.json"',
        'STOP="$ROOT/STOP_p14_full_heldout_eval_${RUN_ID}"',
        'BOOTSTRAP="$ROOT/p14_${RUN_ID}_full_heldout_eval.bootstrap.log"',
        'write_state() { printf \'{"schema_version":"phase14_full_heldout_eval_state_v1","run_id":"%s","status":"%s","step":"%s","updated_at_epoch":%s}\\n\' "$RUN_ID" "$1" "$2" "$(date +%s)" > "$STATE"; }',
        'write_event() { printf \'{"schema_version":"phase14_full_heldout_eval_event_v1","step":"%s","status":"%s","returncode":%s,"updated_at_epoch":%s}\\n\' "$1" "$2" "$3" "$(date +%s)" >> "$EVENTS"; }',
        'thermal_monitor() { while true; do TS="$(date +%s)"; BAT="$(dumpsys battery 2>/dev/null | awk \'/temperature:/ {print $2; exit}\')"; MAX=0; MAXTYPE=unknown; for z in /sys/class/thermal/thermal_zone*; do [ -r "$z/temp" ] || continue; T="$(cat "$z/temp" 2>/dev/null)"; Y="$(cat "$z/type" 2>/dev/null)"; case "$T" in -*) continue;; ""|*[!0-9]*) continue;; esac; if [ "$T" -gt "$MAX" ]; then MAX="$T"; MAXTYPE="$Y"; fi; done; printf \'{"ts":%s,"battery_tenth_c":"%s","max_zone_millideg_c":%s,"max_zone_type":"%s"}\\n\' "$TS" "$BAT" "$MAX" "$MAXTYPE" >> "$SAFETY_LOG"; if [ -n "$BAT" ] && [ "$BAT" -ge 380 ]; then touch "$STOP" "$ROOT"/STOP_p14_*; exit 0; fi; if [ "$MAX" -ge 85000 ]; then touch "$STOP" "$ROOT"/STOP_p14_*; exit 0; fi; sleep 30; done; }',
        'require_checkpoint() { if [ ! -f "$1/manifest.json" ]; then write_state failed "missing_checkpoint_$2"; write_event "missing_checkpoint_$2" fail 2; exit 2; fi; }',
        'run_step() { STEP="$1"; shift; if [ -f "$STOP" ]; then write_state stopped "$STEP"; write_event "$STEP" stopped 130; exit 130; fi; write_state running "$STEP"; "$@" >> "$LOG" 2>&1; RC="$?"; if [ "$RC" -eq 0 ]; then STATUS=pass; else STATUS=fail; fi; write_event "$STEP" "$STATUS" "$RC"; if [ "$RC" -ne 0 ]; then write_state failed "$STEP"; exit "$RC"; fi; }',
        'rm -f "$EVENTS" "$LOG" "$STATE" "$BOOTSTRAP" "$SAFETY_LOG" "$STOP"',
        'rm -f "$ROOT"/STOP_p14_baseline "$ROOT"/STOP_p14_candidate "$ROOT"/STOP_p14_*',
        'mkdir -p "$ROOT/runs"',
    ]
    for arm in ("baseline", "candidate"):
        lines.append(f"require_checkpoint {q(arms[arm]['checkpoint'])} {q(arm)}")
    lines.extend(["thermal_monitor & MONITOR_PID=$!"])
    for arm in ("baseline", "candidate"):
        record = arms[arm]
        lines.append(
            f"run_step {arm} sh -c "
            + q(
                f"cd {phone_eval_root}; {runner} --queue queue/{record['queue_name']} "
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


def telemetry_paths(local_arm_dir: Path) -> list[Path]:
    return sorted((local_arm_dir / "iterations").glob("iter_*/telemetry.json"))


def sorted_present_values(rows: list[dict[str, Any]], key: str) -> list[Any]:
    by_json = {
        json.dumps(row.get(key), sort_keys=True): row.get(key)
        for row in rows
        if row.get(key) is not None
    }
    return [by_json[item] for item in sorted(by_json)]


def weighted_mean(rows: list[dict[str, Any]], key: str, weight_key: str = "active_tokens") -> float | None:
    total_weight = 0.0
    total_value = 0.0
    for row in rows:
        value = row.get(key)
        weight = row.get(weight_key, 0)
        if not isinstance(value, (int, float)) or not isinstance(weight, (int, float)) or weight <= 0:
            continue
        if not math.isfinite(float(value)):
            continue
        total_weight += float(weight)
        total_value += float(value) * float(weight)
    if total_weight <= 0:
        return None
    return total_value / total_weight


def max_checkpoint_delta(rows: list[dict[str, Any]]) -> float | None:
    values: list[float] = []
    for row in rows:
        deltas = row.get("checkpoint_delta_l2")
        if not isinstance(deltas, dict):
            continue
        for value in deltas.values():
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                values.append(abs(float(value)))
    return max(values) if values else None


def aggregate_eval(local_arm_dir: Path) -> dict[str, Any]:
    rows = [load_json(path) for path in telemetry_paths(local_arm_dir)]
    gate_path = local_arm_dir / "gate_result.json"
    gate = load_json(gate_path) if gate_path.exists() else {}
    return {
        "schema_version": "phase14_full_heldout_eval_aggregate_v1",
        "iteration_count": len(rows),
        "gate_status": gate.get("status"),
        "gate_iteration_count": gate.get("iteration_count"),
        "gate_apply_update": gate.get("apply_update"),
        "active_tokens": int(sum(int(row.get("active_tokens", 0)) for row in rows)),
        "loss_topk_kl": weighted_mean(rows, "loss_topk_kl"),
        "mean_student_teacher_top1_probability": weighted_mean(rows, "mean_student_teacher_top1_probability"),
        "student_teacher_top1_agreement": weighted_mean(rows, "student_teacher_top1_agreement"),
        "mean_student_label_probability_when_in_topk": weighted_mean(rows, "mean_student_label_probability_when_in_topk"),
        "label_in_teacher_topk_rate": weighted_mean(rows, "label_in_teacher_topk_rate"),
        "objective_values": sorted_present_values(rows, "objective"),
        "teacher_provenance_values": sorted_present_values(rows, "teacher_provenance"),
        "model_ids": sorted_present_values(rows, "model_id"),
        "hidden_sizes": sorted_present_values(rows, "hidden_size"),
        "applied_update_values": sorted_present_values(rows, "applied_update"),
        "learning_rate_values": sorted_present_values(rows, "learning_rate"),
        "max_checkpoint_delta_l2": max_checkpoint_delta(rows),
        "hidden_state_fixtures_consumed_values": sorted_present_values(rows, "hidden_state_fixtures_consumed"),
        "telemetry_files": [rel(path) for path in telemetry_paths(local_arm_dir)],
    }


def validate_eval_aggregate(aggregate: dict[str, Any], expected_iterations: int) -> list[str]:
    blockers: list[str] = []
    if aggregate.get("iteration_count") != expected_iterations:
        blockers.append(f"expected {expected_iterations} telemetry rows, found {aggregate.get('iteration_count')}")
    if aggregate.get("objective_values") != [OBJECTIVE_NAME]:
        blockers.append("objective telemetry mismatch")
    if aggregate.get("teacher_provenance_values") != [TEACHER_PROVENANCE]:
        blockers.append("teacher provenance telemetry mismatch")
    if aggregate.get("model_ids") != [MODEL_ID]:
        blockers.append("model identity telemetry mismatch")
    if aggregate.get("hidden_sizes") != [HIDDEN]:
        blockers.append("hidden-size telemetry mismatch")
    if aggregate.get("applied_update_values") != [False]:
        blockers.append("evaluator telemetry must have applied_update=false")
    if aggregate.get("learning_rate_values") not in ([0], [0.0]):
        blockers.append("evaluator telemetry must have learning_rate=0")
    max_delta = aggregate.get("max_checkpoint_delta_l2")
    if not isinstance(max_delta, (int, float)) or abs(float(max_delta)) > 1.0e-12:
        blockers.append("evaluator changed checkpoint tensors")
    if aggregate.get("hidden_state_fixtures_consumed_values") not in ([[]], []):
        blockers.append("evaluator consumed hidden-state fixtures")
    return blockers


def validate_pair(
    baseline_dir: Path,
    candidate_dir: Path,
    expected_iterations: int,
    require_improvement: bool,
) -> dict[str, Any]:
    baseline = aggregate_eval(baseline_dir)
    candidate = aggregate_eval(candidate_dir)
    blockers = []
    blockers.extend(f"baseline: {item}" for item in validate_eval_aggregate(baseline, expected_iterations))
    blockers.extend(f"candidate: {item}" for item in validate_eval_aggregate(candidate, expected_iterations))
    base_loss = baseline.get("loss_topk_kl")
    cand_loss = candidate.get("loss_topk_kl")
    loss_delta = None if base_loss is None or cand_loss is None else float(base_loss) - float(cand_loss)
    if require_improvement and not (isinstance(loss_delta, float) and loss_delta > 0):
        blockers.append("candidate did not improve heldout KL versus baseline")
    return {
        "schema_version": "phase14_full_heldout_eval_pair_validation_v1",
        "status": "pass" if not blockers else "fail",
        "expected_iterations": expected_iterations,
        "require_improvement": require_improvement,
        "baseline": baseline,
        "candidate": candidate,
        "deltas": {"loss_topk_kl": loss_delta},
        "blockers": blockers,
    }


def verify_phone_checkpoints(serial: str, checkpoints: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    commands: list[dict[str, Any]] = []
    results: dict[str, Any] = {"schema_version": "phase14_phone_checkpoint_probe_v1", "checkpoints": {}}
    for name, checkpoint in checkpoints.items():
        result = adb_shell(serial, f"test -f {q(checkpoint + '/manifest.json')}", check=False)
        commands.append(command_log_entry(f"phone_checkpoint_exists_{name}", result))
        results["checkpoints"][name] = {
            "checkpoint": checkpoint,
            "manifest_exists": result.returncode == 0,
        }
    results["status"] = "pass" if all(item["manifest_exists"] for item in results["checkpoints"].values()) else "fail"
    return results, commands


def write_artifact_manifest(report_dir: Path) -> None:
    entries: list[dict[str, Any]] = []
    for path in sorted(report_dir.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            entries.append({"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_json(
        report_dir / "artifact_manifest.json",
        {
            "schema_version": "phase14_p14_4_artifact_manifest_v1",
            "created_at_utc": utc_now(),
            "artifacts": entries,
        },
    )


def launch_eval_chain(
    *,
    serial: str,
    phone_eval_root: str,
    chain_script: Path,
    run_id: str,
    arms: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    remote_queue_dir = f"{phone_eval_root}/queue"
    adb_shell(serial, f"mkdir -p {q(remote_queue_dir)}", check=True)
    for arm in arms.values():
        adb_push(serial, REPO_ROOT / arm["local_queue"], f"{remote_queue_dir}/{arm['queue_name']}")
        adb_push(serial, REPO_ROOT / arm["local_config"], f"{remote_queue_dir}/{arm['config_name']}")
    remote_script = f"{phone_eval_root}/{chain_script.name}"
    adb_push(serial, chain_script, remote_script)
    adb_shell(serial, f"chmod 755 {q(remote_script)}", check=True)
    pid_path = f"{phone_eval_root}/p14_{run_id}_full_heldout_eval.pid"
    bootstrap = f"{phone_eval_root}/p14_{run_id}_full_heldout_eval.bootstrap.log"
    launch = adb_shell(
        serial,
        f"cd {q(phone_eval_root)}; rm -f {q(pid_path)} {q(bootstrap)}; "
        f"(nohup sh {q(remote_script)} > {q(bootstrap)} 2>&1 < /dev/null & echo $! > {q(pid_path)})",
        check=False,
    )
    pid_read = adb_shell(serial, f"cat {q(pid_path)} 2>/dev/null || true", check=False)
    return {
        "schema_version": "phase14_full_heldout_eval_detached_launch_v1",
        "status": "launched" if launch.returncode == 0 and pid_read.stdout.strip() else "launch_failed",
        "phone_chain_script": remote_script,
        "phone_chain_pid_path": pid_path,
        "phone_chain_pid": pid_read.stdout.strip(),
        "phone_chain_state": f"{phone_eval_root}/p14_{run_id}_full_heldout_eval_state.json",
        "phone_chain_events": f"{phone_eval_root}/p14_{run_id}_full_heldout_eval_events.jsonl",
        "phone_chain_log": f"{phone_eval_root}/p14_{run_id}_full_heldout_eval.log",
        "phone_chain_bootstrap": bootstrap,
        "launch_returncode": launch.returncode,
        "launch_stdout": launch.stdout,
        "launch_stderr": launch.stderr,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", default=DEFAULT_SERIAL)
    parser.add_argument("--phone-root", default=DEFAULT_PHONE_ROOT)
    parser.add_argument("--phone-eval-root", default=DEFAULT_PHONE_EVAL_ROOT)
    parser.add_argument("--report-dir", type=Path, default=None)
    parser.add_argument("--shard-package", type=Path, default=None)
    parser.add_argument("--shards", type=int, default=128)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--baseline-checkpoint", default=PHASE12_LR3E4_FINAL_CHECKPOINT)
    parser.add_argument("--candidate-checkpoint", default=P13H_PARTIAL_TRAINED_CHECKPOINT)
    parser.add_argument("--phone-bin", default=f"{DEFAULT_PHONE_ROOT}/bin")
    parser.add_argument("--fixture-baseline-dir", type=Path, default=None)
    parser.add_argument("--fixture-candidate-dir", type=Path, default=None)
    parser.add_argument("--fixture-iterations", type=int, default=1)
    parser.add_argument("--require-fixture-improvement", action="store_true")
    parser.add_argument("--verify-phone-checkpoints", action="store_true")
    parser.add_argument("--launch", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_dir = args.report_dir or (latest_phase14_run_root() / P14_GATE_DIR_NAME)
    control_dir = report_dir / "control"
    control_dir.mkdir(parents=True, exist_ok=True)

    run_id = args.run_id or f"p14_full_heldout_eval_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    shard_package = args.shard_package or default_shard_package()
    package = load_json(shard_package)
    tokens, teachers = require_shards(package, args.shards)
    arms = {
        "baseline": write_arm_files(
            control_dir=control_dir,
            phone_eval_root=args.phone_eval_root,
            run_id=run_id,
            arm="baseline",
            token_caches=tokens,
            teacher_shards=teachers,
            checkpoint=args.baseline_checkpoint,
            phone_root=args.phone_root,
        ),
        "candidate": write_arm_files(
            control_dir=control_dir,
            phone_eval_root=args.phone_eval_root,
            run_id=run_id,
            arm="candidate",
            token_caches=tokens,
            teacher_shards=teachers,
            checkpoint=args.candidate_checkpoint,
            phone_root=args.phone_root,
        ),
    }

    chain_script = report_dir / f"{run_id}_eval_chain.sh"
    write_chain_script(
        script_path=chain_script,
        phone_eval_root=args.phone_eval_root,
        run_id=run_id,
        phone_bin=args.phone_bin,
        arms=arms,
    )

    commands: list[dict[str, Any]] = []
    checkpoint_probe = {"schema_version": "phase14_phone_checkpoint_probe_v1", "status": "not_requested"}
    if args.verify_phone_checkpoints:
        checkpoint_probe, checkpoint_commands = verify_phone_checkpoints(
            args.serial,
            {"baseline": args.baseline_checkpoint, "candidate": args.candidate_checkpoint},
        )
        commands.extend(checkpoint_commands)

    fixture_baseline = args.fixture_baseline_dir or default_fixture_arm_dir()
    fixture_candidate = args.fixture_candidate_dir or fixture_baseline
    fixture_validation = validate_pair(
        fixture_baseline,
        fixture_candidate,
        expected_iterations=args.fixture_iterations,
        require_improvement=args.require_fixture_improvement,
    )

    launch = {"schema_version": "phase14_full_heldout_eval_detached_launch_v1", "status": "not_launched"}
    if args.launch:
        if checkpoint_probe.get("status") == "fail":
            raise RuntimeError("refusing launch because checkpoint verification failed")
        launch = launch_eval_chain(
            serial=args.serial,
            phone_eval_root=args.phone_eval_root,
            chain_script=chain_script,
            run_id=run_id,
            arms=arms,
        )

    blockers: list[str] = []
    if fixture_validation["status"] != "pass":
        blockers.extend(f"fixture: {item}" for item in fixture_validation["blockers"])
    if args.verify_phone_checkpoints and checkpoint_probe["status"] != "pass":
        blockers.append("phone checkpoint probe failed")
    if args.launch and launch["status"] != "launched":
        blockers.append("eval launch failed")

    repair_plan = {
        "schema_version": "phase14_p14_4_full_heldout_eval_repair_plan_v1",
        "created_at_utc": utc_now(),
        "run_id": run_id,
        "shard_package_manifest": rel(shard_package),
        "heldout_shards_planned": args.shards,
        "phone_eval_root": args.phone_eval_root,
        "arms": arms,
        "chain_script": rel(chain_script),
        "train_chain_dependency_removed": True,
        "requires_candidate_checkpoint_manifest_before_launch": True,
        "all_eval_arms_apply_update_false": all(not arm["apply_update"] for arm in arms.values()),
    }
    gate = {
        "schema_version": "phase14_p14_4_full_heldout_evaluator_repair_v1",
        "gate": "P14-4 full-heldout evaluator repair",
        "status": "pass_evaluator_repaired_no_training_launched" if not blockers else "fail",
        "created_at_utc": utc_now(),
        "training_launched": False,
        "eval_launch_requested": bool(args.launch),
        "eval_launch": launch,
        "repair_plan": repair_plan,
        "checkpoint_probe": checkpoint_probe,
        "fixture_validation": fixture_validation,
        "blockers": blockers,
        "nonclaims": [
            "P14-4 does not promote P13-H or any heldout improvement.",
            "P14-4 does not launch training.",
            "P14-4 does not replace full-heldout movement with train-loss movement.",
            "P14-4 only repairs the eval control path and validates real telemetry aggregation on existing eval artifacts.",
        ],
        "next_gate": "P14-5 objective repair",
    }

    write_json(report_dir / "repair_plan.json", repair_plan)
    write_json(report_dir / "checkpoint_probe.json", checkpoint_probe)
    write_json(report_dir / "fixture_validation.json", fixture_validation)
    write_json(report_dir / "gate_result.json", gate)
    write_text(
        report_dir / "blockers.md",
        "# P14-4 Blockers\n\n"
        + ("No P14-4 blocker remains.\n" if not blockers else "\n".join(f"- {item}" for item in blockers) + "\n"),
    )
    write_text(
        report_dir / "falsifier_report.md",
        "# P14-4 Falsifier Report\n\n"
        "- Full heldout queues cover the requested heldout shard count for both baseline and candidate arms.\n"
        "- Both evaluator arms force `apply_update=false`, `learning_rate=0`, and independent checkpoint inputs.\n"
        "- The launch script has no wait on a train-final manifest or original train-chain state.\n"
        "- Existing phone eval telemetry aggregates with exact objective, model, hidden-size, and teacher provenance fields.\n"
        "- Existing eval telemetry shows no applied update and zero checkpoint delta.\n",
    )
    write_text(report_dir / "commands.log", json.dumps({"commands": commands}, indent=2, sort_keys=True) + "\n")
    write_artifact_manifest(report_dir)

    print(json.dumps({"status": gate["status"], "gate_result": rel(report_dir / "gate_result.json")}, sort_keys=True))
    return 0 if gate["status"].startswith("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())

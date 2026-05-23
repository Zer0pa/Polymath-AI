#!/usr/bin/env python3
"""Run Phase 11 H11-H combined phone-native POVC gate."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.host.run_phase11_h11f_objective_upgrade import (  # noqa: E402
    DEFAULT_ASSET_DIR,
    DEFAULT_BASE_CHECKPOINT,
    DEFAULT_HELDOUT_CACHE,
    DEFAULT_LAYER0_PACK,
    DEFAULT_LAYER1_PACK,
    DEFAULT_PHASE11_RUNNER,
    DEFAULT_PHONE_ROOT,
    DEFAULT_SERIAL,
    DEFAULT_TRAIN_CACHE,
    adb,
    adb_pull,
    adb_shell,
    compact_utc_now,
    deploy_runner,
    load_json,
    phone_path,
    q,
    run_command,
    sha256_file,
    utc_now,
    write_json,
    write_text,
)


DEFAULT_LAYER_RUNNER = Path(
    "integrations/gemma4-snapdragon-megakernel/build/"
    "gemma4_megakernel_android/gemma4_layer_runner"
)
DEFAULT_FINAL_FALSIFIER = Path(
    "integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/tools/"
    "compare_outputs/final_falsifier_review.py"
)
G1_GATE = Path(
    "runtime/reports/gemma4_megakernel/parity/"
    "20260516_e4b_layer0_opencl_gate/gate_result.json"
)
G3_GATE = Path(
    "runtime/reports/gemma4_megakernel/forward_stack/"
    "20260517T032829Z_g3_two_layer_opencl/gate_result.json"
)
G8_GATE = Path(
    "runtime/reports/gemma4_megakernel/integrated_training/"
    "20260517T071405Z_g8_streamed_corpus_repaired/gate_result.json"
)
H11G_GATE = Path(
    "runtime/reports/gemma4_megakernel/hardware_native_povc/"
    "20260523T223147Z_h11g_htp_mutable_adapter/H11-G-htp-mutable-adapter/"
    "gate_result.json"
)

GATE_DIR_NAME = "H11-H-combined-povc"
OBJECTIVE = "topk_embedding_kl"
OBJECTIVE_CLAIM = "topk_embedding_kl_distillation_v1"
TRAINABLE_SCOPE = "post_layer0_rank4_residual_adapter"


def deploy_binary(*, serial: str, phone_phase11_root: str, binary: Path, remote_name: str) -> str:
    if not binary.exists():
        raise FileNotFoundError(f"required Android binary not found: {binary}")
    adb_shell(serial, f"mkdir -p {q(phone_phase11_root)}")
    remote = f"{phone_phase11_root}/{remote_name}"
    adb(serial, ["push", str(binary), remote])
    adb_shell(serial, f"chmod 755 {q(remote)}")
    return remote


def adb_pull_optional(serial: str, remote_path: str, local_path: Path) -> bool:
    return adb_pull(serial, remote_path, local_path, check=False)


def require_phone_file(serial: str, path: str, label: str) -> None:
    completed = adb_shell(serial, f"test -s {q(path)}", check=False)
    if completed.returncode != 0:
        raise FileNotFoundError(f"missing phone {label}: {path}")


def require_teacher_shard(serial: str, path: str) -> None:
    for name in (
        "manifest.json",
        "topk_token_ids.u32.bin",
        "topk_probabilities.f32.bin",
        "loss_mask.u8.bin",
        "labels.u32.bin",
    ):
        require_phone_file(serial, f"{path}/{name}", f"teacher shard file {name}")


def write_queue_and_config(
    *,
    local_dir: Path,
    phone_root: str,
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
    config = local_dir / f"h11h_{arm}_config.json"
    queue = local_dir / f"h11h_{arm}_queue.jsonl"
    config_payload = {
        "schema_version": "phase11_h11h_config_v1",
        "run_id": f"{run_id}_{arm}",
        "gate_name": "H11-H",
        "gate_dir_name": GATE_DIR_NAME,
        "objective": OBJECTIVE,
        "token_caches": [token_cache],
        "teacher_shards": [teacher_shard],
        "asset_dir": phone_path(phone_root, DEFAULT_ASSET_DIR),
        "layer0_pack": phone_path(phone_root, DEFAULT_LAYER0_PACK),
        "layer1_pack": phone_path(phone_root, DEFAULT_LAYER1_PACK),
        "initial_checkpoint": checkpoint,
        "iteration_count": iterations,
        "sample_every": max(iterations + 1, 1),
        "learning_rate": learning_rate,
        "adapter_rank": 4,
        "apply_update": apply_update,
        "require_disconnect_marker": False,
        "marker_wait_seconds": 0,
        "disconnect_hold_seconds": 0,
        "h11h_queue_record_gate_workaround": "H11-F record dispatches the shared top-k queue runner; config gate_name remains H11-H.",
    }
    write_json(config, config_payload)
    queue.write_text(
        json.dumps(
            {
                "id": f"h11h_{arm}",
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


def pull_iteration_artifacts(
    *,
    serial: str,
    gate_dir: str,
    local_report: Path,
    iterations: int,
) -> None:
    for index in range(iterations):
        remote_iter = f"{gate_dir}/iterations/iter_{index:06d}"
        local_iter = local_report / "iterations" / f"iter_{index:06d}"
        adb_pull_optional(serial, f"{remote_iter}/telemetry.json", local_iter / "telemetry.json")
        adb_pull_optional(
            serial,
            f"{remote_iter}/checkpoint/manifest.json",
            local_iter / "checkpoint_manifest.json",
        )
        adb_pull_optional(
            serial,
            f"{remote_iter}/replay_manifest.json",
            local_iter / "replay_manifest.json",
        )


def pull_gate_artifacts(
    *,
    serial: str,
    phone_phase11_root: str,
    arm_run_id: str,
    gate_dir: str,
    local_report: Path,
    state_path: str,
    heartbeat_path: str,
) -> None:
    for name in (
        "gate_result.json",
        "telemetry.jsonl",
        "timing_breakdown.json",
        "blockers.md",
        "falsifier_report.md",
        "artifact_manifest.json",
        "queue_schema.json",
        "daemon_design_note.md",
        "commands.log",
        "daemon_static_artifact_manifest.json",
        "cold_start_probe.json",
        "one_shot_baseline.json",
    ):
        adb_pull_optional(serial, f"{gate_dir}/{name}", local_report / name)
    run_dir = f"{phone_phase11_root}/runs/{arm_run_id}"
    adb_pull_optional(serial, f"{run_dir}/campaign_manifest.json", local_report / "campaign_manifest.json")
    adb_pull_optional(serial, f"{run_dir}/checksum_chain.jsonl", local_report / "checksum_chain.jsonl")
    adb_pull_optional(serial, state_path, local_report / "runner_state.json")
    adb_pull_optional(serial, heartbeat_path, local_report / "heartbeat.json")


def run_arm(
    *,
    serial: str,
    phone_root: str,
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
        phone_root=phone_root,
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
    local_report = report_dir / "arms" / arm
    control_dir = local_report / "control"
    control_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(queue, control_dir / queue.name)
    shutil.copy2(config, control_dir / config.name)

    remote_queue_dir = f"{phone_phase11_root}/queue"
    adb_shell(serial, f"mkdir -p {q(remote_queue_dir)}")
    adb(serial, ["push", str(queue), f"{remote_queue_dir}/{queue.name}"])
    adb(serial, ["push", str(config), f"{remote_queue_dir}/{config.name}"])

    state_path = f"{phone_phase11_root}/h11h_{arm}_state.json"
    heartbeat_path = f"{phone_phase11_root}/h11h_{arm}_heartbeat.json"
    stop_path = f"{phone_phase11_root}/STOP_h11h_{arm}"
    adb_shell(serial, f"rm -f {q(state_path)} {q(heartbeat_path)} {q(stop_path)}")
    command = (
        f"cd {q(phone_phase11_root)}; "
        f"{q(remote_runner)} --queue {q(f'queue/{queue.name}')} --run-root runs "
        f"--heartbeat {q(heartbeat_path)} --state {q(state_path)} --stop-file {q(stop_path)}"
    )
    started_at = utc_now()
    completed = adb_shell(serial, command, check=False)
    arm_run_id = f"{run_id}_{arm}"
    gate_dir = f"{phone_phase11_root}/runs/{arm_run_id}/{GATE_DIR_NAME}"
    pull_gate_artifacts(
        serial=serial,
        phone_phase11_root=phone_phase11_root,
        arm_run_id=arm_run_id,
        gate_dir=gate_dir,
        local_report=local_report,
        state_path=state_path,
        heartbeat_path=heartbeat_path,
    )
    pull_iteration_artifacts(
        serial=serial,
        gate_dir=gate_dir,
        local_report=local_report,
        iterations=iterations,
    )
    final_checkpoint = f"{gate_dir}/iterations/iter_{iterations - 1:06d}/checkpoint"
    return {
        "schema_version": "phase11_h11h_arm_run_v1",
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
                "mean_teacher_top1_probability": float(
                    telemetry.get("mean_teacher_top1_probability", float("nan"))
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
                "token_to_hidden_elapsed_seconds": telemetry.get("token_to_hidden_elapsed_seconds"),
                "layer_elapsed_seconds": telemetry.get("layer_elapsed_seconds"),
                "objective_elapsed_seconds": telemetry.get("objective_elapsed_seconds"),
                "adapter_elapsed_seconds": telemetry.get("adapter_elapsed_seconds"),
            }
        )
    return metrics


def summarize_arm(arm: dict[str, Any]) -> dict[str, Any]:
    local = Path(arm["local_report_dir"])
    gate_path = local / "gate_result.json"
    timing_path = local / "timing_breakdown.json"
    gate = load_json(gate_path) if gate_path.exists() else {}
    timing = load_json(timing_path) if timing_path.exists() else {}
    metrics = load_iteration_metrics(arm)
    losses = [item["loss_topk_kl"] for item in metrics]
    return {
        "schema_version": "phase11_h11h_arm_summary_v1",
        "arm": arm["arm"],
        "status": "pass" if arm["returncode"] == 0 and gate.get("status") == "pass" else "fail",
        "gate_status": gate.get("status", "missing"),
        "iterations": len(metrics),
        "required_iterations": arm["iterations"],
        "losses": losses,
        "loss_delta": losses[0] - losses[-1] if len(losses) >= 2 else 0.0,
        "first": metrics[0] if metrics else {},
        "last": metrics[-1] if metrics else {},
        "gate": gate,
        "timing": timing,
        "run": arm,
    }


def write_metric_trace(report_dir: Path, summaries: list[dict[str, Any]]) -> None:
    trace_path = report_dir / "metric_trace.jsonl"
    with trace_path.open("w", encoding="utf-8") as handle:
        for summary in summaries:
            arm = summary["arm"]
            for metric in load_iteration_metrics(summary["run"]):
                handle.write(json.dumps({"arm": arm, **metric}, sort_keys=True) + "\n")


def load_gate_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "status": "missing"}
    payload = load_json(path)
    return {"path": str(path), "status": payload.get("status"), "gate": payload.get("gate")}


def run_phone_regression_smokes(
    *,
    serial: str,
    phone_root: str,
    phone_phase11_root: str,
    layer_runner: Path,
    run_id: str,
    report_dir: Path,
    base_checkpoint: str,
    train_cache_phone: str,
) -> dict[str, Any]:
    remote_layer_runner = deploy_binary(
        serial=serial,
        phone_phase11_root=phone_phase11_root,
        binary=layer_runner,
        remote_name="gemma4_layer_runner",
    )
    phone_regression_root = f"{phone_phase11_root}/runs/{run_id}_phone_regressions"
    adb_shell(serial, f"rm -rf {q(phone_regression_root)} && mkdir -p {q(phone_regression_root)}")
    local_root = report_dir / "regressions" / "phone_smokes"
    local_root.mkdir(parents=True, exist_ok=True)

    tests = [
        {
            "name": "g1_layer0_opencl_smoke",
            "command": (
                f"{q(remote_layer_runner)} --run-opencl "
                f"{q(phone_path(phone_root, DEFAULT_LAYER0_PACK))} "
                f"{q(phone_regression_root + '/g1_layer0_opencl_smoke')}"
            ),
            "remote_dir": f"{phone_regression_root}/g1_layer0_opencl_smoke",
            "files": ("telemetry.json",),
        },
        {
            "name": "g3_two_layer_opencl_stack_smoke",
            "command": (
                f"{q(remote_layer_runner)} --run-opencl-stack "
                f"{q(phone_path(phone_root, DEFAULT_LAYER0_PACK))} "
                f"{q(phone_path(phone_root, DEFAULT_LAYER1_PACK))} "
                f"{q(phone_regression_root + '/g3_two_layer_opencl_stack_smoke')}"
            ),
            "remote_dir": f"{phone_regression_root}/g3_two_layer_opencl_stack_smoke",
            "files": ("telemetry.json",),
        },
        {
            "name": "g8_rank4_distill_compact_smoke",
            "command": (
                f"{q(remote_layer_runner)} --run-g8-distill-compact-rank "
                f"{q(train_cache_phone)} "
                f"{q(phone_path(phone_root, DEFAULT_ASSET_DIR))} "
                f"{q(phone_path(phone_root, DEFAULT_LAYER0_PACK))} "
                f"{q(phone_path(phone_root, DEFAULT_LAYER1_PACK))} "
                f"{q(base_checkpoint)} "
                f"{q(phone_regression_root + '/g8_rank4_distill_compact_smoke')} "
                "0.01 4"
            ),
            "remote_dir": f"{phone_regression_root}/g8_rank4_distill_compact_smoke",
            "files": (
                "telemetry.json",
                "artifact_manifest.json",
                "replay_manifest.json",
                "checkpoint/manifest.json",
            ),
        },
    ]

    results: list[dict[str, Any]] = []
    for test in tests:
        started_at = utc_now()
        completed = adb_shell(serial, test["command"], check=False)
        local_test = local_root / test["name"]
        pulled: list[str] = []
        for name in test["files"]:
            local_path = local_test / ("checkpoint_manifest.json" if name == "checkpoint/manifest.json" else name)
            if adb_pull_optional(serial, f"{test['remote_dir']}/{name}", local_path):
                pulled.append(str(local_path))
        telemetry = {}
        telemetry_path = local_test / "telemetry.json"
        if telemetry_path.exists():
            telemetry = load_json(telemetry_path)
        results.append(
            {
                "name": test["name"],
                "status": "pass" if completed.returncode == 0 and telemetry_path.exists() else "fail",
                "started_at_utc": started_at,
                "ended_at_utc": utc_now(),
                "returncode": completed.returncode,
                "stdout_first_2048": completed.stdout[:2048],
                "stderr_first_2048": completed.stderr[:2048],
                "phone_output_dir": test["remote_dir"],
                "pulled_artifacts": pulled,
                "telemetry_summary": {
                    "schema_version": telemetry.get("schema_version"),
                    "backend": telemetry.get("backend"),
                    "layer_backend": telemetry.get("layer_backend"),
                    "adapter_backend": telemetry.get("adapter_backend"),
                    "objective": telemetry.get("objective"),
                    "elapsed_seconds": telemetry.get("elapsed_seconds"),
                    "loss_before": telemetry.get("loss_before"),
                    "loss_after": telemetry.get("loss_after"),
                    "loss_topk_kl": telemetry.get("loss_topk_kl"),
                },
            }
        )

    summary = {
        "schema_version": "phase11_h11h_phone_regression_smokes_v1",
        "status": "pass" if all(item["status"] == "pass" for item in results) else "fail",
        "phone_regression_root": phone_regression_root,
        "tests": results,
    }
    write_json(local_root / "summary.json", summary)
    return summary


def run_final_falsifier_review(*, report_dir: Path, run_id: str, script: Path) -> dict[str, Any]:
    out_dir = report_dir / "regressions" / "g1_g3_g8_falsifier_rerun"
    completed = run_command(
        [
            sys.executable,
            str(script),
            "--repo-root",
            str(REPO_ROOT),
            "--out-dir",
            str(out_dir),
            "--run-id",
            f"{run_id}_g1_g3_g8_regression_floor",
        ],
        check=False,
    )
    gate_path = out_dir / "gate_result.json"
    report_path = out_dir / "falsifier_report.json"
    gate = load_json(gate_path) if gate_path.exists() else {}
    report = load_json(report_path) if report_path.exists() else {}
    return {
        "schema_version": "phase11_h11h_final_falsifier_rerun_v1",
        "status": "pass" if completed.returncode == 0 and gate.get("status") == "pass" else "fail",
        "returncode": completed.returncode,
        "stdout_first_2048": completed.stdout[:2048],
        "stderr_first_2048": completed.stderr[:2048],
        "local_report_dir": str(out_dir),
        "gate_result": gate,
        "failed_checks": report.get("failed_checks", []),
    }


def build_regression_report(
    *,
    report_dir: Path,
    run_id: str,
    phone_smokes: dict[str, Any],
    final_falsifier: dict[str, Any],
) -> dict[str, Any]:
    report = {
        "schema_version": "phase11_h11h_regression_report_v1",
        "run_id": run_id,
        "authority_gates_rechecked": {
            "g1_layer0_opencl": load_gate_status(G1_GATE),
            "g3_two_layer_opencl": load_gate_status(G3_GATE),
            "g8_streamed_corpus_repaired": load_gate_status(G8_GATE),
        },
        "phone_smoke_reruns": phone_smokes,
        "g1_g3_g8_falsifier_floor_rerun": final_falsifier,
    }
    gate_status_ok = all(
        item.get("status") == "pass"
        for item in report["authority_gates_rechecked"].values()
    )
    report["status"] = (
        "pass"
        if gate_status_ok and phone_smokes.get("status") == "pass" and final_falsifier.get("status") == "pass"
        else "fail"
    )
    write_json(report_dir / "regression_report.json", report)
    return report


def artifact_manifest(report_dir: Path) -> dict[str, Any]:
    entries = []
    for path in sorted(report_dir.rglob("*")):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        entries.append({"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return {
        "schema_version": "phase11_h11h_artifact_manifest_v1",
        "gate": "H11-H",
        "report_dir": str(report_dir),
        "git_allowed_artifacts": entries,
    }


def finite(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return number == number and number not in (float("inf"), float("-inf"))


def evaluate_gate(
    *,
    args: argparse.Namespace,
    summaries: dict[str, dict[str, Any]],
    regression_report: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    baseline = summaries["baseline_eval"]
    train = summaries["train"]
    trained = summaries["trained_eval"]

    if train["status"] != "pass" or train["iterations"] < args.iterations:
        blockers.append("predeclared 1000-update train arm did not pass or did not complete")
    if train["loss_delta"] <= 0.0 or not finite(train["loss_delta"]):
        blockers.append("train top-k KL did not decrease over the predeclared run")

    train_gate = train.get("gate", {})
    if train_gate.get("runtime_topology") != "phone_local_queue_no_adb_per_iteration":
        blockers.append("runtime topology regressed from phone-local queue execution")
    active_wall_ratio = train_gate.get("active_wall_ratio")
    if not finite(active_wall_ratio) or float(active_wall_ratio) < 0.50:
        blockers.append("train active/wall ratio did not reach the H11-H >=0.50 floor")

    if baseline["status"] != "pass" or trained["status"] != "pass":
        blockers.append("held-out fixed/trained evaluation arms did not both pass")

    baseline_last = baseline["last"]
    trained_last = trained["last"]
    if baseline_last and trained_last:
        if trained_last["loss_topk_kl"] > baseline_last["loss_topk_kl"] + args.heldout_epsilon:
            blockers.append("held-out top-k KL regressed versus fixed-adapter control")
        if (
            trained_last["mean_student_teacher_top1_probability"]
            <= baseline_last["mean_student_teacher_top1_probability"] + args.heldout_epsilon
        ):
            blockers.append("held-out teacher top-1 probability did not improve beyond fixed control")
        if (
            trained_last["student_teacher_top1_agreement"] + 1.0e-12
            < baseline_last["student_teacher_top1_agreement"]
        ):
            blockers.append("held-out teacher top-1 agreement regressed versus fixed control")
    else:
        blockers.append("held-out metrics are missing")

    if regression_report.get("status") != "pass":
        blockers.append("G1/G3/relevant G8 regression report did not pass")

    return blockers


def report_dir_for(args: argparse.Namespace) -> Path:
    return args.host_report_dir or Path(
        "runtime/reports/gemma4_megakernel/hardware_native_povc"
    ) / args.run_id / GATE_DIR_NAME


def phone_paths(args: argparse.Namespace) -> dict[str, str]:
    phone_phase11_root = f"{args.phone_root.rstrip('/')}/phase11"
    return {
        "phone_phase11_root": phone_phase11_root,
        "train_cache_phone": phone_path(args.phone_root, DEFAULT_TRAIN_CACHE),
        "heldout_cache_phone": phone_path(args.phone_root, DEFAULT_HELDOUT_CACHE),
        "base_checkpoint": phone_path(args.phone_root, DEFAULT_BASE_CHECKPOINT),
        "train_teacher_phone": f"{phone_phase11_root}/h11f_teacher_shards/train",
        "heldout_teacher_phone": f"{phone_phase11_root}/h11f_teacher_shards/heldout",
    }


def write_predeclared_files(args: argparse.Namespace, report_dir: Path, started: str) -> None:
    predeclared_objective = {
        "schema_version": "phase11_h11h_predeclared_objective_v1",
        "declared_before_phone_training_run": True,
        "declared_at_utc": started,
        "duration_objective": {
            "train_iterations": args.iterations,
            "minimum_prd_floor": ">=1000 iterations",
            "wall_hours_extension": "not predeclared; stop after 1000 iterations unless safety stop fires",
        },
        "capability_objective": {
            "train_gate": "loss_topk_kl decreases over the train arm",
            "heldout_gate": "heldout loss_topk_kl non-regression versus fixed-adapter control",
            "mini_metric": "heldout mean_student_teacher_top1_probability improves beyond fixed control",
            "agreement_guardrail": "heldout student_teacher_top1_agreement does not regress",
            "heldout_epsilon": args.heldout_epsilon,
        },
        "runtime_topology_gate": "phone_local_queue_no_adb_per_iteration",
        "active_wall_floor": 0.50,
        "regression_gate": "G1/G3/relevant G8 stored floor plus phone smoke reruns must pass",
    }
    combined_choices = {
        "schema_version": "phase11_h11h_combined_choices_v1",
        "daemon": "H11-A phone-resident queue runner with heartbeat/state/checksum chain",
        "performance_profile": "H11-B baseline-safe profile; no unsafe perf-control promotion",
        "queue_backend": "ordinary OpenCL command queues; H11-D recordable queues retained as evidence only",
        "trainable_scope": TRAINABLE_SCOPE,
        "objective": OBJECTIVE_CLAIM,
        "teacher": "RunPod-precomputed full Gemma4 E4B top-k shards already staged on phone",
        "runtime_teacher_service_used": False,
        "htp_role": "H11-G classified HTP as frozen-forward/teacher only; no mutable-section training in H11-H",
        "h11g_gate": load_gate_status(H11G_GATE),
    }
    write_json(report_dir / "predeclared_objective.json", predeclared_objective)
    write_json(report_dir / "combined_choices.json", combined_choices)


def validate_phone_inputs(args: argparse.Namespace, paths: dict[str, str]) -> None:
    require_teacher_shard(args.serial, paths["train_teacher_phone"])
    require_teacher_shard(args.serial, paths["heldout_teacher_phone"])
    require_phone_file(args.serial, f"{paths['train_cache_phone']}/manifest.json", "train token cache manifest")
    require_phone_file(args.serial, f"{paths['heldout_cache_phone']}/manifest.json", "heldout token cache manifest")
    require_phone_file(args.serial, f"{paths['base_checkpoint']}/adapter_a.f32.bin", "base adapter A")
    require_phone_file(args.serial, f"{paths['base_checkpoint']}/adapter_b.f32.bin", "base adapter B")


def prepare_detached_arm(
    *,
    serial: str,
    phone_root: str,
    phone_phase11_root: str,
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
        phone_root=phone_root,
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
    local_report = report_dir / "arms" / arm
    control_dir = local_report / "control"
    control_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(queue, control_dir / queue.name)
    shutil.copy2(config, control_dir / config.name)
    remote_queue_dir = f"{phone_phase11_root}/queue"
    adb_shell(serial, f"mkdir -p {q(remote_queue_dir)}")
    adb(serial, ["push", str(queue), f"{remote_queue_dir}/{queue.name}"])
    adb(serial, ["push", str(config), f"{remote_queue_dir}/{config.name}"])
    arm_run_id = f"{run_id}_{arm}"
    return {
        "schema_version": "phase11_h11h_detached_arm_v1",
        "arm": arm,
        "apply_update": apply_update,
        "iterations": iterations,
        "run_id": arm_run_id,
        "queue_name": queue.name,
        "config_name": config.name,
        "state_path": f"{phone_phase11_root}/h11h_{arm}_state.json",
        "heartbeat_path": f"{phone_phase11_root}/h11h_{arm}_heartbeat.json",
        "stop_path": f"{phone_phase11_root}/STOP_h11h_{arm}",
        "phone_gate_dir": f"{phone_phase11_root}/runs/{arm_run_id}/{GATE_DIR_NAME}",
        "final_checkpoint": f"{phone_phase11_root}/runs/{arm_run_id}/{GATE_DIR_NAME}/iterations/iter_{iterations - 1:06d}/checkpoint",
        "local_report_dir": str(local_report),
    }


def write_detached_chain_script(
    *,
    script_path: Path,
    args: argparse.Namespace,
    paths: dict[str, str],
    remote_runner: str,
    remote_layer_runner: str,
    arms: dict[str, dict[str, Any]],
) -> None:
    root = paths["phone_phase11_root"]
    regression_root = f"{root}/runs/{args.run_id}_phone_regressions"
    lines = [
        "#!/system/bin/sh",
        "set -u",
        f"ROOT={q(root)}",
        f"RUN_ID={q(args.run_id)}",
        f"RUNNER={q(remote_runner)}",
        f"LAYER_RUNNER={q(remote_layer_runner)}",
        f"REGRESSION_ROOT={q(regression_root)}",
        'LOG="$ROOT/h11h_${RUN_ID}_chain.log"',
        'EVENTS="$ROOT/h11h_${RUN_ID}_chain_events.jsonl"',
        'STATE="$ROOT/h11h_${RUN_ID}_chain_state.json"',
        'STOP="$ROOT/STOP_h11h_chain_${RUN_ID}"',
        'BOOTSTRAP="$ROOT/h11h_${RUN_ID}_chain.bootstrap.log"',
        'write_state() { printf \'{"schema_version":"phase11_h11h_detached_chain_state_v1","run_id":"%s","status":"%s","step":"%s","updated_at_epoch":%s}\\n\' "$RUN_ID" "$1" "$2" "$(date +%s)" > "$STATE"; }',
        'run_step() { STEP="$1"; shift; if [ -f "$STOP" ]; then write_state stopped "$STEP"; '
        + 'printf \'{"schema_version":"phase11_h11h_detached_chain_event_v1","step":"%s","status":"stopped","returncode":130,"updated_at_epoch":%s}\\n\' "$STEP" "$(date +%s)" >> "$EVENTS"'
        + '; exit 130; fi; write_state running "$STEP"; "$@" >> "$LOG" 2>&1; RC="$?"; '
        + 'if [ "$RC" -eq 0 ]; then STATUS=pass; else STATUS=fail; fi; '
        + 'printf \'{"schema_version":"phase11_h11h_detached_chain_event_v1","step":"%s","status":"%s","returncode":%s,"updated_at_epoch":%s}\\n\' "$STEP" "$STATUS" "$RC" "$(date +%s)" >> "$EVENTS"; '
        + 'if [ "$RC" -ne 0 ]; then write_state failed "$STEP"; exit "$RC"; fi; }',
        'rm -f "$EVENTS" "$LOG" "$STATE" "$BOOTSTRAP"',
        'rm -f "$ROOT"/STOP_h11h_baseline_eval "$ROOT"/STOP_h11h_train "$ROOT"/STOP_h11h_trained_eval "$STOP"',
        f"rm -rf {q(regression_root)} "
        f"{q(root + '/runs/' + args.run_id + '_baseline_eval')} "
        f"{q(root + '/runs/' + args.run_id + '_train')} "
        f"{q(root + '/runs/' + args.run_id + '_trained_eval')}",
        'mkdir -p "$REGRESSION_ROOT" "$ROOT/runs"',
        "write_state running preflight",
        "run_step g1_layer0_opencl_smoke \"$LAYER_RUNNER\" --run-opencl "
        f"{q(phone_path(args.phone_root, DEFAULT_LAYER0_PACK))} "
        "\"$REGRESSION_ROOT/g1_layer0_opencl_smoke\"",
        "run_step g3_two_layer_opencl_stack_smoke \"$LAYER_RUNNER\" --run-opencl-stack "
        f"{q(phone_path(args.phone_root, DEFAULT_LAYER0_PACK))} "
        f"{q(phone_path(args.phone_root, DEFAULT_LAYER1_PACK))} "
        "\"$REGRESSION_ROOT/g3_two_layer_opencl_stack_smoke\"",
        "run_step g8_rank4_distill_compact_smoke \"$LAYER_RUNNER\" --run-g8-distill-compact-rank "
        f"{q(paths['train_cache_phone'])} "
        f"{q(phone_path(args.phone_root, DEFAULT_ASSET_DIR))} "
        f"{q(phone_path(args.phone_root, DEFAULT_LAYER0_PACK))} "
        f"{q(phone_path(args.phone_root, DEFAULT_LAYER1_PACK))} "
        f"{q(paths['base_checkpoint'])} "
        "\"$REGRESSION_ROOT/g8_rank4_distill_compact_smoke\" "
        f"{args.learning_rate} 4",
    ]
    for arm in ("baseline_eval", "train", "trained_eval"):
        record = arms[arm]
        lines.append(
            f"run_step {arm} sh -c "
            + q(
                f"cd {root}; {remote_runner} --queue queue/{record['queue_name']} "
                f"--run-root runs --heartbeat {record['heartbeat_path']} "
                f"--state {record['state_path']} --stop-file {record['stop_path']}"
            )
        )
    lines.extend(
        [
            "write_state completed done",
            "exit 0",
        ]
    )
    write_text(script_path, "\n".join(lines) + "\n")


def launch_detached(args: argparse.Namespace) -> int:
    if args.iterations < 1000:
        raise ValueError("H11-H requires at least 1000 train iterations unless the PRD objective is changed")
    report_dir = report_dir_for(args)
    report_dir.mkdir(parents=True, exist_ok=True)
    paths = phone_paths(args)
    started = utc_now()
    write_predeclared_files(args, report_dir, started)
    validate_phone_inputs(args, paths)
    remote_runner = deploy_runner(
        serial=args.serial,
        phone_phase11_root=paths["phone_phase11_root"],
        runner=args.phase11_runner,
    )
    remote_layer_runner = deploy_binary(
        serial=args.serial,
        phone_phase11_root=paths["phone_phase11_root"],
        binary=args.layer_runner,
        remote_name="gemma4_layer_runner",
    )
    final_falsifier = run_final_falsifier_review(
        report_dir=report_dir,
        run_id=args.run_id,
        script=args.final_falsifier_script,
    )
    with tempfile.TemporaryDirectory(prefix="h11h_detached_") as tmp_name:
        tmp = Path(tmp_name)
        train_final_checkpoint = (
            f"{paths['phone_phase11_root']}/runs/{args.run_id}_train/{GATE_DIR_NAME}/"
            f"iterations/iter_{args.iterations - 1:06d}/checkpoint"
        )
        arms = {
            "baseline_eval": prepare_detached_arm(
                serial=args.serial,
                phone_root=args.phone_root,
                phone_phase11_root=paths["phone_phase11_root"],
                run_id=args.run_id,
                arm="baseline_eval",
                token_cache=paths["heldout_cache_phone"],
                teacher_shard=paths["heldout_teacher_phone"],
                checkpoint=paths["base_checkpoint"],
                iterations=1,
                learning_rate=0.0,
                apply_update=False,
                report_dir=report_dir,
                tmp=tmp,
            ),
            "train": prepare_detached_arm(
                serial=args.serial,
                phone_root=args.phone_root,
                phone_phase11_root=paths["phone_phase11_root"],
                run_id=args.run_id,
                arm="train",
                token_cache=paths["train_cache_phone"],
                teacher_shard=paths["train_teacher_phone"],
                checkpoint=paths["base_checkpoint"],
                iterations=args.iterations,
                learning_rate=args.learning_rate,
                apply_update=True,
                report_dir=report_dir,
                tmp=tmp,
            ),
            "trained_eval": prepare_detached_arm(
                serial=args.serial,
                phone_root=args.phone_root,
                phone_phase11_root=paths["phone_phase11_root"],
                run_id=args.run_id,
                arm="trained_eval",
                token_cache=paths["heldout_cache_phone"],
                teacher_shard=paths["heldout_teacher_phone"],
                checkpoint=train_final_checkpoint,
                iterations=1,
                learning_rate=0.0,
                apply_update=False,
                report_dir=report_dir,
                tmp=tmp,
            ),
        }
        script = tmp / f"h11h_{args.run_id}_chain.sh"
        write_detached_chain_script(
            script_path=script,
            args=args,
            paths=paths,
            remote_runner=remote_runner,
            remote_layer_runner=remote_layer_runner,
            arms=arms,
        )
        local_script_copy = report_dir / "detached_chain" / script.name
        local_script_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(script, local_script_copy)
        remote_script = f"{paths['phone_phase11_root']}/{script.name}"
        adb(args.serial, ["push", str(script), remote_script])
        adb_shell(args.serial, f"chmod 755 {q(remote_script)}")

    pid_path = f"{paths['phone_phase11_root']}/h11h_{args.run_id}_chain.pid"
    bootstrap = f"{paths['phone_phase11_root']}/h11h_{args.run_id}_chain.bootstrap.log"
    launch_cmd = (
        f"cd {q(paths['phone_phase11_root'])}; "
        f"rm -f {q(pid_path)} {q(bootstrap)}; "
        f"(nohup sh {q(remote_script)} > {q(bootstrap)} 2>&1 < /dev/null & echo $! > {q(pid_path)})"
    )
    completed = adb_shell(args.serial, launch_cmd, check=False)
    pid_read = adb_shell(args.serial, f"cat {q(pid_path)} 2>/dev/null || true", check=False)
    detached_manifest = {
        "schema_version": "phase11_h11h_detached_launch_v1",
        "run_id": args.run_id,
        "status": "launched" if completed.returncode == 0 and pid_read.stdout.strip() else "launch_failed",
        "started_at_utc": started,
        "phone_phase11_root": paths["phone_phase11_root"],
        "phone_chain_script": remote_script,
        "phone_chain_pid_path": pid_path,
        "phone_chain_pid": pid_read.stdout.strip(),
        "phone_chain_state": f"{paths['phone_phase11_root']}/h11h_{args.run_id}_chain_state.json",
        "phone_chain_events": f"{paths['phone_phase11_root']}/h11h_{args.run_id}_chain_events.jsonl",
        "phone_chain_log": f"{paths['phone_phase11_root']}/h11h_{args.run_id}_chain.log",
        "phone_chain_bootstrap": bootstrap,
        "arms": arms,
        "host_final_falsifier_prelaunch": final_falsifier,
        "collect_command": (
            f"python3 scripts/host/run_phase11_h11h_combined_povc.py --collect-detached "
            f"--run-id {args.run_id} --iterations {args.iterations}"
        ),
        "launch_returncode": completed.returncode,
        "launch_stdout": completed.stdout,
        "launch_stderr": completed.stderr,
    }
    write_json(report_dir / "detached_launch.json", detached_manifest)
    write_json(
        report_dir / "gate_result.json",
        {
            "schema_version": "phase11_h11h_gate_result_v1",
            "gate": "H11-H",
            "status": "running_detached" if detached_manifest["status"] == "launched" else "fail",
            "authority_verdict": "not_promoted_pending_detached_collection",
            "run_id": args.run_id,
            "predeclared_train_iterations": args.iterations,
            "host_report_dir": str(report_dir),
            "phone_chain_state": detached_manifest["phone_chain_state"],
            "phone_chain_pid": detached_manifest["phone_chain_pid"],
            "blockers": [] if detached_manifest["status"] == "launched" else ["detached chain launch failed"],
        },
    )
    write_text(
        report_dir / "commands.log",
        "python3 scripts/host/run_phase11_h11h_combined_povc.py --iterations 1000\n"
        "adb push phase11_runner and gemma4_layer_runner to PHONE_PHASE11_ROOT\n"
        "adb push h11h_<run_id>_chain.sh to PHONE_PHASE11_ROOT\n"
        "adb shell 'nohup sh PHONE_PHASE11_ROOT/h11h_<run_id>_chain.sh > ... 2>&1 < /dev/null &'\n",
    )
    write_json(report_dir / "artifact_manifest.json", artifact_manifest(report_dir))
    print(json.dumps({"status": detached_manifest["status"], "run_id": args.run_id, "host_report_dir": str(report_dir), "phone_pid": detached_manifest["phone_chain_pid"]}, sort_keys=True))
    return 0 if detached_manifest["status"] == "launched" else 1


def collect_phone_smokes(args: argparse.Namespace, report_dir: Path, paths: dict[str, str]) -> dict[str, Any]:
    regression_root = f"{paths['phone_phase11_root']}/runs/{args.run_id}_phone_regressions"
    local_root = report_dir / "regressions" / "phone_smokes"
    tests = {
        "g1_layer0_opencl_smoke": ("telemetry.json",),
        "g3_two_layer_opencl_stack_smoke": ("telemetry.json",),
        "g8_rank4_distill_compact_smoke": (
            "telemetry.json",
            "artifact_manifest.json",
            "replay_manifest.json",
            "checkpoint/manifest.json",
        ),
    }
    results = []
    for name, files in tests.items():
        local_test = local_root / name
        pulled = []
        for remote_name in files:
            local_name = "checkpoint_manifest.json" if remote_name == "checkpoint/manifest.json" else remote_name
            if adb_pull_optional(args.serial, f"{regression_root}/{name}/{remote_name}", local_test / local_name):
                pulled.append(str(local_test / local_name))
        telemetry_path = local_test / "telemetry.json"
        telemetry = load_json(telemetry_path) if telemetry_path.exists() else {}
        results.append(
            {
                "name": name,
                "status": "pass" if telemetry_path.exists() else "missing",
                "phone_output_dir": f"{regression_root}/{name}",
                "pulled_artifacts": pulled,
                "telemetry_summary": {
                    "schema_version": telemetry.get("schema_version"),
                    "backend": telemetry.get("backend"),
                    "layer_backend": telemetry.get("layer_backend"),
                    "adapter_backend": telemetry.get("adapter_backend"),
                    "objective": telemetry.get("objective"),
                    "elapsed_seconds": telemetry.get("elapsed_seconds"),
                    "loss_before": telemetry.get("loss_before"),
                    "loss_after": telemetry.get("loss_after"),
                },
            }
        )
    summary = {
        "schema_version": "phase11_h11h_phone_regression_smokes_v1",
        "status": "pass" if all(item["status"] == "pass" for item in results) else "fail",
        "phone_regression_root": regression_root,
        "tests": results,
    }
    write_json(local_root / "summary.json", summary)
    return summary


def collect_detached_arm(
    *,
    args: argparse.Namespace,
    paths: dict[str, str],
    arm: str,
    iterations: int,
    apply_update: bool,
    report_dir: Path,
) -> dict[str, Any]:
    arm_run_id = f"{args.run_id}_{arm}"
    gate_dir = f"{paths['phone_phase11_root']}/runs/{arm_run_id}/{GATE_DIR_NAME}"
    local_report = report_dir / "arms" / arm
    state_path = f"{paths['phone_phase11_root']}/h11h_{arm}_state.json"
    heartbeat_path = f"{paths['phone_phase11_root']}/h11h_{arm}_heartbeat.json"
    pull_gate_artifacts(
        serial=args.serial,
        phone_phase11_root=paths["phone_phase11_root"],
        arm_run_id=arm_run_id,
        gate_dir=gate_dir,
        local_report=local_report,
        state_path=state_path,
        heartbeat_path=heartbeat_path,
    )
    pull_iteration_artifacts(
        serial=args.serial,
        gate_dir=gate_dir,
        local_report=local_report,
        iterations=iterations,
    )
    gate_path = local_report / "gate_result.json"
    gate = load_json(gate_path) if gate_path.exists() else {}
    return {
        "schema_version": "phase11_h11h_arm_run_v1",
        "arm": arm,
        "apply_update": apply_update,
        "iterations": iterations,
        "run_id": arm_run_id,
        "started_at_utc": None,
        "ended_at_utc": utc_now(),
        "returncode": 0 if gate.get("status") == "pass" else 1,
        "stdout_first_4096": "",
        "stderr_first_4096": "",
        "phone_gate_dir": gate_dir,
        "final_checkpoint": f"{gate_dir}/iterations/iter_{iterations - 1:06d}/checkpoint",
        "local_report_dir": str(local_report),
    }


def collect_detached(args: argparse.Namespace) -> int:
    report_dir = report_dir_for(args)
    report_dir.mkdir(parents=True, exist_ok=True)
    paths = phone_paths(args)
    chain_base = f"{paths['phone_phase11_root']}/h11h_{args.run_id}_chain"
    chain_dir = report_dir / "detached_chain"
    for remote_name, local_name in (
        (f"{chain_base}.sh", f"h11h_{args.run_id}_chain.sh"),
        (f"{chain_base}.pid", "chain.pid"),
        (f"{chain_base}_state.json", "chain_state.json"),
        (f"{chain_base}_events.jsonl", "chain_events.jsonl"),
        (f"{chain_base}.log", "chain.log"),
        (f"{chain_base}.bootstrap.log", "chain.bootstrap.log"),
    ):
        adb_pull_optional(args.serial, remote_name, chain_dir / local_name)
    phone_smokes = collect_phone_smokes(args, report_dir, paths)
    final_falsifier = run_final_falsifier_review(
        report_dir=report_dir,
        run_id=args.run_id,
        script=args.final_falsifier_script,
    )
    regression_report = build_regression_report(
        report_dir=report_dir,
        run_id=args.run_id,
        phone_smokes=phone_smokes,
        final_falsifier=final_falsifier,
    )
    arms = [
        collect_detached_arm(
            args=args,
            paths=paths,
            arm="baseline_eval",
            iterations=1,
            apply_update=False,
            report_dir=report_dir,
        ),
        collect_detached_arm(
            args=args,
            paths=paths,
            arm="train",
            iterations=args.iterations,
            apply_update=True,
            report_dir=report_dir,
        ),
        collect_detached_arm(
            args=args,
            paths=paths,
            arm="trained_eval",
            iterations=1,
            apply_update=False,
            report_dir=report_dir,
        ),
    ]
    summaries = [summarize_arm(item) for item in arms]
    summary_by_arm = {item["arm"]: item for item in summaries}
    blockers = evaluate_gate(args=args, summaries=summary_by_arm, regression_report=regression_report)
    status = "pass" if not blockers else "fail"
    authority_verdict = (
        "promote_exact_h11h_phone_native_rank4_topk_kl_povc_claim"
        if status == "pass"
        else "do_not_promote_h11h_combined_povc"
    )
    write_json(report_dir / "arm_runs.json", {"schema_version": "phase11_h11h_arm_runs_v1", "runs": arms})
    write_json(report_dir / "loss_traces.json", {"schema_version": "phase11_h11h_loss_traces_v1", "arms": summaries})
    write_metric_trace(report_dir, summaries)
    write_json(
        report_dir / "heldout_report.json",
        {
            "schema_version": "phase11_h11h_heldout_report_v1",
            "fixed_adapter_control": summary_by_arm["baseline_eval"],
            "trained_adapter": summary_by_arm["trained_eval"],
        },
    )
    train = arms[1]
    trained_eval = arms[2]
    write_json(
        report_dir / "checkpoint_adapter_manifest.json",
        {
            "schema_version": "phase11_h11h_checkpoint_adapter_manifest_v1",
            "base_checkpoint": paths["base_checkpoint"],
            "train_final_checkpoint_phone": train["final_checkpoint"],
            "train_final_checkpoint_manifest": str(
                Path(train["local_report_dir"])
                / "iterations"
                / f"iter_{args.iterations - 1:06d}"
                / "checkpoint_manifest.json"
            ),
            "heldout_eval_checkpoint_manifest": str(
                Path(trained_eval["local_report_dir"])
                / "iterations"
                / "iter_000000"
                / "checkpoint_manifest.json"
            ),
        },
    )
    write_json(
        report_dir / "gate_result.json",
        {
            "schema_version": "phase11_h11h_gate_result_v1",
            "gate": "H11-H",
            "status": status,
            "authority_verdict": authority_verdict,
            "blockers": blockers,
            "selected_scope": TRAINABLE_SCOPE,
            "objective": OBJECTIVE_CLAIM,
            "predeclared_train_iterations": args.iterations,
            "teacher_shard_status": "reused_h11f_precomputed_teacher_shards_on_phone",
            "runtime_teacher_service_used": False,
            "runtime_topology": summary_by_arm["train"].get("gate", {}).get("runtime_topology"),
            "active_wall_ratio": summary_by_arm["train"].get("gate", {}).get("active_wall_ratio"),
            "fixed_adapter_control": summary_by_arm["baseline_eval"],
            "train_summary": summary_by_arm["train"],
            "trained_heldout_summary": summary_by_arm["trained_eval"],
            "regression_report": regression_report,
            "ended_at_utc": utc_now(),
            "host_report_dir": str(report_dir),
            "phone_phase11_root": paths["phone_phase11_root"],
            "next_on_pass": "write next PRD for longer endurance or broader Gemma scope without expanding claim scope",
            "next_on_fail": "preserve artifacts, mark failed hypothesis, and select the highest-leverage Phase 12 blocker",
        },
    )
    write_text(
        report_dir / "blockers.md",
        "- None for H11-H.\n" if not blockers else "".join(f"- {item}\n" for item in blockers),
    )
    write_text(
        report_dir / "falsifier_report.md",
        "# H11-H Falsifier Report\n\n"
        f"- detached phone chain: {'pass' if (chain_dir / 'chain_events.jsonl').exists() else 'fail'}, "
        "the H11-H long path runs from a phone-local shell chain after launch.\n"
        f"- host-driven iteration loop: {'pass' if summary_by_arm['train'].get('gate', {}).get('runtime_topology') == 'phone_local_queue_no_adb_per_iteration' else 'fail'}.\n"
        f"- throughput-only promotion: {'pass' if summary_by_arm['train']['loss_delta'] > 0.0 else 'fail'}, capability movement is governed by top-k KL and held-out controls.\n"
        f"- active/wall floor: {'pass' if summary_by_arm['train'].get('gate', {}).get('active_wall_ratio', 0.0) >= 0.50 else 'fail'}.\n"
        f"- G1/G3/relevant G8 preservation: {'pass' if regression_report.get('status') == 'pass' else 'fail'}.\n"
        "- HTP overclaim: pass, H11-H uses H11-G only as frozen-forward/teacher classification evidence; no HTP backprop or mutable update claim is made.\n"
        f"- unresolved critical issue: {'none' if status == 'pass' else 'present; see blockers.md'}.\n",
    )
    write_text(
        report_dir / "commands.log",
        "python3 scripts/host/run_phase11_h11h_combined_povc.py --iterations 1000\n"
        f"python3 scripts/host/run_phase11_h11h_combined_povc.py --collect-detached --run-id {args.run_id} --iterations {args.iterations}\n",
    )
    write_json(report_dir / "artifact_manifest.json", artifact_manifest(report_dir))
    print(json.dumps({"status": status, "host_report_dir": str(report_dir)}, sort_keys=True))
    return 0 if status == "pass" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", default=DEFAULT_SERIAL)
    parser.add_argument("--phone-root", default=DEFAULT_PHONE_ROOT)
    parser.add_argument("--run-id", default=f"{compact_utc_now()}_h11h_combined_povc")
    parser.add_argument("--phase11-runner", type=Path, default=DEFAULT_PHASE11_RUNNER)
    parser.add_argument("--layer-runner", type=Path, default=DEFAULT_LAYER_RUNNER)
    parser.add_argument("--final-falsifier-script", type=Path, default=DEFAULT_FINAL_FALSIFIER)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--heldout-epsilon", type=float, default=1.0e-9)
    parser.add_argument("--host-report-dir", type=Path, default=None)
    parser.add_argument("--collect-detached", action="store_true")
    parser.add_argument("--inline", action="store_true", help="Run the old blocking host-launched arm sequence.")
    return parser.parse_args()


def run_inline(args: argparse.Namespace) -> int:
    if args.iterations < 1000:
        raise ValueError("H11-H requires at least 1000 train iterations unless the PRD objective is changed")

    report_dir = args.host_report_dir or Path(
        "runtime/reports/gemma4_megakernel/hardware_native_povc"
    ) / args.run_id / GATE_DIR_NAME
    report_dir.mkdir(parents=True, exist_ok=True)

    phone_phase11_root = f"{args.phone_root.rstrip('/')}/phase11"
    train_cache_phone = phone_path(args.phone_root, DEFAULT_TRAIN_CACHE)
    heldout_cache_phone = phone_path(args.phone_root, DEFAULT_HELDOUT_CACHE)
    base_checkpoint = phone_path(args.phone_root, DEFAULT_BASE_CHECKPOINT)
    train_teacher_phone = f"{phone_phase11_root}/h11f_teacher_shards/train"
    heldout_teacher_phone = f"{phone_phase11_root}/h11f_teacher_shards/heldout"
    started = utc_now()

    predeclared_objective = {
        "schema_version": "phase11_h11h_predeclared_objective_v1",
        "declared_before_phone_training_run": True,
        "declared_at_utc": started,
        "duration_objective": {
            "train_iterations": args.iterations,
            "minimum_prd_floor": ">=1000 iterations",
            "wall_hours_extension": "not predeclared; stop after 1000 iterations unless safety stop fires",
        },
        "capability_objective": {
            "train_gate": "loss_topk_kl decreases over the train arm",
            "heldout_gate": "heldout loss_topk_kl non-regression versus fixed-adapter control",
            "mini_metric": "heldout mean_student_teacher_top1_probability improves beyond fixed control",
            "agreement_guardrail": "heldout student_teacher_top1_agreement does not regress",
            "heldout_epsilon": args.heldout_epsilon,
        },
        "runtime_topology_gate": "phone_local_queue_no_adb_per_iteration",
        "active_wall_floor": 0.50,
        "regression_gate": "G1/G3/relevant G8 stored floor plus phone smoke reruns must pass",
    }
    combined_choices = {
        "schema_version": "phase11_h11h_combined_choices_v1",
        "daemon": "H11-A phone-resident queue runner with heartbeat/state/checksum chain",
        "performance_profile": "H11-B baseline-safe profile; no unsafe perf-control promotion",
        "queue_backend": "ordinary OpenCL command queues; H11-D recordable queues retained as evidence only",
        "trainable_scope": TRAINABLE_SCOPE,
        "objective": OBJECTIVE_CLAIM,
        "teacher": "RunPod-precomputed full Gemma4 E4B top-k shards already staged on phone",
        "runtime_teacher_service_used": False,
        "htp_role": "H11-G classified HTP as frozen-forward/teacher only; no mutable-section training in H11-H",
        "h11g_gate": load_gate_status(H11G_GATE),
    }
    write_json(report_dir / "predeclared_objective.json", predeclared_objective)
    write_json(report_dir / "combined_choices.json", combined_choices)

    require_teacher_shard(args.serial, train_teacher_phone)
    require_teacher_shard(args.serial, heldout_teacher_phone)
    require_phone_file(args.serial, f"{train_cache_phone}/manifest.json", "train token cache manifest")
    require_phone_file(args.serial, f"{heldout_cache_phone}/manifest.json", "heldout token cache manifest")
    require_phone_file(args.serial, f"{base_checkpoint}/adapter_a.f32.bin", "base adapter A")
    require_phone_file(args.serial, f"{base_checkpoint}/adapter_b.f32.bin", "base adapter B")

    remote_runner = deploy_runner(
        serial=args.serial,
        phone_phase11_root=phone_phase11_root,
        runner=args.phase11_runner,
    )
    phone_smokes = run_phone_regression_smokes(
        serial=args.serial,
        phone_root=args.phone_root,
        phone_phase11_root=phone_phase11_root,
        layer_runner=args.layer_runner,
        run_id=args.run_id,
        report_dir=report_dir,
        base_checkpoint=base_checkpoint,
        train_cache_phone=train_cache_phone,
    )
    final_falsifier = run_final_falsifier_review(
        report_dir=report_dir,
        run_id=args.run_id,
        script=args.final_falsifier_script,
    )
    regression_report = build_regression_report(
        report_dir=report_dir,
        run_id=args.run_id,
        phone_smokes=phone_smokes,
        final_falsifier=final_falsifier,
    )

    with tempfile.TemporaryDirectory(prefix="h11h_combined_") as tmp_name:
        tmp = Path(tmp_name)
        baseline_eval = run_arm(
            serial=args.serial,
            phone_root=args.phone_root,
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
            phone_root=args.phone_root,
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
            phone_root=args.phone_root,
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
    blockers = evaluate_gate(
        args=args,
        summaries=summary_by_arm,
        regression_report=regression_report,
    )
    status = "pass" if not blockers else "fail"
    authority_verdict = (
        "promote_exact_h11h_phone_native_rank4_topk_kl_povc_claim"
        if status == "pass"
        else "do_not_promote_h11h_combined_povc"
    )

    write_json(report_dir / "arm_runs.json", {"schema_version": "phase11_h11h_arm_runs_v1", "runs": arms})
    write_json(report_dir / "loss_traces.json", {"schema_version": "phase11_h11h_loss_traces_v1", "arms": summaries})
    write_metric_trace(report_dir, summaries)
    write_json(
        report_dir / "heldout_report.json",
        {
            "schema_version": "phase11_h11h_heldout_report_v1",
            "fixed_adapter_control": summary_by_arm["baseline_eval"],
            "trained_adapter": summary_by_arm["trained_eval"],
        },
    )
    write_json(
        report_dir / "checkpoint_adapter_manifest.json",
        {
            "schema_version": "phase11_h11h_checkpoint_adapter_manifest_v1",
            "base_checkpoint": base_checkpoint,
            "train_final_checkpoint_phone": train["final_checkpoint"],
            "train_final_checkpoint_manifest": str(
                Path(train["local_report_dir"])
                / "iterations"
                / f"iter_{args.iterations - 1:06d}"
                / "checkpoint_manifest.json"
            ),
            "heldout_eval_checkpoint_manifest": str(
                Path(trained_eval["local_report_dir"])
                / "iterations"
                / "iter_000000"
                / "checkpoint_manifest.json"
            ),
        },
    )
    gate_result = {
        "schema_version": "phase11_h11h_gate_result_v1",
        "gate": "H11-H",
        "status": status,
        "authority_verdict": authority_verdict,
        "blockers": blockers,
        "selected_scope": TRAINABLE_SCOPE,
        "objective": OBJECTIVE_CLAIM,
        "predeclared_train_iterations": args.iterations,
        "teacher_shard_status": "reused_h11f_precomputed_teacher_shards_on_phone",
        "runtime_teacher_service_used": False,
        "runtime_topology": summary_by_arm["train"].get("gate", {}).get("runtime_topology"),
        "active_wall_ratio": summary_by_arm["train"].get("gate", {}).get("active_wall_ratio"),
        "fixed_adapter_control": summary_by_arm["baseline_eval"],
        "train_summary": summary_by_arm["train"],
        "trained_heldout_summary": summary_by_arm["trained_eval"],
        "regression_report": regression_report,
        "started_at_utc": started,
        "ended_at_utc": utc_now(),
        "host_report_dir": str(report_dir),
        "phone_phase11_root": phone_phase11_root,
        "next_on_pass": "write next PRD for longer endurance or broader Gemma scope without expanding claim scope",
        "next_on_fail": "preserve artifacts, mark failed hypothesis, and select the highest-leverage Phase 12 blocker",
    }
    write_json(report_dir / "gate_result.json", gate_result)
    write_text(
        report_dir / "blockers.md",
        "- None for H11-H.\n" if not blockers else "".join(f"- {item}\n" for item in blockers),
    )
    write_text(
        report_dir / "falsifier_report.md",
        "# H11-H Falsifier Report\n\n"
        f"- host-driven iteration loop: {'pass' if summary_by_arm['train'].get('gate', {}).get('runtime_topology') == 'phone_local_queue_no_adb_per_iteration' else 'fail'}, "
        "the Mac starts one phone runner process per arm and does not serve iterations.\n"
        f"- throughput-only promotion: {'pass' if train['returncode'] == 0 and summary_by_arm['train']['loss_delta'] > 0.0 else 'fail'}, "
        "capability movement is governed by top-k KL and held-out controls.\n"
        f"- active/wall floor: {'pass' if summary_by_arm['train'].get('gate', {}).get('active_wall_ratio', 0.0) >= 0.50 else 'fail'}.\n"
        f"- G1/G3/relevant G8 preservation: {'pass' if regression_report.get('status') == 'pass' else 'fail'}.\n"
        f"- HTP overclaim: pass, H11-H uses H11-G only as frozen-forward/teacher classification evidence; no HTP backprop or mutable update claim is made.\n"
        f"- replayable adapter artifacts: {'pass' if (report_dir / 'checkpoint_adapter_manifest.json').exists() else 'fail'}, "
        "raw adapter payloads stay on phone with manifest hashes in git.\n"
        f"- unresolved critical issue: {'none' if status == 'pass' else 'present; see blockers.md'}.\n",
    )
    write_text(
        report_dir / "commands.log",
        "python3 scripts/host/run_phase11_h11h_combined_povc.py --iterations 1000\n"
        "adb push phase11_runner PHONE_PHASE11_ROOT/phase11_runner\n"
        "adb push gemma4_layer_runner PHONE_PHASE11_ROOT/gemma4_layer_runner\n"
        "adb shell gemma4_layer_runner --run-opencl / --run-opencl-stack / --run-g8-distill-compact-rank for phone regression smokes\n"
        "python3 final_falsifier_review.py --repo-root REPO_ROOT --out-dir H11-H/regressions/g1_g3_g8_falsifier_rerun\n"
        "adb shell phase11_runner --queue queue/h11h_<arm>_queue.jsonl --run-root runs --heartbeat ... --state ...\n",
    )
    write_json(report_dir / "artifact_manifest.json", artifact_manifest(report_dir))
    print(json.dumps({"status": status, "host_report_dir": str(report_dir)}, sort_keys=True))
    return 0 if status == "pass" else 1


def main() -> int:
    args = parse_args()
    if args.collect_detached:
        return collect_detached(args)
    if args.inline:
        return run_inline(args)
    return launch_detached(args)


if __name__ == "__main__":
    raise SystemExit(main())

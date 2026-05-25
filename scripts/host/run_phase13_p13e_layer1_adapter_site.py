#!/usr/bin/env python3
"""Run Phase 13 P13-E second Gemma residual-adapter site gate."""
from __future__ import annotations

import argparse
import array
import datetime as dt
import json
import math
import random
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.host.run_phase13_p13d_expanded_gradient_parity import (  # noqa: E402
    ABS_TOL,
    ASSET_DIR,
    BASE_LR,
    DEFAULT_LAYER_RUNNER,
    DEFAULT_PHONE_ROOT,
    DEFAULT_SERIAL,
    EPSILON,
    HIDDEN,
    LAYER0_PACK,
    LAYER1_PACK,
    MODEL_ID,
    MODEL_REVISION,
    REL_TOL,
    SIGN_THRESHOLD,
    TEACHER_SHARD,
    TOKEN_CACHE,
    adb_pull,
    adb_push,
    adb_shell,
    command_log_entry,
    deploy_layer_runner,
    l2,
    load_json,
    make_perturbed_checkpoint,
    phone_path,
    pull_checkpoint,
    q,
    read_f32,
    rel,
    result_passes,
    run_command,
    sha256_file,
    source_commit,
    source_dirty,
    write_f32,
    write_json,
    write_text,
)


PHASE13_ROOT = REPO_ROOT / "runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous"
ACTIVE_RUN = PHASE13_ROOT / "active_phase13_run.json"
RANK = 16
SEED = 13005
PROBE_COUNT = 8
MEMORY_BUDGET_KB = 2_500_000
BASE_CHECKPOINT = "phase12/checkpoints/20260524T164412Z_phase12_cde_authority_rank16_init"
RANK4_BASE_CHECKPOINT = "adapter_training/g5g6_rank4_20260517T040000Z/checkpoint"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def active_run_root() -> Path:
    return REPO_ROOT / load_json(ACTIVE_RUN)["run_root"]


def run_layer1_topk_eval(
    *,
    serial: str,
    runner: str,
    phone_root: str,
    checkpoint: str,
    output_dir: str,
    learning_rate: float,
    apply_update: bool,
) -> Any:
    command = (
        f"{q(runner)} --run-h11f-topk-kl-layer1-compact "
        f"{q(phone_path(phone_root, TOKEN_CACHE))} "
        f"{q(phone_path(phone_root, ASSET_DIR))} "
        f"{q(phone_path(phone_root, LAYER0_PACK))} "
        f"{q(phone_path(phone_root, LAYER1_PACK))} "
        f"{q(checkpoint)} "
        f"{q(phone_path(phone_root, TEACHER_SHARD))} "
        f"{q(output_dir)} {learning_rate:.10f} {RANK} "
        f"{'true' if apply_update else 'false'}"
    )
    return adb_shell(serial, f"rm -rf {q(output_dir)} && {command}", check=False)


def run_phone_regression_smokes(
    *,
    serial: str,
    runner: str,
    phone_root: str,
    phone_gate_root: str,
    report_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    commands: list[dict[str, Any]] = []
    remote_root = f"{phone_gate_root}/regressions"
    adb_shell(serial, f"rm -rf {q(remote_root)} && mkdir -p {q(remote_root)}", check=True)
    tests = [
        {
            "name": "g1_layer0_opencl_smoke",
            "command": (
                f"{q(runner)} --run-opencl "
                f"{q(phone_path(phone_root, LAYER0_PACK))} "
                f"{q(remote_root + '/g1_layer0_opencl_smoke')}"
            ),
            "files": ("telemetry.json",),
        },
        {
            "name": "g3_two_layer_opencl_stack_smoke",
            "command": (
                f"{q(runner)} --run-opencl-stack "
                f"{q(phone_path(phone_root, LAYER0_PACK))} "
                f"{q(phone_path(phone_root, LAYER1_PACK))} "
                f"{q(remote_root + '/g3_two_layer_opencl_stack_smoke')}"
            ),
            "files": ("telemetry.json",),
        },
        {
            "name": "g8_rank4_distill_compact_smoke",
            "command": (
                f"{q(runner)} --run-g8-distill-compact-rank "
                f"{q(phone_path(phone_root, TOKEN_CACHE))} "
                f"{q(phone_path(phone_root, ASSET_DIR))} "
                f"{q(phone_path(phone_root, LAYER0_PACK))} "
                f"{q(phone_path(phone_root, LAYER1_PACK))} "
                f"{q(phone_path(phone_root, RANK4_BASE_CHECKPOINT))} "
                f"{q(remote_root + '/g8_rank4_distill_compact_smoke')} "
                "0.01 4"
            ),
            "files": ("telemetry.json", "artifact_manifest.json", "replay_manifest.json", "checkpoint/manifest.json"),
        },
        {
            "name": "post_layer0_topk_regression_smoke",
            "command": (
                f"{q(runner)} --run-h11f-topk-kl-compact "
                f"{q(phone_path(phone_root, TOKEN_CACHE))} "
                f"{q(phone_path(phone_root, ASSET_DIR))} "
                f"{q(phone_path(phone_root, LAYER0_PACK))} "
                f"{q(phone_path(phone_root, LAYER1_PACK))} "
                f"{q(phone_path(phone_root, BASE_CHECKPOINT))} "
                f"{q(phone_path(phone_root, TEACHER_SHARD))} "
                f"{q(remote_root + '/post_layer0_topk_regression_smoke')} "
                "0.0000000000 16 false"
            ),
            "files": ("telemetry.json", "replay_manifest.json", "checkpoint/manifest.json"),
        },
    ]
    results: list[dict[str, Any]] = []
    local_root = report_dir / "regressions" / "phone_smokes"
    for test in tests:
        started = utc_now()
        completed = adb_shell(serial, test["command"], check=False)
        commands.append(command_log_entry(f"regression {test['name']}", completed))
        local_test = local_root / test["name"]
        remote_dir = f"{remote_root}/{test['name']}"
        pulled: list[str] = []
        for name in test["files"]:
            local_name = "checkpoint_manifest.json" if name == "checkpoint/manifest.json" else name
            local_path = local_test / local_name
            if adb_pull(serial, f"{remote_dir}/{name}", local_path, check=False):
                pulled.append(rel(local_path))
        telemetry_path = local_test / "telemetry.json"
        telemetry = load_json(telemetry_path) if telemetry_path.exists() else {}
        results.append(
            {
                "name": test["name"],
                "status": "pass" if completed.returncode == 0 and telemetry_path.exists() else "fail",
                "started_at_utc": started,
                "ended_at_utc": utc_now(),
                "returncode": completed.returncode,
                "phone_output_dir": remote_dir,
                "pulled_artifacts": pulled,
                "telemetry_summary": {
                    "schema_version": telemetry.get("schema_version"),
                    "model_id": telemetry.get("model_id"),
                    "revision": telemetry.get("revision"),
                    "backend": telemetry.get("backend"),
                    "layer_backend": telemetry.get("layer_backend"),
                    "adapter_backend": telemetry.get("adapter_backend"),
                    "trainable_scope": telemetry.get("trainable_scope"),
                    "loss_topk_kl": telemetry.get("loss_topk_kl"),
                    "loss_half_mse": telemetry.get("loss_half_mse"),
                    "max_rss_kb": telemetry.get("max_rss_kb"),
                },
            }
        )
    summary = {
        "schema_version": "phase13_p13e_phone_regression_smokes_v1",
        "status": "pass" if all(item["status"] == "pass" for item in results) else "fail",
        "phone_regression_root": remote_root,
        "tests": results,
    }
    write_json(report_dir / "regressions" / "phone_smokes" / "summary.json", summary)
    return summary, commands


def choose_probe_coordinates() -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    probes: list[dict[str, Any]] = []
    for tensor, count in (("adapter_a", 4), ("adapter_b", 4)):
        selected: set[int] = set()
        while len(selected) < count:
            selected.add(rng.randrange(HIDDEN * RANK))
        for index in sorted(selected):
            probes.append({"tensor": tensor, "index": index, "epsilon": EPSILON})
    return probes


def write_artifact_manifest(report_dir: Path) -> None:
    entries: list[dict[str, Any]] = []
    for path in sorted(report_dir.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            entries.append({"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_json(
        report_dir / "artifact_manifest.json",
        {
            "schema_version": "phase13_p13e_artifact_manifest_v1",
            "created_at_utc": utc_now(),
            "artifacts": entries,
        },
    )


def update_phase13_status(run_root: Path, status: str, gate_result_path: Path) -> None:
    status_path = run_root / "phase13_gate_status.json"
    phase_status = load_json(status_path)
    phase_status["gate_status"]["P13-E"] = status
    phase_status["current_gate"] = "P13-F" if status == "pass" else "P13-E"
    phase_status["latest_gate_result"] = rel(gate_result_path)
    phase_status["updated_at_utc"] = utc_now()
    write_json(status_path, phase_status)
    active = load_json(ACTIVE_RUN)
    active["current_gate"] = phase_status["current_gate"]
    active["updated_at_utc"] = utc_now()
    write_json(ACTIVE_RUN, active)


def update_gpd_state(status: str, gate_result_path: Path, pass_count: int) -> None:
    if status != "pass":
        return
    gate_rel = rel(gate_result_path)
    state_path = REPO_ROOT / ".gpd/state.json"
    state = load_json(state_path)
    desc = (
        f"P13-E passed at {gate_rel}: a second Gemma-compatible post-layer1 rank16 residual adapter "
        f"site ran phone-side forward/backward/update, {pass_count} finite-difference checks passed, "
        "and G1/G3/G8/post-layer0 smoke reruns passed."
    )
    state["position"]["last_activity"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    state["position"]["last_activity_desc"] = desc
    state["position"]["last_activity_description"] = desc
    state["position"]["status"] = "Phase 13 execution in progress; P13-A through P13-E passed; next gate is P13-F Gemma-compatible HTP or hard falsification"
    state["session"]["stopped_at"] = (
        "P13-E post-layer1 adapter site passed; continue with P13-F Gemma-compatible HTP artifact or hard falsification. "
        "Do not run P13-H until P13-F and P13-G also have exact pass/fail/fallback artifacts."
    )
    todos = [
        item for item in state.get("pending_todos", [])
        if "P13-E" not in item and "second Gemma-compatible trainable site" not in item
    ]
    next_todo = "Execute P13-F next: attempt a Gemma-compatible hidden-2560 HTP context or record the exact QAIRT/compiler blocker."
    if next_todo not in todos:
        todos.insert(0, next_todo)
    state["pending_todos"] = todos
    result = (
        f"P13-E second-site adapter passed: {gate_rel}. The new post-layer1 rank16 residual site "
        f"updated on phone and passed {pass_count} sampled finite-difference checks; G1/G3/G8/post-layer0 smokes passed."
    )
    if result not in state.setdefault("intermediate_results", []):
        state["intermediate_results"].append(result)
    state["_synced_at"] = utc_now()
    write_json(state_path, state)

    state_md = REPO_ROOT / ".gpd/STATE.md"
    text = state_md.read_text(encoding="utf-8")
    text = text.replace(
        "**Status:** Phase 13 execution in progress; P13-A through P13-D passed; next gate is P13-E multi-site Gemma adapter",
        "**Status:** Phase 13 execution in progress; P13-A through P13-E passed; next gate is P13-F Gemma-compatible HTP or hard falsification",
    )
    marker = "\n## Session Continuity\n"
    entry = (
        f"- P13-E second Gemma-compatible adapter site passed: `{gate_rel}`. A post-layer1 "
        f"rank16 residual adapter ran phone-side forward/backward/update, passed `{pass_count}` "
        "finite-difference checks, and preserved G1/G3/G8/post-layer0 smoke paths.\n"
    )
    if entry not in text and marker in text:
        text = text.replace(marker, entry + marker)
    text = text.replace(
        "- Execute P13-E next: implement or exactly falsify the smallest real second\n"
        "  Gemma-compatible trainable site.\n",
        "- Execute P13-F next: attempt a Gemma-compatible hidden-2560 HTP context or\n"
        "  record the exact QAIRT/compiler blocker.\n",
    )
    text = text.replace(
        "**Stopped at:** P13-D expanded gradient parity passed; continue with P13-E\n"
        "multi-site Gemma adapter or exact falsification. Do not run P13-H until P13-E\n"
        "through P13-G have exact pass/fail/fallback artifacts.",
        "**Stopped at:** P13-E post-layer1 adapter site passed; continue with P13-F\n"
        "Gemma-compatible HTP artifact or hard falsification. Do not run P13-H until\n"
        "P13-F and P13-G have exact pass/fail/fallback artifacts.",
    )
    state_md.write_text(text, encoding="utf-8")

    with (REPO_ROOT / ".gpd/runlog.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "ts": utc_now(),
                    "event": "phase13_p13e_post_layer1_adapter_site_passed",
                    "project": "polymath-gemma4-snapdragon-megakernel",
                    "status": "pass",
                    "branch": "gemma4-megakernel-native-training",
                    "evidence": gate_rel,
                    "note": (
                        f"P13-E added and validated a second Gemma-compatible post-layer1 rank16 residual adapter site; "
                        f"{pass_count} finite-difference checks and G1/G3/G8/post-layer0 smokes passed."
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
    parser.add_argument("--layer-runner", type=Path, default=DEFAULT_LAYER_RUNNER)
    args = parser.parse_args()

    run_root = active_run_root()
    run_id = load_json(ACTIVE_RUN)["run_id"]
    report_dir = run_root / "P13-E-layer1-adapter-site"
    report_dir.mkdir(parents=True, exist_ok=True)
    phone_gate_root = f"{args.phone_root}/phase13/{run_id}/p13e"
    commands: list[dict[str, Any]] = []
    blockers: list[str] = []

    required_paths = [
        phone_path(args.phone_root, TOKEN_CACHE),
        phone_path(args.phone_root, TEACHER_SHARD),
        phone_path(args.phone_root, ASSET_DIR),
        phone_path(args.phone_root, LAYER0_PACK),
        phone_path(args.phone_root, LAYER1_PACK),
        phone_path(args.phone_root, BASE_CHECKPOINT),
        phone_path(args.phone_root, RANK4_BASE_CHECKPOINT),
    ]
    for path in required_paths:
        if adb_shell(args.serial, f"test -e {q(path)}", check=False).returncode != 0:
            blockers.append(f"missing phone path: {path}")

    deploy: dict[str, Any] = {}
    base_record: dict[str, Any] = {}
    probe_results: list[dict[str, Any]] = []
    regression_summary: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="phase13_p13e_") as tmp_name:
        tmp = Path(tmp_name)
        if not blockers:
            deploy = deploy_layer_runner(args.serial, phone_gate_root, args.layer_runner)
            write_json(report_dir / "binary_deploy_manifest.json", deploy)
            runner = f"{phone_gate_root}/bin/gemma4_layer_runner"
            checkpoint = phone_path(args.phone_root, BASE_CHECKPOINT)
            local_base = tmp / "base"
            local_post = tmp / "post"
            base_payload = pull_checkpoint(args.serial, checkpoint, local_base, RANK)
            base_out = f"{phone_gate_root}/layer1_base_update"
            completed = run_layer1_topk_eval(
                serial=args.serial,
                runner=runner,
                phone_root=args.phone_root,
                checkpoint=checkpoint,
                output_dir=base_out,
                learning_rate=BASE_LR,
                apply_update=True,
            )
            commands.append(command_log_entry("post-layer1 base phone update", completed))
            if completed.returncode != 0:
                blockers.append("post-layer1 base update failed")
            else:
                for remote, local in (
                    ("telemetry.json", report_dir / "layer1_base_update" / "telemetry.json"),
                    ("checkpoint/manifest.json", report_dir / "layer1_base_update" / "checkpoint_manifest.json"),
                    ("replay_manifest.json", report_dir / "layer1_base_update" / "replay_manifest.json"),
                    ("artifact_manifest.json", report_dir / "layer1_base_update" / "runner_artifact_manifest.json"),
                ):
                    adb_pull(args.serial, f"{base_out}/{remote}", local, check=True)
                pull_checkpoint(args.serial, f"{base_out}/checkpoint", local_post, RANK)
                pre_a = base_payload["adapter_a"]
                pre_b = base_payload["adapter_b"]
                post_a = read_f32(local_post / "adapter_a.f32.bin", HIDDEN * RANK)
                post_b = read_f32(local_post / "adapter_b.f32.bin", HIDDEN * RANK)
                grad_a = array.array("f", ((float(pre_a[i]) - float(post_a[i])) / BASE_LR for i in range(len(pre_a))))
                grad_b = array.array("f", ((float(pre_b[i]) - float(post_b[i])) / BASE_LR for i in range(len(pre_b))))
                telemetry = load_json(report_dir / "layer1_base_update" / "telemetry.json")
                base_record = {
                    "phone_output_dir": base_out,
                    "telemetry": telemetry,
                    "inferred_gradient_l2": {"adapter_a": l2(grad_a), "adapter_b": l2(grad_b)},
                    "checkpoint_delta_l2_local": {
                        "adapter_a": math.sqrt(sum((float(post_a[i]) - float(pre_a[i])) ** 2 for i in range(len(pre_a)))),
                        "adapter_b": math.sqrt(sum((float(post_b[i]) - float(pre_b[i])) ** 2 for i in range(len(pre_b)))),
                    },
                }
                probes = choose_probe_coordinates()
                write_json(
                    report_dir / "predeclared_layer1_probe_plan.json",
                    {
                        "schema_version": "phase13_p13e_layer1_probe_plan_v1",
                        "declared_at_utc": utc_now(),
                        "seed": SEED,
                        "adapter_site": "post_layer1",
                        "rank": RANK,
                        "epsilon": EPSILON,
                        "pass_rule": {
                            "relative_error_max": REL_TOL,
                            "absolute_error_max": ABS_TOL,
                            "sign_required_when_abs_analytic_gradient_gte": SIGN_THRESHOLD,
                        },
                        "probes": probes,
                    },
                )
                for ordinal, probe in enumerate(probes):
                    losses: dict[str, float] = {}
                    eval_records: dict[str, Any] = {}
                    for sign_name, sign in (("minus", -1), ("plus", 1)):
                        local_ckpt = tmp / "fd" / f"{ordinal:03d}_{sign_name}" / "checkpoint"
                        make_perturbed_checkpoint(
                            base_a=pre_a,
                            base_b=pre_b,
                            probe=probe,
                            sign=sign,
                            local_dir=local_ckpt,
                        )
                        remote_ckpt = f"{phone_gate_root}/fd_checkpoints/probe_{ordinal:03d}_{sign_name}"
                        adb_shell(args.serial, f"rm -rf {q(remote_ckpt)} && mkdir -p {q(remote_ckpt)}", check=True)
                        adb_push(args.serial, local_ckpt / "adapter_a.f32.bin", f"{remote_ckpt}/adapter_a.f32.bin")
                        adb_push(args.serial, local_ckpt / "adapter_b.f32.bin", f"{remote_ckpt}/adapter_b.f32.bin")
                        remote_out = f"{phone_gate_root}/fd_evals/probe_{ordinal:03d}_{sign_name}"
                        completed = run_layer1_topk_eval(
                            serial=args.serial,
                            runner=runner,
                            phone_root=args.phone_root,
                            checkpoint=remote_ckpt,
                            output_dir=remote_out,
                            learning_rate=0.0,
                            apply_update=False,
                        )
                        commands.append(command_log_entry(f"layer1 finite difference {ordinal:03d} {sign_name}", completed))
                        if completed.returncode != 0:
                            blockers.append(f"layer1 finite-difference eval failed for probe {ordinal:03d} {sign_name}")
                            continue
                        local_eval = report_dir / "evals" / f"probe_{ordinal:03d}_{sign_name}" / "telemetry.json"
                        adb_pull(args.serial, f"{remote_out}/telemetry.json", local_eval, check=True)
                        eval_telemetry = load_json(local_eval)
                        losses[sign_name] = float(eval_telemetry["loss_topk_kl"])
                        eval_records[sign_name] = {
                            "phone_output_dir": remote_out,
                            "local_telemetry": rel(local_eval),
                            "loss_topk_kl": losses[sign_name],
                        }
                    if "plus" not in losses or "minus" not in losses:
                        continue
                    gradient = grad_a if probe["tensor"] == "adapter_a" else grad_b
                    analytic = float(gradient[int(probe["index"])])
                    finite_diff = (losses["plus"] - losses["minus"]) / (2.0 * EPSILON)
                    passed, error_payload = result_passes(analytic, finite_diff)
                    probe_results.append(
                        {
                            "ordinal": ordinal,
                            **probe,
                            "analytic_gradient_from_phone_sgd_delta": analytic,
                            "finite_difference_gradient": finite_diff,
                            "passed": passed,
                            **error_payload,
                            "evals": eval_records,
                        }
                    )
                regression_summary, regression_commands = run_phone_regression_smokes(
                    serial=args.serial,
                    runner=runner,
                    phone_root=args.phone_root,
                    phone_gate_root=phone_gate_root,
                    report_dir=report_dir,
                )
                commands.extend(regression_commands)

    pass_count = sum(1 for item in probe_results if item["passed"])
    fail_count = len(probe_results) - pass_count
    telemetry = base_record.get("telemetry", {})
    if telemetry.get("adapter_site") != "post_layer1":
        blockers.append("layer1 telemetry did not identify adapter_site=post_layer1")
    if telemetry.get("adapter_input_source") != "layer1_output":
        blockers.append("layer1 telemetry did not identify adapter_input_source=layer1_output")
    if telemetry.get("trainable_scope") != "post_layer1_rank16_residual_adapter":
        blockers.append("layer1 telemetry trainable_scope mismatch")
    if telemetry.get("hidden_state_fixtures_consumed") != []:
        blockers.append("layer1 site consumed hidden-state fixtures")
    if float(telemetry.get("combined_gradient_l2", 0.0) or 0.0) <= 0.0:
        blockers.append("layer1 combined gradient L2 was not positive")
    deltas = telemetry.get("checkpoint_delta_l2", {})
    if float(deltas.get("adapter_a", 0.0) or 0.0) <= 0.0 or float(deltas.get("adapter_b", 0.0) or 0.0) <= 0.0:
        blockers.append("layer1 checkpoint did not mutate both adapter tensors")
    if int(telemetry.get("max_rss_kb", 0) or 0) > MEMORY_BUDGET_KB:
        blockers.append("layer1 memory budget exceeded")
    if len(probe_results) != PROBE_COUNT or pass_count != PROBE_COUNT:
        blockers.append(f"layer1 finite-difference parity passed {pass_count}/{PROBE_COUNT} probes")
    if regression_summary.get("status") != "pass":
        blockers.append("phone regression smokes did not all pass")

    summary = {
        "schema_version": "phase13_p13e_layer1_adapter_summary_v1",
        "created_at_utc": utc_now(),
        "run_id": run_id,
        "phone_gate_root": phone_gate_root,
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "adapter_site": "post_layer1",
        "rank": RANK,
        "memory_budget_kb": MEMORY_BUDGET_KB,
        "base_record": base_record,
        "probe_count": len(probe_results),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "probe_results": probe_results,
        "regression_summary": regression_summary,
        "source_commit": source_commit(),
        "source_tree_dirty": source_dirty(),
    }
    write_json(report_dir / "layer1_adapter_summary.json", summary)

    status = "pass" if not blockers else "fail"
    gate = {
        "schema_version": "phase13_p13e_gate_result_v1",
        "gate": "P13-E-layer1-adapter-site",
        "run_id": run_id,
        "status": status,
        "started_at_utc": utc_now(),
        "ended_at_utc": utc_now(),
        "blockers": blockers,
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "phone_gate_root": phone_gate_root,
        "adapter_site": "post_layer1",
        "trainable_scope": telemetry.get("trainable_scope"),
        "rank": RANK,
        "loss_topk_kl": telemetry.get("loss_topk_kl"),
        "combined_gradient_l2": telemetry.get("combined_gradient_l2"),
        "checkpoint_delta_l2": telemetry.get("checkpoint_delta_l2"),
        "max_rss_kb": telemetry.get("max_rss_kb"),
        "finite_difference_pass_count": pass_count,
        "finite_difference_probe_count": len(probe_results),
        "regression_smokes_status": regression_summary.get("status"),
        "promoted_claims": [
            "A second Gemma-compatible post-layer1 rank16 residual adapter site ran phone-side forward/backward/update.",
            f"Post-layer1 site passed {pass_count} sampled finite-difference gradient checks.",
            "G1/G3/G8/post-layer0 smoke paths passed with the patched runner.",
        ]
        if status == "pass"
        else [],
        "nonclaims": [
            "P13-E does not prove simultaneous two-site training.",
            "P13-E does not prove the layer1 site improves heldout quality.",
            "P13-E does not validate HTP backprop or heterogeneous training.",
        ],
    }
    write_json(report_dir / "gate_result.json", gate)
    write_text(report_dir / "blockers.md", "- None.\n" if not blockers else "".join(f"- {item}\n" for item in blockers))
    write_text(
        report_dir / "falsifier_report.md",
        "# P13-E Falsifier Report\n\n"
        f"- Gate status: {status}.\n"
        f"- Adapter site: post_layer1; finite-difference checks: {pass_count}/{PROBE_COUNT}.\n"
        f"- Regression smokes: {regression_summary.get('status')}.\n"
        "- Simultaneous two-site training: not claimed.\n"
        "- HTP backprop: not claimed.\n",
    )
    write_text(report_dir / "commands.log", "\n".join(json.dumps(item, sort_keys=True) for item in commands) + "\n")
    write_artifact_manifest(report_dir)
    update_phase13_status(run_root, status, report_dir / "gate_result.json")
    update_gpd_state(status, report_dir / "gate_result.json", pass_count)

    print(json.dumps({"status": status, "gate_result": rel(report_dir / "gate_result.json")}, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

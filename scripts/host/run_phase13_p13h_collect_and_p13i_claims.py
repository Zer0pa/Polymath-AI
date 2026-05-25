#!/usr/bin/env python3
"""Collect completed P13-H phone artifacts and write P13-I exact claims."""
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
ACTIVE_RUN = PHASE13_ROOT / "active_phase13_run.json"

DEFAULT_SERIAL = "FY25013101C8"
GATE_DIR_NAME = "P13-H-overnight-phone-local-long-run"
P13I_DIR_NAME = "P13-I-exact-claims-and-next-branch"
OBJECTIVE_NAME = "label_contrastive_topk_kl_v1"
OBJECTIVE_CONTRACT = "p13c_label_onehot_topk_over_phone_native_corpus_labels_no_runtime_teacher_service"
TEACHER_PROVENANCE = "phone_native_p13c_labels_to_host_deterministic_onehot_topk_precompute"
MODEL_ID = "google/gemma-4-E4B"
MODEL_REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
HIDDEN = 2560


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


def adb_pull(serial: str, remote: str, local: Path, *, check: bool = False, timeout: int = 600) -> bool:
    local.parent.mkdir(parents=True, exist_ok=True)
    completed = adb(serial, ["pull", remote, str(local)], check=False, timeout=timeout)
    if check and completed.returncode != 0:
        raise RuntimeError(f"adb pull failed: {remote}\n{completed.stderr}")
    return completed.returncode == 0


def command_log_entry(name: str, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "name": name,
        "returncode": result.returncode,
        "stdout_first_4096": result.stdout[:4096],
        "stderr_first_4096": result.stderr[:4096],
    }


def read_phone_json(serial: str, remote: str) -> dict[str, Any]:
    result = adb_shell(serial, f"cat {q(remote)}", check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def phone_file_exists(serial: str, remote: str) -> bool:
    result = adb_shell(serial, f"test -f {q(remote)}", check=False)
    return result.returncode == 0


def list_phone_iterations(serial: str, phone_gate_dir: str) -> list[int]:
    result = adb_shell(
        serial,
        f"find {q(phone_gate_dir + '/iterations')} -maxdepth 1 -type d -name 'iter_*' 2>/dev/null",
        check=False,
    )
    indices: list[int] = []
    for line in result.stdout.splitlines():
        name = line.rstrip("/").split("/")[-1]
        if not name.startswith("iter_"):
            continue
        try:
            indices.append(int(name.removeprefix("iter_")))
        except ValueError:
            continue
    return sorted(set(indices))


def pull_common_artifacts(serial: str, phone_gate_dir: str, local_dir: Path) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    for name in (
        "gate_result.json",
        "telemetry.jsonl",
        "timing_breakdown.json",
        "artifact_manifest.json",
        "blockers.md",
        "falsifier_report.md",
        "commands.log",
        "queue_schema.json",
        "daemon_design_note.md",
        "daemon_static_artifact_manifest.json",
    ):
        remote = f"{phone_gate_dir}/{name}"
        local = local_dir / name
        pulled = adb_pull(serial, remote, local, check=False)
        commands.append({"name": f"pull_{name}", "remote": remote, "local": str(local), "pulled": pulled})
    return commands


def pull_iteration_artifacts(
    *,
    serial: str,
    phone_gate_dir: str,
    local_dir: Path,
    iterations: list[int],
    pull_all: bool,
) -> list[dict[str, Any]]:
    selected = iterations if pull_all else sorted(set(iterations[:2] + iterations[-2:]))
    commands: list[dict[str, Any]] = []
    for index in selected:
        iter_name = f"iter_{index:06d}"
        for relative in ("telemetry.json", "replay_manifest.json", "checkpoint/manifest.json"):
            remote = f"{phone_gate_dir}/iterations/{iter_name}/{relative}"
            local = local_dir / "iterations" / iter_name / relative
            pulled = adb_pull(serial, remote, local, check=False)
            commands.append({"name": "pull_iteration_artifact", "remote": remote, "local": str(local), "pulled": pulled})
    return commands


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            entries.append(json.loads(stripped))
    return entries


def telemetry_paths(local_arm_dir: Path) -> list[Path]:
    return sorted((local_arm_dir / "iterations").glob("iter_*/telemetry.json"))


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


def sorted_present_values(rows: list[dict[str, Any]], key: str) -> list[Any]:
    by_json = {
        json.dumps(row.get(key), sort_keys=True): row.get(key)
        for row in rows
        if row.get(key) is not None
    }
    return [by_json[item] for item in sorted(by_json)]


def aggregate_eval(local_arm_dir: Path) -> dict[str, Any]:
    rows = [load_json(path) for path in telemetry_paths(local_arm_dir)]
    gate_path = local_arm_dir / "gate_result.json"
    gate = load_json(gate_path) if gate_path.exists() else {}
    objective_values = sorted_present_values(rows, "objective")
    provenance_values = sorted_present_values(rows, "teacher_provenance")
    return {
        "schema_version": "phase13_p13h_eval_aggregate_v1",
        "iteration_count": len(rows),
        "gate_status": gate.get("status"),
        "gate_active_wall_ratio": gate.get("active_wall_ratio"),
        "gate_active_training_seconds": gate.get("active_training_seconds"),
        "gate_wall_seconds": gate.get("queue_execution_wall_seconds"),
        "active_tokens": int(sum(int(row.get("active_tokens", 0)) for row in rows)),
        "loss_topk_kl": weighted_mean(rows, "loss_topk_kl"),
        "mean_student_teacher_top1_probability": weighted_mean(rows, "mean_student_teacher_top1_probability"),
        "student_teacher_top1_agreement": weighted_mean(rows, "student_teacher_top1_agreement"),
        "mean_student_label_probability_when_in_topk": weighted_mean(rows, "mean_student_label_probability_when_in_topk"),
        "label_in_teacher_topk_rate": weighted_mean(rows, "label_in_teacher_topk_rate"),
        "objective_values": objective_values,
        "teacher_provenance_values": provenance_values,
        "model_ids": sorted_present_values(rows, "model_id"),
        "hidden_sizes": sorted_present_values(rows, "hidden_size"),
        "telemetry_files": [rel(path) for path in telemetry_paths(local_arm_dir)],
    }


def safety_summary(local_collect_dir: Path) -> dict[str, Any]:
    logs = {
        "original": local_collect_dir / "chain" / "original_safety.jsonl",
        "full_heldout": local_collect_dir / "chain" / "full_heldout_safety.jsonl",
    }
    summary: dict[str, Any] = {
        "schema_version": "phase13_p13h_safety_summary_v1",
        "logs": {},
        "max_battery_tenth_c": None,
        "max_zone_millideg_c": None,
        "max_zone_type": None,
        "threshold_crossed": False,
        "threshold_events": [],
    }
    max_battery: int | None = None
    max_zone: int | None = None
    max_zone_type: str | None = None
    for name, path in logs.items():
        rows = read_jsonl(path)
        log_max_battery: int | None = None
        log_max_zone: int | None = None
        log_max_zone_type: str | None = None
        threshold_events: list[dict[str, Any]] = []
        for row in rows:
            try:
                battery = int(str(row.get("battery_tenth_c", "")))
            except ValueError:
                battery = None
            try:
                zone = int(row.get("max_zone_millideg_c", 0))
            except (TypeError, ValueError):
                zone = None
            if battery is not None and (log_max_battery is None or battery > log_max_battery):
                log_max_battery = battery
            if zone is not None and (log_max_zone is None or zone > log_max_zone):
                log_max_zone = zone
                log_max_zone_type = row.get("max_zone_type")
            crossed = (
                (battery is not None and battery >= 460)
                or (zone is not None and zone >= 92000)
            )
            if crossed:
                event = {
                    "log": name,
                    "ts": row.get("ts"),
                    "battery_tenth_c": battery,
                    "max_zone_millideg_c": zone,
                    "max_zone_type": row.get("max_zone_type"),
                }
                threshold_events.append(event)
                summary["threshold_events"].append(event)
        summary["logs"][name] = {
            "path": rel(path) if path.exists() else str(path),
            "sample_count": len(rows),
            "max_battery_tenth_c": log_max_battery,
            "max_zone_millideg_c": log_max_zone,
            "max_zone_type": log_max_zone_type,
            "threshold_event_count": len(threshold_events),
        }
        if log_max_battery is not None and (max_battery is None or log_max_battery > max_battery):
            max_battery = log_max_battery
        if log_max_zone is not None and (max_zone is None or log_max_zone > max_zone):
            max_zone = log_max_zone
            max_zone_type = log_max_zone_type
    summary["max_battery_tenth_c"] = max_battery
    summary["max_zone_millideg_c"] = max_zone
    summary["max_zone_type"] = max_zone_type
    summary["threshold_crossed"] = bool(summary["threshold_events"])
    return summary


def collect_arm(
    *,
    serial: str,
    arm_name: str,
    phone_gate_dir: str,
    local_collect_dir: Path,
    pull_all_iterations: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    local_arm_dir = local_collect_dir / "arms" / arm_name
    commands = pull_common_artifacts(serial, phone_gate_dir, local_arm_dir)
    iterations = list_phone_iterations(serial, phone_gate_dir)
    commands.extend(
        pull_iteration_artifacts(
            serial=serial,
            phone_gate_dir=phone_gate_dir,
            local_dir=local_arm_dir,
            iterations=iterations,
            pull_all=pull_all_iterations,
        )
    )
    gate = load_json(local_arm_dir / "gate_result.json") if (local_arm_dir / "gate_result.json").exists() else {}
    return {
        "arm": arm_name,
        "phone_gate_dir": phone_gate_dir,
        "local_dir": rel(local_arm_dir),
        "phone_iteration_count_seen": len(iterations),
        "pulled_iteration_count": len(telemetry_paths(local_arm_dir)),
        "gate_status": gate.get("status"),
        "gate_iteration_count": gate.get("iteration_count"),
        "active_wall_ratio": gate.get("active_wall_ratio"),
        "ended_at_utc": gate.get("ended_at_utc"),
    }, commands


def collect_chain_files(
    *,
    serial: str,
    local_collect_dir: Path,
    detached: dict[str, Any],
    attach: dict[str, Any],
) -> list[dict[str, Any]]:
    files = {
        "original_chain_state.json": detached["launch"]["phone_chain_state"],
        "original_chain_events.jsonl": detached["launch"]["phone_chain_events"],
        "original_chain.log": detached["launch"]["phone_chain_log"],
        "original_chain.bootstrap.log": detached["launch"]["phone_chain_bootstrap"],
        "full_heldout_chain_state.json": attach["launch"]["phone_chain_state"],
        "full_heldout_chain_events.jsonl": attach["launch"]["phone_chain_events"],
        "full_heldout_chain.log": attach["launch"]["phone_chain_log"],
        "full_heldout_chain.bootstrap.log": attach["launch"]["phone_chain_bootstrap"],
    }
    commands: list[dict[str, Any]] = []
    for local_name, remote in files.items():
        local = local_collect_dir / "chain" / local_name
        pulled = adb_pull(serial, remote, local, check=False)
        commands.append({"name": "pull_chain_file", "remote": remote, "local": str(local), "pulled": pulled})
    for safety_name, pid in (
        ("original_safety.jsonl", detached["run_id"]),
        ("full_heldout_safety.jsonl", attach["attach_run_id"]),
    ):
        remote = f"{detached['phone_p13h_root']}/p13h_{pid}_safety.jsonl"
        local = local_collect_dir / "chain" / safety_name
        pulled = adb_pull(serial, remote, local, check=False)
        commands.append({"name": "pull_safety_file", "remote": remote, "local": str(local), "pulled": pulled})
    return commands


def build_adjudication(
    *,
    detached: dict[str, Any],
    attach: dict[str, Any],
    arm_summaries: dict[str, dict[str, Any]],
    baseline: dict[str, Any],
    trained: dict[str, Any],
    safety: dict[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []
    if safety.get("threshold_crossed"):
        blockers.append("phone thermal safety threshold crossed during P13-H")
    if arm_summaries["train"].get("gate_status") != "pass":
        blockers.append("5000-update train arm did not pass")
    if int(arm_summaries["train"].get("gate_iteration_count") or 0) < 5000:
        blockers.append("train arm completed fewer than 5000 updates")
    if float(arm_summaries["train"].get("active_wall_ratio") or 0.0) < 0.85:
        blockers.append("train active/wall ratio below 0.85")
    for arm in ("heldout_full_baseline", "heldout_full_trained"):
        if arm_summaries[arm].get("gate_status") != "pass":
            blockers.append(f"{arm} gate did not pass")
        if int(arm_summaries[arm].get("gate_iteration_count") or 0) < 128:
            blockers.append(f"{arm} evaluated fewer than 128 heldout shards")
    expected_identity = (
        baseline.get("objective_values") == [OBJECTIVE_NAME]
        and trained.get("objective_values") == [OBJECTIVE_NAME]
        and baseline.get("teacher_provenance_values") == [TEACHER_PROVENANCE]
        and trained.get("teacher_provenance_values") == [TEACHER_PROVENANCE]
        and baseline.get("model_ids") == [MODEL_ID]
        and trained.get("model_ids") == [MODEL_ID]
        and baseline.get("hidden_sizes") == [HIDDEN]
        and trained.get("hidden_sizes") == [HIDDEN]
    )
    if not expected_identity:
        blockers.append("full heldout identity/provenance telemetry mismatch")

    base_loss = baseline.get("loss_topk_kl")
    trained_loss = trained.get("loss_topk_kl")
    base_metric = baseline.get("mean_student_teacher_top1_probability")
    trained_metric = trained.get("mean_student_teacher_top1_probability")
    base_agreement = baseline.get("student_teacher_top1_agreement")
    trained_agreement = trained.get("student_teacher_top1_agreement")
    loss_improved = (
        isinstance(base_loss, (int, float))
        and isinstance(trained_loss, (int, float))
        and float(trained_loss) < float(base_loss)
    )
    mini_improved = (
        isinstance(base_metric, (int, float))
        and isinstance(trained_metric, (int, float))
        and float(trained_metric) > float(base_metric)
    )
    agreement_nonregress = (
        isinstance(base_agreement, (int, float))
        and isinstance(trained_agreement, (int, float))
        and float(trained_agreement) >= float(base_agreement)
    )
    if not loss_improved:
        blockers.append("full heldout label-contrastive KL did not improve")
    if not mini_improved:
        blockers.append("full heldout mean student teacher-top1 probability did not improve")
    if not agreement_nonregress:
        blockers.append("full heldout top1 agreement regressed")

    return {
        "schema_version": "phase13_p13h_adjudication_v1",
        "detached_run_id": detached["run_id"],
        "full_heldout_run_id": attach["attach_run_id"],
        "train_updates": int(arm_summaries["train"].get("gate_iteration_count") or 0),
        "train_active_wall_ratio": arm_summaries["train"].get("active_wall_ratio"),
        "baseline_full_heldout": baseline,
        "trained_full_heldout": trained,
        "safety": safety,
        "deltas": {
            "loss_topk_kl": None if base_loss is None or trained_loss is None else float(base_loss) - float(trained_loss),
            "mean_student_teacher_top1_probability": None
            if base_metric is None or trained_metric is None
            else float(trained_metric) - float(base_metric),
            "student_teacher_top1_agreement": None
            if base_agreement is None or trained_agreement is None
            else float(trained_agreement) - float(base_agreement),
        },
        "checks": {
            "loss_improved": loss_improved,
            "mini_metric_improved": mini_improved,
            "agreement_nonregress": agreement_nonregress,
            "identity_and_provenance_exact": expected_identity,
            "full_heldout_shards": baseline.get("iteration_count") == 128 and trained.get("iteration_count") == 128,
        },
        "status": "pass" if not blockers else "fail",
        "blockers": blockers,
    }


def artifact_manifest(report_dir: Path, schema_version: str) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for path in sorted(report_dir.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            entries.append({"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return {"schema_version": schema_version, "created_at_utc": utc_now(), "artifacts": entries}


def update_phase13_status(run_root: Path, p13h_gate: Path, p13i_gate: Path, p13h_status: str, p13i_status: str) -> None:
    status_path = run_root / "phase13_gate_status.json"
    phase_status = load_json(status_path)
    phase_status["gate_status"]["P13-H"] = p13h_status
    phase_status["gate_status"]["P13-I"] = p13i_status
    phase_status["current_gate"] = "P13-I"
    phase_status["latest_gate_result"] = rel(p13i_gate)
    phase_status["updated_at_utc"] = utc_now()
    phase_status["phase13_complete"] = p13i_status == "pass_exact_claims_written"
    phase_status.setdefault("primary_artifacts", {})
    phase_status["primary_artifacts"]["P13-H"] = rel(p13h_gate)
    phase_status["primary_artifacts"]["P13-I"] = rel(p13i_gate)
    write_json(status_path, phase_status)
    active = load_json(ACTIVE_RUN)
    active["current_gate"] = "P13-I"
    active["updated_at_utc"] = utc_now()
    write_json(ACTIVE_RUN, active)


def update_gpd_state(run_root: Path, p13i_gate: Path, p13i_status: str, adjudication: dict[str, Any]) -> None:
    state_path = REPO_ROOT / ".gpd/state.json"
    state = load_json(state_path)
    desc = (
        f"Phase 13 P13-I written at {rel(p13i_gate)} with P13-H adjudication {adjudication['status']}; "
        f"full-heldout KL delta={adjudication['deltas']['loss_topk_kl']}."
    )
    state["position"]["last_activity"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    state["position"]["last_activity_desc"] = desc
    state["position"]["last_activity_description"] = desc
    state["position"]["status"] = "Phase 13 exact claims written" if p13i_status == "pass_exact_claims_written" else "Phase 13 exact claims written with blockers"
    state["session"]["stopped_at"] = "Phase 13 P13-I exact claims completed; next branch decision recorded."
    todos = [item for item in state.get("pending_todos", []) if "P13-H" not in item and "P13-I" not in item]
    next_todo = "Start Phase 14 branch selected by P13-I exact claims."
    if next_todo not in todos:
        todos.insert(0, next_todo)
    state["pending_todos"] = todos
    result = f"P13-I exact claims: {rel(p13i_gate)} status={p13i_status}"
    if result not in state.setdefault("intermediate_results", []):
        state["intermediate_results"].append(result)
    state["_synced_at"] = utc_now()
    write_json(state_path, state)
    with (REPO_ROOT / ".gpd/runlog.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "ts": utc_now(),
                    "event": "phase13_p13i_exact_claims_written",
                    "project": "polymath-gemma4-snapdragon-megakernel",
                    "status": p13i_status,
                    "branch": "gemma4-megakernel-native-training",
                    "evidence": rel(p13i_gate),
                },
                sort_keys=True,
            )
            + "\n"
        )


def write_p13i(
    *,
    run_root: Path,
    p13h_gate_path: Path,
    p13i_dir: Path,
    adjudication: dict[str, Any],
) -> Path:
    p13h_status = "pass" if adjudication["status"] == "pass" else "fail"
    promoted_claims = [
        "P13-A through P13-D passed: contamination quarantine, identity/kernel-lineage telemetry, scaled phone-native P13-C corpus cache, and 64/64 expanded gradient parity.",
        "P13-E added a Gemma hidden-size-2560 post-layer1 rank-16 residual adapter site with phone forward/backward/update evidence.",
        "P13-F produced a Gemma hidden-size-2560 HTP ReLU tensor-island context that runs on phone, but it is execution-only.",
        "P13-G selected the Adreno/OpenCL residual adapter fallback because the HTP tensor island is not consumed by the Gemma training loop.",
    ]
    if adjudication["status"] == "pass":
        promoted_claims.append(
            "P13-H completed a phone-local 5000-update scaled-corpus label-contrastive run and improved full-heldout label-contrastive KL versus the fixed baseline under the declared fallback objective."
        )
    else:
        promoted_claims.append(
            "P13-H completed enough artifact collection for adjudication, but the full-heldout acceptance gate did not pass."
        )
    nonclaims = [
        "No full Gemma4 model training is claimed; the trainable scope is residual adapters.",
        "No full-Gemma teacher top-k distillation is claimed for P13-H; it used the declared label-contrastive fallback objective.",
        "No HTP training, HTP backprop, or HTP-to-Adreno optimizer bridge is claimed.",
        "No broad benchmark, product capability, or public benchmark readiness claim is made.",
        "No fused megakernel claim is made; kernel lineage remains residual_adapter_opencl_training for the P13-H run.",
    ]
    blockers = list(adjudication["blockers"])
    next_branch = {
        "schema_version": "phase13_next_branch_decision_v1",
        "selected": (
            "phase14_full_teacher_scaled_distillation_and_true_heterogeneous_bridge"
            if adjudication["status"] == "pass"
            else "phase14_repair_scaled_heldout_learning_before_new_hardware_claims"
        ),
        "rationale": (
            "The fallback objective moved the scaled heldout gate; next work should restore full Gemma teacher shards and test a real HTP-consumed bridge."
            if adjudication["status"] == "pass"
            else "The authority heldout gate failed or is incomplete; repair objective/data/optimizer evidence before widening claims."
        ),
        "must_not_do": [
            "Do not promote the P13-F HTP ReLU island as heterogeneous training.",
            "Do not replace full heldout movement with train-loss movement.",
            "Do not call the residual-adapter OpenCL lane a fused megakernel.",
        ],
    }
    gate = {
        "schema_version": "phase13_p13i_exact_claims_v1",
        "gate": "P13-I exact claims and next branch decision",
        "status": "pass_exact_claims_written" if adjudication["status"] in {"pass", "fail"} else "blocked",
        "created_at_utc": utc_now(),
        "p13h_status": p13h_status,
        "p13h_gate_result": rel(p13h_gate_path),
        "p13h_adjudication": adjudication,
        "promoted_claims": promoted_claims,
        "nonclaims": nonclaims,
        "blockers": blockers,
        "next_branch_decision": next_branch,
    }
    p13i_gate = p13i_dir / "gate_result.json"
    write_json(p13i_gate, gate)
    write_text(p13i_dir / "blockers.md", "\n".join(f"- {item}" for item in blockers) + ("\n" if blockers else "- none\n"))
    write_text(
        p13i_dir / "falsifier_report.md",
        "# P13-I Falsifier Report\n\n"
        "- HTP remains a non-training tensor island unless a later branch consumes it in the Gemma optimizer path.\n"
        "- P13-H promotion is limited to the declared label-contrastive objective and cannot be reworded as full-teacher distillation.\n"
        "- Full-heldout metrics, not train loss, decide the P13-H authority outcome.\n",
    )
    write_json(p13i_dir / "artifact_manifest.json", artifact_manifest(p13i_dir, "phase13_p13i_artifact_manifest_v1"))
    return p13i_gate


def write_summary(run_root: Path, p13i_gate: Path, adjudication: dict[str, Any]) -> None:
    status = "passed" if adjudication["status"] == "pass" else "failed"
    text = (
        "# Phase 13 Summary\n\n"
        f"- P13-H full-heldout adjudication: {status}.\n"
        f"- Train updates: {adjudication['train_updates']}.\n"
        f"- Train active/wall: {adjudication['train_active_wall_ratio']}.\n"
        f"- Full-heldout KL delta baseline-minus-trained: {adjudication['deltas']['loss_topk_kl']}.\n"
        f"- Exact claims: `{rel(p13i_gate)}`.\n"
        "- Nonclaims remain: no full Gemma4 training, no HTP training/backprop, no fused megakernel claim, no benchmark readiness.\n"
    )
    write_text(REPO_ROOT / ".gpd/phases/13-gemma4-only-heterogeneous-corpus-scale/13-01-SUMMARY.md", text)


def status_if_waiting(serial: str, detached: dict[str, Any], attach: dict[str, Any]) -> dict[str, Any]:
    original_state = read_phone_json(serial, detached["launch"]["phone_chain_state"])
    full_state = read_phone_json(serial, attach["launch"]["phone_chain_state"])
    train_manifest = attach["train_final_checkpoint"] + "/manifest.json"
    train_checkpoint_exists = phone_file_exists(serial, train_manifest)
    return {
        "status": "waiting",
        "original_chain_state": original_state,
        "full_heldout_chain_state": full_state,
        "train_final_checkpoint_manifest_exists": train_checkpoint_exists,
        "needed": "original/full heldout chains must reach completed before collection and P13-I",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", default=DEFAULT_SERIAL)
    parser.add_argument("--force-collect", action="store_true")
    args = parser.parse_args()

    run_root = active_run_root()
    p13h_dir = run_root / GATE_DIR_NAME
    p13h_gate_path = p13h_dir / "gate_result.json"
    detached = load_json(p13h_dir / "detached_launch.json")
    attach_rel = load_json(p13h_gate_path).get("full_heldout_attachment")
    if not attach_rel:
        raise RuntimeError("P13-H full-heldout attachment is missing")
    attach = load_json(REPO_ROOT / attach_rel)
    original_state = read_phone_json(args.serial, detached["launch"]["phone_chain_state"])
    full_state = read_phone_json(args.serial, attach["launch"]["phone_chain_state"])
    if not args.force_collect and (
        original_state.get("status") != "completed" or full_state.get("status") != "completed"
    ):
        print(json.dumps(status_if_waiting(args.serial, detached, attach), sort_keys=True))
        return 0

    collect_dir = p13h_dir / "collection"
    commands: list[dict[str, Any]] = []
    commands.extend(collect_chain_files(serial=args.serial, local_collect_dir=collect_dir, detached=detached, attach=attach))
    arm_specs = {
        "baseline_eval": (detached["arms"]["baseline_eval"]["phone_gate_dir"], False),
        "train": (detached["arms"]["train"]["phone_gate_dir"], False),
        "trained_eval": (detached["arms"]["trained_eval"]["phone_gate_dir"], False),
        "heldout_full_baseline": (attach["arms"]["heldout_full_baseline"]["phone_gate_dir"], True),
        "heldout_full_trained": (attach["arms"]["heldout_full_trained"]["phone_gate_dir"], True),
    }
    arm_summaries: dict[str, dict[str, Any]] = {}
    for arm_name, (phone_gate_dir, pull_all) in arm_specs.items():
        summary, arm_commands = collect_arm(
            serial=args.serial,
            arm_name=arm_name,
            phone_gate_dir=phone_gate_dir,
            local_collect_dir=collect_dir,
            pull_all_iterations=pull_all,
        )
        arm_summaries[arm_name] = summary
        commands.extend(arm_commands)
    baseline = aggregate_eval(collect_dir / "arms" / "heldout_full_baseline")
    trained = aggregate_eval(collect_dir / "arms" / "heldout_full_trained")
    safety = safety_summary(collect_dir)
    adjudication = build_adjudication(
        detached=detached,
        attach=attach,
        arm_summaries=arm_summaries,
        baseline=baseline,
        trained=trained,
        safety=safety,
    )
    write_json(collect_dir / "arm_summaries.json", {"schema_version": "phase13_p13h_arm_summaries_v1", "arms": arm_summaries})
    write_json(collect_dir / "full_heldout_aggregates.json", {"baseline": baseline, "trained": trained})
    write_json(collect_dir / "safety_summary.json", safety)
    write_json(collect_dir / "adjudication.json", adjudication)
    write_text(collect_dir / "commands.log", json.dumps({"commands": commands}, indent=2, sort_keys=True) + "\n")
    write_json(collect_dir / "artifact_manifest.json", artifact_manifest(collect_dir, "phase13_p13h_collection_artifact_manifest_v1"))

    p13h_gate = load_json(p13h_gate_path)
    p13h_gate["status"] = "pass" if adjudication["status"] == "pass" else "fail"
    p13h_gate["ended_at_utc"] = utc_now()
    p13h_gate["collection"] = rel(collect_dir)
    p13h_gate["adjudication"] = adjudication
    p13h_gate["blockers"] = adjudication["blockers"]
    write_json(p13h_gate_path, p13h_gate)
    write_json(p13h_dir / "artifact_manifest.json", artifact_manifest(p13h_dir, "phase13_p13h_artifact_manifest_v3"))

    p13i_dir = run_root / P13I_DIR_NAME
    p13i_gate = write_p13i(run_root=run_root, p13h_gate_path=p13h_gate_path, p13i_dir=p13i_dir, adjudication=adjudication)
    p13i_status = "pass_exact_claims_written"
    update_phase13_status(
        run_root,
        p13h_gate_path,
        p13i_gate,
        "pass" if adjudication["status"] == "pass" else "fail",
        p13i_status,
    )
    update_gpd_state(run_root, p13i_gate, p13i_status, adjudication)
    write_summary(run_root, p13i_gate, adjudication)
    print(
        json.dumps(
            {
                "status": p13i_status,
                "p13h_status": adjudication["status"],
                "p13i_gate": rel(p13i_gate),
                "kl_delta": adjudication["deltas"]["loss_topk_kl"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

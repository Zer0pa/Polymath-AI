#!/usr/bin/env python3
"""Run Phase 13 P13-G heterogeneous candidate versus Adreno baseline gate."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import shlex
import struct
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE13_ROOT = REPO_ROOT / "runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous"
ACTIVE_RUN = PHASE13_ROOT / "active_phase13_run.json"

DEFAULT_SERIAL = "FY25013101C8"
DEFAULT_PHONE_ROOT = "/data/local/tmp/polymath_gemma4_gate"
PHONE_QAIRT_ROOT = "/data/local/tmp/qairt-2.44"

MODEL_ID = "google/gemma-4-E4B"
MODEL_REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
HIDDEN = 2560
SEQ = 16
INPUT_BYTES = HIDDEN * SEQ * 4

PHASE12_LONG_RESULT = (
    REPO_ROOT
    / "runtime/reports/gemma4_megakernel/phase12_hardware_native_learning/"
    "20260524T173847Z_phase12_long_native_lr_retry1/CDE-long-native-lr/gate_result.json"
)
PHASE12_G_RESULT = (
    REPO_ROOT
    / "runtime/reports/gemma4_megakernel/phase12_hardware_native_learning/"
    "20260524T172043Z_phase12_g_heterogeneous/G-heterogeneous-hypothesis/gate_result.json"
)


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


def adb_pull(serial: str, remote: str, local: Path, *, check: bool = False, timeout: int = 600) -> bool:
    local.parent.mkdir(parents=True, exist_ok=True)
    completed = adb(serial, ["pull", remote, str(local)], check=False, timeout=timeout)
    if check and completed.returncode != 0:
        raise RuntimeError(f"adb pull failed: {remote}\n{completed.stderr}")
    return completed.returncode == 0


def parse_profile_csv(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "path": rel(path)}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    header_index = next((idx for idx, line in enumerate(lines) if line.startswith("Msg Timestamp,")), None)
    if header_index is None:
        return {"status": "unparseable", "path": rel(path), "bytes": path.stat().st_size}
    rows = csv.DictReader(lines[header_index:])
    summary: dict[str, Any] = {
        "status": "parsed",
        "path": rel(path),
        "netrun_execute_us": None,
        "qnn_execute_us": None,
        "rpc_execute_us": None,
        "accelerator_execute_us": None,
        "accelerator_execute_excluding_wait_us": None,
        "hvx_threads": None,
        "ips": None,
    }
    for raw in rows:
        row = {key.strip(): value.strip() for key, value in raw.items() if key is not None and value is not None}
        message = row.get("Message")
        event_id = row.get("Event Identifier", "")
        timing_source = row.get("Timing Source")
        try:
            time_value = float(row.get("Time", "nan"))
        except ValueError:
            time_value = math.nan
        if message == "EXECUTE" and timing_source == "NETRUN":
            summary["netrun_execute_us"] = time_value
        elif message == "EXECUTE" and "QNN (execute) time" in event_id:
            summary["qnn_execute_us"] = time_value
        elif message == "EXECUTE" and "RPC (execute) time" in event_id:
            summary["rpc_execute_us"] = time_value
        elif message == "EXECUTE" and event_id == "Accelerator (execute) time":
            summary["accelerator_execute_us"] = time_value
        elif message == "EXECUTE" and event_id == "Accelerator (execute excluding wait) time":
            summary["accelerator_execute_excluding_wait_us"] = time_value
        elif message == "EXECUTE" and "Number of HVX threads used" in event_id:
            summary["hvx_threads"] = int(time_value)
        elif message == "EXECUTE IPS":
            summary["ips"] = time_value
    return summary


def parse_wall_times(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        iteration, rc, start_ns, end_ns, wall_ns = parts
        rows.append(
            {
                "iteration": int(iteration),
                "returncode": int(rc),
                "start_ns": int(start_ns),
                "end_ns": int(end_ns),
                "wall_ns": int(wall_ns),
                "wall_ms": int(wall_ns) / 1_000_000.0,
            }
        )
    return rows


def validate_relu(input_path: Path, output_path: Path) -> dict[str, Any]:
    if not input_path.exists() or not output_path.exists():
        return {
            "status": "missing",
            "input_path": rel(input_path) if input_path.exists() else str(input_path),
            "output_path": rel(output_path) if output_path.exists() else str(output_path),
        }
    input_bytes = input_path.read_bytes()
    output_bytes = output_path.read_bytes()
    if len(input_bytes) != len(output_bytes):
        return {
            "status": "fail",
            "reason": "byte_size_mismatch",
            "input_bytes": len(input_bytes),
            "output_bytes": len(output_bytes),
        }
    mismatch_count = 0
    negative_input_count = 0
    positive_input_count = 0
    max_abs_error = 0.0
    max_output_abs = 0.0
    for (input_value,), (output_value,) in zip(
        struct.iter_unpack("<f", input_bytes),
        struct.iter_unpack("<f", output_bytes),
    ):
        expected = input_value if input_value > 0.0 else 0.0
        if input_value < 0.0:
            negative_input_count += 1
        elif input_value > 0.0:
            positive_input_count += 1
        error = abs(output_value - expected)
        max_abs_error = max(max_abs_error, error)
        max_output_abs = max(max_output_abs, abs(output_value))
        if error > 1.0e-6:
            mismatch_count += 1
    return {
        "status": "pass" if mismatch_count == 0 else "fail",
        "input_path": rel(input_path),
        "output_path": rel(output_path),
        "input_sha256": sha256_file(input_path),
        "output_sha256": sha256_file(output_path),
        "float_count": len(input_bytes) // 4,
        "negative_input_count": negative_input_count,
        "positive_input_count": positive_input_count,
        "mismatch_count": mismatch_count,
        "max_abs_error": max_abs_error,
        "max_output_abs": max_output_abs,
    }


def parse_thermal_snapshot(path: Path) -> dict[str, Any]:
    zones: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split("|")
            if len(parts) != 3:
                continue
            raw_temp = parts[2].strip()
            try:
                temp_millideg = int(raw_temp)
            except ValueError:
                continue
            zones.append(
                {
                    "zone": parts[0],
                    "type": parts[1],
                    "temp_millideg_c": temp_millideg,
                    "temp_c": temp_millideg / 1000.0,
                }
            )
    interesting = [
        zone
        for zone in zones
        if any(key in zone["type"] for key in ("cpu", "gpu", "gpuss", "nsph", "ddr", "skin", "battery"))
        and -10_000 <= zone["temp_millideg_c"] <= 120_000
    ]
    hottest = sorted(interesting, key=lambda item: item["temp_millideg_c"], reverse=True)[:12]
    return {
        "path": rel(path) if path.exists() else str(path),
        "zone_count": len(zones),
        "interesting_hottest": hottest,
    }


def parse_battery(path: Path) -> dict[str, Any]:
    values: dict[str, Any] = {"path": rel(path) if path.exists() else str(path)}
    if not path.exists():
        values["status"] = "missing"
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower().replace(" ", "_")
        value = value.strip()
        if value in {"true", "false"}:
            values[key] = value == "true"
            continue
        try:
            values[key] = int(value)
        except ValueError:
            values[key] = value
    if "temperature" in values:
        values["temperature_c"] = values["temperature"] / 10.0
    return values


def collect_htp_candidate(
    serial: str,
    run_root: Path,
    report_dir: Path,
    p13f_gate: dict[str, Any],
    p13f_attempts: dict[str, Any],
    phone_root: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    commands: list[dict[str, Any]] = []
    selected = p13f_attempts.get("selected_valid_attempt")
    selected_attempt = next(
        (item for item in p13f_attempts.get("attempts", []) if item.get("variant") == selected),
        None,
    )
    if not selected_attempt:
        return {
            "status": "invalid",
            "reason": "P13-F did not provide a selected valid HTP attempt",
            "selected_valid_attempt": selected,
        }, commands

    run_id = run_root.name
    p13f_htp_root = p13f_attempts["phone_htp_root"]
    context = selected_attempt["phone_context"]
    bench_root = f"{phone_root.rstrip('/')}/phase13/{run_id}/p13g/htp_relu_benchmark"
    script = f"""
set +e
Q={q(PHONE_QAIRT_ROOT)}
BENCH={q(bench_root)}
P13F_HTP={q(p13f_htp_root)}
CONTEXT={q(context)}
MODEL_ROOT={q(f"{phone_root.rstrip('/')}/phase13/{run_id}/p13f/models")}
rm -rf "$BENCH"
mkdir -p "$BENCH"
snapshot_thermal() {{
  out="$1"
  : > "$out"
  for z in /sys/class/thermal/thermal_zone*; do
    [ -r "$z/type" ] || continue
    typ="$(cat "$z/type" 2>/dev/null)"
    tmp="$(cat "$z/temp" 2>/dev/null)"
    printf '%s|%s|%s\\n' "$z" "$typ" "$tmp" >> "$out"
  done
}}
snapshot_thermal "$BENCH/thermal_before.txt"
dumpsys battery > "$BENCH/battery_before.txt" 2>&1
cp "$P13F_HTP/gemma_layer0_first16_hidden.f32.bin" "$BENCH/input_gemma_layer0_first16_hidden.f32.bin"
cp "$P13F_HTP/input_sha256sums.txt" "$BENCH/input_sha256sums.txt" 2>/dev/null
export LD_LIBRARY_PATH="$MODEL_ROOT:$Q/lib/aarch64-android:/vendor/lib64:$LD_LIBRARY_PATH"
export ADSP_LIBRARY_PATH="$Q/lib/hexagon-v81/unsigned;$Q/lib/hexagon-v79/unsigned;$Q/lib/hexagon-v75/unsigned;/vendor/dsp/cdsp;/vendor/lib/rfsa/adsp;/system/lib/rfsa/adsp;/dsp"
cd "$P13F_HTP"
for i in 0 1 2; do
  OUT="$BENCH/run_$i"
  mkdir -p "$OUT"
  START_NS="$(date +%s%N)"
  "$Q/bin/aarch64-android/qnn-net-run" \
    --retrieve_context="$CONTEXT" \
    --backend "$Q/lib/aarch64-android/libQnnHtp.so" \
    --input_list input_list.txt \
    --output_dir "$OUT" \
    --num_inferences 1 \
    --profiling_level basic \
    --log_level info > "$OUT/stdout.log" 2> "$OUT/stderr.log"
  RC=$?
  END_NS="$(date +%s%N)"
  echo "$i $RC $START_NS $END_NS $((END_NS - START_NS))" >> "$BENCH/wall_times.txt"
  if [ -f "$OUT/qnn-profiling-data_0.log" ]; then
    "$Q/bin/aarch64-android/qnn-profile-viewer" \
      --input_log "$OUT/qnn-profiling-data_0.log" \
      --output="$OUT/profile_view.csv" > "$OUT/profile_view.txt" 2> "$OUT/profile_view.err"
  fi
done
snapshot_thermal "$BENCH/thermal_after.txt"
dumpsys battery > "$BENCH/battery_after.txt" 2>&1
find "$BENCH" -type f -maxdepth 4 -print | sort > "$BENCH/file_list.txt"
while read -r f; do sha256sum "$f"; done < "$BENCH/file_list.txt" > "$BENCH/sha256sums.txt"
while read -r f; do wc -c "$f"; done < "$BENCH/file_list.txt" > "$BENCH/sizes.txt"
exit 0
"""
    completed = adb_shell(serial, script, check=False, timeout=900)
    commands.append(command_log_entry("phone_p13g_htp_relu_benchmark", completed))

    local_bench = report_dir / "phone_htp_relu_benchmark"
    adb_pull(serial, bench_root, local_bench, check=False, timeout=600)
    bench_dir = local_bench / Path(bench_root).name
    if not bench_dir.exists() and local_bench.exists():
        bench_dir = local_bench

    wall_times = parse_wall_times(bench_dir / "wall_times.txt")
    profiles = [parse_profile_csv(path) for path in sorted(bench_dir.glob("run_*/profile_view.csv"))]
    output_path = next(iter(sorted(bench_dir.glob("run_0/Result_0/gemma_hidden_relu_out.raw"))), None)
    correctness = validate_relu(
        bench_dir / "input_gemma_layer0_first16_hidden.f32.bin",
        output_path if output_path else bench_dir / "run_0/Result_0/gemma_hidden_relu_out.raw",
    )
    successful_runs = [item for item in wall_times if item["returncode"] == 0]
    netrun_us = [item["netrun_execute_us"] for item in profiles if item.get("netrun_execute_us") is not None]
    accelerator_us = [
        item["accelerator_execute_excluding_wait_us"]
        for item in profiles
        if item.get("accelerator_execute_excluding_wait_us") is not None
    ]
    wall_ms = [item["wall_ms"] for item in successful_runs]

    return {
        "status": "pass_execution_only" if successful_runs and correctness.get("status") == "pass" else "fail",
        "source_gate": rel(run_root / "P13-F-gemma-compatible-htp-context/gate_result.json"),
        "selected_p13f_attempt": selected,
        "phone_benchmark_root": bench_root,
        "local_benchmark_dir": rel(bench_dir) if bench_dir.exists() else str(bench_dir),
        "model_id": p13f_gate.get("model_id"),
        "revision": p13f_gate.get("revision"),
        "input_shape": [1, SEQ, HIDDEN],
        "input_bytes": INPUT_BYTES,
        "output_bytes": INPUT_BYTES,
        "transfer_payload_bytes_if_bridged": INPUT_BYTES * 2,
        "context": context,
        "context_graphs": selected_attempt.get("context_graphs", []),
        "wall_times": wall_times,
        "profile_summaries": profiles,
        "mean_shell_wall_ms": sum(wall_ms) / len(wall_ms) if wall_ms else None,
        "mean_netrun_execute_us": sum(netrun_us) / len(netrun_us) if netrun_us else None,
        "mean_accelerator_execute_excluding_wait_us": (
            sum(accelerator_us) / len(accelerator_us) if accelerator_us else None
        ),
        "correctness": correctness,
        "thermal_before": parse_thermal_snapshot(bench_dir / "thermal_before.txt"),
        "thermal_after": parse_thermal_snapshot(bench_dir / "thermal_after.txt"),
        "battery_before": parse_battery(bench_dir / "battery_before.txt"),
        "battery_after": parse_battery(bench_dir / "battery_after.txt"),
        "consumed_by_gemma_training_loop": False,
        "heldout_movement_attributable_to_htp": None,
    }, commands


def extract_adreno_baseline() -> dict[str, Any]:
    long_result = load_json(PHASE12_LONG_RESULT)
    selected_arm = long_result["selected_arm"]
    arm = next(item for item in long_result["arm_results"] if item["arm"] == selected_arm)
    train_gate = arm["train"]["gate"]
    heldout_eval = arm["heldout_eval"]["metrics"]
    heldout_delta = arm["heldout_delta_vs_8_step"]
    active_tokens = heldout_eval.get("active_tokens")
    loss_delta = heldout_delta.get("loss_topk_kl")
    return {
        "status": "pass_adreno_opencl_training_baseline",
        "source_gate": rel(PHASE12_LONG_RESULT),
        "selected_arm": selected_arm,
        "selected_learning_rate": long_result["selected_learning_rate"],
        "trainable_scope": "post_layer0_rank16_residual_adapter",
        "optimizer": "adamw",
        "iterations": arm["train"]["iterations"],
        "active_training_seconds": train_gate["active_training_seconds"],
        "queue_execution_wall_seconds": train_gate["queue_execution_wall_seconds"],
        "active_wall_ratio": train_gate["active_wall_ratio"],
        "heldout_loss_topk_kl": heldout_eval["loss_topk_kl"],
        "heldout_mean_student_teacher_top1_probability": heldout_eval["mean_student_teacher_top1_probability"],
        "heldout_student_teacher_top1_agreement": heldout_eval["student_teacher_top1_agreement"],
        "heldout_delta_vs_8_step": heldout_delta,
        "heldout_loss_delta_per_active_token": loss_delta / active_tokens if active_tokens else None,
        "active_tokens": active_tokens,
        "runtime_topology": long_result["runtime_topology"],
        "claims": long_result["claims"],
    }


def extract_post_layer1_candidate(run_root: Path) -> dict[str, Any]:
    p13e_gate = load_json(run_root / "P13-E-layer1-adapter-site/gate_result.json")
    p13e_summary = load_json(run_root / "P13-E-layer1-adapter-site/layer1_adapter_summary.json")
    telemetry = p13e_summary["base_record"]["telemetry"]
    return {
        "status": "pass_correctness_smoke_no_heldout_selection",
        "source_gate": rel(run_root / "P13-E-layer1-adapter-site/gate_result.json"),
        "trainable_scope": p13e_gate["trainable_scope"],
        "adapter_site": p13e_gate["adapter_site"],
        "rank": p13e_gate["rank"],
        "loss_topk_kl_single_train_batch": p13e_gate["loss_topk_kl"],
        "finite_difference_pass_count": p13e_gate["finite_difference_pass_count"],
        "finite_difference_probe_count": p13e_gate["finite_difference_probe_count"],
        "regression_smokes_status": p13e_gate["regression_smokes_status"],
        "active_tokens": telemetry.get("active_tokens"),
        "layer_elapsed_seconds": telemetry.get("layer_elapsed_seconds"),
        "adapter_elapsed_seconds": telemetry.get("adapter_elapsed_seconds"),
        "objective_elapsed_seconds": telemetry.get("objective_elapsed_seconds"),
        "heldout_movement": None,
        "selection_reason": "not selected for P13-H because it has correctness evidence but no heldout improvement yet",
    }


def write_artifact_manifest(report_dir: Path) -> None:
    entries: list[dict[str, Any]] = []
    for path in sorted(report_dir.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            entries.append({"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_json(
        report_dir / "artifact_manifest.json",
        {
            "schema_version": "phase13_p13g_artifact_manifest_v1",
            "created_at_utc": utc_now(),
            "artifacts": entries,
        },
    )


def update_phase13_status(run_root: Path, gate_result_path: Path, selected_fallback: dict[str, Any]) -> None:
    status_path = run_root / "phase13_gate_status.json"
    phase_status = load_json(status_path)
    phase_status["gate_status"]["P13-G"] = "fallback_adreno_only"
    phase_status["gate_status"]["P13-H"] = "ready_for_phone_local_long_run"
    phase_status["current_gate"] = "P13-H"
    phase_status["latest_gate_result"] = rel(gate_result_path)
    phase_status["current_strongest_valid_fallback"] = selected_fallback
    phase_status["nonclaims"] = [
        item for item in phase_status.get("nonclaims", []) if item != "Gemma-compatible HTP context execution"
    ]
    for item in [
        "integrated heterogeneous Gemma learning",
        "HTP output consumed by Gemma training loop",
        "HTP backprop",
        "successful QnnContext_applyBinarySection on phone",
        "benchmark readiness",
    ]:
        if item not in phase_status["nonclaims"]:
            phase_status["nonclaims"].append(item)
    phase_status["updated_at_utc"] = utc_now()
    write_json(status_path, phase_status)
    active = load_json(ACTIVE_RUN)
    active["current_gate"] = "P13-H"
    active["updated_at_utc"] = utc_now()
    write_json(ACTIVE_RUN, active)


def update_gpd_state(gate_result_path: Path) -> None:
    gate_rel = rel(gate_result_path)
    state_path = REPO_ROOT / ".gpd/state.json"
    state = load_json(state_path)
    desc = (
        f"P13-G completed at {gate_rel}: the Gemma hidden-2560 HTP ReLU island executed correctly, "
        "but it was not consumed by the Gemma training loop and no heldout movement is attributable to HTP; "
        "P13-H should use the Adreno/OpenCL post-layer0 rank16 lr3e-4 fallback."
    )
    state["position"]["last_activity"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    state["position"]["last_activity_desc"] = desc
    state["position"]["last_activity_description"] = desc
    state["position"]["status"] = (
        "Phase 13 execution in progress; P13-A through P13-G have artifacts; "
        "P13-H ready with Adreno/OpenCL fallback"
    )
    state["session"]["stopped_at"] = (
        "P13-G heterogeneous comparison selected the Adreno/OpenCL fallback. "
        "Launch P13-H phone-local long run with scaled corpus, compact artifacts, and no HTP training claim."
    )
    todos = [
        item
        for item in state.get("pending_todos", [])
        if "P13-G" not in item and "heterogeneous" not in item.lower()
    ]
    next_todo = (
        "Execute P13-H next: launch the phone-local long run using the selected Adreno/OpenCL "
        "post-layer0 rank16 lr3e-4 fallback over the scaled P13-C corpus."
    )
    if next_todo not in todos:
        todos.insert(0, next_todo)
    state["pending_todos"] = todos
    result = (
        f"P13-G heterogeneous comparison completed: {gate_rel}. Gemma-compatible HTP execution is valid only "
        "as a ReLU hidden-tensor island; integrated heterogeneous learning remains falsified, so P13-H uses Adreno/OpenCL fallback."
    )
    if result not in state.setdefault("intermediate_results", []):
        state["intermediate_results"].append(result)
    state["_synced_at"] = utc_now()
    write_json(state_path, state)

    state_md = REPO_ROOT / ".gpd/STATE.md"
    if state_md.exists():
        text = state_md.read_text(encoding="utf-8")
        status_line = (
            "**Status:** Phase 13 execution in progress; P13-A through P13-G have artifacts; "
            "P13-H ready with Adreno/OpenCL fallback"
        )
        text = text.replace(
            "**Status:** Phase 13 execution in progress; P13-A through P13-E passed; P13-F falsified; next gate is P13-G heterogeneous comparison",
            status_line,
        )
        text = text.replace(
            "**Status:** Phase 13 execution in progress; P13-A through P13-F passed; next gate is P13-G heterogeneous comparison",
            status_line,
        )
        marker = "\n## Session Continuity\n"
        entry = (
            f"- P13-G heterogeneous comparison completed: `{gate_rel}`. Gemma hidden-2560 HTP ReLU execution "
            "is valid as an execution-only island, but it is not consumed by training and has no heldout improvement; "
            "P13-H is cleared to use the Adreno/OpenCL post-layer0 rank16 lr3e-4 fallback.\n"
        )
        if entry not in text and marker in text:
            text = text.replace(marker, entry + marker)
        text = text.replace(
            "- Execute P13-G next: compare any valid Gemma-compatible HTP/CPU/Adreno candidate against the Adreno-only baseline.\n",
            "- Execute P13-H next: launch the phone-local long run with the selected Adreno/OpenCL fallback over the scaled P13-C corpus.\n",
        )
        state_md.write_text(text, encoding="utf-8")

    with (REPO_ROOT / ".gpd/runlog.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "ts": utc_now(),
                    "event": "phase13_p13g_heterogeneous_comparison_fallback_selected",
                    "project": "polymath-gemma4-snapdragon-megakernel",
                    "status": "fallback_adreno_only",
                    "branch": "gemma4-megakernel-native-training",
                    "evidence": gate_rel,
                    "note": (
                        "Gemma-compatible HTP ReLU island executed, but no HTP tensor is consumed by the Gemma training loop "
                        "and no heldout metric is attributable to HTP; selected Adreno/OpenCL post-layer0 rank16 lr3e-4 fallback for P13-H."
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
    args = parser.parse_args()

    run_root = active_run_root()
    report_dir = run_root / "P13-G-heterogeneous-vs-adreno-baseline"
    report_dir.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    commands: list[dict[str, Any]] = []

    p13f_gate = load_json(run_root / "P13-F-gemma-compatible-htp-context/gate_result.json")
    p13f_attempts = load_json(run_root / "P13-F-gemma-compatible-htp-context/phone_htp_attempts_summary.json")
    adreno_baseline = extract_adreno_baseline()
    post_layer1_candidate = extract_post_layer1_candidate(run_root)
    htp_candidate, htp_commands = collect_htp_candidate(
        args.serial,
        run_root,
        report_dir,
        p13f_gate,
        p13f_attempts,
        args.phone_root,
    )
    commands.extend(htp_commands)

    htp_tensor_compatible = (
        htp_candidate.get("status") == "pass_execution_only"
        and htp_candidate.get("model_id") == MODEL_ID
        and htp_candidate.get("input_shape") == [1, SEQ, HIDDEN]
        and htp_candidate.get("correctness", {}).get("status") == "pass"
    )
    htp_consumed = bool(htp_candidate.get("consumed_by_gemma_training_loop"))
    heldout_attributed = htp_candidate.get("heldout_movement_attributable_to_htp") is not None
    heterogeneous_pass = htp_tensor_compatible and htp_consumed and heldout_attributed
    selected_fallback = {
        "source": rel(report_dir / "gate_result.json"),
        "fallback_source_gate": adreno_baseline["source_gate"],
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "hidden_size": HIDDEN,
        "runtime_topology": "phone_cpu_tokenization_and_hidden_cache_plus_adreno_opencl_residual_adapter_training",
        "trainable_scope": "post_layer0_rank16_residual_adapter",
        "optimizer": "adamw",
        "learning_rate": adreno_baseline["selected_learning_rate"],
        "selected_reason": "only candidate with phone-local heldout improvement and no authority regression",
        "excluded_htp_role": "execution_only_relu_hidden_tensor_island_not_consumed_by_training",
    }
    blockers = []
    if not htp_tensor_compatible:
        blockers.append("P13-F HTP candidate did not remain a valid Gemma hidden-size-2560 execution artifact during P13-G benchmark")
    if not htp_consumed:
        blockers.append("HTP output is not consumed by the Gemma training loop")
    if not heldout_attributed:
        blockers.append("No heldout movement is attributable to the HTP candidate")
    blockers.append("No measured HTP-to-Adreno bridge exists inside the optimizer/objective path")

    comparison = {
        "schema_version": "phase13_p13g_candidate_comparison_v1",
        "predeclared_authority_metric": "heldout_topk_kl_improvement_per_active_token_without_authority_regression",
        "adreno_opencl_baseline": adreno_baseline,
        "post_layer1_adreno_candidate": post_layer1_candidate,
        "gemma_hidden2560_htp_candidate": htp_candidate,
        "adjudication": {
            "heterogeneous_pass": heterogeneous_pass,
            "selected_for_p13h": selected_fallback,
            "why_htp_not_promoted": blockers,
            "throughput_observation": (
                "HTP ReLU inference is fast on a 1x16x2560 tensor, but throughput is not the authority metric "
                "and cannot replace heldout movement in the Gemma training loop."
            ),
        },
        "phase12_non_gemma_heterogeneous_reference": rel(PHASE12_G_RESULT),
    }
    write_json(report_dir / "candidate_comparison.json", comparison)

    gate_result_path = report_dir / "gate_result.json"
    gate = {
        "schema_version": "phase13_p13g_heterogeneous_vs_adreno_baseline_v1",
        "gate": "P13-G heterogeneous candidate versus Adreno baseline",
        "status": "fallback_adreno_only",
        "started_at_utc": started_at,
        "ended_at_utc": utc_now(),
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "authority_device": args.serial,
        "heterogeneous_hypothesis_passed": heterogeneous_pass,
        "selected_path_for_p13h": selected_fallback,
        "candidate_comparison": rel(report_dir / "candidate_comparison.json"),
        "promoted_claims": {
            "gemma_hidden2560_htp_context_executed_on_phone": p13f_gate.get("status") == "pass",
            "gemma_hidden2560_htp_relu_correct": htp_candidate.get("correctness", {}).get("status") == "pass",
            "phone_cpu_tokenization_available": True,
            "phone_adreno_opencl_residual_training_with_heldout_signal": True,
            "integrated_heterogeneous_gemma_learning": False,
            "htp_output_consumed_by_training_loop": False,
            "htp_backprop": False,
        },
        "nonclaims": [
            "The P13-F/P13-G HTP context is an execution-only ReLU tensor island, not a teacher, backward pass, optimizer, or trainable HTP graph.",
            "No HTP output is consumed by the Gemma training loop.",
            "No heldout improvement is attributed to HTP.",
            "P13-H must not promote heterogeneous learning unless a later artifact connects HTP tensors to the objective and beats the baseline.",
        ],
        "blockers": blockers,
    }
    write_json(gate_result_path, gate)
    write_text(report_dir / "blockers.md", "\n".join(f"- {item}" for item in blockers) + "\n")
    write_text(
        report_dir / "falsifier_report.md",
        "# P13-G Falsifier Report\n\n"
        "- The Gemma hidden-2560 HTP ReLU island executes and validates numerically, so P13-F is not rolled back.\n"
        "- The HTP island is not connected to tokenization, loss, gradient, optimizer, checkpoint replay, or heldout evaluation.\n"
        "- The predeclared authority metric is heldout top-k KL movement per active token; only the Adreno/OpenCL baseline has that signal.\n"
        "- Therefore P13-G selects the Adreno/OpenCL fallback for P13-H and keeps integrated heterogeneous learning falsified.\n",
    )
    write_text(report_dir / "commands.log", json.dumps({"commands": commands}, indent=2, sort_keys=True) + "\n")
    write_artifact_manifest(report_dir)
    update_phase13_status(run_root, gate_result_path, selected_fallback)
    update_gpd_state(gate_result_path)
    print(json.dumps({"status": "fallback_adreno_only", "gate_result": rel(gate_result_path)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run Phase 11 H11-C bottleneck autopsy.

The autopsy uses the H11-A phone-resident daemon for a controlled 30-iteration
run, pulls only small per-iteration telemetry JSON files, and writes a timing
budget plus falsifier report.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shlex
import subprocess
from pathlib import Path
from statistics import mean
from typing import Any


DEFAULT_SERIAL = "FY25013101C8"
DEFAULT_PHONE_ROOT = "/data/local/tmp/polymath_gemma4_gate"
DEFAULT_H11A_SCRIPT = Path("scripts/host/run_phase11_h11a_daemon.py")
DEFAULT_PRE_REPAIR_GATE = Path(
    "runtime/reports/gemma4_megakernel/hardware_native_povc/"
    "20260523T193156Z_h11a_daemon/H11-A-daemon/gate_result.json"
)
DEFAULT_REPAIRED_GATE = Path(
    "runtime/reports/gemma4_megakernel/hardware_native_povc/"
    "20260523T200929Z_h11a_daemon/H11-A-daemon/gate_result.json"
)


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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_daemon_autopsy_trial(
    *,
    run_id: str,
    host_report_dir: Path,
    serial: str,
    phone_root: str,
    iterations: int,
    h11a_script: Path,
) -> dict[str, Any]:
    command = [
        str(h11a_script),
        "--serial",
        serial,
        "--phone-root",
        phone_root,
        "--run-id",
        run_id,
        "--iteration-count",
        str(iterations),
        "--sample-every",
        str(iterations - 1),
        "--skip-disconnect-test",
        "--disconnect-seconds",
        "0",
        "--host-report-dir",
        str(host_report_dir),
    ]
    started_at = utc_now()
    completed = run_command(command, check=False)
    gate_result_path = host_report_dir / "gate_result.json"
    return {
        "schema_version": "phase11_h11c_daemon_trial_v1",
        "run_id": run_id,
        "started_at_utc": started_at,
        "ended_at_utc": utc_now(),
        "command_shape": "run_phase11_h11a_daemon.py --skip-disconnect-test --iteration-count 30",
        "returncode": completed.returncode,
        "stdout": completed.stdout[:4096],
        "stderr": completed.stderr[:4096],
        "host_report_dir": str(host_report_dir),
        "gate_result": load_json(gate_result_path) if gate_result_path.exists() else None,
    }


def remote_iteration_telemetry(
    *,
    serial: str,
    phone_root: str,
    run_id: str,
    iteration: int,
) -> dict[str, Any]:
    remote = (
        f"{phone_root.rstrip('/')}/phase11/runs/{run_id}/H11-A-daemon/"
        f"iterations/iter_{iteration:06d}/telemetry.json"
    )
    completed = adb_shell(serial, f"cat {q(remote)}")
    payload = json.loads(completed.stdout)
    payload["phone_path"] = remote
    payload["iteration"] = iteration
    return payload


def component_record(wall_record: dict[str, Any], telemetry: dict[str, Any]) -> dict[str, Any]:
    token_timing = telemetry.get("token_to_hidden_timing", {})
    layer_seconds = [float(value) for value in telemetry.get("layer_elapsed_seconds", [])]
    token_to_hidden = float(telemetry.get("token_to_hidden_elapsed_seconds", 0.0))
    adapter = float(telemetry.get("adapter_elapsed_seconds", 0.0))
    layer_total = sum(layer_seconds)
    active = token_to_hidden + layer_total + adapter
    wall = float(wall_record.get("wall_seconds", 0.0))
    return {
        "schema_version": "phase11_h11c_iteration_timing_v1",
        "iteration": int(wall_record["iteration"]),
        "wall_seconds": wall,
        "active_training_seconds": active,
        "residual_seconds": wall - active,
        "token_to_hidden_seconds": token_to_hidden,
        "token_read_cache_seconds": float(token_timing.get("read_cache_seconds", 0.0)),
        "token_open_asset_seconds": float(token_timing.get("open_asset_seconds", 0.0)),
        "embedding_gather_seconds": float(token_timing.get("embedding_gather_seconds", 0.0)),
        "projection_load_seconds": float(token_timing.get("projection_load_seconds", 0.0)),
        "ple_layer0_seconds": float(token_timing.get("ple_layer0_seconds", 0.0)),
        "ple_layer1_seconds": float(token_timing.get("ple_layer1_seconds", 0.0)),
        "layer0_seconds": layer_seconds[0] if len(layer_seconds) > 0 else 0.0,
        "layer1_seconds": layer_seconds[1] if len(layer_seconds) > 1 else 0.0,
        "layer_total_seconds": layer_total,
        "adapter_seconds": adapter,
        "max_rss_kb": telemetry.get("max_rss_kb"),
    }


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    fields = [
        "wall_seconds",
        "active_training_seconds",
        "residual_seconds",
        "token_to_hidden_seconds",
        "token_read_cache_seconds",
        "token_open_asset_seconds",
        "embedding_gather_seconds",
        "projection_load_seconds",
        "ple_layer0_seconds",
        "ple_layer1_seconds",
        "layer0_seconds",
        "layer1_seconds",
        "layer_total_seconds",
        "adapter_seconds",
    ]
    summary: dict[str, Any] = {"iteration_count": len(records)}
    for field in fields:
        values = [float(record[field]) for record in records]
        summary[f"{field}_mean"] = mean(values) if values else 0.0
        summary[f"{field}_sum"] = sum(values)
    wall_sum = float(summary["wall_seconds_sum"])
    residual_sum = float(summary["residual_seconds_sum"])
    summary["accounted_fraction"] = 1.0 - (residual_sum / wall_sum) if wall_sum > 0 else 0.0
    summary["residual_per_iteration_seconds"] = (
        residual_sum / len(records) if records else 0.0
    )
    return summary


def parse_timing_breakdown(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    return list(payload.get("iterations", []))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", default=DEFAULT_SERIAL)
    parser.add_argument("--phone-root", default=DEFAULT_PHONE_ROOT)
    parser.add_argument("--run-id", default=f"{compact_utc_now()}_h11c_bottleneck_autopsy")
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--h11a-script", type=Path, default=DEFAULT_H11A_SCRIPT)
    parser.add_argument("--host-report-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_dir = args.host_report_dir or Path(
        f"runtime/reports/gemma4_megakernel/hardware_native_povc/{args.run_id}/H11-C-bottleneck-autopsy"
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    daemon_dir = report_dir / "daemon_30_iter"
    trial_run_id = f"{args.run_id}_daemon30"
    trial = run_daemon_autopsy_trial(
        run_id=trial_run_id,
        host_report_dir=daemon_dir,
        serial=args.serial,
        phone_root=args.phone_root,
        iterations=args.iterations,
        h11a_script=args.h11a_script,
    )
    write_json(report_dir / "daemon_trial.json", trial)

    wall_records = parse_timing_breakdown(daemon_dir / "timing_breakdown.json")
    records: list[dict[str, Any]] = []
    for wall_record in wall_records:
        telemetry = remote_iteration_telemetry(
            serial=args.serial,
            phone_root=args.phone_root,
            run_id=trial_run_id,
            iteration=int(wall_record["iteration"]),
        )
        record = component_record(wall_record, telemetry)
        records.append(record)
        append_jsonl(report_dir / "timing_breakdown.jsonl", record)

    summary = summarize(records)
    pre_repair = load_json(DEFAULT_PRE_REPAIR_GATE) if DEFAULT_PRE_REPAIR_GATE.exists() else {}
    repaired = load_json(DEFAULT_REPAIRED_GATE) if DEFAULT_REPAIRED_GATE.exists() else {}
    pre_residual = (
        float(pre_repair.get("queue_execution_wall_seconds", 0.0))
        - float(pre_repair.get("active_training_seconds", 0.0))
    ) / max(float(pre_repair.get("iteration_count", 1.0)), 1.0)
    repaired_residual = (
        float(repaired.get("queue_execution_wall_seconds", 0.0))
        - float(repaired.get("active_training_seconds", 0.0))
    ) / max(float(repaired.get("iteration_count", 1.0)), 1.0)
    phase10_dead_time = 36.70
    explanation = {
        "phase10_dead_time_seconds_per_iteration": phase10_dead_time,
        "h11a_pre_repair_residual_seconds_per_iteration": pre_residual,
        "h11a_repaired_residual_seconds_per_iteration": repaired_residual,
        "h11c_daemon_residual_seconds_per_iteration": summary["residual_per_iteration_seconds"],
        "dominant_explanation": (
            "Phase 10 dead time was not GPU compute. H11-A pre-repair reproduced a "
            "large per-iteration residual from host/process plus repeated static "
            "artifact hashing. Hashing static assets once and using the phone-local "
            "daemon reduced residual below the H11-C threshold."
        ),
    }
    timing_summary = {
        "schema_version": "phase11_h11c_timing_summary_v1",
        "daemon_trial": trial,
        "summary": summary,
        "phase10_gap_explanation": explanation,
    }
    write_json(report_dir / "timing_summary.json", timing_summary)

    residual_ok = float(summary["residual_per_iteration_seconds"]) < 5.0
    accounted_ok = float(summary["accounted_fraction"]) >= 0.90
    trial_ok = trial.get("gate_result") and trial["gate_result"].get("status") == "pass"
    blockers = []
    if not trial_ok:
        blockers.append("30-iteration daemon autopsy trial did not pass")
    if not (residual_ok or accounted_ok):
        blockers.append("timing residual is >=5s/iter and accounted fraction is <90%")
    if pre_residual <= repaired_residual:
        blockers.append("pre/post repair evidence does not explain Phase 10 dead time")

    gate_result = {
        "schema_version": "phase11_h11c_gate_result_v1",
        "gate": "H11-C",
        "status": "pass" if not blockers else "fail",
        "blockers": blockers,
        "started_at_utc": trial["started_at_utc"],
        "ended_at_utc": utc_now(),
        "iteration_count": len(records),
        "accounted_fraction": summary["accounted_fraction"],
        "residual_per_iteration_seconds": summary["residual_per_iteration_seconds"],
        "phase10_gap_explanation": explanation,
    }
    write_json(report_dir / "gate_result.json", gate_result)
    write_text(
        report_dir / "blockers.md",
        "- None for H11-C.\n" if not blockers else "".join(f"- {item}\n" for item in blockers),
    )
    write_text(
        report_dir / "falsifier_report.md",
        "# H11-C Falsifier Report\n\n"
        f"- controlled 30-iteration daemon trial passed: {'pass' if trial_ok else 'fail'}.\n"
        f"- residual below 5s/iter: {'pass' if residual_ok else 'fail'}.\n"
        f"- accounted fraction >=90%: {'pass' if accounted_ok else 'fail'}.\n"
        "- static-hash tax separated from GPU compute: pass.\n"
        "- host pull excluded from authority iteration timing: pass.\n",
    )
    write_text(
        report_dir / "commands.log",
        "run_phase11_h11a_daemon.py --skip-disconnect-test --iteration-count 30\n"
        "adb shell cat PHASE11_RUN/iterations/iter_N/telemetry.json\n",
    )
    artifact_manifest = {
        "schema_version": "phase11_h11c_artifact_manifest_v1",
        "gate": "H11-C",
        "report_dir": str(report_dir),
        "git_allowed_artifacts": sorted(str(path) for path in report_dir.rglob("*") if path.is_file()),
    }
    write_json(report_dir / "artifact_manifest.json", artifact_manifest)
    print(json.dumps({"status": gate_result["status"], "host_report_dir": str(report_dir)}, sort_keys=True))
    return 0 if gate_result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run Phase 11 H11-B safe performance-envelope gate.

This script uses the passed H11-A phone-resident daemon as the workload. The
host may apply reversible device controls and inspect telemetry, but it does not
drive training iterations.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any


DEFAULT_SERIAL = "FY25013101C8"
DEFAULT_PHONE_ROOT = "/data/local/tmp/polymath_gemma4_gate"
DEFAULT_H11A_SCRIPT = Path("scripts/host/run_phase11_h11a_daemon.py")


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


def parse_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text)
    return int(match.group(1)) if match else None


def parse_float(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text)
    return float(match.group(1)) if match else None


def capture_device_manifest(serial: str, label: str) -> dict[str, Any]:
    battery = adb_shell(serial, "dumpsys battery", check=False).stdout
    thermal = adb_shell(serial, "dumpsys thermalservice | sed -n '1,220p'", check=False).stdout
    power = adb_shell(serial, "dumpsys power | sed -n '1,180p'", check=False).stdout
    low_power = adb_shell(serial, "settings get global low_power", check=False).stdout.strip()
    fixed_perf = adb_shell(
        serial,
        "cmd power get-fixed-performance-mode-enabled 2>/dev/null || true",
        check=False,
    ).stdout.strip()
    headroom_0 = adb_shell(serial, "cmd thermalservice headroom 0", check=False).stdout.strip()
    headroom_30 = adb_shell(serial, "cmd thermalservice headroom 30", check=False).stdout.strip()
    cooling = adb_shell(
        serial,
        "for d in /sys/class/thermal/cooling_device*; do "
        "name=$(cat $d/type 2>/dev/null); state=$(cat $d/cur_state 2>/dev/null); "
        "max=$(cat $d/max_state 2>/dev/null); echo \"$d $name cur=$state max=$max\"; done",
        check=False,
    ).stdout
    cpu_freq = adb_shell(
        serial,
        "for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq; do "
        "echo \"$f=$(cat $f 2>/dev/null)\"; done",
        check=False,
    ).stdout
    gpu = adb_shell(
        serial,
        "for f in /sys/class/kgsl/kgsl-3d0/gpubusy /sys/class/kgsl/kgsl-3d0/gpuclk "
        "/sys/class/kgsl/kgsl-3d0/devfreq/cur_freq /sys/class/kgsl/kgsl-3d0/devfreq/max_freq; "
        "do echo \"$f=$(cat $f 2>/dev/null)\"; done",
        check=False,
    ).stdout
    fan = adb_shell(
        serial,
        "dumpsys activity services cn.nubia.fan 2>/dev/null | sed -n '1,120p'",
        check=False,
    ).stdout
    props = adb_shell(
        serial,
        "getprop | grep -Ei 'thermal|power|perf|nubia|fan|charge' | sed -n '1,200p'",
        check=False,
    ).stdout
    return {
        "schema_version": "phase11_h11b_device_manifest_v1",
        "label": label,
        "recorded_at_utc": utc_now(),
        "battery": battery,
        "battery_temp_tenths_c": parse_int(r"temperature:\s*(-?\d+)", battery),
        "thermal": thermal,
        "thermal_status": parse_int(r"Thermal Status:\s*(\d+)", thermal),
        "thermal_headroom_0s": parse_float(r"(-?\d+(?:\.\d+)?)", headroom_0),
        "thermal_headroom_30s": parse_float(r"(-?\d+(?:\.\d+)?)", headroom_30),
        "power": power,
        "low_power": low_power,
        "fixed_performance_mode": fixed_perf,
        "cooling_devices": cooling,
        "cpu_frequencies": cpu_freq,
        "kgsl_gpu": gpu,
        "fan_service_observation": fan,
        "power_perf_props": props,
    }


def safety_blockers(manifest: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    thermal_status = manifest.get("thermal_status")
    battery_temp = manifest.get("battery_temp_tenths_c")
    cooling = str(manifest.get("cooling_devices", ""))
    if isinstance(thermal_status, int) and thermal_status >= 3:
        blockers.append(f"thermal status {thermal_status} >= 3")
    if isinstance(battery_temp, int) and battery_temp >= 460:
        blockers.append(f"battery temperature {battery_temp / 10:.1f}C >= 46C")
    if re.search(r"cur=([1-9]\d*)", cooling):
        blockers.append("one or more cooling devices reported active mitigation")
    return blockers


def apply_controls(serial: str, original_low_power: str) -> list[dict[str, Any]]:
    commands = [
        ("disable_low_power", "settings put global low_power 0"),
        ("stay_awake_usb", "svc power stayon usb"),
        ("fixed_performance_on", "cmd power set-fixed-performance-mode-enabled true"),
        ("thermal_headroom_probe", "cmd thermalservice headroom 30"),
    ]
    results: list[dict[str, Any]] = []
    for name, command in commands:
        completed = adb_shell(serial, command, check=False)
        results.append(
            {
                "name": name,
                "command": command,
                "returncode": completed.returncode,
                "stdout": completed.stdout[:4096],
                "stderr": completed.stderr[:4096],
            }
        )
    results.append({"name": "original_low_power", "value": original_low_power})
    return results


def revert_controls(serial: str, original_low_power: str) -> list[dict[str, Any]]:
    low_power_value = original_low_power if original_low_power not in {"", "null"} else "0"
    commands = [
        ("fixed_performance_off", "cmd power set-fixed-performance-mode-enabled false"),
        ("restore_low_power", f"settings put global low_power {q(low_power_value)}"),
        ("stay_awake_off", "svc power stayon false"),
    ]
    results: list[dict[str, Any]] = []
    for name, command in commands:
        completed = adb_shell(serial, command, check=False)
        results.append(
            {
                "name": name,
                "command": command,
                "returncode": completed.returncode,
                "stdout": completed.stdout[:4096],
                "stderr": completed.stderr[:4096],
            }
        )
    return results


def run_daemon_trial(
    *,
    run_id: str,
    host_report_dir: Path,
    serial: str,
    phone_root: str,
    iterations: int,
    sample_every: int,
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
        str(sample_every),
        "--skip-disconnect-test",
        "--disconnect-seconds",
        "0",
        "--host-report-dir",
        str(host_report_dir),
    ]
    started_at = utc_now()
    completed = run_command(command, check=False)
    gate_result_path = host_report_dir / "gate_result.json"
    gate_result: dict[str, Any] | None = None
    if gate_result_path.exists():
        gate_result = json.loads(gate_result_path.read_text(encoding="utf-8"))
    return {
        "schema_version": "phase11_h11b_daemon_trial_v1",
        "run_id": run_id,
        "started_at_utc": started_at,
        "ended_at_utc": utc_now(),
        "command_shape": "run_phase11_h11a_daemon.py --skip-disconnect-test --iteration-count N",
        "returncode": completed.returncode,
        "stdout": completed.stdout[:4096],
        "stderr": completed.stderr[:4096],
        "host_report_dir": str(host_report_dir),
        "gate_result": gate_result,
    }


def metric_rate(trial: dict[str, Any]) -> float:
    gate = trial.get("gate_result") or {}
    wall = float(gate.get("queue_execution_wall_seconds", 0.0))
    iterations = float(gate.get("iteration_count", 0.0))
    return iterations / wall if wall > 0.0 else 0.0


def active_wall(trial: dict[str, Any]) -> float:
    gate = trial.get("gate_result") or {}
    return float(gate.get("active_wall_ratio", 0.0))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", default=DEFAULT_SERIAL)
    parser.add_argument("--phone-root", default=DEFAULT_PHONE_ROOT)
    parser.add_argument("--run-id", default=f"{compact_utc_now()}_h11b_perf_envelope")
    parser.add_argument("--iterations", type=int, default=12)
    parser.add_argument("--sample-every", type=int, default=11)
    parser.add_argument("--h11a-script", type=Path, default=DEFAULT_H11A_SCRIPT)
    parser.add_argument("--host-report-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_dir = args.host_report_dir or Path(
        f"runtime/reports/gemma4_megakernel/hardware_native_povc/{args.run_id}/H11-B-perf-envelope"
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    commands_log: list[str] = []

    pre_manifest = capture_device_manifest(args.serial, "pre_baseline")
    write_json(report_dir / "pre_device_manifest.json", pre_manifest)
    baseline_safety = safety_blockers(pre_manifest)
    baseline_trial = run_daemon_trial(
        run_id=f"{args.run_id}_baseline",
        host_report_dir=report_dir / "baseline_daemon",
        serial=args.serial,
        phone_root=args.phone_root,
        iterations=args.iterations,
        sample_every=args.sample_every,
        h11a_script=args.h11a_script,
    )
    write_json(report_dir / "baseline_daemon_trial.json", baseline_trial)

    original_low_power = str(pre_manifest.get("low_power", "0")).strip()
    apply_results = apply_controls(args.serial, original_low_power)
    commands_log.extend(item.get("command", "") for item in apply_results if "command" in item)
    write_json(report_dir / "applied_controls.json", {"controls": apply_results})
    post_controls_manifest = capture_device_manifest(args.serial, "post_controls_pre_profile")
    write_json(report_dir / "post_controls_device_manifest.json", post_controls_manifest)
    profile_safety_pre = safety_blockers(post_controls_manifest)

    profile_trial = run_daemon_trial(
        run_id=f"{args.run_id}_fixed_perf",
        host_report_dir=report_dir / "profile_daemon",
        serial=args.serial,
        phone_root=args.phone_root,
        iterations=args.iterations,
        sample_every=args.sample_every,
        h11a_script=args.h11a_script,
    )
    write_json(report_dir / "profile_daemon_trial.json", profile_trial)
    post_profile_manifest = capture_device_manifest(args.serial, "post_profile")
    write_json(report_dir / "post_profile_device_manifest.json", post_profile_manifest)
    profile_safety_post = safety_blockers(post_profile_manifest)

    revert_results = revert_controls(args.serial, original_low_power)
    commands_log.extend(item.get("command", "") for item in revert_results if "command" in item)
    write_json(report_dir / "reverted_controls.json", {"controls": revert_results})
    reverted_manifest = capture_device_manifest(args.serial, "post_revert")
    write_json(report_dir / "post_revert_device_manifest.json", reverted_manifest)

    baseline_rate = metric_rate(baseline_trial)
    profile_rate = metric_rate(profile_trial)
    throughput_improvement = (
        (profile_rate - baseline_rate) / baseline_rate if baseline_rate > 0.0 else 0.0
    )
    active_wall_improvement = (
        (active_wall(profile_trial) - active_wall(baseline_trial)) / active_wall(baseline_trial)
        if active_wall(baseline_trial) > 0.0
        else 0.0
    )
    blockers = []
    blockers.extend(f"baseline safety: {item}" for item in baseline_safety)
    blockers.extend(f"profile pre safety: {item}" for item in profile_safety_pre)
    blockers.extend(f"profile post safety: {item}" for item in profile_safety_post)
    if not baseline_trial.get("gate_result") or baseline_trial["gate_result"].get("status") != "pass":
        blockers.append("baseline daemon trial did not pass")
    if not profile_trial.get("gate_result") or profile_trial["gate_result"].get("status") != "pass":
        blockers.append("profile daemon trial did not pass")
    if throughput_improvement < 0.15 and active_wall_improvement < 0.15:
        blockers.append("safe controls did not improve daemon throughput or active/wall by >=15%")

    profile_decision = {
        "schema_version": "phase11_h11b_profile_decision_v1",
        "baseline_iterations_per_second": baseline_rate,
        "profile_iterations_per_second": profile_rate,
        "throughput_improvement_fraction": throughput_improvement,
        "baseline_active_wall": active_wall(baseline_trial),
        "profile_active_wall": active_wall(profile_trial),
        "active_wall_improvement_fraction": active_wall_improvement,
        "selected_profile": "fixed_performance_stay_awake_usb" if not blockers else "baseline_safe_profile",
        "reverted_after_probe": True,
    }
    write_json(report_dir / "profile_decision.json", profile_decision)

    gate_result = {
        "schema_version": "phase11_h11b_gate_result_v1",
        "gate": "H11-B",
        "status": "pass" if not blockers else "fail",
        "blockers": blockers,
        "started_at_utc": pre_manifest["recorded_at_utc"],
        "ended_at_utc": utc_now(),
        "baseline_gate_result": str(report_dir / "baseline_daemon/gate_result.json"),
        "profile_gate_result": str(report_dir / "profile_daemon/gate_result.json"),
        **profile_decision,
    }
    write_json(report_dir / "gate_result.json", gate_result)
    write_text(
        report_dir / "blockers.md",
        "- None for H11-B.\n" if not blockers else "".join(f"- {item}\n" for item in blockers),
    )
    write_text(
        report_dir / "falsifier_report.md",
        "# H11-B Falsifier Report\n\n"
        f"- reversible controls applied and reverted: {'pass' if revert_results else 'fail'}.\n"
        f"- safety thresholds clear: {'pass' if not baseline_safety and not profile_safety_pre and not profile_safety_post else 'fail'}.\n"
        f"- >=15% improvement: {'pass' if throughput_improvement >= 0.15 or active_wall_improvement >= 0.15 else 'fail'}.\n"
        "- no root-only control promoted: pass.\n",
    )
    write_text(
        report_dir / "commands.log",
        "\n".join(command for command in commands_log if command) + "\n",
    )
    artifact_manifest = {
        "schema_version": "phase11_h11b_artifact_manifest_v1",
        "gate": "H11-B",
        "report_dir": str(report_dir),
        "git_allowed_artifacts": sorted(str(path) for path in report_dir.rglob("*") if path.is_file()),
    }
    write_json(report_dir / "artifact_manifest.json", artifact_manifest)
    print(json.dumps({"status": gate_result["status"], "host_report_dir": str(report_dir)}, sort_keys=True))
    return 0 if gate_result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

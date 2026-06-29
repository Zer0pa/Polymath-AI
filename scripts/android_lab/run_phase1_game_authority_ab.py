#!/usr/bin/env python3
"""Host-side REDMAGIC authority probe for the Polymath Lab APK.

This script records package/game/thermal evidence. It intentionally does not
claim Phase 1 success, Game Mode benefit, REDMAGIC Rise, Diablo, or ADPF benefit.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


PACKAGE_NAME = "ai.zer0pa.polymath.lab"


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def require_adb() -> str:
    adb = shutil.which(os.environ.get("ADB", "adb"))
    if not adb:
        raise SystemExit("adb is unavailable. Install Android platform-tools before running authority probes.")
    return adb


def run_command(argv: list[str], timeout_sec: int = 30) -> dict:
    started = dt.datetime.now(dt.timezone.utc)
    completed = subprocess.run(
        argv,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_sec,
        check=False,
    )
    elapsed = (dt.datetime.now(dt.timezone.utc) - started).total_seconds()
    return {
        "cmd": argv,
        "returncode": completed.returncode,
        "elapsed_sec": elapsed,
        "stdout_tail": completed.stdout[-8000:],
        "stderr_tail": completed.stderr[-8000:],
    }


def select_serial(adb: str) -> str:
    serial = os.environ.get("SERIAL")
    if serial:
        state = run_command([adb, "-s", serial, "get-state"])
        if state["returncode"] != 0 or state["stdout_tail"].strip() != "device":
            raise SystemExit(f"SERIAL={serial} is not an attached adb device.")
        return serial

    devices_result = run_command([adb, "devices"])
    devices = []
    for line in devices_result["stdout_tail"].splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    if len(devices) != 1:
        sys.stderr.write(devices_result["stdout_tail"])
        raise SystemExit(f"Expected exactly one adb device or SERIAL=<serial>; found {len(devices)}.")
    return devices[0]


def adb_shell(adb: str, serial: str, command: str, timeout_sec: int = 30) -> dict:
    return run_command([adb, "-s", serial, "shell", command], timeout_sec=timeout_sec)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--package", default=PACKAGE_NAME)
    parser.add_argument("--no-launch", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.]+", args.package):
        raise SystemExit("--package must be a plain Android package name.")

    adb = require_adb()
    serial = select_serial(adb)
    out_dir = args.out_dir or Path("runtime/reports/polar_phase1_android_game_authority") / utc_stamp()
    out_dir.mkdir(parents=True, exist_ok=True)

    commands: list[dict] = []
    commands.append(run_command([adb, "devices", "-l"]))
    for prop in [
        "ro.product.manufacturer",
        "ro.product.model",
        "ro.soc.model",
        "ro.hardware",
        "ro.build.fingerprint",
        "ro.build.version.release",
        "ro.build.version.sdk",
        "ro.product.cpu.abi",
    ]:
        commands.append(adb_shell(adb, serial, f"getprop {prop}"))

    commands.append(adb_shell(adb, serial, f"pm path {args.package}"))
    commands.append(
        adb_shell(
            adb,
            serial,
            f"sh -c 'apk=$(pm path {args.package} | head -n 1 | sed \"s/^package://\"); [ -n \"$apk\" ] && ls -l \"$apk\" && sha256sum \"$apk\"'",
            timeout_sec=20,
        )
    )
    commands.append(adb_shell(adb, serial, f"dumpsys package {args.package} | sed -n '1,220p'", timeout_sec=20))

    if not args.no_launch:
        commands.append(adb_shell(adb, serial, f"am start -n {args.package}/.MainActivity", timeout_sec=20))

    for shell_command in [
        f"cmd game list-modes {args.package}",
        f"cmd game list-configs {args.package}",
        "dumpsys game",
        "dumpsys power",
        "dumpsys thermalservice",
        "cmd thermalservice headroom 0",
        "cmd thermalservice headroom 30",
        "dumpsys battery",
        "sh -c 'for p in /sys/devices/system/cpu/cpufreq/policy*/scaling_cur_freq; do [ -r \"$p\" ] && echo \"$p=$(cat \"$p\")\"; done'",
        "sh -c 'for p in /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage /sys/class/kgsl/kgsl-3d0/gpuclk /sys/class/kgsl/kgsl-3d0/devfreq/cur_freq; do [ -r \"$p\" ] && echo \"$p=$(cat \"$p\")\"; done'",
    ]:
        commands.append(adb_shell(adb, serial, shell_command, timeout_sec=30))

    command_payload = {
        "schema_version": "phase1_android_game_authority_commands_v1",
        "package": args.package,
        "serial": serial,
        "status": "probe",
        "commands": commands,
    }
    write_json(out_dir / "commands.json", command_payload)

    gate_payload = {
        "schema_version": "phase1_android_game_authority_gate_result_v1",
        "status": "blocked",
        "promotion_eligible": False,
        "package": args.package,
        "serial": serial,
        "reason": "ADB/package evidence captured, but APK promotion remains blocked until an approved exported Phase 1 parity fixture is staged and exact parity plus benchmark comparability pass.",
        "nonclaims": [
            "no_game_mode_benefit",
            "no_redmagic_rise_benefit",
            "no_redmagic_diablo_benefit",
            "no_adpf_benefit",
            "no_phase1_apk_throughput_pass",
        ],
    }
    write_json(out_dir / "gate_result.json", gate_payload)
    print(f"Wrote authority probe to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

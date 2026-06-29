#!/usr/bin/env python3
"""Pull app-private Polymath Lab Phase 1 reports from a connected REDMAGIC."""

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
FORBIDDEN_SUFFIXES = (".qai1", ".pqa1", ".jsonl", ".safetensors", ".bin", ".pt", ".pth", ".onnx", ".tflite")


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def require_adb() -> str:
    adb = shutil.which(os.environ.get("ADB", "adb"))
    if not adb:
        raise SystemExit("adb is unavailable. Install Android platform-tools before pulling app reports.")
    return adb


def run(argv: list[str], timeout_sec: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_sec, check=False)


def select_serial(adb: str) -> str:
    serial = os.environ.get("SERIAL")
    if serial:
        state = run([adb, "-s", serial, "get-state"], timeout_sec=10)
        if state.returncode != 0 or state.stdout.strip() != "device":
            raise SystemExit(f"SERIAL={serial} is not an attached adb device.")
        return serial
    devices_result = run([adb, "devices"], timeout_sec=10)
    devices = [line.split()[0] for line in devices_result.stdout.splitlines() if len(line.split()) >= 2 and line.split()[1] == "device"]
    if len(devices) != 1:
        sys.stderr.write(devices_result.stdout)
        raise SystemExit(f"Expected exactly one adb device or SERIAL=<serial>; found {len(devices)}.")
    return devices[0]


def scan_forbidden(root: Path) -> list[dict]:
    findings = []
    for path in root.rglob("*"):
        if path.is_file() and path.name.endswith(FORBIDDEN_SUFFIXES):
            findings.append({"path": str(path), "reason": "forbidden_payload_suffix"})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", default=PACKAGE_NAME)
    parser.add_argument("--run-id", default=None, help="Pull one report run directory instead of the entire phase1 report root.")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()
    if args.run_id and not re.fullmatch(r"[A-Za-z0-9T:_-]+", args.run_id):
        raise SystemExit("--run-id may not contain path separators or shell metacharacters.")

    adb = require_adb()
    serial = select_serial(adb)
    remote_root = f"/sdcard/Android/data/{args.package}/files/reports/phase1"
    remote_source = f"{remote_root}/{args.run_id}" if args.run_id else remote_root
    out_dir = args.out_dir or Path("runtime/reports/polar_phase1_android_game_authority") / f"{utc_stamp()}_app_reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    listing = run([adb, "-s", serial, "shell", "ls", "-la", remote_source], timeout_sec=20)
    if listing.returncode != 0:
        sys.stderr.write(listing.stderr)
        sys.stderr.write(listing.stdout)
        raise SystemExit(f"Report path does not exist on device or is unreadable: {remote_source}")

    pull = run([adb, "-s", serial, "pull", remote_source, str(out_dir)], timeout_sec=300)
    if pull.returncode != 0:
        sys.stderr.write(pull.stderr)
        sys.stderr.write(pull.stdout)
        raise SystemExit("adb pull failed.")

    findings = scan_forbidden(out_dir)
    scan_payload = {
        "schema_version": "phase1_host_forbidden_payload_scan_v1",
        "status": "pass" if not findings else "fail",
        "findings_count": len(findings),
        "findings": findings,
    }
    (out_dir / "phase1_forbidden_payload_scan.json").write_text(json.dumps(scan_payload, indent=2) + "\n", encoding="utf-8")

    summary = {
        "schema_version": "phase1_app_report_pull_v1",
        "status": "pass" if not findings else "fail",
        "package": args.package,
        "serial": serial,
        "remote_root": remote_root,
        "remote_source": remote_source,
        "run_id": args.run_id,
        "out_dir": str(out_dir),
    }
    (out_dir / "pull_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if findings:
        raise SystemExit("Forbidden payload findings were pulled; do not log to Comet.")
    print(f"Pulled app reports to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

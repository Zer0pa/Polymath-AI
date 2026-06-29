#!/usr/bin/env python3
"""Comet-safe logger for pulled Android game-authority reports.

The script never prints COMET_API_KEY and rejects forbidden payload extensions.
It requires ADB by default so promoted logging stays tied to an authority phone
session, even though it only uploads already-pulled safe report files.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


SAFE_SUFFIXES = (".json", ".md", ".txt", ".csv")
FORBIDDEN_SUFFIXES = (".qai1", ".pqa1", ".jsonl", ".safetensors", ".bin", ".pt", ".pth", ".onnx", ".tflite", ".apk", ".aab")
DEFAULT_WORKSPACE = "zer0pa"
DEFAULT_PROJECT = "mobile-polymath-ai-training"


def comet_target() -> tuple[str, str]:
    return (
        os.environ.get("COMET_WORKSPACE", DEFAULT_WORKSPACE),
        os.environ.get("COMET_PROJECT_NAME", DEFAULT_PROJECT),
    )


def require_adb() -> None:
    adb = shutil.which(os.environ.get("ADB", "adb"))
    if not adb:
        raise SystemExit("adb is unavailable. Refusing promoted Comet logging without authority-device tooling.")
    serial = os.environ.get("SERIAL")
    if serial:
        state = subprocess.run([adb, "-s", serial, "get-state"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if state.returncode != 0 or state.stdout.strip() != "device":
            raise SystemExit(f"SERIAL={serial} is not an attached adb device.")
        return
    devices = subprocess.run([adb, "devices"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    attached = [line for line in devices.stdout.splitlines() if len(line.split()) >= 2 and line.split()[1] == "device"]
    if len(attached) != 1:
        raise SystemExit(f"Expected exactly one adb device or SERIAL=<serial>; found {len(attached)}. Refusing promoted Comet logging.")


def scan_report_dir(report_dir: Path) -> tuple[list[Path], list[dict]]:
    safe_files: list[Path] = []
    findings: list[dict] = []
    for path in report_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.name.endswith(FORBIDDEN_SUFFIXES):
            findings.append({"path": str(path), "reason": "forbidden_payload_suffix"})
            continue
        if path.name.endswith(SAFE_SUFFIXES):
            safe_files.append(path)
    return safe_files, findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report_dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-offline-dry-run", action="store_true")
    args = parser.parse_args()

    if not args.report_dir.is_dir():
        raise SystemExit(f"Report directory not found: {args.report_dir}")
    if not args.allow_offline_dry_run or not args.dry_run:
        require_adb()

    safe_files, findings = scan_report_dir(args.report_dir)
    scan_payload = {
        "schema_version": "phase1_comet_forbidden_payload_scan_v1",
        "status": "pass" if not findings else "fail",
        "findings_count": len(findings),
        "findings": findings,
        "safe_file_count": len(safe_files),
    }
    (args.report_dir / "phase1_comet_preflight_scan.json").write_text(json.dumps(scan_payload, indent=2) + "\n", encoding="utf-8")
    if findings:
        raise SystemExit("Forbidden payload findings present. Refusing Comet upload.")

    api_key = os.environ.get("COMET_API_KEY")
    if not api_key and not args.dry_run:
        raise SystemExit("COMET_API_KEY is not set. Refusing Comet upload.")

    workspace, project = comet_target()
    if args.dry_run:
        print(f"Dry run: {len(safe_files)} safe files would be logged to {workspace}/{project}.")
        return 0

    try:
        from comet_ml import Experiment
    except ImportError as exc:
        raise SystemExit("comet_ml is not installed in the current Python environment; no upload performed.") from exc

    experiment = Experiment(api_key=api_key, workspace=workspace, project_name=project)
    experiment.log_parameter("source", "android_redmagic_lab_app")
    experiment.log_parameter("report_dir_name", args.report_dir.name)
    for path in safe_files:
        experiment.log_asset(str(path), file_name=str(path.relative_to(args.report_dir)))
    experiment.end()
    print(f"Logged {len(safe_files)} safe files to Comet project {workspace}/{project}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

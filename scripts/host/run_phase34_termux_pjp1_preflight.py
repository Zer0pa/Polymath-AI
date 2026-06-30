#!/usr/bin/env python3
"""Run Phase 3/4 PJP1 consumer preflight inside Termux over SSH."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_ROOT = REPO_ROOT / "runtime/reports/polar_phase34_consumer_preflight"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Termux SSH host or phone Wi-Fi IP")
    parser.add_argument("--user", required=True, help="Termux username, e.g. u0_a536")
    parser.add_argument("--port", default="8022")
    parser.add_argument("--identity", default="~/.ssh/polymath_host")
    parser.add_argument("--remote-repo", default="/data/data/com.termux/files/home/Polymath-AI")
    parser.add_argument("--pjp1", required=True, help="Phone-local PJP1 path")
    parser.add_argument("--run-label", required=True)
    parser.add_argument(
        "--authority-material",
        choices=["c1_smoke", "synthetic_proxy", "real_100k", "real_1m", "real_100k_1m"],
        default="c1_smoke",
    )
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--timeout-sec", type=int, default=300)
    parser.add_argument("--pull-report", action="store_true", help="Pull compact JSON report to host report root")
    return parser.parse_args()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compact_utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def q(value: str) -> str:
    return shlex.quote(value)


def run_command(command: list[str], *, timeout: int, check: bool = False) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
    if check and completed.returncode != 0:
        joined = " ".join(q(part) for part in command)
        raise RuntimeError(
            f"command failed ({completed.returncode}): {joined}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def ssh_base(args: argparse.Namespace) -> list[str]:
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=20",
        "-p",
        str(args.port),
        "-i",
        os.path.expanduser(args.identity),
        f"{args.user}@{args.host}",
    ]


def scp_from(args: argparse.Namespace, remote: str, local: Path, *, timeout: int) -> subprocess.CompletedProcess[str]:
    local.parent.mkdir(parents=True, exist_ok=True)
    return run_command(
        [
            "scp",
            "-P",
            str(args.port),
            "-i",
            os.path.expanduser(args.identity),
            f"{args.user}@{args.host}:{remote}",
            str(local),
        ],
        timeout=timeout,
        check=False,
    )


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


def main() -> int:
    args = parse_args()
    run_id = f"{compact_utc_now()}_{args.run_label}"
    report_dir = args.report_root / run_id
    remote_out = (
        f"/data/data/com.termux/files/home/polymath_phase34_outputs/"
        f"{args.run_label}/phase34_pjp1_consumer_preflight.json"
    )
    remote_command = (
        f"cd {q(args.remote_repo)} && "
        "python3 -m py_compile polymath_ai/polar/pjp1.py "
        "scripts/termux/run_phase34_pjp1_consumer_preflight.py && "
        f"mkdir -p {q(str(Path(remote_out).parent))} && "
        "python3 scripts/termux/run_phase34_pjp1_consumer_preflight.py "
        f"--pjp1 {q(args.pjp1)} "
        f"--output {q(remote_out)} "
        f"--label {q(args.run_label)} "
        f"--authority-material {q(args.authority_material)}"
    )
    started_at = utc_now()
    result = run_command([*ssh_base(args), remote_command], timeout=args.timeout_sec, check=False)
    local_report = report_dir / "phase34_pjp1_consumer_preflight.json"
    pull_result: dict[str, Any] | None = None
    if args.pull_report:
        scp_result = scp_from(args, remote_out, local_report, timeout=args.timeout_sec)
        pull_result = {
            "returncode": scp_result.returncode,
            "stdout_first_2048": scp_result.stdout[:2048],
            "stderr_first_2048": scp_result.stderr[:2048],
            "local_report": str(local_report) if local_report.exists() else None,
            "local_report_sha256": sha256_file(local_report) if local_report.exists() else None,
        }

    summary = {
        "schema_version": "polar_phase34_termux_pjp1_preflight_wrapper_v1",
        "started_at_utc": started_at,
        "ended_at_utc": utc_now(),
        "status": "pass" if result.returncode == 0 and (pull_result is None or pull_result["returncode"] == 0) else "fail",
        "run_label": args.run_label,
        "authority_material": args.authority_material,
        "phase3_ready_claim": False,
        "remote_repo": args.remote_repo,
        "remote_pjp1": args.pjp1,
        "remote_output": remote_out,
        "ssh": {
            "host": args.host,
            "user": args.user,
            "port": str(args.port),
            "identity_path": os.path.expanduser(args.identity),
        },
        "command_shape": (
            "python3 scripts/termux/run_phase34_pjp1_consumer_preflight.py "
            "--pjp1 PHONE_PJP1 --output PHONE_JSON --label RUN --authority-material MODE"
        ),
        "remote_command": {
            "returncode": result.returncode,
            "stdout_first_4096": result.stdout[:4096],
            "stderr_first_4096": result.stderr[:4096],
        },
        "pull_report": pull_result,
        "nonclaims": [
            "no_phase3_ready_claim",
            "no_npu_htp_execution",
            "no_gpu_optimizer_execution",
            "no_learning_claim",
            "raw_pjp1_not_pulled_to_host",
        ],
    }
    write_json(report_dir / "wrapper_report.json", summary)
    write_text(
        report_dir / "commands.log",
        remote_command.replace(args.pjp1, "PHONE_PJP1").replace(remote_out, "PHONE_JSON") + "\n",
    )
    print(json.dumps({"status": summary["status"], "report_dir": str(report_dir)}))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

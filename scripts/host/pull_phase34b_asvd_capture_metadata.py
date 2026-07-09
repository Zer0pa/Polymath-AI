#!/usr/bin/env python3
"""Pull Phase34B ASVD activation-capture metadata and optional raw captures to scratch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from polymath_ai.polar.task_aligned_projection import (  # noqa: E402
    BLOCKED_STATUS,
    default_raw_boundary,
    report_secret_blockers,
    sha256_file,
    sha256_text,
    utc_stamp,
    write_json,
)


PASS_STATUS = "pass"


def main() -> int:
    args = parse_args()
    report = pull_metadata(args)
    write_json(args.output, report)
    print(args.output)
    return 0 if report["status"] == PASS_STATUS else 2


def pull_metadata(args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[str] = []
    host_scratch = args.host_scratch_root
    metadata_dir = host_scratch / "pulled_metadata"
    captures_dir = host_scratch / "activation_captures"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    captures_dir.mkdir(parents=True, exist_ok=True)

    listing = ssh(args, phone_listing_command(args.phone_root))
    if listing.returncode != 0:
        blockers.append("phone_capture_listing_failed")

    chunk_rows: list[dict[str, Any]] = []
    if not blockers:
        for line in listing.stdout.splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                blockers.append("phone_capture_listing_json_invalid")
                continue
            if isinstance(row, dict):
                chunk_rows.append(row)

    chunk_reports: list[dict[str, Any]] = []
    for row in chunk_rows:
        label = str(row.get("label", ""))
        if not label:
            blockers.append("chunk_label_missing")
            continue
        local_report = metadata_dir / f"{label}_native_report.json"
        local_comet = metadata_dir / f"{label}_comet_result.json"
        local_capture = captures_dir / f"layer24_{label}_capture.f32"
        if row.get("native_report_present") is True:
            scp_one(args, str(row["native_report_path"]), local_report)
        if row.get("comet_result_present") is True:
            scp_one(args, str(row["comet_result_path"]), local_comet)
        capture_pulled = False
        if args.pull_raw_captures and row.get("capture_present") is True:
            scp_one(args, str(row["capture_path"]), local_capture)
            capture_pulled = local_capture.is_file()
        rc = row.get("rc")
        chunk_report = {
            "label": label,
            "rc": rc,
            "native_report_pulled": local_report.is_file(),
            "native_report_sha256": sha256_file(local_report) if local_report.is_file() else "",
            "comet_result_pulled": local_comet.is_file(),
            "comet_result_sha256": sha256_file(local_comet) if local_comet.is_file() else "",
            "capture_present_on_phone": row.get("capture_present") is True,
            "capture_pulled_to_host_scratch": capture_pulled,
            "capture_sha256": sha256_file(local_capture) if capture_pulled else str(row.get("capture_sha256") or ""),
            "capture_bytes": local_capture.stat().st_size if capture_pulled else int(row.get("capture_bytes") or 0),
            "capture_host_path_sha256": sha256_text(str(local_capture)) if capture_pulled else "",
            "record_count": int(row.get("record_count") or 0),
            "progress_bytes": int(row.get("progress_bytes") or 0),
            "raw_rows_embedded": False,
        }
        chunk_reports.append(chunk_report)

    completed = [chunk for chunk in chunk_reports if chunk.get("rc") == 0]
    failed = [chunk for chunk in chunk_reports if chunk.get("rc") not in (None, 0)]
    if failed:
        blockers.append("one_or_more_chunks_failed")
    if args.require_complete and len(completed) != args.expected_chunk_count:
        blockers.append("capture_chain_incomplete")

    rank_trend_input = {
        "run_id": args.run_id,
        "chunks": [
            {
                "activation_capture_f32": str(captures_dir / f"layer24_{chunk['label']}_capture.f32"),
                "record_count": chunk["record_count"],
                "sha256": chunk["capture_sha256"],
            }
            for chunk in chunk_reports
            if chunk.get("capture_pulled_to_host_scratch")
        ],
    }
    rank_trend_path = metadata_dir / "phase34b_rank_trend_input.json"
    rank_trend_path.write_text(json.dumps(rank_trend_input, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report: dict[str, Any] = {
        "schema_version": "phase34b_asvd_capture_metadata_pull_v1",
        "status": PASS_STATUS if not blockers else BLOCKED_STATUS,
        "first_missing_green_field": "none" if not blockers else blockers[0],
        "blockers": list(dict.fromkeys(blockers)),
        "created_utc": utc_stamp(),
        "run_id": args.run_id,
        "phone_root": args.phone_root,
        "phone_root_path_sha256": sha256_text(args.phone_root),
        "chunk_count_observed": len(chunk_reports),
        "chunk_count_complete": len(completed),
        "expected_chunk_count": args.expected_chunk_count,
        "raw_captures_pulled_to_host_scratch": args.pull_raw_captures,
        "rank_trend_input_path": str(rank_trend_path),
        "rank_trend_input_sha256": sha256_file(rank_trend_path),
        "chunk_reports": chunk_reports,
        "raw_boundary": default_raw_boundary(),
        "nonclaims": [
            "metadata pull is not a rank pass",
            "raw captures, if pulled, are outside git scratch and are not embedded",
            "no Gate E pass unless authority report says pass",
        ],
    }
    secret_blockers = report_secret_blockers(report)
    if secret_blockers:
        report["status"] = BLOCKED_STATUS
        report["first_missing_green_field"] = secret_blockers[0]
        report["blockers"] = list(dict.fromkeys([*report["blockers"], *secret_blockers]))
    return report


def phone_listing_command(phone_root: str) -> str:
    quoted = q(phone_root)
    return (
        "python3 - <<'PY'\n"
        "import glob, json, os, hashlib\n"
        f"root={quoted!r}\n"
        "for run in sorted(glob.glob(root + '/runs/chunk*')):\n"
        "    label=os.path.basename(run)\n"
        "    rc_path=f'{run}/reports/{label}_native_rc.txt'\n"
        "    cap_path=f'{run}/raw/layer24_{label}_capture.f32'\n"
        "    report_path=f'{run}/reports/{label}_native_report.json'\n"
        "    comet_path=f'{run}/reports/{label}_comet_result.json'\n"
        "    progress_path=f'{run}/predictions/{label}_predictions.jsonl.progress.jsonl'\n"
        "    record_count=0\n"
        "    chunk_path=f'{root}/chunks/phase34b_asvd_{label}.qa.jsonl'\n"
        "    if os.path.exists(chunk_path):\n"
        "        with open(chunk_path,'rb') as handle:\n"
        "            record_count=sum(1 for _ in handle)\n"
        "    cap_sha=''\n"
        "    if os.path.exists(cap_path):\n"
        "        h=hashlib.sha256()\n"
        "        with open(cap_path,'rb') as handle:\n"
        "            for block in iter(lambda: handle.read(1024*1024), b''):\n"
        "                h.update(block)\n"
        "        cap_sha=h.hexdigest()\n"
        "    rc=None\n"
        "    if os.path.exists(rc_path):\n"
        "        try: rc=int(open(rc_path).read().strip())\n"
        "        except Exception: rc='invalid'\n"
        "    print(json.dumps({\n"
        "        'label': label,\n"
        "        'rc': rc,\n"
        "        'record_count': record_count,\n"
        "        'native_report_present': os.path.exists(report_path),\n"
        "        'native_report_path': report_path,\n"
        "        'comet_result_present': os.path.exists(comet_path),\n"
        "        'comet_result_path': comet_path,\n"
        "        'capture_present': os.path.exists(cap_path),\n"
        "        'capture_path': cap_path,\n"
        "        'capture_sha256': cap_sha,\n"
        "        'capture_bytes': os.path.getsize(cap_path) if os.path.exists(cap_path) else 0,\n"
        "        'progress_bytes': os.path.getsize(progress_path) if os.path.exists(progress_path) else 0,\n"
        "        'raw_rows_embedded': False,\n"
        "    }, sort_keys=True))\n"
        "PY"
    )


def ssh(args: argparse.Namespace, command: str) -> subprocess.CompletedProcess[str]:
    argv = base_ssh(args) + [args.ssh_target, command]
    return subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def scp_one(args: argparse.Namespace, remote: str, local: Path) -> subprocess.CompletedProcess[str]:
    local.parent.mkdir(parents=True, exist_ok=True)
    argv = [
        "scp",
        "-i",
        str(args.ssh_identity.expanduser()),
        "-o",
        "IdentitiesOnly=yes",
        "-P",
        str(args.ssh_port),
        "-o",
        "ConnectTimeout=20",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        f"{args.ssh_target}:{remote}",
        str(local),
    ]
    return subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def base_ssh(args: argparse.Namespace) -> list[str]:
    return [
        "ssh",
        "-i",
        str(args.ssh_identity.expanduser()),
        "-o",
        "IdentitiesOnly=yes",
        "-p",
        str(args.ssh_port),
        "-o",
        "ConnectTimeout=20",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
    ]


def q(value: str) -> str:
    return shlex.quote(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--phone-root", required=True)
    parser.add_argument("--host-scratch-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-chunk-count", type=int, default=16)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--pull-raw-captures", action="store_true")
    parser.add_argument("--ssh-target", default="u0_a536@127.0.0.1")
    parser.add_argument("--ssh-port", type=int, default=18022)
    parser.add_argument("--ssh-identity", type=Path, default=Path("~/.ssh/polymath_host"))
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())

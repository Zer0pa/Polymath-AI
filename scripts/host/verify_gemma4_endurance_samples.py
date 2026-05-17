#!/usr/bin/env python3
"""Verify sampled endurance iterations against the RunPod PyTorch oracle."""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any


REMOTE_HOST = "root@38.80.152.147"
REMOTE_PORT = "31002"
SSH_KEY = "~/.ssh/id_ed25519"
REMOTE_REPO = "/workspace/Polymath-AI"
REMOTE_PYTHON = "/workspace/Polymath-AI/.venv/bin/python"
SNAPSHOT_DIR = "/workspace/models/gemma4_e4b/snapshot"


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, text=True, capture_output=True)
    if check and completed.returncode != 0:
        joined = " ".join(shlex.quote(part) for part in command)
        raise RuntimeError(
            f"command failed ({completed.returncode}): {joined}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def ssh_command(remote_command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(
        [
            "ssh",
            "-i",
            str(Path(SSH_KEY).expanduser()),
            "-p",
            REMOTE_PORT,
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=20",
            REMOTE_HOST,
            remote_command,
        ],
        check=check,
    )


def rsync_to_remote(local_path: Path, remote_path: str) -> None:
    ssh_command(f"mkdir -p {q(remote_path)}")
    run(
        [
            "rsync",
            "-az",
            "--no-owner",
            "--no-group",
            "-e",
            f"ssh -i {Path(SSH_KEY).expanduser()} -p {REMOTE_PORT} -o BatchMode=yes -o ConnectTimeout=20",
            f"{local_path}/",
            f"{REMOTE_HOST}:{remote_path}/",
        ]
    )


def rsync_from_remote(remote_path: str, local_path: Path) -> None:
    local_path.mkdir(parents=True, exist_ok=True)
    run(
        [
            "rsync",
            "-az",
            "--no-owner",
            "--no-group",
            "-e",
            f"ssh -i {Path(SSH_KEY).expanduser()} -p {REMOTE_PORT} -o BatchMode=yes -o ConnectTimeout=20",
            f"{REMOTE_HOST}:{remote_path}/",
            f"{local_path}/",
        ]
    )


def rsync_file_from_remote(remote_path: str, local_path: Path) -> None:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "rsync",
            "-az",
            "--no-owner",
            "--no-group",
            "-e",
            f"ssh -i {Path(SSH_KEY).expanduser()} -p {REMOTE_PORT} -o BatchMode=yes -o ConnectTimeout=20",
            f"{REMOTE_HOST}:{remote_path}",
            str(local_path),
        ]
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def q(value: str) -> str:
    return shlex.quote(value)


def remote_verify_command(sample_remote: str, learning_rate: float) -> str:
    reference = f"{sample_remote}/reference"
    token_cache = f"{sample_remote}/token_cache"
    phone = f"{sample_remote}/phone_output"
    token_metadata = f"{sample_remote}/token_metadata.json"
    layer0_metadata = f"{sample_remote}/layer0_metadata.json"
    layer1_metadata = f"{sample_remote}/layer1_metadata.json"
    layer0_metadata_json = json.dumps(
        {
            "model_id": "google/gemma-4-E4B",
            "revision": "7aa32e6889efd6300124851b164f8b364314c3d8",
            "layer_index": 0,
            "output_shape": [8, 128, 2560],
        },
        separators=(",", ":"),
    )
    layer1_metadata_json = json.dumps(
        {
            "model_id": "google/gemma-4-E4B",
            "revision": "7aa32e6889efd6300124851b164f8b364314c3d8",
            "layer_index": 1,
            "output_shape": [8, 128, 2560],
        },
        separators=(",", ":"),
    )
    parts = [
        "set -e",
        f"cd {q(REMOTE_REPO)}",
        f"printf '%s\\n' {q(layer0_metadata_json)} > {q(token_metadata)}",
        f"cp {q(token_metadata)} {q(layer0_metadata)}",
        f"printf '%s\\n' {q(layer1_metadata_json)} > {q(layer1_metadata)}",
        f"{q(REMOTE_PYTHON)} gemma4_megakernel/tools/reference/create_streamed_distill_reference.py "
        f"--snapshot-dir {q(SNAPSHOT_DIR)} --token-cache {q(token_cache)} "
        f"--checkpoint {q(phone + '/input_checkpoint')} --out {q(reference)} "
        f"--seq 128 --learning-rate {learning_rate}",
        f"{q(REMOTE_PYTHON)} gemma4_megakernel/tools/compare_outputs/compare_outputs.py "
        f"--phone-output {q(phone + '/generated/layer_input.f32.bin')} "
        f"--reference-output {q(reference + '/generated/layer_input.f32.bin')} "
        f"--attention-mask {q(token_cache + '/attention_mask.u8.bin')} "
        f"--manifest {q(token_metadata)} "
        "--shape 8,128,2560 --backend opencl "
        "--device-identity 'nubia NX789J SM8750 FY25013101C8' "
        "--input-dtype f32 --weight-dtype f32 --accumulation-dtype f32 "
        "--phone-dtype f32 --reference-dtype f32 "
        "--phone-command endurance-sample-token-to-hidden "
        "--reference-command create_streamed_distill_reference.py "
        "--expected-layer-index 0 --tensor-name token_to_hidden_layer_input "
        f"--report-json {q(sample_remote + '/token_to_hidden_compare.json')}",
        f"{q(REMOTE_PYTHON)} gemma4_megakernel/tools/compare_outputs/compare_outputs.py "
        f"--phone-output {q(phone + '/layer0_output.f32.bin')} "
        f"--reference-output {q(reference + '/layer0_output.f32.bin')} "
        f"--attention-mask {q(token_cache + '/attention_mask.u8.bin')} "
        f"--manifest {q(layer0_metadata)} "
        "--shape 8,128,2560 --backend opencl "
        "--device-identity 'nubia NX789J SM8750 FY25013101C8' "
        "--input-dtype f32 --weight-dtype f32 --accumulation-dtype f32 "
        "--phone-dtype f32 --reference-dtype f32 "
        "--phone-command endurance-sample-layer0 "
        "--reference-command create_streamed_distill_reference.py "
        "--expected-layer-index 0 --tensor-name endurance_layer0_output "
        f"--report-json {q(sample_remote + '/layer0_compare.json')}",
        f"{q(REMOTE_PYTHON)} gemma4_megakernel/tools/compare_outputs/compare_outputs.py "
        f"--phone-output {q(phone + '/layer1_output.f32.bin')} "
        f"--reference-output {q(reference + '/layer1_output.f32.bin')} "
        f"--attention-mask {q(token_cache + '/attention_mask.u8.bin')} "
        f"--manifest {q(layer1_metadata)} "
        "--shape 8,128,2560 --backend opencl "
        "--device-identity 'nubia NX789J SM8750 FY25013101C8' "
        "--input-dtype f32 --weight-dtype f32 --accumulation-dtype f32 "
        "--phone-dtype f32 --reference-dtype f32 "
        "--phone-command endurance-sample-layer1 "
        "--reference-command create_streamed_distill_reference.py "
        "--expected-layer-index 1 --tensor-name endurance_layer1_output "
        f"--report-json {q(sample_remote + '/layer1_compare.json')}",
        f"{q(REMOTE_PYTHON)} gemma4_megakernel/tools/compare_outputs/compare_adapter_training.py "
        f"--phone-output {q(phone)} --reference {q(reference)} --threshold 0.99 "
        f"--check-update --report {q(sample_remote + '/adapter_update_compare.json')}",
    ]
    return " && ".join(parts)


def collect_status(report: Path) -> dict[str, Any]:
    payload = json.loads(report.read_text(encoding="utf-8"))
    return {
        "path": str(report),
        "status": payload.get("status"),
        "failed_token_count": payload.get("failed_token_count"),
        "failed_tensor_count": payload.get("failed_tensor_count"),
        "p50": payload.get("percentiles", {}).get("p50"),
        "cosine_min": payload.get("cosine_min"),
    }


def update_gate_result(host_report_dir: Path, summary: dict[str, Any]) -> None:
    gate_path = host_report_dir / "gate_result.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    gate["sampled_parity"] = summary
    if summary["status"] != "pass":
        gate["status"] = "fail"
        gate["authority_verdict"] = "six_hour_endurance_not_promoted"
        gate.setdefault("blockers", []).append("sampled parity failed")
    write_json(gate_path, gate)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--host-report-dir", required=True, type=Path)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument(
        "--remote-root",
        default=None,
        help="Remote RunPod sample root. Defaults to /workspace/phase10_endurance_samples/RUN_ID.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = read_jsonl(args.host_report_dir / "iteration_metrics.jsonl")
    sample_records = [record for record in records if record.get("sample")]
    remote_root = args.remote_root or f"/workspace/phase10_endurance_samples/{args.run_id}"
    rsync_to_remote(args.raw_dir / "samples", f"{remote_root}/samples")

    sample_reports: list[dict[str, Any]] = []
    for record in sample_records:
        name = f"iter_{int(record['iteration']):06d}"
        sample_remote = f"{remote_root}/samples/{name}"
        completed = ssh_command(remote_verify_command(sample_remote, args.learning_rate), check=False)
        sample_reports.append(
            {
                "iteration": record["iteration"],
                "remote_sample_dir": sample_remote,
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-4000:],
                "stderr_tail": completed.stderr[-4000:],
            }
        )
    compare_files = (
        "token_to_hidden_compare.json",
        "layer0_compare.json",
        "layer1_compare.json",
        "adapter_update_compare.json",
    )
    for record in sample_records:
        name = f"iter_{int(record['iteration']):06d}"
        for filename in compare_files:
            rsync_file_from_remote(
                f"{remote_root}/samples/{name}/{filename}",
                args.host_report_dir / "sample_parity" / name / filename,
            )

    checks: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for record in sample_records:
        name = f"iter_{int(record['iteration']):06d}"
        base = args.host_report_dir / "sample_parity" / name
        iteration_checks = []
        for filename in compare_files:
            report_path = base / filename
            if report_path.exists():
                status = collect_status(report_path)
            else:
                status = {"path": str(report_path), "status": "missing"}
            iteration_checks.append(status)
            if status.get("status") != "pass":
                failed.append({"iteration": record["iteration"], "check": status})
        checks.append({"iteration": record["iteration"], "checks": iteration_checks})

    summary = {
        "schema_version": "gemma4_phase10_endurance_sample_parity_v1",
        "run_id": args.run_id,
        "status": "pass" if not failed and all(item["returncode"] == 0 for item in sample_reports) else "fail",
        "sample_iterations": [record["iteration"] for record in sample_records],
        "remote_root": remote_root,
        "remote_commands": sample_reports,
        "checks": checks,
        "failed": failed,
    }
    write_json(args.host_report_dir / "sample_parity_summary.json", summary)
    update_gate_result(args.host_report_dir, summary)
    print(json.dumps({"status": summary["status"], "samples": len(sample_records)}, sort_keys=True))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

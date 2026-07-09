#!/usr/bin/env python3
"""Stage and launch detached Phase34B ASVD activation capture chunks on Termux."""

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
TERMUX_HOME = "/data/data/com.termux/files/home"

from polymath_ai.polar.task_aligned_projection import (  # noqa: E402
    BLOCKED_STATUS,
    default_raw_boundary,
    report_secret_blockers,
    repo_contains,
    sha256_file,
    sha256_text,
    utc_stamp,
    write_json,
)


PASS_STATUS = "phase34b_asvd_activation_capture_chain_launched"


def main() -> int:
    args = parse_args()
    report = launch(args)
    write_json(args.output, report)
    print(args.output)
    return 0 if report["status"] == PASS_STATUS else 2


def launch(args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[str] = []
    selected = args.selected_raw_jsonl
    host_scratch = args.host_scratch_root
    chunks_dir = host_scratch / "chunks"
    scripts_dir = host_scratch / "phone_scripts"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)

    if not selected.is_file():
        blockers.append("selected_raw_jsonl_absent")
    if repo_contains(selected, ROOT):
        blockers.append("selected_raw_jsonl_inside_repo")
    if repo_contains(host_scratch, ROOT):
        blockers.append("host_scratch_inside_repo")
    if args.chunk_size <= 0:
        blockers.append("chunk_size_invalid")

    records: list[str] = []
    if selected.is_file():
        records = selected.read_text(encoding="utf-8").splitlines(keepends=True)
    if not records:
        blockers.append("selected_raw_jsonl_empty")

    chunk_paths: list[Path] = []
    if not blockers:
        for index in range(0, len(records), args.chunk_size):
            chunk_index = index // args.chunk_size
            chunk_path = chunks_dir / f"phase34b_asvd_chunk{chunk_index:02d}.qa.jsonl"
            chunk_path.write_text("".join(records[index : index + args.chunk_size]), encoding="utf-8")
            chunk_paths.append(chunk_path)

    session_name = args.session_name or f"phase34b-asvd-{args.run_id}"
    phone_root = args.phone_root.rstrip("/")
    phone_chunks = f"{phone_root}/chunks"
    phone_script = f"{phone_root}/run_phase34b_asvd_capture_chain.sh"
    local_script = scripts_dir / "run_phase34b_asvd_capture_chain.sh"

    commands: list[dict[str, Any]] = []
    if not blockers:
        local_script.write_text(
            phone_chain_script(
                run_id=args.run_id,
                phone_root=phone_root,
                chunk_count=len(chunk_paths),
                chunk_size=args.chunk_size,
                runner=args.phone_runner,
                gate_e_base=args.phone_gate_e_base,
                timeout_seconds=args.timeout_seconds,
            ),
            encoding="utf-8",
        )
        mkdir = ssh(args, f"mkdir -p {q(phone_chunks)} {q(phone_root + '/runs')} {q(phone_root + '/metadata')}")
        commands.append(command_summary("ssh_mkdir_phone_root", mkdir))
        if mkdir.returncode != 0:
            blockers.append("phone_root_stage_failed")

    if not blockers:
        scp_chunks = scp(args, [*chunk_paths, local_script], phone_chunks)
        commands.append(command_summary("scp_chunks_and_script", scp_chunks))
        if scp_chunks.returncode != 0:
            blockers.append("phone_chunk_stage_failed")

    if not blockers:
        install = ssh(args, f"mv {q(phone_chunks + '/' + local_script.name)} {q(phone_script)} && chmod 700 {q(phone_script)}")
        commands.append(command_summary("ssh_install_phone_script", install))
        if install.returncode != 0:
            blockers.append("phone_script_install_failed")

    if not blockers:
        launch_command = (
            f"tmux -L polymath has-session -t {q(session_name)} 2>/dev/null || "
            f"tmux -L polymath new-session -d -s {q(session_name)} {q('/data/data/com.termux/files/usr/bin/bash')} {q(phone_script)}"
        )
        started = ssh(args, launch_command)
        commands.append(command_summary("ssh_tmux_launch", started))
        if started.returncode != 0:
            blockers.append("phone_tmux_launch_failed")

    chunk_reports = [
        {
            "chunk_index": index,
            "record_count": min(args.chunk_size, max(0, len(records) - index * args.chunk_size)),
            "host_chunk_sha256": sha256_file(path),
            "host_chunk_path_sha256": sha256_text(str(path)),
            "phone_chunk_path_sha256": sha256_text(f"{phone_chunks}/{path.name}"),
        }
        for index, path in enumerate(chunk_paths)
    ]
    report: dict[str, Any] = {
        "schema_version": "phase34b_asvd_activation_capture_chain_launch_v1",
        "status": PASS_STATUS if not blockers else BLOCKED_STATUS,
        "first_missing_green_field": "none" if not blockers else blockers[0],
        "blockers": list(dict.fromkeys(blockers)),
        "created_utc": utc_stamp(),
        "run_id": args.run_id,
        "session_name": session_name,
        "phone_root": phone_root,
        "phone_script_path_sha256": sha256_text(phone_script),
        "selected_raw_jsonl_sha256": sha256_file(selected) if selected.is_file() else "",
        "selected_raw_jsonl_path_sha256": sha256_text(str(selected)),
        "selected_record_count": len(records),
        "chunk_size": args.chunk_size,
        "chunk_count": len(chunk_paths),
        "chunk_reports": chunk_reports,
        "phone_runtime": {
            "runner_path_sha256": sha256_text(args.phone_runner),
            "gate_e_base_path_sha256": sha256_text(args.phone_gate_e_base),
            "timeout_seconds_per_chunk": args.timeout_seconds,
            "tmux_detached": True,
            "termux_wakelock_requested": True,
            "comet_workspace": "zer0pa-imc",
            "comet_project_name": "mobile-polymath-ai-training",
        },
        "commands": commands,
        "raw_boundary": default_raw_boundary(),
        "nonclaims": [
            "launch report is not an activation-rank pass",
            "raw calibration rows, predictions, and activation tensors remain outside git",
            "no Gate E pass unless authority report says pass",
        ],
    }
    secret_blockers = report_secret_blockers(report)
    if secret_blockers:
        report["status"] = BLOCKED_STATUS
        report["first_missing_green_field"] = secret_blockers[0]
        report["blockers"] = list(dict.fromkeys([*report["blockers"], *secret_blockers]))
    return report


def phone_chain_script(
    *,
    run_id: str,
    phone_root: str,
    chunk_count: int,
    chunk_size: int,
    runner: str,
    gate_e_base: str,
    timeout_seconds: int,
) -> str:
    lines = [
        "#!/data/data/com.termux/files/usr/bin/bash",
        "set -uo pipefail",
        f"RUN_ID={shlex.quote(run_id)}",
        f"ROOT={shlex.quote(phone_root)}",
        f"CHUNK_COUNT={chunk_count}",
        f"CHUNK_SIZE={chunk_size}",
        f"RUNNER={shlex.quote(runner)}",
        f"BASE={shlex.quote(gate_e_base)}",
        f"TIMEOUT_SECONDS={timeout_seconds}",
        'THETA="$BASE/policy/stable_baseline_zero_theta.f32.bin"',
        'TOKENIZER="$BASE/tokenizer_tables"',
        'DECODER="$BASE/decoder_manifest.json"',
        'POLICY="$BASE/policy/before_stable_native_polar_adapter_site_policy.json"',
        'mkdir -p "$ROOT/runs" "$ROOT/metadata"',
        'termux-wake-lock >/dev/null 2>&1 || true',
        'trap \'termux-wake-unlock >/dev/null 2>&1 || true\' EXIT',
        'printf \'{"event":"chain_started","run_id":"%s","chunk_count":%s,"raw_rows_embedded":false}\\n\' "$RUN_ID" "$CHUNK_COUNT" > "$ROOT/metadata/chain_events.jsonl"',
        'export COMET_WORKSPACE=zer0pa-imc COMET_PROJECT_NAME=mobile-polymath-ai-training',
        'export COMET_DISABLE_AUTO_LOGGING=1 COMET_AUTO_LOG_DISABLE=1 COMET_LOG_ENV_DETAILS=false COMET_LOG_GIT_METADATA=false COMET_LOG_CODE=false COMET_LOG_GRAPH=false',
        'if [ -f "$HOME/.termux_agent_env" ]; then . "$HOME/.termux_agent_env"; export COMET_WORKSPACE=zer0pa-imc COMET_PROJECT_NAME=mobile-polymath-ai-training; fi',
        'overall_status=0',
        'for chunk in "$ROOT"/chunks/phase34b_asvd_chunk*.qa.jsonl; do',
        '  name="$(basename "$chunk" .qa.jsonl)"',
        '  label="${name#phase34b_asvd_}"',
        '  run="$ROOT/runs/$label"',
        '  mkdir -p "$run/raw" "$run/reports" "$run/predictions"',
        '  out="$run/predictions/${label}_predictions.jsonl"',
        '  cap="$run/raw/layer24_${label}_capture.f32"',
        '  report="$run/reports/${label}_native_report.json"',
        '  stderr="$run/reports/${label}_native_stderr.log"',
        '  rcfile="$run/reports/${label}_native_rc.txt"',
        '  events="$run/reports/${label}_events.jsonl"',
        '  if [ -f "$rcfile" ] && [ "$(cat "$rcfile" 2>/dev/null)" = "0" ]; then',
        '    printf \'{"event":"chunk_skipped_existing_pass","label":"%s","raw_rows_embedded":false}\\n\' "$label" >> "$ROOT/metadata/chain_events.jsonl"',
        '    continue',
        '  fi',
        '  record_count="$(wc -l < "$chunk" | tr -d " ")"',
        '  printf \'{"event":"chunk_started","label":"%s","record_count":%s,"raw_rows_embedded":false}\\n\' "$label" "$record_count" > "$events"',
        '  timeout "$TIMEOUT_SECONDS" "$RUNNER" --run-c5-qa-predict \\',
        '    --run-label "phase34b-h1-asvd-${label}" \\',
        '    --eval-point C5_after_C2 \\',
        '    --checkpoint-role stable_baseline \\',
        '    --checkpoint-payload "$THETA" \\',
        '    --checkpoint-sha256 5f70bf18a086007016e948b04aed3b82103a36bea41755b6cddfaf10ace3c6ef \\',
        '    --heldout-qa-jsonl "$chunk" \\',
        '    --output-jsonl "$out" \\',
        '    --tokenizer-dir "$TOKENIZER" \\',
        '    --decoder-manifest "$DECODER" \\',
        '    --adapter-site-policy "$POLICY" \\',
        '    --vocab-chunk-size 4096 \\',
        '    --max-generation-tokens 1 \\',
        '    --max-heldout-records "$CHUNK_SIZE" \\',
        '    --activation-capture-f32 "$cap" \\',
        '    --activation-capture-layer 24 \\',
        '    > "$report" 2> "$stderr"',
        '  status=$?',
        '  printf "%s\\n" "$status" > "$rcfile"',
        '  if [ -f "$cap" ]; then sha256sum "$cap" > "$run/reports/${label}_capture_sha256.txt"; stat -c "%s" "$cap" > "$run/reports/${label}_capture_bytes.txt"; fi',
        '  if [ -f "$out.progress.jsonl" ]; then sha256sum "$out.progress.jsonl" > "$run/reports/${label}_progress_sha256.txt"; fi',
        '  sha256sum "$report" "$stderr" "$rcfile" > "$run/reports/${label}_hashes.txt" 2>/dev/null || true',
        '  printf \'{"event":"chunk_finished","label":"%s","rc":%s,"raw_rows_embedded":false}\\n\' "$label" "$status" >> "$events"',
        '  printf \'{"event":"chunk_finished","label":"%s","rc":%s,"raw_rows_embedded":false}\\n\' "$label" "$status" >> "$ROOT/metadata/chain_events.jsonl"',
        '  if [ "$status" -eq 0 ] && [ -f "$HOME/Polymath-AI/scripts/host/log_apex_metadata_report_to_comet.py" ]; then',
        '    (cd "$HOME/Polymath-AI" && python3 scripts/host/log_apex_metadata_report_to_comet.py --gate PHASE34 --report "$report" --run-name "phase34b-asvd-${label}" --output "$run/reports/${label}_comet_result.json") >/dev/null 2>"$run/reports/${label}_comet_stderr.log" || true',
        '  fi',
        '  if [ "$status" -ne 0 ]; then overall_status="$status"; break; fi',
        'done',
        'printf \'{"event":"chain_finished","rc":%s,"raw_rows_embedded":false}\\n\' "$overall_status" >> "$ROOT/metadata/chain_events.jsonl"',
        'printf "%s\\n" "$overall_status" > "$ROOT/metadata/chain_rc.txt"',
        'exit "$overall_status"',
        "",
    ]
    return "\n".join(lines)


def ssh(args: argparse.Namespace, command: str) -> subprocess.CompletedProcess[str]:
    argv = [
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
        args.ssh_target,
        command,
    ]
    return subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def scp(args: argparse.Namespace, sources: list[Path], dest_dir: str) -> subprocess.CompletedProcess[str]:
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
        *[str(path) for path in sources],
        f"{args.ssh_target}:{dest_dir}/",
    ]
    return subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def command_summary(name: str, completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "name": name,
        "rc": completed.returncode,
        "stdout_bytes": len(completed.stdout.encode("utf-8")),
        "stderr_bytes": len(completed.stderr.encode("utf-8")),
        "stdout_sha256": sha256_text(completed.stdout),
        "stderr_sha256": sha256_text(completed.stderr),
        "raw_stdout_stderr_embedded": False,
    }


def q(value: str) -> str:
    return shlex.quote(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--selected-raw-jsonl", required=True, type=Path)
    parser.add_argument("--host-scratch-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--phone-root", default="")
    parser.add_argument("--chunk-size", type=int, default=8)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--session-name", default="")
    parser.add_argument("--ssh-target", default="u0_a536@127.0.0.1")
    parser.add_argument("--ssh-port", type=int, default=18022)
    parser.add_argument("--ssh-identity", type=Path, default=Path("~/.ssh/polymath_host"))
    parser.add_argument(
        "--phone-runner",
        default=f"{TERMUX_HOME}/Polymath-AI/build/termux-phase34-capture-20260708/gemma4_layer_runner",
    )
    parser.add_argument(
        "--phone-gate-e-base",
        default=f"{TERMUX_HOME}/polymath_phone_native_gate_e_20260708/gate_e_c2_jl",
    )
    args = parser.parse_args()
    if not args.phone_root:
        args.phone_root = f"{TERMUX_HOME}/polymath_phase34b_{args.run_id}/asvd_activation_capture"
    return args


if __name__ == "__main__":
    raise SystemExit(main())

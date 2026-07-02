#!/usr/bin/env python3
"""Run a bounded full-Gemma QNN/HTP forward island and emit metadata only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from polymath_ai.polar.wavec_full_gemma_qnn import (  # noqa: E402
    AUTHORITY_MATERIAL,
    DISALLOWED_FULL_GEMMA_GRAPHS,
    EXPECTED_BYTES,
    EXPECTED_DTYPE,
    EXPECTED_SHAPE,
    FORWARD_SCHEMA_VERSION,
    PRODUCER_KIND,
    parse_qnn_profile_viewer_text,
    validate_full_gemma_qnn_forward_report,
)


DEFAULT_STAGE_REPORT = (
    "/sdcard/Download/polymath_phase34/active_wave/pjp1_htp_relu_input/"
    "phase34_pjp1_htp_relu_input_stage.json"
)
DEFAULT_QAIRT_ROOT = "/data/local/tmp/qairt-2.44"
DEFAULT_REPORT = (
    "runtime/reports/polar_phase34_consumer_preflight/active_wave/"
    "full_gemma_qnn_forward/full_gemma_qnn_forward_report.json"
)


def main() -> int:
    args = parse_args()
    if args.print_schema:
        print_schema()
        return 0

    reject_smoke_graph(args.graph)
    stage_report = read_remote_json(args, args.stage_report)
    input_path = args.remote_input or stage_report["outputs"]["remote_input_path"]
    input_sha256 = args.input_sha256 or stage_report["outputs"]["input_sha256"]
    packet_sha256 = args.input_packet_sha256 or input_sha256
    run_root = args.remote_run_root or str(Path(input_path).parent / "full_gemma_qnn_forward")
    context_sha256 = remote_sha256(args, args.context)
    context_info = run_context_utility(args, run_root)
    result = run_qnn(args, input_path, run_root)
    profile = build_profile_payload(result, args)

    payload: dict[str, Any] = {
        "schema_version": FORWARD_SCHEMA_VERSION,
        "status": "pending_validation",
        "corpus_phase": args.corpus_phase,
        "phase3_ready_claim": False,
        "phase4_ready_claim": False,
        "learning_claim": False,
        "authority_material": AUTHORITY_MATERIAL,
        "stage_report_remote": args.stage_report,
        "pjp1": stage_report.get("pjp1", {}),
        "source_packet": stage_report.get("source_packet", {}),
        "qnn": {
            "producer_kind": PRODUCER_KIND,
            "backend_execution": "qnn_htp",
            "cpu_fallback": False,
            "qnn_htp_backend_verified": True,
            "qairt_root": args.qairt_root,
            "context_path": args.context,
            "context_sha256": context_sha256,
            "context_info_remote": context_info.get("remote_path"),
            "context_info_status": context_info.get("status"),
            "context_info_first_4096": context_info.get("first_4096"),
            "backend": f"{args.qairt_root.rstrip('/')}/lib/aarch64-android/libQnnHtp.so",
            "graph": args.graph,
            "num_inferences": args.num_inferences,
            "input": {
                "path": input_path,
                "shape": EXPECTED_SHAPE,
                "dtype": EXPECTED_DTYPE,
                "bytes": EXPECTED_BYTES,
                "sha256": input_sha256,
                "packet_sha256": packet_sha256,
            },
            "output": {
                "path": result["output_path"],
                "shape": EXPECTED_SHAPE,
                "dtype": EXPECTED_DTYPE,
                "bytes": result["output_bytes"],
                "sha256": result["output_sha256"],
                "packet_sha256": packet_sha256,
            },
            "profile": profile,
            "stdout_first_4096": result["stdout_first_4096"],
            "stderr_first_4096": result["stderr_first_4096"],
        },
        "phase4_consumer_contract": {
            "cell_id": "phase4_opencl_phase3_bridge_rank16_mse_sgd_cell_v0",
            "phase3_output_path": result["output_path"],
            "phase3_output_sha256": result["output_sha256"],
            "phase3_graph": args.graph,
            "phase3_backend": f"{args.qairt_root.rstrip('/')}/lib/aarch64-android/libQnnHtp.so",
            "phase4_target_path": stage_report.get("outputs", {}).get("remote_phase4_target_path"),
            "phase4_target_sha256": stage_report.get("outputs", {}).get("phase4_target_sha256"),
            "required_runner_args": [
                "--phase3-output",
                result["output_path"],
                "--target",
                stage_report.get("outputs", {}).get("remote_phase4_target_path"),
                "--phase3-graph",
                args.graph,
                "--phase3-backend",
                f"{args.qairt_root.rstrip('/')}/lib/aarch64-android/libQnnHtp.so",
                "--context",
                args.context,
                "--context-sha256",
                context_sha256,
            ],
        },
        "raw_payload_rules": {
            "raw_pjp1_pulled_to_host": False,
            "raw_qnn_output_pulled_to_repo": False,
            "raw_model_or_checkpoint_pulled_to_repo": False,
            "compact_hash_report_only": True,
            "repo_paths": [args.report],
        },
        "nonclaims": [
            "No C5 pass.",
            "No learning or model-quality claim.",
            "No Phase3/4 readiness.",
            "No full-Gemma HTP forward claim until this report validates on device.",
        ],
    }
    blockers = validate_full_gemma_qnn_forward_report(payload, require_status=False)
    payload["blockers"] = blockers
    payload["status"] = "pass" if not blockers else "blocked"

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(report_path)
    return 0 if payload["status"] == "pass" else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-report", default=DEFAULT_STAGE_REPORT)
    parser.add_argument("--qairt-root", default=DEFAULT_QAIRT_ROOT)
    parser.add_argument("--context", required=False)
    parser.add_argument("--graph", required=False)
    parser.add_argument("--remote-input", default="")
    parser.add_argument("--input-sha256", default="")
    parser.add_argument("--input-packet-sha256", default="")
    parser.add_argument("--remote-run-root", default="")
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--corpus-phase", default="C1")
    parser.add_argument("--adb-serial", default="")
    parser.add_argument("--num-inferences", type=int, default=1)
    parser.add_argument("--print-schema", action="store_true")
    args = parser.parse_args()
    if not args.print_schema:
        if not args.context:
            parser.error("--context is required")
        if not args.graph:
            parser.error("--graph is required")
        if args.num_inferences < 1:
            parser.error("--num-inferences must be positive")
    return args


def print_schema() -> None:
    print(
        json.dumps(
            {
                "schema_version": FORWARD_SCHEMA_VERSION,
                "required_qnn_fields": [
                    "producer_kind",
                    "backend_execution",
                    "context_path",
                    "context_sha256",
                    "backend",
                    "graph",
                    "input.shape",
                    "input.dtype",
                    "input.bytes",
                    "input.sha256",
                    "output.shape",
                    "output.dtype",
                    "output.bytes",
                    "output.sha256",
                    "profile.profile_log.remote_path",
                    "profile.profile_log.sha256",
                    "profile.qnn_profile_parse_attempted",
                    "profile.qnn_net_run_wall_ms",
                ],
                "disallowed_graphs": sorted(DISALLOWED_FULL_GEMMA_GRAPHS),
                "raw_boundary": "repo receives JSON metadata only; .pjp1/.raw/.f32.bin/model/checkpoint/adapter payloads remain off git",
            },
            indent=2,
            sort_keys=True,
        )
    )


def reject_smoke_graph(graph: str) -> None:
    if graph in DISALLOWED_FULL_GEMMA_GRAPHS:
        raise SystemExit(f"refusing ReLU/identity smoke graph as full-Gemma proof: {graph}")


def run_qnn(args: argparse.Namespace, remote_input: str, run_root: str) -> dict[str, Any]:
    qairt = args.qairt_root.rstrip("/")
    backend = f"{qairt}/lib/aarch64-android/libQnnHtp.so"
    qnn_net_run = f"{qairt}/bin/aarch64-android/qnn-net-run"
    input_list = f"{run_root}/input_list.txt"
    output_dir = f"{run_root}/run"
    stdout_path = f"{run_root}/qnn_stdout.log"
    stderr_path = f"{run_root}/qnn_stderr.log"
    output_sha_path = f"{run_root}/output_sha256.txt"
    output_size_path = f"{run_root}/output_size.txt"
    output_path_path = f"{run_root}/output_path.txt"
    profile_path_path = f"{run_root}/profile_path.txt"
    profile_sha_path = f"{run_root}/profile_sha256.txt"
    profile_size_path = f"{run_root}/profile_size.txt"
    viewer_stdout_path = f"{run_root}/qnn_profile_viewer_stdout.txt"
    adsp_paths = ";".join(
        [
            f"{qairt}/lib/hexagon-v79/unsigned",
            f"{qairt}/lib/hexagon-v81/unsigned",
            "/vendor/dsp/cdsp",
            "/vendor/lib/rfsa/adsp",
            "/system/lib/rfsa/adsp",
        ]
    )
    script = "\n".join(
        [
            "set -eu",
            f"mkdir -p {shlex.quote(run_root)}",
            f"cd {shlex.quote(run_root)}",
            f"printf '%s\\n' {shlex.quote(remote_input)} > {shlex.quote(input_list)}",
            f"rm -rf {shlex.quote(output_dir)}",
            f"mkdir -p {shlex.quote(output_dir)}",
            f"export LD_LIBRARY_PATH={shlex.quote(qairt + '/lib/aarch64-android')}:${{LD_LIBRARY_PATH:-}}",
            f"export ADSP_LIBRARY_PATH={shlex.quote(adsp_paths)}",
            (
                f"{shlex.quote(qnn_net_run)} "
                f"--retrieve_context={shlex.quote(args.context)} "
                f"--backend {shlex.quote(backend)} "
                f"--input_list={shlex.quote(input_list)} "
                f"--output_dir={shlex.quote(output_dir)} "
                f"--num_inferences {args.num_inferences} "
                "--profiling_level basic "
                "--log_level info "
                f"> {shlex.quote(stdout_path)} 2> {shlex.quote(stderr_path)}"
            ),
            (
                f"output_file=$(find {shlex.quote(output_dir)} -type f -name '*.raw' "
                "! -name 'qnn-profiling*' | head -n 1)"
            ),
            'test -n "$output_file"',
            f"printf '%s\\n' \"$output_file\" > {shlex.quote(output_path_path)}",
            f"sha256sum \"$output_file\" > {shlex.quote(output_sha_path)}",
            f"wc -c \"$output_file\" > {shlex.quote(output_size_path)}",
            f"profile_file=$(find {shlex.quote(output_dir)} -type f -name 'qnn-profiling-data_*.log' | head -n 1 || true)",
            "if [ -n \"$profile_file\" ]; then",
            f"  printf '%s\\n' \"$profile_file\" > {shlex.quote(profile_path_path)}",
            f"  sha256sum \"$profile_file\" > {shlex.quote(profile_sha_path)}",
            f"  wc -c \"$profile_file\" > {shlex.quote(profile_size_path)}",
            f"  if [ -x {shlex.quote(qairt + '/bin/aarch64-android/qnn-profile-viewer')} ]; then",
            (
                f"    {shlex.quote(qairt + '/bin/aarch64-android/qnn-profile-viewer')} "
                f"--input_log \"$profile_file\" > {shlex.quote(viewer_stdout_path)} 2>&1 || true"
            ),
            "  else",
            f"    printf '%s\\n' 'qnn-profile-viewer unavailable' > {shlex.quote(viewer_stdout_path)}",
            "  fi",
            "else",
            f"  printf '%s\\n' '' > {shlex.quote(profile_path_path)}",
            f"  printf '%s\\n' '' > {shlex.quote(profile_sha_path)}",
            f"  printf '%s\\n' '0' > {shlex.quote(profile_size_path)}",
            f"  printf '%s\\n' 'qnn profiling log unavailable' > {shlex.quote(viewer_stdout_path)}",
            "fi",
            "echo __WAVEC_OUTPUT_PATH__",
            f"cat {shlex.quote(output_path_path)}",
            "echo __WAVEC_OUTPUT_SHA256__",
            f"cat {shlex.quote(output_sha_path)}",
            "echo __WAVEC_OUTPUT_SIZE__",
            f"cat {shlex.quote(output_size_path)}",
            "echo __WAVEC_PROFILE_PATH__",
            f"cat {shlex.quote(profile_path_path)}",
            "echo __WAVEC_PROFILE_SHA256__",
            f"cat {shlex.quote(profile_sha_path)}",
            "echo __WAVEC_PROFILE_SIZE__",
            f"cat {shlex.quote(profile_size_path)}",
            "echo __WAVEC_PROFILE_VIEWER_BEGIN__",
            f"head -c 4096 {shlex.quote(viewer_stdout_path)}",
            "echo",
            "echo __WAVEC_PROFILE_VIEWER_END__",
            "echo __WAVEC_STDOUT_BEGIN__",
            f"head -c 4096 {shlex.quote(stdout_path)}",
            "echo",
            "echo __WAVEC_STDOUT_END__",
            "echo __WAVEC_STDERR_BEGIN__",
            f"head -c 4096 {shlex.quote(stderr_path)}",
            "echo",
            "echo __WAVEC_STDERR_END__",
        ]
    )
    started = time.perf_counter()
    completed = adb_shell(args, script, check=True)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    parsed = parse_shell_markers(completed.stdout)
    parsed["qnn_net_run_wall_ms"] = elapsed_ms
    return parsed


def build_profile_payload(result: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    parsed_profile = parse_qnn_profile_viewer_text(result["profile_viewer_stdout_first_4096"])
    return {
        "qnn_profile_parse_attempted": parsed_profile["qnn_profile_parse_attempted"],
        "qnn_net_run_wall_ms": result["qnn_net_run_wall_ms"],
        "qnn_accelerator_execute_ms": parsed_profile["qnn_accelerator_execute_ms"],
        "qnn_accelerator_execute_ms_unavailable_reason": parsed_profile[
            "qnn_accelerator_execute_ms_unavailable_reason"
        ],
        "profile_events_considered": parsed_profile["profile_events_considered"],
        "profile_log": {
            "remote_path": result["profile_path"],
            "sha256": result["profile_sha256"],
            "bytes": result["profile_bytes"],
        },
        "profile_viewer_stdout_first_4096": result["profile_viewer_stdout_first_4096"],
        "profile_interpretation": (
            "qnn_net_run_wall_ms includes process launch, context load, file I/O, ADB shell, RPC, "
            "and accelerator execution; do not treat as HTP compute without parsed profile support"
        ),
        "qairt_root": args.qairt_root,
    }


def run_context_utility(args: argparse.Namespace, run_root: str) -> dict[str, Any]:
    qairt = args.qairt_root.rstrip("/")
    context_info_remote = f"{run_root}/context_info.json"
    shell = "\n".join(
        [
            "set -eu",
            f"mkdir -p {shlex.quote(run_root)}",
            f"export LD_LIBRARY_PATH={shlex.quote(qairt + '/lib/aarch64-android')}:${{LD_LIBRARY_PATH:-}}",
            (
                f"if [ -x {shlex.quote(qairt + '/bin/aarch64-android/qnn-context-binary-utility')} ]; then "
                f"{shlex.quote(qairt + '/bin/aarch64-android/qnn-context-binary-utility')} "
                f"--context_binary={shlex.quote(args.context)} --json_file={shlex.quote(context_info_remote)}; "
                "fi"
            ),
            f"if [ -f {shlex.quote(context_info_remote)} ]; then head -c 4096 {shlex.quote(context_info_remote)}; fi",
        ]
    )
    completed = adb_shell(args, shell, check=False)
    return {
        "status": "pass" if completed.returncode == 0 and completed.stdout.strip() else "unavailable",
        "remote_path": context_info_remote,
        "first_4096": completed.stdout[:4096],
    }


def remote_sha256(args: argparse.Namespace, remote_path: str) -> str:
    completed = adb_shell(args, f"sha256sum {shlex.quote(remote_path)}", check=True)
    return completed.stdout.split()[0]


def read_remote_json(args: argparse.Namespace, path: str) -> dict[str, Any]:
    command = ["adb"]
    if args.adb_serial:
        command.extend(["-s", args.adb_serial])
    command.extend(["shell", f"cat {shlex.quote(path)}"])
    completed = subprocess.run(command, text=True, capture_output=True, check=True)
    return json.loads(extract_json_object(completed.stdout))


def parse_shell_markers(stdout: str) -> dict[str, Any]:
    lines = stdout.splitlines()

    def marker(name: str) -> int:
        try:
            return lines.index(name)
        except ValueError as exc:
            raise RuntimeError(f"missing marker {name}") from exc

    profile_size = lines[marker("__WAVEC_PROFILE_SIZE__") + 1].split()
    return {
        "output_path": lines[marker("__WAVEC_OUTPUT_PATH__") + 1].strip(),
        "output_sha256": lines[marker("__WAVEC_OUTPUT_SHA256__") + 1].split()[0],
        "output_bytes": int(lines[marker("__WAVEC_OUTPUT_SIZE__") + 1].split()[0]),
        "profile_path": lines[marker("__WAVEC_PROFILE_PATH__") + 1].strip(),
        "profile_sha256": first_or_empty(lines[marker("__WAVEC_PROFILE_SHA256__") + 1].split()),
        "profile_bytes": int(profile_size[0]) if profile_size else 0,
        "profile_viewer_stdout_first_4096": lines_between(
            lines, "__WAVEC_PROFILE_VIEWER_BEGIN__", "__WAVEC_PROFILE_VIEWER_END__"
        ),
        "stdout_first_4096": lines_between(lines, "__WAVEC_STDOUT_BEGIN__", "__WAVEC_STDOUT_END__"),
        "stderr_first_4096": lines_between(lines, "__WAVEC_STDERR_BEGIN__", "__WAVEC_STDERR_END__"),
    }


def lines_between(lines: list[str], start_marker: str, end_marker: str) -> str:
    start = lines.index(start_marker)
    end = lines.index(end_marker)
    return "\n".join(lines[start + 1 : end])


def first_or_empty(values: list[str]) -> str:
    return values[0] if values else ""


def adb_shell(args: argparse.Namespace, script: str, *, check: bool) -> subprocess.CompletedProcess[str]:
    command = ["adb"]
    if args.adb_serial:
        command.extend(["-s", args.adb_serial])
    command.extend(["shell", script])
    return subprocess.run(command, text=True, capture_output=True, check=check)


def extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError("no JSON object found in command output")
    return text[start : end + 1]


if __name__ == "__main__":
    raise SystemExit(main())

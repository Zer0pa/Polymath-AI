#!/usr/bin/env python3
"""Run a bounded synthetic HTP ReLU smoke against the phone QNN context."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shlex
import struct
import subprocess
import tempfile
from typing import Any


DEFAULT_QAIRT_ROOT = "/data/local/tmp/qairt-2.44"
DEFAULT_CONTEXT = (
    "/data/local/tmp/polymath_gemma4_gate/phase13/"
    "20260524T210920Z_phase13_gemma4_only_heterogeneous/"
    "p13f/htp/relu/context/gemma_hidden2560_relu.qnn.bin"
)
DEFAULT_REMOTE_ROOT = "/data/local/tmp/polymath_phase34/active_wave/htp_relu_smoke"
DEFAULT_REPORT = (
    "runtime/reports/polar_phase34_consumer_preflight/active_wave/"
    "htp_relu_smoke/phase34_adb_htp_relu_smoke.json"
)
FLOAT_COUNT = 1 * 16 * 2560
EXPECTED_BYTES = FLOAT_COUNT * 4


@dataclass(frozen=True)
class TensorCase:
    name: str
    input_bytes: bytes
    expected_relu_bytes: bytes

    @property
    def input_sha256(self) -> str:
        return sha256_bytes(self.input_bytes)

    @property
    def expected_output_sha256(self) -> str:
        return sha256_bytes(self.expected_relu_bytes)


def main() -> int:
    args = parse_args()
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    cases = [
        make_tensor_case("alternating_signed", offset=0),
        make_tensor_case("phase_shifted_signed", offset=5),
    ]

    context_info_remote = f"{args.remote_root.rstrip('/')}/context_info.json"
    context_info = run_context_utility(args, context_info_remote)

    case_reports = []
    with tempfile.TemporaryDirectory(prefix="phase34_htp_relu_smoke_") as temp_dir:
        temp = Path(temp_dir)
        for case in cases:
            local_input = temp / f"{case.name}.f32.bin"
            local_input.write_bytes(case.input_bytes)
            case_reports.append(run_case(args, case, local_input))

    output_hashes = [case_report["actual_output_sha256"] for case_report in case_reports]
    all_match_expected = all(case_report["actual_matches_expected"] for case_report in case_reports)
    output_change_proof = len(set(output_hashes)) == len(output_hashes)

    payload: dict[str, Any] = {
        "schema_version": "polar_phase34_adb_htp_relu_smoke_v1",
        "status": "pass" if all_match_expected and output_change_proof else "fail",
        "phase3_ready_claim": False,
        "phase4_ready_claim": False,
        "learning_claim": False,
        "authority_material": "synthetic_htp_functionality_smoke_only",
        "nonclaims": [
            "This is not Phase 3 readiness.",
            "This is not a real-corpus gate.",
            "This does not consume PJP1.",
            "This does not prove Gemma forward correctness.",
            "This does not prove learning or model-quality movement.",
            "This does not authorize C1-C4 execution.",
        ],
        "device": {
            "adb_serial": args.adb_serial or "default",
        },
        "qairt_root": args.qairt_root,
        "context": args.context,
        "backend": f"{args.qairt_root.rstrip('/')}/lib/aarch64-android/libQnnHtp.so",
        "remote_root": args.remote_root,
        "tensor_shape": [1, 16, 2560],
        "tensor_dtype": "float32_le",
        "expected_bytes": EXPECTED_BYTES,
        "context_info_remote": context_info_remote,
        "context_info": context_info,
        "cases": case_reports,
        "all_outputs_match_expected_relu": all_match_expected,
        "output_change_proof": output_change_proof,
        "raw_payload_rules": {
            "raw_pjp1_pulled_to_host": False,
            "raw_qnn_outputs_pulled_to_repo": False,
            "inputs_are_synthetic": True,
            "repo_contains_hashes_and_logs_only": True,
        },
        "next_required_for_phase3": [
            "Generate the HTP input from phone-local PJP1 through Termux without pulling raw PJP1.",
            "Consume the HTP output in a named route/objective/teacher/state transition.",
            "Record CPU parity, output-change proof, copy counts, and failure routing.",
        ],
    }

    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(report_path)
    return 0 if payload["status"] == "pass" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qairt-root", default=DEFAULT_QAIRT_ROOT)
    parser.add_argument("--context", default=DEFAULT_CONTEXT)
    parser.add_argument("--remote-root", default=DEFAULT_REMOTE_ROOT)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--adb-serial", default="")
    return parser.parse_args()


def make_tensor_case(name: str, *, offset: int) -> TensorCase:
    values = []
    relu_values = []
    for index in range(FLOAT_COUNT):
        raw = ((index + offset) % 31) - 15
        value = raw / 8.0
        values.append(value)
        relu_values.append(value if value > 0.0 else 0.0)
    return TensorCase(
        name=name,
        input_bytes=pack_f32(values),
        expected_relu_bytes=pack_f32(relu_values),
    )


def pack_f32(values: list[float]) -> bytes:
    return struct.pack("<" + "f" * len(values), *values)


def run_context_utility(args: argparse.Namespace, context_info_remote: str) -> dict[str, Any]:
    qairt = args.qairt_root.rstrip("/")
    remote_dir = str(Path(context_info_remote).parent)
    shell = "\n".join(
        [
            "set -eu",
            f"mkdir -p {shlex.quote(remote_dir)}",
            f"export LD_LIBRARY_PATH={shlex.quote(qairt + '/lib/aarch64-android')}:${{LD_LIBRARY_PATH:-}}",
            (
                f"{shlex.quote(qairt + '/bin/aarch64-android/qnn-context-binary-utility')} "
                f"--context_binary={shlex.quote(args.context)} "
                f"--json_file={shlex.quote(context_info_remote)}"
            ),
        ]
    )
    adb_shell(args, shell, check=True)
    result = adb_shell(args, f"cat {shlex.quote(context_info_remote)}", check=True)
    return json.loads(extract_json_object(result.stdout))


def run_case(args: argparse.Namespace, case: TensorCase, local_input: Path) -> dict[str, Any]:
    qairt = args.qairt_root.rstrip("/")
    remote_root = args.remote_root.rstrip("/")
    case_root = f"{remote_root}/{case.name}"
    remote_input = f"{case_root}/{local_input.name}"
    remote_input_list = f"{case_root}/input_list.txt"
    output_dir = f"{case_root}/run"
    stdout_path = f"{case_root}/qnn_stdout.log"
    stderr_path = f"{case_root}/qnn_stderr.log"
    output_sha_path = f"{case_root}/output_sha256.txt"
    output_size_path = f"{case_root}/output_size.txt"
    output_path_path = f"{case_root}/output_path.txt"
    backend = f"{qairt}/lib/aarch64-android/libQnnHtp.so"
    qnn_net_run = f"{qairt}/bin/aarch64-android/qnn-net-run"

    adb_shell(args, f"mkdir -p {shlex.quote(case_root)}", check=True)
    adb_push(args, local_input, remote_input)
    adb_shell(
        args,
        f"printf '%s\\n' {shlex.quote(local_input.name)} > {shlex.quote(remote_input_list)}",
        check=True,
    )

    adsp_paths = ";".join(
        [
            f"{qairt}/lib/hexagon-v79/unsigned",
            f"{qairt}/lib/hexagon-v81/unsigned",
            "/vendor/dsp/cdsp",
            "/vendor/lib/rfsa/adsp",
            "/system/lib/rfsa/adsp",
        ]
    )
    shell = "\n".join(
        [
            "set -eu",
            f"cd {shlex.quote(case_root)}",
            f"rm -rf {shlex.quote(output_dir)}",
            f"mkdir -p {shlex.quote(output_dir)}",
            f"export LD_LIBRARY_PATH={shlex.quote(qairt + '/lib/aarch64-android')}:${{LD_LIBRARY_PATH:-}}",
            f"export ADSP_LIBRARY_PATH={shlex.quote(adsp_paths)}",
            (
                f"{shlex.quote(qnn_net_run)} "
                f"--retrieve_context={shlex.quote(args.context)} "
                f"--backend {shlex.quote(backend)} "
                f"--input_list={shlex.quote(remote_input_list)} "
                f"--output_dir={shlex.quote(output_dir)} "
                "--num_inferences 1 "
                "--profiling_level basic "
                "--log_level info "
                f"> {shlex.quote(stdout_path)} 2> {shlex.quote(stderr_path)}"
            ),
            f"output_file=$(find {shlex.quote(output_dir)} -type f -name '*.raw' | head -n 1)",
            'test -n "$output_file"',
            f"printf '%s\\n' \"$output_file\" > {shlex.quote(output_path_path)}",
            f"sha256sum \"$output_file\" > {shlex.quote(output_sha_path)}",
            f"wc -c \"$output_file\" > {shlex.quote(output_size_path)}",
            "echo __PHASE34_OUTPUT_PATH__",
            f"cat {shlex.quote(output_path_path)}",
            "echo __PHASE34_OUTPUT_SHA256__",
            f"cat {shlex.quote(output_sha_path)}",
            "echo __PHASE34_OUTPUT_SIZE__",
            f"cat {shlex.quote(output_size_path)}",
            "echo __PHASE34_STDOUT_BEGIN__",
            f"head -c 4096 {shlex.quote(stdout_path)}",
            "echo",
            "echo __PHASE34_STDOUT_END__",
            "echo __PHASE34_STDERR_BEGIN__",
            f"head -c 4096 {shlex.quote(stderr_path)}",
            "echo",
            "echo __PHASE34_STDERR_END__",
        ]
    )
    result = adb_shell(args, shell, check=True)
    remote_payload = parse_case_shell_output(result.stdout)

    actual_sha = remote_payload["output_sha256"]
    actual_bytes = remote_payload["output_bytes"]
    return {
        "name": case.name,
        "remote_case_root": case_root,
        "remote_input": remote_input,
        "input_sha256": case.input_sha256,
        "expected_output_sha256": case.expected_output_sha256,
        "actual_output_path": remote_payload["output_path"],
        "actual_output_sha256": actual_sha,
        "actual_output_bytes": actual_bytes,
        "actual_matches_expected": actual_sha == case.expected_output_sha256,
        "output_bytes_match_expected": actual_bytes == EXPECTED_BYTES,
        "stdout_first_4096": remote_payload["stdout_first_4096"],
        "stderr_first_4096": remote_payload["stderr_first_4096"],
    }


def parse_case_shell_output(stdout: str) -> dict[str, Any]:
    lines = stdout.splitlines()

    def marker_line(marker: str) -> int:
        try:
            return lines.index(marker)
        except ValueError as exc:
            raise RuntimeError(f"missing marker {marker}") from exc

    path_index = marker_line("__PHASE34_OUTPUT_PATH__")
    sha_index = marker_line("__PHASE34_OUTPUT_SHA256__")
    size_index = marker_line("__PHASE34_OUTPUT_SIZE__")
    stdout_begin = marker_line("__PHASE34_STDOUT_BEGIN__")
    stdout_end = marker_line("__PHASE34_STDOUT_END__")
    stderr_begin = marker_line("__PHASE34_STDERR_BEGIN__")
    stderr_end = marker_line("__PHASE34_STDERR_END__")
    return {
        "output_path": lines[path_index + 1].strip(),
        "output_sha256": lines[sha_index + 1].split()[0],
        "output_bytes": int(lines[size_index + 1].split()[0]),
        "stdout_first_4096": "\n".join(lines[stdout_begin + 1 : stdout_end]),
        "stderr_first_4096": "\n".join(lines[stderr_begin + 1 : stderr_end]),
    }


def extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError("no JSON object found in command output")
    return text[start : end + 1]


def adb_push(args: argparse.Namespace, local: Path, remote: str) -> None:
    argv = ["adb"]
    if args.adb_serial:
        argv.extend(["-s", args.adb_serial])
    argv.extend(["push", str(local), remote])
    run(argv, check=True)


def adb_shell(
    args: argparse.Namespace, script: str, *, check: bool
) -> subprocess.CompletedProcess[str]:
    argv = ["adb"]
    if args.adb_serial:
        argv.extend(["-s", args.adb_serial])
    argv.extend(["shell", script])
    return run(argv, check=check)


def run(argv: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True, check=check)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())

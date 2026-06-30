#!/usr/bin/env python3
"""Run QNN/HTP ReLU against a PJP1-derived tensor staged by Termux."""

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

from polymath_ai.polar.metrics_contract import metric_report  # noqa: E402


DEFAULT_STAGE_REPORT = (
    "/data/local/tmp/polymath_phase34/active_wave/pjp1_htp_relu_input/"
    "phase34_pjp1_htp_relu_input_stage.json"
)
DEFAULT_QAIRT_ROOT = "/data/local/tmp/qairt-2.44"
DEFAULT_CONTEXT = (
    "/data/local/tmp/polymath_gemma4_gate/phase13/"
    "20260524T210920Z_phase13_gemma4_only_heterogeneous/"
    "p13f/htp/relu/context/gemma_hidden2560_relu.qnn.bin"
)
DEFAULT_REPORT = (
    "runtime/reports/polar_phase34_consumer_preflight/active_wave/"
    "pjp1_htp_relu_run/phase34_pjp1_derived_htp_relu_run.json"
)


def main() -> int:
    args = parse_args()
    stage_report = read_remote_json(args.stage_report)
    outputs = stage_report["outputs"]
    remote_input = outputs["remote_input_path"]
    expected_output_sha256 = outputs["expected_relu_output_sha256"]
    run_root = str(Path(remote_input).parent / "htp_relu_run")
    result = run_htp(args, remote_input, run_root)

    actual_sha = result["output_sha256"]
    status = "pass" if actual_sha == expected_output_sha256 else "fail"
    payload = {
        "schema_version": "polar_phase34_pjp1_derived_htp_relu_run_v1",
        "status": status,
        "phase3_ready_claim": False,
        "phase4_ready_claim": False,
        "learning_claim": False,
        "authority_material": stage_report.get("authority_material", "diagnostic_or_preflight_only"),
        "nonclaims": [
            "This is PJP1-derived HTP smoke metadata only.",
            "This is not Phase 3 readiness.",
            "This does not prove Gemma forward correctness.",
            "This does not prove learning or model-quality movement.",
            "This does not authorize C1-C4 execution.",
        ],
        "stage_report_remote": args.stage_report,
        "pjp1": stage_report["pjp1"],
        "source_packet": stage_report["source_packet"],
        "phase4_accepted_input_surface": stage_report.get("phase4_accepted_input_surface", {}),
        "qnn": {
            "qairt_root": args.qairt_root,
            "context": args.context,
            "backend": f"{args.qairt_root.rstrip('/')}/lib/aarch64-android/libQnnHtp.so",
            "graph": "gemma_hidden2560_relu",
            "input_path": remote_input,
            "input_sha256": outputs["input_sha256"],
            "expected_output_sha256": expected_output_sha256,
            "actual_output_path": result["output_path"],
            "actual_output_sha256": actual_sha,
            "actual_output_bytes": result["output_bytes"],
            "actual_matches_expected_relu": actual_sha == expected_output_sha256,
            "latency_ms": result["elapsed_sec"] * 1000.0,
            "tokens_per_sec": stage_report["source_packet"]["tokens_used"] / result["elapsed_sec"],
            "host_to_device_ms": None,
            "device_compute_ms": None,
            "device_to_host_ms": None,
            "stdout_first_4096": result["stdout_first_4096"],
            "stderr_first_4096": result["stderr_first_4096"],
        },
        "metric_availability": {
            "qnn_latency_ms": "host_observed_adb_shell_wall_time_for_qnn_net_run",
            "host_to_device_ms": "not_isolated_by_current_qnn_net_run_wrapper",
            "device_compute_ms": "not_isolated_by_current_qnn_net_run_wrapper",
            "device_to_host_ms": "not_isolated_by_current_qnn_net_run_wrapper",
        },
        "phase3_metrics": build_phase3_metrics(args, stage_report, result, status),
        "raw_payload_rules": {
            "raw_pjp1_pulled_to_host": False,
            "raw_qnn_output_pulled_to_repo": False,
            "compact_hash_report_only": True,
        },
        "next_required_for_consumed_output": [
            "Run Phase 4 bridge cell on actual_output_path and remote_phase4_target_path.",
            "Verify adapter update telemetry and finite gradients.",
            "Keep phase4_ready_claim=false until heldout/retention gates pass.",
        ],
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(report_path)
    return 0 if status == "pass" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-report", default=DEFAULT_STAGE_REPORT)
    parser.add_argument("--qairt-root", default=DEFAULT_QAIRT_ROOT)
    parser.add_argument("--context", default=DEFAULT_CONTEXT)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--corpus-phase", default="C1", help="Metric namespace corpus phase, e.g. C1, C2, C2.5, C3, C4.")
    return parser.parse_args()


def read_remote_json(path: str) -> dict[str, Any]:
    result = adb_shell(f"cat {shlex.quote(path)}", check=True)
    return json.loads(extract_json_object(result.stdout))


def run_htp(args: argparse.Namespace, remote_input: str, run_root: str) -> dict[str, Any]:
    started = time.perf_counter()
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
    result = adb_shell(script, check=True)
    parsed = parse_shell_markers(result.stdout)
    parsed["elapsed_sec"] = time.perf_counter() - started
    return parsed


def build_phase3_metrics(
    args: argparse.Namespace,
    stage_report: dict[str, Any],
    result: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    token_count = stage_report.get("source_packet", {}).get("tokens_used")
    elapsed_sec = result.get("elapsed_sec")
    metrics = {
        "pjp1_preflight_status": "pass" if stage_report.get("status") == "pass" else stage_report.get("status"),
        "native_preflight_status": None,
        "i8_oracle_mismatches": None,
        "htp_backend": f"{args.qairt_root.rstrip('/')}/lib/aarch64-android/libQnnHtp.so",
        "htp_output_sha256": result.get("output_sha256"),
        "forward_loss": None,
        "forward_mse": 0.0 if status == "pass" else None,
        "forward_cross_entropy": None,
        "perplexity": None,
        "answer_token_accuracy": None,
        "calibration_ece": None,
        "brier_score": None,
        "tokens_per_sec": (float(token_count) / float(elapsed_sec))
        if isinstance(token_count, int) and isinstance(elapsed_sec, (int, float)) and elapsed_sec > 0
        else None,
        "latency_ms": (float(elapsed_sec) * 1000.0) if isinstance(elapsed_sec, (int, float)) else None,
        "host_to_device_ms": None,
        "device_compute_ms": None,
        "device_to_host_ms": None,
        "output_bytes": result.get("output_bytes"),
        "actual_matches_expected_relu": status == "pass",
    }
    blockers = [
        "native_preflight_status_not_in_htp_runner_report",
        "i8_oracle_mismatches_not_in_htp_runner_report",
        "forward_cross_entropy_requires_language_model_target",
        "perplexity_requires_language_model_likelihood",
        "calibration_requires_probabilistic_outputs",
        "device_compute_ms_requires_qnn_profile_parse",
    ]
    if status != "pass":
        blockers.append("htp_output_mismatch")
    return metric_report(
        schema_version="phase3_htp_metric_contract_v1",
        phase_family="phase3",
        corpus_phase=args.corpus_phase,
        metrics=metrics,
        blockers=blockers,
        nonclaims=[
            "phase3_metrics_do_not_claim_phase3_readiness",
            "phase3_metrics_do_not_claim_learning",
        ],
    )


def parse_shell_markers(stdout: str) -> dict[str, Any]:
    lines = stdout.splitlines()

    def index(marker: str) -> int:
        try:
            return lines.index(marker)
        except ValueError as exc:
            raise RuntimeError(f"missing marker {marker}") from exc

    path_index = index("__PHASE34_OUTPUT_PATH__")
    sha_index = index("__PHASE34_OUTPUT_SHA256__")
    size_index = index("__PHASE34_OUTPUT_SIZE__")
    stdout_begin = index("__PHASE34_STDOUT_BEGIN__")
    stdout_end = index("__PHASE34_STDOUT_END__")
    stderr_begin = index("__PHASE34_STDERR_BEGIN__")
    stderr_end = index("__PHASE34_STDERR_END__")
    return {
        "output_path": lines[path_index + 1].strip(),
        "output_sha256": lines[sha_index + 1].split()[0],
        "output_bytes": int(lines[size_index + 1].split()[0]),
        "stdout_first_4096": "\n".join(lines[stdout_begin + 1 : stdout_end]),
        "stderr_first_4096": "\n".join(lines[stderr_begin + 1 : stderr_end]),
    }


def adb_shell(script: str, *, check: bool) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["adb", "shell", script], text=True, capture_output=True, check=check)


def extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError("no JSON object found in command output")
    return text[start : end + 1]


if __name__ == "__main__":
    raise SystemExit(main())

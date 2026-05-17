#!/usr/bin/env python3
"""Run the Phase 10 QNN/HTP probe and keep Hexagon training honest."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any


PHONE_ROOT = "/data/local/tmp/polymath_gemma4_gate"
QAIRT_ROOT = "/data/local/tmp/qairt-2.44"
QNN_CONTEXT = "/data/local/tmp/phase1a/qwen_block.qnn.bin"
QNN_INPUT_LIST = "/data/local/tmp/phase1a/input_list.txt"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, text=True, capture_output=True)
    if check and completed.returncode != 0:
        joined = " ".join(shlex.quote(part) for part in command)
        raise RuntimeError(
            f"command failed ({completed.returncode}): {joined}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def adb(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["adb", *args], check=check)


def adb_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return adb(["shell", command], check=check)


def q(value: str) -> str:
    return shlex.quote(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pull_optional(remote: str, local: Path) -> bool:
    local.parent.mkdir(parents=True, exist_ok=True)
    completed = adb(["pull", remote, str(local)], check=False)
    return completed.returncode == 0


def run_platform_validator(run_id: str) -> dict[str, Any]:
    out = f"{PHONE_ROOT}/hardware_max/{run_id}/qnn_platform_validator"
    command = f"""
set -e
Q={q(QAIRT_ROOT)}
OUT={q(out)}
rm -rf "$OUT"
mkdir -p "$OUT"
export LD_LIBRARY_PATH="$Q/lib/aarch64-android:$LD_LIBRARY_PATH"
export ADSP_LIBRARY_PATH="$Q/lib/hexagon-v79/unsigned;/vendor/dsp/cdsp;/vendor/lib/rfsa/adsp;/system/lib/rfsa/adsp;/dsp;$Q/lib/aarch64-android"
"$Q/bin/aarch64-android/qnn-platform-validator" --backend dsp --libVersion --coreVersion --testBackend --targetPath "$OUT" --debug
cat "$OUT/Result.csv"
"""
    completed = adb_shell(command, check=False)
    stdout = completed.stdout
    passed = completed.returncode == 0 and "QNN is supported for backend DSP" in stdout
    return {
        "status": "pass" if passed else "fail",
        "returncode": completed.returncode,
        "phone_output_dir": out,
        "stdout_tail": stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def run_htp_inference(run_id: str) -> dict[str, Any]:
    out = f"{PHONE_ROOT}/hardware_max/{run_id}/qnn_htp_inference"
    command = f"""
set -e
Q={q(QAIRT_ROOT)}
P=/data/local/tmp/phase1a
OUT={q(out)}
rm -rf "$OUT"
mkdir -p "$OUT"
export LD_LIBRARY_PATH="$Q/lib/aarch64-android:/vendor/dsp/cdsp:/vendor/lib64:$LD_LIBRARY_PATH"
export ADSP_LIBRARY_PATH="$Q/lib/hexagon-v79/unsigned;/vendor/dsp/cdsp;/vendor/lib/rfsa/adsp;/system/lib/rfsa/adsp;/dsp"
cd "$P"
"$Q/bin/aarch64-android/qnn-net-run" --retrieve_context {q(QNN_CONTEXT)} --backend "$Q/lib/aarch64-android/libQnnHtp.so" --input_list {q(QNN_INPUT_LIST)} --output_dir "$OUT" --num_inferences 1 --profiling_level basic --log_level info
sed -n '1,220p' "$OUT/execution_metadata.yaml"
if [ -x "$Q/bin/aarch64-android/qnn-profile-viewer" ]; then
  "$Q/bin/aarch64-android/qnn-profile-viewer" --input_log "$OUT/qnn-profiling-data_0.log" || true
fi
"""
    completed = adb_shell(command, check=False)
    stdout = completed.stdout
    passed = (
        completed.returncode == 0
        and "qnn_partition_0" in stdout
        and re.search(r"inferences_completed:\s*1", stdout) is not None
    )
    return {
        "status": "pass" if passed else "fail",
        "returncode": completed.returncode,
        "phone_output_dir": out,
        "stdout_tail": stdout[-5000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def run_training_surface_checks() -> dict[str, Any]:
    command = f"""
Q={q(QAIRT_ROOT)}
set +e
echo '=== qairt-lora-adapter-bin-updater ==='
"$Q/bin/aarch64-android/qairt-lora-adapter-bin-updater" --help 2>&1 | sed -n '1,160p'
echo '=== qnn-net-run binary_updates ==='
"$Q/bin/aarch64-android/qnn-net-run" --help 2>&1 | grep -A10 -B6 binary_updates
echo '=== training files ==='
find "$Q" -maxdepth 6 -type f \\( -iname '*training*' -o -iname '*torch*' -o -iname 'libGenieTraining.so' \\) 2>/dev/null | sort
"""
    completed = adb_shell(command, check=False)
    stdout = completed.stdout
    genie_training_present = "libGenieTraining.so" in stdout
    return {
        "status": "fail",
        "reason": "No HTP backward/gradient/optimizer update surface was executed. Available update tools mutate inference binaries/adapters, not training state.",
        "returncode": completed.returncode,
        "genie_training_library_present": genie_training_present,
        "stdout_tail": stdout[-8000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def pull_artifacts(report_dir: Path, run_id: str, checks: dict[str, Any]) -> dict[str, Any]:
    pulled: dict[str, Any] = {}
    platform_dir = checks["platform_validator"]["phone_output_dir"]
    inference_dir = checks["htp_inference"]["phone_output_dir"]
    pulled["platform_result_csv"] = pull_optional(
        f"{platform_dir}/Result.csv", report_dir / "qnn_platform_validator/Result.csv"
    )
    pulled["execution_metadata.yaml"] = pull_optional(
        f"{inference_dir}/execution_metadata.yaml",
        report_dir / "qnn_htp_inference/execution_metadata.yaml",
    )
    pulled["qnn-profiling-data_0.log"] = "omitted_binary_profile_log"
    return pulled


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--report-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.report_dir.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    checks = {
        "platform_validator": run_platform_validator(args.run_id),
        "htp_inference": run_htp_inference(args.run_id),
        "training_surface": run_training_surface_checks(),
    }
    pulled = pull_artifacts(args.report_dir, args.run_id, checks)
    status = "pass" if checks["training_surface"]["status"] == "pass" else "fail"
    blockers = []
    if checks["platform_validator"]["status"] != "pass":
        blockers.append("QNN DSP platform validation failed")
    if checks["htp_inference"]["status"] != "pass":
        blockers.append("QNN HTP inference smoke failed")
    blockers.append("Hexagon training update is not proven: no HTP backward/gradient/optimizer path executed")
    gate = {
        "schema_version": "gemma4_phase10_qnn_htp_probe_v1",
        "run_id": args.run_id,
        "gate": "Phase 10 Hexagon/QNN HTP training non-claim falsifier",
        "status": status,
        "started_at_utc": started_at,
        "ended_at_utc": utc_now(),
        "checks": checks,
        "pulled_artifacts": pulled,
        "blockers": blockers,
        "authority_verdict": "hexagon_training_not_promoted",
        "positive_evidence_scope": "QNN/HTP platform support and inference/context execution only",
        "non_claim_remaining": "not Hexagon NPU training",
    }
    write_json(args.report_dir / "gate_result.json", gate)
    (args.report_dir / "blockers.md").write_text(
        "\n".join(f"- {item}" for item in blockers) + "\n", encoding="utf-8"
    )
    (args.report_dir / "commands.log").write_text(
        "Sanitized commands: qnn-platform-validator --backend dsp; "
        "qnn-net-run --retrieve_context qwen_block.qnn.bin --backend libQnnHtp.so; "
        "qairt-lora-adapter-bin-updater --help; qnn-net-run --help binary_updates.\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": gate["status"], "gate_result": str(args.report_dir / "gate_result.json")}, sort_keys=True))
    return 0 if gate["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

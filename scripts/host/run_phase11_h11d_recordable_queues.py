#!/usr/bin/env python3
"""Run Phase 11 H11-D OpenCL recordable queue probe on the authority phone."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_SERIAL = "FY25013101C8"
DEFAULT_PHONE_ROOT = "/data/local/tmp/polymath_gemma4_gate"
DEFAULT_PROBE = Path(
    "integrations/gemma4-snapdragon-megakernel/build/"
    "gemma4_megakernel_android/opencl_recordable_queue_probe"
)
GATE_FILES = (
    "extension_dump.json",
    "symbol_probe.json",
    "queue_property_scan.json",
    "microbenchmark.json",
    "output_comparison.json",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compact_utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def q(value: str) -> str:
    return shlex.quote(value)


def run_command(
    command: list[str], *, check: bool = True, timeout: int | None = None
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if check and completed.returncode != 0:
        joined = " ".join(shlex.quote(part) for part in command)
        raise RuntimeError(
            f"command failed ({completed.returncode}): {joined}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def adb(serial: str, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run_command(["adb", "-s", serial, *args], check=check)


def adb_shell(serial: str, command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return adb(serial, ["shell", command], check=check)


def adb_pull(serial: str, remote_path: str, local_path: Path) -> bool:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    completed = adb(serial, ["pull", remote_path, str(local_path)], check=False)
    return completed.returncode == 0


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deploy_probe(
    *, serial: str, phone_phase11_root: str, probe_binary: Path
) -> str:
    if not probe_binary.exists():
        raise FileNotFoundError(f"probe binary not found: {probe_binary}")
    adb_shell(serial, f"mkdir -p {q(phone_phase11_root)}")
    remote = f"{phone_phase11_root}/opencl_recordable_queue_probe"
    adb(serial, ["push", str(probe_binary), remote])
    adb_shell(serial, f"chmod 755 {q(remote)}")
    return remote


def run_native_probe(
    *,
    serial: str,
    remote_probe: str,
    phone_gate_dir: str,
    iterations: int,
) -> dict[str, Any]:
    command = (
        f"{q(remote_probe)} --output {q(phone_gate_dir)} "
        f"--iterations {q(str(iterations))}"
    )
    started_at = utc_now()
    completed = adb_shell(serial, command, check=False)
    return {
        "schema_version": "phase11_h11d_native_probe_run_v1",
        "started_at_utc": started_at,
        "ended_at_utc": utc_now(),
        "command_shape": "opencl_recordable_queue_probe --output PHONE_GATE --iterations N",
        "returncode": completed.returncode,
        "stdout_first_8192": completed.stdout[:8192],
        "stderr_first_8192": completed.stderr[:8192],
    }


def find_benchmark(payload: dict[str, Any], name: str) -> dict[str, Any]:
    for item in payload.get("benchmarks", []):
        if item.get("name") == name:
            return item
    return {}


def first_symbol_missing(symbol_probe: dict[str, Any], required: set[str]) -> list[str]:
    missing = []
    for name in sorted(required):
        matched = [
            item
            for item in symbol_probe.get("symbols", [])
            if item.get("name") == name
        ]
        if not matched:
            missing.append(name)
            continue
        item = matched[0]
        if not (item.get("dlsym_present") or item.get("extension_address_present")):
            missing.append(name)
    return missing


def selected_property(queue_scan: dict[str, Any]) -> str:
    value = str(queue_scan.get("selected_recordable_property", "0x0"))
    return value if value else "0x0"


def evaluate_gate(
    *,
    native_run: dict[str, Any],
    extension_dump: dict[str, Any],
    symbol_probe: dict[str, Any],
    queue_scan: dict[str, Any],
    microbenchmark: dict[str, Any],
    output_comparison: dict[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []
    supported = bool(extension_dump.get("recordable_queues_supported", False))
    required = {"clNewRecordingQCOM", "clEndRecordingQCOM", "clEnqueueRecordingQCOM"}
    missing_symbols = first_symbol_missing(symbol_probe, required)

    if native_run.get("returncode") != 0:
        blockers.append("native OpenCL recordable queue probe returned nonzero")

    if not supported:
        return {
            "schema_version": "phase11_h11d_gate_result_v1",
            "gate": "H11-D",
            "status": "pass" if not blockers else "fail",
            "blockers": blockers,
            "recordable_queues_supported": False,
            "recordable_queue_decision": "disabled_unsupported",
            "campaign_can_continue": True,
            "reason": (
                "cl_qcom_recordable_queues is not advertised by the selected "
                "OpenCL platform/device; exact driver result recorded."
            ),
        }

    if missing_symbols:
        blockers.append(f"required recordable queue symbols missing: {', '.join(missing_symbols)}")

    if selected_property(queue_scan) == "0x0":
        blockers.append("no accepted non-standard queue property identified for CL_QUEUE_RECORDABLE_QCOM")

    noop = find_benchmark(microbenchmark, "noop_recorded_sequence")
    fixed = find_benchmark(microbenchmark, "fixed_arg_recorded_add")
    mutable = find_benchmark(microbenchmark, "mutable_arg_recorded_add")

    if noop.get("status") != "completed":
        blockers.append("no-op recorded sequence benchmark did not complete")
    if fixed.get("status") != "completed":
        blockers.append("fixed-arg recorded sequence benchmark did not complete")
    if not output_comparison.get("noop_outputs_match", False):
        blockers.append("no-op recorded output comparison failed")
    if not output_comparison.get("fixed_arg_outputs_match", False):
        blockers.append("fixed-arg recorded output comparison failed")
    if mutable.get("status") != "completed":
        blockers.append("mutable-arg recorded benchmark was not completed")
    if not output_comparison.get("mutable_arg_outputs_match", False):
        blockers.append("mutable-arg recorded output comparison failed")

    best_speedup = max(
        float(noop.get("speedup_ratio", 0.0) or 0.0),
        float(fixed.get("speedup_ratio", 0.0) or 0.0),
        float(mutable.get("speedup_ratio", 0.0) or 0.0),
    )
    if best_speedup <= 1.0:
        blockers.append("recorded queue benchmark did not improve measured launch time")

    return {
        "schema_version": "phase11_h11d_gate_result_v1",
        "gate": "H11-D",
        "status": "pass" if not blockers else "fail",
        "blockers": blockers,
        "recordable_queues_supported": True,
        "recordable_queue_decision": (
            "eligible_for_narrow_sequence_ab_not_default"
            if not blockers
            else "disabled_failed_probe"
        ),
        "campaign_can_continue": True,
        "selected_recordable_property": selected_property(queue_scan),
        "missing_required_symbols": missing_symbols,
        "best_launch_speedup_ratio": best_speedup,
        "noop_status": noop.get("status", "missing"),
        "fixed_arg_status": fixed.get("status", "missing"),
        "mutable_arg_status": mutable.get("status", "missing"),
    }


def write_reports(
    *,
    report_dir: Path,
    gate_result: dict[str, Any],
    native_run: dict[str, Any],
    phone_gate_dir: str,
    remote_probe: str,
    iterations: int,
) -> None:
    write_json(report_dir / "native_probe_run.json", native_run)
    write_json(report_dir / "gate_result.json", gate_result)
    blockers = gate_result.get("blockers", [])
    write_text(
        report_dir / "blockers.md",
        "- None for H11-D.\n" if not blockers else "".join(f"- {item}\n" for item in blockers),
    )
    write_text(
        report_dir / "falsifier_report.md",
        "# H11-D Falsifier Report\n\n"
        f"- authority runtime was REDMAGIC phone via ADB: pass.\n"
        f"- native probe binary path: `{remote_probe}`.\n"
        f"- phone gate artifact directory: `{phone_gate_dir}`.\n"
        f"- requested iterations per microbenchmark: {iterations}.\n"
        f"- recordable queues eligible for later narrow A/B: {gate_result.get('recordable_queue_decision') == 'eligible_for_narrow_sequence_ab_not_default'}.\n"
        "- CPU fallback excluded: probe uses libOpenCL platform/device extension strings and OpenCL command queues.\n"
        "- mutable update ABI source checked against MNN's vendored `cl_ext_qcom.h` and wrapper signatures before rerun.\n"
        "- promotion requires mutable-arg correctness and measured benefit; skipped or failed mutable evidence blocks promotion.\n",
    )
    write_text(
        report_dir / "commands.log",
        "adb push opencl_recordable_queue_probe PHONE_PHASE11_ROOT/opencl_recordable_queue_probe\n"
        "adb shell PHONE_PROBE --output PHONE_GATE/H11-D-recordable-queues --iterations N\n"
        "adb pull PHONE_GATE/H11-D-recordable-queues/{extension_dump,symbol_probe,queue_property_scan,microbenchmark,output_comparison}.json\n",
    )
    artifact_entries = []
    for path in sorted(report_dir.rglob("*")):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        artifact_entries.append(
            {
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    write_json(
        report_dir / "artifact_manifest.json",
        {
            "schema_version": "phase11_h11d_artifact_manifest_v1",
            "gate": "H11-D",
            "report_dir": str(report_dir),
            "git_allowed_artifacts": artifact_entries,
        },
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", default=DEFAULT_SERIAL)
    parser.add_argument("--phone-root", default=DEFAULT_PHONE_ROOT)
    parser.add_argument("--run-id", default=f"{compact_utc_now()}_h11d_recordable_queues")
    parser.add_argument("--probe-binary", type=Path, default=DEFAULT_PROBE)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--host-report-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_dir = args.host_report_dir or Path(
        f"runtime/reports/gemma4_megakernel/hardware_native_povc/"
        f"{args.run_id}/H11-D-recordable-queues"
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    phone_phase11_root = f"{args.phone_root.rstrip('/')}/phase11"
    phone_gate_dir = f"{phone_phase11_root}/runs/{args.run_id}/H11-D-recordable-queues"
    adb_shell(args.serial, f"rm -rf {q(phone_gate_dir)} && mkdir -p {q(phone_gate_dir)}")
    remote_probe = deploy_probe(
        serial=args.serial,
        phone_phase11_root=phone_phase11_root,
        probe_binary=args.probe_binary,
    )
    native_run = run_native_probe(
        serial=args.serial,
        remote_probe=remote_probe,
        phone_gate_dir=phone_gate_dir,
        iterations=args.iterations,
    )
    for name in GATE_FILES:
        adb_pull(args.serial, f"{phone_gate_dir}/{name}", report_dir / name)

    empty: dict[str, Any] = {}
    extension_dump = load_json(report_dir / "extension_dump.json") if (report_dir / "extension_dump.json").exists() else empty
    symbol_probe = load_json(report_dir / "symbol_probe.json") if (report_dir / "symbol_probe.json").exists() else empty
    queue_scan = load_json(report_dir / "queue_property_scan.json") if (report_dir / "queue_property_scan.json").exists() else empty
    microbenchmark = load_json(report_dir / "microbenchmark.json") if (report_dir / "microbenchmark.json").exists() else empty
    output_comparison = load_json(report_dir / "output_comparison.json") if (report_dir / "output_comparison.json").exists() else empty
    gate_result = evaluate_gate(
        native_run=native_run,
        extension_dump=extension_dump,
        symbol_probe=symbol_probe,
        queue_scan=queue_scan,
        microbenchmark=microbenchmark,
        output_comparison=output_comparison,
    )
    gate_result["started_at_utc"] = native_run["started_at_utc"]
    gate_result["ended_at_utc"] = utc_now()
    gate_result["host_report_dir"] = str(report_dir)
    gate_result["phone_gate_dir"] = phone_gate_dir
    write_reports(
        report_dir=report_dir,
        gate_result=gate_result,
        native_run=native_run,
        phone_gate_dir=phone_gate_dir,
        remote_probe=remote_probe,
        iterations=args.iterations,
    )
    print(json.dumps({"status": gate_result["status"], "host_report_dir": str(report_dir)}, sort_keys=True))
    return 0 if gate_result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

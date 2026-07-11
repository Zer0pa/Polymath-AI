#!/usr/bin/env python3
"""Execute and adjudicate the frozen V79 S16 LM-head diagnostic on-phone."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import time
import types
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FRONTIER_ROOT = ROOT / "polymath_ai/frontier"
BUNDLE_PACKAGE = "_e4b_phone_gate_bundle"


def _load_bundle_module(name: str) -> types.ModuleType:
    qualified = f"{BUNDLE_PACKAGE}.{name}"
    spec = importlib.util.spec_from_file_location(qualified, FRONTIER_ROOT / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load execution module: {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


_bundle = types.ModuleType(BUNDLE_PACKAGE)
_bundle.__path__ = [str(FRONTIER_ROOT)]
sys.modules[BUNDLE_PACKAGE] = _bundle
_load_bundle_module("e4b_f5_probe")
_load_bundle_module("e4b_f5_qnn_exporter")
_projection_gate = _load_bundle_module("e4b_l2_projection_gate")
adjudicate_metrics = _projection_gate.adjudicate_metrics
bf16_payload_to_floats = _projection_gate.bf16_payload_to_floats
canonical_json = _projection_gate.canonical_json
softmax_js_divergence = _projection_gate.softmax_js_divergence
vector_metrics = _projection_gate.vector_metrics


PREREG_SCHEMA = "gemma4_e4b_l2_int16_phone_execution_preregistration_v1"
RECEIPT_SCHEMA = "gemma4_e4b_l2_int16_phone_execution_receipt_v1"
SHA256_LENGTH = 64


class PhoneGateError(RuntimeError):
    """Raised when the phone experiment cannot preserve its frozen contract."""


@dataclass(frozen=True)
class CaseContract:
    case_id: str
    input_path: Path
    input_sha256: str
    reference_path: Path
    reference_sha256: str
    output_bytes: int


def sha256_path(path: Path) -> str:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    digest = hashlib.sha256()
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise PhoneGateError(f"not a regular file: {path}")
        while chunk := os.read(descriptor, 8 * 1024 * 1024):
            digest.update(chunk)
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def read_regular(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise PhoneGateError(f"not a regular file: {path}")
        chunks = []
        while chunk := os.read(descriptor, 8 * 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def write_exclusive(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, mode)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError(f"short write to {path}")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_hashed_receipt(path: Path, payload: dict[str, Any]) -> str:
    encoded = canonical_json(payload)
    write_exclusive(path, encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    write_exclusive(
        path.with_suffix(path.suffix + ".sha256"),
        f"{digest}  {path.name}\n".encode("ascii"),
    )
    return digest


def load_json(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise PhoneGateError(f"non-finite JSON constant: {value}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PhoneGateError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    value = json.loads(
        read_regular(path),
        parse_constant=reject_constant,
        object_pairs_hook=reject_duplicates,
    )
    if not isinstance(value, dict):
        raise PhoneGateError(f"JSON root must be an object: {path}")
    return value


def resolve_relative(root: Path, relative: object) -> Path:
    if not isinstance(relative, str):
        raise PhoneGateError("relative path must be a string")
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise PhoneGateError(f"unsafe relative path: {relative}")
    return root / candidate


def validate_file(path: Path, *, expected_bytes: int, expected_sha256: str) -> None:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise PhoneGateError(f"expected regular file: {path}")
    if metadata.st_size != expected_bytes:
        raise PhoneGateError(f"byte count mismatch: {path}")
    if sha256_path(path) != expected_sha256:
        raise PhoneGateError(f"SHA-256 mismatch: {path}")


def load_preregistration(path: Path, expected_sha256: str) -> dict[str, Any]:
    if len(expected_sha256) != SHA256_LENGTH or sha256_path(path) != expected_sha256:
        raise PhoneGateError("execution preregistration digest mismatch")
    prereg = load_json(path)
    if prereg.get("schema_version") != PREREG_SCHEMA:
        raise PhoneGateError("execution preregistration schema mismatch")
    if prereg.get("state") != "frozen_unobserved":
        raise PhoneGateError("execution preregistration is not frozen-unobserved")
    if prereg.get("candidate_output_observed") is not False:
        raise PhoneGateError("execution preregistration contains candidate output")
    return prereg


def validate_toolchain(qairt_root: Path, prereg: dict[str, Any]) -> Path:
    records = prereg.get("phone_toolchain", {}).get("files")
    if not isinstance(records, list) or not records:
        raise PhoneGateError("phone toolchain contract is empty")
    qnn_net_run = None
    for record in records:
        path = resolve_relative(qairt_root, record.get("relative_path"))
        validate_file(
            path,
            expected_bytes=int(record["bytes"]),
            expected_sha256=str(record["sha256"]),
        )
        if record.get("role") == "qnn_net_run":
            qnn_net_run = path
    if qnn_net_run is None or not os.access(qnn_net_run, os.X_OK):
        raise PhoneGateError("qnn-net-run is not executable")
    return qnn_net_run


def validate_execution_code(prereg: dict[str, Any]) -> None:
    records = prereg.get("execution_code", {}).get("files")
    if not isinstance(records, list) or not records:
        raise PhoneGateError("execution-code contract is empty")
    for record in records:
        path = resolve_relative(ROOT, record.get("relative_path"))
        validate_file(
            path,
            expected_bytes=int(record["bytes"]),
            expected_sha256=str(record["sha256"]),
        )


def validate_cases(run_root: Path, prereg: dict[str, Any]) -> list[CaseContract]:
    records = prereg.get("cases")
    if not isinstance(records, list) or len(records) != 3:
        raise PhoneGateError("exactly three frozen cases are required")
    cases = []
    for record in records:
        input_path = resolve_relative(run_root, record.get("input_relative_path"))
        reference_path = resolve_relative(run_root, record.get("reference_relative_path"))
        validate_file(
            input_path,
            expected_bytes=int(record["input_bytes"]),
            expected_sha256=str(record["input_sha256"]),
        )
        validate_file(
            reference_path,
            expected_bytes=int(record["reference_bytes"]),
            expected_sha256=str(record["reference_sha256"]),
        )
        cases.append(
            CaseContract(
                case_id=str(record["case_id"]),
                input_path=input_path,
                input_sha256=str(record["input_sha256"]),
                reference_path=reference_path,
                reference_sha256=str(record["reference_sha256"]),
                output_bytes=int(record["output_bytes"]),
            )
        )
    if len({case.case_id for case in cases}) != len(cases):
        raise PhoneGateError("duplicate case identity")
    return cases


def thermal_snapshot() -> list[dict[str, Any]]:
    records = []
    for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
        try:
            type_name = (zone / "type").read_text(encoding="utf-8").strip()
            temperature = int((zone / "temp").read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
        records.append({"type": type_name, "millidegrees_c": temperature})
    return records


def enforce_thermal_guard(snapshot: list[dict[str, Any]], guard: dict[str, Any]) -> None:
    sensor = str(guard["sensor_type"])
    limit = int(guard["stop_at_or_above_millidegrees_c"])
    values = [record["millidegrees_c"] for record in snapshot if record["type"] == sensor]
    if len(values) != 1:
        raise PhoneGateError(f"thermal guard sensor cardinality mismatch: {sensor}")
    if values[0] >= limit:
        raise PhoneGateError(f"thermal guard stopped execution: {values[0]} >= {limit}")


def qnn_environment(qairt_root: Path) -> dict[str, str]:
    environment = dict(os.environ)
    native_lib = qairt_root / "lib/aarch64-android"
    environment["LD_LIBRARY_PATH"] = f"{native_lib}:{environment.get('LD_LIBRARY_PATH', '')}"
    environment["ADSP_LIBRARY_PATH"] = ";".join(
        [
            str(qairt_root / "lib/hexagon-v79/unsigned"),
            str(qairt_root / "lib/hexagon-v81/unsigned"),
            str(qairt_root / "lib/hexagon-v75/unsigned"),
            "/vendor/dsp/cdsp",
            "/vendor/lib/rfsa/adsp",
            "/system/lib/rfsa/adsp",
            "/dsp",
        ]
    )
    return environment


def build_qnn_command(
    *,
    qnn_net_run: Path,
    qairt_root: Path,
    context_path: Path,
    input_list: Path,
    output_dir: Path,
) -> list[str]:
    return [
        str(qnn_net_run),
        f"--retrieve_context={context_path}",
        "--backend",
        str(qairt_root / "lib/aarch64-android/libQnnHtp.so"),
        f"--input_list=__,{input_list}",
        f"--output_dir={output_dir}",
        "--num_inferences",
        "1",
        "--keep_num_outputs",
        "1",
        "--profiling_level",
        "basic",
        "--log_level",
        "info",
        "--use_native_input_files",
        "--use_native_output_files",
    ]


def run_case(
    *,
    case: CaseContract,
    run_root: Path,
    qairt_root: Path,
    qnn_net_run: Path,
    context_path: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    input_list_dir = run_root / "input_lists"
    output_dir = run_root / "outputs" / case.case_id
    log_dir = run_root / "logs"
    input_list_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    output_dir.mkdir(mode=0o700, parents=True)
    input_list = input_list_dir / f"{case.case_id}.txt"
    write_exclusive(input_list, f"{case.input_path}\n".encode("utf-8"))
    command = build_qnn_command(
        qnn_net_run=qnn_net_run,
        qairt_root=qairt_root,
        context_path=context_path,
        input_list=input_list,
        output_dir=output_dir,
    )
    started_ns = time.monotonic_ns()
    timed_out = False
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            env=qnn_environment(qairt_root),
            timeout=timeout_seconds,
        )
        return_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as error:
        timed_out = True
        return_code = 124
        stdout = error.stdout or b""
        stderr = error.stderr or b""
    elapsed_ns = time.monotonic_ns() - started_ns
    stdout_path = log_dir / f"{case.case_id}.stdout.log"
    stderr_path = log_dir / f"{case.case_id}.stderr.log"
    write_exclusive(stdout_path, stdout)
    write_exclusive(stderr_path, stderr)
    result: dict[str, Any] = {
        "case_id": case.case_id,
        "command": command,
        "return_code": return_code,
        "timed_out": timed_out,
        "elapsed_ns": elapsed_ns,
        "stdout": {"bytes": len(stdout), "sha256": hashlib.sha256(stdout).hexdigest()},
        "stderr": {"bytes": len(stderr), "sha256": hashlib.sha256(stderr).hexdigest()},
    }
    if return_code != 0:
        result["state"] = "blocked_fail_closed"
        return result
    raw_outputs = sorted(output_dir.rglob("*.raw"))
    if len(raw_outputs) != 1:
        raise PhoneGateError(f"expected one raw output for {case.case_id}, got {len(raw_outputs)}")
    output = raw_outputs[0]
    if output.stat().st_size != case.output_bytes:
        raise PhoneGateError(f"candidate output byte count mismatch: {case.case_id}")
    result["state"] = "available_unmeasured"
    result["output"] = {
        "relative_path": output.relative_to(run_root).as_posix(),
        "bytes": output.stat().st_size,
        "sha256": sha256_path(output),
    }
    return result


def decode_s16(payload: bytes, scale: float) -> list[float]:
    if len(payload) % 2:
        raise PhoneGateError("S16 payload has an odd byte count")
    return [value[0] * scale for value in struct.iter_unpack("<h", payload)]


def adjudicate_case(
    *,
    case: CaseContract,
    output_path: Path,
    output_scale: float,
    limits: dict[str, Any],
) -> dict[str, Any]:
    reference = bf16_payload_to_floats(read_regular(case.reference_path))
    candidate = decode_s16(read_regular(output_path), output_scale)
    metrics = vector_metrics(reference, candidate)
    metrics["softmax_js_divergence"] = softmax_js_divergence(reference, candidate)
    passed, failures = adjudicate_metrics(metrics, limits)
    return {
        "case_id": case.case_id,
        "passed": passed,
        "failures": failures,
        "metrics": metrics,
    }


def execute(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    run_root = args.run_root.resolve()
    prereg = load_preregistration(args.execution_preregistration, args.expected_preregistration_sha256)
    if run_root.as_posix() != prereg.get("phone_run_root"):
        raise PhoneGateError("phone run root differs from preregistration")
    validate_execution_code(prereg)
    context_record = prereg["context_artifact"]
    context_path = resolve_relative(run_root, context_record["relative_path"])
    validate_file(
        context_path,
        expected_bytes=int(context_record["bytes"]),
        expected_sha256=str(context_record["sha256"]),
    )
    qairt_root = args.qairt_root.resolve()
    qnn_net_run = validate_toolchain(qairt_root, prereg)
    cases = validate_cases(run_root, prereg)
    thermal_before = thermal_snapshot()
    enforce_thermal_guard(thermal_before, prereg["thermal_guard"])

    executions = []
    for case in cases:
        snapshot = thermal_snapshot()
        enforce_thermal_guard(snapshot, prereg["thermal_guard"])
        record = run_case(
            case=case,
            run_root=run_root,
            qairt_root=qairt_root,
            qnn_net_run=qnn_net_run,
            context_path=context_path,
            timeout_seconds=int(prereg["command_contract"]["timeout_seconds_per_case"]),
        )
        record["thermal_before"] = snapshot
        record["thermal_after"] = thermal_snapshot()
        executions.append(record)
        if record["state"] == "blocked_fail_closed":
            break

    qnn_execution_count = sum(record["return_code"] == 0 for record in executions)
    blocked = len(executions) != len(cases) or any(
        record["state"] == "blocked_fail_closed" for record in executions
    )
    adjudications = []
    if not blocked:
        output_scale = float(prereg["output_quantization"]["scale"])
        limits = prereg["numeric_and_ranking_thresholds"]
        by_case = {case.case_id: case for case in cases}
        for execution in executions:
            output_path = resolve_relative(run_root, execution["output"]["relative_path"])
            adjudications.append(
                adjudicate_case(
                    case=by_case[execution["case_id"]],
                    output_path=output_path,
                    output_scale=output_scale,
                    limits=limits,
                )
            )

    every_case_passed = bool(adjudications) and all(record["passed"] for record in adjudications)
    if blocked:
        status = "blocked_fail_closed"
        exit_code = 3
    elif every_case_passed:
        status = "passed_scope"
        exit_code = 0
    else:
        status = "falsified_scope"
        exit_code = 2
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "status": status,
        "scope": "bounded_phone_native_s16_terminal_head_projection_diagnostic",
        "candidate_id": prereg["candidate_id"],
        "source_revision": prereg["source_revision"],
        "execution_preregistration_sha256": args.expected_preregistration_sha256,
        "provider_context_report_sha256": prereg["provider_context_report_sha256"],
        "context_artifact": {
            "bytes": int(context_record["bytes"]),
            "sha256": str(context_record["sha256"]),
        },
        "phone": prereg["phone"],
        "qnn_execution_count": qnn_execution_count,
        "executions": executions,
        "adjudications": adjudications,
        "numeric_and_ranking_thresholds": prereg["numeric_and_ranking_thresholds"],
        "every_case_passed": every_case_passed,
        "thermal_before": thermal_before,
        "thermal_after": thermal_snapshot(),
        "provider_generator_cleanup_anomaly": True,
        "promotion_allowed": False,
        "full_L2_passed": False,
        "raw_outputs_egressed_from_phone": False,
        "nonclaims": [
            "No clean provider-generator exit, full L1, full L2, learning, or authority-quality pass is claimed.",
            "A passed diagnostic admits only this frozen S16 terminal-head projection surface.",
        ],
    }
    return receipt, exit_code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-preregistration", type=Path, required=True)
    parser.add_argument("--expected-preregistration-sha256", required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--qairt-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        receipt, exit_code = execute(args)
    except Exception as error:
        receipt = {
            "schema_version": RECEIPT_SCHEMA,
            "status": "blocked_fail_closed",
            "scope": "bounded_phone_native_s16_terminal_head_projection_diagnostic",
            "error_type": type(error).__name__,
            "error": str(error),
            "promotion_allowed": False,
            "full_L2_passed": False,
        }
        exit_code = 4
    args.receipt.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    digest = write_hashed_receipt(args.receipt, receipt)
    print(json.dumps({"receipt_sha256": digest, "status": receipt["status"]}, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

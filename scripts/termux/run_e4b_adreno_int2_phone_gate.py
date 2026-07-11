#!/usr/bin/env python3
"""Build, execute, and adjudicate the frozen Adreno packed-INT2 LM head on-phone."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTRACT_PATH = ROOT / "polymath_ai/frontier/e4b_adreno_int2_lm_head.py"
SPEC = importlib.util.spec_from_file_location(
    "_e4b_adreno_int2_contract", CONTRACT_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load Adreno execution contract")
contract = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = contract
SPEC.loader.exec_module(contract)


class PhoneExecutionError(contract.AdrenoGateError):
    """Raised when the phone execution cannot preserve the frozen experiment."""


def minimal_phone_environment(*, temporary_directory: Path) -> dict[str, str]:
    return {
        "HOME": "/data/data/com.termux/files/home",
        "PATH": "/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin",
        "TMPDIR": str(temporary_directory),
        "LANG": "C",
        "LC_ALL": "C",
        "TZ": "UTC",
    }


def create_private_directory(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise PhoneExecutionError(f"refusing to reuse private directory: {path}")
    path.mkdir(mode=0o700, parents=False)
    metadata = path.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_nlink < 2:
        raise PhoneExecutionError(f"private directory creation failed: {path}")


def read_frozen_payload(
    path: Path, *, expected_bytes: int, expected_sha256: str, label: str
) -> bytes:
    contract.validate_regular(
        path,
        expected_bytes=expected_bytes,
        expected_sha256=expected_sha256,
    )
    payload = contract.read_regular(path)
    if len(payload) != expected_bytes or contract.sha256_bytes(payload) != (
        expected_sha256
    ):
        raise PhoneExecutionError(f"{label} changed during retained read")
    return payload


def load_bound_preregistration(path: Path, expected_sha256: str) -> dict[str, Any]:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise PhoneExecutionError("preregistration path is unsafe")
    raw = contract.read_regular(path)
    if (
        len(expected_sha256) != 64
        or any(character not in "0123456789abcdef" for character in expected_sha256)
        or hashlib.sha256(raw).hexdigest() != expected_sha256
    ):
        raise PhoneExecutionError("preregistration digest mismatch")
    payload = contract.strict_json_decode(raw, source=str(path))
    contract.validate_preregistration(payload)
    contract.validate_source_closure(ROOT, payload)
    return payload


def thermal_snapshot() -> list[dict[str, Any]]:
    result = []
    for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
        try:
            sensor = (zone / "type").read_text(encoding="utf-8").strip()
            value = int((zone / "temp").read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
        result.append({"sensor": sensor, "millidegrees_c": value})
    return result


def enforce_thermal_guard(
    snapshot: list[dict[str, Any]], envelope: dict[str, Any]
) -> int:
    sensor = str(envelope["thermal_sensor_type"])
    limit = int(envelope["thermal_stop_at_or_above_millidegrees_c"])
    observed = [item["millidegrees_c"] for item in snapshot if item["sensor"] == sensor]
    if len(observed) != 1:
        raise PhoneExecutionError("thermal guard sensor cardinality mismatch")
    if observed[0] >= limit:
        raise PhoneExecutionError("thermal guard stopped execution")
    return observed[0]


def available_memory_bytes() -> int:
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("MemAvailable:"):
            fields = line.split()
            if len(fields) == 3 and fields[2] == "kB":
                return int(fields[1]) * 1024
    raise PhoneExecutionError("MemAvailable is unavailable")


def validate_resource_floor(run_root: Path, envelope: dict[str, Any]) -> dict[str, int]:
    memory = available_memory_bytes()
    storage = shutil.disk_usage(run_root).free
    if memory < int(envelope["minimum_available_memory_bytes"]):
        raise PhoneExecutionError("available memory is below the frozen floor")
    if storage < int(envelope["minimum_available_storage_bytes"]):
        raise PhoneExecutionError("available storage is below the frozen floor")
    temperature = enforce_thermal_guard(thermal_snapshot(), envelope)
    return {
        "available_memory_bytes": memory,
        "available_storage_bytes": storage,
        "temperature_millidegrees_c": temperature,
    }


def validate_phone_runtime_identity(preregistration: dict[str, Any]) -> dict[str, Any]:
    evidence = preregistration.get("opencl_evidence")
    if not isinstance(evidence, dict):
        raise PhoneExecutionError("OpenCL evidence binding is absent")
    if evidence.get("android_build_fingerprint_stdout_sha256") != (
        contract.ANDROID_BUILD_FINGERPRINT_STDOUT_SHA256
    ):
        raise PhoneExecutionError("Android fingerprint preregistration drifted")
    frozen_files = [dict(item) for item in contract.VENDOR_RUNTIME_FILES]
    if evidence.get("vendor_runtime_files") != frozen_files:
        raise PhoneExecutionError("OpenCL vendor runtime preregistration drifted")
    for record in frozen_files:
        contract.validate_regular(
            Path(record["absolute_path"]),
            expected_bytes=int(record["bytes"]),
            expected_sha256=str(record["sha256"]),
        )
    fingerprint = subprocess.run(
        ["/system/bin/getprop", "ro.build.fingerprint"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout
    if not fingerprint.endswith(b"\n") or fingerprint.count(b"\n") != 1:
        raise PhoneExecutionError("Android build fingerprint stdout shape drifted")
    if hashlib.sha256(fingerprint).hexdigest() != (
        contract.ANDROID_BUILD_FINGERPRINT_STDOUT_SHA256
    ):
        raise PhoneExecutionError("Android build fingerprint drifted")
    compiler = Path(contract.TERMUX_CLANGXX_PATH)
    if not compiler.is_symlink():
        raise PhoneExecutionError("Termux clang++ link topology drifted")
    resolved_compiler = compiler.resolve(strict=True)
    contract.validate_regular(
        resolved_compiler,
        expected_bytes=contract.TERMUX_CLANGXX_RESOLVED_BYTES,
        expected_sha256=contract.TERMUX_CLANGXX_RESOLVED_SHA256,
    )
    version = subprocess.run(
        [str(compiler), "--version"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ).stdout
    if hashlib.sha256(version).hexdigest() != (
        contract.TERMUX_CLANGXX_VERSION_STDOUT_SHA256
    ):
        raise PhoneExecutionError("Termux clang++ version drifted")
    return {
        "android_build_fingerprint_stdout_sha256": (
            contract.ANDROID_BUILD_FINGERPRINT_STDOUT_SHA256
        ),
        "vendor_runtime_files": [
            {"role": item["role"], "bytes": item["bytes"], "sha256": item["sha256"]}
            for item in frozen_files
        ],
        "compiler_resolved_bytes": contract.TERMUX_CLANGXX_RESOLVED_BYTES,
        "compiler_resolved_sha256": contract.TERMUX_CLANGXX_RESOLVED_SHA256,
        "compiler_version_stdout_sha256": (
            contract.TERMUX_CLANGXX_VERSION_STDOUT_SHA256
        ),
    }


def build_phone_binary(binary_path: Path, log_dir: Path) -> dict[str, Any]:
    build_script = ROOT / "native/e4b_adreno_int2_lm_head/build_phone.sh"
    environment = minimal_phone_environment(temporary_directory=log_dir)
    toolchain = subprocess.run(
        [contract.TERMUX_CLANGXX_PATH, "--version"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=environment,
    ).stdout
    started = time.monotonic_ns()
    process = subprocess.run(
        [str(build_script), str(binary_path)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )
    elapsed = time.monotonic_ns() - started
    contract.write_exclusive(log_dir / "build.stdout.log", process.stdout)
    contract.write_exclusive(log_dir / "build.stderr.log", process.stderr)
    if process.returncode != 0:
        raise PhoneExecutionError("native build failed")
    metadata = binary_path.lstat()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or not os.access(binary_path, os.X_OK)
    ):
        raise PhoneExecutionError("native binary publication failed")
    return {
        "binary_bytes": metadata.st_size,
        "binary_sha256": contract.sha256_path(binary_path),
        "toolchain_version_sha256": hashlib.sha256(toolchain).hexdigest(),
        "toolchain_resolved_sha256": contract.sha256_path(
            Path(contract.TERMUX_CLANGXX_PATH).resolve(strict=True)
        ),
        "build_elapsed_ns": elapsed,
        "stdout_sha256": hashlib.sha256(process.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(process.stderr).hexdigest(),
    }


def prepare_phone_tensors(
    packed_weight_path: Path,
    source_scale_path: Path,
    tensor_dir: Path,
) -> tuple[Path, Path, bytes, bytes, dict[str, Any]]:
    packed_weight = read_frozen_payload(
        packed_weight_path,
        expected_bytes=contract.PACKED_WEIGHT_BYTES,
        expected_sha256=contract.PACKED_WEIGHT_SHA256,
        label="packed weight",
    )
    source_scale = read_frozen_payload(
        source_scale_path,
        expected_bytes=contract.SCALE_F32_BYTES,
        expected_sha256=contract.SCALE_F32_SHA256,
        label="source scale",
    )
    exact_f32, compact_bf16 = contract.bf16_rne_scales(source_scale)
    if contract.sha256_bytes(exact_f32) != contract.SCALE_BF16_RNE_AS_F32_SHA256:
        raise PhoneExecutionError("BF16-RNE scale transform digest mismatch")
    staged_packed_path = tensor_dir / "lm_head_weight.u2.packed.bin"
    contract.write_exclusive(staged_packed_path, packed_weight, mode=0o400)
    compact_path = tensor_dir / "lm_head_weight_scale.bf16.raw"
    contract.write_exclusive(compact_path, compact_bf16, mode=0o400)
    return (
        staged_packed_path,
        compact_path,
        packed_weight,
        compact_bf16,
        {
            "model_lineage_sha256": contract.MODEL_SHA256,
            "runtime_tensor_source": "phone_private_hash_bound_extracted_tensors",
            "packed_weight_sha256": contract.PACKED_WEIGHT_SHA256,
            "source_scale_sha256": contract.SCALE_F32_SHA256,
            "transformed_exact_f32_scale_sha256": (
                contract.SCALE_BF16_RNE_AS_F32_SHA256
            ),
            "compact_bf16_scale_sha256": contract.sha256_bytes(compact_bf16),
        },
    )


def prepare_inputs_and_references(
    run_root: Path,
    preregistration: dict[str, Any],
    private_input_dir: Path,
    private_reference_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cases = []
    for record in preregistration["cases"]:
        source = contract.resolve_relative(run_root, record["s16_source_relative_path"])
        authority = contract.resolve_relative(
            run_root, record["authority_relative_path"]
        )
        source_payload = read_frozen_payload(
            source,
            expected_bytes=int(record["s16_source_bytes"]),
            expected_sha256=str(record["s16_source_sha256"]),
            label=f"{record['case_id']} S16 input",
        )
        authority_payload = read_frozen_payload(
            authority,
            expected_bytes=int(record["authority_bytes"]),
            expected_sha256=str(record["authority_sha256"]),
            label=f"{record['case_id']} authority",
        )
        staged_authority = private_reference_dir / f"{record['case_id']}.bf16.raw"
        contract.write_exclusive(staged_authority, authority_payload, mode=0o400)
        bf16_payload = contract.s16_input_to_bf16(source_payload)
        if contract.sha256_bytes(bf16_payload) != record["bf16_input_sha256"]:
            raise PhoneExecutionError("lossless S16-to-BF16 input recovery drifted")
        input_path = private_input_dir / f"{record['case_id']}.bf16.raw"
        contract.write_exclusive(input_path, bf16_payload)
        cases.append(
            {
                "contract": record,
                "input_path": input_path,
                "authority": staged_authority,
            }
        )

    sentinel_contract = preregistration["off_s16_lattice_sentinel"]
    sentinel_payload = contract.off_s16_lattice_sentinel()
    sentinel_path = private_input_dir / f"{contract.SENTINEL_CASE_ID}.bf16.raw"
    contract.write_exclusive(sentinel_path, sentinel_payload)
    sentinel = {"contract": sentinel_contract, "input_path": sentinel_path}
    return cases, sentinel


def output_paths(
    run_root: Path,
    cases: list[dict[str, Any]],
    sentinel: dict[str, Any],
) -> list[dict[str, Any]]:
    all_cases = [*cases, sentinel]
    for item in all_cases:
        record = item["contract"]
        paths = [
            contract.resolve_relative(run_root, relative)
            for relative in record["replay_output_relative_paths"]
        ]
        if any(path.exists() or path.is_symlink() for path in paths):
            raise PhoneExecutionError("candidate output path already exists")
        item["output_paths"] = paths
    return all_cases


def native_command(
    *,
    binary_path: Path,
    packed_weight_path: Path,
    scale_path: Path,
    native_summary_path: Path,
    all_cases: list[dict[str, Any]],
) -> list[str]:
    command = [
        str(binary_path),
        "--packed-weight",
        str(packed_weight_path),
        "--scale-bf16",
        str(scale_path),
        "--summary",
        str(native_summary_path),
    ]
    for item in all_cases:
        command.extend(
            [
                "--case",
                str(item["contract"]["case_id"]),
                str(item["input_path"]),
                str(item["output_paths"][0]),
                str(item["output_paths"][1]),
            ]
        )
    return command


def run_monitored(
    *,
    command: list[str],
    environment: dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
    envelope: dict[str, Any],
    progress: dict[str, Any],
) -> dict[str, Any]:
    temperatures = []
    started = time.monotonic_ns()
    maximum_ns = int(envelope["maximum_wall_time_seconds"]) * 1_000_000_000
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        progress["native_launch_state"] = "launch_attempted"
        process = subprocess.Popen(
            command, env=environment, stdout=stdout, stderr=stderr
        )
        progress["native_launch_state"] = "process_started"
        progress["candidate_execution_count"] = 1
        stopped = False
        while process.poll() is None:
            try:
                temperatures.append(enforce_thermal_guard(thermal_snapshot(), envelope))
            except PhoneExecutionError:
                stopped = True
                process.terminate()
                break
            if time.monotonic_ns() - started > maximum_ns:
                stopped = True
                process.terminate()
                break
            time.sleep(0.25)
        if stopped:
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                process.kill()
        return_code = process.wait()
        progress["native_launch_state"] = "process_returned"
        progress["native_return_code"] = return_code
    elapsed = time.monotonic_ns() - started
    return {
        "return_code": return_code,
        "elapsed_ns": elapsed,
        "thermal_or_timeout_stop": stopped,
        "temperature_min_millidegrees_c": min(temperatures) if temperatures else None,
        "temperature_max_millidegrees_c": max(temperatures) if temperatures else None,
        "temperature_snapshot_count": len(temperatures),
        "stdout_sha256": contract.sha256_path(stdout_path),
        "stderr_sha256": contract.sha256_path(stderr_path),
    }


def validate_native_summary(
    path: Path,
    preregistration: dict[str, Any],
    return_code: int,
) -> dict[str, Any]:
    summary = contract.strict_json_load(path)
    if summary.get("schema_version") != "gemma4_e4b_adreno_int2_native_summary_v1":
        raise PhoneExecutionError("native summary schema mismatch")
    if summary.get("candidate_id") != contract.CANDIDATE_ID:
        raise PhoneExecutionError("native summary candidate mismatch")
    if summary.get("build_options") != "-cl-std=CL3.0":
        raise PhoneExecutionError("native OpenCL build options drifted")
    lifecycle = summary.get("lifecycle")
    expected_lifecycle = {
        "process_count": 1,
        "context_count": 1,
        "program_build_count": 1,
        "packed_weight_upload_count": 1,
        "scale_upload_count": 1,
        "authority_case_count": 3,
        "sentinel_case_count": 1,
        "replays_per_case": 2,
        "dispatch_count": 8,
    }
    if lifecycle != expected_lifecycle:
        raise PhoneExecutionError("native residency lifecycle mismatch")
    if not isinstance(summary.get("all_replays_byte_identical"), bool):
        raise PhoneExecutionError("native replay aggregate is invalid")
    case_records = summary.get("cases")
    expected_ids = [case["case_id"] for case in preregistration["cases"]]
    expected_ids.append(contract.SENTINEL_CASE_ID)
    if (
        not isinstance(case_records, list)
        or [item.get("case_id") for item in case_records] != expected_ids
    ):
        raise PhoneExecutionError("native case order or cardinality mismatch")
    replay_flags = [item.get("replay_byte_identical") for item in case_records]
    if any(not isinstance(value, bool) for value in replay_flags):
        raise PhoneExecutionError("native case replay record is invalid")
    if summary["all_replays_byte_identical"] != all(replay_flags):
        raise PhoneExecutionError("native replay aggregate disagrees with cases")
    expected_return_code = 0 if summary["all_replays_byte_identical"] else 2
    if return_code != expected_return_code:
        raise PhoneExecutionError("native return code disagrees with replay summary")
    for item in case_records:
        timings = item.get("kernel_elapsed_ns")
        if (
            not isinstance(timings, list)
            or len(timings) != 2
            or any(not isinstance(value, int) or value < 0 for value in timings)
        ):
            raise PhoneExecutionError("native kernel timing record is invalid")
    return summary


def validate_native_replay_observations(
    summary: dict[str, Any],
    case_results: list[dict[str, Any]],
    sentinel_result: dict[str, Any],
) -> None:
    observed = {
        item["case_id"]: item["replay_byte_identical"]
        for item in [*case_results, sentinel_result]
    }
    native = {
        item["case_id"]: item["replay_byte_identical"] for item in summary["cases"]
    }
    if native != observed:
        raise PhoneExecutionError(
            "native replay claims disagree with independently read outputs"
        )


def sanitized_metrics(result: dict[str, Any]) -> dict[str, Any]:
    metrics = result["metrics"]
    return {
        "max_abs": metrics["max_abs"],
        "rms": metrics["rms"],
        "relative_l2": metrics["relative_l2"],
        "cosine": metrics["cosine"],
        "softmax_js_divergence": metrics["softmax_js_divergence"],
        "top_k_set_overlap": metrics["top_k_set_overlap"],
        "top_1_equal": metrics["top_1_equal"],
    }


def adjudicate_outputs(
    *,
    cases: list[dict[str, Any]],
    sentinel: dict[str, Any],
    sentinel_reference: bytes,
) -> tuple[list[dict[str, Any]], dict[str, Any], bool]:
    case_results = []
    every_passed = True
    for item in cases:
        outputs = item["output_paths"]
        for path in outputs:
            contract.validate_regular(
                path,
                expected_bytes=contract.OUTPUT_BYTES,
                expected_sha256=contract.sha256_path(path),
            )
        first = contract.read_regular(outputs[0])
        second = contract.read_regular(outputs[1])
        replay_equal = first == second
        authority = read_frozen_payload(
            item["authority"],
            expected_bytes=int(item["contract"]["authority_bytes"]),
            expected_sha256=str(item["contract"]["authority_sha256"]),
            label=f"{item['contract']['case_id']} staged authority",
        )
        result = contract.adjudicate_bf16_output(authority, first)
        failures = list(result["failures"])
        if not replay_equal:
            failures.append("replay_not_byte_identical")
        passed = replay_equal and bool(result["passed"])
        every_passed = every_passed and passed
        case_results.append(
            {
                "case_id": item["contract"]["case_id"],
                "passed": passed,
                "failures": failures,
                "metrics": sanitized_metrics(result),
                "candidate_output_bytes": len(first),
                "candidate_output_sha256": contract.sha256_bytes(first),
                "replay_output_sha256": contract.sha256_bytes(second),
                "replay_byte_identical": replay_equal,
            }
        )
    for path in sentinel["output_paths"]:
        contract.validate_regular(
            path,
            expected_bytes=contract.OUTPUT_BYTES,
            expected_sha256=contract.sha256_path(path),
        )
    sentinel_outputs = [
        contract.read_regular(path) for path in sentinel["output_paths"]
    ]
    sentinel_replay = sentinel_outputs[0] == sentinel_outputs[1]
    sentinel_exact = sentinel_outputs[0] == sentinel_reference
    sentinel_passed = sentinel_replay and sentinel_exact
    every_passed = every_passed and sentinel_passed
    sentinel_result = {
        "case_id": contract.SENTINEL_CASE_ID,
        "passed": sentinel_passed,
        "failures": [
            failure
            for failure, failed in (
                ("sentinel_reference_mismatch", not sentinel_exact),
                ("replay_not_byte_identical", not sentinel_replay),
            )
            if failed
        ],
        "full_width_single_product_reference_exact": sentinel_exact,
        "replay_byte_identical": sentinel_replay,
        "reference_sha256": contract.sha256_bytes(sentinel_reference),
        "candidate_output_sha256": contract.sha256_bytes(sentinel_outputs[0]),
        "replay_output_sha256": contract.sha256_bytes(sentinel_outputs[1]),
    }
    return case_results, sentinel_result, every_passed


def publish_receipt_transaction(directory: Path, payload: dict[str, Any]) -> str:
    if directory.exists() or directory.is_symlink():
        raise FileExistsError(directory)
    parent = directory.parent
    metadata = parent.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or parent.is_symlink():
        raise PhoneExecutionError("receipt parent must be a real directory")
    temporary = Path(tempfile.mkdtemp(prefix=f".{directory.name}.tmp-", dir=parent))
    os.chmod(temporary, 0o700)
    encoded = contract.canonical_json(payload)
    digest = hashlib.sha256(encoded).hexdigest()
    published = False
    try:
        contract.write_exclusive(temporary / "receipt.json", encoded)
        contract.write_exclusive(
            temporary / "receipt.json.sha256",
            f"{digest}  receipt.json\n".encode("ascii"),
        )
        completion = {
            "schema_version": "gemma4_e4b_adreno_phone_receipt_completion_v1",
            "state": "complete",
            "receipt_sha256": digest,
            "receipt_status": payload["status"],
        }
        contract.write_exclusive(
            temporary / "COMPLETE.json", contract.canonical_json(completion)
        )
        contract._fsync_directory(temporary)
        contract._rename_noreplace(temporary, directory)
        published = True
        contract._fsync_directory(parent)
        return digest
    except Exception:
        if published:
            observed = load_complete_receipt(directory)
            if contract.canonical_json(observed) != encoded:
                raise PhoneExecutionError(
                    "published receipt failed post-rename verification"
                )
            return digest
        if temporary.exists():
            for child in temporary.iterdir():
                child.unlink()
            temporary.rmdir()
        raise


def load_complete_receipt(directory: Path) -> dict[str, Any]:
    expected_names = {"receipt.json", "receipt.json.sha256", "COMPLETE.json"}
    if not directory.is_dir() or directory.is_symlink():
        raise PhoneExecutionError("receipt transaction directory is invalid")
    if {path.name for path in directory.iterdir()} != expected_names:
        raise PhoneExecutionError(
            "receipt transaction is incomplete or has extra files"
        )
    receipt_path = directory / "receipt.json"
    receipt = contract.strict_json_load(receipt_path)
    digest = contract.sha256_path(receipt_path)
    sidecar = contract.read_regular(directory / "receipt.json.sha256")
    if sidecar != f"{digest}  receipt.json\n".encode("ascii"):
        raise PhoneExecutionError("receipt sidecar mismatch")
    completion = contract.strict_json_load(directory / "COMPLETE.json")
    expected_completion = {
        "schema_version": "gemma4_e4b_adreno_phone_receipt_completion_v1",
        "state": "complete",
        "receipt_sha256": digest,
        "receipt_status": receipt.get("status"),
    }
    if completion != expected_completion:
        raise PhoneExecutionError("receipt completion marker mismatch")
    return receipt


def execute(args: argparse.Namespace, progress: dict[str, Any]) -> int:
    preregistration = load_bound_preregistration(
        args.preregistration, args.prereg_sha256
    )
    run_root = args.run_root
    metadata = run_root.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or run_root.is_symlink():
        raise PhoneExecutionError("run root must be a real directory")
    envelope = preregistration["phone_execution_envelope"]
    resource_before = validate_resource_floor(run_root, envelope)
    runtime_identity = validate_phone_runtime_identity(preregistration)

    private_inputs = run_root / "private_inputs"
    private_outputs = run_root / "private_outputs"
    private_tensors = run_root / "private_tensors"
    private_references = run_root / "private_references"
    native_dir = run_root / "native_execution"
    for path in (
        private_inputs,
        private_outputs,
        private_tensors,
        private_references,
        native_dir,
    ):
        create_private_directory(path)

    binary_path = native_dir / "e4b_adreno_int2_lm_head"
    build = build_phone_binary(binary_path, native_dir)
    (
        staged_packed_path,
        scale_path,
        packed_weight,
        compact_scale,
        tensor_identity,
    ) = prepare_phone_tensors(args.packed_weight, args.source_scale, private_tensors)
    cases, sentinel = prepare_inputs_and_references(
        run_root, preregistration, private_inputs, private_references
    )
    sentinel_reference = contract.sentinel_reference_output(
        packed_weight, compact_scale
    )
    del packed_weight
    all_cases = output_paths(run_root, cases, sentinel)
    progress["expected_outputs"] = [
        {
            "case_id": item["contract"]["case_id"],
            "replay": replay,
            "path": path,
        }
        for item in all_cases
        for replay, path in enumerate(item["output_paths"])
    ]
    native_summary_path = native_dir / "native_summary.json"
    progress["native_summary_path"] = native_summary_path
    command = native_command(
        binary_path=binary_path,
        packed_weight_path=staged_packed_path,
        scale_path=scale_path,
        native_summary_path=native_summary_path,
        all_cases=all_cases,
    )
    environment = minimal_phone_environment(temporary_directory=native_dir)
    environment.update(contract.runtime_environment(preregistration["opencl_contract"]))
    execution = run_monitored(
        command=command,
        environment=environment,
        stdout_path=native_dir / "native.stdout.log",
        stderr_path=native_dir / "native.stderr.log",
        envelope=envelope,
        progress=progress,
    )
    if execution["thermal_or_timeout_stop"]:
        raise PhoneExecutionError("native execution stopped by resource guard")
    if execution["return_code"] not in {0, 2}:
        raise PhoneExecutionError(
            "native execution failed before numerical adjudication"
        )
    summary = validate_native_summary(
        native_summary_path, preregistration, execution["return_code"]
    )
    progress["candidate_output_state"] = "present_pending_adjudication"
    case_results, sentinel_result, every_passed = adjudicate_outputs(
        cases=cases,
        sentinel=sentinel,
        sentinel_reference=sentinel_reference,
    )
    progress["candidate_output_state"] = "fully_adjudicated"
    progress["candidate_output_adjudicated"] = True
    progress["adjudication_status"] = (
        "passed_scope" if every_passed else "falsified_scope"
    )
    progress["every_case_and_metric_passed"] = every_passed
    validate_native_replay_observations(summary, case_results, sentinel_result)
    contract.validate_regular(
        staged_packed_path,
        expected_bytes=contract.PACKED_WEIGHT_BYTES,
        expected_sha256=contract.PACKED_WEIGHT_SHA256,
    )
    contract.validate_regular(
        scale_path,
        expected_bytes=contract.SCALE_BF16_BYTES,
        expected_sha256=tensor_identity["compact_bf16_scale_sha256"],
    )
    resource_after = validate_resource_floor(run_root, envelope)
    status = "passed_scope" if every_passed else "falsified_scope"
    receipt = {
        "schema_version": contract.PHONE_RECEIPT_SCHEMA,
        "status": status,
        "candidate_id": contract.CANDIDATE_ID,
        "preregistration_sha256": args.prereg_sha256,
        "frontier_selector_sha256": preregistration["frontier_selector_sha256"],
        "candidate_execution_count": 1,
        "bounded_terminal_head_every_case_and_metric_passed": every_passed,
        "source_and_build": build,
        "phone_runtime_identity": runtime_identity,
        "tensor_identity": tensor_identity,
        "runtime_identity_sha256": contract.sha256_bytes(
            contract.canonical_json(summary["runtime"])
        ),
        "native_summary_sha256": contract.sha256_path(native_summary_path),
        "lifecycle": summary["lifecycle"],
        "case_results": case_results,
        "off_s16_lattice_sentinel": sentinel_result,
        "numeric_and_ranking_thresholds": contract.FROZEN_THRESHOLDS,
        "execution": execution,
        "performance_secondary": {
            "authority_gate": False,
            "kernel_elapsed_ns_by_case_and_replay": [
                {
                    "case_id": item["case_id"],
                    "kernel_elapsed_ns": item["kernel_elapsed_ns"],
                }
                for item in summary["cases"]
            ],
        },
        "resource_before": resource_before,
        "resource_after": resource_after,
        "custody": {
            "raw_model_inputs_references_candidate_outputs_and_sentinel": "phone_private",
            "raw_output_egress": False,
            "phone_private_upload_to_provider": False,
            "sanitized_hash_bound_receipt_only": True,
        },
        "promotion_allowed": False,
        "nonclaims": [
            "bounded_terminal_head_only",
            "no_full_L1_or_L2_pass",
            "no_learning_or_authority_quality_pass",
            "performance_is_secondary_and_not_an_authority_gate",
        ],
    }
    publish_receipt_transaction(args.receipt_dir, receipt)
    return 0 if every_passed else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--prereg-sha256", required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--packed-weight", type=Path, required=True)
    parser.add_argument("--source-scale", type=Path, required=True)
    parser.add_argument("--receipt-dir", type=Path, required=True)
    args = parser.parse_args()
    progress: dict[str, Any] = {
        "native_launch_state": "not_started",
        "candidate_execution_count": 0,
        "candidate_output_state": "none_known_present",
        "candidate_output_adjudicated": False,
        "adjudication_status": None,
        "every_case_and_metric_passed": None,
    }
    try:
        return execute(args, progress)
    except Exception as exc:
        if not args.receipt_dir.exists() and args.run_root.exists():
            output_presence = []
            for expected in progress.get("expected_outputs", []):
                path = expected["path"]
                present = path.is_file() and not path.is_symlink()
                record = {
                    "case_id": expected["case_id"],
                    "replay": expected["replay"],
                    "present": present,
                }
                if present:
                    record["bytes"] = path.stat().st_size
                    record["sha256"] = contract.sha256_path(path)
                output_presence.append(record)
            output_count = sum(1 for item in output_presence if item["present"])
            if output_count:
                progress["candidate_output_state"] = "present_unadjudicated_or_partial"
            summary_path = progress.get("native_summary_path")
            summary_present = (
                isinstance(summary_path, Path)
                and summary_path.is_file()
                and not summary_path.is_symlink()
            )
            detail = f"{type(exc).__name__}:{exc}".encode("utf-8", errors="replace")
            blocker = {
                "schema_version": contract.PHONE_RECEIPT_SCHEMA,
                "status": "blocked_fail_closed",
                "candidate_id": contract.CANDIDATE_ID,
                "preregistration_sha256": args.prereg_sha256,
                "candidate_execution_count": progress["candidate_execution_count"],
                "native_launch_state": progress["native_launch_state"],
                "native_return_code": progress.get("native_return_code"),
                "candidate_output_state": progress["candidate_output_state"],
                "candidate_output_file_count": output_count,
                "candidate_output_presence": output_presence,
                "native_summary_present": summary_present,
                "native_summary_sha256": (
                    contract.sha256_path(summary_path) if summary_present else None
                ),
                "candidate_output_adjudicated": progress[
                    "candidate_output_adjudicated"
                ],
                "adjudication_status": progress["adjudication_status"],
                "bounded_terminal_head_every_case_and_metric_passed": progress[
                    "every_case_and_metric_passed"
                ],
                "blocker_detail_sha256": hashlib.sha256(detail).hexdigest(),
                "raw_output_egress": False,
                "promotion_allowed": False,
            }
            try:
                publish_receipt_transaction(args.receipt_dir, blocker)
            except Exception:
                pass
        print("Adreno gate blocked fail-closed", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

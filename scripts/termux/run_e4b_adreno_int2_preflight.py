#!/usr/bin/env python3
"""Build and probe the Adreno candidate without model, tensor, or candidate data."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import select
import stat
import subprocess
import sys
import time
from typing import Any

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = ROOT / "scripts/termux/run_e4b_adreno_int2_phone_gate.py"
SPEC = importlib.util.spec_from_file_location("_e4b_adreno_phone_gate", GATE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load Adreno phone gate")
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


def git_status() -> bytes:
    return subprocess.run(
        [
            "/data/data/com.termux/files/usr/bin/git",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=dict(os.environ),
    ).stdout


def validate_platform_identity(temporary_directory: Path) -> dict[str, Any]:
    frozen_files = [dict(item) for item in gate.contract.VENDOR_RUNTIME_FILES]
    for record in frozen_files:
        gate.contract.validate_regular(
            Path(record["absolute_path"]),
            expected_bytes=int(record["bytes"]),
            expected_sha256=str(record["sha256"]),
        )
    fingerprint = subprocess.run(
        ["/system/bin/getprop", "ro.build.fingerprint"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=gate.minimal_phone_environment(temporary_directory=temporary_directory),
    ).stdout
    if (
        not fingerprint.endswith(b"\n")
        or fingerprint.count(b"\n") != 1
        or hashlib.sha256(fingerprint).hexdigest()
        != gate.contract.ANDROID_BUILD_FINGERPRINT_STDOUT_SHA256
    ):
        raise gate.PhoneExecutionError("Android build fingerprint drifted")
    gate.validate_android_linker64()
    gate.validate_termux_toolchain_files()
    for record in gate.contract.TERMUX_PYTHON_RUNTIME_FILES:
        gate.validate_bound_file_record(record, label="Python runtime")
    python_stdlib_identity = gate.contract.directory_tree_identity(
        Path(gate.contract.TERMUX_PYTHON_STDLIB_DIR)
    )
    if python_stdlib_identity != gate.contract.TERMUX_PYTHON_STDLIB_TREE_IDENTITY:
        raise gate.PhoneExecutionError("Termux Python stdlib tree identity drifted")
    return {
        "android_build_fingerprint_stdout_sha256": (
            gate.contract.ANDROID_BUILD_FINGERPRINT_STDOUT_SHA256
        ),
        "vendor_runtime_files": frozen_files,
        "android_linker64_sha256": gate.contract.ANDROID_LINKER64_RESOLVED_SHA256,
        "compiler_sha256": gate.contract.TERMUX_CLANGXX_RESOLVED_SHA256,
        "linker_sha256": gate.contract.TERMUX_LLD_RESOLVED_SHA256,
        "cxx_runtime_sha256": gate.contract.TERMUX_LIBCXX_SHA256,
        "termux_exec_source_sha256": gate.contract.TERMUX_EXEC_INTERPOSER_SHA256,
        "python_runtime_files": [
            dict(item) for item in gate.contract.TERMUX_PYTHON_RUNTIME_FILES
        ],
        "python_stdlib_tree": {
            "absolute_path": gate.contract.TERMUX_PYTHON_STDLIB_DIR,
            **python_stdlib_identity,
        },
        "compiler_runtime_libraries": [
            dict(item) for item in gate.contract.TERMUX_COMPILER_RUNTIME_FILES
        ],
        "compiler_resource_tree": {
            "absolute_path": gate.contract.TERMUX_CLANG_RESOURCE_DIR,
            **gate.contract.TERMUX_CLANG_RESOURCE_TREE_IDENTITY,
        },
        "include_tree": {
            "absolute_path": gate.contract.TERMUX_INCLUDE_DIR,
            **gate.contract.TERMUX_INCLUDE_TREE_IDENTITY,
        },
        "link_input_files": [
            dict(item) for item in gate.contract.TERMUX_LINK_INPUT_FILES
        ],
        "phone_system_runtime_files": [
            dict(item) for item in gate.contract.PHONE_SYSTEM_RUNTIME_FILES
        ],
    }


def require_new_output(path: Path, *, parent: Path) -> None:
    if (
        not path.is_absolute()
        or path.parent != parent
        or path.exists()
        or path.is_symlink()
    ):
        raise gate.PhoneExecutionError(f"unsafe preflight output path: {path}")


def publish_success_transaction(
    *, report_path: Path, report: dict[str, Any], build_dir: Path
) -> None:
    if report_path.name != "preflight_report.json":
        raise gate.PhoneExecutionError("preflight report filename is not canonical")
    encoded = gate.contract.canonical_json(report)
    digest = gate.contract.sha256_bytes(encoded)
    sidecar_path = build_dir / "preflight_report.json.sha256"
    completion_path = build_dir / "PREFLIGHT_COMPLETE.json"
    require_new_output(sidecar_path, parent=build_dir)
    require_new_output(completion_path, parent=build_dir)
    gate.contract.write_exclusive(report_path, encoded)
    gate.contract.write_exclusive(
        sidecar_path, f"{digest}  preflight_report.json\n".encode("ascii")
    )
    completion = {
        "schema_version": "gemma4_e4b_adreno_preflight_completion_v1",
        "state": "complete",
        "report_sha256": digest,
        "source_revision": report["source_revision"],
        "binary_sha256": report["build"]["first"]["binary_sha256"],
        "contract_sha256": report["probe"]["contract_sha256"],
        "custody_challenge": report["custody_challenge"],
    }
    gate.contract.write_exclusive(
        completion_path, gate.contract.canonical_json(completion)
    )
    gate.contract._fsync_directory(build_dir)


def publish_blocker(args: argparse.Namespace, error: Exception) -> None:
    if not args.build_dir.is_dir() or args.build_dir.is_symlink():
        return
    blocker = args.build_dir / "PREFLIGHT_BLOCKER.json"
    if blocker.exists() or blocker.is_symlink():
        return
    payload = {
        "schema_version": "gemma4_e4b_adreno_source_neutral_preflight_blocker_v1",
        "status": "blocked_fail_closed",
        "candidate_output_observed": False,
        "candidate_output_observation_scope": "this_custody_run_only",
        "model_or_tensor_path_supplied": False,
        "model_or_tensor_access_count_measured": False,
        "model_or_tensor_access_observation": "not_observed_no_paths_supplied",
        "model_or_tensor_access_observation_basis": (
            "exclusive_probe_argv_and_source_bound_control_flow_no_syscall_trace"
        ),
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    gate.contract.write_exclusive(blocker, gate.contract.canonical_json(payload))
    gate.contract._fsync_directory(args.build_dir)


def run(args: argparse.Namespace) -> int:
    gate.validate_parent_termux_exec_binding()
    if not gate.contract.is_sha256(args.custody_challenge):
        raise gate.PhoneExecutionError("custody challenge must be 256-bit lowercase hex")
    if git_status():
        raise gate.PhoneExecutionError("preflight source checkout is not clean")
    revision_before, closure_before = gate.contract.source_closure(ROOT)
    source_closure_sha256 = gate.contract.sha256_bytes(
        gate.contract.canonical_json(closure_before)
    )
    if not args.build_dir.is_absolute():
        raise gate.PhoneExecutionError("preflight build directory must be absolute")
    parent_metadata = args.build_dir.parent.lstat()
    if (
        not stat.S_ISDIR(parent_metadata.st_mode)
        or args.build_dir.parent.is_symlink()
    ):
        raise gate.PhoneExecutionError("preflight parent directory is unsafe")
    gate.create_private_directory(args.build_dir)
    require_new_output(args.probe_contract_output, parent=args.build_dir)
    require_new_output(args.report, parent=args.build_dir)
    platform_before = validate_platform_identity(args.build_dir)
    first_build_dir = args.build_dir / "build_a"
    second_build_dir = args.build_dir / "build_b"
    gate.create_private_directory(first_build_dir)
    gate.create_private_directory(second_build_dir)
    binary_path = first_build_dir / "e4b_adreno_int2_lm_head"
    second_binary_path = second_build_dir / "e4b_adreno_int2_lm_head"
    first_build = gate.build_phone_binary(
        binary_path,
        first_build_dir,
        source_closure=closure_before,
    )
    second_build = gate.build_phone_binary(
        second_binary_path,
        second_build_dir,
        source_closure=closure_before,
    )
    if (
        first_build["binary_bytes"] != second_build["binary_bytes"]
        or first_build["binary_sha256"] != second_build["binary_sha256"]
    ):
        raise gate.PhoneExecutionError("source-neutral native rebuild is not deterministic")
    binary_payload = gate.read_frozen_payload(
        binary_path,
        expected_bytes=first_build["binary_bytes"],
        expected_sha256=first_build["binary_sha256"],
        label="source-neutral preflight binary",
    )
    binary_descriptor = gate.open_unlinked_snapshot(
        payload=binary_payload,
        expected_sha256=first_build["binary_sha256"],
        temporary_directory=args.build_dir,
        prefix="e4b-preflight-binary",
    )
    environment = gate.minimal_phone_environment(temporary_directory=args.build_dir)
    command = [
        gate.contract.ANDROID_LINKER64_PATH,
        f"/proc/self/fd/{binary_descriptor}",
        "--probe-contract",
        str(args.probe_contract_output),
        "--custody-challenge",
        args.custody_challenge,
    ]
    started = time.monotonic_ns()
    stdout_path = args.build_dir / "probe.stdout.log"
    stderr_path = args.build_dir / "probe.stderr.log"
    try:
        with stdout_path.open("xb") as stdout_file, stderr_path.open("xb") as stderr_file:
            process = subprocess.Popen(
                command,
                stdout=stdout_file,
                stderr=stderr_file,
                env=environment,
                pass_fds=(binary_descriptor,),
                cwd=ROOT,
            )
            try:
                pidfd = gate.open_pidfd(process.pid)
            except Exception:
                process.terminate()
                process.wait(timeout=10)
                raise
            try:
                pidfd_metadata = os.fstat(pidfd)
                poller = select.poll()
                poller.register(pidfd, select.POLLIN)
                if not poller.poll(600_000):
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    raise gate.PhoneExecutionError("source-neutral probe timed out")
                wait_observation = os.waitid(
                    os.P_PIDFD, pidfd, os.WEXITED | os.WNOWAIT
                )
                process.wait()
            finally:
                os.close(pidfd)
                if process.returncode is None:
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
        elapsed = time.monotonic_ns() - started
        if (
            os.fstat(binary_descriptor).st_nlink != 0
            or gate._sha256_descriptor(binary_descriptor)
            != first_build["binary_sha256"]
        ):
            raise gate.PhoneExecutionError("preflight binary snapshot drifted")
    finally:
        os.close(binary_descriptor)
    stdout = gate.contract.read_regular(stdout_path)
    stderr = gate.contract.read_regular(stderr_path)
    if process.returncode != 0:
        raise gate.PhoneExecutionError("source-neutral OpenCL probe failed")
    raw_contract = gate.contract.read_regular(args.probe_contract_output)
    decoded_contract = gate.contract.strict_json_decode(
        raw_contract, source=str(args.probe_contract_output)
    )
    normalized_contract = gate.contract.normalize_opencl_contract(decoded_contract)
    if normalized_contract["custody_challenge"] != args.custody_challenge:
        raise gate.PhoneExecutionError("native probe custody challenge drifted")
    platform_after = validate_platform_identity(args.build_dir)
    if platform_after != platform_before:
        raise gate.PhoneExecutionError("platform identity changed during preflight")
    revision_after, closure_after = gate.contract.source_closure(ROOT)
    if revision_after != revision_before or closure_after != closure_before or git_status():
        raise gate.PhoneExecutionError("source checkout changed during preflight")
    report = {
        "schema_version": "gemma4_e4b_adreno_source_neutral_preflight_v1",
        "state": "passed_scope",
        "candidate_output_observed": False,
        "candidate_output_observation_scope": "this_custody_run_only",
        "model_or_tensor_path_supplied": False,
        "model_or_tensor_access_count_measured": False,
        "model_or_tensor_access_observation": "not_observed_no_paths_supplied",
        "model_or_tensor_access_observation_basis": (
            "exclusive_probe_argv_and_source_bound_control_flow_no_syscall_trace"
        ),
        "source_revision": revision_before,
        "custody_challenge": args.custody_challenge,
        "source_closure": closure_before,
        "source_closure_sha256": source_closure_sha256,
        "source_checkout_clean_before_and_after": True,
        "build": {
            "first": first_build,
            "second": second_build,
            "byte_identical_rebuild": True,
        },
        "probe": {
            "return_code": process.returncode,
            "elapsed_ns": elapsed,
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
            "launched_binary_bytes": first_build["binary_bytes"],
            "launched_binary_sha256": first_build["binary_sha256"],
            "process_receipt": {
                "pid": process.pid,
                "pidfd_opened": True,
                "pidfd_inode": pidfd_metadata.st_ino,
                "pidfd_poll_ready": True,
                "timeout_seconds": 600,
                "waitid_pid": wait_observation.si_pid,
                "waitid_code": wait_observation.si_code,
                "waitid_status": wait_observation.si_status,
                "popen_return_code": process.returncode,
            },
            "contract_bytes": len(raw_contract),
            "contract_sha256": hashlib.sha256(raw_contract).hexdigest(),
            "contract_canonical_sha256": gate.contract.sha256_bytes(
                gate.contract.canonical_json(normalized_contract)
            ),
            "runtime_isolation": normalized_contract["runtime_isolation"],
            "runtime_mapping_identity": normalized_contract[
                "runtime_mapping_identity"
            ],
            "binary_snapshot_unlinked_before_launch": True,
            "launcher": gate.contract.ANDROID_LINKER64_PATH,
            "child_environment_keys": sorted(environment),
            "loader_injection_environment_absent": True,
        },
        "platform_identity": platform_before,
        "custody": {
            "source_neutral_build_directory": True,
            "fresh_host_challenge_bound": True,
            "authorized_adb_forwarded_ssh_custody_receipt_required_for_admission": True,
            "model_tensor_input_reference_or_candidate_payload_path_supplied": False,
            "sanitized_hash_bound_metadata_egress_allowed": True,
        },
        "nonclaims": [
            "no_candidate_logits_observed",
            "no_authority_metric_result",
            "no_model_or_tensor_execution",
            "no_performance_claim",
            "no_kernel_level_filesystem_access_trace",
            "no_hardware_attestation",
            "no_resistance_to_malicious_same_uid_or_fully_compromised_phone",
        ],
    }
    publish_success_transaction(
        report_path=args.report, report=report, build_dir=args.build_dir
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--probe-contract-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--custody-challenge", required=True)
    args = parser.parse_args()
    try:
        return run(args)
    except Exception as error:
        publish_blocker(args, error)
        raise


if __name__ == "__main__":
    raise SystemExit(main())

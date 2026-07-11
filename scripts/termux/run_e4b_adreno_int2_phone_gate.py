#!/usr/bin/env python3
"""Build, execute, and adjudicate the frozen Adreno packed-INT2 LM head on-phone."""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import select
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any

sys.dont_write_bytecode = True
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


def open_pidfd(process_id: int) -> int:
    library = ctypes.CDLL(None, use_errno=True)
    function = getattr(library, "pidfd_open", None)
    if function is None:
        raise PhoneExecutionError("pidfd_open is unavailable")
    function.argtypes = [ctypes.c_int, ctypes.c_uint]
    function.restype = ctypes.c_int
    descriptor = function(process_id, 0)
    if descriptor < 0:
        error = ctypes.get_errno()
        raise OSError(error or errno.ENOSYS, os.strerror(error or errno.ENOSYS))
    return descriptor


def minimal_phone_environment(*, temporary_directory: Path) -> dict[str, str]:
    return {
        "HOME": "/data/data/com.termux/files/home",
        "PATH": "/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin",
        "TMPDIR": str(temporary_directory),
        "LANG": "C",
        "LC_ALL": "C",
        "TZ": "UTC",
    }


def _sha256_descriptor(descriptor: int) -> str:
    digest = hashlib.sha256()
    offset = 0
    while chunk := os.pread(descriptor, 1024 * 1024, offset):
        digest.update(chunk)
        offset += len(chunk)
    return digest.hexdigest()


def _read_descriptor(descriptor: int) -> bytes:
    chunks = []
    offset = 0
    while chunk := os.pread(descriptor, 1024 * 1024, offset):
        chunks.append(chunk)
        offset += len(chunk)
    return b"".join(chunks)


def _validate_termux_exec_metadata(metadata: os.stat_result) -> None:
    expected = {
        "regular": True,
        "links": 1,
        "bytes": contract.TERMUX_EXEC_INTERPOSER_BYTES,
        "mode": contract.TERMUX_EXEC_INTERPOSER_MODE,
        "uid": contract.TERMUX_EXEC_INTERPOSER_UID,
        "gid": contract.TERMUX_EXEC_INTERPOSER_GID,
    }
    observed = {
        "regular": stat.S_ISREG(metadata.st_mode),
        "links": metadata.st_nlink,
        "bytes": metadata.st_size,
        "mode": stat.S_IMODE(metadata.st_mode),
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
    }
    if observed != expected:
        raise PhoneExecutionError("Termux exec interposer metadata drifted")


def open_verified_termux_exec_source() -> int:
    path = Path(contract.TERMUX_EXEC_INTERPOSER_PATH)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        descriptor_metadata = os.fstat(descriptor)
        path_metadata = path.lstat()
        _validate_termux_exec_metadata(descriptor_metadata)
        _validate_termux_exec_metadata(path_metadata)
        if (descriptor_metadata.st_dev, descriptor_metadata.st_ino) != (
            path_metadata.st_dev,
            path_metadata.st_ino,
        ):
            raise PhoneExecutionError("Termux exec interposer path changed during open")
        if _sha256_descriptor(descriptor) != contract.TERMUX_EXEC_INTERPOSER_SHA256:
            raise PhoneExecutionError("Termux exec interposer digest drifted")
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def open_unlinked_snapshot(
    *,
    payload: bytes,
    expected_sha256: str,
    temporary_directory: Path,
    prefix: str,
) -> int:
    directory_metadata = temporary_directory.lstat()
    if (
        not temporary_directory.is_absolute()
        or not stat.S_ISDIR(directory_metadata.st_mode)
        or temporary_directory.is_symlink()
        or stat.S_IMODE(directory_metadata.st_mode) != 0o700
        or directory_metadata.st_uid != os.geteuid()
        or directory_metadata.st_gid != os.getegid()
    ):
        raise PhoneExecutionError("snapshot directory is unsafe")
    write_descriptor, name = tempfile.mkstemp(
        prefix=f".{prefix}-", dir=temporary_directory
    )
    path = Path(name)
    read_descriptor: int | None = None
    try:
        os.fchmod(write_descriptor, 0o400)
        view = memoryview(payload)
        while view:
            written = os.write(write_descriptor, view)
            if written <= 0:
                raise OSError("short snapshot write")
            view = view[written:]
        os.fsync(write_descriptor)
        os.close(write_descriptor)
        write_descriptor = -1
        read_descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        metadata = os.fstat(read_descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o400
            or metadata.st_uid != os.geteuid()
            or metadata.st_gid != os.getegid()
            or metadata.st_size != len(payload)
            or _sha256_descriptor(read_descriptor) != expected_sha256
        ):
            raise PhoneExecutionError("private snapshot identity drifted")
        path.unlink()
        contract._fsync_directory(temporary_directory)
        if os.fstat(read_descriptor).st_nlink != 0:
            raise PhoneExecutionError("private snapshot remained path-addressable")
        return read_descriptor
    except Exception:
        if read_descriptor is not None:
            os.close(read_descriptor)
        if write_descriptor >= 0:
            os.close(write_descriptor)
        if path.exists() and not path.is_symlink():
            path.unlink()
        raise


def open_termux_exec_snapshot(*, temporary_directory: Path) -> int:
    source_descriptor = open_verified_termux_exec_source()
    try:
        payload = _read_descriptor(source_descriptor)
    finally:
        os.close(source_descriptor)
    descriptor = open_unlinked_snapshot(
        payload=payload,
        expected_sha256=contract.TERMUX_EXEC_INTERPOSER_SHA256,
        temporary_directory=temporary_directory,
        prefix="e4b-termux-exec",
    )
    validate_termux_exec_snapshot(descriptor)
    return descriptor


def validate_termux_exec_snapshot(descriptor: int) -> None:
    metadata = os.fstat(descriptor)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 0
        or metadata.st_size != contract.TERMUX_EXEC_INTERPOSER_BYTES
        or stat.S_IMODE(metadata.st_mode) != 0o400
        or metadata.st_uid != os.geteuid()
        or metadata.st_gid != os.getegid()
        or _sha256_descriptor(descriptor) != contract.TERMUX_EXEC_INTERPOSER_SHA256
    ):
        raise PhoneExecutionError("unlinked Termux exec snapshot drifted")


def compiler_phone_environment(
    *, temporary_directory: Path, interposer_descriptor: int
) -> dict[str, str]:
    validate_termux_exec_snapshot(interposer_descriptor)
    preload = f"/proc/self/fd/{interposer_descriptor}"
    if not preload.removeprefix("/proc/self/fd/").isdigit():
        raise PhoneExecutionError("invalid retained interposer descriptor path")
    environment = minimal_phone_environment(temporary_directory=temporary_directory)
    environment["LD_PRELOAD"] = preload
    return environment


def validate_termux_exec_mapping_payload(
    payload: str, *, metadata: os.stat_result
) -> None:
    expected_path = contract.TERMUX_EXEC_INTERPOSER_PATH
    expected_device = f"{os.major(metadata.st_dev):x}:{os.minor(metadata.st_dev):x}"
    records = []
    for line in payload.splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) == 6 and "libtermux-exec.so" in fields[5]:
            records.append(fields)
    if not records or any(
        record[3] != expected_device
        or int(record[4]) != metadata.st_ino
        or record[5] != expected_path
        for record in records
    ):
        raise PhoneExecutionError("phone runner interposer mapping is not exact")


def validate_parent_termux_exec_binding() -> None:
    expected_path = contract.TERMUX_EXEC_INTERPOSER_PATH
    expected_environment = {
        "HOME": "/data/data/com.termux/files/home",
        "PATH": "/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin",
        "TMPDIR": "/data/data/com.termux/files/usr/tmp",
        "LANG": "C",
        "LC_ALL": "C",
        "TZ": "UTC",
        "LD_PRELOAD": expected_path,
        "TERMUX_EXEC__PROC_SELF_EXE": contract.TERMUX_PYTHON_PATH,
    }
    if dict(os.environ) != expected_environment:
        raise PhoneExecutionError("phone runner parent environment is not exact")
    required_flags = {
        "isolated": 1,
        "no_site": 1,
        "dont_write_bytecode": 1,
        "ignore_environment": 1,
        "safe_path": True,
        "no_user_site": 1,
    }
    if any(getattr(sys.flags, name) != value for name, value in required_flags.items()):
        raise PhoneExecutionError("phone runner Python isolation flags drifted")
    python = Path(contract.TERMUX_PYTHON_PATH)
    if (
        not python.is_symlink()
        or os.readlink(python) != contract.TERMUX_PYTHON_LINK_TARGET
        or python.resolve(strict=True) != Path(contract.TERMUX_PYTHON_RESOLVED_PATH)
        or ".".join(str(value) for value in sys.version_info[:3])
        != contract.TERMUX_PYTHON_VERSION
    ):
        raise PhoneExecutionError("phone runner Python identity drifted")
    contract.validate_regular(
        Path(contract.TERMUX_PYTHON_RESOLVED_PATH),
        expected_bytes=contract.TERMUX_PYTHON_RESOLVED_BYTES,
        expected_sha256=contract.TERMUX_PYTHON_RESOLVED_SHA256,
    )
    for record in contract.TERMUX_PYTHON_RUNTIME_FILES:
        validate_bound_file_record(record, label="Python runtime")
    observed_stdlib = contract.directory_tree_identity(
        Path(contract.TERMUX_PYTHON_STDLIB_DIR)
    )
    if observed_stdlib != contract.TERMUX_PYTHON_STDLIB_TREE_IDENTITY:
        raise PhoneExecutionError("Termux Python stdlib tree identity drifted")
    descriptor = open_verified_termux_exec_source()
    try:
        metadata = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    validate_termux_exec_mapping_payload(
        Path("/proc/self/maps").read_text(encoding="utf-8"), metadata=metadata
    )


def validate_bound_file_record(record: dict[str, Any], *, label: str) -> None:
    entry = Path(record["entry_absolute_path"])
    resolved = Path(record["resolved_absolute_path"])
    symlink_target = record["symlink_target"]
    if symlink_target is None:
        if entry.is_symlink() or entry != resolved:
            raise PhoneExecutionError(f"{label} topology drifted")
    elif (
        not entry.is_symlink()
        or os.readlink(entry) != symlink_target
        or entry.resolve(strict=True) != resolved
    ):
        raise PhoneExecutionError(f"{label} symlink topology drifted")
    contract.validate_regular(
        resolved,
        expected_bytes=int(record["bytes"]),
        expected_sha256=str(record["sha256"]),
    )


def validate_termux_toolchain_files() -> None:
    compiler = Path(contract.TERMUX_CLANGXX_PATH)
    if (
        not compiler.is_symlink()
        or os.readlink(compiler) != contract.TERMUX_CLANGXX_LINK_TARGET
        or compiler.resolve(strict=True) != Path(contract.TERMUX_CLANGXX_RESOLVED_PATH)
    ):
        raise PhoneExecutionError("Termux clang++ link topology drifted")
    contract.validate_regular(
        Path(contract.TERMUX_CLANGXX_RESOLVED_PATH),
        expected_bytes=contract.TERMUX_CLANGXX_RESOLVED_BYTES,
        expected_sha256=contract.TERMUX_CLANGXX_RESOLVED_SHA256,
    )
    linker = Path(contract.TERMUX_LLD_PATH)
    if (
        not linker.is_symlink()
        or os.readlink(linker) != contract.TERMUX_LLD_LINK_TARGET
        or linker.resolve(strict=True) != Path(contract.TERMUX_LLD_RESOLVED_PATH)
    ):
        raise PhoneExecutionError("Termux LLD link topology drifted")
    contract.validate_regular(
        Path(contract.TERMUX_LLD_RESOLVED_PATH),
        expected_bytes=contract.TERMUX_LLD_RESOLVED_BYTES,
        expected_sha256=contract.TERMUX_LLD_RESOLVED_SHA256,
    )
    contract.validate_regular(
        Path(contract.TERMUX_LIBCXX_PATH),
        expected_bytes=contract.TERMUX_LIBCXX_BYTES,
        expected_sha256=contract.TERMUX_LIBCXX_SHA256,
    )
    for record in contract.TERMUX_COMPILER_RUNTIME_FILES:
        validate_bound_file_record(record, label="compiler runtime")
    observed_trees = {
        "resource": contract.directory_tree_identity(
            Path(contract.TERMUX_CLANG_RESOURCE_DIR)
        ),
        "include": contract.directory_tree_identity(Path(contract.TERMUX_INCLUDE_DIR)),
    }
    expected_trees = {
        "resource": contract.TERMUX_CLANG_RESOURCE_TREE_IDENTITY,
        "include": contract.TERMUX_INCLUDE_TREE_IDENTITY,
    }
    if observed_trees != expected_trees:
        raise PhoneExecutionError("Termux compiler tree identity drifted")
    for record in contract.TERMUX_LINK_INPUT_FILES:
        validate_bound_file_record(record, label="native link input")
    for record in contract.PHONE_SYSTEM_RUNTIME_FILES:
        validate_bound_file_record(record, label="phone system runtime")


def validate_android_linker64() -> None:
    linker = Path(contract.ANDROID_LINKER64_PATH)
    if (
        not linker.is_symlink()
        or os.readlink(linker) != contract.ANDROID_LINKER64_LINK_TARGET
        or linker.resolve(strict=True) != Path(contract.ANDROID_LINKER64_RESOLVED_PATH)
    ):
        raise PhoneExecutionError("Android linker64 topology drifted")
    contract.validate_regular(
        Path(contract.ANDROID_LINKER64_RESOLVED_PATH),
        expected_bytes=contract.ANDROID_LINKER64_RESOLVED_BYTES,
        expected_sha256=contract.ANDROID_LINKER64_RESOLVED_SHA256,
    )


def create_private_directory(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise PhoneExecutionError(f"refusing to reuse private directory: {path}")
    path.mkdir(mode=0o700, parents=False)
    os.chmod(path, 0o700)
    metadata = path.lstat()
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_nlink < 2
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or metadata.st_uid != os.geteuid()
        or metadata.st_gid != os.getegid()
    ):
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


def validate_phone_runtime_identity(
    preregistration: dict[str, Any], *, temporary_directory: Path
) -> dict[str, Any]:
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
        env=minimal_phone_environment(temporary_directory=temporary_directory),
    ).stdout
    if not fingerprint.endswith(b"\n") or fingerprint.count(b"\n") != 1:
        raise PhoneExecutionError("Android build fingerprint stdout shape drifted")
    if hashlib.sha256(fingerprint).hexdigest() != (
        contract.ANDROID_BUILD_FINGERPRINT_STDOUT_SHA256
    ):
        raise PhoneExecutionError("Android build fingerprint drifted")
    validate_termux_toolchain_files()
    validate_android_linker64()
    interposer_descriptor = open_termux_exec_snapshot(
        temporary_directory=temporary_directory
    )
    try:
        compiler_environment = compiler_phone_environment(
            temporary_directory=temporary_directory,
            interposer_descriptor=interposer_descriptor,
        )
        version = subprocess.run(
            [contract.TERMUX_CLANGXX_RESOLVED_PATH, "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=compiler_environment,
            pass_fds=(interposer_descriptor,),
            timeout=60,
        ).stdout
        linker_version = subprocess.run(
            [contract.TERMUX_LLD_PATH, "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=compiler_environment,
            pass_fds=(interposer_descriptor,),
            timeout=60,
        ).stdout
        validate_termux_exec_snapshot(interposer_descriptor)
    finally:
        os.close(interposer_descriptor)
    if hashlib.sha256(version).hexdigest() != (
        contract.TERMUX_CLANGXX_VERSION_STDOUT_SHA256
    ):
        raise PhoneExecutionError("Termux clang++ version drifted")
    if hashlib.sha256(linker_version).hexdigest() != (
        contract.TERMUX_LLD_VERSION_STDOUT_SHA256
    ):
        raise PhoneExecutionError("Termux LLD version drifted")
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
        "linker_resolved_bytes": contract.TERMUX_LLD_RESOLVED_BYTES,
        "linker_resolved_sha256": contract.TERMUX_LLD_RESOLVED_SHA256,
        "linker_version_stdout_sha256": contract.TERMUX_LLD_VERSION_STDOUT_SHA256,
        "cxx_runtime_bytes": contract.TERMUX_LIBCXX_BYTES,
        "cxx_runtime_sha256": contract.TERMUX_LIBCXX_SHA256,
        "termux_exec_interposer": {
            "source_bytes": contract.TERMUX_EXEC_INTERPOSER_BYTES,
            "source_sha256": contract.TERMUX_EXEC_INTERPOSER_SHA256,
            "source_mode_octal": "0700",
            "source_uid": contract.TERMUX_EXEC_INTERPOSER_UID,
            "source_gid": contract.TERMUX_EXEC_INTERPOSER_GID,
            "parent_mapping_exact": True,
        },
        "candidate_launcher": {
            "resolved_bytes": contract.ANDROID_LINKER64_RESOLVED_BYTES,
            "resolved_sha256": contract.ANDROID_LINKER64_RESOLVED_SHA256,
            "runtime_ld_preload_present": False,
        },
    }


def stage_native_source_snapshot(
    log_dir: Path, source_closure: list[dict[str, Any]]
) -> tuple[Path, list[dict[str, Any]]]:
    expected_records = {
        record.get("relative_path"): record
        for record in source_closure
        if isinstance(record, dict)
    }
    snapshot_dir = log_dir / "source_snapshot"
    create_private_directory(snapshot_dir)
    records = []
    for relative in contract.NATIVE_BUILD_SOURCE_FILES:
        expected = expected_records.get(relative)
        if not isinstance(expected, dict) or expected.get("git_mode") != "100644":
            raise PhoneExecutionError("native source closure record is absent")
        payload = read_frozen_payload(
            ROOT / relative,
            expected_bytes=int(expected["bytes"]),
            expected_sha256=str(expected["sha256"]),
            label=f"native source {relative}",
        )
        destination = snapshot_dir / Path(relative).name
        contract.write_exclusive(destination, payload, mode=0o400)
        records.append(
            {
                "relative_path": relative,
                "snapshot_name": destination.name,
                "bytes": len(payload),
                "sha256": contract.sha256_bytes(payload),
            }
        )
    validate_native_source_snapshot(snapshot_dir, records)
    return snapshot_dir, records


def validate_native_source_snapshot(
    snapshot_dir: Path, records: list[dict[str, Any]]
) -> None:
    expected_names = {record["snapshot_name"] for record in records}
    if {path.name for path in snapshot_dir.iterdir()} != expected_names:
        raise PhoneExecutionError("native source snapshot inventory drifted")
    for record in records:
        path = snapshot_dir / record["snapshot_name"]
        contract.validate_regular(
            path,
            expected_bytes=int(record["bytes"]),
            expected_sha256=str(record["sha256"]),
        )
        if stat.S_IMODE(path.lstat().st_mode) != 0o400:
            raise PhoneExecutionError("native source snapshot mode drifted")


def build_phone_binary(
    binary_path: Path, log_dir: Path, *, source_closure: list[dict[str, Any]]
) -> dict[str, Any]:
    source_closure_sha256 = contract.sha256_bytes(
        contract.canonical_json(source_closure)
    )
    if not contract.is_sha256(source_closure_sha256):
        raise PhoneExecutionError("native build source closure digest is invalid")
    if (
        not binary_path.is_absolute()
        or not log_dir.is_absolute()
        or binary_path.parent != log_dir
        or binary_path.exists()
        or binary_path.is_symlink()
    ):
        raise PhoneExecutionError("native binary destination is unsafe")
    interposer_descriptor = open_termux_exec_snapshot(temporary_directory=log_dir)
    staging_path: Path | None = None
    published = False
    try:
        source_directory, source_snapshot = stage_native_source_snapshot(
            log_dir, source_closure
        )
        source_snapshot_sha256 = contract.sha256_bytes(
            contract.canonical_json(source_snapshot)
        )
        validate_termux_toolchain_files()
        staging_descriptor, staging_name = tempfile.mkstemp(
            prefix=".e4b_adreno_int2.build-", dir=log_dir
        )
        staging_path = Path(staging_name)
        try:
            os.fchmod(staging_descriptor, 0o600)
        finally:
            os.close(staging_descriptor)
        environment = compiler_phone_environment(
            temporary_directory=log_dir,
            interposer_descriptor=interposer_descriptor,
        )
        toolchain = subprocess.run(
            [contract.TERMUX_CLANGXX_RESOLVED_PATH, "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=environment,
            pass_fds=(interposer_descriptor,),
            timeout=60,
        ).stdout
        linker_version = subprocess.run(
            [contract.TERMUX_LLD_PATH, "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=environment,
            pass_fds=(interposer_descriptor,),
            timeout=60,
        ).stdout
        if hashlib.sha256(toolchain).hexdigest() != (
            contract.TERMUX_CLANGXX_VERSION_STDOUT_SHA256
        ):
            raise PhoneExecutionError("Termux clang++ version drifted before build")
        if hashlib.sha256(linker_version).hexdigest() != (
            contract.TERMUX_LLD_VERSION_STDOUT_SHA256
        ):
            raise PhoneExecutionError("Termux LLD version drifted before build")
        build_command = [
            contract.TERMUX_CLANGXX_RESOLVED_PATH,
            *contract.NATIVE_BUILD_ARGUMENTS,
            f'-DPOLYMATH_SOURCE_CLOSURE_SHA256="{source_closure_sha256}"',
            str(source_directory / "opencl_dynamic_runtime.cpp"),
            str(source_directory / "e4b_adreno_int2_lm_head.cpp"),
            "-ldl",
            "-o",
            str(staging_path),
        ]
        started = time.monotonic_ns()
        try:
            process = subprocess.run(
                build_command,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                pass_fds=(interposer_descriptor,),
                cwd=ROOT,
                timeout=600,
            )
        except subprocess.TimeoutExpired as error:
            contract.write_exclusive(
                log_dir / "build.stdout.log", error.stdout or b""
            )
            contract.write_exclusive(
                log_dir / "build.stderr.log", error.stderr or b""
            )
            raise PhoneExecutionError("native build timed out") from error
        elapsed = time.monotonic_ns() - started
        contract.write_exclusive(log_dir / "build.stdout.log", process.stdout)
        contract.write_exclusive(log_dir / "build.stderr.log", process.stderr)
        if process.returncode != 0:
            raise PhoneExecutionError("native build failed")
        validate_termux_exec_snapshot(interposer_descriptor)
        validate_native_source_snapshot(source_directory, source_snapshot)
        for record in source_snapshot:
            read_frozen_payload(
                ROOT / record["relative_path"],
                expected_bytes=int(record["bytes"]),
                expected_sha256=str(record["sha256"]),
                label=f"native source {record['relative_path']}",
            )
        source_recheck = open_verified_termux_exec_source()
        os.close(source_recheck)
        validate_termux_toolchain_files()
        metadata = staging_path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise PhoneExecutionError("native staging binary is unsafe")
        publication_descriptor = os.open(
            staging_path,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            retained_metadata = os.fstat(publication_descriptor)
            if (retained_metadata.st_dev, retained_metadata.st_ino) != (
                metadata.st_dev,
                metadata.st_ino,
            ):
                raise PhoneExecutionError("native staging binary changed before retain")
            os.fchmod(publication_descriptor, 0o700)
            retained_metadata = os.fstat(publication_descriptor)
            if stat.S_IMODE(retained_metadata.st_mode) != 0o700:
                raise PhoneExecutionError("native staging binary mode publication failed")
            binary_sha256 = _sha256_descriptor(publication_descriptor)
            os.fsync(publication_descriptor)
            contract._rename_noreplace(staging_path, binary_path)
            published = True
            contract._fsync_directory(log_dir)
            destination_metadata = binary_path.lstat()
            if (destination_metadata.st_dev, destination_metadata.st_ino) != (
                retained_metadata.st_dev,
                retained_metadata.st_ino,
            ):
                raise PhoneExecutionError("native binary publication changed inode")
            validate_regular_descriptor = _sha256_descriptor(publication_descriptor)
            if validate_regular_descriptor != binary_sha256:
                raise PhoneExecutionError("published native binary changed after retain")
        finally:
            os.close(publication_descriptor)
        contract.validate_regular(
            binary_path,
            expected_bytes=retained_metadata.st_size,
            expected_sha256=binary_sha256,
        )
        if not os.access(binary_path, os.X_OK):
            raise PhoneExecutionError("native binary publication lost execute mode")
        return {
            "binary_bytes": retained_metadata.st_size,
            "binary_sha256": binary_sha256,
            "toolchain_version_sha256": hashlib.sha256(toolchain).hexdigest(),
            "toolchain_resolved_sha256": contract.sha256_path(
                Path(contract.TERMUX_CLANGXX_RESOLVED_PATH)
            ),
            "linker_version_sha256": hashlib.sha256(linker_version).hexdigest(),
            "linker_resolved_sha256": contract.sha256_path(
                Path(contract.TERMUX_LLD_RESOLVED_PATH)
            ),
            "cxx_runtime_sha256": contract.sha256_path(
                Path(contract.TERMUX_LIBCXX_PATH)
            ),
            "compiler_arguments": list(contract.NATIVE_BUILD_ARGUMENTS),
            "source_closure_sha256": source_closure_sha256,
            "native_source_snapshot_sha256": source_snapshot_sha256,
            "termux_exec_interposer_sha256": (
                contract.TERMUX_EXEC_INTERPOSER_SHA256
            ),
            "termux_exec_transport": (
                "private_unlinked_exact_snapshot_read_only_fd_via_proc_self_fd"
            ),
            "binary_publication": "renameat2_RENAME_NOREPLACE_same_directory",
            "build_elapsed_ns": elapsed,
            "stdout_sha256": hashlib.sha256(process.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(process.stderr).hexdigest(),
        }
    finally:
        os.close(interposer_descriptor)
        if (
            not published
            and staging_path is not None
            and staging_path.exists()
            and not staging_path.is_symlink()
        ):
            staging_path.unlink()


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
    if not binary_path.is_absolute():
        raise PhoneExecutionError("native candidate path must be absolute")
    command = [
        contract.ANDROID_LINKER64_PATH,
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
    pass_fds: tuple[int, ...] = (),
) -> dict[str, Any]:
    temperatures = []
    started = time.monotonic_ns()
    maximum_ns = int(envelope["maximum_wall_time_seconds"]) * 1_000_000_000
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        progress["native_launch_state"] = "launch_attempted"
        process = subprocess.Popen(
            command,
            env=environment,
            stdout=stdout,
            stderr=stderr,
            pass_fds=pass_fds,
        )
        try:
            pidfd = open_pidfd(process.pid)
        except Exception:
            process.terminate()
            process.wait(timeout=10)
            raise
        pidfd_metadata = os.fstat(pidfd)
        poller = select.poll()
        poller.register(pidfd, select.POLLIN)
        progress["native_launch_state"] = "process_started"
        progress["candidate_execution_count"] = 1
        stopped = False
        wait_observation = None
        try:
            while not poller.poll(0):
                try:
                    temperatures.append(
                        enforce_thermal_guard(thermal_snapshot(), envelope)
                    )
                except PhoneExecutionError:
                    stopped = True
                    process.terminate()
                    break
                if time.monotonic_ns() - started > maximum_ns:
                    stopped = True
                    process.terminate()
                    break
                time.sleep(0.25)
            if stopped and not poller.poll(5_000):
                process.kill()
                if not poller.poll(5_000):
                    raise PhoneExecutionError("native process did not terminate")
            wait_observation = os.waitid(
                os.P_PIDFD, pidfd, os.WEXITED | os.WNOWAIT
            )
            return_code = process.wait()
        finally:
            os.close(pidfd)
            if process.returncode is None:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        if wait_observation is None:
            raise PhoneExecutionError("native pidfd completion observation is absent")
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
        "process_receipt": {
            "pid": process.pid,
            "pidfd_opened": True,
            "pidfd_inode": pidfd_metadata.st_ino,
            "pidfd_poll_ready": True,
            "waitid_pid": wait_observation.si_pid,
            "waitid_code": wait_observation.si_code,
            "waitid_status": wait_observation.si_status,
            "popen_return_code": return_code,
        },
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
    if summary.get("source_closure_sha256") != preregistration["source_binding"].get(
        "closure_sha256"
    ):
        raise PhoneExecutionError("native summary source closure witness drifted")
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
    validate_parent_termux_exec_binding()
    preregistration = load_bound_preregistration(
        args.preregistration, args.prereg_sha256
    )
    run_root = args.run_root
    metadata = run_root.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or run_root.is_symlink():
        raise PhoneExecutionError("run root must be a real directory")
    envelope = preregistration["phone_execution_envelope"]
    resource_before = validate_resource_floor(run_root, envelope)

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
    runtime_identity = validate_phone_runtime_identity(
        preregistration, temporary_directory=native_dir
    )

    binary_path = native_dir / "e4b_adreno_int2_lm_head"
    build = build_phone_binary(
        binary_path, native_dir, source_closure=preregistration["source_closure"]
    )
    binary_contract = preregistration["native_binary_contract"]
    if (
        build["binary_bytes"] != binary_contract["preflight_bytes"]
        or build["binary_sha256"] != binary_contract["preflight_sha256"]
    ):
        raise PhoneExecutionError("candidate binary drifted from source-neutral preflight")
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
    environment = minimal_phone_environment(temporary_directory=native_dir)
    environment.update(contract.runtime_environment(preregistration["opencl_contract"]))
    if {"LD_PRELOAD", "LD_LIBRARY_PATH"}.intersection(environment):
        raise PhoneExecutionError("candidate launcher environment contains loader injection")
    binary_payload = read_frozen_payload(
        binary_path,
        expected_bytes=binary_contract["preflight_bytes"],
        expected_sha256=binary_contract["preflight_sha256"],
        label="candidate native binary",
    )
    binary_descriptor = open_unlinked_snapshot(
        payload=binary_payload,
        expected_sha256=binary_contract["preflight_sha256"],
        temporary_directory=native_dir,
        prefix="e4b-candidate-binary",
    )
    try:
        command = native_command(
            binary_path=Path(f"/proc/self/fd/{binary_descriptor}"),
            packed_weight_path=staged_packed_path,
            scale_path=scale_path,
            native_summary_path=native_summary_path,
            all_cases=all_cases,
        )
        execution = run_monitored(
            command=command,
            environment=environment,
            stdout_path=native_dir / "native.stdout.log",
            stderr_path=native_dir / "native.stderr.log",
            envelope=envelope,
            progress=progress,
            pass_fds=(binary_descriptor,),
        )
        if (
            os.fstat(binary_descriptor).st_nlink != 0
            or _sha256_descriptor(binary_descriptor)
            != binary_contract["preflight_sha256"]
        ):
            raise PhoneExecutionError("retained candidate binary snapshot drifted")
    finally:
        os.close(binary_descriptor)
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
    interposer_recheck = open_verified_termux_exec_source()
    os.close(interposer_recheck)
    validate_termux_toolchain_files()
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

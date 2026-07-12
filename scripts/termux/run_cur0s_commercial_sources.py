#!/usr/bin/env python3
"""Acquire and attest the CUR-0S commercial source roster on the phone.

The runner is deliberately a custody boundary, not a corpus compiler.  It
downloads the preregistered public bytes and exact historical Git trees into
one phone-private candidate, verifies identity, rights evidence, structure,
and persistence, and emits only a hash-bound aggregate receipt.  It makes no
semantic, CUR-0S, learning, or authority claim.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import resource
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import types
from typing import Any, BinaryIO, Callable, Mapping, Sequence
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ElementTree
import zipfile


EXPECTED_BUILD_FINGERPRINT_SHA256 = (
    "sha256:fce358a6cdd6535afbecf6f72088412abaccf9b9902c05800ee8852512f9882f"
)
EXPECTED_ADB_SERIAL_SHA256 = (
    "sha256:383e1fef6040334134430241a105f7d900f6d924e485fdc858441e734d3ae0f4"
)
EXPECTED_OEM_THERMAL_PROPERTIES = {
    "ro.vendor.feature.zte_feature_ccc_bat_temp_cntrl": "true",
    "ro.vendor.feature.zte_feature_ccc_temp_threshold": "skin,54,battery,45",
}
EXPECTED_PARENT_CAPSULE_SHA256 = (
    "sha256:e6905f36fa526e15a0a1d8ac4eadbf670061a2837fea9a7ac51a1df6bb608f15"
)
EXPECTED_PARENT_FRONTIER_ROOT_SHA256 = (
    "sha256:d118000d8fd457962f2332f2597bb25f6c6e33ee61010f5cd1459ab9768235fc"
)
PREREG_SCHEMA = "cur0s_commercial_sources_preregistration_v1"
RECEIPT_SCHEMA = "cur0s_commercial_sources_receipt_v1"
COMPLETE_SCHEMA = "cur0s_commercial_sources_completion_v1"
EXECUTION_CLAIM_SCHEMA = "cur0s_commercial_sources_execution_claim_v1"
ABORT_SCHEMA = "cur0s_commercial_sources_abort_v1"
RUN_ID_RE = re.compile(r"[0-9]{8}T[0-9]{6}Z_cur0s_commercial_sources_v1\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
SHA256_RE = re.compile(r"(?:sha256:)?([0-9a-f]{64})\Z")
SAFE_COMPONENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
XML_FORBIDDEN_RE = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
EPUB_CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
OPF_NS = "http://www.idpf.org/2007/opf"
DC_NS = "http://purl.org/dc/elements/1.1/"
XHTML_NS = "http://www.w3.org/1999/xhtml"
EPUB_OPS_NS = "http://www.idpf.org/2007/ops"
PHONE_HOME = Path("/data/data/com.termux/files/home")
PHONE_PACKAGE_ROOT = Path("/data/data/com.termux")
PHONE_RUN_ROOT_RELATIVE = "polymath_gemma4_e4b_frontier"
PHONE_RUN_ROOT = PHONE_HOME / PHONE_RUN_ROOT_RELATIVE
CURL = "/data/data/com.termux/files/usr/bin/curl"
GIT = "/data/data/com.termux/files/usr/bin/git"
GETPROP = "/system/bin/getprop"
GIT_EXEC_PATH = "/data/data/com.termux/files/usr/libexec/git-core"
TERMUX_EXEC_INTERPOSER = "/data/data/com.termux/files/usr/lib/libtermux-exec.so"
BOUND_SOURCE_FILES = (
    "polymath_ai/corpus/cur0s_commercial_sources.py",
    "scripts/termux/run_cur0s_commercial_sources.py",
)
THERMAL_UNAVAILABLE_SENTINELS_MILLIDEGREES_C = frozenset({-273_000, -40_960})
THERMAL_SAMPLE_SCHEMA = "cur0s_phone_thermal_sample_v1"
CONTROL_RESERVE_BYTES = 2 * 1024 * 1024
TERMINALIZATION_RESERVE_SECONDS = 30
PROCESS_POLL_SECONDS = 0.25
MAX_PROCESS_LOG_BYTES = 128 * 1024
MAX_HEADER_BYTES = 128 * 1024
MAX_ARCHIVE_ENTRIES = 100_000
DIRECT_TRANSFER_MAX_ATTEMPTS = 4
MAX_DIRECT_RANGE_CHUNK_BYTES = 16 * 1024 * 1024
DIRECT_RANGE_COPY_BUFFER_BYTES = 1024 * 1024
HTTP_RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
RUNNER_EXECUTION_FD = 3
RUNNER_EXECUTION_PATH = f"/proc/self/fd/{RUNNER_EXECUTION_FD}"
NATIVE_PREFLIGHT_ATTESTATION_FD = 4
NATIVE_PREFLIGHT_MANIFEST_FD = 5
NATIVE_PREFLIGHT_PREREGISTRATION_FD = 6
NATIVE_PREFLIGHT_PYTHON_EXEC_CLOEXEC_FD = 7
EXPECTED_NATIVE_PREFLIGHT_FIXED_FD_MAP = {
    "manifest": NATIVE_PREFLIGHT_MANIFEST_FD,
    "native_attestation": NATIVE_PREFLIGHT_ATTESTATION_FD,
    "preregistration": NATIVE_PREFLIGHT_PREREGISTRATION_FD,
    "python_exec_cloexec": NATIVE_PREFLIGHT_PYTHON_EXEC_CLOEXEC_FD,
    "runner": RUNNER_EXECUTION_FD,
}
EXPECTED_NATIVE_OUTER_ENVIRONMENT: dict[str, str] = {}
EXPECTED_NATIVE_OUTER_ENVIRONMENT_SHA256 = (
    "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
)
EXPECTED_SYSTEM_LAUNCHER_ENV_IDENTITY_SHA256 = (
    "sha256:fa05d874c2f7c8954c0f842ad8d6372982c70480a05f3bcf4effa47ed0dcf697"
)
NATIVE_OUTER_LAUNCH_CONTRACT_SCHEMA = "cur0s_native_outer_launch_contract_v1"
EXPECTED_PYTHON_PREFIX = "/data/data/com.termux/files/usr"
EXPECTED_PYTHON_INITIAL_SYS_PATH = (
    f"{EXPECTED_PYTHON_PREFIX}/lib/python313.zip",
    f"{EXPECTED_PYTHON_PREFIX}/lib/python3.13",
    f"{EXPECTED_PYTHON_PREFIX}/lib/python3.13/lib-dynload",
)
EXPECTED_PYTHON_SANITIZED_SYS_PATH = EXPECTED_PYTHON_INITIAL_SYS_PATH[1:]
RUN_SCOPED_PYCACHE_DIRECTORY_NAME = "python_pycache_forbidden"
EXPECTED_PYTHON_LAUNCH_ENVIRONMENT = {
    "ANDROID_ROOT": "/system",
    "CUR0S_NATIVE_ATTESTATION_FD": "4",
    "CUR0S_NATIVE_MANIFEST_FD": "5",
    "CUR0S_PREREGISTRATION_FD": "6",
    "HOME": str(PHONE_HOME),
    "LC_ALL": "C",
    "LD_PRELOAD": f"{EXPECTED_PYTHON_PREFIX}/lib/libtermux-exec.so",
    "PATH": f"{EXPECTED_PYTHON_PREFIX}/bin:/system/bin",
    "TERMUX_EXEC__PROC_SELF_EXE": f"{EXPECTED_PYTHON_PREFIX}/bin/python",
}


def derive_checkout_root() -> Path:
    """Derive the checkout from the inherited runner FD used by CPython."""

    if __name__ != "__main__":
        return Path(os.path.abspath(__file__)).parents[2]
    if __file__ != RUNNER_EXECUTION_PATH:
        raise RuntimeError("runner_must_execute_through_inherited_fd_3")
    try:
        target = os.readlink(RUNNER_EXECUTION_PATH)
    except OSError as error:
        raise RuntimeError("runner_execution_fd_unavailable") from error
    if not target.startswith("/") or target.endswith(" (deleted)"):
        raise RuntimeError("runner_execution_fd_target_invalid")
    runner_path = Path(target)
    if runner_path.name != "run_cur0s_commercial_sources.py":
        raise RuntimeError("runner_execution_fd_target_name_invalid")
    return runner_path.parents[2]


ROOT = derive_checkout_root()
FD_PATH_ROOT = (
    Path("/proc/self/fd") if Path("/proc/self/fd").is_dir() else Path("/dev/fd")
)


class BootstrapError(RuntimeError):
    """The stdlib-only pre-import authority boundary rejected execution."""


class AcquisitionError(RuntimeError):
    """A source identity, rights, structure, or custody gate failed closed."""


class ClaimPublicationError(AcquisitionError):
    """The one-shot claim did not reach a safely usable committed state."""


# Repository objects are assigned only after their exact source bytes and the
# preregistration have been attested.  Keeping these placeholders explicit is
# part of the executable pre-import boundary.
CommercialSourceError: Any = AcquisitionError
DirectSourceSpec: Any = None
GitSourceSpec: Any = None
DIRECT_SOURCES: Any = ()
GIT_SOURCES: Any = ()
build_source_root: Any = None
canonical_json_bytes: Any = None
canonical_sha256: Any = None
phone_thermal_safety_contract: Any = None
phone_toolchain_contract: Any = None
build_native_preflight_execution_contract: Any = None
build_native_preflight_manifest_bytes: Any = None
NATIVE_PREFLIGHT_SOURCE_FILES: Any = ()
source_contract: Any = None
validate_source_contract: Any = None


_ATTESTED_TOOLCHAIN_VOLATILE_IDENTITIES: dict[str, tuple[int, ...]] = {}
_ATTESTED_TOOLCHAIN_CONTRACT: dict[str, Any] | None = None
_ATTESTED_STDLIB_VOLATILE_IDENTITY: tuple[int, ...] | None = None
_ATTESTED_CURRENT_PROCESS_IDENTITY: dict[str, Any] | None = None
_EXECUTED_RUNNER_IDENTITY: dict[str, Any] | None = None
_NATIVE_PREFLIGHT_EXEC_ATTESTATION: dict[str, Any] | None = None
_NATIVE_PREFLIGHT_MANIFEST_BYTES: bytes | None = None
_NATIVE_PREFLIGHT_PREREGISTRATION_BYTES: bytes | None = None
_NATIVE_PREFLIGHT_MANIFEST_IDENTITY: tuple[int, ...] | None = None
_NATIVE_PREFLIGHT_PREREGISTRATION_IDENTITY: tuple[int, ...] | None = None


def bootstrap_read_inherited_fd(
    fd: int,
    *,
    role: str,
    max_bytes: int,
    expected_mode: int,
    expected_nlink: int,
) -> tuple[bytes, tuple[int, ...]]:
    """Read one exact native-held descriptor without pathname reopening."""

    try:
        descriptor_flags = fcntl.fcntl(fd, fcntl.F_GETFD)
        initial = os.fstat(fd)
        initial_offset = os.lseek(fd, 0, os.SEEK_CUR)
    except OSError as error:
        raise BootstrapError(f"native_{role}_fd_unavailable") from error
    if (
        descriptor_flags & fcntl.FD_CLOEXEC
        or not stat.S_ISREG(initial.st_mode)
        or stat.S_IMODE(initial.st_mode) != expected_mode
        or initial.st_nlink != expected_nlink
        or initial.st_uid != os.geteuid()
        or initial.st_gid != os.getegid()
        or initial.st_size <= 0
        or initial.st_size > max_bytes
        or initial_offset != 0
    ):
        raise BootstrapError(f"native_{role}_fd_metadata_invalid")
    payload = bytearray()
    while True:
        try:
            chunk = os.read(fd, min(1024 * 1024, max_bytes + 1 - len(payload)))
        except OSError as error:
            raise BootstrapError(f"native_{role}_fd_read_failed") from error
        if not chunk:
            break
        payload.extend(chunk)
        if len(payload) > max_bytes:
            raise BootstrapError(f"native_{role}_fd_oversize")
    try:
        final = os.fstat(fd)
    except OSError as error:
        raise BootstrapError(f"native_{role}_fd_final_stat_failed") from error
    if (
        stat_identity(initial) != stat_identity(final)
        or stat.S_IMODE(final.st_mode) != expected_mode
        or final.st_nlink != expected_nlink
        or final.st_uid != os.geteuid()
        or final.st_gid != os.getegid()
        or len(payload) != initial.st_size
    ):
        raise BootstrapError(f"native_{role}_fd_changed")
    return bytes(payload), stat_identity(final)


def observe_python_startup_identity() -> dict[str, Any]:
    """Return the Python startup state that must be fixed before any claim."""

    return {
        "sys_executable": sys.executable,
        "base_executable": getattr(sys, "_base_executable", None),
        "real_executable": os.path.realpath(sys.executable),
        "prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
        "exec_prefix": sys.exec_prefix,
        "base_exec_prefix": sys.base_exec_prefix,
        "initial_sys_path": list(sys.path),
        "sys_flags": {
            "isolated": sys.flags.isolated,
            "no_site": sys.flags.no_site,
            "no_user_site": sys.flags.no_user_site,
            "ignore_environment": sys.flags.ignore_environment,
            "safe_path": sys.flags.safe_path,
            "dont_write_bytecode": sys.flags.dont_write_bytecode,
            "optimize": sys.flags.optimize,
        },
        "xoptions": dict(sys._xoptions),
        "pycache_prefix": sys.pycache_prefix,
        "orig_argv": list(sys.orig_argv),
        "environment": dict(os.environ),
    }


def runner_pycache_prefix_from_orig_argv(orig_argv: Any) -> Path:
    if not isinstance(orig_argv, list) or len(orig_argv) != 11:
        raise BootstrapError("python_startup_orig_argv_shape_mismatch")
    tail = orig_argv[5:]
    if (
        tail[0] != "--preregistration"
        or tail[2] != "--expected-preregistration-sha256"
        or tail[4] != "--output-dir"
    ):
        raise BootstrapError("python_startup_orig_argv_shape_mismatch")
    preregistration_path = Path(tail[1])
    action_root = preregistration_path.parent
    if (
        not preregistration_path.is_absolute()
        or str(preregistration_path) != tail[1]
        or preregistration_path.name != "preregistration.json"
        or action_root.parent != PHONE_RUN_ROOT
        or RUN_ID_RE.fullmatch(action_root.name) is None
    ):
        raise BootstrapError("python_startup_action_root_mismatch")
    return action_root / RUN_SCOPED_PYCACHE_DIRECTORY_NAME


def require_exact_python_startup(observed: Mapping[str, Any]) -> None:
    expected_prefix = EXPECTED_PYTHON_PREFIX
    expected = {
        "sys_executable": f"{expected_prefix}/bin/python",
        "base_executable": f"{expected_prefix}/bin/python",
        "real_executable": f"{expected_prefix}/bin/python3.13",
        "prefix": expected_prefix,
        "base_prefix": expected_prefix,
        "exec_prefix": expected_prefix,
        "base_exec_prefix": expected_prefix,
        "initial_sys_path": list(EXPECTED_PYTHON_INITIAL_SYS_PATH),
        "sys_flags": {
            "isolated": 1,
            "no_site": 1,
            "no_user_site": 1,
            "ignore_environment": 1,
            "safe_path": True,
            "dont_write_bytecode": 1,
            "optimize": 0,
        },
        "environment": EXPECTED_PYTHON_LAUNCH_ENVIRONMENT,
    }
    for field, value in expected.items():
        if observed.get(field) != value:
            raise BootstrapError(f"python_startup_{field}_mismatch")
    orig_argv = observed.get("orig_argv")
    pycache_prefix = runner_pycache_prefix_from_orig_argv(orig_argv)
    expected_argv_prefix = [
        f"{expected_prefix}/bin/python",
        "-IBS",
        "-X",
        f"pycache_prefix={pycache_prefix}",
        RUNNER_EXECUTION_PATH,
    ]
    if not isinstance(orig_argv, list) or orig_argv[:5] != expected_argv_prefix:
        raise BootstrapError("python_startup_orig_argv_prefix_mismatch")
    if observed.get("xoptions") != {"pycache_prefix": str(pycache_prefix)}:
        raise BootstrapError("python_startup_xoptions_mismatch")
    if observed.get("pycache_prefix") != str(pycache_prefix):
        raise BootstrapError("python_startup_pycache_prefix_mismatch")
    if os.path.lexists(pycache_prefix):
        raise BootstrapError("python_startup_pycache_prefix_not_absent")


def attest_executed_runner_fd() -> dict[str, Any]:
    """Bind the bytes CPython executed to the checkout directory entry."""

    global _EXECUTED_RUNNER_IDENTITY
    try:
        initial = os.fstat(RUNNER_EXECUTION_FD)
        target_text = os.readlink(RUNNER_EXECUTION_PATH)
    except OSError as error:
        raise BootstrapError("runner_execution_fd_attestation_failed") from error
    expected_path = ROOT / BOUND_SOURCE_FILES[1]
    if target_text != str(expected_path) or target_text.endswith(" (deleted)"):
        raise BootstrapError("runner_execution_fd_path_mismatch")
    try:
        entry = os.stat(expected_path, follow_symlinks=False)
    except OSError as error:
        raise BootstrapError("runner_checkout_entry_stat_failed") from error
    if (
        not stat.S_ISREG(initial.st_mode)
        or initial.st_nlink != 1
        or initial.st_uid != os.geteuid()
        or initial.st_gid != os.getegid()
        or stat_identity(initial) != stat_identity(entry)
    ):
        raise BootstrapError("runner_execution_fd_inode_mismatch")
    digest, byte_count = hash_fd(RUNNER_EXECUTION_FD)
    final = os.fstat(RUNNER_EXECUTION_FD)
    if stat_identity(initial) != stat_identity(final):
        raise BootstrapError("runner_execution_fd_changed_during_hash")
    _EXECUTED_RUNNER_IDENTITY = {
        "path": str(expected_path),
        "sha256": digest,
        "bytes": byte_count,
        "stat_identity": list(stat_identity(final)),
    }
    return dict(_EXECUTED_RUNNER_IDENTITY)


def bootstrap_expected_native_outer_launch_contract(
    layout: Mapping[str, Any],
) -> dict[str, Any]:
    """Reconstruct the bound outer launch declaration before contract import."""

    required_paths = {
        "launch_envelope_path",
        "manifest_path",
        "native_binary_path",
        "preregistration_path",
    }
    if not isinstance(layout, Mapping) or not required_paths <= set(layout):
        raise BootstrapError("native_outer_launch_layout_invalid")
    for field in required_paths:
        value = layout[field]
        if (
            not isinstance(value, str)
            or not value.startswith("/")
            or any(character in value for character in "\x00\r\n\t")
        ):
            raise BootstrapError("native_outer_launch_layout_invalid")
    if (
        bootstrap_canonical_sha256(EXPECTED_NATIVE_OUTER_ENVIRONMENT)
        != EXPECTED_NATIVE_OUTER_ENVIRONMENT_SHA256
    ):
        raise BootstrapError("native_outer_environment_constant_invalid")
    return {
        "schema_version": NATIVE_OUTER_LAUNCH_CONTRACT_SCHEMA,
        "launcher_path": "/system/bin/env",
        "launcher_toolchain_artifact_role": "system_launcher_env",
        "launcher_toolchain_artifact_identity_sha256": (
            EXPECTED_SYSTEM_LAUNCHER_ENV_IDENTITY_SHA256
        ),
        "launcher_resolved_path": "/system/bin/toybox",
        "launcher_clear_environment_argument": "-i",
        "launcher_argv_plan": [
            {"kind": "literal", "value": "/system/bin/env"},
            {"kind": "literal", "value": "-i"},
            {"kind": "literal", "value": layout["native_binary_path"]},
            {"kind": "literal", "value": "--launch"},
            {"kind": "literal", "value": "--manifest"},
            {"kind": "literal", "value": layout["manifest_path"]},
            {"kind": "literal", "value": "--manifest-sha256"},
            {"kind": "derived", "source": "native_manifest_bytes_sha256"},
            {
                "kind": "literal",
                "value": "--expected-preregistration-sha256",
            },
            {"kind": "derived", "source": "preregistration_bytes_sha256"},
        ],
        "launcher_argv_resolution": (
            "typed_literal_or_canonical_payload_sha256_no_shell_interpolation"
        ),
        "outer_environment": {},
        "outer_environment_sha256": EXPECTED_NATIVE_OUTER_ENVIRONMENT_SHA256,
        "outer_environment_must_be_empty": True,
        "forbidden_outer_environment_name_prefixes": ["LD_"],
        "native_attestation_required": {
            "outer_env_observed": True,
            "outer_environment_sha256": EXPECTED_NATIVE_OUTER_ENVIRONMENT_SHA256,
        },
        "shell_interpolation_allowed": False,
        "malicious_same_UID_tamper_resistance_claimed": False,
        "security_ceiling": (
            "observational_only_no_guarantee_against_a_concurrent_malicious_"
            "same_uid_between_checks"
        ),
    }


def bootstrap_native_contract_from_preregistration(
    preregistration_payload: bytes,
) -> dict[str, Any]:
    """Extract only a canonical, exact FD/outer-launch prereg declaration."""

    try:
        preregistration = bootstrap_strict_json_loads(preregistration_payload)
    except (BootstrapError, json.JSONDecodeError, UnicodeError) as error:
        raise BootstrapError("native_preregistration_json_invalid") from error
    if (
        not isinstance(preregistration, dict)
        or bootstrap_canonical_json_bytes(preregistration) + b"\n"
        != preregistration_payload
    ):
        raise BootstrapError("native_preregistration_not_canonical")
    native = preregistration.get("native_preflight")
    if not isinstance(native, dict):
        raise BootstrapError("native_preflight_contract_missing")
    if native.get("fixed_fd_map") != EXPECTED_NATIVE_PREFLIGHT_FIXED_FD_MAP:
        raise BootstrapError("native_preflight_fixed_fd_map_mismatch")
    expected_outer = bootstrap_expected_native_outer_launch_contract(
        native.get("execution_layout")
    )
    if native.get("outer_launch") != expected_outer or native.get(
        "outer_launch_sha256"
    ) != bootstrap_canonical_sha256(expected_outer):
        raise BootstrapError("native_outer_launch_contract_mismatch")
    toolchain = preregistration.get("phone_toolchain_identity")
    artifacts = toolchain.get("artifacts") if isinstance(toolchain, dict) else None
    launcher = (
        artifacts.get("system_launcher_env") if isinstance(artifacts, dict) else None
    )
    if (
        not isinstance(launcher, dict)
        or bootstrap_canonical_sha256(launcher)
        != expected_outer["launcher_toolchain_artifact_identity_sha256"]
        or launcher.get("literal_path") != expected_outer["launcher_path"]
        or launcher.get("resolved_path") != expected_outer["launcher_resolved_path"]
    ):
        raise BootstrapError("native_outer_launcher_identity_mismatch")
    return native


def bootstrap_validate_native_maps(
    attestation: Mapping[str, Any],
    native_contract: Mapping[str, Any],
) -> None:
    maps = attestation.get("native_maps")
    maps_contract = native_contract.get("native_maps_contract")
    native_self_shape = (
        maps_contract.get("native_self_executable_map")
        if isinstance(maps_contract, Mapping)
        else None
    )
    if (
        not isinstance(native_self_shape, Mapping)
        or set(native_self_shape) != {"mapped_bytes", "offset", "source"}
        or native_self_shape.get("source")
        != "deterministic_build_receipt_executable_PT_LOAD"
        or type(native_self_shape.get("offset")) is not int
        or native_self_shape["offset"] < 0
        or type(native_self_shape.get("mapped_bytes")) is not int
        or native_self_shape["mapped_bytes"] <= 0
    ):
        raise BootstrapError("native_attestation_self_map_contract_invalid")
    expected_contract = {
        "capture_timing": "first_action_in_main_before_argument_parsing",
        "executable_mapping_policy": (
            "exact_nine_record_phone_native_runtime_closure_only"
        ),
        "normalized_fields": [
            "bytes",
            "device_major",
            "device_minor",
            "inode",
            "mapped_bytes",
            "offset",
            "path",
            "permissions",
            "runtime_role",
            "sha256",
        ],
        "record_count": 9,
        "native_self_executable_map": dict(native_self_shape),
        "schema_version": "cur0s_native_earliest_main_maps_v1",
        "start_and_end_addresses_excluded_as_ASLR_only": True,
        "unexpected_executable_mappings_forbidden": True,
        "vvar_required_nonexecutable": True,
    }
    expected_map_fields = {
        "capture_timing",
        "executable_mapping_policy",
        "production_policy_enforced",
        "records",
        "schema_version",
        "unexpected_executable_mappings_absent",
        "vvar",
    }
    if (
        maps_contract != expected_contract
        or not isinstance(maps, Mapping)
        or set(maps) != expected_map_fields
        or maps["capture_timing"] != expected_contract["capture_timing"]
        or maps["executable_mapping_policy"]
        != expected_contract["executable_mapping_policy"]
        or maps["production_policy_enforced"] is not True
        or maps["schema_version"] != expected_contract["schema_version"]
        or maps["unexpected_executable_mappings_absent"] is not True
        or maps["vvar"] != {"nonexecutable": True, "present": True}
        or attestation.get("native_maps_root_sha256")
        != bootstrap_canonical_sha256(maps)
    ):
        raise BootstrapError("native_attestation_maps_contract_mismatch")
    records = maps["records"]
    record_fields = set(expected_contract["normalized_fields"])
    if not isinstance(records, list) or len(records) != 9:
        raise BootstrapError("native_attestation_maps_record_count_mismatch")
    static_records = native_contract.get("static_manifest_records")
    if not isinstance(static_records, list):
        raise BootstrapError("native_attestation_maps_manifest_missing")
    toolchain_files = {
        record.get("toolchain_role"): record
        for record in static_records
        if isinstance(record, dict)
        and record.get("record_type") == "FILE"
        and isinstance(record.get("toolchain_role"), str)
    }
    native_self = next(
        (
            record
            for record in static_records
            if isinstance(record, dict)
            and record.get("record_type") == "FILE"
            and record.get("runtime_role") == "native_self"
        ),
        None,
    )
    expected_shapes = {
        "android_linker64": (0x4C000, 0x116000),
        "android_bionic_libc": (0x48000, 0x8F000),
        "android_bionic_libdl": (0x4000, 0x1000),
        "android_bionic_libm": (0x14000, 0x24000),
        "system_libcxx": (0x84000, 0x7B000),
        "system_libnetd_client": (0x4000, 0x4000),
    }
    expected_by_role: dict[str, Mapping[str, Any] | None] = {
        **{role: toolchain_files.get(role) for role in expected_shapes},
        "native-self": native_self,
        "kernel_vdso": None,
        "kernel_vvar": None,
    }
    observed_roles: list[str] = []
    for record in records:
        if not isinstance(record, Mapping) or set(record) != record_fields:
            raise BootstrapError("native_attestation_maps_record_schema_invalid")
        role = record["runtime_role"]
        expected_file = expected_by_role.get(role)
        if role not in expected_by_role or role in observed_roles:
            raise BootstrapError("native_attestation_maps_role_closure_invalid")
        observed_roles.append(role)
        for field in (
            "device_major",
            "device_minor",
            "inode",
            "mapped_bytes",
            "offset",
        ):
            if type(record[field]) is not int or record[field] < 0:
                raise BootstrapError("native_attestation_maps_integer_invalid")
        if role == "kernel_vdso":
            expected_kernel = {
                "bytes": None,
                "device_major": 0,
                "device_minor": 0,
                "inode": 0,
                "mapped_bytes": 0x1000,
                "offset": 0,
                "path": "[vdso]",
                "permissions": "r-xp",
                "runtime_role": role,
                "sha256": None,
            }
            if dict(record) != expected_kernel:
                raise BootstrapError("native_attestation_vdso_identity_invalid")
            continue
        if role == "kernel_vvar":
            expected_kernel = {
                "bytes": None,
                "device_major": 0,
                "device_minor": 0,
                "inode": 0,
                "mapped_bytes": 0x2000,
                "offset": 0,
                "path": "[vvar]",
                "permissions": "r--p",
                "runtime_role": role,
                "sha256": None,
            }
            if dict(record) != expected_kernel:
                raise BootstrapError("native_attestation_vvar_identity_invalid")
            continue
        if not isinstance(expected_file, Mapping):
            raise BootstrapError("native_attestation_maps_manifest_role_missing")
        if (
            record["bytes"] != expected_file["bytes"]
            or record["path"] != expected_file["path"]
            or record["sha256"] != expected_file["sha256"]
            or record["permissions"] != "r-xp"
            or record["inode"] <= 0
        ):
            raise BootstrapError("native_attestation_maps_file_identity_invalid")
        if role == "native-self":
            if (record["offset"], record["mapped_bytes"]) != (
                native_self_shape["offset"],
                native_self_shape["mapped_bytes"],
            ):
                raise BootstrapError("native_attestation_self_map_shape_invalid")
        elif (record["offset"], record["mapped_bytes"]) != expected_shapes[role]:
            raise BootstrapError("native_attestation_runtime_map_shape_invalid")
    if set(observed_roles) != set(expected_by_role) or records != sorted(
        records,
        key=lambda record: (
            record["path"],
            record["offset"],
            record["permissions"],
            record["inode"],
        ),
    ):
        raise BootstrapError("native_attestation_maps_order_or_roles_invalid")


def bootstrap_native_preflight_guard() -> dict[str, Any]:
    """Require the sealed same-PID native measurement handoff before imports."""

    global _NATIVE_PREFLIGHT_EXEC_ATTESTATION
    global _NATIVE_PREFLIGHT_MANIFEST_BYTES
    global _NATIVE_PREFLIGHT_MANIFEST_IDENTITY
    global _NATIVE_PREFLIGHT_PREREGISTRATION_BYTES
    global _NATIVE_PREFLIGHT_PREREGISTRATION_IDENTITY

    receipt_payload, _receipt_identity = bootstrap_read_inherited_fd(
        NATIVE_PREFLIGHT_ATTESTATION_FD,
        role="attestation",
        max_bytes=64 * 1024,
        expected_mode=0o400,
        expected_nlink=0,
    )
    get_seals = getattr(fcntl, "F_GET_SEALS", 1034)
    expected_seals = (
        getattr(fcntl, "F_SEAL_SEAL", 0x0001)
        | getattr(fcntl, "F_SEAL_SHRINK", 0x0002)
        | getattr(fcntl, "F_SEAL_GROW", 0x0004)
        | getattr(fcntl, "F_SEAL_WRITE", 0x0008)
    )
    try:
        observed_seals = fcntl.fcntl(NATIVE_PREFLIGHT_ATTESTATION_FD, get_seals)
    except OSError as error:
        raise BootstrapError("native_attestation_memfd_seals_unavailable") from error
    if observed_seals != expected_seals:
        raise BootstrapError("native_attestation_memfd_seals_mismatch")
    try:
        os.close(NATIVE_PREFLIGHT_ATTESTATION_FD)
    except OSError as error:
        raise BootstrapError("native_attestation_fd_close_failed") from error

    manifest_payload, manifest_identity = bootstrap_read_inherited_fd(
        NATIVE_PREFLIGHT_MANIFEST_FD,
        role="manifest",
        max_bytes=4 * 1024 * 1024,
        expected_mode=0o600,
        expected_nlink=1,
    )
    prereg_payload, prereg_identity = bootstrap_read_inherited_fd(
        NATIVE_PREFLIGHT_PREREGISTRATION_FD,
        role="preregistration",
        max_bytes=1024 * 1024,
        expected_mode=0o600,
        expected_nlink=1,
    )
    native_contract = bootstrap_native_contract_from_preregistration(prereg_payload)
    try:
        os.fstat(NATIVE_PREFLIGHT_PYTHON_EXEC_CLOEXEC_FD)
    except OSError:
        pass
    else:
        raise BootstrapError("native_python_exec_fd_not_cloexec")

    try:
        attestation = bootstrap_strict_json_loads(receipt_payload)
    except (BootstrapError, json.JSONDecodeError, UnicodeError) as error:
        raise BootstrapError("native_attestation_json_invalid") from error
    if (
        not isinstance(attestation, dict)
        or bootstrap_canonical_json_bytes(attestation) != receipt_payload
    ):
        raise BootstrapError("native_attestation_not_canonical")
    expected_fields = {
        "entries_verified",
        "fixed_fds",
        "helper_dependency_swap_safety_claimed",
        "manifest_sha256",
        "mode",
        "native_maps",
        "native_maps_root_sha256",
        "outer_env_observed",
        "outer_environment_sha256",
        "passes_completed",
        "persistent_writes",
        "pid",
        "python_pycache_prefix",
        "python_pycache_prefix_absent",
        "roles",
        "run_id",
        "schema_version",
        "security_ceiling",
        "status",
    }
    fixed_fds = native_contract["fixed_fd_map"]
    outer_launch = native_contract["outer_launch"]
    if (
        set(attestation) != expected_fields
        or attestation.get("schema_version") != "cur0s_native_launch_attestation_v2"
        or attestation.get("status") != "verified"
        or attestation.get("mode") != "launch"
        or attestation.get("passes_completed") != 2
        or attestation.get("persistent_writes") is not False
        or attestation.get("outer_env_observed") is not True
        or attestation.get("outer_environment_sha256")
        != outer_launch["outer_environment_sha256"]
        or attestation.get("helper_dependency_swap_safety_claimed") is not False
        or attestation.get("security_ceiling")
        != (
            "observational_only_no_guarantee_against_a_concurrent_malicious_"
            "same_uid_between_checks"
        )
        or attestation.get("pid") != os.getpid()
        or attestation.get("python_pycache_prefix")
        != native_contract.get("python_pycache_prefix")
        or attestation.get("python_pycache_prefix_absent") is not True
        or native_contract.get("python_pycache_prefix_must_be_absent") is not True
        or os.path.lexists(attestation.get("python_pycache_prefix", ""))
        or type(attestation.get("entries_verified")) is not int
        or attestation["entries_verified"] <= 0
        or not isinstance(attestation.get("run_id"), str)
        or RUN_ID_RE.fullmatch(attestation["run_id"]) is None
        or fixed_fds != EXPECTED_NATIVE_PREFLIGHT_FIXED_FD_MAP
        or attestation.get("fixed_fds") != fixed_fds
    ):
        raise BootstrapError("native_attestation_claim_mismatch")
    bootstrap_validate_native_maps(attestation, native_contract)
    manifest_sha256 = "sha256:" + hashlib.sha256(manifest_payload).hexdigest()
    if (
        normalize_bootstrap_sha(
            attestation.get("manifest_sha256"),
            "native_attestation_manifest_sha256",
        )
        != manifest_sha256
    ):
        raise BootstrapError("native_attestation_manifest_sha256_mismatch")
    roles = attestation.get("roles")
    if not isinstance(roles, dict) or set(roles) != {
        "native-self",
        "preregistration",
        "python",
        "runner",
    }:
        raise BootstrapError("native_attestation_role_closure_invalid")
    for role, value in roles.items():
        if (
            not isinstance(value, dict)
            or set(value) != {"bytes", "path", "sha256"}
            or type(value.get("bytes")) is not int
            or value["bytes"] <= 0
            or not isinstance(value.get("path"), str)
            or not value["path"].startswith("/")
            or any(character in value["path"] for character in "\x00\r\n\t")
        ):
            raise BootstrapError(f"native_attestation_role_invalid:{role}")
        normalize_bootstrap_sha(value.get("sha256"), f"native_{role}_sha256")
    prereg_sha256 = "sha256:" + hashlib.sha256(prereg_payload).hexdigest()
    runner = _EXECUTED_RUNNER_IDENTITY
    if (
        roles["preregistration"]["bytes"] != len(prereg_payload)
        or roles["preregistration"]["sha256"] != prereg_sha256
        or not isinstance(runner, dict)
        or roles["runner"]["bytes"] != runner.get("bytes")
        or roles["runner"]["sha256"] != runner.get("sha256")
        or roles["runner"]["path"] != runner.get("path")
    ):
        raise BootstrapError("native_attestation_held_role_mismatch")

    _NATIVE_PREFLIGHT_EXEC_ATTESTATION = attestation
    _NATIVE_PREFLIGHT_MANIFEST_BYTES = manifest_payload
    _NATIVE_PREFLIGHT_MANIFEST_IDENTITY = manifest_identity
    _NATIVE_PREFLIGHT_PREREGISTRATION_BYTES = prereg_payload
    _NATIVE_PREFLIGHT_PREREGISTRATION_IDENTITY = prereg_identity
    return dict(attestation)


def preimport_python_guard() -> None:
    """Reject every runtime except the isolated REDMAGIC Termux instance."""

    observed_startup = observe_python_startup_identity()
    require_exact_python_startup(observed_startup)
    if os.path.lexists(EXPECTED_PYTHON_INITIAL_SYS_PATH[0]):
        raise BootstrapError("python313_zip_must_remain_absent")
    sys.path[:] = EXPECTED_PYTHON_SANITIZED_SYS_PATH
    attest_executed_runner_fd()
    bootstrap_native_preflight_guard()
    if platform.system() != "Android" or platform.machine() != "aarch64":
        raise BootstrapError("runner_requires_android_aarch64")
    expected_home = str(PHONE_HOME)
    if str(Path.home()) != expected_home:
        raise BootstrapError("runner_requires_exact_termux_private_home")


def preimport_phone_guard() -> None:
    """Compatibility wrapper for the exact Python and live-device guards."""

    preimport_python_guard()
    observed: dict[str, str] = {}
    for key, prop in {
        "model": "ro.product.model",
        "device": "ro.product.device",
        "soc": "ro.soc.model",
    }.items():
        observed[key] = getprop(prop)
    if observed != {"model": "NX789J", "device": "NX789J", "soc": "SM8750"}:
        raise BootstrapError("live_phone_identity_mismatch")
    fingerprint = getprop_raw("ro.build.fingerprint")
    fingerprint_sha256 = "sha256:" + hashlib.sha256(fingerprint).hexdigest()
    if fingerprint_sha256 != EXPECTED_BUILD_FINGERPRINT_SHA256:
        raise BootstrapError("live_phone_build_fingerprint_mismatch")
    for property_name, expected_value in EXPECTED_OEM_THERMAL_PROPERTIES.items():
        observed_value = getprop_raw(property_name)
        if observed_value != (expected_value + "\n").encode("ascii"):
            raise BootstrapError("live_phone_oem_thermal_property_mismatch")


def load_bound_module(module_name: str, relative_path: str, source_bytes: bytes):
    """Execute only repository bytes already admitted by the bootstrap."""

    module = types.ModuleType(module_name)
    module.__file__ = str(ROOT / relative_path)
    module.__package__ = ""
    sys.modules[module_name] = module
    code = compile(source_bytes, module.__file__, "exec", dont_inherit=True)
    exec(code, module.__dict__)
    return module


def bind_bound_module(source_bytes: dict[str, bytes] | None = None) -> None:
    """Bind the commercial contract after its bytes have been attested."""

    relative_path = BOUND_SOURCE_FILES[0]
    if source_bytes is None:
        payload = (ROOT / relative_path).read_bytes()
    else:
        payload = source_bytes[relative_path]
    module = load_bound_module(
        "_cur0s_commercial_sources_bound", relative_path, payload
    )
    globals().update(
        {
            "CommercialSourceError": module.CommercialSourceError,
            "DirectSourceSpec": module.DirectSourceSpec,
            "GitSourceSpec": module.GitSourceSpec,
            "DIRECT_SOURCES": module.DIRECT_SOURCES,
            "GIT_SOURCES": module.GIT_SOURCES,
            "build_source_root": module.build_source_root,
            "canonical_json_bytes": module.canonical_json_bytes,
            "canonical_sha256": module.canonical_sha256,
            "phone_thermal_safety_contract": module.phone_thermal_safety_contract,
            "phone_toolchain_contract": module.phone_toolchain_contract,
            "build_native_preflight_execution_contract": (
                module.build_native_preflight_execution_contract
            ),
            "build_native_preflight_manifest_bytes": (
                module.build_native_preflight_manifest_bytes
            ),
            "NATIVE_PREFLIGHT_SOURCE_FILES": module.NATIVE_PREFLIGHT_SOURCE_FILES,
            "source_contract": module.source_contract,
            "validate_source_contract": module.validate_source_contract,
        }
    )


if __name__ != "__main__":
    bind_bound_module()


_PREIMPORT_SOURCE_ATTESTATION: dict[str, Any] | None = None


def bootstrap_authority(
    args: argparse.Namespace,
) -> tuple[bytes, dict[str, Any], dict[str, bytes], dict[str, Any]]:
    """Verify the canonical preregistration and bound code before import."""

    if _NATIVE_PREFLIGHT_PREREGISTRATION_BYTES is None:
        if __name__ == "__main__":
            raise BootstrapError("native_preregistration_fd_required")
        prereg_bytes = bootstrap_read_private_preregistration(args.preregistration)
    else:
        prereg_bytes = _NATIVE_PREFLIGHT_PREREGISTRATION_BYTES
    expected_preregistration_sha256 = normalize_bootstrap_sha(
        args.expected_preregistration_sha256,
        "expected_preregistration_sha256",
    )
    observed_preregistration_sha256 = (
        "sha256:" + hashlib.sha256(prereg_bytes).hexdigest()
    )
    if observed_preregistration_sha256 != expected_preregistration_sha256:
        raise BootstrapError("external_preregistration_sha256_mismatch")
    prereg = bootstrap_strict_json_loads(prereg_bytes)
    if not isinstance(prereg, dict):
        raise BootstrapError("preregistration_must_be_object")
    if prereg_bytes != bootstrap_canonical_json_bytes(prereg) + b"\n":
        raise BootstrapError("preregistration_not_canonical")
    if prereg.get("schema_version") != PREREG_SCHEMA:
        raise BootstrapError("preregistration_schema_mismatch")
    run_id = prereg.get("run_id")
    if not isinstance(run_id, str) or RUN_ID_RE.fullmatch(run_id) is None:
        raise BootstrapError("run_id_invalid")
    lease = prereg.get("campaign_lease")
    if not isinstance(lease, dict) or lease.get("action_id") != run_id:
        raise BootstrapError("campaign_lease_action_mismatch")
    claimed_root = normalize_bootstrap_sha(
        prereg.get("preregistration_root_sha256"),
        "preregistration_root_sha256",
    )
    without_root = dict(prereg)
    without_root.pop("preregistration_root_sha256", None)
    if bootstrap_canonical_sha256(without_root) != claimed_root:
        raise BootstrapError("preregistration_root_mismatch")

    contract = prereg.get("commercial_source_contract")
    if not isinstance(contract, dict):
        raise BootstrapError("commercial_source_contract_missing")
    contract_sha = normalize_bootstrap_sha(
        prereg.get("commercial_source_contract_sha256"),
        "commercial_source_contract_sha256",
    )
    if bootstrap_canonical_sha256(contract) != contract_sha:
        raise BootstrapError("commercial_source_contract_sha256_mismatch")

    toolchain = prereg.get("phone_toolchain_identity")
    if not isinstance(toolchain, dict):
        raise BootstrapError("phone_toolchain_identity_missing")
    toolchain_sha = normalize_bootstrap_sha(
        prereg.get("phone_toolchain_identity_sha256"),
        "phone_toolchain_identity_sha256",
    )
    if bootstrap_canonical_sha256(toolchain) != toolchain_sha:
        raise BootstrapError("phone_toolchain_identity_sha256_mismatch")

    native_preflight = prereg.get("native_preflight")
    if not isinstance(native_preflight, dict):
        raise BootstrapError("native_preflight_contract_missing")
    native_preflight_sha = normalize_bootstrap_sha(
        prereg.get("native_preflight_sha256"),
        "native_preflight_sha256",
    )
    if bootstrap_canonical_sha256(native_preflight) != native_preflight_sha:
        raise BootstrapError("native_preflight_sha256_mismatch")
    native_body = dict(native_preflight)
    native_root = normalize_bootstrap_sha(
        native_body.pop("contract_root_sha256", None),
        "native_preflight_contract_root_sha256",
    )
    if bootstrap_canonical_sha256(native_body) != native_root:
        raise BootstrapError("native_preflight_contract_root_mismatch")
    execution_layout = native_preflight.get("execution_layout")
    if not isinstance(execution_layout, dict):
        raise BootstrapError("native_preflight_execution_layout_mismatch")
    expected_outer_launch = bootstrap_expected_native_outer_launch_contract(
        execution_layout
    )
    native_attestation = _NATIVE_PREFLIGHT_EXEC_ATTESTATION
    if (
        native_preflight.get("fixed_fd_map") != EXPECTED_NATIVE_PREFLIGHT_FIXED_FD_MAP
        or native_preflight.get("outer_launch") != expected_outer_launch
        or native_preflight.get("outer_launch_sha256")
        != bootstrap_canonical_sha256(expected_outer_launch)
        or (
            _NATIVE_PREFLIGHT_PREREGISTRATION_BYTES is not None
            and (
                not isinstance(native_attestation, dict)
                or native_attestation.get("fixed_fds")
                != native_preflight["fixed_fd_map"]
                or native_attestation.get("outer_env_observed") is not True
                or native_attestation.get("outer_environment_sha256")
                != expected_outer_launch["outer_environment_sha256"]
            )
        )
    ):
        raise BootstrapError("native_preflight_runtime_contract_mismatch")
    if _NATIVE_PREFLIGHT_PREREGISTRATION_BYTES is not None and (
        execution_layout.get("preregistration_path") != args.preregistration
        or execution_layout.get("candidate_output") != args.output_dir
        or execution_layout.get("checkout_root") != str(ROOT)
        or execution_layout.get("runner_path") != str(ROOT / BOUND_SOURCE_FILES[1])
        or execution_layout.get("commercial_sources_path")
        != str(ROOT / BOUND_SOURCE_FILES[0])
    ):
        raise BootstrapError("native_preflight_execution_layout_mismatch")

    bindings = prereg.get("source_file_bindings")
    if not isinstance(bindings, dict) or set(bindings) != set(BOUND_SOURCE_FILES):
        raise BootstrapError("source_file_bindings_missing")
    source_commit = prereg.get("source_commit")
    if not isinstance(source_commit, str) or COMMIT_RE.fullmatch(source_commit) is None:
        raise BootstrapError("source_commit_invalid")
    if prereg.get("parent_capsule_sha256") != EXPECTED_PARENT_CAPSULE_SHA256:
        raise BootstrapError("parent_capsule_sha256_mismatch")
    if (
        prereg.get("parent_frontier_root_sha256")
        != EXPECTED_PARENT_FRONTIER_ROOT_SHA256
    ):
        raise BootstrapError("parent_frontier_root_sha256_mismatch")

    checkout_fd = bootstrap_open_checkout_root()
    source_bytes: dict[str, bytes] = {}
    observed_bindings: dict[str, dict[str, Any]] = {}
    try:
        for relative_path in BOUND_SOURCE_FILES:
            payload = bootstrap_read_regular_beneath(checkout_fd, relative_path)
            source_bytes[relative_path] = payload
            observed_bindings[relative_path] = {
                "bytes": len(payload),
                "sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
                "git_blob_oid": bootstrap_git_blob_oid(payload),
            }
    finally:
        os.close(checkout_fd)
    if bindings != observed_bindings:
        raise BootstrapError("source_file_binding_mismatch")
    executed_runner = _EXECUTED_RUNNER_IDENTITY
    runner_binding = observed_bindings[BOUND_SOURCE_FILES[1]]
    if (
        not isinstance(executed_runner, dict)
        or executed_runner.get("sha256") != runner_binding["sha256"]
        or executed_runner.get("bytes") != runner_binding["bytes"]
    ):
        raise BootstrapError("executed_runner_binding_mismatch")
    expected_hashes = {
        "commercial_sources_sha256": observed_bindings[BOUND_SOURCE_FILES[0]]["sha256"],
        "runner_sha256": observed_bindings[BOUND_SOURCE_FILES[1]]["sha256"],
    }
    if prereg.get("source_file_sha256") != expected_hashes:
        raise BootstrapError("source_file_hash_binding_mismatch")
    attestation = {
        "source_commit": source_commit,
        "source_file_sha256": expected_hashes,
        "source_file_bindings": observed_bindings,
        "git_HEAD_verified": False,
        "bound_source_files_clean": False,
        "external_preregistration_sha256_verified": True,
        "runner_execution_fd_verified": _EXECUTED_RUNNER_IDENTITY is not None,
        "bound_contract_bytes_verified_before_contract_import": True,
    }
    return prereg_bytes, prereg, source_bytes, attestation


def bootstrap_read_private_preregistration(path_text: str) -> bytes:
    path = Path(path_text)
    if not path.is_absolute():
        raise BootstrapError("preregistration_must_be_absolute")
    absolute = Path(os.path.abspath(path))
    try:
        relative = absolute.relative_to(PHONE_HOME)
    except ValueError:
        raise BootstrapError("preregistration_outside_phone_private_home") from None
    if not relative.parts or relative.parts[0] != PHONE_RUN_ROOT_RELATIVE:
        raise BootstrapError("preregistration_outside_campaign_root")
    home_fd = os.open(
        PHONE_HOME,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        fd = bootstrap_open_regular_beneath(
            home_fd,
            str(relative),
            require_owner_only_components=True,
            require_owner_only_file=True,
        )
    finally:
        os.close(home_fd)
    try:
        initial = os.fstat(fd)
        if initial.st_nlink != 1 or initial.st_size > 1024 * 1024:
            raise BootstrapError("preregistration_inode_or_size_invalid")
        return bootstrap_read_stable_fd(fd, initial, 1024 * 1024)
    finally:
        os.close(fd)


def bootstrap_open_checkout_root() -> int:
    try:
        relative = ROOT.relative_to(PHONE_HOME)
    except ValueError:
        raise BootstrapError("source_checkout_outside_phone_private_home") from None
    home_fd = os.open(
        PHONE_HOME,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        return bootstrap_open_directory_beneath(home_fd, str(relative))
    finally:
        os.close(home_fd)


def bootstrap_open_regular_beneath(
    root_fd: int,
    relative_path: str,
    *,
    require_owner_only_components: bool = False,
    require_owner_only_file: bool = False,
) -> int:
    components = validate_relative_components(relative_path, BootstrapError)
    current_fd = os.dup(root_fd)
    try:
        for component in components[:-1]:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
            bootstrap_require_owned_fd(
                current_fd,
                owner_only=require_owner_only_components,
                role="bootstrap_directory",
            )
        file_fd = os.open(
            components[-1],
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=current_fd,
        )
        info = os.fstat(file_fd)
        if not stat.S_ISREG(info.st_mode):
            os.close(file_fd)
            raise BootstrapError("bootstrap_artifact_not_regular")
        bootstrap_require_owned_fd(
            file_fd,
            owner_only=require_owner_only_file,
            role="bootstrap_file",
        )
        return file_fd
    finally:
        os.close(current_fd)


def bootstrap_open_directory_beneath(root_fd: int, relative_path: str) -> int:
    components = validate_relative_components(relative_path, BootstrapError)
    current_fd = os.dup(root_fd)
    try:
        for component in components:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
            bootstrap_require_owned_fd(
                current_fd,
                owner_only=False,
                role="source_checkout_directory",
            )
        result = current_fd
        current_fd = -1
        return result
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def bootstrap_require_owned_fd(fd: int, *, owner_only: bool, role: str) -> None:
    info = os.fstat(fd)
    if info.st_uid != os.geteuid() or info.st_gid != os.getegid():
        raise BootstrapError(f"{role}_owner_mismatch")
    forbidden = 0o077 if owner_only else 0o022
    if stat.S_IMODE(info.st_mode) & forbidden:
        raise BootstrapError(f"{role}_permissions_invalid")


def bootstrap_read_regular_beneath(root_fd: int, relative_path: str) -> bytes:
    fd = bootstrap_open_regular_beneath(root_fd, relative_path)
    try:
        initial = os.fstat(fd)
        if initial.st_nlink != 1 or initial.st_size > 16 * 1024 * 1024:
            raise BootstrapError("bound_source_inode_or_size_invalid")
        return bootstrap_read_stable_fd(fd, initial, 16 * 1024 * 1024)
    finally:
        os.close(fd)


def bootstrap_read_stable_fd(fd: int, initial: os.stat_result, limit: int) -> bytes:
    result = bytearray()
    while True:
        chunk = os.read(fd, min(1024 * 1024, limit + 1 - len(result)))
        if not chunk:
            break
        result.extend(chunk)
        if len(result) > limit:
            raise BootstrapError("bootstrap_artifact_too_large")
    final = os.fstat(fd)
    if stat_identity(initial) != stat_identity(final):
        raise BootstrapError("bootstrap_artifact_changed_during_read")
    return bytes(result)


def bootstrap_git_blob_oid(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def bootstrap_strict_json_loads(payload: bytes) -> Any:
    def reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise BootstrapError("duplicate_json_key")
            result[key] = value
        return result

    def reject_constant(_: str) -> None:
        raise BootstrapError("nonfinite_json_constant")

    return json.loads(
        payload,
        object_pairs_hook=reject_pairs,
        parse_constant=reject_constant,
    )


def bootstrap_canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def bootstrap_canonical_sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(bootstrap_canonical_json_bytes(value)).hexdigest()


def normalize_bootstrap_sha(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise BootstrapError(f"{field}_missing")
    match = SHA256_RE.fullmatch(value)
    if match is None:
        raise BootstrapError(f"{field}_invalid")
    return "sha256:" + match.group(1)


class OperationalStop(RuntimeError):
    """A preregistered finite-resource or thermal boundary stopped execution."""

    def __init__(self, code: str, checkpoint: str) -> None:
        super().__init__(code)
        self.code = code
        self.checkpoint = sanitize_checkpoint(checkpoint)


@dataclass(frozen=True)
class CampaignLease:
    lease_id: str
    action_id: str
    issued_at: datetime
    expires_at: datetime
    max_wall_seconds: int
    terminalization_reserve_seconds: int
    max_private_output_bytes: int
    min_free_storage_bytes: int
    thermal_safety_contract: Mapping[str, Any]
    thermal_sample_interval_seconds: int


@dataclass(frozen=True)
class ThermalGroupSample:
    group: str
    maximum_temperature_millidegrees_c: int
    sensor_types: tuple[str, ...]
    readable_sensor_types: tuple[str, ...]
    unavailable_sensor_types: tuple[str, ...]


@dataclass(frozen=True)
class ThermalSample:
    schema_version: str
    thermal_safety_contract_root_sha256: str
    zone_type_roster_sha256: str
    readable_sensor_count: int
    excluded_non_temperature_sensor_types: tuple[str, ...]
    groups: tuple[ThermalGroupSample, ...]


class ResourceEnvelope:
    """Continuously enforce the preregistered phone execution envelope."""

    def __init__(
        self,
        lease: CampaignLease,
        candidate: "PrivateCandidate",
        started_monotonic: float,
        *,
        now_fn=None,
        monotonic_fn=None,
        thermal_reader=None,
        statvfs_fn=None,
    ) -> None:
        self.lease = lease
        self.candidate = candidate
        self._started_monotonic = started_monotonic
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._monotonic_fn = monotonic_fn or time.monotonic
        self._thermal_reader = thermal_reader or read_thermal_zones
        self._statvfs_fn = statvfs_fn or os.fstatvfs
        self._checkpoint = "not_started"
        self._previous_handler: Any = None
        self._armed = False
        self._terminalizing = False
        self._last_thermal_sample_monotonic: float | None = None
        self._maximum_elapsed_seconds = 0.0
        self._minimum_free_storage_bytes: int | None = None
        thermal_groups = self.lease.thermal_safety_contract[
            "group_ceilings_millidegrees_c"
        ]
        self._maximum_thermal_group_temperatures: dict[str, int | None] = {
            group: None for group in thermal_groups
        }
        self._observed_thermal_sensor_types_by_group: dict[str, tuple[str, ...]] = {
            group: () for group in thermal_groups
        }
        self._thermal_sample_count = 0
        self._maximum_readable_thermal_sensor_count = 0
        self._maximum_private_output_bytes = 0
        self._maximum_private_allocated_bytes = 0
        self._ephemeral_controls: dict[int, tuple[int, str]] = {}
        self._maximum_ephemeral_control_bytes = 0
        self._maximum_ephemeral_control_allocated_bytes = 0

    def register_ephemeral_control(self, fd: int, *, limit: int, role: str) -> None:
        if fd in self._ephemeral_controls or limit <= 0:
            raise AcquisitionError("ephemeral_control_registration_invalid")
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise AcquisitionError("ephemeral_control_inode_invalid")
        self._ephemeral_controls[fd] = (limit, sanitize_checkpoint(role))

    def unregister_ephemeral_control(self, fd: int) -> None:
        if self._ephemeral_controls.pop(fd, None) is None:
            raise AcquisitionError("ephemeral_control_not_registered")

    def _ephemeral_usage(self) -> tuple[int, int]:
        logical = 0
        allocated = 0
        for fd, (limit, role) in self._ephemeral_controls.items():
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink not in {0, 1}:
                raise AcquisitionError(f"ephemeral_control_inode_changed:{role}")
            if info.st_size > limit:
                raise AcquisitionError(f"ephemeral_control_size_limit:{role}")
            logical += info.st_size
            allocated += info.st_blocks * 512
        self._maximum_ephemeral_control_bytes = max(
            self._maximum_ephemeral_control_bytes, logical
        )
        self._maximum_ephemeral_control_allocated_bytes = max(
            self._maximum_ephemeral_control_allocated_bytes, allocated
        )
        return logical, allocated

    def arm(self) -> None:
        if self._armed:
            raise AcquisitionError("resource_envelope_already_armed")
        remaining_wall = self.lease.max_wall_seconds - self.elapsed_seconds()
        remaining_lease = (self.lease.expires_at - self._now_fn()).total_seconds()
        duration = min(remaining_wall, remaining_lease)
        if duration <= self.lease.terminalization_reserve_seconds:
            raise OperationalStop("lease_or_wall_deadline_reached", self._checkpoint)
        self._previous_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, self._handle_alarm)
        signal.setitimer(
            signal.ITIMER_REAL,
            max(0.001, duration - self.lease.terminalization_reserve_seconds),
        )
        self._armed = True

    def begin_terminalization(self, checkpoint: str) -> None:
        """Switch the soft execution alarm to the immutable hard lease deadline."""

        self._checkpoint = sanitize_checkpoint(checkpoint)
        remaining_wall = self.lease.max_wall_seconds - self.elapsed_seconds()
        remaining_lease = (self.lease.expires_at - self._now_fn()).total_seconds()
        duration = min(remaining_wall, remaining_lease)
        if duration <= 0:
            raise OperationalStop("terminalization_deadline_reached", self._checkpoint)
        if self._terminalizing:
            signal.setitimer(signal.ITIMER_REAL, max(0.001, duration))
            return
        if not self._armed:
            self._previous_handler = signal.getsignal(signal.SIGALRM)
            signal.signal(signal.SIGALRM, self._handle_alarm)
            self._armed = True
        signal.setitimer(signal.ITIMER_REAL, max(0.001, duration))
        self._terminalizing = True

    def disarm(self) -> None:
        if not self._armed:
            return
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, self._previous_handler)
        self._armed = False
        # Preserve terminal threshold semantics for the final synchronous
        # evidence audit that runs after the process-local alarm is removed.

    def check(self, checkpoint: str, *, force_thermal: bool = False) -> None:
        self._checkpoint = sanitize_checkpoint(checkpoint)
        elapsed = self.elapsed_seconds()
        self._maximum_elapsed_seconds = max(self._maximum_elapsed_seconds, elapsed)
        wall_limit = self.lease.max_wall_seconds
        lease_limit = self.lease.expires_at
        if not self._terminalizing:
            wall_limit -= self.lease.terminalization_reserve_seconds
            lease_limit -= timedelta(seconds=self.lease.terminalization_reserve_seconds)
        if elapsed >= wall_limit:
            raise OperationalStop("wall_time_limit_reached", self._checkpoint)
        if self._now_fn() >= lease_limit:
            raise OperationalStop(
                "campaign_lease_expired_mid_execution", self._checkpoint
            )

        self.candidate.revalidate_path_binding()
        filesystem = self._statvfs_fn(self.candidate.directory_fd)
        free_bytes = filesystem.f_bavail * filesystem.f_frsize
        if self._minimum_free_storage_bytes is None:
            self._minimum_free_storage_bytes = free_bytes
        else:
            self._minimum_free_storage_bytes = min(
                self._minimum_free_storage_bytes, free_bytes
            )
        if free_bytes < self.lease.min_free_storage_bytes:
            raise OperationalStop("free_storage_floor_crossed", self._checkpoint)

        logical, allocated = private_tree_usage(self.candidate.directory_fd)
        ephemeral_logical, ephemeral_allocated = self._ephemeral_usage()
        logical += ephemeral_logical
        allocated += ephemeral_allocated
        self._maximum_private_output_bytes = max(
            self._maximum_private_output_bytes, logical
        )
        self._maximum_private_allocated_bytes = max(
            self._maximum_private_allocated_bytes, allocated
        )
        if logical + CONTROL_RESERVE_BYTES > self.lease.max_private_output_bytes:
            raise OperationalStop("private_output_budget_reached", self._checkpoint)

        now_monotonic = self._monotonic_fn()
        thermal_due = (
            force_thermal
            or self._last_thermal_sample_monotonic is None
            or now_monotonic - self._last_thermal_sample_monotonic
            >= self.lease.thermal_sample_interval_seconds
        )
        if thermal_due:
            self._sample_thermal()
            self._last_thermal_sample_monotonic = now_monotonic

    def elapsed_seconds(self) -> float:
        return max(0.0, self._monotonic_fn() - self._started_monotonic)

    def receipt_metrics(self) -> dict[str, Any]:
        self.candidate.revalidate_path_binding()
        self._maximum_elapsed_seconds = max(
            self._maximum_elapsed_seconds, self.elapsed_seconds()
        )
        logical, allocated = private_tree_usage(self.candidate.directory_fd)
        ephemeral_logical, ephemeral_allocated = self._ephemeral_usage()
        logical += ephemeral_logical
        allocated += ephemeral_allocated
        self._maximum_private_output_bytes = max(
            self._maximum_private_output_bytes, logical
        )
        self._maximum_private_allocated_bytes = max(
            self._maximum_private_allocated_bytes, allocated
        )
        return {
            "action_id": self.lease.action_id,
            "phone_execution_ordinal": 1,
            "max_wall_seconds": self.lease.max_wall_seconds,
            "terminalization_reserve_seconds": (
                self.lease.terminalization_reserve_seconds
            ),
            "maximum_observed_elapsed_seconds": self._maximum_elapsed_seconds,
            "min_free_storage_bytes": self.lease.min_free_storage_bytes,
            "minimum_observed_free_storage_bytes": self._minimum_free_storage_bytes,
            "thermal_safety_contract_root_sha256": (
                self.lease.thermal_safety_contract["contract_root_sha256"]
            ),
            "thermal_group_ceilings_millidegrees_c": dict(
                self.lease.thermal_safety_contract["group_ceilings_millidegrees_c"]
            ),
            "maximum_observed_thermal_group_millidegrees_c": dict(
                self._maximum_thermal_group_temperatures
            ),
            "observed_thermal_sensor_types_by_group": {
                group: list(sensor_types)
                for group, sensor_types in self._observed_thermal_sensor_types_by_group.items()
            },
            "thermal_unavailable_sentinels_millidegrees_c": list(
                self.lease.thermal_safety_contract[
                    "unavailable_sentinels_millidegrees_c"
                ]
            ),
            "thermal_sample_interval_seconds": (
                self.lease.thermal_sample_interval_seconds
            ),
            "thermal_sample_count": self._thermal_sample_count,
            "maximum_readable_thermal_sensor_count": (
                self._maximum_readable_thermal_sensor_count
            ),
            "max_private_output_bytes": self.lease.max_private_output_bytes,
            "private_output_bytes_before_receipt": logical,
            "private_output_allocated_bytes_before_receipt": allocated,
            "maximum_observed_private_output_bytes": (
                self._maximum_private_output_bytes
            ),
            "maximum_observed_private_allocated_bytes": (
                self._maximum_private_allocated_bytes
            ),
            "maximum_ephemeral_control_bytes": (self._maximum_ephemeral_control_bytes),
            "maximum_ephemeral_control_allocated_bytes": (
                self._maximum_ephemeral_control_allocated_bytes
            ),
            "ephemeral_control_files_open_at_receipt": len(self._ephemeral_controls),
            "lease_expires_at_utc": iso_utc(self.lease.expires_at),
        }

    def _sample_thermal(self) -> None:
        try:
            sample = self._thermal_reader()
        except OperationalStop as stop:
            raise OperationalStop(stop.code, self._checkpoint) from None
        group_maxima, sensor_types_by_group, readable_count = (
            validate_thermal_sample_against_lease(
                sample,
                self.lease,
                checkpoint=self._checkpoint,
            )
        )
        self._thermal_sample_count += 1
        self._maximum_readable_thermal_sensor_count = max(
            self._maximum_readable_thermal_sensor_count, readable_count
        )
        for group, maximum in group_maxima.items():
            previous = self._maximum_thermal_group_temperatures[group]
            self._maximum_thermal_group_temperatures[group] = (
                maximum if previous is None else max(previous, maximum)
            )
            self._observed_thermal_sensor_types_by_group[group] = sensor_types_by_group[
                group
            ]
        enforce_thermal_group_ceilings(
            group_maxima,
            self.lease,
            checkpoint=self._checkpoint,
        )

    def _handle_alarm(self, _signum: int, _frame: Any) -> None:
        raise OperationalStop("wall_or_lease_alarm_reached", self._checkpoint)


class EphemeralControlFiles:
    """Account unlinked temporary control files inside the sovereign budget."""

    def __init__(
        self,
        envelope: ResourceEnvelope,
        entries: Sequence[tuple[int, int, str]],
    ) -> None:
        self._envelope = envelope
        self._entries = tuple(entries)
        self._registered: list[int] = []

    def __enter__(self) -> "EphemeralControlFiles":
        try:
            for fd, limit, role in self._entries:
                self._envelope.register_ephemeral_control(fd, limit=limit, role=role)
                self._registered.append(fd)
        except BaseException:
            for fd in reversed(self._registered):
                self._envelope.unregister_ephemeral_control(fd)
            raise
        return self

    def __exit__(self, _error_type: Any, _error: Any, _traceback: Any) -> None:
        first_error: BaseException | None = None
        for fd in reversed(self._registered):
            try:
                self._envelope.unregister_ephemeral_control(fd)
            except BaseException as error:
                first_error = first_error or error
        self._registered.clear()
        if first_error is not None and _error is None:
            raise first_error


def read_thermal_zones() -> ThermalSample:
    """Read the exact held NX789J zone/type roster without unit confusion."""

    contract = phone_thermal_safety_contract()
    expected_roster = contract["zone_type_roster"]
    root_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        root_fd = os.open(contract["sysfs_root"], root_flags)
    except OSError as error:
        raise OperationalStop(
            "thermal_zone_root_unavailable", "thermal_sample"
        ) from error
    observations: list[tuple[str, str, int | None, bool]] = []
    try:
        try:
            zone_names = sorted(
                (
                    name
                    for name in os.listdir(root_fd)
                    if re.fullmatch(r"thermal_zone[0-9]+", name)
                ),
                key=lambda name: int(name.removeprefix("thermal_zone")),
            )
        except OSError as error:
            raise OperationalStop(
                "thermal_zone_roster_unreadable", "thermal_sample"
            ) from error
        if zone_names != list(expected_roster):
            raise OperationalStop("thermal_zone_roster_mismatch", "thermal_sample")
        for zone_name in zone_names:
            observations.append(
                _read_held_thermal_zone(
                    root_fd,
                    zone_name,
                    expected_roster[zone_name],
                    contract,
                )
            )
    finally:
        os.close(root_fd)
    return assemble_thermal_sample(observations, contract)


def _open_thermal_attribute(zone_fd: int, name: str) -> int:
    try:
        fd = os.open(
            name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=zone_fd,
        )
    except OSError as error:
        raise OperationalStop(
            f"thermal_sensor_{name}_unavailable", "thermal_sample"
        ) from error
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0:
        os.close(fd)
        raise OperationalStop(f"thermal_sensor_{name}_inode_invalid", "thermal_sample")
    return fd


def _read_held_thermal_zone(
    root_fd: int,
    zone_name: str,
    expected_type: str,
    contract: Mapping[str, Any],
) -> tuple[str, str, int | None, bool]:
    try:
        zone_fd = os.open(
            zone_name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY,
            dir_fd=root_fd,
        )
    except OSError as error:
        raise OperationalStop(
            "thermal_zone_directory_unavailable", "thermal_sample"
        ) from error
    try:
        zone_info = os.fstat(zone_fd)
        if not stat.S_ISDIR(zone_info.st_mode) or zone_info.st_uid != 0:
            raise OperationalStop(
                "thermal_zone_directory_inode_invalid", "thermal_sample"
            )
        first_type_fd = _open_thermal_attribute(zone_fd, "type")
        try:
            observed_type = read_thermal_type(first_type_fd)
        finally:
            os.close(first_type_fd)
        second_type_fd = _open_thermal_attribute(zone_fd, "type")
        temperature_fd: int | None = None
        value_was_read = expected_type not in set(
            contract["excluded_non_temperature_sensor_types"]
        )
        if value_was_read:
            temperature_fd = _open_thermal_attribute(zone_fd, "temp")
        try:
            temperature = (
                read_thermal_value(
                    temperature_fd,
                    plausible_range=tuple(
                        contract["plausible_temperature_range_millidegrees_c"]
                    ),
                    unavailable_sentinels=frozenset(
                        contract["unavailable_sentinels_millidegrees_c"]
                    ),
                )
                if temperature_fd is not None
                else None
            )
            repeated_type = read_thermal_type(second_type_fd)
        finally:
            if temperature_fd is not None:
                os.close(temperature_fd)
            os.close(second_type_fd)
        if observed_type != repeated_type:
            raise OperationalStop(
                "thermal_sensor_type_changed_during_sample", "thermal_sample"
            )
        return zone_name, observed_type, temperature, value_was_read
    finally:
        os.close(zone_fd)


def assemble_thermal_sample(
    observations: Sequence[tuple[str, str, int | None, bool]],
    contract: Mapping[str, Any],
) -> ThermalSample:
    expected_roster = contract["zone_type_roster"]
    if len(observations) != contract["expected_zone_count"]:
        raise OperationalStop("thermal_zone_roster_mismatch", "thermal_sample")
    observed_zones: set[str] = set()
    observed_types: set[str] = set()
    temperatures_by_group: dict[str, list[tuple[str, int | None]]] = {
        group: [] for group in contract["sensor_types_by_group"]
    }
    type_to_group = {
        sensor_type: group
        for group, sensor_types in contract["sensor_types_by_group"].items()
        for sensor_type in sensor_types
    }
    excluded_types = set(contract["excluded_non_temperature_sensor_types"])
    plausible_minimum, plausible_maximum = contract[
        "plausible_temperature_range_millidegrees_c"
    ]
    for zone_name, sensor_type, temperature, value_was_read in observations:
        if zone_name in observed_zones:
            raise OperationalStop("thermal_zone_duplicate", "thermal_sample")
        if sensor_type in observed_types:
            raise OperationalStop("thermal_sensor_type_duplicate", "thermal_sample")
        observed_zones.add(zone_name)
        observed_types.add(sensor_type)
        if expected_roster.get(zone_name) != sensor_type:
            raise OperationalStop("thermal_sensor_type_swap", "thermal_sample")
        if sensor_type in excluded_types:
            if value_was_read or temperature is not None:
                raise OperationalStop(
                    "thermal_non_temperature_value_admitted", "thermal_sample"
                )
            continue
        group = type_to_group.get(sensor_type)
        if group is None or not value_was_read:
            raise OperationalStop(
                "thermal_sensor_classification_unknown", "thermal_sample"
            )
        if temperature is not None and (
            type(temperature) is not int
            or not plausible_minimum <= temperature <= plausible_maximum
        ):
            raise OperationalStop(
                "thermal_sensor_unit_or_value_shape_invalid", "thermal_sample"
            )
        temperatures_by_group[group].append((sensor_type, temperature))
    if list(observed_zones) == [] or observed_zones != set(expected_roster):
        raise OperationalStop("thermal_zone_roster_mismatch", "thermal_sample")
    groups: list[ThermalGroupSample] = []
    readable_count = 0
    for group in sorted(temperatures_by_group):
        values = temperatures_by_group[group]
        expected_types = tuple(contract["sensor_types_by_group"][group])
        if (
            tuple(sorted(sensor_type for sensor_type, _value in values))
            != expected_types
        ):
            raise OperationalStop(
                "thermal_group_type_roster_mismatch", "thermal_sample"
            )
        readable = tuple(
            sorted(sensor_type for sensor_type, value in values if value is not None)
        )
        unavailable = tuple(
            sorted(sensor_type for sensor_type, value in values if value is None)
        )
        if not readable:
            raise OperationalStop(
                f"thermal_group_sensor_unavailable:{group}", "thermal_sample"
            )
        maximum = max(value for _sensor_type, value in values if value is not None)
        readable_count += len(readable)
        groups.append(
            ThermalGroupSample(
                group=group,
                maximum_temperature_millidegrees_c=maximum,
                sensor_types=expected_types,
                readable_sensor_types=readable,
                unavailable_sensor_types=unavailable,
            )
        )
    return ThermalSample(
        schema_version=THERMAL_SAMPLE_SCHEMA,
        thermal_safety_contract_root_sha256=contract["contract_root_sha256"],
        zone_type_roster_sha256=canonical_sha256(expected_roster),
        readable_sensor_count=readable_count,
        excluded_non_temperature_sensor_types=tuple(
            contract["excluded_non_temperature_sensor_types"]
        ),
        groups=tuple(groups),
    )


def validate_thermal_sample_against_lease(
    sample: Any,
    lease: CampaignLease,
    *,
    checkpoint: str,
) -> tuple[dict[str, int], dict[str, tuple[str, ...]], int]:
    contract = lease.thermal_safety_contract
    if not isinstance(sample, ThermalSample):
        raise OperationalStop("thermal_sample_shape_invalid", checkpoint)
    expected_groups = contract["sensor_types_by_group"]
    if (
        sample.schema_version != THERMAL_SAMPLE_SCHEMA
        or sample.thermal_safety_contract_root_sha256
        != contract["contract_root_sha256"]
        or sample.zone_type_roster_sha256
        != canonical_sha256(contract["zone_type_roster"])
        or sample.excluded_non_temperature_sensor_types
        != tuple(contract["excluded_non_temperature_sensor_types"])
        or tuple(group.group for group in sample.groups) != tuple(expected_groups)
    ):
        raise OperationalStop("thermal_sample_contract_mismatch", checkpoint)
    group_maxima: dict[str, int] = {}
    sensor_types_by_group: dict[str, tuple[str, ...]] = {}
    readable_count = 0
    for group_sample in sample.groups:
        expected_types = tuple(expected_groups[group_sample.group])
        if (
            group_sample.sensor_types != expected_types
            or set(group_sample.readable_sensor_types)
            & set(group_sample.unavailable_sensor_types)
            or tuple(
                sorted(
                    group_sample.readable_sensor_types
                    + group_sample.unavailable_sensor_types
                )
            )
            != expected_types
            or not group_sample.readable_sensor_types
            or type(group_sample.maximum_temperature_millidegrees_c) is not int
        ):
            raise OperationalStop("thermal_sample_group_shape_invalid", checkpoint)
        maximum = group_sample.maximum_temperature_millidegrees_c
        plausible_minimum, plausible_maximum = contract[
            "plausible_temperature_range_millidegrees_c"
        ]
        if not plausible_minimum <= maximum <= plausible_maximum:
            raise OperationalStop("thermal_sample_group_shape_invalid", checkpoint)
        group_maxima[group_sample.group] = maximum
        sensor_types_by_group[group_sample.group] = expected_types
        readable_count += len(group_sample.readable_sensor_types)
    if sample.readable_sensor_count != readable_count:
        raise OperationalStop("thermal_sample_sensor_count_invalid", checkpoint)
    return group_maxima, sensor_types_by_group, readable_count


def enforce_thermal_group_ceilings(
    group_maxima: Mapping[str, int],
    lease: CampaignLease,
    *,
    checkpoint: str,
) -> None:
    ceilings = lease.thermal_safety_contract["group_ceilings_millidegrees_c"]
    for group, ceiling in ceilings.items():
        if group_maxima[group] >= ceiling:
            raise OperationalStop(f"thermal_ceiling_reached:{group}", checkpoint)


def read_thermal_type(fd: int) -> str:
    try:
        payload = os.read(fd, 66)
    except OSError as error:
        raise OperationalStop(
            "thermal_sensor_type_unreadable", "thermal_sample"
        ) from error
    if len(payload) > 65:
        raise OperationalStop("thermal_sensor_type_oversize", "thermal_sample")
    if not payload.endswith(b"\n") or payload.count(b"\n") != 1:
        raise OperationalStop("thermal_sensor_type_malformed", "thermal_sample")
    try:
        sensor_type = payload[:-1].decode("ascii")
    except UnicodeDecodeError:
        raise OperationalStop(
            "thermal_sensor_type_malformed", "thermal_sample"
        ) from None
    if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", sensor_type) is None:
        raise OperationalStop("thermal_sensor_type_malformed", "thermal_sample")
    return sensor_type


def read_thermal_value(
    fd: int,
    *,
    plausible_range: tuple[int, int] = (5_000, 150_000),
    unavailable_sentinels: frozenset[int] = (
        THERMAL_UNAVAILABLE_SENTINELS_MILLIDEGREES_C
    ),
) -> int | None:
    try:
        payload = os.read(fd, 65)
    except OSError as error:
        raise OperationalStop(
            "thermal_sensor_value_unreadable", "thermal_sample"
        ) from error
    if len(payload) > 64:
        raise OperationalStop("thermal_sensor_value_oversize", "thermal_sample")
    if not payload.endswith(b"\n") or payload.count(b"\n") != 1:
        raise OperationalStop("thermal_sensor_value_malformed", "thermal_sample")
    try:
        text = payload[:-1].decode("ascii")
    except UnicodeDecodeError:
        raise OperationalStop(
            "thermal_sensor_value_malformed", "thermal_sample"
        ) from None
    if re.fullmatch(r"-?[0-9]+", text) is None:
        raise OperationalStop("thermal_sensor_value_malformed", "thermal_sample")
    value = int(text)
    if value in unavailable_sentinels:
        return None
    if not plausible_range[0] <= value <= plausible_range[1]:
        raise OperationalStop(
            "thermal_sensor_unit_or_value_shape_invalid", "thermal_sample"
        )
    return value


def sanitize_checkpoint(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}", value) is None:
        return "sanitized_runtime_checkpoint"
    return value


@dataclass(frozen=True)
class WrittenArtifact:
    name: str
    sha256: str
    size: int
    stat_identity: tuple[int, int, int, int, int, int, int, int, int]


@dataclass
class ExclusiveCreateProvenance:
    create_attempted: bool = False
    created_by_this_call: bool = False
    creation_binding: tuple[int, int, int, int] | None = None


@dataclass(frozen=True)
class DirectoryBinding:
    """One retained directory inode in the canonical phone custody chain."""

    name: str
    fd: int
    identity: tuple[int, int, int, int, int, int]


def execution_claim_name(run_id: str) -> str:
    if RUN_ID_RE.fullmatch(run_id) is None:
        raise AcquisitionError("run_id_invalid")
    return f".{run_id}.cur0s_execution_claim.json"


def execution_abort_name(run_id: str) -> str:
    if RUN_ID_RE.fullmatch(run_id) is None:
        raise AcquisitionError("run_id_invalid")
    return f".{run_id}.cur0s_ABORT.json"


class PrivateCandidate:
    """An owner-only candidate prepared before its one-shot claim is published."""

    def __init__(
        self,
        path: Path,
        directory_fd: int,
        canonical_chain: tuple[DirectoryBinding, ...],
        prepared_identity: tuple[int, int, int, int, int, int, int, int, int],
        run_id: str,
        preregistration_root_sha256: str,
        contract_root_sha256: str,
    ) -> None:
        self.path = path
        self.bound_path = FD_PATH_ROOT / str(directory_fd)
        self._directory_fd = directory_fd
        self._canonical_chain = canonical_chain
        self._control_fd = canonical_chain[0].fd
        self._parent_fd = canonical_chain[-1].fd
        self._claim_name = execution_claim_name(run_id)
        self._abort_name = execution_abort_name(run_id)
        self._prepared_identity = prepared_identity
        self._run_id = run_id
        self._preregistration_root_sha256 = preregistration_root_sha256
        self._contract_root_sha256 = contract_root_sha256
        self._claim: WrittenArtifact | None = None
        self._own_claim_entry_created = False
        self._foreign_claim_observed = False
        self._receipt: WrittenArtifact | None = None
        self._completion: WrittenArtifact | None = None
        self._expected_receipt_payload: bytes | None = None
        self._expected_completion_payload: bytes | None = None
        self._terminal_custody_revalidator: Callable[[frozenset[str]], None] | None = (
            None
        )
        self._completed = False
        self._removed = False

    @classmethod
    def prepare(
        cls,
        path: Path,
        run_id: str,
        preregistration_root_sha256: str,
        contract_root_sha256: str,
    ) -> "PrivateCandidate":
        required_parent = PHONE_RUN_ROOT / run_id / "candidate_runs"
        if path.parent != required_parent or path.name != "candidate-001":
            raise AcquisitionError("private_candidate_path_mismatch")
        canonical_chain = open_phone_candidate_chain(run_id)
        parent_fd = canonical_chain[-1].fd
        control_fd = canonical_chain[0].fd
        claim_name = execution_claim_name(run_id)
        abort_name = execution_abort_name(run_id)
        directory_fd = -1
        prepared_identity = None
        created = False
        try:
            if entry_exists_at(control_fd, abort_name):
                raise AcquisitionError("prior_abort_forbids_execution_claim")
            if entry_exists_at(control_fd, claim_name):
                raise AcquisitionError("prior_execution_claim_forbids_replay")
            try:
                os.mkdir(path.name, mode=0o700, dir_fd=parent_fd)
                created = True
                os.fsync(parent_fd)
            except FileExistsError:
                # A power loss can leave the durably prepared empty directory
                # before the stable one-shot claim is published.  Adopt only
                # that exact, owner-only, empty inode; every other orphan is a
                # terminal initialization blocker.
                created = False
            created_entry = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
            if not stat.S_ISDIR(created_entry.st_mode):
                raise AcquisitionError("prepared_candidate_not_directory")
            prepared_identity = stat_identity(created_entry)
            directory_fd = os.open(
                path.name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=parent_fd,
            )
            require_owned_fd(directory_fd, owner_only=True, role="candidate_output")
            prepared = os.fstat(directory_fd)
            if (
                not stat.S_ISDIR(prepared.st_mode)
                or stat_identity(prepared) != prepared_identity
                or os.listdir(directory_fd)
            ):
                raise AcquisitionError("prepared_candidate_not_empty_directory")
            os.fsync(directory_fd)
            revalidate_directory_chain(canonical_chain)
            return cls(
                path,
                directory_fd,
                canonical_chain,
                prepared_identity,
                run_id,
                preregistration_root_sha256,
                contract_root_sha256,
            )
        except BaseException as preparation_error:
            if directory_fd >= 0:
                try:
                    os.close(directory_fd)
                except OSError:
                    pass
            try:
                candidate_entry_present = entry_exists_at(parent_fd, path.name)
            except BaseException:
                candidate_entry_present = True
            prior_terminal_control = isinstance(
                preparation_error, AcquisitionError
            ) and str(preparation_error) in {
                "prior_abort_forbids_execution_claim",
                "prior_execution_claim_forbids_replay",
            }
            if prior_terminal_control:
                pass
            elif created:
                try:
                    remove_exact_empty_directory_at(
                        parent_fd,
                        path.name,
                        expected_identity=prepared_identity,
                    )
                except BaseException as cleanup_error:
                    try:
                        publish_initialization_abort_at(
                            control_fd,
                            name=abort_name,
                            run_id=run_id,
                            preregistration_root_sha256=preregistration_root_sha256,
                            contract_root_sha256=contract_root_sha256,
                            blocker=sanitize_blocker_text(str(cleanup_error)),
                            checkpoint="candidate_preparation_cleanup",
                            claim_state="not_published",
                        )
                    except BaseException:
                        pass
            elif candidate_entry_present:
                try:
                    publish_initialization_abort_at(
                        control_fd,
                        name=abort_name,
                        run_id=run_id,
                        preregistration_root_sha256=preregistration_root_sha256,
                        contract_root_sha256=contract_root_sha256,
                        blocker="candidate_preparation_identity_unproven",
                        checkpoint="candidate_preparation_cleanup",
                        claim_state="not_published",
                    )
                except BaseException:
                    pass
            close_directory_bindings(canonical_chain)
            raise

    @property
    def claimed(self) -> bool:
        return self._claim is not None

    @property
    def claim_consumed(self) -> bool:
        return self.claimed or self._own_claim_entry_created

    @property
    def foreign_claim_observed(self) -> bool:
        return self._foreign_claim_observed

    @property
    def completed(self) -> bool:
        return self.reconcile_exact_completion_if_present()

    def publish_execution_claim(self) -> WrittenArtifact:
        if self._removed or self._claim is not None:
            raise AcquisitionError("execution_claim_state_invalid")
        self.revalidate_path_binding(require_prepared_identity=True)
        if entry_exists_at(self._control_fd, self._abort_name):
            raise AcquisitionError("parent_abort_appeared_before_claim")
        if entry_exists_at(self._control_fd, self._claim_name):
            self._foreign_claim_observed = True
            raise ClaimPublicationError("execution_claim_already_present")
        if os.listdir(self._directory_fd):
            raise AcquisitionError("candidate_not_empty_before_claim")
        prepared = os.fstat(self._directory_fd)
        if stat_identity(prepared) != self._prepared_identity:
            raise AcquisitionError("prepared_candidate_identity_changed")
        claim_value = {
            "schema_version": EXECUTION_CLAIM_SCHEMA,
            "state": "claimed_terminal_pending",
            "run_id": self._run_id,
            "output_directory_name": self.path.name,
            "stable_control_anchor": str(PHONE_PACKAGE_ROOT),
            "execution_claim_filename": self._claim_name,
            "phone_execution_ordinal": 1,
            "preregistration_root_sha256": self._preregistration_root_sha256,
            "contract_root_sha256": self._contract_root_sha256,
            "candidate_directory_prepared_identity": {
                "device": self._prepared_identity[0],
                "inode": self._prepared_identity[1],
                "file_type": "directory",
                "link_count": self._prepared_identity[3],
                "bytes": self._prepared_identity[4],
                "uid": self._prepared_identity[5],
                "gid": self._prepared_identity[6],
                "mode": "0700",
            },
            "replay_allowed": False,
            "claim_only_disposition": "blocked_incomplete_nonreplayable",
            "valid_terminal_resolutions": [
                "canonical_receipt_bound_COMPLETE_in_candidate",
                "stable_control_anchor_ABORT_without_source_root_pass",
            ],
        }
        payload = canonical_json_bytes(claim_value) + b"\n"
        self.revalidate_path_binding(require_prepared_identity=True)
        if entry_exists_at(self._control_fd, self._abort_name):
            raise AcquisitionError("parent_abort_appeared_before_claim")
        if entry_exists_at(self._control_fd, self._claim_name):
            self._foreign_claim_observed = True
            raise ClaimPublicationError("execution_claim_already_present")
        provenance = ExclusiveCreateProvenance()
        try:
            claim = publish_exact_bytes_at(
                self._control_fd,
                self._claim_name,
                payload,
                mode=0o400,
                provenance=provenance,
            )
        except BaseException as error:
            if provenance.created_by_this_call:
                self._own_claim_entry_created = True
            elif entry_exists_at(self._control_fd, self._claim_name):
                self._foreign_claim_observed = True
            else:
                self.rollback_unclaimed()
            raise ClaimPublicationError("execution_claim_publication_failed") from error
        if not provenance.created_by_this_call:
            raise AcquisitionError("execution_claim_create_provenance_missing")
        self._claim = claim
        self._own_claim_entry_created = True
        return claim

    def rollback_unclaimed(self) -> None:
        if self._removed:
            return
        if self._foreign_claim_observed:
            raise AcquisitionError("foreign_execution_claim_cleanup_forbidden")
        if self._claim is not None or self._own_claim_entry_created:
            raise AcquisitionError("execution_claim_present_cleanup_forbidden")
        if entry_exists_at(self._control_fd, self._claim_name):
            self._foreign_claim_observed = True
            raise AcquisitionError("foreign_execution_claim_cleanup_forbidden")
        self.revalidate_path_binding(require_prepared_identity=True)
        if os.listdir(self._directory_fd):
            raise AcquisitionError("unclaimed_candidate_not_empty")
        current = os.fstat(self._directory_fd)
        if stat_identity(current) != self._prepared_identity:
            raise AcquisitionError("unclaimed_candidate_identity_changed")
        os.close(self._directory_fd)
        self._directory_fd = -1
        remove_exact_empty_directory_at(
            self._parent_fd,
            self.path.name,
            expected_identity=self._prepared_identity,
        )
        self._removed = True

    def write_parent_abort(
        self,
        *,
        blocker: str,
        checkpoint: str,
        claim_state: str | None = None,
    ) -> WrittenArtifact:
        if not self.claim_consumed:
            raise AcquisitionError("parent_abort_requires_owned_execution_claim")
        if self.reconcile_exact_completion_if_present():
            raise AcquisitionError("completion_entry_present_abort_forbidden")
        value = {
            "schema_version": ABORT_SCHEMA,
            "state": "blocked_incomplete_terminalization",
            "run_id": self._run_id,
            "output_directory_name": self.path.name,
            "phone_execution_ordinal": 1,
            "preregistration_root_sha256": self._preregistration_root_sha256,
            "contract_root_sha256": self._contract_root_sha256,
            "claim_state": claim_state
            or ("committed" if self._claim is not None else "present_unverified"),
            "claim_sha256": self._claim.sha256 if self._claim is not None else None,
            "receipt_sha256": (
                self._receipt.sha256 if self._receipt is not None else None
            ),
            "completion_sha256": (
                self._completion.sha256 if self._completion is not None else None
            ),
            "blocker": sanitize_blocker_text(blocker),
            "checkpoint": sanitize_checkpoint(checkpoint),
            "replay_allowed": False,
            "source_root_pass_claimed": False,
            "raw_payload_egressed": False,
        }
        return publish_exact_bytes_at(
            self._control_fd,
            self._abort_name,
            canonical_json_bytes(value) + b"\n",
            mode=0o400,
        )

    def bind_expected_terminal(
        self,
        receipt: Mapping[str, Any],
        complete: Mapping[str, Any],
    ) -> None:
        """Bind the only receipt/COMPLETE pair this invocation may adopt."""

        receipt_value = dict(receipt)
        complete_value = dict(complete)
        if (
            receipt_value.get("schema_version") != RECEIPT_SCHEMA
            or receipt_value.get("run_id") != self._run_id
            or receipt_value.get("state") not in {"passed_scope", "blocked_fail_closed"}
        ):
            raise AcquisitionError("terminal_receipt_identity_invalid")
        claim_record = receipt_value.get("execution_claim")
        if (
            not isinstance(claim_record, Mapping)
            or self._claim is None
            or claim_record.get("claim_sha256") != self._claim.sha256
            or claim_record.get("state") != "claimed_terminal_pending_once_O_EXCL"
        ):
            raise AcquisitionError("terminal_receipt_claim_binding_invalid")
        receipt_without_root = dict(receipt_value)
        receipt_root = receipt_without_root.pop("receipt_root_sha256", None)
        if receipt_root != canonical_sha256(receipt_without_root):
            raise AcquisitionError("terminal_receipt_root_invalid")
        expected_protocol = (
            "raw_sources_fsync_read_only_then_receipt_O_EXCL_fsync_read_only_then_"
            "COMPLETE_O_EXCL_fsync_last"
            if receipt_value["state"] == "passed_scope"
            else "partial_raw_preserved_then_blocker_receipt_O_EXCL_fsync_read_only_"
            "then_COMPLETE_O_EXCL_fsync_last"
        )
        expected_complete_fields = {
            "schema_version",
            "run_id",
            "state",
            "receipt_sha256",
            "receipt_root_sha256",
            "receipt_bytes",
            "completion_marker_prepared_at_utc",
            "completion_protocol",
            "raw_sources_preserved_on_phone",
            "output_directory_mode",
        }
        receipt_payload = canonical_json_bytes(receipt_value) + b"\n"
        if (
            set(complete_value) != expected_complete_fields
            or complete_value.get("schema_version") != COMPLETE_SCHEMA
            or complete_value.get("run_id") != self._run_id
            or complete_value.get("state") != receipt_value["state"]
            or complete_value.get("receipt_sha256")
            != "sha256:" + hashlib.sha256(receipt_payload).hexdigest()
            or complete_value.get("receipt_root_sha256") != receipt_root
            or complete_value.get("receipt_bytes") != len(receipt_payload)
            or complete_value.get("completion_protocol") != expected_protocol
            or complete_value.get("raw_sources_preserved_on_phone") is not True
            or complete_value.get("output_directory_mode") != "owner_only_0700"
        ):
            raise AcquisitionError("terminal_completion_binding_invalid")
        parse_utc_second(
            complete_value.get("completion_marker_prepared_at_utc"),
            "completion_marker_prepared_at_utc",
        )
        completion_payload = canonical_json_bytes(complete_value) + b"\n"
        if self._expected_receipt_payload is not None and (
            self._expected_receipt_payload != receipt_payload
            or self._expected_completion_payload != completion_payload
        ):
            raise AcquisitionError("terminal_binding_already_fixed")
        self._expected_receipt_payload = receipt_payload
        self._expected_completion_payload = completion_payload

    def bind_terminal_custody_revalidator(
        self,
        revalidator: Callable[[frozenset[str]], None],
    ) -> None:
        if not callable(revalidator):
            raise AcquisitionError("terminal_custody_revalidator_invalid")
        if (
            self._terminal_custody_revalidator is not None
            and self._terminal_custody_revalidator is not revalidator
        ):
            raise AcquisitionError("terminal_custody_revalidator_already_bound")
        self._terminal_custody_revalidator = revalidator

    def revalidate_terminal_custody(
        self,
        expected_control_entries: frozenset[str],
    ) -> None:
        if self._terminal_custody_revalidator is None:
            raise AcquisitionError("terminal_custody_revalidator_missing")
        self._terminal_custody_revalidator(expected_control_entries)

    def reconcile_exact_completion_if_present(self) -> bool:
        """Adopt only a canonical receipt-bound COMPLETE from this candidate."""

        if (
            self._claim is None
            or self._expected_receipt_payload is None
            or self._expected_completion_payload is None
        ):
            self._completed = False
            return False
        receipt_record = read_canonical_json_artifact_at(
            self._directory_fd, "receipt.json"
        )
        completion_record = read_canonical_json_artifact_at(
            self._directory_fd, "COMPLETE.json"
        )
        if receipt_record is None or completion_record is None:
            self._completed = False
            return False
        receipt_artifact, receipt = receipt_record
        completion_artifact, completion = completion_record
        if (
            canonical_json_bytes(receipt) + b"\n" != self._expected_receipt_payload
            or canonical_json_bytes(completion) + b"\n"
            != self._expected_completion_payload
        ):
            self._completed = False
            return False
        try:
            self._revalidate_exact_terminal_state(
                receipt_artifact,
                completion_artifact,
                receipt,
            )
        except (OSError, AcquisitionError):
            self._completed = False
            return False
        self._receipt = receipt_artifact
        self._completion = completion_artifact
        self._completed = True
        return True

    def _revalidate_exact_terminal_state(
        self,
        receipt_artifact: WrittenArtifact,
        completion_artifact: WrittenArtifact,
        receipt: Mapping[str, Any],
    ) -> None:
        """Reprove the public terminal transaction after COMPLETE publication."""

        required_candidate_entries = {"receipt.json", "COMPLETE.json"}
        allowed_candidate_entries = {*required_candidate_entries, "sources"}
        passed_scope = receipt.get("state") == "passed_scope"
        if passed_scope:
            required_candidate_entries.add("sources")
        for _pass in range(2):
            if passed_scope:
                self.revalidate_terminal_custody(
                    frozenset({"receipt.json", "COMPLETE.json"})
                )
            self.revalidate_path_binding()
            self._revalidate_execution_claim()
            current_receipt = read_canonical_json_artifact_at(
                self._directory_fd, "receipt.json"
            )
            current_completion = read_canonical_json_artifact_at(
                self._directory_fd, "COMPLETE.json"
            )
            if (
                current_receipt is None
                or current_completion is None
                or current_receipt[0] != receipt_artifact
                or current_completion[0] != completion_artifact
                or canonical_json_bytes(current_receipt[1]) + b"\n"
                != self._expected_receipt_payload
                or canonical_json_bytes(current_completion[1]) + b"\n"
                != self._expected_completion_payload
            ):
                raise AcquisitionError("terminal_artifact_binding_changed")
            candidate_entries = set(os.listdir(self._directory_fd))
            if not required_candidate_entries.issubset(
                candidate_entries
            ) or not candidate_entries.issubset(allowed_candidate_entries):
                raise AcquisitionError("terminal_candidate_entry_set_invalid")
            parent_entries = set(os.listdir(self._parent_fd))
            if parent_entries != {self.path.name}:
                raise AcquisitionError("terminal_parent_entry_set_invalid")
            if entry_exists_at(self._control_fd, self._abort_name):
                raise AcquisitionError("terminal_abort_conflicts_with_completion")
            os.fsync(self._directory_fd)
            os.fsync(self._parent_fd)
            os.fsync(self._control_fd)

    @property
    def directory_fd(self) -> int:
        if self._directory_fd < 0:
            raise AcquisitionError("candidate_directory_closed")
        return self._directory_fd

    def create_source_roots(self) -> tuple[Path, Path]:
        self.revalidate_path_binding()
        sources_fd = mkdir_open_at(self._directory_fd, "sources")
        try:
            direct_fd = mkdir_open_at(sources_fd, "direct")
            git_fd = mkdir_open_at(sources_fd, "git")
        finally:
            os.close(sources_fd)
        os.close(direct_fd)
        os.close(git_fd)
        os.fsync(self._directory_fd)
        self.revalidate_path_binding()
        return self.bound_path / "sources/direct", self.bound_path / "sources/git"

    def revalidate_path_binding(
        self, *, require_prepared_identity: bool = False
    ) -> None:
        """Prove the public path still names the held private candidate inode."""

        revalidate_directory_chain(self._canonical_chain)
        held = os.fstat(self._directory_fd)
        entry = os.stat(
            self.path.name,
            dir_fd=self._parent_fd,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISDIR(held.st_mode)
            or not stat.S_ISDIR(entry.st_mode)
            or (held.st_dev, held.st_ino) != (entry.st_dev, entry.st_ino)
            or held.st_uid != os.getuid()
            or entry.st_uid != os.getuid()
            or stat.S_IMODE(held.st_mode) != 0o700
            or stat.S_IMODE(entry.st_mode) != 0o700
        ):
            raise AcquisitionError("candidate_path_binding_changed")
        if require_prepared_identity and (
            stat_identity(held) != self._prepared_identity
            or stat_identity(entry) != self._prepared_identity
        ):
            raise AcquisitionError("prepared_candidate_identity_changed")

    def write_receipt(self, value: Mapping[str, Any]) -> WrittenArtifact:
        if self._completed or self._receipt is not None:
            raise AcquisitionError("candidate_already_completed")
        self._revalidate_execution_claim()
        payload = canonical_json_bytes(dict(value)) + b"\n"
        if (
            self._expected_receipt_payload is None
            or payload != self._expected_receipt_payload
        ):
            raise AcquisitionError("receipt_not_bound_for_this_terminalization")
        artifact = publish_exact_bytes_at(
            self._directory_fd,
            "receipt.json",
            payload,
            mode=0o400,
        )
        self._receipt = artifact
        return artifact

    def write_completion_last(self, value: Mapping[str, Any]) -> WrittenArtifact:
        if self._completed:
            raise AcquisitionError("candidate_already_completed")
        if self._receipt is None:
            raise AcquisitionError("receipt_missing_before_completion")
        self._revalidate_execution_claim()
        payload = canonical_json_bytes(dict(value)) + b"\n"
        if (
            self._expected_completion_payload is None
            or payload != self._expected_completion_payload
        ):
            raise AcquisitionError("completion_not_bound_for_this_terminalization")
        receipt_fd = os.open(
            "receipt.json",
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=self._directory_fd,
        )
        try:
            receipt_info = os.fstat(receipt_fd)
            receipt_entry = os.stat(
                "receipt.json", dir_fd=self._directory_fd, follow_symlinks=False
            )
            if (
                stat_identity(receipt_info) != self._receipt.stat_identity
                or stat_identity(receipt_entry) != self._receipt.stat_identity
                or hash_fd(receipt_fd) != (self._receipt.sha256, self._receipt.size)
            ):
                raise AcquisitionError("receipt_binding_changed_before_completion")
        finally:
            os.close(receipt_fd)
        if (
            not stat.S_ISREG(receipt_info.st_mode)
            or stat.S_IMODE(receipt_info.st_mode) != 0o400
        ):
            raise AcquisitionError("receipt_not_sealed_before_completion")
        artifact = publish_exact_bytes_at(
            self._directory_fd,
            "COMPLETE.json",
            payload,
            mode=0o400,
        )
        self._completion = artifact
        self._completed = False
        if not self.reconcile_exact_completion_if_present():
            raise AcquisitionError("terminal_postpublication_revalidation_failed")
        return artifact

    def _revalidate_execution_claim(self) -> None:
        if self._claim is None:
            raise AcquisitionError("execution_claim_not_committed")
        claim_name = self._claim_name
        fd = os.open(
            claim_name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=self._control_fd,
        )
        try:
            opened = os.fstat(fd)
            entry = os.stat(claim_name, dir_fd=self._control_fd, follow_symlinks=False)
            if (
                stat_identity(opened) != self._claim.stat_identity
                or stat_identity(entry) != self._claim.stat_identity
                or hash_fd(fd) != (self._claim.sha256, self._claim.size)
            ):
                raise AcquisitionError("execution_claim_binding_changed")
        finally:
            os.close(fd)

    def execution_claim_receipt(self) -> dict[str, Any]:
        if self._claim is None:
            raise AcquisitionError("execution_claim_not_committed")
        return {
            "state": "claimed_terminal_pending_once_O_EXCL",
            "claim_sha256": self._claim.sha256,
            "claim_bytes": self._claim.size,
            "stable_control_anchor": str(PHONE_PACKAGE_ROOT),
            "execution_claim_filename": self._claim_name,
            "claim_egressed": False,
            "claim_is_crash_anchor": True,
            "claim_only_state_is_blocked_and_never_replayable": True,
            "exclusive_Termux_UID_operational_assumption": True,
            "malicious_same_UID_tamper_resistance_claimed": False,
            "replay_allowed": False,
            "terminal_resolution_required": (
                "exact_receipt_bound_COMPLETE_or_stable_control_ABORT"
            ),
        }

    def close(self) -> None:
        if self._directory_fd >= 0:
            try:
                os.close(self._directory_fd)
            except OSError:
                pass
            self._directory_fd = -1
        close_directory_bindings(self._canonical_chain)
        self._canonical_chain = ()
        self._control_fd = -1
        self._parent_fd = -1


class TerminationSignalGuard:
    """Convert ordinary operator stop signals into typed operational stops."""

    def __init__(self) -> None:
        self._previous: dict[int, Any] = {}
        self._armed = False
        self._deferred: list[str] = []
        signals = [signal.SIGINT, signal.SIGTERM]
        if hasattr(signal, "SIGHUP"):
            signals.append(signal.SIGHUP)
        self._managed_signals = tuple(signals)
        self._initialization_mask: set[signal.Signals] | None = None

    @property
    def deferred_signals(self) -> tuple[str, ...]:
        return tuple(self._deferred)

    def block_during_initialization(self) -> None:
        if self._initialization_mask is not None:
            raise AcquisitionError("initialization_signal_mask_already_blocked")
        self._initialization_mask = signal.pthread_sigmask(
            signal.SIG_BLOCK, self._managed_signals
        )

    def restore_initialization_mask(self) -> None:
        if self._initialization_mask is None:
            return
        previous = self._initialization_mask
        self._initialization_mask = None
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)

    def arm(self) -> None:
        if self._armed:
            raise AcquisitionError("termination_signal_guard_already_armed")
        try:
            for signum in self._managed_signals:
                self._previous[signum] = signal.getsignal(signum)
                signal.signal(signum, self._handle)
        except BaseException:
            self.disarm()
            raise
        self._armed = True

    def disarm(self) -> None:
        first_error: BaseException | None = None
        for signum, previous in reversed(tuple(self._previous.items())):
            try:
                signal.signal(signum, previous)
            except BaseException as error:
                first_error = first_error or error
        self._previous.clear()
        self._armed = False
        if first_error is not None:
            raise first_error

    def defer_during_terminalization(self) -> None:
        """Make terminal publication non-interruptible by ordinary stop signals."""

        if not self._armed:
            return
        for signum in self._previous:
            signal.signal(signum, self._record_deferred)

    def _record_deferred(self, signum: int, _frame: Any) -> None:
        try:
            name = signal.Signals(signum).name
        except ValueError:
            name = str(signum)
        self._deferred.append(name)

    def _handle(self, signum: int, _frame: Any) -> None:
        try:
            name = signal.Signals(signum).name
        except ValueError:
            name = str(signum)
        raise OperationalStop(f"termination_signal_{name}", "signal")


def main(
    *,
    args: argparse.Namespace | None = None,
    prereg_bytes: bytes | None = None,
    prereg: dict[str, Any] | None = None,
) -> int:
    args = args or parse_args()
    started_monotonic = time.monotonic()
    started_at = utc_now()
    if prereg_bytes is None:
        prereg_path = validate_private_existing_path(
            Path(args.preregistration), "preregistration"
        )
        prereg_bytes = read_private_file(prereg_path)
    if prereg is None:
        prereg = strict_json_loads(prereg_bytes)
    if not isinstance(prereg, dict):
        raise AcquisitionError("preregistration_must_be_object")
    native_execution_identity = validate_native_preflight_execution_binding(
        prereg,
        prereg_bytes,
    )
    prevalidated_toolchain = validate_phone_toolchain(
        prereg.get("phone_toolchain_identity")
    )
    source_execution_identity = validate_preregistration(prereg)
    source_execution_identity["native_preflight_execution"] = native_execution_identity
    runtime_observed = guard_phone_environment()
    runtime_identity = validate_phone_runtime(
        prereg,
        runtime_observed,
        prevalidated_toolchain=prevalidated_toolchain,
    )
    lease = validate_campaign_lease(prereg)
    output_path = validate_private_output_path(
        Path(args.output_dir), prereg["run_id"], prereg["output_directory_name"]
    )
    preclaim_resource_check(output_path.parent, lease, started_monotonic)
    contract = source_contract()
    acquired_artifacts: list[dict[str, Any]] = []
    inspection_summaries: list[dict[str, Any]] = []
    active_source_id: str | None = None
    terminal_receipt: dict[str, Any] | None = None
    terminal_committed = False
    exit_code = 2
    transaction_error: BaseException | None = None
    envelope: ResourceEnvelope | None = None
    signal_guard = TerminationSignalGuard()
    candidate: PrivateCandidate | None = None

    def failure_receipt(
        *,
        blocker: str,
        blocker_class: str,
        checkpoint: str,
    ) -> dict[str, Any] | None:
        nonlocal transaction_error
        if candidate is None or not candidate.claimed or envelope is None:
            return None
        try:
            return build_failure_receipt(
                prereg=prereg,
                prereg_bytes=prereg_bytes,
                source_execution_identity=source_execution_identity,
                runtime_identity=runtime_identity,
                acquired_artifacts=acquired_artifacts,
                inspection_summaries=inspection_summaries,
                active_source_id=active_source_id,
                blocker=blocker,
                blocker_class=blocker_class,
                checkpoint=checkpoint,
                candidate=candidate,
                envelope=envelope,
                started_at=started_at,
                started_monotonic=started_monotonic,
            )
        except BaseException as error:
            transaction_error = error
            return None

    def enter_terminalization(checkpoint: str) -> bool:
        nonlocal transaction_error
        if envelope is None:
            return False
        try:
            envelope.begin_terminalization(checkpoint)
            return True
        except BaseException as error:
            transaction_error = error
            return False

    signal_guard.block_during_initialization()
    try:
        candidate = PrivateCandidate.prepare(
            output_path,
            prereg["run_id"],
            prereg["preregistration_root_sha256"],
            contract["contract_root_sha256"],
        )
        envelope = ResourceEnvelope(lease, candidate, started_monotonic)
        signal_guard.arm()
        signal_guard.restore_initialization_mask()
        envelope.arm()
        envelope.check("before_execution_claim", force_thermal=True)
        candidate.publish_execution_claim()
        envelope.check("candidate_claimed", force_thermal=True)
        direct_root, git_root = candidate.create_source_roots()
        allowed_hosts = frozenset(prereg["network_policy"]["allowed_https_hosts"])
        for source in DIRECT_SOURCES:
            active_source_id = source.source_id
            envelope.check(f"before_direct:{source.source_id}", force_thermal=True)
            artifact, inspection = acquire_direct_source(
                source,
                direct_root,
                candidate,
                envelope,
                allowed_hosts,
            )
            acquired_artifacts.append(artifact)
            inspection_summaries.append(inspection)
            envelope.check(f"after_direct:{source.source_id}", force_thermal=True)

        for source in GIT_SOURCES:
            active_source_id = source.source_id
            envelope.check(f"before_git:{source.source_id}", force_thermal=True)
            artifact, inspection = acquire_git_source(
                source,
                git_root,
                candidate,
                envelope,
                allowed_hosts,
            )
            acquired_artifacts.append(artifact)
            inspection_summaries.append(inspection)
            envelope.check(f"after_git:{source.source_id}", force_thermal=True)

        active_source_id = None
        if len(acquired_artifacts) != contract["source_count"]:
            raise AcquisitionError("commercial_source_artifact_count_mismatch")
        final_native_custody = validate_native_preflight_execution_binding(
            prereg,
            prereg_bytes,
        )
        source_execution_identity["native_preflight_final_revalidation"] = (
            final_native_custody
        )
        final_toolchain_custody = revalidate_full_phone_toolchain()
        runtime_identity["phone_toolchain"]["final_revalidation"] = (
            final_toolchain_custody
        )
        final_source_custody = reattest_candidate_source_tree(
            candidate,
            acquired_artifacts,
            envelope,
        )
        source_execution_identity["final_source_custody_reattestation"] = (
            final_source_custody
        )

        def revalidate_success_source_custody(
            expected_control_entries: frozenset[str],
        ) -> None:
            native_before = validate_native_preflight_execution_binding(
                prereg,
                prereg_bytes,
            )
            toolchain_before = revalidate_full_phone_toolchain()
            observed = reattest_candidate_source_tree(
                candidate,
                acquired_artifacts,
                envelope,
                expected_candidate_control_entries=expected_control_entries,
                expected_source_tree_mode=0o500,
            )
            if observed != final_source_custody:
                raise AcquisitionError("terminal_source_custody_changed")
            toolchain_after = revalidate_full_phone_toolchain()
            native_after = validate_native_preflight_execution_binding(
                prereg,
                prereg_bytes,
            )
            if (
                toolchain_before != final_toolchain_custody
                or toolchain_after != final_toolchain_custody
            ):
                raise AcquisitionError("terminal_toolchain_custody_changed")
            if (
                native_before != final_native_custody
                or native_after != final_native_custody
            ):
                raise AcquisitionError("terminal_native_preflight_custody_changed")

        candidate.bind_terminal_custody_revalidator(revalidate_success_source_custody)
        source_root = build_source_root(acquired_artifacts)
        envelope.check("source_root_built", force_thermal=True)
        envelope.begin_terminalization("success_receipt_terminalization")
        receipt = build_success_receipt(
            prereg=prereg,
            prereg_bytes=prereg_bytes,
            source_execution_identity=source_execution_identity,
            runtime_identity=runtime_identity,
            source_root=source_root,
            inspection_summaries=inspection_summaries,
            candidate=candidate,
            envelope=envelope,
            started_at=started_at,
            started_monotonic=started_monotonic,
        )
        terminal_receipt = receipt
        exit_code = 0
    except OperationalStop as stop:
        transaction_error = stop
        if enter_terminalization("operational_stop_terminalization"):
            terminal_receipt = failure_receipt(
                blocker=stop.code,
                blocker_class="operational_stop",
                checkpoint=stop.checkpoint,
            )
        exit_code = 3
    except (Exception, KeyboardInterrupt) as error:
        transaction_error = error
        if enter_terminalization("source_failure_terminalization"):
            terminal_receipt = failure_receipt(
                blocker=sanitize_blocker(error),
                blocker_class="source_gate_failure",
                checkpoint="source_acquisition",
            )
        exit_code = 2
    finally:
        try:
            signal_guard.defer_during_terminalization()
        except OperationalStop as stop:
            transaction_error = stop
            if enter_terminalization("signal_stop_terminalization"):
                terminal_receipt = failure_receipt(
                    blocker=stop.code,
                    blocker_class="operational_stop",
                    checkpoint=stop.checkpoint,
                )
            exit_code = 3
        except BaseException as error:
            transaction_error = transaction_error or error
        if candidate is None:
            terminalize_uncertain_preparation(
                output_path,
                run_id=prereg["run_id"],
                preregistration_root_sha256=prereg["preregistration_root_sha256"],
                contract_root_sha256=contract["contract_root_sha256"],
                blocker=sanitize_blocker_text(
                    str(transaction_error or "candidate_preparation_failed")
                ),
            )
        elif (
            candidate.claimed and terminal_receipt is not None and envelope is not None
        ):
            try:
                finalize_candidate(
                    candidate,
                    envelope,
                    prereg["run_id"],
                    terminal_receipt,
                    recheck=exit_code == 0,
                )
                terminal_committed = True
            except BaseException as error:
                transaction_error = error
                if candidate.reconcile_exact_completion_if_present():
                    terminal_committed = True
                else:
                    exit_code = 4
        elif candidate is not None and candidate.claimed:
            exit_code = 4

        if (
            candidate is not None
            and not terminal_committed
            and candidate.foreign_claim_observed
        ):
            # Another invocation owns the durable O_EXCL claim. This loser
            # must not publish ABORT or remove the shared prepared directory.
            exit_code = 5
        elif (
            candidate is not None
            and not terminal_committed
            and candidate.claim_consumed
        ):
            try:
                candidate.write_parent_abort(
                    blocker=sanitize_blocker_text(
                        str(transaction_error or "terminal_receipt_unavailable")
                    ),
                    checkpoint="terminal_evidence_publication",
                )
            except BaseException:
                # The durable claim remains a typed, non-replayable crash anchor.
                exit_code = 4
        elif candidate is not None and not candidate.claim_consumed:
            try:
                candidate.rollback_unclaimed()
            except BaseException as error:
                try:
                    candidate.write_parent_abort(
                        blocker=sanitize_blocker_text(str(error)),
                        checkpoint="unclaimed_candidate_cleanup",
                        claim_state="not_proven_absent",
                    )
                except BaseException:
                    pass
                exit_code = 4
        if envelope is not None:
            try:
                envelope.disarm()
            except BaseException as error:
                transaction_error = transaction_error or error
                exit_code = 4
        try:
            signal_guard.disarm()
        except BaseException:
            # Candidate evidence is already terminal or anchored. Signal-handler
            # restoration is process-local and cannot rewrite that result.
            exit_code = 4 if not terminal_committed else exit_code
        try:
            signal_guard.restore_initialization_mask()
        except BaseException:
            exit_code = 4 if not terminal_committed else exit_code
        if signal_guard.deferred_signals and exit_code == 0:
            exit_code = 3
        if candidate is not None and terminal_committed:
            try:
                if not candidate.reconcile_exact_completion_if_present():
                    raise AcquisitionError("final_terminal_snapshot_invalid")
            except BaseException as error:
                transaction_error = transaction_error or error
                terminal_committed = False
                exit_code = 4
        if candidate is not None:
            candidate.close()

    if terminal_committed and terminal_receipt is not None:
        emit_committed_receipt(terminal_receipt)
    return exit_code


def emit_committed_receipt(receipt: Mapping[str, Any]) -> None:
    """Best-effort aggregate egress outside the immutable phone transaction."""

    try:
        print(canonical_json_bytes(dict(receipt)).decode("utf-8"))
    except (OSError, ValueError):
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", required=True)
    parser.add_argument("--expected-preregistration-sha256", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def validate_preregistration(prereg: dict[str, Any]) -> dict[str, Any]:
    if prereg.get("schema_version") != PREREG_SCHEMA:
        raise AcquisitionError("preregistration_schema_mismatch")
    expected_state = {
        "candidate_id": "cur0s_commercial_authority_sources_phone_native_v1",
        "parent_experiment_id": "EXP-CUR0S-SOVEREIGN-COMPOSITE-V1",
        "state": "frozen_unobserved",
        "candidate_output_observed": False,
        "candidate_output_files_present": False,
        "phone_execution_started": False,
        "promotion_allowed": False,
        "claim_scope": "commercial_source_acquisition_identity_rights_and_phone_custody",
        "claim_ceiling": "source_root_passed_scope_only_not_integrated_CUR_0S",
        "output_directory_name": "candidate-001",
        "expected_disposition": (
            "retain_phone_private_source_root_and_continue_near_semantic_Arm_C"
        ),
    }
    if any(prereg.get(key) != value for key, value in expected_state.items()):
        raise AcquisitionError("preregistration_candidate_state_mismatch")
    run_id = prereg.get("run_id")
    if not isinstance(run_id, str) or RUN_ID_RE.fullmatch(run_id) is None:
        raise AcquisitionError("run_id_invalid")
    source_commit = prereg.get("source_commit")
    if not isinstance(source_commit, str) or COMMIT_RE.fullmatch(source_commit) is None:
        raise AcquisitionError("source_commit_invalid")
    if prereg.get("parent_capsule_sha256") != EXPECTED_PARENT_CAPSULE_SHA256:
        raise AcquisitionError("parent_capsule_sha256_mismatch")
    if (
        prereg.get("parent_frontier_root_sha256")
        != EXPECTED_PARENT_FRONTIER_ROOT_SHA256
    ):
        raise AcquisitionError("parent_frontier_root_sha256_mismatch")
    require_sha256(prereg.get("maximal_selector_sha256"), "maximal_selector_sha256")
    if prereg["maximal_selector_sha256"] != prereg["parent_frontier_root_sha256"]:
        raise AcquisitionError("maximal_selector_binding_mismatch")
    if prereg.get("ACCESS_receipt_sha256") != (
        "sha256:7b2b6d506b3ab82a17008edc4c79dd51512f6f9598e3db37cd1bb6f5ee4331ca"
    ):
        raise AcquisitionError("ACCESS_receipt_binding_mismatch")

    contract = validate_source_contract(prereg.get("commercial_source_contract"))
    eligibility = contract.get("preregistration_eligibility")
    if (
        not isinstance(eligibility, Mapping)
        or eligibility.get("eligible") is not True
        or eligibility.get("selection_critical_identity_blockers") != []
    ):
        blockers = (
            eligibility.get("selection_critical_identity_blockers")
            if isinstance(eligibility, Mapping)
            else None
        )
        if isinstance(blockers, list) and any(
            isinstance(blocker, Mapping)
            and blocker.get("reason") == "payload_grade_metadata_identity_unresolved"
            for blocker in blockers
        ):
            raise AcquisitionError("payload_grade_metadata_identity_unresolved")
        raise AcquisitionError("commercial_source_preregistration_ineligible")
    if prereg.get("commercial_source_contract_sha256") != canonical_sha256(contract):
        raise AcquisitionError("commercial_source_contract_hash_mismatch")
    expected_toolchain = phone_toolchain_contract()
    if prereg.get("phone_toolchain_identity") != expected_toolchain:
        raise AcquisitionError("phone_toolchain_identity_mismatch")
    if prereg.get("phone_toolchain_identity_sha256") != canonical_sha256(
        expected_toolchain
    ):
        raise AcquisitionError("phone_toolchain_identity_hash_mismatch")
    native_preflight = prereg.get("native_preflight")
    if not isinstance(native_preflight, Mapping):
        raise AcquisitionError("native_preflight_contract_missing")
    native_source_bindings = native_preflight.get("native_source_file_bindings")
    native_build_receipt = native_preflight.get("build_receipt")
    if not isinstance(native_source_bindings, Mapping) or not isinstance(
        native_build_receipt,
        Mapping,
    ):
        raise AcquisitionError("native_preflight_contract_invalid")
    try:
        expected_native_preflight = build_native_preflight_execution_contract(
            run_id=run_id,
            source_commit=source_commit,
            source_file_bindings=prereg.get("source_file_bindings"),
            native_source_file_bindings=native_source_bindings,
            native_build_receipt=native_build_receipt,
        )
    except CommercialSourceError as error:
        raise AcquisitionError("native_preflight_contract_invalid") from error
    if native_preflight != expected_native_preflight or prereg.get(
        "native_preflight_sha256"
    ) != canonical_sha256(expected_native_preflight):
        raise AcquisitionError("native_preflight_contract_mismatch")
    validate_campaign_lease(prereg)
    validate_network_policy(prereg, contract)
    validate_transaction_policy(prereg)
    validate_governing_inputs(prereg)

    if _PREIMPORT_SOURCE_ATTESTATION is None:
        expected_hashes = {
            "commercial_sources_sha256": file_sha256(ROOT / BOUND_SOURCE_FILES[0]),
            "runner_sha256": file_sha256(ROOT / BOUND_SOURCE_FILES[1]),
        }
        observed_bindings = {}
        for relative_path in BOUND_SOURCE_FILES:
            payload = (ROOT / relative_path).read_bytes()
            observed_bindings[relative_path] = {
                "bytes": len(payload),
                "sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
                "git_blob_oid": bootstrap_git_blob_oid(payload),
            }
        preimport_verified = False
    else:
        expected_hashes = _PREIMPORT_SOURCE_ATTESTATION["source_file_sha256"]
        observed_bindings = _PREIMPORT_SOURCE_ATTESTATION["source_file_bindings"]
        preimport_verified = True
    if prereg.get("source_file_sha256") != expected_hashes:
        raise AcquisitionError("source_file_hash_binding_mismatch")
    if prereg.get("source_file_bindings") != observed_bindings:
        raise AcquisitionError("source_file_git_binding_mismatch")
    if git_output("for-each-ref", "--format=%(refname)", "refs/replace"):
        raise AcquisitionError("source_checkout_replace_refs_forbidden")
    git_head = git_output("rev-parse", "HEAD")
    if git_head != source_commit:
        raise AcquisitionError("source_checkout_commit_mismatch")
    for relative_path in (*BOUND_SOURCE_FILES, *NATIVE_PREFLIGHT_SOURCE_FILES):
        binding_map = (
            observed_bindings
            if relative_path in BOUND_SOURCE_FILES
            else native_source_bindings
        )
        expected_blob = binding_map[relative_path]["git_blob_oid"]
        if git_output("rev-parse", f"HEAD:{relative_path}") != expected_blob:
            raise AcquisitionError("source_checkout_bound_blob_mismatch")
    dirty = git_output(
        "status",
        "--porcelain",
        "--untracked-files=no",
        "--",
        *BOUND_SOURCE_FILES,
        *NATIVE_PREFLIGHT_SOURCE_FILES,
    )
    if dirty:
        raise AcquisitionError("source_checkout_bound_files_dirty")

    claimed_root = require_sha256(
        prereg.get("preregistration_root_sha256"), "preregistration_root_sha256"
    )
    without_root = dict(prereg)
    without_root.pop("preregistration_root_sha256", None)
    if canonical_sha256(without_root) != claimed_root:
        raise AcquisitionError("preregistration_root_mismatch")
    return {
        "source_commit": source_commit,
        "source_file_sha256": expected_hashes,
        "source_file_bindings": observed_bindings,
        "git_HEAD_verified": True,
        "bound_source_files_clean": True,
        "preimport_source_bytes_verified": preimport_verified,
        "commercial_source_contract_sha256": canonical_sha256(contract),
        "commercial_source_contract_root_sha256": contract["contract_root_sha256"],
        "phone_toolchain_identity_sha256": canonical_sha256(expected_toolchain),
        "phone_toolchain_root_sha256": expected_toolchain["toolchain_root_sha256"],
        "native_preflight_contract_sha256": canonical_sha256(expected_native_preflight),
        "native_preflight_contract_root_sha256": expected_native_preflight[
            "contract_root_sha256"
        ],
    }


def validate_native_preflight_execution_binding(
    prereg: Mapping[str, Any],
    prereg_bytes: bytes,
) -> dict[str, Any]:
    """Bind the native attestation and inherited FDs to the frozen prereg."""

    if (
        _NATIVE_PREFLIGHT_EXEC_ATTESTATION is None
        or _NATIVE_PREFLIGHT_MANIFEST_BYTES is None
        or _NATIVE_PREFLIGHT_PREREGISTRATION_BYTES is None
        or _NATIVE_PREFLIGHT_MANIFEST_IDENTITY is None
        or _NATIVE_PREFLIGHT_PREREGISTRATION_IDENTITY is None
    ):
        raise AcquisitionError("native_preflight_inherited_binding_missing")
    if prereg_bytes != _NATIVE_PREFLIGHT_PREREGISTRATION_BYTES:
        raise AcquisitionError("native_preflight_preregistration_bytes_mismatch")
    try:
        expected_manifest = build_native_preflight_manifest_bytes(prereg)
    except CommercialSourceError as error:
        raise AcquisitionError("native_preflight_manifest_contract_invalid") from error
    if expected_manifest != _NATIVE_PREFLIGHT_MANIFEST_BYTES:
        raise AcquisitionError("native_preflight_manifest_closure_mismatch")
    native = prereg.get("native_preflight")
    if not isinstance(native, Mapping):
        raise AcquisitionError("native_preflight_contract_missing")
    attestation = _NATIVE_PREFLIGHT_EXEC_ATTESTATION
    roles = attestation["roles"]
    layout = native["execution_layout"]
    outer_launch = native.get("outer_launch")
    if not isinstance(outer_launch, Mapping):
        raise AcquisitionError("native_preflight_outer_launch_contract_missing")
    outer_environment = outer_launch.get("outer_environment")
    source_bindings = prereg["source_file_bindings"]
    toolchain = prereg["phone_toolchain_identity"]
    binary = native["build_receipt"]["binary_identity"]
    expected_roles = {
        "native-self": {
            "bytes": binary["bytes"],
            "path": layout["native_binary_path"],
            "sha256": binary["sha256"],
        },
        "preregistration": {
            "bytes": len(prereg_bytes),
            "path": layout["preregistration_path"],
            "sha256": "sha256:" + hashlib.sha256(prereg_bytes).hexdigest(),
        },
        "python": {
            "bytes": toolchain["artifacts"]["python"]["bytes"],
            "path": toolchain["artifacts"]["python"]["resolved_path"],
            "sha256": toolchain["artifacts"]["python"]["sha256"],
        },
        "runner": {
            "bytes": source_bindings[BOUND_SOURCE_FILES[1]]["bytes"],
            "path": layout["runner_path"],
            "sha256": source_bindings[BOUND_SOURCE_FILES[1]]["sha256"],
        },
    }
    if (
        roles != expected_roles
        or attestation["schema_version"] != native.get("native_receipt_schema")
        or attestation["run_id"] != prereg.get("run_id")
        or attestation["entries_verified"] != len(native["static_manifest_records"]) + 1
        or native.get("fixed_fd_map") != EXPECTED_NATIVE_PREFLIGHT_FIXED_FD_MAP
        or attestation.get("fixed_fds") != native["fixed_fd_map"]
        or attestation.get("outer_env_observed") is not True
        or attestation.get("outer_environment_sha256")
        != outer_launch.get("outer_environment_sha256")
        or outer_environment != {}
        or any(name.startswith("LD_") for name in outer_environment)
        or attestation.get("python_pycache_prefix")
        != native.get("python_pycache_prefix")
        or attestation.get("python_pycache_prefix_absent") is not True
        or os.path.lexists(native.get("python_pycache_prefix", ""))
    ):
        raise AcquisitionError("native_preflight_attestation_binding_mismatch")
    revalidate_inherited_path_binding(
        layout["manifest_path"],
        NATIVE_PREFLIGHT_MANIFEST_FD,
        _NATIVE_PREFLIGHT_MANIFEST_IDENTITY,
        "manifest",
    )
    revalidate_inherited_path_binding(
        layout["preregistration_path"],
        NATIVE_PREFLIGHT_PREREGISTRATION_FD,
        _NATIVE_PREFLIGHT_PREREGISTRATION_IDENTITY,
        "preregistration",
    )
    return {
        "schema_version": attestation["schema_version"],
        "manifest_sha256": attestation["manifest_sha256"],
        "manifest_bytes": len(expected_manifest),
        "native_maps_root_sha256": attestation["native_maps_root_sha256"],
        "entries_verified": attestation["entries_verified"],
        "passes_completed": attestation["passes_completed"],
        "same_pid_execveat_verified": True,
        "sealed_memfd_attestation_verified": True,
        "fixed_fd_map": dict(attestation["fixed_fds"]),
        "fixed_fd_map_matches_preregistration": True,
        "outer_env_observed": True,
        "outer_environment_sha256": attestation["outer_environment_sha256"],
        "outer_launch_contract_sha256": native["outer_launch_sha256"],
        "outer_launcher_argv_preregistered": True,
        "helper_dependency_swap_safety_claimed": False,
        "security_ceiling": attestation["security_ceiling"],
        "validated_before_candidate_preparation_and_execution_claim": True,
    }


def revalidate_inherited_path_binding(
    path_text: str,
    fd: int,
    expected_identity: tuple[int, ...],
    role: str,
) -> None:
    reopened_fd = -1
    try:
        reopened_fd = open_absolute_regular_nofollow(path_text)
        path_info = os.fstat(reopened_fd)
        fd_info = os.fstat(fd)
    except OSError as error:
        raise AcquisitionError(f"native_{role}_path_revalidation_failed") from error
    finally:
        if reopened_fd >= 0:
            os.close(reopened_fd)
    if (
        stat_identity(path_info) != expected_identity
        or stat_identity(fd_info) != expected_identity
        or stat.S_IMODE(path_info.st_mode) != 0o600
        or stat.S_IMODE(fd_info.st_mode) != 0o600
        or path_info.st_uid != os.geteuid()
        or fd_info.st_uid != os.geteuid()
        or path_info.st_gid != os.getegid()
        or fd_info.st_gid != os.getegid()
        or path_info.st_nlink != 1
        or fd_info.st_nlink != 1
    ):
        raise AcquisitionError(f"native_{role}_path_binding_changed")


def validate_network_policy(
    prereg: Mapping[str, Any], contract: Mapping[str, Any]
) -> None:
    expected = {
        "allowed_https_hosts": [
            "apps.usgs.gov",
            "ftp.ebi.ac.uk",
            "github-cloud.s3.amazonaws.com",
            "github.com",
            "lod.nal.usda.gov",
            "objects.githubusercontent.com",
            "raw.githubusercontent.com",
            "release.geneontology.org",
            "wordnetcode.princeton.edu",
            "www.siyavula.com",
        ],
        "cleartext_transport_allowed": False,
        "curl_resume_allowed": False,
        "direct_source_pre_and_post_metadata_required": True,
        "git_protocol": "https_only_exact_commit_sparse_fetch",
        "redirect_hops_must_remain_allowlisted_https": True,
    }
    if prereg.get("network_policy") != expected:
        raise AcquisitionError("network_policy_mismatch")
    allowed_hosts = frozenset(expected["allowed_https_hosts"])
    for spec in contract["direct_sources"]:
        validate_https_url(spec["url"], allowed_hosts)
    for spec in contract["git_sources"]:
        validate_https_url(spec["clone_url"], allowed_hosts)


def validate_transaction_policy(prereg: Mapping[str, Any]) -> None:
    expected_transaction = {
        "execution_claim_publication": (
            "canonical_empty_candidate_fsync_then_stable_package_anchor_"
            "run_keyed_O_EXCL_claim_last"
        ),
        "execution_claim_replay_allowed": False,
        "claim_only_disposition": "blocked_incomplete_nonreplayable",
        "terminal_success": "canonical_receipt_bound_COMPLETE_O_EXCL_fsync_last",
        "terminal_abort": (
            "stable_package_anchor_run_keyed_ABORT_O_EXCL_without_source_root_pass"
        ),
        "partial_claim_blocks_replay": True,
        "preclaim_orphan_reconciliation": (
            "exact_empty_owner_only_adopt_else_stable_ABORT"
        ),
        "control_anchor": str(PHONE_PACKAGE_ROOT),
        "exclusive_Termux_UID_operational_assumption": True,
        "concurrent_same_UID_writer_allowed": False,
        "malicious_same_UID_tamper_resistance_claimed": False,
        "package_reset_or_uninstall_invalidates_local_control_anchor": True,
    }
    if prereg.get("transaction_policy") != expected_transaction:
        raise AcquisitionError("transaction_policy_mismatch")
    expected_resources = {
        "phone_adb_serial_sha256": EXPECTED_ADB_SERIAL_SHA256,
        "phone_model": "NX789J",
        "phone_soc": "SM8750",
        "runpod": "not_used_for_this_action",
        "github_repository": "Zer0pa/Polymath-AI",
        "huggingface_visibility": "private_revision_pinned_C4_COM_only",
        "comet_payload": "hash_bound_metadata_only",
        "public_release": False,
    }
    if prereg.get("resource_slice") != expected_resources:
        raise AcquisitionError("resource_slice_mismatch")
    if prereg.get("source_checkout_policy") != (
        "git_HEAD_equals_source_commit_and_bound_files_match_blob_oid_bytes_sha256"
    ):
        raise AcquisitionError("source_checkout_policy_mismatch")
    expected_custody = {
        "C4_COM_and_C4_RX_roots_separate": True,
        "aggregate_hash_bound_receipt_egress": True,
        "execution_plane": "phone_private",
        "Mac_raw_cache": False,
        "private_HF_mirror": "deferred_until_source_root_passes_then_revision_pinned",
        "raw_payload_egress": False,
    }
    if prereg.get("custody") != expected_custody:
        raise AcquisitionError("custody_contract_mismatch")
    expected_nonclaims = [
        "not_semantic_material_compilation",
        "not_near_semantic_Arm_C",
        "not_connected_split_or_exposure_ledger",
        "not_C3_dictionary_or_C4_syllabus_admission",
        "not_CUR_0S_or_CUR_0P_or_composite_CUR_0",
        "not_target_data_learning_or_authority",
    ]
    if prereg.get("nonclaims") != expected_nonclaims:
        raise AcquisitionError("nonclaims_contract_mismatch")


def validate_campaign_lease(
    prereg: Mapping[str, Any], *, now: datetime | None = None
) -> CampaignLease:
    lease = prereg.get("campaign_lease")
    if not isinstance(lease, dict):
        raise AcquisitionError("campaign_lease_missing")
    expected_keys = {
        "lease_id",
        "action_id",
        "state",
        "issued_at_utc",
        "expires_at_utc",
        "additional_paid_capacity",
        "max_phone_execution_count",
        "phone_execution_count_before",
        "max_wall_seconds",
        "terminalization_reserve_seconds",
        "max_private_output_bytes",
        "min_free_storage_bytes",
        "thermal_safety_contract",
        "thermal_sample_interval_seconds",
    }
    if set(lease) != expected_keys:
        raise AcquisitionError("campaign_lease_field_set_mismatch")
    if lease["lease_id"] != "current_user_sovereign_frontier_campaign_20260712":
        raise AcquisitionError("campaign_lease_id_mismatch")
    if lease["action_id"] != prereg.get("run_id"):
        raise AcquisitionError("campaign_lease_action_mismatch")
    if lease["state"] != "active" or lease["additional_paid_capacity"] is not False:
        raise AcquisitionError("campaign_lease_state_mismatch")
    expected_integers = {
        "max_phone_execution_count": 1,
        "phone_execution_count_before": 0,
        "max_wall_seconds": 7200,
        "terminalization_reserve_seconds": TERMINALIZATION_RESERVE_SECONDS,
        "max_private_output_bytes": 2_147_483_648,
        "min_free_storage_bytes": 10_737_418_240,
        "thermal_sample_interval_seconds": 5,
    }
    for field, expected in expected_integers.items():
        if type(lease[field]) is not int or lease[field] != expected:
            raise AcquisitionError(f"campaign_lease_{field}_mismatch")
    thermal_contract = lease["thermal_safety_contract"]
    expected_thermal_contract = phone_thermal_safety_contract()
    if thermal_contract != expected_thermal_contract:
        raise AcquisitionError("campaign_lease_thermal_contract_mismatch")
    issued_at = parse_utc_second(lease["issued_at_utc"], "campaign_lease_issued_at")
    expires_at = parse_utc_second(lease["expires_at_utc"], "campaign_lease_expires_at")
    current = now or datetime.now(timezone.utc)
    if expires_at <= issued_at:
        raise AcquisitionError("campaign_lease_nonpositive_duration")
    if (expires_at - issued_at).total_seconds() > 4 * 60 * 60:
        raise AcquisitionError("campaign_lease_duration_exceeds_four_hours")
    if issued_at > current:
        raise AcquisitionError("campaign_lease_not_yet_active")
    if current >= expires_at:
        raise AcquisitionError("campaign_lease_expired")
    return CampaignLease(
        lease_id=lease["lease_id"],
        action_id=lease["action_id"],
        issued_at=issued_at,
        expires_at=expires_at,
        max_wall_seconds=lease["max_wall_seconds"],
        terminalization_reserve_seconds=lease["terminalization_reserve_seconds"],
        max_private_output_bytes=lease["max_private_output_bytes"],
        min_free_storage_bytes=lease["min_free_storage_bytes"],
        thermal_safety_contract=thermal_contract,
        thermal_sample_interval_seconds=lease["thermal_sample_interval_seconds"],
    )


def validate_governing_inputs(prereg: Mapping[str, Any]) -> None:
    expected = {
        "PRD_sha256": "sha256:725d0ad6ac77fdcfc06a2635c7552cc414e0ed48f30fbd0f7f7ec38720493a3c",
        "living_concept_sha256": "sha256:b2f617766b660237ddfd329c6b7fa2370f9a2641983e71915b4cd71c6d31bacc",
        "corpus_audit_sha256": "sha256:c3a5d5eacf424f6e50ae0a170873d1c80e566581e22031a8f64bc899f8eec0fa",
    }
    if prereg.get("governing_inputs") != expected:
        raise AcquisitionError("governing_inputs_mismatch")


def guard_phone_environment() -> dict[str, Any]:
    preimport_phone_guard()
    actual = {
        "model": getprop("ro.product.model"),
        "device": getprop("ro.product.device"),
        "soc": getprop("ro.soc.model"),
        "architecture": platform.machine(),
        "python_platform_system": platform.system(),
        "private_home": str(Path.home()),
        "build_fingerprint_sha256": "sha256:"
        + hashlib.sha256(getprop_raw("ro.build.fingerprint")).hexdigest(),
    }
    if (actual["model"], actual["device"], actual["soc"]) != (
        "NX789J",
        "NX789J",
        "SM8750",
    ):
        raise AcquisitionError("live_phone_identity_mismatch")
    return actual


def mode_identity(info: os.stat_result) -> str:
    return f"{stat.S_IMODE(info.st_mode):04o}"


def open_absolute_regular_nofollow(path_text: str) -> int:
    """Open an absolute regular file without following any path component."""

    path = Path(path_text)
    if (
        not path.is_absolute()
        or str(path) != path_text
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts[1:])
    ):
        raise AcquisitionError("toolchain_path_not_canonical_absolute")
    current_fd = os.open(
        "/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    )
    try:
        for component in path.parts[1:-1]:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
        result = os.open(
            path.parts[-1],
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=current_fd,
        )
        if not stat.S_ISREG(os.fstat(result).st_mode):
            os.close(result)
            raise AcquisitionError("toolchain_resolved_entry_not_regular")
        return result
    except OSError as error:
        raise AcquisitionError("toolchain_secure_open_failed") from error
    finally:
        os.close(current_fd)


def validate_elf_aarch64(fd: int, expected: Mapping[str, Any] | None) -> None:
    if expected is None:
        return
    if expected != {
        "class_bits": 64,
        "data_encoding": "little_endian",
        "machine": "AArch64",
    }:
        raise AcquisitionError("toolchain_ELF_contract_invalid")
    os.lseek(fd, 0, os.SEEK_SET)
    header = os.read(fd, 20)
    if (
        len(header) != 20
        or header[:4] != b"\x7fELF"
        or header[4] != 2
        or header[5] != 1
        or int.from_bytes(header[18:20], "little") != 183
    ):
        raise AcquisitionError("toolchain_ELF_identity_mismatch")


def attest_toolchain_artifact(
    role: str, expected: Mapping[str, Any]
) -> tuple[int, ...]:
    expected_fields = {
        "literal_path",
        "literal_entry_type",
        "literal_mode",
        "literal_uid",
        "literal_gid",
        "literal_nlink",
        "literal_symlink_target",
        "resolved_path",
        "resolved_entry_type",
        "resolved_mode",
        "resolved_uid",
        "resolved_gid",
        "resolved_nlink",
        "bytes",
        "sha256",
        "elf_identity",
    }
    if not isinstance(expected, Mapping) or set(expected) != expected_fields:
        raise AcquisitionError(f"toolchain_artifact_schema_mismatch:{role}")
    literal_path = expected["literal_path"]
    resolved_path = expected["resolved_path"]
    if not isinstance(literal_path, str) or not isinstance(resolved_path, str):
        raise AcquisitionError(f"toolchain_artifact_path_invalid:{role}")
    try:
        literal = os.lstat(literal_path)
    except OSError as error:
        raise AcquisitionError(f"toolchain_literal_lstat_failed:{role}") from error
    literal_type = expected["literal_entry_type"]
    if literal_type == "symbolic_link":
        if not stat.S_ISLNK(literal.st_mode):
            raise AcquisitionError(f"toolchain_literal_type_mismatch:{role}")
        try:
            observed_target = os.readlink(literal_path)
        except OSError as error:
            raise AcquisitionError(f"toolchain_symlink_read_failed:{role}") from error
        if observed_target != expected["literal_symlink_target"]:
            raise AcquisitionError(f"toolchain_symlink_target_mismatch:{role}")
    elif literal_type == "regular_file":
        if not stat.S_ISREG(literal.st_mode):
            raise AcquisitionError(f"toolchain_literal_type_mismatch:{role}")
        if expected["literal_symlink_target"] is not None:
            raise AcquisitionError(f"toolchain_symlink_contract_mismatch:{role}")
    else:
        raise AcquisitionError(f"toolchain_literal_type_invalid:{role}")
    if (
        mode_identity(literal) != expected["literal_mode"]
        or literal.st_uid != expected["literal_uid"]
        or literal.st_gid != expected["literal_gid"]
        or literal.st_nlink != expected["literal_nlink"]
    ):
        raise AcquisitionError(f"toolchain_literal_stat_mismatch:{role}")
    if os.path.realpath(literal_path) != resolved_path:
        raise AcquisitionError(f"toolchain_resolved_path_mismatch:{role}")

    fd = open_absolute_regular_nofollow(resolved_path)
    try:
        initial = os.fstat(fd)
        if (
            expected["resolved_entry_type"] != "regular_file"
            or not stat.S_ISREG(initial.st_mode)
            or mode_identity(initial) != expected["resolved_mode"]
            or initial.st_uid != expected["resolved_uid"]
            or initial.st_gid != expected["resolved_gid"]
            or initial.st_nlink != expected["resolved_nlink"]
            or initial.st_size != expected["bytes"]
        ):
            raise AcquisitionError(f"toolchain_resolved_stat_mismatch:{role}")
        digest, size = hash_fd(fd)
        if digest != expected["sha256"] or size != expected["bytes"]:
            raise AcquisitionError(f"toolchain_hash_mismatch:{role}")
        validate_elf_aarch64(fd, expected["elf_identity"])
        final = os.fstat(fd)
        if stat_identity(initial) != stat_identity(final):
            raise AcquisitionError(f"toolchain_changed_during_attestation:{role}")
        return stat_identity(final)
    finally:
        os.close(fd)


def open_absolute_directory_nofollow(path_text: str) -> int:
    path = Path(path_text)
    if not path.is_absolute() or str(path) != path_text:
        raise AcquisitionError("toolchain_tree_path_not_canonical_absolute")
    current_fd = os.open(
        "/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    )
    try:
        for component in path.parts[1:]:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
        result = current_fd
        current_fd = -1
        return result
    except OSError as error:
        raise AcquisitionError("toolchain_tree_secure_open_failed") from error
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def attest_python_stdlib_tree(expected: Mapping[str, Any]) -> tuple[int, ...]:
    expected_fields = {
        "root_path",
        "root_mode",
        "root_uid",
        "root_gid",
        "root_nlink",
        "entry_count",
        "regular_bytes",
        "root_sha256",
        "canonicalization",
    }
    if not isinstance(expected, Mapping) or set(expected) != expected_fields:
        raise AcquisitionError("python_stdlib_tree_schema_mismatch")
    if expected["canonicalization"] != (
        "sorted_relative_POSIX_paths_canonical_JSON_type_mode_"
        "regular_bytes_sha256_source_only_excluding_root_site_packages_"
        "all_pycache_and_pyc_reject_external_symlinks_root_excluded"
    ):
        raise AcquisitionError("python_stdlib_tree_canonicalization_mismatch")
    root_fd = open_absolute_directory_nofollow(expected["root_path"])
    try:
        initial_root = os.fstat(root_fd)
        if (
            not stat.S_ISDIR(initial_root.st_mode)
            or mode_identity(initial_root) != expected["root_mode"]
            or initial_root.st_uid != expected["root_uid"]
            or initial_root.st_gid != expected["root_gid"]
            or initial_root.st_nlink != expected["root_nlink"]
        ):
            raise AcquisitionError("python_stdlib_tree_root_stat_mismatch")
        records: list[dict[str, Any]] = []
        regular_bytes = 0
        try:
            walk = os.fwalk(
                ".",
                topdown=True,
                follow_symlinks=False,
                dir_fd=root_fd,
            )
            for current, directory_names, file_names, directory_fd in walk:
                directory_names[:] = sorted(
                    name
                    for name in directory_names
                    if name != "__pycache__"
                    and not (current == "." and name == "site-packages")
                )
                file_names.sort()
                for name in (*directory_names, *file_names):
                    relative = str(PurePosixPath(current, name))
                    if relative.startswith("./"):
                        relative = relative[2:]
                    info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                    mode = mode_identity(info)
                    if name.endswith(".pyc"):
                        if not stat.S_ISREG(info.st_mode):
                            raise AcquisitionError(
                                "python_stdlib_excluded_pyc_not_regular"
                            )
                        continue
                    if stat.S_ISDIR(info.st_mode):
                        records.append(
                            {
                                "relative_path": relative,
                                "type": "directory",
                                "mode": mode,
                            }
                        )
                        continue
                    if stat.S_ISLNK(info.st_mode):
                        target = os.readlink(name, dir_fd=directory_fd)
                        if not stdlib_symlink_is_internal(relative, target):
                            raise AcquisitionError(
                                "python_stdlib_external_symlink_forbidden"
                            )
                        records.append(
                            {
                                "relative_path": relative,
                                "type": "symlink",
                                "mode": mode,
                                "target": target,
                            }
                        )
                        continue
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise AcquisitionError("python_stdlib_tree_unsafe_entry")
                    fd = os.open(
                        name,
                        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                        dir_fd=directory_fd,
                    )
                    try:
                        opened = os.fstat(fd)
                        if stat_identity(info) != stat_identity(opened):
                            raise AcquisitionError("python_stdlib_tree_entry_replaced")
                        digest, size = hash_fd(fd)
                        if stat_identity(opened) != stat_identity(os.fstat(fd)):
                            raise AcquisitionError("python_stdlib_tree_entry_changed")
                    finally:
                        os.close(fd)
                    regular_bytes += size
                    records.append(
                        {
                            "relative_path": relative,
                            "type": "regular",
                            "mode": mode,
                            "bytes": size,
                            "sha256": digest.removeprefix("sha256:"),
                        }
                    )
        except OSError as error:
            raise AcquisitionError("python_stdlib_tree_walk_failed") from error
        records.sort(key=lambda item: item["relative_path"])
        observed_root = (
            "sha256:" + hashlib.sha256(canonical_json_bytes(records)).hexdigest()
        )
        if (
            len(records) != expected["entry_count"]
            or regular_bytes != expected["regular_bytes"]
            or observed_root != expected["root_sha256"]
        ):
            raise AcquisitionError("python_stdlib_tree_identity_mismatch")
        final_root = os.fstat(root_fd)
        if stat_identity(initial_root) != stat_identity(final_root):
            raise AcquisitionError("python_stdlib_tree_root_changed")
        return stat_identity(final_root)
    finally:
        os.close(root_fd)


def stdlib_symlink_is_internal(relative_path: str, target: str) -> bool:
    if not target or "\x00" in target or target.startswith("/"):
        return False
    components: list[str] = []
    for component in (
        *PurePosixPath(relative_path).parent.parts,
        *PurePosixPath(target).parts,
    ):
        if component in {"", "."}:
            continue
        if component == "..":
            if not components:
                return False
            components.pop()
            continue
        components.append(component)
    return bool(components)


def read_proc_self_maps(limit: int = 2 * 1024 * 1024) -> bytes:
    try:
        fd = os.open(
            "/proc/self/maps",
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
    except OSError as error:
        raise AcquisitionError("proc_self_maps_open_failed") from error
    try:
        payload = bytearray()
        while True:
            chunk = os.read(fd, min(64 * 1024, limit + 1 - len(payload)))
            if not chunk:
                break
            payload.extend(chunk)
            if len(payload) > limit:
                raise AcquisitionError("proc_self_maps_oversize")
        return bytes(payload)
    finally:
        os.close(fd)


def parse_proc_maps(payload: bytes) -> list[dict[str, Any]]:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise AcquisitionError("proc_self_maps_encoding_invalid") from None
    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        fields = line.split(None, 5)
        if len(fields) < 5:
            raise AcquisitionError("proc_self_maps_record_invalid")
        address, permissions, offset, device, inode_text = fields[:5]
        path = fields[5] if len(fields) == 6 else ""
        try:
            start_text, end_text = address.split("-", 1)
            major_text, minor_text = device.split(":", 1)
            record = {
                "start": int(start_text, 16),
                "end": int(end_text, 16),
                "permissions": permissions,
                "offset": int(offset, 16),
                "device_major": int(major_text, 16),
                "device_minor": int(minor_text, 16),
                "inode": int(inode_text),
                "path": path,
            }
        except (TypeError, ValueError):
            raise AcquisitionError("proc_self_maps_record_invalid") from None
        if (
            record["start"] >= record["end"]
            or len(permissions) != 4
            or any(
                permissions[index] not in allowed
                for index, allowed in enumerate(("r-", "w-", "x-", "ps"))
            )
        ):
            raise AcquisitionError("proc_self_maps_record_invalid")
        records.append(record)
    if not records:
        raise AcquisitionError("proc_self_maps_empty")
    return records


def current_python_runtime_snapshot() -> dict[str, Any]:
    observed = observe_python_startup_identity()
    observed["initial_sys_path"] = list(sys.path)
    return observed


def canonical_runtime_path(value: Any) -> str:
    if not isinstance(value, str):
        raise AcquisitionError("python_module_origin_path_invalid")
    path = PurePosixPath(value)
    if (
        not path.is_absolute()
        or str(path) != value
        or any(component in {".", ".."} for component in path.parts)
        or "\x00" in value
    ):
        raise AcquisitionError("python_module_origin_path_invalid")
    return value


def loaded_python_module_origin_records(pycache_prefix: str) -> list[dict[str, Any]]:
    stdlib_root = f"{EXPECTED_PYTHON_PREFIX}/lib/python3.13"
    extension_root = f"{stdlib_root}/lib-dynload"
    held_sources = {
        "__main__": RUNNER_EXECUTION_PATH,
        "_cur0s_commercial_sources_bound": str(ROOT / BOUND_SOURCE_FILES[0]),
    }
    records: list[dict[str, Any]] = []
    for name, module in sorted(sys.modules.items()):
        if module is None:
            continue
        specification = getattr(module, "__spec__", None)
        if specification is None:
            origin = getattr(module, "__file__", None)
            if held_sources.get(name) != origin:
                raise AcquisitionError("python_module_without_spec_not_admitted")
            records.append(
                {
                    "cached": None,
                    "loader": "explicit_held_source",
                    "name": name,
                    "origin": origin,
                    "origin_kind": "held_source",
                }
            )
            continue
        loader = specification.loader
        if isinstance(loader, type):
            loader_name = f"{loader.__module__}.{loader.__qualname__}"
        elif loader is None:
            loader_name = None
        else:
            loader_type = type(loader)
            loader_name = f"{loader_type.__module__}.{loader_type.__qualname__}"
        if loader_name is not None and loader_name.endswith(".SourcelessFileLoader"):
            raise AcquisitionError("python_sourceless_file_loader_forbidden")
        origin = specification.origin
        cached = specification.cached
        if origin in {"built-in", "frozen"}:
            if cached is not None:
                raise AcquisitionError("python_builtin_or_frozen_module_cached")
            origin_kind = origin.replace("-", "_")
        elif origin is None:
            if specification.submodule_search_locations is None or cached is not None:
                raise AcquisitionError("python_namespace_module_identity_invalid")
            locations = [
                canonical_runtime_path(location)
                for location in specification.submodule_search_locations
            ]
            if any(
                not location.startswith(stdlib_root + "/") for location in locations
            ):
                raise AcquisitionError("python_namespace_module_outside_stdlib")
            origin_kind = "namespace"
            origin = "namespace:" + ":".join(locations)
        else:
            origin = canonical_runtime_path(origin)
            if (
                origin.endswith(".pyc")
                or "/__pycache__/" in origin
                or origin.startswith(f"{stdlib_root}/site-packages/")
            ):
                raise AcquisitionError("python_module_origin_not_source_only")
            information = os.stat(origin, follow_symlinks=False)
            if not stat.S_ISREG(information.st_mode) or information.st_nlink != 1:
                raise AcquisitionError("python_module_origin_file_identity_invalid")
            if origin.startswith(extension_root + "/") and origin.endswith(".so"):
                if loader_name is None or not loader_name.endswith(
                    ".ExtensionFileLoader"
                ):
                    raise AcquisitionError("python_extension_loader_identity_invalid")
                if cached is not None:
                    raise AcquisitionError("python_extension_module_cached")
                origin_kind = "stdlib_extension"
            elif origin.startswith(stdlib_root + "/") and origin.endswith(".py"):
                if loader_name is None or not loader_name.endswith(".SourceFileLoader"):
                    raise AcquisitionError("python_source_loader_identity_invalid")
                if not isinstance(cached, str) or not cached.startswith(
                    pycache_prefix + "/"
                ):
                    raise AcquisitionError("python_source_cached_path_not_quarantined")
                canonical_runtime_path(cached)
                origin_kind = "stdlib_source"
            else:
                raise AcquisitionError("python_module_origin_outside_admitted_roots")
        records.append(
            {
                "cached": cached,
                "loader": loader_name,
                "name": name,
                "origin": origin,
                "origin_kind": origin_kind,
            }
        )
    if set(held_sources) - {record["name"] for record in records}:
        raise AcquisitionError("python_held_module_origin_missing")
    return records


def validate_sanitized_python_runtime(expected: Mapping[str, Any]) -> None:
    if not isinstance(expected, Mapping):
        raise AcquisitionError("python_runtime_contract_invalid")
    observed = current_python_runtime_snapshot()
    field_pairs = {
        "sys_executable": "sys_executable",
        "base_executable": "base_executable",
        "prefix": "prefix",
        "base_prefix": "base_prefix",
        "exec_prefix": "exec_prefix",
        "base_exec_prefix": "base_exec_prefix",
        "sys_flags": "sys_flags",
        "environment": "launch_environment",
    }
    for observed_field, expected_field in field_pairs.items():
        if observed[observed_field] != expected.get(expected_field):
            raise AcquisitionError(f"current_python_{observed_field}_mismatch")
    if observed["real_executable"] != expected.get("proc_self_exe"):
        raise AcquisitionError("current_python_real_executable_mismatch")
    if observed["initial_sys_path"] != expected.get("sanitized_sys_path"):
        raise AcquisitionError("current_python_sys_path_mismatch")
    orig_argv = observed["orig_argv"]
    try:
        pycache_prefix = runner_pycache_prefix_from_orig_argv(orig_argv)
    except BootstrapError as error:
        raise AcquisitionError("current_python_orig_argv_mismatch") from error
    expected_prefix = [
        expected["sys_executable"],
        "-IBS",
        "-X",
        f"pycache_prefix={pycache_prefix}",
        RUNNER_EXECUTION_PATH,
    ]
    if (
        orig_argv[:5] != expected_prefix
        or len(orig_argv) != 11
        or observed["xoptions"] != {"pycache_prefix": str(pycache_prefix)}
        or observed["pycache_prefix"] != str(pycache_prefix)
        or expected.get("pycache_prefix_policy") != "run_scoped_verified_absent"
        or os.path.lexists(pycache_prefix)
    ):
        raise AcquisitionError("current_python_orig_argv_mismatch")
    for absent in expected.get("absent_sys_path_entries", []):
        if os.path.lexists(absent):
            raise AcquisitionError("current_python_absent_path_appeared")


def map_device(record: Mapping[str, Any]) -> int:
    return os.makedev(record["device_major"], record["device_minor"])


def attest_current_python_process(
    runtime: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
    volatile: Mapping[str, tuple[int, ...]],
) -> dict[str, Any]:
    validate_sanitized_python_runtime(runtime)
    try:
        pycache_prefix = runner_pycache_prefix_from_orig_argv(list(sys.orig_argv))
    except BootstrapError as error:
        raise AcquisitionError("current_python_orig_argv_mismatch") from error
    module_origins = loaded_python_module_origin_records(str(pycache_prefix))
    try:
        proc_exe_target = os.readlink("/proc/self/exe")
        proc_exe_fd = os.open("/proc/self/exe", os.O_RDONLY | os.O_CLOEXEC)
    except OSError as error:
        raise AcquisitionError("proc_self_exe_open_failed") from error
    try:
        proc_exe = os.fstat(proc_exe_fd)
        if proc_exe_target != runtime["proc_self_exe"] or stat_identity(
            proc_exe
        ) != volatile.get("python"):
            raise AcquisitionError("current_python_proc_exe_identity_mismatch")
        digest, size = hash_fd(proc_exe_fd)
        python_artifact = artifacts["python"]
        if (
            digest != python_artifact["sha256"]
            or size != python_artifact["bytes"]
            or stat_identity(proc_exe) != stat_identity(os.fstat(proc_exe_fd))
        ):
            raise AcquisitionError("current_python_proc_exe_hash_mismatch")
        validate_elf_aarch64(proc_exe_fd, python_artifact["elf_identity"])
    finally:
        os.close(proc_exe_fd)

    maps_payload = read_proc_self_maps()
    records = parse_proc_maps(maps_payload)
    executable = [record for record in records if "x" in record["permissions"]]
    required_role_values = runtime.get("executable_mapping_artifact_roles")
    expected_extension_paths = runtime.get(
        "executable_mapping_stdlib_extension_paths"
    )
    expected_paths = runtime.get("executable_mapping_expected_paths")
    expected_count = runtime.get("executable_mapping_expected_count")
    if (
        not isinstance(required_role_values, list)
        or required_role_values != sorted(set(required_role_values))
        or not isinstance(expected_extension_paths, list)
        or expected_extension_paths != sorted(set(expected_extension_paths))
        or not isinstance(expected_paths, list)
        or expected_paths != sorted(set(expected_paths))
        or type(expected_count) is not int
        or expected_count != len(expected_paths)
    ):
        raise AcquisitionError("python_executable_mapping_contract_invalid")
    required_roles = set(required_role_values)
    if not required_roles.issubset(artifacts):
        raise AcquisitionError("python_executable_mapping_role_invalid")
    artifact_by_path = {
        artifacts[role]["resolved_path"]: role for role in required_role_values
    }
    if len(artifact_by_path) != len(required_roles):
        raise AcquisitionError("python_executable_mapping_path_duplicate")
    derived_expected_paths = sorted(
        [*artifact_by_path, *expected_extension_paths, "[vdso]"]
    )
    if expected_paths != derived_expected_paths:
        raise AcquisitionError("python_executable_mapping_contract_invalid")
    observed_extension_origins = sorted(
        record["origin"]
        for record in module_origins
        if record["origin_kind"] == "stdlib_extension"
    )
    if observed_extension_origins != expected_extension_paths:
        raise AcquisitionError("python_loaded_extension_closure_mismatch")
    expected_extension_set = set(expected_extension_paths)
    observed_roles: set[str] = set()
    observed_extension_paths: set[str] = set()
    observed_paths: list[str] = []
    canonical_executable: list[dict[str, Any]] = []
    for record in executable:
        path = record["path"]
        observed_paths.append(path)
        if path == "[vdso]":
            if (
                record["permissions"] != "r-xp"
                or record["offset"] != 0
                or record["device_major"] != 0
                or record["device_minor"] != 0
                or record["inode"] != 0
            ):
                raise AcquisitionError("python_vdso_mapping_identity_invalid")
            canonical_executable.append(
                {
                    "permissions": record["permissions"],
                    "offset": record["offset"],
                    "device_major": record["device_major"],
                    "device_minor": record["device_minor"],
                    "inode": record["inode"],
                    "path": path,
                }
            )
            continue
        if not path.startswith("/") or path.endswith(" (deleted)"):
            raise AcquisitionError("unapproved_executable_mapping")
        if record["permissions"] != "r-xp":
            raise AcquisitionError("python_executable_mapping_permissions_invalid")
        role = artifact_by_path.get(path)
        if role is not None:
            identity = volatile[role]
            if map_device(record) != identity[0] or record["inode"] != identity[1]:
                raise AcquisitionError(f"executable_mapping_inode_mismatch:{role}")
            observed_roles.add(role)
        elif path in expected_extension_set:
            try:
                entry = os.stat(path, follow_symlinks=False)
            except OSError as error:
                raise AcquisitionError(
                    "stdlib_executable_mapping_stat_failed"
                ) from error
            if (
                not stat.S_ISREG(entry.st_mode)
                or entry.st_nlink != 1
                or entry.st_dev != map_device(record)
                or entry.st_ino != record["inode"]
            ):
                raise AcquisitionError("stdlib_executable_mapping_inode_mismatch")
            observed_extension_paths.add(path)
        else:
            raise AcquisitionError(f"unapproved_executable_mapping:{path}")
        canonical_executable.append(
            {
                "permissions": record["permissions"],
                "offset": record["offset"],
                "device_major": record["device_major"],
                "device_minor": record["device_minor"],
                "inode": record["inode"],
                "path": path,
            }
        )
    if observed_roles != required_roles:
        raise AcquisitionError("required_python_executable_mapping_missing")
    if observed_extension_paths != expected_extension_set:
        raise AcquisitionError("required_python_extension_mapping_missing")
    if len(observed_paths) != len(set(observed_paths)):
        raise AcquisitionError("python_executable_mapping_duplicate")
    if sorted(observed_paths) != expected_paths or len(observed_paths) != expected_count:
        raise AcquisitionError("python_executable_mapping_closure_mismatch")
    return {
        "proc_self_exe_sha256": artifacts["python"]["sha256"],
        "proc_self_exe_volatile_identity": list(volatile["python"]),
        "executable_mapping_count": len(canonical_executable),
        "executable_mappings_sha256": canonical_sha256(canonical_executable),
        "executable_mappings": canonical_executable,
        "isolated_startup_verified": True,
        "loaded_module_origin_count": len(module_origins),
        "loaded_module_origins": module_origins,
        "loaded_module_origins_sha256": canonical_sha256(module_origins),
        "pycache_prefix": str(pycache_prefix),
        "pycache_prefix_absent": True,
        "sys_xoptions": {"pycache_prefix": str(pycache_prefix)},
        "unexpected_executable_file_mappings_absent": True,
    }


def run_toolchain_probe(
    role: str,
    expected: Mapping[str, Any],
    environments: Mapping[str, Mapping[str, str]],
    artifacts: Mapping[str, Mapping[str, Any]],
    volatile_identities: Mapping[str, tuple[int, ...]],
) -> None:
    expected_fields = {
        "argv",
        "environment",
        "returncode",
        "stdout_bytes",
        "stdout_sha256",
        "stderr_bytes",
        "stderr_sha256",
    }
    if not isinstance(expected, Mapping) or set(expected) != expected_fields:
        raise AcquisitionError(f"toolchain_probe_schema_mismatch:{role}")
    environment_name = expected["environment"]
    if environment_name not in environments:
        raise AcquisitionError(f"toolchain_probe_environment_invalid:{role}")
    argv = expected["argv"]
    if (
        not isinstance(argv, list)
        or not argv
        or any(not isinstance(item, str) or "\x00" in item for item in argv)
    ):
        raise AcquisitionError(f"toolchain_probe_argv_invalid:{role}")
    placeholder = "pycache_prefix=$RUN_SCOPED_PYCACHE_PREFIX"
    placeholder_count = argv.count(placeholder)
    if placeholder_count not in {0, 1} or (
        placeholder_count == 1 and role != "python_version"
    ):
        raise AcquisitionError(f"toolchain_probe_pycache_placeholder_invalid:{role}")
    resolved_argv = [
        (
            f"pycache_prefix={sys.pycache_prefix}"
            if argument == placeholder
            else argument
        )
        for argument in argv
    ]
    if placeholder_count == 1 and (
        not isinstance(sys.pycache_prefix, str) or os.path.lexists(sys.pycache_prefix)
    ):
        raise AcquisitionError(f"toolchain_probe_pycache_prefix_invalid:{role}")
    executable_fd = open_attested_executable_fd(
        resolved_argv[0], artifacts, volatile_identities
    )
    try:
        result = subprocess.run(
            resolved_argv,
            executable=str(FD_PATH_ROOT / str(executable_fd)),
            env=dict(environments[environment_name]),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=30,
            check=False,
            pass_fds=(executable_fd,),
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise AcquisitionError(f"toolchain_probe_execution_failed:{role}") from error
    finally:
        os.close(executable_fd)
    if placeholder_count == 1 and os.path.lexists(sys.pycache_prefix):
        raise AcquisitionError(f"toolchain_probe_pycache_prefix_appeared:{role}")
    observed = {
        "returncode": result.returncode,
        "stdout_bytes": len(result.stdout),
        "stdout_sha256": "sha256:" + hashlib.sha256(result.stdout).hexdigest(),
        "stderr_bytes": len(result.stderr),
        "stderr_sha256": "sha256:" + hashlib.sha256(result.stderr).hexdigest(),
    }
    if observed != {key: expected[key] for key in observed}:
        raise AcquisitionError(f"toolchain_probe_identity_mismatch:{role}")


def validate_phone_toolchain(expected: Mapping[str, Any]) -> dict[str, Any]:
    global _ATTESTED_CURRENT_PROCESS_IDENTITY
    global _ATTESTED_TOOLCHAIN_CONTRACT
    global _ATTESTED_TOOLCHAIN_VOLATILE_IDENTITIES
    global _ATTESTED_STDLIB_VOLATILE_IDENTITY

    if expected != phone_toolchain_contract():
        raise AcquisitionError("phone_toolchain_contract_mismatch")
    expected_fields = {
        "schema_version",
        "artifacts",
        "environments",
        "command_probes",
        "python_stdlib_tree",
        "python_runtime",
        "curl_required_options",
        "git_https_child_exec_probe_network_access",
        "runner_python_flags",
        "attestation_timing",
        "toolchain_root_sha256",
    }
    if set(expected) != expected_fields:
        raise AcquisitionError("phone_toolchain_field_set_mismatch")
    if expected["runner_python_flags"] != [
        "-IBS",
        "-X",
        "pycache_prefix=$RUN_SCOPED_PYCACHE_PREFIX",
    ]:
        raise AcquisitionError("phone_toolchain_runner_python_flags_mismatch")
    without_root = dict(expected)
    root = without_root.pop("toolchain_root_sha256")
    if canonical_sha256(without_root) != root:
        raise AcquisitionError("phone_toolchain_root_mismatch")
    artifacts = expected["artifacts"]
    environments = expected["environments"]
    probes = expected["command_probes"]
    if not all(
        isinstance(value, Mapping) for value in (artifacts, environments, probes)
    ):
        raise AcquisitionError("phone_toolchain_nested_contract_invalid")
    if environments != {"base": curl_environment(), "git": git_environment()}:
        raise AcquisitionError("phone_toolchain_environment_drift")
    volatile = {
        role: attest_toolchain_artifact(role, artifact)
        for role, artifact in sorted(artifacts.items())
    }
    stdlib_identity = attest_python_stdlib_tree(expected["python_stdlib_tree"])
    process_identity = attest_current_python_process(
        expected["python_runtime"], artifacts, volatile
    )
    for role, probe in sorted(probes.items()):
        run_toolchain_probe(role, probe, environments, artifacts, volatile)
    for role, artifact in sorted(artifacts.items()):
        if attest_toolchain_artifact(role, artifact) != volatile[role]:
            raise AcquisitionError(f"toolchain_changed_across_probes:{role}")
    if (
        attest_current_python_process(expected["python_runtime"], artifacts, volatile)
        != process_identity
    ):
        raise AcquisitionError("current_python_changed_across_probes")
    _ATTESTED_TOOLCHAIN_CONTRACT = dict(expected)
    _ATTESTED_TOOLCHAIN_VOLATILE_IDENTITIES = volatile
    _ATTESTED_STDLIB_VOLATILE_IDENTITY = stdlib_identity
    _ATTESTED_CURRENT_PROCESS_IDENTITY = process_identity
    return {
        "toolchain_root_sha256": root,
        "artifact_count": len(artifacts),
        "artifact_manifest_sha256": canonical_sha256(artifacts),
        "command_probe_count": len(probes),
        "command_probe_manifest_sha256": canonical_sha256(probes),
        "python_stdlib_tree_root_sha256": expected["python_stdlib_tree"]["root_sha256"],
        "python_stdlib_tree_entry_count": expected["python_stdlib_tree"]["entry_count"],
        "python_stdlib_tree_volatile_identity": list(stdlib_identity),
        "current_process_identity_sha256": canonical_sha256(process_identity),
        "current_process_executable_mapping_count": process_identity[
            "executable_mapping_count"
        ],
        "validated_before_candidate_preparation_and_execution_claim": True,
    }


def command_toolchain_roles(executable: str) -> frozenset[str]:
    shared = {
        "android_bionic_libc",
        "android_bionic_libdl",
        "android_bionic_libm",
        "android_linker64",
        "libcrypto",
        "libandroid_posix_semaphore",
        "system_libcxx",
        "system_liblog",
        "system_libnetd_client",
        "libz",
    }
    transport = {
        "ca_certificate_bundle",
        "libbz2",
        "libcurl",
        "libexpat",
        "liblzma",
        "libnghttp2",
        "libnghttp3",
        "libngtcp2",
        "libngtcp2_crypto_ossl",
        "libssh2",
        "libssl",
    }
    if executable == CURL:
        return frozenset({"curl", *shared, *transport})
    if executable == GIT:
        return frozenset(
            {
                "git",
                "git_https_helper",
                "libpcre2",
                "libtermux_exec",
                *shared,
                *transport,
            }
        )
    if executable == GETPROP:
        return frozenset(
            {
                "android_getprop",
                "android_bionic_libc",
                "android_bionic_libdl",
                "android_bionic_libm",
                "android_linker64",
                "system_libbase",
                "system_libcxx",
                "system_liblog",
            }
        )
    raise AcquisitionError("unattested_subprocess_executable")


def open_attested_executable_fd(
    executable: str,
    artifacts: Mapping[str, Mapping[str, Any]] | None = None,
    volatile_identities: Mapping[str, tuple[int, ...]] | None = None,
) -> int:
    """Open the exact attested executable inode that the child must execute."""

    if artifacts is None:
        if _ATTESTED_TOOLCHAIN_CONTRACT is None:
            raise AcquisitionError("phone_toolchain_not_preclaim_attested")
        artifacts = _ATTESTED_TOOLCHAIN_CONTRACT["artifacts"]
    if volatile_identities is None:
        volatile_identities = _ATTESTED_TOOLCHAIN_VOLATILE_IDENTITIES
    matches = [
        (role, artifact)
        for role, artifact in artifacts.items()
        if artifact.get("literal_path") == executable
    ]
    if len(matches) != 1:
        raise AcquisitionError("subprocess_executable_artifact_binding_invalid")
    role, artifact = matches[0]
    expected_identity = volatile_identities.get(role)
    if expected_identity is None:
        raise AcquisitionError("subprocess_executable_identity_missing")
    observed_identity = attest_toolchain_artifact(role, artifact)
    if observed_identity != expected_identity:
        raise AcquisitionError(f"toolchain_replaced_after_attestation:{role}")
    fd = open_absolute_regular_nofollow(artifact["resolved_path"])
    try:
        if stat_identity(os.fstat(fd)) != expected_identity:
            raise AcquisitionError("subprocess_executable_opened_inode_mismatch")
        return fd
    except BaseException:
        os.close(fd)
        raise


def revalidate_attested_toolchain_roles(roles: frozenset[str]) -> None:
    if (
        _ATTESTED_TOOLCHAIN_CONTRACT is None
        or not _ATTESTED_TOOLCHAIN_VOLATILE_IDENTITIES
    ):
        raise AcquisitionError("phone_toolchain_not_preclaim_attested")
    artifacts = _ATTESTED_TOOLCHAIN_CONTRACT["artifacts"]
    if not roles or not roles.issubset(artifacts):
        raise AcquisitionError("toolchain_revalidation_role_invalid")
    for role in sorted(roles):
        observed = attest_toolchain_artifact(role, artifacts[role])
        if observed != _ATTESTED_TOOLCHAIN_VOLATILE_IDENTITIES[role]:
            raise AcquisitionError(f"toolchain_replaced_after_attestation:{role}")


def revalidate_full_phone_toolchain() -> dict[str, Any]:
    if (
        _ATTESTED_TOOLCHAIN_CONTRACT is None
        or _ATTESTED_STDLIB_VOLATILE_IDENTITY is None
        or _ATTESTED_CURRENT_PROCESS_IDENTITY is None
    ):
        raise AcquisitionError("phone_toolchain_not_preclaim_attested")
    roles = frozenset(_ATTESTED_TOOLCHAIN_CONTRACT["artifacts"])
    revalidate_attested_toolchain_roles(roles)
    stdlib = attest_python_stdlib_tree(
        _ATTESTED_TOOLCHAIN_CONTRACT["python_stdlib_tree"]
    )
    if stdlib != _ATTESTED_STDLIB_VOLATILE_IDENTITY:
        raise AcquisitionError("python_stdlib_tree_replaced_after_attestation")
    current_process = attest_current_python_process(
        _ATTESTED_TOOLCHAIN_CONTRACT["python_runtime"],
        _ATTESTED_TOOLCHAIN_CONTRACT["artifacts"],
        _ATTESTED_TOOLCHAIN_VOLATILE_IDENTITIES,
    )
    if current_process != _ATTESTED_CURRENT_PROCESS_IDENTITY:
        raise AcquisitionError("current_python_changed_after_attestation")
    return {
        "toolchain_root_sha256": _ATTESTED_TOOLCHAIN_CONTRACT["toolchain_root_sha256"],
        "artifact_count": len(roles),
        "python_stdlib_tree_root_sha256": _ATTESTED_TOOLCHAIN_CONTRACT[
            "python_stdlib_tree"
        ]["root_sha256"],
        "current_process_identity_sha256": canonical_sha256(current_process),
        "final_revalidation_passed": True,
    }


def validate_phone_runtime(
    prereg: Mapping[str, Any],
    actual: Mapping[str, Any],
    *,
    prevalidated_toolchain: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if prevalidated_toolchain is None:
        raise AcquisitionError("phone_toolchain_must_precede_device_property_use")
    expected = prereg.get("target_device")
    if not isinstance(expected, dict):
        raise AcquisitionError("target_device_missing")
    exact = {
        "adb_serial_sha256": EXPECTED_ADB_SERIAL_SHA256,
        "architecture": "aarch64",
        "build_fingerprint_sha256": EXPECTED_BUILD_FINGERPRINT_SHA256,
        "device": "NX789J",
        "model": "NX789J",
        "private_home": str(PHONE_HOME),
        "python_platform_system": "Android",
        "soc": "SM8750",
    }
    if expected != exact:
        raise AcquisitionError("target_device_contract_mismatch")
    for field in (
        "architecture",
        "build_fingerprint_sha256",
        "device",
        "model",
        "private_home",
        "python_platform_system",
        "soc",
    ):
        if actual[field] != expected[field]:
            raise AcquisitionError(f"live_target_device_{field}_mismatch")
    toolchain_identity = dict(prevalidated_toolchain)
    return {
        "model": actual["model"],
        "device": actual["device"],
        "soc": actual["soc"],
        "architecture": actual["architecture"],
        "python_platform_system": actual["python_platform_system"],
        "private_home_sha256": "sha256:"
        + hashlib.sha256(actual["private_home"].encode("utf-8")).hexdigest(),
        "build_fingerprint_sha256": actual["build_fingerprint_sha256"],
        "adb_serial_sha256": EXPECTED_ADB_SERIAL_SHA256,
        "adb_serial_runtime_visibility": "external_ADB_custody_only",
        "phone_private_runtime_guard_passed": True,
        "phone_toolchain": toolchain_identity,
    }


def validate_private_existing_path(path: Path, role: str) -> Path:
    if not path.is_absolute():
        raise AcquisitionError(f"{role}_must_be_absolute")
    absolute = Path(os.path.abspath(path))
    assert_no_symlink_components(absolute, PHONE_RUN_ROOT)
    assert_owner_only_chain(absolute, PHONE_RUN_ROOT)
    resolved = absolute.resolve(strict=True)
    require_beneath(resolved, PHONE_RUN_ROOT, role)
    if not resolved.is_file():
        raise AcquisitionError(f"{role}_must_be_regular_file")
    require_owner_only(resolved, role)
    return resolved


def validate_private_output_path(path: Path, run_id: str, expected_name: str) -> Path:
    if RUN_ID_RE.fullmatch(run_id) is None:
        raise AcquisitionError("run_id_invalid")
    if not path.is_absolute():
        raise AcquisitionError("output_dir_must_be_absolute")
    absolute = Path(os.path.abspath(path))
    if absolute.name != expected_name or expected_name != "candidate-001":
        raise AcquisitionError("output_directory_name_mismatch")
    parent = absolute.parent.resolve(strict=True)
    required_parent = PHONE_RUN_ROOT / run_id / "candidate_runs"
    if parent != required_parent:
        raise AcquisitionError("output_parent_not_preregistered_candidate_root")
    assert_no_symlink_components(parent, PHONE_RUN_ROOT)
    assert_owner_only_chain(parent, PHONE_RUN_ROOT)
    return parent / absolute.name


def preclaim_resource_check(
    parent: Path, lease: CampaignLease, started_monotonic: float
) -> None:
    elapsed = time.monotonic() - started_monotonic
    if (
        elapsed >= lease.max_wall_seconds
        or datetime.now(timezone.utc) >= lease.expires_at
    ):
        raise OperationalStop("lease_or_wall_deadline_before_claim", "preclaim")
    filesystem = os.statvfs(parent)
    free_bytes = filesystem.f_bavail * filesystem.f_frsize
    expected_payload_bytes = sum(
        source.expected_bytes for source in DIRECT_SOURCES
    ) + sum(source.selected_bytes for source in GIT_SOURCES)
    if expected_payload_bytes + CONTROL_RESERVE_BYTES >= lease.max_private_output_bytes:
        raise AcquisitionError("expected_source_payload_exceeds_output_lease")
    projected_overhead_reserve = 512 * 1024 * 1024
    required_free_bytes = (
        lease.min_free_storage_bytes
        + expected_payload_bytes
        + projected_overhead_reserve
        + CONTROL_RESERVE_BYTES
    )
    if free_bytes < required_free_bytes:
        raise OperationalStop("insufficient_free_storage_before_claim", "preclaim")
    group_maxima, _sensor_types, _readable_count = (
        validate_thermal_sample_against_lease(
            read_thermal_zones(),
            lease,
            checkpoint="preclaim",
        )
    )
    enforce_thermal_group_ceilings(
        group_maxima,
        lease,
        checkpoint="preclaim",
    )


def read_private_file(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        initial = os.fstat(fd)
        if initial.st_nlink != 1 or not stat.S_ISREG(initial.st_mode):
            raise AcquisitionError("private_file_inode_invalid")
        if initial.st_size > 1024 * 1024:
            raise AcquisitionError("private_file_too_large")
        payload = read_fd_bounded(fd, 1024 * 1024)
        if stat_identity(initial) != stat_identity(os.fstat(fd)):
            raise AcquisitionError("private_file_changed_during_read")
        return payload
    finally:
        os.close(fd)


def strict_json_loads(payload: bytes) -> Any:
    def reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AcquisitionError("duplicate_json_key")
            result[key] = value
        return result

    return json.loads(
        payload,
        object_pairs_hook=reject_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(
            AcquisitionError("nonfinite_json_constant")
        ),
    )


def parse_utc_second(value: Any, field: str) -> datetime:
    if (
        not isinstance(value, str)
        or re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value
        )
        is None
    ):
        raise AcquisitionError(f"{field}_invalid")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        raise AcquisitionError(f"{field}_invalid") from None
    if iso_utc(parsed) != value:
        raise AcquisitionError(f"{field}_not_canonical")
    return parsed


def getprop(name: str) -> str:
    return getprop_raw(name)[:-1].decode("ascii")


def getprop_raw(name: str) -> bytes:
    if not isinstance(name, str) or re.fullmatch(r"[a-z0-9._-]{1,128}", name) is None:
        raise AcquisitionError("getprop_property_name_invalid")
    roles = command_toolchain_roles(GETPROP)
    revalidate_attested_toolchain_roles(roles)
    executable_fd = open_attested_executable_fd(GETPROP)
    try:
        completed = subprocess.run(
            [GETPROP, name],
            executable=str(FD_PATH_ROOT / str(executable_fd)),
            check=True,
            capture_output=True,
            timeout=5,
            pass_fds=(executable_fd,),
            env={
                "ANDROID_ROOT": "/system",
                "HOME": str(PHONE_HOME),
                "PATH": "/system/bin:/data/data/com.termux/files/usr/bin",
                "LC_ALL": "C",
            },
        )
        payload = completed.stdout
        value = payload[:-1] if payload.endswith(b"\n") else b""
        if (
            completed.stderr
            or not payload.endswith(b"\n")
            or payload.count(b"\n") != 1
            or not value
            or len(value) > 4096
            or any(byte < 0x21 or byte > 0x7E for byte in value)
        ):
            raise AcquisitionError("getprop_response_shape_invalid")
        return payload
    finally:
        os.close(executable_fd)
        revalidate_attested_toolchain_roles(roles)


def git_output(*args: str, cwd: Path = ROOT, timeout: int = 30) -> str:
    roles = command_toolchain_roles(GIT)
    revalidate_attested_toolchain_roles(roles)
    executable_fd = open_attested_executable_fd(GIT)
    try:
        return subprocess.run(
            [GIT, *git_safety_options(), *args],
            executable=str(FD_PATH_ROOT / str(executable_fd)),
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=git_environment(),
            pass_fds=(executable_fd,),
        ).stdout.strip()
    finally:
        os.close(executable_fd)
        revalidate_attested_toolchain_roles(roles)


def git_environment() -> dict[str, str]:
    return {
        "ANDROID_ROOT": "/system",
        "GIT_ASKPASS": "/system/bin/false",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_EXEC_PATH": GIT_EXEC_PATH,
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "HOME": str(PHONE_HOME),
        "LC_ALL": "C",
        "LD_PRELOAD": TERMUX_EXEC_INTERPOSER,
        "PATH": "/data/data/com.termux/files/usr/bin:/system/bin",
    }


def git_safety_options() -> tuple[str, ...]:
    return (
        "--no-replace-objects",
        "-c",
        "advice.detachedHead=false",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "credential.helper=",
        "-c",
        "fetch.fsckObjects=true",
        "-c",
        "http.followRedirects=false",
        "-c",
        "http.lowSpeedLimit=1024",
        "-c",
        "http.lowSpeedTime=120",
        "-c",
        "http.sslVerify=true",
        "-c",
        "protocol.version=2",
        "-c",
        "protocol.allow=never",
        "-c",
        "protocol.https.allow=always",
        "-c",
        "protocol.file.allow=never",
        "-c",
        "submodule.recurse=false",
        "-c",
        "transfer.fsckObjects=true",
    )


def curl_environment() -> dict[str, str]:
    return {
        "ANDROID_ROOT": "/system",
        "HOME": str(PHONE_HOME),
        "LC_ALL": "C",
        "PATH": "/data/data/com.termux/files/usr/bin:/system/bin",
    }


def run_monitored(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    envelope: ResourceEnvelope,
    checkpoint: str,
    pass_fds: Sequence[int] = (),
) -> bytes:
    """Run a quiet child while retaining thermal, disk, time, and output gates."""

    if not argv or any(not isinstance(value, str) or "\x00" in value for value in argv):
        raise AcquisitionError("subprocess_argv_invalid")
    toolchain_roles = command_toolchain_roles(argv[0])
    revalidate_attested_toolchain_roles(toolchain_roles)
    envelope.candidate.revalidate_path_binding()
    with (
        tempfile.TemporaryFile(dir=envelope.candidate.bound_path) as output_log,
        tempfile.TemporaryFile(dir=envelope.candidate.bound_path) as error_log,
        EphemeralControlFiles(
            envelope,
            (
                (output_log.fileno(), MAX_PROCESS_LOG_BYTES, "subprocess_stdout"),
                (error_log.fileno(), MAX_PROCESS_LOG_BYTES, "subprocess_stderr"),
            ),
        ),
    ):
        executable_fd = open_attested_executable_fd(argv[0])
        child_pass_fds = tuple(
            dict.fromkeys((*pass_fds, envelope.candidate.directory_fd, executable_fd))
        )
        try:
            process = subprocess.Popen(
                list(argv),
                executable=str(FD_PATH_ROOT / str(executable_fd)),
                cwd=cwd,
                env=dict(env),
                stdin=subprocess.DEVNULL,
                stdout=output_log,
                stderr=error_log,
                close_fds=True,
                pass_fds=child_pass_fds,
                start_new_session=True,
            )
        finally:
            os.close(executable_fd)
        try:
            while process.poll() is None:
                envelope.check(checkpoint)
                time.sleep(PROCESS_POLL_SECONDS)
            return_code = process.returncode
            envelope.check(checkpoint)
        except BaseException:
            terminate_process_group(process)
            revalidate_attested_toolchain_roles(toolchain_roles)
            raise
        revalidate_attested_toolchain_roles(toolchain_roles)
        output_log.flush()
        error_log.flush()
        output_size = os.fstat(output_log.fileno()).st_size
        error_size = os.fstat(error_log.fileno()).st_size
        if output_size > MAX_PROCESS_LOG_BYTES or error_size > MAX_PROCESS_LOG_BYTES:
            raise AcquisitionError("subprocess_log_oversize")
        output_log.seek(0)
        error_log.seek(0)
        output = output_log.read(MAX_PROCESS_LOG_BYTES + 1)
        error_output = error_log.read(MAX_PROCESS_LOG_BYTES + 1)
        if return_code != 0:
            detail_sha = hashlib.sha256(output + b"\x00" + error_output).hexdigest()[
                :16
            ]
            raise AcquisitionError(f"subprocess_exit_{return_code}_{detail_sha}")
        return output


def terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
        return
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except OSError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


@dataclass(frozen=True)
class HttpObservation:
    url: str
    status_code: int
    content_length: int
    etag: str
    last_modified: str | None
    content_type: str | None
    content_encoding: str | None
    content_range: str | None
    redirect_count: int
    downloaded_bytes: int
    response_attempt_count: int

    def stable_identity(self) -> tuple[Any, ...]:
        normalized_encoding = (
            None
            if self.content_encoding is None
            or self.content_encoding.casefold() == "identity"
            else self.content_encoding.casefold()
        )
        return (
            self.url,
            self.status_code,
            self.content_length,
            self.etag,
            self.last_modified,
            normalized_encoding,
            self.content_range,
        )


@dataclass(frozen=True)
class DirectDownloadResult:
    """Exact transport facts for one completed direct-source transfer."""

    observation: HttpObservation
    transfer_mode: str
    fixed_chunk_bytes: int | None
    per_chunk_attempts: tuple[int, ...]
    every_response_206: bool
    every_content_range_exact: bool
    no_overlap: bool
    no_gap: bool
    held_destination_single_inode: bool

    @property
    def chunk_count(self) -> int:
        return len(self.per_chunk_attempts)

    @property
    def total_attempts(self) -> int:
        return sum(self.per_chunk_attempts)

    @property
    def downloaded_bytes(self) -> int:
        return self.observation.downloaded_bytes

    @property
    def response_attempt_count(self) -> int:
        return self.total_attempts


def require_evidence_markers(
    payload: bytes, markers: Sequence[str], source_id: str
) -> None:
    for marker in markers:
        try:
            encoded = marker.encode("utf-8")
        except UnicodeEncodeError:
            raise AcquisitionError("payload_rights_marker_encoding_invalid") from None
        if encoded not in payload:
            raise AcquisitionError(
                f"payload_rights_required_marker_missing:{source_id}"
            )


def read_exact_zip_member_for_rights(
    data_fd: int,
    member: str,
    source_id: str,
) -> bytes:
    os.lseek(data_fd, 0, os.SEEK_SET)
    try:
        with os.fdopen(os.dup(data_fd), "rb", closefd=True) as handle:
            with zipfile.ZipFile(handle, mode="r") as archive:
                matches = [
                    info for info in archive.infolist() if info.filename == member
                ]
                if len(matches) != 1 or matches[0].is_dir():
                    raise AcquisitionError(
                        f"payload_rights_zip_member_cardinality:{source_id}"
                    )
                info = matches[0]
                if info.file_size > 8 * 1024 * 1024:
                    raise AcquisitionError(
                        f"payload_rights_zip_member_oversize:{source_id}"
                    )
                with archive.open(info, mode="r") as stream:
                    payload = stream.read(8 * 1024 * 1024 + 1)
                if len(payload) != info.file_size:
                    raise AcquisitionError(
                        f"payload_rights_zip_member_size_mismatch:{source_id}"
                    )
                return payload
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        if isinstance(error, AcquisitionError):
            raise
        raise AcquisitionError(
            f"payload_rights_zip_member_read_failed:{source_id}"
        ) from error


def verify_payload_rights_evidence(
    source: Any,
    data_fd: int,
) -> list[dict[str, Any]]:
    """Verify the exact acquired bytes that alone support rights admission."""

    initial = os.fstat(data_fd)
    specs = source.payload_rights_specs()
    if not specs:
        records = source.expected_payload_rights_records()
    else:
        records = []
        for evidence in specs:
            if evidence.locator_kind == "direct_prefix":
                payload = os.pread(
                    data_fd,
                    evidence.byte_length,
                    evidence.byte_offset,
                )
                if len(payload) != evidence.byte_length:
                    raise AcquisitionError(
                        f"payload_rights_direct_prefix_short_read:{source.source_id}"
                    )
            elif evidence.locator_kind == "zip_member":
                payload = read_exact_zip_member_for_rights(
                    data_fd,
                    evidence.locator,
                    source.source_id,
                )
            else:
                raise AcquisitionError(
                    f"payload_rights_locator_kind_invalid:{source.source_id}"
                )
            if hashlib.sha256(payload).hexdigest() != evidence.sha256:
                raise AcquisitionError(
                    f"payload_rights_evidence_sha256_mismatch:{source.source_id}"
                )
            require_evidence_markers(
                payload,
                evidence.required_markers,
                source.source_id,
            )
            records.append(evidence.observed_record())
    if stat_identity(initial) != stat_identity(os.fstat(data_fd)):
        raise AcquisitionError(f"payload_rights_source_changed:{source.source_id}")
    if records != source.expected_payload_rights_records():
        raise AcquisitionError(
            f"payload_rights_observed_record_mismatch:{source.source_id}"
        )
    return records


def acquire_direct_source(
    source: Any,
    direct_root: Path,
    candidate: PrivateCandidate,
    envelope: ResourceEnvelope,
    allowed_hosts: frozenset[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_source_component(source.source_id, "source_id")
    validate_source_component(source.filename, "filename")
    validate_https_url(source.url, allowed_hosts)
    source_dir = direct_root / source.source_id
    create_owner_only_directory(source_dir, direct_root)
    directory_fd = os.open(
        source_dir,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    temporary_name = ".download.partial"
    data_fd = -1
    try:
        pre = observe_direct_metadata(
            source,
            source_dir,
            envelope,
            allowed_hosts,
            checkpoint=f"direct_preflight:{source.source_id}",
        )
        validate_http_observation(pre, source, expected_downloaded_bytes=0)
        data_fd = os.open(
            temporary_name,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_fd,
        )
        initial = os.fstat(data_fd)
        download_result = download_direct_file(
            source,
            source_dir,
            data_fd,
            envelope,
            allowed_hosts,
        )
        validate_direct_download_result(download_result, source)
        get_observation = download_result.observation
        os.fsync(data_fd)
        validate_same_entry(directory_fd, temporary_name, initial, os.fstat(data_fd))
        validate_http_observation(
            get_observation,
            source,
            expected_downloaded_bytes=source.expected_bytes,
        )
        if pre.stable_identity() != get_observation.stable_identity():
            raise AcquisitionError(
                f"direct_pre_get_metadata_mismatch:{source.source_id}"
            )
        stable_download = os.fstat(data_fd)
        admission_digest, admission_bytes = hash_fd(data_fd)
        if stat_identity(stable_download) != stat_identity(os.fstat(data_fd)):
            raise AcquisitionError(
                f"direct_file_changed_during_admission_hash:{source.source_id}"
            )
        if (
            admission_bytes != source.expected_bytes
            or admission_digest != "sha256:" + source.expected_sha256
        ):
            raise AcquisitionError(
                f"direct_preinspection_sha256_mismatch:{source.source_id}"
            )
        transfer_evidence = build_direct_transfer_evidence_after_hash(
            download_result,
            source,
            verified_digest=admission_digest,
            verified_bytes=admission_bytes,
        )
        inspection = inspect_direct_source(source, data_fd, envelope)
        observed_rights_evidence = verify_payload_rights_evidence(
            source,
            data_fd,
        )
        payload_rights_evidence_root_sha256 = canonical_sha256(observed_rights_evidence)
        if stat_identity(stable_download) != stat_identity(os.fstat(data_fd)):
            raise AcquisitionError(
                f"direct_file_changed_during_inspection:{source.source_id}"
            )
        post = observe_direct_metadata(
            source,
            source_dir,
            envelope,
            allowed_hosts,
            checkpoint=f"direct_postflight:{source.source_id}",
        )
        validate_http_observation(post, source, expected_downloaded_bytes=0)
        if pre.stable_identity() != post.stable_identity():
            raise AcquisitionError(
                f"direct_pre_post_metadata_mismatch:{source.source_id}"
            )
        if stat_identity(stable_download) != stat_identity(os.fstat(data_fd)):
            raise AcquisitionError(
                f"direct_file_changed_during_postflight:{source.source_id}"
            )
        try:
            os.stat(source.filename, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise AcquisitionError(
                f"direct_destination_already_exists:{source.source_id}"
            )
        os.rename(
            temporary_name,
            source.filename,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        final = os.fstat(data_fd)
        validate_same_entry(directory_fd, source.filename, stable_download, final)
        os.fchmod(data_fd, 0o400)
        os.fsync(data_fd)
        sealed_before_hash = os.fstat(data_fd)
        digest, byte_count = hash_fd(data_fd)
        sealed = os.fstat(data_fd)
        if stat_identity(sealed_before_hash) != stat_identity(sealed):
            raise AcquisitionError(
                f"direct_file_changed_during_authoritative_hash:{source.source_id}"
            )
        if byte_count != source.expected_bytes:
            raise AcquisitionError(f"direct_size_mismatch:{source.source_id}")
        if digest != "sha256:" + source.expected_sha256:
            raise AcquisitionError(f"direct_sha256_mismatch:{source.source_id}")
        validate_same_entry(directory_fd, source.filename, final, sealed)
        os.fsync(directory_fd)
        os.fchmod(directory_fd, 0o500)
        os.fsync(directory_fd)
        local_locator = f"sources/direct/{source.source_id}/{source.filename}"
        content_manifest = {
            "schema_version": "cur0s_direct_content_manifest_v1",
            "files": [
                {
                    "relative_path": local_locator,
                    "bytes": byte_count,
                    "sha256": digest,
                }
            ],
        }
        content_manifest_sha256 = canonical_sha256(content_manifest)
        verification = {
            "conditional_lock_mode": source.conditional_lock_mode,
            "content_manifest_sha256": content_manifest_sha256,
            "cryptographic_payload_identity_verified": True,
            "https_only": True,
            "identity_verified": True,
            "license_markers_verified": True,
            "metadata_match": True,
            "observed_payload_rights_evidence": observed_rights_evidence,
            "observed_etag": post.etag,
            "observed_final_url": post.url,
            "observed_last_modified": post.last_modified,
            "observed_content_type": post.content_type,
            "path_safety_verified": True,
            "phone_private": True,
            "pre_post_metadata_match": True,
            "payload_rights_evidence_root_sha256": (
                payload_rights_evidence_root_sha256
            ),
            "raw_fsynced": True,
            "rights_admission_basis": source.rights_admission_basis,
            "rights_verified": True,
            "stage_binding_verified": True,
            "structure_verified": True,
            "server_conditional_lock_enforced": (
                source.conditional_lock_mode
                == "if_match_enforced_observed_412_on_mismatch"
            ),
            "transport_conditionals_identity_role": "defense_in_depth_only",
            "external_rights_evidence_used_for_admission": False,
        }
        artifact = source_artifact(
            source,
            byte_count=byte_count,
            digest=digest,
            local_locator=local_locator,
            content_manifest=content_manifest,
            verification=verification,
        )
        inspection_summary = {
            "source_id": source.source_id,
            "acquisition_mode": source.acquisition_mode,
            "archive_or_document_type": inspection["archive_or_document_type"],
            "member_count": inspection["member_count"],
            "uncompressed_or_document_bytes": inspection[
                "uncompressed_or_document_bytes"
            ],
            "required_marker_count": len(source.required_markers),
            "required_markers_verified": True,
            "payload_rights_evidence_root_sha256": (
                payload_rights_evidence_root_sha256
            ),
            "external_rights_evidence_runtime_verified": False,
            "transport_response_attempts": {
                "preflight": pre.response_attempt_count,
                "download": download_result.total_attempts,
                "postflight": post.response_attempt_count,
            },
            "transfer_evidence": transfer_evidence,
            "structure_checks": inspection["structure_checks"],
            "raw_payload_egressed": False,
        }
        return artifact, inspection_summary
    finally:
        if data_fd >= 0:
            os.close(data_fd)
        os.close(directory_fd)


def observe_direct_metadata(
    source: Any,
    cwd: Path,
    envelope: ResourceEnvelope,
    allowed_hosts: frozenset[str],
    *,
    checkpoint: str,
) -> HttpObservation:
    validate_https_url(source.url, allowed_hosts)
    with (
        tempfile.TemporaryFile(dir=cwd) as headers,
        EphemeralControlFiles(
            envelope,
            ((headers.fileno(), MAX_HEADER_BYTES, "curl_HEAD_headers"),),
        ),
    ):
        argv = [
            CURL,
            "--disable",
            "--silent",
            "--show-error",
            "--head",
            "--fail",
            "--proto",
            "=https",
            "--max-redirs",
            "0",
            "--connect-timeout",
            "30",
            "--retry",
            "3",
            "--retry-all-errors",
            "--retry-connrefused",
            "--retry-delay",
            "2",
            "--retry-max-time",
            "120",
            "--max-time",
            str(curl_timeout_seconds(envelope, ceiling=180)),
            "--tlsv1.2",
            "--header",
            "Accept-Encoding: identity",
            "--user-agent",
            "Polymath-CUR0S-source-custody/1.0",
            "--dump-header",
            f"/proc/self/fd/{headers.fileno()}",
            "--output",
            "/dev/null",
            "--write-out",
            curl_writeout_format(),
            "--url",
            source.url,
        ]
        output = run_monitored(
            argv,
            cwd=cwd,
            env=curl_environment(),
            envelope=envelope,
            checkpoint=checkpoint,
            pass_fds=(headers.fileno(),),
        )
        header_bytes = read_temporary_file(headers, MAX_HEADER_BYTES)
    return parse_http_observation(output, header_bytes, downloaded_bytes=0)


def download_direct_file(
    source: Any,
    cwd: Path,
    data_fd: int,
    envelope: ResourceEnvelope,
    allowed_hosts: frozenset[str],
) -> DirectDownloadResult:
    transfer_mode, fixed_chunk_bytes = validate_direct_transfer_policy(source)
    if transfer_mode == "fixed_range_chunks_v1":
        assert fixed_chunk_bytes is not None
        result = download_direct_file_in_fixed_ranges(
            source,
            cwd,
            data_fd,
            envelope,
            allowed_hosts,
            fixed_chunk_bytes=fixed_chunk_bytes,
        )
    else:
        result = download_direct_file_in_single_response(
            source,
            cwd,
            data_fd,
            envelope,
            allowed_hosts,
        )
    validate_direct_download_result(result, source)
    return result


def validate_direct_transfer_policy(source: Any) -> tuple[str, int | None]:
    transfer_mode = getattr(source, "transfer_mode", None)
    fixed_chunk_bytes = getattr(source, "fixed_chunk_bytes", None)
    if type(source.expected_bytes) is not int or source.expected_bytes <= 0:
        raise AcquisitionError(f"direct_expected_bytes_invalid:{source.source_id}")
    if not isinstance(source.expected_etag, str) or not source.expected_etag:
        raise AcquisitionError(f"direct_expected_etag_invalid:{source.source_id}")
    if transfer_mode == "single_response_v1":
        if fixed_chunk_bytes is not None:
            raise AcquisitionError(
                f"direct_single_response_chunk_size_invalid:{source.source_id}"
            )
        return transfer_mode, None
    if transfer_mode != "fixed_range_chunks_v1":
        raise AcquisitionError(f"direct_transfer_mode_invalid:{source.source_id}")
    if (
        not isinstance(fixed_chunk_bytes, int)
        or isinstance(fixed_chunk_bytes, bool)
        or not 1 <= fixed_chunk_bytes <= MAX_DIRECT_RANGE_CHUNK_BYTES
    ):
        raise AcquisitionError(f"direct_range_chunk_size_invalid:{source.source_id}")
    if source.expected_etag.startswith("W/"):
        raise AcquisitionError(f"direct_range_strong_etag_required:{source.source_id}")
    return transfer_mode, fixed_chunk_bytes


def validate_direct_download_result(
    result: DirectDownloadResult,
    source: Any,
) -> None:
    if not isinstance(result, DirectDownloadResult):
        raise AcquisitionError(f"direct_download_result_invalid:{source.source_id}")
    transfer_mode, fixed_chunk_bytes = validate_direct_transfer_policy(source)
    expected_chunks = (
        (source.expected_bytes + fixed_chunk_bytes - 1) // fixed_chunk_bytes
        if fixed_chunk_bytes is not None
        else 1
    )
    attempts = result.per_chunk_attempts
    attempts_valid = (
        isinstance(attempts, tuple)
        and len(attempts) == expected_chunks
        and all(
            isinstance(value, int)
            and not isinstance(value, bool)
            and 1 <= value <= DIRECT_TRANSFER_MAX_ATTEMPTS
            for value in attempts
        )
    )
    common_valid = (
        result.transfer_mode == transfer_mode
        and result.fixed_chunk_bytes == fixed_chunk_bytes
        and attempts_valid
        and result.observation.response_attempt_count == result.total_attempts
        and result.no_overlap is True
        and result.no_gap is True
        and result.held_destination_single_inode is True
    )
    range_flags_valid = (
        result.every_response_206 is True and result.every_content_range_exact is True
        if transfer_mode == "fixed_range_chunks_v1"
        else result.every_response_206 is False
        and result.every_content_range_exact is False
    )
    if not common_valid or not range_flags_valid:
        raise AcquisitionError(
            f"direct_download_result_evidence_invalid:{source.source_id}"
        )


def build_direct_transfer_evidence_after_hash(
    result: DirectDownloadResult,
    source: Any,
    *,
    verified_digest: str,
    verified_bytes: int,
) -> dict[str, Any]:
    """Mint receipt evidence only from the caller's completed admission hash."""

    validate_direct_download_result(result, source)
    if (
        verified_bytes != source.expected_bytes
        or verified_digest != "sha256:" + source.expected_sha256
    ):
        raise AcquisitionError(
            f"direct_transfer_post_hash_proof_invalid:{source.source_id}"
        )
    return {
        "schema_version": "cur0s_direct_transfer_evidence_v1",
        "mode": result.transfer_mode,
        "fixed_chunk_bytes": result.fixed_chunk_bytes,
        "chunk_count": result.chunk_count,
        "per_chunk_attempts": list(result.per_chunk_attempts),
        "total_attempts": result.total_attempts,
        "every_response_206": result.every_response_206,
        "every_content_range_exact": result.every_content_range_exact,
        "no_overlap": result.no_overlap,
        "no_gap": result.no_gap,
        "held_destination_single_inode": result.held_destination_single_inode,
        "full_length_and_sha256_verified": True,
    }


def download_direct_file_in_single_response(
    source: Any,
    cwd: Path,
    data_fd: int,
    envelope: ResourceEnvelope,
    allowed_hosts: frozenset[str],
) -> DirectDownloadResult:
    validate_https_url(source.url, allowed_hosts)
    held_identity = held_regular_inode_identity(data_fd, "direct_destination")
    with (
        tempfile.TemporaryFile(dir=cwd) as headers,
        EphemeralControlFiles(
            envelope,
            ((headers.fileno(), MAX_HEADER_BYTES, "curl_GET_headers"),),
        ),
    ):
        argv = [
            CURL,
            "--disable",
            "--silent",
            "--show-error",
            "--fail",
            "--proto",
            "=https",
            "--max-redirs",
            "0",
            "--connect-timeout",
            "30",
            "--speed-limit",
            "1024",
            "--speed-time",
            "180",
            "--max-time",
            str(curl_timeout_seconds(envelope, ceiling=3600)),
            "--max-filesize",
            str(source.expected_bytes),
            "--tlsv1.2",
            "--header",
            "Accept-Encoding: identity",
            "--header",
            f"If-Match: {source.expected_etag}",
        ]
        if source.expected_last_modified is not None:
            argv.extend(
                ["--header", f"If-Unmodified-Since: {source.expected_last_modified}"]
            )
        argv.extend(
            [
                "--user-agent",
                "Polymath-CUR0S-source-custody/1.0",
                "--dump-header",
                f"/proc/self/fd/{headers.fileno()}",
                "--output",
                f"/proc/self/fd/{data_fd}",
                "--write-out",
                curl_writeout_format(),
                "--url",
                source.url,
            ]
        )
        output: bytes | None = None
        successful_attempt = 0
        for attempt in range(1, DIRECT_TRANSFER_MAX_ATTEMPTS + 1):
            os.ftruncate(data_fd, 0)
            os.lseek(data_fd, 0, os.SEEK_SET)
            headers.seek(0)
            headers.truncate(0)
            envelope.check(
                f"direct_download_attempt:{source.source_id}",
                force_thermal=True,
            )
            try:
                output = run_monitored(
                    argv,
                    cwd=cwd,
                    env=curl_environment(),
                    envelope=envelope,
                    checkpoint=f"direct_download:{source.source_id}",
                    pass_fds=(headers.fileno(), data_fd),
                )
                successful_attempt = attempt
                break
            except AcquisitionError as error:
                if attempt == DIRECT_TRANSFER_MAX_ATTEMPTS or not str(error).startswith(
                    "subprocess_exit_"
                ):
                    raise
                envelope.check(
                    f"direct_download_retry:{source.source_id}",
                    force_thermal=True,
                )
                time.sleep(2 ** (attempt - 1))
        if output is None or successful_attempt == 0:
            raise AcquisitionError("direct_download_retry_state_unreachable")
        header_bytes = read_temporary_file(headers, MAX_HEADER_BYTES)
    downloaded_bytes = os.fstat(data_fd).st_size
    observation = parse_http_observation(
        output,
        header_bytes,
        downloaded_bytes=downloaded_bytes,
    )
    if observation.response_attempt_count != 1:
        raise AcquisitionError("direct_download_single_attempt_header_count_invalid")
    observation = replace(observation, response_attempt_count=successful_attempt)
    if held_regular_inode_identity(data_fd, "direct_destination") != held_identity:
        raise AcquisitionError("direct_download_destination_inode_changed")
    return DirectDownloadResult(
        observation=observation,
        transfer_mode="single_response_v1",
        fixed_chunk_bytes=None,
        per_chunk_attempts=(successful_attempt,),
        every_response_206=False,
        every_content_range_exact=False,
        no_overlap=True,
        no_gap=True,
        held_destination_single_inode=True,
    )


def download_direct_file_in_fixed_ranges(
    source: Any,
    cwd: Path,
    data_fd: int,
    envelope: ResourceEnvelope,
    allowed_hosts: frozenset[str],
    *,
    fixed_chunk_bytes: int,
) -> DirectDownloadResult:
    validate_https_url(source.url, allowed_hosts)
    held_identity = held_regular_inode_identity(data_fd, "direct_destination")
    if os.fstat(data_fd).st_size != 0:
        raise AcquisitionError("direct_range_destination_not_empty")
    chunk_count = (source.expected_bytes + fixed_chunk_bytes - 1) // fixed_chunk_bytes
    attempts: list[int] = []
    first_observation: HttpObservation | None = None
    response_identity: tuple[Any, ...] | None = None
    for chunk_index in range(chunk_count):
        start = chunk_index * fixed_chunk_bytes
        end = min(source.expected_bytes, start + fixed_chunk_bytes) - 1
        observation, attempt_count = download_direct_range_chunk(
            source,
            cwd,
            data_fd,
            envelope,
            allowed_hosts,
            start=start,
            end=end,
            held_destination_identity=held_identity,
        )
        current_identity = (
            observation.url,
            observation.etag,
            observation.last_modified,
            observation.content_type,
            normalize_content_encoding(observation.content_encoding),
        )
        if response_identity is None:
            response_identity = current_identity
            first_observation = observation
        elif current_identity != response_identity:
            raise AcquisitionError(
                f"direct_range_response_identity_changed:{source.source_id}"
            )
        attempts.append(attempt_count)
    if first_observation is None or len(attempts) != chunk_count:
        raise AcquisitionError("direct_range_transfer_state_unreachable")
    final_info = os.fstat(data_fd)
    if (
        final_info.st_size != source.expected_bytes
        or held_regular_inode_identity(data_fd, "direct_destination") != held_identity
    ):
        raise AcquisitionError("direct_range_destination_final_state_invalid")
    total_attempts = sum(attempts)
    aggregate = HttpObservation(
        url=first_observation.url,
        status_code=200,
        content_length=source.expected_bytes,
        etag=first_observation.etag,
        last_modified=first_observation.last_modified,
        content_type=first_observation.content_type,
        content_encoding=first_observation.content_encoding,
        content_range=None,
        redirect_count=0,
        downloaded_bytes=source.expected_bytes,
        response_attempt_count=total_attempts,
    )
    return DirectDownloadResult(
        observation=aggregate,
        transfer_mode="fixed_range_chunks_v1",
        fixed_chunk_bytes=fixed_chunk_bytes,
        per_chunk_attempts=tuple(attempts),
        every_response_206=True,
        every_content_range_exact=True,
        no_overlap=True,
        no_gap=True,
        held_destination_single_inode=True,
    )


def download_direct_range_chunk(
    source: Any,
    cwd: Path,
    data_fd: int,
    envelope: ResourceEnvelope,
    allowed_hosts: frozenset[str],
    *,
    start: int,
    end: int,
    held_destination_identity: tuple[int, ...],
) -> tuple[HttpObservation, int]:
    validate_https_url(source.url, allowed_hosts)
    expected_chunk_bytes = end - start + 1
    if start < 0 or end < start or end >= source.expected_bytes:
        raise AcquisitionError("direct_range_bounds_invalid")
    with (
        tempfile.TemporaryFile(dir=cwd) as headers,
        tempfile.TemporaryFile(dir=cwd) as chunk,
        EphemeralControlFiles(
            envelope,
            (
                (headers.fileno(), MAX_HEADER_BYTES, "curl_range_GET_headers"),
                (
                    chunk.fileno(),
                    expected_chunk_bytes,
                    "curl_range_GET_payload",
                ),
            ),
        ),
    ):
        argv = direct_range_curl_argv(
            source,
            headers_fd=headers.fileno(),
            chunk_fd=chunk.fileno(),
            start=start,
            end=end,
            envelope=envelope,
        )
        output: bytes | None = None
        successful_attempt = 0
        for attempt in range(1, DIRECT_TRANSFER_MAX_ATTEMPTS + 1):
            reset_temporary_file(headers)
            reset_temporary_file(chunk)
            envelope.check(
                f"direct_range_attempt:{source.source_id}:{start}-{end}",
                force_thermal=True,
            )
            try:
                output = run_monitored(
                    argv,
                    cwd=cwd,
                    env=curl_environment(),
                    envelope=envelope,
                    checkpoint=f"direct_range_download:{source.source_id}",
                    pass_fds=(headers.fileno(), chunk.fileno()),
                )
                successful_attempt = attempt
                break
            except AcquisitionError as error:
                if not str(error).startswith("subprocess_exit_"):
                    raise
                failed_headers = read_temporary_file(headers, MAX_HEADER_BYTES)
                if failed_headers:
                    validate_failed_range_response_headers(
                        failed_headers,
                        source,
                        start=start,
                        end=end,
                    )
                if attempt == DIRECT_TRANSFER_MAX_ATTEMPTS:
                    raise
                envelope.check(
                    f"direct_range_retry:{source.source_id}:{start}-{end}",
                    force_thermal=True,
                )
                time.sleep(2 ** (attempt - 1))
        if output is None or successful_attempt == 0:
            raise AcquisitionError("direct_range_retry_state_unreachable")
        header_bytes = read_temporary_file(headers, MAX_HEADER_BYTES)
        downloaded_bytes = os.fstat(chunk.fileno()).st_size
        observation = parse_http_observation(
            output,
            header_bytes,
            downloaded_bytes=downloaded_bytes,
            allowed_final_status_codes=frozenset({206}),
        )
        validate_range_http_observation(
            observation,
            source,
            start=start,
            end=end,
        )
        if observation.response_attempt_count != 1:
            raise AcquisitionError("direct_range_multi_response_ambiguity")
        append_exact_range_chunk(
            chunk.fileno(),
            data_fd,
            start=start,
            end=end,
            held_destination_identity=held_destination_identity,
        )
    return observation, successful_attempt


def direct_range_curl_argv(
    source: Any,
    *,
    headers_fd: int,
    chunk_fd: int,
    start: int,
    end: int,
    envelope: ResourceEnvelope,
) -> list[str]:
    chunk_bytes = end - start + 1
    argv = [
        CURL,
        "--disable",
        "--silent",
        "--show-error",
        "--fail",
        "--proto",
        "=https",
        "--max-redirs",
        "0",
        "--connect-timeout",
        "30",
        "--speed-limit",
        "1024",
        "--speed-time",
        "180",
        "--max-time",
        str(curl_timeout_seconds(envelope, ceiling=3600)),
        "--max-filesize",
        str(chunk_bytes),
        "--tlsv1.2",
        "--header",
        "Accept-Encoding: identity",
        "--header",
        f"Range: bytes={start}-{end}",
        "--header",
        f"If-Range: {source.expected_etag}",
        "--header",
        f"If-Match: {source.expected_etag}",
    ]
    if source.expected_last_modified is not None:
        argv.extend(
            ["--header", f"If-Unmodified-Since: {source.expected_last_modified}"]
        )
    argv.extend(
        [
            "--user-agent",
            "Polymath-CUR0S-source-custody/1.0",
            "--dump-header",
            f"/proc/self/fd/{headers_fd}",
            "--output",
            f"/proc/self/fd/{chunk_fd}",
            "--write-out",
            curl_writeout_format(),
            "--url",
            source.url,
        ]
    )
    return argv


def reset_temporary_file(handle: BinaryIO) -> None:
    handle.seek(0)
    handle.truncate(0)


def held_regular_inode_identity(fd: int, role: str) -> tuple[int, ...]:
    info = os.fstat(fd)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_nlink not in {0, 1}
    ):
        raise AcquisitionError(f"{role}_inode_invalid")
    return (
        info.st_dev,
        info.st_ino,
        stat.S_IFMT(info.st_mode),
        info.st_nlink,
        info.st_uid,
        info.st_gid,
    )


def append_exact_range_chunk(
    chunk_fd: int,
    data_fd: int,
    *,
    start: int,
    end: int,
    held_destination_identity: tuple[int, ...],
) -> None:
    expected_bytes = end - start + 1
    chunk_before = os.fstat(chunk_fd)
    destination_before = os.fstat(data_fd)
    if (
        not stat.S_ISREG(chunk_before.st_mode)
        or chunk_before.st_size != expected_bytes
        or destination_before.st_size != start
        or held_regular_inode_identity(data_fd, "direct_destination")
        != held_destination_identity
    ):
        raise AcquisitionError("direct_range_append_precondition_invalid")
    copied = 0
    while copied < expected_bytes:
        payload = os.pread(
            chunk_fd,
            min(DIRECT_RANGE_COPY_BUFFER_BYTES, expected_bytes - copied),
            copied,
        )
        if not payload:
            raise AcquisitionError("direct_range_chunk_short_read")
        pwrite_all(data_fd, payload, start + copied)
        copied += len(payload)
    chunk_after = os.fstat(chunk_fd)
    destination_after = os.fstat(data_fd)
    if (
        stat_identity(chunk_before) != stat_identity(chunk_after)
        or copied != expected_bytes
        or destination_after.st_size != end + 1
        or held_regular_inode_identity(data_fd, "direct_destination")
        != held_destination_identity
    ):
        raise AcquisitionError("direct_range_append_postcondition_invalid")


def pwrite_all(fd: int, payload: bytes, offset: int) -> None:
    view = memoryview(payload)
    written_total = 0
    while view:
        written = os.pwrite(fd, view, offset + written_total)
        if written <= 0:
            raise AcquisitionError("direct_range_zero_length_pwrite")
        written_total += written
        view = view[written:]


def normalize_content_encoding(value: str | None) -> str | None:
    if value is None or value.casefold() == "identity":
        return None
    return value.casefold()


def validate_failed_range_response_headers(
    payload: bytes,
    source: Any,
    *,
    start: int,
    end: int,
) -> None:
    allowed = frozenset({200, 206}) | HTTP_RETRYABLE_STATUS_CODES
    headers = parse_http_headers(payload, allowed_final_status_codes=allowed)
    if headers["response_attempt_count"] != 1:
        raise AcquisitionError("direct_range_multi_response_ambiguity")
    if headers["status_code"] in HTTP_RETRYABLE_STATUS_CODES:
        return
    validate_range_header_values(headers, source, start=start, end=end)


def validate_range_http_observation(
    observed: HttpObservation,
    source: Any,
    *,
    start: int,
    end: int,
) -> None:
    expected_bytes = end - start + 1
    if observed.url != source.url or observed.redirect_count != 0:
        raise AcquisitionError(f"direct_range_final_url_mismatch:{source.source_id}")
    if observed.status_code != 206:
        raise AcquisitionError(f"direct_range_status_not_206:{source.source_id}")
    if observed.content_length != expected_bytes:
        raise AcquisitionError(
            f"direct_range_content_length_mismatch:{source.source_id}"
        )
    validate_direct_response_identity(
        etag=observed.etag,
        last_modified=observed.last_modified,
        content_type=observed.content_type,
        content_encoding=observed.content_encoding,
        source=source,
    )
    require_exact_content_range(
        observed.content_range,
        start=start,
        end=end,
        total=source.expected_bytes,
        source_id=source.source_id,
    )
    if observed.downloaded_bytes != expected_bytes:
        raise AcquisitionError(
            f"direct_range_downloaded_bytes_mismatch:{source.source_id}"
        )


def validate_range_header_values(
    headers: Mapping[str, Any],
    source: Any,
    *,
    start: int,
    end: int,
) -> None:
    if headers["status_code"] != 206:
        raise AcquisitionError(f"direct_range_status_not_206:{source.source_id}")
    expected_bytes = end - start + 1
    if parse_single_integer_header(headers, "content-length") != expected_bytes:
        raise AcquisitionError(
            f"direct_range_content_length_mismatch:{source.source_id}"
        )
    validate_direct_response_identity(
        etag=parse_single_header(headers, "etag"),
        last_modified=parse_optional_single_header(headers, "last-modified"),
        content_type=parse_optional_single_header(headers, "content-type"),
        content_encoding=parse_optional_single_header(headers, "content-encoding"),
        source=source,
    )
    require_exact_content_range(
        parse_optional_single_header(headers, "content-range"),
        start=start,
        end=end,
        total=source.expected_bytes,
        source_id=source.source_id,
    )


def validate_direct_response_identity(
    *,
    etag: str,
    last_modified: str | None,
    content_type: str | None,
    content_encoding: str | None,
    source: Any,
) -> None:
    if etag != source.expected_etag:
        raise AcquisitionError(f"direct_range_etag_mismatch:{source.source_id}")
    if last_modified != source.expected_last_modified:
        raise AcquisitionError(
            f"direct_range_last_modified_mismatch:{source.source_id}"
        )
    if content_type is not None:
        observed_media_type = content_type.split(";", 1)[0].strip().lower()
        expected_media_type = source.media_type.split(";", 1)[0].strip().lower()
        if not observed_media_type or observed_media_type != expected_media_type:
            raise AcquisitionError(
                f"direct_range_content_type_mismatch:{source.source_id}"
            )
    if normalize_content_encoding(content_encoding) is not None:
        raise AcquisitionError(
            f"direct_range_content_encoding_mismatch:{source.source_id}"
        )


def require_exact_content_range(
    value: str | None,
    *,
    start: int,
    end: int,
    total: int,
    source_id: str,
) -> None:
    match = (
        re.fullmatch(r"bytes ([0-9]+)-([0-9]+)/([0-9]+)", value)
        if isinstance(value, str)
        else None
    )
    if match is None or tuple(int(item) for item in match.groups()) != (
        start,
        end,
        total,
    ):
        raise AcquisitionError(f"direct_range_content_range_mismatch:{source_id}")


def curl_writeout_format() -> str:
    return (
        "CUR0S_URL:%{url_effective}\\n"
        "CUR0S_CODE:%{response_code}\\n"
        "CUR0S_SIZE:%{size_download}\\n"
        "CUR0S_REDIRECTS:%{num_redirects}\\n"
        "CUR0S_TYPE:%{content_type}\\n"
    )


def parse_http_observation(
    output: bytes,
    header_bytes: bytes,
    *,
    downloaded_bytes: int,
    allowed_final_status_codes: frozenset[int] = frozenset({200}),
) -> HttpObservation:
    try:
        text = output.decode("utf-8")
    except UnicodeDecodeError:
        raise AcquisitionError("curl_writeout_not_utf8") from None
    values: dict[str, str] = {}
    expected_prefixes = {
        "CUR0S_URL": "url",
        "CUR0S_CODE": "code",
        "CUR0S_SIZE": "size",
        "CUR0S_REDIRECTS": "redirects",
        "CUR0S_TYPE": "type",
    }
    for line in text.splitlines():
        if ":" not in line:
            raise AcquisitionError("curl_writeout_line_invalid")
        prefix, value = line.split(":", 1)
        key = expected_prefixes.get(prefix)
        if key is None or key in values:
            raise AcquisitionError("curl_writeout_field_invalid")
        values[key] = value
    if set(values) != set(expected_prefixes.values()):
        raise AcquisitionError("curl_writeout_field_set_mismatch")
    if re.fullmatch(r"[0-9]{3}", values["code"]) is None:
        raise AcquisitionError("curl_status_invalid")
    if re.fullmatch(r"[0-9]+", values["size"]) is None:
        raise AcquisitionError("curl_size_invalid")
    if re.fullmatch(r"[0-9]+", values["redirects"]) is None:
        raise AcquisitionError("curl_redirect_count_invalid")
    if int(values["size"]) != downloaded_bytes:
        raise AcquisitionError("curl_reported_download_size_mismatch")
    headers = parse_http_headers(
        header_bytes,
        allowed_final_status_codes=allowed_final_status_codes,
    )
    status_code = int(values["code"])
    if headers["status_code"] != status_code:
        raise AcquisitionError("curl_header_status_mismatch")
    content_length = parse_single_integer_header(headers, "content-length")
    etag = parse_single_header(headers, "etag")
    last_modified = parse_optional_single_header(headers, "last-modified")
    content_type = parse_optional_single_header(headers, "content-type")
    content_encoding = parse_optional_single_header(headers, "content-encoding")
    content_range = parse_optional_single_header(headers, "content-range")
    return HttpObservation(
        url=values["url"],
        status_code=status_code,
        content_length=content_length,
        etag=etag,
        last_modified=last_modified,
        content_type=content_type,
        content_encoding=content_encoding,
        content_range=content_range,
        redirect_count=int(values["redirects"]),
        downloaded_bytes=downloaded_bytes,
        response_attempt_count=headers["response_attempt_count"],
    )


def parse_http_headers(
    payload: bytes,
    *,
    allowed_final_status_codes: frozenset[int] = frozenset({200}),
) -> dict[str, Any]:
    if (
        not isinstance(allowed_final_status_codes, frozenset)
        or not allowed_final_status_codes
        or any(
            not isinstance(code, int)
            or isinstance(code, bool)
            or not 100 <= code <= 599
            for code in allowed_final_status_codes
        )
    ):
        raise AcquisitionError("http_allowed_final_status_set_invalid")
    if len(payload) > MAX_HEADER_BYTES or b"\x00" in payload:
        raise AcquisitionError("http_header_block_invalid")
    try:
        text = payload.decode("iso-8859-1")
    except UnicodeDecodeError:
        raise AcquisitionError("http_header_decode_failed") from None
    normalized = text.replace("\r\n", "\n")
    blocks = [block for block in normalized.split("\n\n") if block.strip()]
    parsed_blocks: list[tuple[int, dict[str, list[str]]]] = []
    for block in blocks:
        lines = block.split("\n")
        match = re.fullmatch(r"HTTP/[0-9.]+ ([0-9]{3})(?: .*)?", lines[0].strip())
        if match is None:
            raise AcquisitionError("http_status_line_invalid")
        fields: dict[str, list[str]] = {}
        for line in lines[1:]:
            if not line:
                continue
            if line[:1] in {" ", "\t"} or ":" not in line:
                raise AcquisitionError("http_header_line_invalid")
            name, value = line.split(":", 1)
            if re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name) is None:
                raise AcquisitionError("http_header_name_invalid")
            value = value.strip()
            if "\r" in value or "\n" in value:
                raise AcquisitionError("http_header_value_invalid")
            fields.setdefault(name.lower(), []).append(value)
        parsed_blocks.append((int(match.group(1)), fields))
    if not parsed_blocks:
        raise AcquisitionError("http_header_block_missing")
    allowed_observed = {100} | set(allowed_final_status_codes)
    if any(code not in allowed_observed for code, _ in parsed_blocks):
        raise AcquisitionError("http_redirect_or_nonretryable_error_forbidden")
    status_code, fields = parsed_blocks[-1]
    if status_code not in allowed_final_status_codes:
        raise AcquisitionError("http_final_status_not_allowed")
    response_attempt_count = sum(code != 100 for code, _ in parsed_blocks)
    if not 1 <= response_attempt_count <= 4:
        raise AcquisitionError("http_response_attempt_count_invalid")
    return {
        "status_code": status_code,
        "fields": fields,
        "response_attempt_count": response_attempt_count,
    }


def parse_single_header(headers: Mapping[str, Any], name: str) -> str:
    values = headers["fields"].get(name)
    if not isinstance(values, list) or len(values) != 1 or not values[0]:
        raise AcquisitionError(f"http_{name}_header_invalid")
    return values[0]


def parse_optional_single_header(headers: Mapping[str, Any], name: str) -> str | None:
    values = headers["fields"].get(name)
    if values is None:
        return None
    if not isinstance(values, list) or len(values) != 1 or not values[0]:
        raise AcquisitionError(f"http_{name}_header_invalid")
    return values[0]


def parse_single_integer_header(headers: Mapping[str, Any], name: str) -> int:
    value = parse_single_header(headers, name)
    if re.fullmatch(r"[0-9]+", value) is None:
        raise AcquisitionError(f"http_{name}_header_invalid")
    return int(value)


def validate_http_observation(
    observed: HttpObservation,
    source: Any,
    *,
    expected_downloaded_bytes: int,
) -> None:
    if observed.url != source.url:
        raise AcquisitionError(f"direct_final_url_mismatch:{source.source_id}")
    if observed.status_code != 200 or observed.redirect_count != 0:
        raise AcquisitionError(f"direct_http_status_or_redirect:{source.source_id}")
    if observed.content_length != source.expected_bytes:
        raise AcquisitionError(f"direct_content_length_mismatch:{source.source_id}")
    if observed.etag != source.expected_etag:
        raise AcquisitionError(f"direct_etag_mismatch:{source.source_id}")
    if observed.last_modified != source.expected_last_modified:
        raise AcquisitionError(f"direct_last_modified_mismatch:{source.source_id}")
    if observed.content_type is not None:
        observed_media_type = observed.content_type.split(";", 1)[0].strip().lower()
        expected_media_type = source.media_type.split(";", 1)[0].strip().lower()
        if not observed_media_type or observed_media_type != expected_media_type:
            raise AcquisitionError(f"direct_content_type_mismatch:{source.source_id}")
    if (
        observed.content_encoding is not None
        and observed.content_encoding.casefold() != "identity"
    ):
        raise AcquisitionError(f"direct_content_encoding_mismatch:{source.source_id}")
    if observed.content_range is not None:
        raise AcquisitionError(f"direct_partial_content_forbidden:{source.source_id}")
    if observed.downloaded_bytes != expected_downloaded_bytes:
        raise AcquisitionError(f"direct_downloaded_bytes_mismatch:{source.source_id}")


def curl_timeout_seconds(envelope: ResourceEnvelope, *, ceiling: int) -> int:
    remaining_wall = envelope.lease.max_wall_seconds - envelope.elapsed_seconds()
    remaining_lease = (
        envelope.lease.expires_at - datetime.now(timezone.utc)
    ).total_seconds()
    result = int(min(ceiling, remaining_wall, remaining_lease))
    if result <= 0:
        raise OperationalStop("curl_deadline_unavailable", "curl_setup")
    return result


class MarkerTracker:
    """Find every exact ASCII/UTF-8 contract marker across stream chunks."""

    def __init__(self, markers: Sequence[str]) -> None:
        self._markers = {marker: marker.encode("utf-8") for marker in markers}
        self._found: set[str] = set()
        self._tail = b""
        self._overlap = (
            max((len(value) for value in self._markers.values()), default=1) - 1
        )

    def feed(self, chunk: bytes, *, continue_stream: bool = True) -> None:
        haystack = self._tail + chunk
        for marker, encoded in self._markers.items():
            if marker not in self._found and encoded in haystack:
                self._found.add(marker)
        if continue_stream and self._overlap > 0:
            self._tail = haystack[-self._overlap :]
        else:
            self._tail = b""

    def end_stream(self) -> None:
        self._tail = b""

    def require_all(self, source_id: str) -> None:
        if self._found != set(self._markers):
            raise AcquisitionError(f"required_license_marker_missing:{source_id}")

    def reject_any(self, source_id: str) -> None:
        if self._found:
            raise AcquisitionError(f"forbidden_XML_markup:{source_id}")


def inspect_direct_source(
    source: Any, data_fd: int, envelope: ResourceEnvelope
) -> dict[str, Any]:
    before = os.fstat(data_fd)
    media_type = source.media_type.split(";", 1)[0].strip().lower()
    if media_type == "application/x-gzip":
        result = inspect_safe_tar(source, data_fd, envelope)
    elif media_type in {"application/zip", "application/epub+zip"}:
        result = inspect_safe_zip(
            source, data_fd, envelope, epub=media_type.endswith("epub+zip")
        )
    elif media_type in {"text/obo", "text/plain"}:
        result = inspect_obo_or_text(source, data_fd, envelope)
    elif media_type == "application/rdf+xml":
        result = inspect_rdf_xml(source, data_fd, envelope)
    else:
        raise AcquisitionError(f"unsupported_direct_media_type:{source.source_id}")
    after = os.fstat(data_fd)
    if stat_identity(before) != stat_identity(after):
        raise AcquisitionError(
            f"direct_source_changed_during_inspection:{source.source_id}"
        )
    return result


def inspect_safe_tar(
    source: Any, data_fd: int, envelope: ResourceEnvelope
) -> dict[str, Any]:
    os.lseek(data_fd, 0, os.SEEK_SET)
    if os.read(data_fd, 2) != b"\x1f\x8b":
        raise AcquisitionError(f"gzip_magic_mismatch:{source.source_id}")
    os.lseek(data_fd, 0, os.SEEK_SET)
    tracker = MarkerTracker(source.required_markers)
    seen_names: set[str] = set()
    member_count = 0
    regular_count = 0
    total_bytes = 0
    processed_since_check = 0
    wordnet_members: set[str] = set()
    with os.fdopen(os.dup(data_fd), "rb", closefd=True) as handle:
        try:
            with tarfile.open(fileobj=handle, mode="r:gz") as archive:
                for member in archive:
                    member_count += 1
                    if member_count > MAX_ARCHIVE_ENTRIES:
                        raise AcquisitionError("tar_member_count_limit")
                    validate_archive_member_name(member.name, seen_names)
                    if member.issparse():
                        raise AcquisitionError("tar_sparse_member_forbidden")
                    if member.isdir():
                        continue
                    if not member.isreg():
                        raise AcquisitionError("tar_nonregular_member_forbidden")
                    if member.size < 0 or member.size > 512 * 1024 * 1024:
                        raise AcquisitionError("tar_member_size_invalid")
                    total_bytes += member.size
                    tar_limit = min(
                        max(source.expected_bytes * 32, 512 * 1024 * 1024),
                        2 * 1024**3,
                    )
                    if total_bytes > tar_limit:
                        raise AcquisitionError("tar_uncompressed_size_limit")
                    regular_count += 1
                    normalized = member.name.lstrip("./")
                    wordnet_members.add(normalized)
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise AcquisitionError("tar_regular_member_unreadable")
                    marker_eligible = is_textual_archive_member(member.name)
                    consumed = 0
                    while True:
                        chunk = stream.read(1024 * 1024)
                        if not chunk:
                            break
                        consumed += len(chunk)
                        processed_since_check += len(chunk)
                        if marker_eligible:
                            tracker.feed(chunk)
                        if processed_since_check >= 16 * 1024 * 1024:
                            envelope.check(f"tar_inspect:{source.source_id}")
                            processed_since_check = 0
                    tracker.end_stream()
                    if consumed != member.size:
                        raise AcquisitionError("tar_member_size_readback_mismatch")
        except (tarfile.TarError, OSError) as error:
            raise AcquisitionError(
                f"safe_tar_validation_failed:{source.source_id}"
            ) from error
    tracker.require_all(source.source_id)
    required_suffixes = {
        "dict/data.noun",
        "dict/data.verb",
        "dict/data.adj",
        "dict/data.adv",
        "dict/index.noun",
        "dict/index.verb",
        "dict/index.adj",
        "dict/index.adv",
    }
    for suffix in required_suffixes:
        if not any(name.endswith(suffix) for name in wordnet_members):
            raise AcquisitionError(
                f"wordnet_required_member_missing:{suffix.replace('/', '_')}"
            )
    if not any(PurePosixPath(name).name == "LICENSE" for name in wordnet_members):
        raise AcquisitionError("wordnet_bundled_license_missing")
    return {
        "archive_or_document_type": "safe_tar_gzip",
        "member_count": member_count,
        "uncompressed_or_document_bytes": total_bytes,
        "structure_checks": {
            "all_members_streamed": True,
            "bundled_license_present": True,
            "required_dictionary_and_index_members_present": True,
            "regular_member_count": regular_count,
            "special_or_link_members_present": False,
        },
    }


def inspect_safe_zip(
    source: Any,
    data_fd: int,
    envelope: ResourceEnvelope,
    *,
    epub: bool,
) -> dict[str, Any]:
    os.lseek(data_fd, 0, os.SEEK_SET)
    if os.read(data_fd, 4)[:2] != b"PK":
        raise AcquisitionError(f"zip_magic_mismatch:{source.source_id}")
    os.lseek(data_fd, 0, os.SEEK_SET)
    tracker = MarkerTracker(source.required_markers)
    seen_names: set[str] = set()
    total_bytes = 0
    regular_count = 0
    nalt_turtle = bytearray()
    nalt_turtle_member_count = 0
    xml_payloads: dict[str, bytes] = {}
    processed_since_check = 0
    try:
        with os.fdopen(os.dup(data_fd), "rb", closefd=True) as handle:
            with zipfile.ZipFile(handle, mode="r") as archive:
                infos = archive.infolist()
                if not infos or len(infos) > MAX_ARCHIVE_ENTRIES:
                    raise AcquisitionError("zip_member_count_invalid")
                if epub:
                    first = infos[0]
                    if (
                        first.filename != "mimetype"
                        or first.compress_type != zipfile.ZIP_STORED
                    ):
                        raise AcquisitionError(
                            "epub_mimetype_entry_order_or_method_invalid"
                        )
                for info in infos:
                    validate_archive_member_name(info.filename, seen_names)
                    validate_zip_member_mode(info)
                    if info.flag_bits & 0x1:
                        raise AcquisitionError("encrypted_zip_member_forbidden")
                    if info.is_dir():
                        continue
                    if info.file_size < 0 or info.file_size > 1024 * 1024 * 1024:
                        raise AcquisitionError("zip_member_size_invalid")
                    if info.compress_size == 0 and info.file_size > 0:
                        raise AcquisitionError("zip_compressed_size_invalid")
                    if (
                        info.compress_size > 0
                        and info.file_size / info.compress_size > 10_000
                    ):
                        raise AcquisitionError("zip_member_compression_ratio_invalid")
                    total_bytes += info.file_size
                    zip_limit = min(
                        max(source.expected_bytes * 32, 512 * 1024 * 1024),
                        4 * 1024**3,
                    )
                    if total_bytes > zip_limit:
                        raise AcquisitionError("zip_uncompressed_size_limit")
                    regular_count += 1
                    epub_identity_paths = (
                        {
                            source.epub_identity.opf_path,
                            source.epub_identity.navigation_path,
                            source.epub_identity.rights_member_path,
                        }
                        if epub and source.epub_identity is not None
                        else set()
                    )
                    collect_xml = info.filename in {
                        "mimetype",
                        "META-INF/container.xml",
                        *epub_identity_paths,
                    }
                    collect_turtle = (
                        source.source_id == "usda_nalt_core_2024"
                        and info.filename.lower().endswith((".ttl", ".turtle"))
                    )
                    collected = bytearray()
                    marker_eligible = is_textual_archive_member(info.filename)
                    consumed = 0
                    with archive.open(info, mode="r") as stream:
                        while True:
                            chunk = stream.read(1024 * 1024)
                            if not chunk:
                                break
                            consumed += len(chunk)
                            processed_since_check += len(chunk)
                            if marker_eligible:
                                tracker.feed(chunk)
                            if collect_xml or collect_turtle:
                                collected.extend(chunk)
                                limit = (
                                    8 * 1024 * 1024
                                    if collect_xml
                                    else 256 * 1024 * 1024
                                )
                                if len(collected) > limit:
                                    raise AcquisitionError(
                                        "zip_selected_member_too_large"
                                    )
                            if processed_since_check >= 16 * 1024 * 1024:
                                envelope.check(f"zip_inspect:{source.source_id}")
                                processed_since_check = 0
                    tracker.end_stream()
                    if consumed != info.file_size:
                        raise AcquisitionError("zip_member_size_readback_mismatch")
                    if collect_xml:
                        xml_payloads[info.filename] = bytes(collected)
                        if (
                            len(xml_payloads) > 34
                            or sum(len(value) for value in xml_payloads.values())
                            > 64 * 1024 * 1024
                        ):
                            raise AcquisitionError("epub_metadata_collection_limit")
                    if collect_turtle:
                        nalt_turtle_member_count += 1
                        if nalt_turtle_member_count > 1:
                            raise AcquisitionError("nalt_multiple_turtle_members")
                        nalt_turtle.extend(collected)
                        if len(nalt_turtle) > 256 * 1024 * 1024:
                            raise AcquisitionError("nalt_turtle_collection_limit")
    except (zipfile.BadZipFile, OSError, RuntimeError) as error:
        if isinstance(error, AcquisitionError):
            raise
        raise AcquisitionError(
            f"safe_zip_validation_failed:{source.source_id}"
        ) from error
    tracker.require_all(source.source_id)
    if epub:
        structure_checks = validate_epub_identity(source, xml_payloads, seen_names)
        archive_type = "safe_crc_verified_epub"
    elif source.source_id == "usda_nalt_core_2024":
        if nalt_turtle_member_count != 1:
            raise AcquisitionError("nalt_exactly_one_turtle_member_required")
        structure_checks = validate_nalt_core_turtle(bytes(nalt_turtle))
        archive_type = "safe_crc_verified_nalt_core_zip"
    else:
        if not regular_count:
            raise AcquisitionError("zip_no_regular_members")
        structure_checks = {
            "all_member_CRCs_verified": True,
            "regular_member_count": regular_count,
        }
        archive_type = "safe_crc_verified_zip"
    return {
        "archive_or_document_type": archive_type,
        "member_count": len(seen_names),
        "uncompressed_or_document_bytes": total_bytes,
        "structure_checks": structure_checks,
    }


def validate_nalt_core_turtle(payload: bytes) -> dict[str, Any]:
    if not payload:
        raise AcquisitionError("nalt_core_turtle_member_missing")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise AcquisitionError("nalt_core_turtle_not_utf8") from None
    counts = count_nalt_turtle_constructs(text)
    expected = {
        "concepts": 14_196,
        "english_pref_labels": 14_196,
        "alt_labels": 19_075,
        "hidden_labels": 0,
    }
    if counts != expected:
        raise AcquisitionError("nalt_core_authoritative_count_mismatch")
    return {
        "all_member_CRCs_verified": True,
        "turtle_member_present": True,
        "authoritative_counts": counts,
        "authoritative_counts_verified": True,
    }


def count_nalt_turtle_constructs(text: str) -> dict[str, int]:
    """Count unique English SKOS assertions in the exact NALT Turtle dialect."""

    validate_nalt_prefix_bindings(text)
    concepts: set[str] = set()
    preferred: dict[str, set[str]] = {}
    alternate: set[tuple[str, str]] = set()
    hidden: set[tuple[str, str]] = set()
    state = "subject"
    subject: str | None = None
    predicate: str | None = None
    pending_literal: tuple[str, str, str] | None = None
    object_complete = False
    nested: list[str] = []
    directives = {"@base", "@prefix", "BASE", "PREFIX"}

    def record_literal(
        literal_subject: str,
        literal_predicate: str,
        literal: str,
        language: str | None,
    ) -> None:
        if (
            language is None
            or re.fullmatch(r"@en(?:-[A-Za-z0-9]+)*", language, flags=re.IGNORECASE)
            is None
        ):
            return
        if literal_predicate == "skos:prefLabel":
            preferred.setdefault(literal_subject, set()).add(literal)
        elif literal_predicate == "skos:altLabel":
            alternate.add((literal_subject, literal))
        elif literal_predicate == "skos:hiddenLabel":
            hidden.add((literal_subject, literal))

    for token_type, token in turtle_tokens(text):
        if state == "directive":
            if token == ".":
                state = "subject"
            continue
        if nested:
            if token in {"[", "("}:
                nested.append(token)
            elif token == "]" and nested[-1] == "[":
                nested.pop()
            elif token == ")" and nested[-1] == "(":
                nested.pop()
            if not nested:
                object_complete = True
            continue
        if pending_literal is not None:
            literal_subject, literal_predicate, literal = pending_literal
            if token_type == "word" and token.startswith("@"):
                record_literal(literal_subject, literal_predicate, literal, token)
                pending_literal = None
                object_complete = True
                continue
            if token_type == "word" and token.startswith("^^"):
                pending_literal = None
                object_complete = True
                continue
            record_literal(literal_subject, literal_predicate, literal, None)
            pending_literal = None
            object_complete = True
        if state == "subject":
            if token in directives:
                state = "directive"
                continue
            if token == ".":
                continue
            if token_type == "string" or token in {";", ",", "]", ")"}:
                raise AcquisitionError("nalt_turtle_subject_invalid")
            subject = token
            state = "predicate"
            continue
        if state == "predicate":
            if token == ".":
                state = "subject"
                subject = None
                continue
            if token == ";":
                continue
            if subject is None or token_type == "string" or token in {",", "]", ")"}:
                raise AcquisitionError("nalt_turtle_predicate_invalid")
            predicate = token
            object_complete = False
            state = "object"
            continue
        if token in {"[", "("}:
            if object_complete:
                raise AcquisitionError("nalt_turtle_object_separator_missing")
            nested.append(token)
            continue
        if token == ",":
            if not object_complete:
                raise AcquisitionError("nalt_turtle_empty_object")
            object_complete = False
            continue
        if token == ";":
            if not object_complete:
                raise AcquisitionError("nalt_turtle_empty_object")
            state = "predicate"
            predicate = None
            continue
        if token == ".":
            if not object_complete:
                raise AcquisitionError("nalt_turtle_empty_object")
            state = "subject"
            subject = None
            predicate = None
            continue
        if object_complete or subject is None or predicate is None:
            raise AcquisitionError("nalt_turtle_object_separator_missing")
        if predicate in {"a", "rdf:type"} and token == "skos:Concept":
            concepts.add(subject)
            object_complete = True
            continue
        if token_type == "string":
            pending_literal = (subject, predicate, token)
            continue
        object_complete = True
    if pending_literal is not None:
        record_literal(*pending_literal, None)
    if nested or state != "subject" or subject is not None:
        raise AcquisitionError("nalt_turtle_structure_unterminated")
    label_subjects = set(preferred)
    label_subjects.update(subject for subject, _literal in alternate)
    label_subjects.update(subject for subject, _literal in hidden)
    if not label_subjects.issubset(concepts):
        raise AcquisitionError("nalt_label_subject_not_concept")
    if set(preferred) != concepts or any(
        len(values) != 1 for values in preferred.values()
    ):
        raise AcquisitionError("nalt_exactly_one_english_pref_label_required")
    return {
        "concepts": len(concepts),
        "english_pref_labels": sum(len(values) for values in preferred.values()),
        "alt_labels": len(alternate),
        "hidden_labels": len(hidden),
    }


def validate_nalt_prefix_bindings(text: str) -> None:
    expected = {
        "rdf": RDF_NS,
        "skos": "http://www.w3.org/2004/02/skos/core#",
    }
    observed: dict[str, list[str]] = {name: [] for name in expected}
    pattern = re.compile(
        r"(?im)^[ \t]*@prefix[ \t]+(rdf|skos):[ \t]*<([^>\r\n]+)>[ \t]*\.[ \t]*(?:#.*)?$"
    )
    for match in pattern.finditer(text):
        observed[match.group(1).casefold()].append(match.group(2))
    if re.search(r"(?im)^[ \t]*PREFIX[ \t]+(?:rdf|skos):", text):
        raise AcquisitionError("nalt_prefix_form_not_preregistered")
    if any(observed[name] != [namespace] for name, namespace in expected.items()):
        raise AcquisitionError("nalt_prefix_binding_mismatch")


def turtle_tokens(text: str):
    """Yield safe lexical tokens sufficient for top-level SKOS counting."""

    index = 0
    length = len(text)
    punctuation = {";", ",", ".", "[", "]", "(", ")"}
    while index < length:
        character = text[index]
        if character.isspace():
            index += 1
            continue
        if character == "#":
            newline = text.find("\n", index + 1)
            index = length if newline < 0 else newline + 1
            continue
        if character in punctuation:
            yield "punctuation", character
            index += 1
            continue
        if character == "<":
            end = index + 1
            while end < length:
                if text[end] == ">" and not turtle_character_is_escaped(text, end):
                    break
                end += 1
            if end >= length:
                raise AcquisitionError("nalt_turtle_IRI_unterminated")
            yield "iri", text[index : end + 1]
            index = end + 1
            continue
        if character in {'"', "'"}:
            quote = character
            triple = text.startswith(quote * 3, index)
            delimiter = quote * (3 if triple else 1)
            end = index + len(delimiter)
            while end < length:
                if text.startswith(delimiter, end) and not turtle_character_is_escaped(
                    text, end
                ):
                    break
                if text[end] == "\\":
                    end += 2
                else:
                    end += 1
            if end >= length:
                raise AcquisitionError("nalt_turtle_literal_unterminated")
            yield "string", text[index : end + len(delimiter)]
            index = end + len(delimiter)
            continue
        end = index + 1
        while (
            end < length
            and not text[end].isspace()
            and text[end] not in punctuation
            and text[end] != "#"
        ):
            end += 1
        yield "word", text[index:end]
        index = end


def turtle_character_is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1


def validate_epub_identity(
    source: Any,
    payloads: Mapping[str, bytes],
    archive_names: set[str],
) -> dict[str, Any]:
    identity = source.epub_identity
    if identity is None:
        raise AcquisitionError("epub_preregistered_identity_missing")
    if payloads.get("mimetype") != b"application/epub+zip":
        raise AcquisitionError("epub_mimetype_payload_invalid")
    container_payload = payloads.get("META-INF/container.xml")
    if container_payload is None:
        raise AcquisitionError("epub_container_missing")
    internal_member_sha256 = {
        "container": "sha256:" + hashlib.sha256(container_payload).hexdigest(),
    }
    if (
        identity.container_sha256 is not None
        and internal_member_sha256["container"] != "sha256:" + identity.container_sha256
    ):
        raise AcquisitionError("epub_container_sha256_mismatch")
    reject_forbidden_xml_markup(container_payload, source.source_id)
    try:
        container = ElementTree.fromstring(container_payload)
    except ElementTree.ParseError:
        raise AcquisitionError("epub_container_xml_invalid") from None
    if container.tag != qualified_xml_name(EPUB_CONTAINER_NS, "container"):
        raise AcquisitionError("epub_container_namespace_invalid")
    for element in container.iter():
        if local_xml_name(element.tag) in {"container", "rootfiles", "rootfile"} and (
            not isinstance(element.tag, str)
            or not element.tag.startswith(f"{{{EPUB_CONTAINER_NS}}}")
        ):
            raise AcquisitionError("epub_container_namespace_invalid")
    rootfiles = [
        (
            element.attrib.get("full-path"),
            element.attrib.get("media-type"),
        )
        for element in container.iter()
        if element.tag == qualified_xml_name(EPUB_CONTAINER_NS, "rootfile")
    ]
    if (
        len(rootfiles) != 1
        or not rootfiles[0][0]
        or rootfiles[0][1] != "application/oebps-package+xml"
    ):
        raise AcquisitionError("epub_rootfile_identity_invalid")
    opf_path = rootfiles[0][0]
    if opf_path is None:
        raise AcquisitionError("epub_rootfile_identity_invalid")
    validate_archive_member_name(opf_path, set())
    if opf_path != identity.opf_path:
        raise AcquisitionError("epub_declared_OPF_path_mismatch")
    opf_payload = payloads.get(opf_path)
    if opf_payload is None or opf_path not in archive_names:
        raise AcquisitionError("epub_declared_opf_missing")
    if hashlib.sha256(opf_payload).hexdigest() != identity.opf_sha256:
        raise AcquisitionError("epub_OPF_sha256_mismatch")
    navigation_payload = payloads.get(identity.navigation_path)
    rights_payload = payloads.get(identity.rights_member_path)
    if (
        navigation_payload is None
        or identity.navigation_path not in archive_names
        or rights_payload is None
        or identity.rights_member_path not in archive_names
    ):
        raise AcquisitionError("epub_bound_navigation_or_rights_member_missing")
    if hashlib.sha256(navigation_payload).hexdigest() != identity.navigation_sha256:
        raise AcquisitionError("epub_navigation_sha256_mismatch")
    if hashlib.sha256(rights_payload).hexdigest() != identity.rights_member_sha256:
        raise AcquisitionError("epub_rights_member_sha256_mismatch")
    internal_member_sha256.update(
        {
            "navigation": "sha256:" + hashlib.sha256(navigation_payload).hexdigest(),
            "opf": "sha256:" + hashlib.sha256(opf_payload).hexdigest(),
            "rights": "sha256:" + hashlib.sha256(rights_payload).hexdigest(),
        }
    )
    rights_tracker = MarkerTracker(source.required_markers)
    rights_tracker.feed(rights_payload, continue_stream=False)
    rights_tracker.require_all(source.source_id)
    reject_forbidden_xml_markup(opf_payload, source.source_id)
    try:
        package = ElementTree.fromstring(opf_payload)
    except ElementTree.ParseError:
        raise AcquisitionError("epub_opf_xml_invalid") from None
    if package.tag != qualified_xml_name(OPF_NS, "package"):
        raise AcquisitionError("epub_opf_namespace_invalid")
    expected_namespaces = {
        "package": OPF_NS,
        "metadata": OPF_NS,
        "manifest": OPF_NS,
        "item": OPF_NS,
        "spine": OPF_NS,
        "itemref": OPF_NS,
        "meta": OPF_NS,
        "title": DC_NS,
        "language": DC_NS,
        "identifier": DC_NS,
        "creator": DC_NS,
        "publisher": DC_NS,
        "rights": DC_NS,
        "subject": DC_NS,
    }
    for element in package.iter():
        local_name = local_xml_name(element.tag)
        expected_namespace = expected_namespaces.get(local_name)
        if expected_namespace is not None and element.tag != qualified_xml_name(
            expected_namespace, local_name
        ):
            raise AcquisitionError(f"epub_OPF_namespace_invalid:{local_name}")
    structural_counts = {
        local_name: sum(
            1
            for element in package.iter()
            if element.tag == qualified_xml_name(OPF_NS, local_name)
        )
        for local_name in ("metadata", "manifest", "spine")
    }
    if any(count != 1 for count in structural_counts.values()):
        raise AcquisitionError("epub_OPF_package_structure_invalid")
    package_version = package.attrib.get("version")
    unique_identifier_id = package.attrib.get("unique-identifier")
    if package_version is None or re.fullmatch(r"3\.[0-9]+", package_version) is None:
        raise AcquisitionError("epub_package_version_invalid")
    if (
        identity.package_version is not None
        and package_version != identity.package_version
    ):
        raise AcquisitionError("epub_package_version_mismatch")
    if (
        unique_identifier_id is None
        or re.fullmatch(r"[A-Za-z_][A-Za-z0-9._:-]{0,127}", unique_identifier_id)
        is None
    ):
        raise AcquisitionError("epub_package_unique_identifier_invalid")
    if source.url.rsplit("/", 1)[
        -1
    ] != source.filename or not source.filename.startswith(
        f"{identity.filename_grade_token}_{identity.filename_subject_token}_"
    ):
        raise AcquisitionError("epub_filename_subject_grade_contract_mismatch")
    identifiers = epub_dc_values(package, "identifier")
    titles = epub_dc_values(package, "title")
    languages = epub_dc_values(package, "language")
    modified = [
        (element.text or "").strip()
        for element in package.iter()
        if element.tag == qualified_xml_name(OPF_NS, "meta")
        and element.attrib.get("property") == "dcterms:modified"
    ]
    if identifiers != [identity.identifier]:
        raise AcquisitionError("epub_identifier_metadata_mismatch")
    if titles != [identity.title]:
        raise AcquisitionError("epub_title_metadata_mismatch")
    if languages != [identity.language]:
        raise AcquisitionError("epub_language_metadata_mismatch")
    if modified != [identity.modified]:
        raise AcquisitionError("epub_modified_metadata_mismatch")
    linked_identifiers = [
        element
        for element in package.iter()
        if element.tag == qualified_xml_name(DC_NS, "identifier")
        and element.attrib.get("id") == unique_identifier_id
    ]
    if (
        len(linked_identifiers) != 1
        or (linked_identifiers[0].text or "").strip() != identity.identifier
    ):
        raise AcquisitionError("epub_package_unique_identifier_link_mismatch")
    observed_metadata = {
        "dc_creator_values": epub_dc_values(package, "creator"),
        "dc_identifier_values": identifiers,
        "dc_language_values": languages,
        "dc_publisher_values": epub_dc_values(package, "publisher"),
        "dc_rights_values": epub_dc_values(package, "rights"),
        "dc_subject_values": epub_dc_values(package, "subject"),
        "dc_title_values": titles,
        "dcterms_modified_values": modified,
        "grade_metadata_values": epub_grade_metadata_values(package),
    }
    expected_observed_metadata = {
        "dc_creator_values": list(identity.opf_creator_values),
        "dc_identifier_values": [identity.identifier],
        "dc_language_values": [identity.language],
        "dc_publisher_values": list(identity.opf_publisher_values),
        "dc_rights_values": list(identity.opf_rights_values),
        "dc_subject_values": list(identity.opf_subject_values),
        "dc_title_values": [identity.title],
        "dcterms_modified_values": [identity.modified],
    }
    if any(
        observed_metadata.get(field) != expected
        for field, expected in expected_observed_metadata.items()
    ) or (
        identity.opf_grade_values is not None
        and observed_metadata["grade_metadata_values"]
        != list(identity.opf_grade_values)
    ):
        raise AcquisitionError("epub_preregistered_metadata_observation_mismatch")
    manifest_ids: dict[str, tuple[str, str, tuple[str, ...]]] = {}
    manifest_targets: set[str] = set()
    xhtml_ids: set[str] = set()
    for element in package.iter():
        if element.tag != qualified_xml_name(OPF_NS, "item"):
            continue
        item_id = element.attrib.get("id")
        href = element.attrib.get("href")
        media_type = element.attrib.get("media-type")
        properties = manifest_property_tokens(element.attrib.get("properties", ""))
        if not item_id or not href or not media_type:
            raise AcquisitionError("epub_manifest_item_invalid")
        resolved = resolve_epub_member(opf_path, href)
        if resolved not in archive_names:
            raise AcquisitionError("epub_manifest_member_missing")
        if item_id in manifest_ids:
            raise AcquisitionError("epub_duplicate_manifest_id")
        if resolved in manifest_targets:
            raise AcquisitionError("epub_duplicate_manifest_target")
        manifest_ids[item_id] = (resolved, media_type, properties)
        manifest_targets.add(resolved)
        if media_type == "application/xhtml+xml":
            xhtml_ids.add(item_id)
    navigation_items = [
        (item_id, *item) for item_id, item in manifest_ids.items() if "nav" in item[2]
    ]
    if len(navigation_items) != 1:
        raise AcquisitionError("epub_unique_navigation_manifest_item_required")
    (
        _navigation_id,
        navigation_member,
        navigation_media_type,
        navigation_properties,
    ) = navigation_items[0]
    if (
        navigation_member != identity.navigation_path
        or navigation_media_type != "application/xhtml+xml"
    ):
        raise AcquisitionError("epub_navigation_manifest_binding_mismatch")
    rights_items = [
        (item_id, *item)
        for item_id, item in manifest_ids.items()
        if item[0] == identity.rights_member_path
    ]
    if (
        len(rights_items) != 1
        or rights_items[0][2] != "application/xhtml+xml"
        or "nav" in rights_items[0][3]
    ):
        raise AcquisitionError("epub_rights_manifest_binding_mismatch")
    spine_ids = [
        element.attrib.get("idref")
        for element in package.iter()
        if element.tag == qualified_xml_name(OPF_NS, "itemref")
    ]
    if (
        not xhtml_ids
        or not spine_ids
        or any(item not in xhtml_ids for item in spine_ids)
        or len(spine_ids) != len(set(spine_ids))
    ):
        raise AcquisitionError("epub_manifest_or_spine_invalid")
    if (
        identity.navigation_path not in manifest_targets
        or identity.rights_member_path not in manifest_targets
    ):
        raise AcquisitionError("epub_bound_evidence_not_in_manifest")
    navigation_structure = validate_epub_navigation_member(
        navigation_payload,
        source.source_id,
        identity.navigation_path,
        archive_names,
    )
    rights_structure = validate_epub_rights_member(
        rights_payload,
        source.source_id,
        identity.artifact_notice_url,
    )
    return {
        "all_member_CRCs_verified": True,
        "container_and_declared_OPF_verified": True,
        "internal_member_sha256": internal_member_sha256,
        "manifest_and_spine_verified": True,
        "metadata_observation": observed_metadata,
        "mimetype_first_and_stored": True,
        "navigation_toc_structure": {
            "manifest_media_type": navigation_media_type,
            "manifest_properties": list(navigation_properties),
            **navigation_structure,
        },
        "package_identity": {
            "unique_identifier_id": unique_identifier_id,
            "unique_identifier_linked": True,
            "version": package_version,
        },
        "preregistered_catalogue_conflict_context_bound": True,
        "rights_context": {
            "artifact_notice_license_id": identity.artifact_notice_license_id,
            "artifact_notice_url": identity.artifact_notice_url,
            "catalogue_license_id": identity.catalogue_license_id,
            "catalogue_or_terms_evidence_runtime_verified": False,
            "preregistered_rights_subject_template_mismatch": (
                identity.rights_subject_template_mismatch
            ),
            "resolved_license_id": identity.resolved_license_id,
        },
        "rights_link_structure": {
            "manifest_media_type": rights_items[0][2],
            **rights_structure,
        },
        "subject_grade_evidence": {
            "catalogue": {
                "evidence_root_sha256": "sha256:"
                + identity.catalogue_evidence_root_sha256,
                "grade": identity.catalogue_grade,
                "subject": identity.catalogue_subject,
            },
            "download_filename": {
                "filename": source.filename,
                "grade_token": identity.filename_grade_token,
                "subject_token": identity.filename_subject_token,
            },
            "opf_observation": {
                "dc_subject_values": observed_metadata["dc_subject_values"],
                "grade_metadata_values": observed_metadata["grade_metadata_values"],
                "grade_assertion_present": bool(
                    observed_metadata["grade_metadata_values"]
                ),
                "subject_assertion_present": bool(
                    observed_metadata["dc_subject_values"]
                ),
            },
        },
        "xhtml_manifest_item_count": len(xhtml_ids),
        "spine_item_count": len(spine_ids),
    }


def epub_dc_values(package: ElementTree.Element, local_name: str) -> list[str]:
    return [
        (element.text or "").strip()
        for element in package.iter()
        if element.tag == qualified_xml_name(DC_NS, local_name)
    ]


def epub_grade_metadata_values(package: ElementTree.Element) -> list[str]:
    values: list[str] = []
    for element in package.iter():
        if element.tag != qualified_xml_name(OPF_NS, "meta"):
            continue
        property_name = element.attrib.get("property", "")
        normalized_property = property_name.rsplit(":", 1)[-1].casefold()
        if normalized_property not in {"educationlevel", "educationallevel", "grade"}:
            continue
        values.append((element.text or "").strip())
    return values


def manifest_property_tokens(value: str) -> tuple[str, ...]:
    tokens = tuple(value.split())
    if len(tokens) != len(set(tokens)) or any(
        re.fullmatch(r"[A-Za-z][A-Za-z0-9._:-]*", token) is None for token in tokens
    ):
        raise AcquisitionError("epub_manifest_properties_invalid")
    return tokens


def validate_epub_xhtml_member(
    payload: bytes, source_id: str, role: str
) -> ElementTree.Element:
    if role == "rights":
        try:
            decoded = payload.decode(xml_scan_encoding(payload[:4]), errors="strict")
        except UnicodeDecodeError:
            raise AcquisitionError(f"XML_encoding_invalid:{source_id}") from None
        if decoded.count("<!DOCTYPE html>") != 1:
            raise AcquisitionError("epub_rights_HTML5_doctype_mismatch")
        without_html5_doctype = decoded.replace("<!DOCTYPE html>", "", 1)
        if XML_FORBIDDEN_RE.search(without_html5_doctype):
            raise AcquisitionError(f"forbidden_XML_markup:{source_id}")
    else:
        reject_forbidden_xml_markup(payload, source_id)
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        raise AcquisitionError(f"epub_{role}_XHTML_invalid") from None
    if root.tag != qualified_xml_name(XHTML_NS, "html"):
        raise AcquisitionError(f"epub_{role}_XHTML_namespace_invalid")
    for element in root.iter():
        if local_xml_name(element.tag) in {"a", "body", "html", "nav"} and (
            not isinstance(element.tag, str)
            or not element.tag.startswith(f"{{{XHTML_NS}}}")
        ):
            raise AcquisitionError(f"epub_{role}_XHTML_namespace_invalid")
    return root


def validate_epub_navigation_member(
    payload: bytes,
    source_id: str,
    member_path: str,
    archive_names: set[str],
) -> dict[str, int]:
    root = validate_epub_xhtml_member(payload, source_id, "navigation")
    toc_nodes = [
        element
        for element in root.iter()
        if element.tag == qualified_xml_name(XHTML_NS, "nav")
        and "toc"
        in element.attrib.get(qualified_xml_name(EPUB_OPS_NS, "type"), "").split()
    ]
    if len(toc_nodes) != 1:
        raise AcquisitionError("epub_navigation_unique_TOC_role_required")
    toc_links = [
        element.attrib.get("href", "")
        for element in toc_nodes[0].iter()
        if element.tag == qualified_xml_name(XHTML_NS, "a")
    ]
    if not toc_links or any(not href for href in toc_links):
        raise AcquisitionError("epub_navigation_TOC_link_missing")
    for href in toc_links:
        resolved = resolve_epub_member(member_path, href)
        if resolved not in archive_names:
            raise AcquisitionError("epub_navigation_TOC_target_missing")
    return {"toc_link_count": len(toc_links), "toc_nav_count": 1}


def validate_epub_rights_member(
    payload: bytes,
    source_id: str,
    artifact_notice_url: str,
) -> dict[str, Any]:
    root = validate_epub_xhtml_member(payload, source_id, "rights")
    notice_links = [
        element
        for element in root.iter()
        if element.tag == qualified_xml_name(XHTML_NS, "a")
        and element.attrib.get("href") == artifact_notice_url
    ]
    if not notice_links:
        raise AcquisitionError("epub_rights_structured_license_link_missing")
    return {
        "artifact_notice_url": artifact_notice_url,
        "structured_license_link_count": len(notice_links),
    }


def resolve_epub_member(opf_path: str, href: str) -> str:
    if not href or "\x00" in href or "\\" in href:
        raise AcquisitionError("epub_manifest_href_invalid")
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc:
        raise AcquisitionError("epub_remote_manifest_URI_rejected")
    href_path = unquote(parsed.path)
    if not href_path:
        if parsed.fragment:
            return opf_path
        raise AcquisitionError("epub_manifest_href_invalid")
    if href_path.startswith("/"):
        raise AcquisitionError("epub_manifest_href_escapes_root")
    base = PurePosixPath(opf_path).parent
    combined = base / PurePosixPath(href_path)
    parts: list[str] = []
    for part in combined.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise AcquisitionError("epub_manifest_href_escapes_root")
            parts.pop()
            continue
        parts.append(part)
    if not parts:
        raise AcquisitionError("epub_manifest_href_invalid")
    result = "/".join(parts)
    validate_archive_member_name(result, set())
    return result


def inspect_obo_or_text(
    source: Any, data_fd: int, envelope: ResourceEnvelope
) -> dict[str, Any]:
    tracker = MarkerTracker(source.required_markers)
    term_count = 0
    id_count = 0
    name_count = 0
    definition_count = 0
    byte_count = 0
    os.lseek(data_fd, 0, os.SEEK_SET)
    with os.fdopen(os.dup(data_fd), "rb", closefd=True) as handle:
        for line_index, line in enumerate(handle, start=1):
            byte_count += len(line)
            tracker.feed(line)
            if line.rstrip(b"\r\n") == b"[Term]":
                term_count += 1
            elif line.startswith(b"id: "):
                id_count += 1
            elif line.startswith(b"name: "):
                name_count += 1
            elif line.startswith(b"def: "):
                definition_count += 1
            if line_index % 250_000 == 0:
                envelope.check(f"text_inspect:{source.source_id}")
    tracker.require_all(source.source_id)
    if byte_count != source.expected_bytes:
        raise AcquisitionError("text_document_size_mismatch")
    if source.media_type.split(";", 1)[0] == "text/obo":
        if term_count < 100 or id_count < term_count or name_count < term_count // 2:
            raise AcquisitionError("obo_term_structure_invalid")
        checks = {
            "OBO_term_stanzas": term_count,
            "definition_line_count": definition_count,
            "id_line_count": id_count,
            "name_line_count": name_count,
            "release_and_license_headers_verified": True,
        }
        document_type = "validated_OBO_document"
    else:
        if b"data-version:" not in read_fd_prefix(data_fd, 1024 * 1024):
            raise AcquisitionError("ontology_text_header_missing")
        checks = {
            "document_nonempty": True,
            "release_and_license_headers_verified": True,
        }
        document_type = "validated_ontology_text_document"
    return {
        "archive_or_document_type": document_type,
        "member_count": 1,
        "uncompressed_or_document_bytes": byte_count,
        "structure_checks": checks,
    }


def inspect_rdf_xml(
    source: Any, data_fd: int, envelope: ResourceEnvelope
) -> dict[str, Any]:
    os.lseek(data_fd, 0, os.SEEK_SET)
    payload = read_fd_bounded(data_fd, source.expected_bytes)
    if len(payload) != source.expected_bytes:
        raise AcquisitionError("rdf_document_size_mismatch")
    reject_forbidden_xml_markup(payload, source.source_id)
    tracker = MarkerTracker(source.required_markers)
    tracker.feed(payload, continue_stream=False)
    byte_count = len(payload)
    tracker.require_all(source.source_id)
    description_count = 0
    root_seen = False
    os.lseek(data_fd, 0, os.SEEK_SET)
    try:
        with os.fdopen(os.dup(data_fd), "rb", closefd=True) as handle:
            for event_index, (event, element) in enumerate(
                ElementTree.iterparse(handle, events=("start", "end")), start=1
            ):
                if not root_seen and event == "start":
                    root_seen = True
                    if element.tag != qualified_xml_name(RDF_NS, "RDF"):
                        raise AcquisitionError("rdf_root_namespace_mismatch")
                if event == "end" and element.tag == qualified_xml_name(
                    RDF_NS, "Description"
                ):
                    description_count += 1
                elif event == "end" and local_xml_name(element.tag) == "Description":
                    raise AcquisitionError("rdf_description_namespace_mismatch")
                if event == "end":
                    element.clear()
                if event_index % 50_000 == 0:
                    envelope.check(f"rdf_inspect:{source.source_id}")
    except ElementTree.ParseError:
        raise AcquisitionError("rdf_xml_not_well_formed") from None
    if description_count < 100:
        raise AcquisitionError("rdf_description_count_implausible")
    return {
        "archive_or_document_type": "well_formed_RDF_XML_document",
        "member_count": 1,
        "uncompressed_or_document_bytes": byte_count,
        "structure_checks": {
            "RDF_description_count": description_count,
            "date_and_public_domain_markers_verified": True,
            "well_formed_XML": True,
        },
    }


def validate_archive_member_name(name: str, seen: set[str]) -> None:
    if (
        not isinstance(name, str)
        or not name
        or len(name.encode("utf-8")) > 1024
        or "\x00" in name
        or "\\" in name
        or "//" in name
        or any(ord(character) < 32 or ord(character) == 127 for character in name)
    ):
        raise AcquisitionError("archive_member_name_invalid")
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise AcquisitionError("archive_absolute_member_forbidden")
    path = PurePosixPath(name)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise AcquisitionError("archive_traversal_member_forbidden")
    normalized = "/".join(path.parts)
    if normalized in seen:
        raise AcquisitionError("archive_duplicate_member_forbidden")
    seen.add(normalized)


def validate_zip_member_mode(info: zipfile.ZipInfo) -> None:
    mode = (info.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(mode)
    allowed = {0, stat.S_IFREG, stat.S_IFDIR}
    if file_type not in allowed:
        raise AcquisitionError("zip_link_or_special_member_forbidden")


def is_textual_archive_member(name: str) -> bool:
    lower = name.casefold()
    basename = PurePosixPath(lower).name
    return basename in {"license", "copying", "mimetype"} or lower.endswith(
        (
            ".css",
            ".csv",
            ".htm",
            ".html",
            ".js",
            ".json",
            ".ncx",
            ".obo",
            ".opf",
            ".rdf",
            ".text",
            ".ttl",
            ".txt",
            ".xhtml",
            ".xml",
        )
    )


def local_xml_name(tag: Any) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def qualified_xml_name(namespace: str, local_name: str) -> str:
    return f"{{{namespace}}}{local_name}"


def xml_scan_encoding(prefix: bytes) -> str:
    if prefix.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        return "utf-32"
    if prefix.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    if prefix.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if prefix.startswith(b"\x3c\x00\x00\x00"):
        return "utf-32-le"
    if prefix.startswith(b"\x00\x00\x00\x3c"):
        return "utf-32-be"
    if len(prefix) >= 4 and prefix[0] == 0x3C and prefix[1] == 0 and prefix[3] == 0:
        return "utf-16-le"
    if len(prefix) >= 4 and prefix[0] == 0 and prefix[1] == 0x3C and prefix[2] == 0:
        return "utf-16-be"
    return "utf-8"


def reject_forbidden_xml_markup(payload: bytes, source_id: str) -> None:
    try:
        decoded = payload.decode(xml_scan_encoding(payload[:4]), errors="strict")
    except UnicodeDecodeError:
        raise AcquisitionError(f"XML_encoding_invalid:{source_id}") from None
    if XML_FORBIDDEN_RE.search(decoded):
        raise AcquisitionError(f"forbidden_XML_markup:{source_id}")


def remove_owned_directory_tree(
    parent_fd: int,
    name: str,
    envelope: ResourceEnvelope,
    checkpoint: str,
    counter: list[int] | None = None,
) -> None:
    """Delete an owner-only directory tree without following any link."""

    counter = counter if counter is not None else [0]
    try:
        info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as error:
        raise AcquisitionError("git_metadata_lstat_failed") from error
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.geteuid()
        or info.st_gid != os.getegid()
    ):
        raise AcquisitionError("git_metadata_directory_invalid")
    try:
        directory_fd = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
    except OSError as error:
        raise AcquisitionError("git_metadata_directory_open_failed") from error
    try:
        for child in sorted(os.listdir(directory_fd)):
            child_info = os.stat(child, dir_fd=directory_fd, follow_symlinks=False)
            if child_info.st_uid != os.geteuid() or child_info.st_gid != os.getegid():
                raise AcquisitionError("git_metadata_entry_owner_mismatch")
            if stat.S_ISDIR(child_info.st_mode):
                remove_owned_directory_tree(
                    directory_fd,
                    child,
                    envelope,
                    checkpoint,
                    counter,
                )
            elif stat.S_ISREG(child_info.st_mode) and child_info.st_nlink == 1:
                os.unlink(child, dir_fd=directory_fd)
            else:
                raise AcquisitionError("git_metadata_unsafe_entry")
            counter[0] += 1
            if counter[0] % 128 == 0:
                envelope.check(checkpoint)
        os.fsync(directory_fd)
    except OSError as error:
        raise AcquisitionError("git_metadata_removal_failed") from error
    finally:
        os.close(directory_fd)
    try:
        os.rmdir(name, dir_fd=parent_fd)
        os.fsync(parent_fd)
    except OSError as error:
        raise AcquisitionError("git_metadata_directory_removal_failed") from error


def remove_git_metadata(
    checkout: Path,
    envelope: ResourceEnvelope,
    source_id: str,
) -> None:
    checkout_fd = os.open(
        checkout,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        remove_owned_directory_tree(
            checkout_fd,
            ".git",
            envelope,
            f"git_metadata_remove:{source_id}",
        )
        try:
            os.stat(".git", dir_fd=checkout_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise AcquisitionError(f"git_metadata_removal_incomplete:{source_id}")
    finally:
        os.close(checkout_fd)


def acquire_git_source(
    source: Any,
    git_root: Path,
    candidate: PrivateCandidate,
    envelope: ResourceEnvelope,
    allowed_hosts: frozenset[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_source_component(source.source_id, "source_id")
    validate_https_url(source.clone_url, allowed_hosts)
    if urlsplit(source.clone_url).hostname != "github.com":
        raise AcquisitionError("git_source_host_not_github")
    source_dir = git_root / source.source_id
    create_owner_only_directory(source_dir, git_root)
    checkout = source_dir / "checkout"
    os.mkdir(checkout, mode=0o700)
    run_git(
        ["init", "--quiet"],
        checkout,
        envelope,
        f"git_init:{source.source_id}",
    )
    run_git(
        ["remote", "add", "origin", source.clone_url],
        checkout,
        envelope,
        f"git_remote:{source.source_id}",
    )
    fetch_attempts = run_git_with_retries(
        [
            "fetch",
            "--quiet",
            "--no-tags",
            "--filter=blob:none",
            "--depth=1",
            "origin",
            source.commit_sha,
        ],
        checkout,
        envelope,
        f"git_fetch:{source.source_id}",
    )
    fetched_commit = run_git_text(
        ["rev-parse", "FETCH_HEAD^{commit}"],
        checkout,
        envelope,
        f"git_verify_fetch:{source.source_id}",
    )
    if fetched_commit != source.commit_sha:
        raise AcquisitionError(f"git_fetched_commit_mismatch:{source.source_id}")
    observed_tree = run_git_text(
        ["rev-parse", f"{source.commit_sha}^{{tree}}"],
        checkout,
        envelope,
        f"git_verify_tree:{source.source_id}",
    )
    if observed_tree != source.tree_sha:
        raise AcquisitionError(f"git_tree_mismatch:{source.source_id}")
    tree_payload = run_git_capture(
        [
            "ls-tree",
            "-r",
            "-z",
            "--full-tree",
            source.commit_sha,
            "--",
            *source.selected_paths,
        ],
        checkout,
        envelope,
        f"git_tree_manifest:{source.source_id}",
        max_bytes=2 * 1024 * 1024,
    )
    tree_records = parse_git_tree_records(tree_payload, source)
    run_git(
        ["sparse-checkout", "init", "--no-cone"],
        checkout,
        envelope,
        f"git_sparse_init:{source.source_id}",
    )
    sparse_patterns = [
        sparse_checkout_pattern(path, tree_records) for path in source.selected_paths
    ]
    run_git(
        ["sparse-checkout", "set", "--no-cone", *sparse_patterns],
        checkout,
        envelope,
        f"git_sparse_set:{source.source_id}",
    )
    run_git(
        ["checkout", "--quiet", "--detach", source.commit_sha],
        checkout,
        envelope,
        f"git_checkout:{source.source_id}",
    )
    observed_commit = run_git_text(
        ["rev-parse", "HEAD"],
        checkout,
        envelope,
        f"git_HEAD:{source.source_id}",
    )
    observed_head_tree = run_git_text(
        ["rev-parse", "HEAD^{tree}"],
        checkout,
        envelope,
        f"git_HEAD_tree:{source.source_id}",
    )
    if observed_commit != source.commit_sha or observed_head_tree != source.tree_sha:
        raise AcquisitionError(f"git_HEAD_or_tree_mismatch:{source.source_id}")
    remote_url = run_git_text(
        ["remote", "get-url", "origin"],
        checkout,
        envelope,
        f"git_remote_verify:{source.source_id}",
    )
    if remote_url != source.clone_url:
        raise AcquisitionError(f"git_remote_url_mismatch:{source.source_id}")
    status = run_git_capture(
        ["status", "--porcelain=v1", "--untracked-files=all"],
        checkout,
        envelope,
        f"git_status:{source.source_id}",
        max_bytes=1024 * 1024,
    )
    if status:
        raise AcquisitionError(f"git_worktree_not_clean:{source.source_id}")

    manifest_files, selected_bytes = build_worktree_manifest(
        checkout,
        source,
        tree_records,
        envelope,
    )
    license_path = checkout / "LICENSE"
    observed_license_sha256 = file_sha256(license_path)
    if observed_license_sha256 != "sha256:" + source.license_sha256:
        raise AcquisitionError(f"git_license_sha256_mismatch:{source.source_id}")
    content_manifest = {
        "schema_version": "cur0s_git_sparse_content_manifest_v1",
        "commit_sha": source.commit_sha,
        "tree_sha": source.tree_sha,
        "files": manifest_files,
    }
    content_manifest_sha256 = canonical_sha256(content_manifest)
    final_status = run_git_capture(
        ["status", "--porcelain=v1", "--untracked-files=all"],
        checkout,
        envelope,
        f"git_preseal_final_status:{source.source_id}",
        max_bytes=1024 * 1024,
    )
    if final_status:
        raise AcquisitionError(f"git_preseal_worktree_not_clean:{source.source_id}")
    if (
        run_git_text(
            ["rev-parse", "HEAD"],
            checkout,
            envelope,
            f"git_final_HEAD:{source.source_id}",
        )
        != source.commit_sha
        or run_git_text(
            ["rev-parse", "HEAD^{tree}"],
            checkout,
            envelope,
            f"git_final_tree:{source.source_id}",
        )
        != source.tree_sha
    ):
        raise AcquisitionError(f"git_preseal_identity_changed:{source.source_id}")
    remove_git_metadata(checkout, envelope, source.source_id)
    fsync_and_seal_tree(checkout, envelope, source.source_id)
    sealed_manifest_files, sealed_selected_bytes = build_worktree_manifest(
        checkout,
        source,
        tree_records,
        envelope,
    )
    if (
        sealed_manifest_files != manifest_files
        or sealed_selected_bytes != selected_bytes
        or file_sha256(license_path) != observed_license_sha256
    ):
        raise AcquisitionError(f"git_postseal_manifest_changed:{source.source_id}")
    source_fd = os.open(
        source_dir,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        os.fchmod(source_fd, 0o500)
        os.fsync(source_fd)
    finally:
        os.close(source_fd)
    git_root_fd = os.open(
        git_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        os.fsync(git_root_fd)
    finally:
        os.close(git_root_fd)
    local_locator = f"sources/git/{source.source_id}/checkout"
    verification = {
        "commit_verified": True,
        "content_manifest_sha256": content_manifest_sha256,
        "cryptographic_payload_identity_verified": True,
        "identity_verified": True,
        "license_verified": True,
        "observed_commit_sha": observed_commit,
        "observed_file_count": len(manifest_files),
        "observed_license_sha256": observed_license_sha256,
        "observed_selected_bytes": selected_bytes,
        "observed_tree_sha": observed_head_tree,
        "path_safety_verified": True,
        "phone_private": True,
        "raw_fsynced": True,
        "rights_verified": True,
        "stage_binding_verified": True,
        "symlink_policy_verified": True,
        "tree_verified": True,
        "worktree_clean": True,
    }
    artifact = source_artifact(
        source,
        byte_count=selected_bytes,
        digest=content_manifest_sha256,
        local_locator=local_locator,
        content_manifest=content_manifest,
        verification=verification,
    )
    inspection = {
        "source_id": source.source_id,
        "acquisition_mode": source.acquisition_mode,
        "archive_or_document_type": "exact_sparse_Git_commit_worktree",
        "member_count": len(manifest_files),
        "uncompressed_or_document_bytes": selected_bytes,
        "required_marker_count": 1,
        "required_markers_verified": True,
        "structure_checks": {
            "commit_and_tree_verified": True,
            "Git_transport_redirects_allowed": False,
            "fetch_command_attempt_count": fetch_attempts,
            "license_sha256_verified": True,
            "git_metadata_removed_before_seal": True,
            "selected_tree_regular_blob_count": len(tree_records),
            "sparse_worktree_matches_selected_tree": True,
            "special_submodule_or_symlink_entries_present": False,
            "worktree_clean_before_seal": True,
        },
        "raw_payload_egressed": False,
    }
    return artifact, inspection


def run_git(
    args: Sequence[str],
    cwd: Path,
    envelope: ResourceEnvelope,
    checkpoint: str,
) -> None:
    output = run_git_capture(
        args,
        cwd,
        envelope,
        checkpoint,
        max_bytes=MAX_PROCESS_LOG_BYTES,
    )
    if output.strip():
        # Git warnings can conceal fallback or sparse-checkout policy changes.
        raise AcquisitionError(
            f"git_unexpected_output:{sanitize_checkpoint(checkpoint)}"
        )


def run_git_with_retries(
    args: Sequence[str],
    cwd: Path,
    envelope: ResourceEnvelope,
    checkpoint: str,
) -> int:
    for attempt in range(1, 4):
        try:
            run_git(args, cwd, envelope, checkpoint)
            return attempt
        except AcquisitionError as error:
            if attempt == 3 or not str(error).startswith("git_exit_"):
                raise
            envelope.check(checkpoint, force_thermal=True)
            time.sleep(2 ** (attempt - 1))
    raise AcquisitionError("git_retry_state_unreachable")


def run_git_text(
    args: Sequence[str],
    cwd: Path,
    envelope: ResourceEnvelope,
    checkpoint: str,
) -> str:
    payload = run_git_capture(
        args,
        cwd,
        envelope,
        checkpoint,
        max_bytes=MAX_PROCESS_LOG_BYTES,
    )
    try:
        text = payload.decode("ascii")
    except UnicodeDecodeError:
        raise AcquisitionError("git_identity_output_not_ascii") from None
    if "\x00" in text:
        raise AcquisitionError("git_identity_output_invalid")
    return text.strip()


def run_git_capture(
    args: Sequence[str],
    cwd: Path,
    envelope: ResourceEnvelope,
    checkpoint: str,
    *,
    max_bytes: int,
) -> bytes:
    envelope.candidate.revalidate_path_binding()
    with (
        tempfile.TemporaryFile(dir=envelope.candidate.bound_path) as output_file,
        EphemeralControlFiles(
            envelope,
            ((output_file.fileno(), max_bytes, "git_capture"),),
        ),
    ):
        argv = [GIT, *git_safety_options(), *args]
        toolchain_roles = command_toolchain_roles(GIT)
        revalidate_attested_toolchain_roles(toolchain_roles)
        executable_fd = open_attested_executable_fd(GIT)
        try:
            process = subprocess.Popen(
                argv,
                executable=str(FD_PATH_ROOT / str(executable_fd)),
                cwd=cwd,
                env=git_environment(),
                stdin=subprocess.DEVNULL,
                stdout=output_file,
                stderr=subprocess.STDOUT,
                close_fds=True,
                pass_fds=(envelope.candidate.directory_fd, executable_fd),
                start_new_session=True,
            )
        finally:
            os.close(executable_fd)
        try:
            while process.poll() is None:
                envelope.check(checkpoint)
                time.sleep(PROCESS_POLL_SECONDS)
            return_code = process.returncode
            envelope.check(checkpoint)
        except BaseException:
            terminate_process_group(process)
            revalidate_attested_toolchain_roles(toolchain_roles)
            raise
        revalidate_attested_toolchain_roles(toolchain_roles)
        output_file.flush()
        size = os.fstat(output_file.fileno()).st_size
        if size > max_bytes:
            raise AcquisitionError("git_output_oversize")
        output_file.seek(0)
        output = output_file.read(max_bytes + 1)
        if return_code != 0:
            detail_sha = hashlib.sha256(output).hexdigest()[:16]
            raise AcquisitionError(f"git_exit_{return_code}_{detail_sha}")
        return output


def parse_git_tree_records(payload: bytes, source: Any) -> dict[str, tuple[str, str]]:
    records: dict[str, tuple[str, str]] = {}
    for raw_record in payload.split(b"\x00"):
        if not raw_record:
            continue
        try:
            metadata, raw_path = raw_record.split(b"\t", 1)
            mode, object_type, oid = metadata.decode("ascii").split(" ")
            path = raw_path.decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            raise AcquisitionError("git_tree_record_invalid") from None
        validate_git_relative_path(path)
        if mode not in {"100644", "100755"} or object_type != "blob":
            raise AcquisitionError(
                f"git_tree_special_entry_forbidden:{source.source_id}"
            )
        if COMMIT_RE.fullmatch(oid) is None:
            raise AcquisitionError("git_tree_blob_oid_invalid")
        if path in records:
            raise AcquisitionError("git_tree_duplicate_path")
        records[path] = (mode, oid)
    if len(records) != source.selected_file_count:
        raise AcquisitionError(f"git_selected_file_count_mismatch:{source.source_id}")
    for selected in source.selected_paths:
        if not any(
            path == selected or path.startswith(selected + "/") for path in records
        ):
            raise AcquisitionError(f"git_selected_path_empty:{source.source_id}")
    return records


def sparse_checkout_pattern(
    path: str, tree_records: Mapping[str, tuple[str, str]]
) -> str:
    validate_git_relative_path(path)
    return f"/{path}" if path in tree_records else f"/{path}/"


def build_worktree_manifest(
    checkout: Path,
    source: Any,
    tree_records: Mapping[str, tuple[str, str]],
    envelope: ResourceEnvelope,
) -> tuple[list[dict[str, Any]], int]:
    observed_paths: set[str] = set()
    manifest: list[dict[str, Any]] = []
    selected_bytes = 0
    for root_text, directories, files in os.walk(
        checkout, topdown=True, followlinks=False
    ):
        root = Path(root_text)
        if root == checkout:
            directories[:] = [name for name in directories if name != ".git"]
        for name in directories:
            path = root / name
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode) or path.is_symlink():
                raise AcquisitionError(
                    f"git_worktree_directory_invalid:{source.source_id}"
                )
        for name in files:
            path = root / name
            relative = path.relative_to(checkout).as_posix()
            validate_git_relative_path(relative)
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise AcquisitionError(
                    f"git_worktree_nonregular_file:{source.source_id}"
                )
            if info.st_uid != os.geteuid() or info.st_gid != os.getegid():
                raise AcquisitionError(
                    f"git_worktree_file_owner_mismatch:{source.source_id}"
                )
            digest, file_size, observed_blob_oid = hash_worktree_file(path)
            expected_blob_oid = tree_records[relative][1]
            if observed_blob_oid != expected_blob_oid:
                raise AcquisitionError(
                    f"git_worktree_blob_identity_mismatch:{source.source_id}"
                )
            observed_paths.add(relative)
            selected_bytes += file_size
            manifest.append(
                {"relative_path": relative, "bytes": file_size, "sha256": digest}
            )
            if len(manifest) % 128 == 0:
                envelope.check(f"git_manifest:{source.source_id}")
    if observed_paths != set(tree_records):
        raise AcquisitionError(f"git_sparse_worktree_tree_mismatch:{source.source_id}")
    if len(manifest) != source.selected_file_count:
        raise AcquisitionError(f"git_worktree_file_count_mismatch:{source.source_id}")
    if selected_bytes != source.selected_bytes:
        raise AcquisitionError(
            f"git_worktree_selected_bytes_mismatch:{source.source_id}"
        )
    manifest.sort(key=lambda value: value["relative_path"])
    return manifest, selected_bytes


def fsync_and_seal_tree(root: Path, envelope: ResourceEnvelope, source_id: str) -> None:
    paths: list[Path] = []
    file_count = 0
    for root_text, directories, files in os.walk(root, topdown=True, followlinks=False):
        directory = Path(root_text)
        paths.append(directory)
        for name in directories:
            child = directory / name
            if child.is_symlink() or not child.is_dir():
                raise AcquisitionError(f"git_tree_symlink_or_special:{source_id}")
        for name in files:
            path = directory / name
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise AcquisitionError(f"git_tree_nonregular_inode:{source_id}")
            fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
            try:
                os.fchmod(fd, 0o400)
                os.fsync(fd)
            finally:
                os.close(fd)
            file_count += 1
            if file_count % 128 == 0:
                envelope.check(f"git_fsync:{source_id}")
        if len(paths) % 128 == 0:
            envelope.check(f"git_fsync:{source_id}")
    for path in reversed(paths):
        fd = os.open(
            path,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        try:
            os.fchmod(fd, 0o500)
            os.fsync(fd)
        finally:
            os.close(fd)


def hash_worktree_file(path: Path) -> tuple[str, int, str]:
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise AcquisitionError("git_worktree_hash_target_invalid")
        sha256 = hashlib.sha256()
        sha1 = hashlib.sha1(usedforsecurity=False)
        sha1.update(f"blob {before.st_size}\0".encode("ascii"))
        size = 0
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            sha256.update(chunk)
            sha1.update(chunk)
            size += len(chunk)
        if size != before.st_size or stat_identity(before) != stat_identity(
            os.fstat(fd)
        ):
            raise AcquisitionError("git_worktree_file_changed_during_hash")
        return "sha256:" + sha256.hexdigest(), size, sha1.hexdigest()
    finally:
        os.close(fd)


def source_artifact(
    source: Any,
    *,
    byte_count: int,
    digest: str,
    local_locator: str,
    content_manifest: Mapping[str, Any],
    verification: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "source_id": source.source_id,
        "acquisition_mode": source.acquisition_mode,
        "release_identity": source.release_identity,
        "stages": list(source.stages),
        "license_id": source.license_id,
        "license_class": source.license_class,
        "rights_proof": source.rights_proof,
        "bytes": byte_count,
        "sha256": digest,
        "local_locator": local_locator,
        "content_manifest": dict(content_manifest),
        "verification": dict(verification),
    }


def open_exact_child_directory(parent_fd: int, name: str, *, expected_mode: int) -> int:
    validate_literal_child_name(name, "final_source_directory")
    try:
        fd = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
    except OSError as error:
        raise AcquisitionError("final_source_directory_open_failed") from error
    info = os.fstat(fd)
    entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat_identity(info) != stat_identity(entry)
        or info.st_uid != os.geteuid()
        or info.st_gid != os.getegid()
        or stat.S_IMODE(info.st_mode) != expected_mode
    ):
        os.close(fd)
        raise AcquisitionError("final_source_directory_identity_mismatch")
    return fd


def exact_directory_entries(directory_fd: int) -> set[str]:
    try:
        entries = os.listdir(directory_fd)
    except OSError as error:
        raise AcquisitionError("final_source_directory_list_failed") from error
    if any(
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or "/" in name
        or "\x00" in name
        for name in entries
    ):
        raise AcquisitionError("final_source_directory_entry_invalid")
    return set(entries)


def reattest_direct_source(
    source: Any,
    artifact: Mapping[str, Any],
    direct_root_fd: int,
) -> dict[str, Any]:
    source_fd = open_exact_child_directory(
        direct_root_fd, source.source_id, expected_mode=0o500
    )
    try:
        if exact_directory_entries(source_fd) != {source.filename}:
            raise AcquisitionError(
                f"final_direct_entry_set_mismatch:{source.source_id}"
            )
        fd = os.open(
            source.filename,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=source_fd,
        )
        try:
            initial = os.fstat(fd)
            entry = os.stat(source.filename, dir_fd=source_fd, follow_symlinks=False)
            if (
                not stat.S_ISREG(initial.st_mode)
                or stat_identity(initial) != stat_identity(entry)
                or initial.st_nlink != 1
                or initial.st_uid != os.geteuid()
                or initial.st_gid != os.getegid()
                or stat.S_IMODE(initial.st_mode) != 0o400
            ):
                raise AcquisitionError(
                    f"final_direct_inode_identity_mismatch:{source.source_id}"
                )
            digest, size = hash_fd(fd)
            if stat_identity(initial) != stat_identity(os.fstat(fd)):
                raise AcquisitionError(
                    f"final_direct_changed_during_hash:{source.source_id}"
                )
        finally:
            os.close(fd)
        local_locator = f"sources/direct/{source.source_id}/{source.filename}"
        manifest = {
            "schema_version": "cur0s_direct_content_manifest_v1",
            "files": [
                {
                    "relative_path": local_locator,
                    "bytes": size,
                    "sha256": digest,
                }
            ],
        }
        if (
            digest != "sha256:" + source.expected_sha256
            or size != source.expected_bytes
            or artifact.get("bytes") != size
            or artifact.get("sha256") != digest
            or artifact.get("local_locator") != local_locator
            or artifact.get("content_manifest") != manifest
            or artifact.get("verification", {}).get("content_manifest_sha256")
            != canonical_sha256(manifest)
        ):
            raise AcquisitionError(f"final_direct_manifest_mismatch:{source.source_id}")
        return {
            "source_id": source.source_id,
            "acquisition_mode": source.acquisition_mode,
            "bytes": size,
            "sha256": digest,
            "content_manifest_sha256": canonical_sha256(manifest),
        }
    finally:
        os.close(source_fd)


def expected_manifest_directories(files: Sequence[Mapping[str, Any]]) -> set[str]:
    directories: set[str] = set()
    for record in files:
        relative = validate_git_relative_path(record.get("relative_path"))
        path = PurePosixPath(relative)
        for depth in range(1, len(path.parts)):
            directories.add("/".join(path.parts[:depth]))
    return directories


def hash_sealed_git_checkout(
    checkout_fd: int,
    source: Any,
    expected_files: Sequence[Mapping[str, Any]],
    envelope: ResourceEnvelope,
) -> list[dict[str, Any]]:
    root = os.fstat(checkout_fd)
    if (
        not stat.S_ISDIR(root.st_mode)
        or root.st_uid != os.geteuid()
        or root.st_gid != os.getegid()
        or stat.S_IMODE(root.st_mode) != 0o500
    ):
        raise AcquisitionError(f"final_git_checkout_root_invalid:{source.source_id}")
    expected_directories = expected_manifest_directories(expected_files)
    observed_directories: set[str] = set()
    observed_files: list[dict[str, Any]] = []
    try:
        walk = os.fwalk(
            ".",
            topdown=True,
            follow_symlinks=False,
            dir_fd=checkout_fd,
        )
        for root_text, directory_names, file_names, directory_fd in walk:
            directory_names.sort()
            file_names.sort()
            if root_text == ".":
                if ".git" in directory_names or ".git" in file_names:
                    raise AcquisitionError(
                        f"final_git_metadata_must_be_absent:{source.source_id}"
                    )
            for name in directory_names:
                relative = str(PurePosixPath(root_text, name))
                if relative.startswith("./"):
                    relative = relative[2:]
                validate_git_relative_path(relative)
                info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if (
                    not stat.S_ISDIR(info.st_mode)
                    or info.st_uid != os.geteuid()
                    or info.st_gid != os.getegid()
                    or stat.S_IMODE(info.st_mode) != 0o500
                ):
                    raise AcquisitionError(
                        f"final_git_worktree_directory_invalid:{source.source_id}"
                    )
                observed_directories.add(relative)
            for name in file_names:
                relative = str(PurePosixPath(root_text, name))
                if relative.startswith("./"):
                    relative = relative[2:]
                validate_git_relative_path(relative)
                info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1
                    or info.st_uid != os.geteuid()
                    or info.st_gid != os.getegid()
                    or stat.S_IMODE(info.st_mode) != 0o400
                ):
                    raise AcquisitionError(
                        f"final_git_worktree_file_invalid:{source.source_id}"
                    )
                fd = os.open(
                    name,
                    os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=directory_fd,
                )
                try:
                    opened = os.fstat(fd)
                    if stat_identity(info) != stat_identity(opened):
                        raise AcquisitionError(
                            f"final_git_worktree_file_replaced:{source.source_id}"
                        )
                    digest, size = hash_fd(fd)
                    if stat_identity(opened) != stat_identity(os.fstat(fd)):
                        raise AcquisitionError(
                            f"final_git_worktree_file_changed:{source.source_id}"
                        )
                finally:
                    os.close(fd)
                observed_files.append(
                    {"relative_path": relative, "bytes": size, "sha256": digest}
                )
                if len(observed_files) % 128 == 0:
                    envelope.check(f"final_git_reattest:{source.source_id}")
    except OSError as error:
        raise AcquisitionError(
            f"final_git_worktree_walk_failed:{source.source_id}"
        ) from error
    observed_files.sort(key=lambda record: record["relative_path"])
    if observed_directories != expected_directories:
        raise AcquisitionError(
            f"final_git_worktree_directory_set_mismatch:{source.source_id}"
        )
    return observed_files


def reattest_git_source(
    source: Any,
    artifact: Mapping[str, Any],
    git_root_fd: int,
    envelope: ResourceEnvelope,
) -> dict[str, Any]:
    source_fd = open_exact_child_directory(
        git_root_fd, source.source_id, expected_mode=0o500
    )
    try:
        if exact_directory_entries(source_fd) != {"checkout"}:
            raise AcquisitionError(f"final_git_entry_set_mismatch:{source.source_id}")
        checkout_fd = open_exact_child_directory(
            source_fd, "checkout", expected_mode=0o500
        )
        try:
            manifest = artifact.get("content_manifest")
            if (
                not isinstance(manifest, Mapping)
                or manifest.get("schema_version")
                != "cur0s_git_sparse_content_manifest_v1"
                or manifest.get("commit_sha") != source.commit_sha
                or manifest.get("tree_sha") != source.tree_sha
                or not isinstance(manifest.get("files"), list)
            ):
                raise AcquisitionError(
                    f"final_git_manifest_schema_mismatch:{source.source_id}"
                )
            expected_files = manifest["files"]
            observed_files = hash_sealed_git_checkout(
                checkout_fd, source, expected_files, envelope
            )
        finally:
            os.close(checkout_fd)
        observed_manifest = {
            "schema_version": "cur0s_git_sparse_content_manifest_v1",
            "commit_sha": source.commit_sha,
            "tree_sha": source.tree_sha,
            "files": observed_files,
        }
        manifest_sha256 = canonical_sha256(observed_manifest)
        selected_bytes = sum(record["bytes"] for record in observed_files)
        if (
            observed_manifest != manifest
            or len(observed_files) != source.selected_file_count
            or selected_bytes != source.selected_bytes
            or artifact.get("bytes") != selected_bytes
            or artifact.get("sha256") != manifest_sha256
            or artifact.get("local_locator")
            != f"sources/git/{source.source_id}/checkout"
            or artifact.get("verification", {}).get("content_manifest_sha256")
            != manifest_sha256
        ):
            raise AcquisitionError(f"final_git_manifest_mismatch:{source.source_id}")
        return {
            "source_id": source.source_id,
            "acquisition_mode": source.acquisition_mode,
            "bytes": selected_bytes,
            "sha256": manifest_sha256,
            "content_manifest_sha256": manifest_sha256,
        }
    finally:
        os.close(source_fd)


def reattest_candidate_source_tree(
    candidate: PrivateCandidate,
    artifacts: Sequence[Mapping[str, Any]],
    envelope: ResourceEnvelope,
    *,
    expected_candidate_control_entries: frozenset[str] = frozenset(),
    expected_source_tree_mode: int = 0o700,
) -> dict[str, Any]:
    if not expected_candidate_control_entries.issubset(
        {"receipt.json", "COMPLETE.json"}
    ):
        raise AcquisitionError("final_candidate_control_entry_contract_invalid")
    if expected_source_tree_mode not in {0o500, 0o700}:
        raise AcquisitionError("final_source_tree_mode_contract_invalid")
    candidate.revalidate_path_binding()
    expected_candidate_entries = {
        "sources",
        *expected_candidate_control_entries,
    }
    if exact_directory_entries(candidate.directory_fd) != expected_candidate_entries:
        raise AcquisitionError("final_candidate_pre_receipt_entry_set_mismatch")
    artifact_by_id = {artifact.get("source_id"): artifact for artifact in artifacts}
    expected_ids = {source.source_id for source in (*DIRECT_SOURCES, *GIT_SOURCES)}
    if set(artifact_by_id) != expected_ids or len(artifact_by_id) != len(artifacts):
        raise AcquisitionError("final_source_artifact_identity_set_mismatch")
    sources_fd = open_exact_child_directory(
        candidate.directory_fd, "sources", expected_mode=expected_source_tree_mode
    )
    try:
        if exact_directory_entries(sources_fd) != {"direct", "git"}:
            raise AcquisitionError("final_source_lane_entry_set_mismatch")
        direct_fd = open_exact_child_directory(
            sources_fd, "direct", expected_mode=expected_source_tree_mode
        )
        git_fd = open_exact_child_directory(
            sources_fd, "git", expected_mode=expected_source_tree_mode
        )
        try:
            direct_ids = {source.source_id for source in DIRECT_SOURCES}
            git_ids = {source.source_id for source in GIT_SOURCES}
            if exact_directory_entries(direct_fd) != direct_ids:
                raise AcquisitionError("final_direct_source_set_mismatch")
            if exact_directory_entries(git_fd) != git_ids:
                raise AcquisitionError("final_git_source_set_mismatch")
            observations = [
                reattest_direct_source(
                    source, artifact_by_id[source.source_id], direct_fd
                )
                for source in DIRECT_SOURCES
            ]
            observations.extend(
                reattest_git_source(
                    source, artifact_by_id[source.source_id], git_fd, envelope
                )
                for source in GIT_SOURCES
            )
            for fd in (direct_fd, git_fd, sources_fd):
                os.fchmod(fd, 0o500)
                os.fsync(fd)
        finally:
            os.close(direct_fd)
            os.close(git_fd)
    finally:
        os.close(sources_fd)
    candidate.revalidate_path_binding()
    if exact_directory_entries(candidate.directory_fd) != expected_candidate_entries:
        raise AcquisitionError("final_candidate_post_read_entry_set_mismatch")
    observations.sort(key=lambda record: record["source_id"])
    body = {
        "schema_version": "cur0s_final_source_custody_reattestation_v1",
        "artifact_count": len(observations),
        "artifacts": observations,
        "candidate_entry_set": ["sources"],
        "C4_COM_and_C4_RX_roots_separate": True,
        "fd_root_O_NOFOLLOW_readback": True,
        "raw_payload_egressed": False,
    }
    return {**body, "reattestation_root_sha256": canonical_sha256(body)}


def build_success_receipt(
    *,
    prereg: Mapping[str, Any],
    prereg_bytes: bytes,
    source_execution_identity: Mapping[str, Any],
    runtime_identity: Mapping[str, Any],
    source_root: Mapping[str, Any],
    inspection_summaries: Sequence[Mapping[str, Any]],
    candidate: PrivateCandidate,
    envelope: ResourceEnvelope,
    started_at: str,
    started_monotonic: float,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "candidate_id": prereg["candidate_id"],
        "run_id": prereg["run_id"],
        "state": "passed_scope",
        "candidate_output_observed": True,
        "source_root_state": "passed_scope",
        "all_source_identity_and_rights_gates_passed": True,
        "commercial_source_contract_sha256": prereg[
            "commercial_source_contract_sha256"
        ],
        "commercial_source_contract_root_sha256": prereg["commercial_source_contract"][
            "contract_root_sha256"
        ],
        "source_execution_identity": dict(source_execution_identity),
        "runtime_identity": dict(runtime_identity),
        "authority_bindings": sanitized_authority_bindings(prereg, prereg_bytes),
        "source_root": dict(source_root),
        "source_inspection_summaries": [dict(value) for value in inspection_summaries],
        "first_next_blocker": "private_C4_COM_mirror",
        "mandatory_next_disposition": (
            "retain_phone_private_source_root_mirror_to_private_revision_pinned_"
            "C4_COM_then_compile_semantic_materials_before_near_semantic_Arm_C"
        ),
        "claim_ceiling": "commercial_source_identity_rights_and_phone_custody_only",
        "semantic_rows_compiled": False,
        "near_semantic_arm_C_executed": False,
        "connected_split_assigned": False,
        "cur0s_static_pass_claimed": False,
        "cur0s_pass_claimed": False,
        "composite_cur0_pass_claimed": False,
        "target_data_learning_claimed": False,
        "authority_claimed": False,
        "private_HF_mirror_completed": False,
        "c4_rx_content_present": False,
        "custody": {
            "raw_source_owner": "phone",
            "raw_source_path_egressed": False,
            "raw_payload_egressed": False,
            "Mac_raw_cache": False,
            "receipt_contains_hash_bound_aggregates_only": True,
            "C4_COM_and_C4_RX_roots_separate": True,
        },
        "execution_claim": candidate.execution_claim_receipt(),
        "preterminal_resource_envelope_snapshot": {
            **envelope.receipt_metrics(),
            "snapshot_scope": "through_receipt_construction_before_publication",
        },
        "preterminal_execution_snapshot": execution_snapshot(
            started_at, started_monotonic
        ),
        "pending_transaction_links": [
            "post_run_evidence_commit",
            "origin_push_readback",
            "capsule_CAS_transition",
            "private_revision_pinned_HF_C4_COM_mirror",
        ],
        "nonclaims": [
            "not_semantic_material_compilation",
            "not_near_semantic_Arm_C",
            "not_connected_split_or_exposure_ledger",
            "not_C3_dictionary_or_C4_syllabus_admission",
            "not_CUR_0S_or_CUR_0P_or_composite_CUR_0",
            "not_target_data_learning_or_authority",
            "not_Section_0_5_success",
        ],
    }
    receipt["receipt_root_sha256"] = canonical_sha256(receipt)
    return receipt


def build_failure_receipt(
    *,
    prereg: Mapping[str, Any],
    prereg_bytes: bytes,
    source_execution_identity: Mapping[str, Any],
    runtime_identity: Mapping[str, Any],
    acquired_artifacts: Sequence[Mapping[str, Any]],
    inspection_summaries: Sequence[Mapping[str, Any]],
    active_source_id: str | None,
    blocker: str,
    blocker_class: str,
    checkpoint: str,
    candidate: PrivateCandidate,
    envelope: ResourceEnvelope,
    started_at: str,
    started_monotonic: float,
) -> dict[str, Any]:
    candidate.revalidate_path_binding()
    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "candidate_id": prereg["candidate_id"],
        "run_id": prereg["run_id"],
        "state": "blocked_fail_closed",
        "candidate_output_observed": True,
        "source_root_state": "not_claimed",
        "all_source_identity_and_rights_gates_passed": False,
        "blocker": {
            "class": blocker_class,
            "code": sanitize_blocker_text(blocker),
            "checkpoint": sanitize_checkpoint(checkpoint),
            "active_source_id": active_source_id,
        },
        "commercial_source_contract_sha256": prereg[
            "commercial_source_contract_sha256"
        ],
        "commercial_source_contract_root_sha256": prereg["commercial_source_contract"][
            "contract_root_sha256"
        ],
        "source_execution_identity": dict(source_execution_identity),
        "runtime_identity": dict(runtime_identity),
        "authority_bindings": sanitized_authority_bindings(prereg, prereg_bytes),
        "partial_source_acquisition": {
            "acquisition_time_verified_artifact_count": len(acquired_artifacts),
            "acquisition_time_verified_artifacts": [
                dict(value) for value in acquired_artifacts
            ],
            "current_custody_reattested_at_terminal": False,
            "current_byte_identity_claimed": False,
            "inspection_summaries": [dict(value) for value in inspection_summaries],
            "partial_private_output": partial_output_report(candidate),
            "raw_payload_egressed": False,
        },
        "first_next_blocker": "commercial_source_root",
        "claim_ceiling": "fail_closed_source_acquisition_evidence_only",
        "semantic_rows_compiled": False,
        "near_semantic_arm_C_executed": False,
        "connected_split_assigned": False,
        "cur0s_static_pass_claimed": False,
        "cur0s_pass_claimed": False,
        "composite_cur0_pass_claimed": False,
        "target_data_learning_claimed": False,
        "authority_claimed": False,
        "private_HF_mirror_completed": False,
        "c4_rx_content_present": False,
        "custody": {
            "raw_source_owner": "phone",
            "raw_source_path_egressed": False,
            "raw_payload_egressed": False,
            "partial_private_sources_preserved": True,
            "Mac_raw_cache": False,
        },
        "execution_claim": candidate.execution_claim_receipt(),
        "preterminal_resource_envelope_snapshot": {
            **envelope.receipt_metrics(),
            "snapshot_scope": "through_receipt_construction_before_publication",
        },
        "preterminal_execution_snapshot": execution_snapshot(
            started_at, started_monotonic
        ),
        "pending_transaction_links": [
            "post_run_blocker_evidence_commit",
            "capsule_CAS_blocker_transition",
        ],
        "nonclaims": [
            "not_commercial_source_root_pass",
            "not_semantic_material_compilation",
            "not_near_semantic_Arm_C",
            "not_connected_split_or_exposure_ledger",
            "not_CUR_0S_or_CUR_0P_or_composite_CUR_0",
            "not_target_data_learning_or_authority",
            "not_Section_0_5_success",
        ],
    }
    receipt["receipt_root_sha256"] = canonical_sha256(receipt)
    return receipt


def finalize_candidate(
    candidate: PrivateCandidate,
    envelope: ResourceEnvelope,
    run_id: str,
    receipt: dict[str, Any],
    *,
    recheck: bool = True,
) -> None:
    candidate.revalidate_path_binding()
    if recheck:
        envelope.check("before_final_evidence_commit", force_thermal=True)
    receipt_payload = canonical_json_bytes(receipt) + b"\n"
    expected_receipt_sha256 = "sha256:" + hashlib.sha256(receipt_payload).hexdigest()
    completion_protocol = (
        "raw_sources_fsync_read_only_then_receipt_O_EXCL_fsync_read_only_then_"
        "COMPLETE_O_EXCL_fsync_last"
        if receipt["state"] == "passed_scope"
        else "partial_raw_preserved_then_blocker_receipt_O_EXCL_fsync_read_only_"
        "then_COMPLETE_O_EXCL_fsync_last"
    )
    complete = {
        "schema_version": COMPLETE_SCHEMA,
        "run_id": run_id,
        "state": receipt["state"],
        "receipt_sha256": expected_receipt_sha256,
        "receipt_root_sha256": receipt["receipt_root_sha256"],
        "receipt_bytes": len(receipt_payload),
        "completion_marker_prepared_at_utc": utc_now(),
        "completion_protocol": completion_protocol,
        "raw_sources_preserved_on_phone": True,
        "output_directory_mode": "owner_only_0700",
    }
    completion_payload = canonical_json_bytes(complete) + b"\n"
    candidate.bind_expected_terminal(receipt, complete)
    logical_before_publication, _allocated = private_tree_usage(candidate.directory_fd)
    final_logical_bytes = (
        logical_before_publication + len(receipt_payload) + len(completion_payload)
    )
    if final_logical_bytes > envelope.lease.max_private_output_bytes:
        raise AcquisitionError("terminal_evidence_reserve_unavailable")
    if receipt["state"] == "passed_scope":
        if not recheck:
            raise AcquisitionError("passed_scope_terminal_recheck_required")
        candidate.revalidate_terminal_custody(frozenset())
    receipt_artifact = candidate.write_receipt(receipt)
    if (
        receipt_artifact.sha256 != expected_receipt_sha256
        or receipt_artifact.size != len(receipt_payload)
    ):
        raise AcquisitionError("receipt_publication_identity_mismatch")
    if receipt["state"] == "passed_scope":
        candidate.revalidate_terminal_custody(frozenset({"receipt.json"}))
    candidate.write_completion_last(complete)


def sanitized_authority_bindings(
    prereg: Mapping[str, Any], prereg_bytes: bytes
) -> dict[str, Any]:
    return {
        "parent_capsule_sha256": prereg["parent_capsule_sha256"],
        "parent_frontier_root_sha256": prereg["parent_frontier_root_sha256"],
        "maximal_selector_sha256": prereg["maximal_selector_sha256"],
        "campaign_lease_root_sha256": canonical_sha256(prereg["campaign_lease"]),
        "resource_slice_root_sha256": canonical_sha256(prereg["resource_slice"]),
        "network_policy_root_sha256": canonical_sha256(prereg["network_policy"]),
        "preregistration_sha256": "sha256:" + hashlib.sha256(prereg_bytes).hexdigest(),
        "preregistration_root_sha256": prereg["preregistration_root_sha256"],
        "ACCESS_receipt_sha256": prereg["ACCESS_receipt_sha256"],
    }


def execution_snapshot(started_at: str, started_monotonic: float) -> dict[str, Any]:
    return {
        "started_at_utc": started_at,
        "snapshot_at_utc": utc_now(),
        "elapsed_seconds_at_snapshot": time.monotonic() - started_monotonic,
        "peak_rss_kib_at_snapshot": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "python": sys.version.split()[0],
    }


def partial_output_report(candidate: PrivateCandidate) -> dict[str, Any]:
    logical, allocated = private_tree_usage(candidate.directory_fd)
    regular_files = 0
    directories = 0
    try:
        for _root, directory_names, file_names, _fd in os.fwalk(
            ".",
            topdown=True,
            follow_symlinks=False,
            dir_fd=candidate.directory_fd,
        ):
            directories += len(directory_names)
            regular_files += len(file_names)
    except OSError as error:
        raise AcquisitionError("partial_output_walk_failed") from error
    return {
        "regular_file_count": regular_files,
        "directory_count_below_candidate": directories,
        "logical_bytes": logical,
        "allocated_bytes": allocated,
        "completion_marker_present": entry_exists_at(
            candidate.directory_fd, "COMPLETE.json"
        ),
        "private_payload_egressed": False,
    }


def sanitize_blocker(error: Exception) -> str:
    return sanitize_blocker_text(str(error) or error.__class__.__name__)


def sanitize_blocker_text(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_.:-]{1,192}", value) is None:
        return "sanitized_commercial_source_gate_failure"
    return value


def validate_https_url(url: Any, allowed_hosts: frozenset[str]) -> str:
    if not isinstance(url, str) or not url or "\x00" in url:
        raise AcquisitionError("https_url_invalid")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise AcquisitionError("https_url_parse_failed") from None
    hostname = parsed.hostname
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or hostname is None
        or hostname.casefold() != hostname
        or hostname not in allowed_hosts
        or port not in {None, 443}
        or parsed.fragment
        or not parsed.path.startswith("/")
        or any(ord(character) < 32 or ord(character) == 127 for character in url)
    ):
        raise AcquisitionError("https_url_policy_rejected")
    return url


def validate_source_component(value: Any, role: str) -> str:
    if not isinstance(value, str) or SAFE_COMPONENT_RE.fullmatch(value) is None:
        raise AcquisitionError(f"{role}_component_invalid")
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise AcquisitionError(f"{role}_component_invalid")
    return value


def validate_literal_child_name(value: Any, role: str) -> str:
    if (
        not isinstance(value, str)
        or value in {"", ".", ".."}
        or Path(value).parts != (value,)
        or re.fullmatch(r"[A-Za-z0-9._-]{1,160}", value) is None
    ):
        raise AcquisitionError(f"{role}_invalid")
    return value


def validate_git_relative_path(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > 4096
        or value.startswith(("/", "\\", "-"))
        or "\\" in value
        or "\x00" in value
        or any(character in value for character in "*?[]!")
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise AcquisitionError("git_relative_path_invalid")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise AcquisitionError("git_relative_path_invalid")
    return value


def validate_relative_components(
    relative_path: str, error_type: type[Exception] = AcquisitionError
) -> tuple[str, ...]:
    path = Path(relative_path)
    components = path.parts
    if (
        path.is_absolute()
        or not components
        or any(component in {"", ".", ".."} for component in components)
    ):
        raise error_type("invalid_relative_path")
    return components


def require_beneath(path: Path, root: Path, role: str) -> None:
    try:
        path.relative_to(root)
    except ValueError:
        raise AcquisitionError(f"{role}_outside_phone_private_root") from None


def assert_no_symlink_components(path: Path, anchor: Path) -> None:
    require_beneath(path, anchor, "path")
    current = anchor
    if current.is_symlink():
        raise AcquisitionError("phone_private_anchor_symlink_forbidden")
    for component in path.relative_to(anchor).parts:
        current /= component
        if current.exists() and current.is_symlink():
            raise AcquisitionError("phone_private_path_symlink_forbidden")


def assert_owner_only_chain(path: Path, anchor: Path) -> None:
    current = anchor
    require_owner_only(current, "phone_private_path_component")
    for component in path.relative_to(anchor).parts:
        current /= component
        if current.exists():
            require_owner_only(current, "phone_private_path_component")


def require_owner_only(path: Path, role: str) -> None:
    info = path.stat(follow_symlinks=False)
    if info.st_uid != os.geteuid() or info.st_gid != os.getegid():
        raise AcquisitionError(f"{role}_owner_mismatch")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise AcquisitionError(f"{role}_permissions_not_owner_only")


def require_owned_fd(fd: int, *, owner_only: bool, role: str) -> None:
    info = os.fstat(fd)
    if info.st_uid != os.geteuid() or info.st_gid != os.getegid():
        raise AcquisitionError(f"{role}_owner_mismatch")
    forbidden = 0o077 if owner_only else 0o022
    if stat.S_IMODE(info.st_mode) & forbidden:
        raise AcquisitionError(f"{role}_permissions_invalid")


def open_directory_beneath(
    root_fd: int,
    relative_path: str,
    *,
    require_owner_only_components: bool,
) -> int:
    components = validate_relative_components(relative_path)
    current_fd = os.dup(root_fd)
    try:
        for component in components:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
            require_owned_fd(
                current_fd,
                owner_only=require_owner_only_components,
                role="private_directory_component",
            )
        result = current_fd
        current_fd = -1
        return result
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def directory_binding_identity(
    info: os.stat_result,
) -> tuple[int, int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        stat.S_IFMT(info.st_mode),
        info.st_uid,
        info.st_gid,
        stat.S_IMODE(info.st_mode),
    )


def open_bound_directory_at(
    parent_fd: int,
    name: str,
    *,
    exact_mode: int,
) -> DirectoryBinding:
    validate_literal_child_name(name, "canonical_directory_component")
    before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    fd = os.open(
        name,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        dir_fd=parent_fd,
    )
    try:
        opened = os.fstat(fd)
        after = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        identity = directory_binding_identity(opened)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or identity != directory_binding_identity(before)
            or identity != directory_binding_identity(after)
            or opened.st_uid != os.geteuid()
            or opened.st_gid != os.getegid()
            or stat.S_IMODE(opened.st_mode) != exact_mode
        ):
            raise AcquisitionError("canonical_directory_binding_invalid")
        return DirectoryBinding(name=name, fd=fd, identity=identity)
    except BaseException:
        os.close(fd)
        raise


def open_phone_package_anchor() -> DirectoryBinding:
    if (
        not PHONE_PACKAGE_ROOT.is_absolute()
        or PHONE_HOME != PHONE_PACKAGE_ROOT / "files" / "home"
        or PHONE_RUN_ROOT != PHONE_HOME / PHONE_RUN_ROOT_RELATIVE
    ):
        raise AcquisitionError("phone_package_anchor_configuration_invalid")
    before = os.stat(PHONE_PACKAGE_ROOT, follow_symlinks=False)
    fd = os.open(
        PHONE_PACKAGE_ROOT,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        opened = os.fstat(fd)
        after = os.stat(PHONE_PACKAGE_ROOT, follow_symlinks=False)
        identity = directory_binding_identity(opened)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or identity != directory_binding_identity(before)
            or identity != directory_binding_identity(after)
            or opened.st_uid != os.geteuid()
            or opened.st_gid != os.getegid()
            or stat.S_IMODE(opened.st_mode) != 0o700
        ):
            raise AcquisitionError("phone_package_anchor_binding_invalid")
        return DirectoryBinding(
            name=str(PHONE_PACKAGE_ROOT),
            fd=fd,
            identity=identity,
        )
    except BaseException:
        os.close(fd)
        raise


def open_phone_candidate_chain(run_id: str) -> tuple[DirectoryBinding, ...]:
    if RUN_ID_RE.fullmatch(run_id) is None:
        raise AcquisitionError("run_id_invalid")
    bindings = [open_phone_package_anchor()]
    try:
        for name, exact_mode in (
            ("files", 0o771),
            ("home", 0o700),
            (PHONE_RUN_ROOT_RELATIVE, 0o700),
            (run_id, 0o700),
            ("candidate_runs", 0o700),
        ):
            bindings.append(
                open_bound_directory_at(
                    bindings[-1].fd,
                    name,
                    exact_mode=exact_mode,
                )
            )
        result = tuple(bindings)
        revalidate_directory_chain(result)
        return result
    except BaseException:
        close_directory_bindings(tuple(bindings))
        raise


def revalidate_directory_chain(bindings: tuple[DirectoryBinding, ...]) -> None:
    if len(bindings) != 6:
        raise AcquisitionError("canonical_directory_chain_invalid")
    anchor = bindings[0]
    anchor_entry = os.stat(PHONE_PACKAGE_ROOT, follow_symlinks=False)
    anchor_held = os.fstat(anchor.fd)
    if (
        directory_binding_identity(anchor_entry) != anchor.identity
        or directory_binding_identity(anchor_held) != anchor.identity
    ):
        raise AcquisitionError("phone_package_anchor_binding_changed")
    for parent, child in zip(bindings, bindings[1:]):
        entry = os.stat(child.name, dir_fd=parent.fd, follow_symlinks=False)
        held = os.fstat(child.fd)
        if (
            directory_binding_identity(entry) != child.identity
            or directory_binding_identity(held) != child.identity
        ):
            raise AcquisitionError("canonical_directory_chain_changed")


def close_directory_bindings(bindings: tuple[DirectoryBinding, ...]) -> None:
    closed: set[int] = set()
    for binding in reversed(bindings):
        if binding.fd in closed or binding.fd < 0:
            continue
        try:
            os.close(binding.fd)
        except OSError:
            pass
        closed.add(binding.fd)


def mkdir_open_at(parent_fd: int, name: str) -> int:
    validate_source_component(name, "directory")
    os.mkdir(name, mode=0o700, dir_fd=parent_fd)
    os.fsync(parent_fd)
    fd = os.open(
        name,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        dir_fd=parent_fd,
    )
    require_owned_fd(fd, owner_only=True, role="new_private_directory")
    return fd


def create_owner_only_directory(path: Path, expected_parent: Path) -> None:
    if path.parent != expected_parent:
        raise AcquisitionError("source_directory_parent_mismatch")
    validate_source_component(path.name, "source_directory")
    parent_fd = os.open(
        expected_parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        fd = mkdir_open_at(parent_fd, path.name)
        os.close(fd)
    finally:
        os.close(parent_fd)


def entry_exists_at(directory_fd: int, name: str) -> bool:
    validate_literal_child_name(name, "entry_name")
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def remove_exact_empty_directory_at(
    parent_fd: int,
    name: str,
    *,
    expected_identity: tuple[int, int, int, int, int, int, int, int, int] | None,
) -> None:
    validate_source_component(name, "candidate_directory")
    try:
        fd = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
    except FileNotFoundError:
        return
    try:
        require_owned_fd(fd, owner_only=True, role="unclaimed_candidate")
        info = os.fstat(fd)
        if expected_identity is not None and stat_identity(info) != expected_identity:
            raise AcquisitionError("unclaimed_candidate_cleanup_identity_mismatch")
        if os.listdir(fd):
            raise AcquisitionError("unclaimed_candidate_cleanup_not_empty")
        entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (entry.st_dev, entry.st_ino) != (info.st_dev, info.st_ino):
            raise AcquisitionError("unclaimed_candidate_cleanup_entry_changed")
    finally:
        os.close(fd)
    os.rmdir(name, dir_fd=parent_fd)
    os.fsync(parent_fd)


def read_exact_artifact_at(
    directory_fd: int,
    name: str,
    payload: bytes,
    *,
    mode: int,
    expected_creation_binding: tuple[int, int, int, int],
) -> WrittenArtifact | None:
    validate_literal_child_name(name, "output_filename")
    try:
        fd = os.open(
            name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=directory_fd,
        )
    except FileNotFoundError:
        return None
    try:
        opened = os.fstat(fd)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or stat.S_IMODE(opened.st_mode) != mode
            or (
                opened.st_dev,
                opened.st_ino,
                opened.st_uid,
                opened.st_gid,
            )
            != expected_creation_binding
        ):
            return None
        expected = ("sha256:" + hashlib.sha256(payload).hexdigest(), len(payload))
        if hash_fd(fd) != expected:
            return None
        final = os.fstat(fd)
        if stat_identity(opened) != stat_identity(final):
            return None
        entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat_identity(entry) != stat_identity(final):
            return None
        return WrittenArtifact(
            name=name,
            sha256=expected[0],
            size=expected[1],
            stat_identity=stat_identity(final),
        )
    finally:
        os.close(fd)


def read_canonical_json_artifact_at(
    directory_fd: int,
    name: str,
    *,
    max_bytes: int = 1024 * 1024,
) -> tuple[WrittenArtifact, dict[str, Any]] | None:
    """Read one sealed canonical JSON artifact without trusting path contents."""

    validate_literal_child_name(name, "output_filename")
    try:
        fd = os.open(
            name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=directory_fd,
        )
    except FileNotFoundError:
        return None
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) != 0o400
            or not 0 < before.st_size <= max_bytes
        ):
            return None
        payload = read_fd_bounded(fd, max_bytes)
        after = os.fstat(fd)
        entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            stat_identity(before) != stat_identity(after)
            or stat_identity(after) != stat_identity(entry)
            or not payload.endswith(b"\n")
        ):
            return None
        value = strict_json_loads(payload)
        if (
            not isinstance(value, dict)
            or canonical_json_bytes(value) + b"\n" != payload
        ):
            return None
        artifact = WrittenArtifact(
            name=name,
            sha256="sha256:" + hashlib.sha256(payload).hexdigest(),
            size=len(payload),
            stat_identity=stat_identity(after),
        )
        return artifact, value
    except (OSError, ValueError, AcquisitionError):
        return None
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def publish_exact_bytes_at(
    directory_fd: int,
    name: str,
    payload: bytes,
    *,
    mode: int,
    provenance: ExclusiveCreateProvenance | None = None,
) -> WrittenArtifact:
    """Publish a newly created immutable file without adopting prior entries."""

    return write_exclusive_bytes_at(
        directory_fd,
        name,
        payload,
        mode=mode,
        provenance=provenance,
    )


def publish_initialization_abort_at(
    parent_fd: int,
    *,
    name: str,
    run_id: str,
    preregistration_root_sha256: str,
    contract_root_sha256: str,
    blocker: str,
    checkpoint: str,
    claim_state: str,
) -> WrittenArtifact:
    value = {
        "schema_version": ABORT_SCHEMA,
        "state": "blocked_incomplete_initialization",
        "run_id": run_id,
        "output_directory_name": "candidate-001",
        "phone_execution_ordinal": 1,
        "preregistration_root_sha256": preregistration_root_sha256,
        "contract_root_sha256": contract_root_sha256,
        "claim_state": claim_state,
        "claim_sha256": None,
        "receipt_sha256": None,
        "completion_sha256": None,
        "blocker": sanitize_blocker_text(blocker),
        "checkpoint": sanitize_checkpoint(checkpoint),
        "replay_allowed": False,
        "source_root_pass_claimed": False,
        "raw_payload_egressed": False,
    }
    return publish_exact_bytes_at(
        parent_fd,
        name,
        canonical_json_bytes(value) + b"\n",
        mode=0o400,
    )


def terminalize_uncertain_preparation(
    path: Path,
    *,
    run_id: str,
    preregistration_root_sha256: str,
    contract_root_sha256: str,
    blocker: str,
) -> None:
    """Best-effort terminal evidence for an exception across prepare() return."""

    anchor: DirectoryBinding | None = None
    try:
        anchor = open_phone_package_anchor()
        claim_name = execution_claim_name(run_id)
        abort_name = execution_abort_name(run_id)
        if entry_exists_at(anchor.fd, claim_name):
            return
        if entry_exists_at(anchor.fd, abort_name):
            return
        publish_initialization_abort_at(
            anchor.fd,
            name=abort_name,
            run_id=run_id,
            preregistration_root_sha256=preregistration_root_sha256,
            contract_root_sha256=contract_root_sha256,
            blocker=blocker,
            checkpoint="candidate_preparation_return_boundary",
            claim_state="not_published",
        )
    except BaseException:
        # The original preparation failure remains primary; any exact claim is
        # itself a conservative non-replayable anchor.
        return
    finally:
        if anchor is not None:
            close_directory_bindings((anchor,))


def write_exclusive_bytes_at(
    directory_fd: int,
    name: str,
    payload: bytes,
    *,
    mode: int,
    provenance: ExclusiveCreateProvenance | None = None,
) -> WrittenArtifact:
    validate_literal_child_name(name, "output_filename")
    if provenance is not None:
        if (
            provenance.create_attempted
            or provenance.created_by_this_call
            or provenance.creation_binding is not None
        ):
            raise AcquisitionError("exclusive_create_provenance_not_pristine")
        provenance.create_attempted = True
    fd = os.open(
        name,
        os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
        mode,
        dir_fd=directory_fd,
    )
    if provenance is not None:
        provenance.created_by_this_call = True
    creation_binding: tuple[int, int, int, int] | None = None
    seal_fsynced = False
    artifact: WrittenArtifact | None = None
    publication_error: BaseException | None = None
    try:
        initial = os.fstat(fd)
        if (
            not stat.S_ISREG(initial.st_mode)
            or initial.st_nlink != 1
            or initial.st_uid != os.getuid()
        ):
            raise AcquisitionError("exclusive_artifact_created_inode_invalid")
        creation_binding = (
            initial.st_dev,
            initial.st_ino,
            initial.st_uid,
            initial.st_gid,
        )
        if provenance is not None:
            provenance.creation_binding = creation_binding
        write_all(fd, payload)
        os.fsync(fd)
        expected = ("sha256:" + hashlib.sha256(payload).hexdigest(), len(payload))
        if hash_fd(fd) != expected:
            raise AcquisitionError("exclusive_artifact_readback_mismatch")
        os.fchmod(fd, mode)
        os.fsync(fd)
        seal_fsynced = True
        final = os.fstat(fd)
        validate_same_entry(directory_fd, name, initial, final)
        artifact = WrittenArtifact(
            name=name,
            sha256=expected[0],
            size=expected[1],
            stat_identity=stat_identity(final),
        )
    except BaseException as error:
        publication_error = error
    try:
        os.close(fd)
    except BaseException as error:
        publication_error = publication_error or error

    if publication_error is not None:
        if (
            not isinstance(publication_error, OSError)
            or not seal_fsynced
            or creation_binding is None
        ):
            raise publication_error
        recovered = read_exact_artifact_at(
            directory_fd,
            name,
            payload,
            mode=mode,
            expected_creation_binding=creation_binding,
        )
        if recovered is None:
            raise publication_error
        os.fsync(directory_fd)
        return recovered

    if artifact is None or creation_binding is None:
        raise AcquisitionError("exclusive_artifact_publication_state_invalid")
    try:
        os.fsync(directory_fd)
    except OSError:
        recovered = read_exact_artifact_at(
            directory_fd,
            name,
            payload,
            mode=mode,
            expected_creation_binding=creation_binding,
        )
        if recovered is None:
            raise
        os.fsync(directory_fd)
        return recovered
    return artifact


def write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("zero_length_write")
        view = view[written:]


def validate_same_entry(
    directory_fd: int,
    name: str,
    initial: os.stat_result,
    final: os.stat_result,
) -> None:
    entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    if (initial.st_dev, initial.st_ino) != (final.st_dev, final.st_ino):
        raise AcquisitionError("artifact_inode_changed")
    if (final.st_dev, final.st_ino) != (entry.st_dev, entry.st_ino):
        raise AcquisitionError("artifact_directory_entry_replaced")
    if final.st_nlink != 1 or not stat.S_ISREG(final.st_mode):
        raise AcquisitionError("artifact_inode_invalid")


def stat_identity(
    info: os.stat_result,
) -> tuple[int, int, int, int, int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        stat.S_IFMT(info.st_mode),
        info.st_nlink,
        info.st_size,
        info.st_uid,
        info.st_gid,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def hash_fd(fd: int) -> tuple[str, int]:
    os.lseek(fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
    return "sha256:" + digest.hexdigest(), size


def file_sha256(path: Path) -> str:
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise AcquisitionError("hash_target_not_regular")
        digest = hash_fd(fd)[0]
        if stat_identity(info) != stat_identity(os.fstat(fd)):
            raise AcquisitionError("hash_target_changed_during_read")
        return digest
    finally:
        os.close(fd)


def read_fd_prefix(fd: int, limit: int) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    return os.read(fd, limit)


def read_fd_bounded(fd: int, limit: int) -> bytes:
    result = bytearray()
    while True:
        chunk = os.read(fd, min(1024 * 1024, limit + 1 - len(result)))
        if not chunk:
            break
        result.extend(chunk)
        if len(result) > limit:
            raise AcquisitionError("bounded_read_limit_exceeded")
    return bytes(result)


def read_temporary_file(handle: BinaryIO, limit: int) -> bytes:
    handle.flush()
    size = os.fstat(handle.fileno()).st_size
    if size > limit:
        raise AcquisitionError("temporary_evidence_file_oversize")
    handle.seek(0)
    payload = handle.read(limit + 1)
    if len(payload) > limit:
        raise AcquisitionError("temporary_evidence_file_oversize")
    return payload


def private_tree_usage(directory_fd: int) -> tuple[int, int]:
    logical = 0
    allocated = 0
    root_info = os.fstat(directory_fd)
    if not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != os.getuid():
        raise AcquisitionError("candidate_root_inode_invalid")
    allocated += root_info.st_blocks * 512
    try:
        for _root, directories, files, walk_fd in os.fwalk(
            ".",
            topdown=True,
            follow_symlinks=False,
            dir_fd=directory_fd,
        ):
            for name in directories:
                info = os.stat(name, dir_fd=walk_fd, follow_symlinks=False)
                if not stat.S_ISDIR(info.st_mode):
                    raise AcquisitionError(
                        "private_output_symlink_or_special_directory"
                    )
                allocated += info.st_blocks * 512
            for name in files:
                info = os.stat(name, dir_fd=walk_fd, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise AcquisitionError("private_output_symlink_or_special_file")
                logical += info.st_size
                allocated += info.st_blocks * 512
    except OSError as error:
        raise AcquisitionError("private_output_tree_walk_failed") from error
    return logical, allocated


def require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise AcquisitionError(f"{field}_missing")
    match = SHA256_RE.fullmatch(value)
    if match is None:
        raise AcquisitionError(f"{field}_invalid")
    return "sha256:" + match.group(1)


def utc_now() -> str:
    return iso_utc(datetime.now(timezone.utc))


def iso_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("datetime_must_be_UTC")
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    preimport_python_guard()
    _main_args = parse_args()
    (
        _main_prereg_bytes,
        _main_prereg,
        _main_source_bytes,
        _PREIMPORT_SOURCE_ATTESTATION,
    ) = bootstrap_authority(_main_args)
    bind_bound_module(_main_source_bytes)
    raise SystemExit(
        main(
            args=_main_args,
            prereg_bytes=_main_prereg_bytes,
            prereg=_main_prereg,
        )
    )

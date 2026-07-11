"""Final authority-correct V79 S16 LM-head candidate and exact-dot oracle.

The v1 candidate used the checkpoint's F32 row scales directly.  Gemma's
BF16 authority instead converts those scales to the input dtype before the
matrix product.  This module freezes the one admitted repair: round every
F32 row scale to BF16 with round-to-nearest-even, store that rounded value
exactly in F32 QNN metadata, retain the packed INT2 tensor and the 2^-9 S16
input ABI, and use a 2^-10 S16 output ABI.

Preregistration is deliberately separate from observation.  The full-width
oracle cannot run unless the immutable preregistration is present, and a
provider package cannot be materialized unless the resulting oracle gate is
green for all three frozen cases under the unchanged authority thresholds.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import secrets
import stat
import struct
import subprocess
import sys
import time
from typing import Any, Sequence

from .e4b_f5_probe import LM_HEAD, QAT_MODEL_SHA256
from .e4b_f5_qnn_exporter import (
    LM_HEAD_GRAPH,
    publish_directory_noreplace,
    render_direct_qnn_cpp,
)
from .e4b_l2_int16_head import (
    DESCRIPTIVE_EDGE_KEYS,
    INPUT_SCALE,
)
from .e4b_l2_projection_gate import (
    TOP_K,
    ProjectionGateError,
    adjudicate_metrics,
    bf16_payload_to_floats,
    canonical_json,
    sha256_bytes,
    sha256_path,
    softmax_js_divergence,
    threshold_policy,
    vector_metrics,
    write_hashed_json,
)


# The imports above intentionally reuse only the v1 input quantization and the
# original threshold partition.  All v2 identities remain explicit here to
# prevent accidental inheritance of the killed candidate's identity.
INT16_V1_PREREG_SHA256 = (
    "51f1e9977258d8d61c7eb1ff76964b293a15d38eb852da1b5692cb58aaeea284"
)
INT16_V1_POLICY_SHA256 = (
    "36d4689f6c59f8ce8d9d99c6dc4085d7e63089a6448c20517fd0fcc74964ad05"
)
FRONTIER_SELECTOR_SHA256 = (
    "bb045f0761405b521705609d473fa1cb7b504634197256b2b684c061e1fc4d78"
)
NUMERIC_THRESHOLD_SUBSET_SHA256 = (
    "30704ef1cb88042a1451f46b5c516b815cbb440a7227b9013893ee7b42cdd914"
)

V2_CANDIDATE_ID = "w2_s16_activation_bw2_weight_bf16_rne_scale_s16_output_2m10_v2"
V2_POLICY_SCHEMA = "gemma4_e4b_l2_int16_head_policy_v2"
V2_PREREG_SCHEMA = "gemma4_e4b_l2_int16_head_preregistration_v2"
V2_ORACLE_SCHEMA = "gemma4_e4b_l2_int16_exact_dot_oracle_gate_v2"

PACKED_WEIGHT_SHA256 = LM_HEAD.weight.data_sha256
ORIGINAL_SCALE_SHA256 = LM_HEAD.weight_scale.data_sha256
ROW_SCALE_COUNT = LM_HEAD.output_features
ORIGINAL_SCALE_BYTES = LM_HEAD.weight_scale.nbytes
PACKED_WEIGHT_BYTES = LM_HEAD.weight.nbytes
INPUT_FEATURES = LM_HEAD.input_features
OUTPUT_FEATURES = LM_HEAD.output_features
OUTPUT_SCALE = 1.0 / 1024.0
SIGNED_WEIGHT_SHIFT = LM_HEAD.signed_shift
WEIGHT_BITS = LM_HEAD.num_bits
FULL_WIDTH_DOT_PRODUCTS_PER_CASE = INPUT_FEATURES * OUTPUT_FEATURES
SCALE_ARTIFACT_RELATIVE_PATH = "tensors/w2_lm_head_weight_scale.bf16_rne.f32.bin"
ORIGINAL_SCALE_ARTIFACT_RELATIVE_PATH = (
    "tensors/w2_lm_head_weight_scale.original.f32.bin"
)
FULL_REVISION = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
UTC_TIMESTAMP = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
SANITIZED_RUN_ID = re.compile(
    r"^(?P<timestamp>[0-9]{8}T[0-9]{6}Z)_"
    r"(?P<suffix>l2_s16_v2_exact_oracle|l2_s16_v2_exact_verification)$"
)
ORACLE_PYTHON_VERSION = "3.13.13"
ORACLE_NUMPY_VERSION = "2.4.4"
ORACLE_ROW_BLOCK_SIZE = 2048
THERMAL_SENSOR_TYPE = "pmih010x_lite_tz"
THERMAL_STOP_MILLICELSIUS = 90_000
MIN_AVAILABLE_MEMORY_BYTES = 2 * 1024 * 1024 * 1024
MIN_AVAILABLE_STORAGE_BYTES = 2 * 1024 * 1024 * 1024
MAX_ORACLE_WALL_SECONDS = 4 * 60 * 60
PARENT_CAPSULE_SHA256 = (
    "66072e0dee357c9d7c178c3fa3628a6230fa5992659325b80e7eefa6e4dbdd2b"
)
ACCESS_RECEIPT_SHA256 = (
    "7b2b6d506b3ab82a17008edc4c79dd51512f6f9598e3db37cd1bb6f5ee4331ca"
)
CAMPAIGN_LEASE_ID = "current_user_sovereign_frontier_campaign_20260711"
RESOURCE_SLICE = {
    "additional_paid_capacity": False,
    "comet_payload": "hash_bound_metadata_only",
    "github_repository": "Zer0pa/Polymath-AI",
    "huggingface_visibility": "private_revision_pinned_only",
    "phone": "REDMAGIC_NX789J_SM8750",
    "phone_serial_sha256": "383e1fef6040334134430241a105f7d900f6d924e485fdc858441e734d3ae0f4",
    "phone_private_raw_upload": False,
    "public_release": False,
    "runpod": "uh57jg7iguwqth_existing_only",
}
PHONE_RUNTIME_PREFIX = Path(
    "/data/data/com.termux/files/home/polymath_gemma4_e4b_frontier"
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MODULE_RELATIVE_PATH = "polymath_ai/frontier/e4b_l2_int16_v2.py"
SOURCE_CLOSURE_RELATIVE_PATHS = (
    "polymath_ai/__init__.py",
    "polymath_ai/_version.py",
    "polymath_ai/frontier/__init__.py",
    "polymath_ai/frontier/e4b_l0.py",
    "polymath_ai/frontier/hardened_hf.py",
    "polymath_ai/frontier/safetensors_identity.py",
    MODULE_RELATIVE_PATH,
    "polymath_ai/frontier/e4b_l2_int16_v2_verifier.py",
    "polymath_ai/frontier/e4b_l2_int16_v2_package.py",
    "polymath_ai/frontier/e4b_l2_projection_gate.py",
    "polymath_ai/frontier/e4b_f5_probe.py",
    "polymath_ai/frontier/e4b_f5_qnn_exporter.py",
    "polymath_ai/frontier/e4b_l2_int16_head.py",
    "polymath_ai/frontier/e4b_l2_int16_package.py",
    "scripts/host/build_e4b_l2_int16_v2_package.py",
    "scripts/termux/run_e4b_l2_int16_v2_oracle.py",
)

FROZEN_CASES = (
    {
        "case_id": "structured_dynamic",
        "bf16_input_sha256": "5cca991319c94de485360d2b05b87a80b9b88bc3fe636c8a478ccda9461bada8",
        "s16_input_relative_path": "inputs/gemma4_e4b_f5_w2_lm_head.structured_dynamic.s16.raw",
        "s16_input_bytes": 5120,
        "s16_input_sha256": "360e7c9f22a0dbb0c135b3a1b696d206e66d02b57b6320eb3e8210d1e880e236",
        "authority_output": {
            "bytes": 524288,
            "dtype": "bfloat16",
            "provider_relative_path": "references/structured_dynamic.w2_qat_authority.bf16.raw",
            "sha256": "30e624bdbad91be77ef6f3d18d46eef2cec6dc5b7a23e7fb4438bf74ae54a30a",
            "shape": [1, 1, 262144],
        },
    },
    {
        "case_id": "balanced_splitmix64",
        "bf16_input_sha256": "2065c350db9e1b835193f7b369b4561bae099eb20931562bede7687727af16aa",
        "s16_input_relative_path": "inputs/gemma4_e4b_f5_w2_lm_head.balanced_splitmix64.s16.raw",
        "s16_input_bytes": 5120,
        "s16_input_sha256": "8ac246d9328dca16ae2c182906bdb11b8080f0dc71161d28838291eb27f1bf90",
        "authority_output": {
            "bytes": 524288,
            "dtype": "bfloat16",
            "provider_relative_path": "references/balanced_splitmix64.w2_qat_authority.bf16.raw",
            "sha256": "4d61ad4b4c98089646a6c11e825fb7486090c94fba376d6de1c0a5127c20e26a",
            "shape": [1, 1, 262144],
        },
    },
    {
        "case_id": "low_amplitude_splitmix64",
        "bf16_input_sha256": "0d0d93d4562b91ee90d129e0e7c277654659e27a7a87cbc4e4a62276e61dcbe3",
        "s16_input_relative_path": "inputs/gemma4_e4b_f5_w2_lm_head.low_amplitude_splitmix64.s16.raw",
        "s16_input_bytes": 5120,
        "s16_input_sha256": "05b0526761aa7a5c83156a6bcdf3954a784b23d8b97ffc864e3acc963a3b490a",
        "authority_output": {
            "bytes": 524288,
            "dtype": "bfloat16",
            "provider_relative_path": "references/low_amplitude_splitmix64.w2_qat_authority.bf16.raw",
            "sha256": "9769af1ba2b21d3d7803f9bb139c17eb96c0ae0a893ef763b87060d3c68bebd2",
            "shape": [1, 1, 262144],
        },
    },
)


def _read_regular(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ProjectionGateError(f"not a regular file: {path}")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 8 * 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _write_exclusive(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, mode)
    try:
        view = memoryview(payload)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                raise OSError(f"short write to {path}")
            view = view[count:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _regular_file_identity(path: Path) -> tuple[int, int, int, int, int]:
    metadata = os.stat(path, follow_symlinks=False)
    if not stat.S_ISREG(metadata.st_mode):
        raise ProjectionGateError(f"not a regular file: {path}")
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _hash_regular_file(path: Path) -> tuple[tuple[int, int, int, int, int], str]:
    before = _regular_file_identity(path)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    digest = hashlib.sha256()
    try:
        metadata = os.fstat(descriptor)
        opened = (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        )
        if opened != before or not stat.S_ISREG(metadata.st_mode):
            raise ProjectionGateError(f"file identity changed before hashing: {path}")
        while chunk := os.read(descriptor, 8 * 1024 * 1024):
            digest.update(chunk)
    finally:
        os.close(descriptor)
    if _regular_file_identity(path) != before:
        raise ProjectionGateError(f"file identity changed while hashing: {path}")
    return before, digest.hexdigest()


def _run_git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ProjectionGateError(f"git source binding failed: {' '.join(args)}")
    return completed.stdout.strip()


def validate_created_at_utc(value: str) -> None:
    if not isinstance(value, str) or not UTC_TIMESTAMP.fullmatch(value):
        raise ProjectionGateError(
            "v2 created_at_utc must be a whole-second UTC timestamp"
        )
    try:
        time.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ProjectionGateError(
            "v2 created_at_utc is not a valid UTC timestamp"
        ) from exc


def validate_sanitized_run_id(value: str) -> None:
    match = SANITIZED_RUN_ID.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise ProjectionGateError("v2 run_id is not a sanitized experiment identifier")
    try:
        time.strptime(match.group("timestamp"), "%Y%m%dT%H%M%SZ")
    except ValueError as exc:
        raise ProjectionGateError(
            "v2 run_id is not a sanitized experiment identifier"
        ) from exc


def _validate_source_revision(source_revision: str) -> dict[str, Any]:
    if not FULL_REVISION.fullmatch(source_revision):
        raise ProjectionGateError(
            "v2 preregistration source revision must be immutable"
        )
    if _run_git("rev-parse", "HEAD") != source_revision:
        raise ProjectionGateError(
            "v2 source revision is not the executing repository HEAD"
        )
    if _run_git("status", "--porcelain", "--", *SOURCE_CLOSURE_RELATIVE_PATHS):
        raise ProjectionGateError("v2 execution closure has uncommitted source drift")
    closure: list[dict[str, Any]] = []
    for relative in SOURCE_CLOSURE_RELATIVE_PATHS:
        committed = subprocess.run(
            [
                "git",
                "-C",
                str(REPOSITORY_ROOT),
                "show",
                f"{source_revision}:{relative}",
            ],
            check=False,
            capture_output=True,
        )
        if committed.returncode != 0:
            raise ProjectionGateError(
                f"v2 execution closure file is absent from source revision: {relative}"
            )
        current = _read_regular(REPOSITORY_ROOT / relative)
        if committed.stdout != current:
            raise ProjectionGateError(
                f"v2 execution closure differs from committed bytes: {relative}"
            )
        closure.append(
            {
                "relative_path": relative,
                "sha256": sha256_bytes(current),
                "git_blob_oid": _run_git("rev-parse", f"{source_revision}:{relative}"),
            }
        )
    current = _read_regular(Path(__file__))
    return {
        "repository": "Zer0pa/Polymath-AI",
        "revision": source_revision,
        "module_relative_path": MODULE_RELATIVE_PATH,
        "module_sha256": sha256_bytes(current),
        "git_blob_oid": _run_git(
            "rev-parse", f"{source_revision}:{MODULE_RELATIVE_PATH}"
        ),
        "execution_closure": closure,
        "head_equals_revision": True,
        "module_clean": True,
    }


def _validate_phone_runtime_paths(
    *,
    phone_runtime_root: Path,
    existing_inputs: Sequence[Path],
    output_path: Path,
) -> dict[str, Any]:
    root = phone_runtime_root.resolve(strict=True)
    if not root.is_relative_to(PHONE_RUNTIME_PREFIX) or root == PHONE_RUNTIME_PREFIX:
        raise ProjectionGateError(
            "phone runtime root is outside a fresh Termux authority run"
        )
    locators: list[str] = []
    for path in existing_inputs:
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ProjectionGateError(
                f"phone oracle input escapes runtime root: {path}"
            )
        locators.append(resolved.relative_to(root).as_posix())
    output_parent = output_path.parent.resolve(strict=True)
    if not output_parent.is_relative_to(root):
        raise ProjectionGateError("phone oracle output escapes runtime root")
    return {
        "execution_plane": "phone_native_termux",
        "device": RESOURCE_SLICE["phone"],
        "root": str(root),
        "input_locators": locators,
        "output_locator": output_path.resolve(strict=False)
        .relative_to(root)
        .as_posix(),
        "raw_output_custody": "phone_private_no_egress",
        "raw_phone_private_upload": False,
        "qnn_execution": False,
    }


def _validate_campaign_inputs(*, parent_capsule: Path, access_receipt: Path) -> None:
    if sha256_path(parent_capsule) != PARENT_CAPSULE_SHA256:
        raise ProjectionGateError("v2 parent capsule digest mismatch")
    if sha256_path(access_receipt) != ACCESS_RECEIPT_SHA256:
        raise ProjectionGateError("v2 access receipt digest mismatch")
    _verify_sidecar(access_receipt, ACCESS_RECEIPT_SHA256)
    access = json.loads(_read_regular(access_receipt))
    expected_access = {
        "schema_version": "gemma4_e4b_access_resource_refresh_v1",
        "state": "passed_scope_with_typed_transient_constraints",
    }
    for name, expected in expected_access.items():
        if access.get(name) != expected:
            raise ProjectionGateError(f"v2 access receipt mismatch: {name}")
    exact_slice = access.get("exact_resource_slice")
    if not isinstance(exact_slice, dict):
        raise ProjectionGateError("v2 access receipt lacks exact resource slice")
    if (
        exact_slice.get("additional_paid_capacity") != 0
        or exact_slice.get("publications") != 0
    ):
        raise ProjectionGateError(
            "v2 access receipt exceeds the authorized resource slice"
        )
    custody = access.get("custody")
    if (
        not isinstance(custody, dict)
        or custody.get("raw_phone_private_payload_egress") is not False
    ):
        raise ProjectionGateError(
            "v2 access receipt permits forbidden phone-private egress"
        )


def execution_envelope() -> dict[str, Any]:
    return {
        "row_block_size": ORACLE_ROW_BLOCK_SIZE,
        "thermal_sensor_type": THERMAL_SENSOR_TYPE,
        "thermal_stop_at_or_above_millidegrees_c": THERMAL_STOP_MILLICELSIUS,
        "minimum_available_memory_bytes": MIN_AVAILABLE_MEMORY_BYTES,
        "minimum_available_storage_bytes": MIN_AVAILABLE_STORAGE_BYTES,
        "maximum_wall_time_seconds": MAX_ORACLE_WALL_SECONDS,
        "guard_before_first_block": True,
        "guard_between_every_row_block": True,
        "performance_ranking_attempted": False,
        "failure_mode": "stop_fail_closed_without_provider_authorization",
    }


def _thermal_temperature() -> tuple[str, int]:
    thermal_root = Path("/sys/class/thermal")
    matches = []
    for type_path in thermal_root.glob("thermal_zone*/type"):
        try:
            sensor_type = type_path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if sensor_type == THERMAL_SENSOR_TYPE:
            matches.append(type_path.parent)
    if len(matches) != 1:
        raise ProjectionGateError(
            f"expected one {THERMAL_SENSOR_TYPE} thermal zone, found {len(matches)}"
        )
    temperature_path = matches[0] / "temp"
    try:
        temperature = int(temperature_path.read_text(encoding="ascii").strip())
    except (OSError, ValueError) as exc:
        raise ProjectionGateError("cannot read frozen phone thermal sensor") from exc
    return str(temperature_path), temperature


def _available_memory_bytes() -> int:
    for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise ProjectionGateError("MemAvailable is missing from /proc/meminfo")


def enforce_phone_resource_envelope(
    *, output_root: Path, started: float, checkpoint: str
) -> dict[str, Any]:
    sensor_path, temperature = _thermal_temperature()
    memory = _available_memory_bytes()
    filesystem = os.statvfs(output_root)
    storage = filesystem.f_bavail * filesystem.f_frsize
    elapsed = time.monotonic() - started
    snapshot = {
        "checkpoint": checkpoint,
        "sensor_type": THERMAL_SENSOR_TYPE,
        "sensor_path": sensor_path,
        "temperature_millidegrees_c": temperature,
        "available_memory_bytes": memory,
        "available_storage_bytes": storage,
        "elapsed_seconds": elapsed,
    }
    if temperature >= THERMAL_STOP_MILLICELSIUS:
        raise ProjectionGateError(
            f"thermal guard stopped execution at {temperature} millidegrees C"
        )
    if memory < MIN_AVAILABLE_MEMORY_BYTES:
        raise ProjectionGateError(
            f"memory guard stopped execution at {memory} available bytes"
        )
    if storage < MIN_AVAILABLE_STORAGE_BYTES:
        raise ProjectionGateError(
            f"storage guard stopped execution at {storage} available bytes"
        )
    if elapsed >= MAX_ORACLE_WALL_SECONDS:
        raise ProjectionGateError(
            f"wall-time guard stopped execution at {elapsed} seconds"
        )
    return snapshot


def validate_resource_snapshots(snapshots: Any, *, independent: bool = False) -> None:
    expected_count = (
        OUTPUT_FEATURES + ORACLE_ROW_BLOCK_SIZE - 1
    ) // ORACLE_ROW_BLOCK_SIZE
    if not isinstance(snapshots, list) or len(snapshots) != expected_count:
        raise ProjectionGateError("phone resource snapshot count mismatch")
    prefix = "independent_" if independent else ""
    expected_checkpoints = [f"{prefix}before_first_row_block"]
    expected_checkpoints.extend(
        f"{prefix}after_rows_{start}_{min(start + ORACLE_ROW_BLOCK_SIZE, OUTPUT_FEATURES)}"
        for start in range(
            0, OUTPUT_FEATURES - ORACLE_ROW_BLOCK_SIZE, ORACLE_ROW_BLOCK_SIZE
        )
    )
    previous_elapsed = -1.0
    exact_keys = {
        "checkpoint",
        "sensor_type",
        "temperature_millidegrees_c",
        "available_memory_bytes",
        "available_storage_bytes",
        "elapsed_seconds",
    }
    for snapshot, checkpoint in zip(snapshots, expected_checkpoints, strict=True):
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("sensor_type") != THERMAL_SENSOR_TYPE
        ):
            raise ProjectionGateError("phone thermal snapshot identity mismatch")
        if set(snapshot) != exact_keys or snapshot.get("checkpoint") != checkpoint:
            raise ProjectionGateError(
                "phone resource snapshot structure/checkpoint mismatch"
            )
        temperature = snapshot.get("temperature_millidegrees_c")
        memory = snapshot.get("available_memory_bytes")
        storage = snapshot.get("available_storage_bytes")
        elapsed = snapshot.get("elapsed_seconds")
        if (
            not isinstance(temperature, int)
            or isinstance(temperature, bool)
            or temperature >= THERMAL_STOP_MILLICELSIUS
        ):
            raise ProjectionGateError(
                "phone thermal snapshot crossed frozen stop threshold"
            )
        if (
            not isinstance(memory, int)
            or isinstance(memory, bool)
            or memory < MIN_AVAILABLE_MEMORY_BYTES
        ):
            raise ProjectionGateError(
                "phone memory snapshot crossed frozen stop threshold"
            )
        if (
            not isinstance(storage, int)
            or isinstance(storage, bool)
            or storage < MIN_AVAILABLE_STORAGE_BYTES
        ):
            raise ProjectionGateError(
                "phone storage snapshot crossed frozen stop threshold"
            )
        if (
            not isinstance(elapsed, (int, float))
            or isinstance(elapsed, bool)
            or not math.isfinite(float(elapsed))
        ):
            raise ProjectionGateError("phone elapsed-time snapshot is invalid")
        if elapsed < previous_elapsed or elapsed >= MAX_ORACLE_WALL_SECONDS:
            raise ProjectionGateError(
                "phone elapsed-time snapshots violate frozen envelope"
            )
        previous_elapsed = float(elapsed)


def sanitized_runtime_binding(binding: dict[str, Any]) -> dict[str, Any]:
    root = str(binding.get("root", ""))
    return {
        "execution_plane": "phone_native_termux",
        "device": RESOURCE_SLICE["phone"],
        "phone_serial_sha256": RESOURCE_SLICE["phone_serial_sha256"],
        "runtime_root_sha256": sha256_bytes(root.encode("utf-8")),
        "raw_output_custody": "phone_private_no_egress",
        "raw_phone_private_upload": False,
        "qnn_execution": False,
        "absolute_paths_egressed": False,
    }


def validate_sanitized_runtime_binding(binding: Any) -> None:
    exact_keys = {
        "execution_plane",
        "device",
        "phone_serial_sha256",
        "runtime_root_sha256",
        "raw_output_custody",
        "raw_phone_private_upload",
        "qnn_execution",
        "absolute_paths_egressed",
    }
    if not isinstance(binding, dict) or set(binding) != exact_keys:
        raise ProjectionGateError("sanitized phone runtime binding structure mismatch")
    expected = {
        "execution_plane": "phone_native_termux",
        "device": RESOURCE_SLICE["phone"],
        "phone_serial_sha256": RESOURCE_SLICE["phone_serial_sha256"],
        "raw_output_custody": "phone_private_no_egress",
        "raw_phone_private_upload": False,
        "qnn_execution": False,
        "absolute_paths_egressed": False,
    }
    for name, value in expected.items():
        if binding.get(name) != value:
            raise ProjectionGateError(
                f"sanitized phone runtime binding mismatch: {name}"
            )
    if not SHA256.fullmatch(str(binding.get("runtime_root_sha256", ""))):
        raise ProjectionGateError("sanitized phone runtime root digest is invalid")


def sanitized_resource_snapshots(
    snapshots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in snapshot.items() if key != "sensor_path"}
        for snapshot in snapshots
    ]


def _strict_load_canonical(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ProjectionGateError(f"non-finite JSON constant: {value}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ProjectionGateError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    raw = _read_regular(path)
    value = json.loads(
        raw, parse_constant=reject_constant, object_pairs_hook=reject_duplicates
    )
    if not isinstance(value, dict) or canonical_json(value) != raw:
        raise ProjectionGateError(f"JSON is not a canonical object: {path}")
    return value


def _verify_sidecar(path: Path, digest: str) -> None:
    expected = f"{digest}  {path.name}\n".encode("ascii")
    if _read_regular(path.with_suffix(path.suffix + ".sha256")) != expected:
        raise ProjectionGateError(f"digest sidecar mismatch: {path}")


def _temporary_directory(output_dir: Path) -> Path:
    output_dir.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    temporary = output_dir.with_name(f".{output_dir.name}.tmp.{secrets.token_hex(16)}")
    temporary.mkdir(mode=0o700)
    return temporary


def _publish(temporary: Path, output_dir: Path) -> None:
    directory = os.open(temporary, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    publish_directory_noreplace(temporary, output_dir)


def bf16_rne_scales_as_exact_f32(
    payload: bytes,
    *,
    expected_count: int = ROW_SCALE_COUNT,
) -> bytes:
    """Round positive finite F32 scales to BF16 RNE and store exact F32 bits.

    The implementation is integer-only after validation.  In particular, it
    does not depend on host BF16 support or on a language-level float cast.
    Every emitted F32 word has its low sixteen fraction bits cleared.
    """

    if len(payload) != expected_count * 4:
        raise ProjectionGateError(
            f"row-scale byte count mismatch: expected {expected_count * 4}, got {len(payload)}"
        )
    output = bytearray(len(payload))
    for index, (bits,) in enumerate(struct.iter_unpack("<I", payload)):
        value = struct.unpack("<f", struct.pack("<I", bits))[0]
        if not math.isfinite(value) or value <= 0.0:
            raise ProjectionGateError(f"row scale {index} is not positive finite F32")
        upper = bits >> 16
        rounded_upper = upper + int((bits & 0xFFFF) > 0x8000)
        if (bits & 0xFFFF) == 0x8000 and (upper & 1):
            rounded_upper += 1
        rounded_bits = (rounded_upper & 0xFFFF) << 16
        rounded_value = struct.unpack("<f", struct.pack("<I", rounded_bits))[0]
        if not math.isfinite(rounded_value) or rounded_value <= 0.0:
            raise ProjectionGateError(
                f"row scale {index} over/underflowed during BF16 RNE"
            )
        struct.pack_into("<I", output, index * 4, rounded_bits)
    return bytes(output)


def _numeric_thresholds() -> dict[str, Any]:
    parent = threshold_policy()["edges"]["w2_bf16_qat_to_qnn_combined"]
    numeric = {
        key: value for key, value in parent.items() if key not in DESCRIPTIVE_EDGE_KEYS
    }
    if sha256_bytes(canonical_json(numeric)) != NUMERIC_THRESHOLD_SUBSET_SHA256:
        raise ProjectionGateError("unchanged authority threshold subset drift")
    return numeric


def oracle_output_relative_path(case_id: str) -> str:
    return f"oracle_outputs/{LM_HEAD_GRAPH}.{case_id}.exact_int32_oracle.s16.raw"


def _validate_oracle_metric_record(metrics: Any) -> None:
    exact_keys = {
        "count",
        "max_abs",
        "rms",
        "relative_l2",
        "cosine",
        "top_k",
        "top_k_set_overlap",
        "top_1_equal",
        "reference_top_k",
        "candidate_top_k",
        "softmax_js_divergence",
    }
    if not isinstance(metrics, dict) or set(metrics) != exact_keys:
        raise ProjectionGateError("sanitized phone oracle metric structure mismatch")
    if metrics.get("count") != OUTPUT_FEATURES or metrics.get("top_k") != TOP_K:
        raise ProjectionGateError("sanitized phone oracle metric width/top-k mismatch")
    for name in (
        "max_abs",
        "rms",
        "relative_l2",
        "cosine",
        "top_k_set_overlap",
        "softmax_js_divergence",
    ):
        value = metrics.get(name)
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
        ):
            raise ProjectionGateError(
                f"sanitized phone oracle metric is invalid: {name}"
            )
    if not isinstance(metrics.get("top_1_equal"), bool):
        raise ProjectionGateError("sanitized phone oracle top-1 metric is invalid")
    for name in ("reference_top_k", "candidate_top_k"):
        indices = metrics.get(name)
        if (
            not isinstance(indices, list)
            or len(indices) != TOP_K
            or any(
                not isinstance(index, int) or isinstance(index, bool)
                for index in indices
            )
            or len(set(indices)) != TOP_K
            or any(index < 0 or index >= OUTPUT_FEATURES for index in indices)
        ):
            raise ProjectionGateError(f"sanitized phone oracle {name} is invalid")
    passed, failures = adjudicate_metrics(metrics, _numeric_thresholds())
    if not passed or failures:
        raise ProjectionGateError(
            "sanitized phone oracle metrics fail unchanged thresholds"
        )


def validate_sanitized_oracle_case(gate_case: Any, frozen: dict[str, Any]) -> None:
    exact_keys = {
        "case_id",
        "input_sha256",
        "authority_output",
        "candidate_output",
        "exact_int32_dot",
        "s16_saturation_count",
        "metrics",
        "failures",
        "passed",
    }
    if not isinstance(gate_case, dict) or set(gate_case) != exact_keys:
        raise ProjectionGateError("sanitized phone oracle case structure mismatch")
    if gate_case.get("case_id") != frozen["case_id"]:
        raise ProjectionGateError("sanitized phone oracle case order/identity mismatch")
    if gate_case.get("input_sha256") != frozen["s16_input_sha256"]:
        raise ProjectionGateError("sanitized phone oracle input binding mismatch")
    authority = frozen["authority_output"]
    if gate_case.get("authority_output") != {
        "relative_path": authority["provider_relative_path"],
        "bytes": authority["bytes"],
        "sha256": authority["sha256"],
    }:
        raise ProjectionGateError("sanitized phone oracle authority binding mismatch")
    output = gate_case.get("candidate_output")
    expected_output_keys = {
        "relative_path",
        "bytes",
        "sha256",
        "dtype",
        "scale",
        "shape",
    }
    if not isinstance(output, dict) or set(output) != expected_output_keys:
        raise ProjectionGateError("sanitized phone oracle output structure mismatch")
    if (
        output.get("relative_path") != oracle_output_relative_path(frozen["case_id"])
        or output.get("bytes") != OUTPUT_FEATURES * 2
        or not SHA256.fullmatch(str(output.get("sha256", "")))
        or output.get("dtype") != "int16"
        or output.get("scale") != OUTPUT_SCALE
        or output.get("shape") != [1, 1, OUTPUT_FEATURES]
    ):
        raise ProjectionGateError("sanitized phone oracle output binding/ABI mismatch")
    exact = gate_case.get("exact_int32_dot")
    exact_keys = {
        "input_features",
        "output_features",
        "multiply_accumulate_count",
        "accumulator_dtype",
        "worst_case_abs_bound",
        "int32_safe",
    }
    if not isinstance(exact, dict) or set(exact) != exact_keys:
        raise ProjectionGateError("sanitized phone oracle exact-dot structure mismatch")
    expected_exact = {
        "input_features": INPUT_FEATURES,
        "output_features": OUTPUT_FEATURES,
        "multiply_accumulate_count": FULL_WIDTH_DOT_PRODUCTS_PER_CASE,
        "accumulator_dtype": "int32",
        "int32_safe": True,
    }
    if any(exact.get(name) != value for name, value in expected_exact.items()):
        raise ProjectionGateError("sanitized phone oracle exact-dot contract mismatch")
    bound = exact.get("worst_case_abs_bound")
    if (
        not isinstance(bound, int)
        or isinstance(bound, bool)
        or not 0 <= bound <= 2_147_483_647
    ):
        raise ProjectionGateError("sanitized phone oracle exact-dot bound is invalid")
    _validate_oracle_metric_record(gate_case.get("metrics"))
    if (
        gate_case.get("s16_saturation_count") != 0
        or gate_case.get("failures") != []
        or gate_case.get("passed") is not True
    ):
        raise ProjectionGateError(
            "sanitized phone oracle case is not an unqualified pass"
        )


def int16_v2_candidate_policy() -> dict[str, Any]:
    numeric = _numeric_thresholds()
    return {
        "schema_version": V2_POLICY_SCHEMA,
        "state": "frozen_before_v2_candidate_output",
        "candidate_id": V2_CANDIDATE_ID,
        "frontier_selector_sha256": FRONTIER_SELECTOR_SHA256,
        "parent_capsule_sha256": PARENT_CAPSULE_SHA256,
        "access_receipt_sha256": ACCESS_RECEIPT_SHA256,
        "resource_slice": RESOURCE_SLICE,
        "phone_execution_envelope": execution_envelope(),
        "parent_int16_v1_policy_sha256": INT16_V1_POLICY_SHA256,
        "authority_edge": {
            "name": "w2_bf16_qat_to_qnn_combined",
            "numeric_and_ranking_thresholds": numeric,
            "numeric_and_ranking_threshold_subset_sha256": NUMERIC_THRESHOLD_SUBSET_SHA256,
            "threshold_values_changed_from_parent": False,
            "every_metric_and_every_case_must_pass": True,
        },
        "input_quantization": {
            "dtype": "QNN_DATATYPE_SFIXED_POINT_16",
            "scale": INPUT_SCALE,
            "offset": 0,
            "changed_from_v1": False,
        },
        "weight_quantization": {
            "packed_weight_sha256": PACKED_WEIGHT_SHA256,
            "original_f32_scale_sha256": ORIGINAL_SCALE_SHA256,
            "scale_transform": "float32_to_bfloat16_RNE_then_exact_float32_storage",
            "dtype": "QNN_DATATYPE_SFIXED_POINT_8",
            "storage_bitwidth": WEIGHT_BITS,
            "axis": 0,
            "transpose_in1": True,
            "packed_tensor_changed_from_v1": False,
        },
        "output_quantization": {
            "dtype": "QNN_DATATYPE_SFIXED_POINT_16",
            "scale": OUTPUT_SCALE,
            "offset": 0,
            "representable_range": [-32768 * OUTPUT_SCALE, 32767 * OUTPUT_SCALE],
            "selection_used_v2_candidate_output": False,
        },
        "pre_provider_falsifier": {
            "kind": "full_width_exact_INT32_dot_quantized_oracle",
            "case_count": 3,
            "dot_products_per_case": FULL_WIDTH_DOT_PRODUCTS_PER_CASE,
            "provider_build_allowed_only_if_every_case_passes": True,
        },
        "failure_rule": "kill_standard_HTP_S16_without_provider_build_if_oracle_fails",
        "nonclaims": [
            "no_v2_oracle_output",
            "no_provider_build_or_context",
            "no_phone_execution",
            "no_L1_or_L2_pass",
            "no_learning_or_authority_quality",
        ],
    }


def _load_v1_preregistration(root: Path) -> dict[str, Any]:
    manifest_path = root / "preregistration.json"
    policy_path = root / "threshold_policy.json"
    if sha256_path(manifest_path) != INT16_V1_PREREG_SHA256:
        raise ProjectionGateError("v1 preregistration digest mismatch")
    if sha256_path(policy_path) != INT16_V1_POLICY_SHA256:
        raise ProjectionGateError("v1 policy digest mismatch")
    _verify_sidecar(manifest_path, INT16_V1_PREREG_SHA256)
    _verify_sidecar(policy_path, INT16_V1_POLICY_SHA256)
    manifest = _strict_load_canonical(manifest_path)
    if manifest.get("state") != "frozen_unobserved":
        raise ProjectionGateError("v1 preregistration is not frozen-unobserved")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != 3:
        raise ProjectionGateError("v1 preregistration case set mismatch")
    for observed, expected in zip(cases, FROZEN_CASES, strict=True):
        required = {
            **expected,
            "candidate_output_present": False,
            "input_roundtrip_max_abs": 0.0,
        }
        if observed != required:
            raise ProjectionGateError(
                f"v1 parent case contract drift: {expected['case_id']}"
            )
    return manifest


def _validate_frontier_selector(path: Path) -> None:
    if sha256_path(path) != FRONTIER_SELECTOR_SHA256:
        raise ProjectionGateError("v2 frontier selector digest mismatch")
    _verify_sidecar(path, FRONTIER_SELECTOR_SHA256)
    event = json.loads(_read_regular(path))
    contract = (
        event.get("immutable_candidate_contract") if isinstance(event, dict) else None
    )
    required_contract = {
        "candidate_id": V2_CANDIDATE_ID,
        "packed_weight_sha256": PACKED_WEIGHT_SHA256,
        "original_scale_sha256": ORIGINAL_SCALE_SHA256,
        "scale_transform": "float32_to_bfloat16_RNE_then_exact_float32_storage",
        "input_dtype": "QNN_DATATYPE_SFIXED_POINT_16",
        "input_scale": INPUT_SCALE,
        "weight_dtype": "QNN_DATATYPE_SFIXED_POINT_8_BW2_axis0",
        "output_dtype": "QNN_DATATYPE_SFIXED_POINT_16",
        "output_scale": OUTPUT_SCALE,
        "thresholds_sha256": INT16_V1_POLICY_SHA256,
        "numeric_ranking_threshold_subset_sha256": NUMERIC_THRESHOLD_SUBSET_SHA256,
        "thresholds_changed": False,
        "v2_candidate_output_observed": False,
    }
    if not isinstance(contract, dict) or event.get("state") != "selected":
        raise ProjectionGateError(
            "v2 frontier selector is not a selected candidate event"
        )
    for name, expected in required_contract.items():
        if contract.get(name) != expected:
            raise ProjectionGateError(f"v2 frontier selector contract mismatch: {name}")
    if (
        event.get("provider_context_generated") is not False
        or event.get("phone_execution_started") is not False
    ):
        raise ProjectionGateError(
            "v2 frontier selector is already observed or provider-mutated"
        )


def _expected_v2_case(frozen: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": frozen["case_id"],
        "s16_input_relative_path": frozen["s16_input_relative_path"],
        "s16_input_bytes": frozen["s16_input_bytes"],
        "s16_input_sha256": frozen["s16_input_sha256"],
        "authority_output": frozen["authority_output"],
        "v2_oracle_output_present": False,
        "v2_qnn_output_present": False,
    }


def _validate_preregistration_tree(root: Path) -> None:
    expected_files = {
        "preregistration.json",
        "preregistration.json.sha256",
        "threshold_policy.json",
        "threshold_policy.json.sha256",
        ORIGINAL_SCALE_ARTIFACT_RELATIVE_PATH,
        SCALE_ARTIFACT_RELATIVE_PATH,
        *(case["s16_input_relative_path"] for case in FROZEN_CASES),
    }
    expected_directories = {"inputs", "tensors"}
    observed_files: set[str] = set()
    observed_directories: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ProjectionGateError(
                f"symlink forbidden in v2 preregistration: {relative}"
            )
        if path.is_dir():
            observed_directories.add(relative)
        elif path.is_file():
            observed_files.add(relative)
        else:
            raise ProjectionGateError(f"non-regular preregistration entry: {relative}")
    if observed_files != expected_files or observed_directories != expected_directories:
        raise ProjectionGateError("v2 preregistration file-tree whitelist mismatch")


def _validate_preregistration_metadata_tree(root: Path) -> None:
    expected_files = {
        "preregistration.json",
        "preregistration.json.sha256",
        "threshold_policy.json",
        "threshold_policy.json.sha256",
    }
    observed_files: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ProjectionGateError(
                f"symlink forbidden in sanitized v2 metadata: {relative}"
            )
        if path.is_dir():
            raise ProjectionGateError(
                f"directory forbidden in sanitized v2 metadata: {relative}"
            )
        if not path.is_file():
            raise ProjectionGateError(
                f"non-regular sanitized v2 metadata entry: {relative}"
            )
        observed_files.add(relative)
    if observed_files != expected_files:
        raise ProjectionGateError("sanitized v2 metadata file-tree whitelist mismatch")


def build_int16_v2_preregistration(
    *,
    parent_int16_prereg_dir: Path,
    frontier_selector: Path,
    parent_capsule: Path,
    access_receipt: Path,
    phone_runtime_root: Path,
    original_scale_path: Path,
    output_dir: Path,
    created_at_utc: str,
    source_revision: str,
) -> dict[str, Any]:
    """Atomically freeze v2 inputs and transformed metadata before output."""

    if output_dir.exists():
        raise ProjectionGateError(f"output already exists: {output_dir}")
    validate_created_at_utc(created_at_utc)
    source_binding = _validate_source_revision(source_revision)
    runtime_binding = _validate_phone_runtime_paths(
        phone_runtime_root=phone_runtime_root,
        existing_inputs=(
            parent_int16_prereg_dir,
            frontier_selector,
            parent_capsule,
            access_receipt,
            original_scale_path,
            REPOSITORY_ROOT,
        ),
        output_path=output_dir,
    )
    _validate_campaign_inputs(
        parent_capsule=parent_capsule, access_receipt=access_receipt
    )
    _validate_frontier_selector(frontier_selector)
    parent = _load_v1_preregistration(parent_int16_prereg_dir)
    original_scales = _read_regular(original_scale_path)
    if len(original_scales) != ORIGINAL_SCALE_BYTES:
        raise ProjectionGateError("original row-scale byte count mismatch")
    if sha256_bytes(original_scales) != ORIGINAL_SCALE_SHA256:
        raise ProjectionGateError("original row-scale digest mismatch")
    transformed_scales = bf16_rne_scales_as_exact_f32(
        original_scales,
        expected_count=ROW_SCALE_COUNT,
    )

    temporary = _temporary_directory(output_dir)
    (temporary / "inputs").mkdir(mode=0o700)
    (temporary / "tensors").mkdir(mode=0o700)
    policy = int16_v2_candidate_policy()
    policy_sha256 = write_hashed_json(temporary / "threshold_policy.json", policy)
    scale_path = temporary / SCALE_ARTIFACT_RELATIVE_PATH
    original_scale_artifact = temporary / ORIGINAL_SCALE_ARTIFACT_RELATIVE_PATH
    _write_exclusive(original_scale_artifact, original_scales)
    _write_exclusive(scale_path, transformed_scales)

    cases: list[dict[str, Any]] = []
    for parent_case, frozen_case in zip(parent["cases"], FROZEN_CASES, strict=True):
        case_id = parent_case.get("case_id")
        relative = parent_case.get("s16_input_relative_path")
        if not isinstance(case_id, str) or not isinstance(relative, str):
            raise ProjectionGateError("invalid parent INT16 case")
        source = parent_int16_prereg_dir / relative
        payload = _read_regular(source)
        if len(payload) != parent_case.get("s16_input_bytes") or sha256_bytes(
            payload
        ) != parent_case.get("s16_input_sha256"):
            raise ProjectionGateError(f"parent S16 input drift: {case_id}")
        destination = temporary / "inputs" / Path(relative).name
        _write_exclusive(destination, payload)
        authority = parent_case.get("authority_output")
        if not isinstance(authority, dict) or not SHA256.fullmatch(
            str(authority.get("sha256", ""))
        ):
            raise ProjectionGateError(f"invalid authority binding: {case_id}")
        expected_case = _expected_v2_case(frozen_case)
        observed_case = {
            **expected_case,
            "s16_input_relative_path": f"inputs/{destination.name}",
            "s16_input_bytes": len(payload),
            "s16_input_sha256": sha256_bytes(payload),
            "authority_output": authority,
        }
        if observed_case != expected_case:
            raise ProjectionGateError(f"v2 frozen case drift: {case_id}")
        cases.append(observed_case)

    module_sha256 = sha256_path(Path(__file__))
    manifest = {
        "schema_version": V2_PREREG_SCHEMA,
        "state": "frozen_unobserved",
        "created_at_utc": created_at_utc,
        "source_revision": source_revision,
        "source_binding": source_binding,
        "implementation_module_sha256": module_sha256,
        "frontier_selector_sha256": FRONTIER_SELECTOR_SHA256,
        "parent_capsule_sha256": PARENT_CAPSULE_SHA256,
        "access_receipt_sha256": ACCESS_RECEIPT_SHA256,
        "campaign_lease_id": CAMPAIGN_LEASE_ID,
        "resource_slice": RESOURCE_SLICE,
        "phone_execution_envelope": execution_envelope(),
        "runtime_binding": sanitized_runtime_binding(runtime_binding),
        "candidate_id": V2_CANDIDATE_ID,
        "model_sha256": QAT_MODEL_SHA256,
        "graph_name": LM_HEAD_GRAPH,
        "input_features": INPUT_FEATURES,
        "output_features": OUTPUT_FEATURES,
        "parent_int16_v1_preregistration_sha256": INT16_V1_PREREG_SHA256,
        "parent_int16_v1_policy_sha256": INT16_V1_POLICY_SHA256,
        "threshold_policy_sha256": policy_sha256,
        "numeric_and_ranking_threshold_subset_sha256": NUMERIC_THRESHOLD_SUBSET_SHA256,
        "candidate_contract": {
            "packed_weight_sha256": PACKED_WEIGHT_SHA256,
            "packed_weight_changed_from_v1": False,
            "original_scale_sha256": ORIGINAL_SCALE_SHA256,
            "original_scale_relative_path": ORIGINAL_SCALE_ARTIFACT_RELATIVE_PATH,
            "original_scale_bytes": len(original_scales),
            "transformed_scale_relative_path": SCALE_ARTIFACT_RELATIVE_PATH,
            "transformed_scale_bytes": len(transformed_scales),
            "transformed_scale_sha256": sha256_bytes(transformed_scales),
            "scale_transform": "float32_to_bfloat16_RNE_then_exact_float32_storage",
            "input_scale": INPUT_SCALE,
            "output_scale": OUTPUT_SCALE,
            "weight_bitwidth": WEIGHT_BITS,
            "weight_axis": 0,
            "transpose_in1": True,
        },
        "cases": cases,
        "required_next_gate": {
            "schema_version": V2_ORACLE_SCHEMA,
            "kind": "full_width_exact_INT32_dot_quantized_oracle",
            "case_count": 3,
            "every_case_and_every_unchanged_metric_must_pass": True,
            "provider_build_before_pass_forbidden": True,
        },
        "v2_candidate_output_files_present": False,
        "provider_build_allowed": False,
        "custody": {
            "preregistration_plane": "phone_native_termux",
            "oracle_raw_output_plane": "phone_private_only",
            "oracle_raw_output_egress": False,
            "phone_private_raw_upload_to_provider": False,
            "repository_or_comet_raw_output_storage": False,
            "sanitized_hash_bound_metadata_egress_only": True,
            "qnn_phone_execution_is_distinct_and_unstarted": True,
        },
        "claim_boundary": "final_S16_v2_preregistration_and_scale_transform_only",
        "nonclaims": policy["nonclaims"],
    }
    preregistration_sha256 = write_hashed_json(
        temporary / "preregistration.json", manifest
    )
    _validate_preregistration_tree(temporary)
    _publish(temporary, output_dir)
    return {
        "preregistration_sha256": preregistration_sha256,
        "threshold_policy_sha256": policy_sha256,
        "transformed_scale_sha256": sha256_bytes(transformed_scales),
        "case_count": len(cases),
        "provider_build_allowed": False,
    }


def validate_int16_v2_preregistration(root: Path) -> tuple[dict[str, Any], str]:
    _validate_preregistration_tree(root)
    manifest_path = root / "preregistration.json"
    policy_path = root / "threshold_policy.json"
    manifest = _strict_load_canonical(manifest_path)
    manifest_sha256 = sha256_path(manifest_path)
    _verify_sidecar(manifest_path, manifest_sha256)
    policy = _strict_load_canonical(policy_path)
    policy_sha256 = sha256_path(policy_path)
    _verify_sidecar(policy_path, policy_sha256)
    if policy != int16_v2_candidate_policy():
        raise ProjectionGateError("v2 policy drift")
    exact_manifest_keys = {
        "schema_version",
        "state",
        "created_at_utc",
        "source_revision",
        "source_binding",
        "implementation_module_sha256",
        "frontier_selector_sha256",
        "parent_capsule_sha256",
        "access_receipt_sha256",
        "campaign_lease_id",
        "resource_slice",
        "phone_execution_envelope",
        "runtime_binding",
        "candidate_id",
        "model_sha256",
        "graph_name",
        "input_features",
        "output_features",
        "parent_int16_v1_preregistration_sha256",
        "parent_int16_v1_policy_sha256",
        "threshold_policy_sha256",
        "numeric_and_ranking_threshold_subset_sha256",
        "candidate_contract",
        "cases",
        "required_next_gate",
        "v2_candidate_output_files_present",
        "provider_build_allowed",
        "custody",
        "claim_boundary",
        "nonclaims",
    }
    if set(manifest) != exact_manifest_keys:
        raise ProjectionGateError("v2 preregistration manifest structure mismatch")
    required = {
        "schema_version": V2_PREREG_SCHEMA,
        "state": "frozen_unobserved",
        "candidate_id": V2_CANDIDATE_ID,
        "model_sha256": QAT_MODEL_SHA256,
        "graph_name": LM_HEAD_GRAPH,
        "input_features": INPUT_FEATURES,
        "output_features": OUTPUT_FEATURES,
        "frontier_selector_sha256": FRONTIER_SELECTOR_SHA256,
        "parent_capsule_sha256": PARENT_CAPSULE_SHA256,
        "access_receipt_sha256": ACCESS_RECEIPT_SHA256,
        "campaign_lease_id": CAMPAIGN_LEASE_ID,
        "resource_slice": RESOURCE_SLICE,
        "phone_execution_envelope": execution_envelope(),
        "implementation_module_sha256": sha256_path(Path(__file__)),
        "parent_int16_v1_preregistration_sha256": INT16_V1_PREREG_SHA256,
        "parent_int16_v1_policy_sha256": INT16_V1_POLICY_SHA256,
        "threshold_policy_sha256": policy_sha256,
        "numeric_and_ranking_threshold_subset_sha256": NUMERIC_THRESHOLD_SUBSET_SHA256,
        "v2_candidate_output_files_present": False,
        "provider_build_allowed": False,
    }
    for name, expected in required.items():
        if manifest.get(name) != expected:
            raise ProjectionGateError(f"v2 preregistration contract mismatch: {name}")
    validate_created_at_utc(manifest.get("created_at_utc"))
    if not FULL_REVISION.fullmatch(str(manifest.get("source_revision", ""))):
        raise ProjectionGateError("v2 preregistration source revision is invalid")
    source_binding = _validate_source_revision(manifest["source_revision"])
    if manifest.get("source_binding") != source_binding:
        raise ProjectionGateError("v2 preregistration source commit binding mismatch")
    expected_custody = {
        "preregistration_plane": "phone_native_termux",
        "oracle_raw_output_plane": "phone_private_only",
        "oracle_raw_output_egress": False,
        "phone_private_raw_upload_to_provider": False,
        "repository_or_comet_raw_output_storage": False,
        "sanitized_hash_bound_metadata_egress_only": True,
        "qnn_phone_execution_is_distinct_and_unstarted": True,
    }
    if manifest.get("custody") != expected_custody:
        raise ProjectionGateError("v2 preregistration custody contract mismatch")
    expected_next_gate = {
        "schema_version": V2_ORACLE_SCHEMA,
        "kind": "full_width_exact_INT32_dot_quantized_oracle",
        "case_count": 3,
        "every_case_and_every_unchanged_metric_must_pass": True,
        "provider_build_before_pass_forbidden": True,
    }
    if manifest.get("required_next_gate") != expected_next_gate:
        raise ProjectionGateError("v2 preregistration next-gate contract mismatch")
    if (
        manifest.get("claim_boundary")
        != "final_S16_v2_preregistration_and_scale_transform_only"
    ):
        raise ProjectionGateError("v2 preregistration claim boundary mismatch")
    if manifest.get("nonclaims") != policy["nonclaims"]:
        raise ProjectionGateError("v2 preregistration nonclaim set mismatch")
    validate_sanitized_runtime_binding(manifest.get("runtime_binding"))
    contract = manifest.get("candidate_contract")
    expected_contract = {
        "packed_weight_sha256": PACKED_WEIGHT_SHA256,
        "packed_weight_changed_from_v1": False,
        "original_scale_sha256": ORIGINAL_SCALE_SHA256,
        "original_scale_relative_path": ORIGINAL_SCALE_ARTIFACT_RELATIVE_PATH,
        "original_scale_bytes": ORIGINAL_SCALE_BYTES,
        "transformed_scale_relative_path": SCALE_ARTIFACT_RELATIVE_PATH,
        "transformed_scale_bytes": ORIGINAL_SCALE_BYTES,
        "scale_transform": "float32_to_bfloat16_RNE_then_exact_float32_storage",
        "input_scale": INPUT_SCALE,
        "output_scale": OUTPUT_SCALE,
        "weight_bitwidth": WEIGHT_BITS,
        "weight_axis": 0,
        "transpose_in1": True,
    }
    if not isinstance(contract, dict):
        raise ProjectionGateError("v2 candidate contract is missing")
    if set(contract) != {*expected_contract, "transformed_scale_sha256"}:
        raise ProjectionGateError("v2 candidate contract structure mismatch")
    for name, expected in expected_contract.items():
        if contract.get(name) != expected:
            raise ProjectionGateError(f"v2 candidate contract mismatch: {name}")
    original_path = root / ORIGINAL_SCALE_ARTIFACT_RELATIVE_PATH
    original_payload = _read_regular(original_path)
    if (
        len(original_payload) != ORIGINAL_SCALE_BYTES
        or sha256_bytes(original_payload) != ORIGINAL_SCALE_SHA256
    ):
        raise ProjectionGateError("v2 original scale artifact drift")
    expected_transformed = bf16_rne_scales_as_exact_f32(
        original_payload,
        expected_count=ROW_SCALE_COUNT,
    )
    scale_path = root / SCALE_ARTIFACT_RELATIVE_PATH
    scale_payload = _read_regular(scale_path)
    if len(scale_payload) != contract.get("transformed_scale_bytes") or sha256_bytes(
        scale_payload
    ) != contract.get("transformed_scale_sha256"):
        raise ProjectionGateError("v2 transformed scale artifact drift")
    if scale_payload != expected_transformed:
        raise ProjectionGateError(
            "v2 transformed scale does not recompute from bound original F32 scale"
        )
    if any(bits & 0xFFFF for (bits,) in struct.iter_unpack("<I", scale_payload)):
        raise ProjectionGateError("v2 scale artifact is not exact BF16-as-F32 storage")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != 3:
        raise ProjectionGateError("v2 preregistration case set mismatch")
    for record, frozen in zip(cases, FROZEN_CASES, strict=True):
        if not isinstance(record, dict):
            raise ProjectionGateError("invalid v2 case record")
        if record != _expected_v2_case(frozen):
            raise ProjectionGateError(
                f"v2 preregistration frozen case drift: {frozen['case_id']}"
            )
        relative = record.get("s16_input_relative_path")
        if (
            not isinstance(relative, str)
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            raise ProjectionGateError("unsafe v2 input path")
        payload = _read_regular(root / relative)
        if len(payload) != record.get("s16_input_bytes") or sha256_bytes(
            payload
        ) != record.get("s16_input_sha256"):
            raise ProjectionGateError(f"v2 S16 input drift: {record.get('case_id')}")
        if (
            record.get("v2_oracle_output_present") is not False
            or record.get("v2_qnn_output_present") is not False
        ):
            raise ProjectionGateError("v2 preregistration contains observed output")
    return manifest, manifest_sha256


def validate_int16_v2_preregistration_metadata(
    root: Path,
) -> tuple[dict[str, Any], str]:
    """Validate the sanitized preregistration surface without opening tensors."""

    _validate_preregistration_metadata_tree(root)
    manifest_path = root / "preregistration.json"
    policy_path = root / "threshold_policy.json"
    manifest = _strict_load_canonical(manifest_path)
    manifest_sha256 = sha256_path(manifest_path)
    _verify_sidecar(manifest_path, manifest_sha256)
    policy = _strict_load_canonical(policy_path)
    policy_sha256 = sha256_path(policy_path)
    _verify_sidecar(policy_path, policy_sha256)
    if policy != int16_v2_candidate_policy():
        raise ProjectionGateError("sanitized v2 policy drift")
    exact_manifest_keys = {
        "schema_version",
        "state",
        "created_at_utc",
        "source_revision",
        "source_binding",
        "implementation_module_sha256",
        "frontier_selector_sha256",
        "parent_capsule_sha256",
        "access_receipt_sha256",
        "campaign_lease_id",
        "resource_slice",
        "phone_execution_envelope",
        "runtime_binding",
        "candidate_id",
        "model_sha256",
        "graph_name",
        "input_features",
        "output_features",
        "parent_int16_v1_preregistration_sha256",
        "parent_int16_v1_policy_sha256",
        "threshold_policy_sha256",
        "numeric_and_ranking_threshold_subset_sha256",
        "candidate_contract",
        "cases",
        "required_next_gate",
        "v2_candidate_output_files_present",
        "provider_build_allowed",
        "custody",
        "claim_boundary",
        "nonclaims",
    }
    if set(manifest) != exact_manifest_keys:
        raise ProjectionGateError(
            "sanitized v2 preregistration manifest structure mismatch"
        )
    required = {
        "schema_version": V2_PREREG_SCHEMA,
        "state": "frozen_unobserved",
        "candidate_id": V2_CANDIDATE_ID,
        "model_sha256": QAT_MODEL_SHA256,
        "graph_name": LM_HEAD_GRAPH,
        "input_features": INPUT_FEATURES,
        "output_features": OUTPUT_FEATURES,
        "frontier_selector_sha256": FRONTIER_SELECTOR_SHA256,
        "parent_capsule_sha256": PARENT_CAPSULE_SHA256,
        "access_receipt_sha256": ACCESS_RECEIPT_SHA256,
        "campaign_lease_id": CAMPAIGN_LEASE_ID,
        "resource_slice": RESOURCE_SLICE,
        "phone_execution_envelope": execution_envelope(),
        "implementation_module_sha256": sha256_path(Path(__file__)),
        "parent_int16_v1_preregistration_sha256": INT16_V1_PREREG_SHA256,
        "parent_int16_v1_policy_sha256": INT16_V1_POLICY_SHA256,
        "threshold_policy_sha256": policy_sha256,
        "numeric_and_ranking_threshold_subset_sha256": NUMERIC_THRESHOLD_SUBSET_SHA256,
        "v2_candidate_output_files_present": False,
        "provider_build_allowed": False,
    }
    for name, expected in required.items():
        if manifest.get(name) != expected:
            raise ProjectionGateError(f"sanitized v2 preregistration mismatch: {name}")
    validate_created_at_utc(manifest.get("created_at_utc"))
    source_binding = _validate_source_revision(str(manifest.get("source_revision", "")))
    if manifest.get("source_binding") != source_binding:
        raise ProjectionGateError("sanitized v2 source binding mismatch")
    if manifest.get("cases") != [_expected_v2_case(case) for case in FROZEN_CASES]:
        raise ProjectionGateError("sanitized v2 frozen case set mismatch")
    contract = manifest.get("candidate_contract")
    if not isinstance(contract, dict):
        raise ProjectionGateError("sanitized v2 candidate contract is missing")
    expected_contract = {
        "packed_weight_sha256": PACKED_WEIGHT_SHA256,
        "packed_weight_changed_from_v1": False,
        "original_scale_sha256": ORIGINAL_SCALE_SHA256,
        "original_scale_relative_path": ORIGINAL_SCALE_ARTIFACT_RELATIVE_PATH,
        "original_scale_bytes": ORIGINAL_SCALE_BYTES,
        "transformed_scale_relative_path": SCALE_ARTIFACT_RELATIVE_PATH,
        "transformed_scale_bytes": ORIGINAL_SCALE_BYTES,
        "scale_transform": "float32_to_bfloat16_RNE_then_exact_float32_storage",
        "input_scale": INPUT_SCALE,
        "output_scale": OUTPUT_SCALE,
        "weight_bitwidth": WEIGHT_BITS,
        "weight_axis": 0,
        "transpose_in1": True,
    }
    for name, expected in expected_contract.items():
        if contract.get(name) != expected:
            raise ProjectionGateError(
                f"sanitized v2 candidate contract mismatch: {name}"
            )
    if set(contract) != {*expected_contract, "transformed_scale_sha256"}:
        raise ProjectionGateError("sanitized v2 candidate contract structure mismatch")
    if not SHA256.fullmatch(str(contract.get("transformed_scale_sha256", ""))):
        raise ProjectionGateError("sanitized v2 transformed scale digest is invalid")
    expected_custody = {
        "preregistration_plane": "phone_native_termux",
        "oracle_raw_output_plane": "phone_private_only",
        "oracle_raw_output_egress": False,
        "phone_private_raw_upload_to_provider": False,
        "repository_or_comet_raw_output_storage": False,
        "sanitized_hash_bound_metadata_egress_only": True,
        "qnn_phone_execution_is_distinct_and_unstarted": True,
    }
    if manifest.get("custody") != expected_custody:
        raise ProjectionGateError("sanitized v2 custody contract mismatch")
    expected_next_gate = {
        "schema_version": V2_ORACLE_SCHEMA,
        "kind": "full_width_exact_INT32_dot_quantized_oracle",
        "case_count": 3,
        "every_case_and_every_unchanged_metric_must_pass": True,
        "provider_build_before_pass_forbidden": True,
    }
    if manifest.get("required_next_gate") != expected_next_gate:
        raise ProjectionGateError("sanitized v2 next-gate contract mismatch")
    if (
        manifest.get("claim_boundary")
        != "final_S16_v2_preregistration_and_scale_transform_only"
    ):
        raise ProjectionGateError("sanitized v2 claim boundary mismatch")
    if manifest.get("nonclaims") != policy["nonclaims"]:
        raise ProjectionGateError("sanitized v2 nonclaim set mismatch")
    validate_sanitized_runtime_binding(manifest.get("runtime_binding"))
    return manifest, manifest_sha256


def render_int16_v2_head_cpp() -> str:
    """Render the exact two-graph source with only the admitted v2 S16 ABI."""

    source = render_direct_qnn_cpp()
    old = """    GraphSpec headSpec{
        "gemma4_e4b_f5_w2_lm_head",
        "lm_head_input_f16",
        "lm_head_weight_s8_bw2",
        "lm_head_output_f16_pre_softcap",
        "lm_head_matmul",
        2560,
        262144,
        2,
        QNN_DATATYPE_FLOAT_16,
        undefinedQuantization(),
        undefinedQuantization(),
    };"""
    new = f"""    GraphSpec headSpec{{
        "gemma4_e4b_f5_w2_lm_head",
        "lm_head_input_s16_v2",
        "lm_head_weight_s8_bw2_bf16_rne_scale_v2",
        "lm_head_output_s16_2m10_pre_softcap_v2",
        "lm_head_matmul_v2",
        2560,
        262144,
        2,
        QNN_DATATYPE_SFIXED_POINT_16,
        scaleOffsetQuantization({INPUT_SCALE:.10f}f),
        scaleOffsetQuantization({OUTPUT_SCALE:.10f}f),
    }};"""
    if source.count(old) != 1:
        raise ProjectionGateError("cannot identify exact FP16 head graph block")
    transformed = source.replace(old, new)
    if (
        "lm_head_input_f16" in transformed
        or "lm_head_output_f16_pre_softcap" in transformed
    ):
        raise ProjectionGateError("FP16 head ABI survived v2 transformation")
    return transformed


def _decode_bf16(payload: bytes) -> list[float]:
    if len(payload) != OUTPUT_FEATURES * 2:
        raise ProjectionGateError("authority BF16 output byte count mismatch")
    return bf16_payload_to_floats(payload)


def _unpack_weight_rows(packed_rows: Any) -> Any:
    """Unpack a NumPy U8 [rows, width/4] block in Transformers lane order."""

    import numpy as np

    if packed_rows.ndim != 2 or packed_rows.shape[1] * 4 != INPUT_FEATURES:
        raise ProjectionGateError("packed oracle weight block shape mismatch")
    lanes = np.empty((packed_rows.shape[0], packed_rows.shape[1], 4), dtype=np.int8)
    for lane in range(4):
        lanes[:, :, lane] = ((packed_rows >> (lane * 2)) & 0x03).astype(
            np.int8
        ) + SIGNED_WEIGHT_SHIFT
    return lanes.reshape(packed_rows.shape[0], INPUT_FEATURES)


def _oracle_metrics(
    reference: Sequence[float], candidate: Sequence[float]
) -> dict[str, Any]:
    metrics = vector_metrics(reference, candidate)
    metrics["softmax_js_divergence"] = softmax_js_divergence(reference, candidate)
    return metrics


def run_int16_v2_exact_dot_oracle(
    *,
    prereg_dir: Path,
    packed_weight_path: Path,
    authority_root: Path,
    phone_runtime_root: Path,
    output_dir: Path,
    run_id: str,
    row_block_size: int = 2048,
) -> dict[str, Any]:
    """Execute the full 3x262144x2560 exact-INT32 pre-provider oracle.

    This is the first operation that observes v2 candidate outputs.  It writes
    to a no-replace transaction and publishes a provider authorization only
    when every case passes the unchanged numeric and ranking thresholds.
    """

    import numpy as np

    if output_dir.exists():
        raise ProjectionGateError(f"output already exists: {output_dir}")
    validate_sanitized_run_id(run_id)
    if platform.python_version() != ORACLE_PYTHON_VERSION:
        raise ProjectionGateError(
            f"exact-dot oracle Python drift: {platform.python_version()}"
        )
    if np.__version__ != ORACLE_NUMPY_VERSION:
        raise ProjectionGateError(f"exact-dot oracle NumPy drift: {np.__version__}")
    if row_block_size != ORACLE_ROW_BLOCK_SIZE:
        raise ProjectionGateError(
            "oracle row block size differs from preregistered execution envelope"
        )
    runtime_binding = _validate_phone_runtime_paths(
        phone_runtime_root=phone_runtime_root,
        existing_inputs=(
            prereg_dir,
            packed_weight_path,
            authority_root,
            REPOSITORY_ROOT,
        ),
        output_path=output_dir,
    )
    prereg, prereg_sha256 = validate_int16_v2_preregistration(prereg_dir)
    packed_identity, packed_sha256 = _hash_regular_file(packed_weight_path)
    if (
        packed_identity[2] != PACKED_WEIGHT_BYTES
        or packed_sha256 != PACKED_WEIGHT_SHA256
    ):
        raise ProjectionGateError("packed INT2 tensor identity mismatch")

    cases = prereg["cases"]
    inputs = []
    references: list[list[float]] = []
    reference_records: list[dict[str, Any]] = []
    input_artifacts: list[tuple[Path, tuple[int, int, int, int, int]]] = []
    authority_artifacts: list[tuple[Path, tuple[int, int, int, int, int]]] = []
    for record in cases:
        input_path = prereg_dir / record["s16_input_relative_path"]
        input_identity, input_sha256 = _hash_regular_file(input_path)
        input_payload = _read_regular(input_path)
        if (
            input_identity[2] != record["s16_input_bytes"]
            or input_sha256 != record["s16_input_sha256"]
        ):
            raise ProjectionGateError(
                f"S16 input identity mismatch: {record['case_id']}"
            )
        input_artifacts.append((input_path, input_identity))
        input_values = np.frombuffer(input_payload, dtype="<i2").astype(np.int32)
        if input_values.size != INPUT_FEATURES:
            raise ProjectionGateError(f"S16 input width mismatch: {record['case_id']}")
        inputs.append(input_values)
        authority = record["authority_output"]
        relative = authority.get("provider_relative_path")
        if (
            not isinstance(relative, str)
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            raise ProjectionGateError("unsafe authority output path")
        authority_path = authority_root / relative
        authority_identity, authority_sha256 = _hash_regular_file(authority_path)
        payload = _read_regular(authority_path)
        if authority_identity[2] != authority.get(
            "bytes"
        ) or authority_sha256 != authority.get("sha256"):
            raise ProjectionGateError(f"authority output drift: {record['case_id']}")
        authority_artifacts.append((authority_path, authority_identity))
        references.append(_decode_bf16(payload))
        reference_records.append(
            {
                "relative_path": relative,
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
            }
        )
    input_matrix = np.stack(inputs, axis=0).astype(np.int32, copy=False)
    max_abs_input = int(np.max(np.abs(input_matrix.astype(np.int64))))
    integer_bound = max_abs_input * abs(SIGNED_WEIGHT_SHIFT) * INPUT_FEATURES
    if integer_bound > np.iinfo(np.int32).max:
        raise ProjectionGateError("exact INT32 dot bound exceeds INT32")

    scale_contract = prereg["candidate_contract"]
    scale_path = prereg_dir / scale_contract["transformed_scale_relative_path"]
    scale_identity, scale_sha256 = _hash_regular_file(scale_path)
    scale_payload = _read_regular(scale_path)
    if (
        scale_identity[2] != scale_contract["transformed_scale_bytes"]
        or scale_sha256 != scale_contract["transformed_scale_sha256"]
    ):
        raise ProjectionGateError("transformed scale identity mismatch")
    scales = np.frombuffer(scale_payload, dtype="<f4")
    if (
        scales.size != OUTPUT_FEATURES
        or not np.all(np.isfinite(scales))
        or not np.all(scales > 0)
    ):
        raise ProjectionGateError("transformed scale vector is invalid")
    if np.any(scales.view(np.uint32) & np.uint32(0xFFFF)):
        raise ProjectionGateError("transformed scales are not exact BF16-as-F32")

    temporary = _temporary_directory(output_dir)
    outputs_dir = temporary / "oracle_outputs"
    outputs_dir.mkdir(mode=0o700)
    candidate_bins = np.empty((3, OUTPUT_FEATURES), dtype=np.int16)
    packed = np.memmap(
        packed_weight_path,
        dtype=np.uint8,
        mode="r",
        shape=(OUTPUT_FEATURES, INPUT_FEATURES // 4),
    )
    saturation_counts = np.zeros(3, dtype=np.int64)
    started = time.monotonic()
    resource_snapshots = [
        enforce_phone_resource_envelope(
            output_root=temporary,
            started=started,
            checkpoint="before_first_row_block",
        )
    ]
    for start in range(0, OUTPUT_FEATURES, row_block_size):
        end = min(start + row_block_size, OUTPUT_FEATURES)
        weights = _unpack_weight_rows(np.asarray(packed[start:end]))
        dots = input_matrix @ weights.astype(np.int32, copy=False).T
        if dots.dtype != np.int32:
            raise ProjectionGateError("oracle dot did not use INT32 accumulation")
        scaled = (
            dots.astype(np.float64) * (INPUT_SCALE / OUTPUT_SCALE) * scales[start:end]
        )
        rounded = np.rint(scaled)
        saturation_counts += np.count_nonzero(
            (rounded < np.iinfo(np.int16).min) | (rounded > np.iinfo(np.int16).max),
            axis=1,
        )
        candidate_bins[:, start:end] = np.clip(
            rounded,
            np.iinfo(np.int16).min,
            np.iinfo(np.int16).max,
        ).astype(np.int16)
        if end < OUTPUT_FEATURES:
            resource_snapshots.append(
                enforce_phone_resource_envelope(
                    output_root=temporary,
                    started=started,
                    checkpoint=f"after_rows_{start}_{end}",
                )
            )
    del packed
    if _regular_file_identity(packed_weight_path) != packed_identity:
        raise ProjectionGateError(
            "packed INT2 tensor identity changed during oracle execution"
        )

    limits = _numeric_thresholds()
    case_records: list[dict[str, Any]] = []
    candidate_artifacts: list[tuple[Path, tuple[int, int, int, int, int]]] = []
    every_case_passed = True
    for index, record in enumerate(cases):
        output_payload = (
            candidate_bins[index].astype("<i2", copy=False).tobytes(order="C")
        )
        output_name = f"{LM_HEAD_GRAPH}.{record['case_id']}.exact_int32_oracle.s16.raw"
        output_path = outputs_dir / output_name
        _write_exclusive(output_path, output_payload)
        output_identity, output_sha256 = _hash_regular_file(output_path)
        candidate_artifacts.append((output_path, output_identity))
        candidate = (candidate_bins[index].astype(np.float64) * OUTPUT_SCALE).tolist()
        metrics = _oracle_metrics(references[index], candidate)
        passed, failures = adjudicate_metrics(metrics, limits)
        if int(saturation_counts[index]) != 0:
            passed = False
            failures.append(f"s16_saturation_count_{int(saturation_counts[index])}")
        every_case_passed = every_case_passed and passed
        case_records.append(
            {
                "case_id": record["case_id"],
                "input_sha256": record["s16_input_sha256"],
                "authority_output": reference_records[index],
                "candidate_output": {
                    "relative_path": f"oracle_outputs/{output_name}",
                    "bytes": len(output_payload),
                    "sha256": output_sha256,
                    "dtype": "int16",
                    "scale": OUTPUT_SCALE,
                    "shape": [1, 1, OUTPUT_FEATURES],
                },
                "exact_int32_dot": {
                    "input_features": INPUT_FEATURES,
                    "output_features": OUTPUT_FEATURES,
                    "multiply_accumulate_count": FULL_WIDTH_DOT_PRODUCTS_PER_CASE,
                    "accumulator_dtype": "int32",
                    "worst_case_abs_bound": integer_bound,
                    "int32_safe": True,
                },
                "s16_saturation_count": int(saturation_counts[index]),
                "metrics": metrics,
                "failures": failures,
                "passed": passed,
            }
        )

    for artifact_path, identity in (
        (packed_weight_path, packed_identity),
        *input_artifacts,
        *authority_artifacts,
        (scale_path, scale_identity),
        *candidate_artifacts,
    ):
        if _regular_file_identity(artifact_path) != identity:
            raise ProjectionGateError(
                f"phone-local oracle artifact identity changed: {artifact_path.name}"
            )

    status = "passed_scope" if every_case_passed else "falsified_scope"
    gate = {
        "schema_version": V2_ORACLE_SCHEMA,
        "status": status,
        "scope": "full_width_exact_INT32_dot_pre_provider_falsifier",
        "run_id": run_id,
        "candidate_id": V2_CANDIDATE_ID,
        "frontier_selector_sha256": FRONTIER_SELECTOR_SHA256,
        "parent_capsule_sha256": PARENT_CAPSULE_SHA256,
        "access_receipt_sha256": ACCESS_RECEIPT_SHA256,
        "resource_slice": RESOURCE_SLICE,
        "phone_execution_envelope": execution_envelope(),
        "source_revision": prereg["source_revision"],
        "implementation_module_sha256": prereg["implementation_module_sha256"],
        "preregistration_sha256": prereg_sha256,
        "threshold_policy_sha256": prereg["threshold_policy_sha256"],
        "numeric_and_ranking_threshold_subset_sha256": NUMERIC_THRESHOLD_SUBSET_SHA256,
        "packed_weight_sha256": PACKED_WEIGHT_SHA256,
        "transformed_scale_sha256": scale_contract["transformed_scale_sha256"],
        "scale_transform": "float32_to_bfloat16_RNE_then_exact_float32_storage",
        "input_scale": INPUT_SCALE,
        "output_scale": OUTPUT_SCALE,
        "oracle_execution_count": 3,
        "full_width_dot_products_total": FULL_WIDTH_DOT_PRODUCTS_PER_CASE * 3,
        "case_records": case_records,
        "every_case_passed": every_case_passed,
        "provider_build_allowed": every_case_passed,
        "qnn_execution_count": 0,
        "phone_qnn_execution_count": 0,
        "phone_native_exact_oracle_execution_count": 1,
        "wall_time_seconds": time.monotonic() - started,
        "python_version": ORACLE_PYTHON_VERSION,
        "python_executable_sha256": sha256_path(Path(sys.executable)),
        "numpy_version": ORACLE_NUMPY_VERSION,
        "runtime_binding": sanitized_runtime_binding(runtime_binding),
        "resource_snapshots": sanitized_resource_snapshots(resource_snapshots),
        "custody": {
            "raw_candidate_outputs": "phone_private",
            "raw_authority_outputs": "phone_private",
            "raw_output_egress": False,
            "sanitized_gate_egress_allowed": True,
            "qnn_phone_execution_is_distinct": True,
        },
        "failure_rule": "provider_build_forbidden_unless_status_passed_scope_and_every_case_passed",
        "claim_boundary": "exact_quantized_oracle_only_no_provider_or_phone_execution",
    }
    oracle_gate_sha256 = write_hashed_json(temporary / "oracle_gate.json", gate)
    _publish(temporary, output_dir)
    return {
        "status": status,
        "oracle_gate_sha256": oracle_gate_sha256,
        "every_case_passed": every_case_passed,
        "provider_build_allowed": every_case_passed,
    }


def validate_passed_int16_v2_oracle_local(
    *,
    prereg_dir: Path,
    oracle_gate_path: Path,
    authority_root: Path,
) -> tuple[dict[str, Any], str, dict[str, Any], str]:
    """Recompute phone-local metrics; this function is forbidden on RunPod."""

    prereg, prereg_sha256 = validate_int16_v2_preregistration(prereg_dir)
    gate = _strict_load_canonical(oracle_gate_path)
    gate_sha256 = sha256_path(oracle_gate_path)
    _verify_sidecar(oracle_gate_path, gate_sha256)
    exact_gate_keys = {
        "schema_version",
        "status",
        "scope",
        "run_id",
        "candidate_id",
        "frontier_selector_sha256",
        "parent_capsule_sha256",
        "access_receipt_sha256",
        "resource_slice",
        "phone_execution_envelope",
        "source_revision",
        "implementation_module_sha256",
        "preregistration_sha256",
        "threshold_policy_sha256",
        "numeric_and_ranking_threshold_subset_sha256",
        "packed_weight_sha256",
        "transformed_scale_sha256",
        "scale_transform",
        "input_scale",
        "output_scale",
        "oracle_execution_count",
        "full_width_dot_products_total",
        "case_records",
        "every_case_passed",
        "provider_build_allowed",
        "qnn_execution_count",
        "phone_qnn_execution_count",
        "phone_native_exact_oracle_execution_count",
        "wall_time_seconds",
        "python_version",
        "python_executable_sha256",
        "numpy_version",
        "runtime_binding",
        "resource_snapshots",
        "custody",
        "failure_rule",
        "claim_boundary",
    }
    if set(gate) != exact_gate_keys:
        raise ProjectionGateError("v2 oracle gate structure mismatch")
    required = {
        "schema_version": V2_ORACLE_SCHEMA,
        "status": "passed_scope",
        "scope": "full_width_exact_INT32_dot_pre_provider_falsifier",
        "candidate_id": V2_CANDIDATE_ID,
        "frontier_selector_sha256": FRONTIER_SELECTOR_SHA256,
        "parent_capsule_sha256": PARENT_CAPSULE_SHA256,
        "access_receipt_sha256": ACCESS_RECEIPT_SHA256,
        "resource_slice": RESOURCE_SLICE,
        "phone_execution_envelope": execution_envelope(),
        "source_revision": prereg["source_revision"],
        "implementation_module_sha256": prereg["implementation_module_sha256"],
        "preregistration_sha256": prereg_sha256,
        "threshold_policy_sha256": prereg["threshold_policy_sha256"],
        "numeric_and_ranking_threshold_subset_sha256": NUMERIC_THRESHOLD_SUBSET_SHA256,
        "packed_weight_sha256": PACKED_WEIGHT_SHA256,
        "transformed_scale_sha256": prereg["candidate_contract"][
            "transformed_scale_sha256"
        ],
        "scale_transform": "float32_to_bfloat16_RNE_then_exact_float32_storage",
        "input_scale": INPUT_SCALE,
        "output_scale": OUTPUT_SCALE,
        "oracle_execution_count": 3,
        "full_width_dot_products_total": FULL_WIDTH_DOT_PRODUCTS_PER_CASE * 3,
        "every_case_passed": True,
        "provider_build_allowed": True,
        "qnn_execution_count": 0,
        "phone_qnn_execution_count": 0,
        "phone_native_exact_oracle_execution_count": 1,
        "python_version": ORACLE_PYTHON_VERSION,
        "numpy_version": ORACLE_NUMPY_VERSION,
    }
    for name, expected in required.items():
        if gate.get(name) != expected:
            raise ProjectionGateError(
                f"v2 oracle does not authorize provider build: {name}"
            )
    validate_sanitized_run_id(gate.get("run_id"))
    validate_sanitized_runtime_binding(gate.get("runtime_binding"))
    if not SHA256.fullmatch(str(gate.get("python_executable_sha256", ""))):
        raise ProjectionGateError("v2 oracle Python executable digest is invalid")
    wall_time = gate.get("wall_time_seconds")
    if (
        not isinstance(wall_time, (int, float))
        or isinstance(wall_time, bool)
        or not math.isfinite(float(wall_time))
        or not 0 <= float(wall_time) < MAX_ORACLE_WALL_SECONDS
    ):
        raise ProjectionGateError("v2 oracle wall time is outside the frozen envelope")
    expected_custody = {
        "raw_candidate_outputs": "phone_private",
        "raw_authority_outputs": "phone_private",
        "raw_output_egress": False,
        "sanitized_gate_egress_allowed": True,
        "qnn_phone_execution_is_distinct": True,
    }
    if gate.get("custody") != expected_custody:
        raise ProjectionGateError("v2 oracle custody contract mismatch")
    if gate.get("failure_rule") != (
        "provider_build_forbidden_unless_status_passed_scope_and_every_case_passed"
    ):
        raise ProjectionGateError("v2 oracle failure rule mismatch")
    if (
        gate.get("claim_boundary")
        != "exact_quantized_oracle_only_no_provider_or_phone_execution"
    ):
        raise ProjectionGateError("v2 oracle claim boundary mismatch")
    validate_resource_snapshots(gate.get("resource_snapshots"))
    expected_cases = {record["case_id"]: record for record in prereg["cases"]}
    observed = gate.get("case_records")
    if not isinstance(observed, list) or len(observed) != 3:
        raise ProjectionGateError("v2 oracle case set mismatch")
    for record, frozen in zip(observed, FROZEN_CASES, strict=True):
        validate_sanitized_oracle_case(record, frozen)
    limits = _numeric_thresholds()
    for record in observed:
        if not isinstance(record, dict):
            raise ProjectionGateError("invalid v2 oracle case record")
        parent = expected_cases.pop(record.get("case_id"), None)
        if parent is None or record.get("input_sha256") != parent["s16_input_sha256"]:
            raise ProjectionGateError("v2 oracle input binding mismatch")
        authority = record.get("authority_output")
        parent_authority = parent["authority_output"]
        if not isinstance(authority, dict) or authority != {
            "relative_path": parent_authority["provider_relative_path"],
            "bytes": parent_authority["bytes"],
            "sha256": parent_authority["sha256"],
        }:
            raise ProjectionGateError("v2 oracle authority output binding mismatch")
        authority_path = authority_root / parent_authority["provider_relative_path"]
        authority_payload = _read_regular(authority_path)
        if (
            len(authority_payload) != parent_authority["bytes"]
            or sha256_bytes(authority_payload) != parent_authority["sha256"]
        ):
            raise ProjectionGateError("v2 phone-local authority output drift")
        exact = record.get("exact_int32_dot")
        if exact != {
            "input_features": INPUT_FEATURES,
            "output_features": OUTPUT_FEATURES,
            "multiply_accumulate_count": FULL_WIDTH_DOT_PRODUCTS_PER_CASE,
            "accumulator_dtype": "int32",
            "worst_case_abs_bound": exact.get("worst_case_abs_bound")
            if isinstance(exact, dict)
            else None,
            "int32_safe": True,
        }:
            raise ProjectionGateError("v2 oracle exact-dot proof mismatch")
        if (
            not isinstance(exact.get("worst_case_abs_bound"), int)
            or exact["worst_case_abs_bound"] < 0
        ):
            raise ProjectionGateError("v2 oracle INT32 bound is invalid")
        if exact["worst_case_abs_bound"] > 2_147_483_647:
            raise ProjectionGateError("v2 oracle INT32 bound exceeds INT32")
        metrics = record.get("metrics")
        if not isinstance(metrics, dict):
            raise ProjectionGateError("v2 oracle metrics are missing")
        numeric_metric_names = (
            "max_abs",
            "rms",
            "relative_l2",
            "cosine",
            "softmax_js_divergence",
            "top_k_set_overlap",
        )
        if any(
            not isinstance(metrics.get(name), (int, float))
            or isinstance(metrics.get(name), bool)
            or not math.isfinite(float(metrics[name]))
            for name in numeric_metric_names
        ):
            raise ProjectionGateError(
                "v2 oracle contains a non-finite or missing metric"
            )
        if not isinstance(metrics.get("top_1_equal"), bool):
            raise ProjectionGateError("v2 oracle top-1 metric is invalid")
        passed, failures = adjudicate_metrics(metrics, limits)
        if (
            not passed
            or failures
            or record.get("failures") != []
            or record.get("passed") is not True
        ):
            raise ProjectionGateError("v2 oracle recorded a failed unchanged metric")
        if record.get("s16_saturation_count") != 0:
            raise ProjectionGateError("v2 oracle saturated S16 output")
        output = record.get("candidate_output")
        if not isinstance(output, dict):
            raise ProjectionGateError("v2 oracle candidate output record is missing")
        relative = output.get("relative_path")
        if (
            not isinstance(relative, str)
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            raise ProjectionGateError("unsafe v2 oracle output path")
        payload = _read_regular(oracle_gate_path.parent / relative)
        if len(payload) != output.get("bytes") or sha256_bytes(payload) != output.get(
            "sha256"
        ):
            raise ProjectionGateError("v2 oracle candidate output drift")
        if (
            output.get("bytes") != OUTPUT_FEATURES * 2
            or output.get("dtype") != "int16"
            or output.get("shape") != [1, 1, OUTPUT_FEATURES]
            or output.get("scale") != OUTPUT_SCALE
        ):
            raise ProjectionGateError("v2 oracle output ABI mismatch")
        candidate_values = [
            value * OUTPUT_SCALE for (value,) in struct.iter_unpack("<h", payload)
        ]
        recomputed_metrics = _oracle_metrics(
            bf16_payload_to_floats(authority_payload),
            candidate_values,
        )
        if metrics != recomputed_metrics:
            raise ProjectionGateError(
                "v2 oracle metrics do not recompute from phone-local raw outputs"
            )
    if expected_cases:
        raise ProjectionGateError("v2 oracle omitted a frozen case")
    return prereg, prereg_sha256, gate, gate_sha256

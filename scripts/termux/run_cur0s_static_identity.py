#!/usr/bin/env python3
"""Execute the bounded phone-private CUR-0S static identity discriminator.

Raw rows and the row-level overlay remain in the output directory on the
phone.  Standard output and the retrievable receipt contain aggregates and
content hashes only.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import signal
import stat
import subprocess
import sys
import time
import types
from typing import Any


EXPECTED_BUILD_FINGERPRINT_SHA256 = (
    "sha256:fce358a6cdd6535afbecf6f72088412abaccf9b9902c05800ee8852512f9882f"
)
PREREG_SCHEMA = "cur0s_static_identity_preregistration_v1"
RECEIPT_SCHEMA = "cur0s_static_identity_receipt_v1"
COMPLETE_SCHEMA = "cur0s_static_identity_completion_v1"
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
SHA_RE = re.compile(r"(?:sha256:)?([0-9a-f]{64})\Z")
RUN_ID_RE = re.compile(r"[0-9]{8}T[0-9]{6}Z_cur0s_static_identity_v1\Z")
PHONE_HOME = Path("/data/data/com.termux/files/home")
PHONE_RUN_ROOT_RELATIVE = "polymath_gemma4_e4b_frontier"
PHONE_RUN_ROOT = PHONE_HOME / PHONE_RUN_ROOT_RELATIVE
PHONE_SOURCE_ROOT_RELATIVE = (
    "polymath_mac_offload/20260709T_disk_emergency/Polymat_AI/runtime/tmp/"
    "c1_c4_integrated_20260630T164809Z/hf_packages/packages"
)
PHONE_SOURCE_ROOT = PHONE_HOME / PHONE_SOURCE_ROOT_RELATIVE
PHONE_SOURCE_LOCATOR = "phone-private://cur0s/current-physical-504dd91c/packages"
BOUND_SOURCE_FILES = (
    "polymath_ai/corpus/cur0s_exact.py",
    "polymath_ai/corpus/cur0s_static.py",
    "scripts/termux/run_cur0s_static_identity.py",
)
ROOT = Path(os.path.abspath(__file__)).parents[2]


class BootstrapError(RuntimeError):
    """The stdlib-only pre-import authority boundary rejected execution."""


# The exact objects are assigned only after attested source bytes are loaded.
# Explicit placeholders keep the stdlib-only bootstrap import boundary visible
# to static analysis without importing repository modules early.
AntiPercolationPolicy: Any = None
Cur0sExactError: Any = BootstrapError
build_exact_identity: Any = None
canonical_json_bytes: Any = None
canonical_sha256: Any = None
strict_json_loads: Any = None
SOURCE_REPOSITORY: Any = None
SOURCE_REVISION: Any = None
STAGE_LOCKS: Any = None
TOTAL_ROWS: Any = None
first_missing_green_field: Any = None
physical_lock_contract: Any = None
static_gate_matrix: Any = None


def preimport_phone_guard() -> None:
    """Reject the wrong runtime before executing any repository module."""

    if platform.system() != "Linux" or platform.machine() != "aarch64":
        raise RuntimeError("runner_requires_android_aarch64")
    expected_home = "/data/data/com.termux/files/home"
    if os.environ.get("HOME") != expected_home or str(Path.home()) != expected_home:
        raise RuntimeError("runner_requires_exact_termux_private_home")
    environment = {
        "ANDROID_ROOT": "/system",
        "HOME": expected_home,
        "PATH": "/system/bin:/data/data/com.termux/files/usr/bin",
    }
    observed = {}
    for key, prop in {
        "model": "ro.product.model",
        "device": "ro.product.device",
        "soc": "ro.soc.model",
    }.items():
        observed[key] = subprocess.run(
            ["/system/bin/getprop", prop],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
            env=environment,
        ).stdout.strip()
    if observed != {"model": "NX789J", "device": "NX789J", "soc": "SM8750"}:
        raise RuntimeError("live_phone_identity_mismatch")
    fingerprint = subprocess.run(
        ["/system/bin/getprop", "ro.build.fingerprint"],
        check=True,
        capture_output=True,
        timeout=5,
        env=environment,
    ).stdout
    fingerprint_sha256 = "sha256:" + hashlib.sha256(fingerprint).hexdigest()
    if fingerprint_sha256 != EXPECTED_BUILD_FINGERPRINT_SHA256:
        raise RuntimeError("live_phone_build_fingerprint_mismatch")


def load_bound_module(module_name: str, relative_path: str, source_bytes: bytes):
    """Execute exactly the bytes attested by the pre-import boundary."""

    module = types.ModuleType(module_name)
    module.__file__ = str(ROOT / relative_path)
    module.__package__ = ""
    sys.modules[module_name] = module
    code = compile(source_bytes, module.__file__, "exec", dont_inherit=True)
    exec(code, module.__dict__)
    return module


def bind_bound_modules(source_bytes: dict[str, bytes] | None = None) -> None:
    """Bind the two repository modules after their exact bytes are known."""

    if source_bytes is None:
        source_bytes = {
            relative_path: (ROOT / relative_path).read_bytes()
            for relative_path in BOUND_SOURCE_FILES[:2]
        }
    exact = load_bound_module(
        "_cur0s_exact_bound", BOUND_SOURCE_FILES[0], source_bytes[BOUND_SOURCE_FILES[0]]
    )
    static = load_bound_module(
        "_cur0s_static_bound", BOUND_SOURCE_FILES[1], source_bytes[BOUND_SOURCE_FILES[1]]
    )
    globals().update(
        {
            "AntiPercolationPolicy": exact.AntiPercolationPolicy,
            "Cur0sExactError": exact.Cur0sExactError,
            "build_exact_identity": exact.build_exact_identity,
            "canonical_json_bytes": exact.canonical_json_bytes,
            "canonical_sha256": exact.canonical_sha256,
            "strict_json_loads": exact.strict_json_loads,
            "SOURCE_REPOSITORY": static.SOURCE_REPOSITORY,
            "SOURCE_REVISION": static.SOURCE_REVISION,
            "STAGE_LOCKS": static.STAGE_LOCKS,
            "TOTAL_ROWS": static.TOTAL_ROWS,
            "first_missing_green_field": static.first_missing_green_field,
            "physical_lock_contract": static.physical_lock_contract,
            "static_gate_matrix": static.static_gate_matrix,
        }
    )


if __name__ != "__main__":
    bind_bound_modules()


_PREIMPORT_SOURCE_ATTESTATION: dict[str, Any] | None = None


def bootstrap_authority(
    args: argparse.Namespace,
) -> tuple[bytes, dict[str, Any], dict[str, bytes], dict[str, Any]]:
    """Validate preregistration and source bytes before repository code executes."""

    prereg_bytes = bootstrap_read_private_preregistration(args.preregistration)
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
    claimed_root = prereg.get("preregistration_root_sha256")
    if not isinstance(claimed_root, str) or SHA_RE.fullmatch(claimed_root) is None:
        raise BootstrapError("preregistration_root_invalid")
    without_root = dict(prereg)
    without_root.pop("preregistration_root_sha256")
    if bootstrap_canonical_sha256(without_root) != normalize_bootstrap_sha(claimed_root):
        raise BootstrapError("preregistration_root_mismatch")

    bindings = prereg.get("source_file_bindings")
    if not isinstance(bindings, dict) or set(bindings) != set(BOUND_SOURCE_FILES):
        raise BootstrapError("source_file_bindings_missing")
    source_commit = prereg.get("source_commit")
    if not isinstance(source_commit, str) or COMMIT_RE.fullmatch(source_commit) is None:
        raise BootstrapError("source_commit_invalid")

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

    expected_hashes = {
        "cur0s_exact_sha256": observed_bindings[BOUND_SOURCE_FILES[0]]["sha256"],
        "cur0s_static_sha256": observed_bindings[BOUND_SOURCE_FILES[1]]["sha256"],
        "runner_sha256": observed_bindings[BOUND_SOURCE_FILES[2]]["sha256"],
    }
    if prereg.get("source_file_sha256") != expected_hashes:
        raise BootstrapError("source_file_hash_binding_mismatch")
    if bootstrap_git_output("rev-parse", "HEAD") != source_commit:
        raise BootstrapError("source_checkout_commit_mismatch")
    for relative_path in BOUND_SOURCE_FILES:
        if bootstrap_git_output("rev-parse", f"HEAD:{relative_path}") != (
            observed_bindings[relative_path]["git_blob_oid"]
        ):
            raise BootstrapError("source_checkout_bound_file_dirty")

    attestation = {
        "source_commit": source_commit,
        "source_file_sha256": expected_hashes,
        "source_file_bindings": observed_bindings,
        "git_HEAD_verified": True,
        "bound_source_files_clean": True,
        "preimport_exact_bytes_executed": True,
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
        info = os.fstat(fd)
        if info.st_nlink != 1:
            raise BootstrapError("preregistration_hardlink_forbidden")
        if info.st_size > 1024 * 1024:
            raise BootstrapError("preregistration_too_large")
        return bootstrap_read_stable_fd(fd, info, 1024 * 1024)
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
    path = Path(relative_path)
    components = path.parts
    if path.is_absolute() or not components or any(
        component in {"", ".", ".."} for component in components
    ):
        raise BootstrapError("invalid_bootstrap_relative_path")
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
    path = Path(relative_path)
    components = path.parts
    if path.is_absolute() or not components or any(
        component in {"", ".", ".."} for component in components
    ):
        raise BootstrapError("invalid_bootstrap_directory_path")
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
                current_fd, owner_only=False, role="source_checkout_directory"
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
        info = os.fstat(fd)
        if info.st_nlink != 1:
            raise BootstrapError("bound_source_hardlink_forbidden")
        if info.st_size > 16 * 1024 * 1024:
            raise BootstrapError("bound_source_too_large")
        return bootstrap_read_stable_fd(fd, info, 16 * 1024 * 1024)
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
    if bootstrap_stat_identity(initial) != bootstrap_stat_identity(final):
        raise BootstrapError("bootstrap_artifact_changed_during_read")
    return bytes(result)


def bootstrap_stat_identity(
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


def bootstrap_git_blob_oid(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def bootstrap_git_output(*args: str) -> str:
    return subprocess.run(
        ["/data/data/com.termux/files/usr/bin/git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
        env={
            "HOME": str(PHONE_HOME),
            "PATH": "/data/data/com.termux/files/usr/bin:/system/bin",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        },
    ).stdout.strip()


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


def normalize_bootstrap_sha(value: str) -> str:
    match = SHA_RE.fullmatch(value)
    if match is None:
        raise BootstrapError("invalid_sha256")
    return "sha256:" + match.group(1)


class OperationalStop(RuntimeError):
    """A preregistered runtime safety boundary stopped the candidate."""

    def __init__(self, code: str, checkpoint: str) -> None:
        super().__init__(code)
        self.code = code
        self.checkpoint = checkpoint


@dataclass(frozen=True)
class CampaignLease:
    lease_id: str
    action_id: str
    issued_at: datetime
    expires_at: datetime
    max_wall_seconds: int
    max_private_output_bytes: int
    min_free_storage_bytes: int
    max_temperature_millidegrees_c: int
    thermal_sample_every_records: int


class ResourceEnvelope:
    """Enforce the finite phone action envelope and retain aggregate telemetry."""

    def __init__(
        self,
        lease: CampaignLease,
        output_directory_fd: int,
        started_monotonic: float,
        *,
        now_fn=None,
        monotonic_fn=None,
        thermal_reader=None,
        statvfs_fn=None,
    ) -> None:
        self.lease = lease
        self._output_directory_fd = output_directory_fd
        self._started_monotonic = started_monotonic
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._monotonic_fn = monotonic_fn or time.monotonic
        self._thermal_reader = thermal_reader or read_thermal_zones
        self._statvfs_fn = statvfs_fn or os.fstatvfs
        self._checkpoint = "not_started"
        self._previous_handler: Any = None
        self._armed = False
        self._maximum_elapsed_seconds = 0.0
        self._minimum_free_storage_bytes: int | None = None
        self._maximum_temperature_millidegrees_c: int | None = None
        self._thermal_sample_count = 0
        self._maximum_readable_thermal_sensor_count = 0

    def arm(self) -> None:
        if self._armed:
            raise Cur0sExactError("resource_envelope_already_armed")
        remaining_wall = self.lease.max_wall_seconds - self.elapsed_seconds()
        remaining_lease = (self.lease.expires_at - self._now_fn()).total_seconds()
        duration = min(remaining_wall, remaining_lease)
        if duration <= 0:
            raise OperationalStop("lease_or_wall_deadline_reached", self._checkpoint)
        self._previous_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, self._handle_alarm)
        signal.setitimer(signal.ITIMER_REAL, max(0.001, duration))
        self._armed = True

    def disarm(self) -> None:
        if not self._armed:
            return
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, self._previous_handler)
        self._armed = False

    def check(self, checkpoint: str, *, sample_thermal: bool = True) -> None:
        self._checkpoint = sanitize_checkpoint(checkpoint)
        elapsed = self.elapsed_seconds()
        self._maximum_elapsed_seconds = max(self._maximum_elapsed_seconds, elapsed)
        if elapsed >= self.lease.max_wall_seconds:
            raise OperationalStop("wall_time_limit_reached", self._checkpoint)
        if self._now_fn() >= self.lease.expires_at:
            raise OperationalStop("campaign_lease_expired_mid_execution", self._checkpoint)

        filesystem = self._statvfs_fn(self._output_directory_fd)
        free_bytes = filesystem.f_bavail * filesystem.f_frsize
        if self._minimum_free_storage_bytes is None:
            self._minimum_free_storage_bytes = free_bytes
        else:
            self._minimum_free_storage_bytes = min(
                self._minimum_free_storage_bytes, free_bytes
            )
        if free_bytes < self.lease.min_free_storage_bytes:
            raise OperationalStop("free_storage_floor_crossed", self._checkpoint)

        if not sample_thermal:
            return
        try:
            temperatures = self._thermal_reader()
        except OperationalStop as stop:
            raise OperationalStop(stop.code, self._checkpoint) from None
        if not temperatures:
            raise OperationalStop("thermal_sensor_unavailable", self._checkpoint)
        maximum = max(temperatures)
        self._thermal_sample_count += 1
        self._maximum_readable_thermal_sensor_count = max(
            self._maximum_readable_thermal_sensor_count, len(temperatures)
        )
        if self._maximum_temperature_millidegrees_c is None:
            self._maximum_temperature_millidegrees_c = maximum
        else:
            self._maximum_temperature_millidegrees_c = max(
                self._maximum_temperature_millidegrees_c, maximum
            )
        if maximum >= self.lease.max_temperature_millidegrees_c:
            raise OperationalStop("thermal_ceiling_reached", self._checkpoint)

    def elapsed_seconds(self) -> float:
        return max(0.0, self._monotonic_fn() - self._started_monotonic)

    def receipt_metrics(self, *, private_output_bytes: int) -> dict[str, Any]:
        elapsed = self.elapsed_seconds()
        self._maximum_elapsed_seconds = max(self._maximum_elapsed_seconds, elapsed)
        return {
            "action_id": self.lease.action_id,
            "phone_execution_ordinal": 1,
            "max_wall_seconds": self.lease.max_wall_seconds,
            "maximum_observed_elapsed_seconds": self._maximum_elapsed_seconds,
            "min_free_storage_bytes": self.lease.min_free_storage_bytes,
            "minimum_observed_free_storage_bytes": self._minimum_free_storage_bytes,
            "max_temperature_millidegrees_c": (
                self.lease.max_temperature_millidegrees_c
            ),
            "maximum_observed_temperature_millidegrees_c": (
                self._maximum_temperature_millidegrees_c
            ),
            "thermal_sample_count": self._thermal_sample_count,
            "maximum_readable_thermal_sensor_count": (
                self._maximum_readable_thermal_sensor_count
            ),
            "thermal_sample_every_records": (
                self.lease.thermal_sample_every_records
            ),
            "max_private_output_bytes": self.lease.max_private_output_bytes,
            "private_output_bytes_before_receipt": private_output_bytes,
            "lease_expires_at_utc": iso_utc(self.lease.expires_at),
        }

    def _handle_alarm(self, _signum: int, _frame: Any) -> None:
        raise OperationalStop("wall_or_lease_alarm_reached", self._checkpoint)


def read_thermal_zones() -> list[int]:
    """Return all readable sysfs thermal values without exposing sensor names."""

    temperatures: list[int] = []
    thermal_root = Path("/sys/class/thermal")
    try:
        with os.scandir(thermal_root) as iterator:
            entries = sorted(
                [
                    entry
                    for entry in iterator
                    if re.fullmatch(r"thermal_zone[0-9]+", entry.name)
                ],
                key=lambda entry: entry.name,
            )
    except OSError:
        return temperatures
    for entry in entries:
        try:
            fd = os.open(
                Path(entry.path) / "temp",
                os.O_RDONLY | os.O_CLOEXEC,
            )
        except OSError:
            continue
        try:
            payload = os.read(fd, 64)
            if os.read(fd, 1):
                raise OperationalStop("thermal_sensor_value_oversize", "thermal_sample")
        finally:
            os.close(fd)
        try:
            text = payload.decode("ascii").strip()
        except UnicodeDecodeError:
            raise OperationalStop("thermal_sensor_value_malformed", "thermal_sample") from None
        if re.fullmatch(r"-?[0-9]+", text) is None:
            raise OperationalStop("thermal_sensor_value_malformed", "thermal_sample")
        value = int(text)
        if not -100_000 <= value <= 250_000:
            raise OperationalStop("thermal_sensor_value_out_of_range", "thermal_sample")
        temperatures.append(value)
    return temperatures


def sanitize_checkpoint(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}", value) is None:
        return "sanitized_runtime_checkpoint"
    return value


def main(
    *,
    args: argparse.Namespace | None = None,
    prereg_bytes: bytes | None = None,
    prereg: dict[str, Any] | None = None,
) -> int:
    args = args or parse_args()
    started_monotonic = time.monotonic()
    started_at = utc_now()

    observed_runtime = guard_phone_environment()
    if prereg_bytes is None:
        prereg_path = validate_private_existing_path(
            Path(args.preregistration), "preregistration"
        )
        prereg_bytes = read_private_file(prereg_path)
    if prereg is None:
        prereg = strict_json_loads(prereg_bytes)
    if not isinstance(prereg, dict):
        raise Cur0sExactError("preregistration_must_be_object")
    source_identity = validate_preregistration(prereg)
    runtime_identity = validate_phone_runtime(prereg, observed_runtime)
    lease = validate_transaction_authority(prereg)

    package_root = validate_package_root(Path(args.package_root))
    output_dir = validate_private_output_path(
        Path(args.output_dir), prereg["run_id"], prereg["output_directory_name"]
    )
    output = PrivateOutput.create(
        output_dir,
        prereg["run_id"],
        max_bytes=lease.max_private_output_bytes,
    )
    envelope = ResourceEnvelope(
        lease,
        output.directory_fd,
        started_monotonic,
    )

    snapshot: SourceSnapshot | None = None
    physical: dict[str, Any] = {
        "state": "not_executed",
        "passed": False,
        "total_master_rows": 0,
        "artifact_count": 0,
        "artifacts": [],
    }
    identity_progress: dict[str, Any] = {
        "state": "not_executed",
        "private_overlay_written": False,
    }
    try:
        envelope.arm()
        envelope.check("before_source_snapshot")
        snapshot = SourceSnapshot.open(package_root)
        physical = snapshot.verify(envelope)
        if not physical["passed"]:
            receipt = build_early_receipt(
                prereg=prereg,
                prereg_bytes=prereg_bytes,
                source_identity=source_identity,
                runtime_identity=runtime_identity,
                physical=physical,
                state="invalidated",
                blocker="physical_source_lock_mismatch",
                started_at=started_at,
                started_monotonic=started_monotonic,
            )
            finish_receipt(output, envelope, prereg["run_id"], receipt)
            print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
            return 2
        policy = AntiPercolationPolicy(**prereg["anti_percolation_policy"])
        identity_progress = {
            "state": "in_progress",
            "private_overlay_written": False,
        }
        try:
            exact = build_exact_identity(
                iter_master_records(snapshot, envelope),
                source_repository=SOURCE_REPOSITORY,
                source_revision=SOURCE_REVISION,
                policy=policy,
            )
            identity_progress = {
                "state": "identity_built_overlay_not_written",
                "private_overlay_written": False,
            }
        except Cur0sExactError as error:
            if snapshot.verify(envelope) != physical:
                raise Cur0sExactError("physical_source_changed_during_failed_identity") from error
            receipt = build_early_receipt(
                prereg=prereg,
                prereg_bytes=prereg_bytes,
                source_identity=source_identity,
                runtime_identity=runtime_identity,
                physical=physical,
                state="blocked_fail_closed",
                blocker=sanitize_blocker(error),
                started_at=started_at,
                started_monotonic=started_monotonic,
            )
            finish_receipt(output, envelope, prereg["run_id"], receipt)
            print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
            return 2
        envelope.check("after_exact_identity")
        physical_revalidation = snapshot.verify(envelope)
        if not physical["passed"] or physical_revalidation != physical:
            raise Cur0sExactError("physical_source_not_stable_and_exact")
        physical["stable_revalidation_passed"] = True
        overlay_sha256, overlay_bytes = output.write_overlay(
            "exact_identity_overlay.private.jsonl", exact.rows, envelope
        )
        identity_progress = {
            "state": "overlay_written",
            "private_overlay_written": True,
            "private_overlay_bytes": overlay_bytes,
        }

        expected_stage_counts = {lock.stage: lock.rows for lock in STAGE_LOCKS}
        result_contract_pass = (
            exact.report["record_count"] == TOTAL_ROWS
            and exact.report["stage_counts"] == expected_stage_counts
        )
        exact_pass = (
            exact.report["anti_percolation"]["status"] == "passed_scope"
            and result_contract_pass
        )
        gates = static_gate_matrix(physical_pass=physical["passed"], exact_identity_pass=exact_pass)
        finished_at = utc_now()
        receipt = {
            "schema_version": RECEIPT_SCHEMA,
            "candidate_id": prereg["candidate_id"],
            "run_id": prereg["run_id"],
            "state": "blocked_fail_closed",
            "candidate_output_observed": True,
            "cur0s_static_pass_claimed": False,
            "cur0s_pass_claimed": False,
            "composite_cur0_pass_claimed": False,
            "source_identity": {
                "repository": SOURCE_REPOSITORY,
                "revision": SOURCE_REVISION,
                "role": "physically_valid_evidence_only",
                "physical_lock_contract_sha256": physical_lock_contract()["contract_sha256"],
            },
            "source_execution_identity": source_identity,
            "runtime_identity": runtime_identity,
            "authority_bindings": sanitized_authority_bindings(prereg, prereg_bytes),
            "physical_verification": physical,
            "exact_identity": {
                "state": "passed_scope" if exact_pass else "falsified_scope",
                "overlay_root_sha256": exact.overlay_root_sha256,
                "private_overlay_file_sha256": overlay_sha256,
                "private_overlay_bytes": overlay_bytes,
                "private_overlay_egressed": False,
                "expected_record_count": TOTAL_ROWS,
                "expected_stage_counts": expected_stage_counts,
                "result_contract_passed": result_contract_pass,
                "report": exact.report,
            },
            "current_legacy_split_disposition": {
                "state": "invalidated_non_authoritative_audit_only",
                "conflicting_exact_component_count": exact.report[
                    "legacy_split_conflict_component_count"
                ],
                "historically_exposed_component_count": exact.report[
                    "historically_exposed_component_count"
                ],
                "successor_split_assigned": False,
            },
            "static_gate_matrix": gates,
            "first_missing_green_field": first_missing_green_field(gates),
            "mandatory_next_disposition": "continue_commercial_source_tournament_and_build_successor_static_root",
            "claim_ceiling": "exact_identity_and_current_physical_custody_only",
            "nonclaims": [
                "not_integrated_successor_CUR_0S_static_attempt",
                "not_near_semantic_Arm_C",
                "not_successor_connected_split",
                "not_rights_quality_or_semantic_admission",
                "not_C1_C2_closure_C3_dictionary_or_C4_syllabus",
                "not_CUR_0S_or_CUR_0P_or_composite_CUR_0",
                "not_target_data_learning_or_authority",
                "not_Section_0_5_success",
            ],
            "custody": {
                "this_runner_raw_egress": False,
                "this_runner_row_overlay_egress": False,
                "external_ADB_custody_attestation_required": True,
            },
            "pending_transaction_links": [
                "post_run_evidence_commit",
                "origin_push_readback",
                "capsule_CAS_transition",
            ],
            "execution": {
                "started_at_utc": started_at,
                "finished_at_utc": finished_at,
                "elapsed_seconds": time.monotonic() - started_monotonic,
                "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "python": sys.version.split()[0],
            },
        }
        finish_receipt(output, envelope, prereg["run_id"], receipt)
        print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        return 0 if exact_pass else 2
    except OperationalStop as stop:
        envelope.disarm()
        receipt = build_operational_stop_receipt(
            prereg=prereg,
            prereg_bytes=prereg_bytes,
            source_identity=source_identity,
            runtime_identity=runtime_identity,
            physical=physical,
            identity_progress=identity_progress,
            stop=stop,
            envelope=envelope,
            output=output,
            started_at=started_at,
            started_monotonic=started_monotonic,
        )
        finalize_output(output, prereg["run_id"], receipt)
        print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        return 3
    except Exception:
        # A partial directory is deliberately not completion-valid.
        raise
    finally:
        envelope.disarm()
        if snapshot is not None:
            snapshot.close()
        output.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--preregistration", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def sanitize_blocker(error: Exception) -> str:
    value = str(error)
    if not value or len(value) > 160 or re.fullmatch(r"[A-Za-z0-9_.:-]+", value) is None:
        return "sanitized_CUR0S_identity_error"
    return value


def finish_receipt(
    output: "PrivateOutput",
    envelope: ResourceEnvelope,
    run_id: str,
    receipt: dict[str, Any],
) -> None:
    """Recheck authority, freeze aggregate telemetry, and commit completion."""

    envelope.check("before_final_evidence_commit")
    receipt.pop("receipt_root_sha256", None)
    receipt["execution_claim"] = output.execution_claim_receipt()
    receipt["resource_envelope"] = envelope.receipt_metrics(
        private_output_bytes=output.bytes_written
    )
    receipt["receipt_root_sha256"] = canonical_sha256(receipt)
    envelope.disarm()
    finalize_output(output, run_id, receipt)


def build_operational_stop_receipt(
    *,
    prereg: dict[str, Any],
    prereg_bytes: bytes,
    source_identity: dict[str, Any],
    runtime_identity: dict[str, Any],
    physical: dict[str, Any],
    identity_progress: dict[str, Any],
    stop: OperationalStop,
    envelope: ResourceEnvelope,
    output: "PrivateOutput",
    started_at: str,
    started_monotonic: float,
) -> dict[str, Any]:
    gates = static_gate_matrix(
        physical_pass=physical.get("passed") is True,
        exact_identity_pass=False,
    )
    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "candidate_id": prereg["candidate_id"],
        "run_id": prereg["run_id"],
        "state": "stopped_fail_closed",
        "candidate_output_observed": True,
        "operational_stop": {
            "code": stop.code,
            "checkpoint": sanitize_checkpoint(stop.checkpoint),
            "expected_typed_stop": True,
        },
        "cur0s_static_pass_claimed": False,
        "cur0s_pass_claimed": False,
        "composite_cur0_pass_claimed": False,
        "target_data_learning_claimed": False,
        "authority_improvement_claimed": False,
        "source_execution_identity": source_identity,
        "runtime_identity": runtime_identity,
        "authority_bindings": sanitized_authority_bindings(prereg, prereg_bytes),
        "physical_verification": physical,
        "exact_identity": identity_progress,
        "static_gate_matrix": gates,
        "first_missing_green_field": first_missing_green_field(gates),
        "claim_ceiling": "operational_stop_evidence_only",
        "custody": {
            "this_runner_raw_egress": False,
            "this_runner_row_overlay_egress": False,
            "partial_private_output_egressed": False,
            "external_ADB_custody_attestation_required": True,
        },
        "private_output": output.partial_output_report(),
        "execution_claim": output.execution_claim_receipt(),
        "resource_envelope": envelope.receipt_metrics(
            private_output_bytes=output.bytes_written
        ),
        "execution": {
            "started_at_utc": started_at,
            "finished_at_utc": utc_now(),
            "elapsed_seconds": time.monotonic() - started_monotonic,
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "python": sys.version.split()[0],
        },
        "pending_transaction_links": [
            "post_run_evidence_commit",
            "origin_push_readback",
            "capsule_CAS_transition",
        ],
        "nonclaims": [
            "not_exact_identity_pass",
            "not_CUR_0S_or_CUR_0P_or_composite_CUR_0",
            "not_target_data_learning_or_authority",
            "not_Section_0_5_success",
        ],
    }
    receipt["receipt_root_sha256"] = canonical_sha256(receipt)
    return receipt


def build_early_receipt(
    *,
    prereg: dict[str, Any],
    prereg_bytes: bytes,
    source_identity: dict[str, Any],
    runtime_identity: dict[str, Any],
    physical: dict[str, Any],
    state: str,
    blocker: str,
    started_at: str,
    started_monotonic: float,
) -> dict[str, Any]:
    gates = static_gate_matrix(physical_pass=physical["passed"], exact_identity_pass=False)
    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "candidate_id": prereg["candidate_id"],
        "run_id": prereg["run_id"],
        "state": state,
        "candidate_output_observed": True,
        "cur0s_static_pass_claimed": False,
        "cur0s_pass_claimed": False,
        "composite_cur0_pass_claimed": False,
        "source_execution_identity": source_identity,
        "runtime_identity": runtime_identity,
        "authority_bindings": sanitized_authority_bindings(prereg, prereg_bytes),
        "physical_verification": physical,
        "exact_identity": {
            "state": "not_executed",
            "blocker": blocker,
            "private_overlay_written": False,
        },
        "static_gate_matrix": gates,
        "first_missing_green_field": first_missing_green_field(gates),
        "claim_ceiling": "physical_custody_only",
        "custody": {
            "this_runner_raw_egress": False,
            "this_runner_row_overlay_egress": False,
            "external_ADB_custody_attestation_required": True,
        },
        "execution": {
            "started_at_utc": started_at,
            "finished_at_utc": utc_now(),
            "elapsed_seconds": time.monotonic() - started_monotonic,
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "python": sys.version.split()[0],
        },
        "pending_transaction_links": [
            "post_run_evidence_commit",
            "origin_push_readback",
            "capsule_CAS_transition",
        ],
        "nonclaims": [
            "not_exact_identity_pass",
            "not_CUR_0S_or_CUR_0P_or_composite_CUR_0",
            "not_target_data_learning_or_authority",
        ],
    }
    receipt["receipt_root_sha256"] = canonical_sha256(receipt)
    return receipt


def sanitized_authority_bindings(
    prereg: dict[str, Any], prereg_bytes: bytes
) -> dict[str, Any]:
    return {
        "parent_capsule_sha256": prereg["parent_capsule_sha256"],
        "parent_frontier_root_sha256": prereg["parent_frontier_root_sha256"],
        "maximal_selector_sha256": prereg["maximal_selector_sha256"],
        "campaign_lease_root_sha256": canonical_sha256(prereg["campaign_lease"]),
        "resource_slice_root_sha256": canonical_sha256(prereg["resource_slice"]),
        "preregistration_sha256": "sha256:" + hashlib.sha256(prereg_bytes).hexdigest(),
        "preregistration_root_sha256": prereg["preregistration_root_sha256"],
        "ACCESS_receipt_sha256": prereg["ACCESS_receipt_sha256"],
    }


def finalize_output(output: "PrivateOutput", run_id: str, receipt: dict[str, Any]) -> None:
    receipt_sha256, receipt_bytes = output.write_receipt("receipt.json", receipt)
    complete = {
        "schema_version": COMPLETE_SCHEMA,
        "run_id": run_id,
        "state": receipt["state"],
        "receipt_sha256": receipt_sha256,
        "receipt_root_sha256": receipt["receipt_root_sha256"],
        "receipt_bytes": receipt_bytes,
        "completed_at_utc": utc_now(),
        "completion_protocol": (
            "payload_files_fsync_read_only_then_COMPLETE_O_EXCL_fsync_last"
        ),
        "output_directory_mode": "owner_only_0700",
    }
    output.seal_payload_before_completion()
    output.write_completion_last("COMPLETE.json", complete)


def validate_preregistration(prereg: dict[str, Any]) -> dict[str, Any]:
    if prereg.get("schema_version") != PREREG_SCHEMA:
        raise Cur0sExactError("preregistration_schema_mismatch")
    expected_state = {
        "candidate_id": "cur0s_current_physical_exact_identity_v1",
        "parent_experiment_id": "EXP-CUR0S-SOVEREIGN-COMPOSITE-V1",
        "candidate_output_observed": False,
        "phone_execution_started": False,
        "promotion_allowed": False,
        "source_role": "physically_valid_evidence_only",
        "claim_ceiling": "subordinate_identity_evidence_not_CUR_0S",
    }
    if any(prereg.get(key) != value for key, value in expected_state.items()):
        raise Cur0sExactError("preregistration_candidate_state_mismatch")
    if prereg.get("source_repository") != SOURCE_REPOSITORY:
        raise Cur0sExactError("preregistered_source_repository_mismatch")
    if prereg.get("source_revision") != SOURCE_REVISION:
        raise Cur0sExactError("preregistered_source_revision_mismatch")
    if prereg.get("physical_lock_contract_sha256") != physical_lock_contract()["contract_sha256"]:
        raise Cur0sExactError("physical_lock_contract_mismatch")
    source_commit = prereg.get("source_commit")
    if not isinstance(source_commit, str) or COMMIT_RE.fullmatch(source_commit) is None:
        raise Cur0sExactError("source_commit_invalid")
    for field in (
        "parent_capsule_sha256",
        "parent_frontier_root_sha256",
        "maximal_selector_sha256",
    ):
        require_sha256(prereg.get(field), field)
    if prereg.get("ACCESS_receipt_sha256") != (
        "sha256:7b2b6d506b3ab82a17008edc4c79dd51512f6f9598e3db37cd1bb6f5ee4331ca"
    ):
        raise Cur0sExactError("ACCESS_receipt_binding_mismatch")
    if prereg.get("maximal_selector_sha256") != prereg.get(
        "parent_frontier_root_sha256"
    ):
        raise Cur0sExactError("maximal_selector_binding_mismatch")
    if prereg.get("raw_source_locator") != PHONE_SOURCE_LOCATOR:
        raise Cur0sExactError("raw_source_locator_mismatch")
    validate_transaction_authority(prereg)

    if _PREIMPORT_SOURCE_ATTESTATION is None:
        expected = {
            "cur0s_exact_sha256": file_sha256(ROOT / BOUND_SOURCE_FILES[0]),
            "cur0s_static_sha256": file_sha256(ROOT / BOUND_SOURCE_FILES[1]),
            "runner_sha256": file_sha256(ROOT / BOUND_SOURCE_FILES[2]),
        }
        observed_bindings = {
            relative_path: {
                "bytes": (ROOT / relative_path).stat().st_size,
                "sha256": file_sha256(ROOT / relative_path),
                "git_blob_oid": git_output("rev-parse", f"HEAD:{relative_path}"),
            }
            for relative_path in BOUND_SOURCE_FILES
        }
        git_head = git_output("rev-parse", "HEAD")
        dirty = git_output(
            "status",
            "--porcelain",
            "--untracked-files=no",
            "--",
            *BOUND_SOURCE_FILES,
        )
        preimport_verified = False
    else:
        expected = _PREIMPORT_SOURCE_ATTESTATION["source_file_sha256"]
        observed_bindings = _PREIMPORT_SOURCE_ATTESTATION["source_file_bindings"]
        git_head = _PREIMPORT_SOURCE_ATTESTATION["source_commit"]
        dirty = ""
        preimport_verified = True
    if prereg.get("source_file_sha256") != expected:
        raise Cur0sExactError("source_file_binding_mismatch")
    bindings = prereg.get("source_file_bindings")
    if not isinstance(bindings, dict) or set(bindings) != set(BOUND_SOURCE_FILES):
        raise Cur0sExactError("source_file_bindings_missing")
    if bindings != observed_bindings:
        raise Cur0sExactError("source_file_git_binding_mismatch")
    if git_head != source_commit:
        raise Cur0sExactError("source_checkout_commit_mismatch")
    if dirty:
        raise Cur0sExactError("source_checkout_bound_files_dirty")
    policy = prereg.get("anti_percolation_policy")
    if not isinstance(policy, dict):
        raise Cur0sExactError("anti_percolation_policy_missing")
    AntiPercolationPolicy(**policy)
    if prereg.get("anti_percolation_policy_sha256") != canonical_sha256(policy):
        raise Cur0sExactError("anti_percolation_policy_root_mismatch")
    validate_governing_inputs(prereg)

    claimed_root = prereg.get("preregistration_root_sha256")
    require_sha256(claimed_root, "preregistration_root_sha256")
    without_root = dict(prereg)
    without_root.pop("preregistration_root_sha256")
    if canonical_sha256(without_root) != claimed_root:
        raise Cur0sExactError("preregistration_root_mismatch")
    return {
        "source_commit": source_commit,
        "source_file_sha256": expected,
        "git_HEAD_verified": True,
        "bound_source_files_clean": True,
        "preimport_source_bytes_verified": preimport_verified,
    }


def validate_transaction_authority(prereg: dict[str, Any]) -> CampaignLease:
    campaign_lease = validate_campaign_lease(prereg)
    resource_slice = prereg.get("resource_slice")
    if not isinstance(resource_slice, dict):
        raise Cur0sExactError("resource_slice_missing")
    required_resources = {
        "phone_adb_serial_sha256": "sha256:383e1fef6040334134430241a105f7d900f6d924e485fdc858441e734d3ae0f4",
        "phone_model": "NX789J",
        "phone_soc": "SM8750",
        "runpod": "uh57jg7iguwqth_existing_only",
        "github_repository": "Zer0pa/Polymath-AI",
        "huggingface_visibility": "private_revision_pinned_only",
        "comet_payload": "hash_bound_metadata_only",
        "public_release": False,
    }
    if resource_slice != required_resources:
        raise Cur0sExactError("resource_slice_mismatch")
    if prereg.get("source_checkout_policy") != (
        "git_HEAD_equals_source_commit_and_bound_files_clean"
    ):
        raise Cur0sExactError("source_checkout_policy_mismatch")
    expected_grouping = {
        "arm_A": "exact_dataset_revision_source_local_identity",
        "arm_B": "Arm_A_union_conservative_exact_joint_question_material_identity",
        "answer_only_edges": "forbidden",
        "near_semantic_Arm_C": "not_executed_in_this_subordinate_candidate",
        "successor_split_assignment": "forbidden_before_Arm_C_admission",
    }
    if prereg.get("grouping_contract") != expected_grouping:
        raise Cur0sExactError("grouping_contract_mismatch")
    expected_custody = {
        "execution_plane": "phone_private",
        "raw_payload_egress": False,
        "row_membership_overlay_egress": False,
        "aggregate_hash_bound_receipt_egress": True,
    }
    if prereg.get("custody") != expected_custody:
        raise Cur0sExactError("custody_contract_mismatch")
    if prereg.get("claim_scope") != (
        "current_physical_root_exact_identity_and_custody_only"
    ):
        raise Cur0sExactError("claim_scope_mismatch")
    if prereg.get("output_directory_name") != "candidate-001":
        raise Cur0sExactError("output_directory_name_mismatch")
    return campaign_lease


def validate_campaign_lease(
    prereg: dict[str, Any], *, now: datetime | None = None
) -> CampaignLease:
    lease = prereg.get("campaign_lease")
    if not isinstance(lease, dict):
        raise Cur0sExactError("campaign_lease_missing")
    expected_lease_keys = {
        "lease_id",
        "action_id",
        "state",
        "issued_at_utc",
        "expires_at_utc",
        "additional_paid_capacity",
        "max_phone_execution_count",
        "phone_execution_count_before",
        "max_wall_seconds",
        "max_private_output_bytes",
        "min_free_storage_bytes",
        "max_temperature_millidegrees_c",
        "thermal_sample_every_records",
    }
    if set(lease) != expected_lease_keys:
        raise Cur0sExactError("campaign_lease_field_set_mismatch")
    if lease["lease_id"] != "current_user_sovereign_frontier_campaign_20260711":
        raise Cur0sExactError("campaign_lease_id_mismatch")
    if lease["action_id"] != prereg.get("run_id"):
        raise Cur0sExactError("campaign_lease_action_mismatch")
    if lease["state"] != "active" or lease["additional_paid_capacity"] is not False:
        raise Cur0sExactError("campaign_lease_state_mismatch")
    expected_integers = {
        "max_phone_execution_count": 1,
        "phone_execution_count_before": 0,
        "max_wall_seconds": 1800,
        "max_private_output_bytes": 268435456,
        "min_free_storage_bytes": 10737418240,
        "max_temperature_millidegrees_c": 85000,
        "thermal_sample_every_records": 1024,
    }
    for field, expected in expected_integers.items():
        value = lease[field]
        if type(value) is not int or value != expected:
            raise Cur0sExactError(f"campaign_lease_{field}_mismatch")
    issued_at = parse_utc_second(lease["issued_at_utc"], "campaign_lease_issued_at")
    expires_at = parse_utc_second(
        lease["expires_at_utc"], "campaign_lease_expires_at"
    )
    current_time = now or datetime.now(timezone.utc)
    if expires_at <= issued_at:
        raise Cur0sExactError("campaign_lease_nonpositive_duration")
    if (expires_at - issued_at).total_seconds() > 4 * 60 * 60:
        raise Cur0sExactError("campaign_lease_duration_exceeds_four_hours")
    if issued_at > current_time:
        raise Cur0sExactError("campaign_lease_not_yet_active")
    if current_time >= expires_at:
        raise Cur0sExactError("campaign_lease_expired")
    return CampaignLease(
        lease_id=lease["lease_id"],
        action_id=lease["action_id"],
        issued_at=issued_at,
        expires_at=expires_at,
        max_wall_seconds=lease["max_wall_seconds"],
        max_private_output_bytes=lease["max_private_output_bytes"],
        min_free_storage_bytes=lease["min_free_storage_bytes"],
        max_temperature_millidegrees_c=lease[
            "max_temperature_millidegrees_c"
        ],
        thermal_sample_every_records=lease["thermal_sample_every_records"],
    )


def parse_utc_second(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value
    ) is None:
        raise Cur0sExactError(f"{field}_invalid")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        raise Cur0sExactError(f"{field}_invalid") from None
    if iso_utc(parsed) != value:
        raise Cur0sExactError(f"{field}_not_canonical")
    return parsed


def validate_governing_inputs(prereg: dict[str, Any]) -> None:
    expected = {
        "PRD_sha256": "sha256:725d0ad6ac77fdcfc06a2635c7552cc414e0ed48f30fbd0f7f7ec38720493a3c",
        "living_concept_sha256": "sha256:b2f617766b660237ddfd329c6b7fa2370f9a2641983e71915b4cd71c6d31bacc",
        "corpus_audit_sha256": "sha256:c3a5d5eacf424f6e50ae0a170873d1c80e566581e22031a8f64bc899f8eec0fa",
    }
    if prereg.get("governing_inputs") != expected:
        raise Cur0sExactError("governing_inputs_mismatch")


def guard_phone_environment() -> dict[str, Any]:
    preimport_phone_guard()
    if platform.system() != "Linux" or platform.machine() != "aarch64":
        raise Cur0sExactError("runner_requires_android_aarch64")
    if Path.home() != PHONE_HOME or os.environ.get("HOME") != str(PHONE_HOME):
        raise Cur0sExactError("runner_requires_exact_termux_private_home")
    actual = {
        "model": getprop("ro.product.model"),
        "device": getprop("ro.product.device"),
        "soc": getprop("ro.soc.model"),
        "architecture": platform.machine(),
        "private_home": str(Path.home()),
        "build_fingerprint_sha256": "sha256:"
        + hashlib.sha256(getprop_raw("ro.build.fingerprint")).hexdigest(),
    }
    if (actual["model"], actual["device"], actual["soc"]) != (
        "NX789J",
        "NX789J",
        "SM8750",
    ):
        raise Cur0sExactError("live_phone_identity_mismatch")
    return actual


def validate_phone_runtime(
    prereg: dict[str, Any], actual: dict[str, Any]
) -> dict[str, Any]:
    expected = prereg.get("target_device")
    if not isinstance(expected, dict):
        raise Cur0sExactError("target_device_missing")
    for key in ("model", "device", "soc", "architecture", "private_home"):
        if actual[key] != expected.get(key):
            raise Cur0sExactError(f"target_device_{key}_mismatch")
    if expected.get("build_fingerprint_sha256") != EXPECTED_BUILD_FINGERPRINT_SHA256:
        raise Cur0sExactError("target_device_build_fingerprint_binding_mismatch")
    if actual["build_fingerprint_sha256"] != EXPECTED_BUILD_FINGERPRINT_SHA256:
        raise Cur0sExactError("live_build_fingerprint_mismatch")
    expected_serial_hash = (
        "sha256:383e1fef6040334134430241a105f7d900f6d924e485fdc858441e734d3ae0f4"
    )
    if expected.get("adb_serial_sha256") != expected_serial_hash:
        raise Cur0sExactError("target_device_adb_serial_binding_mismatch")
    return {
        "model": actual["model"],
        "device": actual["device"],
        "soc": actual["soc"],
        "architecture": actual["architecture"],
        "private_home_sha256": "sha256:"
        + hashlib.sha256(actual["private_home"].encode()).hexdigest(),
        "build_fingerprint_sha256": actual["build_fingerprint_sha256"],
        "adb_serial_sha256": expected_serial_hash,
        "adb_serial_runtime_visibility": "external_ADB_custody_only",
        "phone_private_runtime_guard_passed": True,
    }


def validate_package_root(path: Path) -> Path:
    if not path.is_absolute():
        raise Cur0sExactError("package_root_must_be_absolute")
    absolute = Path(os.path.abspath(path))
    assert_no_symlink_components(absolute, PHONE_HOME)
    resolved = absolute.resolve(strict=True)
    if resolved != PHONE_SOURCE_ROOT:
        raise Cur0sExactError("package_root_not_preregistered_phone_source")
    return resolved


def validate_private_existing_path(path: Path, role: str) -> Path:
    if not path.is_absolute():
        raise Cur0sExactError(f"{role}_must_be_absolute")
    absolute = Path(os.path.abspath(path))
    assert_no_symlink_components(absolute, PHONE_RUN_ROOT)
    assert_owner_only_chain(absolute, PHONE_RUN_ROOT)
    resolved = absolute.resolve(strict=True)
    require_beneath(resolved, PHONE_RUN_ROOT, role)
    if not resolved.is_file():
        raise Cur0sExactError(f"{role}_must_be_regular_file")
    require_owner_only(resolved, role)
    return resolved


def validate_private_output_path(path: Path, run_id: str, expected_name: str) -> Path:
    if RUN_ID_RE.fullmatch(run_id) is None:
        raise Cur0sExactError("run_id_invalid")
    absolute = Path(os.path.abspath(path))
    if not path.is_absolute():
        raise Cur0sExactError("output_dir_must_be_absolute")
    if absolute.exists():
        raise Cur0sExactError("output_dir_must_not_exist")
    if absolute.name != expected_name or expected_name != "candidate-001":
        raise Cur0sExactError("output_directory_name_mismatch")
    parent = absolute.parent.resolve(strict=True)
    required_parent = PHONE_RUN_ROOT / run_id / "candidate_runs"
    if parent != required_parent:
        raise Cur0sExactError("output_parent_not_preregistered_candidate_root")
    assert_no_symlink_components(parent, PHONE_RUN_ROOT)
    assert_owner_only_chain(parent, PHONE_RUN_ROOT)
    return parent / absolute.name


def require_beneath(path: Path, root: Path, role: str) -> None:
    try:
        path.relative_to(root)
    except ValueError:
        raise Cur0sExactError(f"{role}_outside_phone_private_root") from None


def assert_no_symlink_components(path: Path, anchor: Path) -> None:
    require_beneath(path, anchor, "path")
    current = anchor
    if current.is_symlink():
        raise Cur0sExactError("phone_private_anchor_symlink_forbidden")
    for component in path.relative_to(anchor).parts:
        current /= component
        if current.exists() and current.is_symlink():
            raise Cur0sExactError("phone_private_path_symlink_forbidden")


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
        raise Cur0sExactError(f"{role}_owner_mismatch")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise Cur0sExactError(f"{role}_must_be_owner_only")


def read_private_file(path: Path) -> bytes:
    home_fd = os.open(
        PHONE_HOME,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        run_root_fd = open_directory_beneath(
            home_fd,
            PHONE_RUN_ROOT_RELATIVE,
            require_owner_only_components=True,
        )
    finally:
        os.close(home_fd)
    try:
        fd = open_regular_beneath(
            run_root_fd, str(path.relative_to(PHONE_RUN_ROOT))
        )
        try:
            info_before = os.fstat(fd)
            if info_before.st_uid != os.geteuid() or info_before.st_gid != os.getegid():
                raise Cur0sExactError("private_file_owner_mismatch")
            if stat.S_IMODE(info_before.st_mode) & 0o077:
                raise Cur0sExactError("private_file_permissions_invalid")
            if info_before.st_nlink != 1:
                raise Cur0sExactError("private_file_hardlink_forbidden")
            if info_before.st_size > 1024 * 1024:
                raise Cur0sExactError("private_file_too_large")
            chunks: list[bytes] = []
            size = 0
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > 1024 * 1024:
                    raise Cur0sExactError("private_file_too_large")
            if stat_identity(os.fstat(fd)) != stat_identity(info_before):
                raise Cur0sExactError("private_file_changed_during_read")
            return b"".join(chunks)
        finally:
            os.close(fd)
    finally:
        os.close(run_root_fd)


def getprop(name: str) -> str:
    return getprop_raw(name).decode("utf-8").strip()


def getprop_raw(name: str) -> bytes:
    return subprocess.run(
        ["/system/bin/getprop", name],
        check=True,
        capture_output=True,
        timeout=5,
        env={
            "ANDROID_ROOT": "/system",
            "HOME": str(PHONE_HOME),
            "PATH": "/system/bin:/data/data/com.termux/files/usr/bin",
        },
    ).stdout


def git_output(*args: str) -> str:
    executable = Path("/data/data/com.termux/files/usr/bin/git")
    if not executable.is_file():
        executable = Path("git")
    return subprocess.run(
        [str(executable), *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
        env={
            "HOME": str(PHONE_HOME if PHONE_HOME.exists() else Path.home()),
            "PATH": "/data/data/com.termux/files/usr/bin:/system/bin:/usr/local/bin:/usr/bin:/bin",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        },
    ).stdout.strip()


@dataclass(frozen=True)
class OpenArtifact:
    stage: str
    role: str
    relative_path: str
    expected_sha256: str
    expected_rows: int | None
    fd: int
    initial_stat: tuple[int, int, int, int, int, int, int, int, int]


class SourceSnapshot:
    """One open-file snapshot shared by hashing, parsing, and revalidation."""

    def __init__(self, root_fd: int, artifacts: tuple[OpenArtifact, ...]) -> None:
        self._root_fd = root_fd
        self.artifacts = artifacts

    @classmethod
    def open(cls, package_root: Path) -> "SourceSnapshot":
        if package_root != PHONE_SOURCE_ROOT:
            raise Cur0sExactError("source_snapshot_root_mismatch")
        home_fd = os.open(
            PHONE_HOME,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        try:
            root_fd = open_directory_beneath(home_fd, PHONE_SOURCE_ROOT_RELATIVE)
        finally:
            os.close(home_fd)
        opened: list[OpenArtifact] = []
        seen_inodes: set[tuple[int, int]] = set()
        try:
            for lock in STAGE_LOCKS:
                for role, relative_path, expected_sha, expected_rows in (
                    ("master", lock.master_relative_path, lock.master_sha256, lock.rows),
                    ("qa", lock.qa_relative_path, lock.qa_sha256, lock.rows),
                    ("manifest", lock.manifest_relative_path, lock.manifest_sha256, None),
                ):
                    fd = open_regular_beneath(root_fd, relative_path)
                    info = os.fstat(fd)
                    inode = (info.st_dev, info.st_ino)
                    if inode in seen_inodes:
                        os.close(fd)
                        raise Cur0sExactError("source_inode_alias_forbidden")
                    seen_inodes.add(inode)
                    opened.append(
                        OpenArtifact(
                            stage=lock.stage,
                            role=role,
                            relative_path=relative_path,
                            expected_sha256=expected_sha,
                            expected_rows=expected_rows,
                            fd=fd,
                            initial_stat=stat_identity(info),
                        )
                    )
            return cls(root_fd, tuple(opened))
        except Exception:
            for artifact in opened:
                os.close(artifact.fd)
            os.close(root_fd)
            raise

    def verify(self, envelope: ResourceEnvelope | None = None) -> dict[str, Any]:
        artifacts: list[dict[str, Any]] = []
        total_master_rows = 0
        for artifact in self.artifacts:
            actual_sha, rows, size = hash_open_artifact(artifact, envelope)
            rows_pass = artifact.expected_rows is None or rows == artifact.expected_rows
            item = {
                "stage": artifact.stage,
                "role": artifact.role,
                "relative_path": artifact.relative_path,
                "bytes": size,
                "sha256": actual_sha,
                "rows": rows if artifact.expected_rows is not None else None,
                "passed": actual_sha == artifact.expected_sha256 and rows_pass,
            }
            artifacts.append(item)
            if artifact.role == "master":
                total_master_rows += rows
        passed = total_master_rows == TOTAL_ROWS and all(item["passed"] for item in artifacts)
        return {
            "state": "passed_scope" if passed else "falsified_scope",
            "passed": passed,
            "total_master_rows": total_master_rows,
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
            "single_open_fd_snapshot": True,
            "this_runner_raw_payload_egress": False,
            "external_custody_attestation_required": True,
        }

    def close(self) -> None:
        for artifact in self.artifacts:
            try:
                os.close(artifact.fd)
            except OSError:
                pass
        try:
            os.close(self._root_fd)
        except OSError:
            pass


def iter_master_records(
    snapshot: SourceSnapshot, envelope: ResourceEnvelope | None = None
):
    global_record_count = 0
    for lock in STAGE_LOCKS:
        artifact = next(
            item
            for item in snapshot.artifacts
            if item.stage == lock.stage and item.role == "master"
        )
        os.lseek(artifact.fd, 0, os.SEEK_SET)
        with os.fdopen(os.dup(artifact.fd), "rb") as handle:
            for line_number, raw in enumerate(handle, start=1):
                if (
                    envelope is not None
                    and global_record_count % envelope.lease.thermal_sample_every_records
                    == 0
                ):
                    envelope.check("identity_parse_record_checkpoint")
                try:
                    payload = strict_json_loads(raw)
                except Exception as error:
                    raise Cur0sExactError(
                        f"invalid_master_json_stage_{lock.stage}_line_{line_number}"
                    ) from error
                if not isinstance(payload, dict):
                    raise Cur0sExactError("master_row_must_be_object")
                global_record_count += 1
                yield lock.stage, payload


def open_regular_beneath(root_fd: int, relative_path: str) -> int:
    path = Path(relative_path)
    components = path.parts
    if path.is_absolute() or not components or any(
        part in {"", ".", ".."} for part in components
    ):
        raise Cur0sExactError("invalid_source_relative_path")
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
        file_fd = os.open(
            components[-1],
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=current_fd,
        )
        info = os.fstat(file_fd)
        if not stat.S_ISREG(info.st_mode):
            os.close(file_fd)
            raise Cur0sExactError("source_artifact_not_regular")
        return file_fd
    finally:
        os.close(current_fd)


def open_directory_beneath(
    root_fd: int,
    relative_path: str,
    *,
    require_owner_only_components: bool = False,
) -> int:
    path = Path(relative_path)
    components = path.parts
    if path.is_absolute() or not components or any(
        part in {"", ".", ".."} for part in components
    ):
        raise Cur0sExactError("invalid_directory_relative_path")
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
            if require_owner_only_components:
                require_owner_only_fd(current_fd, "private_directory_component")
        result = current_fd
        current_fd = -1
        return result
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def require_owner_only_fd(fd: int, role: str) -> None:
    info = os.fstat(fd)
    if info.st_uid != os.geteuid() or info.st_gid != os.getegid():
        raise Cur0sExactError(f"{role}_owner_mismatch")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise Cur0sExactError(f"{role}_must_be_owner_only")


def hash_open_artifact(
    artifact: OpenArtifact, envelope: ResourceEnvelope | None = None
) -> tuple[str, int, int]:
    before = os.fstat(artifact.fd)
    if stat_identity(before) != artifact.initial_stat:
        raise Cur0sExactError("source_artifact_stat_changed")
    os.lseek(artifact.fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    rows = 0
    while True:
        if envelope is not None:
            envelope.check(f"physical_hash_{artifact.stage}_{artifact.role}")
        chunk = os.read(artifact.fd, 4 * 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        rows += chunk.count(b"\n")
    after = os.fstat(artifact.fd)
    if stat_identity(after) != artifact.initial_stat:
        raise Cur0sExactError("source_artifact_changed_during_read")
    return digest.hexdigest(), rows, after.st_size


def stat_identity(info: os.stat_result) -> tuple[int, int, int, int, int, int, int, int, int]:
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


class PrivateOutput:
    """A retained no-follow directory transaction for all candidate outputs."""

    DATA_CONTROL_RESERVE_BYTES = 2 * 1024 * 1024
    COMPLETION_RESERVE_BYTES = 64 * 1024

    def __init__(
        self,
        directory_fd: int,
        max_bytes: int,
        *,
        execution_claim_sha256: str | None = None,
        execution_claim_bytes: int | None = None,
    ) -> None:
        self._directory_fd = directory_fd
        self._max_bytes = max_bytes
        self._accounted_bytes = 0
        self._files: list[str] = []
        self._payload_sealed = False
        self._completed = False
        self._execution_claim_sha256 = execution_claim_sha256
        self._execution_claim_bytes = execution_claim_bytes

    @classmethod
    def create(cls, path: Path, run_id: str, *, max_bytes: int) -> "PrivateOutput":
        if path.parent != PHONE_RUN_ROOT / run_id / "candidate_runs":
            raise Cur0sExactError("private_output_parent_mismatch")
        if path.name != "candidate-001":
            raise Cur0sExactError("private_output_name_mismatch")
        home_fd = os.open(
            PHONE_HOME,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        try:
            run_root_fd = open_directory_beneath(
                home_fd, PHONE_RUN_ROOT_RELATIVE, require_owner_only_components=True
            )
        finally:
            os.close(home_fd)
        try:
            parent_fd = open_directory_beneath(
                run_root_fd,
                f"{run_id}/candidate_runs",
                require_owner_only_components=True,
            )
        finally:
            os.close(run_root_fd)
        try:
            claim = {
                "schema_version": "cur0s_static_identity_execution_claim_v1",
                "run_id": run_id,
                "output_directory_name": path.name,
                "phone_execution_ordinal": 1,
            }
            claim_sha256, claim_bytes = write_exclusive_bytes_at(
                parent_fd,
                ".cur0s_static_identity_execution_claim",
                canonical_json_bytes(claim) + b"\n",
                mode=0o400,
            )
            os.mkdir(path.name, mode=0o700, dir_fd=parent_fd)
            os.fsync(parent_fd)
            directory_fd = os.open(
                path.name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=parent_fd,
            )
            require_owner_only_fd(directory_fd, "private_output")
            return cls(
                directory_fd,
                max_bytes,
                execution_claim_sha256=claim_sha256,
                execution_claim_bytes=claim_bytes,
            )
        finally:
            os.close(parent_fd)

    @property
    def directory_fd(self) -> int:
        return self._directory_fd

    @property
    def bytes_written(self) -> int:
        return self._accounted_bytes

    def write_overlay(
        self, name: str, rows, envelope: ResourceEnvelope
    ) -> tuple[str, int]:
        self._require_writable_name(name)
        self._files.append(name)
        return write_overlay_at(
            self._directory_fd,
            name,
            rows,
            envelope=envelope,
            reserve_bytes=self._reserve_data_bytes,
        )

    def write_receipt(self, name: str, value: dict[str, Any]) -> tuple[str, int]:
        self._require_writable_name(name)
        payload = canonical_json_bytes(value) + b"\n"
        self._reserve_receipt_bytes(len(payload))
        result = write_exclusive_bytes_at(
            self._directory_fd, name, payload, mode=0o600
        )
        self._files.append(name)
        return result

    def seal_payload_before_completion(self) -> None:
        if self._payload_sealed or self._completed:
            raise Cur0sExactError("private_output_already_sealed")
        for name in self._files:
            fd = os.open(
                name,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=self._directory_fd,
            )
            try:
                os.fchmod(fd, 0o400)
                os.fsync(fd)
            finally:
                os.close(fd)
        os.fsync(self._directory_fd)
        self._payload_sealed = True

    def write_completion_last(
        self, name: str, value: dict[str, Any]
    ) -> tuple[str, int]:
        if not self._payload_sealed or self._completed:
            raise Cur0sExactError("completion_order_invalid")
        if name != "COMPLETE.json":
            raise Cur0sExactError("completion_name_invalid")
        payload = canonical_json_bytes(value) + b"\n"
        self._reserve_completion_bytes(len(payload))
        result = write_exclusive_bytes_at(
            self._directory_fd,
            name,
            payload,
            mode=0o400,
        )
        self._completed = True
        return result

    def partial_output_report(self) -> dict[str, Any]:
        actual_bytes = 0
        existing_files = 0
        for name in self._files:
            try:
                info = os.stat(name, dir_fd=self._directory_fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            if stat.S_ISREG(info.st_mode):
                actual_bytes += info.st_size
                existing_files += 1
        return {
            "tracked_private_file_count": existing_files,
            "actual_partial_private_output_bytes": actual_bytes,
            "budget_accounted_private_output_bytes": self._accounted_bytes,
            "partial_overlay_possible": "exact_identity_overlay.private.jsonl"
            in self._files,
            "completion_marker_present": self._completed,
            "private_payload_egressed": False,
        }

    def execution_claim_receipt(self) -> dict[str, Any]:
        return {
            "state": "claimed_once_O_EXCL"
            if self._execution_claim_sha256 is not None
            else "test_fixture_without_external_claim",
            "claim_sha256": self._execution_claim_sha256,
            "claim_bytes": self._execution_claim_bytes,
            "claim_egressed": False,
            "claim_persistent_after_all_stop_classes": True,
        }

    def close(self) -> None:
        try:
            os.close(self._directory_fd)
        except OSError:
            pass

    def _require_writable_name(self, name: str) -> None:
        if self._payload_sealed or self._completed:
            raise Cur0sExactError("private_output_is_sealed")
        if Path(name).parts != (name,) or name in {"", ".", ".."}:
            raise Cur0sExactError("private_output_name_invalid")
        if name in self._files:
            raise Cur0sExactError("private_output_name_reused")

    def _reserve_data_bytes(self, size: int) -> None:
        limit = self._max_bytes - self.DATA_CONTROL_RESERVE_BYTES
        self._reserve_bytes(size, limit, "private_output_data_budget_reached")

    def _reserve_receipt_bytes(self, size: int) -> None:
        limit = self._max_bytes - self.COMPLETION_RESERVE_BYTES
        self._reserve_bytes(size, limit, "private_output_receipt_budget_reached")

    def _reserve_completion_bytes(self, size: int) -> None:
        self._reserve_bytes(size, self._max_bytes, "private_output_completion_budget_reached")

    def _reserve_bytes(self, size: int, limit: int, code: str) -> None:
        if type(size) is not int or size < 0:
            raise Cur0sExactError("private_output_size_invalid")
        if self._accounted_bytes + size > limit:
            raise OperationalStop(code, "private_output_write")
        self._accounted_bytes += size


def write_overlay_at(
    directory_fd: int,
    name: str,
    rows,
    *,
    envelope: ResourceEnvelope,
    reserve_bytes,
) -> tuple[str, int]:
    fd = os.open(
        name,
        os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
        0o600,
        dir_fd=directory_fd,
    )
    initial = os.fstat(fd)
    digest = hashlib.sha256()
    size = 0
    try:
        for row_index, row in enumerate(rows):
            if row_index % envelope.lease.thermal_sample_every_records == 0:
                envelope.check("overlay_write_record_checkpoint")
            payload = canonical_json_bytes(row.private_overlay_dict()) + b"\n"
            reserve_bytes(len(payload))
            write_all(fd, payload)
            digest.update(payload)
            size += len(payload)
        os.fsync(fd)
        expected_sha = "sha256:" + digest.hexdigest()
        if hash_open_fd(fd) != (expected_sha, size):
            raise Cur0sExactError("private_overlay_readback_mismatch")
        require_same_directory_entry(directory_fd, name, initial, os.fstat(fd))
    except OperationalStop:
        os.fsync(fd)
        os.fsync(directory_fd)
        raise
    finally:
        os.close(fd)
    os.fsync(directory_fd)
    return expected_sha, size


def write_exclusive_bytes_at(
    directory_fd: int, name: str, payload: bytes, *, mode: int = 0o600
) -> tuple[str, int]:
    fd = os.open(
        name,
        os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
        mode,
        dir_fd=directory_fd,
    )
    try:
        initial = os.fstat(fd)
        write_all(fd, payload)
        os.fsync(fd)
        expected = ("sha256:" + hashlib.sha256(payload).hexdigest(), len(payload))
        if hash_open_fd(fd) != expected:
            raise Cur0sExactError("private_json_readback_mismatch")
        final = os.fstat(fd)
        require_same_directory_entry(directory_fd, name, initial, final)
        os.fchmod(fd, mode)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(directory_fd)
    return expected


def write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("zero_length_write")
        view = view[written:]


def hash_open_fd(fd: int) -> tuple[str, int]:
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


def require_same_directory_entry(
    directory_fd: int,
    name: str,
    initial: os.stat_result,
    final: os.stat_result,
) -> None:
    entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    if (initial.st_dev, initial.st_ino) != (final.st_dev, final.st_ino):
        raise Cur0sExactError("private_output_inode_changed")
    if (final.st_dev, final.st_ino) != (entry.st_dev, entry.st_ino):
        raise Cur0sExactError("private_output_entry_replaced")
    if final.st_nlink != 1 or not stat.S_ISREG(final.st_mode):
        raise Cur0sExactError("private_output_inode_invalid")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise Cur0sExactError(f"{field}_missing")
    match = SHA_RE.fullmatch(value)
    if match is None:
        raise Cur0sExactError(f"{field}_invalid")
    return "sha256:" + match.group(1)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def iso_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("datetime_must_be_UTC")
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    preimport_phone_guard()
    _main_args = parse_args()
    (
        _main_prereg_bytes,
        _main_prereg,
        _main_source_bytes,
        _PREIMPORT_SOURCE_ATTESTATION,
    ) = bootstrap_authority(_main_args)
    bind_bound_modules(_main_source_bytes)
    raise SystemExit(
        main(
            args=_main_args,
            prereg_bytes=_main_prereg_bytes,
            prereg=_main_prereg,
        )
    )

#!/usr/bin/env python3
"""Run the Adreno preflight through an ADB-attested forwarded SSH channel.

This host wrapper deliberately has no candidate/model/tensor path arguments.  Its
only egress allowlist is the four source-neutral preflight transaction artifacts.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import subprocess
import sys
import tempfile
from typing import Any, Callable, Mapping, Sequence

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "polymath_ai/frontier/e4b_adreno_int2_lm_head.py"
SPEC = importlib.util.spec_from_file_location(
    "_e4b_adreno_int2_adb_custody_contract", CONTRACT_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load Adreno custody contract")
contract = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = contract
SPEC.loader.exec_module(contract)

ADB_EXECUTABLE = "adb"
ADB_SERIAL = "FY25013101C8"
ADB_FORWARD_LOCAL = "tcp:18022"
ADB_FORWARD_REMOTE = "tcp:8022"
ADB_FORWARD_EXPECTED_LINE = f"{ADB_SERIAL} {ADB_FORWARD_LOCAL} {ADB_FORWARD_REMOTE}"
SSH_EXECUTABLE = "ssh"
SSH_KEYGEN_EXECUTABLE = "ssh-keygen"
SSH_ALIAS = "redmagic-termux-polymath"
SSH_RESOLVED_HOST = "127.0.0.1"
SSH_RESOLVED_PORT = 18_022
SSH_RESOLVED_USER = "u0_a536"
SSH_RESOLVED_IDENTITY_FILE = "/Users/prinivenpillay/.ssh/polymath_host"
SSH_CLIENT_PUBLIC_KEY_FINGERPRINT = "SHA256:gKxDEgEScPrY8O3omM8WWAG3Hwo2cCyq13demaGw3bY"
SSH_RESOLVED_USER_KNOWN_HOSTS_FILE = "/Users/prinivenpillay/.ssh/known_hosts"
SSH_SERVER_HOST_KEY_FINGERPRINT = "SHA256:RK4COBqnfndb+gOOFkaCMNOHDV0AxQkhx94X1yW+tgs"
SSH_REQUIRED_OVERRIDES = (
    "-T",
    "-o",
    "BatchMode=yes",
    "-o",
    "PasswordAuthentication=no",
    "-o",
    "KbdInteractiveAuthentication=no",
    "-o",
    "NumberOfPasswordPrompts=0",
    "-o",
    "RequestTTY=no",
    "-o",
    "StrictHostKeyChecking=yes",
    "-o",
    "IdentitiesOnly=yes",
)
REMOTE_UID = 10_536
REMOTE_GID = 10_536
TERMUX_HOME = "/data/data/com.termux/files/home"
TERMUX_PREFIX = "/data/data/com.termux/files/usr"
TERMUX_ENV = f"{TERMUX_PREFIX}/bin/env"
TERMUX_PYTHON = f"{TERMUX_PREFIX}/bin/python3"
TERMUX_TMPDIR = f"{TERMUX_PREFIX}/tmp"
TERMUX_EXEC_INTERPOSER = f"{TERMUX_PREFIX}/lib/libtermux-exec.so"
BOOT_ID_PATH = "/proc/sys/kernel/random/boot_id"
PREFLIGHT_RELATIVE_PATH = "scripts/termux/run_e4b_adreno_int2_preflight.py"
PREFLIGHT_TIMEOUT_SECONDS = 1_800
ADB_CONTROL_TIMEOUT_SECONDS = 60
CHALLENGE_HEX_BYTES = 32
CHALLENGE_PREFIX_HEX_CHARS = 16

RETRIEVED_ARTIFACT_NAMES = (
    "preflight_report.json",
    "preflight_report.json.sha256",
    "PREFLIGHT_COMPLETE.json",
    "opencl_contract.json",
)
EXPECTED_REMOTE_TOP_LEVEL = frozenset(
    {
        *RETRIEVED_ARTIFACT_NAMES,
        "build_a",
        "build_b",
        "probe.stdout.log",
        "probe.stderr.log",
    }
)
MAX_ARTIFACT_BYTES = {
    "preflight_report.json": 4 * 1024 * 1024,
    "preflight_report.json.sha256": 256,
    "PREFLIGHT_COMPLETE.json": 64 * 1024,
    "opencl_contract.json": 4 * 1024 * 1024,
}
LOCAL_RECEIPT_NAME = "adb_custody_receipt.json"
LOCAL_RECEIPT_SIDECAR_NAME = "adb_custody_receipt.json.sha256"
LOCAL_COMPLETION_NAME = "ADB_CUSTODY_COMPLETE.json"
LOCAL_OUTPUT_NAMES = frozenset(
    {
        *RETRIEVED_ARTIFACT_NAMES,
        LOCAL_RECEIPT_NAME,
        LOCAL_RECEIPT_SIDECAR_NAME,
        LOCAL_COMPLETION_NAME,
    }
)
RECEIPT_SCHEMA = "gemma4_e4b_adreno_adb_forwarded_ssh_custody_receipt_v2"
COMPLETION_SCHEMA = "gemma4_e4b_adreno_adb_forwarded_ssh_custody_completion_v2"
REMOTE_PATH_PATTERN = re.compile(r"/[A-Za-z0-9._/-]+\Z")
CHALLENGE_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
BOOT_ID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
SOURCE_REVISION_PATTERN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")

if (
    contract.ADB_PREFLIGHT_CUSTODY_SCHEMA != RECEIPT_SCHEMA
    or contract.ADB_PREFLIGHT_CUSTODY_COMPLETION_SCHEMA != COMPLETION_SCHEMA
    or contract.AUTHORIZED_ADB_SERIAL != ADB_SERIAL
    or contract.AUTHORIZED_ADB_FORWARD_LOCAL != ADB_FORWARD_LOCAL
    or contract.AUTHORIZED_ADB_FORWARD_REMOTE != ADB_FORWARD_REMOTE
    or contract.AUTHORIZED_TERMUX_SSH_ALIAS != SSH_ALIAS
    or contract.AUTHORIZED_TERMUX_SSH_HOST != SSH_RESOLVED_HOST
    or contract.AUTHORIZED_TERMUX_SSH_PORT != SSH_RESOLVED_PORT
    or contract.AUTHORIZED_TERMUX_SSH_USER != SSH_RESOLVED_USER
    or contract.AUTHORIZED_TERMUX_SSH_IDENTITY_FILE != SSH_RESOLVED_IDENTITY_FILE
    or contract.AUTHORIZED_TERMUX_SSH_KNOWN_HOSTS_FILE
    != SSH_RESOLVED_USER_KNOWN_HOSTS_FILE
    or contract.AUTHORIZED_TERMUX_SSH_SERVER_KEY_FINGERPRINT
    != SSH_SERVER_HOST_KEY_FINGERPRINT
    or contract.AUTHORIZED_TERMUX_SSH_CLIENT_KEY_FINGERPRINT
    != SSH_CLIENT_PUBLIC_KEY_FINGERPRINT
    or tuple(contract.AUTHORIZED_TERMUX_SSH_REQUIRED_OVERRIDES)
    != SSH_REQUIRED_OVERRIDES
    or contract.AUTHORIZED_TERMUX_UID != REMOTE_UID
    or contract.AUTHORIZED_TERMUX_GID != REMOTE_GID
):
    raise RuntimeError("ADB-forwarded SSH wrapper and governing contract drifted")


class AdbCustodyError(contract.AdrenoGateError):
    """Raised when the explicit ADB custody transaction cannot be proven."""


RunCallable = Callable[..., subprocess.CompletedProcess[bytes]]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_timestamp(value: datetime | None = None) -> str:
    observed = value or _utc_now()
    if observed.tzinfo is None or observed.utcoffset() != timezone.utc.utcoffset(
        observed
    ):
        raise AdbCustodyError("custody timestamp is not UTC")
    return observed.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _utc_run_id(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise AdbCustodyError("custody run id source is not UTC")
    return value.strftime("%Y%m%dT%H%M%S%fZ")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validate_remote_path(value: str, *, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not REMOTE_PATH_PATTERN.fullmatch(value):
        raise AdbCustodyError(f"{label} is not a safe absolute phone path")
    path = PurePosixPath(value)
    if str(path) != value or any(part in {"", ".", ".."} for part in path.parts[1:]):
        raise AdbCustodyError(f"{label} is not canonical")
    try:
        path.relative_to(PurePosixPath(TERMUX_HOME))
    except ValueError as error:
        raise AdbCustodyError(
            f"{label} is outside the Termux home custody root"
        ) from error
    if path == PurePosixPath(TERMUX_HOME):
        raise AdbCustodyError(f"{label} must name a child of the Termux home")
    return path


def _validate_local_output(output_dir: Path) -> None:
    if not output_dir.is_absolute() or output_dir.name in {"", ".", ".."}:
        raise AdbCustodyError("local output directory must be an absolute new path")
    parent = output_dir.parent
    try:
        parent_metadata = parent.lstat()
    except FileNotFoundError as error:
        raise AdbCustodyError("local output parent does not exist") from error
    if not stat.S_ISDIR(parent_metadata.st_mode) or parent.is_symlink():
        raise AdbCustodyError("local output parent must be a real directory")
    if os.path.lexists(output_dir):
        raise AdbCustodyError("local output directory already exists")


def _validate_clean_success(
    result: subprocess.CompletedProcess[bytes], *, operation: str
) -> bytes:
    if not isinstance(result.stdout, bytes) or not isinstance(result.stderr, bytes):
        raise AdbCustodyError(f"{operation} did not return byte streams")
    if result.returncode != 0:
        raise AdbCustodyError(
            f"{operation} failed: return_code={result.returncode}, "
            f"stdout_sha256={_sha256(result.stdout)}, stderr_sha256={_sha256(result.stderr)}"
        )
    if result.stderr:
        raise AdbCustodyError(
            f"{operation} emitted stderr: sha256={_sha256(result.stderr)}"
        )
    return result.stdout


class ExplicitAdbTransport:
    """ADB transport that cannot issue a command without the frozen serial."""

    def __init__(
        self,
        *,
        executable: str = ADB_EXECUTABLE,
        serial: str = ADB_SERIAL,
        runner: RunCallable | None = None,
    ) -> None:
        if executable != ADB_EXECUTABLE or serial != ADB_SERIAL:
            raise AdbCustodyError("ADB executable or explicit serial drifted")
        self.executable = executable
        self.serial = serial
        self._runner = runner or subprocess.run
        self._environment = dict(os.environ)
        self._environment.pop("ANDROID_SERIAL", None)
        self._environment.pop("ADB_SERIAL", None)

    @property
    def prefix(self) -> list[str]:
        return [self.executable, "-s", self.serial]

    def run(
        self, arguments: Sequence[str], *, timeout_seconds: int
    ) -> subprocess.CompletedProcess[bytes]:
        if not arguments or any(
            not isinstance(argument, str) or not argument or "\x00" in argument
            for argument in arguments
        ):
            raise AdbCustodyError("invalid ADB argument vector")
        argv = [*self.prefix, *arguments]
        try:
            return self._runner(
                argv,
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
                env=self._environment,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise AdbCustodyError("explicit ADB transport failed") from error

    def exact_output(
        self, arguments: Sequence[str], *, operation: str, timeout_seconds: int
    ) -> bytes:
        return _validate_clean_success(
            self.run(arguments, timeout_seconds=timeout_seconds), operation=operation
        )

    def require_zero(
        self, arguments: Sequence[str], *, operation: str, timeout_seconds: int
    ) -> subprocess.CompletedProcess[bytes]:
        result = self.run(arguments, timeout_seconds=timeout_seconds)
        _validate_clean_success(result, operation=operation)
        return result


class ForwardedSshTransport:
    """Noninteractive SSH transport bound to the frozen ADB-forwarded alias."""

    def __init__(
        self,
        *,
        executable: str = SSH_EXECUTABLE,
        alias: str = SSH_ALIAS,
        runner: RunCallable | None = None,
    ) -> None:
        if executable != SSH_EXECUTABLE or alias != SSH_ALIAS:
            raise AdbCustodyError("forwarded SSH executable or alias drifted")
        self.executable = executable
        self.alias = alias
        self._runner = runner or subprocess.run
        self._environment = dict(os.environ)
        self._environment.pop("SSH_ASKPASS", None)
        self._environment.pop("SSH_ASKPASS_REQUIRE", None)

    @property
    def configuration_argv(self) -> list[str]:
        return [
            self.executable,
            "-G",
            *SSH_REQUIRED_OVERRIDES,
            self.alias,
        ]

    @property
    def command_prefix(self) -> list[str]:
        return [
            self.executable,
            *SSH_REQUIRED_OVERRIDES,
            self.alias,
            "--",
        ]

    def _run_argv(
        self, argv: Sequence[str], *, timeout_seconds: int
    ) -> subprocess.CompletedProcess[bytes]:
        if not argv or any(
            not isinstance(argument, str) or not argument or "\x00" in argument
            for argument in argv
        ):
            raise AdbCustodyError("invalid forwarded SSH argument vector")
        try:
            return self._runner(
                list(argv),
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
                env=self._environment,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise AdbCustodyError("forwarded SSH transport failed") from error

    def resolve_configuration(self) -> bytes:
        return _validate_clean_success(
            self._run_argv(
                self.configuration_argv,
                timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
            ),
            operation="forwarded SSH effective configuration",
        )

    def run_remote(
        self, arguments: Sequence[str], *, timeout_seconds: int
    ) -> subprocess.CompletedProcess[bytes]:
        return self._run_argv(
            [*self.command_prefix, *arguments], timeout_seconds=timeout_seconds
        )

    def exact_remote_output(
        self, arguments: Sequence[str], *, operation: str, timeout_seconds: int
    ) -> bytes:
        return _validate_clean_success(
            self.run_remote(arguments, timeout_seconds=timeout_seconds),
            operation=operation,
        )

    def require_remote_zero(
        self, arguments: Sequence[str], *, operation: str, timeout_seconds: int
    ) -> subprocess.CompletedProcess[bytes]:
        result = self.run_remote(arguments, timeout_seconds=timeout_seconds)
        _validate_clean_success(result, operation=operation)
        return result


def _decode_exact_line(payload: bytes, *, expected: str, operation: str) -> str:
    expected_payload = f"{expected}\n".encode("ascii")
    if payload != expected_payload:
        raise AdbCustodyError(f"{operation} identity drifted")
    return expected


def _decode_boot_id(payload: bytes) -> str:
    try:
        decoded = payload.decode("ascii")
    except UnicodeDecodeError as error:
        raise AdbCustodyError("boot_id is not ASCII") from error
    if not decoded.endswith("\n") or decoded.count("\n") != 1:
        raise AdbCustodyError("boot_id framing drifted")
    boot_id = decoded[:-1]
    if not BOOT_ID_PATTERN.fullmatch(boot_id):
        raise AdbCustodyError("boot_id shape drifted")
    return boot_id


def _read_adb_boot_id(transport: ExplicitAdbTransport) -> str:
    payload = transport.exact_output(
        ["exec-out", "/system/bin/cat", BOOT_ID_PATH],
        operation="ADB boot_id read",
        timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
    )
    return _decode_boot_id(payload)


def _read_ssh_boot_id(transport: ForwardedSshTransport) -> str:
    payload = transport.exact_remote_output(
        ["/system/bin/cat", BOOT_ID_PATH],
        operation="forwarded SSH boot_id read",
        timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
    )
    return _decode_boot_id(payload)


def _validate_forward_list(payload: bytes) -> list[str]:
    if not payload or len(payload) > 64 * 1024:
        raise AdbCustodyError("ADB forward list is empty or oversized")
    try:
        decoded = payload.decode("ascii")
    except UnicodeDecodeError as error:
        raise AdbCustodyError("ADB forward list is not ASCII") from error
    if not decoded.endswith("\n") or "\r" in decoded:
        raise AdbCustodyError("ADB forward list framing drifted")
    lines = decoded.splitlines()
    if lines and lines[-1] == "":
        lines.pop()
    if not lines or any(not line for line in lines):
        raise AdbCustodyError("ADB forward list terminal framing drifted")
    if len(lines) != len(set(lines)):
        raise AdbCustodyError("ADB forward list contains duplicate mappings")
    records: list[tuple[str, str, str]] = []
    for line in lines:
        fields = line.split()
        if len(fields) != 3 or any(not field for field in fields):
            raise AdbCustodyError("ADB forward list record drifted")
        records.append((fields[0], fields[1], fields[2]))
    exact = (ADB_SERIAL, ADB_FORWARD_LOCAL, ADB_FORWARD_REMOTE)
    if records.count(exact) != 1:
        raise AdbCustodyError("required ADB forward mapping is absent or duplicated")
    conflicts = [
        record
        for record in records
        if (
            record[1] == ADB_FORWARD_LOCAL
            or (record[0] == ADB_SERIAL and record[2] == ADB_FORWARD_REMOTE)
        )
        and record != exact
    ]
    if conflicts:
        raise AdbCustodyError("ADB forward mapping conflicts with frozen channel")
    return sorted(lines)


def _parse_ssh_configuration(payload: bytes) -> dict[str, list[str]]:
    if not payload or len(payload) > 512 * 1024:
        raise AdbCustodyError("forwarded SSH effective configuration is invalid")
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise AdbCustodyError("forwarded SSH configuration is not UTF-8") from error
    if not decoded.endswith("\n") or "\r" in decoded:
        raise AdbCustodyError("forwarded SSH configuration framing drifted")
    values: dict[str, list[str]] = {}
    for line in decoded.splitlines():
        key, separator, value = line.partition(" ")
        if (
            not separator
            or not re.fullmatch(r"[A-Za-z0-9]+", key)
            or not value
            or "\x00" in value
        ):
            raise AdbCustodyError("forwarded SSH configuration record drifted")
        values.setdefault(key.casefold(), []).append(value)
    return values


def _single_ssh_value(configuration: Mapping[str, list[str]], key: str) -> str:
    values = configuration.get(key)
    if not isinstance(values, list) or len(values) != 1:
        raise AdbCustodyError(f"forwarded SSH configuration key drifted: {key}")
    return values[0]


def _validate_ssh_configuration(payload: bytes) -> dict[str, Any]:
    configuration = _parse_ssh_configuration(payload)
    host = _single_ssh_value(configuration, "hostname")
    user = _single_ssh_value(configuration, "user")
    port = _single_ssh_value(configuration, "port")
    expected_values = {
        "batchmode": "yes",
        "passwordauthentication": "no",
        "kbdinteractiveauthentication": "no",
        "numberofpasswordprompts": "0",
        "requesttty": "false",
        "stricthostkeychecking": "true",
        "identitiesonly": "yes",
        "canonicalizehostname": "false",
        "permitlocalcommand": "no",
        "proxyusefdpass": "no",
        "controlmaster": "false",
        "controlpersist": "no",
        "forwardagent": "no",
        "forwardx11": "no",
    }
    forbidden_routing_keys = {
        "proxycommand",
        "proxyjump",
        "localcommand",
        "hostkeyalias",
        "localforward",
        "remoteforward",
        "dynamicforward",
        "remotecommand",
        "controlpath",
    }
    if (
        host != SSH_RESOLVED_HOST
        or user != SSH_RESOLVED_USER
        or port != str(SSH_RESOLVED_PORT)
        or forbidden_routing_keys.intersection(configuration)
        or any(
            _single_ssh_value(configuration, key) != value
            for key, value in expected_values.items()
        )
    ):
        raise AdbCustodyError("forwarded SSH effective configuration is unsafe")
    identity_files = configuration.get("identityfile")
    if identity_files != ["~/.ssh/polymath_host"]:
        raise AdbCustodyError("forwarded SSH identity file resolution drifted")
    resolved_identity = str(Path(identity_files[0]).expanduser())
    known_hosts = _single_ssh_value(configuration, "userknownhostsfile").split()
    if (
        resolved_identity != SSH_RESOLVED_IDENTITY_FILE
        or not known_hosts
        or known_hosts[0] != SSH_RESOLVED_USER_KNOWN_HOSTS_FILE
    ):
        raise AdbCustodyError("forwarded SSH key custody paths drifted")
    return {
        "resolved_host": host,
        "resolved_port": int(port),
        "resolved_user": user,
        "resolved_identity_file": resolved_identity,
        "resolved_user_known_hosts_file": known_hosts[0],
        "effective_configuration": {
            "batch_mode": True,
            "password_authentication": False,
            "kbd_interactive_authentication": False,
            "number_of_password_prompts": 0,
            "request_tty": False,
            "strict_host_key_checking": True,
            "identities_only": True,
        },
    }


def _parse_keygen_fingerprint_line(
    line: str, *, expected_comment: str | None = None
) -> str | None:
    fields = line.split()
    if len(fields) < 4 or fields[0] != "256" or fields[-1] != "(ED25519)":
        return None
    if expected_comment is not None and fields[2] != expected_comment:
        return None
    fingerprint = fields[1]
    if not fingerprint.startswith("SHA256:") or len(fingerprint) < 20:
        return None
    return fingerprint


def _verify_ssh_key_bindings(
    transport: ForwardedSshTransport, *, resolved_host: str
) -> dict[str, str]:
    client_argv = [
        SSH_KEYGEN_EXECUTABLE,
        "-lf",
        f"{SSH_RESOLVED_IDENTITY_FILE}.pub",
        "-E",
        "sha256",
    ]
    client_payload = _validate_clean_success(
        transport._run_argv(client_argv, timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS),
        operation="SSH client public-key fingerprint verification",
    )
    try:
        client_lines = client_payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise AdbCustodyError("SSH client fingerprint output is not UTF-8") from error
    client_fingerprints = [
        fingerprint
        for line in client_lines
        if (fingerprint := _parse_keygen_fingerprint_line(line)) is not None
    ]
    if client_fingerprints != [SSH_CLIENT_PUBLIC_KEY_FINGERPRINT]:
        raise AdbCustodyError("SSH client public-key fingerprint drifted")

    server_argv = [
        SSH_KEYGEN_EXECUTABLE,
        "-lf",
        SSH_RESOLVED_USER_KNOWN_HOSTS_FILE,
        "-E",
        "sha256",
    ]
    server_payload = _validate_clean_success(
        transport._run_argv(server_argv, timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS),
        operation="SSH server host-key fingerprint verification",
    )
    target = f"[{resolved_host}]:{SSH_RESOLVED_PORT}"
    try:
        server_lines = server_payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise AdbCustodyError("SSH host fingerprint output is not UTF-8") from error
    server_fingerprints = [
        fingerprint
        for line in server_lines
        if (
            fingerprint := _parse_keygen_fingerprint_line(line, expected_comment=target)
        )
        is not None
    ]
    if server_fingerprints != [SSH_SERVER_HOST_KEY_FINGERPRINT]:
        raise AdbCustodyError("SSH server host-key fingerprint drifted")
    return {
        "client_public_key_fingerprint": SSH_CLIENT_PUBLIC_KEY_FINGERPRINT,
        "server_host_key_fingerprint": SSH_SERVER_HOST_KEY_FINGERPRINT,
    }


def _decode_remote_identity(payload: bytes, *, expected: int, label: str) -> int:
    expected_payload = f"{expected}\n".encode("ascii")
    if payload != expected_payload:
        raise AdbCustodyError(f"forwarded SSH remote {label} drifted")
    return expected


def _preflight_remote_argv(
    *,
    remote_script_path: PurePosixPath,
    remote_build_dir: PurePosixPath,
    challenge: str,
) -> list[str]:
    probe_path = remote_build_dir / "opencl_contract.json"
    report_path = remote_build_dir / "preflight_report.json"
    return [
        TERMUX_ENV,
        "-i",
        f"HOME={TERMUX_HOME}",
        f"PATH={TERMUX_PREFIX}/bin:/system/bin:/system/xbin",
        f"TMPDIR={TERMUX_TMPDIR}",
        "LANG=C",
        "LC_ALL=C",
        "TZ=UTC",
        f"LD_PRELOAD={TERMUX_EXEC_INTERPOSER}",
        f"TERMUX_EXEC__PROC_SELF_EXE={TERMUX_PYTHON}",
        TERMUX_PYTHON,
        "-I",
        "-S",
        "-B",
        str(remote_script_path),
        "--build-dir",
        str(remote_build_dir),
        "--probe-contract-output",
        str(probe_path),
        "--report",
        str(report_path),
        "--custody-challenge",
        challenge,
    ]


def _validate_remote_inventory(payload: bytes) -> list[str]:
    if len(payload) > 16 * 1024:
        raise AdbCustodyError("remote preflight inventory is oversized")
    try:
        decoded = payload.decode("ascii")
    except UnicodeDecodeError as error:
        raise AdbCustodyError("remote preflight inventory is not ASCII") from error
    if not decoded.endswith("\n") or "\r" in decoded:
        raise AdbCustodyError("remote preflight inventory framing drifted")
    observed = decoded.splitlines()
    if (
        len(observed) != len(set(observed))
        or set(observed) != EXPECTED_REMOTE_TOP_LEVEL
    ):
        raise AdbCustodyError("remote preflight transaction inventory drifted")
    return sorted(observed)


def _write_retrieved_artifacts(stage: Path, artifacts: Mapping[str, bytes]) -> None:
    if set(artifacts) != set(RETRIEVED_ARTIFACT_NAMES):
        raise AdbCustodyError("retrieved artifact allowlist drifted")
    for name in RETRIEVED_ARTIFACT_NAMES:
        contract.write_exclusive(stage / name, artifacts[name])
    contract._fsync_directory(stage)


def _validate_retrieved_transaction(
    stage: Path, artifacts: Mapping[str, bytes], *, expected_challenge: str
) -> tuple[dict[str, Any], str, str]:
    report_raw = artifacts["preflight_report.json"]
    report = contract.strict_json_decode(
        report_raw, source="retrieved:preflight_report.json"
    )
    if contract.canonical_json(report) != report_raw:
        raise AdbCustodyError("retrieved preflight report is not canonical JSON")
    source_revision = report.get("source_revision")
    if not isinstance(source_revision, str) or not SOURCE_REVISION_PATTERN.fullmatch(
        source_revision
    ):
        raise AdbCustodyError("retrieved preflight source revision is invalid")

    report_sha256 = _sha256(report_raw)
    expected_sidecar = f"{report_sha256}  preflight_report.json\n".encode("ascii")
    if artifacts["preflight_report.json.sha256"] != expected_sidecar:
        raise AdbCustodyError("retrieved preflight report sidecar drifted")
    if report.get("custody_challenge") != expected_challenge:
        raise AdbCustodyError("retrieved preflight custody challenge drifted")

    completion_raw = artifacts["PREFLIGHT_COMPLETE.json"]
    completion = contract.strict_json_decode(
        completion_raw, source="retrieved:PREFLIGHT_COMPLETE.json"
    )
    if contract.canonical_json(completion) != completion_raw:
        raise AdbCustodyError("retrieved preflight completion is not canonical JSON")

    opencl_raw = artifacts["opencl_contract.json"]
    opencl_decoded = contract.strict_json_decode(
        opencl_raw, source="retrieved:opencl_contract.json"
    )
    normalized_opencl = contract.normalize_opencl_contract(opencl_decoded)

    local_revision, local_closure = contract.source_closure(ROOT)
    if local_revision != source_revision:
        raise AdbCustodyError(
            "phone preflight revision differs from host source closure"
        )
    contract._validate_source_neutral_preflight(
        report,
        source_revision=local_revision,
        closure=local_closure,
        opencl_raw=opencl_raw,
        opencl=normalized_opencl,
    )
    completion_sha256 = contract._validate_source_neutral_preflight_transaction(
        stage / "preflight_report.json", report_raw, report
    )
    if completion_sha256 != _sha256(completion_raw):
        raise AdbCustodyError("preflight completion validation digest drifted")
    return report, report_sha256, completion_sha256


def _cleanup_owned_stage(stage: Path) -> None:
    if not os.path.lexists(stage):
        return
    try:
        metadata = stage.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISDIR(metadata.st_mode) or stage.is_symlink():
        return
    for name in LOCAL_OUTPUT_NAMES:
        path = stage / name
        if not os.path.lexists(path):
            continue
        try:
            child = path.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISREG(child.st_mode) or stat.S_ISLNK(child.st_mode):
            path.unlink()
    try:
        stage.rmdir()
    except OSError:
        pass


def _publish_local_transaction(
    *,
    output_dir: Path,
    artifacts: Mapping[str, bytes],
    receipt: Mapping[str, Any],
) -> None:
    parent = output_dir.parent
    stage = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=parent))
    os.chmod(stage, 0o700)
    published = False
    try:
        _write_retrieved_artifacts(stage, artifacts)
        validated_report, report_sha256, _ = _validate_retrieved_transaction(
            stage,
            artifacts,
            expected_challenge=str(receipt["custody_challenge"]),
        )
        if (
            receipt.get("source_revision") != validated_report.get("source_revision")
            or receipt.get("artifacts", {})
            .get("preflight_report.json", {})
            .get("sha256")
            != report_sha256
        ):
            raise AdbCustodyError("custody receipt inputs drifted during validation")

        receipt_raw = contract.canonical_json(receipt)
        receipt_sha256 = _sha256(receipt_raw)
        contract.write_exclusive(stage / LOCAL_RECEIPT_NAME, receipt_raw)
        contract.write_exclusive(
            stage / LOCAL_RECEIPT_SIDECAR_NAME,
            f"{receipt_sha256}  {LOCAL_RECEIPT_NAME}\n".encode("ascii"),
        )
        completion = {
            "schema_version": COMPLETION_SCHEMA,
            "state": "complete",
            "receipt_sha256": receipt_sha256,
            "artifact_set_sha256": receipt["artifact_set_sha256"],
            "serial": receipt["serial"],
            "custody_challenge": receipt["custody_challenge"],
            "boot_id": receipt["boot_id_continuity"]["adb_before"],
            "remote_build_directory": receipt["remote_paths"]["build_directory"],
            "source_revision": receipt["source_revision"],
        }
        contract.write_exclusive(
            stage / LOCAL_COMPLETION_NAME, contract.canonical_json(completion)
        )
        if {path.name for path in stage.iterdir()} != LOCAL_OUTPUT_NAMES:
            raise AdbCustodyError("local custody transaction inventory drifted")
        contract._fsync_directory(stage)
        contract._rename_noreplace(stage, output_dir)
        published = True
        contract._fsync_directory(parent)
    finally:
        if not published:
            _cleanup_owned_stage(stage)


def _artifact_receipts(
    *,
    artifacts: Mapping[str, bytes],
    remote_build_dir: PurePosixPath,
    retrieved_at_utc: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "remote_absolute_path": str(remote_build_dir / name),
            "local_filename": name,
            "bytes": len(artifacts[name]),
            "sha256": _sha256(artifacts[name]),
            "retrieved_at_utc": retrieved_at_utc[name],
        }
        for name in RETRIEVED_ARTIFACT_NAMES
    }


def run_custody(
    *,
    remote_repository_root: str,
    remote_build_parent: str,
    local_output_dir: Path,
    runner: RunCallable | None = None,
) -> dict[str, Any]:
    """Execute one fresh ADB-forward-attested SSH custody transaction."""

    _validate_local_output(local_output_dir)
    repository_root = _validate_remote_path(
        remote_repository_root, label="remote repository root"
    )
    build_parent = _validate_remote_path(
        remote_build_parent, label="remote build parent"
    )
    started = _utc_now()
    started_at_utc = _utc_timestamp(started)
    run_id = _utc_run_id(started)
    challenge = secrets.token_hex(CHALLENGE_HEX_BYTES)
    if not CHALLENGE_PATTERN.fullmatch(challenge):
        raise AdbCustodyError("fresh custody challenge generation drifted")
    build_name = (
        f"{run_id}_adreno_preflight_adb_forwarded_ssh_"
        f"{challenge[:CHALLENGE_PREFIX_HEX_CHARS]}"
    )
    remote_build_dir = build_parent / build_name
    remote_script_path = repository_root / PREFLIGHT_RELATIVE_PATH
    probe_path = remote_build_dir / "opencl_contract.json"
    report_path = remote_build_dir / "preflight_report.json"
    blocker_path = remote_build_dir / "PREFLIGHT_BLOCKER.json"

    adb = ExplicitAdbTransport(runner=runner)
    ssh = ForwardedSshTransport(runner=runner)
    state_payload = adb.exact_output(
        ["get-state"],
        operation="ADB get-state",
        timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
    )
    state = _decode_exact_line(
        state_payload, expected="device", operation="ADB get-state"
    )
    serial_payload = adb.exact_output(
        ["get-serialno"],
        operation="ADB get-serialno",
        timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
    )
    serial = _decode_exact_line(
        serial_payload, expected=ADB_SERIAL, operation="ADB get-serialno"
    )
    identity_verified_at_utc = _utc_timestamp()

    forward_argv = [*adb.prefix, "forward", "--list"]
    forward_before = adb.exact_output(
        ["forward", "--list"],
        operation="ADB forward mapping before preflight",
        timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
    )
    _validate_forward_list(forward_before)
    forward_before_observed_at_utc = _utc_timestamp()

    ssh_configuration_before_raw = ssh.resolve_configuration()
    ssh_configuration_before = _validate_ssh_configuration(ssh_configuration_before_raw)
    ssh_key_bindings_before = _verify_ssh_key_bindings(
        ssh, resolved_host=str(ssh_configuration_before["resolved_host"])
    )
    ssh_configuration_before_observed_at_utc = _utc_timestamp()

    adb_boot_before = _read_adb_boot_id(adb)
    adb_boot_before_observed_at_utc = _utc_timestamp()
    ssh_boot_before = _read_ssh_boot_id(ssh)
    ssh_boot_before_observed_at_utc = _utc_timestamp()
    if adb_boot_before != ssh_boot_before:
        raise AdbCustodyError("ADB and forwarded SSH boot_id differ before preflight")

    uid_remote_argv = ["/system/bin/id", "-u"]
    gid_remote_argv = ["/system/bin/id", "-g"]
    uid_before = _decode_remote_identity(
        ssh.exact_remote_output(
            uid_remote_argv,
            operation="forwarded SSH UID before preflight",
            timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
        ),
        expected=REMOTE_UID,
        label="UID",
    )
    gid_before = _decode_remote_identity(
        ssh.exact_remote_output(
            gid_remote_argv,
            operation="forwarded SSH GID before preflight",
            timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
        ),
        expected=REMOTE_GID,
        label="GID",
    )
    remote_identity_before_observed_at_utc = _utc_timestamp()
    transport_before_verified_at_utc = _utc_timestamp()

    ssh.require_remote_zero(
        ["/system/bin/test", "-d", str(build_parent)],
        operation="remote build parent directory check",
        timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
    )
    ssh.require_remote_zero(
        ["/system/bin/test", "!", "-L", str(build_parent)],
        operation="remote build parent symlink rejection",
        timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
    )
    ssh.require_remote_zero(
        ["/system/bin/test", "-f", str(remote_script_path)],
        operation="committed preflight script presence check",
        timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
    )
    ssh.require_remote_zero(
        ["/system/bin/test", "!", "-L", str(remote_script_path)],
        operation="preflight script symlink rejection",
        timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
    )
    ssh.require_remote_zero(
        ["/system/bin/test", "!", "-e", str(remote_build_dir)],
        operation="fresh remote build directory check",
        timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
    )

    remote_argv = _preflight_remote_argv(
        remote_script_path=remote_script_path,
        remote_build_dir=remote_build_dir,
        challenge=challenge,
    )
    launch_argv = [*ssh.command_prefix, *remote_argv]
    preflight_started_at_utc = _utc_timestamp()
    launch = ssh.require_remote_zero(
        remote_argv,
        operation="committed source-neutral Adreno preflight",
        timeout_seconds=PREFLIGHT_TIMEOUT_SECONDS,
    )
    preflight_completed_at_utc = _utc_timestamp()
    if launch.stdout:
        raise AdbCustodyError(
            "committed source-neutral Adreno preflight emitted unexpected stdout"
        )

    retrieval_started_at_utc = _utc_timestamp()
    artifacts: dict[str, bytes] = {}
    retrieved_at_utc: dict[str, str] = {}
    for name in RETRIEVED_ARTIFACT_NAMES:
        payload = ssh.exact_remote_output(
            ["/system/bin/cat", str(remote_build_dir / name)],
            operation=f"exact forwarded SSH retrieval of {name}",
            timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
        )
        if not payload or len(payload) > MAX_ARTIFACT_BYTES[name]:
            raise AdbCustodyError(f"retrieved artifact size is invalid: {name}")
        artifacts[name] = payload
        retrieved_at_utc[name] = _utc_timestamp()
    retrieval_completed_at_utc = _utc_timestamp()

    ssh.require_remote_zero(
        ["/system/bin/test", "!", "-e", str(blocker_path)],
        operation="remote preflight blocker absence check",
        timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
    )
    inventory_payload = ssh.exact_remote_output(
        ["/system/bin/ls", "-1A", str(remote_build_dir)],
        operation="remote preflight transaction inventory",
        timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
    )
    remote_inventory = _validate_remote_inventory(inventory_payload)
    inventory_observed_at_utc = _utc_timestamp()

    uid_after = _decode_remote_identity(
        ssh.exact_remote_output(
            uid_remote_argv,
            operation="forwarded SSH UID after preflight",
            timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
        ),
        expected=REMOTE_UID,
        label="UID",
    )
    gid_after = _decode_remote_identity(
        ssh.exact_remote_output(
            gid_remote_argv,
            operation="forwarded SSH GID after preflight",
            timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
        ),
        expected=REMOTE_GID,
        label="GID",
    )
    remote_identity_after_observed_at_utc = _utc_timestamp()
    ssh_boot_after = _read_ssh_boot_id(ssh)
    ssh_boot_after_observed_at_utc = _utc_timestamp()
    adb_boot_after = _read_adb_boot_id(adb)
    adb_boot_after_observed_at_utc = _utc_timestamp()

    ssh_configuration_after_raw = ssh.resolve_configuration()
    ssh_configuration_after = _validate_ssh_configuration(ssh_configuration_after_raw)
    ssh_key_bindings_after = _verify_ssh_key_bindings(
        ssh, resolved_host=str(ssh_configuration_after["resolved_host"])
    )
    ssh_configuration_after_observed_at_utc = _utc_timestamp()
    forward_after = adb.exact_output(
        ["forward", "--list"],
        operation="ADB forward mapping after preflight",
        timeout_seconds=ADB_CONTROL_TIMEOUT_SECONDS,
    )
    _validate_forward_list(forward_after)
    forward_after_observed_at_utc = _utc_timestamp()

    if (
        forward_after != forward_before
        or ssh_configuration_after_raw != ssh_configuration_before_raw
        or ssh_configuration_after != ssh_configuration_before
        or ssh_key_bindings_after != ssh_key_bindings_before
        or uid_after != uid_before
        or gid_after != gid_before
    ):
        raise AdbCustodyError("ADB-forwarded SSH transport identity changed")
    if len({adb_boot_before, ssh_boot_before, ssh_boot_after, adb_boot_after}) != 1:
        raise AdbCustodyError("cross-channel phone boot_id continuity failed")
    transport_after_verified_at_utc = _utc_timestamp()

    report = contract.strict_json_decode(
        artifacts["preflight_report.json"],
        source="ADB-forwarded-SSH:preflight_report.json",
    )
    source_revision = report.get("source_revision")
    if not isinstance(source_revision, str) or not SOURCE_REVISION_PATTERN.fullmatch(
        source_revision
    ):
        raise AdbCustodyError("forwarded SSH preflight source revision is invalid")
    if report.get("custody_challenge") != challenge:
        raise AdbCustodyError("forwarded SSH preflight custody challenge drifted")

    artifact_receipts = _artifact_receipts(
        artifacts=artifacts,
        remote_build_dir=remote_build_dir,
        retrieved_at_utc=retrieved_at_utc,
    )
    artifact_set_sha256 = _sha256(contract.canonical_json(artifact_receipts))
    sealed_at_utc = _utc_timestamp()
    timestamp_values = [
        started_at_utc,
        identity_verified_at_utc,
        transport_before_verified_at_utc,
        preflight_started_at_utc,
        preflight_completed_at_utc,
        retrieval_started_at_utc,
        retrieval_completed_at_utc,
        inventory_observed_at_utc,
        transport_after_verified_at_utc,
        sealed_at_utc,
    ]
    if timestamp_values != sorted(timestamp_values):
        raise AdbCustodyError("host UTC clock regressed during ADB custody transaction")
    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "state": "complete",
        "serial": serial,
        "custody_challenge": challenge,
        "custody_challenge_generation": {
            "method": "python_secrets.token_hex",
            "entropy_bytes": CHALLENGE_HEX_BYTES,
            "lowercase_hex": True,
            "used_once_for_this_transaction": True,
        },
        "utc_run_id": run_id,
        "source_revision": source_revision,
        "device_identity": {
            "expected_serial": ADB_SERIAL,
            "get_state": state,
            "get_state_stdout_sha256": _sha256(state_payload),
            "get_serialno": serial,
            "get_serialno_stdout_sha256": _sha256(serial_payload),
            "selection": "every_command_uses_explicit_adb_-s_serial",
            "environment_serial_selectors_removed": ["ANDROID_SERIAL", "ADB_SERIAL"],
        },
        "transport_continuity": {
            "adb_forward": {
                "verification_argv": forward_argv,
                "expected_mapping_line": ADB_FORWARD_EXPECTED_LINE,
                "local_spec": ADB_FORWARD_LOCAL,
                "remote_spec": ADB_FORWARD_REMOTE,
                "before_stdout_bytes": len(forward_before),
                "before_stdout_sha256": _sha256(forward_before),
                "after_stdout_bytes": len(forward_after),
                "after_stdout_sha256": _sha256(forward_after),
                "stdout_byte_identical": True,
                "mapping_present_exactly_once_before_and_after": True,
                "before_observed_at_utc": forward_before_observed_at_utc,
                "after_observed_at_utc": forward_after_observed_at_utc,
                "forward_created_or_modified_by_wrapper": False,
            },
            "ssh": {
                "executable": SSH_EXECUTABLE,
                "alias": SSH_ALIAS,
                "configuration_argv": ssh.configuration_argv,
                "required_cli_overrides": list(SSH_REQUIRED_OVERRIDES),
                "command_prefix": ssh.command_prefix,
                "resolved_host": ssh_configuration_before["resolved_host"],
                "resolved_port": ssh_configuration_before["resolved_port"],
                "resolved_user": ssh_configuration_before["resolved_user"],
                "resolved_identity_file": ssh_configuration_before[
                    "resolved_identity_file"
                ],
                "client_public_key_fingerprint": ssh_key_bindings_before[
                    "client_public_key_fingerprint"
                ],
                "resolved_user_known_hosts_file": ssh_configuration_before[
                    "resolved_user_known_hosts_file"
                ],
                "server_host_key_fingerprint": ssh_key_bindings_before[
                    "server_host_key_fingerprint"
                ],
                "effective_configuration": ssh_configuration_before[
                    "effective_configuration"
                ],
                "before_config_stdout_bytes": len(ssh_configuration_before_raw),
                "before_config_stdout_sha256": _sha256(ssh_configuration_before_raw),
                "after_config_stdout_bytes": len(ssh_configuration_after_raw),
                "after_config_stdout_sha256": _sha256(ssh_configuration_after_raw),
                "config_stdout_byte_identical": True,
                "before_observed_at_utc": (ssh_configuration_before_observed_at_utc),
                "after_observed_at_utc": ssh_configuration_after_observed_at_utc,
            },
            "remote_identity": {
                "uid_argv": [*ssh.command_prefix, *uid_remote_argv],
                "gid_argv": [*ssh.command_prefix, *gid_remote_argv],
                "expected_uid": REMOTE_UID,
                "expected_gid": REMOTE_GID,
                "uid_before": uid_before,
                "uid_after": uid_after,
                "gid_before": gid_before,
                "gid_after": gid_after,
                "continuous": True,
                "before_observed_at_utc": remote_identity_before_observed_at_utc,
                "after_observed_at_utc": remote_identity_after_observed_at_utc,
            },
        },
        "boot_id_continuity": {
            "source_absolute_path": BOOT_ID_PATH,
            "adb_before": adb_boot_before,
            "ssh_before": ssh_boot_before,
            "ssh_after": ssh_boot_after,
            "adb_after": adb_boot_after,
            "all_four_equal": True,
            "adb_before_observed_at_utc": adb_boot_before_observed_at_utc,
            "ssh_before_observed_at_utc": ssh_boot_before_observed_at_utc,
            "ssh_after_observed_at_utc": ssh_boot_after_observed_at_utc,
            "adb_after_observed_at_utc": adb_boot_after_observed_at_utc,
        },
        "remote_paths": {
            "repository_root": str(repository_root),
            "preflight_script": str(remote_script_path),
            "build_parent": str(build_parent),
            "build_directory": str(remote_build_dir),
            "probe_contract": str(probe_path),
            "preflight_report": str(report_path),
            "blocker": str(blocker_path),
        },
        "invocation_contract": {
            "ssh_argv": launch_argv,
            "remote_argv": remote_argv,
            "host_shell_used": False,
            "stdin_transport": "DEVNULL",
            "timeout_seconds": PREFLIGHT_TIMEOUT_SECONDS,
            "return_code": launch.returncode,
            "stdout_bytes": len(launch.stdout),
            "stdout_sha256": _sha256(launch.stdout),
            "stderr_bytes": len(launch.stderr),
            "stderr_sha256": _sha256(launch.stderr),
        },
        "retrieval_contract": {
            "method": (
                "verified_explicit_ADB_forward_plus_forwarded_SSH_"
                "/system/bin/cat_exact_path"
            ),
            "ssh_command_prefix": ssh.command_prefix,
            "allowlisted_artifact_names": list(RETRIEVED_ARTIFACT_NAMES),
            "every_retrieval_used_exact_absolute_path": True,
            "blocker_path_absent": True,
            "remote_top_level_inventory": remote_inventory,
            "raw_model_tensor_or_candidate_path_requested": False,
            "scp_used": False,
            "direct_adb_shell_used": False,
        },
        "artifacts": artifact_receipts,
        "artifact_set_sha256": artifact_set_sha256,
        "timestamps": {
            "wrapper_started_at_utc": started_at_utc,
            "device_identity_verified_at_utc": identity_verified_at_utc,
            "transport_before_verified_at_utc": transport_before_verified_at_utc,
            "preflight_started_at_utc": preflight_started_at_utc,
            "preflight_completed_at_utc": preflight_completed_at_utc,
            "retrieval_started_at_utc": retrieval_started_at_utc,
            "retrieval_completed_at_utc": retrieval_completed_at_utc,
            "inventory_observed_at_utc": inventory_observed_at_utc,
            "transport_after_verified_at_utc": transport_after_verified_at_utc,
            "receipt_sealed_at_utc": sealed_at_utc,
        },
        "custody": {
            "source_neutral_artifacts_only": True,
            "retrieval_allowlist_fixed_in_source": True,
            "local_directory_atomic_noreplace_publication": True,
            "raw_model_tensor_or_candidate_data_retrieved": False,
            "termux_execution_via_forwarded_ssh_only": True,
            "direct_adb_shell_used": False,
            "adb_forward_created_or_modified": False,
            "scp_used": False,
        },
        "nonclaims": [
            "no_hardware_attestation",
            "no_resistance_to_malicious_same-UID_compromise",
            "no_kernel_level_ADB_or_SSH_transport_attestation",
            "no_raw_model_tensor_or_candidate_payload_custody_claim",
        ],
    }
    _publish_local_transaction(
        output_dir=local_output_dir, artifacts=artifacts, receipt=receipt
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote-repository-root", required=True)
    parser.add_argument("--remote-build-parent", required=True)
    parser.add_argument("--local-output-dir", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_custody(
        remote_repository_root=args.remote_repository_root,
        remote_build_parent=args.remote_build_parent,
        local_output_dir=args.local_output_dir,
    )
    print(contract.canonical_json(receipt).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

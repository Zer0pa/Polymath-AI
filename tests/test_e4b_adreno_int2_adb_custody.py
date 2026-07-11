from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
WRAPPER_PATH = ROOT / "scripts/host/run_e4b_adreno_int2_preflight_via_adb.py"
SPEC = importlib.util.spec_from_file_location(
    "_test_e4b_adreno_int2_adb_custody", WRAPPER_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load ADB-forwarded SSH custody wrapper")
custody = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = custody
SPEC.loader.exec_module(custody)

REMOTE_REPOSITORY = f"{custody.TERMUX_HOME}/polymath-source"
REMOTE_BUILD_PARENT = f"{custody.TERMUX_HOME}/polymath-preflight-builds"
SOURCE_REVISION = "1" * 40
BINARY_SHA256 = "d" * 64
DEFAULT_CHALLENGE = "ab" * custody.CHALLENGE_HEX_BYTES
BOOT_ID_A = "11111111-2222-3333-4444-555555555555"
BOOT_ID_B = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def preflight_artifacts(*, challenge: str = DEFAULT_CHALLENGE) -> dict[str, bytes]:
    opencl_raw = custody.contract.canonical_json(
        {"synthetic_opencl_contract": True, "custody_challenge": challenge}
    )
    report = {
        "schema_version": custody.contract.SOURCE_NEUTRAL_PREFLIGHT_SCHEMA,
        "state": "passed_scope",
        "source_revision": SOURCE_REVISION,
        "custody_challenge": challenge,
        "build": {"first": {"binary_sha256": BINARY_SHA256}},
        "probe": {"contract_sha256": _sha256(opencl_raw)},
    }
    report_raw = custody.contract.canonical_json(report)
    report_sha256 = _sha256(report_raw)
    completion = {
        "schema_version": custody.contract.SOURCE_NEUTRAL_PREFLIGHT_COMPLETION_SCHEMA,
        "state": "complete",
        "report_sha256": report_sha256,
        "source_revision": SOURCE_REVISION,
        "binary_sha256": BINARY_SHA256,
        "contract_sha256": _sha256(opencl_raw),
        "custody_challenge": challenge,
    }
    return {
        "preflight_report.json": report_raw,
        "preflight_report.json.sha256": (
            f"{report_sha256}  preflight_report.json\n".encode("ascii")
        ),
        "PREFLIGHT_COMPLETE.json": custody.contract.canonical_json(completion),
        "opencl_contract.json": opencl_raw,
    }


def effective_ssh_configuration(*, batch_mode: str = "yes") -> bytes:
    fields = [
        f"user {custody.SSH_RESOLVED_USER}",
        "hostname 127.0.0.1",
        f"port {custody.SSH_RESOLVED_PORT}",
        f"batchmode {batch_mode}",
        "identitiesonly yes",
        "kbdinteractiveauthentication no",
        "passwordauthentication no",
        "requesttty false",
        "stricthostkeychecking true",
        "numberofpasswordprompts 0",
        "canonicalizehostname false",
        "permitlocalcommand no",
        "proxyusefdpass no",
        "controlmaster false",
        "controlpersist no",
        "forwardagent no",
        "forwardx11 no",
        "identityfile ~/.ssh/polymath_host",
        (
            "userknownhostsfile "
            f"{custody.SSH_RESOLVED_USER_KNOWN_HOSTS_FILE} "
            "/Users/prinivenpillay/.ssh/known_hosts2"
        ),
    ]
    return ("\n".join(fields) + "\n").encode("utf-8")


class FakeTransports:
    def __init__(
        self,
        *,
        artifacts: dict[str, bytes] | None = None,
        state: str = "device",
        serial: str = custody.ADB_SERIAL,
        adb_boot_ids: tuple[str, str] = (BOOT_ID_A, BOOT_ID_A),
        ssh_boot_ids: tuple[str, str] = (BOOT_ID_A, BOOT_ID_A),
        forward_payloads: tuple[bytes, bytes] | None = None,
        ssh_config_payloads: tuple[bytes, bytes] | None = None,
        uid_values: tuple[int, int] = (custody.REMOTE_UID, custody.REMOTE_UID),
        gid_values: tuple[int, int] = (custody.REMOTE_GID, custody.REMOTE_GID),
        client_fingerprint: str = custody.SSH_CLIENT_PUBLIC_KEY_FINGERPRINT,
        server_fingerprint: str = custody.SSH_SERVER_HOST_KEY_FINGERPRINT,
        inventory: set[str] | None = None,
    ) -> None:
        self.artifacts = artifacts or preflight_artifacts()
        self.state = state
        self.serial = serial
        self.adb_boot_ids = adb_boot_ids
        self.ssh_boot_ids = ssh_boot_ids
        default_forward = f"{custody.ADB_FORWARD_EXPECTED_LINE}\n\n".encode("ascii")
        self.forward_payloads = forward_payloads or (default_forward, default_forward)
        default_config = effective_ssh_configuration()
        self.ssh_config_payloads = ssh_config_payloads or (
            default_config,
            default_config,
        )
        self.uid_values = uid_values
        self.gid_values = gid_values
        self.client_fingerprint = client_fingerprint
        self.server_fingerprint = server_fingerprint
        self.inventory = inventory or set(custody.EXPECTED_REMOTE_TOP_LEVEL)
        self.calls: list[list[str]] = []
        self.adb_boot_reads = 0
        self.ssh_boot_reads = 0
        self.forward_reads = 0
        self.ssh_config_reads = 0
        self.uid_reads = 0
        self.gid_reads = 0

    @staticmethod
    def _result(
        argv: list[str],
        *,
        returncode: int = 0,
        stdout: bytes = b"",
        stderr: bytes = b"",
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)

    def _adb(self, observed: list[str]) -> subprocess.CompletedProcess[bytes]:
        assert observed[:3] == [custody.ADB_EXECUTABLE, "-s", custody.ADB_SERIAL]
        tail = observed[3:]
        assert "shell" not in tail
        if tail == ["get-state"]:
            return self._result(observed, stdout=f"{self.state}\n".encode("ascii"))
        if tail == ["get-serialno"]:
            return self._result(observed, stdout=f"{self.serial}\n".encode("ascii"))
        if tail == ["forward", "--list"]:
            payload = self.forward_payloads[self.forward_reads]
            self.forward_reads += 1
            return self._result(observed, stdout=payload)
        if tail == ["exec-out", "/system/bin/cat", custody.BOOT_ID_PATH]:
            boot_id = self.adb_boot_ids[self.adb_boot_reads]
            self.adb_boot_reads += 1
            return self._result(observed, stdout=f"{boot_id}\n".encode("ascii"))
        raise AssertionError(f"unexpected ADB invocation: {observed}")

    def _ssh(self, observed: list[str]) -> subprocess.CompletedProcess[bytes]:
        configuration_argv = [
            custody.SSH_EXECUTABLE,
            "-G",
            *custody.SSH_REQUIRED_OVERRIDES,
            custody.SSH_ALIAS,
        ]
        if observed == configuration_argv:
            payload = self.ssh_config_payloads[self.ssh_config_reads]
            self.ssh_config_reads += 1
            return self._result(observed, stdout=payload)
        prefix = [
            custody.SSH_EXECUTABLE,
            *custody.SSH_REQUIRED_OVERRIDES,
            custody.SSH_ALIAS,
            "--",
        ]
        assert observed[: len(prefix)] == prefix
        remote = observed[len(prefix) :]
        if remote == ["/system/bin/cat", custody.BOOT_ID_PATH]:
            boot_id = self.ssh_boot_ids[self.ssh_boot_reads]
            self.ssh_boot_reads += 1
            return self._result(observed, stdout=f"{boot_id}\n".encode("ascii"))
        if remote == ["/system/bin/id", "-u"]:
            value = self.uid_values[self.uid_reads]
            self.uid_reads += 1
            return self._result(observed, stdout=f"{value}\n".encode("ascii"))
        if remote == ["/system/bin/id", "-g"]:
            value = self.gid_values[self.gid_reads]
            self.gid_reads += 1
            return self._result(observed, stdout=f"{value}\n".encode("ascii"))
        if remote[:1] == ["/system/bin/test"]:
            return self._result(observed)
        if remote[:1] == [custody.TERMUX_ENV]:
            return self._result(observed)
        if remote[:1] == ["/system/bin/cat"]:
            name = Path(remote[-1]).name
            if name in self.artifacts:
                return self._result(observed, stdout=self.artifacts[name])
        if remote[:2] == ["/system/bin/ls", "-1A"]:
            payload = ("\n".join(sorted(self.inventory)) + "\n").encode("ascii")
            return self._result(observed, stdout=payload)
        raise AssertionError(f"unexpected forwarded SSH invocation: {observed}")

    def _ssh_keygen(self, observed: list[str]) -> subprocess.CompletedProcess[bytes]:
        if observed[1:3] == ["-lf", f"{custody.SSH_RESOLVED_IDENTITY_FILE}.pub"]:
            payload = (
                "256 "
                f"{self.client_fingerprint} "
                "polymath-codex-host-20260629 (ED25519)\n"
            ).encode("utf-8")
            return self._result(observed, stdout=payload)
        if observed[1:3] == [
            "-lf",
            custody.SSH_RESOLVED_USER_KNOWN_HOSTS_FILE,
        ]:
            payload = (
                "256 "
                f"{self.server_fingerprint} "
                f"[127.0.0.1]:{custody.SSH_RESOLVED_PORT} (ED25519)\n"
            ).encode("utf-8")
            return self._result(observed, stdout=payload)
        raise AssertionError(f"unexpected ssh-keygen invocation: {observed}")

    def __call__(
        self, argv: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[bytes]:
        observed = list(argv)
        self.calls.append(observed)
        assert kwargs["check"] is False
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert kwargs["stdout"] is subprocess.PIPE
        assert kwargs["stderr"] is subprocess.PIPE
        if observed[0] == custody.ADB_EXECUTABLE:
            assert "ANDROID_SERIAL" not in kwargs["env"]
            assert "ADB_SERIAL" not in kwargs["env"]
            return self._adb(observed)
        if observed[0] == custody.SSH_EXECUTABLE:
            assert "SSH_ASKPASS" not in kwargs["env"]
            assert "SSH_ASKPASS_REQUIRE" not in kwargs["env"]
            return self._ssh(observed)
        if observed[0] == custody.SSH_KEYGEN_EXECUTABLE:
            return self._ssh_keygen(observed)
        raise AssertionError(f"unexpected host executable: {observed}")


def patch_semantic_preflight_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        custody.contract,
        "normalize_opencl_contract",
        lambda payload: payload,
    )
    monkeypatch.setattr(
        custody.contract,
        "source_closure",
        lambda root: (SOURCE_REVISION, []),
    )
    monkeypatch.setattr(
        custody.contract,
        "_validate_source_neutral_preflight",
        lambda payload, **kwargs: (123_456, BINARY_SHA256),
    )


def run_with_fake(tmp_path: Path, fake: FakeTransports) -> Path:
    output = tmp_path / "custody"
    custody.run_custody(
        remote_repository_root=REMOTE_REPOSITORY,
        remote_build_parent=REMOTE_BUILD_PARENT,
        local_output_dir=output,
        runner=fake,
    )
    return output


@pytest.mark.parametrize(
    ("state", "serial", "message"),
    [
        ("offline", custody.ADB_SERIAL, "get-state identity drifted"),
        ("device", "WRONG-SERIAL", "get-serialno identity drifted"),
    ],
)
def test_wrong_state_or_serial_fails_closed(
    tmp_path: Path, state: str, serial: str, message: str
) -> None:
    fake = FakeTransports(state=state, serial=serial)
    with pytest.raises(custody.AdbCustodyError, match=message):
        run_with_fake(tmp_path, fake)
    assert not (tmp_path / "custody").exists()
    assert all(
        call[:3] == [custody.ADB_EXECUTABLE, "-s", custody.ADB_SERIAL]
        for call in fake.calls
        if call[0] == custody.ADB_EXECUTABLE
    )


@pytest.mark.parametrize(
    "forward_payload",
    [
        b"OTHER-SERIAL tcp:18022 tcp:8022\n",
        f"{custody.ADB_SERIAL} tcp:18022 tcp:9999\n".encode("ascii"),
    ],
)
def test_missing_or_wrong_adb_forward_fails_closed(
    tmp_path: Path, forward_payload: bytes
) -> None:
    fake = FakeTransports(forward_payloads=(forward_payload, forward_payload))
    with pytest.raises(custody.AdbCustodyError, match="required ADB forward mapping"):
        run_with_fake(tmp_path, fake)
    assert fake.forward_reads == 1
    assert not (tmp_path / "custody").exists()


def test_ssh_effective_configuration_drift_fails_before_connection(
    tmp_path: Path,
) -> None:
    unsafe = effective_ssh_configuration(batch_mode="no")
    fake = FakeTransports(ssh_config_payloads=(unsafe, unsafe))
    with pytest.raises(custody.AdbCustodyError, match="configuration is unsafe"):
        run_with_fake(tmp_path, fake)
    assert fake.ssh_config_reads == 1
    assert fake.ssh_boot_reads == 0
    assert not (tmp_path / "custody").exists()


def test_cross_channel_boot_mismatch_fails_before_preflight(tmp_path: Path) -> None:
    fake = FakeTransports(
        adb_boot_ids=(BOOT_ID_A, BOOT_ID_A),
        ssh_boot_ids=(BOOT_ID_B, BOOT_ID_B),
    )
    with pytest.raises(custody.AdbCustodyError, match="differ before preflight"):
        run_with_fake(tmp_path, fake)
    assert fake.adb_boot_reads == 1
    assert fake.ssh_boot_reads == 1
    assert not (tmp_path / "custody").exists()


def test_wrong_forwarded_ssh_uid_fails_before_preflight(tmp_path: Path) -> None:
    fake = FakeTransports(uid_values=(2_000, 2_000))
    with pytest.raises(custody.AdbCustodyError, match="remote UID drifted"):
        run_with_fake(tmp_path, fake)
    assert fake.uid_reads == 1
    assert not (tmp_path / "custody").exists()


def test_ssh_server_host_key_fingerprint_drift_fails_closed(tmp_path: Path) -> None:
    fake = FakeTransports(server_fingerprint="SHA256:" + "A" * 43)
    with pytest.raises(custody.AdbCustodyError, match="server host-key fingerprint"):
        run_with_fake(tmp_path, fake)
    assert fake.ssh_boot_reads == 0
    assert not (tmp_path / "custody").exists()


def test_forward_mapping_drift_after_retrieval_is_not_publishable(
    tmp_path: Path,
) -> None:
    valid = f"{custody.ADB_FORWARD_EXPECTED_LINE}\n".encode("ascii")
    drifted = valid + b"OTHER-SERIAL tcp:19000 tcp:9000\n"
    fake = FakeTransports(forward_payloads=(valid, drifted))
    with pytest.raises(custody.AdbCustodyError, match="transport identity changed"):
        run_with_fake(tmp_path, fake)
    assert fake.forward_reads == 2
    assert not (tmp_path / "custody").exists()


def test_stale_local_output_collision_is_never_replaced(tmp_path: Path) -> None:
    output = tmp_path / "custody"
    output.mkdir()
    marker = output / "owner.txt"
    marker.write_text("preserve", encoding="utf-8")

    def transport_must_not_run(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("transport must not run after a local collision")

    with pytest.raises(custody.AdbCustodyError, match="already exists"):
        custody.run_custody(
            remote_repository_root=REMOTE_REPOSITORY,
            remote_build_parent=REMOTE_BUILD_PARENT,
            local_output_dir=output,
            runner=transport_must_not_run,
        )
    assert marker.read_text(encoding="utf-8") == "preserve"
    assert {path.name for path in output.iterdir()} == {"owner.txt"}


def test_report_sidecar_hash_mismatch_leaves_no_local_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(custody.secrets, "token_hex", lambda length: DEFAULT_CHALLENGE)
    artifacts = preflight_artifacts()
    artifacts["preflight_report.json.sha256"] = (
        f"{'0' * 64}  preflight_report.json\n".encode("ascii")
    )
    fake = FakeTransports(artifacts=artifacts)
    with pytest.raises(custody.AdbCustodyError, match="sidecar drifted"):
        run_with_fake(tmp_path, fake)
    assert list(tmp_path.iterdir()) == []


def test_success_publishes_forwarded_ssh_uid_and_key_bound_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_semantic_preflight_validation(monkeypatch)
    challenge = DEFAULT_CHALLENGE
    monkeypatch.setattr(custody.secrets, "token_hex", lambda length: challenge)
    artifacts = preflight_artifacts()
    fake = FakeTransports(artifacts=artifacts)
    output = tmp_path / "custody"

    returned = custody.run_custody(
        remote_repository_root=REMOTE_REPOSITORY,
        remote_build_parent=REMOTE_BUILD_PARENT,
        local_output_dir=output,
        runner=fake,
    )

    assert output.is_dir() and not output.is_symlink()
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert {path.name for path in output.iterdir()} == custody.LOCAL_OUTPUT_NAMES
    receipt_raw = (output / custody.LOCAL_RECEIPT_NAME).read_bytes()
    receipt = json.loads(receipt_raw)
    assert receipt == returned
    assert receipt_raw == custody.contract.canonical_json(receipt)
    receipt_sha256 = _sha256(receipt_raw)
    assert (output / custody.LOCAL_RECEIPT_SIDECAR_NAME).read_bytes() == (
        f"{receipt_sha256}  {custody.LOCAL_RECEIPT_NAME}\n".encode("ascii")
    )

    completion = json.loads((output / custody.LOCAL_COMPLETION_NAME).read_bytes())
    assert completion["schema_version"] == custody.COMPLETION_SCHEMA
    assert completion["receipt_sha256"] == receipt_sha256
    assert completion["custody_challenge"] == challenge
    assert completion["boot_id"] == BOOT_ID_A

    assert receipt["schema_version"] == custody.RECEIPT_SCHEMA
    assert receipt["state"] == "complete"
    assert receipt["serial"] == custody.ADB_SERIAL
    assert receipt["source_revision"] == SOURCE_REVISION
    assert receipt["boot_id_continuity"] == {
        **receipt["boot_id_continuity"],
        "adb_before": BOOT_ID_A,
        "ssh_before": BOOT_ID_A,
        "ssh_after": BOOT_ID_A,
        "adb_after": BOOT_ID_A,
        "all_four_equal": True,
    }
    assert receipt["remote_paths"]["build_directory"].endswith(
        "_adreno_preflight_adb_forwarded_ssh_"
        f"{challenge[: custody.CHALLENGE_PREFIX_HEX_CHARS]}"
    )
    assert receipt["artifact_set_sha256"] == _sha256(
        custody.contract.canonical_json(receipt["artifacts"])
    )
    for name, payload in artifacts.items():
        assert (output / name).read_bytes() == payload
        assert receipt["artifacts"][name]["bytes"] == len(payload)
        assert receipt["artifacts"][name]["sha256"] == _sha256(payload)

    transport = receipt["transport_continuity"]
    assert transport["adb_forward"]["expected_mapping_line"] == (
        custody.ADB_FORWARD_EXPECTED_LINE
    )
    assert transport["adb_forward"]["stdout_byte_identical"] is True
    assert transport["ssh"]["alias"] == custody.SSH_ALIAS
    assert transport["ssh"]["resolved_host"] == "127.0.0.1"
    assert transport["ssh"]["resolved_port"] == custody.SSH_RESOLVED_PORT
    assert transport["ssh"]["resolved_user"] == custody.SSH_RESOLVED_USER
    assert transport["ssh"]["resolved_identity_file"] == (
        custody.SSH_RESOLVED_IDENTITY_FILE
    )
    assert transport["ssh"]["client_public_key_fingerprint"] == (
        custody.SSH_CLIENT_PUBLIC_KEY_FINGERPRINT
    )
    assert transport["ssh"]["server_host_key_fingerprint"] == (
        custody.SSH_SERVER_HOST_KEY_FINGERPRINT
    )
    assert transport["remote_identity"] == {
        **transport["remote_identity"],
        "expected_uid": custody.REMOTE_UID,
        "expected_gid": custody.REMOTE_GID,
        "uid_before": custody.REMOTE_UID,
        "uid_after": custody.REMOTE_UID,
        "gid_before": custody.REMOTE_GID,
        "gid_after": custody.REMOTE_GID,
        "continuous": True,
    }

    invocation = receipt["invocation_contract"]
    assert (
        invocation["ssh_argv"][: len(transport["ssh"]["command_prefix"])]
        == (transport["ssh"]["command_prefix"])
    )
    assert invocation["remote_argv"][:2] == [custody.TERMUX_ENV, "-i"]
    assert invocation["stdin_transport"] == "DEVNULL"
    challenge_index = invocation["remote_argv"].index("--custody-challenge")
    assert invocation["remote_argv"][challenge_index + 1] == challenge

    ssh_prefix = transport["ssh"]["command_prefix"]
    retrieved_names = {
        Path(call[-1]).name
        for call in fake.calls
        if call[: len(ssh_prefix)] == ssh_prefix
        and call[len(ssh_prefix) : len(ssh_prefix) + 1] == ["/system/bin/cat"]
        and call[-1] != custody.BOOT_ID_PATH
    }
    assert retrieved_names == set(custody.RETRIEVED_ARTIFACT_NAMES)
    adb_calls = [call for call in fake.calls if call[0] == custody.ADB_EXECUTABLE]
    assert all(
        call[:3] == [custody.ADB_EXECUTABLE, "-s", custody.ADB_SERIAL]
        and "shell" not in call[3:]
        for call in adb_calls
    )
    assert fake.forward_reads == 2
    assert fake.ssh_config_reads == 2
    assert fake.uid_reads == 2 and fake.gid_reads == 2
    assert not any(call[0] == "scp" for call in fake.calls)
    assert receipt["retrieval_contract"]["direct_adb_shell_used"] is False
    assert receipt["retrieval_contract"]["scp_used"] is False
    assert receipt["custody"]["termux_execution_via_forwarded_ssh_only"] is True
    assert "no_hardware_attestation" in receipt["nonclaims"]
    assert "no_resistance_to_malicious_same-UID_compromise" in receipt["nonclaims"]

    admitted = custody.contract._validate_adb_custody_receipt_transaction(
        output / custody.LOCAL_RECEIPT_NAME,
        preflight_report_path=output / "preflight_report.json",
        preflight_report_raw=artifacts["preflight_report.json"],
        preflight_report=json.loads(artifacts["preflight_report.json"]),
        opencl_contract_path=output / "opencl_contract.json",
        opencl_contract_raw=artifacts["opencl_contract.json"],
        preflight_completion_sha256=_sha256(artifacts["PREFLIGHT_COMPLETE.json"]),
        source_revision=SOURCE_REVISION,
    )
    assert admitted == {
        "schema_version": custody.RECEIPT_SCHEMA,
        "receipt_sha256": receipt_sha256,
        "completion_sha256": _sha256(
            (output / custody.LOCAL_COMPLETION_NAME).read_bytes()
        ),
        "artifact_set_sha256": receipt["artifact_set_sha256"],
        "serial": custody.ADB_SERIAL,
        "transport": "explicit_ADB_forward_plus_forwarded_SSH",
        "custody_challenge": challenge,
        "boot_id": BOOT_ID_A,
        "remote_build_directory": receipt["remote_paths"]["build_directory"],
        "source_revision": SOURCE_REVISION,
        "hardware_attestation": False,
        "direct_adb_shell_used": False,
    }

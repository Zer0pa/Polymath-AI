from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace

import pytest

from polymath_ai.corpus.cur0s_static import StageLock


RUNNER_PATH = (
    Path(__file__).resolve().parents[1] / "scripts/termux/run_cur0s_static_identity.py"
)
BUILDER_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts/host/build_cur0s_static_preregistration.py"
)
RUN_ID = "20260711T220000Z_cur0s_static_identity_v1"


@pytest.fixture
def runner():
    spec = importlib.util.spec_from_file_location("cur0s_static_runner_test", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def builder():
    spec = importlib.util.spec_from_file_location("cur0s_static_builder_test", BUILDER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_fixture(root: Path) -> tuple[StageLock, dict]:
    master = {
        "instruction": "Define force.",
        "input": "",
        "output": "Force changes momentum.",
        "metadata": {
            "record_id": "row-1",
            "phase": 1,
            "dataset_id": "fixture/source",
            "dataset_revision": "fixture-revision",
            "source_local_id": "one",
            "split": "train",
        },
    }
    master_bytes = canonical_line(master)
    qa_bytes = b'{"record_id":"row-1"}\n'
    manifest_bytes = b'{"status":"fixture"}\n'
    stage_root = root / "C1"
    (stage_root / "qa_bridge").mkdir(parents=True)
    (stage_root / "phase_C1_full.jsonl").write_bytes(master_bytes)
    (stage_root / "qa_bridge/phase_C1_full.qa.jsonl").write_bytes(qa_bytes)
    (stage_root / "phase_C1_build_manifest.json").write_bytes(manifest_bytes)
    lock = StageLock(
        stage="C1",
        directory="C1",
        phase_filename="C1",
        rows=1,
        master_sha256=sha(master_bytes),
        qa_sha256=sha(qa_bytes),
        manifest_sha256=sha(manifest_bytes),
    )
    return lock, master


def test_source_snapshot_pins_old_bytes_and_invalidates_path_replacement(
    runner, tmp_path, monkeypatch
) -> None:
    lock, master = write_fixture(tmp_path)
    monkeypatch.setattr(runner, "STAGE_LOCKS", (lock,))
    monkeypatch.setattr(runner, "TOTAL_ROWS", 1)
    monkeypatch.setattr(runner, "PHONE_HOME", tmp_path.parent)
    monkeypatch.setattr(runner, "PHONE_SOURCE_ROOT", tmp_path)
    monkeypatch.setattr(runner, "PHONE_SOURCE_ROOT_RELATIVE", tmp_path.name)
    snapshot = runner.SourceSnapshot.open(tmp_path)
    try:
        first = snapshot.verify()
        assert first["passed"] is True

        master_path = tmp_path / lock.master_relative_path
        old_path = master_path.with_suffix(".old")
        master_path.rename(old_path)
        master_path.write_bytes(canonical_line({**master, "output": "replacement"}))

        parsed = list(runner.iter_master_records(snapshot))
        assert parsed == [("C1", master)]
        with pytest.raises(runner.Cur0sExactError, match="stat_changed"):
            snapshot.verify()
    finally:
        snapshot.close()


def test_source_snapshot_detects_in_place_mutation(runner, tmp_path, monkeypatch) -> None:
    lock, _ = write_fixture(tmp_path)
    monkeypatch.setattr(runner, "STAGE_LOCKS", (lock,))
    monkeypatch.setattr(runner, "TOTAL_ROWS", 1)
    monkeypatch.setattr(runner, "PHONE_HOME", tmp_path.parent)
    monkeypatch.setattr(runner, "PHONE_SOURCE_ROOT", tmp_path)
    monkeypatch.setattr(runner, "PHONE_SOURCE_ROOT_RELATIVE", tmp_path.name)
    snapshot = runner.SourceSnapshot.open(tmp_path)
    try:
        assert snapshot.verify()["passed"] is True
        with (tmp_path / lock.master_relative_path).open("ab") as handle:
            handle.write(b"tamper\n")
            handle.flush()
            os.fsync(handle.fileno())
        with pytest.raises(runner.Cur0sExactError, match="stat_changed"):
            snapshot.verify()
    finally:
        snapshot.close()


def test_open_beneath_rejects_symlink_component(runner, tmp_path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "file").write_text("content")
    (tmp_path / "link").symlink_to(real, target_is_directory=True)
    root_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(OSError):
            runner.open_regular_beneath(root_fd, "link/file")
    finally:
        os.close(root_fd)


def test_exclusive_publish_cannot_overwrite(runner, tmp_path) -> None:
    target = tmp_path / "receipt.json"
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        first = runner.write_exclusive_bytes_at(directory_fd, target.name, b"first\n")
        assert first == ("sha256:" + sha(b"first\n"), 6)
        with pytest.raises(FileExistsError):
            runner.write_exclusive_bytes_at(directory_fd, target.name, b"second\n")
    finally:
        os.close(directory_fd)
    assert target.read_bytes() == b"first\n"


def test_stat_identity_includes_ownership_and_link_count(runner, tmp_path) -> None:
    target = tmp_path / "artifact"
    target.write_text("x")
    identity = runner.stat_identity(target.stat())
    assert len(identity) == 9
    assert identity[3] == 1
    assert identity[5] == os.geteuid()


def test_builder_lease_round_trips_runner_strict_validation(runner, builder) -> None:
    issued = datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc)
    lease_dict = builder.build_campaign_lease(RUN_ID, issued)
    lease = runner.validate_campaign_lease(
        {"run_id": RUN_ID, "campaign_lease": lease_dict},
        now=issued + timedelta(hours=1),
    )
    assert lease.action_id == RUN_ID
    assert lease.expires_at - lease.issued_at == timedelta(hours=4)
    assert lease.max_private_output_bytes == 256 * 1024 * 1024


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda lease: lease.pop("max_wall_seconds"), "field_set"),
        (lambda lease: lease.__setitem__("unexpected", 1), "field_set"),
        (lambda lease: lease.__setitem__("max_wall_seconds", True), "max_wall"),
        (lambda lease: lease.__setitem__("action_id", "wrong"), "action"),
        (lambda lease: lease.__setitem__("issued_at_utc", "not-a-time"), "issued_at"),
    ],
)
def test_campaign_lease_rejects_malformed_authority(
    runner, builder, mutation, message: str
) -> None:
    issued = datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc)
    lease = builder.build_campaign_lease(RUN_ID, issued)
    mutation(lease)
    with pytest.raises(runner.Cur0sExactError, match=message):
        runner.validate_campaign_lease(
            {"run_id": RUN_ID, "campaign_lease": lease},
            now=issued + timedelta(hours=1),
        )


def test_campaign_lease_rejects_future_expired_and_overlong(runner, builder) -> None:
    issued = datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc)
    base = builder.build_campaign_lease(RUN_ID, issued)
    with pytest.raises(runner.Cur0sExactError, match="not_yet_active"):
        runner.validate_campaign_lease(
            {"run_id": RUN_ID, "campaign_lease": base},
            now=issued - timedelta(seconds=1),
        )
    with pytest.raises(runner.Cur0sExactError, match="expired"):
        runner.validate_campaign_lease(
            {"run_id": RUN_ID, "campaign_lease": base},
            now=issued + timedelta(hours=4),
        )
    overlong = copy.deepcopy(base)
    overlong["expires_at_utc"] = "2026-07-12T00:00:01Z"
    with pytest.raises(runner.Cur0sExactError, match="exceeds_four_hours"):
        runner.validate_campaign_lease(
            {"run_id": RUN_ID, "campaign_lease": overlong},
            now=issued + timedelta(hours=1),
        )


def test_resource_envelope_temperature_threshold_is_exact(runner, tmp_path) -> None:
    now = datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc)
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        passing = make_envelope(
            runner,
            directory_fd,
            now,
            temperatures=[84_999],
            free_bytes=10_737_418_240,
        )
        passing.check("thermal_boundary")
        failing = make_envelope(
            runner,
            directory_fd,
            now,
            temperatures=[85_000],
            free_bytes=10_737_418_240,
        )
        with pytest.raises(runner.OperationalStop, match="thermal_ceiling"):
            failing.check("thermal_boundary")
    finally:
        os.close(directory_fd)


def test_resource_envelope_storage_floor_and_sensor_availability(runner, tmp_path) -> None:
    now = datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc)
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        make_envelope(
            runner,
            directory_fd,
            now,
            temperatures=[40_000],
            free_bytes=10_737_418_240,
        ).check("storage_boundary")
        with pytest.raises(runner.OperationalStop, match="storage_floor"):
            make_envelope(
                runner,
                directory_fd,
                now,
                temperatures=[40_000],
                free_bytes=10_737_418_239,
            ).check("storage_boundary")
        with pytest.raises(runner.OperationalStop, match="sensor_unavailable"):
            make_envelope(
                runner,
                directory_fd,
                now,
                temperatures=[],
                free_bytes=10_737_418_240,
            ).check("thermal_availability")
    finally:
        os.close(directory_fd)


def test_resource_envelope_wall_and_midrun_lease_expiry(runner, tmp_path) -> None:
    now = datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc)
    monotonic = [0.0]
    wall_clock = [now]
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        envelope = make_envelope(
            runner,
            directory_fd,
            now,
            temperatures=[40_000],
            free_bytes=10_737_418_240,
            monotonic=monotonic,
            wall_clock=wall_clock,
        )
        monotonic[0] = 1_799.999
        envelope.check("wall_boundary")
        monotonic[0] = 1_800.0
        with pytest.raises(runner.OperationalStop, match="wall_time"):
            envelope.check("wall_boundary")

        monotonic[0] = 0.0
        expired = make_envelope(
            runner,
            directory_fd,
            now,
            temperatures=[40_000],
            free_bytes=10_737_418_240,
            monotonic=monotonic,
            wall_clock=wall_clock,
        )
        wall_clock[0] = now + timedelta(hours=4)
        with pytest.raises(runner.OperationalStop, match="expired_mid_execution"):
            expired.check("lease_boundary")
        with pytest.raises(runner.OperationalStop, match="alarm"):
            expired._handle_alarm(0, None)
    finally:
        os.close(directory_fd)


def test_private_output_budget_reserves_terminal_evidence(runner, tmp_path) -> None:
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    output = runner.PrivateOutput(
        directory_fd,
        runner.PrivateOutput.DATA_CONTROL_RESERVE_BYTES + 10,
    )
    try:
        output._reserve_data_bytes(10)
        assert output.bytes_written == 10
        with pytest.raises(runner.OperationalStop, match="data_budget"):
            output._reserve_data_bytes(1)
    finally:
        output.close()


def test_completion_marker_is_exclusive_read_only_and_last(runner, tmp_path) -> None:
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    output = runner.PrivateOutput(directory_fd, 8 * 1024 * 1024)
    receipt = {"state": "blocked_fail_closed", "evidence": "aggregate-only"}
    receipt["receipt_root_sha256"] = runner.canonical_sha256(receipt)
    try:
        runner.finalize_output(output, RUN_ID, receipt)
        assert stat.S_IMODE((tmp_path / "receipt.json").stat().st_mode) == 0o400
        assert stat.S_IMODE((tmp_path / "COMPLETE.json").stat().st_mode) == 0o400
        complete = json.loads((tmp_path / "COMPLETE.json").read_bytes())
        assert complete["completion_protocol"].endswith("O_EXCL_fsync_last")
        with pytest.raises(runner.Cur0sExactError, match="sealed"):
            output.write_receipt("after.json", {"forbidden": True})
    finally:
        output.close()


def test_seal_failure_never_exposes_complete_marker(
    runner, tmp_path, monkeypatch
) -> None:
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    output = runner.PrivateOutput(directory_fd, 8 * 1024 * 1024)
    receipt = {"state": "blocked_fail_closed"}
    receipt["receipt_root_sha256"] = runner.canonical_sha256(receipt)

    def fail_seal(_fd: int, _mode: int) -> None:
        raise OSError("synthetic_seal_failure")

    monkeypatch.setattr(runner.os, "fchmod", fail_seal)
    try:
        with pytest.raises(OSError, match="synthetic_seal_failure"):
            runner.finalize_output(output, RUN_ID, receipt)
        assert not (tmp_path / "COMPLETE.json").exists()
    finally:
        output.close()


def test_partial_overlay_is_accounted_and_can_receive_typed_stop_completion(
    runner, tmp_path
) -> None:
    class Row:
        def __init__(self, index: int) -> None:
            self.index = index

        def private_overlay_dict(self) -> dict:
            return {"row": self.index}

    now = datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc)
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    output = runner.PrivateOutput(directory_fd, 8 * 1024 * 1024)
    temperatures = iter(([40_000], [85_000]))
    lease = make_lease(runner, now, thermal_sample_every_records=1)
    envelope = runner.ResourceEnvelope(
        lease,
        output.directory_fd,
        0.0,
        now_fn=lambda: now,
        monotonic_fn=lambda: 0.0,
        thermal_reader=lambda: next(temperatures),
        statvfs_fn=lambda _fd: SimpleNamespace(
            f_bavail=10_737_418_240, f_frsize=1
        ),
    )
    try:
        with pytest.raises(runner.OperationalStop) as failure:
            output.write_overlay("exact_identity_overlay.private.jsonl", [Row(1), Row(2)], envelope)
        partial = output.partial_output_report()
        assert partial["actual_partial_private_output_bytes"] > 0
        assert partial["completion_marker_present"] is False
        receipt = {"state": "stopped_fail_closed", "stop": failure.value.code}
        receipt["receipt_root_sha256"] = runner.canonical_sha256(receipt)
        runner.finalize_output(output, RUN_ID, receipt)
        assert (tmp_path / "COMPLETE.json").is_file()
        assert stat.S_IMODE(
            (tmp_path / "exact_identity_overlay.private.jsonl").stat().st_mode
        ) == 0o400
    finally:
        output.close()


def test_one_shot_claim_persists_and_rejects_replay(
    runner, tmp_path, monkeypatch
) -> None:
    run_root = tmp_path / runner.PHONE_RUN_ROOT_RELATIVE
    candidate_root = run_root / RUN_ID / "candidate_runs"
    candidate_root.mkdir(parents=True, mode=0o700)
    for path in (run_root, run_root / RUN_ID, candidate_root):
        path.chmod(0o700)
    monkeypatch.setattr(runner, "PHONE_HOME", tmp_path)
    monkeypatch.setattr(runner, "PHONE_RUN_ROOT", run_root)
    output_path = candidate_root / "candidate-001"
    first = runner.PrivateOutput.create(
        output_path,
        RUN_ID,
        max_bytes=8 * 1024 * 1024,
    )
    first.close()
    claim = candidate_root / ".cur0s_static_identity_execution_claim"
    assert claim.is_file()
    assert stat.S_IMODE(claim.stat().st_mode) == 0o400
    with pytest.raises(FileExistsError):
        runner.PrivateOutput.create(
            output_path,
            RUN_ID,
            max_bytes=8 * 1024 * 1024,
        )


def test_beneath_helpers_reject_absolute_paths(runner, tmp_path) -> None:
    root_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(runner.Cur0sExactError, match="relative"):
            runner.open_regular_beneath(root_fd, "/etc/passwd")
        with pytest.raises(runner.Cur0sExactError, match="relative"):
            runner.open_directory_beneath(root_fd, "/tmp")
        with pytest.raises(runner.BootstrapError, match="relative"):
            runner.bootstrap_open_regular_beneath(root_fd, "/etc/passwd")
    finally:
        os.close(root_fd)


def test_builder_publication_rejects_dangling_final_symlink(builder, tmp_path) -> None:
    target = tmp_path / "prereg.json"
    target.symlink_to(tmp_path / "missing")
    with pytest.raises(FileExistsError):
        builder.exclusive_publish(target, b"{}\n")


def test_retained_output_descriptor_never_writes_into_replacement_parent(
    runner, tmp_path
) -> None:
    original = tmp_path / "candidate"
    original.mkdir()
    directory_fd = os.open(original, os.O_RDONLY | os.O_DIRECTORY)
    output = runner.PrivateOutput(directory_fd, 8 * 1024 * 1024)
    moved = tmp_path / "candidate-original"
    original.rename(moved)
    original.mkdir()
    try:
        output.write_receipt("receipt.json", {"aggregate": True})
        assert (moved / "receipt.json").is_file()
        assert not (original / "receipt.json").exists()
    finally:
        output.close()


def test_physical_hash_and_identity_parse_checkpoint_cadence(
    runner, tmp_path, monkeypatch
) -> None:
    class Checkpoints:
        def __init__(self) -> None:
            self.lease = SimpleNamespace(thermal_sample_every_records=1024)
            self.values: list[str] = []

        def check(self, checkpoint: str) -> None:
            self.values.append(checkpoint)

    source = tmp_path / "master.jsonl"
    source.write_bytes(b"{}\n" * 2049)
    fd = os.open(source, os.O_RDONLY)
    try:
        info = os.fstat(fd)
        artifact = runner.OpenArtifact(
            stage="C1",
            role="master",
            relative_path="master.jsonl",
            expected_sha256=sha(source.read_bytes()),
            expected_rows=2049,
            fd=fd,
            initial_stat=runner.stat_identity(info),
        )
        hash_checks = Checkpoints()
        runner.hash_open_artifact(artifact, hash_checks)
        assert hash_checks.values == [
            "physical_hash_C1_master",
            "physical_hash_C1_master",
        ]

        lock = StageLock(
            stage="C1",
            directory="C1",
            phase_filename="C1",
            rows=2049,
            master_sha256=sha(source.read_bytes()),
            qa_sha256="0" * 64,
            manifest_sha256="0" * 64,
        )
        monkeypatch.setattr(runner, "STAGE_LOCKS", (lock,))
        snapshot = SimpleNamespace(artifacts=(artifact,))
        parse_checks = Checkpoints()
        assert len(list(runner.iter_master_records(snapshot, parse_checks))) == 2049
        assert parse_checks.values == [
            "identity_parse_record_checkpoint",
            "identity_parse_record_checkpoint",
            "identity_parse_record_checkpoint",
        ]
    finally:
        os.close(fd)


@pytest.mark.parametrize(
    "stop_code",
    [
        "wall_time_limit_reached",
        "free_storage_floor_crossed",
        "thermal_ceiling_reached",
        "private_output_data_budget_reached",
    ],
)
def test_typed_operational_stops_commit_complete_evidence(
    runner, tmp_path, stop_code: str
) -> None:
    candidate = tmp_path / stop_code
    candidate.mkdir()
    directory_fd = os.open(candidate, os.O_RDONLY | os.O_DIRECTORY)
    output = runner.PrivateOutput(directory_fd, 8 * 1024 * 1024)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    monotonic = [0.0]
    envelope = runner.ResourceEnvelope(
        make_lease(runner, now),
        output.directory_fd,
        0.0,
        now_fn=lambda: now,
        monotonic_fn=lambda: monotonic[0],
        thermal_reader=lambda: [40_000],
        statvfs_fn=lambda _fd: SimpleNamespace(
            f_bavail=10_737_418_240, f_frsize=1
        ),
    )
    prereg = operational_prereg(runner, now)
    try:
        receipt = runner.build_operational_stop_receipt(
            prereg=prereg,
            prereg_bytes=runner.canonical_json_bytes(prereg) + b"\n",
            source_identity={"preimport_source_bytes_verified": True},
            runtime_identity={"phone_private_runtime_guard_passed": True},
            physical={"state": "not_executed", "passed": False},
            identity_progress={
                "state": "not_executed",
                "private_overlay_written": False,
            },
            stop=runner.OperationalStop(stop_code, "test_checkpoint"),
            envelope=envelope,
            output=output,
            started_at=runner.utc_now(),
            started_monotonic=0.0,
        )
        runner.finalize_output(output, RUN_ID, receipt)
        assert receipt["state"] == "stopped_fail_closed"
        assert receipt["operational_stop"]["code"] == stop_code
        assert (candidate / "COMPLETE.json").is_file()
    finally:
        output.close()


def test_unexpected_runtime_error_leaves_no_complete(runner, tmp_path) -> None:
    class BrokenRow:
        def private_overlay_dict(self) -> dict:
            raise RuntimeError("unexpected_programming_failure")

    now = datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc)
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    output = runner.PrivateOutput(directory_fd, 8 * 1024 * 1024)
    envelope = make_envelope(
        runner,
        output.directory_fd,
        now,
        temperatures=[40_000],
        free_bytes=10_737_418_240,
    )
    try:
        with pytest.raises(RuntimeError, match="unexpected_programming_failure"):
            output.write_overlay(
                "exact_identity_overlay.private.jsonl", [BrokenRow()], envelope
            )
        assert not (tmp_path / "COMPLETE.json").exists()
    finally:
        output.close()


def test_preimport_loader_executes_attested_bytes_not_current_path(runner) -> None:
    module = runner.load_bound_module(
        "_cur0s_attested_bytes_test",
        "path/is/display_only.py",
        b"VALUE = 'attested'\n",
    )
    assert module.VALUE == "attested"


def test_bootstrap_preregistration_rejects_hardlink_and_oversize(
    runner, tmp_path, monkeypatch
) -> None:
    run_root = tmp_path / runner.PHONE_RUN_ROOT_RELATIVE
    private_dir = run_root / RUN_ID
    private_dir.mkdir(parents=True, mode=0o700)
    run_root.chmod(0o700)
    private_dir.chmod(0o700)
    prereg = private_dir / "prereg.json"
    prereg.write_bytes(b"{}\n")
    prereg.chmod(0o400)
    hardlink = private_dir / "hardlink.json"
    os.link(prereg, hardlink)
    hardlink.chmod(0o400)
    monkeypatch.setattr(runner, "PHONE_HOME", tmp_path)
    with pytest.raises(runner.BootstrapError, match="hardlink"):
        runner.bootstrap_read_private_preregistration(str(prereg))

    oversized = private_dir / "oversized.json"
    oversized.write_bytes(b"x" * (1024 * 1024 + 1))
    oversized.chmod(0o400)
    with pytest.raises(runner.BootstrapError, match="too_large"):
        runner.bootstrap_read_private_preregistration(str(oversized))


def make_lease(runner, now: datetime, **overrides):
    values = {
        "lease_id": "test-lease",
        "action_id": RUN_ID,
        "issued_at": now,
        "expires_at": now + timedelta(hours=4),
        "max_wall_seconds": 1800,
        "max_private_output_bytes": 256 * 1024 * 1024,
        "min_free_storage_bytes": 10_737_418_240,
        "max_temperature_millidegrees_c": 85_000,
        "thermal_sample_every_records": 1024,
    }
    values.update(overrides)
    return runner.CampaignLease(**values)


def make_envelope(
    runner,
    directory_fd: int,
    now: datetime,
    *,
    temperatures: list[int],
    free_bytes: int,
    monotonic: list[float] | None = None,
    wall_clock: list[datetime] | None = None,
):
    monotonic = monotonic or [0.0]
    wall_clock = wall_clock or [now]
    return runner.ResourceEnvelope(
        make_lease(runner, now),
        directory_fd,
        0.0,
        now_fn=lambda: wall_clock[0],
        monotonic_fn=lambda: monotonic[0],
        thermal_reader=lambda: temperatures,
        statvfs_fn=lambda _fd: SimpleNamespace(
            f_bavail=free_bytes,
            f_frsize=1,
        ),
    )


def operational_prereg(runner, now: datetime) -> dict:
    sha_value = "sha256:" + "1" * 64
    return {
        "candidate_id": "cur0s_current_physical_exact_identity_v1",
        "run_id": RUN_ID,
        "parent_capsule_sha256": sha_value,
        "parent_frontier_root_sha256": sha_value,
        "maximal_selector_sha256": sha_value,
        "campaign_lease": {
            "lease_id": "test",
            "action_id": RUN_ID,
            "issued_at_utc": runner.iso_utc(now),
            "expires_at_utc": runner.iso_utc(now + timedelta(hours=4)),
        },
        "resource_slice": {"phone": "test"},
        "preregistration_root_sha256": sha_value,
        "ACCESS_receipt_sha256": sha_value,
    }


def canonical_line(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()

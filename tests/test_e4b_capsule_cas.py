from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import pytest

from polymath_ai.frontier import e4b_capsule_cas as capsule_cas


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_V4 = (
    ROOT
    / "docs"
    / "APEX-CURRENT-REALITY-CAPSULE-GEMMA4-E4B-QNN-CELL-2026-07-10.yaml.archive"
    / "7f85799e260658cd400b837a784035438c7601e3057d963e4cf9b98f14841266.yaml"
)
NEW_CUTOFF = "2026-07-11T10:30:00Z"


class InjectedCrash(RuntimeError):
    pass


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(capsule_cas.canonical_json(value) + b"\n")


def _local_artifact(
    repository: Path,
    relative: str,
    *,
    role: str,
    payload: bytes | None = None,
) -> dict[str, Any]:
    path = repository / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    content = payload if payload is not None else f"{role}\n".encode()
    path.write_bytes(content)
    return {
        "role": role,
        "locator": relative,
        "sha256": capsule_cas.sha256_bytes(content),
        "bytes": len(content),
        "custody": "repository_local",
        "local_path": relative,
    }


def _remote_artifact(role: str, seed: str) -> dict[str, Any]:
    payload = seed.encode()
    return {
        "role": role,
        "locator": f"phone://FY25013101C8/private/{seed}",
        "sha256": capsule_cas.sha256_bytes(payload),
        "bytes": len(payload),
        "custody": "phone_private",
    }


def _bindings(repository: Path) -> dict[str, Any]:
    frontier = _local_artifact(
        repository,
        "runtime/frontier.json",
        role="frontier_event",
    )
    preregistration = _local_artifact(
        repository,
        "runtime/preregistration.json",
        role="phone_preregistration_v4",
    )
    selector = _local_artifact(
        repository,
        "runtime/selector.json",
        role="maximal_selector_receipt",
    )
    lease = _local_artifact(
        repository,
        "runtime/access_refresh.json",
        role="campaign_lease_receipt",
    )
    input_artifact = _local_artifact(
        repository,
        "runtime/context_info.json",
        role="int16_context_info",
    )
    sanitized = _local_artifact(
        repository,
        "runtime/phone_attempt_report.json",
        role="sanitized_phone_attempt",
    )
    transition_evidence = sanitized["sha256"]
    return {
        "frontier": frontier,
        "preregistrations": [preregistration],
        "maximal_selector": selector,
        "lease": {
            "lease_id": "active_user_campaign_2026-07-11",
            "artifact": lease,
            "resource_slice": {
                "phone": "FY25013101C8",
                "runpod": "uh57jg7iguwqth_existing_only",
                "public_release": False,
            },
            "expires_at_utc": None,
        },
        "inputs": [input_artifact],
        "raw_reports": [_remote_artifact("phone_execution_receipt", "receipt-v4")],
        "sanitized_reports": [sanitized],
        "transitions": [
            {
                "subject_id": "L2_INT16_PHONE",
                "subject_kind": "gate",
                "from": "staged_unexecuted",
                "to": "blocked_fail_closed",
                "evidence_sha256": transition_evidence,
                "reason": "device_creation_failed_before_graph_execution",
            }
        ],
        "rollback": {
            "disposition": "retain_parent_archive_and_invalidate_no_artifacts",
            "rollback_base": None,
            "invalidated_sha256": [],
            "preserved_sha256": [input_artifact["sha256"]],
        },
        "source_commit": {
            "repository": "Zer0pa/Polymath-AI",
            "commit_sha": "1" * 40,
            "scope": ["source", "runner"],
        },
        "evidence_commit": {
            "repository": "Zer0pa/Polymath-AI",
            "commit_sha": "2" * 40,
            "scope": ["sanitized_report", "frontier_event"],
        },
    }


def _operations(parent: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "op": "replace",
            "path": ["schema_version"],
            "expected_old_sha256": capsule_cas.value_sha256(
                parent["schema_version"]
            ),
            "value": capsule_cas.V5_SCHEMA,
        },
        {
            "op": "replace",
            "path": ["evidence_cutoff_utc"],
            "expected_old_sha256": capsule_cas.value_sha256(
                parent["evidence_cutoff_utc"]
            ),
            "value": NEW_CUTOFF,
        },
        {
            "op": "add",
            "path": ["last_experiment_transaction"],
            "expected_old_sha256": None,
            "value": {
                "state": "blocked_fail_closed",
                "claim_ceiling": "no_numerical_falsification",
            },
        },
    ]


def _setup(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, Any]]:
    repository = tmp_path / "repository"
    repository.mkdir()
    canonical = repository / "capsule.yaml"
    canonical.write_bytes(CANONICAL_V4.read_bytes())
    parent = capsule_cas.strict_yaml_loads(canonical.read_bytes())
    spec = {
        "schema_version": capsule_cas.SPEC_SCHEMA,
        "transaction_id": "capsule-v4-to-v5-20260711T103000Z",
        "expected_parent_sha256": capsule_cas.EXPECTED_V4_SHA256,
        "evidence_cutoff_utc": NEW_CUTOFF,
        "mutation": {"operations": _operations(parent)},
        "bindings": _bindings(repository),
    }
    spec_path = repository / "transition_spec.json"
    _write_json(spec_path, spec)
    return repository, canonical, spec_path, spec


def _execute(
    repository: Path,
    canonical: Path,
    spec_path: Path,
    *,
    fault_injector: Any = None,
) -> dict[str, Any]:
    return capsule_cas.advance_capsule(
        canonical_path=canonical,
        transition_spec_path=spec_path,
        repository_root=repository,
        fault_injector=fault_injector,
    )


def _crash_at(target: str):
    def inject(phase: str) -> None:
        if phase == target:
            raise InjectedCrash(target)

    return inject


def test_governing_v4_is_exact_and_strict_parseable() -> None:
    payload = CANONICAL_V4.read_bytes()
    assert capsule_cas.sha256_bytes(payload) == capsule_cas.EXPECTED_V4_SHA256
    assert capsule_cas.strict_yaml_loads(payload)["schema_version"] == (
        capsule_cas.V4_SCHEMA
    )


def test_strict_json_rejects_duplicate_keys() -> None:
    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.strict_json_loads(b'{"a":1,"a":2}')
    assert raised.value.code == "json_duplicate_key:a"


def test_strict_json_rejects_non_finite_numbers() -> None:
    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.strict_json_loads(b'{"a":NaN}')
    assert raised.value.code == "json_non_finite_number"


def test_strict_yaml_rejects_duplicate_keys() -> None:
    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.strict_yaml_loads(b"a: 1\na: 2\n")
    assert raised.value.code == "yaml_duplicate_key:a"


def test_strict_yaml_rejects_aliases() -> None:
    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.strict_yaml_loads(b"a: &value [1]\nb: *value\n")
    assert raised.value.code == "yaml_alias_forbidden"


def test_spec_requires_the_exact_governing_parent(tmp_path: Path) -> None:
    repository, _canonical, _spec_path, spec = _setup(tmp_path)
    spec["expected_parent_sha256"] = "0" * 64
    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_spec(spec, repository)
    assert raised.value.code == "expected_parent_sha256_mismatch"


def test_child_derivation_is_deterministic_and_v5(tmp_path: Path) -> None:
    repository, canonical, _spec_path, spec = _setup(tmp_path)
    parent = capsule_cas.strict_yaml_loads(canonical.read_bytes())
    validated = capsule_cas.validate_spec(spec, repository)
    first = capsule_cas.derive_child_capsule(parent, validated)
    second = capsule_cas.derive_child_capsule(parent, validated)
    assert capsule_cas.deterministic_yaml(first) == capsule_cas.deterministic_yaml(
        second
    )
    assert first["schema_version"] == capsule_cas.V5_SCHEMA
    assert first["evidence_cutoff_utc"] == NEW_CUTOFF
    assert first["generated_from"] == parent["generated_from"]


def test_operation_old_value_hash_is_a_field_level_cas(tmp_path: Path) -> None:
    repository, canonical, _spec_path, spec = _setup(tmp_path)
    parent = capsule_cas.strict_yaml_loads(canonical.read_bytes())
    spec["mutation"]["operations"][0]["expected_old_sha256"] = "3" * 64
    validated = capsule_cas.validate_spec(spec, repository)
    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.derive_child_capsule(parent, validated)
    assert raised.value.code == "operation_old_value_sha256_mismatch"


def test_overlapping_mutation_paths_are_rejected(tmp_path: Path) -> None:
    repository, _canonical, _spec_path, spec = _setup(tmp_path)
    spec["mutation"]["operations"].extend(
        [
            {
                "op": "replace",
                "path": ["current_design_decision"],
                "expected_old_sha256": "4" * 64,
                "value": {},
            },
            {
                "op": "replace",
                "path": ["current_design_decision", "canonical_route"],
                "expected_old_sha256": "5" * 64,
                "value": [],
            },
        ]
    )
    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_spec(spec, repository)
    assert raised.value.code == "operation_paths_overlap"


def test_success_archives_parent_and_binds_complete_receipt(tmp_path: Path) -> None:
    repository, canonical, spec_path, spec = _setup(tmp_path)
    unrelated = repository / "user-dirt.txt"
    unrelated.write_text("preserve me\n", encoding="utf-8")
    parent_bytes = canonical.read_bytes()

    result = _execute(repository, canonical, spec_path)

    assert result["status"] == "complete"
    child_bytes = canonical.read_bytes()
    assert capsule_cas.sha256_bytes(child_bytes) == result["child_capsule_sha256"]
    child = capsule_cas.strict_yaml_loads(child_bytes)
    assert child["schema_version"] == capsule_cas.V5_SCHEMA
    assert unrelated.read_text(encoding="utf-8") == "preserve me\n"

    archive = Path(result["archive_path"])
    receipt_path = Path(result["receipt_path"])
    completion_path = Path(result["completion_path"])
    assert archive.read_bytes() == parent_bytes
    assert capsule_cas.sha256_bytes(archive.read_bytes()) == (
        capsule_cas.EXPECTED_V4_SHA256
    )
    receipt = capsule_cas.strict_json_loads(receipt_path.read_bytes())
    assert receipt["schema_version"] == capsule_cas.RECEIPT_SCHEMA
    assert receipt["capsule"]["parent"]["sha256"] == (
        capsule_cas.EXPECTED_V4_SHA256
    )
    assert receipt["capsule"]["child"]["sha256"] == result[
        "child_capsule_sha256"
    ]
    assert receipt["bindings"] == spec["bindings"]
    completion = capsule_cas.strict_json_loads(completion_path.read_bytes())
    assert completion["status"] == "complete"
    assert completion["receipt_sha256"] == result["receipt_sha256"]
    assert canonical.with_name(f"{canonical.name}.lock").is_file()


def test_completed_transaction_is_idempotent(tmp_path: Path) -> None:
    repository, canonical, spec_path, _spec = _setup(tmp_path)
    first = _execute(repository, canonical, spec_path)
    child_before = canonical.read_bytes()
    receipt_before = Path(first["receipt_path"]).read_bytes()
    completion_before = Path(first["completion_path"]).read_bytes()

    second = _execute(repository, canonical, spec_path)

    assert second["status"] == "already_complete"
    assert second["child_capsule_sha256"] == first["child_capsule_sha256"]
    assert canonical.read_bytes() == child_before
    assert Path(first["receipt_path"]).read_bytes() == receipt_before
    assert Path(first["completion_path"]).read_bytes() == completion_before


@pytest.mark.parametrize("phase", ["after_archive", "after_receipt"])
def test_crash_before_replace_resumes_from_exact_parent(
    tmp_path: Path,
    phase: str,
) -> None:
    repository, canonical, spec_path, _spec = _setup(tmp_path)
    with pytest.raises(InjectedCrash):
        _execute(
            repository,
            canonical,
            spec_path,
            fault_injector=_crash_at(phase),
        )
    assert capsule_cas.sha256_bytes(canonical.read_bytes()) == (
        capsule_cas.EXPECTED_V4_SHA256
    )

    result = _execute(repository, canonical, spec_path)

    assert result["status"] == "complete"
    assert Path(result["completion_path"]).is_file()


def test_crash_after_replace_finalizes_exact_child(tmp_path: Path) -> None:
    repository, canonical, spec_path, _spec = _setup(tmp_path)
    with pytest.raises(InjectedCrash):
        _execute(
            repository,
            canonical,
            spec_path,
            fault_injector=_crash_at("after_replace"),
        )
    child_before = canonical.read_bytes()
    assert capsule_cas.strict_yaml_loads(child_before)["schema_version"] == (
        capsule_cas.V5_SCHEMA
    )

    result = _execute(repository, canonical, spec_path)

    assert result["status"] == "already_complete"
    assert canonical.read_bytes() == child_before
    assert Path(result["completion_path"]).is_file()


def test_compare_and_swap_conflict_never_overwrites_foreign_child(
    tmp_path: Path,
) -> None:
    repository, canonical, spec_path, _spec = _setup(tmp_path)
    with pytest.raises(InjectedCrash):
        _execute(
            repository,
            canonical,
            spec_path,
            fault_injector=_crash_at("after_receipt"),
        )
    foreign = b"schema_version: foreign\n"
    canonical.write_bytes(foreign)

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        _execute(repository, canonical, spec_path)

    assert raised.value.code == "canonical_compare_and_swap_conflict"
    assert canonical.read_bytes() == foreign


def test_corrupt_completion_marker_fails_closed(tmp_path: Path) -> None:
    repository, canonical, spec_path, _spec = _setup(tmp_path)
    result = _execute(repository, canonical, spec_path)
    completion = Path(result["completion_path"])
    completion.write_bytes(b'{"status":"foreign"}\n')

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        _execute(repository, canonical, spec_path)

    assert raised.value.code == "completion_existing_mismatch"


def test_corrupt_parent_archive_blocks_child_recovery(tmp_path: Path) -> None:
    repository, canonical, spec_path, _spec = _setup(tmp_path)
    result = _execute(repository, canonical, spec_path)
    Path(result["archive_path"]).write_bytes(b"corrupt\n")

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        _execute(repository, canonical, spec_path)

    assert raised.value.code == "parent_archive_sha256_mismatch"


def test_symlink_capsule_is_rejected(tmp_path: Path) -> None:
    repository, canonical, spec_path, _spec = _setup(tmp_path)
    real = repository / "real-capsule.yaml"
    canonical.rename(real)
    canonical.symlink_to(real.name)

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        _execute(repository, canonical, spec_path)

    assert "symlink" in raised.value.code
    assert real.read_bytes() == CANONICAL_V4.read_bytes()


def test_hardlinked_capsule_is_rejected(tmp_path: Path) -> None:
    repository, canonical, spec_path, _spec = _setup(tmp_path)
    alias = repository / "capsule-alias.yaml"
    os.link(canonical, alias)

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        _execute(repository, canonical, spec_path)

    assert raised.value.code == "canonical_capsule_hardlink_forbidden"


def test_local_bound_artifact_symlink_is_rejected(tmp_path: Path) -> None:
    repository, canonical, spec_path, spec = _setup(tmp_path)
    relative = spec["bindings"]["frontier"]["local_path"]
    path = repository / relative
    real = path.with_suffix(".real")
    path.rename(real)
    path.symlink_to(real.name)

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        _execute(repository, canonical, spec_path)

    assert "symlink" in raised.value.code
    assert capsule_cas.sha256_bytes(canonical.read_bytes()) == (
        capsule_cas.EXPECTED_V4_SHA256
    )


def test_local_bound_artifact_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    repository, canonical, spec_path, spec = _setup(tmp_path)
    relative = spec["bindings"]["sanitized_reports"][0]["local_path"]
    (repository / relative).write_bytes(b"changed\n")

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        _execute(repository, canonical, spec_path)

    assert raised.value.code in {
        "sanitized_reports_0_local_file_bytes_mismatch",
        "sanitized_reports_0_local_file_sha256_mismatch",
    }
    assert capsule_cas.sha256_bytes(canonical.read_bytes()) == (
        capsule_cas.EXPECTED_V4_SHA256
    )


def test_local_bindings_are_reverified_after_lock_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, canonical, spec_path, spec = _setup(tmp_path)
    relative = spec["bindings"]["frontier"]["local_path"]
    original_enter = capsule_cas._AdjacentLock.__enter__

    def mutate_then_enter(lock: Any) -> Any:
        result = original_enter(lock)
        (repository / relative).write_bytes(b"changed-after-preflight\n")
        return result

    monkeypatch.setattr(capsule_cas._AdjacentLock, "__enter__", mutate_then_enter)

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        _execute(repository, canonical, spec_path)

    assert raised.value.code == "frontier_local_file_bytes_mismatch"
    assert capsule_cas.sha256_bytes(canonical.read_bytes()) == (
        capsule_cas.EXPECTED_V4_SHA256
    )


def test_mapping_key_deletion_is_forbidden(tmp_path: Path) -> None:
    repository, canonical, _spec_path, spec = _setup(tmp_path)
    parent = capsule_cas.strict_yaml_loads(canonical.read_bytes())
    spec["mutation"]["operations"].append(
        {
            "op": "replace",
            "path": ["path_bases"],
            "expected_old_sha256": capsule_cas.value_sha256(parent["path_bases"]),
            "value": {
                "generated_from_and_FIR_path": parent["path_bases"][
                    "generated_from_and_FIR_path"
                ]
            },
        }
    )
    validated = capsule_cas.validate_spec(spec, repository)

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.derive_child_capsule(parent, validated)

    assert raised.value.code.startswith("mapping_key_deletion_forbidden:")


def test_governing_objective_mutation_is_forbidden(tmp_path: Path) -> None:
    repository, canonical, _spec_path, spec = _setup(tmp_path)
    parent = capsule_cas.strict_yaml_loads(canonical.read_bytes())
    changed = copy.deepcopy(parent["governing_objective"])
    changed["model_target"] = "substituted_model"
    spec["mutation"]["operations"].append(
        {
            "op": "replace",
            "path": ["governing_objective"],
            "expected_old_sha256": capsule_cas.value_sha256(
                parent["governing_objective"]
            ),
            "value": changed,
        }
    )
    validated = capsule_cas.validate_spec(spec, repository)

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.derive_child_capsule(parent, validated)

    assert raised.value.code == "governing_objective_changed"


def test_secret_values_are_forbidden_in_lease_binding(tmp_path: Path) -> None:
    repository, _canonical, _spec_path, spec = _setup(tmp_path)
    spec["bindings"]["lease"]["resource_slice"]["token"] = "hf_not_a_real_token"

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_spec(spec, repository)

    assert raised.value.code == "secret_field_forbidden:token"


def test_existing_archive_with_wrong_bytes_fails_before_replace(tmp_path: Path) -> None:
    repository, canonical, spec_path, _spec = _setup(tmp_path)
    spec_sha = capsule_cas.sha256_bytes(spec_path.read_bytes())
    assert spec_sha
    archive_root = canonical.with_name(f"{canonical.name}.archive")
    archive_root.mkdir()
    archive_path = archive_root / f"{capsule_cas.EXPECTED_V4_SHA256}.yaml"
    archive_path.write_bytes(b"foreign archive\n")

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        _execute(repository, canonical, spec_path)

    assert raised.value.code == "parent_archive_existing_mismatch"
    assert capsule_cas.sha256_bytes(canonical.read_bytes()) == (
        capsule_cas.EXPECTED_V4_SHA256
    )


def test_receipt_is_durable_before_canonical_replace(tmp_path: Path) -> None:
    repository, canonical, spec_path, _spec = _setup(tmp_path)
    with pytest.raises(InjectedCrash):
        _execute(
            repository,
            canonical,
            spec_path,
            fault_injector=_crash_at("after_receipt"),
        )
    transaction_root = canonical.with_name(f".{canonical.name}.transactions")
    receipts = list(transaction_root.glob("*/transition_receipt.json"))
    assert len(receipts) == 1
    receipt = capsule_cas.strict_json_loads(receipts[0].read_bytes())
    assert receipt["capsule"]["parent"]["sha256"] == (
        capsule_cas.EXPECTED_V4_SHA256
    )
    assert capsule_cas.sha256_bytes(canonical.read_bytes()) == (
        capsule_cas.EXPECTED_V4_SHA256
    )

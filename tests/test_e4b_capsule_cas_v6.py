from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from polymath_ai.frontier import e4b_capsule_cas as capsule_cas


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_V5 = (
    ROOT
    / "docs"
    / ".APEX-CURRENT-REALITY-CAPSULE-GEMMA4-E4B-QNN-CELL-2026-07-10.yaml.transactions"
    / "dd2c76bca63e3da9d1966a3cf5b2599829dd6b563ec30ebe48471b632e6fd193"
    / "child_capsule.yaml"
)
CANONICAL_V6_SPEC = (
    ROOT
    / "runtime"
    / "reports"
    / "apex_frontier"
    / "capsule_transitions"
    / "20260711T152007Z_v5_to_v6"
    / "transition_spec.json"
)
NEW_CUTOFF = "2026-07-11T15:21:39Z"


class InjectedCrash(RuntimeError):
    pass


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(capsule_cas.canonical_json(value) + b"\n")


def _local_artifact(
    repository: Path,
    relative: str,
    *,
    role: str,
) -> dict[str, Any]:
    path = repository / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = f"{role}\n".encode()
    path.write_bytes(payload)
    return {
        "role": role,
        "locator": relative,
        "sha256": capsule_cas.sha256_bytes(payload),
        "bytes": len(payload),
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
        "runtime/opencl_frontier.json",
        role="opencl_frontier_event",
    )
    preregistration = _local_artifact(
        repository,
        "runtime/s16_v2_preregistration.json",
        role="s16_v2_preregistration",
    )
    selector = _local_artifact(
        repository,
        "runtime/opencl_selector.json",
        role="opencl_maximal_selector",
    )
    lease = _local_artifact(
        repository,
        "runtime/access_refresh.json",
        role="campaign_lease_receipt",
    )
    input_artifact = _local_artifact(
        repository,
        "runtime/opencl_contract.json",
        role="opencl_contract",
    )
    sanitized = _local_artifact(
        repository,
        "runtime/s16_falsification.json",
        role="s16_v2_falsification",
    )
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
        "raw_reports": [_remote_artifact("phone_oracle_output", "s16-v2")],
        "sanitized_reports": [sanitized],
        "transitions": [
            {
                "subject_id": "F5_W2_S16_V2",
                "subject_kind": "candidate",
                "from": "proposed",
                "to": "killed_falsified_scope",
                "evidence_sha256": sanitized["sha256"],
                "reason": "exact_dot_oracle_failed_frozen_authority_metric",
            }
        ],
        "rollback": {
            "disposition": "archive_v5_and_preserve_falsification",
            "rollback_base": None,
            "invalidated_sha256": [preregistration["sha256"]],
            "preserved_sha256": [sanitized["sha256"], frontier["sha256"]],
        },
        "source_commit": {
            "repository": "Zer0pa/Polymath-AI",
            "commit_sha": "1" * 40,
            "scope": ["capsule_v6_migration"],
        },
        "evidence_commit": {
            "repository": "Zer0pa/Polymath-AI",
            "commit_sha": "2" * 40,
            "scope": ["s16_v2_kill", "opencl_selection"],
        },
    }


def _operations(
    parent: dict[str, Any],
    bindings: dict[str, Any],
) -> list[dict[str, Any]]:
    campaign_state = copy.deepcopy(parent["last_verified_campaign_state"])
    campaign_state.update(
        {
            "source_commit": bindings["source_commit"]["commit_sha"],
            "evidence_commit": bindings["evidence_commit"]["commit_sha"],
            "frontier_root_sha256": bindings["frontier"]["sha256"],
            "parent_capsule_sha256": capsule_cas.EXPECTED_V5_SHA256,
        }
    )
    return [
        {
            "op": "replace",
            "path": ["schema_version"],
            "expected_old_sha256": capsule_cas.value_sha256(
                parent["schema_version"]
            ),
            "value": capsule_cas.V6_SCHEMA,
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
            "op": "replace",
            "path": ["last_verified_campaign_state"],
            "expected_old_sha256": capsule_cas.value_sha256(
                parent["last_verified_campaign_state"]
            ),
            "value": campaign_state,
        },
        {
            "op": "add",
            "path": ["last_v6_test_transition"],
            "expected_old_sha256": None,
            "value": {
                "state": "selected_frozen_unobserved",
                "promotion_allowed": False,
            },
        },
    ]


def _campaign_operation(spec: dict[str, Any]) -> dict[str, Any]:
    return next(
        operation
        for operation in spec["mutation"]["operations"]
        if operation["path"] == ["last_verified_campaign_state"]
    )


def _setup(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, Any]]:
    repository = tmp_path / "repository"
    repository.mkdir()
    canonical = repository / "capsule.yaml"
    canonical.write_bytes(CANONICAL_V5.read_bytes())
    parent = capsule_cas.strict_yaml_loads(canonical.read_bytes())
    bindings = _bindings(repository)
    spec = {
        "schema_version": capsule_cas.V6_SPEC_SCHEMA,
        "transaction_id": "capsule-v5-to-v6-20260711T152007Z",
        "expected_parent_sha256": capsule_cas.EXPECTED_V5_SHA256,
        "evidence_cutoff_utc": NEW_CUTOFF,
        "mutation": {"operations": _operations(parent, bindings)},
        "bindings": bindings,
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
    return capsule_cas.advance_capsule_v5_to_v6(
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


def test_governing_v5_snapshot_is_exact_and_strict_parseable() -> None:
    payload = CANONICAL_V5.read_bytes()
    assert capsule_cas.sha256_bytes(payload) == capsule_cas.EXPECTED_V5_SHA256
    assert capsule_cas.strict_yaml_loads(payload)["schema_version"] == (
        capsule_cas.V5_SCHEMA
    )


def test_governing_v6_spec_is_canonical_and_blocked_on_source_commit() -> None:
    raw = CANONICAL_V6_SPEC.read_bytes()
    spec = capsule_cas.strict_json_loads(raw)
    assert capsule_cas.canonical_json(spec) + b"\n" == raw
    digest = capsule_cas.sha256_bytes(raw)
    assert CANONICAL_V6_SPEC.with_suffix(".json.sha256").read_bytes() == (
        f"{digest}  transition_spec.json\n".encode("ascii")
    )
    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_v6_spec(spec, ROOT)
    assert raised.value.code == "v6_source_commit_placeholder_unresolved"

    source_bound = copy.deepcopy(spec)
    source_bound["bindings"]["source_commit"]["commit_sha"] = "f" * 40
    campaign_operation = _campaign_operation(source_bound)
    campaign_operation["value"]["source_commit"] = "f" * 40
    validated = capsule_cas.validate_v6_spec(source_bound, ROOT)
    parent = capsule_cas.strict_yaml_loads(CANONICAL_V5.read_bytes())

    child = capsule_cas.derive_v6_child_capsule(parent, validated)

    assert validated["bindings"]["evidence_commit"]["commit_sha"] == (
        "17bcc4176caeb3222be6bce5c79445fb3240a95c"
    )
    assert validated["evidence_cutoff_utc"] == "2026-07-11T15:21:39Z"
    assert validated["bindings"]["frontier"]["sha256"] == (
        "a3ab8f26d5c794e2235a65a93cfc5b4eea7a40d479d9d83be34fabf2ee4a9647"
    )
    assert validated["bindings"]["sanitized_reports"][2]["sha256"] == (
        "6b0605334c085a4fe7f404ff0723ffe295283796e1048dfdbfdda1bf5a2fe3a2"
    )
    assert child["frontier_execution_policy"]["frontier_root_sha256"] == (
        "a3ab8f26d5c794e2235a65a93cfc5b4eea7a40d479d9d83be34fabf2ee4a9647"
    )
    assert child["measured_claims"]["F5_W2_S16_V2"]["state"] == (
        "killed_falsified_scope"
    )
    assert child["measured_claims"]["F5_W2_ADRENO_OPENCL_BF16"]["state"] == (
        "selected_frozen_unobserved"
    )
    assert child["success_terminal"]["section_0_5_satisfied"] is False


def test_v6_child_derivation_is_deterministic(tmp_path: Path) -> None:
    repository, canonical, _spec_path, spec = _setup(tmp_path)
    parent = capsule_cas.strict_yaml_loads(canonical.read_bytes())
    validated = capsule_cas.validate_v6_spec(spec, repository)

    first = capsule_cas.derive_v6_child_capsule(parent, validated)
    second = capsule_cas.derive_v6_child_capsule(parent, validated)

    assert capsule_cas.deterministic_yaml(first) == capsule_cas.deterministic_yaml(
        second
    )
    assert first["schema_version"] == capsule_cas.V6_SCHEMA
    assert first["evidence_cutoff_utc"] == NEW_CUTOFF
    assert first["generated_from"] == parent["generated_from"]


def test_v6_success_archives_exact_v5_and_binds_profile_receipts(
    tmp_path: Path,
) -> None:
    repository, canonical, spec_path, spec = _setup(tmp_path)
    parent_bytes = canonical.read_bytes()

    result = _execute(repository, canonical, spec_path)

    assert result["status"] == "complete"
    assert Path(result["archive_path"]).read_bytes() == parent_bytes
    assert Path(result["archive_path"]).name == (
        f"{capsule_cas.EXPECTED_V5_SHA256}.yaml"
    )
    receipt = capsule_cas.strict_json_loads(Path(result["receipt_path"]).read_bytes())
    assert receipt["schema_version"] == capsule_cas.V6_RECEIPT_SCHEMA
    assert receipt["transition_spec"]["schema_version"] == (
        capsule_cas.V6_SPEC_SCHEMA
    )
    assert receipt["capsule"]["parent"]["schema_version"] == capsule_cas.V5_SCHEMA
    assert receipt["capsule"]["child"]["schema_version"] == capsule_cas.V6_SCHEMA
    assert receipt["bindings"] == spec["bindings"]
    completion = capsule_cas.strict_json_loads(
        Path(result["completion_path"]).read_bytes()
    )
    assert completion["schema_version"] == capsule_cas.V6_COMPLETION_SCHEMA
    assert completion["parent_capsule_sha256"] == capsule_cas.EXPECTED_V5_SHA256
    assert completion["receipt_sha256"] == result["receipt_sha256"]


def test_v6_completed_transaction_is_idempotent(tmp_path: Path) -> None:
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
def test_v6_crash_before_replace_resumes_from_exact_v5(
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
        capsule_cas.EXPECTED_V5_SHA256
    )

    result = _execute(repository, canonical, spec_path)

    assert result["status"] == "complete"
    assert Path(result["completion_path"]).is_file()


def test_v6_crash_after_replace_finalizes_exact_child(tmp_path: Path) -> None:
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
        capsule_cas.V6_SCHEMA
    )

    result = _execute(repository, canonical, spec_path)

    assert result["status"] == "already_complete"
    assert canonical.read_bytes() == child_before
    assert Path(result["completion_path"]).is_file()


def test_v6_compare_and_swap_conflict_never_overwrites_foreign_child(
    tmp_path: Path,
) -> None:
    repository, canonical, spec_path, _spec = _setup(tmp_path)
    foreign = b"schema_version: foreign\n"
    canonical.write_bytes(foreign)

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        _execute(repository, canonical, spec_path)

    assert raised.value.code == "canonical_compare_and_swap_conflict"
    assert canonical.read_bytes() == foreign


def test_v6_rejects_wrong_parent_and_original_api_rejects_v6_spec(
    tmp_path: Path,
) -> None:
    repository, canonical, _spec_path, spec = _setup(tmp_path)
    spec["expected_parent_sha256"] = capsule_cas.EXPECTED_V4_SHA256
    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_v6_spec(spec, repository)
    assert raised.value.code == "expected_parent_sha256_mismatch"

    spec["expected_parent_sha256"] = capsule_cas.EXPECTED_V5_SHA256
    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_spec(spec, repository)
    assert raised.value.code == "spec_schema_version_mismatch"
    assert capsule_cas.sha256_bytes(canonical.read_bytes()) == (
        capsule_cas.EXPECTED_V5_SHA256
    )


@pytest.mark.parametrize(
    ("field", "foreign_value", "error_code"),
    [
        (
            "source_commit",
            "3" * 40,
            "v6_campaign_state_source_commit_binding_mismatch",
        ),
        (
            "evidence_commit",
            "3" * 40,
            "v6_campaign_state_evidence_commit_binding_mismatch",
        ),
        (
            "frontier_root_sha256",
            "3" * 64,
            "v6_campaign_state_frontier_root_sha256_binding_mismatch",
        ),
        (
            "parent_capsule_sha256",
            "3" * 64,
            "v6_campaign_state_parent_capsule_sha256_binding_mismatch",
        ),
    ],
)
def test_v6_campaign_state_must_equal_transaction_bindings(
    tmp_path: Path,
    field: str,
    foreign_value: str,
    error_code: str,
) -> None:
    repository, _canonical, _spec_path, spec = _setup(tmp_path)
    _campaign_operation(spec)["value"][field] = foreign_value

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_v6_spec(spec, repository)

    assert raised.value.code == error_code


def test_v6_requires_exactly_one_campaign_state_replacement(
    tmp_path: Path,
) -> None:
    repository, _canonical, _spec_path, spec = _setup(tmp_path)
    spec["mutation"]["operations"].remove(_campaign_operation(spec))

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_v6_spec(spec, repository)

    assert raised.value.code == "v6_campaign_state_replacement_count_invalid"


def test_v6_campaign_state_operation_must_be_replace(tmp_path: Path) -> None:
    repository, _canonical, _spec_path, spec = _setup(tmp_path)
    operation = _campaign_operation(spec)
    operation["op"] = "add"
    operation["expected_old_sha256"] = None

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_v6_spec(spec, repository)

    assert raised.value.code == "v6_campaign_state_operation_not_replace"

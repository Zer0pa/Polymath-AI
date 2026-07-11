from __future__ import annotations

import copy
from pathlib import Path
import subprocess
import sys
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
CANONICAL_V6_ADRENO_PASS_PARENT = (
    ROOT
    / "docs"
    / ".APEX-CURRENT-REALITY-CAPSULE-GEMMA4-E4B-QNN-CELL-2026-07-10.yaml.transactions"
    / "708f7d1eb5f5bdf81b470c2b21701465de1d0a0e59467772a3f93d5635d969f6"
    / "child_capsule.yaml"
)
V6_ADRENO_PASS_CLI = (
    ROOT / "scripts" / "host" / "advance_e4b_current_reality_capsule_v6_adreno_pass.py"
)
CANONICAL_V6_CUR0S_EXACT_PARENT = (
    ROOT
    / "docs"
    / ".APEX-CURRENT-REALITY-CAPSULE-GEMMA4-E4B-QNN-CELL-2026-07-10.yaml.transactions"
    / "ea13d27beb44066e33faa88721eda637e21eec76b118f7817d486fa17793e3c9"
    / "child_capsule.yaml"
)
V6_CUR0S_EXACT_CLI = (
    ROOT / "scripts" / "host" / "advance_e4b_current_reality_capsule_v6_cur0s_exact.py"
)
NEW_CUTOFF = "2026-07-11T15:21:39Z"
ADRENO_PASS_CUTOFF = "2026-07-11T18:56:00Z"
CUR0S_EXACT_CUTOFF = "2026-07-11T21:17:47Z"


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


def test_governing_v6_spec_is_canonical_bound_and_derivable() -> None:
    raw = CANONICAL_V6_SPEC.read_bytes()
    spec = capsule_cas.strict_json_loads(raw)
    assert capsule_cas.canonical_json(spec) + b"\n" == raw
    digest = capsule_cas.sha256_bytes(raw)
    assert CANONICAL_V6_SPEC.with_suffix(".json.sha256").read_bytes() == (
        f"{digest}  transition_spec.json\n".encode("ascii")
    )
    validated = capsule_cas.validate_v6_spec(spec, ROOT)
    parent = capsule_cas.strict_yaml_loads(CANONICAL_V5.read_bytes())

    child = capsule_cas.derive_v6_child_capsule(parent, validated)

    assert validated["bindings"]["source_commit"]["commit_sha"] == (
        "b40e98d194865ead97cfad3778f0a212e8295e25"
    )
    assert validated["bindings"]["source_commit"]["scope"] == [
        "capsule_v6_CAS_module",
        "capsule_v6_CAS_CLI",
        "capsule_v6_CAS_tests",
    ]
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

    placeholder_spec = copy.deepcopy(spec)
    placeholder_spec["bindings"]["source_commit"]["commit_sha"] = "0" * 40
    _campaign_operation(placeholder_spec)["value"]["source_commit"] = "0" * 40
    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_v6_spec(placeholder_spec, repository)
    assert raised.value.code == "v6_source_commit_placeholder_unresolved"

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


def _adreno_pass_bindings(repository: Path) -> dict[str, Any]:
    frontier = _local_artifact(
        repository,
        "runtime/adreno_pass_frontier.json",
        role="adreno_pass_frontier_event",
    )
    preregistration = _local_artifact(
        repository,
        "runtime/adreno_phone_preregistration.json",
        role="adreno_phone_preregistration",
    )
    selector = _local_artifact(
        repository,
        "runtime/adreno_maximal_selector.json",
        role="adreno_maximal_selector",
    )
    lease = _local_artifact(
        repository,
        "runtime/adreno_execution_lease.json",
        role="adreno_execution_lease",
    )
    input_contract = _local_artifact(
        repository,
        "runtime/adreno_opencl_contract.json",
        role="adreno_opencl_contract",
    )
    sanitized = _local_artifact(
        repository,
        "runtime/adreno_phone_receipt.json",
        role="adreno_phone_sanitized_receipt",
    )
    return {
        "frontier": frontier,
        "preregistrations": [preregistration],
        "maximal_selector": selector,
        "lease": {
            "lease_id": "adreno_pass_campaign_2026-07-11",
            "artifact": lease,
            "resource_slice": {
                "phone": "FY25013101C8",
                "candidate_execution_count": 1,
                "public_release": False,
            },
            "expires_at_utc": None,
        },
        "inputs": [input_contract],
        "raw_reports": [
            _remote_artifact("phone_private_adreno_outputs", "adreno-pass")
        ],
        "sanitized_reports": [sanitized],
        "transitions": [
            {
                "subject_id": "F5_W2_ADRENO_OPENCL_BF16",
                "subject_kind": "candidate",
                "from": "selected_frozen_unobserved",
                "to": "passed_scope",
                "evidence_sha256": sanitized["sha256"],
                "reason": "three_authority_cases_and_off_lattice_sentinel_exact",
            }
        ],
        "rollback": {
            "disposition": "archive_v6_parent_and_preserve_bounded_pass",
            "rollback_base": None,
            "invalidated_sha256": [],
            "preserved_sha256": [
                preregistration["sha256"],
                sanitized["sha256"],
                frontier["sha256"],
            ],
        },
        "source_commit": {
            "repository": "Zer0pa/Polymath-AI",
            "commit_sha": "a" * 40,
            "scope": ["adreno_phone_gate_source"],
        },
        "evidence_commit": {
            "repository": "Zer0pa/Polymath-AI",
            "commit_sha": "b" * 40,
            "scope": ["adreno_bounded_pass_evidence"],
        },
    }


def _adreno_pass_operations(
    parent: dict[str, Any],
    bindings: dict[str, Any],
) -> list[dict[str, Any]]:
    campaign_state = copy.deepcopy(parent["last_verified_campaign_state"])
    campaign_state.update(
        {
            "active_sovereign_gate": "F5_terminal_head_successor_selection",
            "first_missing_green_field": "next_decisive_F5_successor_selection",
            "last_disposition": "Adreno_OpenCL_BF16_passed_bounded_scope",
            "source_commit": bindings["source_commit"]["commit_sha"],
            "evidence_commit": bindings["evidence_commit"]["commit_sha"],
            "frontier_root_sha256": bindings["frontier"]["sha256"],
            "parent_capsule_sha256": (
                capsule_cas.EXPECTED_V6_ADRENO_PASS_PARENT_SHA256
            ),
        }
    )
    measured_claim = copy.deepcopy(
        parent["measured_claims"]["F5_W2_ADRENO_OPENCL_BF16"]
    )
    measured_claim.update(
        {
            "state": "passed_scope",
            "claim_class": "bounded_terminal_head_measured",
            "candidate_output_observed": True,
            "phone_model_execution_count": 1,
            "preregistration_present": True,
            "source_committed": True,
        }
    )
    return [
        {
            "op": "replace",
            "path": ["evidence_cutoff_utc"],
            "expected_old_sha256": capsule_cas.value_sha256(
                parent["evidence_cutoff_utc"]
            ),
            "value": ADRENO_PASS_CUTOFF,
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
            "op": "replace",
            "path": ["measured_claims", "F5_W2_ADRENO_OPENCL_BF16"],
            "expected_old_sha256": capsule_cas.value_sha256(
                parent["measured_claims"]["F5_W2_ADRENO_OPENCL_BF16"]
            ),
            "value": measured_claim,
        },
    ]


def _setup_adreno_pass(
    tmp_path: Path,
) -> tuple[Path, Path, Path, dict[str, Any]]:
    repository = tmp_path / "adreno_repository"
    repository.mkdir()
    canonical = repository / "capsule.yaml"
    canonical.write_bytes(CANONICAL_V6_ADRENO_PASS_PARENT.read_bytes())
    parent = capsule_cas.strict_yaml_loads(canonical.read_bytes())
    bindings = _adreno_pass_bindings(repository)
    spec = {
        "schema_version": capsule_cas.V6_SPEC_SCHEMA,
        "transaction_id": "capsule-v6-adreno-pass-20260711T185600Z",
        "expected_parent_sha256": (capsule_cas.EXPECTED_V6_ADRENO_PASS_PARENT_SHA256),
        "evidence_cutoff_utc": ADRENO_PASS_CUTOFF,
        "mutation": {
            "operations": _adreno_pass_operations(parent, bindings),
        },
        "bindings": bindings,
    }
    spec_path = repository / "adreno_pass_transition_spec.json"
    _write_json(spec_path, spec)
    return repository, canonical, spec_path, spec


def _execute_adreno_pass(
    repository: Path,
    canonical: Path,
    spec_path: Path,
    *,
    fault_injector: Any = None,
) -> dict[str, Any]:
    return capsule_cas.advance_capsule_v6_adreno_pass(
        canonical_path=canonical,
        transition_spec_path=spec_path,
        repository_root=repository,
        fault_injector=fault_injector,
    )


def _adreno_campaign_operation(spec: dict[str, Any]) -> dict[str, Any]:
    return next(
        operation
        for operation in spec["mutation"]["operations"]
        if operation["path"] == ["last_verified_campaign_state"]
    )


def test_v6_adreno_pass_parent_pin_and_schema_are_exact() -> None:
    payload = CANONICAL_V6_ADRENO_PASS_PARENT.read_bytes()

    assert capsule_cas.sha256_bytes(payload) == (
        capsule_cas.EXPECTED_V6_ADRENO_PASS_PARENT_SHA256
    )
    assert capsule_cas.strict_yaml_loads(payload)["schema_version"] == (
        capsule_cas.V6_SCHEMA
    )


def test_v6_adreno_pass_derivation_is_deterministic(tmp_path: Path) -> None:
    repository, canonical, _spec_path, spec = _setup_adreno_pass(tmp_path)
    parent = capsule_cas.strict_yaml_loads(canonical.read_bytes())
    validated = capsule_cas.validate_v6_adreno_pass_spec(spec, repository)

    first = capsule_cas.derive_v6_adreno_pass_child_capsule(parent, validated)
    second = capsule_cas.derive_v6_adreno_pass_child_capsule(parent, validated)

    assert capsule_cas.deterministic_yaml(first) == capsule_cas.deterministic_yaml(
        second
    )
    assert first["schema_version"] == capsule_cas.V6_SCHEMA
    assert first["evidence_cutoff_utc"] == ADRENO_PASS_CUTOFF
    assert first["success_terminal"]["section_0_5_satisfied"] is False


def test_v6_adreno_pass_archives_and_seals_v2_transaction(
    tmp_path: Path,
) -> None:
    repository, canonical, spec_path, spec = _setup_adreno_pass(tmp_path)
    parent_bytes = canonical.read_bytes()

    result = _execute_adreno_pass(repository, canonical, spec_path)

    assert result["status"] == "complete"
    assert result["parent_capsule_sha256"] == (
        capsule_cas.EXPECTED_V6_ADRENO_PASS_PARENT_SHA256
    )
    assert Path(result["archive_path"]).read_bytes() == parent_bytes
    assert Path(result["archive_path"]).name == (
        f"{capsule_cas.EXPECTED_V6_ADRENO_PASS_PARENT_SHA256}.yaml"
    )
    receipt = capsule_cas.strict_json_loads(Path(result["receipt_path"]).read_bytes())
    assert receipt["schema_version"] == capsule_cas.V6_RECEIPT_SCHEMA
    assert receipt["transition_spec"]["schema_version"] == (capsule_cas.V6_SPEC_SCHEMA)
    assert receipt["capsule"]["parent"]["schema_version"] == (capsule_cas.V6_SCHEMA)
    assert receipt["capsule"]["child"]["schema_version"] == (capsule_cas.V6_SCHEMA)
    assert receipt["bindings"] == spec["bindings"]
    completion = capsule_cas.strict_json_loads(
        Path(result["completion_path"]).read_bytes()
    )
    assert completion["schema_version"] == capsule_cas.V6_COMPLETION_SCHEMA
    assert completion["parent_capsule_sha256"] == (
        capsule_cas.EXPECTED_V6_ADRENO_PASS_PARENT_SHA256
    )
    assert completion["receipt_sha256"] == result["receipt_sha256"]


def test_v6_adreno_pass_completed_transaction_is_idempotent(
    tmp_path: Path,
) -> None:
    repository, canonical, spec_path, _spec = _setup_adreno_pass(tmp_path)
    first = _execute_adreno_pass(repository, canonical, spec_path)
    child_before = canonical.read_bytes()
    receipt_before = Path(first["receipt_path"]).read_bytes()
    completion_before = Path(first["completion_path"]).read_bytes()

    second = _execute_adreno_pass(repository, canonical, spec_path)

    assert second["status"] == "already_complete"
    assert second["child_capsule_sha256"] == first["child_capsule_sha256"]
    assert canonical.read_bytes() == child_before
    assert Path(first["receipt_path"]).read_bytes() == receipt_before
    assert Path(first["completion_path"]).read_bytes() == completion_before


@pytest.mark.parametrize(
    "phase",
    ["after_archive", "after_receipt", "after_replace", "after_completion"],
)
def test_v6_adreno_pass_fault_recovery_is_exact(
    tmp_path: Path,
    phase: str,
) -> None:
    repository, canonical, spec_path, _spec = _setup_adreno_pass(tmp_path)
    with pytest.raises(InjectedCrash):
        _execute_adreno_pass(
            repository,
            canonical,
            spec_path,
            fault_injector=_crash_at(phase),
        )

    observed_schema = capsule_cas.strict_yaml_loads(canonical.read_bytes())[
        "schema_version"
    ]
    assert observed_schema == capsule_cas.V6_SCHEMA
    if phase in {"after_archive", "after_receipt"}:
        assert capsule_cas.sha256_bytes(canonical.read_bytes()) == (
            capsule_cas.EXPECTED_V6_ADRENO_PASS_PARENT_SHA256
        )

    result = _execute_adreno_pass(repository, canonical, spec_path)

    expected_status = (
        "complete"
        if phase in {"after_archive", "after_receipt"}
        else "already_complete"
    )
    assert result["status"] == expected_status
    assert Path(result["completion_path"]).is_file()


def test_v6_adreno_pass_foreign_child_conflict_never_overwrites(
    tmp_path: Path,
) -> None:
    repository, canonical, spec_path, _spec = _setup_adreno_pass(tmp_path)
    with pytest.raises(InjectedCrash):
        _execute_adreno_pass(
            repository,
            canonical,
            spec_path,
            fault_injector=_crash_at("after_archive"),
        )
    foreign = b"schema_version: foreign-v6-child\n"
    canonical.write_bytes(foreign)

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        _execute_adreno_pass(repository, canonical, spec_path)

    assert raised.value.code == "canonical_compare_and_swap_conflict"
    assert canonical.read_bytes() == foreign


def test_v6_adreno_pass_rejects_wrong_profile_entrypoints(
    tmp_path: Path,
) -> None:
    repository, canonical, spec_path, spec = _setup_adreno_pass(tmp_path)
    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_v6_spec(spec, repository)
    assert raised.value.code == "expected_parent_sha256_mismatch"

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.advance_capsule_v5_to_v6(
            canonical_path=canonical,
            transition_spec_path=spec_path,
            repository_root=repository,
        )
    assert raised.value.code == "expected_parent_sha256_mismatch"
    assert capsule_cas.sha256_bytes(canonical.read_bytes()) == (
        capsule_cas.EXPECTED_V6_ADRENO_PASS_PARENT_SHA256
    )

    old_profile_root = tmp_path / "old_profile"
    old_profile_root.mkdir()
    old_repository, _old_canonical, _old_spec_path, old_spec = _setup(old_profile_root)
    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_v6_adreno_pass_spec(old_spec, old_repository)
    assert raised.value.code == "expected_parent_sha256_mismatch"


@pytest.mark.parametrize("field", ["source_commit", "evidence_commit"])
@pytest.mark.parametrize("width", [40, 64])
def test_v6_adreno_pass_rejects_zero_commit_placeholders(
    tmp_path: Path,
    field: str,
    width: int,
) -> None:
    repository, _canonical, _spec_path, spec = _setup_adreno_pass(tmp_path)
    spec["bindings"][field]["commit_sha"] = "0" * width
    _adreno_campaign_operation(spec)["value"][field] = "0" * width

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_v6_adreno_pass_spec(spec, repository)

    assert raised.value.code == f"v6_{field}_placeholder_unresolved"


def test_v5_to_v6_profile_also_rejects_zero_evidence_placeholder(
    tmp_path: Path,
) -> None:
    repository, _canonical, _spec_path, spec = _setup(tmp_path)
    spec["bindings"]["evidence_commit"]["commit_sha"] = "0" * 40
    _campaign_operation(spec)["value"]["evidence_commit"] = "0" * 40

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_v6_spec(spec, repository)

    assert raised.value.code == "v6_evidence_commit_placeholder_unresolved"


@pytest.mark.parametrize(
    ("field", "foreign_value", "error_code"),
    [
        (
            "source_commit",
            "c" * 40,
            "v6_campaign_state_source_commit_binding_mismatch",
        ),
        (
            "evidence_commit",
            "c" * 40,
            "v6_campaign_state_evidence_commit_binding_mismatch",
        ),
        (
            "frontier_root_sha256",
            "c" * 64,
            "v6_campaign_state_frontier_root_sha256_binding_mismatch",
        ),
        (
            "parent_capsule_sha256",
            "c" * 64,
            "v6_campaign_state_parent_capsule_sha256_binding_mismatch",
        ),
    ],
)
def test_v6_adreno_pass_campaign_state_cross_bindings_are_exact(
    tmp_path: Path,
    field: str,
    foreign_value: str,
    error_code: str,
) -> None:
    repository, _canonical, _spec_path, spec = _setup_adreno_pass(tmp_path)
    _adreno_campaign_operation(spec)["value"][field] = foreign_value

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_v6_adreno_pass_spec(spec, repository)

    assert raised.value.code == error_code


def test_v6_adreno_pass_cli_is_dedicated_and_exact() -> None:
    process = subprocess.run(
        [sys.executable, str(V6_ADRENO_PASS_CLI), "--help"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert process.returncode == 0
    assert "bounded Adreno pass" in " ".join(process.stdout.split())
    assert "--transition-spec" in process.stdout


def _copy_cur0s_exact_artifact(
    repository: Path,
    role: str,
    expected: dict[str, Any],
) -> dict[str, Any]:
    relative = expected["local_path"]
    source = ROOT / relative
    destination = repository / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = source.read_bytes()
    destination.write_bytes(payload)
    assert capsule_cas.sha256_bytes(payload) == expected["sha256"]
    assert len(payload) == expected["bytes"]
    return capsule_cas._exact_local_artifact(
        role,
        expected["sha256"],
        expected["bytes"],
        relative,
    )


def _cur0s_exact_bindings(repository: Path) -> dict[str, Any]:
    frontier_path = "runtime/reports/apex_frontier/frontier_event_20260711T192408Z.json"
    frontier_expected = {
        "sha256": capsule_cas._CUR0S_EXACT_FRONTIER_SHA256,
        "bytes": 10398,
        "local_path": frontier_path,
    }
    frontier = _copy_cur0s_exact_artifact(
        repository,
        "frontier_root",
        frontier_expected,
    )
    selector = copy.deepcopy(frontier)
    selector["role"] = "maximal_selector"
    preregistrations = [
        _copy_cur0s_exact_artifact(repository, role, expected)
        for role, expected in (
            capsule_cas._CUR0S_EXACT_PREREGISTRATION_ARTIFACTS.items()
        )
    ]
    sanitized_reports = [
        _copy_cur0s_exact_artifact(repository, role, expected)
        for role, expected in capsule_cas._CUR0S_EXACT_SANITIZED_ARTIFACTS.items()
    ]
    prd = _copy_cur0s_exact_artifact(
        repository,
        "governing_prd",
        {
            "sha256": (
                "725d0ad6ac77fdcfc06a2635c7552cc414e0ed48f30fbd0f7f7ec38720493a3c"
            ),
            "bytes": 209401,
            "local_path": (
                "docs/PRD-GEMMA4-E4B-PHONE-NATIVE-QNN-LEARNING-CELL-"
                "2026-07-10.md"
            ),
        },
    )
    audit = _copy_cur0s_exact_artifact(
        repository,
        "corpus_readiness_audit",
        {
            "sha256": (
                "c3a5d5eacf424f6e50ae0a170873d1c80e566581e22031a8f64bc899f8eec0fa"
            ),
            "bytes": 43722,
            "local_path": (
                "docs/APEX-C1-C4-CORPUS-READINESS-AND-INTEGRATION-AUDIT-"
                "2026-07-10.md"
            ),
        },
    )
    access = _copy_cur0s_exact_artifact(
        repository,
        "access_resource_refresh",
        {
            "sha256": (
                "7b2b6d506b3ab82a17008edc4c79dd51512f6f9598e3db37cd1bb6f5ee4331ca"
            ),
            "bytes": 3552,
            "local_path": (
                "runtime/reports/apex_frontier/access_refresh_20260711T020533Z.json"
            ),
        },
    )
    preserved_sha256 = [
        capsule_cas.EXPECTED_V6_CUR0S_EXACT_PARENT_SHA256,
        capsule_cas._CUR0S_EXACT_FRONTIER_SHA256,
        access["sha256"],
        *(artifact["sha256"] for artifact in preregistrations),
        *(artifact["sha256"] for artifact in sanitized_reports),
        "604931c652f74c8160c076edf8f80ef65570cab3c4ac7f849fb1ba84526309e9",
        "9502f57f55e57fc5008ebbeec749bccaa0639ebefee8b8b212ee7ff53817ed05",
        prd["sha256"],
        audit["sha256"],
        "b2f617766b660237ddfd329c6b7fa2370f9a2641983e71915b4cd71c6d31bacc",
    ]
    return {
        "frontier": frontier,
        "preregistrations": preregistrations,
        "maximal_selector": selector,
        "lease": {
            "lease_id": "current_user_sovereign_frontier_campaign_20260711",
            "expires_at_utc": "2026-07-12T01:13:53Z",
            "artifact": access,
            "resource_slice": {
                "additional_paid_capacity": False,
                "comet_payload": "hash_bound_metadata_only",
                "github_repository": "Zer0pa/Polymath-AI",
                "huggingface_visibility": "private_revision_pinned_only",
                "phone_adb_serial_sha256": (
                    "383e1fef6040334134430241a105f7d900f6d924e485fdc858441e734d3ae0f4"
                ),
                "phone_model": "NX789J",
                "phone_private_raw_upload": False,
                "public_release": False,
                "runpod": "uh57jg7iguwqth_existing_only",
            },
        },
        "inputs": [
            prd,
            audit,
            {
                "role": "living_engineering_concept",
                "locator": (
                    "external-frozen://Polymath-AI-Mobile-Native-Gemma4-E4B-"
                    "Heterogeneous-Learning"
                ),
                "sha256": (
                    "b2f617766b660237ddfd329c6b7fa2370f9a2641983e71915b4cd71c6d31bacc"
                ),
                "bytes": 186381,
                "custody": "external_frozen",
            },
        ],
        "raw_reports": [
            {
                "role": "cur0s_exact_identity_overlay_private",
                "locator": (
                    "phone:///data/data/com.termux/files/home/"
                    "polymath_gemma4_e4b_frontier/"
                    "20260711T211344Z_cur0s_static_identity_v1/candidate_runs/"
                    "candidate-001/exact_identity_overlay.private.jsonl"
                ),
                "sha256": (
                    "604931c652f74c8160c076edf8f80ef65570cab3c4ac7f849fb1ba84526309e9"
                ),
                "bytes": 58860037,
                "custody": "phone_private",
            }
        ],
        "sanitized_reports": sanitized_reports,
        "transitions": [
            {
                "subject_id": "CUR-0S-CURRENT-EXACT-IDENTITY",
                "subject_kind": "candidate",
                "from": "selected_frozen_unobserved",
                "to": "passed_scope",
                "evidence_sha256": capsule_cas._CUR0S_EXACT_RECEIPT_SHA256,
                "reason": (
                    "physical_and_exact_identity_passed_without_CUR0S_promotion"
                ),
            }
        ],
        "rollback": {
            "rollback_base": {
                "role": "parent_capsule_archive",
                "locator": (
                    "archive://docs/current_reality/v6/"
                    f"{capsule_cas.EXPECTED_V6_CUR0S_EXACT_PARENT_SHA256}"
                ),
                "sha256": capsule_cas.EXPECTED_V6_CUR0S_EXACT_PARENT_SHA256,
                "bytes": 61531,
                "custody": "repository_archive",
            },
            "preserved_sha256": preserved_sha256,
            "invalidated_sha256": [],
            "disposition": (
                "preserve_CUR0S_physical_and_exact_identity_passed_scope_"
                "without_CUR0S_admission"
            ),
        },
        "source_commit": {
            "repository": "Zer0pa/Polymath-AI",
            "commit_sha": "c" * 40,
            "scope": [
                "exact_v6_CUR0S_identity_CAS_profile",
                "dedicated_v6_CUR0S_identity_CLI",
                "fail_closed_profile_and_race_tests",
            ],
        },
        "evidence_commit": {
            "repository": "Zer0pa/Polymath-AI",
            "commit_sha": capsule_cas._CUR0S_EXACT_EVIDENCE_COMMIT,
            "scope": ["CUR0S_exact_identity_phone_evidence"],
        },
        "scoped_push_receipt": None,
    }


def _cur0s_exact_operations(
    parent: dict[str, Any], bindings: dict[str, Any]
) -> list[dict[str, Any]]:
    campaign_state = capsule_cas._cur0s_exact_expected_campaign(
        parent,
        {"bindings": bindings},
    )
    return [
        {
            "op": "replace",
            "path": ["evidence_cutoff_utc"],
            "expected_old_sha256": capsule_cas.value_sha256(
                parent["evidence_cutoff_utc"]
            ),
            "value": CUR0S_EXACT_CUTOFF,
        },
        {
            "op": "replace",
            "path": ["corpus_curriculum", "curriculum_gates", "CUR-0S"],
            "expected_old_sha256": capsule_cas.value_sha256(
                parent["corpus_curriculum"]["curriculum_gates"]["CUR-0S"]
            ),
            "value": capsule_cas._cur0s_exact_expected_gate(parent),
        },
        {
            "op": "replace",
            "path": ["measured_claims", "CUR_0S_CURRENT"],
            "expected_old_sha256": capsule_cas.value_sha256(
                parent["measured_claims"]["CUR_0S_CURRENT"]
            ),
            "value": capsule_cas._cur0s_exact_expected_claim(parent),
        },
        {
            "op": "replace",
            "path": ["frontier_execution_policy", "active_candidate"],
            "expected_old_sha256": capsule_cas.value_sha256(
                parent["frontier_execution_policy"]["active_candidate"]
            ),
            "value": "cur0s_successor_commercial_source_root_v1",
        },
        {
            "op": "replace",
            "path": ["frontier_execution_policy", "last_disposition"],
            "expected_old_sha256": capsule_cas.value_sha256(
                parent["frontier_execution_policy"]["last_disposition"]
            ),
            "value": capsule_cas._CUR0S_EXACT_DISPOSITION,
        },
        {
            "op": "replace",
            "path": ["current_design_decision"],
            "expected_old_sha256": capsule_cas.value_sha256(
                parent["current_design_decision"]
            ),
            "value": capsule_cas._cur0s_exact_expected_design(parent),
        },
        {
            "op": "replace",
            "path": ["next_action"],
            "expected_old_sha256": capsule_cas.value_sha256(parent["next_action"]),
            "value": capsule_cas._cur0s_exact_expected_next_action(parent),
        },
        {
            "op": "replace",
            "path": ["last_verified_campaign_state"],
            "expected_old_sha256": capsule_cas.value_sha256(
                parent["last_verified_campaign_state"]
            ),
            "value": campaign_state,
        },
    ]


def _setup_cur0s_exact(
    tmp_path: Path,
) -> tuple[Path, Path, Path, dict[str, Any]]:
    repository = tmp_path / "cur0s_exact_repository"
    repository.mkdir()
    canonical = repository / "capsule.yaml"
    canonical.write_bytes(CANONICAL_V6_CUR0S_EXACT_PARENT.read_bytes())
    parent = capsule_cas.strict_yaml_loads(canonical.read_bytes())
    bindings = _cur0s_exact_bindings(repository)
    spec = {
        "schema_version": capsule_cas.V6_SPEC_SCHEMA,
        "transaction_id": "capsule-v6-cur0s-exact-20260711T211747Z",
        "expected_parent_sha256": (
            capsule_cas.EXPECTED_V6_CUR0S_EXACT_PARENT_SHA256
        ),
        "evidence_cutoff_utc": CUR0S_EXACT_CUTOFF,
        "mutation": {"operations": _cur0s_exact_operations(parent, bindings)},
        "bindings": bindings,
    }
    spec_path = repository / "cur0s_exact_transition_spec.json"
    _write_json(spec_path, spec)
    return repository, canonical, spec_path, spec


def test_v6_cur0s_exact_parent_pin_and_derivation_are_exact(
    tmp_path: Path,
) -> None:
    payload = CANONICAL_V6_CUR0S_EXACT_PARENT.read_bytes()
    assert capsule_cas.sha256_bytes(payload) == (
        capsule_cas.EXPECTED_V6_CUR0S_EXACT_PARENT_SHA256
    )
    repository, canonical, _spec_path, spec = _setup_cur0s_exact(tmp_path)
    parent = capsule_cas.strict_yaml_loads(canonical.read_bytes())
    validated = capsule_cas.validate_v6_cur0s_exact_spec(spec, repository)
    first = capsule_cas.derive_v6_cur0s_exact_child_capsule(parent, validated)
    second = capsule_cas.derive_v6_cur0s_exact_child_capsule(parent, validated)
    assert capsule_cas.deterministic_yaml(first) == capsule_cas.deterministic_yaml(
        second
    )
    claim = first["measured_claims"]["CUR_0S_CURRENT"]
    assert claim["exact_identity_state"] == "passed_scope"
    assert claim["cur0s_static_pass_claimed"] is False
    assert first["frontier_execution_policy"]["frontier_root_sha256"] == (
        capsule_cas._CUR0S_EXACT_FRONTIER_SHA256
    )
    assert first["last_verified_campaign_state"]["frontier_root_sha256"] == (
        capsule_cas._CUR0S_EXACT_FRONTIER_SHA256
    )
    assert first["success_terminal"]["section_0_5_satisfied"] is False


def test_v6_cur0s_exact_cas_archives_seals_and_is_idempotent(
    tmp_path: Path,
) -> None:
    repository, canonical, spec_path, _spec = _setup_cur0s_exact(tmp_path)
    parent_bytes = canonical.read_bytes()
    first = capsule_cas.advance_capsule_v6_cur0s_exact(
        canonical_path=canonical,
        transition_spec_path=spec_path,
        repository_root=repository,
    )
    assert first["status"] == "complete"
    assert Path(first["archive_path"]).read_bytes() == parent_bytes
    completion = capsule_cas.strict_json_loads(
        Path(first["completion_path"]).read_bytes()
    )
    assert completion["parent_capsule_sha256"] == (
        capsule_cas.EXPECTED_V6_CUR0S_EXACT_PARENT_SHA256
    )
    second = capsule_cas.advance_capsule_v6_cur0s_exact(
        canonical_path=canonical,
        transition_spec_path=spec_path,
        repository_root=repository,
    )
    assert second["status"] == "already_complete"
    assert second["child_capsule_sha256"] == first["child_capsule_sha256"]


def test_v6_cur0s_exact_profile_forbids_CUR0S_promotion(tmp_path: Path) -> None:
    repository, canonical, _spec_path, spec = _setup_cur0s_exact(tmp_path)
    claim_operation = next(
        operation
        for operation in spec["mutation"]["operations"]
        if operation["path"] == ["measured_claims", "CUR_0S_CURRENT"]
    )
    claim_operation["value"]["cur0s_static_pass_claimed"] = True
    parent = capsule_cas.strict_yaml_loads(canonical.read_bytes())
    validated = capsule_cas.validate_v6_cur0s_exact_spec(spec, repository)
    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.derive_v6_cur0s_exact_child_capsule(parent, validated)
    assert raised.value.code == "cur0s_exact_claim_mismatch"


def test_v6_cur0s_exact_rejects_unexpected_authority_fields(tmp_path: Path) -> None:
    repository, canonical, _spec_path, spec = _setup_cur0s_exact(tmp_path)
    gate_operation = next(
        operation
        for operation in spec["mutation"]["operations"]
        if operation["path"]
        == ["corpus_curriculum", "curriculum_gates", "CUR-0S"]
    )
    gate_operation["value"]["science_authority_passed"] = True
    parent = capsule_cas.strict_yaml_loads(canonical.read_bytes())
    validated = capsule_cas.validate_v6_cur0s_exact_spec(spec, repository)

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.derive_v6_cur0s_exact_child_capsule(parent, validated)

    assert raised.value.code == "cur0s_exact_gate_mismatch"


def test_v6_cur0s_exact_rejects_campaign_success_rewrite(tmp_path: Path) -> None:
    repository, canonical, _spec_path, spec = _setup_cur0s_exact(tmp_path)
    campaign_operation = next(
        operation
        for operation in spec["mutation"]["operations"]
        if operation["path"] == ["last_verified_campaign_state"]
    )
    campaign_operation["value"]["campaign_status"] = "SUCCESS"
    parent = capsule_cas.strict_yaml_loads(canonical.read_bytes())
    validated = capsule_cas.validate_v6_cur0s_exact_spec(spec, repository)

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.derive_v6_cur0s_exact_child_capsule(parent, validated)

    assert raised.value.code == "cur0s_exact_campaign_mismatch"


def test_v6_cur0s_exact_rejects_incomplete_operation_surface(
    tmp_path: Path,
) -> None:
    repository, _canonical, _spec_path, spec = _setup_cur0s_exact(tmp_path)
    spec["mutation"]["operations"] = [
        operation
        for operation in spec["mutation"]["operations"]
        if operation["path"] != ["next_action"]
    ]

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_v6_cur0s_exact_spec(spec, repository)

    assert raised.value.code == "cur0s_exact_operation_surface_invalid"


def test_v6_cur0s_exact_rejects_unbounded_evidence_cutoff(tmp_path: Path) -> None:
    repository, _canonical, _spec_path, spec = _setup_cur0s_exact(tmp_path)
    future_cutoff = "2099-12-31T23:59:59Z"
    spec["evidence_cutoff_utc"] = future_cutoff
    cutoff_operation = next(
        operation
        for operation in spec["mutation"]["operations"]
        if operation["path"] == ["evidence_cutoff_utc"]
    )
    cutoff_operation["value"] = future_cutoff

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_v6_cur0s_exact_spec(spec, repository)

    assert raised.value.code == "cur0s_exact_evidence_cutoff_invalid"


def test_v6_cur0s_exact_rejects_authority_transition_binding(
    tmp_path: Path,
) -> None:
    repository, _canonical, _spec_path, spec = _setup_cur0s_exact(tmp_path)
    spec["bindings"]["transitions"][0]["to"] = "passed_authority"

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_v6_cur0s_exact_spec(spec, repository)

    assert raised.value.code == "cur0s_exact_transition_binding_invalid"


def test_v6_cur0s_exact_rejects_unrelated_sanitized_role(tmp_path: Path) -> None:
    repository, _canonical, _spec_path, spec = _setup_cur0s_exact(tmp_path)
    spec["bindings"]["sanitized_reports"][0]["role"] = (
        "unrelated_adreno_phone_receipt"
    )

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_v6_cur0s_exact_spec(spec, repository)

    assert raised.value.code == "cur0s_exact_sanitized_reports_roles_invalid"


def test_v6_cur0s_exact_rejects_foreign_evidence_commit(tmp_path: Path) -> None:
    repository, _canonical, _spec_path, spec = _setup_cur0s_exact(tmp_path)
    spec["bindings"]["evidence_commit"]["commit_sha"] = "d" * 40
    campaign_operation = next(
        operation
        for operation in spec["mutation"]["operations"]
        if operation["path"] == ["last_verified_campaign_state"]
    )
    campaign_operation["value"]["evidence_commit"] = "d" * 40

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.validate_v6_cur0s_exact_spec(spec, repository)

    assert raised.value.code == "cur0s_exact_evidence_commit_invalid"


def test_v6_cur0s_exact_detects_canonical_change_before_replace(
    tmp_path: Path,
) -> None:
    repository, canonical, spec_path, _spec = _setup_cur0s_exact(tmp_path)
    foreign = b"schema_version: foreign-racing-writer\n"

    def write_after_receipt(phase: str) -> None:
        if phase == "after_receipt":
            canonical.write_bytes(foreign)

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.advance_capsule_v6_cur0s_exact(
            canonical_path=canonical,
            transition_spec_path=spec_path,
            repository_root=repository,
            fault_injector=write_after_receipt,
        )

    assert raised.value.code == "canonical_changed_before_atomic_replace"
    assert canonical.read_bytes() == foreign


def test_v6_cur0s_exact_detects_canonical_change_after_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, canonical, spec_path, _spec = _setup_cur0s_exact(tmp_path)
    foreign = b"schema_version: foreign-during-canonical-stage\n"
    original_write = capsule_cas.write_exclusive_or_verify

    def write_then_race(
        path: Path,
        payload: bytes,
        context: str,
    ) -> None:
        original_write(path, payload, context)
        if context == "canonical_stage":
            canonical.write_bytes(foreign)

    monkeypatch.setattr(capsule_cas, "write_exclusive_or_verify", write_then_race)

    with pytest.raises(capsule_cas.CapsuleTransitionError) as raised:
        capsule_cas.advance_capsule_v6_cur0s_exact(
            canonical_path=canonical,
            transition_spec_path=spec_path,
            repository_root=repository,
        )

    assert raised.value.code == "canonical_changed_before_atomic_replace"
    assert canonical.read_bytes() == foreign


def test_v6_cur0s_exact_cli_is_dedicated_and_exact() -> None:
    process = subprocess.run(
        [sys.executable, str(V6_CUR0S_EXACT_CLI), "--help"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.returncode == 0
    assert "scoped CUR-0S physical and exact-identity evidence" in " ".join(
        process.stdout.split()
    )
    assert "--transition-spec" in process.stdout

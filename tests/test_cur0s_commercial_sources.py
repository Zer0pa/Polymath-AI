"""Tests for the frozen CUR-0S commercial-source acquisition contract."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import re
from typing import Any

import pytest

from polymath_ai.corpus import cur0s_commercial_sources as commercial


SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
STAGES = ("C1", "C2", "B23", "C3", "C4")

EXPECTED_OPENSTAX = {
    "openstax_biology_bundle_pre_transition": {
        "repository": "openstax/osbooks-biology-bundle",
        "commit_sha": "4460012626ee747bdb9db8c4418317798fbc67ce",
        "tree_sha": "f09b4ae56f850e5c287d6971ffb11d99da61856c",
        "license_sha256": (
            "0ff174546cbe3dd1287da231f9796618ac2f6e6595b2d11f567b2c9790f64868"
        ),
    },
    "openstax_chemistry_bundle_pre_transition": {
        "repository": "openstax/osbooks-chemistry-bundle",
        "commit_sha": "9928441ef0badc3ff024c6a1fe2842c0048ea858",
        "tree_sha": "937b9e2e8a8479d7f60c32db4ebecbbd4c010e91",
        "license_sha256": (
            "0ff174546cbe3dd1287da231f9796618ac2f6e6595b2d11f567b2c9790f64868"
        ),
    },
    "openstax_university_physics_bundle_pre_transition": {
        "repository": "openstax/osbooks-university-physics-bundle",
        "commit_sha": "9364cbc32511afea3d4695e70a88687ffc1a3696",
        "tree_sha": "9cd4a12b01ebcb58c891e43e7a30f70ffb200c63",
        "license_sha256": (
            "38a27c0f017da132e9a04ec8be91ead41cf8a55d85018c2de50c2b831dcfac38"
        ),
    },
    "openstax_astronomy_pre_transition": {
        "repository": "openstax/osbooks-astronomy",
        "commit_sha": "9d7e69a2e0c9a651ad42254b9a93b701a6b08c10",
        "tree_sha": "aadd140722b936185ebbb633e83d0b22681788a2",
        "license_sha256": (
            "0ff174546cbe3dd1287da231f9796618ac2f6e6595b2d11f567b2c9790f64868"
        ),
    },
    "openstax_anatomy_physiology_pre_transition": {
        "repository": "openstax/osbooks-anatomy-physiology",
        "commit_sha": "3f855aef2941c1da9c01db904d45b129e26106f2",
        "tree_sha": "2c5a9dc2b84bf2aadb5fb0f0c43dfb0d052f3063",
        "license_sha256": (
            "0ff174546cbe3dd1287da231f9796618ac2f6e6595b2d11f567b2c9790f64868"
        ),
    },
}


def _sha256(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def _sources() -> tuple[commercial.DirectSourceSpec | commercial.GitSourceSpec, ...]:
    return (*commercial.DIRECT_SOURCES, *commercial.GIT_SOURCES)


def _verification(
    source: commercial.DirectSourceSpec | commercial.GitSourceSpec,
) -> dict[str, Any]:
    receipt_contract = commercial.source_contract()["artifact_receipt_contract"]
    kind = "direct" if isinstance(source, commercial.DirectSourceSpec) else "git"
    fields = set(receipt_contract[f"{kind}_verification_fields"])
    true_fields = set(receipt_contract["verification_booleans_required_true"])
    value: dict[str, Any] = {field: True for field in fields & true_fields}
    value["content_manifest_sha256"] = _sha256(f"manifest:{source.source_id}")

    if isinstance(source, commercial.DirectSourceSpec):
        value.update(
            {
                "conditional_lock_mode": source.conditional_lock_mode,
                "observed_content_type": source.media_type,
                "observed_etag": source.expected_etag,
                "observed_final_url": source.url,
                "observed_last_modified": source.expected_last_modified,
                "observed_payload_rights_evidence": (
                    source.expected_payload_rights_records()
                ),
                "payload_rights_evidence_root_sha256": commercial.canonical_sha256(
                    source.expected_payload_rights_records()
                ),
                "rights_admission_basis": source.rights_admission_basis,
                "external_rights_evidence_used_for_admission": False,
                "server_conditional_lock_enforced": (
                    source.conditional_lock_mode
                    == "if_match_enforced_observed_412_on_mismatch"
                ),
                "transport_conditionals_identity_role": "defense_in_depth_only",
            }
        )
    else:
        value.update(
            {
                "observed_commit_sha": source.commit_sha,
                "observed_file_count": source.selected_file_count,
                "observed_license_sha256": "sha256:" + source.license_sha256,
                "observed_selected_bytes": source.selected_bytes,
                "observed_tree_sha": source.tree_sha,
            }
        )

    assert set(value) == fields
    return value


def _artifact(
    source: commercial.DirectSourceSpec | commercial.GitSourceSpec,
) -> dict[str, Any]:
    byte_count = (
        source.expected_bytes
        if isinstance(source, commercial.DirectSourceSpec)
        else source.selected_bytes
    )
    local_locator = f"phone_private/cur0s/raw/{source.source_id}"
    if isinstance(source, commercial.DirectSourceSpec):
        digest = (
            "sha256:" + source.expected_sha256
            if source.expected_sha256 is not None
            else _sha256(f"artifact:{source.source_id}")
        )
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
    else:
        quotient, remainder = divmod(byte_count, source.selected_file_count)
        files = [
            {
                "relative_path": f"fixture/{index:04d}.bin",
                "bytes": quotient + (1 if index < remainder else 0),
                "sha256": _sha256(f"{source.source_id}:{index}"),
            }
            for index in range(source.selected_file_count)
        ]
        content_manifest = {
            "schema_version": "cur0s_git_sparse_content_manifest_v1",
            "commit_sha": source.commit_sha,
            "tree_sha": source.tree_sha,
            "files": files,
        }
        digest = commercial.canonical_sha256(content_manifest)
    verification = _verification(source)
    verification["content_manifest_sha256"] = commercial.canonical_sha256(
        content_manifest
    )
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
        "content_manifest": content_manifest,
        "verification": verification,
    }


def _artifacts() -> list[dict[str, Any]]:
    return [_artifact(source) for source in _sources()]


def _contract_without_root() -> dict[str, Any]:
    body = commercial.source_contract()
    body.pop("contract_root_sha256")
    return body


def _root_without_digest(root: dict[str, Any]) -> dict[str, Any]:
    body = deepcopy(root)
    body.pop("source_root_sha256")
    return body


def test_contract_is_deterministic_canonical_and_detached() -> None:
    first = commercial.source_contract()
    second = commercial.source_contract()

    assert first == second
    assert first is not second
    assert SHA256_RE.fullmatch(first["contract_root_sha256"])
    assert first["contract_root_sha256"] == commercial.canonical_sha256(
        _contract_without_root()
    )
    assert commercial.validate_source_contract(first) == first

    first["direct_sources"][0]["stages"].append("not-a-stage")
    assert commercial.source_contract() == second
    with pytest.raises(
        commercial.CommercialSourceError,
        match="commercial_source_contract_mismatch",
    ):
        commercial.validate_source_contract(first)


def test_contract_has_exact_ordered_16_source_roster_and_stage_coverage() -> None:
    sources = _sources()
    expected_ids = [source.source_id for source in sources]
    contract = commercial.source_contract()
    contract_ids = [
        source["source_id"]
        for source in (*contract["direct_sources"], *contract["git_sources"])
    ]

    assert len(sources) == 16
    assert contract["source_count"] == 16
    assert contract_ids == expected_ids
    assert len(set(contract_ids)) == 16
    assert {stage for source in sources for stage in source.stages} == set(STAGES)
    for stage in STAGES:
        assert [source.source_id for source in sources if stage in source.stages]

    assert "usda_nalt_core_2024" in expected_ids
    assert not any("nalt_full" in source_id for source_id in expected_ids)
    assert [
        source_id
        for source_id in expected_ids
        if source_id.startswith("siyavula_mathematics_")
    ] == [
        "siyavula_mathematics_grade_10_cc_by",
        "siyavula_mathematics_grade_11_cc_by",
        "siyavula_mathematics_grade_12_cc_by",
    ]


def test_artifact_receipt_contract_exposes_exact_verification_shapes() -> None:
    receipt = commercial.source_contract()["artifact_receipt_contract"]
    common = {
        "content_manifest_sha256",
        "identity_verified",
        "phone_private",
        "raw_fsynced",
        "rights_verified",
        "stage_binding_verified",
    }
    direct_only = {
        "conditional_lock_mode",
        "cryptographic_payload_identity_verified",
        "https_only",
        "license_markers_verified",
        "metadata_match",
        "observed_etag",
        "observed_final_url",
        "observed_last_modified",
        "observed_content_type",
        "path_safety_verified",
        "pre_post_metadata_match",
        "structure_verified",
        "server_conditional_lock_enforced",
        "transport_conditionals_identity_role",
        "observed_payload_rights_evidence",
        "payload_rights_evidence_root_sha256",
        "rights_admission_basis",
        "external_rights_evidence_used_for_admission",
    }
    git_only = {
        "commit_verified",
        "cryptographic_payload_identity_verified",
        "license_verified",
        "observed_commit_sha",
        "observed_file_count",
        "observed_license_sha256",
        "observed_selected_bytes",
        "observed_tree_sha",
        "path_safety_verified",
        "symlink_policy_verified",
        "tree_verified",
        "worktree_clean",
    }

    assert set(receipt["common_verification_fields"]) == common
    assert set(receipt["direct_verification_fields"]) == common | direct_only
    assert set(receipt["git_verification_fields"]) == common | git_only
    assert receipt["direct_size_etag_last_modified_and_final_url_must_match"] is True
    assert (
        receipt["git_commit_tree_license_count_and_selected_bytes_must_match"] is True
    )
    assert receipt["transport_metadata_is_not_upstream_cryptographic_identity"] is True


def test_source_root_is_deterministic_hash_bound_and_claim_limited() -> None:
    artifacts = _artifacts()
    first = commercial.build_source_root(artifacts)
    second = commercial.build_source_root(deepcopy(artifacts))

    assert first == second
    assert first["source_artifact_count"] == 16
    assert first["source_root_sha256"] == commercial.canonical_sha256(
        _root_without_digest(first)
    )
    assert (
        first["contract_root_sha256"]
        == commercial.source_contract()["contract_root_sha256"]
    )
    assert first["source_root_state"] == "passed_scope"
    assert first["all_source_identity_and_rights_gates_passed"] is True
    assert first["first_next_blocker"] == "private_C4_COM_mirror"
    assert first["rights_classes"] == ["A", "B"]

    for field in (
        "private_HF_mirror_completed",
        "c4_rx_content_present",
        "semantic_rows_compiled",
        "near_semantic_arm_C_executed",
        "connected_split_assigned",
        "cur0s_static_pass_claimed",
        "target_data_learning_claimed",
        "authority_claimed",
    ):
        assert first[field] is False

    expected_stage_ids = {
        stage: [source.source_id for source in _sources() if stage in source.stages]
        for stage in STAGES
    }
    assert first["stage_source_ids"] == expected_stage_ids


def test_source_root_does_not_depend_on_mapping_insertion_order() -> None:
    artifacts = _artifacts()
    reordered = []
    for artifact in artifacts:
        item = dict(reversed(list(artifact.items())))
        item["verification"] = dict(reversed(list(item["verification"].items())))
        reordered.append(item)

    assert commercial.build_source_root(reordered) == commercial.build_source_root(
        artifacts
    )


def test_source_root_rejects_missing_reordered_or_duplicate_sources() -> None:
    artifacts = _artifacts()
    cases = [
        artifacts[:-1],
        list(reversed(artifacts)),
        [*artifacts[:-1], deepcopy(artifacts[-2])],
    ]

    for invalid in cases:
        with pytest.raises(
            commercial.CommercialSourceError,
            match="source_artifact_order_or_identity_mismatch",
        ):
            commercial.build_source_root(invalid)


def test_source_root_rejects_non_mapping_artifact_fail_closed() -> None:
    artifacts: list[Any] = _artifacts()
    artifacts[0] = []

    with pytest.raises(
        commercial.CommercialSourceError,
        match="source_artifact_not_mapping",
    ):
        commercial.build_source_root(artifacts)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("acquisition_mode", "unverified_copy"),
        ("release_identity", "moving-latest"),
        ("stages", ["C1"]),
        ("license_id", "unknown"),
        ("license_class", "A"),
        ("rights_proof", "card-level-claim-only"),
        ("bytes", 1),
    ],
)
def test_direct_artifact_identity_rights_and_stage_fields_are_strictly_bound(
    field: str,
    invalid: Any,
) -> None:
    artifacts = _artifacts()
    artifacts[0][field] = invalid

    with pytest.raises(commercial.CommercialSourceError, match=f"{field}.*mismatch"):
        commercial.build_source_root(artifacts)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("acquisition_mode", "https_file"),
        ("release_identity", "openstax/main"),
        ("stages", ["C3"]),
        ("license_id", "CC-BY-NC-SA-4.0"),
        ("license_class", "C"),
        ("rights_proof", "current-main-license"),
        ("bytes", 1),
    ],
)
def test_git_artifact_identity_rights_and_stage_fields_are_strictly_bound(
    field: str,
    invalid: Any,
) -> None:
    artifacts = _artifacts()
    artifacts[-1][field] = invalid

    with pytest.raises(commercial.CommercialSourceError, match=f"{field}.*mismatch"):
        commercial.build_source_root(artifacts)


def test_artifact_field_set_is_exact() -> None:
    missing = _artifacts()
    missing[0].pop("rights_proof")
    extra = _artifacts()
    extra[0]["raw_payload"] = "forbidden"

    for artifacts in (missing, extra):
        with pytest.raises(
            commercial.CommercialSourceError,
            match="source_artifact_field_set_mismatch",
        ):
            commercial.build_source_root(artifacts)


@pytest.mark.parametrize(
    "invalid",
    [None, True, "", "0" * 64, "sha256:", "sha256:" + "A" * 64, "sha256:" + "0" * 63],
)
def test_artifact_sha256_must_be_exact_lowercase_prefixed_digest(invalid: Any) -> None:
    artifacts = _artifacts()
    artifacts[0]["sha256"] = invalid

    with pytest.raises(
        commercial.CommercialSourceError,
        match="source_artifact_sha256_invalid",
    ):
        commercial.build_source_root(artifacts)


@pytest.mark.parametrize(
    "invalid",
    ["", "/absolute/path", "../escape", "a/../escape", "a//b", "a\\b", "a\x00b"],
)
def test_artifact_local_locator_must_be_safe_phone_relative_path(invalid: str) -> None:
    artifacts = _artifacts()
    artifacts[0]["local_locator"] = invalid

    with pytest.raises(
        commercial.CommercialSourceError,
        match="source_artifact_local_locator_invalid",
    ):
        commercial.build_source_root(artifacts)


def test_artifact_verification_requires_exact_field_set() -> None:
    missing = _artifacts()
    missing[0]["verification"].pop("identity_verified")
    extra = _artifacts()
    extra[0]["verification"]["narrative_pass"] = True

    for artifacts in (missing, extra):
        with pytest.raises(
            commercial.CommercialSourceError,
            match="source_artifact_verification_field_set_mismatch",
        ):
            commercial.build_source_root(artifacts)


@pytest.mark.parametrize("invalid", [False, None, 0, 1, "true"])
def test_artifact_verification_booleans_require_literal_true(invalid: Any) -> None:
    artifacts = _artifacts()
    artifacts[0]["verification"]["rights_verified"] = invalid

    with pytest.raises(
        commercial.CommercialSourceError,
        match="source_artifact_rights_verified_not_verified",
    ):
        commercial.build_source_root(artifacts)


@pytest.mark.parametrize("invalid", [True, None, 0, "false"])
def test_external_rights_evidence_can_never_be_admission_bearing(invalid: Any) -> None:
    artifacts = _artifacts()
    artifacts[0]["verification"]["external_rights_evidence_used_for_admission"] = (
        invalid
    )
    with pytest.raises(
        commercial.CommercialSourceError,
        match="external_rights_evidence_used_for_admission",
    ):
        commercial.build_source_root(artifacts)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda verification: verification["observed_payload_rights_evidence"][
                0
            ].__setitem__("locator", "elsewhere"),
            "payload_rights_evidence_mismatch",
        ),
        (
            lambda verification: verification.__setitem__(
                "payload_rights_evidence_root_sha256", "sha256:" + "0" * 64
            ),
            "payload_rights_evidence_root_mismatch",
        ),
        (
            lambda verification: verification.__setitem__(
                "rights_admission_basis", "external_narrative"
            ),
            "rights_admission_basis_mismatch",
        ),
    ],
)
def test_payload_rights_evidence_records_and_root_are_not_naked_booleans(
    mutation, message: str
) -> None:
    artifacts = _artifacts()
    mutation(artifacts[0]["verification"])
    with pytest.raises(commercial.CommercialSourceError, match=message):
        commercial.build_source_root(artifacts)


@pytest.mark.parametrize(
    ("field", "invalid", "error"),
    [
        ("observed_etag", "moving", "observed_etag_mismatch"),
        (
            "observed_last_modified",
            "Thu, 01 Jan 1970 00:00:00 GMT",
            "observed_last_modified_mismatch",
        ),
        (
            "observed_final_url",
            "https://example.invalid/latest",
            "observed_final_url_mismatch",
        ),
        ("content_manifest_sha256", "not-a-digest", "content_manifest_sha256_invalid"),
    ],
)
def test_direct_transport_and_content_verification_is_strict(
    field: str,
    invalid: Any,
    error: str,
) -> None:
    artifacts = _artifacts()
    artifacts[0]["verification"][field] = invalid

    with pytest.raises(commercial.CommercialSourceError, match=error):
        commercial.build_source_root(artifacts)


def test_content_manifests_are_derived_not_disconnected_digest_assertions() -> None:
    direct = _artifacts()
    direct[0]["content_manifest"]["files"][0]["bytes"] -= 1
    with pytest.raises(
        commercial.CommercialSourceError, match="content_manifest_hash_mismatch"
    ):
        commercial.build_source_root(direct)

    git = _artifacts()
    git[-1]["sha256"] = _sha256("disconnected-git-artifact")
    with pytest.raises(
        commercial.CommercialSourceError, match="git_manifest_identity_mismatch"
    ):
        commercial.build_source_root(git)

    reordered = _artifacts()
    reordered[-1]["content_manifest"]["files"].reverse()
    reordered[-1]["verification"]["content_manifest_sha256"] = (
        commercial.canonical_sha256(reordered[-1]["content_manifest"])
    )
    reordered[-1]["sha256"] = reordered[-1]["verification"]["content_manifest_sha256"]
    with pytest.raises(
        commercial.CommercialSourceError, match="git_manifest_paths_invalid"
    ):
        commercial.build_source_root(reordered)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("observed_commit_sha", "0" * 40),
        ("observed_tree_sha", "0" * 40),
        ("observed_license_sha256", "sha256:" + "0" * 64),
        ("observed_file_count", 1),
        ("observed_selected_bytes", 1),
    ],
)
def test_git_commit_tree_license_and_selection_verification_is_strict(
    field: str,
    invalid: Any,
) -> None:
    artifacts = _artifacts()
    artifacts[-1]["verification"][field] = invalid

    with pytest.raises(commercial.CommercialSourceError, match=f"{field}_mismatch"):
        commercial.build_source_root(artifacts)


def test_openstax_snapshots_have_exact_pre_transition_git_and_license_identity() -> (
    None
):
    observed = {source.source_id: source for source in commercial.GIT_SOURCES}

    assert set(observed) == set(EXPECTED_OPENSTAX)
    for source_id, expected in EXPECTED_OPENSTAX.items():
        source = observed[source_id]
        assert source.repository == expected["repository"]
        assert source.commit_sha == expected["commit_sha"]
        assert source.tree_sha == expected["tree_sha"]
        assert source.license_sha256 == expected["license_sha256"]
        assert source.release_identity == (
            f"{source.repository}@{source.commit_sha}_tree_{source.tree_sha}"
        )
        assert source.license_id == "CC-BY-4.0"
        assert source.license_class == "B"
        assert source.stages == ("C4",)
        assert source.acquisition_mode == "git_sparse_commit"
        assert source.clone_url == f"https://github.com/{source.repository}.git"
        assert source.selected_paths == (
            "LICENSE",
            "README.md",
            "META-INF",
            "collections",
            "modules",
        )
        assert re.fullmatch(r"[0-9a-f]{40}", source.commit_sha)
        assert re.fullmatch(r"[0-9a-f]{40}", source.tree_sha)
        assert re.fullmatch(r"[0-9a-f]{64}", source.license_sha256)


def test_go_release_date_and_ontology_data_version_are_not_conflated() -> None:
    go = next(
        source
        for source in commercial.DIRECT_SOURCES
        if source.source_id == "gene_ontology_go_basic_2026_06_19"
    )

    assert "/2026-06-19/ontology/go-basic.obo" in go.url
    assert "GO_official_release_2026-06-19" in go.release_identity
    assert "DOI_10.5281/zenodo.20943148" in go.release_identity
    assert "ontology_data_version_2026-06-15" in go.release_identity
    assert "data-version: releases/2026-06-15" in go.required_markers
    assert "data-version: releases/2026-06-19" not in go.required_markers


def test_every_direct_source_has_cryptographic_identity_and_closed_conditional_mode() -> (
    None
):
    allowed_modes = {
        "if_match_enforced_observed_412_on_mismatch",
        "dated_release_pre_get_post_identity_server_ignores_conditionals",
    }
    for source in commercial.DIRECT_SOURCES:
        assert source.expected_sha256 is not None
        assert re.fullmatch(r"[0-9a-f]{64}", source.expected_sha256)
        assert source.conditional_lock_mode in allowed_modes
        assert source.transfer_mode == "fixed_range_chunks_v1"
        assert source.fixed_chunk_bytes == 8_388_608
        serialized = source.to_dict()
        assert serialized["transfer_mode"] == source.transfer_mode
        assert serialized["fixed_chunk_bytes"] == source.fixed_chunk_bytes


@pytest.mark.parametrize("field", ["expected_sha256", "conditional_lock_mode"])
def test_frozen_direct_specs_reject_missing_hash_or_unknown_condition_mode(
    monkeypatch, field: str
) -> None:
    first = commercial.DIRECT_SOURCES[0]
    mutation = None if field == "expected_sha256" else "narrative_only_lock"
    monkeypatch.setattr(
        commercial,
        "DIRECT_SOURCES",
        (replace(first, **{field: mutation}), *commercial.DIRECT_SOURCES[1:]),
    )
    with pytest.raises(commercial.CommercialSourceError):
        commercial.source_contract()


@pytest.mark.parametrize(
    "mutation",
    [
        {"transfer_mode": "unknown", "fixed_chunk_bytes": None},
        {"transfer_mode": "fixed_range_chunks_v1", "fixed_chunk_bytes": None},
        {"transfer_mode": "fixed_range_chunks_v1", "fixed_chunk_bytes": True},
        {
            "transfer_mode": "fixed_range_chunks_v1",
            "fixed_chunk_bytes": 16 * 1024 * 1024 + 1,
        },
        {"transfer_mode": "single_response_v1", "fixed_chunk_bytes": 8_388_608},
        {
            "transfer_mode": "fixed_range_chunks_v1",
            "fixed_chunk_bytes": 8_388_608,
            "expected_etag": 'W/"weak"',
        },
    ],
)
def test_direct_transfer_policy_mode_and_chunk_pairing_is_closed(
    monkeypatch, mutation: dict[str, object]
) -> None:
    first = commercial.DIRECT_SOURCES[0]
    monkeypatch.setattr(
        commercial,
        "DIRECT_SOURCES",
        (replace(first, **mutation), *commercial.DIRECT_SOURCES[1:]),
    )
    with pytest.raises(commercial.CommercialSourceError, match="transfer"):
        commercial.source_contract()


def test_single_response_transfer_policy_requires_null_chunk_size(monkeypatch) -> None:
    first = commercial.DIRECT_SOURCES[0]
    monkeypatch.setattr(
        commercial,
        "DIRECT_SOURCES",
        (
            replace(
                first,
                transfer_mode="single_response_v1",
                fixed_chunk_bytes=None,
            ),
            *commercial.DIRECT_SOURCES[1:],
        ),
    )
    contract = commercial.source_contract()
    assert contract["direct_sources"][0]["transfer_mode"] == "single_response_v1"
    assert contract["direct_sources"][0]["fixed_chunk_bytes"] is None


def test_siyavula_version_conflict_is_structured_and_grade12_science_is_quarantined() -> (
    None
):
    siyavula = [
        source
        for source in commercial.DIRECT_SOURCES
        if source.source_id.startswith("siyavula_")
    ]
    assert len(siyavula) == 5
    assert not any(
        "physical_sciences_grade_12" in source.source_id for source in siyavula
    )
    for source in siyavula:
        identity = source.epub_identity
        assert identity is not None
        assert source.license_id == identity.resolved_license_id
        assert identity.catalogue_license_id == "CC-BY-3.0"
        assert identity.artifact_notice_license_id == "CC-BY-4.0"
        assert "http://creativecommons.org/licenses/by/4.0/" in source.required_markers
        assert identity.package_version is None
        assert identity.catalogue_grade in {10, 11, 12}
        assert identity.filename_grade_token == f"Gr{identity.catalogue_grade}"
        assert source.filename.startswith(
            f"{identity.filename_grade_token}_{identity.filename_subject_token}_"
        )
        assert identity.opf_creator_values == ()
        assert identity.opf_publisher_values == ()
        assert identity.opf_rights_values == ()
        assert identity.opf_subject_values == ()
        assert identity.opf_grade_values is None
        assert all(
            re.fullmatch(r"[0-9a-f]{64}", digest)
            for digest in (
                identity.opf_sha256,
                identity.navigation_sha256,
                identity.rights_member_sha256,
                identity.catalogue_evidence_root_sha256,
                identity.terms_evidence_root_sha256,
            )
        )
    rejects = {
        item["source_id"]: item for item in commercial.source_contract()["hard_rejects"]
    }
    assert rejects["siyavula_physical_sciences_grade_12_cc_by"]["disposition"] == (
        "quarantine_transport_incomplete_internal_identity_unverified"
    )


def test_siyavula_catalogue_subject_is_not_collapsed_into_filename_token() -> None:
    identity = commercial._siyavula_epub_identity(
        stem="science7",
        opf_sha256="1" * 64,
        navigation_sha256="2" * 64,
        rights_sha256="3" * 64,
        identifier="fixture.science7",
        modified="2015-01-01T00:00:00Z",
        catalogue_subject="Natural Sciences",
        catalogue_grade=7,
        filename_subject_token="PhysicalSciences",
        filename_grade_token="Gr7",
    )

    assert identity.catalogue_subject == "Natural Sciences"
    assert identity.filename_subject_token == "PhysicalSciences"
    assert (
        identity.catalogue_subject.replace(" ", "") != identity.filename_subject_token
    )


def test_unresolved_payload_grade_metadata_blocks_preregistration(
    monkeypatch,
) -> None:
    eligibility = commercial.source_contract()["preregistration_eligibility"]

    assert eligibility["eligible"] is False
    assert eligibility["selection_critical_identity_blockers"] == [
        {
            "field": "opf_grade_values",
            "reason": "payload_grade_metadata_identity_unresolved",
            "source_id": source.source_id,
        }
        for source in commercial.DIRECT_SOURCES
        if source.epub_identity is not None
    ]

    resolved_sources = tuple(
        replace(
            source,
            epub_identity=(
                None
                if source.epub_identity is None
                else replace(source.epub_identity, opf_grade_values=())
            ),
        )
        for source in commercial.DIRECT_SOURCES
    )
    monkeypatch.setattr(commercial, "DIRECT_SOURCES", resolved_sources)
    assert commercial.source_contract()["preregistration_eligibility"] == {
        "eligible": True,
        "selection_critical_identity_blockers": [],
    }


@pytest.mark.parametrize(
    "mutation",
    [
        {"package_version": "2.0"},
        {"catalogue_grade": True},
        {"filename_grade_token": "Gr11"},
        {"filename_subject_token": "Physical Sciences"},
        {"container_sha256": "not-a-digest"},
        {"opf_subject_values": ["Mathematics"]},
    ],
)
def test_siyavula_identity_metadata_contract_fails_closed(
    monkeypatch, mutation: dict[str, object]
) -> None:
    index, source = next(
        (index, source)
        for index, source in enumerate(commercial.DIRECT_SOURCES)
        if source.source_id == "siyavula_mathematics_grade_10_cc_by"
    )
    assert source.epub_identity is not None
    mutated = replace(
        source,
        epub_identity=replace(source.epub_identity, **mutation),
    )
    sources = list(commercial.DIRECT_SOURCES)
    sources[index] = mutated
    monkeypatch.setattr(commercial, "DIRECT_SOURCES", tuple(sources))

    with pytest.raises(
        commercial.CommercialSourceError,
        match="EPUB_subject_grade_or_metadata_identity",
    ):
        commercial.source_contract()


def test_chebi_rights_template_discrepancy_is_hash_bound_not_narrated_away() -> None:
    chebi = next(
        source
        for source in commercial.DIRECT_SOURCES
        if source.source_id == "chebi_release_252_three_star"
    )
    payload = chebi.payload_rights_specs()
    external = {item.evidence_id: item for item in chebi.external_rights_specs()}
    assert chebi.license_id == "CC-BY-4.0"
    assert len(payload) == 1
    assert payload[0].locator_kind == "direct_prefix"
    assert payload[0].byte_length == 1392
    assert payload[0].sha256 == (
        "e36272c2e15176c950125936ba19ce7fcc96d4ba53a10b4af67cb497bfcdadd7"
    )
    assert external["chebi_rel252_archived_README"].observed_license_id == (
        "LicenseRef-ChEBI-README-CC-BY-SA-4.0-wording"
    )
    assert external["chebi_rel252_archived_LICENSE"].observed_license_id == (
        "CC-BY-4.0"
    )
    assert all(
        item.role == "supplementary_conflict_context" for item in external.values()
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda evidence, source: replace(evidence, locator_kind="unbounded_search"),
        lambda evidence, source: replace(evidence, locator="../escape"),
        lambda evidence, source: replace(
            evidence, byte_length=source.expected_bytes + 1
        ),
        lambda evidence, source: replace(evidence, sha256="A" * 64),
    ],
)
def test_payload_rights_spec_schema_fails_closed(monkeypatch, mutate) -> None:
    source = next(
        item
        for item in commercial.DIRECT_SOURCES
        if item.source_id == "chebi_release_252_three_star"
    )
    evidence = mutate(source.payload_rights_specs()[0], source)
    replacement = replace(source, payload_rights_evidence=(evidence,))
    monkeypatch.setattr(
        commercial,
        "DIRECT_SOURCES",
        tuple(
            replacement if item is source else item
            for item in commercial.DIRECT_SOURCES
        ),
    )
    with pytest.raises(
        commercial.CommercialSourceError,
        match="source_spec_payload_rights",
    ):
        commercial.source_contract()


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("canonicalization", "opaque_string"),
        ("role", "admission_basis"),
    ],
)
def test_external_rights_evidence_is_structured_supplementary_only(
    monkeypatch, field: str, invalid: str
) -> None:
    source = next(
        item
        for item in commercial.DIRECT_SOURCES
        if item.source_id == "chebi_release_252_three_star"
    )
    evidence = source.external_rights_specs()[0]
    replacement_evidence = replace(evidence, **{field: invalid})
    replacement = replace(
        source,
        external_rights_evidence=(
            replacement_evidence,
            *source.external_rights_evidence[1:],
        ),
    )
    monkeypatch.setattr(
        commercial,
        "DIRECT_SOURCES",
        tuple(
            replacement if item is source else item
            for item in commercial.DIRECT_SOURCES
        ),
    )
    with pytest.raises(
        commercial.CommercialSourceError,
        match="source_spec_external_rights_evidence_invalid",
    ):
        commercial.source_contract()


def test_epub_payload_rights_descriptor_must_match_bound_member(monkeypatch) -> None:
    source = next(
        item
        for item in commercial.DIRECT_SOURCES
        if item.source_id == "siyavula_mathematics_grade_10_cc_by"
    )
    evidence = replace(source.payload_rights_specs()[0], locator="wrong.xhtml")
    replacement = replace(source, payload_rights_evidence=(evidence,))
    monkeypatch.setattr(
        commercial,
        "DIRECT_SOURCES",
        tuple(
            replacement if item is source else item
            for item in commercial.DIRECT_SOURCES
        ),
    )
    with pytest.raises(
        commercial.CommercialSourceError,
        match="EPUB_payload_rights_binding_invalid",
    ):
        commercial.source_contract()


def test_phone_toolchain_contract_binds_exec_interposer_dependencies_and_probes() -> (
    None
):
    contract = commercial.phone_toolchain_contract()
    body = dict(contract)
    root = body.pop("toolchain_root_sha256")
    assert commercial.canonical_sha256(body) == root
    assert contract["runner_python_flags"] == [
        "-IBS",
        "-X",
        "pycache_prefix=$RUN_SCOPED_PYCACHE_PREFIX",
    ]
    assert contract["environments"]["git"]["LD_PRELOAD"].endswith(
        "/lib/libtermux-exec.so"
    )
    assert contract["environments"]["git"]["GIT_EXEC_PATH"].endswith(
        "/libexec/git-core"
    )
    assert contract["environments"]["git"]["GIT_NO_REPLACE_OBJECTS"] == "1"
    assert contract["python_runtime"]["absent_sys_path_entries"] == [
        "/data/data/com.termux/files/usr/lib/python313.zip"
    ]
    assert {
        "curl",
        "git",
        "git_https_helper",
        "libtermux_exec",
        "python",
        "libpython",
        "ca_certificate_bundle",
        "android_getprop",
        "system_launcher_env",
        "system_libbase",
    }.issubset(contract["artifacts"])
    assert all(
        artifact["literal_nlink"] == 1 for artifact in contract["artifacts"].values()
    )
    assert not any("onnxruntime" in role for role in contract["artifacts"])
    getprop_probes = {
        name
        for name in contract["command_probes"]
        if name.startswith("android_getprop_")
    }
    assert getprop_probes == {
        "android_getprop_build_fingerprint",
        "android_getprop_device",
        "android_getprop_model",
        "android_getprop_soc",
    }
    assert contract["command_probes"]["android_env_i_empty_environment"] == {
        "argv": ["/system/bin/env", "-i", "/system/bin/env"],
        "environment": "base",
        "returncode": 0,
        "stdout_bytes": 0,
        "stdout_sha256": (
            "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ),
        "stderr_bytes": 0,
        "stderr_sha256": (
            "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ),
    }
    assert contract["python_stdlib_tree"] == {
        "root_path": "/data/data/com.termux/files/usr/lib/python3.13",
        "root_mode": "0700",
        "root_uid": 10536,
        "root_gid": 10536,
        "root_nlink": 38,
        "entry_count": 691,
        "regular_bytes": 16922387,
        "root_sha256": "sha256:303f8e4b3a9a521cd88d5a2ed2c2312c5bdad135365a60dfb8110d441c1fa700",
        "canonicalization": (
            "sorted_relative_POSIX_paths_canonical_JSON_type_mode_"
            "regular_bytes_sha256_source_only_excluding_root_site_packages_"
            "all_pycache_and_pyc_reject_external_symlinks_root_excluded"
        ),
    }


def test_native_outer_launch_contract_is_empty_env_shell_free_and_exact_fd_map() -> (
    None
):
    layout = commercial.native_preflight_execution_layout(
        "20260712T120000Z_cur0s_commercial_sources_v1",
        "a" * 40,
    )
    outer = commercial.native_outer_launch_contract(layout)
    launcher = commercial.phone_toolchain_contract()["artifacts"]["system_launcher_env"]

    assert commercial.NATIVE_PREFLIGHT_FIXED_FD_MAP == {
        "manifest": 5,
        "native_attestation": 4,
        "preregistration": 6,
        "python_exec_cloexec": 7,
        "runner": 3,
    }
    assert outer["launcher_argv_plan"][:2] == [
        {"kind": "literal", "value": "/system/bin/env"},
        {"kind": "literal", "value": "-i"},
    ]
    assert outer["outer_environment"] == {}
    assert outer["outer_environment_sha256"] == commercial.canonical_sha256({})
    assert outer["outer_environment_must_be_empty"] is True
    assert launcher == {
        "literal_path": "/system/bin/env",
        "literal_entry_type": "symbolic_link",
        "literal_mode": "0755",
        "literal_uid": 0,
        "literal_gid": 2000,
        "literal_nlink": 1,
        "literal_symlink_target": "toybox",
        "resolved_path": "/system/bin/toybox",
        "resolved_entry_type": "regular_file",
        "resolved_mode": "0755",
        "resolved_uid": 0,
        "resolved_gid": 2000,
        "resolved_nlink": 1,
        "bytes": 577184,
        "sha256": (
            "sha256:a581d694b3d74f550d3bc896cf75ddda84a33f56f4e3ab47e06945ad3383c82d"
        ),
        "elf_identity": {
            "class_bits": 64,
            "data_encoding": "little_endian",
            "machine": "AArch64",
        },
    }
    assert outer["launcher_toolchain_artifact_identity_sha256"] == (
        commercial.canonical_sha256(launcher)
    )
    assert outer["shell_interpolation_allowed"] is False
    assert outer["malicious_same_UID_tamper_resistance_claimed"] is False
    assert all(not name.startswith("LD_") for name in outer["outer_environment"])


def test_native_build_v3_freezes_full_phone_toolchain_input_closure() -> None:
    assert commercial.NATIVE_PREFLIGHT_BUILD_SCHEMA == (
        "cur0s_native_preflight_android_build_receipt_v3"
    )
    assert set(commercial.NATIVE_PREFLIGHT_SOURCE_FILES) == {
        "polymath_ai/corpus/cur0s_commercial_sources.py",
        "scripts/termux/build_cur0s_native_preflight.py",
        "scripts/termux/native/cur0s_native_preflight.c",
        "scripts/termux/native/cur0s_sha256.c",
        "scripts/termux/native/cur0s_sha256.h",
    }
    include_trees = commercial.NATIVE_PREFLIGHT_BUILD_INCLUDE_TREES
    assert set(include_trees) == {
        "clang_resource_tree",
        "termux_arch_headers",
        "termux_system_headers",
    }
    assert include_trees["clang_resource_tree"]["sha256"] == (
        "sha256:d97053fa2e97adeb5812e1f79b6946e53e75096f6cdea652361b089e97c3f48a"
    )
    assert include_trees["termux_arch_headers"]["sha256"] == (
        "sha256:6f5a4c1ce9ad3151bd9c1237b7be7698695edc9b63bd5893fdca0cd7ad62b43d"
    )
    assert include_trees["termux_system_headers"]["sha256"] == (
        "sha256:3390524567ef958bd79c7460816eec8f90591fb6277aa96588683850ca55c316"
    )
    assert set(commercial.NATIVE_PREFLIGHT_BUILD_LINK_INPUTS) == {
        "android_libc",
        "android_libdl",
        "clang_rt_builtins",
        "crtbegin_dynamic",
        "crtend_android",
        "libunwind",
    }
    compile_template = commercial.NATIVE_PREFLIGHT_COMPILE_ARGV_TEMPLATE
    assert "--no-default-config" in compile_template
    assert "-nostdinc" in compile_template
    assert "$HELD_SOURCE" in compile_template
    assert not any("$SOURCE_ROOT" in argument for argument in compile_template)
    link_template = commercial.NATIVE_PREFLIGHT_LINK_ARGV_TEMPLATE
    assert link_template[:3] == (
        "/data/data/com.termux/files/usr/bin/ld.lld",
        "-flavor",
        "gnu",
    )
    assert "$HELD_FD:crtbegin_dynamic" in link_template
    assert "$HELD_FD:crtend_android" in link_template
    runtime = commercial.NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_IDENTITY
    assert runtime["schema_version"] == (
        "cur0s_native_aarch64_recursive_runtime_dependency_closure_v2"
    )
    assert runtime["recursive_resolution_complete"] is True
    assert len(runtime["runtime_inputs"]) == 15
    assert len(runtime["dependency_graph"]) == 17
    assert runtime["runtime_inputs"]["libllvm"]["sha256"] == (
        "sha256:d8157ef272769f24142408f819e9eb27139e9c3b0fecbd468fe5416e77c402ce"
    )
    assert runtime["dependency_graph"]["compiler"]["interpreter"] == (
        "/system/bin/linker64"
    )
    python_runtime = commercial.native_preflight_build_python_runtime_identity()
    assert len(python_runtime["artifact_inputs"]) == 15
    assert python_runtime["artifact_inputs"]["libbz2"]["sha256"] == (
        "sha256:5129a738fec8c6733954fa6a98f1fad9538e818f38db89d5391f12e5657746dc"
    )
    assert python_runtime["artifact_inputs"]["liblzma"]["sha256"] == (
        "sha256:f8ab7f7548a57222c1115274bd6ff10d08917ba0701c1b3892be5a12a8d506cf"
    )
    assert len(python_runtime["executable_mapping_artifact_roles"]) == 15
    assert "file_backed_executable_mapping_paths" not in python_runtime
    assert python_runtime["stdlib_executable_mapping_policy"] == (
        "exact_loaded_ExtensionFileLoader_origins_plus_manifest_bound_dependencies"
    )
    assert python_runtime["kernel_executable_mapping_boundary"] == ["[vdso]"]
    assert python_runtime["stdlib_tree"]["root_sha256"] == (
        "sha256:303f8e4b3a9a521cd88d5a2ed2c2312c5bdad135365a60dfb8110d441c1fa700"
    )


def test_phone_thermal_contract_freezes_exact_roster_groups_and_oem_inputs() -> None:
    contract = commercial.phone_thermal_safety_contract()
    assert contract["schema_version"] == "cur0s_phone_thermal_safety_contract_v1"
    assert contract["expected_zone_count"] == 84
    assert list(contract["zone_type_roster"]) == [
        f"thermal_zone{index}" for index in range(84)
    ]
    assert contract["group_ceilings_millidegrees_c"] == {
        "battery_usb": 45_000,
        "compute_cpu_soc": 85_000,
        "ddr": 85_000,
        "gpu": 85_000,
        "npu": 85_000,
        "pmic": 85_000,
        "skin": 54_000,
    }
    assert contract["unavailable_sentinels_millidegrees_c"] == [
        -273_000,
        -40_960,
    ]
    assert contract["oem_thermal_property_inputs"] == {
        "ro.vendor.feature.zte_feature_ccc_bat_temp_cntrl": "true",
        "ro.vendor.feature.zte_feature_ccc_temp_threshold": "skin,54,battery,45",
    }
    assert contract["contract_root_sha256"] == commercial.canonical_sha256(
        {key: value for key, value in contract.items() if key != "contract_root_sha256"}
    )


def test_c4_com_contract_preserves_rx_and_hard_reject_boundaries() -> None:
    contract = commercial.source_contract()
    rejects = {item["source_id"]: item for item in contract["hard_rejects"]}
    admitted_ids = {source.source_id for source in _sources()}

    assert contract["lane"] == "C4-COM"
    assert contract["custody"]["C4_COM_and_C4_RX_roots_separate"] is True
    assert (
        rejects["MegaScience_TextbookReasoning_and_MegaScience"]["disposition"]
        == "C4_RX_only"
    )
    assert rejects["openstax_current_main"]["disposition"] == "rejected"
    assert rejects["qasc_as_C4_COM"]["disposition"] == "rejected_for_C4_COM"
    assert rejects["openbookqa"]["disposition"] == "rejected"
    assert rejects["chebi_lite"]["disposition"] == "rejected_for_C3_dictionary"
    assert (
        rejects["siyavula_branded_or_non_derivative_editions"]["disposition"]
        == "rejected"
    )
    assert not admitted_ids.intersection(rejects)
    assert not any("MegaScience" in source_id for source_id in admitted_ids)

    root = commercial.build_source_root(_artifacts())
    assert root["lane"] == "C4-COM"
    assert root["c4_rx_content_present"] is False
    assert root["hard_rejects"] == contract["hard_rejects"]


def test_canonical_json_is_compact_sorted_utf8_and_tuple_normalizing() -> None:
    value = {"z": [3, 2], "a": "café", "tuple": (True, None)}
    encoded = commercial.canonical_json_bytes(value)

    assert encoded == (b'{"a":"caf\xc3\xa9","tuple":[true,null],"z":[3,2]}')
    assert json.loads(encoded) == {
        "a": "café",
        "tuple": [True, None],
        "z": [3, 2],
    }
    assert commercial.canonical_sha256(value) == _sha256(encoded.decode("utf-8"))


def test_canonical_json_is_independent_of_mapping_insertion_order() -> None:
    left = {"b": {"d": 4, "c": 3}, "a": 1}
    right = {"a": 1, "b": {"c": 3, "d": 4}}

    assert commercial.canonical_json_bytes(left) == commercial.canonical_json_bytes(
        right
    )
    assert commercial.canonical_sha256(left) == commercial.canonical_sha256(right)


def test_canonical_json_allows_shared_acyclic_values() -> None:
    shared = ["same-object", 1]

    assert json.loads(commercial.canonical_json_bytes({"a": shared, "b": shared})) == {
        "a": shared,
        "b": shared,
    }


def test_canonical_json_rejects_direct_and_indirect_cycles() -> None:
    direct: list[Any] = []
    direct.append(direct)
    indirect: dict[str, Any] = {}
    child = [indirect]
    indirect["child"] = child

    for value in (direct, indirect):
        with pytest.raises(
            commercial.CommercialSourceError,
            match="cyclic_json_value",
        ):
            commercial.canonical_json_bytes(value)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_canonical_json_rejects_nonfinite_numbers(value: float) -> None:
    with pytest.raises(
        commercial.CommercialSourceError,
        match="nonfinite_json_number",
    ):
        commercial.canonical_json_bytes({"nested": [value]})


@pytest.mark.parametrize("value", [{1: "non-string-key"}, {"set": {1, 2}}, object()])
def test_canonical_json_rejects_non_json_types(value: Any) -> None:
    with pytest.raises(
        commercial.CommercialSourceError,
        match="json_key_not_string|unsupported_json_value",
    ):
        commercial.canonical_json_bytes(value)

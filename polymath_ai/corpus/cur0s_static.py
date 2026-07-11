"""Frozen current-source locks and the fail-closed CUR-0S static gate matrix."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


SOURCE_REPOSITORY = "Zer0pa/polymat-gemmalit-c1-c4-commercial-corpus"
SOURCE_REVISION = "504dd91c5a7c8365882d690d52f3de20697c4f7b"
SOURCE_ROLE = "physically_valid_evidence_only"
TOTAL_ROWS = 77_023


@dataclass(frozen=True)
class StageLock:
    stage: str
    directory: str
    phase_filename: str
    rows: int
    master_sha256: str
    qa_sha256: str
    manifest_sha256: str

    @property
    def master_relative_path(self) -> str:
        return f"{self.directory}/phase_{self.phase_filename}_full.jsonl"

    @property
    def qa_relative_path(self) -> str:
        return f"{self.directory}/qa_bridge/phase_{self.phase_filename}_full.qa.jsonl"

    @property
    def manifest_relative_path(self) -> str:
        return f"{self.directory}/phase_{self.phase_filename}_build_manifest.json"

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "rows": self.rows,
            "master": {"relative_path": self.master_relative_path, "sha256": self.master_sha256},
            "qa": {"relative_path": self.qa_relative_path, "sha256": self.qa_sha256},
            "manifest": {
                "relative_path": self.manifest_relative_path,
                "sha256": self.manifest_sha256,
            },
        }


STAGE_LOCKS = (
    StageLock(
        stage="C1",
        directory="C1",
        phase_filename="C1",
        rows=5_180,
        master_sha256="4348f38e353c7bfb226a9b120023f10230bd3b07b513208508235800cc28f4e7",
        qa_sha256="a752cafde223b0203be9478c3f28cf672d2ba0962394377f61a926da771c8088",
        manifest_sha256="7349512beadd2da2f678c3229425fc291576912f274450f3186f8c695fe8e305",
    ),
    StageLock(
        stage="C2",
        directory="C2",
        phase_filename="C2",
        rows=3_198,
        master_sha256="7db577f5e110bbb63561d7b4d0f9ad182ec01a167e00c6a2e625899b6972cbf6",
        qa_sha256="676d985fff59d4a60c36d3e5142ac679a45db6082003fe98fa440b8cdbc517a3",
        manifest_sha256="3ed5a4d0190911744716f7e294a59271b54b319c0d80bab67f9cca3a1dbdeaee",
    ),
    StageLock(
        stage="B23",
        directory="C2_5",
        phase_filename="C2.5",
        rows=20,
        master_sha256="323f3e256bb8a72d4e1c597b184f402447af112a62f90adc871a7a306c5bf4eb",
        qa_sha256="ec5a85f111ba42bf778fffd98212f3f92ec871e9eb0a757196393cef99d2ba83",
        manifest_sha256="b1b7ed6f03cc2da281959c87dfa6ffb84cddfb23805e76c3682fc916a6284316",
    ),
    StageLock(
        stage="C3",
        directory="C3",
        phase_filename="C3",
        rows=56_138,
        master_sha256="b4bf2813b8e8f9931710b8d4a9806150111088da5e176ec6bb1fedf39b31bcdc",
        qa_sha256="c6c3e98ebd1c583fc92588160922aad758af6a0d56c75ca7fb6cd8c7d0d1a87a",
        manifest_sha256="f95b1569f01b8c541d0cbe1c359d81dcbe8d1b036d9ddc6838780cdf1ae215be",
    ),
    StageLock(
        stage="C4",
        directory="C4",
        phase_filename="C4",
        rows=12_487,
        master_sha256="014ee4ca2dbf2afacb5144337b7afe11538eb6cd05dd058003d7338a8f392516",
        qa_sha256="0bfe358075383a74dbd0b6cf763e2ea5d5407ce3e3a894cccea4b67f41dcdcc6",
        manifest_sha256="451b879c2ab4df71db2b11da7868fb0a71664a09b35b8f7d73aec56dea5bf490",
    ),
)


def physical_lock_contract() -> dict[str, Any]:
    contract = {
        "schema_version": "cur0s_current_physical_lock_v1",
        "source_repository": SOURCE_REPOSITORY,
        "source_revision": SOURCE_REVISION,
        "immutable_role": SOURCE_ROLE,
        "total_rows": TOTAL_ROWS,
        "stages": [lock.to_dict() for lock in STAGE_LOCKS],
    }
    return {**contract, "contract_sha256": canonical_sha256(contract)}


def static_gate_matrix(*, physical_pass: bool, exact_identity_pass: bool) -> list[dict[str, Any]]:
    """Describe the complete static gate without promoting absent evidence."""

    return [
        _gate("immutable_physical_source", physical_pass, "current_evidence_root_only"),
        _gate(
            "exact_source_and_joint_content_identity",
            exact_identity_pass,
            "subordinate_exact_identity_scope_only",
        ),
        _blocked("successor_commercial_source_root", "source_tournament_not_admitted"),
        _blocked("near_semantic_arm_C", "joint_content_detector_and_independent_audit_absent"),
        _blocked("connected_successor_split", "requires_admitted_Arm_C_and_sealed_policy"),
        _blocked("permanent_exposure_ledger", "capsule_bound_genesis_and_successor_taint_absent"),
        _blocked("row_level_rights_and_provider_terms", "C1_C2_and_source_lineage_unresolved"),
        _blocked("row_level_semantic_quality", "repair_reject_rejudge_overlay_absent"),
        _blocked("lexeme_concept_and_base_vocabulary_policy", "semantic_vocabulary_root_absent"),
        _blocked("C1_lexical_self_expansion_closure", "closure_root_absent"),
        _blocked("C2_known_vocabulary_certificates", "certificate_root_absent"),
        _blocked("dependency_prerequisite_DAG", "topology_SCC_and_zero_reference_proof_absent"),
        _blocked("C3_science_dictionary", "current_C3_is_source_pool_not_target_dictionary"),
        _blocked("C4_COM_prerequisite_syllabus", "current_C4_is_paired_view_not_target_syllabus"),
        _blocked("C4_COM_static_comparability_vector", "rubric_and_observation_absent"),
        _blocked("missing_context_and_numeric_unit_quarantine", "successor_overlay_absent"),
        _blocked("independent_hidden_C5_and_retention_roots", "optimizer_inaccessible_roots_absent"),
        {
            "gate": "B23_disposition",
            "state": "contract_frozen_evidence_not_yet_joined",
            "required": {"stage_weight": 0, "authority_role": "diagnostic_canary"},
        },
        {
            "gate": "deferred_equal_budget_learning_retention_dimension",
            "state": "policy_dependency_deadlock",
            "reason": "must_be_frozen_now_but_observed_only_post_composite_CUR_0_under_current_PRD",
            "promotion_effect": "CUR_0S_and_CUR_0_remain_blocked_without_explicit_timing_correction",
        },
    ]


def first_missing_green_field(matrix: list[dict[str, Any]]) -> str | None:
    for entry in matrix:
        if entry["state"] not in {"passed_scope", "contract_frozen_evidence_not_yet_joined"}:
            return str(entry["gate"])
    return None


def _gate(gate: str, passed: bool, scope: str) -> dict[str, Any]:
    return {
        "gate": gate,
        "state": "passed_scope" if passed else "blocked_fail_closed",
        "scope": scope,
    }


def _blocked(gate: str, reason: str) -> dict[str, Any]:
    return {"gate": gate, "state": "blocked_fail_closed", "reason": reason}

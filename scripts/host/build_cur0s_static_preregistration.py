#!/usr/bin/env python3
"""Freeze an unobserved, source-bound CUR-0S exact-identity preregistration."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from polymath_ai.corpus.cur0s_exact import canonical_json_bytes, canonical_sha256  # noqa: E402
from polymath_ai.corpus.cur0s_static import (  # noqa: E402
    SOURCE_REPOSITORY,
    SOURCE_REVISION,
    physical_lock_contract,
)


SCHEMA_VERSION = "cur0s_static_identity_preregistration_v1"
SHA_RE = re.compile(r"(?:sha256:)?([0-9a-f]{64})\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
RUN_ID_RE = re.compile(r"[0-9]{8}T[0-9]{6}Z_cur0s_static_identity_v1\Z")
SOURCE_FILES = (
    "polymath_ai/corpus/cur0s_exact.py",
    "polymath_ai/corpus/cur0s_static.py",
    "scripts/termux/run_cur0s_static_identity.py",
)


def main() -> int:
    args = parse_args()
    if RUN_ID_RE.fullmatch(args.run_id) is None:
        raise ValueError("invalid_run_id")
    source_commit = git_output("rev-parse", "HEAD")
    if COMMIT_RE.fullmatch(source_commit) is None:
        raise ValueError("invalid_source_commit")
    for relative_path in SOURCE_FILES:
        if git_output("status", "--short", "--", relative_path):
            raise ValueError(f"source_file_not_committed:{relative_path}")

    source_hashes = {
        "cur0s_exact_sha256": file_sha256(ROOT / SOURCE_FILES[0]),
        "cur0s_static_sha256": file_sha256(ROOT / SOURCE_FILES[1]),
        "runner_sha256": file_sha256(ROOT / SOURCE_FILES[2]),
    }
    source_bindings = {
        relative_path: {
            "bytes": (ROOT / relative_path).stat().st_size,
            "sha256": file_sha256(ROOT / relative_path),
            "git_blob_oid": git_output("rev-parse", f"HEAD:{relative_path}"),
        }
        for relative_path in SOURCE_FILES
    }
    anti_percolation_policy = {
        "max_component_size": 64,
        "max_giant_component_share": 0.01,
        "max_source_instances_per_component": 64,
    }
    issued_at = datetime.now(timezone.utc).replace(microsecond=0)
    preregistration: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": "cur0s_current_physical_exact_identity_v1",
        "parent_experiment_id": "EXP-CUR0S-SOVEREIGN-COMPOSITE-V1",
        "run_id": args.run_id,
        "candidate_output_observed": False,
        "phone_execution_started": False,
        "promotion_allowed": False,
        "source_commit": source_commit,
        "source_file_sha256": source_hashes,
        "source_file_bindings": source_bindings,
        "source_repository": SOURCE_REPOSITORY,
        "source_revision": SOURCE_REVISION,
        "source_role": "physically_valid_evidence_only",
        "physical_lock_contract_sha256": physical_lock_contract()["contract_sha256"],
        "parent_capsule_sha256": normalize_sha(args.parent_capsule_sha256),
        "parent_frontier_root_sha256": normalize_sha(args.parent_frontier_root_sha256),
        "maximal_selector_sha256": normalize_sha(args.parent_frontier_root_sha256),
        "ACCESS_receipt_sha256": "sha256:7b2b6d506b3ab82a17008edc4c79dd51512f6f9598e3db37cd1bb6f5ee4331ca",
        "campaign_lease": build_campaign_lease(args.run_id, issued_at),
        "resource_slice": {
            "phone_adb_serial_sha256": "sha256:383e1fef6040334134430241a105f7d900f6d924e485fdc858441e734d3ae0f4",
            "phone_model": "NX789J",
            "phone_soc": "SM8750",
            "runpod": "uh57jg7iguwqth_existing_only",
            "github_repository": "Zer0pa/Polymath-AI",
            "huggingface_visibility": "private_revision_pinned_only",
            "comet_payload": "hash_bound_metadata_only",
            "public_release": False,
        },
        "target_device": {
            "adb_serial_sha256": "sha256:383e1fef6040334134430241a105f7d900f6d924e485fdc858441e734d3ae0f4",
            "model": "NX789J",
            "device": "NX789J",
            "soc": "SM8750",
            "architecture": "aarch64",
            "python_platform_system": "Android",
            "private_home": "/data/data/com.termux/files/home",
            "build_fingerprint_sha256": "sha256:fce358a6cdd6535afbecf6f72088412abaccf9b9902c05800ee8852512f9882f",
        },
        "raw_source_locator": "phone-private://cur0s/current-physical-504dd91c/packages",
        "source_checkout_policy": "git_HEAD_equals_source_commit_and_bound_files_clean",
        "governing_inputs": {
            "PRD_sha256": "sha256:725d0ad6ac77fdcfc06a2635c7552cc414e0ed48f30fbd0f7f7ec38720493a3c",
            "living_concept_sha256": "sha256:b2f617766b660237ddfd329c6b7fa2370f9a2641983e71915b4cd71c6d31bacc",
            "corpus_audit_sha256": "sha256:c3a5d5eacf424f6e50ae0a170873d1c80e566581e22031a8f64bc899f8eec0fa",
        },
        "anti_percolation_policy": anti_percolation_policy,
        "anti_percolation_policy_sha256": canonical_sha256(anti_percolation_policy),
        "grouping_contract": {
            "arm_A": "exact_dataset_revision_source_local_identity",
            "arm_B": "Arm_A_union_conservative_exact_joint_question_material_identity",
            "answer_only_edges": "forbidden",
            "near_semantic_Arm_C": "not_executed_in_this_subordinate_candidate",
            "successor_split_assignment": "forbidden_before_Arm_C_admission",
        },
        "claim_scope": "current_physical_root_exact_identity_and_custody_only",
        "claim_ceiling": "subordinate_identity_evidence_not_CUR_0S",
        "output_directory_name": "candidate-001",
        "static_gate_rule": "all_absent_successor_rights_quality_semantic_and_comparability_artifacts_fail_closed",
        "expected_disposition": "continue_commercial_source_tournament_and_build_integrated_successor_static_root",
        "outcome_to_decision": {
            "physical_lock_mismatch": "invalid_or_external_custody_blocker_do_not_group",
            "missing_lineage": "rebuild_source_identity_do_not_assign_splits",
            "anti_percolation_failure": "rebuild_exact_identity_policy_or_source_do_not_relax_thresholds",
            "exact_identity_pass": "retain_substrate_and_continue_integrated_successor_CUR_0S_attempt",
        },
        "custody": {
            "execution_plane": "phone_private",
            "raw_payload_egress": False,
            "row_membership_overlay_egress": False,
            "aggregate_hash_bound_receipt_egress": True,
        },
        "nonclaims": [
            "not_near_semantic_Arm_C",
            "not_successor_connected_split",
            "not_rights_quality_or_semantic_admission",
            "not_CUR_0S_or_CUR_0P_or_composite_CUR_0",
            "not_target_data_learning_or_authority",
        ],
    }
    preregistration["preregistration_root_sha256"] = canonical_sha256(preregistration)
    output = Path(args.output)
    if not output.is_absolute() or Path(output.name).parts != (output.name,):
        raise ValueError("output_must_be_absolute_literal_child")
    require_output_parent(output.parent)
    payload = canonical_json_bytes(preregistration) + b"\n"
    output_sha256, output_bytes = exclusive_publish(output, payload)
    print(
        json.dumps(
            {
                "output": str(output),
                "bytes": output_bytes,
                "sha256": output_sha256,
                "preregistration_root_sha256": preregistration[
                    "preregistration_root_sha256"
                ],
                "source_commit": source_commit,
                "candidate_output_observed": False,
            },
            sort_keys=True,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--parent-capsule-sha256", required=True)
    parser.add_argument("--parent-frontier-root-sha256", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def build_campaign_lease(run_id: str, issued_at: datetime) -> dict[str, Any]:
    if RUN_ID_RE.fullmatch(run_id) is None:
        raise ValueError("invalid_run_id")
    if issued_at.tzinfo is None or issued_at.utcoffset() != timedelta(0):
        raise ValueError("issued_at_must_be_UTC")
    issued_at = issued_at.replace(microsecond=0)
    expires_at = issued_at + timedelta(hours=4)
    return {
        "lease_id": "current_user_sovereign_frontier_campaign_20260711",
        "action_id": run_id,
        "state": "active",
        "issued_at_utc": iso_utc(issued_at),
        "expires_at_utc": iso_utc(expires_at),
        "additional_paid_capacity": False,
        "max_phone_execution_count": 1,
        "phone_execution_count_before": 0,
        "max_wall_seconds": 1800,
        "max_private_output_bytes": 268435456,
        "min_free_storage_bytes": 10737418240,
        "max_temperature_millidegrees_c": 85000,
        "thermal_unavailable_sentinels_millidegrees_c": [-273000],
        "thermal_sample_every_records": 1024,
    }


def git_output(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def normalize_sha(value: str) -> str:
    match = SHA_RE.fullmatch(value)
    if match is None:
        raise ValueError("invalid_sha256")
    return "sha256:" + match.group(1)


def iso_utc(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def require_output_parent(parent: Path) -> None:
    allowed = (ROOT / "runtime/reports/apex_frontier").resolve(strict=True)
    if parent != allowed or parent.is_symlink():
        raise ValueError("output_parent_must_be_existing_apex_frontier_root")


def exclusive_publish(path: Path, payload: bytes) -> tuple[str, int]:
    parent_fd = os.open(
        path.parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        fd = os.open(
            path.name,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        try:
            initial = os.fstat(fd)
            if initial.st_nlink != 1 or not stat.S_ISREG(initial.st_mode):
                raise RuntimeError("preregistration_inode_invalid")
            view = memoryview(payload)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise RuntimeError("preregistration_short_write")
                view = view[written:]
            os.fchmod(fd, 0o600)
            os.fsync(fd)
            os.lseek(fd, 0, os.SEEK_SET)
            readback = bytearray()
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    break
                readback.extend(chunk)
            final = os.fstat(fd)
            entry = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
            if (initial.st_dev, initial.st_ino) != (final.st_dev, final.st_ino):
                raise RuntimeError("preregistration_inode_changed")
            if (final.st_dev, final.st_ino) != (entry.st_dev, entry.st_ino):
                raise RuntimeError("preregistration_entry_replaced")
            if final.st_nlink != 1 or not stat.S_ISREG(final.st_mode):
                raise RuntimeError("preregistration_inode_invalid")
        finally:
            os.close(fd)
        os.fsync(parent_fd)
        if bytes(readback) != payload:
            raise RuntimeError("preregistration_readback_mismatch")
        return "sha256:" + hashlib.sha256(payload).hexdigest(), len(payload)
    finally:
        os.close(parent_fd)


if __name__ == "__main__":
    raise SystemExit(main())

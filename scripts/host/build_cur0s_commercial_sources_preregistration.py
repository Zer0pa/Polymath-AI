#!/usr/bin/env python3
"""Freeze the one-shot phone-native commercial-source acquisition attempt."""

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

from polymath_ai.corpus.cur0s_commercial_sources import (  # noqa: E402
    NATIVE_PREFLIGHT_SOURCE_FILES,
    build_native_launch_envelope,
    build_native_preflight_execution_contract,
    build_native_preflight_manifest_bytes,
    canonical_json_bytes,
    canonical_sha256,
    phone_thermal_safety_contract,
    phone_toolchain_contract,
    source_contract,
)


SCHEMA_VERSION = "cur0s_commercial_sources_preregistration_v1"
SHA_RE = re.compile(r"(?:sha256:)?([0-9a-f]{64})\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
RUN_ID_RE = re.compile(r"[0-9]{8}T[0-9]{6}Z_cur0s_commercial_sources_v1\Z")
EXPECTED_PARENT_CAPSULE_SHA256 = (
    "sha256:e6905f36fa526e15a0a1d8ac4eadbf670061a2837fea9a7ac51a1df6bb608f15"
)
EXPECTED_PARENT_FRONTIER_ROOT_SHA256 = (
    "sha256:d118000d8fd457962f2332f2597bb25f6c6e33ee61010f5cd1459ab9768235fc"
)
HOST_GIT = "/usr/bin/git"
SOURCE_FILES = (
    "polymath_ai/corpus/cur0s_commercial_sources.py",
    "scripts/termux/run_cur0s_commercial_sources.py",
)
SOURCE_HASH_NAMES = ("commercial_sources_sha256", "runner_sha256")
NATIVE_SOURCE_FILES = NATIVE_PREFLIGHT_SOURCE_FILES
ALLOWED_HTTPS_HOSTS = (
    "apps.usgs.gov",
    "ftp.ebi.ac.uk",
    "github-cloud.s3.amazonaws.com",
    "github.com",
    "lod.nal.usda.gov",
    "objects.githubusercontent.com",
    "raw.githubusercontent.com",
    "release.geneontology.org",
    "wordnetcode.princeton.edu",
    "www.siyavula.com",
)


def main() -> int:
    args = parse_args()
    require_preregistration_eligible()
    preregistration = build_preregistration(args)
    output = Path(args.output)
    manifest_output = Path(args.native_manifest_output)
    launch_envelope_output = Path(args.native_launch_envelope_output)
    outputs = (output, manifest_output, launch_envelope_output)
    for path in outputs:
        if not path.is_absolute() or Path(path.name).parts != (path.name,):
            raise ValueError("output_must_be_absolute_literal_child")
        require_output_parent(path.parent)
    if len(set(outputs)) != len(outputs):
        raise ValueError("preregistration_manifest_launch_outputs_must_differ")
    if any(path.exists() for path in outputs):
        raise FileExistsError("preregistration_manifest_or_launch_output_exists")
    payload = canonical_json_bytes(preregistration) + b"\n"
    manifest_payload = build_native_preflight_manifest_bytes(preregistration)
    launch_envelope = build_native_launch_envelope(
        preregistration,
        manifest_payload,
    )
    launch_envelope_payload = canonical_json_bytes(launch_envelope) + b"\n"
    output_sha256, output_bytes = exclusive_publish(output, payload)
    manifest_sha256, manifest_bytes = exclusive_publish(
        manifest_output,
        manifest_payload,
    )
    launch_envelope_sha256, launch_envelope_bytes = exclusive_publish(
        launch_envelope_output,
        launch_envelope_payload,
    )
    print(
        json.dumps(
            {
                "bytes": output_bytes,
                "candidate_output_observed": False,
                "commercial_source_contract_root_sha256": preregistration[
                    "commercial_source_contract"
                ]["contract_root_sha256"],
                "output": str(output),
                "native_manifest": str(manifest_output),
                "native_manifest_bytes": manifest_bytes,
                "native_manifest_sha256": manifest_sha256,
                "native_launch_envelope": str(launch_envelope_output),
                "native_launch_envelope_bytes": launch_envelope_bytes,
                "native_launch_envelope_sha256": launch_envelope_sha256,
                "native_launch_envelope_root_sha256": launch_envelope[
                    "envelope_root_sha256"
                ],
                "preregistration_root_sha256": preregistration[
                    "preregistration_root_sha256"
                ],
                "sha256": output_sha256,
                "source_commit": preregistration["source_commit"],
            },
            sort_keys=True,
        )
    )
    return 0


def require_preregistration_eligible() -> None:
    """Reject an ineligible sovereign source contract before any publication."""

    contract = source_contract()
    eligibility = contract.get("preregistration_eligibility")
    if not isinstance(eligibility, dict) or eligibility.get("eligible") is not True:
        raise ValueError("commercial_source_contract_preregistration_ineligible")


def build_preregistration(args: argparse.Namespace) -> dict[str, Any]:
    if RUN_ID_RE.fullmatch(args.run_id) is None:
        raise ValueError("invalid_run_id")
    parent_capsule_sha256 = normalize_sha(args.parent_capsule_sha256)
    parent_frontier_root_sha256 = normalize_sha(args.parent_frontier_root_sha256)
    if parent_capsule_sha256 != EXPECTED_PARENT_CAPSULE_SHA256:
        raise ValueError("parent_capsule_sha256_mismatch")
    if parent_frontier_root_sha256 != EXPECTED_PARENT_FRONTIER_ROOT_SHA256:
        raise ValueError("parent_frontier_root_sha256_mismatch")
    if git_output("for-each-ref", "--format=%(refname)", "refs/replace"):
        raise ValueError("source_checkout_replace_refs_forbidden")
    source_commit = git_output("rev-parse", "HEAD")
    if COMMIT_RE.fullmatch(source_commit) is None:
        raise ValueError("invalid_source_commit")
    for relative_path in (*SOURCE_FILES, *NATIVE_SOURCE_FILES):
        if git_output("status", "--short", "--", relative_path):
            raise ValueError(f"source_file_not_committed:{relative_path}")

    source_bindings = {
        relative_path: build_source_binding(relative_path)
        for relative_path in SOURCE_FILES
    }
    source_hashes = {
        name: source_bindings[path]["sha256"]
        for name, path in zip(SOURCE_HASH_NAMES, SOURCE_FILES, strict=True)
    }
    native_source_bindings = {
        relative_path: build_source_binding(relative_path)
        for relative_path in NATIVE_SOURCE_FILES
    }
    native_build_receipt = load_native_preflight_build_receipt(args)
    native_preflight = build_native_preflight_execution_contract(
        run_id=args.run_id,
        source_commit=source_commit,
        source_file_bindings=source_bindings,
        native_source_file_bindings=native_source_bindings,
        native_build_receipt=native_build_receipt,
    )
    contract = source_contract()
    phone_toolchain = phone_toolchain_contract()
    issued_at = datetime.now(timezone.utc).replace(microsecond=0)
    preregistration: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": "cur0s_commercial_authority_sources_phone_native_v1",
        "parent_experiment_id": "EXP-CUR0S-SOVEREIGN-COMPOSITE-V1",
        "run_id": args.run_id,
        "state": "frozen_unobserved",
        "candidate_output_observed": False,
        "candidate_output_files_present": False,
        "phone_execution_started": False,
        "promotion_allowed": False,
        "source_commit": source_commit,
        "source_file_sha256": source_hashes,
        "source_file_bindings": source_bindings,
        "commercial_source_contract": contract,
        "commercial_source_contract_sha256": canonical_sha256(contract),
        "phone_toolchain_identity": phone_toolchain,
        "phone_toolchain_identity_sha256": canonical_sha256(phone_toolchain),
        "native_preflight": native_preflight,
        "native_preflight_sha256": canonical_sha256(native_preflight),
        "parent_capsule_sha256": parent_capsule_sha256,
        "parent_frontier_root_sha256": parent_frontier_root_sha256,
        "maximal_selector_sha256": parent_frontier_root_sha256,
        "ACCESS_receipt_sha256": (
            "sha256:7b2b6d506b3ab82a17008edc4c79dd51512f6f9598e3db37cd1bb6f5ee4331ca"
        ),
        "campaign_lease": build_campaign_lease(args.run_id, issued_at),
        "resource_slice": {
            "phone_adb_serial_sha256": (
                "sha256:383e1fef6040334134430241a105f7d900f6d924e485fdc858441e734d3ae0f4"
            ),
            "phone_model": "NX789J",
            "phone_soc": "SM8750",
            "runpod": "not_used_for_this_action",
            "github_repository": "Zer0pa/Polymath-AI",
            "huggingface_visibility": "private_revision_pinned_C4_COM_only",
            "comet_payload": "hash_bound_metadata_only",
            "public_release": False,
        },
        "target_device": {
            "adb_serial_sha256": (
                "sha256:383e1fef6040334134430241a105f7d900f6d924e485fdc858441e734d3ae0f4"
            ),
            "architecture": "aarch64",
            "build_fingerprint_sha256": (
                "sha256:fce358a6cdd6535afbecf6f72088412abaccf9b9902c05800ee8852512f9882f"
            ),
            "device": "NX789J",
            "model": "NX789J",
            "private_home": "/data/data/com.termux/files/home",
            "python_platform_system": "Android",
            "soc": "SM8750",
        },
        "network_policy": {
            "allowed_https_hosts": list(ALLOWED_HTTPS_HOSTS),
            "cleartext_transport_allowed": False,
            "curl_resume_allowed": False,
            "direct_source_pre_and_post_metadata_required": True,
            "git_protocol": "https_only_exact_commit_sparse_fetch",
            "redirect_hops_must_remain_allowlisted_https": True,
        },
        "source_checkout_policy": (
            "git_HEAD_equals_source_commit_and_bound_files_match_blob_oid_bytes_sha256"
        ),
        "governing_inputs": {
            "PRD_sha256": (
                "sha256:725d0ad6ac77fdcfc06a2635c7552cc414e0ed48f30fbd0f7f7ec38720493a3c"
            ),
            "living_concept_sha256": (
                "sha256:b2f617766b660237ddfd329c6b7fa2370f9a2641983e71915b4cd71c6d31bacc"
            ),
            "corpus_audit_sha256": (
                "sha256:c3a5d5eacf424f6e50ae0a170873d1c80e566581e22031a8f64bc899f8eec0fa"
            ),
        },
        "claim_scope": "commercial_source_acquisition_identity_rights_and_phone_custody",
        "claim_ceiling": "source_root_passed_scope_only_not_integrated_CUR_0S",
        "output_directory_name": "candidate-001",
        "expected_disposition": (
            "retain_phone_private_source_root_and_continue_near_semantic_Arm_C"
        ),
        "transaction_policy": {
            "execution_claim_publication": (
                "canonical_empty_candidate_fsync_then_stable_package_anchor_"
                "run_keyed_O_EXCL_claim_last"
            ),
            "execution_claim_replay_allowed": False,
            "claim_only_disposition": "blocked_incomplete_nonreplayable",
            "terminal_success": ("canonical_receipt_bound_COMPLETE_O_EXCL_fsync_last"),
            "terminal_abort": (
                "stable_package_anchor_run_keyed_ABORT_O_EXCL_without_source_root_pass"
            ),
            "partial_claim_blocks_replay": True,
            "preclaim_orphan_reconciliation": (
                "exact_empty_owner_only_adopt_else_stable_ABORT"
            ),
            "control_anchor": "/data/data/com.termux",
            "exclusive_Termux_UID_operational_assumption": True,
            "concurrent_same_UID_writer_allowed": False,
            "malicious_same_UID_tamper_resistance_claimed": False,
            "package_reset_or_uninstall_invalidates_local_control_anchor": True,
        },
        "custody": {
            "C4_COM_and_C4_RX_roots_separate": True,
            "aggregate_hash_bound_receipt_egress": True,
            "execution_plane": "phone_private",
            "Mac_raw_cache": False,
            "private_HF_mirror": "deferred_until_source_root_passes_then_revision_pinned",
            "raw_payload_egress": False,
        },
        "nonclaims": [
            "not_semantic_material_compilation",
            "not_near_semantic_Arm_C",
            "not_connected_split_or_exposure_ledger",
            "not_C3_dictionary_or_C4_syllabus_admission",
            "not_CUR_0S_or_CUR_0P_or_composite_CUR_0",
            "not_target_data_learning_or_authority",
        ],
    }
    preregistration["preregistration_root_sha256"] = canonical_sha256(preregistration)
    return preregistration


def load_native_preflight_build_receipt(args: argparse.Namespace) -> dict[str, Any]:
    path_value = getattr(args, "native_preflight_build_receipt", None)
    expected_value = getattr(
        args,
        "expected_native_preflight_build_receipt_sha256",
        None,
    )
    if not isinstance(path_value, str) or not isinstance(expected_value, str):
        raise ValueError("native_preflight_build_receipt_arguments_required")
    path = Path(path_value)
    if not path.is_absolute() or Path(path.name).parts != (path.name,):
        raise ValueError("native_preflight_build_receipt_path_invalid")
    require_output_parent(path.parent)
    expected_sha256 = normalize_sha(expected_value)
    payload = read_stable_regular_file(path, 4 * 1024 * 1024)
    observed_sha256 = "sha256:" + hashlib.sha256(payload).hexdigest()
    if observed_sha256 != expected_sha256:
        raise ValueError("native_preflight_build_receipt_sha256_mismatch")

    def reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("native_preflight_build_receipt_duplicate_key")
            value[key] = item
        return value

    try:
        receipt = json.loads(
            payload,
            object_pairs_hook=reject_pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                ValueError("native_preflight_build_receipt_nonfinite")
            ),
        )
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ValueError("native_preflight_build_receipt_json_invalid") from error
    if not isinstance(receipt, dict) or canonical_json_bytes(receipt) != payload:
        raise ValueError("native_preflight_build_receipt_not_canonical")
    return receipt


def read_stable_regular_file(path: Path, max_bytes: int) -> bytes:
    parent_fd = os.open(
        path.parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        fd = os.open(
            path.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        try:
            initial = os.fstat(fd)
            if (
                not stat.S_ISREG(initial.st_mode)
                or initial.st_nlink != 1
                or initial.st_size <= 1
                or initial.st_size > max_bytes
            ):
                raise ValueError("native_preflight_build_receipt_inode_invalid")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(fd, min(1024 * 1024, max_bytes + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("native_preflight_build_receipt_oversize")
            final = os.fstat(fd)
            entry = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
            if (
                source_stat_identity(initial) != source_stat_identity(final)
                or source_stat_identity(final) != source_stat_identity(entry)
                or total != initial.st_size
            ):
                raise ValueError("native_preflight_build_receipt_changed")
            return b"".join(chunks)
        finally:
            os.close(fd)
    finally:
        os.close(parent_fd)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--parent-capsule-sha256", required=True)
    parser.add_argument("--parent-frontier-root-sha256", required=True)
    parser.add_argument("--native-preflight-build-receipt", required=True)
    parser.add_argument(
        "--expected-native-preflight-build-receipt-sha256",
        required=True,
    )
    parser.add_argument("--native-manifest-output", required=True)
    parser.add_argument("--native-launch-envelope-output", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def build_campaign_lease(run_id: str, issued_at: datetime) -> dict[str, Any]:
    if RUN_ID_RE.fullmatch(run_id) is None:
        raise ValueError("invalid_run_id")
    if issued_at.tzinfo is None or issued_at.utcoffset() != timedelta(0):
        raise ValueError("issued_at_must_be_UTC")
    issued_at = issued_at.replace(microsecond=0)
    expires_at = issued_at + timedelta(hours=4)
    thermal_contract = phone_thermal_safety_contract()
    return {
        "lease_id": "current_user_sovereign_frontier_campaign_20260712",
        "action_id": run_id,
        "state": "active",
        "issued_at_utc": iso_utc(issued_at),
        "expires_at_utc": iso_utc(expires_at),
        "additional_paid_capacity": False,
        "max_phone_execution_count": 1,
        "phone_execution_count_before": 0,
        "max_wall_seconds": 7200,
        "terminalization_reserve_seconds": 30,
        "max_private_output_bytes": 2_147_483_648,
        "min_free_storage_bytes": 10_737_418_240,
        "thermal_safety_contract": thermal_contract,
        "thermal_sample_interval_seconds": 5,
    }


def git_output(*args: str) -> str:
    return subprocess.run(
        [HOST_GIT, "--no-replace-objects", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
        env={
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "HOME": str(Path.home()),
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
        },
    ).stdout.strip()


def build_source_binding(relative_path: str) -> dict[str, Any]:
    path = ROOT / relative_path
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        initial = os.fstat(fd)
        if not stat.S_ISREG(initial.st_mode) or initial.st_nlink != 1:
            raise ValueError(f"source_file_inode_invalid:{relative_path}")
        payload = bytearray()
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            payload.extend(chunk)
        final = os.fstat(fd)
        entry = os.stat(path, follow_symlinks=False)
        initial_identity = source_stat_identity(initial)
        final_identity = source_stat_identity(final)
        entry_identity = source_stat_identity(entry)
        if initial_identity != final_identity or final_identity != entry_identity:
            raise ValueError(f"source_file_changed_during_read:{relative_path}")
    finally:
        os.close(fd)
    payload_bytes = bytes(payload)
    blob_header = f"blob {len(payload_bytes)}\0".encode("ascii")
    observed_blob = hashlib.sha1(
        blob_header + payload_bytes,
        usedforsecurity=False,
    ).hexdigest()
    expected_blob = git_output("rev-parse", f"HEAD:{relative_path}")
    if observed_blob != expected_blob:
        raise ValueError(f"source_file_blob_mismatch:{relative_path}")
    return {
        "bytes": len(payload_bytes),
        "git_blob_oid": expected_blob,
        "sha256": "sha256:" + hashlib.sha256(payload_bytes).hexdigest(),
    }


def source_stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


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
        if bytes(readback) != payload:
            raise RuntimeError("preregistration_readback_mismatch")
        os.fsync(parent_fd)
        return "sha256:" + hashlib.sha256(payload).hexdigest(), len(payload)
    finally:
        os.close(parent_fd)


if __name__ == "__main__":
    raise SystemExit(main())

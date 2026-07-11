#!/usr/bin/env python3
"""Build and atomically seal the Gemma 4 E4B L0 parent manifest."""

from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import errno
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
from pathlib import PurePosixPath
import stat
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from polymath_ai.frontier.e4b_l0 import (  # noqa: E402
    FULL_REVISION,
    HuggingFaceHubClient,
    build_default_l0_manifest,
    canonical_json_bytes,
    canonical_sha256,
)


MAX_JSON_INPUT_BYTES = 16 * 1024 * 1024
MAX_CAPSULE_BYTES = 16 * 1024 * 1024
MAX_SOURCE_FILE_BYTES = 8 * 1024 * 1024
MAX_SEALED_FILE_BYTES = 64 * 1024 * 1024
READ_CHUNK_BYTES = 1024 * 1024
GIT_TIMEOUT_SECONDS = 15
RENAME_NOREPLACE = 1
RENAME_EXCL = 0x00000004
LINUX_AT_FDCWD = -100
COMPLETION_MARKER_NAME = "L0_TRANSACTION_COMPLETE.json"
EXPORTER_REPOSITORY_LOCATOR = "github://Zer0pa/Polymath-AI"
LOCAL_CONVERTER_PROVENANCE_FIELDS = (
    "base_l0_input_bundle_manifest",
    "qairt_core_foundry_receipt",
    "qnn_api_source_identity",
    "qnn_common_header",
    "qairt_tool_verification_receipt",
)
REQUIRED_QAIRT_TOOLS = {
    "libQnnHtp",
    "libQnnSystem",
    "qnn_context_binary_generator",
    "qnn_context_binary_utility",
    "qnn_net_run",
}


class TransactionError(RuntimeError):
    """A deliberately sanitized, fail-closed transaction error."""

    def __init__(self, code: str) -> None:
        allowed = "abcdefghijklmnopqrstuvwxyz0123456789_"
        if not code or any(character not in allowed for character in code):
            code = "invalid_transaction_error"
        super().__init__(code)
        self.code = code


class DuplicateJsonKey(ValueError):
    """Raised when strict JSON contains a duplicate object member."""


class NonFiniteJson(ValueError):
    """Raised when strict JSON contains NaN or infinity."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--provisional-build-source",
        choices=("none", "qat_mobile_transformers", "qat_mobile_compressed_tensors"),
        required=True,
    )
    parser.add_argument("--reference-stacks", required=True)
    parser.add_argument("--weight-verification-receipts", required=True)
    parser.add_argument("--edge-a-protocol", required=True)
    parser.add_argument("--converter-lineage", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--parent-capsule", required=True)
    parser.add_argument("--parent-capsule-sha256", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return execute(parse_args(argv))
    except TransactionError as error:
        print(json.dumps({"error": error.code}, sort_keys=True), file=sys.stderr)
        return 1
    except Exception:
        # Provider, parser, filesystem, and builder exceptions can carry URLs,
        # paths, response bodies, or credentials. Never echo them from this
        # authority-bearing command.
        print(json.dumps({"error": "l0_manifest_transaction_failed"}), file=sys.stderr)
        return 1


def execute(args: argparse.Namespace) -> int:
    if not FULL_REVISION.fullmatch(args.source_revision):
        raise TransactionError("source_revision_must_be_full_sha")
    parent_capsule_sha256 = validate_sha256(
        args.parent_capsule_sha256,
        "parent_capsule_sha256_invalid",
    )

    # Refuse to make provider calls from a dirty or stale L0 implementation.
    verify_source_tree(args.source_revision)

    parent_capsule_path = absolute_path(args.parent_capsule)
    parent_capsule_bytes = read_bounded_regular_file(
        parent_capsule_path,
        max_bytes=MAX_CAPSULE_BYTES,
        error_prefix="parent_capsule",
    )
    observed_parent_sha256 = hashlib.sha256(parent_capsule_bytes).hexdigest()
    if observed_parent_sha256 != parent_capsule_sha256:
        raise TransactionError("parent_capsule_sha256_mismatch")
    parent_capsule_record = versioned_repository_file_record(
        parent_capsule_path,
        parent_capsule_bytes,
        source_revision=args.source_revision,
        error_prefix="parent_capsule",
    )

    input_paths = {
        "reference_stacks": absolute_path(args.reference_stacks),
        "weight_verification_receipts": absolute_path(
            args.weight_verification_receipts
        ),
        "edge_a_protocol": absolute_path(args.edge_a_protocol),
        "converter_lineage": absolute_path(args.converter_lineage),
    }
    inputs: dict[str, Any] = {}
    input_records: dict[str, dict[str, Any]] = {}
    for name, path in input_paths.items():
        value, payload = read_strict_json(path, error_prefix=name)
        inputs[name] = value
        input_records[name] = versioned_repository_file_record(
            path,
            payload,
            source_revision=args.source_revision,
            error_prefix=name,
        )

    verify_converter_lineage_provenance(
        inputs["converter_lineage"],
        source_revision=args.source_revision,
    )

    provisional_build_source = (
        None
        if args.provisional_build_source == "none"
        else args.provisional_build_source
    )
    payload = build_default_l0_manifest(
        HuggingFaceHubClient(token=None),
        provisional_build_source=provisional_build_source,
        reference_stacks=inputs["reference_stacks"],
        converter_lineage=inputs["converter_lineage"],
        edge_a_protocol=inputs["edge_a_protocol"],
        weight_verification_receipts=inputs["weight_verification_receipts"],
    )
    manifest = payload["manifest"]
    manifest_bytes = canonical_json_bytes(manifest)
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest_sha256 != payload["manifest_sha256"]:
        raise TransactionError("builder_manifest_hash_mismatch")

    # Capture modules imported lazily by the builder as well as the initial
    # import closure, and prove HEAD did not move during provider access.
    source_files = verify_source_tree(args.source_revision)

    output_dir = prepare_final_output_path(args.output_dir)
    final_manifest_path = output_dir / f"e4b_l0_parent_{manifest_sha256}.json"
    receipt = build_execution_receipt(
        args=args,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        parent_capsule=parent_capsule_record,
        inputs=input_records,
        source_files=source_files,
    )
    receipt_bytes = canonical_json_bytes(receipt)
    receipt_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
    final_receipt_path = output_dir / f"l0_execution_receipt_{receipt_sha256}.json"
    final_completion_marker_path = output_dir / COMPLETION_MARKER_NAME

    stage_path: Path | None = None
    stage_identity: tuple[int, int] | None = None
    staged_names: set[str] = set()
    try:
        stage_path, stage_identity = create_staging_directory(output_dir)
        staged_manifest_path = stage_path / final_manifest_path.name
        staged_receipt_path = stage_path / final_receipt_path.name

        exclusive_write(staged_manifest_path, manifest_bytes, "manifest")
        staged_names.add(staged_manifest_path.name)
        verify_file(
            staged_manifest_path,
            manifest_sha256,
            manifest_bytes,
            "manifest",
        )
        exclusive_write(staged_receipt_path, receipt_bytes, "receipt")
        staged_names.add(staged_receipt_path.name)
        verify_file(
            staged_receipt_path,
            receipt_sha256,
            receipt_bytes,
            "receipt",
        )
        fsync_directory(stage_path, "staging")

        if verify_source_tree(args.source_revision) != source_files:
            raise TransactionError("source_tree_changed_before_publish")

        atomic_rename_directory_noreplace(stage_path, output_dir)
        stage_path = None
        stage_identity = None

        verify_file(
            final_manifest_path,
            manifest_sha256,
            manifest_bytes,
            "final_manifest",
        )
        verify_file(
            final_receipt_path,
            receipt_sha256,
            receipt_bytes,
            "final_receipt",
        )
        fsync_directory(output_dir, "final_output")
        fsync_directory(output_dir.parent, "output_parent")

        # Admission is deliberately impossible until the already-published
        # manifest and receipt have both survived post-publish readback. The
        # marker itself is exclusive, file-fsynced by exclusive_write, then
        # directory-fsynced before any successful or completed-nonpassing exit.
        completion_marker = build_completion_marker(
            manifest=manifest,
            manifest_filename=final_manifest_path.name,
            manifest_sha256=manifest_sha256,
            receipt_filename=final_receipt_path.name,
            receipt_sha256=receipt_sha256,
        )
        completion_marker_bytes = canonical_json_bytes(completion_marker)
        completion_marker_sha256 = hashlib.sha256(completion_marker_bytes).hexdigest()
        exclusive_write(
            final_completion_marker_path,
            completion_marker_bytes,
            "completion_marker",
        )
        verify_file(
            final_completion_marker_path,
            completion_marker_sha256,
            completion_marker_bytes,
            "completion_marker",
        )
        fsync_directory(output_dir, "completion_marker_directory")
        fsync_directory(output_dir.parent, "completion_marker_parent")
        admitted = verify_published_transaction_admission(output_dir)
    finally:
        if stage_path is not None and stage_identity is not None:
            cleanup_owned_staging_directory(
                stage_path,
                stage_identity=stage_identity,
                staged_names=staged_names,
            )

    print(
        json.dumps(
            {
                "manifest": str(final_manifest_path),
                "manifest_sha256": manifest_sha256,
                "receipt": str(final_receipt_path),
                "receipt_sha256": receipt_sha256,
                "completion_marker": str(final_completion_marker_path),
                "completion_marker_sha256": completion_marker_sha256,
                "admitted": admitted,
                "state": manifest["state"],
            },
            sort_keys=True,
        )
    )
    if admitted != (manifest["state"] == "passed_scope"):
        raise TransactionError("completion_marker_admission_mismatch")
    return 0 if manifest["state"] == "passed_scope" else 2


def build_execution_receipt(
    *,
    args: argparse.Namespace,
    manifest: dict[str, Any],
    manifest_sha256: str,
    parent_capsule: dict[str, Any],
    inputs: dict[str, dict[str, Any]],
    source_files: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    blockers, manifest_effects = validate_manifest_admission_semantics(manifest)
    eligible_successors = manifest_effects["eligible_successors"]
    receipt_effects = dict(manifest_effects)
    receipt_effects["eligible_successors"] = list(eligible_successors)
    manifest_locator = content_addressed_locator(manifest_sha256)
    command_contract = {
        "operation": "build_gemma4_e4b_l0_manifest",
        "provisional_build_source": args.provisional_build_source,
        "source_revision": args.source_revision,
        "parent_capsule_sha256": parent_capsule["sha256"],
        "input_sha256s": {name: record["sha256"] for name, record in inputs.items()},
        "source_file_sha256s": {
            name: record["sha256"] for name, record in source_files.items()
        },
    }
    return {
        "schema_version": "gemma4_e4b_l0_execution_receipt_v3",
        "claim": {
            "claim_id": f"L0-E4B-transaction-{manifest_sha256[:16]}",
            "class": "local_verification",
            "state": "running",
            "manifest_state": manifest["state"],
            "scope": build_l0_claim_scope(manifest, manifest_sha256),
            "evidence": {
                "report_path_or_content_addressed_locator": manifest_locator,
                "report_sha256": manifest_sha256,
                "predecessor_claim_ids": [],
                "observed_at_utc": datetime.now(timezone.utc).isoformat(),
                "freshness": "immutable_event",
            },
            "blocker": {
                "class": None if not blockers else "identity_or_custody",
                "first_missing_green_field": blockers[0] if blockers else None,
            },
            "effects": receipt_effects,
            "effects_activation": {
                "state": "inactive_pending_completion_marker",
                "required_marker_filename": COMPLETION_MARKER_NAME,
            },
            "nonclaims": manifest["nonclaims"],
            "custody": {
                "raw_location_class": "provider_or_phone_local_or_none",
                "egress_result": "metadata_only",
            },
        },
        "transaction": {
            "parent_capsule": parent_capsule,
            "source_revision": args.source_revision,
            "source_files": source_files,
            "command_contract": command_contract,
            "command_contract_sha256": canonical_sha256(command_contract),
            "inputs": inputs,
            "manifest_locator": manifest_locator,
            "manifest_sha256": manifest_sha256,
            "atomic_directory_publish": True,
            "exclusive_noreplace_publish": True,
            "pre_publish_readback_verified": True,
            "post_publish_readback": "required_before_success_exit",
            "completion_marker": {
                "filename": COMPLETION_MARKER_NAME,
                "exclusive_create": True,
                "file_and_directory_fsync_required": True,
                "post_publish": True,
                "required_for_admission": True,
            },
            "capsule_advanced": False,
        },
    }


def build_completion_marker(
    *,
    manifest: dict[str, Any],
    manifest_filename: str,
    manifest_sha256: str,
    receipt_filename: str,
    receipt_sha256: str,
) -> dict[str, Any]:
    manifest_state = manifest.get("state")
    blockers, effects = validate_manifest_admission_semantics(manifest)
    completed_at_utc = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": "gemma4_e4b_l0_completion_marker_v1",
        "transaction_state": "complete",
        "artifacts": {
            "manifest": {
                "filename": manifest_filename,
                "locator": content_addressed_locator(manifest_sha256),
                "sha256": manifest_sha256,
            },
            "receipt": {
                "filename": receipt_filename,
                "locator": content_addressed_locator(receipt_sha256),
                "sha256": receipt_sha256,
            },
        },
        "claim": {
            "claim_id": f"L0-E4B-{manifest_sha256[:16]}",
            "class": "local_verification",
            "state": manifest_state,
            "scope": build_l0_claim_scope(manifest, manifest_sha256),
            "evidence": {
                "report_path_or_content_addressed_locator": (
                    content_addressed_locator(manifest_sha256)
                ),
                "report_sha256": manifest_sha256,
                "predecessor_claim_ids": [
                    f"L0-E4B-transaction-{manifest_sha256[:16]}"
                ],
                "observed_at_utc": completed_at_utc,
                "freshness": "immutable_event",
            },
            "blocker": {
                "class": None if not blockers else "identity_or_custody",
                "first_missing_green_field": blockers[0] if blockers else None,
            },
            "effects": dict(effects),
            "nonclaims": manifest.get("nonclaims", []),
            "custody": {
                "raw_location_class": "provider_or_phone_local_or_none",
                "egress_result": "metadata_only",
            },
        },
        "completed_at_utc": completed_at_utc,
    }


def validate_manifest_admission_semantics(
    manifest: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    state = manifest.get("state")
    if state not in {"passed_scope", "blocked_fail_closed"}:
        raise TransactionError("manifest_state_invalid")
    blockers = manifest.get("blockers")
    if (
        not isinstance(blockers, list)
        or any(not isinstance(blocker, str) or not blocker for blocker in blockers)
        or len(blockers) != len(set(blockers))
    ):
        raise TransactionError("manifest_blockers_invalid")
    if (state == "passed_scope") != (not blockers):
        raise TransactionError("manifest_state_blocker_mismatch")

    effects = manifest.get("effects")
    required_effects = {
        "closes_only",
        "eligible_successors",
        "promotion_allowed",
        "execution_authorized",
    }
    if not isinstance(effects, dict) or set(effects) != required_effects:
        raise TransactionError("manifest_effects_invalid")
    for field in ("closes_only", "eligible_successors"):
        values = effects.get(field)
        if (
            not isinstance(values, list)
            or any(not isinstance(value, str) or not value for value in values)
            or len(values) != len(set(values))
        ):
            raise TransactionError(f"manifest_{field}_invalid")
    if (
        effects.get("promotion_allowed") is not False
        or effects.get("execution_authorized") is not False
    ):
        raise TransactionError("manifest_forbidden_effect_enabled")
    if state != "passed_scope" and (
        effects["closes_only"] or effects["eligible_successors"]
    ):
        raise TransactionError("manifest_nonpassing_effects_active")
    return blockers, effects


def build_l0_claim_scope(
    manifest: dict[str, Any],
    manifest_sha256: str,
) -> dict[str, Any]:
    return {
        "model_artifact_sha256": manifest_sha256,
        "graph_context_sha256": "not_instantiated",
        "curriculum_root_sha256": "independent_not_joined_at_L0",
        "corpus_stage_and_material_view": "not_data_dependent",
        "source_instance_semantic_cluster_and_split_group_ids": (
            "not_real_data_dependent"
        ),
        "split_and_fixture_class": "not_data_dependent",
        "device_runtime_identity": "not_executed",
        "control_objective_evaluator_identity": manifest[
            "high_precision_task_oracle"
        ][
            "edge_A_decode_template_stop_length_seed_and_evaluator_protocol_sha256"
        ],
    }


def verify_published_transaction_admission(output_dir: Path) -> bool:
    """Verify the exclusive completion marker and every object it binds.

    A published directory without this marker is a crash remnant, never an L0
    admission. A completed nonpassing transaction is valid evidence but cannot
    activate effects or eligible successors.
    """

    marker_path = output_dir / COMPLETION_MARKER_NAME
    marker_bytes = read_bounded_regular_file(
        marker_path,
        max_bytes=MAX_SEALED_FILE_BYTES,
        error_prefix="completion_marker",
        require_unique_link=True,
    )
    marker = parse_strict_json_bytes(
        marker_bytes,
        error_prefix="completion_marker",
    )
    if not isinstance(marker, dict) or set(marker) != {
        "schema_version",
        "transaction_state",
        "artifacts",
        "claim",
        "completed_at_utc",
    }:
        raise TransactionError("completion_marker_schema_invalid")
    if (
        marker.get("schema_version") != "gemma4_e4b_l0_completion_marker_v1"
        or marker.get("transaction_state") != "complete"
    ):
        raise TransactionError("completion_marker_schema_invalid")

    artifacts = marker.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {"manifest", "receipt"}:
        raise TransactionError("completion_marker_artifacts_invalid")
    loaded: dict[str, dict[str, Any]] = {}
    for role in ("manifest", "receipt"):
        record = artifacts.get(role)
        if not isinstance(record, dict) or set(record) != {
            "filename",
            "locator",
            "sha256",
        }:
            raise TransactionError(f"completion_marker_{role}_invalid")
        filename = record.get("filename")
        sha256 = validate_sha256(
            str(record.get("sha256", "")),
            f"completion_marker_{role}_sha256_invalid",
        )
        if (
            not isinstance(filename, str)
            or not filename
            or PurePosixPath(filename).name != filename
            or filename in {".", "..", COMPLETION_MARKER_NAME}
        ):
            raise TransactionError(f"completion_marker_{role}_filename_invalid")
        expected_filename = (
            f"e4b_l0_parent_{sha256}.json"
            if role == "manifest"
            else f"l0_execution_receipt_{sha256}.json"
        )
        if filename != expected_filename:
            raise TransactionError(f"completion_marker_{role}_filename_invalid")
        if record.get("locator") != content_addressed_locator(sha256):
            raise TransactionError(f"completion_marker_{role}_locator_invalid")
        payload = read_bounded_regular_file(
            output_dir / filename,
            max_bytes=MAX_SEALED_FILE_BYTES,
            error_prefix=f"completion_marker_{role}",
            require_unique_link=True,
        )
        if hashlib.sha256(payload).hexdigest() != sha256:
            raise TransactionError(f"completion_marker_{role}_hash_mismatch")
        value = parse_strict_json_bytes(
            payload,
            error_prefix=f"completion_marker_{role}",
        )
        if not isinstance(value, dict):
            raise TransactionError(f"completion_marker_{role}_json_invalid")
        loaded[role] = value

    manifest = loaded["manifest"]
    receipt = loaded["receipt"]
    final_claim = marker.get("claim")
    expected_claim_fields = {
        "claim_id",
        "class",
        "state",
        "scope",
        "evidence",
        "blocker",
        "effects",
        "nonclaims",
        "custody",
    }
    if not isinstance(final_claim, dict) or set(final_claim) != expected_claim_fields:
        raise TransactionError("completion_marker_admission_invalid")
    manifest_state = manifest.get("state")
    admitted = manifest_state == "passed_scope"
    effects = manifest.get("effects")
    if not isinstance(effects, dict):
        raise TransactionError("completion_marker_manifest_effects_invalid")
    eligible_successors = effects.get("eligible_successors")
    if not isinstance(eligible_successors, list):
        raise TransactionError("completion_marker_manifest_effects_invalid")
    blockers = manifest.get("blockers")
    if not isinstance(blockers, list):
        raise TransactionError("completion_marker_manifest_blockers_invalid")
    expected_final_claim = {
        "claim_id": f"L0-E4B-{artifacts['manifest']['sha256'][:16]}",
        "class": "local_verification",
        "state": manifest_state,
        "scope": build_l0_claim_scope(manifest, artifacts["manifest"]["sha256"]),
        "evidence": {
            "report_path_or_content_addressed_locator": artifacts["manifest"][
                "locator"
            ],
            "report_sha256": artifacts["manifest"]["sha256"],
            "predecessor_claim_ids": [
                f"L0-E4B-transaction-{artifacts['manifest']['sha256'][:16]}"
            ],
            "observed_at_utc": marker.get("completed_at_utc"),
            "freshness": "immutable_event",
        },
        "blocker": {
            "class": None if not blockers else "identity_or_custody",
            "first_missing_green_field": blockers[0] if blockers else None,
        },
        "effects": effects,
        "nonclaims": manifest.get("nonclaims", []),
        "custody": {
            "raw_location_class": "provider_or_phone_local_or_none",
            "egress_result": "metadata_only",
        },
    }
    if final_claim != expected_final_claim:
        raise TransactionError("completion_marker_admission_mismatch")

    claim = receipt.get("claim")
    transaction = receipt.get("transaction")
    if not isinstance(claim, dict) or not isinstance(transaction, dict):
        raise TransactionError("completion_marker_receipt_contract_invalid")
    if (
        receipt.get("schema_version") != "gemma4_e4b_l0_execution_receipt_v3"
        or claim.get("claim_id")
        != f"L0-E4B-transaction-{artifacts['manifest']['sha256'][:16]}"
        or claim.get("state") != "running"
        or claim.get("manifest_state") != manifest_state
        or claim.get("effects") != effects
        or claim.get("effects_activation")
        != {
            "state": "inactive_pending_completion_marker",
            "required_marker_filename": COMPLETION_MARKER_NAME,
        }
        or transaction.get("manifest_sha256")
        != artifacts["manifest"]["sha256"]
        or transaction.get("manifest_locator") != artifacts["manifest"]["locator"]
    ):
        raise TransactionError("completion_marker_receipt_contract_invalid")
    marker_contract = transaction.get("completion_marker")
    if not isinstance(marker_contract, dict) or marker_contract != {
        "filename": COMPLETION_MARKER_NAME,
        "exclusive_create": True,
        "file_and_directory_fsync_required": True,
        "post_publish": True,
        "required_for_admission": True,
    }:
        raise TransactionError("completion_marker_receipt_contract_invalid")
    return admitted


def content_addressed_locator(sha256: str) -> str:
    return f"immutable://sha256/{validate_sha256(sha256, 'sha256_invalid')}"


def absolute_path(value: str | os.PathLike[str]) -> Path:
    return Path(os.path.abspath(os.fspath(value)))


def file_record(path: Path, payload: bytes) -> dict[str, Any]:
    sha256 = hashlib.sha256(payload).hexdigest()
    return {
        "locator": stable_file_locator(path, sha256),
        "sha256": sha256,
        "bytes": len(payload),
    }


def stable_file_locator(path: Path, sha256: str, *, root: Path = ROOT) -> str:
    try:
        resolved_root = root.resolve(strict=True)
        resolved_path = path.resolve(strict=True)
        relative = resolved_path.relative_to(resolved_root).as_posix()
    except (OSError, ValueError):
        return content_addressed_locator(sha256)
    if not relative:
        return content_addressed_locator(sha256)
    return relative


def versioned_repository_file_record(
    path: Path,
    payload: bytes,
    *,
    source_revision: str,
    error_prefix: str = "parent_capsule",
    root: Path = ROOT,
) -> dict[str, Any]:
    try:
        resolved_root = root.resolve(strict=True)
        relative = path.relative_to(resolved_root).as_posix()
    except (OSError, ValueError) as error:
        raise TransactionError(f"{error_prefix}_outside_repository") from error
    relative = validate_repository_relative_locator(
        relative,
        error_code=f"{error_prefix}_locator_invalid",
    )
    verified_path = resolve_repository_file(
        resolved_root,
        relative,
        error_prefix=error_prefix,
    )
    if verified_path != path:
        raise TransactionError(f"{error_prefix}_locator_invalid")
    committed = git_output(
        resolved_root,
        ["cat-file", "blob", f"{source_revision}:{relative}"],
        MAX_CAPSULE_BYTES,
    )
    if committed != payload:
        raise TransactionError(f"{error_prefix}_differs_from_source_revision")
    try:
        git_blob_oid = (
            git_output(
                resolved_root,
                ["rev-parse", "--verify", f"{source_revision}:{relative}"],
                256,
            )
            .decode("ascii", errors="strict")
            .strip()
        )
    except UnicodeDecodeError as error:
        raise TransactionError(f"{error_prefix}_blob_oid_invalid") from error
    if len(git_blob_oid) not in {40, 64} or any(
        character not in "0123456789abcdef" for character in git_blob_oid
    ):
        raise TransactionError(f"{error_prefix}_blob_oid_invalid")
    return {
        "locator": relative,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "source_revision": source_revision,
        "git_blob_oid": git_blob_oid,
    }


def verify_converter_lineage_provenance(
    converter: Any,
    *,
    source_revision: str,
    root: Path = ROOT,
) -> None:
    if not FULL_REVISION.fullmatch(source_revision):
        raise TransactionError("converter_provenance_source_revision_invalid")
    if not isinstance(converter, dict):
        raise TransactionError("converter_lineage_not_object")

    local_payloads: dict[str, bytes] = {}
    for field in LOCAL_CONVERTER_PROVENANCE_FIELDS:
        local_payloads[field] = verify_repository_file_record(
            converter.get(field),
            root=root,
            source_revision=source_revision,
            error_prefix=f"converter_{field}",
        )

    source_identity = parse_strict_json_bytes(
        local_payloads["qnn_api_source_identity"],
        error_prefix="converter_qnn_api_source_identity",
    )
    if not isinstance(source_identity, dict):
        raise TransactionError("converter_qnn_api_source_identity_not_object")
    if source_identity.get("resolved_version") != converter.get("QNN_API_version"):
        raise TransactionError("converter_qnn_api_version_provenance_mismatch")
    if source_identity.get("sdk_build") != converter.get(
        "converter_and_QAIRT_build"
    ):
        raise TransactionError("converter_qairt_build_provenance_mismatch")
    qnn_common_header = converter.get("qnn_common_header")
    if not isinstance(qnn_common_header, dict):
        raise TransactionError("converter_qnn_common_header_record_invalid")
    if source_identity.get("source_sha256") != qnn_common_header.get("sha256"):
        raise TransactionError("converter_qnn_header_provenance_mismatch")

    qairt_tools = verify_qairt_tool_records(converter.get("qairt_tools"))
    tool_verification = parse_strict_json_bytes(
        local_payloads["qairt_tool_verification_receipt"],
        error_prefix="converter_qairt_tool_verification_receipt",
    )
    if not isinstance(tool_verification, dict):
        raise TransactionError("converter_qairt_tool_receipt_not_object")
    if tool_verification.get("qairt_build") != converter.get(
        "converter_and_QAIRT_build"
    ):
        raise TransactionError("converter_qairt_tool_build_mismatch")
    if tool_verification.get("tools") != qairt_tools:
        raise TransactionError("converter_qairt_tool_receipt_mismatch")

    verify_exporter_source(converter, root=root)


def verify_repository_file_record(
    record: Any,
    *,
    root: Path,
    source_revision: str,
    error_prefix: str,
) -> bytes:
    if not isinstance(record, dict) or set(record) != {"locator", "sha256"}:
        raise TransactionError(f"{error_prefix}_record_invalid")
    locator = record.get("locator")
    relative = validate_repository_relative_locator(
        locator,
        error_code=f"{error_prefix}_locator_invalid",
    )
    sha256 = validate_sha256(
        str(record.get("sha256", "")),
        f"{error_prefix}_sha256_invalid",
    )
    path = resolve_repository_file(
        root,
        relative,
        error_prefix=error_prefix,
    )
    payload = read_bounded_regular_file(
        path,
        max_bytes=MAX_SEALED_FILE_BYTES,
        error_prefix=error_prefix,
    )
    if hashlib.sha256(payload).hexdigest() != sha256:
        raise TransactionError(f"{error_prefix}_hash_mismatch")
    committed = git_output(
        root,
        ["cat-file", "blob", f"{source_revision}:{relative}"],
        MAX_SEALED_FILE_BYTES,
    )
    if committed != payload:
        raise TransactionError(f"{error_prefix}_differs_from_source_revision")
    return payload


def validate_repository_relative_locator(locator: Any, *, error_code: str) -> str:
    if (
        not isinstance(locator, str)
        or not locator
        or "\\" in locator
        or "\x00" in locator
        or "://" in locator
    ):
        raise TransactionError(error_code)
    path = PurePosixPath(locator)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise TransactionError(error_code)
    normalized = path.as_posix()
    if normalized != locator:
        raise TransactionError(error_code)
    return normalized


def resolve_repository_file(
    root: Path,
    relative: str,
    *,
    error_prefix: str,
) -> Path:
    try:
        resolved_root = root.resolve(strict=True)
        root_metadata = resolved_root.lstat()
    except OSError as error:
        raise TransactionError(f"{error_prefix}_repository_root_invalid") from error
    if not stat.S_ISDIR(root_metadata.st_mode) or resolved_root.is_symlink():
        raise TransactionError(f"{error_prefix}_repository_root_invalid")

    current = resolved_root
    parts = PurePosixPath(relative).parts
    for index, part in enumerate(parts):
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as error:
            raise TransactionError(f"{error_prefix}_read_failed") from error
        if stat.S_ISLNK(metadata.st_mode):
            raise TransactionError(f"{error_prefix}_symlink_forbidden")
        if index < len(parts) - 1 and not stat.S_ISDIR(metadata.st_mode):
            raise TransactionError(f"{error_prefix}_parent_not_directory")
    try:
        current.relative_to(resolved_root)
    except ValueError as error:
        raise TransactionError(f"{error_prefix}_locator_invalid") from error
    return current


def verify_qairt_tool_records(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict) or set(value) != REQUIRED_QAIRT_TOOLS:
        raise TransactionError("converter_qairt_tools_invalid")
    verified: dict[str, dict[str, str]] = {}
    for name, record in value.items():
        if not isinstance(record, dict) or set(record) != {"locator", "sha256"}:
            raise TransactionError("converter_qairt_tool_record_invalid")
        locator = record.get("locator")
        if (
            not isinstance(locator, str)
            or not locator.startswith("runpod://")
            or locator == "runpod://"
            or "?" in locator
            or "#" in locator
            or "\x00" in locator
        ):
            raise TransactionError("converter_qairt_tool_locator_invalid")
        sha256 = validate_sha256(
            str(record.get("sha256", "")),
            "converter_qairt_tool_sha256_invalid",
        )
        verified[name] = {"locator": locator, "sha256": sha256}
    return dict(sorted(verified.items()))


def verify_exporter_source(converter: dict[str, Any], *, root: Path) -> None:
    exporter = converter.get("exporter_source")
    if not isinstance(exporter, dict) or set(exporter) != {
        "repository_locator",
        "revision",
        "source_files",
    }:
        raise TransactionError("converter_exporter_source_invalid")
    if exporter.get("repository_locator") != EXPORTER_REPOSITORY_LOCATOR:
        raise TransactionError("converter_exporter_repository_invalid")
    revision = str(exporter.get("revision", ""))
    if not FULL_REVISION.fullmatch(revision):
        raise TransactionError("converter_exporter_revision_invalid")
    if revision != converter.get("exporter_revision"):
        raise TransactionError("converter_exporter_revision_mismatch")
    source_files = exporter.get("source_files")
    if not isinstance(source_files, dict) or not source_files:
        raise TransactionError("converter_exporter_source_files_invalid")
    for locator, expected_sha256 in source_files.items():
        relative = validate_repository_relative_locator(
            locator,
            error_code="converter_exporter_source_locator_invalid",
        )
        sha256 = validate_sha256(
            str(expected_sha256),
            "converter_exporter_source_sha256_invalid",
        )
        committed = git_output(
            root,
            ["cat-file", "blob", f"{revision}:{relative}"],
            MAX_SOURCE_FILE_BYTES,
        )
        if hashlib.sha256(committed).hexdigest() != sha256:
            raise TransactionError("converter_exporter_source_hash_mismatch")


def read_strict_json(path: Path, *, error_prefix: str) -> tuple[Any, bytes]:
    payload = read_bounded_regular_file(
        path,
        max_bytes=MAX_JSON_INPUT_BYTES,
        error_prefix=error_prefix,
    )
    return parse_strict_json_bytes(payload, error_prefix=error_prefix), payload


def parse_strict_json_bytes(payload: bytes, *, error_prefix: str) -> Any:
    try:
        text = payload.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicate_json_keys,
            parse_constant=reject_json_constant,
        )
        validate_finite_json_tree(value)
    except DuplicateJsonKey as error:
        raise TransactionError(f"{error_prefix}_duplicate_json_key") from error
    except NonFiniteJson as error:
        raise TransactionError(f"{error_prefix}_nonfinite_json") from error
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise TransactionError(f"{error_prefix}_invalid_json") from error
    return value


def reject_duplicate_json_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKey
        result[key] = value
    return result


def reject_json_constant(_value: str) -> None:
    raise NonFiniteJson


def validate_finite_json_tree(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise NonFiniteJson
    if isinstance(value, list):
        for item in value:
            validate_finite_json_tree(item)
    elif isinstance(value, dict):
        for item in value.values():
            validate_finite_json_tree(item)


def read_bounded_regular_file(
    path: Path,
    *,
    max_bytes: int,
    error_prefix: str,
    require_unique_link: bool = False,
) -> bytes:
    if not hasattr(os, "O_NOFOLLOW"):
        raise TransactionError("o_nofollow_unavailable")
    flags = os.O_RDONLY | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise TransactionError(f"{error_prefix}_not_regular_file")
        if require_unique_link and before.st_nlink != 1:
            raise TransactionError(f"{error_prefix}_not_unique_file")
        if before.st_size < 0 or before.st_size > max_bytes:
            raise TransactionError(f"{error_prefix}_size_out_of_bounds")

        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(
                descriptor,
                min(READ_CHUNK_BYTES, max_bytes + 1 - total),
            )
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise TransactionError(f"{error_prefix}_size_out_of_bounds")
        after = os.fstat(descriptor)
        identity_before = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if identity_before != identity_after or total != before.st_size:
            raise TransactionError(f"{error_prefix}_changed_during_read")
        return b"".join(chunks)
    except TransactionError:
        raise
    except OSError as error:
        raise TransactionError(f"{error_prefix}_read_failed") from error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


def validate_sha256(value: str, error_code: str) -> str:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise TransactionError(error_code)
    return value


def collect_loaded_l0_source_paths() -> list[Path]:
    paths = {Path(__file__).resolve()}
    for module_name, module in tuple(sys.modules.items()):
        if module_name != "polymath_ai" and not module_name.startswith("polymath_ai."):
            continue
        module_file = getattr(module, "__file__", None)
        if not module_file:
            raise TransactionError("loaded_source_has_no_file")
        path = Path(module_file)
        if path.suffix in {".pyc", ".pyo"}:
            try:
                path = Path(importlib.util.source_from_cache(str(path)))
            except ValueError as error:
                raise TransactionError("loaded_source_path_invalid") from error
        if path.suffix != ".py":
            raise TransactionError("loaded_source_not_python")
        paths.add(absolute_path(path))
    return sorted(paths, key=str)


def verify_source_tree(
    source_revision: str,
    *,
    root: Path = ROOT,
    source_paths: Sequence[Path] | None = None,
) -> dict[str, dict[str, Any]]:
    root = root.resolve()
    observed_root = git_output(root, ["rev-parse", "--show-toplevel"], 4096)
    try:
        git_root = Path(observed_root.decode("utf-8").strip()).resolve()
    except (UnicodeDecodeError, OSError) as error:
        raise TransactionError("git_root_invalid") from error
    if git_root != root:
        raise TransactionError("git_root_mismatch")

    try:
        observed_head = (
            git_output(
                root,
                ["rev-parse", "--verify", "HEAD^{commit}"],
                256,
            )
            .decode("ascii", errors="strict")
            .strip()
        )
    except UnicodeDecodeError as error:
        raise TransactionError("git_head_invalid") from error
    if observed_head != source_revision:
        raise TransactionError("source_revision_not_current_head")

    paths = (
        list(source_paths)
        if source_paths is not None
        else collect_loaded_l0_source_paths()
    )
    records: dict[str, dict[str, Any]] = {}
    for path in paths:
        resolved_path = absolute_path(path)
        try:
            relative_path = resolved_path.relative_to(root).as_posix()
        except ValueError as error:
            raise TransactionError("loaded_source_outside_repository") from error
        if relative_path in records:
            raise TransactionError("duplicate_loaded_source_path")
        local_bytes = read_bounded_regular_file(
            resolved_path,
            max_bytes=MAX_SOURCE_FILE_BYTES,
            error_prefix="source_file",
        )
        object_spec = f"{source_revision}:{relative_path}"
        committed_bytes = git_output(
            root,
            ["cat-file", "blob", object_spec],
            MAX_SOURCE_FILE_BYTES,
        )
        if committed_bytes != local_bytes:
            raise TransactionError("loaded_source_differs_from_commit")
        try:
            blob_oid = (
                git_output(
                    root,
                    ["rev-parse", "--verify", object_spec],
                    256,
                )
                .decode("ascii", errors="strict")
                .strip()
            )
        except UnicodeDecodeError as error:
            raise TransactionError("source_blob_oid_invalid") from error
        if len(blob_oid) not in {40, 64} or any(
            character not in "0123456789abcdef" for character in blob_oid
        ):
            raise TransactionError("source_blob_oid_invalid")
        records[relative_path] = {
            "sha256": hashlib.sha256(local_bytes).hexdigest(),
            "bytes": len(local_bytes),
            "git_blob_oid": blob_oid,
        }
    if not records:
        raise TransactionError("no_loaded_source_files")
    return dict(sorted(records.items()))


def git_output(root: Path, arguments: Sequence[str], max_bytes: int) -> bytes:
    environment = os.environ.copy()
    environment.update({"GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"})
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            ["git", *arguments],
            cwd=root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if process.stdout is None:
            raise TransactionError("git_verification_failed")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = process.stdout.read(min(READ_CHUNK_BYTES, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                process.kill()
                process.wait(timeout=GIT_TIMEOUT_SECONDS)
                raise TransactionError("git_verification_failed")
        return_code = process.wait(timeout=GIT_TIMEOUT_SECONDS)
    except TransactionError:
        raise
    except (OSError, subprocess.TimeoutExpired) as error:
        if process is not None:
            try:
                process.kill()
                process.wait(timeout=GIT_TIMEOUT_SECONDS)
            except (OSError, subprocess.TimeoutExpired):
                pass
        raise TransactionError("git_verification_failed") from error
    if return_code != 0:
        raise TransactionError("git_verification_failed")
    return b"".join(chunks)


def prepare_final_output_path(value: str | os.PathLike[str]) -> Path:
    requested_path = absolute_path(value)
    if requested_path.name in {"", ".", ".."}:
        raise TransactionError("output_dir_invalid")
    try:
        parent = requested_path.parent.resolve(strict=True)
        parent_metadata = parent.lstat()
    except OSError as error:
        raise TransactionError("output_parent_invalid") from error
    if not stat.S_ISDIR(parent_metadata.st_mode) or parent.is_symlink():
        raise TransactionError("output_parent_invalid")
    output_dir = parent / requested_path.name
    try:
        output_dir.lstat()
    except FileNotFoundError:
        return output_dir
    except OSError as error:
        raise TransactionError("output_dir_probe_failed") from error
    raise TransactionError("output_dir_already_exists")


def create_staging_directory(output_dir: Path) -> tuple[Path, tuple[int, int]]:
    stage: Path | None = None
    try:
        stage = Path(
            tempfile.mkdtemp(
                prefix=f".{output_dir.name}.staging-",
                dir=output_dir.parent,
            )
        )
        metadata = stage.lstat()
    except OSError as error:
        if stage is not None:
            try:
                os.rmdir(stage)
            except OSError:
                pass
        raise TransactionError("staging_directory_create_failed") from error
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_nlink < 2:
        try:
            os.rmdir(stage)
        except OSError:
            pass
        raise TransactionError("staging_directory_invalid")
    return stage, (metadata.st_dev, metadata.st_ino)


def exclusive_write(path: Path, payload: bytes, error_prefix: str) -> None:
    if not hasattr(os, "O_NOFOLLOW"):
        raise TransactionError("o_nofollow_unavailable")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags, 0o444)
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise TransactionError(f"{error_prefix}_write_failed")
            view = view[written:]
        os.fsync(descriptor)
    except TransactionError:
        raise
    except OSError as error:
        raise TransactionError(f"{error_prefix}_write_failed") from error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


def verify_file(
    path: Path,
    expected_sha256: str,
    expected_bytes: bytes,
    error_prefix: str,
) -> None:
    observed = read_bounded_regular_file(
        path,
        max_bytes=max(MAX_SEALED_FILE_BYTES, len(expected_bytes)),
        error_prefix=error_prefix,
        require_unique_link=True,
    )
    if observed != expected_bytes:
        raise TransactionError(f"{error_prefix}_readback_mismatch")
    if hashlib.sha256(observed).hexdigest() != expected_sha256:
        raise TransactionError(f"{error_prefix}_hash_mismatch")


def fsync_directory(path: Path, error_prefix: str) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode):
            raise TransactionError(f"{error_prefix}_not_directory")
        os.fsync(descriptor)
    except TransactionError:
        raise
    except OSError as error:
        raise TransactionError(f"{error_prefix}_fsync_failed") from error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


def atomic_rename_directory_noreplace(source: Path, destination: Path) -> None:
    if source.parent != destination.parent:
        raise TransactionError("staging_not_same_parent")
    libc = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    if sys.platform.startswith("linux"):
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is None:
            raise TransactionError("atomic_noreplace_rename_unavailable")
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        result = renameat2(
            LINUX_AT_FDCWD,
            source_bytes,
            LINUX_AT_FDCWD,
            destination_bytes,
            RENAME_NOREPLACE,
        )
    elif sys.platform == "darwin":
        renamex_np = getattr(libc, "renamex_np", None)
        if renamex_np is None:
            raise TransactionError("atomic_noreplace_rename_unavailable")
        renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        renamex_np.restype = ctypes.c_int
        result = renamex_np(source_bytes, destination_bytes, RENAME_EXCL)
    else:
        raise TransactionError("atomic_noreplace_rename_unavailable")
    if result == 0:
        return
    observed_errno = ctypes.get_errno()
    if observed_errno in {errno.EEXIST, errno.ENOTEMPTY}:
        raise TransactionError("output_dir_already_exists")
    raise TransactionError("atomic_noreplace_rename_failed")


def cleanup_owned_staging_directory(
    path: Path,
    *,
    stage_identity: tuple[int, int],
    staged_names: set[str],
) -> None:
    """Best-effort cleanup that cannot recurse outside the owned stage."""

    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        metadata = os.fstat(descriptor)
        if (metadata.st_dev, metadata.st_ino) != stage_identity:
            return
        observed_names = set(os.listdir(descriptor))
        if not observed_names.issubset(staged_names):
            return
        for name in observed_names:
            os.unlink(name, dir_fd=descriptor)
    except OSError:
        return
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
    try:
        os.rmdir(path)
    except OSError:
        pass


if __name__ == "__main__":
    raise SystemExit(main())

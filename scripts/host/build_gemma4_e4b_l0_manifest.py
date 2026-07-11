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
        choices=("qat_mobile_transformers", "qat_mobile_compressed_tensors"),
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
    parent_capsule_record = file_record(parent_capsule_path, parent_capsule_bytes)

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
        input_records[name] = file_record(path, payload)

    payload = build_default_l0_manifest(
        HuggingFaceHubClient(token=None),
        provisional_build_source=args.provisional_build_source,
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
        manifest_path=final_manifest_path,
        manifest_sha256=manifest_sha256,
        parent_capsule=parent_capsule_record,
        inputs=input_records,
        source_files=source_files,
    )
    receipt_bytes = canonical_json_bytes(receipt)
    receipt_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
    final_receipt_path = output_dir / f"l0_execution_receipt_{receipt_sha256}.json"

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
                "state": manifest["state"],
            },
            sort_keys=True,
        )
    )
    return 0 if manifest["state"] == "passed_scope" else 2


def build_execution_receipt(
    *,
    args: argparse.Namespace,
    manifest: dict[str, Any],
    manifest_path: Path,
    manifest_sha256: str,
    parent_capsule: dict[str, Any],
    inputs: dict[str, dict[str, Any]],
    source_files: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    blockers = manifest.get("blockers", [])
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
        "schema_version": "gemma4_e4b_l0_execution_receipt_v2",
        "claim": {
            "claim_id": f"L0-E4B-{manifest_sha256[:16]}",
            "class": "local_verification",
            "state": manifest["state"],
            "scope": {
                "model_artifact_sha256": manifest_sha256,
                "graph_context_sha256": "not_instantiated",
                "curriculum_root_sha256": "independent_not_joined_at_L0",
                "device_runtime_identity": "not_executed",
                "control_objective_evaluator_identity": manifest[
                    "high_precision_task_oracle"
                ][
                    "edge_A_decode_template_stop_length_seed_and_evaluator_protocol_sha256"
                ],
            },
            "evidence": {
                "report_path_or_content_addressed_locator": str(manifest_path),
                "report_sha256": manifest_sha256,
                "predecessor_claim_ids": [],
                "observed_at_utc": datetime.now(timezone.utc).isoformat(),
                "freshness": "immutable_event",
            },
            "blocker": {
                "class": None if not blockers else "identity_or_custody",
                "first_missing_green_field": blockers[0] if blockers else None,
            },
            "effects": manifest["effects"],
            "nonclaims": manifest["nonclaims"],
            "custody": {
                "raw_location_class": "provider_local_or_none",
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
            "manifest_locator": str(manifest_path),
            "manifest_sha256": manifest_sha256,
            "atomic_directory_publish": True,
            "exclusive_noreplace_publish": True,
            "pre_publish_readback_verified": True,
            "post_publish_readback": "required_before_success_exit",
            "capsule_advanced": False,
        },
    }


def absolute_path(value: str | os.PathLike[str]) -> Path:
    return Path(os.path.abspath(os.fspath(value)))


def file_record(path: Path, payload: bytes) -> dict[str, Any]:
    return {
        "locator": str(path),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
    }


def read_strict_json(path: Path, *, error_prefix: str) -> tuple[Any, bytes]:
    payload = read_bounded_regular_file(
        path,
        max_bytes=MAX_JSON_INPUT_BYTES,
        error_prefix=error_prefix,
    )
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
    return value, payload


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

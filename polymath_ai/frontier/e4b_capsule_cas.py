"""Fail-closed current-reality capsule compare-and-swap migrations.

The capsule is a last-verified pointer, not an authorization document.  This
module admits only explicit, reviewed migration profiles.  A later capsule
schema must get a new profile instead of inheriting a permissive updater.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import copy
from dataclasses import dataclass
import errno
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
from typing import Any, NoReturn

import yaml


EXPECTED_V4_SHA256 = (
    "7f85799e260658cd400b837a784035438c7601e3057d963e4cf9b98f14841266"
)
EXPECTED_V5_SHA256 = (
    "66072e0dee357c9d7c178c3fa3628a6230fa5992659325b80e7eefa6e4dbdd2b"
)
V4_SCHEMA = "apex_current_reality_gemma4_e4b_qnn_cell_v4"
V5_SCHEMA = "apex_current_reality_gemma4_e4b_qnn_cell_v5"
V6_SCHEMA = "apex_current_reality_gemma4_e4b_qnn_cell_v6"
SPEC_SCHEMA = "apex_current_reality_capsule_transition_spec_v1"
RECEIPT_SCHEMA = "apex_current_reality_capsule_transition_receipt_v1"
COMPLETION_SCHEMA = "apex_current_reality_capsule_transition_completion_v1"
V6_SPEC_SCHEMA = "apex_current_reality_capsule_transition_spec_v2"
V6_RECEIPT_SCHEMA = "apex_current_reality_capsule_transition_receipt_v2"
V6_COMPLETION_SCHEMA = "apex_current_reality_capsule_transition_completion_v2"


@dataclass(frozen=True)
class _MigrationProfile:
    expected_parent_sha256: str
    parent_schema: str
    child_schema: str
    spec_schema: str
    receipt_schema: str
    completion_schema: str
    child_schema_error: str


_V4_TO_V5 = _MigrationProfile(
    expected_parent_sha256=EXPECTED_V4_SHA256,
    parent_schema=V4_SCHEMA,
    child_schema=V5_SCHEMA,
    spec_schema=SPEC_SCHEMA,
    receipt_schema=RECEIPT_SCHEMA,
    completion_schema=COMPLETION_SCHEMA,
    child_schema_error="child_schema_version_not_v5",
)
_V5_TO_V6 = _MigrationProfile(
    expected_parent_sha256=EXPECTED_V5_SHA256,
    parent_schema=V5_SCHEMA,
    child_schema=V6_SCHEMA,
    spec_schema=V6_SPEC_SCHEMA,
    receipt_schema=V6_RECEIPT_SCHEMA,
    completion_schema=V6_COMPLETION_SCHEMA,
    child_schema_error="child_schema_version_not_v6",
)

MAX_CAPSULE_BYTES = 16 * 1024 * 1024
MAX_SPEC_BYTES = 4 * 1024 * 1024
MAX_BOUND_ARTIFACT_BYTES = 32 * 1024 * 1024 * 1024

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

_TOP_LEVEL_SPEC_KEYS = {
    "schema_version",
    "transaction_id",
    "expected_parent_sha256",
    "evidence_cutoff_utc",
    "mutation",
    "bindings",
}
_BINDING_KEYS = {
    "frontier",
    "preregistrations",
    "maximal_selector",
    "lease",
    "inputs",
    "raw_reports",
    "sanitized_reports",
    "transitions",
    "rollback",
    "source_commit",
    "evidence_commit",
    "scoped_push_receipt",
}
_REQUIRED_BINDING_KEYS = _BINDING_KEYS - {"scoped_push_receipt"}
_ARTIFACT_REQUIRED_KEYS = {"role", "locator", "sha256", "bytes", "custody"}
_ARTIFACT_OPTIONAL_KEYS = {"local_path"}
_SECRET_KEYS = {
    "access_token",
    "api_key",
    "authorization_header",
    "credential",
    "credential_value",
    "password",
    "private_key",
    "refresh_token",
    "secret_value",
    "token",
}
_SECRET_PREFIXES = ("Bearer ", "ghp_", "github_pat_", "hf_", "sk-")


class CapsuleTransitionError(RuntimeError):
    """Stable fail-closed error carrying a machine-readable code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class StrictYAMLLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects aliases and duplicate mapping keys."""

    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(yaml.events.AliasEvent):
            raise CapsuleTransitionError("yaml_alias_forbidden")
        return super().compose_node(parent, index)


def _construct_unique_mapping(
    loader: StrictYAMLLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[str, Any]:
    loader.flatten_mapping(node)
    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str):
            raise CapsuleTransitionError("yaml_mapping_key_not_string")
        if key in result:
            raise CapsuleTransitionError(f"yaml_duplicate_key:{key}")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


StrictYAMLLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json(value: Any) -> bytes:
    _validate_data_tree(value, "canonical_json")
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise CapsuleTransitionError("canonical_json_invalid") from error
    return encoded.encode("utf-8")


def value_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json(value))


def strict_json_loads(payload: bytes) -> dict[str, Any]:
    def reject_constant(_value: str) -> NoReturn:
        raise CapsuleTransitionError("json_non_finite_number")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise CapsuleTransitionError(f"json_duplicate_key:{key}")
            result[key] = value
        return result

    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CapsuleTransitionError("json_not_utf8") from error
    try:
        value = json.loads(
            decoded,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except CapsuleTransitionError:
        raise
    except (json.JSONDecodeError, RecursionError) as error:
        raise CapsuleTransitionError("json_parse_failed") from error
    if not isinstance(value, dict):
        raise CapsuleTransitionError("json_root_not_mapping")
    _validate_data_tree(value, "json")
    return value


def strict_yaml_loads(payload: bytes) -> dict[str, Any]:
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CapsuleTransitionError("yaml_not_utf8") from error
    try:
        value = yaml.load(decoded, Loader=StrictYAMLLoader)
    except CapsuleTransitionError:
        raise
    except yaml.YAMLError as error:
        raise CapsuleTransitionError("yaml_parse_failed") from error
    if not isinstance(value, dict):
        raise CapsuleTransitionError("yaml_root_not_mapping")
    _validate_data_tree(value, "yaml")
    return value


def deterministic_yaml(value: Mapping[str, Any]) -> bytes:
    _validate_data_tree(value, "capsule")

    class StableDumper(yaml.SafeDumper):
        def ignore_aliases(self, _data: Any) -> bool:
            return True

    try:
        rendered = yaml.dump(
            dict(value),
            Dumper=StableDumper,
            allow_unicode=True,
            default_flow_style=False,
            explicit_end=False,
            sort_keys=False,
            width=4096,
        )
    except yaml.YAMLError as error:
        raise CapsuleTransitionError("yaml_render_failed") from error
    if not rendered.endswith("\n"):
        rendered += "\n"
    payload = rendered.encode("utf-8")
    strict_yaml_loads(payload)
    return payload


def _validate_data_tree(value: Any, context: str, seen: set[int] | None = None) -> None:
    if seen is None:
        seen = set()
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CapsuleTransitionError(f"{context}_non_finite_number")
        return
    if isinstance(value, (dict, list)):
        identity = id(value)
        if identity in seen:
            raise CapsuleTransitionError(f"{context}_cyclic_value")
        seen.add(identity)
        try:
            if isinstance(value, dict):
                for key, child in value.items():
                    if not isinstance(key, str):
                        raise CapsuleTransitionError(
                            f"{context}_mapping_key_not_string"
                        )
                    _validate_data_tree(child, context, seen)
            else:
                for child in value:
                    _validate_data_tree(child, context, seen)
        finally:
            seen.remove(identity)
        return
    raise CapsuleTransitionError(f"{context}_unsupported_value_type")


def _reject_secret_material(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.casefold() in _SECRET_KEYS:
                raise CapsuleTransitionError(f"secret_field_forbidden:{key}")
            _reject_secret_material(child)
        return
    if isinstance(value, list):
        for child in value:
            _reject_secret_material(child)
        return
    if isinstance(value, str) and value.startswith(_SECRET_PREFIXES):
        raise CapsuleTransitionError("secret_value_prefix_forbidden")


def _require_exact_keys(
    value: Mapping[str, Any],
    required: set[str],
    optional: set[str],
    context: str,
) -> None:
    observed = set(value)
    missing = required - observed
    extra = observed - required - optional
    if missing:
        raise CapsuleTransitionError(f"{context}_missing:{sorted(missing)[0]}")
    if extra:
        raise CapsuleTransitionError(f"{context}_extra:{sorted(extra)[0]}")


def _require_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value or "\n" in value or "\r" in value:
        raise CapsuleTransitionError(f"{context}_invalid")
    return value


def _require_sha256(value: Any, context: str) -> str:
    text = _require_string(value, context)
    if SHA256_RE.fullmatch(text) is None:
        raise CapsuleTransitionError(f"{context}_invalid")
    return text


def _require_identifier(value: Any, context: str) -> str:
    text = _require_string(value, context)
    if IDENTIFIER_RE.fullmatch(text) is None:
        raise CapsuleTransitionError(f"{context}_invalid")
    return text


def _require_string_list(value: Any, context: str) -> list[str]:
    if not isinstance(value, list):
        raise CapsuleTransitionError(f"{context}_not_list")
    result = [_require_string(item, f"{context}_item") for item in value]
    if len(result) != len(set(result)):
        raise CapsuleTransitionError(f"{context}_duplicate")
    return result


def _check_existing_directory(path: Path, context: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise CapsuleTransitionError(f"{context}_lstat_failed") from error
    if stat.S_ISLNK(metadata.st_mode):
        raise CapsuleTransitionError(f"{context}_symlink_forbidden")
    if not stat.S_ISDIR(metadata.st_mode):
        raise CapsuleTransitionError(f"{context}_not_directory")
    return metadata


def _assert_no_symlink_components(path: Path, context: str) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current = current / component
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            return
        except OSError as error:
            raise CapsuleTransitionError(f"{context}_component_lstat_failed") from error
        if stat.S_ISLNK(metadata.st_mode):
            raise CapsuleTransitionError(f"{context}_symlink_component_forbidden")


def read_regular_file(
    path: Path,
    *,
    max_bytes: int,
    context: str,
    require_unique_link: bool = True,
) -> bytes:
    _assert_no_symlink_components(path, context)
    try:
        before = path.lstat()
    except OSError as error:
        raise CapsuleTransitionError(f"{context}_lstat_failed") from error
    if stat.S_ISLNK(before.st_mode):
        raise CapsuleTransitionError(f"{context}_symlink_forbidden")
    if not stat.S_ISREG(before.st_mode):
        raise CapsuleTransitionError(f"{context}_not_regular_file")
    if require_unique_link and before.st_nlink != 1:
        raise CapsuleTransitionError(f"{context}_hardlink_forbidden")
    if before.st_size > max_bytes:
        raise CapsuleTransitionError(f"{context}_too_large")

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise CapsuleTransitionError(f"{context}_not_regular_file")
        if require_unique_link and opened.st_nlink != 1:
            raise CapsuleTransitionError(f"{context}_hardlink_forbidden")
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise CapsuleTransitionError(f"{context}_changed_before_open")
        chunks: list[bytes] = []
        observed_bytes = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, max_bytes + 1 - observed_bytes))
            if not chunk:
                break
            chunks.append(chunk)
            observed_bytes += len(chunk)
            if observed_bytes > max_bytes:
                raise CapsuleTransitionError(f"{context}_too_large")
        after = os.fstat(descriptor)
        if (opened.st_size, opened.st_mtime_ns) != (
            after.st_size,
            after.st_mtime_ns,
        ):
            raise CapsuleTransitionError(f"{context}_changed_during_read")
        payload = b"".join(chunks)
        if len(payload) != after.st_size:
            raise CapsuleTransitionError(f"{context}_short_read")
        return payload
    except CapsuleTransitionError:
        raise
    except OSError as error:
        raise CapsuleTransitionError(f"{context}_read_failed") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def verify_regular_file_identity(
    path: Path,
    *,
    expected_sha256: str,
    expected_bytes: int,
    context: str,
) -> None:
    """Stream a large bound artifact through a race-checked regular-file FD."""

    _assert_no_symlink_components(path, context)
    try:
        before = path.lstat()
    except OSError as error:
        raise CapsuleTransitionError(f"{context}_lstat_failed") from error
    if stat.S_ISLNK(before.st_mode):
        raise CapsuleTransitionError(f"{context}_symlink_forbidden")
    if not stat.S_ISREG(before.st_mode):
        raise CapsuleTransitionError(f"{context}_not_regular_file")
    if before.st_nlink != 1:
        raise CapsuleTransitionError(f"{context}_hardlink_forbidden")
    if before.st_size != expected_bytes:
        raise CapsuleTransitionError(f"{context}_bytes_mismatch")

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise CapsuleTransitionError(f"{context}_not_regular_file")
        if opened.st_nlink != 1:
            raise CapsuleTransitionError(f"{context}_hardlink_forbidden")
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise CapsuleTransitionError(f"{context}_changed_before_open")
        digest = hashlib.sha256()
        observed_bytes = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            observed_bytes += len(chunk)
            if observed_bytes > expected_bytes:
                raise CapsuleTransitionError(f"{context}_grew_during_read")
        after = os.fstat(descriptor)
        if (opened.st_size, opened.st_mtime_ns) != (
            after.st_size,
            after.st_mtime_ns,
        ):
            raise CapsuleTransitionError(f"{context}_changed_during_read")
        if observed_bytes != expected_bytes:
            raise CapsuleTransitionError(f"{context}_bytes_mismatch")
        if digest.hexdigest() != expected_sha256:
            raise CapsuleTransitionError(f"{context}_sha256_mismatch")
    except CapsuleTransitionError:
        raise
    except OSError as error:
        raise CapsuleTransitionError(f"{context}_read_failed") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def fsync_directory(path: Path, context: str) -> None:
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
            raise CapsuleTransitionError(f"{context}_not_directory")
        os.fsync(descriptor)
    except CapsuleTransitionError:
        raise
    except OSError as error:
        raise CapsuleTransitionError(f"{context}_fsync_failed") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _ensure_directory(path: Path, context: str) -> None:
    if path.exists():
        _check_existing_directory(path, context)
        return
    _check_existing_directory(path.parent, f"{context}_parent")
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        _check_existing_directory(path, context)
        return
    except OSError as error:
        raise CapsuleTransitionError(f"{context}_create_failed") from error
    fsync_directory(path.parent, f"{context}_parent")


def _write_all(descriptor: int, payload: bytes, context: str) -> None:
    offset = 0
    while offset < len(payload):
        try:
            written = os.write(descriptor, payload[offset:])
        except OSError as error:
            raise CapsuleTransitionError(f"{context}_write_failed") from error
        if written <= 0:
            raise CapsuleTransitionError(f"{context}_write_failed")
        offset += written


def write_exclusive_or_verify(path: Path, payload: bytes, context: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags, 0o600)
        _write_all(descriptor, payload, context)
        os.fsync(descriptor)
    except FileExistsError:
        observed = read_regular_file(
            path,
            max_bytes=max(MAX_CAPSULE_BYTES, len(payload)),
            context=context,
        )
        if observed != payload:
            raise CapsuleTransitionError(f"{context}_existing_mismatch")
        return
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise CapsuleTransitionError(f"{context}_symlink_forbidden") from error
        raise CapsuleTransitionError(f"{context}_create_failed") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
    fsync_directory(path.parent, f"{context}_parent")
    observed = read_regular_file(
        path,
        max_bytes=max(MAX_CAPSULE_BYTES, len(payload)),
        context=context,
    )
    if observed != payload:
        raise CapsuleTransitionError(f"{context}_readback_mismatch")


class _AdjacentLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.descriptor: int | None = None

    def __enter__(self) -> "_AdjacentLock":
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            self.descriptor = os.open(self.path, flags, 0o600)
            metadata = os.fstat(self.descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise CapsuleTransitionError("lock_not_regular_file")
            if metadata.st_nlink != 1:
                raise CapsuleTransitionError("lock_hardlink_forbidden")
            fcntl.flock(self.descriptor, fcntl.LOCK_EX)
        except CapsuleTransitionError:
            self.__exit__(None, None, None)
            raise
        except OSError as error:
            self.__exit__(None, None, None)
            raise CapsuleTransitionError("lock_open_failed") from error
        return self

    def __exit__(self, *_args: Any) -> None:
        if self.descriptor is None:
            return
        try:
            fcntl.flock(self.descriptor, fcntl.LOCK_UN)
        finally:
            os.close(self.descriptor)
            self.descriptor = None


def _normalize_local_path(value: str, repository_root: Path, context: str) -> Path:
    if "\\" in value:
        raise CapsuleTransitionError(f"{context}_backslash_forbidden")
    candidate = Path(value)
    if candidate.is_absolute() or not candidate.parts:
        raise CapsuleTransitionError(f"{context}_not_relative")
    if any(part in {"", ".", ".."} for part in candidate.parts):
        raise CapsuleTransitionError(f"{context}_traversal_forbidden")
    return repository_root / candidate


def _validate_artifact(
    value: Any,
    context: str,
    repository_root: Path,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CapsuleTransitionError(f"{context}_not_mapping")
    _require_exact_keys(
        value,
        _ARTIFACT_REQUIRED_KEYS,
        _ARTIFACT_OPTIONAL_KEYS,
        context,
    )
    _require_identifier(value["role"], f"{context}_role")
    _require_string(value["locator"], f"{context}_locator")
    expected_sha256 = _require_sha256(value["sha256"], f"{context}_sha256")
    expected_bytes = value["bytes"]
    if (
        not isinstance(expected_bytes, int)
        or isinstance(expected_bytes, bool)
        or expected_bytes < 0
        or expected_bytes > MAX_BOUND_ARTIFACT_BYTES
    ):
        raise CapsuleTransitionError(f"{context}_bytes_invalid")
    _require_identifier(value["custody"], f"{context}_custody")
    if "local_path" not in value:
        return copy.deepcopy(value)

    relative = _require_string(value["local_path"], f"{context}_local_path")
    path = _normalize_local_path(relative, repository_root, f"{context}_local_path")
    verify_regular_file_identity(
        path,
        expected_sha256=expected_sha256,
        expected_bytes=expected_bytes,
        context=f"{context}_local_file",
    )
    return copy.deepcopy(value)


def _validate_artifact_list(
    value: Any,
    context: str,
    repository_root: Path,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise CapsuleTransitionError(f"{context}_not_nonempty_list")
    records = [
        _validate_artifact(item, f"{context}_{index}", repository_root)
        for index, item in enumerate(value)
    ]
    roles = [record["role"] for record in records]
    if len(roles) != len(set(roles)):
        raise CapsuleTransitionError(f"{context}_duplicate_role")
    return records


def _validate_commit(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CapsuleTransitionError(f"{context}_not_mapping")
    _require_exact_keys(value, {"repository", "commit_sha", "scope"}, set(), context)
    _require_string(value["repository"], f"{context}_repository")
    commit_sha = _require_string(value["commit_sha"], f"{context}_commit_sha")
    if COMMIT_RE.fullmatch(commit_sha) is None:
        raise CapsuleTransitionError(f"{context}_commit_sha_invalid")
    scope = _require_string_list(value["scope"], f"{context}_scope")
    if not scope:
        raise CapsuleTransitionError(f"{context}_scope_empty")
    return copy.deepcopy(value)


def _validate_lease(
    value: Any,
    repository_root: Path,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CapsuleTransitionError("lease_not_mapping")
    _require_exact_keys(
        value,
        {"lease_id", "artifact", "resource_slice", "expires_at_utc"},
        set(),
        "lease",
    )
    _require_identifier(value["lease_id"], "lease_id")
    _validate_artifact(value["artifact"], "lease_artifact", repository_root)
    resource_slice = value["resource_slice"]
    if not isinstance(resource_slice, dict) or not resource_slice:
        raise CapsuleTransitionError("lease_resource_slice_not_nonempty_mapping")
    _validate_data_tree(resource_slice, "lease_resource_slice")
    expires = value["expires_at_utc"]
    if expires is not None and (
        not isinstance(expires, str) or UTC_RE.fullmatch(expires) is None
    ):
        raise CapsuleTransitionError("lease_expires_at_utc_invalid")
    return copy.deepcopy(value)


def _validate_transitions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise CapsuleTransitionError("transitions_not_nonempty_list")
    result: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    required = {
        "subject_id",
        "subject_kind",
        "from",
        "to",
        "evidence_sha256",
    }
    for index, item in enumerate(value):
        context = f"transition_{index}"
        if not isinstance(item, dict):
            raise CapsuleTransitionError(f"{context}_not_mapping")
        _require_exact_keys(item, required, {"reason"}, context)
        subject_id = _require_identifier(item["subject_id"], f"{context}_subject_id")
        subject_kind = _require_identifier(
            item["subject_kind"], f"{context}_subject_kind"
        )
        before = _require_string(item["from"], f"{context}_from")
        after = _require_string(item["to"], f"{context}_to")
        if before == after:
            raise CapsuleTransitionError(f"{context}_no_state_change")
        _require_sha256(item["evidence_sha256"], f"{context}_evidence_sha256")
        if "reason" in item:
            _require_string(item["reason"], f"{context}_reason")
        identity = (subject_kind, subject_id)
        if identity in identities:
            raise CapsuleTransitionError("transitions_duplicate_subject")
        identities.add(identity)
        result.append(copy.deepcopy(item))
    return result


def _validate_rollback(
    value: Any,
    repository_root: Path,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CapsuleTransitionError("rollback_not_mapping")
    _require_exact_keys(
        value,
        {
            "disposition",
            "rollback_base",
            "invalidated_sha256",
            "preserved_sha256",
        },
        set(),
        "rollback",
    )
    _require_string(value["disposition"], "rollback_disposition")
    if value["rollback_base"] is not None:
        _validate_artifact(
            value["rollback_base"], "rollback_base", repository_root
        )
    for key in ("invalidated_sha256", "preserved_sha256"):
        values = _require_string_list(value[key], f"rollback_{key}")
        for index, digest in enumerate(values):
            _require_sha256(digest, f"rollback_{key}_{index}")
    return copy.deepcopy(value)


def validate_bindings(
    value: Any,
    repository_root: Path,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CapsuleTransitionError("bindings_not_mapping")
    _require_exact_keys(
        value,
        _REQUIRED_BINDING_KEYS,
        {"scoped_push_receipt"},
        "bindings",
    )
    _validate_artifact(value["frontier"], "frontier", repository_root)
    _validate_artifact_list(
        value["preregistrations"], "preregistrations", repository_root
    )
    _validate_artifact(
        value["maximal_selector"], "maximal_selector", repository_root
    )
    _validate_lease(value["lease"], repository_root)
    _validate_artifact_list(value["inputs"], "inputs", repository_root)
    _validate_artifact_list(
        value["raw_reports"], "raw_reports", repository_root
    )
    _validate_artifact_list(
        value["sanitized_reports"], "sanitized_reports", repository_root
    )
    _validate_transitions(value["transitions"])
    _validate_rollback(value["rollback"], repository_root)
    _validate_commit(value["source_commit"], "source_commit")
    _validate_commit(value["evidence_commit"], "evidence_commit")
    if "scoped_push_receipt" in value and value["scoped_push_receipt"] is not None:
        _validate_artifact(
            value["scoped_push_receipt"],
            "scoped_push_receipt",
            repository_root,
        )
    _reject_secret_material(value)
    return copy.deepcopy(value)


def _validate_spec_for_profile(
    value: dict[str, Any],
    repository_root: Path,
    profile: _MigrationProfile,
) -> dict[str, Any]:
    _require_exact_keys(value, _TOP_LEVEL_SPEC_KEYS, set(), "spec")
    if value["schema_version"] != profile.spec_schema:
        raise CapsuleTransitionError("spec_schema_version_mismatch")
    _require_identifier(value["transaction_id"], "transaction_id")
    if value["expected_parent_sha256"] != profile.expected_parent_sha256:
        raise CapsuleTransitionError("expected_parent_sha256_mismatch")
    cutoff = value["evidence_cutoff_utc"]
    if not isinstance(cutoff, str) or UTC_RE.fullmatch(cutoff) is None:
        raise CapsuleTransitionError("evidence_cutoff_utc_invalid")
    mutation = value["mutation"]
    if not isinstance(mutation, dict):
        raise CapsuleTransitionError("mutation_not_mapping")
    _require_exact_keys(mutation, {"operations"}, set(), "mutation")
    _validate_operations(mutation["operations"])
    validate_bindings(value["bindings"], repository_root)
    if profile is _V5_TO_V6:
        _validate_v6_operation_cross_bindings(value)
        if value["bindings"]["source_commit"]["commit_sha"] == "0" * 40:
            raise CapsuleTransitionError("v6_source_commit_placeholder_unresolved")
    _reject_secret_material(value)
    return copy.deepcopy(value)


def _validate_v6_operation_cross_bindings(spec: Mapping[str, Any]) -> None:
    operations = spec["mutation"]["operations"]
    campaign_operations = [
        operation
        for operation in operations
        if operation["path"] == ["last_verified_campaign_state"]
    ]
    if len(campaign_operations) != 1:
        raise CapsuleTransitionError(
            "v6_campaign_state_replacement_count_invalid"
        )
    operation = campaign_operations[0]
    if operation["op"] != "replace":
        raise CapsuleTransitionError("v6_campaign_state_operation_not_replace")
    campaign_state = operation["value"]
    if not isinstance(campaign_state, dict):
        raise CapsuleTransitionError("v6_campaign_state_value_not_mapping")

    bindings = spec["bindings"]
    expected = {
        "source_commit": bindings["source_commit"]["commit_sha"],
        "evidence_commit": bindings["evidence_commit"]["commit_sha"],
        "frontier_root_sha256": bindings["frontier"]["sha256"],
        "parent_capsule_sha256": spec["expected_parent_sha256"],
    }
    for field, expected_value in expected.items():
        if campaign_state.get(field) != expected_value:
            raise CapsuleTransitionError(
                f"v6_campaign_state_{field}_binding_mismatch"
            )


def validate_spec(
    value: dict[str, Any],
    repository_root: Path,
) -> dict[str, Any]:
    """Validate the original reviewed v4 -> v5 transition specification."""

    return _validate_spec_for_profile(value, repository_root, _V4_TO_V5)


def validate_v6_spec(
    value: dict[str, Any],
    repository_root: Path,
) -> dict[str, Any]:
    """Validate the reviewed v5 -> v6 transition specification."""

    return _validate_spec_for_profile(value, repository_root, _V5_TO_V6)


def _validate_operations(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise CapsuleTransitionError("operations_not_nonempty_list")
    result: list[dict[str, Any]] = []
    paths: list[tuple[str, ...]] = []
    for index, item in enumerate(value):
        context = f"operation_{index}"
        if not isinstance(item, dict):
            raise CapsuleTransitionError(f"{context}_not_mapping")
        _require_exact_keys(
            item,
            {"op", "path", "expected_old_sha256", "value"},
            set(),
            context,
        )
        if item["op"] not in {"add", "replace"}:
            raise CapsuleTransitionError(f"{context}_op_invalid")
        path = item["path"]
        if not isinstance(path, list) or not path:
            raise CapsuleTransitionError(f"{context}_path_invalid")
        normalized = tuple(
            _require_string(component, f"{context}_path_component")
            for component in path
        )
        if any(component in {".", ".."} for component in normalized):
            raise CapsuleTransitionError(f"{context}_path_component_invalid")
        expected = item["expected_old_sha256"]
        if item["op"] == "add" and expected is not None:
            raise CapsuleTransitionError(f"{context}_add_expected_old_not_null")
        if item["op"] == "replace":
            _require_sha256(expected, f"{context}_expected_old_sha256")
        _validate_data_tree(item["value"], f"{context}_value")
        paths.append(normalized)
        result.append(copy.deepcopy(item))
    for index, path in enumerate(paths):
        for other in paths[index + 1 :]:
            shared = min(len(path), len(other))
            if path[:shared] == other[:shared]:
                raise CapsuleTransitionError("operation_paths_overlap")
    return result


def _lookup_parent(
    capsule: dict[str, Any],
    path: Sequence[str],
) -> tuple[dict[str, Any], str]:
    current: Any = capsule
    for component in path[:-1]:
        if not isinstance(current, dict) or component not in current:
            raise CapsuleTransitionError("operation_parent_path_absent")
        current = current[component]
    if not isinstance(current, dict):
        raise CapsuleTransitionError("operation_parent_path_not_mapping")
    return current, path[-1]


def _assert_no_mapping_key_deletions(
    parent: Any,
    child: Any,
    path: tuple[str, ...] = (),
) -> None:
    if not isinstance(parent, dict):
        return
    if not isinstance(child, dict):
        joined = "/".join(path)
        raise CapsuleTransitionError(f"mapping_replaced_by_non_mapping:{joined}")
    missing = set(parent) - set(child)
    if missing:
        joined = "/".join((*path, sorted(missing)[0]))
        raise CapsuleTransitionError(f"mapping_key_deletion_forbidden:{joined}")
    for key, value in parent.items():
        _assert_no_mapping_key_deletions(value, child[key], (*path, key))


def _derive_child_capsule_for_profile(
    parent: dict[str, Any],
    spec: dict[str, Any],
    profile: _MigrationProfile,
) -> dict[str, Any]:
    if parent.get("schema_version") != profile.parent_schema:
        raise CapsuleTransitionError("parent_schema_version_mismatch")
    child = copy.deepcopy(parent)
    operations = sorted(
        spec["mutation"]["operations"],
        key=lambda operation: tuple(operation["path"]),
    )
    for operation in operations:
        container, key = _lookup_parent(child, operation["path"])
        if operation["op"] == "add":
            if key in container:
                raise CapsuleTransitionError("operation_add_target_exists")
        else:
            if key not in container:
                raise CapsuleTransitionError("operation_replace_target_absent")
            observed = value_sha256(container[key])
            if observed != operation["expected_old_sha256"]:
                raise CapsuleTransitionError("operation_old_value_sha256_mismatch")
        container[key] = copy.deepcopy(operation["value"])

    _assert_no_mapping_key_deletions(parent, child)
    if child.get("schema_version") != profile.child_schema:
        raise CapsuleTransitionError(profile.child_schema_error)
    if child.get("evidence_cutoff_utc") != spec["evidence_cutoff_utc"]:
        raise CapsuleTransitionError("child_evidence_cutoff_mismatch")
    parent_cutoff = parent.get("evidence_cutoff_utc")
    if not isinstance(parent_cutoff, str) or UTC_RE.fullmatch(parent_cutoff) is None:
        raise CapsuleTransitionError("parent_evidence_cutoff_invalid")
    if spec["evidence_cutoff_utc"] <= parent_cutoff:
        raise CapsuleTransitionError("child_evidence_cutoff_not_advanced")
    _validate_capsule_invariants(parent, child)
    return child


def derive_child_capsule(
    parent: dict[str, Any],
    spec: dict[str, Any],
) -> dict[str, Any]:
    """Derive the original reviewed v4 -> v5 capsule child."""

    return _derive_child_capsule_for_profile(parent, spec, _V4_TO_V5)


def derive_v6_child_capsule(
    parent: dict[str, Any],
    spec: dict[str, Any],
) -> dict[str, Any]:
    """Derive the reviewed v5 -> v6 capsule child."""

    return _derive_child_capsule_for_profile(parent, spec, _V5_TO_V6)


def _nested(value: Mapping[str, Any], *path: str) -> Any:
    current: Any = value
    for component in path:
        if not isinstance(current, dict) or component not in current:
            raise CapsuleTransitionError(f"capsule_required_path_absent:{'/'.join(path)}")
        current = current[component]
    return current


def _validate_capsule_invariants(
    parent: dict[str, Any],
    child: dict[str, Any],
) -> None:
    if child.get("state_kind") != "last_verified_not_live_revalidated":
        raise CapsuleTransitionError("child_state_kind_invalid")
    if child.get("generated_from") != parent.get("generated_from"):
        raise CapsuleTransitionError("governing_documents_changed")
    if child.get("governing_objective") != parent.get("governing_objective"):
        raise CapsuleTransitionError("governing_objective_changed")
    if _nested(child, "governing_objective", "model_target") != "Gemma_4_E4B_only":
        raise CapsuleTransitionError("model_target_changed")
    semantics = _nested(child, "document_semantics")
    required_false = {
        "records_execution_authority",
        "grants_execution_authority",
        "grants_promotion_authority",
        "stored_document_or_capsule_is_a_lease",
        "executable_command_present",
    }
    for key in required_false:
        if not isinstance(semantics, dict) or semantics.get(key) is not False:
            raise CapsuleTransitionError(f"capsule_authority_invariant_failed:{key}")


def _relative_locator(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError as error:
        raise CapsuleTransitionError("transaction_path_not_adjacent") from error


def _build_receipt(
    *,
    profile: _MigrationProfile,
    spec: dict[str, Any],
    spec_sha256: str,
    spec_bytes: int,
    canonical_path: Path,
    archive_path: Path,
    child_snapshot_path: Path,
    receipt_path: Path,
    completion_path: Path,
    lock_path: Path,
    parent_bytes: bytes,
    child_bytes: bytes,
) -> dict[str, Any]:
    base = canonical_path.parent
    return {
        "schema_version": profile.receipt_schema,
        "transaction_id": spec["transaction_id"],
        "evidence_cutoff_utc": spec["evidence_cutoff_utc"],
        "transition_spec": {
            "sha256": spec_sha256,
            "bytes": spec_bytes,
            "schema_version": profile.spec_schema,
        },
        "capsule": {
            "canonical_locator": canonical_path.name,
            "parent": {
                "schema_version": profile.parent_schema,
                "sha256": profile.expected_parent_sha256,
                "bytes": len(parent_bytes),
                "archive_locator": _relative_locator(archive_path, base),
            },
            "child": {
                "schema_version": profile.child_schema,
                "sha256": sha256_bytes(child_bytes),
                "bytes": len(child_bytes),
                "snapshot_locator": _relative_locator(child_snapshot_path, base),
            },
        },
        "mutation": {
            "operation_count": len(spec["mutation"]["operations"]),
            "operations_sha256": value_sha256(spec["mutation"]["operations"]),
            "mapping_key_deletion_allowed": False,
        },
        "bindings": copy.deepcopy(spec["bindings"]),
        "atomicity": {
            "stable_lock_locator": lock_path.name,
            "receipt_locator": _relative_locator(receipt_path, base),
            "completion_locator": _relative_locator(completion_path, base),
            "archive_before_replace": True,
            "receipt_before_replace": True,
            "canonical_replace": "same_directory_os_replace_then_directory_fsync",
            "immediate_child_rehash_required": True,
            "completion_creation": "O_CREAT_O_EXCL_then_fsync",
            "recovery": "parent_resume_or_exact_child_finalize_only",
        },
    }


def _completion_payload(
    *,
    profile: _MigrationProfile,
    spec: dict[str, Any],
    spec_sha256: str,
    receipt_sha256: str,
    receipt_bytes: int,
    child_sha256: str,
) -> bytes:
    value = {
        "schema_version": profile.completion_schema,
        "status": "complete",
        "transaction_id": spec["transaction_id"],
        "evidence_cutoff_utc": spec["evidence_cutoff_utc"],
        "transition_spec_sha256": spec_sha256,
        "parent_capsule_sha256": profile.expected_parent_sha256,
        "child_capsule_sha256": child_sha256,
        "receipt_sha256": receipt_sha256,
        "receipt_bytes": receipt_bytes,
    }
    return canonical_json(value) + b"\n"


def _atomic_replace_canonical(
    canonical_path: Path,
    temporary_path: Path,
    child_bytes: bytes,
) -> None:
    write_exclusive_or_verify(temporary_path, child_bytes, "canonical_stage")
    try:
        os.replace(temporary_path, canonical_path)
    except OSError as error:
        raise CapsuleTransitionError("canonical_atomic_replace_failed") from error
    fsync_directory(canonical_path.parent, "canonical_parent")
    observed = read_regular_file(
        canonical_path,
        max_bytes=MAX_CAPSULE_BYTES,
        context="canonical_child",
    )
    if observed != child_bytes:
        raise CapsuleTransitionError("canonical_immediate_readback_mismatch")
    strict_yaml_loads(observed)


def _fault(
    fault_injector: Callable[[str], None] | None,
    phase: str,
) -> None:
    if fault_injector is not None:
        fault_injector(phase)


def _advance_capsule_for_profile(
    *,
    profile: _MigrationProfile,
    canonical_path: Path,
    transition_spec_path: Path,
    repository_root: Path,
    fault_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Perform or recover one exact migration profile."""

    canonical_path = canonical_path.absolute()
    transition_spec_path = transition_spec_path.absolute()
    repository_root = repository_root.absolute()
    _check_existing_directory(repository_root, "repository_root")
    _check_existing_directory(canonical_path.parent, "canonical_parent")

    initial_spec_bytes = read_regular_file(
        transition_spec_path,
        max_bytes=MAX_SPEC_BYTES,
        context="transition_spec",
    )
    spec = _validate_spec_for_profile(
        strict_json_loads(initial_spec_bytes), repository_root, profile
    )
    spec_sha256 = sha256_bytes(initial_spec_bytes)

    lock_path = canonical_path.with_name(f"{canonical_path.name}.lock")
    archive_root = canonical_path.with_name(f"{canonical_path.name}.archive")
    transaction_root = canonical_path.with_name(f".{canonical_path.name}.transactions")
    transaction_dir = transaction_root / spec_sha256
    archive_path = archive_root / f"{profile.expected_parent_sha256}.yaml"
    child_snapshot_path = transaction_dir / "child_capsule.yaml"
    receipt_path = transaction_dir / "transition_receipt.json"
    completion_path = transaction_dir / "COMPLETE.json"
    temporary_path = canonical_path.with_name(
        f".{canonical_path.name}.{spec_sha256}.replace"
    )

    with _AdjacentLock(lock_path):
        locked_spec_bytes = read_regular_file(
            transition_spec_path,
            max_bytes=MAX_SPEC_BYTES,
            context="transition_spec_locked",
        )
        if locked_spec_bytes != initial_spec_bytes:
            raise CapsuleTransitionError("transition_spec_changed_before_lock")
        # Reverify every local binding under the stable capsule lock.  The
        # receipt must never inherit a pre-lock observation of mutable bytes.
        spec = _validate_spec_for_profile(
            strict_json_loads(locked_spec_bytes), repository_root, profile
        )

        current_bytes = read_regular_file(
            canonical_path,
            max_bytes=MAX_CAPSULE_BYTES,
            context="canonical_capsule",
        )
        current_sha256 = sha256_bytes(current_bytes)

        if current_sha256 == profile.expected_parent_sha256:
            parent_bytes = current_bytes
        else:
            if not archive_path.exists():
                raise CapsuleTransitionError("canonical_compare_and_swap_conflict")
            parent_bytes = read_regular_file(
                archive_path,
                max_bytes=MAX_CAPSULE_BYTES,
                context="parent_archive_recovery",
            )
            if sha256_bytes(parent_bytes) != profile.expected_parent_sha256:
                raise CapsuleTransitionError("parent_archive_sha256_mismatch")

        parent = strict_yaml_loads(parent_bytes)
        child = _derive_child_capsule_for_profile(parent, spec, profile)
        child_bytes = deterministic_yaml(child)
        child_sha256 = sha256_bytes(child_bytes)

        if current_sha256 not in {profile.expected_parent_sha256, child_sha256}:
            raise CapsuleTransitionError("canonical_compare_and_swap_conflict")

        _ensure_directory(archive_root, "archive_root")
        _ensure_directory(transaction_root, "transaction_root")
        _ensure_directory(transaction_dir, "transaction_dir")
        write_exclusive_or_verify(archive_path, parent_bytes, "parent_archive")
        _fault(fault_injector, "after_archive")
        write_exclusive_or_verify(
            child_snapshot_path,
            child_bytes,
            "child_snapshot",
        )

        receipt = _build_receipt(
            profile=profile,
            spec=spec,
            spec_sha256=spec_sha256,
            spec_bytes=len(initial_spec_bytes),
            canonical_path=canonical_path,
            archive_path=archive_path,
            child_snapshot_path=child_snapshot_path,
            receipt_path=receipt_path,
            completion_path=completion_path,
            lock_path=lock_path,
            parent_bytes=parent_bytes,
            child_bytes=child_bytes,
        )
        receipt_bytes = canonical_json(receipt) + b"\n"
        write_exclusive_or_verify(receipt_path, receipt_bytes, "transition_receipt")
        _fault(fault_injector, "after_receipt")

        if current_sha256 == profile.expected_parent_sha256:
            _atomic_replace_canonical(canonical_path, temporary_path, child_bytes)
        else:
            if current_bytes != child_bytes:
                raise CapsuleTransitionError("canonical_child_bytes_mismatch")
            strict_yaml_loads(current_bytes)
        _fault(fault_injector, "after_replace")

        final_bytes = read_regular_file(
            canonical_path,
            max_bytes=MAX_CAPSULE_BYTES,
            context="canonical_final",
        )
        if sha256_bytes(final_bytes) != child_sha256 or final_bytes != child_bytes:
            raise CapsuleTransitionError("canonical_final_rehash_mismatch")

        receipt_sha256 = sha256_bytes(receipt_bytes)
        completion_bytes = _completion_payload(
            profile=profile,
            spec=spec,
            spec_sha256=spec_sha256,
            receipt_sha256=receipt_sha256,
            receipt_bytes=len(receipt_bytes),
            child_sha256=child_sha256,
        )
        write_exclusive_or_verify(completion_path, completion_bytes, "completion")
        _fault(fault_injector, "after_completion")

        return {
            "status": (
                "already_complete" if current_sha256 == child_sha256 else "complete"
            ),
            "transaction_id": spec["transaction_id"],
            "transition_spec_sha256": spec_sha256,
            "parent_capsule_sha256": profile.expected_parent_sha256,
            "child_capsule_sha256": child_sha256,
            "receipt_sha256": receipt_sha256,
            "completion_sha256": sha256_bytes(completion_bytes),
            "archive_path": str(archive_path),
            "receipt_path": str(receipt_path),
            "completion_path": str(completion_path),
        }


def advance_capsule(
    *,
    canonical_path: Path,
    transition_spec_path: Path,
    repository_root: Path,
    fault_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Perform or idempotently recover the reviewed v4 -> v5 CAS."""

    return _advance_capsule_for_profile(
        profile=_V4_TO_V5,
        canonical_path=canonical_path,
        transition_spec_path=transition_spec_path,
        repository_root=repository_root,
        fault_injector=fault_injector,
    )


def advance_capsule_v5_to_v6(
    *,
    canonical_path: Path,
    transition_spec_path: Path,
    repository_root: Path,
    fault_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Perform or idempotently recover the reviewed v5 -> v6 CAS."""

    return _advance_capsule_for_profile(
        profile=_V5_TO_V6,
        canonical_path=canonical_path,
        transition_spec_path=transition_spec_path,
        repository_root=repository_root,
        fault_injector=fault_injector,
    )


__all__ = [
    "COMPLETION_SCHEMA",
    "EXPECTED_V4_SHA256",
    "EXPECTED_V5_SHA256",
    "RECEIPT_SCHEMA",
    "SPEC_SCHEMA",
    "V4_SCHEMA",
    "V5_SCHEMA",
    "V6_COMPLETION_SCHEMA",
    "V6_RECEIPT_SCHEMA",
    "V6_SCHEMA",
    "V6_SPEC_SCHEMA",
    "CapsuleTransitionError",
    "advance_capsule",
    "advance_capsule_v5_to_v6",
    "canonical_json",
    "derive_child_capsule",
    "derive_v6_child_capsule",
    "deterministic_yaml",
    "sha256_bytes",
    "strict_json_loads",
    "strict_yaml_loads",
    "validate_spec",
    "validate_v6_spec",
    "value_sha256",
    "verify_regular_file_identity",
]

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
EXPECTED_V6_ADRENO_PASS_PARENT_SHA256 = (
    "838eeb8b847c9b00e6600a3c9b5621086281f8eadeee843044da1902bf2dec2a"
)
EXPECTED_V6_CUR0S_EXACT_PARENT_SHA256 = (
    "37555d7938a32cd22053d2741cb972e399030a2b6e559a19df8677406155136a"
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
    transition_kind: str
    expected_parent_sha256: str
    parent_schema: str
    child_schema: str
    spec_schema: str
    receipt_schema: str
    completion_schema: str
    child_schema_error: str
    require_v6_campaign_cross_bindings: bool


_V4_TO_V5 = _MigrationProfile(
    transition_kind="v4_to_v5",
    expected_parent_sha256=EXPECTED_V4_SHA256,
    parent_schema=V4_SCHEMA,
    child_schema=V5_SCHEMA,
    spec_schema=SPEC_SCHEMA,
    receipt_schema=RECEIPT_SCHEMA,
    completion_schema=COMPLETION_SCHEMA,
    child_schema_error="child_schema_version_not_v5",
    require_v6_campaign_cross_bindings=False,
)
_V5_TO_V6 = _MigrationProfile(
    transition_kind="v5_to_v6",
    expected_parent_sha256=EXPECTED_V5_SHA256,
    parent_schema=V5_SCHEMA,
    child_schema=V6_SCHEMA,
    spec_schema=V6_SPEC_SCHEMA,
    receipt_schema=V6_RECEIPT_SCHEMA,
    completion_schema=V6_COMPLETION_SCHEMA,
    child_schema_error="child_schema_version_not_v6",
    require_v6_campaign_cross_bindings=True,
)
_V6_ADRENO_PASS = _MigrationProfile(
    transition_kind="v6_adreno_pass",
    expected_parent_sha256=EXPECTED_V6_ADRENO_PASS_PARENT_SHA256,
    parent_schema=V6_SCHEMA,
    child_schema=V6_SCHEMA,
    spec_schema=V6_SPEC_SCHEMA,
    receipt_schema=V6_RECEIPT_SCHEMA,
    completion_schema=V6_COMPLETION_SCHEMA,
    child_schema_error="child_schema_version_not_v6",
    require_v6_campaign_cross_bindings=True,
)
_V6_CUR0S_EXACT = _MigrationProfile(
    transition_kind="v6_cur0s_exact",
    expected_parent_sha256=EXPECTED_V6_CUR0S_EXACT_PARENT_SHA256,
    parent_schema=V6_SCHEMA,
    child_schema=V6_SCHEMA,
    spec_schema=V6_SPEC_SCHEMA,
    receipt_schema=V6_RECEIPT_SCHEMA,
    completion_schema=V6_COMPLETION_SCHEMA,
    child_schema_error="child_schema_version_not_v6",
    require_v6_campaign_cross_bindings=True,
)

_V6_CUR0S_EXACT_OPERATION_PATHS = frozenset(
    {
        ("evidence_cutoff_utc",),
        ("corpus_curriculum", "curriculum_gates", "CUR-0S"),
        ("measured_claims", "CUR_0S_CURRENT"),
        ("frontier_execution_policy", "active_candidate"),
        ("frontier_execution_policy", "last_disposition"),
        ("current_design_decision",),
        ("next_action",),
        ("last_verified_campaign_state",),
    }
)
_CUR0S_EXACT_DISCRIMINATOR_SOURCE_COMMIT = (
    "b10ecdd36acd877c62cefba394e44e093fb0abd5"
)
_CUR0S_EXACT_RECEIPT_SHA256 = (
    "839b20dc4c2ec1d426005a0e54f1d28f675589053887b5a142aeeb053410cc15"
)
_CUR0S_EXACT_EVIDENCE_CUTOFF_UTC = "2026-07-11T21:17:47Z"
_CUR0S_EXACT_DISPOSITION = (
    "CUR0S_physical_and_exact_identity_passed_scope_"
    "successor_commercial_source_root_selected"
)
_CUR0S_EXACT_FRONTIER_SHA256 = (
    "d118000d8fd457962f2332f2597bb25f6c6e33ee61010f5cd1459ab9768235fc"
)
_CUR0S_EXACT_EVIDENCE_COMMIT = "87cc6a1a5e6092440009d43b00d14b8e398d5b35"
_CUR0S_EXACT_PREREGISTRATION_ARTIFACTS = {
    "cur0s_exact_attempt_1_preregistration": {
        "sha256": "4bb0ab5e64c7c5dfc1c2aef5b3d3292d327ea1a770f235dedbd60c12f11509b0",
        "bytes": 5382,
        "local_path": (
            "runtime/reports/apex_frontier/"
            "20260711T210019Z_cur0s_static_identity_v1_preregistration.json"
        ),
    },
    "cur0s_exact_attempt_2_preregistration": {
        "sha256": "71718c40401b803b6e2e20f49aef249b3b2a149ee6f4ab6fb944ac640d1f58bb",
        "bytes": 5417,
        "local_path": (
            "runtime/reports/apex_frontier/"
            "20260711T210523Z_cur0s_static_identity_v1_preregistration.json"
        ),
    },
    "cur0s_exact_attempt_3_preregistration": {
        "sha256": "c8c0c411e023129a6c61294592410a665756e3cc941383fb707d0b7ad296150f",
        "bytes": 5417,
        "local_path": (
            "runtime/reports/apex_frontier/"
            "20260711T210854Z_cur0s_static_identity_v1_preregistration.json"
        ),
    },
    "cur0s_exact_attempt_4_preregistration": {
        "sha256": "4c9156e8db2147899a7a7d2cc9f0161e6d32fefa9da8de486a1c1a029ab98c1e",
        "bytes": 5474,
        "local_path": (
            "runtime/reports/apex_frontier/"
            "20260711T211344Z_cur0s_static_identity_v1_preregistration.json"
        ),
    },
}
_CUR0S_EXACT_SANITIZED_ARTIFACTS = {
    "cur0s_exact_typed_stop_receipt": {
        "sha256": "db20b86aadf7623fef5326b86b7bca851f27b8ef0dccec71c015fddb92480dbd",
        "bytes": 6898,
        "local_path": (
            "runtime/reports/apex_frontier/"
            "20260711T210854Z_cur0s_static_identity_v1_phone_receipt/receipt.json"
        ),
    },
    "cur0s_exact_typed_stop_completion": {
        "sha256": "9cde314ea2f5e610cbf378063622e1168c73bb40c75e29eaab71840ce4870a81",
        "bytes": 518,
        "local_path": (
            "runtime/reports/apex_frontier/"
            "20260711T210854Z_cur0s_static_identity_v1_phone_receipt/COMPLETE.json"
        ),
    },
    "cur0s_exact_typed_stop_custody": {
        "sha256": "e0806c78fe36b3c390b343d1015701e5355a134f70736ca4037cab65d0f3d01d",
        "bytes": 1644,
        "local_path": (
            "runtime/reports/apex_frontier/"
            "20260711T210854Z_cur0s_static_identity_v1_phone_receipt/custody.json"
        ),
    },
    "cur0s_exact_success_receipt": {
        "sha256": _CUR0S_EXACT_RECEIPT_SHA256,
        "bytes": 12773,
        "local_path": (
            "runtime/reports/apex_frontier/"
            "20260711T211344Z_cur0s_static_identity_v1_phone_receipt/receipt.json"
        ),
    },
    "cur0s_exact_success_completion": {
        "sha256": "65235bd90421c4b31cf5cf7d0d6d33336f00aa0c125e41b8ebcc825b8bd30031",
        "bytes": 519,
        "local_path": (
            "runtime/reports/apex_frontier/"
            "20260711T211344Z_cur0s_static_identity_v1_phone_receipt/COMPLETE.json"
        ),
    },
    "cur0s_exact_success_custody": {
        "sha256": "1759a001568225fc6de75daa014481d1136f9ad98cc6cd317a2002779ab7b350",
        "bytes": 1976,
        "local_path": (
            "runtime/reports/apex_frontier/"
            "20260711T211344Z_cur0s_static_identity_v1_phone_receipt/custody.json"
        ),
    },
    "cur0s_exact_attempt_ledger": {
        "sha256": "ea862816568935af740a233348e52305d59b3744b55fca3869dc910f92a16c5f",
        "bytes": 3331,
        "local_path": (
            "runtime/reports/apex_frontier/"
            "20260711T211344Z_cur0s_static_identity_attempt_ledger.json"
        ),
    },
}

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
    if profile.require_v6_campaign_cross_bindings:
        _validate_v6_operation_cross_bindings(value)
        _reject_v6_commit_placeholders(value)
    if profile.transition_kind == "v6_cur0s_exact":
        _validate_cur0s_exact_operation_surface(value)
        _validate_cur0s_exact_bindings(value)
    _reject_secret_material(value)
    return copy.deepcopy(value)


def _validate_cur0s_exact_operation_surface(spec: Mapping[str, Any]) -> None:
    if spec["evidence_cutoff_utc"] != _CUR0S_EXACT_EVIDENCE_CUTOFF_UTC:
        raise CapsuleTransitionError("cur0s_exact_evidence_cutoff_invalid")
    operations = spec["mutation"]["operations"]
    observed_paths = {
        tuple(operation["path"])
        for operation in operations
    }
    if observed_paths != _V6_CUR0S_EXACT_OPERATION_PATHS:
        raise CapsuleTransitionError("cur0s_exact_operation_surface_invalid")
    if any(operation["op"] != "replace" for operation in operations):
        raise CapsuleTransitionError("cur0s_exact_operation_not_replace")


def _exact_local_artifact(
    role: str,
    sha256: str,
    byte_count: int,
    local_path: str,
) -> dict[str, Any]:
    return {
        "role": role,
        "locator": local_path,
        "sha256": sha256,
        "bytes": byte_count,
        "custody": "repository_local",
        "local_path": local_path,
    }


def _validate_exact_local_artifact_collection(
    observed: Sequence[Mapping[str, Any]],
    expected_by_role: Mapping[str, Mapping[str, Any]],
    context: str,
) -> None:
    observed_by_role = {artifact["role"]: artifact for artifact in observed}
    if len(observed_by_role) != len(observed):
        raise CapsuleTransitionError(f"cur0s_exact_{context}_role_duplicate")
    if set(observed_by_role) != set(expected_by_role):
        raise CapsuleTransitionError(f"cur0s_exact_{context}_roles_invalid")
    for role, expected in expected_by_role.items():
        expected_artifact = _exact_local_artifact(
            role,
            expected["sha256"],
            expected["bytes"],
            expected["local_path"],
        )
        if observed_by_role[role] != expected_artifact:
            raise CapsuleTransitionError(
                f"cur0s_exact_{context}_{role}_artifact_invalid"
            )


def _validate_cur0s_exact_bindings(spec: Mapping[str, Any]) -> None:
    bindings = spec["bindings"]
    frontier_path = "runtime/reports/apex_frontier/frontier_event_20260711T192408Z.json"
    expected_frontier = _exact_local_artifact(
        "frontier_root",
        _CUR0S_EXACT_FRONTIER_SHA256,
        10398,
        frontier_path,
    )
    if bindings["frontier"] != expected_frontier:
        raise CapsuleTransitionError("cur0s_exact_frontier_binding_invalid")
    expected_selector = copy.deepcopy(expected_frontier)
    expected_selector["role"] = "maximal_selector"
    if bindings["maximal_selector"] != expected_selector:
        raise CapsuleTransitionError("cur0s_exact_selector_binding_invalid")

    _validate_exact_local_artifact_collection(
        bindings["preregistrations"],
        _CUR0S_EXACT_PREREGISTRATION_ARTIFACTS,
        "preregistrations",
    )
    _validate_exact_local_artifact_collection(
        bindings["sanitized_reports"],
        _CUR0S_EXACT_SANITIZED_ARTIFACTS,
        "sanitized_reports",
    )

    expected_inputs = {
        "governing_prd": _exact_local_artifact(
            "governing_prd",
            "725d0ad6ac77fdcfc06a2635c7552cc414e0ed48f30fbd0f7f7ec38720493a3c",
            209401,
            "docs/PRD-GEMMA4-E4B-PHONE-NATIVE-QNN-LEARNING-CELL-2026-07-10.md",
        ),
        "corpus_readiness_audit": _exact_local_artifact(
            "corpus_readiness_audit",
            "c3a5d5eacf424f6e50ae0a170873d1c80e566581e22031a8f64bc899f8eec0fa",
            43722,
            "docs/APEX-C1-C4-CORPUS-READINESS-AND-INTEGRATION-AUDIT-2026-07-10.md",
        ),
        "living_engineering_concept": {
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
    }
    observed_inputs = {artifact["role"]: artifact for artifact in bindings["inputs"]}
    if len(observed_inputs) != len(bindings["inputs"]):
        raise CapsuleTransitionError("cur0s_exact_inputs_role_duplicate")
    if observed_inputs != expected_inputs:
        raise CapsuleTransitionError("cur0s_exact_inputs_invalid")

    expected_raw_reports = [
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
    ]
    if bindings["raw_reports"] != expected_raw_reports:
        raise CapsuleTransitionError("cur0s_exact_raw_reports_invalid")

    expected_lease = {
        "lease_id": "current_user_sovereign_frontier_campaign_20260711",
        "expires_at_utc": "2026-07-12T01:13:53Z",
        "artifact": _exact_local_artifact(
            "access_resource_refresh",
            "7b2b6d506b3ab82a17008edc4c79dd51512f6f9598e3db37cd1bb6f5ee4331ca",
            3552,
            "runtime/reports/apex_frontier/access_refresh_20260711T020533Z.json",
        ),
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
    }
    if bindings["lease"] != expected_lease:
        raise CapsuleTransitionError("cur0s_exact_lease_invalid")

    expected_transition = {
        "subject_id": "CUR-0S-CURRENT-EXACT-IDENTITY",
        "subject_kind": "candidate",
        "from": "selected_frozen_unobserved",
        "to": "passed_scope",
        "evidence_sha256": _CUR0S_EXACT_RECEIPT_SHA256,
        "reason": "physical_and_exact_identity_passed_without_CUR0S_promotion",
    }
    if bindings["transitions"] != [expected_transition]:
        raise CapsuleTransitionError("cur0s_exact_transition_binding_invalid")

    expected_source_scope = [
        "exact_v6_CUR0S_identity_CAS_profile",
        "dedicated_v6_CUR0S_identity_CLI",
        "fail_closed_profile_and_race_tests",
    ]
    source_commit = bindings["source_commit"]
    if source_commit["repository"] != "Zer0pa/Polymath-AI":
        raise CapsuleTransitionError("cur0s_exact_source_repository_invalid")
    if source_commit["scope"] != expected_source_scope:
        raise CapsuleTransitionError("cur0s_exact_source_scope_invalid")
    expected_evidence_commit = {
        "repository": "Zer0pa/Polymath-AI",
        "commit_sha": _CUR0S_EXACT_EVIDENCE_COMMIT,
        "scope": ["CUR0S_exact_identity_phone_evidence"],
    }
    if bindings["evidence_commit"] != expected_evidence_commit:
        raise CapsuleTransitionError("cur0s_exact_evidence_commit_invalid")
    if bindings.get("scoped_push_receipt") is not None:
        raise CapsuleTransitionError("cur0s_exact_scoped_push_receipt_invalid")

    preserved_sha256 = [
        EXPECTED_V6_CUR0S_EXACT_PARENT_SHA256,
        _CUR0S_EXACT_FRONTIER_SHA256,
        "7b2b6d506b3ab82a17008edc4c79dd51512f6f9598e3db37cd1bb6f5ee4331ca",
        *(
            artifact["sha256"]
            for artifact in _CUR0S_EXACT_PREREGISTRATION_ARTIFACTS.values()
        ),
        *(
            artifact["sha256"]
            for artifact in _CUR0S_EXACT_SANITIZED_ARTIFACTS.values()
        ),
        "604931c652f74c8160c076edf8f80ef65570cab3c4ac7f849fb1ba84526309e9",
        "9502f57f55e57fc5008ebbeec749bccaa0639ebefee8b8b212ee7ff53817ed05",
        "725d0ad6ac77fdcfc06a2635c7552cc414e0ed48f30fbd0f7f7ec38720493a3c",
        "c3a5d5eacf424f6e50ae0a170873d1c80e566581e22031a8f64bc899f8eec0fa",
        "b2f617766b660237ddfd329c6b7fa2370f9a2641983e71915b4cd71c6d31bacc",
    ]
    expected_rollback = {
        "rollback_base": {
            "role": "parent_capsule_archive",
            "locator": (
                "archive://docs/current_reality/v6/"
                f"{EXPECTED_V6_CUR0S_EXACT_PARENT_SHA256}"
            ),
            "sha256": EXPECTED_V6_CUR0S_EXACT_PARENT_SHA256,
            "bytes": 61531,
            "custody": "repository_archive",
        },
        "preserved_sha256": preserved_sha256,
        "invalidated_sha256": [],
        "disposition": (
            "preserve_CUR0S_physical_and_exact_identity_passed_scope_"
            "without_CUR0S_admission"
        ),
    }
    if bindings["rollback"] != expected_rollback:
        raise CapsuleTransitionError("cur0s_exact_rollback_invalid")


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


def _reject_v6_commit_placeholders(spec: Mapping[str, Any]) -> None:
    bindings = spec["bindings"]
    for field in ("source_commit", "evidence_commit"):
        commit_sha = bindings[field]["commit_sha"]
        if set(commit_sha) == {"0"}:
            raise CapsuleTransitionError(f"v6_{field}_placeholder_unresolved")


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


def validate_v6_adreno_pass_spec(
    value: dict[str, Any],
    repository_root: Path,
) -> dict[str, Any]:
    """Validate the exact reviewed v6 Adreno-pass transition specification."""

    return _validate_spec_for_profile(value, repository_root, _V6_ADRENO_PASS)


def validate_v6_cur0s_exact_spec(
    value: dict[str, Any],
    repository_root: Path,
) -> dict[str, Any]:
    """Validate the exact reviewed v6 CUR-0S identity transition."""

    return _validate_spec_for_profile(value, repository_root, _V6_CUR0S_EXACT)


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
    if profile.transition_kind == "v6_cur0s_exact":
        _validate_cur0s_exact_child(parent, child, spec)
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


def derive_v6_adreno_pass_child_capsule(
    parent: dict[str, Any],
    spec: dict[str, Any],
) -> dict[str, Any]:
    """Derive the exact reviewed v6 child after the bounded Adreno pass."""

    return _derive_child_capsule_for_profile(parent, spec, _V6_ADRENO_PASS)


def derive_v6_cur0s_exact_child_capsule(
    parent: dict[str, Any],
    spec: dict[str, Any],
) -> dict[str, Any]:
    """Derive the exact v6 child after scoped CUR-0S exact identity."""

    return _derive_child_capsule_for_profile(parent, spec, _V6_CUR0S_EXACT)


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


def _cur0s_exact_expected_gate(parent: dict[str, Any]) -> dict[str, Any]:
    expected = copy.deepcopy(
        _nested(parent, "corpus_curriculum", "curriculum_gates", "CUR-0S")
    )
    expected.update(
        {
            "exact_identity_state": "passed_scope",
            "physical_verification_state": "passed_scope",
            "cur0s_static_pass_claimed": False,
            "cur0s_pass_claimed": False,
            "target_data_learning_claimed": False,
            "promotion_allowed": False,
            "first_missing_green_field": "successor_commercial_source_root",
            "implementation_substrate": (
                "committed_cur0s_exact_discriminator_"
                f"{_CUR0S_EXACT_DISCRIMINATOR_SOURCE_COMMIT}"
            ),
            "phone_execution_count": 3,
            "source_changes_adopted": True,
            "subordinate_receipt_sha256": _CUR0S_EXACT_RECEIPT_SHA256,
            "subordinate_overlay_root_sha256": (
                "9502f57f55e57fc5008ebbeec749bccaa0639ebefee8b8b212ee7ff53817ed05"
            ),
            "state": "blocked_fail_closed",
        }
    )
    return expected


def _cur0s_exact_expected_claim(parent: dict[str, Any]) -> dict[str, Any]:
    expected = copy.deepcopy(_nested(parent, "measured_claims", "CUR_0S_CURRENT"))
    expected.update(
        {
            "exact_identity_state": "passed_scope",
            "physical_verification_state": "passed_scope",
            "cur0s_static_pass_claimed": False,
            "cur0s_pass_claimed": False,
            "target_data_learning_claimed": False,
            "promotion_allowed": False,
            "first_missing_green_field": "successor_commercial_source_root",
            "implementation_source_commit": (
                _CUR0S_EXACT_DISCRIMINATOR_SOURCE_COMMIT
            ),
            "source_committed": True,
            "preregistered_attempt_count": 4,
            "phone_execution_count": 3,
            "successful_action_count": 1,
            "observed_at_utc": "2026-07-11T21:17:47Z",
            "evidence": {
                "receipt_sha256": _CUR0S_EXACT_RECEIPT_SHA256,
                "receipt_root_sha256": (
                    "33f6de080a98d921392a970d9751a21d31ca443e1d54c7179244c1cd504f7605"
                ),
                "completion_sha256": (
                    "65235bd90421c4b31cf5cf7d0d6d33336f00aa0c125e41b8ebcc825b8bd30031"
                ),
                "overlay_file_sha256": (
                    "604931c652f74c8160c076edf8f80ef65570cab3c4ac7f849fb1ba84526309e9"
                ),
                "overlay_root_sha256": (
                    "9502f57f55e57fc5008ebbeec749bccaa0639ebefee8b8b212ee7ff53817ed05"
                ),
                "success_custody_root_sha256": (
                    "9a37bd21689a2dc2347d210541585a605eb92d8499dfc2cdef3d736ed9430f2b"
                ),
                "attempt_ledger_root_sha256": (
                    "9d1fd786b0ed930c5a7997b99b9d2942477a19bfc631eb3aff60fbeae0f52365"
                ),
            },
            "scope": {
                "master_row_count": 77023,
                "overlay_row_count": 77023,
                "exact_semantic_cluster_count": 77023,
                "repeated_semantic_cluster_count": 0,
                "source_instance_component_count": 64139,
                "maximum_component_size": 22,
                "maximum_source_instances_per_component": 1,
                "giant_component_share": 0.0002856289679706062,
                "answer_only_union_edge_count": 0,
                "legacy_split_conflict_component_count": 1150,
                "legacy_split_conflict_row_count": 2442,
                "historically_exposed_component_count": 3727,
                "historically_exposed_row_count": 5043,
                "cross_stage_component_count": 11961,
                "cross_stage_row_count": 24775,
                "raw_overlay_phone_private": True,
            },
            "nonclaims": [
                "CUR-0S_static_admission",
                "CUR-0P",
                "composite_CUR-0",
                "target_data_learning",
                "quality_authority",
                "PRD_section_0_5",
            ],
            "state": "blocked_fail_closed",
        }
    )
    return expected


def _cur0s_exact_expected_design(parent: dict[str, Any]) -> dict[str, Any]:
    expected = copy.deepcopy(_nested(parent, "current_design_decision"))
    expected["last_verified_executed_prefix"] = [
        *expected["last_verified_executed_prefix"],
        "CUR-0S_physical_and_exact_identity_passed_scope_subordinate_only",
    ]
    return expected


def _cur0s_exact_expected_next_action(parent: dict[str, Any]) -> dict[str, Any]:
    expected = copy.deepcopy(_nested(parent, "next_action"))
    expected.update(
        {
            "design_predecessor": (
                f"cur0s_exact_identity_receipt_{_CUR0S_EXACT_RECEIPT_SHA256}"
            ),
            "executable_action": (
                "build_and_freeze_successor_commercial_source_root_on_phone_"
                "then_run_static_CUR-0S_admission"
            ),
        }
    )
    return expected


def _cur0s_exact_expected_campaign(
    parent: dict[str, Any],
    spec: dict[str, Any],
) -> dict[str, Any]:
    expected = copy.deepcopy(_nested(parent, "last_verified_campaign_state"))
    expected.update(
        {
            "active_sovereign_gate": (
                "CUR-0_curriculum_readiness_via_successor_commercial_source_root"
            ),
            "evidence_commit": spec["bindings"]["evidence_commit"]["commit_sha"],
            "first_missing_green_field": "successor_commercial_source_root",
            "frontier_root_sha256": spec["bindings"]["frontier"]["sha256"],
            "last_disposition": _CUR0S_EXACT_DISPOSITION,
            "parent_capsule_sha256": EXPECTED_V6_CUR0S_EXACT_PARENT_SHA256,
            "rollback_base": {
                "archive_locator": (
                    "docs/APEX-CURRENT-REALITY-CAPSULE-GEMMA4-E4B-QNN-CELL-"
                    "2026-07-10.yaml.archive/"
                    f"{EXPECTED_V6_CUR0S_EXACT_PARENT_SHA256}.yaml"
                ),
                "capsule_sha256": EXPECTED_V6_CUR0S_EXACT_PARENT_SHA256,
            },
            "source_commit": spec["bindings"]["source_commit"]["commit_sha"],
            "terminal_status": "not_reached",
            "cur0s_exact_identity_receipt_sha256": _CUR0S_EXACT_RECEIPT_SHA256,
            "cur0s_static_pass_claimed": False,
            "target_data_learning_claimed": False,
        }
    )
    return expected


def _validate_cur0s_exact_child(
    parent: dict[str, Any],
    child: dict[str, Any],
    spec: dict[str, Any],
) -> None:
    expected_values = {
        "gate": (
            _nested(child, "corpus_curriculum", "curriculum_gates", "CUR-0S"),
            _cur0s_exact_expected_gate(parent),
        ),
        "claim": (
            _nested(child, "measured_claims", "CUR_0S_CURRENT"),
            _cur0s_exact_expected_claim(parent),
        ),
        "design": (
            _nested(child, "current_design_decision"),
            _cur0s_exact_expected_design(parent),
        ),
        "next_action": (
            _nested(child, "next_action"),
            _cur0s_exact_expected_next_action(parent),
        ),
        "campaign": (
            _nested(child, "last_verified_campaign_state"),
            _cur0s_exact_expected_campaign(parent, spec),
        ),
    }
    for context, (observed, expected) in expected_values.items():
        if observed != expected:
            raise CapsuleTransitionError(f"cur0s_exact_{context}_mismatch")

    frontier = _nested(child, "frontier_execution_policy")
    if frontier.get("active_candidate") != "cur0s_successor_commercial_source_root_v1":
        raise CapsuleTransitionError("cur0s_exact_active_candidate_invalid")
    if frontier.get("last_disposition") != _CUR0S_EXACT_DISPOSITION:
        raise CapsuleTransitionError("cur0s_exact_last_disposition_invalid")
    if _nested(child, "success_terminal", "section_0_5_satisfied") is not False:
        raise CapsuleTransitionError("cur0s_exact_child_success_terminal_promoted")


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
    expected_parent_bytes: bytes,
    child_bytes: bytes,
) -> None:
    write_exclusive_or_verify(temporary_path, child_bytes, "canonical_stage")
    # The adjacent advisory lock is the writer-serialization authority.  This
    # final identity check additionally catches a non-cooperating write during
    # transaction materialization, immediately before the atomic rename.
    pre_replace_bytes = read_regular_file(
        canonical_path,
        max_bytes=MAX_CAPSULE_BYTES,
        context="canonical_pre_replace",
    )
    if pre_replace_bytes != expected_parent_bytes:
        raise CapsuleTransitionError("canonical_changed_before_atomic_replace")
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
            _atomic_replace_canonical(
                canonical_path,
                temporary_path,
                parent_bytes,
                child_bytes,
            )
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


def advance_capsule_v6_adreno_pass(
    *,
    canonical_path: Path,
    transition_spec_path: Path,
    repository_root: Path,
    fault_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Perform or recover the one exact v6 Adreno-pass capsule CAS."""

    return _advance_capsule_for_profile(
        profile=_V6_ADRENO_PASS,
        canonical_path=canonical_path,
        transition_spec_path=transition_spec_path,
        repository_root=repository_root,
        fault_injector=fault_injector,
    )


def advance_capsule_v6_cur0s_exact(
    *,
    canonical_path: Path,
    transition_spec_path: Path,
    repository_root: Path,
    fault_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Perform or recover the exact v6 CUR-0S identity capsule CAS."""

    return _advance_capsule_for_profile(
        profile=_V6_CUR0S_EXACT,
        canonical_path=canonical_path,
        transition_spec_path=transition_spec_path,
        repository_root=repository_root,
        fault_injector=fault_injector,
    )


__all__ = [
    "COMPLETION_SCHEMA",
    "EXPECTED_V4_SHA256",
    "EXPECTED_V5_SHA256",
    "EXPECTED_V6_ADRENO_PASS_PARENT_SHA256",
    "EXPECTED_V6_CUR0S_EXACT_PARENT_SHA256",
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
    "advance_capsule_v6_adreno_pass",
    "advance_capsule_v6_cur0s_exact",
    "canonical_json",
    "derive_child_capsule",
    "derive_v6_adreno_pass_child_capsule",
    "derive_v6_cur0s_exact_child_capsule",
    "derive_v6_child_capsule",
    "deterministic_yaml",
    "sha256_bytes",
    "strict_json_loads",
    "strict_yaml_loads",
    "validate_spec",
    "validate_v6_adreno_pass_spec",
    "validate_v6_cur0s_exact_spec",
    "validate_v6_spec",
    "value_sha256",
    "verify_regular_file_identity",
]

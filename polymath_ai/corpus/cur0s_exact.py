"""Fail-closed exact identity for the CUR-0S commercial curriculum frontier.

This module implements the source-lineage and exact joint-content arms of the
global connected-group contract.  It intentionally does not discover near
semantic edges, assign successor splits, admit rights/quality, or claim
CUR-0S.  Those are separate authority boundaries.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
import hashlib
import json
import math
import re
import unicodedata
from typing import Any


ALGORITHM_VERSION = "cur0s_exact_lineage_joint_content_v1"
OVERLAY_VERSION = "cur0s_exact_identity_overlay_v1"
REPORT_VERSION = "cur0s_exact_identity_report_v1"

_STAGE_ALIASES = {
    "C1": "C1",
    "C2": "C2",
    "C2.5": "B23",
    "C2_5": "B23",
    "B23": "B23",
    "C3": "C3",
    "C4": "C4",
}
_EXPECTED_PHASE = {"C1": 1.0, "C2": 2.0, "B23": 2.5, "C3": 3.0, "C4": 4.0}
_TOP_LEVEL_FIELDS = frozenset({"instruction", "input", "output", "metadata"})
_SPACE_RE = re.compile(r"\s+")

# Operational and provenance fields must not make otherwise identical material
# look semantically different.  Unknown metadata remains semantic by default.
_NON_SEMANTIC_METADATA_FIELDS = frozenset(
    {
        "created_at",
        "dataset_id",
        "dataset_revision",
        "enrichment_quarantine",
        "enrichment_schema_version",
        "enrichment_template_hash",
        "enrichment_template_version",
        "enrichment_validation",
        "generated_at",
        "generator_model",
        "ingested_at",
        "license",
        "license_class",
        "phase",
        "prompt_batch_size",
        "prompt_hash",
        "provenance_url",
        "provider_id",
        "provider_model",
        "quality_score",
        "record_id",
        "row_id",
        "source",
        "source_id",
        "source_local_id",
        "source_ref",
        "source_revision",
        "source_url",
        "split",
        "structured_field_derivation",
        "template_version",
        "tier",
        "updated_at",
        "vocab_violation_score",
    }
)


class Cur0sExactError(ValueError):
    """The exact identity input or result is not admissible."""


class MissingLineageError(Cur0sExactError):
    """A row is missing immutable source-instance lineage."""


class DuplicateRecordError(Cur0sExactError):
    """A master record identity repeats."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def strict_json_loads(payload: str | bytes) -> Any:
    return json.loads(
        payload,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_nonfinite_constant,
    )


def normalize_stage(value: str) -> str:
    stage = _STAGE_ALIASES.get(str(value).strip().upper())
    if stage is None:
        raise Cur0sExactError("unsupported_stage")
    return stage


def normalize_text(value: str) -> str:
    return _SPACE_RE.sub(" ", unicodedata.normalize("NFC", value)).strip()


def normalize_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise Cur0sExactError("nonfinite_semantic_number")
        return value
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, list):
        return [normalize_json(item) for item in value]
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise Cur0sExactError("non_string_semantic_key")
            normalized_key = normalize_text(key)
            if not normalized_key or normalized_key in result:
                raise Cur0sExactError("invalid_or_colliding_semantic_key")
            result[normalized_key] = normalize_json(item)
        return result
    raise Cur0sExactError("non_json_semantic_value")


@dataclass(frozen=True)
class AntiPercolationPolicy:
    max_component_size: int
    max_giant_component_share: float
    max_source_instances_per_component: int

    def __post_init__(self) -> None:
        if type(self.max_component_size) is not int:
            raise Cur0sExactError("max_component_size_must_be_exact_integer")
        if self.max_component_size < 1:
            raise Cur0sExactError("max_component_size_must_be_positive")
        if type(self.max_giant_component_share) is not float or not math.isfinite(
            self.max_giant_component_share
        ):
            raise Cur0sExactError("max_giant_component_share_must_be_finite_float")
        if not 0 < self.max_giant_component_share <= 1:
            raise Cur0sExactError("max_giant_component_share_out_of_range")
        if type(self.max_source_instances_per_component) is not int:
            raise Cur0sExactError("max_source_instances_must_be_exact_integer")
        if self.max_source_instances_per_component < 1:
            raise Cur0sExactError("max_source_instances_must_be_positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_component_size": self.max_component_size,
            "max_giant_component_share": self.max_giant_component_share,
            "max_source_instances_per_component": self.max_source_instances_per_component,
        }


@dataclass(frozen=True)
class RecordIdentity:
    stage: str
    master_record_id: str
    master_record_sha256: str
    source_instance_id: str
    exact_semantic_id: str
    exact_question_id: str
    exact_answer_id: str
    exact_split_group_id: str = ""
    legacy_split: str = ""

    def private_overlay_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OVERLAY_VERSION,
            "stage": self.stage,
            "master_record_id": self.master_record_id,
            "master_record_sha256": self.master_record_sha256,
            "source_instance_id": self.source_instance_id,
            "exact_semantic_id": self.exact_semantic_id,
            "exact_question_id": self.exact_question_id,
            "exact_answer_id": self.exact_answer_id,
            "exact_split_group_id": self.exact_split_group_id,
            "legacy_split": self.legacy_split,
        }


@dataclass(frozen=True)
class ExactIdentityResult:
    rows: tuple[RecordIdentity, ...]
    overlay_root_sha256: str
    report: dict[str, Any]


class _UnionFind:
    def __init__(self) -> None:
        self._parent: list[int] = []
        self._size: list[int] = []

    def add(self) -> int:
        index = len(self._parent)
        self._parent.append(index)
        self._size.append(1)
        return index

    def find(self, index: int) -> int:
        root = index
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[index] != index:
            parent = self._parent[index]
            self._parent[index] = root
            index = parent
        return root

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self._size[left_root] < self._size[right_root]:
            left_root, right_root = right_root, left_root
        self._parent[right_root] = left_root
        self._size[left_root] += self._size[right_root]


def record_identity(stage: str, payload: Mapping[str, Any]) -> RecordIdentity:
    normalized_stage = normalize_stage(stage)
    if set(payload) != _TOP_LEVEL_FIELDS:
        raise Cur0sExactError("master_top_level_contract_mismatch")

    metadata = payload.get("metadata")
    if not isinstance(metadata, Mapping):
        raise Cur0sExactError("metadata_must_be_object")
    _validate_phase(normalized_stage, metadata.get("phase"))

    record_id = _required_identifier(metadata, "record_id")
    dataset_id = _required_lineage_string(metadata, "dataset_id")
    dataset_revision = _required_lineage_string(metadata, "dataset_revision")
    source_local_id = _required_lineage_string(metadata, "source_local_id")
    legacy_split = _normalize_legacy_split(_required_string(metadata, "split"))

    source_instance_id = "src:v1:" + _digest(
        {
            "dataset_id": dataset_id,
            "dataset_revision": dataset_revision,
            "source_local_id": source_local_id,
        }
    )
    semantic_metadata = {
        str(key): item
        for key, item in metadata.items()
        if str(key) not in _NON_SEMANTIC_METADATA_FIELDS
    }
    instruction = normalize_json(_required_top_string(payload, "instruction"))
    input_text = normalize_json(_required_top_string(payload, "input"))
    output = normalize_json(_required_top_string(payload, "output"))
    semantic_projection = {
        "instruction": instruction,
        "input": input_text,
        "output": output,
        "metadata": normalize_json(semantic_metadata),
    }
    exact_semantic_id = "sem:exact:v1:" + _digest(semantic_projection)
    exact_question_id = "question:exact:v1:" + _digest(
        {"instruction": instruction, "input": input_text}
    )
    exact_answer_id = "answer:exact:v1:" + _digest({"output": output})
    return RecordIdentity(
        stage=normalized_stage,
        master_record_id=record_id,
        master_record_sha256="sha256:" + hashlib.sha256(canonical_json_bytes(payload)).hexdigest(),
        source_instance_id=source_instance_id,
        exact_semantic_id=exact_semantic_id,
        exact_question_id=exact_question_id,
        exact_answer_id=exact_answer_id,
        legacy_split=legacy_split,
    )


def build_exact_identity(
    records: Iterable[tuple[str, Mapping[str, Any]]],
    *,
    source_repository: str,
    source_revision: str,
    policy: AntiPercolationPolicy,
) -> ExactIdentityResult:
    if not source_repository.strip() or not source_revision.strip():
        raise Cur0sExactError("source_identity_must_be_nonempty")

    union = _UnionFind()
    rows: list[RecordIdentity] = []
    record_ids: set[str] = set()
    source_first: dict[str, int] = {}
    semantic_first: dict[str, int] = {}

    for stage, payload in records:
        row = record_identity(stage, payload)
        if row.master_record_id in record_ids:
            raise DuplicateRecordError("duplicate_master_record_id")
        record_ids.add(row.master_record_id)
        index = union.add()
        rows.append(row)
        _union_with_first(union, source_first, row.source_instance_id, index)
        _union_with_first(union, semantic_first, row.exact_semantic_id, index)

    if not rows:
        raise Cur0sExactError("empty_source")

    members_by_root: dict[int, list[int]] = defaultdict(list)
    for index in range(len(rows)):
        members_by_root[union.find(index)].append(index)

    group_by_root = {
        root: _component_id(rows, members)
        for root, members in members_by_root.items()
    }
    grouped = tuple(
        replace(row, exact_split_group_id=group_by_root[union.find(index)])
        for index, row in enumerate(rows)
    )
    ordered = tuple(sorted(grouped, key=lambda row: (row.stage, row.master_record_id)))
    overlay_root = canonical_sha256(
        {
            "schema_version": OVERLAY_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "source_repository": source_repository,
            "source_revision": source_revision,
            "rows": [row.private_overlay_dict() for row in ordered],
        }
    )
    report = _build_report(ordered, policy, overlay_root)
    return ExactIdentityResult(rows=ordered, overlay_root_sha256=overlay_root, report=report)


def _build_report(
    rows: tuple[RecordIdentity, ...],
    policy: AntiPercolationPolicy,
    overlay_root: str,
) -> dict[str, Any]:
    by_group: dict[str, list[RecordIdentity]] = defaultdict(list)
    by_source: Counter[str] = Counter()
    by_semantic: Counter[str] = Counter()
    by_question: Counter[str] = Counter()
    by_answer: Counter[str] = Counter()
    stage_counts: Counter[str] = Counter()
    for row in rows:
        by_group[row.exact_split_group_id].append(row)
        by_source[row.source_instance_id] += 1
        by_semantic[row.exact_semantic_id] += 1
        by_question[row.exact_question_id] += 1
        by_answer[row.exact_answer_id] += 1
        stage_counts[row.stage] += 1

    component_sizes = sorted((len(group) for group in by_group.values()), reverse=True)
    max_component_size = component_sizes[0]
    giant_share = max_component_size / len(rows)
    max_sources = max(
        len({row.source_instance_id for row in group}) for group in by_group.values()
    )
    cross_stage = [group for group in by_group.values() if len({row.stage for row in group}) > 1]
    split_conflicts = [
        group for group in by_group.values() if len({row.legacy_split for row in group}) > 1
    ]
    within_stage_conflicts = 0
    for group in by_group.values():
        splits_by_stage: dict[str, set[str]] = defaultdict(set)
        for row in group:
            splits_by_stage[row.stage].add(row.legacy_split)
        if any(len(splits) > 1 for splits in splits_by_stage.values()):
            within_stage_conflicts += 1
    exposed_groups = [
        group
        for group in by_group.values()
        if any(row.legacy_split in {"validation", "test", "hidden_test"} for row in group)
    ]
    failures = []
    if max_component_size > policy.max_component_size:
        failures.append("maximum_component_size_exceeded")
    if giant_share > policy.max_giant_component_share:
        failures.append("giant_component_share_exceeded")
    if max_sources > policy.max_source_instances_per_component:
        failures.append("source_instances_per_component_exceeded")

    histogram = Counter(component_sizes)
    return {
        "schema_version": REPORT_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "overlay_root_sha256": overlay_root,
        "record_count": len(rows),
        "stage_counts": dict(sorted(stage_counts.items())),
        "source_instance_count": len(by_source),
        "repeated_source_instance_count": sum(count > 1 for count in by_source.values()),
        "maximum_rows_per_source_instance": max(by_source.values()),
        "exact_semantic_cluster_count": len(by_semantic),
        "repeated_exact_semantic_cluster_count": sum(count > 1 for count in by_semantic.values()),
        "maximum_rows_per_exact_semantic_cluster": max(by_semantic.values()),
        "exact_question_unit_count": len(by_question),
        "repeated_exact_question_unit_count": sum(
            count > 1 for count in by_question.values()
        ),
        "maximum_rows_per_exact_question_unit": max(by_question.values()),
        "exact_question_overlap_root_sha256": _overlap_root("question", by_question),
        "exact_answer_unit_count": len(by_answer),
        "repeated_exact_answer_unit_count": sum(
            count > 1 for count in by_answer.values()
        ),
        "maximum_rows_per_exact_answer_unit": max(by_answer.values()),
        "exact_answer_overlap_root_sha256": _overlap_root("answer", by_answer),
        "answer_only_union_edges": 0,
        "exact_connected_component_count": len(by_group),
        "component_size_histogram": {str(size): count for size, count in sorted(histogram.items())},
        "maximum_component_size": max_component_size,
        "giant_component_share": giant_share,
        "maximum_source_instances_per_component": max_sources,
        "cross_stage_component_count": len(cross_stage),
        "cross_stage_component_row_count": sum(map(len, cross_stage)),
        "legacy_split_conflict_component_count": len(split_conflicts),
        "legacy_split_conflict_row_count": sum(map(len, split_conflicts)),
        "within_stage_legacy_split_conflict_component_count": within_stage_conflicts,
        "historically_exposed_component_count": len(exposed_groups),
        "historically_exposed_row_count": sum(map(len, exposed_groups)),
        "anti_percolation": {
            "policy": policy.to_dict(),
            "policy_sha256": canonical_sha256(policy.to_dict()),
            "status": "passed_scope" if not failures else "falsified_scope",
            "failures": failures,
        },
        "claim_scope": "exact_source_lineage_plus_exact_joint_content_only",
        "nonclaims": [
            "not_near_semantic_grouping",
            "not_successor_split_assignment",
            "not_rights_or_quality_admission",
            "not_CUR_0S",
            "not_CUR_0P_or_composite_CUR_0",
        ],
    }


def _component_id(rows: list[RecordIdentity], members: list[int]) -> str:
    material = sorted(
        (
            rows[index].master_record_sha256,
            rows[index].source_instance_id,
            rows[index].exact_semantic_id,
        )
        for index in members
    )
    return "sg:exact:v1:" + _digest({"members": material})


def _union_with_first(
    union: _UnionFind, first_by_key: dict[str, int], key: str, index: int
) -> None:
    previous = first_by_key.setdefault(key, index)
    union.union(previous, index)


def _required_string(metadata: Mapping[str, Any], key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value:
        raise Cur0sExactError(f"missing_or_invalid_{key}")
    return value


def _required_lineage_string(metadata: Mapping[str, Any], key: str) -> str:
    try:
        return _required_identifier(metadata, key)
    except Cur0sExactError:
        raise MissingLineageError(f"missing_lineage_{key}") from None


def _required_identifier(metadata: Mapping[str, Any], key: str) -> str:
    value = _required_string(metadata, key)
    if value != value.strip() or not value.strip():
        raise Cur0sExactError(f"missing_or_invalid_{key}")
    if any(unicodedata.category(character) in {"Cc", "Cf", "Cs"} for character in value):
        raise Cur0sExactError(f"invalid_control_character_{key}")
    return value


def _required_top_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise Cur0sExactError(f"master_{key}_must_be_string")
    return value


def _validate_phase(stage: str, value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Cur0sExactError("phase_must_be_numeric")
    if float(value) != _EXPECTED_PHASE[stage]:
        raise Cur0sExactError("stage_phase_mismatch")


def _normalize_legacy_split(value: str) -> str:
    normalized = {"train": "train", "val": "validation", "validation": "validation", "test": "test"}.get(
        value.strip().lower()
    )
    if normalized is None:
        raise Cur0sExactError("unsupported_legacy_split")
    return normalized


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _overlap_root(kind: str, counts: Counter[str]) -> str:
    return canonical_sha256(
        {
            "schema_version": "cur0s_exact_overlap_aggregate_v1",
            "kind": kind,
            "opaque_unit_counts": sorted(counts.items()),
        }
    )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise Cur0sExactError("duplicate_json_key")
        result[key] = value
    return result


def _reject_nonfinite_constant(_: str) -> None:
    raise Cur0sExactError("nonfinite_json_constant")

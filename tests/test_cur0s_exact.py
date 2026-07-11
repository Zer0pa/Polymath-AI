from __future__ import annotations

import copy

import pytest

from polymath_ai.corpus.cur0s_exact import (
    AntiPercolationPolicy,
    Cur0sExactError,
    DuplicateRecordError,
    MissingLineageError,
    build_exact_identity,
    normalize_text,
    record_identity,
    strict_json_loads,
)
from polymath_ai.corpus.cur0s_static import (
    SOURCE_REVISION,
    STAGE_LOCKS,
    TOTAL_ROWS,
    first_missing_green_field,
    physical_lock_contract,
    static_gate_matrix,
)


PHASES = {"C1": 1, "C2": 2, "B23": 2.5, "C3": 3, "C4": 4}


def master(
    record_id: str,
    *,
    stage: str = "C3",
    dataset_id: str = "dataset/a",
    dataset_revision: str = "rev-1",
    source_local_id: str | None = None,
    instruction: str = "What is inertia?",
    input_text: str = "",
    output: str = "Inertia is resistance to a change in motion.",
    split: str = "train",
    extra: dict | None = None,
) -> tuple[str, dict]:
    metadata = {
        "record_id": record_id,
        "phase": PHASES[stage],
        "dataset_id": dataset_id,
        "dataset_revision": dataset_revision,
        "source_local_id": source_local_id or f"source-{record_id}",
        "split": split,
        "license": "cc-by-4.0",
        "quality_score": 0.9,
    }
    metadata.update(extra or {})
    return stage, {
        "instruction": instruction,
        "input": input_text,
        "output": output,
        "metadata": metadata,
    }


def policy(**overrides) -> AntiPercolationPolicy:
    values = {
        "max_component_size": 16,
        "max_giant_component_share": 1.0,
        "max_source_instances_per_component": 16,
    }
    values.update(overrides)
    return AntiPercolationPolicy(**values)


def build(records, *, selected_policy=None):
    return build_exact_identity(
        records,
        source_repository="Zer0pa/test-private",
        source_revision="immutable-test-revision",
        policy=selected_policy or policy(),
    )


def test_same_source_instance_connects_stage_views() -> None:
    records = [
        master("c3", stage="C3", source_local_id="shared", instruction="long view"),
        master("c4", stage="C4", source_local_id="shared", instruction="short view"),
    ]
    result = build(records)
    assert len({row.exact_split_group_id for row in result.rows}) == 1
    assert result.report["cross_stage_component_count"] == 1


def test_exact_joint_content_connects_different_sources() -> None:
    records = [
        master("one", dataset_id="dataset/a", source_local_id="1"),
        master("two", dataset_id="dataset/b", source_local_id="2"),
    ]
    result = build(records)
    assert result.report["source_instance_count"] == 2
    assert result.report["exact_semantic_cluster_count"] == 1
    assert result.report["exact_connected_component_count"] == 1


def test_answer_only_match_does_not_connect() -> None:
    records = [
        master("one", instruction="Which planet?", output="Mercury."),
        master(
            "two",
            dataset_id="dataset/b",
            source_local_id="2",
            instruction="Which element?",
            output="Mercury.",
        ),
    ]
    result = build(records)
    assert result.report["exact_connected_component_count"] == 2
    assert result.report["repeated_exact_answer_unit_count"] == 1
    assert result.report["answer_only_union_edges"] == 0


def test_question_only_match_is_aggregate_but_does_not_connect() -> None:
    records = [
        master("one", instruction="Which planet?", output="Mercury."),
        master(
            "two",
            dataset_id="dataset/b",
            source_local_id="2",
            instruction="Which planet?",
            output="Venus.",
        ),
    ]
    result = build(records)
    assert result.report["exact_connected_component_count"] == 2
    assert result.report["repeated_exact_question_unit_count"] == 1
    assert result.report["maximum_rows_per_exact_question_unit"] == 2
    assert result.report["exact_question_overlap_root_sha256"].startswith("sha256:")


def test_semantic_metadata_is_conservative_but_provenance_is_ignored() -> None:
    base = master("one", extra={"evidence": {"unit": "m/s"}})
    same = master(
        "two",
        dataset_id="dataset/b",
        dataset_revision="rev-2",
        source_local_id="2",
        split="validation",
        extra={"evidence": {"unit": "m/s"}},
    )
    different = master(
        "three",
        dataset_id="dataset/c",
        source_local_id="3",
        extra={"evidence": {"unit": "km/s"}},
    )
    result = build([base, same, different])
    rows = {row.master_record_id: row for row in result.rows}
    assert rows["one"].exact_semantic_id == rows["two"].exact_semantic_id
    assert rows["one"].exact_semantic_id != rows["three"].exact_semantic_id


def test_unicode_and_space_normalize_but_case_remains_semantic() -> None:
    assert normalize_text(" cafe\u0301  field ") == "café field"
    first = master("one", instruction="Force  field")
    second = master(
        "two", dataset_id="dataset/b", source_local_id="2", instruction="Force field"
    )
    third = master(
        "three", dataset_id="dataset/c", source_local_id="3", instruction="force field"
    )
    result = build([first, second, third])
    rows = {row.master_record_id: row for row in result.rows}
    assert rows["one"].exact_semantic_id == rows["two"].exact_semantic_id
    assert rows["one"].exact_semantic_id != rows["three"].exact_semantic_id


@pytest.mark.parametrize("field", ["dataset_id", "dataset_revision", "source_local_id"])
def test_missing_lineage_fails_closed(field: str) -> None:
    stage, payload = master("one")
    del payload["metadata"][field]
    with pytest.raises(MissingLineageError, match=field):
        record_identity(stage, payload)


def test_duplicate_record_id_fails_without_leaking_value() -> None:
    with pytest.raises(DuplicateRecordError) as failure:
        build([master("secret-id"), master("secret-id", dataset_id="dataset/b")])
    assert "secret-id" not in str(failure.value)


def test_legacy_split_conflict_and_exposure_are_aggregate_only() -> None:
    result = build(
        [
            master("train", source_local_id="shared", split="train"),
            master("test", source_local_id="shared", split="test"),
        ]
    )
    assert result.report["legacy_split_conflict_component_count"] == 1
    assert result.report["historically_exposed_component_count"] == 1
    assert result.report["historically_exposed_row_count"] == 2
    assert "master_record_id" not in result.report


def test_result_is_order_independent() -> None:
    records = [
        master("a", source_local_id="shared"),
        master("b", source_local_id="shared", instruction="other"),
        master("c", dataset_id="dataset/c", source_local_id="c"),
    ]
    forward = build(records)
    reverse = build(reversed(records))
    assert forward.overlay_root_sha256 == reverse.overlay_root_sha256
    assert forward.report == reverse.report


def test_anti_percolation_failure_is_explicit() -> None:
    records = [master(str(index), source_local_id="shared") for index in range(3)]
    result = build(records, selected_policy=policy(max_component_size=2))
    assert result.report["anti_percolation"]["status"] == "falsified_scope"
    assert result.report["anti_percolation"]["failures"] == [
        "maximum_component_size_exceeded"
    ]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"max_component_size": True}, "exact_integer"),
        ({"max_component_size": 1.0}, "exact_integer"),
        ({"max_source_instances_per_component": False}, "exact_integer"),
        ({"max_source_instances_per_component": 2.5}, "exact_integer"),
        ({"max_giant_component_share": 1}, "finite_float"),
        ({"max_giant_component_share": float("nan")}, "finite_float"),
        ({"max_giant_component_share": float("inf")}, "finite_float"),
    ],
)
def test_anti_percolation_policy_requires_exact_finite_types(
    overrides: dict, message: str
) -> None:
    with pytest.raises(Cur0sExactError, match=message):
        policy(**overrides)


def test_invalid_master_shape_and_phase_fail() -> None:
    stage, payload = master("one")
    payload["unexpected"] = True
    with pytest.raises(Cur0sExactError, match="top_level"):
        record_identity(stage, payload)
    _, wrong_phase = master("two")
    wrong_phase["metadata"]["phase"] = 4
    with pytest.raises(Cur0sExactError, match="stage_phase"):
        record_identity("C3", wrong_phase)


def test_strict_json_rejects_duplicate_and_nonfinite_values() -> None:
    with pytest.raises(Cur0sExactError, match="duplicate_json_key"):
        strict_json_loads('{"a":1,"a":2}')
    with pytest.raises(Cur0sExactError, match="nonfinite_json_constant"):
        strict_json_loads('{"a":NaN}')


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dataset_id", "   "),
        ("dataset_revision", "\trev"),
        ("source_local_id", "source\nidentifier"),
        ("record_id", "\u200bhidden"),
    ],
)
def test_identity_fields_reject_whitespace_and_control_characters(
    field: str, value: str
) -> None:
    stage, payload = master("one")
    payload["metadata"][field] = value
    expected = MissingLineageError if field != "record_id" else Cur0sExactError
    with pytest.raises(expected):
        record_identity(stage, payload)


def test_static_physical_contract_is_exact_and_self_rooted() -> None:
    contract = physical_lock_contract()
    assert contract["source_revision"] == SOURCE_REVISION
    assert sum(lock.rows for lock in STAGE_LOCKS) == TOTAL_ROWS
    root = contract.pop("contract_sha256")
    from polymath_ai.corpus.cur0s_exact import canonical_sha256

    assert root == canonical_sha256(contract)


def test_gate_matrix_never_promotes_partial_identity() -> None:
    gates = static_gate_matrix(physical_pass=True, exact_identity_pass=True)
    assert gates[0]["state"] == "passed_scope"
    assert gates[1]["state"] == "passed_scope"
    assert first_missing_green_field(gates) == "successor_commercial_source_root"
    assert any(
        gate["state"] == "policy_dependency_deadlock"
        for gate in gates
        if gate["gate"] == "deferred_equal_budget_learning_retention_dimension"
    )


def test_record_identity_does_not_mutate_input() -> None:
    stage, payload = master("one")
    before = copy.deepcopy(payload)
    record_identity(stage, payload)
    assert payload == before

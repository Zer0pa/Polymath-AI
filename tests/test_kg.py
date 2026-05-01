"""KG node/edge serialization and reconstruction."""
from __future__ import annotations

import pytest

from polymath_ai.kg.graph import KGEdge, KGNode, KGStore, NODE_TYPES, reconstruct_kg


def test_node_type_validation():
    from polymath_ai.kg.graph import KG
    kg = KG()
    kg.add_node(KGNode(node_id="run:1", node_type="Run"))
    with pytest.raises(ValueError):
        kg.add_node(KGNode(node_id="x", node_type="NotAType"))


def test_edge_type_validation():
    from polymath_ai.kg.graph import KG
    kg = KG()
    kg.add_node(KGNode(node_id="a", node_type="Run"))
    kg.add_node(KGNode(node_id="b", node_type="Run"))
    with pytest.raises(ValueError):
        kg.add_edge(KGEdge(edge_id="e1", edge_type="NotAType", src_id="a", dst_id="b"))


def test_round_trip(tmp_path):
    store = KGStore(tmp_path)
    store.write_node(node_id="run:1", node_type="Run", attributes={"phase": "phase0a_substrate"})
    store.write_node(node_id="ckpt:abc", node_type="Checkpoint", attributes={"step": 100})
    store.write_edge(
        edge_id="e:run:1->ckpt:abc",
        edge_type="PRODUCED",
        src_id="run:1",
        dst_id="ckpt:abc",
        attributes={"recorded_at": "2026-05-01T00:00:00Z"},
    )

    kg = reconstruct_kg(tmp_path)
    assert "run:1" in kg.nodes
    assert "ckpt:abc" in kg.nodes
    assert kg.nodes["run:1"].attributes["phase"] == "phase0a_substrate"
    neighbors = kg.neighbors("run:1", edge_type="PRODUCED")
    assert len(neighbors) == 1
    assert neighbors[0].node_id == "ckpt:abc"


def test_reconstruct_with_missing_referenced_node(tmp_path):
    """Edges referencing absent nodes still reconstruct, with placeholders."""
    store = KGStore(tmp_path)
    store.write_edge(
        edge_id="e:dangling",
        edge_type="DERIVED_FROM",
        src_id="phantom_a",
        dst_id="phantom_b",
    )
    kg = reconstruct_kg(tmp_path)
    assert "phantom_a" in kg.nodes
    assert "phantom_b" in kg.nodes
    assert kg.nodes["phantom_a"].attributes.get("placeholder") is True


def test_node_types_match_prd_set():
    must_have = {
        "Run",
        "Phase",
        "Experiment",
        "Model",
        "Tokenizer",
        "CorpusManifest",
        "CorpusSource",
        "CorpusChunk",
        "LicenseFinding",
        "OCRProvenance",
        "Checkpoint",
        "DeviceState",
        "DispatchRecord",
        "SchedulerPolicy",
        "EvalArtifact",
        "TeacherPanelJudgment",
        "FalsifierResult",
        "DisagreementRecord",
        "Decision",
        "SyncEvent",
        "ReasonerTuple",
    }
    assert must_have.issubset(set(NODE_TYPES))

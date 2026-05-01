"""Knowledge graph nodes / edges + JSONL projection of the audit log."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Tuple

from polymath_ai._version import SCHEMA_VERSION
from polymath_ai.boundary.text import boundary_envelope
from polymath_ai.utils.canonical import (
    canonical_json,
    hash_mapping,
    utc_now_iso,
)


NODE_TYPES: Tuple[str, ...] = (
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
    "ExportProbe",
)

EDGE_TYPES: Tuple[str, ...] = (
    "USED_MODEL",
    "USED_TOKENIZER",
    "USED_CORPUS",
    "PRODUCED",
    "VALIDATED_BY",
    "FAILED_BY",
    "WARNED_BY",
    "DISAGREES_WITH",
    "DERIVED_FROM",
    "SYNCED_TO",
    "BLOCKED_BY",
    "SUPERSEDES",
    "RIGHTS_CONSTRAINED_BY",
    "JUDGED_BY",
)


@dataclass(frozen=True)
class KGNode:
    """In-memory KG node representation."""

    node_id: str
    node_type: str
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KGEdge:
    """In-memory KG edge representation."""

    edge_id: str
    edge_type: str
    src_id: str
    dst_id: str
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class KG:
    """Lightweight in-memory KG built from the JSONL store."""

    nodes: Dict[str, KGNode] = field(default_factory=dict)
    edges: Dict[str, KGEdge] = field(default_factory=dict)
    out_edges: Dict[str, List[str]] = field(default_factory=dict)
    in_edges: Dict[str, List[str]] = field(default_factory=dict)

    def add_node(self, node: KGNode) -> None:
        if node.node_type not in NODE_TYPES:
            raise ValueError(f"unknown node_type {node.node_type!r}")
        self.nodes[node.node_id] = node
        self.out_edges.setdefault(node.node_id, [])
        self.in_edges.setdefault(node.node_id, [])

    def add_edge(self, edge: KGEdge) -> None:
        if edge.edge_type not in EDGE_TYPES:
            raise ValueError(f"unknown edge_type {edge.edge_type!r}")
        self.edges[edge.edge_id] = edge
        self.out_edges.setdefault(edge.src_id, []).append(edge.edge_id)
        self.in_edges.setdefault(edge.dst_id, []).append(edge.edge_id)

    def neighbors(self, node_id: str, edge_type: Optional[str] = None) -> List[KGNode]:
        out_ids = self.out_edges.get(node_id, [])
        result: List[KGNode] = []
        for eid in out_ids:
            edge = self.edges[eid]
            if edge_type is None or edge.edge_type == edge_type:
                tgt = self.nodes.get(edge.dst_id)
                if tgt is not None:
                    result.append(tgt)
        return result


@dataclass
class KGStore:
    """JSONL-backed KG writer.

    Separate files for nodes and edges keep diffs readable. Both files are
    append-only.
    """

    nodes_path: Path
    edges_path: Path

    def __init__(self, root: str | os.PathLike[str]) -> None:
        rp = Path(root)
        rp.mkdir(parents=True, exist_ok=True)
        self.nodes_path = rp / "nodes.jsonl"
        self.edges_path = rp / "edges.jsonl"

    def write_node(
        self,
        *,
        node_id: str,
        node_type: str,
        attributes: Mapping[str, Any] | None = None,
        recorded_at: Optional[str] = None,
    ) -> dict:
        attrs = dict(attributes or {})
        row = {
            "schema_version": SCHEMA_VERSION,
            "boundary": boundary_envelope(),
            "kind": "node",
            "node_id": node_id,
            "node_type": node_type,
            "attributes": attrs,
            "attributes_sha256": hash_mapping(attrs) if attrs else "sha256:empty",
            "recorded_at": recorded_at or utc_now_iso(),
        }
        with open(self.nodes_path, "a", encoding="utf-8") as f:
            f.write(canonical_json(row) + "\n")
        return row

    def write_edge(
        self,
        *,
        edge_id: str,
        edge_type: str,
        src_id: str,
        dst_id: str,
        attributes: Mapping[str, Any] | None = None,
        recorded_at: Optional[str] = None,
    ) -> dict:
        attrs = dict(attributes or {})
        row = {
            "schema_version": SCHEMA_VERSION,
            "boundary": boundary_envelope(),
            "kind": "edge",
            "edge_id": edge_id,
            "edge_type": edge_type,
            "src_id": src_id,
            "dst_id": dst_id,
            "attributes": attrs,
            "recorded_at": recorded_at or utc_now_iso(),
        }
        with open(self.edges_path, "a", encoding="utf-8") as f:
            f.write(canonical_json(row) + "\n")
        return row


def _iter_jsonl(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def reconstruct_kg(root: str | os.PathLike[str]) -> KG:
    """Read the JSONL store at ``root`` and return an in-memory KG."""
    rp = Path(root)
    kg = KG()
    for row in _iter_jsonl(rp / "nodes.jsonl"):
        kg.add_node(
            KGNode(
                node_id=row["node_id"],
                node_type=row["node_type"],
                attributes=row.get("attributes", {}),
            )
        )
    for row in _iter_jsonl(rp / "edges.jsonl"):
        if row["src_id"] not in kg.nodes:
            kg.add_node(KGNode(node_id=row["src_id"], node_type="Run", attributes={"placeholder": True}))
        if row["dst_id"] not in kg.nodes:
            kg.add_node(KGNode(node_id=row["dst_id"], node_type="Run", attributes={"placeholder": True}))
        kg.add_edge(
            KGEdge(
                edge_id=row["edge_id"],
                edge_type=row["edge_type"],
                src_id=row["src_id"],
                dst_id=row["dst_id"],
                attributes=row.get("attributes", {}),
            )
        )
    return kg

"""Append-only knowledge-graph nodes and edges with reconstruction utilities.

Nodes and edges are written to JSONL alongside the audit log. The KG is a
*projection* of the audit log into typed nodes and edges, not a separate
authority. Reconstruction reads the JSONL and returns an in-memory graph.
"""
from polymath_ai.kg.graph import (
    KG,
    KGEdge,
    KGNode,
    NODE_TYPES,
    EDGE_TYPES,
    KGStore,
    reconstruct_kg,
)

__all__ = [
    "KG",
    "KGEdge",
    "KGNode",
    "NODE_TYPES",
    "EDGE_TYPES",
    "KGStore",
    "reconstruct_kg",
]

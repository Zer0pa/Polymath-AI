"""Append-only hash-chained JSONL audit log.

The audit log is the canonical record of every event in a run. Each row's
``event_hash`` covers ``prev_event_hash``, ``recorded_at``, and ``payload`` so
tamper, reorder, insert, and delete are detectable by replay.

DuckDB / SQLite indices over the JSONL are caches only. The JSONL is source of
truth.
"""
from polymath_ai.audit.chain import (
    AuditChainError,
    AuditWriter,
    GENESIS_HASH,
    canonical_event_payload,
    compute_event_hash,
    iter_audit,
    validate_audit_chain,
)

__all__ = [
    "AuditChainError",
    "AuditWriter",
    "GENESIS_HASH",
    "canonical_event_payload",
    "compute_event_hash",
    "iter_audit",
    "validate_audit_chain",
]

"""JSON Schema and dataclass contracts for Polymath envelopes and records.

Every machine-readable artifact this package produces conforms to one of the
shapes defined here. Schemas are intentionally written in plain
``dict``-of-strings form rather than a heavy schema library so the contract is
copy-pasteable across host, Termux, and Runpod machines without dependency
risk.

A Pydantic-like layer can be added later if validation cost matters; for now,
``validate(record, schema)`` performs a minimal structural check.
"""
from polymath_ai.schemas.envelope import (
    ENVELOPE_SCHEMA,
    new_envelope,
    fingerprint_envelope,
)
from polymath_ai.schemas.records import (
    AUDIT_ROW_SCHEMA,
    CHECKPOINT_RECORD_SCHEMA,
    CORPUS_MANIFEST_SCHEMA,
    DEVICE_STATE_SCHEMA,
    DISPATCH_RECORD_SCHEMA,
    EVAL_RECORD_SCHEMA,
    FALSIFIER_RESULT_SCHEMA,
    PENDING_UPLOAD_SCHEMA,
    REASONER_TUPLE_SCHEMA,
    SYNC_EVENT_SCHEMA,
)
from polymath_ai.schemas.validate import validate, ValidationError

__all__ = [
    "ENVELOPE_SCHEMA",
    "new_envelope",
    "fingerprint_envelope",
    "AUDIT_ROW_SCHEMA",
    "CHECKPOINT_RECORD_SCHEMA",
    "CORPUS_MANIFEST_SCHEMA",
    "DEVICE_STATE_SCHEMA",
    "DISPATCH_RECORD_SCHEMA",
    "EVAL_RECORD_SCHEMA",
    "FALSIFIER_RESULT_SCHEMA",
    "PENDING_UPLOAD_SCHEMA",
    "REASONER_TUPLE_SCHEMA",
    "SYNC_EVENT_SCHEMA",
    "validate",
    "ValidationError",
]

# Audit Trail Specification

**Boundary:** Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts - model checkpoints, training telemetry, evaluation reports, throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

## Overview

The audit log is the canonical record of every event in a Polymath run. It is append-only JSONL with a SHA-256 hash chain. Implementation lives in `polymath_ai/audit/chain.py`. The hash chain is what enforces the brain-functionality gate (PRD §Acceptance Gates): a fresh agent reading GitHub + HF + the audit log alone can reconstruct state without conversation context.

## Row schema

Every row is a single JSON object:

```json
{
  "schema_version": "1.0.0",
  "boundary": {
    "boundary_id": "boundary:polymath:v1",
    "boundary_text_sha256": "sha256:<hex>",
    "boundary_manifest": "polymath_ai/boundary/text.py"
  },
  "recorded_at": "2026-05-01T03:14:15Z",
  "run_id": "run:<timestamp>:<slug>",
  "event_type": "<see enum below>",
  "payload": { ... },
  "prev_event_hash": "sha256:<hex>",
  "event_hash": "sha256:<hex>"
}
```

### `event_type` enum

| Type | When emitted |
|---|---|
| `genesis` | First event in a run. Payload carries phase + arg snapshot. |
| `train_step` | Each ELO Stage 1 / Stage 2 step. Payload: `{step, loss, grad_norm, frozen_changed: [], ...}`. |
| `checkpoint` | Every checkpoint save. Payload: full `CHECKPOINT_RECORD_SCHEMA` row or pointer. |
| `eval` | Each eval run. Payload: `EVAL_RECORD_SCHEMA` row. |
| `decision` | Decision recorded; mirror of a `docs/DECISIONS.md` entry. |
| `sync` | Each GitHub / HF / ADB push or pull. Payload: `SYNC_EVENT_SCHEMA`. |
| `falsifier` | Each falsifier evaluation. Payload: `{falsifier_id, result, detail, blocking}`. |
| `device_probe` | Each phone / ADB / Termux probe. Payload: `DEVICE_STATE_SCHEMA`. |
| `export_probe` | Each LiteRT / QNN compile attempt. Payload: compile log + delegate report + status. |
| `boundary_check` | Boundary scanner outcome. Payload: `BoundaryScanResult[]` summary. |
| `reasoner_tuple` | Eval tuple writes; mirror of `reasoner_queue/` tuple. |
| `phase_gate` | A phase-advancement gate decision. Payload: `{from_phase, to_phase, falsifiers_passed: [...]}`. |

## Hash chain semantics

* `prev_event_hash` of the first event is the genesis hash `sha256:000…000`.
* `event_hash = sha256(canonical_json({prev_event_hash, recorded_at, payload}))`.
* `recorded_at` is part of the hash so reordering is detectable.
* Canonical JSON: keys sorted, no whitespace between separators, ASCII escapes, UTF-8.
* JSONL is the source of truth. Any DuckDB / SQLite indices are caches and rebuilt from JSONL.

## Tamper / reorder / insert / delete detection

`polymath_ai.audit.validate_audit_chain(path)` returns a list of error strings, empty when clean. The detection rules:

* **Tamper:** recomputed `event_hash` differs from stored `event_hash` -> "event_hash mismatch" error.
* **Reorder:** the next row's `prev_event_hash` no longer matches the previous row's `event_hash` -> "prev_event_hash mismatch".
* **Insert:** a fabricated row will either fail event-hash recomputation (caller supplied a bad hash) or break the `prev_event_hash` chain on the row after.
* **Delete:** the row after the deletion has `prev_event_hash` pointing to a hash no longer in the file -> chain break.

All four are covered by `tests/test_audit_chain.py`.

## Resume semantics

`AuditWriter(path, run_id)` reads the last row at construction and uses its `event_hash` as the chain head for the next append. This makes crash-resume safe: a process that died mid-run can re-attach to its log and continue without re-deriving state.

If the file does not exist or is empty, the chain head is the genesis hash.

## Persistence guarantees

* `AuditWriter.append` writes the row, calls `flush()`, then `os.fsync()`.
* If the process crashes after `flush()` but before `fsync()`, on most filesystems the row is durable; on some, the tail row may be lost. The next `AuditWriter` construction recovers from whatever made it to disk.
* Concurrent writers to the same audit file are not supported. Each run owns its own file under `runtime/runs/<run_id>/audit.jsonl`.

## KG projection

The KG (`polymath_ai.kg.graph`) is a *projection* of the audit log into typed nodes and edges. Reconstruction is read-only: `reconstruct_kg(root)` reads `nodes.jsonl` and `edges.jsonl` and returns an in-memory `KG`.

Node types (PRD §KG Node Types) are validated at write time via `KG.add_node`; unknown types raise `ValueError`. Same for edges.

## Brain-functionality gate

For a fresh agent to reconstruct state from GitHub + HF + audit log, the following must be true:

1. The audit log validates clean.
2. Every checkpoint referenced by audit rows is reachable on HF (or pending in the upload manifest).
3. Every corpus manifest referenced by audit rows is in GitHub.
4. Every decision row in the audit log mirrors a `docs/DECISIONS.md` entry (or vice versa).
5. The KG reconstructs without missing-node placeholders that block downstream reasoning.

Falsifier `overclaim` fires if any report claims something not provable from this set.

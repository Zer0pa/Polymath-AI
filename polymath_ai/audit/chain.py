"""Hash-chained JSONL audit log."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, List, Mapping, Optional

from polymath_ai._version import SCHEMA_VERSION
from polymath_ai.boundary.text import boundary_envelope
from polymath_ai.utils.canonical import (
    canonical_json,
    canonical_json_bytes,
    sha256_bytes,
    utc_now_iso,
)


GENESIS_HASH = "sha256:" + ("0" * 64)


class AuditChainError(Exception):
    """Raised when the audit chain fails validation."""


def canonical_event_payload(*, prev_event_hash: str, recorded_at: str, payload: Mapping[str, Any]) -> bytes:
    """Canonical bytes that the event_hash covers.

    Excludes the row's own ``event_hash`` (chicken-and-egg) and excludes
    ``run_id``/``event_type`` because they are present in ``payload``-level
    fields when relevant; the chain's invariant is over the timestamp + prior
    hash + payload triple. ``run_id`` and ``event_type`` are still part of the
    final row for human readability and grep-ability.
    """
    return canonical_json_bytes(
        {
            "prev_event_hash": prev_event_hash,
            "recorded_at": recorded_at,
            "payload": payload,
        }
    )


def compute_event_hash(*, prev_event_hash: str, recorded_at: str, payload: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_event_payload(prev_event_hash=prev_event_hash, recorded_at=recorded_at, payload=payload))


@dataclass
class AuditWriter:
    """Append events to a JSONL file, maintaining the hash chain.

    Usage:

        writer = AuditWriter(path)
        writer.append(event_type="train_step", run_id="run:...", payload={...})

    The writer reads the last row on open to recover ``prev_event_hash`` so
    crash-resume picks up the chain correctly.
    """

    path: Path
    run_id: str
    _prev_hash: str = GENESIS_HASH

    def __init__(self, path: str | os.PathLike[str], run_id: str) -> None:
        self.path = Path(path)
        self.run_id = run_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._prev_hash = self._recover_tail_hash()

    def _recover_tail_hash(self) -> str:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return GENESIS_HASH
        last: Optional[dict] = None
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                last = json.loads(line)
        if not last:
            return GENESIS_HASH
        return last["event_hash"]

    @property
    def tail_hash(self) -> str:
        return self._prev_hash

    def append(
        self,
        *,
        event_type: str,
        payload: Mapping[str, Any],
        recorded_at: Optional[str] = None,
    ) -> dict:
        """Append a single event row and return it.

        The chain is fsync'd after each append. JSONL is the source of truth.
        """
        ts = recorded_at or utc_now_iso()
        event_hash = compute_event_hash(prev_event_hash=self._prev_hash, recorded_at=ts, payload=payload)
        row = {
            "schema_version": SCHEMA_VERSION,
            "boundary": boundary_envelope(),
            "recorded_at": ts,
            "run_id": self.run_id,
            "event_type": event_type,
            "payload": dict(payload),
            "prev_event_hash": self._prev_hash,
            "event_hash": event_hash,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(canonical_json(row) + "\n")
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        self._prev_hash = event_hash
        return row


def iter_audit(path: str | os.PathLike[str]) -> Iterator[dict]:
    p = Path(path)
    if not p.exists():
        return
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def validate_audit_chain(path: str | os.PathLike[str]) -> List[str]:
    """Return a list of error messages; empty list means valid.

    Detects:
      * recomputed ``event_hash`` mismatch (tamper / reorder / insert / delete)
      * ``prev_event_hash`` chain break
    """
    errors: List[str] = []
    expected_prev = GENESIS_HASH
    for i, row in enumerate(iter_audit(path)):
        if row.get("prev_event_hash") != expected_prev:
            errors.append(
                f"row {i}: prev_event_hash mismatch (got {row.get('prev_event_hash')!r}, "
                f"expected {expected_prev!r})"
            )
        recomputed = compute_event_hash(
            prev_event_hash=row["prev_event_hash"],
            recorded_at=row["recorded_at"],
            payload=row["payload"],
        )
        if recomputed != row.get("event_hash"):
            errors.append(
                f"row {i}: event_hash mismatch (got {row.get('event_hash')!r}, recomputed {recomputed!r})"
            )
        expected_prev = row.get("event_hash", expected_prev)
    return errors

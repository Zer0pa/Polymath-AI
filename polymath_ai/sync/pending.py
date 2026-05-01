"""Pending-upload manifest writer.

When the HF token is absent, the network is unavailable, or an upload fails
mid-flight, the executor enqueues the artifact here. Each manifest row
captures local path, sha256, size, and the intended HF target so a future
agent can flush queued uploads without losing intent.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, List, Mapping, Optional

from polymath_ai._version import SCHEMA_VERSION
from polymath_ai.boundary.text import boundary_envelope
from polymath_ai.utils.canonical import canonical_json, sha256_file, utc_now_iso


@dataclass
class PendingUploadStore:
    """Append-only JSONL queue of pending uploads."""

    path: Path

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        *,
        pending_id: str,
        local_path: str,
        size_bytes: int,
        intended_target: Mapping[str, Any],
        sha256: Optional[str] = None,
        license_attestation_id: Optional[str] = None,
        blocked_by: Optional[str] = None,
    ) -> dict:
        if sha256 is None:
            if Path(local_path).is_file():
                sha256 = sha256_file(local_path)
            else:
                sha256 = "sha256:absent"
        row = {
            "schema_version": SCHEMA_VERSION,
            "boundary": boundary_envelope(),
            "pending_id": pending_id,
            "local_path": str(local_path),
            "sha256": sha256,
            "size_bytes": int(size_bytes),
            "intended_target": dict(intended_target),
            "license_attestation_id": license_attestation_id,
            "blocked_by": blocked_by,
            "queued_at": utc_now_iso(),
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(canonical_json(row) + "\n")
        return row

    def list(self) -> List[dict]:
        return list(self._iter())

    def _iter(self) -> Iterator[dict]:
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)


def queue_pending_upload(
    store_path: str | os.PathLike[str],
    *,
    pending_id: str,
    local_path: str,
    intended_target: Mapping[str, Any],
    blocked_by: Optional[str] = None,
    license_attestation_id: Optional[str] = None,
) -> dict:
    """Convenience wrapper. Computes size automatically."""
    p = Path(local_path)
    size = p.stat().st_size if p.is_file() else 0
    sha = sha256_file(p) if p.is_file() else "sha256:absent"
    store = PendingUploadStore(store_path)
    return store.append(
        pending_id=pending_id,
        local_path=str(p),
        size_bytes=size,
        intended_target=intended_target,
        sha256=sha,
        license_attestation_id=license_attestation_id,
        blocked_by=blocked_by,
    )


def list_pending_uploads(store_path: str | os.PathLike[str]) -> List[dict]:
    return PendingUploadStore(store_path).list()

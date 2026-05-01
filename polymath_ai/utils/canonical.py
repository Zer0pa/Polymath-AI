"""Canonical JSON, hashing, and time helpers.

Canonical JSON rules:

* UTF-8 encoded.
* Keys sorted lexicographically at every level.
* No whitespace between separators.
* ASCII-safe escapes (``ensure_ascii=True``) so file diff tooling stays sane
  across editors.

All audit hashes, KG node hashes, checkpoint hashes, and reasoner-tuple hashes
go through ``canonical_json`` -> ``sha256`` so two replays of the same input
produce identical hashes.
"""
from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def canonical_json(obj: Any) -> str:
    """Return canonical JSON for ``obj``."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_json_bytes(obj: Any) -> bytes:
    return canonical_json(obj).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: str | Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            buf = f.read(chunk)
            if not buf:
                break
            h.update(buf)
    return "sha256:" + h.hexdigest()


def utc_now_iso(now: datetime.datetime | None = None) -> str:
    """Return ISO-8601 UTC, second precision, ``Z`` suffix."""
    dt = now or datetime.datetime.now(tz=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hash_mapping(payload: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(payload))

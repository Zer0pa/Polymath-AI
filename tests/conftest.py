"""Shared fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


# Make the source tree importable without pip install -e .
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def tmp_run(tmp_path):
    return {
        "run_id": "run:20260501T000000Z:test",
        "audit_path": tmp_path / "audit.jsonl",
        "kg_root": tmp_path / "kg",
        "pending_path": tmp_path / "pending.jsonl",
    }

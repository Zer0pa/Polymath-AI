"""Audit hash-chain tamper / reorder / insert / delete tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from polymath_ai.audit.chain import (
    AuditWriter,
    GENESIS_HASH,
    iter_audit,
    validate_audit_chain,
)


def _write_three_events(path):
    w = AuditWriter(path, run_id="run:test:0001")
    w.append(event_type="train_step", payload={"step": 0, "loss": 5.0})
    w.append(event_type="train_step", payload={"step": 1, "loss": 4.7})
    w.append(event_type="checkpoint", payload={"step": 1, "checkpoint_sha256": "sha256:abc"})
    return w


def test_chain_genesis_for_first_event(tmp_path):
    p = tmp_path / "audit.jsonl"
    AuditWriter(p, run_id="r").append(event_type="train_step", payload={"step": 0})
    rows = list(iter_audit(p))
    assert rows[0]["prev_event_hash"] == GENESIS_HASH


def test_chain_validates_on_clean_log(tmp_path):
    p = tmp_path / "audit.jsonl"
    _write_three_events(p)
    assert validate_audit_chain(p) == []


def test_resume_recovers_tail_hash(tmp_path):
    p = tmp_path / "audit.jsonl"
    _write_three_events(p)
    # Reopen and append. New row's prev_event_hash must match prior tail.
    rows1 = list(iter_audit(p))
    tail = rows1[-1]["event_hash"]
    AuditWriter(p, run_id="r").append(event_type="eval", payload={"metric": "perplexity", "value": 12.0})
    rows2 = list(iter_audit(p))
    assert rows2[3]["prev_event_hash"] == tail
    assert validate_audit_chain(p) == []


def test_chain_detects_tampered_payload(tmp_path):
    p = tmp_path / "audit.jsonl"
    _write_three_events(p)
    # Tamper: rewrite middle row's payload but keep its event_hash.
    lines = p.read_text().splitlines()
    middle = json.loads(lines[1])
    middle["payload"]["loss"] = 0.001  # implausible improvement
    lines[1] = json.dumps(middle, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")
    errors = validate_audit_chain(p)
    assert any("event_hash mismatch" in e for e in errors)


def test_chain_detects_reorder(tmp_path):
    p = tmp_path / "audit.jsonl"
    _write_three_events(p)
    lines = p.read_text().splitlines()
    # Swap rows 1 and 2.
    lines[1], lines[2] = lines[2], lines[1]
    p.write_text("\n".join(lines) + "\n")
    errors = validate_audit_chain(p)
    assert any("prev_event_hash mismatch" in e for e in errors)


def test_chain_detects_insert(tmp_path):
    p = tmp_path / "audit.jsonl"
    _write_three_events(p)
    lines = p.read_text().splitlines()
    fake = json.loads(lines[1])
    fake["payload"] = {"step": 99, "loss": 0.0}
    fake["recorded_at"] = "2027-01-01T00:00:00Z"
    lines.insert(2, json.dumps(fake, sort_keys=True))
    p.write_text("\n".join(lines) + "\n")
    errors = validate_audit_chain(p)
    assert errors  # any error


def test_chain_detects_delete(tmp_path):
    p = tmp_path / "audit.jsonl"
    _write_three_events(p)
    lines = p.read_text().splitlines()
    del lines[1]
    p.write_text("\n".join(lines) + "\n")
    errors = validate_audit_chain(p)
    assert any("prev_event_hash mismatch" in e for e in errors)


def test_chain_canonical_json_sorts_keys(tmp_path):
    p = tmp_path / "audit.jsonl"
    AuditWriter(p, run_id="r").append(event_type="train_step", payload={"b": 2, "a": 1})
    line = p.read_text().splitlines()[0]
    # Keys must appear sorted in JSON.
    assert line.index('"a"') < line.index('"b"')

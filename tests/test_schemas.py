"""Schema validator + envelope smoke tests."""
from __future__ import annotations

import pytest

from polymath_ai.schemas import (
    AUDIT_ROW_SCHEMA,
    CHECKPOINT_RECORD_SCHEMA,
    CORPUS_MANIFEST_SCHEMA,
    DEVICE_STATE_SCHEMA,
    ENVELOPE_SCHEMA,
    PENDING_UPLOAD_SCHEMA,
    REASONER_TUPLE_SCHEMA,
    new_envelope,
    fingerprint_envelope,
    validate,
    ValidationError,
)
from polymath_ai.boundary.text import boundary_envelope


def test_envelope_passes_validation():
    env = new_envelope(
        run_id="run:20260501T000000Z:smoke",
        phase="phase0a_substrate",
    )
    validate(env, ENVELOPE_SCHEMA)


def test_envelope_missing_required_fails():
    env = new_envelope(run_id="r", phase="phase0a_substrate")
    del env["model"]
    with pytest.raises(ValidationError):
        validate(env, ENVELOPE_SCHEMA)


def test_envelope_invalid_phase_fails():
    env = new_envelope(run_id="r", phase="phase0a_substrate")
    env["phase"] = "phase999_unknown"
    with pytest.raises(ValidationError):
        validate(env, ENVELOPE_SCHEMA)


def test_envelope_fingerprint_stable_under_outputs_change():
    env1 = new_envelope(run_id="r1", phase="phase0a_substrate")
    env2 = new_envelope(run_id="r2_different", phase="phase0a_substrate")
    # Same scientific contract -> same fingerprint despite different run_id.
    assert fingerprint_envelope(env1) == fingerprint_envelope(env2)
    env2["model"]["model_id"] = "Qwen/Qwen2.5-1.5B"
    # Different model -> different fingerprint.
    assert fingerprint_envelope(env1) != fingerprint_envelope(env2)


def test_corpus_manifest_validates():
    manifest = {
        "schema_version": "1.0.0",
        "boundary": boundary_envelope(),
        "manifest_id": "corpus:seed-v0:smoke-001",
        "manifest_sha256": "sha256:" + "a" * 64,
        "stage": "smoke",
        "tokens_target": 10_000,
        "domain_mix": {"cs_ml_systems": 0.5, "general_replay": 0.5},
        "language_mix": {"en": 1.0},
        "license_classes_allowed": ["A", "B"],
        "sources": [
            {
                "source_id": "gutenberg:1342",
                "uri": "https://www.gutenberg.org/ebooks/1342",
                "license_class": "A",
                "license_attestation_id": "license:gutenberg:public-domain",
                "language": "en",
                "domain": "philosophy_history",
                "ocr_provenance_id": None,
                "tokens_estimate": 120_000,
                "chunk_count": 60,
                "notes": "Pride and Prejudice; public domain",
            }
        ],
    }
    validate(manifest, CORPUS_MANIFEST_SCHEMA)


def test_checkpoint_record_validates():
    rec = {
        "schema_version": "1.0.0",
        "boundary": boundary_envelope(),
        "run_id": "run:test",
        "checkpoint_kind": "stage1_boundary",
        "model_id": "tiny.qwen.shape",
        "checkpoint_sha256": "sha256:" + "b" * 64,
        "trainable_param_names": ["model.layers.0.weight", "lm_head.weight"],
        "frozen_param_hash_sample": {"model.layers.5.weight": "sha256:" + "c" * 64},
        "optimizer_state_keys": ["model.layers.0.weight", "lm_head.weight"],
        "step": 100,
        "tokens_seen": 51200,
        "config_sha256": "sha256:" + "d" * 64,
        "corpus_slice_id": "corpus_slice:smoke-001",
        "base_model_pointer": "tiny.qwen.shape@base",
        "license_attestation_id": None,
        "hf_repo_id": None,
        "hf_path": None,
        "local_path": "/tmp/ckpt.safetensors",
    }
    validate(rec, CHECKPOINT_RECORD_SCHEMA)


def test_pending_upload_validates():
    rec = {
        "schema_version": "1.0.0",
        "boundary": boundary_envelope(),
        "pending_id": "pending:smoke:001",
        "local_path": "/tmp/x.safetensors",
        "sha256": "sha256:" + "e" * 64,
        "size_bytes": 1024,
        "intended_target": {
            "target_kind": "hf_model",
            "repo_id": "Architect-Prime/polymath-smoke",
            "path_in_repo": "ckpt-001.safetensors",
        },
        "license_attestation_id": None,
        "blocked_by": "hf_token_absent",
        "queued_at": "2026-05-01T00:00:00Z",
    }
    validate(rec, PENDING_UPLOAD_SCHEMA)


def test_reasoner_tuple_validates():
    rec = {
        "schema_version": "1.0.0",
        "boundary": boundary_envelope(),
        "run_id": "run:eval:001",
        "tuple_id": "tuple:001",
        "input": {
            "prompt": "Translate 'hello' to French.",
            "language": "en",
            "domain": "linguistics",
            "source_refs": [],
        },
        "output": {
            "model_id": "tiny.qwen.shape",
            "checkpoint_sha256": None,
            "text": "bonjour",
        },
        "judgment": {"status": "pass", "falsifier_ids": [], "teacher_panel": []},
        "correction": None,
        "hashes": {
            "input_sha256": "sha256:" + "1" * 64,
            "output_sha256": "sha256:" + "2" * 64,
            "judgment_sha256": "sha256:" + "3" * 64,
        },
    }
    validate(rec, REASONER_TUPLE_SCHEMA)

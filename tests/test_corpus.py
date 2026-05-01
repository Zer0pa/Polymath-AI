"""Corpus manifest + license-classification + fertility tests."""
from __future__ import annotations

import json

import pytest

from polymath_ai.corpus.license_classes import (
    LICENSE_CLASS_DESCRIPTIONS,
    audit_license,
    classify_source,
)
from polymath_ai.corpus.manifest import (
    CorpusSourceSpec,
    SeedCorpusV0Templates,
    build_manifest,
    load_manifest,
    save_manifest,
)


def test_classify_known_classes():
    assert classify_source("Public Domain (US)") == "A"
    assert classify_source("CC0 1.0") == "A"
    assert classify_source("Apache-2.0") == "B"
    assert classify_source("MIT License") == "B"
    assert classify_source("CC BY 4.0") == "B"
    assert classify_source("CC BY-SA 4.0") == "C"
    assert classify_source("GPL-3.0") == "C"
    assert classify_source("Crawled web text, no license") == "D"
    assert classify_source("All rights reserved") == "E"
    assert classify_source("") == "D"


def test_audit_license_ok_when_only_a_b():
    sources = [
        {"source_id": "g1", "license_class": "A"},
        {"source_id": "g2", "license_class": "B"},
    ]
    rep = audit_license(sources)
    assert rep["ok"] is True
    assert rep["by_class"] == {"A": 1, "B": 1}


def test_audit_license_fails_on_c_d_e():
    sources = [
        {"source_id": "g1", "license_class": "A"},
        {"source_id": "g2", "license_class": "C"},
        {"source_id": "g3", "license_class": "E"},
    ]
    rep = audit_license(sources)
    assert rep["ok"] is False
    assert len(rep["failures"]) == 2
    failed_ids = {f["source_id"] for f in rep["failures"]}
    assert failed_ids == {"g2", "g3"}


def test_audit_license_fails_on_missing_class():
    rep = audit_license([{"source_id": "g1"}])
    assert rep["ok"] is False


def test_build_manifest_smoke():
    sources = [
        CorpusSourceSpec(
            source_id="gutenberg:1342",
            uri="https://www.gutenberg.org/ebooks/1342",
            license_class="A",
            license_attestation_id="license:gutenberg:public-domain",
            language="en",
            domain="philosophy_history_epistemology",
            tokens_estimate=120_000,
            chunk_count=60,
            notes="Pride and Prejudice; public domain",
        )
    ]
    manifest = build_manifest(
        manifest_id="corpus:seed-v0:smoke-001",
        stage="smoke",
        tokens_target=100_000,
        sources=sources,
        domain_mix={"philosophy_history_epistemology": 1.0},
        language_mix={"en": 1.0},
    )
    assert manifest["manifest_id"] == "corpus:seed-v0:smoke-001"
    assert manifest["manifest_sha256"].startswith("sha256:")
    assert manifest["sources"][0]["source_id"] == "gutenberg:1342"


def test_build_manifest_rejects_bad_mix():
    with pytest.raises(ValueError, match="domain_mix"):
        build_manifest(
            manifest_id="corpus:bad",
            stage="smoke",
            tokens_target=100,
            sources=[],
            domain_mix={"a": 0.4, "b": 0.4},  # sums to 0.8
            language_mix={"en": 1.0},
        )


def test_save_load_round_trip(tmp_path):
    sources = [
        CorpusSourceSpec(
            source_id="x",
            license_class="A",
            language="en",
            domain="general_replay",
        )
    ]
    manifest = build_manifest(
        manifest_id="corpus:seed-v0:smoke-002",
        stage="smoke",
        tokens_target=10_000,
        sources=sources,
        domain_mix={"general_replay": 1.0},
        language_mix={"en": 1.0},
    )
    p = save_manifest(manifest, tmp_path / "manifest.json")
    loaded = load_manifest(p)
    assert loaded["manifest_sha256"] == manifest["manifest_sha256"]


def test_phase1a_template_mixes_sum_to_1():
    domain = SeedCorpusV0Templates.phase1a_domain_mix()
    language = SeedCorpusV0Templates.phase1a_language_mix()
    assert abs(sum(domain.values()) - 1.0) < 0.001
    assert abs(sum(language.values()) - 1.0) < 0.001

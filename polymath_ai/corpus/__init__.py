"""Seed Corpus v0 manifests, license decomposition, OCR provenance.

PRD §Seed Corpus v0 Specification: every chunk has a license class
(A/B/C/D/E); only A and B enter default training. C requires a decision
record. D and E are excluded.

This package builds and audits manifests and emits ``CorpusManifest``
records that pass ``CORPUS_MANIFEST_SCHEMA``. Bulk corpus content is never
stored in the repo - only manifests and tiny fixtures.
"""
from polymath_ai.corpus.license_classes import (
    LICENSE_CLASS_DESCRIPTIONS,
    LICENSE_CLASSES_ALLOWED_DEFAULT,
    audit_license,
    classify_source,
)
from polymath_ai.corpus.manifest import (
    CorpusSourceSpec,
    SeedCorpusV0Templates,
    build_manifest,
    save_manifest,
    load_manifest,
)
from polymath_ai.corpus.fertility import (
    FertilityResult,
    fertility_report,
    summarize_fertility,
)

__all__ = [
    "LICENSE_CLASS_DESCRIPTIONS",
    "LICENSE_CLASSES_ALLOWED_DEFAULT",
    "audit_license",
    "classify_source",
    "CorpusSourceSpec",
    "SeedCorpusV0Templates",
    "build_manifest",
    "save_manifest",
    "load_manifest",
    "FertilityResult",
    "fertility_report",
    "summarize_fertility",
]

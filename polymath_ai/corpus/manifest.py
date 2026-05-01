"""Seed Corpus v0 manifest builder + per-stage templates.

The repo carries manifests, not bulk text. ``build_manifest`` returns a
record that conforms to ``CORPUS_MANIFEST_SCHEMA``. Bulk shards live on
private Hugging Face under Architect-Prime; the manifest references them by
``source_id`` + ``uri`` and never embeds text.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Sequence

from polymath_ai._version import SCHEMA_VERSION
from polymath_ai.boundary.text import boundary_envelope
from polymath_ai.corpus.license_classes import LICENSE_CLASSES_ALLOWED_DEFAULT
from polymath_ai.utils.canonical import canonical_json, hash_mapping


@dataclasses.dataclass
class CorpusSourceSpec:
    """A single corpus source.

    Notes:
      * ``license_class`` must be ``A``..``E``.
      * ``language`` uses ISO 639-1 / 639-3 codes.
      * ``domain`` matches the PRD domain mix keys.
      * ``ocr_provenance_id`` is required when text was OCR-derived.
    """

    source_id: str
    license_class: str
    language: str
    domain: str
    uri: Optional[str] = None
    license_attestation_id: Optional[str] = None
    ocr_provenance_id: Optional[str] = None
    tokens_estimate: Optional[int] = None
    chunk_count: Optional[int] = None
    notes: Optional[str] = None

    def to_record(self) -> dict:
        return {
            "source_id": self.source_id,
            "uri": self.uri,
            "license_class": self.license_class,
            "license_attestation_id": self.license_attestation_id,
            "language": self.language,
            "domain": self.domain,
            "ocr_provenance_id": self.ocr_provenance_id,
            "tokens_estimate": self.tokens_estimate,
            "chunk_count": self.chunk_count,
            "notes": self.notes,
        }


_DOMAIN_MIX_PHASE1A: Mapping[str, float] = {
    "cs_ml_systems_mobile_compute": 0.15,
    "math_formal_reasoning": 0.12,
    "physics_engineering": 0.12,
    "biology_chemistry_materials_energy_synbio": 0.12,
    "music_audio_signal_processing": 0.12,
    "philosophy_history_epistemology": 0.10,
    "linguistics_language_translation": 0.10,
    "code_technical_docs_permissive": 0.10,
    "general_replay": 0.07,
}

# PRD §Seed Corpus > Language Mix gives group-level targets; this is the
# concrete per-language allocation that sums to 1.0 by construction.
# Anchor (en) 30% + High-resource European 25% + CJK 15% +
# Arabic/Russian/Hindi 15% + African/low-resource 10% + Classical 5% = 100%.
_LANGUAGE_MIX_PHASE1A: Mapping[str, float] = {
    "en": 0.30,                     # 30%  anchor + replay + domain depth
    # High-resource European languages (25% group)
    "fr": 0.07,
    "es": 0.06,
    "de": 0.06,
    "it": 0.03,
    "pt": 0.03,
    # CJK (15% group)
    "zh": 0.07,
    "ja": 0.05,
    "ko": 0.03,
    # Arabic, Russian, Hindi (15% group)
    "ar": 0.05,
    "ru": 0.05,
    "hi": 0.05,
    # African + low-resource (10% group)
    "sw": 0.04,
    "zu": 0.03,
    "af": 0.03,
    # Classical (5% group)
    "la": 0.025,
    "el": 0.025,                    # Classical or Modern Greek slice
}


@dataclasses.dataclass
class SeedCorpusV0Templates:
    """Hard-coded mix targets per stage from PRD §Seed Corpus v0."""

    @staticmethod
    def smoke_domain_mix() -> Mapping[str, float]:
        return {
            "general_replay": 0.5,
            "philosophy_history_epistemology": 0.25,
            "music_audio_signal_processing": 0.25,
        }

    @staticmethod
    def smoke_language_mix() -> Mapping[str, float]:
        return {"en": 1.0}

    @staticmethod
    def phase1a_domain_mix() -> Mapping[str, float]:
        return dict(_DOMAIN_MIX_PHASE1A)

    @staticmethod
    def phase1a_language_mix() -> Mapping[str, float]:
        return dict(_LANGUAGE_MIX_PHASE1A)


def build_manifest(
    *,
    manifest_id: str,
    stage: str,
    tokens_target: int,
    sources: Sequence[CorpusSourceSpec],
    domain_mix: Optional[Mapping[str, float]] = None,
    language_mix: Optional[Mapping[str, float]] = None,
    license_classes_allowed: Sequence[str] = LICENSE_CLASSES_ALLOWED_DEFAULT,
) -> dict:
    """Construct a corpus manifest record."""
    domain_mix = domain_mix or {}
    language_mix = language_mix or {}
    source_records = [s.to_record() for s in sources]

    if abs(sum(domain_mix.values()) - 1.0) > 0.001 and domain_mix:
        raise ValueError(f"domain_mix does not sum to 1: {sum(domain_mix.values())}")
    if abs(sum(language_mix.values()) - 1.0) > 0.001 and language_mix:
        raise ValueError(f"language_mix does not sum to 1: {sum(language_mix.values())}")

    body = {
        "manifest_id": manifest_id,
        "stage": stage,
        "tokens_target": int(tokens_target),
        "domain_mix": dict(domain_mix),
        "language_mix": dict(language_mix),
        "license_classes_allowed": list(license_classes_allowed),
        "sources": source_records,
    }
    manifest_sha256 = hash_mapping(body)
    return {
        "schema_version": SCHEMA_VERSION,
        "boundary": boundary_envelope(),
        "manifest_id": manifest_id,
        "manifest_sha256": manifest_sha256,
        "stage": stage,
        "tokens_target": int(tokens_target),
        "domain_mix": dict(domain_mix),
        "language_mix": dict(language_mix),
        "license_classes_allowed": list(license_classes_allowed),
        "sources": source_records,
    }


def save_manifest(manifest: Mapping, path: str | os.PathLike[str]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(canonical_json(manifest))
    return str(p)


def load_manifest(path: str | os.PathLike[str]) -> dict:
    return json.loads(Path(path).read_text())

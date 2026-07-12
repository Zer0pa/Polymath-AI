"""Fail-closed, phone-native normalization for frozen CUR-0S sources.

The parsers in this module use only the Python standard library.  They emit a
single canonical :class:`SourceUnit` schema while retaining exact source,
release, rights, member, and record provenance.  They deliberately make no
claim about semantic admission, connected splits, authority, learning, or the
CUR-0S gate.  Those remain downstream decisions.

Every parser is bounded by :class:`ParserLimits`.  Archive paths, links,
encrypted entries, XML DTD/entity declarations, ambiguous identifiers, and
unsupported Turtle grammar fail closed instead of being silently repaired.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import codecs
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
import struct
import tarfile
import tempfile
from typing import Any, BinaryIO, Callable, Iterable, Iterator, Mapping, Sequence
import unicodedata
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET
import xml.parsers.expat as expat
import zipfile


SOURCE_UNIT_SCHEMA = "cur0s_source_unit_v2"
PRODUCTION_VERIFICATION_SCHEMA = "cur0s_production_source_verification_v1"
VERIFIED_SOURCE_UNIT_ENVELOPE_SCHEMA = "cur0s_verified_source_unit_envelope_v1"
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
RUN_ID_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z_cur0s_commercial_sources_v1$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#?%+@=~-]*$")
NUMERIC_RE = re.compile(r"\d")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
XML_FORBIDDEN_RE = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)

PHONE_PACKAGE_ROOT = Path("/data/data/com.termux")
PHONE_HOME = PHONE_PACKAGE_ROOT / "files" / "home"
PHONE_RUN_ROOT = PHONE_HOME / "polymath_gemma4_e4b_frontier"
EXPECTED_PARENT_CAPSULE_SHA256 = (
    "sha256:e6905f36fa526e15a0a1d8ac4eadbf670061a2837fea9a7ac51a1df6bb608f15"
)
EXPECTED_PARENT_FRONTIER_ROOT_SHA256 = (
    "sha256:d118000d8fd457962f2332f2597bb25f6c6e33ee61010f5cd1459ab9768235fc"
)
EXPECTED_ACCESS_RECEIPT_SHA256 = (
    "sha256:7b2b6d506b3ab82a17008edc4c79dd51512f6f9598e3db37cd1bb6f5ee4331ca"
)
EXPECTED_BUILD_FINGERPRINT_SHA256 = (
    "sha256:fce358a6cdd6535afbecf6f72088412abaccf9b9902c05800ee8852512f9882f"
)
EXPECTED_ADB_SERIAL_SHA256 = (
    "sha256:383e1fef6040334134430241a105f7d900f6d924e485fdc858441e734d3ae0f4"
)
BOUND_SOURCE_FILES = (
    "polymath_ai/corpus/cur0s_commercial_sources.py",
    "scripts/termux/run_cur0s_commercial_sources.py",
)

RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
SKOS_NS = "http://www.w3.org/2004/02/skos/core#"
XML_NS = "http://www.w3.org/XML/1998/namespace"
EPUB_CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
EPUB_OPF_NS = "http://www.idpf.org/2007/opf"
XHTML_NS = "http://www.w3.org/1999/xhtml"
DC_NS = "http://purl.org/dc/elements/1.1/"
EPUB_OPS_NS = "http://www.idpf.org/2007/ops"
MATHML_NS = "http://www.w3.org/1998/Math/MathML"
SVG_NS = "http://www.w3.org/2000/svg"
CNXML_NS = "http://cnx.rice.edu/cnxml"
COLLXML_NS = "http://cnx.rice.edu/collxml"

_RDF_SEMANTIC_NAMESPACES = {
    "RDF": RDF_NS,
    "Description": RDF_NS,
    "type": RDF_NS,
    "Concept": SKOS_NS,
    "prefLabel": SKOS_NS,
    "altLabel": SKOS_NS,
    "definition": SKOS_NS,
    "scopeNote": SKOS_NS,
    "note": SKOS_NS,
    "broader": SKOS_NS,
}
_EPUB_CONTAINER_NAMESPACES = {
    "container": EPUB_CONTAINER_NS,
    "rootfiles": EPUB_CONTAINER_NS,
    "rootfile": EPUB_CONTAINER_NS,
}
_EPUB_OPF_NAMESPACES = {
    "package": EPUB_OPF_NS,
    "metadata": EPUB_OPF_NS,
    "manifest": EPUB_OPF_NS,
    "item": EPUB_OPF_NS,
    "spine": EPUB_OPF_NS,
    "itemref": EPUB_OPF_NS,
    "meta": EPUB_OPF_NS,
    "creator": DC_NS,
    "identifier": DC_NS,
    "language": DC_NS,
    "publisher": DC_NS,
    "rights": DC_NS,
    "subject": DC_NS,
    "title": DC_NS,
}
_CNXML_SEMANTIC_NAMESPACES = {
    "document": CNXML_NS,
    "content-id": CNXML_NS,
    "content": CNXML_NS,
}
_COLLXML_SEMANTIC_NAMESPACES = {
    "collection": COLLXML_NS,
    "content": COLLXML_NS,
    "module": COLLXML_NS,
}

_TURTLE_RDF_TYPE = RDF_NS + "type"
_TURTLE_SKOS_CONCEPT = SKOS_NS + "Concept"
_TURTLE_LABEL_PROPERTIES = {
    SKOS_NS + "prefLabel": "pref",
    SKOS_NS + "altLabel": "alt",
    SKOS_NS + "hiddenLabel": "hidden",
}
_TURTLE_TEXT_PROPERTIES = {
    SKOS_NS + "definition": "definition",
    SKOS_NS + "scopeNote": "scope_note",
    SKOS_NS + "note": "note",
}


class SourceParseError(RuntimeError):
    """A source is malformed, unsafe, ambiguous, or exceeds a frozen bound."""


@dataclass(frozen=True)
class ParserLimits:
    """Hard resource bounds shared by all source parsers."""

    max_source_bytes: int = 512 * 1024 * 1024
    max_archive_members: int = 100_000
    max_archive_uncompressed_bytes: int = 2 * 1024 * 1024 * 1024
    max_member_bytes: int = 384 * 1024 * 1024
    max_compression_ratio: float = 1_000.0
    max_files: int = 100_000
    max_line_bytes: int = 2 * 1024 * 1024
    max_statement_chars: int = 2 * 1024 * 1024
    max_field_chars: int = 2 * 1024 * 1024
    max_unit_text_chars: int = 4 * 1024 * 1024
    max_synonyms_per_unit: int = 8_192
    max_edges_per_unit: int = 8_192
    max_units: int = 1_000_000
    max_xml_depth: int = 128
    max_xml_elements: int = 2_000_000
    max_openstax_xml_bytes: int = 64 * 1024 * 1024
    max_spool_bytes: int = 8 * 1024 * 1024 * 1024

    def validate(self) -> None:
        values = asdict(self)
        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise SourceParseError(f"invalid_limit_type:{name}")
            if not math.isfinite(float(value)) or value <= 0:
                raise SourceParseError(f"invalid_limit_value:{name}")


DEFAULT_LIMITS = ParserLimits()


@dataclass(frozen=True)
class ParseContext:
    """Low-level parse identity; authoritative callers must not construct it.

    The production entry point derives this value from the exact acquisition
    receipt, completion marker, source root, and frozen source contract.  The
    low-level parsers accept manually constructed contexts only for isolated
    fixtures and diagnostics and make no acquisition-authority claim.
    """

    source_id: str
    release_identity: str
    source_sha256: str
    source_locator: str
    license_id: str
    license_class: str
    rights_proof: str
    source_manifest_json: str | None = None

    def validate(self, limits: ParserLimits = DEFAULT_LIMITS) -> None:
        limits.validate()
        _validate_identifier(self.source_id, "source_id", limits)
        _validate_scalar(self.release_identity, "release_identity", limits)
        _validate_scalar(self.source_locator, "source_locator", limits)
        _validate_scalar(self.license_id, "license_id", limits)
        _validate_scalar(self.rights_proof, "rights_proof", limits)
        if not SHA256_RE.fullmatch(self.source_sha256):
            raise SourceParseError("invalid_source_sha256")
        if self.license_class not in {"A", "B"}:
            raise SourceParseError("inadmissible_license_class")
        if self.source_manifest_json is not None:
            manifest = _decode_exact_canonical_contract_json(
                self.source_manifest_json,
                "source_manifest",
            )
            if _contract_canonical_sha256(manifest) != self.source_sha256:
                raise SourceParseError("source_manifest_sha256_mismatch")


@dataclass(frozen=True, order=True)
class SourceEdge:
    """A normalized intra-source hierarchy or prerequisite edge."""

    edge_type: str
    predicate: str
    target_source_key: str
    target_unit_id: str


@dataclass(frozen=True)
class SourceFlags:
    """Mechanical flags only; no semantic-quality conclusion is implied."""

    missing_media: bool
    has_table: bool
    has_numeric_content: bool
    present_visual_media: bool
    uninterpreted_nontext_media: bool
    visual_context_quarantined: bool


def _validate_source_flags(flags: SourceFlags) -> SourceFlags:
    values = asdict(flags)
    if any(type(value) is not bool for value in values.values()):
        raise SourceParseError("source_flags_boolean_invalid")
    if (flags.present_visual_media and not flags.uninterpreted_nontext_media) or (
        (flags.missing_media or flags.uninterpreted_nontext_media)
        and not flags.visual_context_quarantined
    ):
        raise SourceParseError("source_flags_media_quarantine_invariant_invalid")
    return flags


@dataclass(frozen=True, order=True)
class SourceFacet:
    """Selection-critical source metadata retained without interpretation."""

    name: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class RightsRecord:
    license_id: str
    license_class: str
    rights_proof: str


@dataclass(frozen=True)
class ProvenanceRecord:
    source_id: str
    release_identity: str
    source_sha256: str
    source_locator: str
    source_member: str
    record_locator: str
    record_sha256: str
    record_digest_scope: str


@dataclass(frozen=True)
class SourceUnit:
    """Canonical normalized record emitted by every frozen source parser."""

    schema: str
    unit_id: str
    source_key: str
    kind: str
    title: str
    text: str
    definition: str | None
    synonyms: tuple[str, ...]
    facets: tuple[SourceFacet, ...]
    edges: tuple[SourceEdge, ...]
    flags: SourceFlags
    rights: RightsRecord
    provenance: ProvenanceRecord
    canonical_sha256: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["synonyms"] = list(self.synonyms)
        value["facets"] = [asdict(facet) for facet in self.facets]
        value["edges"] = [asdict(edge) for edge in self.edges]
        return value


@dataclass(frozen=True)
class ProductionVerificationRecord:
    """Receipt-derived authority retained beside every production unit."""

    schema_version: str
    production_transaction_verified: bool
    run_id: str
    candidate_id: str
    source_id: str
    receipt_sha256: str
    receipt_root_sha256: str
    completion_sha256: str
    source_root_sha256: str
    source_artifact_sha256: str
    commercial_source_contract_root_sha256: str
    execution_claim_sha256: str
    preregistration_sha256: str
    native_manifest_sha256: str
    native_launch_envelope_sha256: str
    native_build_receipt_sha256: str
    native_binary_sha256: str
    source_commit: str
    verification_scope: str
    verification_root_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerifiedSourceUnitEnvelope:
    """Mandatory production envelope; low-level ``ParseContext`` cannot mint it."""

    schema_version: str
    unit: SourceUnit
    production_verification: ProductionVerificationRecord
    envelope_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "unit": self.unit.to_dict(),
            "production_verification": self.production_verification.to_dict(),
            "envelope_sha256": self.envelope_sha256,
        }


@dataclass(frozen=True)
class ProductionAuthorityExpectation:
    """Out-of-band host-ledger anchors required for production parsing.

    The preregistration digest is frozen before the one-shot phone action.  The
    receipt digest is added to the host evidence ledger after aggregate-only
    retrieval and before semantic compilation.  Neither value is accepted from
    the phone transaction that it authenticates.
    """

    preregistration_sha256: str
    acquisition_receipt_sha256: str

    def validate(self) -> None:
        if not isinstance(self, ProductionAuthorityExpectation):
            raise SourceParseError("production_authority_expectation_required")
        _require_sha256(
            self.preregistration_sha256,
            "expected_preregistration_sha256_invalid",
        )
        _require_sha256(
            self.acquisition_receipt_sha256,
            "expected_acquisition_receipt_sha256_invalid",
        )


def validate_source_unit(
    unit: SourceUnit,
    expected_context: ParseContext | None = None,
) -> SourceUnit:
    """Recompute identity fields and, when supplied, enforce exact binding.

    Validation without ``expected_context`` is structural only and is not an
    authority check.  Production parsing always supplies its receipt-derived
    context before a record is committed to the all-or-nothing spool.
    """

    if not isinstance(unit, SourceUnit) or unit.schema != SOURCE_UNIT_SCHEMA:
        raise SourceParseError("source_unit_schema_mismatch")
    if (
        not isinstance(unit.rights, RightsRecord)
        or not isinstance(unit.provenance, ProvenanceRecord)
        or not isinstance(unit.flags, SourceFlags)
        or not isinstance(unit.edges, tuple)
        or any(not isinstance(edge, SourceEdge) for edge in unit.edges)
    ):
        raise SourceParseError("source_unit_structure_invalid")
    scalar_values = (
        unit.unit_id,
        unit.source_key,
        unit.kind,
        unit.title,
        unit.text,
        unit.canonical_sha256,
    )
    if (
        any(not isinstance(value, str) or not value for value in scalar_values)
        or (unit.definition is not None and not isinstance(unit.definition, str))
        or not isinstance(unit.synonyms, tuple)
        or any(not isinstance(value, str) or not value for value in unit.synonyms)
        or not isinstance(unit.facets, tuple)
        or any(not isinstance(facet, SourceFacet) for facet in unit.facets)
    ):
        raise SourceParseError("source_unit_structure_invalid")
    if (
        tuple(sorted(set(unit.synonyms))) != unit.synonyms
        or any(
            not isinstance(facet.name, str)
            or not facet.name
            or not isinstance(facet.values, tuple)
            or any(not isinstance(value, str) or not value for value in facet.values)
            or tuple(sorted(set(facet.values))) != facet.values
            for facet in unit.facets
        )
        or tuple(sorted(unit.facets)) != unit.facets
        or len({facet.name for facet in unit.facets}) != len(unit.facets)
        or any(
            type(value) is not bool
            for value in (
                unit.flags.missing_media,
                unit.flags.has_table,
                unit.flags.has_numeric_content,
            )
        )
    ):
        raise SourceParseError("source_unit_canonical_structure_invalid")
    rights_values = (
        unit.rights.license_id,
        unit.rights.license_class,
        unit.rights.rights_proof,
    )
    if any(
        not isinstance(value, str) or not value for value in rights_values
    ) or unit.rights.license_class not in {"A", "B"}:
        raise SourceParseError("source_unit_rights_structure_invalid")
    provenance_values = (
        unit.provenance.source_id,
        unit.provenance.release_identity,
        unit.provenance.source_locator,
        unit.provenance.source_member,
        unit.provenance.record_locator,
    )
    if (
        any(not isinstance(value, str) or not value for value in provenance_values)
        or unit.provenance.record_digest_scope != "normalized_record_v1"
    ):
        raise SourceParseError("source_unit_record_scope_invalid")
    expected_id = stable_unit_id(
        unit.provenance.source_id,
        unit.provenance.release_identity,
        unit.source_key,
    )
    if unit.unit_id != expected_id:
        raise SourceParseError("source_unit_id_mismatch")
    if not isinstance(unit.provenance.source_sha256, str) or not SHA256_RE.fullmatch(
        unit.provenance.source_sha256
    ):
        raise SourceParseError("source_unit_provenance_sha256_invalid")
    if not isinstance(unit.provenance.record_sha256, str) or not SHA256_RE.fullmatch(
        unit.provenance.record_sha256
    ):
        raise SourceParseError("source_unit_record_sha256_invalid")
    for edge in unit.edges:
        if (
            edge.edge_type not in {"hierarchy", "prerequisite"}
            or not all(
                isinstance(value, str) and value
                for value in (
                    edge.predicate,
                    edge.target_source_key,
                    edge.target_unit_id,
                )
            )
            or edge.target_unit_id
            != stable_unit_id(
                unit.provenance.source_id,
                unit.provenance.release_identity,
                edge.target_source_key,
            )
        ):
            raise SourceParseError("source_unit_edge_target_binding_invalid")
    if tuple(sorted(set(unit.edges))) != unit.edges:
        raise SourceParseError("source_unit_edge_canonicalization_invalid")
    body = unit.to_dict()
    observed = body.pop("canonical_sha256")
    if observed != canonical_sha256(body):
        raise SourceParseError("source_unit_canonical_sha256_mismatch")
    if expected_context is not None:
        expected_context.validate()
        expected_rights = RightsRecord(
            expected_context.license_id,
            expected_context.license_class,
            expected_context.rights_proof,
        )
        expected_provenance = {
            "source_id": expected_context.source_id,
            "release_identity": expected_context.release_identity,
            "source_sha256": expected_context.source_sha256,
            "source_locator": expected_context.source_locator,
        }
        if unit.rights != expected_rights:
            raise SourceParseError("source_unit_rights_binding_mismatch")
        if any(
            getattr(unit.provenance, field) != value
            for field, value in expected_provenance.items()
        ):
            raise SourceParseError("source_unit_provenance_binding_mismatch")
    return unit


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize a JSON tree identically across supported Python runtimes."""

    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def canonical_sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _contract_canonical_json_bytes(value: Any) -> bytes:
    """Match the acquisition contract's canonical JSON (without newline)."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _contract_canonical_sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_contract_canonical_json_bytes(value)).hexdigest()


def _reject_duplicate_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SourceParseError("duplicate_json_key")
        result[key] = value
    return result


def _decode_exact_canonical_contract_json(value: str, field: str) -> Any:
    if not isinstance(value, str) or not value:
        raise SourceParseError(f"{field}_invalid")
    try:
        decoded = json.loads(value, object_pairs_hook=_reject_duplicate_json_object)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise SourceParseError(f"{field}_invalid") from exc
    try:
        canonical = _contract_canonical_json_bytes(decoded).decode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise SourceParseError(f"{field}_invalid") from exc
    if canonical != value:
        raise SourceParseError(f"{field}_not_canonical")
    return decoded


def stable_unit_id(source_id: str, release_identity: str, source_key: str) -> str:
    """Return an identity hash independent of physical paths and parse order."""

    identity = {
        "release_identity": release_identity,
        "source_id": source_id,
        "source_key": source_key,
    }
    return (
        "urn:cur0s:source-unit:"
        + hashlib.sha256(canonical_json_bytes(identity)).hexdigest()
    )


def _validate_scalar(value: str, name: str, limits: ParserLimits) -> str:
    if not isinstance(value, str):
        raise SourceParseError(f"invalid_scalar_type:{name}")
    normalized = unicodedata.normalize("NFC", value)
    if not normalized or len(normalized) > limits.max_field_chars:
        raise SourceParseError(f"invalid_scalar_length:{name}")
    if CONTROL_RE.search(normalized):
        raise SourceParseError(f"control_character:{name}")
    return normalized


def _validate_identifier(value: str, name: str, limits: ParserLimits) -> str:
    normalized = _validate_scalar(value, name, limits)
    if not IDENTIFIER_RE.fullmatch(normalized):
        raise SourceParseError(f"invalid_identifier:{name}")
    return normalized


def _normalize_inline(value: str, name: str, limits: ParserLimits) -> str:
    value = _validate_scalar(value, name, limits)
    normalized = " ".join(value.split())
    if not normalized:
        raise SourceParseError(f"empty_normalized_field:{name}")
    return normalized


def _normalize_text(value: str, limits: ParserLimits) -> str:
    value = unicodedata.normalize(
        "NFC", value.replace("\r\n", "\n").replace("\r", "\n")
    )
    if CONTROL_RE.search(value):
        raise SourceParseError("control_character:text")
    paragraphs = [" ".join(part.split()) for part in value.split("\n")]
    normalized = "\n".join(part for part in paragraphs if part)
    if not normalized:
        raise SourceParseError("empty_normalized_field:text")
    if len(normalized) > limits.max_unit_text_chars:
        raise SourceParseError("unit_text_limit_exceeded")
    return normalized


def _record_sha256(value: Any) -> str:
    return canonical_sha256({"digest_scope": "normalized_record_v1", "record": value})


def _make_edge(
    context: ParseContext,
    edge_type: str,
    predicate: str,
    target_source_key: str,
    limits: ParserLimits,
) -> SourceEdge:
    if edge_type not in {"hierarchy", "prerequisite"}:
        raise SourceParseError("invalid_edge_type")
    predicate = _validate_identifier(predicate, "edge_predicate", limits)
    target_source_key = _validate_scalar(
        target_source_key, "edge_target_source_key", limits
    )
    return SourceEdge(
        edge_type=edge_type,
        predicate=predicate,
        target_source_key=target_source_key,
        target_unit_id=stable_unit_id(
            context.source_id, context.release_identity, target_source_key
        ),
    )


def _make_unit(
    *,
    context: ParseContext,
    source_key: str,
    kind: str,
    title: str,
    text: str,
    synonyms: Iterable[str],
    edges: Iterable[SourceEdge],
    flags: SourceFlags,
    source_member: str,
    record_locator: str,
    record_value: Any,
    limits: ParserLimits,
    definition: str | None = None,
    facets: Mapping[str, Iterable[str]] | None = None,
) -> SourceUnit:
    context.validate(limits)
    flags = _validate_source_flags(flags)
    source_key = _validate_scalar(source_key, "source_key", limits)
    kind = _validate_identifier(kind, "kind", limits)
    title = _normalize_inline(title, "title", limits)
    text = _normalize_text(text, limits)
    if definition is not None:
        definition = _normalize_text(definition, limits)
    source_member = _validate_scalar(source_member, "source_member", limits)
    record_locator = _validate_scalar(record_locator, "record_locator", limits)

    normalized_synonyms = tuple(
        sorted(
            {
                _normalize_inline(value, "synonym", limits)
                for value in synonyms
                if value and " ".join(value.split()) != title
            }
        )
    )
    if len(normalized_synonyms) > limits.max_synonyms_per_unit:
        raise SourceParseError("synonym_limit_exceeded")
    normalized_facets: list[SourceFacet] = []
    facet_value_count = 0
    for name, values in sorted((facets or {}).items()):
        facet_name = _validate_identifier(name, "facet_name", limits)
        facet_values = tuple(
            sorted(
                {_normalize_inline(value, "facet_value", limits) for value in values}
            )
        )
        if not facet_values:
            continue
        facet_value_count += len(facet_values)
        if facet_value_count > limits.max_edges_per_unit:
            raise SourceParseError("facet_value_limit_exceeded")
        normalized_facets.append(SourceFacet(facet_name, facet_values))
    if len(normalized_facets) > limits.max_edges_per_unit:
        raise SourceParseError("facet_limit_exceeded")
    normalized_edges = tuple(sorted(set(edges)))
    if len(normalized_edges) > limits.max_edges_per_unit:
        raise SourceParseError("edge_limit_exceeded")

    unit_id = stable_unit_id(context.source_id, context.release_identity, source_key)
    body: dict[str, Any] = {
        "schema": SOURCE_UNIT_SCHEMA,
        "unit_id": unit_id,
        "source_key": source_key,
        "kind": kind,
        "title": title,
        "text": text,
        "definition": definition,
        "synonyms": list(normalized_synonyms),
        "facets": [asdict(facet) for facet in normalized_facets],
        "edges": [asdict(edge) for edge in normalized_edges],
        "flags": asdict(flags),
        "rights": {
            "license_id": context.license_id,
            "license_class": context.license_class,
            "rights_proof": context.rights_proof,
        },
        "provenance": {
            "source_id": context.source_id,
            "release_identity": context.release_identity,
            "source_sha256": context.source_sha256,
            "source_locator": context.source_locator,
            "source_member": source_member,
            "record_locator": record_locator,
            "record_sha256": _record_sha256(record_value),
            "record_digest_scope": "normalized_record_v1",
        },
    }
    return SourceUnit(
        schema=SOURCE_UNIT_SCHEMA,
        unit_id=unit_id,
        source_key=source_key,
        kind=kind,
        title=title,
        text=text,
        definition=definition,
        synonyms=normalized_synonyms,
        facets=tuple(normalized_facets),
        edges=normalized_edges,
        flags=flags,
        rights=RightsRecord(**body["rights"]),
        provenance=ProvenanceRecord(**body["provenance"]),
        canonical_sha256=canonical_sha256(body),
    )


def _stat_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_uid,
        metadata.st_gid,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _hash_regular_fd(fd: int, limit: int, error_prefix: str) -> tuple[str, int]:
    try:
        original_offset = os.lseek(fd, 0, os.SEEK_CUR)
        os.lseek(fd, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise SourceParseError(f"{error_prefix}_size_limit_exceeded")
            digest.update(chunk)
        os.lseek(fd, original_offset, os.SEEK_SET)
    except OSError as exc:
        raise SourceParseError(f"{error_prefix}_read_failed") from exc
    return "sha256:" + digest.hexdigest(), total


def _open_regular_path_fd(
    path: str | os.PathLike[str],
    limits: ParserLimits,
) -> tuple[int, str]:
    limits.validate()
    value = os.fspath(path)
    try:
        fd = os.open(
            value,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
    except OSError as exc:
        raise SourceParseError("source_open_no_follow_failed") from exc
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise SourceParseError("source_not_regular_file")
        if metadata.st_size > limits.max_source_bytes:
            raise SourceParseError("source_size_limit_exceeded")
    except Exception:
        os.close(fd)
        raise
    return fd, Path(value).name


def _initial_regular_file_binding(
    fd: int,
    context: ParseContext,
    limits: ParserLimits,
) -> tuple[tuple[int, ...], str, int]:
    context.validate(limits)
    try:
        before = os.fstat(fd)
    except OSError as exc:
        raise SourceParseError("source_stat_failed") from exc
    if not stat.S_ISREG(before.st_mode):
        raise SourceParseError("source_not_regular_file")
    if before.st_size > limits.max_source_bytes:
        raise SourceParseError("source_size_limit_exceeded")
    digest, byte_count = _hash_regular_fd(fd, limits.max_source_bytes, "source")
    try:
        after = os.fstat(fd)
    except OSError as exc:
        raise SourceParseError("source_stat_failed") from exc
    if _stat_identity(before) != _stat_identity(after) or byte_count != before.st_size:
        raise SourceParseError("source_changed_during_initial_hash")
    if digest != context.source_sha256:
        raise SourceParseError("source_context_sha256_mismatch")
    return _stat_identity(after), digest, byte_count


def _reattest_regular_file_binding(
    fd: int,
    expected_identity: tuple[int, ...],
    expected_digest: str,
    expected_bytes: int,
    limits: ParserLimits,
) -> None:
    try:
        before = os.fstat(fd)
    except OSError as exc:
        raise SourceParseError("source_stat_failed") from exc
    digest, byte_count = _hash_regular_fd(fd, limits.max_source_bytes, "source")
    try:
        after = os.fstat(fd)
    except OSError as exc:
        raise SourceParseError("source_stat_failed") from exc
    if (
        _stat_identity(before) != expected_identity
        or _stat_identity(after) != expected_identity
        or digest != expected_digest
        or byte_count != expected_bytes
    ):
        raise SourceParseError("source_changed_during_parse")


def _source_unit_from_dict(value: Any) -> SourceUnit:
    if not isinstance(value, dict) or set(value) != {
        "schema",
        "unit_id",
        "source_key",
        "kind",
        "title",
        "text",
        "definition",
        "synonyms",
        "facets",
        "edges",
        "flags",
        "rights",
        "provenance",
        "canonical_sha256",
    }:
        raise SourceParseError("spooled_source_unit_shape_invalid")
    if not isinstance(value["synonyms"], list) or not all(
        isinstance(item, str) for item in value["synonyms"]
    ):
        raise SourceParseError("spooled_source_unit_synonyms_invalid")
    facets = value["facets"]
    if not isinstance(facets, list) or any(
        not isinstance(item, dict)
        or set(item) != {"name", "values"}
        or not isinstance(item["name"], str)
        or not isinstance(item["values"], list)
        or not all(isinstance(entry, str) for entry in item["values"])
        for item in facets
    ):
        raise SourceParseError("spooled_source_unit_facets_invalid")
    edges = value["edges"]
    if not isinstance(edges, list) or any(
        not isinstance(item, dict)
        or set(item)
        != {"edge_type", "predicate", "target_source_key", "target_unit_id"}
        or not all(isinstance(entry, str) for entry in item.values())
        for item in edges
    ):
        raise SourceParseError("spooled_source_unit_edges_invalid")
    flags = value["flags"]
    rights = value["rights"]
    provenance = value["provenance"]
    if (
        not isinstance(flags, dict)
        or set(flags)
        != {
            "missing_media",
            "has_table",
            "has_numeric_content",
            "present_visual_media",
            "uninterpreted_nontext_media",
            "visual_context_quarantined",
        }
        or any(type(entry) is not bool for entry in flags.values())
        or not isinstance(rights, dict)
        or set(rights) != {"license_id", "license_class", "rights_proof"}
        or not all(isinstance(entry, str) for entry in rights.values())
        or not isinstance(provenance, dict)
        or set(provenance)
        != {
            "source_id",
            "release_identity",
            "source_sha256",
            "source_locator",
            "source_member",
            "record_locator",
            "record_sha256",
            "record_digest_scope",
        }
        or not all(isinstance(entry, str) for entry in provenance.values())
    ):
        raise SourceParseError("spooled_source_unit_binding_invalid")
    scalar_fields = (
        "schema",
        "unit_id",
        "source_key",
        "kind",
        "title",
        "text",
        "canonical_sha256",
    )
    if any(not isinstance(value[field], str) for field in scalar_fields) or (
        value["definition"] is not None and not isinstance(value["definition"], str)
    ):
        raise SourceParseError("spooled_source_unit_scalar_invalid")
    parsed_flags = _validate_source_flags(SourceFlags(**flags))
    return SourceUnit(
        schema=value["schema"],
        unit_id=value["unit_id"],
        source_key=value["source_key"],
        kind=value["kind"],
        title=value["title"],
        text=value["text"],
        definition=value["definition"],
        synonyms=tuple(value["synonyms"]),
        facets=tuple(
            SourceFacet(item["name"], tuple(item["values"])) for item in facets
        ),
        edges=tuple(SourceEdge(**item) for item in edges),
        flags=parsed_flags,
        rights=RightsRecord(**rights),
        provenance=ProvenanceRecord(**provenance),
        canonical_sha256=value["canonical_sha256"],
    )


def _spool_all_or_nothing(
    units: Iterable[SourceUnit],
    context: ParseContext,
    limits: ParserLimits,
    final_revalidator: Callable[[], None],
) -> Iterator[SourceUnit]:
    """Exhaust and reattest before replaying one bounded disk spool."""

    count = 0
    total = 0
    seen_unit_ids: set[str] = set()
    try:
        spool = tempfile.TemporaryFile(prefix="cur0s-source-units-")
    except OSError as exc:
        raise SourceParseError("source_unit_spool_open_failed") from exc
    with spool:
        try:
            for unit in units:
                validate_source_unit(unit, context)
                if unit.unit_id in seen_unit_ids:
                    raise SourceParseError("duplicate_source_unit_id")
                seen_unit_ids.add(unit.unit_id)
                count += 1
                if count > limits.max_units:
                    raise SourceParseError("unit_limit_exceeded")
                payload = canonical_json_bytes(unit.to_dict())
                framed_bytes = 8 + len(payload)
                total += framed_bytes
                if total > limits.max_spool_bytes:
                    raise SourceParseError("source_unit_spool_limit_exceeded")
                spool.write(struct.pack("!Q", len(payload)))
                spool.write(payload)
            spool.flush()
            os.fsync(spool.fileno())
        except OSError as exc:
            raise SourceParseError("source_unit_spool_write_failed") from exc
        final_revalidator()

        def read_record() -> SourceUnit:
            header = spool.read(8)
            if len(header) != 8:
                raise SourceParseError("source_unit_spool_truncated")
            payload_size = struct.unpack("!Q", header)[0]
            if payload_size <= 0 or payload_size > limits.max_spool_bytes:
                raise SourceParseError("source_unit_spool_record_invalid")
            payload = spool.read(payload_size)
            if len(payload) != payload_size:
                raise SourceParseError("source_unit_spool_truncated")
            value = json.loads(
                payload,
                object_pairs_hook=_reject_duplicate_json_object,
            )
            if canonical_json_bytes(value) != payload:
                raise SourceParseError("source_unit_spool_not_canonical")
            return validate_source_unit(_source_unit_from_dict(value), context)

        try:
            # Prove the entire persisted batch before the first record escapes.
            spool.seek(0)
            for _ in range(count):
                read_record()
            if spool.read(1):
                raise SourceParseError("source_unit_spool_trailing_data")
            spool.seek(0)
            for _ in range(count):
                yield read_record()
            if spool.read(1):
                raise SourceParseError("source_unit_spool_trailing_data")
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise SourceParseError("source_unit_spool_decode_failed") from exc


_RegularHandleParser = Callable[
    [BinaryIO, str, ParseContext, ParserLimits],
    Iterator[SourceUnit],
]


def _iter_held_regular_fd(
    fd: int,
    source_member: str,
    context: ParseContext,
    limits: ParserLimits,
    parser: _RegularHandleParser,
    external_revalidator: Callable[[], None] | None = None,
) -> Iterator[SourceUnit]:
    identity, digest, byte_count = _initial_regular_file_binding(
        fd,
        context,
        limits,
    )

    def parsed_units() -> Iterator[SourceUnit]:
        try:
            duplicate = os.dup(fd)
        except OSError as exc:
            raise SourceParseError("source_fd_duplicate_failed") from exc
        with os.fdopen(duplicate, "rb", closefd=True) as handle:
            handle.seek(0)
            yield from parser(handle, source_member, context, limits)

    def revalidate() -> None:
        _reattest_regular_file_binding(
            fd,
            identity,
            digest,
            byte_count,
            limits,
        )
        if external_revalidator is not None:
            external_revalidator()

    yield from _spool_all_or_nothing(parsed_units(), context, limits, revalidate)


def _iter_regular_path(
    path: str | os.PathLike[str],
    context: ParseContext,
    limits: ParserLimits,
    parser: _RegularHandleParser,
) -> Iterator[SourceUnit]:
    fd, source_member = _open_regular_path_fd(path, limits)
    path_identity = _stat_identity(os.fstat(fd))

    def revalidate_path() -> None:
        reopened, _name = _open_regular_path_fd(path, limits)
        try:
            if _stat_identity(os.fstat(reopened)) != path_identity:
                raise SourceParseError("source_path_changed_during_parse")
        finally:
            os.close(reopened)

    try:
        yield from _iter_held_regular_fd(
            fd,
            source_member,
            context,
            limits,
            parser,
            revalidate_path,
        )
    finally:
        os.close(fd)


def _safe_archive_name(name: str) -> str:
    if not isinstance(name, str) or not name or "\x00" in name or "\\" in name:
        raise SourceParseError("unsafe_archive_path")
    if re.match(r"^[A-Za-z]:", name):
        raise SourceParseError("unsafe_archive_path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise SourceParseError("unsafe_archive_path")
    return path.as_posix().rstrip("/")


def _bounded_utf8_lines(
    handle: BinaryIO, limits: ParserLimits
) -> Iterator[tuple[int, str]]:
    line_number = 0
    while True:
        raw = handle.readline(limits.max_line_bytes + 1)
        if not raw:
            return
        line_number += 1
        if len(raw) > limits.max_line_bytes:
            raise SourceParseError(f"line_limit_exceeded:{line_number}")
        try:
            yield line_number, raw.decode("utf-8", errors="strict").rstrip("\r\n")
        except UnicodeDecodeError as exc:
            raise SourceParseError(f"invalid_utf8:{line_number}") from exc


def _validate_zip(
    handle: BinaryIO, limits: ParserLimits
) -> tuple[zipfile.ZipFile, dict[str, zipfile.ZipInfo]]:
    try:
        handle.seek(0)
        archive = zipfile.ZipFile(handle, "r")
        infos = archive.infolist()
    except (OSError, zipfile.BadZipFile) as exc:
        raise SourceParseError("invalid_zip_archive") from exc
    if len(infos) > limits.max_archive_members:
        archive.close()
        raise SourceParseError("archive_member_limit_exceeded")
    result: dict[str, zipfile.ZipInfo] = {}
    total = 0
    try:
        for info in infos:
            name = _safe_archive_name(info.filename)
            if info.flag_bits & 0x1:
                raise SourceParseError("encrypted_zip_member_rejected")
            if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                raise SourceParseError("unsupported_zip_compression")
            mode = (info.external_attr >> 16) & 0xFFFF
            file_type = stat.S_IFMT(mode) if info.create_system == 3 else 0
            if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise SourceParseError("archive_non_regular_member_rejected")
            if info.is_dir():
                if file_type not in {0, stat.S_IFDIR}:
                    raise SourceParseError("archive_non_regular_member_rejected")
                continue
            if file_type == stat.S_IFDIR:
                raise SourceParseError("archive_non_regular_member_rejected")
            if name in result:
                raise SourceParseError("duplicate_archive_member")
            if info.file_size > limits.max_member_bytes:
                raise SourceParseError("archive_member_size_limit_exceeded")
            total += info.file_size
            if total > limits.max_archive_uncompressed_bytes:
                raise SourceParseError("archive_uncompressed_limit_exceeded")
            if info.file_size:
                if info.compress_size == 0:
                    raise SourceParseError("invalid_zip_compressed_size")
                ratio = info.file_size / info.compress_size
                if ratio > limits.max_compression_ratio:
                    raise SourceParseError("zip_compression_ratio_exceeded")
            result[name] = info
    except Exception:
        archive.close()
        raise
    return archive, result


def _read_zip_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    limits: ParserLimits,
) -> bytes:
    with archive.open(info, "r") as handle:
        value = handle.read(limits.max_member_bytes + 1)
        if len(value) > limits.max_member_bytes or len(value) != info.file_size:
            raise SourceParseError("zip_member_read_size_mismatch")
        if handle.read(1):
            raise SourceParseError("zip_member_trailing_data")
        return value


def _xml_encoding(prefix: bytes) -> str:
    """Infer only XML's deterministic UTF encodings without parser allocation."""

    if prefix.startswith(b"\xff\xfe\x00\x00"):
        return "utf-32"
    if prefix.startswith(b"\x00\x00\xfe\xff"):
        return "utf-32"
    if prefix.startswith(b"\xff\xfe") or prefix.startswith(b"\xfe\xff"):
        return "utf-16"
    if prefix.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if prefix.startswith(b"\x3c\x00\x00\x00"):
        return "utf-32-le"
    if prefix.startswith(b"\x00\x00\x00\x3c"):
        return "utf-32-be"
    if len(prefix) >= 4 and prefix[0] == 0x3C and prefix[1] == 0 and prefix[3] == 0:
        return "utf-16-le"
    if len(prefix) >= 4 and prefix[0] == 0 and prefix[1] == 0x3C and prefix[2] == 0:
        return "utf-16-be"
    return "utf-8"


def _decode_xml_for_scan(value: bytes) -> str:
    try:
        return value.decode(_xml_encoding(value[:4]), errors="strict")
    except UnicodeDecodeError as exc:
        raise SourceParseError("invalid_xml_encoding") from exc


def _reject_xml_bytes(value: bytes) -> None:
    if XML_FORBIDDEN_RE.search(_decode_xml_for_scan(value)):
        raise SourceParseError("xml_dtd_or_entity_rejected")


def _xml_allocation_guard(
    limits: ParserLimits,
    *,
    total_text_limit: int | None = None,
) -> expat.xmlparser:
    parser = expat.ParserCreate()
    depth = 0
    element_count = 0
    text_segment_chars = 0
    total_text_chars = 0

    def start_element(name: str, attributes: dict[str, str]) -> None:
        nonlocal depth, element_count, text_segment_chars
        depth += 1
        element_count += 1
        text_segment_chars = 0
        if depth > limits.max_xml_depth:
            raise SourceParseError("xml_depth_limit_exceeded")
        if element_count > limits.max_xml_elements:
            raise SourceParseError("xml_element_count_limit_exceeded")
        if len(name) > limits.max_field_chars or any(
            len(key) > limits.max_field_chars or len(value) > limits.max_field_chars
            for key, value in attributes.items()
        ):
            raise SourceParseError("xml_attribute_limit_exceeded")

    def end_element(_name: str) -> None:
        nonlocal depth, text_segment_chars
        depth -= 1
        text_segment_chars = 0

    def character_data(value: str) -> None:
        nonlocal text_segment_chars, total_text_chars
        text_segment_chars += len(value)
        total_text_chars += len(value)
        if text_segment_chars > limits.max_field_chars:
            raise SourceParseError("xml_text_limit_exceeded")
        if total_text_limit is not None and total_text_chars > total_text_limit:
            raise SourceParseError("xml_total_text_limit_exceeded")

    def reject_doctype(*_args: Any) -> None:
        raise SourceParseError("xml_dtd_or_entity_rejected")

    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element
    parser.CharacterDataHandler = character_data
    parser.StartDoctypeDeclHandler = reject_doctype
    parser.EntityDeclHandler = reject_doctype
    parser.ExternalEntityRefHandler = lambda *_args: 0
    return parser


def _secure_xml_from_bytes(value: bytes, limits: ParserLimits) -> ET.Element:
    _reject_xml_bytes(value)
    guard = _xml_allocation_guard(
        limits,
        total_text_limit=limits.max_unit_text_chars,
    )
    try:
        for offset in range(0, len(value), 64 * 1024):
            guard.Parse(value[offset : offset + 64 * 1024], False)
        guard.Parse(b"", True)
    except expat.ExpatError as exc:
        raise SourceParseError("malformed_xml") from exc
    try:
        root = ET.fromstring(value)
    except ET.ParseError as exc:
        raise SourceParseError("malformed_xml") from exc
    stack: list[tuple[ET.Element, int]] = [(root, 1)]
    while stack:
        element, depth = stack.pop()
        if depth > limits.max_xml_depth:
            raise SourceParseError("xml_depth_limit_exceeded")
        if element.text and len(element.text) > limits.max_field_chars:
            raise SourceParseError("xml_text_limit_exceeded")
        if element.tail and len(element.tail) > limits.max_field_chars:
            raise SourceParseError("xml_text_limit_exceeded")
        for key, attribute in element.attrib.items():
            if (
                len(key) > limits.max_field_chars
                or len(attribute) > limits.max_field_chars
            ):
                raise SourceParseError("xml_attribute_limit_exceeded")
        stack.extend((child, depth + 1) for child in element)
    return root


def _scan_xml_handle(handle: BinaryIO, limits: ParserLimits) -> None:
    carry = ""
    guard = _xml_allocation_guard(limits)
    try:
        handle.seek(0)
        total = 0
        decoder: codecs.IncrementalDecoder | None = None
        while True:
            chunk = handle.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > limits.max_source_bytes:
                raise SourceParseError("source_size_limit_exceeded")
            if decoder is None:
                decoder = codecs.getincrementaldecoder(_xml_encoding(chunk[:4]))(
                    errors="strict"
                )
            probe = carry + decoder.decode(chunk)
            if XML_FORBIDDEN_RE.search(probe):
                raise SourceParseError("xml_dtd_or_entity_rejected")
            guard.Parse(chunk, False)
            carry = probe[-64:]
        if decoder is not None:
            probe = carry + decoder.decode(b"", final=True)
            if XML_FORBIDDEN_RE.search(probe):
                raise SourceParseError("xml_dtd_or_entity_rejected")
        guard.Parse(b"", True)
        handle.seek(0)
    except UnicodeDecodeError as exc:
        raise SourceParseError("invalid_xml_encoding") from exc
    except OSError as exc:
        raise SourceParseError("source_read_failed") from exc
    except expat.ExpatError as exc:
        raise SourceParseError("malformed_xml") from exc


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _qualified_name(namespace: str, local_name: str) -> str:
    return f"{{{namespace}}}{local_name}"


def _require_qualified_root(
    root: ET.Element,
    namespace: str,
    local_name: str,
    error: str,
) -> None:
    if root.tag != _qualified_name(namespace, local_name):
        raise SourceParseError(error)


def _reject_confusable_namespaces(
    root: ET.Element,
    expected_namespaces: Mapping[str, str],
    error: str,
) -> None:
    for element in root.iter():
        local_name = _local_name(element.tag)
        expected_namespace = expected_namespaces.get(local_name)
        if expected_namespace is None:
            continue
        if element.tag != _qualified_name(expected_namespace, local_name):
            raise SourceParseError(f"{error}:{local_name}")


def _qualified_elements(
    root: ET.Element, namespace: str, local_name: str
) -> Iterator[ET.Element]:
    qualified_name = _qualified_name(namespace, local_name)
    return (element for element in root.iter() if element.tag == qualified_name)


def _first_qualified_element(
    root: ET.Element, namespace: str, local_name: str
) -> ET.Element | None:
    return next(_qualified_elements(root, namespace, local_name), None)


def _qualified_xml_title(
    root: ET.Element,
    namespace: str,
    fallback: str,
    limits: ParserLimits,
) -> str:
    for preferred in ("title", "h1", "h2"):
        for element in _qualified_elements(root, namespace, preferred):
            value = " ".join(element.itertext()).strip()
            if value:
                return _normalize_inline(value, "title", limits)
    return _normalize_inline(fallback, "title", limits)


def _element_text(root: ET.Element, limits: ParserLimits) -> str:
    pieces: list[str] = []
    size = 0
    for value in root.itertext():
        size += len(value)
        if size > limits.max_unit_text_chars:
            raise SourceParseError("unit_text_limit_exceeded")
        pieces.append(value)
    return _normalize_text(" ".join(pieces), limits)


@dataclass(frozen=True)
class _XmlMediaAnalysis:
    flags: SourceFlags
    present_dependencies: tuple[str, ...]


def _xml_media_analysis(
    root: ET.Element,
    text: str,
    resolve_media: Callable[[str], str | None],
    semantic_namespace: str,
    limits: ParserLimits,
) -> _XmlMediaAnalysis:
    has_table = False
    missing_media = False
    has_math = False
    has_visual_semantic = False
    has_uninterpreted_nontext = False
    quarantine_required = False
    present_dependencies: set[str] = set()
    media_element_count = 0
    visual_names = {"embed", "iframe", "image", "img", "object", "video"}
    nontext_names = {
        "audio",
        "embed",
        "iframe",
        "image",
        "img",
        "media",
        "object",
        "picture",
        "source",
        "video",
    }
    for element in root.iter():
        name = _local_name(element.tag).lower()
        namespace = (
            element.tag[1:].split("}", 1)[0]
            if element.tag.startswith("{") and "}" in element.tag
            else ""
        )
        if namespace == MATHML_NS:
            has_math = has_math or name in {"math", "equation", "formula"}
            continue
        if namespace == SVG_NS:
            has_visual_semantic = True
            has_uninterpreted_nontext = True
            quarantine_required = True
            present_dependencies.add("inline_svg")
            continue
        if namespace != semantic_namespace:
            continue
        has_table = has_table or name in {"table", "informaltable"}
        has_math = has_math or name in {"math", "equation", "formula"}
        if name == "figure":
            has_visual_semantic = True
            has_uninterpreted_nontext = True
            quarantine_required = True
        if name not in nontext_names:
            continue
        media_element_count += 1
        if media_element_count > limits.max_edges_per_unit:
            raise SourceParseError("media_dependency_limit_exceeded")
        has_visual_semantic = has_visual_semantic or name in visual_names
        has_uninterpreted_nontext = True
        quarantine_required = True
        refs = [
            value
            for attribute, value in element.attrib.items()
            if _local_name(attribute).lower() in {"data", "href", "src", "url"}
            and value
        ]
        child_has_reference = any(
            _local_name(child.tag).lower()
            in {
                "audio",
                "embed",
                "iframe",
                "image",
                "img",
                "object",
                "source",
                "video",
            }
            for child in element.iter()
            if child is not element
            and child.tag.startswith(f"{{{semantic_namespace}}}")
        )
        resolved_references = [resolve_media(value) for value in refs]
        present_dependencies.update(
            value for value in resolved_references if value is not None
        )
        if len(present_dependencies) > limits.max_edges_per_unit:
            raise SourceParseError("media_dependency_limit_exceeded")
        if (not refs and not child_has_reference) or any(
            value is None for value in resolved_references
        ):
            missing_media = True
    return _XmlMediaAnalysis(
        flags=SourceFlags(
            missing_media=missing_media,
            has_table=has_table,
            has_numeric_content=bool(NUMERIC_RE.search(text)) or has_math,
            present_visual_media=(has_visual_semantic and bool(present_dependencies)),
            uninterpreted_nontext_media=has_uninterpreted_nontext,
            visual_context_quarantined=quarantine_required,
        ),
        present_dependencies=tuple(sorted(present_dependencies)),
    )


@dataclass(frozen=True)
class _WordNetRecord:
    source_key: str
    offset: str
    file_pos: str
    synset_pos: str
    words: tuple[str, ...]
    gloss: str
    pointers: tuple[tuple[str, str, str], ...]
    raw_line: str
    member: str
    line_number: int


def _parse_wordnet_data_line(
    line: str,
    member: str,
    line_number: int,
    file_pos: str,
    limits: ParserLimits,
) -> _WordNetRecord:
    if " | " not in line:
        raise SourceParseError(f"wordnet_missing_gloss:{member}:{line_number}")
    body, gloss = line.split(" | ", 1)
    fields = body.split()
    if len(fields) < 5 or not re.fullmatch(r"\d{8}", fields[0]):
        raise SourceParseError(f"wordnet_malformed_data:{member}:{line_number}")
    offset = fields[0]
    synset_pos = fields[2]
    if synset_pos not in {"n", "v", "a", "s", "r"}:
        raise SourceParseError(f"wordnet_invalid_pos:{member}:{line_number}")
    if file_pos == "a":
        if synset_pos not in {"a", "s"}:
            raise SourceParseError(f"wordnet_file_pos_mismatch:{member}:{line_number}")
    elif synset_pos != file_pos:
        raise SourceParseError(f"wordnet_file_pos_mismatch:{member}:{line_number}")
    try:
        word_count = int(fields[3], 16)
    except ValueError as exc:
        raise SourceParseError(
            f"wordnet_invalid_word_count:{member}:{line_number}"
        ) from exc
    cursor = 4
    words: list[str] = []
    for _ in range(word_count):
        if cursor + 1 >= len(fields):
            raise SourceParseError(f"wordnet_truncated_words:{member}:{line_number}")
        words.append(fields[cursor].replace("_", " "))
        if not re.fullmatch(r"[0-9a-fA-F]", fields[cursor + 1]):
            raise SourceParseError(f"wordnet_invalid_lex_id:{member}:{line_number}")
        cursor += 2
    if not words or cursor >= len(fields):
        raise SourceParseError(f"wordnet_missing_pointer_count:{member}:{line_number}")
    try:
        pointer_count = int(fields[cursor], 10)
    except ValueError as exc:
        raise SourceParseError(
            f"wordnet_invalid_pointer_count:{member}:{line_number}"
        ) from exc
    cursor += 1
    pointers: list[tuple[str, str, str]] = []
    for _ in range(pointer_count):
        if cursor + 3 >= len(fields):
            raise SourceParseError(f"wordnet_truncated_pointer:{member}:{line_number}")
        symbol, target_offset, target_pos, source_target = fields[cursor : cursor + 4]
        if not re.fullmatch(r"\d{8}", target_offset):
            raise SourceParseError(
                f"wordnet_invalid_pointer_offset:{member}:{line_number}"
            )
        if target_pos not in {"n", "v", "a", "s", "r"}:
            raise SourceParseError(
                f"wordnet_invalid_pointer_pos:{member}:{line_number}"
            )
        if not re.fullmatch(r"[0-9a-fA-F]{4}", source_target):
            raise SourceParseError(
                f"wordnet_invalid_pointer_scope:{member}:{line_number}"
            )
        pointers.append((symbol, target_offset, target_pos))
        cursor += 4
    if synset_pos == "v":
        if cursor >= len(fields):
            raise SourceParseError(
                f"wordnet_missing_frame_count:{member}:{line_number}"
            )
        try:
            frame_count = int(fields[cursor], 10)
        except ValueError as exc:
            raise SourceParseError(
                f"wordnet_invalid_frame_count:{member}:{line_number}"
            ) from exc
        cursor += 1
        for _ in range(frame_count):
            if cursor + 2 >= len(fields) or fields[cursor] != "+":
                raise SourceParseError(f"wordnet_invalid_frame:{member}:{line_number}")
            cursor += 3
    if cursor != len(fields):
        raise SourceParseError(f"wordnet_trailing_data_fields:{member}:{line_number}")
    gloss = _normalize_inline(gloss, "wordnet_gloss", limits)
    return _WordNetRecord(
        source_key=f"wn:{synset_pos}:{offset}",
        offset=offset,
        file_pos=file_pos,
        synset_pos=synset_pos,
        words=tuple(words),
        gloss=gloss,
        pointers=tuple(pointers),
        raw_line=line,
        member=member,
        line_number=line_number,
    )


def _parse_wordnet_index(
    handle: BinaryIO,
    member: str,
    file_pos: str,
    limits: ParserLimits,
) -> set[str]:
    offsets: set[str] = set()
    for line_number, line in _bounded_utf8_lines(handle, limits):
        if not line or line.startswith(" "):
            continue
        fields = line.split()
        if len(fields) < 6 or fields[1] != file_pos:
            raise SourceParseError(f"wordnet_malformed_index:{member}:{line_number}")
        try:
            synset_count = int(fields[2])
            pointer_count = int(fields[3])
        except ValueError as exc:
            raise SourceParseError(
                f"wordnet_invalid_index_count:{member}:{line_number}"
            ) from exc
        cursor = 4 + pointer_count
        if cursor + 2 + synset_count != len(fields):
            raise SourceParseError(f"wordnet_index_arity:{member}:{line_number}")
        try:
            sense_count = int(fields[cursor])
            int(fields[cursor + 1])
        except ValueError as exc:
            raise SourceParseError(
                f"wordnet_invalid_sense_count:{member}:{line_number}"
            ) from exc
        if sense_count != synset_count:
            raise SourceParseError(
                f"wordnet_sense_count_mismatch:{member}:{line_number}"
            )
        for offset in fields[cursor + 2 :]:
            if not re.fullmatch(r"\d{8}", offset):
                raise SourceParseError(
                    f"wordnet_invalid_index_offset:{member}:{line_number}"
                )
            offsets.add(offset)
    return offsets


def _tar_octal_size(field: bytes) -> int:
    if not field or field[0] & 0x80:
        raise SourceParseError("tar_numeric_encoding_rejected")
    stripped = field.rstrip(b"\0 ").lstrip(b" ")
    if not stripped:
        return 0
    if re.fullmatch(rb"[0-7]+", stripped) is None:
        raise SourceParseError("tar_numeric_field_invalid")
    return int(stripped, 8)


def _validate_pax_extension(payload: bytes, limits: ParserLimits) -> None:
    offset = 0
    seen_keys: set[str] = set()
    while offset < len(payload):
        separator = payload.find(b" ", offset, min(len(payload), offset + 32))
        if separator < 0:
            raise SourceParseError("tar_pax_record_invalid")
        length_field = payload[offset:separator]
        if re.fullmatch(rb"[1-9][0-9]{0,19}", length_field) is None:
            raise SourceParseError("tar_pax_record_invalid")
        record_length = int(length_field)
        record_end = offset + record_length
        if record_end > len(payload) or payload[record_end - 1 : record_end] != b"\n":
            raise SourceParseError("tar_pax_record_invalid")
        record = payload[separator + 1 : record_end - 1]
        key_bytes, marker, value_bytes = record.partition(b"=")
        if not marker or not key_bytes or b"\0" in record:
            raise SourceParseError("tar_pax_record_invalid")
        try:
            key = key_bytes.decode("utf-8", errors="strict")
            value = value_bytes.decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise SourceParseError("tar_pax_record_encoding_invalid") from exc
        if (
            len(key) > limits.max_field_chars
            or len(value) > limits.max_field_chars
            or key in seen_keys
        ):
            raise SourceParseError("tar_extension_metadata_limit_exceeded")
        seen_keys.add(key)
        if key.startswith("GNU.sparse"):
            raise SourceParseError("tar_sparse_metadata_rejected")
        if key == "size":
            if (
                re.fullmatch(r"[0-9]+", value) is None
                or int(value) > limits.max_member_bytes
            ):
                raise SourceParseError("archive_member_size_limit_exceeded")
        if key == "path":
            _safe_archive_name(value)
        if key == "linkpath":
            raise SourceParseError("archive_link_or_special_member_rejected")
        offset = record_end


def _validate_gnu_extension(
    type_flag: bytes,
    payload: bytes,
    limits: ParserLimits,
) -> None:
    if type_flag == b"K":
        raise SourceParseError("archive_link_or_special_member_rejected")
    value_bytes = payload.rstrip(b"\0\n")
    try:
        value = value_bytes.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise SourceParseError("tar_gnu_extension_encoding_invalid") from exc
    if not value or len(value) > limits.max_field_chars:
        raise SourceParseError("tar_extension_metadata_limit_exceeded")
    _safe_archive_name(value)


def _preflight_gzip_tar_stream(handle: BinaryIO, limits: ParserLimits) -> None:
    try:
        handle.seek(0, os.SEEK_END)
        compressed_bytes = handle.tell()
        handle.seek(0)
        if handle.read(2) != b"\x1f\x8b":
            raise SourceParseError("wordnet_gzip_required")
        handle.seek(0)
    except OSError as exc:
        raise SourceParseError("source_read_failed") from exc
    maximum_stream_bytes = (
        limits.max_archive_uncompressed_bytes + (limits.max_archive_members + 16) * 1024
    )
    stream_bytes = 0
    declared_bytes = 0
    member_count = 0

    def read_exact(stream: gzip.GzipFile, size: int) -> bytes:
        nonlocal stream_bytes
        chunks: list[bytes] = []
        remaining = size
        while remaining:
            chunk = stream.read(min(64 * 1024, remaining))
            if not chunk:
                raise SourceParseError("truncated_tar_archive")
            chunks.append(chunk)
            remaining -= len(chunk)
            stream_bytes += len(chunk)
            if stream_bytes > maximum_stream_bytes:
                raise SourceParseError("tar_decompression_limit_exceeded")
        return b"".join(chunks)

    try:
        with gzip.GzipFile(fileobj=handle, mode="rb") as stream:
            zero_headers = 0
            while zero_headers < 2:
                header = read_exact(stream, 512)
                if header == b"\0" * 512:
                    zero_headers += 1
                    continue
                if zero_headers:
                    raise SourceParseError("tar_end_marker_invalid")
                member_count += 1
                if member_count > limits.max_archive_members:
                    raise SourceParseError("archive_member_limit_exceeded")
                size = _tar_octal_size(header[124:136])
                type_flag = header[156:157]
                extension = type_flag in {b"x", b"g", b"L", b"K"}
                if type_flag not in {b"", b"\0", b"0", b"5", b"x", b"g", b"L", b"K"}:
                    raise SourceParseError("archive_link_or_special_member_rejected")
                if type_flag == b"5" and size:
                    raise SourceParseError("tar_directory_payload_rejected")
                metadata_limit = min(limits.max_member_bytes, limits.max_field_chars)
                if extension and size > metadata_limit:
                    raise SourceParseError("tar_extension_metadata_limit_exceeded")
                if not extension and size > limits.max_member_bytes:
                    raise SourceParseError("archive_member_size_limit_exceeded")
                declared_bytes += size
                if declared_bytes > limits.max_archive_uncompressed_bytes:
                    raise SourceParseError("archive_uncompressed_limit_exceeded")
                if extension:
                    extension_payload = read_exact(stream, size)
                    if type_flag in {b"x", b"g"}:
                        _validate_pax_extension(extension_payload, limits)
                    else:
                        _validate_gnu_extension(type_flag, extension_payload, limits)
                    remaining = (-size) % 512
                else:
                    remaining = size + ((-size) % 512)
                while remaining:
                    amount = min(64 * 1024, remaining)
                    read_exact(stream, amount)
                    remaining -= amount
            while True:
                trailing = stream.read(64 * 1024)
                if not trailing:
                    break
                stream_bytes += len(trailing)
                if stream_bytes > maximum_stream_bytes:
                    raise SourceParseError("tar_decompression_limit_exceeded")
                if trailing.strip(b"\0"):
                    raise SourceParseError("tar_trailing_data_rejected")
    except (gzip.BadGzipFile, EOFError, OSError) as exc:
        raise SourceParseError("invalid_tar_archive") from exc
    if compressed_bytes <= 0 or (
        stream_bytes / compressed_bytes > limits.max_compression_ratio
    ):
        raise SourceParseError("tar_compression_ratio_exceeded")
    handle.seek(0)


def _parse_wordnet_tar_handle(
    handle: BinaryIO,
    source_member: str,
    context: ParseContext,
    limits: ParserLimits,
) -> Iterator[SourceUnit]:
    suffixes = {"noun": "n", "verb": "v", "adj": "a", "adv": "r"}
    selected: dict[str, tarfile.TarInfo] = {}
    total = 0
    _preflight_gzip_tar_stream(handle, limits)
    try:
        handle.seek(0)
        archive = tarfile.open(fileobj=handle, mode="r:gz")
    except (OSError, tarfile.TarError) as exc:
        raise SourceParseError("invalid_tar_archive") from exc
    with archive:
        member_count = 0
        for member in archive:
            member_count += 1
            if member_count > limits.max_archive_members:
                raise SourceParseError("archive_member_limit_exceeded")
            name = _safe_archive_name(member.name)
            if len(name) > limits.max_field_chars or any(
                len(str(key)) > limits.max_field_chars
                or len(str(value)) > limits.max_field_chars
                for key, value in member.pax_headers.items()
            ):
                raise SourceParseError("tar_extension_metadata_limit_exceeded")
            if member.isdir():
                continue
            if not member.isreg():
                raise SourceParseError("archive_link_or_special_member_rejected")
            if member.size > limits.max_member_bytes:
                raise SourceParseError("archive_member_size_limit_exceeded")
            total += member.size
            if total > limits.max_archive_uncompressed_bytes:
                raise SourceParseError("archive_uncompressed_limit_exceeded")
            basename = PurePosixPath(name).name
            if basename in {
                f"{prefix}.{suffix}"
                for prefix in ("data", "index")
                for suffix in suffixes
            }:
                if basename in selected:
                    raise SourceParseError("ambiguous_wordnet_member")
                selected[basename] = member
        expected = {
            f"{prefix}.{suffix}" for prefix in ("data", "index") for suffix in suffixes
        }
        if set(selected) != expected:
            raise SourceParseError("wordnet_required_members_missing")

        records: list[_WordNetRecord] = []
        data_offsets: dict[str, dict[str, _WordNetRecord]] = {
            pos: {} for pos in suffixes.values()
        }
        for suffix, pos in suffixes.items():
            member = selected[f"data.{suffix}"]
            handle = archive.extractfile(member)
            if handle is None:
                raise SourceParseError("wordnet_member_unreadable")
            with handle:
                for line_number, line in _bounded_utf8_lines(handle, limits):
                    if not line or line.startswith(" "):
                        continue
                    record = _parse_wordnet_data_line(
                        line, member.name, line_number, pos, limits
                    )
                    if record.offset in data_offsets[pos]:
                        raise SourceParseError("ambiguous_wordnet_offset")
                    data_offsets[pos][record.offset] = record
                    records.append(record)
                    if len(records) > limits.max_units:
                        raise SourceParseError("unit_limit_exceeded")
        for suffix, pos in suffixes.items():
            member = selected[f"index.{suffix}"]
            handle = archive.extractfile(member)
            if handle is None:
                raise SourceParseError("wordnet_member_unreadable")
            with handle:
                indexed = _parse_wordnet_index(handle, member.name, pos, limits)
            if not indexed.issubset(set(data_offsets[pos])):
                raise SourceParseError("wordnet_index_references_missing_synset")

    for record in records:
        edges: list[SourceEdge] = []
        for symbol, target_offset, target_pos in record.pointers:
            if symbol not in {"@", "@i"}:
                continue
            lookup_pos = "a" if target_pos == "s" else target_pos
            target = data_offsets.get(lookup_pos, {}).get(target_offset)
            if target is None:
                raise SourceParseError("wordnet_hypernym_target_missing")
            edges.append(
                _make_edge(
                    context,
                    "hierarchy",
                    "instance_hypernym" if symbol == "@i" else "hypernym",
                    target.source_key,
                    limits,
                )
            )
        yield _make_unit(
            context=context,
            source_key=record.source_key,
            kind="lexical_synset",
            title=record.words[0],
            text=record.gloss,
            synonyms=record.words[1:],
            edges=edges,
            flags=SourceFlags(
                missing_media=False,
                has_table=False,
                has_numeric_content=bool(NUMERIC_RE.search(record.gloss)),
                present_visual_media=False,
                uninterpreted_nontext_media=False,
                visual_context_quarantined=False,
            ),
            source_member=record.member,
            record_locator=f"line:{record.line_number}:offset:{record.offset}",
            record_value={"line": record.raw_line},
            limits=limits,
            definition=record.gloss,
            facets={"part_of_speech": (record.synset_pos,)},
        )


@dataclass(frozen=True)
class _TurtleToken:
    kind: str
    value: str
    language: str | None = None
    datatype: str | None = None


def _iter_turtle_statements(
    handle: BinaryIO, limits: ParserLimits
) -> Iterator[tuple[int, str]]:
    buffer: list[str] = []
    size = 0
    start_line = 1
    quote: str | None = None
    triple = False
    escaped = False
    iri = False
    in_comment = False

    def append(value: str) -> None:
        nonlocal size
        buffer.append(value)
        size += len(value)
        if size > limits.max_statement_chars:
            raise SourceParseError("turtle_statement_limit_exceeded")

    for line_number, line in _bounded_utf8_lines(handle, limits):
        line += "\n"
        index = 0
        while index < len(line):
            char = line[index]
            if in_comment:
                if char == "\n":
                    append(" ")
                    in_comment = False
                index += 1
                continue
            if iri:
                append(char)
                if char == ">" and not escaped:
                    iri = False
                escaped = char == "\\" and not escaped
                if char != "\\":
                    escaped = False
                index += 1
                continue
            if quote is not None:
                if triple and line[index : index + 3] == quote * 3 and not escaped:
                    append(quote * 3)
                    index += 3
                    quote = None
                    triple = False
                    continue
                append(char)
                if not triple and char == quote and not escaped:
                    quote = None
                escaped = char == "\\" and not escaped
                if char != "\\":
                    escaped = False
                index += 1
                continue
            if char == "#":
                in_comment = True
                index += 1
                continue
            if char == "<":
                iri = True
                escaped = False
                append(char)
                index += 1
                continue
            if char in {'"', "'"}:
                quote = char
                triple = line[index : index + 3] == char * 3
                append(char * (3 if triple else 1))
                index += 3 if triple else 1
                continue
            if char in "[](){}":
                raise SourceParseError("unsupported_turtle_collection_or_blank_node")
            if char == ".":
                next_char = line[index + 1] if index + 1 < len(line) else "\n"
                if next_char.isspace() or next_char == "#":
                    statement = "".join(buffer).strip()
                    if statement:
                        yield start_line, statement
                    buffer = []
                    size = 0
                    start_line = line_number
                    index += 1
                    continue
            append(char)
            index += 1
    if quote is not None or iri:
        raise SourceParseError("unterminated_turtle_token")
    if "".join(buffer).strip():
        raise SourceParseError("unterminated_turtle_statement")


def _decode_turtle_escape(value: str) -> str:
    output: list[str] = []
    index = 0
    simple = {
        "t": "\t",
        "b": "\b",
        "n": "\n",
        "r": "\r",
        "f": "\f",
        '"': '"',
        "'": "'",
        "\\": "\\",
    }
    while index < len(value):
        if value[index] != "\\":
            output.append(value[index])
            index += 1
            continue
        index += 1
        if index >= len(value):
            raise SourceParseError("invalid_turtle_escape")
        marker = value[index]
        if marker in simple:
            output.append(simple[marker])
            index += 1
            continue
        width = 4 if marker == "u" else 8 if marker == "U" else 0
        if not width or index + width >= len(value):
            raise SourceParseError("invalid_turtle_escape")
        digits = value[index + 1 : index + 1 + width]
        if not re.fullmatch(r"[0-9A-Fa-f]+", digits):
            raise SourceParseError("invalid_turtle_unicode_escape")
        codepoint = int(digits, 16)
        if codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
            raise SourceParseError("invalid_turtle_unicode_codepoint")
        output.append(chr(codepoint))
        index += width + 1
    return "".join(output)


def _tokenize_turtle(statement: str, limits: ParserLimits) -> list[_TurtleToken]:
    tokens: list[_TurtleToken] = []
    index = 0
    while index < len(statement):
        if statement[index].isspace():
            index += 1
            continue
        if statement[index] in ";,":
            tokens.append(_TurtleToken("punct", statement[index]))
            index += 1
            continue
        if statement[index] == "<":
            end = statement.find(">", index + 1)
            if end < 0:
                raise SourceParseError("malformed_turtle_iri")
            value = statement[index + 1 : end]
            if not value or any(char.isspace() for char in value) or "<" in value:
                raise SourceParseError("malformed_turtle_iri")
            tokens.append(_TurtleToken("iri", _decode_turtle_escape(value)))
            index = end + 1
            continue
        if statement[index] in {'"', "'"}:
            quote = statement[index]
            triple = statement[index : index + 3] == quote * 3
            index += 3 if triple else 1
            start = index
            escaped = False
            pieces: list[str] = []
            while index < len(statement):
                if triple and statement[index : index + 3] == quote * 3 and not escaped:
                    pieces.append(statement[start:index])
                    index += 3
                    break
                if not triple and statement[index] == quote and not escaped:
                    pieces.append(statement[start:index])
                    index += 1
                    break
                escaped = statement[index] == "\\" and not escaped
                if statement[index] != "\\":
                    escaped = False
                index += 1
            else:
                raise SourceParseError("unterminated_turtle_literal")
            literal = _decode_turtle_escape("".join(pieces))
            if len(literal) > limits.max_field_chars:
                raise SourceParseError("turtle_literal_limit_exceeded")
            language: str | None = None
            datatype: str | None = None
            if index < len(statement) and statement[index] == "@":
                match = re.match(r"@[A-Za-z]+(?:-[A-Za-z0-9]+)*", statement[index:])
                if match is None:
                    raise SourceParseError("invalid_turtle_language_tag")
                language = match.group(0)[1:].lower()
                index += len(match.group(0))
            elif statement[index : index + 2] == "^^":
                index += 2
                start = index
                if index < len(statement) and statement[index] == "<":
                    end = statement.find(">", index + 1)
                    if end < 0:
                        raise SourceParseError("invalid_turtle_datatype")
                    datatype = statement[index : end + 1]
                    index = end + 1
                else:
                    while (
                        index < len(statement)
                        and not statement[index].isspace()
                        and statement[index] not in ";,"
                    ):
                        index += 1
                    datatype = statement[start:index]
                if not datatype:
                    raise SourceParseError("invalid_turtle_datatype")
            tokens.append(_TurtleToken("literal", literal, language, datatype))
            continue
        start = index
        while (
            index < len(statement)
            and not statement[index].isspace()
            and statement[index] not in ";,"
        ):
            index += 1
        value = statement[start:index]
        if not value or value.startswith("_:") or value in {"[", "]", "(", ")"}:
            raise SourceParseError("unsupported_turtle_term")
        if len(value) > limits.max_field_chars:
            raise SourceParseError("turtle_token_limit_exceeded")
        tokens.append(_TurtleToken("bare", value))
    return tokens


def _absolute_iri(value: str, base: str | None = None) -> str:
    result = urljoin(base, value) if base else value
    parsed = urlsplit(result)
    if not parsed.scheme or CONTROL_RE.search(result):
        raise SourceParseError("relative_or_invalid_turtle_iri")
    return result


def _expand_turtle_term(
    token: _TurtleToken,
    prefixes: Mapping[str, str],
    base: str | None,
) -> str:
    if token.kind == "iri":
        return _absolute_iri(token.value, base)
    if token.kind != "bare":
        raise SourceParseError("turtle_resource_expected")
    if token.value == "a":
        return _TURTLE_RDF_TYPE
    if ":" not in token.value:
        raise SourceParseError("unsupported_turtle_bare_term")
    prefix, local = token.value.split(":", 1)
    if prefix not in prefixes or "\\" in local:
        raise SourceParseError("unknown_or_escaped_turtle_prefix")
    return _absolute_iri(prefixes[prefix] + unquote(local))


def _parse_turtle_tokens(
    tokens: Sequence[_TurtleToken],
    prefixes: Mapping[str, str],
    base: str | None,
) -> Iterator[tuple[str, str, _TurtleToken]]:
    if len(tokens) < 3:
        raise SourceParseError("turtle_statement_arity")
    subject = _expand_turtle_term(tokens[0], prefixes, base)
    cursor = 1
    while cursor < len(tokens):
        predicate = _expand_turtle_term(tokens[cursor], prefixes, base)
        cursor += 1
        if cursor >= len(tokens) or tokens[cursor].kind == "punct":
            raise SourceParseError("turtle_missing_object")
        while True:
            value = tokens[cursor]
            if value.kind == "punct":
                raise SourceParseError("turtle_invalid_object")
            yield subject, predicate, value
            cursor += 1
            if cursor >= len(tokens):
                return
            delimiter = tokens[cursor]
            if delimiter.kind != "punct":
                raise SourceParseError("turtle_missing_delimiter")
            cursor += 1
            if delimiter.value == ",":
                if cursor >= len(tokens):
                    raise SourceParseError("turtle_trailing_comma")
                continue
            if cursor >= len(tokens):
                return
            break


@dataclass
class _ConceptAccumulator:
    is_concept: bool
    pref: list[str]
    alt: list[str]
    hidden: list[str]
    definition: list[str]
    scope_note: list[str]
    note: list[str]
    broader: list[str]
    definition_refs: list[str]
    rdf_values: list[str]
    rdf_types: list[str]
    schemes: list[str]
    value_count: int
    accumulated_chars: int


def _new_concept() -> _ConceptAccumulator:
    return _ConceptAccumulator(
        False,
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        0,
        0,
    )


def _append_nalt_concept_value(
    concept: _ConceptAccumulator,
    field: str,
    value: str,
    limits: ParserLimits,
) -> None:
    """Append one assertion while enforcing bounds before it is retained."""

    values = getattr(concept, field)
    if not isinstance(values, list):
        raise SourceParseError("nalt_accumulator_field_invalid")
    if field in {"alt", "hidden"}:
        field_count = len(concept.alt) + len(concept.hidden)
        field_limit = limits.max_synonyms_per_unit
    elif field == "broader":
        field_count = len(values)
        field_limit = limits.max_edges_per_unit
    elif field in {"rdf_types", "schemes"}:
        field_count = len(concept.rdf_types) + len(concept.schemes)
        field_limit = limits.max_edges_per_unit
    else:
        field_count = len(values)
        field_limit = limits.max_edges_per_unit
    if field_count >= field_limit:
        raise SourceParseError(f"nalt_{field}_assertion_limit_exceeded")
    total_value_limit = limits.max_synonyms_per_unit + 4 * limits.max_edges_per_unit
    if concept.value_count >= total_value_limit:
        raise SourceParseError("nalt_concept_assertion_limit_exceeded")
    next_chars = concept.accumulated_chars + len(value)
    if next_chars > limits.max_unit_text_chars:
        raise SourceParseError("nalt_concept_accumulator_char_limit_exceeded")
    values.append(value)
    concept.value_count += 1
    concept.accumulated_chars = next_chars


def _bounded_nalt_definition_parts(
    concept: _ConceptAccumulator,
    concepts: Mapping[str, _ConceptAccumulator],
    limits: ParserLimits,
) -> list[str]:
    """Resolve definition nodes without a references-times-values expansion."""

    output: list[str] = []
    seen: set[str] = set()
    total_chars = 0

    def retain(value: str) -> None:
        nonlocal total_chars
        if value in seen:
            return
        if len(output) >= limits.max_edges_per_unit:
            raise SourceParseError("nalt_definition_part_limit_exceeded")
        total_chars += len(value)
        if total_chars > limits.max_unit_text_chars:
            raise SourceParseError("nalt_definition_char_limit_exceeded")
        seen.add(value)
        output.append(value)

    for value in concept.definition:
        retain(value)
    for reference in concept.definition_refs:
        target = concepts.get(reference)
        if target is None:
            continue
        for value in target.rdf_values:
            retain(value)
    for values in (concept.scope_note, concept.note):
        for value in values:
            retain(value)
    return output


def _language_admissible(language: str | None) -> bool:
    return language is None or language == "en" or language.startswith("en-")


def _parse_nalt_turtle_handle(
    handle: BinaryIO,
    context: ParseContext,
    source_member: str,
    limits: ParserLimits,
) -> Iterator[SourceUnit]:
    prefixes: dict[str, str] = {}
    base: str | None = None
    concepts: dict[str, _ConceptAccumulator] = {}
    statement_count = 0
    for line_number, statement in _iter_turtle_statements(handle, limits):
        statement_count += 1
        tokens = _tokenize_turtle(statement, limits)
        if not tokens:
            continue
        directive = tokens[0].value.lower()
        if directive in {"@prefix", "prefix"}:
            if (
                len(tokens) != 3
                or tokens[1].kind != "bare"
                or not tokens[1].value.endswith(":")
                or tokens[2].kind != "iri"
            ):
                raise SourceParseError(f"invalid_turtle_prefix:{line_number}")
            prefix = tokens[1].value[:-1]
            iri = _absolute_iri(tokens[2].value, base)
            if prefix in prefixes and prefixes[prefix] != iri:
                raise SourceParseError("ambiguous_turtle_prefix")
            prefixes[prefix] = iri
            continue
        if directive in {"@base", "base"}:
            if len(tokens) != 2 or tokens[1].kind != "iri":
                raise SourceParseError(f"invalid_turtle_base:{line_number}")
            candidate = _absolute_iri(tokens[1].value, base)
            if base is not None and base != candidate:
                raise SourceParseError("ambiguous_turtle_base")
            base = candidate
            continue
        for subject, predicate, obj in _parse_turtle_tokens(tokens, prefixes, base):
            concept = concepts.setdefault(subject, _new_concept())
            if len(concepts) > limits.max_units:
                raise SourceParseError("unit_limit_exceeded")
            if predicate == _TURTLE_RDF_TYPE:
                if obj.kind == "literal":
                    raise SourceParseError("nalt_rdf_type_not_resource")
                rdf_type = _expand_turtle_term(obj, prefixes, base)
                _append_nalt_concept_value(
                    concept,
                    "rdf_types",
                    rdf_type,
                    limits,
                )
                if rdf_type == _TURTLE_SKOS_CONCEPT:
                    concept.is_concept = True
                continue
            label_kind = _TURTLE_LABEL_PROPERTIES.get(predicate)
            if label_kind is not None:
                if obj.kind != "literal":
                    raise SourceParseError("nalt_label_not_literal")
                if _language_admissible(obj.language):
                    _append_nalt_concept_value(
                        concept,
                        label_kind,
                        obj.value,
                        limits,
                    )
                continue
            text_kind = _TURTLE_TEXT_PROPERTIES.get(predicate)
            if text_kind is not None:
                if obj.kind == "literal":
                    if _language_admissible(obj.language):
                        _append_nalt_concept_value(
                            concept,
                            text_kind,
                            obj.value,
                            limits,
                        )
                elif text_kind == "definition":
                    _append_nalt_concept_value(
                        concept,
                        "definition_refs",
                        _expand_turtle_term(obj, prefixes, base),
                        limits,
                    )
                else:
                    raise SourceParseError("nalt_text_not_literal")
                continue
            if predicate == RDF_NS + "value":
                if obj.kind != "literal":
                    raise SourceParseError("nalt_rdf_value_not_literal")
                if _language_admissible(obj.language):
                    _append_nalt_concept_value(
                        concept,
                        "rdf_values",
                        obj.value,
                        limits,
                    )
                continue
            if predicate == SKOS_NS + "broader":
                if obj.kind == "literal":
                    raise SourceParseError("nalt_broader_not_resource")
                _append_nalt_concept_value(
                    concept,
                    "broader",
                    _expand_turtle_term(obj, prefixes, base),
                    limits,
                )
                continue
            if predicate == SKOS_NS + "inScheme":
                if obj.kind == "literal":
                    raise SourceParseError("nalt_scheme_not_resource")
                _append_nalt_concept_value(
                    concept,
                    "schemes",
                    _expand_turtle_term(obj, prefixes, base),
                    limits,
                )

    emitted = 0
    for subject in sorted(concepts):
        concept = concepts[subject]
        if not concept.is_concept:
            continue
        pref = sorted(
            {
                _normalize_inline(value, "nalt_pref_label", limits)
                for value in concept.pref
            }
        )
        if len(pref) != 1:
            raise SourceParseError("nalt_ambiguous_or_missing_english_pref_label")
        definition_parts = _bounded_nalt_definition_parts(concept, concepts, limits)
        definition = "\n".join(definition_parts) or None
        text = definition or pref[0]
        edges = [
            _make_edge(context, "hierarchy", "skos_broader", target, limits)
            for target in sorted(set(concept.broader))
        ]
        emitted += 1
        if emitted > limits.max_units:
            raise SourceParseError("unit_limit_exceeded")
        yield _make_unit(
            context=context,
            source_key=subject,
            kind="controlled_vocabulary_concept",
            title=pref[0],
            text=text,
            synonyms=[*concept.alt, *concept.hidden],
            edges=edges,
            flags=SourceFlags(
                missing_media=False,
                has_table=False,
                has_numeric_content=bool(NUMERIC_RE.search(text)),
                present_visual_media=False,
                uninterpreted_nontext_media=False,
                visual_context_quarantined=False,
            ),
            source_member=source_member,
            record_locator=subject,
            record_value={
                "subject": subject,
                "pref": pref,
                "alt": sorted(set(concept.alt)),
                "hidden": sorted(set(concept.hidden)),
                "text": definition_parts,
                "definition_refs": sorted(set(concept.definition_refs)),
                "rdf_types": sorted(set(concept.rdf_types)),
                "schemes": sorted(set(concept.schemes)),
                "broader": sorted(set(concept.broader)),
                "statement_count_in_source": statement_count,
            },
            limits=limits,
            definition=definition,
            facets={
                "rdf_type": concept.rdf_types,
                "scheme": concept.schemes,
            },
        )


def _parse_nalt_turtle_zip_handle(
    handle: BinaryIO,
    source_member: str,
    context: ParseContext,
    limits: ParserLimits,
) -> Iterator[SourceUnit]:
    archive, entries = _validate_zip(handle, limits)
    with archive:
        candidates = [name for name in entries if name.lower().endswith(".ttl")]
        if len(candidates) != 1:
            raise SourceParseError("ambiguous_nalt_turtle_member")
        member = candidates[0]
        with archive.open(entries[member], "r") as handle:
            yield from _parse_nalt_turtle_handle(handle, context, member, limits)


def _obo_quoted(value: str, field: str, limits: ParserLimits) -> str:
    if not value.startswith('"'):
        raise SourceParseError(f"obo_{field}_not_quoted")
    output: list[str] = []
    escaped = False
    cursor = 1
    while cursor < len(value):
        char = value[cursor]
        if escaped:
            translations = {"n": "\n", "t": "\t", "r": "\r"}
            output.append(translations.get(char, char))
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            return _normalize_inline("".join(output), f"obo_{field}", limits)
        else:
            output.append(char)
        cursor += 1
    raise SourceParseError(f"obo_{field}_unterminated")


def _obo_term_to_unit(
    fields: Mapping[str, list[str]],
    raw_lines: Sequence[str],
    context: ParseContext,
    source_member: str,
    stanza_number: int,
    limits: ParserLimits,
) -> SourceUnit | None:
    if fields.get("is_obsolete", ["false"])[-1].split()[0].lower() == "true":
        return None
    ids = fields.get("id", [])
    names = fields.get("name", [])
    definitions = fields.get("def", [])
    if len(ids) != 1 or len(names) != 1:
        raise SourceParseError("obo_ambiguous_or_missing_identity")
    source_key = ids[0].split(" ! ", 1)[0].strip()
    _validate_identifier(source_key, "obo_id", limits)
    title = names[0].split(" ! ", 1)[0].strip()
    definition = (
        "\n".join(_obo_quoted(value, "definition", limits) for value in definitions)
        or None
    )
    text = definition or title
    synonyms = [
        _obo_quoted(value, "synonym", limits) for value in fields.get("synonym", [])
    ]
    edges: list[SourceEdge] = []
    unadjudicated_relations: list[str] = []
    for value in fields.get("is_a", []):
        target = value.split(" ! ", 1)[0].strip()
        edges.append(_make_edge(context, "hierarchy", "is_a", target, limits))
    for value in fields.get("relationship", []):
        parts = value.split()
        if len(parts) < 2:
            raise SourceParseError("obo_malformed_relationship")
        predicate, target = parts[:2]
        _validate_identifier(predicate, "obo_relationship_predicate", limits)
        _validate_identifier(target, "obo_relationship_target", limits)
        if predicate == "part_of":
            edges.append(_make_edge(context, "hierarchy", predicate, target, limits))
            continue
        unadjudicated_relations.append(
            _normalize_inline(value, "obo_unadjudicated_relationship", limits)
        )
    return _make_unit(
        context=context,
        source_key=source_key,
        kind="ontology_term",
        title=title,
        text=text,
        synonyms=synonyms,
        edges=edges,
        flags=SourceFlags(
            missing_media=False,
            has_table=False,
            has_numeric_content=bool(NUMERIC_RE.search(text)),
            present_visual_media=False,
            uninterpreted_nontext_media=False,
            visual_context_quarantined=False,
        ),
        source_member=source_member,
        record_locator=f"stanza:{stanza_number}:{source_key}",
        record_value={"lines": list(raw_lines)},
        limits=limits,
        definition=definition,
        facets={
            "namespace": fields.get("namespace", ()),
            "subset": fields.get("subset", ()),
            "unadjudicated_ontology_relation": unadjudicated_relations,
        },
    )


def _parse_obo_handle(
    handle: BinaryIO,
    source_member: str,
    context: ParseContext,
    limits: ParserLimits,
) -> Iterator[SourceUnit]:
    seen: set[str] = set()
    fields: dict[str, list[str]] = {}
    raw_lines: list[str] = []
    stanza_kind: str | None = None
    stanza_number = 0
    emitted = 0

    def finish() -> SourceUnit | None:
        if stanza_kind != "Term":
            return None
        return _obo_term_to_unit(
            fields,
            raw_lines,
            context,
            source_member,
            stanza_number,
            limits,
        )

    try:
        handle.seek(0)
        for line_number, line in _bounded_utf8_lines(handle, limits):
            stripped = line.strip()
            if not stripped or stripped.startswith("!"):
                continue
            if stripped.startswith("["):
                if not stripped.endswith("]"):
                    raise SourceParseError(f"obo_malformed_stanza:{line_number}")
                unit = finish()
                if unit is not None:
                    if unit.source_key in seen:
                        raise SourceParseError("obo_duplicate_identity")
                    seen.add(unit.source_key)
                    emitted += 1
                    if emitted > limits.max_units:
                        raise SourceParseError("unit_limit_exceeded")
                    yield unit
                stanza_number += 1
                stanza_kind = stripped[1:-1]
                fields = {}
                raw_lines = []
                continue
            if stanza_kind is None:
                continue
            if ":" not in line:
                raise SourceParseError(f"obo_malformed_tag_value:{line_number}")
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            _validate_identifier(key, "obo_tag", limits)
            if len(value) > limits.max_field_chars:
                raise SourceParseError("obo_field_limit_exceeded")
            fields.setdefault(key, []).append(value)
            raw_lines.append(line)
        unit = finish()
        if unit is not None:
            if unit.source_key in seen:
                raise SourceParseError("obo_duplicate_identity")
            emitted += 1
            if emitted > limits.max_units:
                raise SourceParseError("unit_limit_exceeded")
            yield unit
    except OSError as exc:
        raise SourceParseError("source_read_failed") from exc


def _rdf_concept_unit(
    element: ET.Element,
    context: ParseContext,
    source_member: str,
    limits: ParserLimits,
) -> SourceUnit | None:
    child_limit = min(
        limits.max_files,
        limits.max_synonyms_per_unit + limits.max_edges_per_unit + 64,
    )
    if len(element) > child_limit:
        raise SourceParseError("rdf_concept_child_limit_exceeded")
    is_concept = element.tag == _qualified_name(SKOS_NS, "Concept")
    if element.tag == _qualified_name(RDF_NS, "Description"):
        is_concept = any(
            child.tag == _qualified_name(RDF_NS, "type")
            and child.attrib.get(f"{{{RDF_NS}}}resource") == SKOS_NS + "Concept"
            for child in element
        )
    if not is_concept:
        return None
    subject = element.attrib.get(f"{{{RDF_NS}}}about")
    if not subject:
        raise SourceParseError("rdf_concept_missing_about")
    subject = _absolute_iri(subject)
    if len(subject) > limits.max_field_chars:
        raise SourceParseError("rdf_subject_limit_exceeded")
    pref: list[str] = []
    synonyms: list[str] = []
    texts: list[str] = []
    broader: list[str] = []
    accumulated_text_chars = 0
    for child in element:
        if child.tag.startswith(f"{{{SKOS_NS}}}"):
            name = _local_name(child.tag)
        else:
            name = ""
        language = child.attrib.get(f"{{{XML_NS}}}lang")
        if name in {"prefLabel", "altLabel", "definition", "scopeNote", "note"}:
            pieces: list[str] = []
            value_chars = 0
            for piece in child.itertext():
                value_chars += len(piece)
                if value_chars > limits.max_field_chars:
                    raise SourceParseError("rdf_text_limit_exceeded")
                pieces.append(piece)
            value = " ".join(pieces).strip()
            if not value or not _language_admissible(language):
                continue
            accumulated_text_chars += len(value)
            if accumulated_text_chars > limits.max_unit_text_chars:
                raise SourceParseError("rdf_accumulated_text_limit_exceeded")
            if name == "prefLabel":
                pref.append(value)
            elif name == "altLabel":
                synonyms.append(value)
                if len(synonyms) > limits.max_synonyms_per_unit:
                    raise SourceParseError("synonym_limit_exceeded")
            else:
                texts.append(value)
        elif name == "broader":
            target = child.attrib.get(f"{{{RDF_NS}}}resource")
            if not target:
                raise SourceParseError("rdf_broader_missing_resource")
            normalized_target = _absolute_iri(target)
            if len(normalized_target) > limits.max_field_chars:
                raise SourceParseError("rdf_broader_target_limit_exceeded")
            broader.append(normalized_target)
            if len(broader) > limits.max_edges_per_unit:
                raise SourceParseError("edge_limit_exceeded")
    labels = sorted(
        {_normalize_inline(value, "rdf_pref_label", limits) for value in pref}
    )
    if len(labels) != 1:
        raise SourceParseError("rdf_ambiguous_or_missing_english_pref_label")
    definition = "\n".join(dict.fromkeys(texts)) or None
    text = definition or labels[0]
    edges = [
        _make_edge(context, "hierarchy", "skos_broader", target, limits)
        for target in sorted(set(broader))
    ]
    record = {
        "subject": subject,
        "pref": labels,
        "synonyms": sorted(set(synonyms)),
        "texts": texts,
        "broader": sorted(set(broader)),
    }
    return _make_unit(
        context=context,
        source_key=subject,
        kind="controlled_vocabulary_concept",
        title=labels[0],
        text=text,
        synonyms=synonyms,
        edges=edges,
        flags=SourceFlags(
            missing_media=False,
            has_table=False,
            has_numeric_content=bool(NUMERIC_RE.search(text)),
            present_visual_media=False,
            uninterpreted_nontext_media=False,
            visual_context_quarantined=False,
        ),
        source_member=source_member,
        record_locator=subject,
        record_value=record,
        limits=limits,
        definition=definition,
    )


def _parse_usgs_skos_rdf_handle(
    handle: BinaryIO,
    source_member: str,
    context: ParseContext,
    limits: ParserLimits,
) -> Iterator[SourceUnit]:
    _scan_xml_handle(handle, limits)
    depth = 0
    seen: set[str] = set()
    emitted = 0
    candidate_depth = 0
    candidate_tags = {
        _qualified_name(SKOS_NS, "Concept"),
        _qualified_name(RDF_NS, "Description"),
    }
    candidate_root_depth = 0
    candidate_child_count = 0
    candidate_accumulated_chars = 0
    candidate_child_limit = min(
        limits.max_files,
        limits.max_synonyms_per_unit + limits.max_edges_per_unit + 64,
    )
    element_stack: list[ET.Element] = []
    try:
        for event, element in ET.iterparse(handle, events=("start", "end")):
            if event == "start":
                depth += 1
                if element.tag in candidate_tags:
                    if candidate_depth:
                        raise SourceParseError("rdf_nested_concept_rejected")
                    candidate_depth = 1
                    candidate_root_depth = depth
                    candidate_child_count = 0
                    candidate_accumulated_chars = 0
                elif candidate_depth and depth == candidate_root_depth + 1:
                    candidate_child_count += 1
                    if candidate_child_count > candidate_child_limit:
                        raise SourceParseError("rdf_concept_child_limit_exceeded")
                element_stack.append(element)
                if depth > limits.max_xml_depth:
                    raise SourceParseError("xml_depth_limit_exceeded")
                if depth == 1:
                    _require_qualified_root(
                        element,
                        RDF_NS,
                        "RDF",
                        "rdf_root_namespace_mismatch",
                    )
                local_name = _local_name(element.tag)
                expected_namespace = _RDF_SEMANTIC_NAMESPACES.get(local_name)
                if expected_namespace is not None and element.tag != _qualified_name(
                    expected_namespace, local_name
                ):
                    raise SourceParseError(f"rdf_namespace_mismatch:{local_name}")
                continue
            if not element_stack or element_stack[-1] is not element:
                raise SourceParseError("rdf_element_stack_invalid")
            parent = element_stack[-2] if len(element_stack) > 1 else None
            if candidate_depth and depth == candidate_root_depth + 1:
                direct_child_chars = 0
                for piece in element.itertext():
                    direct_child_chars += len(piece)
                    if direct_child_chars > limits.max_unit_text_chars:
                        raise SourceParseError("rdf_accumulated_text_limit_exceeded")
                candidate_accumulated_chars += direct_child_chars
                if candidate_accumulated_chars > limits.max_unit_text_chars:
                    raise SourceParseError("rdf_accumulated_text_limit_exceeded")
            if element.tag in candidate_tags:
                unit = _rdf_concept_unit(element, context, source_member, limits)
                if unit is not None:
                    if unit.source_key in seen:
                        raise SourceParseError("rdf_duplicate_identity")
                    seen.add(unit.source_key)
                    emitted += 1
                    if emitted > limits.max_units:
                        raise SourceParseError("unit_limit_exceeded")
                    yield unit
                candidate_depth = 0
                candidate_root_depth = 0
                if parent is not None:
                    parent.remove(element)
                element.clear()
            elif candidate_depth == 0:
                if parent is not None:
                    parent.remove(element)
                element.clear()
            element_stack.pop()
            depth -= 1
    except ET.ParseError as exc:
        raise SourceParseError("malformed_xml") from exc
    except OSError as exc:
        raise SourceParseError("source_read_failed") from exc


def _resolve_archive_href(base_member: str, href: str) -> str | None:
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc:
        return None
    decoded = unquote(parsed.path)
    if not decoded:
        return base_member
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(base_member), decoded))
    try:
        return _safe_archive_name(joined)
    except SourceParseError:
        raise SourceParseError("unsafe_archive_reference") from None


def _epub_manifest_property_tokens(value: str) -> tuple[str, ...]:
    tokens = tuple(value.split())
    if len(tokens) != len(set(tokens)) or any(
        re.fullmatch(r"[A-Za-z][A-Za-z0-9._:-]*", token) is None for token in tokens
    ):
        raise SourceParseError("epub_manifest_properties_invalid")
    return tokens


def _is_siyavula_rights_member(member: str) -> bool:
    basename = PurePosixPath(member).name
    if basename == "copyright_acknowledgements_ccby.html":
        return True
    return (
        re.fullmatch(
            r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*-frontmatter\.(?:xhtml|html)",
            basename,
            flags=re.IGNORECASE,
        )
        is not None
    )


def _epub_rights_xhtml_root(value: bytes, limits: ParserLimits) -> ET.Element:
    try:
        decoded = value.decode(_xml_encoding(value[:4]), errors="strict")
    except UnicodeDecodeError as exc:
        raise SourceParseError("invalid_xml_encoding") from exc
    if decoded.count("<!DOCTYPE html>") != 1:
        raise SourceParseError("epub_rights_HTML5_doctype_mismatch")
    without_doctype = decoded.replace("<!DOCTYPE html>", "", 1).encode("utf-8")
    return _secure_xml_from_bytes(without_doctype, limits)


def _validate_epub_xhtml_namespaces(root: ET.Element, role: str) -> None:
    _require_qualified_root(
        root,
        XHTML_NS,
        "html",
        f"epub_{role}_xhtml_namespace_mismatch",
    )
    _reject_confusable_namespaces(
        root,
        {"a": XHTML_NS, "body": XHTML_NS, "html": XHTML_NS, "nav": XHTML_NS},
        f"epub_{role}_xhtml_namespace_mismatch",
    )


def _validate_epub_navigation_toc(
    root: ET.Element,
    member: str,
    entries: Mapping[str, zipfile.ZipInfo],
) -> int:
    _validate_epub_xhtml_namespaces(root, "navigation")
    toc_nodes = [
        element
        for element in root.iter()
        if element.tag == _qualified_name(XHTML_NS, "nav")
        and "toc"
        in element.attrib.get(_qualified_name(EPUB_OPS_NS, "type"), "").split()
    ]
    if len(toc_nodes) != 1:
        raise SourceParseError("epub_navigation_unique_toc_role_required")
    links = [
        element.attrib.get("href", "")
        for element in toc_nodes[0].iter()
        if element.tag == _qualified_name(XHTML_NS, "a")
    ]
    if not links or any(not href for href in links):
        raise SourceParseError("epub_navigation_toc_link_missing")
    for href in links:
        resolved = _resolve_archive_href(member, href)
        if resolved is None:
            raise SourceParseError("epub_remote_navigation_target_rejected")
        if resolved not in entries:
            raise SourceParseError("epub_navigation_target_missing")
    return len(links)


def _validate_epub_rights_link(root: ET.Element) -> int:
    _validate_epub_xhtml_namespaces(root, "rights")
    expected_url = "http://creativecommons.org/licenses/by/4.0/"
    links = [
        element
        for element in root.iter()
        if element.tag == _qualified_name(XHTML_NS, "a")
        and element.attrib.get("href") == expected_url
    ]
    if not links:
        raise SourceParseError("epub_rights_structured_license_link_missing")
    return len(links)


def _parse_siyavula_epub_handle(
    handle: BinaryIO,
    source_member: str,
    context: ParseContext,
    limits: ParserLimits,
) -> Iterator[SourceUnit]:
    archive, entries = _validate_zip(handle, limits)
    with archive:
        required = {"mimetype", "META-INF/container.xml"}
        if not required.issubset(entries):
            raise SourceParseError("epub_required_member_missing")
        first = archive.infolist()[0] if archive.infolist() else None
        if (
            first is None
            or first.filename != "mimetype"
            or first.compress_type != zipfile.ZIP_STORED
        ):
            raise SourceParseError("epub_mimetype_entry_order_or_method_invalid")
        mimetype = _read_zip_member(archive, entries["mimetype"], limits)
        if mimetype != b"application/epub+zip":
            raise SourceParseError("epub_invalid_mimetype")
        container = _secure_xml_from_bytes(
            _read_zip_member(archive, entries["META-INF/container.xml"], limits),
            limits,
        )
        _require_qualified_root(
            container,
            EPUB_CONTAINER_NS,
            "container",
            "epub_container_namespace_mismatch",
        )
        _reject_confusable_namespaces(
            container,
            _EPUB_CONTAINER_NAMESPACES,
            "epub_container_namespace_mismatch",
        )
        rootfiles = [
            (
                element.attrib.get("full-path", ""),
                element.attrib.get("media-type", ""),
            )
            for element in _qualified_elements(container, EPUB_CONTAINER_NS, "rootfile")
        ]
        if (
            len(rootfiles) != 1
            or not rootfiles[0][0]
            or rootfiles[0][1] != "application/oebps-package+xml"
        ):
            raise SourceParseError("epub_ambiguous_or_missing_package")
        package_member = _safe_archive_name(rootfiles[0][0])
        if package_member not in entries:
            raise SourceParseError("epub_ambiguous_or_missing_package")
        package = _secure_xml_from_bytes(
            _read_zip_member(archive, entries[package_member], limits), limits
        )
        _require_qualified_root(
            package,
            EPUB_OPF_NS,
            "package",
            "epub_opf_namespace_mismatch",
        )
        structural_counts = {
            local_name: sum(
                1
                for element in package.iter()
                if element.tag == _qualified_name(EPUB_OPF_NS, local_name)
            )
            for local_name in ("metadata", "manifest", "spine")
        }
        if any(count != 1 for count in structural_counts.values()):
            raise SourceParseError("epub_opf_package_structure_invalid")
        _reject_confusable_namespaces(
            package,
            _EPUB_OPF_NAMESPACES,
            "epub_opf_namespace_mismatch",
        )
        package_version = package.attrib.get("version")
        unique_identifier_id = package.attrib.get("unique-identifier")
        if (
            package_version is None
            or re.fullmatch(r"3\.[0-9]+", package_version) is None
        ):
            raise SourceParseError("epub_package_version_invalid")
        if (
            unique_identifier_id is None
            or re.fullmatch(r"[A-Za-z_][A-Za-z0-9._:-]{0,127}", unique_identifier_id)
            is None
        ):
            raise SourceParseError("epub_package_unique_identifier_invalid")
        identifiers = list(_qualified_elements(package, DC_NS, "identifier"))
        linked_identifiers = [
            element
            for element in identifiers
            if element.attrib.get("id") == unique_identifier_id
            and " ".join((element.text or "").split())
        ]
        if len(identifiers) != 1 or len(linked_identifiers) != 1:
            raise SourceParseError("epub_package_unique_identifier_link_invalid")
        manifest: dict[str, tuple[str, str, tuple[str, ...]]] = {}
        manifest_targets: set[str] = set()
        for element in _qualified_elements(package, EPUB_OPF_NS, "item"):
            item_id = element.attrib.get("id", "")
            href = element.attrib.get("href", "")
            media_type = element.attrib.get("media-type", "")
            properties = _epub_manifest_property_tokens(
                element.attrib.get("properties", "")
            )
            _validate_identifier(item_id, "epub_manifest_id", limits)
            resolved = _resolve_archive_href(package_member, href)
            if resolved is None:
                raise SourceParseError("epub_remote_manifest_item_rejected")
            if item_id in manifest:
                raise SourceParseError("epub_duplicate_manifest_id")
            if resolved in manifest_targets:
                raise SourceParseError("epub_duplicate_manifest_target")
            manifest[item_id] = (resolved, media_type, properties)
            manifest_targets.add(resolved)
        navigation_items = [
            (item_id, *item) for item_id, item in manifest.items() if "nav" in item[2]
        ]
        if len(navigation_items) != 1:
            raise SourceParseError("epub_unique_navigation_manifest_item_required")
        (
            _navigation_id,
            navigation_member,
            navigation_media_type,
            _navigation_properties,
        ) = navigation_items[0]
        if navigation_media_type != "application/xhtml+xml":
            raise SourceParseError("epub_navigation_manifest_media_type_invalid")
        if navigation_member not in entries:
            raise SourceParseError("epub_navigation_member_missing")
        navigation_root = _secure_xml_from_bytes(
            _read_zip_member(archive, entries[navigation_member], limits), limits
        )
        _validate_epub_navigation_toc(navigation_root, navigation_member, entries)
        rights_items = [
            (item_id, *item)
            for item_id, item in manifest.items()
            if _is_siyavula_rights_member(item[0])
        ]
        if (
            len(rights_items) != 1
            or rights_items[0][2] != "application/xhtml+xml"
            or "nav" in rights_items[0][3]
        ):
            raise SourceParseError("epub_rights_manifest_binding_invalid")
        rights_member = rights_items[0][1]
        if rights_member not in entries:
            raise SourceParseError("epub_rights_member_missing")
        rights_root = _epub_rights_xhtml_root(
            _read_zip_member(archive, entries[rights_member], limits), limits
        )
        _validate_epub_rights_link(rights_root)
        spine: list[str] = []
        for element in _qualified_elements(package, EPUB_OPF_NS, "itemref"):
            item_id = element.attrib.get("idref", "")
            if item_id not in manifest:
                raise SourceParseError("epub_spine_reference_missing")
            if item_id in spine:
                raise SourceParseError("epub_duplicate_spine_identity")
            spine.append(item_id)
        if not spine:
            raise SourceParseError("epub_empty_spine")
        if len(spine) > limits.max_units:
            raise SourceParseError("unit_limit_exceeded")

        for position, item_id in enumerate(spine, start=1):
            member, media_type, _properties = manifest[item_id]
            if media_type not in {"application/xhtml+xml", "text/html"}:
                raise SourceParseError("epub_unsupported_spine_media_type")
            if member not in entries:
                raise SourceParseError("epub_spine_member_missing")
            content = _read_zip_member(archive, entries[member], limits)
            root = _secure_xml_from_bytes(content, limits)
            _require_qualified_root(
                root,
                XHTML_NS,
                "html",
                "epub_xhtml_namespace_mismatch",
            )
            _reject_confusable_namespaces(
                root,
                {"html": XHTML_NS, "body": XHTML_NS},
                "epub_xhtml_namespace_mismatch",
            )
            bodies = list(_qualified_elements(root, XHTML_NS, "body"))
            if len(bodies) != 1:
                raise SourceParseError("epub_ambiguous_or_missing_xhtml_body")
            semantic_root = bodies[0]
            text = _element_text(semantic_root, limits)
            title = _qualified_xml_title(root, XHTML_NS, item_id, limits)

            def resolve_media(reference: str) -> str | None:
                if urlsplit(reference).scheme == "data":
                    return "inline_data_uri"
                resolved = _resolve_archive_href(member, reference)
                return (
                    resolved if resolved is not None and resolved in entries else None
                )

            media = _xml_media_analysis(
                semantic_root,
                text,
                resolve_media,
                XHTML_NS,
                limits,
            )
            source_key = f"epub:{item_id}"
            yield _make_unit(
                context=context,
                source_key=source_key,
                kind="textbook_spine_item",
                title=title,
                text=text,
                synonyms=(),
                edges=(),
                flags=media.flags,
                source_member=member,
                record_locator=f"spine:{position}:manifest:{item_id}",
                record_value={
                    "member_sha256": "sha256:" + hashlib.sha256(content).hexdigest(),
                    "position": position,
                    "manifest_id": item_id,
                },
                limits=limits,
                facets={
                    "media_type": (media_type,),
                    "media_dependency_member": media.present_dependencies,
                    "spine_position": (str(position),),
                    "structural_sequence_evidence": (
                        f"epub_spine_position:{position}",
                    ),
                },
            )


def _openstax_expected_manifest(
    context: ParseContext,
    limits: ParserLimits,
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    context.validate(limits)
    if context.source_manifest_json is None:
        raise SourceParseError("openstax_source_manifest_required")
    manifest = _decode_exact_canonical_contract_json(
        context.source_manifest_json,
        "source_manifest",
    )
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema_version",
        "commit_sha",
        "tree_sha",
        "files",
    }:
        raise SourceParseError("openstax_source_manifest_shape_invalid")
    if manifest["schema_version"] != "cur0s_git_sparse_content_manifest_v1":
        raise SourceParseError("openstax_source_manifest_schema_invalid")
    if not isinstance(manifest["commit_sha"], str) or not re.fullmatch(
        r"[0-9a-f]{40}", manifest["commit_sha"]
    ):
        raise SourceParseError("openstax_source_manifest_commit_invalid")
    if not isinstance(manifest["tree_sha"], str) or not re.fullmatch(
        r"[0-9a-f]{40}", manifest["tree_sha"]
    ):
        raise SourceParseError("openstax_source_manifest_tree_invalid")
    records = manifest["files"]
    if not isinstance(records, list) or not records:
        raise SourceParseError("openstax_source_manifest_files_invalid")
    files: dict[str, dict[str, Any]] = {}
    directories: set[str] = set()
    previous_relative: str | None = None
    total = 0
    for record in records:
        if not isinstance(record, dict) or set(record) != {
            "relative_path",
            "bytes",
            "sha256",
        }:
            raise SourceParseError("openstax_source_manifest_entry_invalid")
        relative = _safe_archive_name(record["relative_path"])
        if len(PurePosixPath(relative).parts) > min(limits.max_xml_depth, 128):
            raise SourceParseError("openstax_directory_depth_limit_exceeded")
        if relative == ".git" or ".git" in PurePosixPath(relative).parts:
            raise SourceParseError("openstax_git_metadata_rejected")
        byte_count = record["bytes"]
        digest = record["sha256"]
        if (
            type(byte_count) is not int
            or byte_count < 0
            or byte_count > limits.max_member_bytes
            or not isinstance(digest, str)
            or not SHA256_RE.fullmatch(digest)
        ):
            raise SourceParseError("openstax_source_manifest_entry_invalid")
        if relative in files:
            raise SourceParseError("openstax_source_manifest_duplicate_path")
        if previous_relative is not None and relative <= previous_relative:
            raise SourceParseError("openstax_source_manifest_order_invalid")
        if len(files) >= limits.max_files:
            raise SourceParseError("openstax_file_count_limit_exceeded")
        files[relative] = record
        previous_relative = relative
        total += byte_count
        if total > limits.max_archive_uncompressed_bytes:
            raise SourceParseError("openstax_tree_size_limit_exceeded")
        parent = PurePosixPath(relative).parent
        while parent != PurePosixPath("."):
            directories.add(parent.as_posix())
            if len(directories) > limits.max_files:
                raise SourceParseError("openstax_directory_count_limit_exceeded")
            parent = parent.parent
    return files, directories


def _openstax_inventory_fd(
    root_fd: int,
    expected_files: Mapping[str, Mapping[str, Any]],
    expected_directories: set[str],
    limits: ParserLimits,
    *,
    sealed_owner_uid: int | None = None,
) -> None:
    observed_files: dict[str, dict[str, Any]] = {}
    observed_directories: set[str] = set()
    total = 0
    try:
        root_metadata = os.fstat(root_fd)
    except OSError as exc:
        raise SourceParseError("openstax_root_stat_failed") from exc
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise SourceParseError("openstax_root_not_safe_directory")
    if sealed_owner_uid is not None and (
        stat.S_IMODE(root_metadata.st_mode) != 0o500
        or root_metadata.st_uid != sealed_owner_uid
    ):
        raise SourceParseError("openstax_root_seal_invalid")
    entry_count = 0

    def visit(directory_fd: int, relative_directory: str, depth: int) -> None:
        nonlocal entry_count, total
        if depth > min(limits.max_xml_depth, 128):
            raise SourceParseError("openstax_directory_depth_limit_exceeded")
        try:
            entries = os.scandir(directory_fd)
        except OSError as exc:
            raise SourceParseError("openstax_directory_scan_failed") from exc
        with entries:
            for entry in entries:
                entry_count += 1
                if entry_count > limits.max_files * 2:
                    raise SourceParseError("openstax_entry_count_limit_exceeded")
                name = entry.name
                if name in {"", ".", ".."} or "/" in name or "\x00" in name:
                    raise SourceParseError("openstax_unsafe_entry_name")
                if name == ".git":
                    raise SourceParseError("openstax_git_metadata_rejected")
                relative = (
                    f"{relative_directory}/{name}" if relative_directory else name
                )
                _safe_archive_name(relative)
                try:
                    metadata = entry.stat(follow_symlinks=False)
                except OSError as exc:
                    raise SourceParseError("openstax_entry_stat_failed") from exc
                if stat.S_ISLNK(metadata.st_mode):
                    raise SourceParseError("openstax_symlink_rejected")
                if stat.S_ISDIR(metadata.st_mode):
                    if sealed_owner_uid is not None and (
                        stat.S_IMODE(metadata.st_mode) != 0o500
                        or metadata.st_uid != sealed_owner_uid
                    ):
                        raise SourceParseError("openstax_directory_seal_invalid")
                    if len(observed_directories) >= limits.max_files:
                        raise SourceParseError(
                            "openstax_directory_count_limit_exceeded"
                        )
                    try:
                        child_fd = os.open(
                            name,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                            dir_fd=directory_fd,
                        )
                    except OSError as exc:
                        raise SourceParseError(
                            "openstax_directory_open_failed"
                        ) from exc
                    try:
                        opened = os.fstat(child_fd)
                        if _stat_identity(metadata) != _stat_identity(opened):
                            raise SourceParseError("openstax_directory_changed")
                        observed_directories.add(relative)
                        visit(child_fd, relative, depth + 1)
                        if _stat_identity(os.fstat(child_fd)) != _stat_identity(opened):
                            raise SourceParseError("openstax_directory_changed")
                    finally:
                        os.close(child_fd)
                    continue
                if not stat.S_ISREG(metadata.st_mode):
                    raise SourceParseError("openstax_special_file_rejected")
                if sealed_owner_uid is not None and (
                    stat.S_IMODE(metadata.st_mode) != 0o400
                    or metadata.st_uid != sealed_owner_uid
                    or metadata.st_nlink != 1
                ):
                    raise SourceParseError("openstax_file_seal_invalid")
                if metadata.st_size > limits.max_member_bytes:
                    raise SourceParseError("openstax_file_size_limit_exceeded")
                try:
                    file_fd = os.open(
                        name,
                        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                        dir_fd=directory_fd,
                    )
                except OSError as exc:
                    raise SourceParseError("openstax_file_open_failed") from exc
                try:
                    opened = os.fstat(file_fd)
                    digest, byte_count = _hash_regular_fd(
                        file_fd,
                        limits.max_member_bytes,
                        "openstax_file",
                    )
                    after = os.fstat(file_fd)
                finally:
                    os.close(file_fd)
                if (
                    _stat_identity(metadata) != _stat_identity(opened)
                    or _stat_identity(opened) != _stat_identity(after)
                    or byte_count != metadata.st_size
                ):
                    raise SourceParseError("openstax_file_changed")
                if len(observed_files) >= limits.max_files:
                    raise SourceParseError("openstax_file_count_limit_exceeded")
                observed_files[relative] = {
                    "relative_path": relative,
                    "bytes": byte_count,
                    "sha256": digest,
                }
                total += byte_count
                if total > limits.max_archive_uncompressed_bytes:
                    raise SourceParseError("openstax_tree_size_limit_exceeded")

    visit(root_fd, "", 1)
    expected_normalized = {
        path: {
            "relative_path": path,
            "bytes": record["bytes"],
            "sha256": record["sha256"],
        }
        for path, record in expected_files.items()
    }
    if observed_directories != expected_directories:
        raise SourceParseError("openstax_directory_manifest_mismatch")
    if observed_files != expected_normalized:
        raise SourceParseError("openstax_file_manifest_mismatch")


@contextmanager
def _open_relative_regular_fd(
    root_fd: int,
    relative: str,
    *,
    sealed_owner_uid: int | None = None,
) -> Iterator[int]:
    parts = PurePosixPath(_safe_archive_name(relative)).parts
    try:
        current_fd = os.dup(root_fd)
    except OSError as exc:
        raise SourceParseError("openstax_root_duplicate_failed") from exc
    try:
        for part in parts[:-1]:
            try:
                child_fd = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=current_fd,
                )
            except OSError as exc:
                raise SourceParseError("openstax_directory_open_failed") from exc
            child_metadata = os.fstat(child_fd)
            if sealed_owner_uid is not None and (
                stat.S_IMODE(child_metadata.st_mode) != 0o500
                or child_metadata.st_uid != sealed_owner_uid
            ):
                os.close(child_fd)
                raise SourceParseError("acquisition_directory_seal_invalid")
            os.close(current_fd)
            current_fd = child_fd
        try:
            file_fd = os.open(
                parts[-1],
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=current_fd,
            )
        except OSError as exc:
            raise SourceParseError("openstax_file_open_failed") from exc
        try:
            file_metadata = os.fstat(file_fd)
            if not stat.S_ISREG(file_metadata.st_mode):
                raise SourceParseError("openstax_special_file_rejected")
            if sealed_owner_uid is not None and (
                stat.S_IMODE(file_metadata.st_mode) != 0o400
                or file_metadata.st_uid != sealed_owner_uid
                or file_metadata.st_nlink != 1
            ):
                raise SourceParseError("acquisition_file_seal_invalid")
            yield file_fd
        finally:
            os.close(file_fd)
    finally:
        os.close(current_fd)


def _read_openstax_manifest_file(
    root_fd: int,
    relative: str,
    expected: Mapping[str, Any],
    limits: ParserLimits,
) -> bytearray:
    with _open_relative_regular_fd(root_fd, relative) as file_fd:
        initial = os.fstat(file_fd)
        if initial.st_size > min(
            limits.max_member_bytes,
            limits.max_openstax_xml_bytes,
        ):
            raise SourceParseError("openstax_file_size_limit_exceeded")
        try:
            os.lseek(file_fd, 0, os.SEEK_SET)
            payload = bytearray()
            total = 0
            digest = hashlib.sha256()
            while True:
                chunk = os.read(file_fd, 1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > min(
                    limits.max_member_bytes,
                    limits.max_openstax_xml_bytes,
                ):
                    raise SourceParseError("openstax_file_size_limit_exceeded")
                payload.extend(chunk)
                digest.update(chunk)
            after = os.fstat(file_fd)
        except OSError as exc:
            raise SourceParseError("source_read_failed") from exc
        observed_digest = "sha256:" + digest.hexdigest()
        if (
            _stat_identity(initial) != _stat_identity(after)
            or total != expected["bytes"]
            or observed_digest != expected["sha256"]
        ):
            raise SourceParseError("openstax_file_binding_mismatch")
        return payload


@dataclass(frozen=True)
class _OpenStaxModule:
    module_id: str
    member: str
    member_sha256: str


@dataclass(frozen=True)
class _OpenStaxCollection:
    source_key: str
    member: str
    member_sha256: str
    title: str
    modules: tuple[str, ...]


def _openstax_module_identity(
    root: ET.Element, member: str, limits: ParserLimits
) -> str:
    path_id = PurePosixPath(member).parent.name
    candidates = [path_id]
    if root.attrib.get("id"):
        candidates.append(root.attrib["id"])
    for element in _qualified_elements(root, CNXML_NS, "content-id"):
        if element.text and element.text.strip():
            candidates.append(element.text.strip())
    normalized = {
        _validate_identifier(value, "openstax_module_id", limits)
        for value in candidates
    }
    if len(normalized) != 1:
        raise SourceParseError("openstax_ambiguous_module_identity")
    return normalized.pop()


def _collection_modules(root: ET.Element, limits: ParserLimits) -> tuple[str, ...]:
    values: list[str] = []
    for element in _qualified_elements(root, COLLXML_NS, "module"):
        value = element.attrib.get("document", "")
        values.append(_validate_identifier(value, "openstax_collection_module", limits))
        if len(values) > limits.max_edges_per_unit:
            raise SourceParseError("openstax_collection_module_limit_exceeded")
    if not values:
        raise SourceParseError("openstax_collection_without_modules")
    return tuple(values)


def _parse_openstax_tree_fd_units(
    root_fd: int,
    files: Mapping[str, Mapping[str, Any]],
    context: ParseContext,
    limits: ParserLimits,
) -> Iterator[SourceUnit]:
    module_members = sorted(
        member
        for member in files
        if PurePosixPath(member).name == "index.cnxml"
        and "modules" in PurePosixPath(member).parts
    )
    collection_members = sorted(
        member
        for member in files
        if member.endswith(".collection.xml")
        and "collections" in PurePosixPath(member).parts
    )
    if not module_members or not collection_members:
        raise SourceParseError("openstax_required_cnxml_missing")
    if len(module_members) + len(collection_members) > limits.max_units:
        raise SourceParseError("unit_limit_exceeded")

    modules: dict[str, _OpenStaxModule] = {}
    for member in module_members:
        content = _read_openstax_manifest_file(
            root_fd,
            member,
            files[member],
            limits,
        )
        parsed = _secure_xml_from_bytes(content, limits)
        _require_qualified_root(
            parsed,
            CNXML_NS,
            "document",
            "openstax_cnxml_namespace_mismatch",
        )
        _reject_confusable_namespaces(
            parsed,
            _CNXML_SEMANTIC_NAMESPACES,
            "openstax_cnxml_namespace_mismatch",
        )
        module_id = _openstax_module_identity(parsed, member, limits)
        if module_id in modules:
            raise SourceParseError("openstax_duplicate_module_identity")
        modules[module_id] = _OpenStaxModule(
            module_id,
            member,
            "sha256:" + hashlib.sha256(content).hexdigest(),
        )

    collections: list[_OpenStaxCollection] = []
    collection_keys: set[str] = set()
    for member in collection_members:
        content = _read_openstax_manifest_file(
            root_fd,
            member,
            files[member],
            limits,
        )
        parsed = _secure_xml_from_bytes(content, limits)
        _require_qualified_root(
            parsed,
            COLLXML_NS,
            "collection",
            "openstax_collxml_namespace_mismatch",
        )
        _reject_confusable_namespaces(
            parsed,
            _COLLXML_SEMANTIC_NAMESPACES,
            "openstax_collxml_namespace_mismatch",
        )
        source_key = "collection:" + member
        if source_key in collection_keys:
            raise SourceParseError("openstax_duplicate_collection_identity")
        collection_keys.add(source_key)
        title = _qualified_xml_title(
            parsed,
            COLLXML_NS,
            PurePosixPath(member).stem,
            limits,
        )
        module_ids = _collection_modules(parsed, limits)
        missing = sorted(set(module_ids) - set(modules))
        if missing:
            raise SourceParseError("openstax_collection_reference_missing_module")
        collections.append(
            _OpenStaxCollection(
                source_key,
                member,
                "sha256:" + hashlib.sha256(content).hexdigest(),
                title,
                module_ids,
            )
        )

    module_edges: dict[str, set[SourceEdge]] = {
        module_id: set() for module_id in modules
    }
    module_structural_evidence: dict[str, set[str]] = {
        module_id: set() for module_id in modules
    }
    for collection in collections:
        for position, module_id in enumerate(collection.modules, start=1):
            module_edges[module_id].add(
                _make_edge(
                    context,
                    "hierarchy",
                    "collection_membership",
                    collection.source_key,
                    limits,
                )
            )
            module_structural_evidence[module_id].add(
                f"{collection.source_key}:position:{position}"
            )
            if (
                len(module_edges[module_id]) > limits.max_edges_per_unit
                or len(module_structural_evidence[module_id])
                > limits.max_edges_per_unit
            ):
                raise SourceParseError("openstax_module_membership_limit_exceeded")

    for collection in collections:
        text = collection.title
        yield _make_unit(
            context=context,
            source_key=collection.source_key,
            kind="textbook_collection",
            title=collection.title,
            text=text,
            synonyms=(),
            edges=(),
            flags=SourceFlags(
                missing_media=False,
                has_table=False,
                has_numeric_content=bool(NUMERIC_RE.search(text)),
                present_visual_media=False,
                uninterpreted_nontext_media=False,
                visual_context_quarantined=False,
            ),
            source_member=collection.member,
            record_locator=collection.source_key,
            record_value={
                "member_sha256": collection.member_sha256,
                "modules": list(collection.modules),
            },
            limits=limits,
        )

    file_names = set(files)
    for module_id in sorted(modules):
        module = modules[module_id]
        content = _read_openstax_manifest_file(
            root_fd,
            module.member,
            files[module.member],
            limits,
        )
        module_root = _secure_xml_from_bytes(content, limits)
        _require_qualified_root(
            module_root,
            CNXML_NS,
            "document",
            "openstax_cnxml_namespace_mismatch",
        )
        _reject_confusable_namespaces(
            module_root,
            _CNXML_SEMANTIC_NAMESPACES,
            "openstax_cnxml_namespace_mismatch",
        )
        if _openstax_module_identity(module_root, module.member, limits) != module_id:
            raise SourceParseError("openstax_module_identity_changed")
        semantic_root = _first_qualified_element(module_root, CNXML_NS, "content")
        if semantic_root is None:
            raise SourceParseError("openstax_cnxml_content_missing")
        text = _element_text(semantic_root, limits)

        def resolve_media(reference: str) -> str | None:
            parsed = urlsplit(reference)
            if parsed.scheme == "data":
                return "inline_data_uri"
            if parsed.scheme or parsed.netloc:
                return None
            decoded = unquote(parsed.path)
            if not decoded:
                return None
            resolved = posixpath.normpath(
                posixpath.join(posixpath.dirname(module.member), decoded)
            )
            try:
                resolved = _safe_archive_name(resolved)
            except SourceParseError:
                raise SourceParseError("unsafe_openstax_media_reference") from None
            return resolved if resolved in file_names else None

        media = _xml_media_analysis(
            semantic_root,
            text,
            resolve_media,
            CNXML_NS,
            limits,
        )

        yield _make_unit(
            context=context,
            source_key=f"module:{module_id}",
            kind="textbook_module",
            title=_qualified_xml_title(module_root, CNXML_NS, module_id, limits),
            text=text,
            synonyms=(),
            edges=module_edges[module_id],
            flags=media.flags,
            source_member=module.member,
            record_locator=f"module:{module_id}",
            record_value={
                "member_sha256": module.member_sha256,
                "module_id": module_id,
            },
            limits=limits,
            facets={
                "media_dependency_member": media.present_dependencies,
                "structural_sequence_evidence": module_structural_evidence[module_id],
            },
        )


def _iter_held_openstax_fd(
    root_fd: int,
    context: ParseContext,
    limits: ParserLimits,
    external_revalidator: Callable[[], None] | None = None,
    sealed_owner_uid: int | None = None,
) -> Iterator[SourceUnit]:
    files, directories = _openstax_expected_manifest(context, limits)
    try:
        initial_root = os.fstat(root_fd)
    except OSError as exc:
        raise SourceParseError("openstax_root_stat_failed") from exc
    if not stat.S_ISDIR(initial_root.st_mode):
        raise SourceParseError("openstax_root_not_safe_directory")
    if sealed_owner_uid is not None and (
        stat.S_IMODE(initial_root.st_mode) != 0o500
        or initial_root.st_uid != sealed_owner_uid
    ):
        raise SourceParseError("openstax_root_seal_invalid")
    root_identity = _stat_identity(initial_root)
    _openstax_inventory_fd(
        root_fd,
        files,
        directories,
        limits,
        sealed_owner_uid=sealed_owner_uid,
    )

    def revalidate() -> None:
        _openstax_inventory_fd(
            root_fd,
            files,
            directories,
            limits,
            sealed_owner_uid=sealed_owner_uid,
        )
        try:
            final_root = os.fstat(root_fd)
        except OSError as exc:
            raise SourceParseError("openstax_root_stat_failed") from exc
        if _stat_identity(final_root) != root_identity:
            raise SourceParseError("openstax_root_changed_during_parse")
        if external_revalidator is not None:
            external_revalidator()

    yield from _spool_all_or_nothing(
        _parse_openstax_tree_fd_units(root_fd, files, context, limits),
        context,
        limits,
        revalidate,
    )


def parse_wordnet_tar(
    path: str | os.PathLike[str],
    context: ParseContext,
    limits: ParserLimits = DEFAULT_LIMITS,
) -> Iterator[SourceUnit]:
    """Low-level, non-authoritative WordNet fixture parser."""

    yield from _iter_regular_path(path, context, limits, _parse_wordnet_tar_handle)


def parse_nalt_turtle_zip(
    path: str | os.PathLike[str],
    context: ParseContext,
    limits: ParserLimits = DEFAULT_LIMITS,
) -> Iterator[SourceUnit]:
    """Low-level, non-authoritative NALT fixture parser."""

    yield from _iter_regular_path(
        path,
        context,
        limits,
        _parse_nalt_turtle_zip_handle,
    )


def parse_obo(
    path: str | os.PathLike[str],
    context: ParseContext,
    limits: ParserLimits = DEFAULT_LIMITS,
) -> Iterator[SourceUnit]:
    """Low-level, non-authoritative OBO fixture parser."""

    yield from _iter_regular_path(path, context, limits, _parse_obo_handle)


def parse_usgs_skos_rdf(
    path: str | os.PathLike[str],
    context: ParseContext,
    limits: ParserLimits = DEFAULT_LIMITS,
) -> Iterator[SourceUnit]:
    """Low-level, non-authoritative RDF/XML fixture parser."""

    yield from _iter_regular_path(
        path,
        context,
        limits,
        _parse_usgs_skos_rdf_handle,
    )


def parse_siyavula_epub(
    path: str | os.PathLike[str],
    context: ParseContext,
    limits: ParserLimits = DEFAULT_LIMITS,
) -> Iterator[SourceUnit]:
    """Low-level, non-authoritative EPUB fixture parser."""

    yield from _iter_regular_path(
        path,
        context,
        limits,
        _parse_siyavula_epub_handle,
    )


def parse_openstax_tree(
    path: str | os.PathLike[str],
    context: ParseContext,
    limits: ParserLimits = DEFAULT_LIMITS,
) -> Iterator[SourceUnit]:
    """Low-level, non-authoritative OpenStax fixture parser."""

    limits.validate()
    context.validate(limits)
    try:
        root_fd = os.open(
            os.fspath(path),
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
    except OSError as exc:
        raise SourceParseError("openstax_root_open_no_follow_failed") from exc
    root_identity = _stat_identity(os.fstat(root_fd))

    def revalidate_path() -> None:
        try:
            reopened = os.open(
                os.fspath(path),
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
        except OSError as exc:
            raise SourceParseError("openstax_root_reopen_failed") from exc
        try:
            if _stat_identity(os.fstat(reopened)) != root_identity:
                raise SourceParseError("openstax_root_path_changed")
        finally:
            os.close(reopened)

    try:
        yield from _iter_held_openstax_fd(
            root_fd,
            context,
            limits,
            revalidate_path,
        )
    finally:
        os.close(root_fd)


UNVERIFIED_PARSER_FORMATS = {
    "wordnet_tar": parse_wordnet_tar,
    "nalt_turtle_zip": parse_nalt_turtle_zip,
    "obo": parse_obo,
    "usgs_skos_rdf": parse_usgs_skos_rdf,
    "siyavula_epub": parse_siyavula_epub,
    "openstax_tree": parse_openstax_tree,
}


def iter_unverified_source_units(
    source_format: str,
    path: str | os.PathLike[str],
    context: ParseContext,
    limits: ParserLimits = DEFAULT_LIMITS,
) -> Iterator[SourceUnit]:
    """Dispatch only low-level fixtures; this is never an authority API."""

    parser = UNVERIFIED_PARSER_FORMATS.get(source_format)
    if parser is None:
        raise SourceParseError("unsupported_source_format")
    yield from parser(path, context, limits)


@dataclass(frozen=True)
class _CanonicalJsonArtifact:
    payload: bytes
    value: dict[str, Any]
    identity: tuple[int, ...]


@dataclass(frozen=True)
class _RegularArtifact:
    payload: bytes
    sha256: str
    identity: tuple[int, ...]


@dataclass(frozen=True)
class _ActionAuthorityClosure:
    action_root_identity: tuple[int, ...]
    candidate_runs_identity: tuple[int, ...]
    checkout_identity: tuple[int, ...]
    preregistration: _CanonicalJsonArtifact
    native_manifest: _RegularArtifact
    native_launch_envelope: _CanonicalJsonArtifact
    native_build_receipt: _CanonicalJsonArtifact
    native_binary: _RegularArtifact
    source_file_artifacts: tuple[tuple[str, _RegularArtifact], ...]
    source_commit: str


@dataclass(frozen=True)
class _VerifiedSourceBinding:
    context: ParseContext
    source_format: str
    local_locator: str
    is_tree: bool
    owner_uid: int
    candidate_path: Path
    candidate_identity: tuple[int, ...]
    receipt: _CanonicalJsonArtifact
    completion: _CanonicalJsonArtifact
    expected_authority: ProductionAuthorityExpectation
    authority_closure: _ActionAuthorityClosure
    production_verification: ProductionVerificationRecord


def _read_canonical_contract_json_at(
    directory_fd: int,
    name: str,
    max_bytes: int = 64 * 1024 * 1024,
) -> _CanonicalJsonArtifact:
    claim_name_allowed = bool(
        re.fullmatch(
            r"\.[0-9]{8}T[0-9]{6}Z_cur0s_commercial_sources_v1\."
            r"cur0s_execution_claim\.json",
            name,
        )
    )
    if name not in {"receipt.json", "COMPLETE.json"} and not claim_name_allowed:
        raise SourceParseError("terminal_artifact_name_invalid")
    try:
        fd = os.open(
            name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=directory_fd,
        )
    except OSError as exc:
        raise SourceParseError("terminal_artifact_open_failed") from exc
    try:
        initial = os.fstat(fd)
        if (
            not stat.S_ISREG(initial.st_mode)
            or stat.S_IMODE(initial.st_mode) != 0o400
            or initial.st_nlink != 1
            or initial.st_size <= 1
            or initial.st_size > max_bytes
        ):
            raise SourceParseError("terminal_artifact_metadata_invalid")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise SourceParseError("terminal_artifact_size_limit_exceeded")
            chunks.append(chunk)
        final = os.fstat(fd)
    except OSError as exc:
        raise SourceParseError("terminal_artifact_read_failed") from exc
    finally:
        os.close(fd)
    if _stat_identity(initial) != _stat_identity(final) or total != initial.st_size:
        raise SourceParseError("terminal_artifact_changed")
    payload = b"".join(chunks)
    try:
        value = json.loads(
            payload,
            object_pairs_hook=_reject_duplicate_json_object,
        )
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise SourceParseError("terminal_artifact_json_invalid") from exc
    if not isinstance(value, dict):
        raise SourceParseError("terminal_artifact_json_invalid")
    if _contract_canonical_json_bytes(value) + b"\n" != payload:
        raise SourceParseError("terminal_artifact_not_canonical")
    return _CanonicalJsonArtifact(payload, value, _stat_identity(final))


def _read_regular_artifact_at(
    directory_fd: int,
    name: str,
    *,
    exact_mode: int | frozenset[int],
    owner_uid: int,
    max_bytes: int,
    error_prefix: str,
) -> _RegularArtifact:
    if (
        not isinstance(name, str)
        or not name
        or Path(name).parts != (name,)
        or name in {".", ".."}
    ):
        raise SourceParseError(f"{error_prefix}_name_invalid")
    try:
        directory_metadata = os.fstat(directory_fd)
        fd = os.open(
            name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=directory_fd,
        )
    except OSError as exc:
        raise SourceParseError(f"{error_prefix}_open_failed") from exc
    try:
        initial = os.fstat(fd)
        entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        allowed_modes = (
            exact_mode if isinstance(exact_mode, frozenset) else frozenset({exact_mode})
        )
        if (
            not stat.S_ISREG(initial.st_mode)
            or _stat_identity(initial) != _stat_identity(entry)
            or stat.S_IMODE(initial.st_mode) not in allowed_modes
            or initial.st_uid != owner_uid
            or initial.st_gid != directory_metadata.st_gid
            or initial.st_nlink != 1
            or initial.st_size <= 0
            or initial.st_size > max_bytes
        ):
            raise SourceParseError(f"{error_prefix}_metadata_invalid")
        digest, byte_count = _hash_regular_fd(fd, max_bytes, error_prefix)
        os.lseek(fd, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        remaining = byte_count
        while remaining:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                raise SourceParseError(f"{error_prefix}_short_read")
            chunks.append(chunk)
            remaining -= len(chunk)
        final = os.fstat(fd)
        final_entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except OSError as exc:
        raise SourceParseError(f"{error_prefix}_read_failed") from exc
    finally:
        os.close(fd)
    if not (
        _stat_identity(initial) == _stat_identity(final) == _stat_identity(final_entry)
    ):
        raise SourceParseError(f"{error_prefix}_changed")
    payload = b"".join(chunks)
    if "sha256:" + hashlib.sha256(payload).hexdigest() != digest:
        raise SourceParseError(f"{error_prefix}_changed")
    return _RegularArtifact(payload, digest, _stat_identity(final))


def _decode_canonical_json_artifact(
    artifact: _RegularArtifact,
    *,
    trailing_newline: bool,
    error_prefix: str,
) -> _CanonicalJsonArtifact:
    try:
        value = json.loads(
            artifact.payload,
            object_pairs_hook=_reject_duplicate_json_object,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                SourceParseError(f"{error_prefix}_nonfinite")
            ),
        )
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise SourceParseError(f"{error_prefix}_json_invalid") from exc
    if not isinstance(value, dict):
        raise SourceParseError(f"{error_prefix}_json_invalid")
    expected = _contract_canonical_json_bytes(value)
    if trailing_newline:
        expected += b"\n"
    if artifact.payload != expected:
        raise SourceParseError(f"{error_prefix}_not_canonical")
    return _CanonicalJsonArtifact(artifact.payload, value, artifact.identity)


def _read_canonical_json_artifact_at(
    directory_fd: int,
    name: str,
    *,
    exact_mode: int | frozenset[int],
    owner_uid: int,
    max_bytes: int,
    trailing_newline: bool,
    error_prefix: str,
) -> _CanonicalJsonArtifact:
    artifact = _read_regular_artifact_at(
        directory_fd,
        name,
        exact_mode=exact_mode,
        owner_uid=owner_uid,
        max_bytes=max_bytes,
        error_prefix=error_prefix,
    )
    return _decode_canonical_json_artifact(
        artifact,
        trailing_newline=trailing_newline,
        error_prefix=error_prefix,
    )


def _require_exact_mapping(
    value: Any,
    fields: set[str],
    error: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise SourceParseError(error)
    return value


def _require_sha256(value: Any, error: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise SourceParseError(error)
    return value


def _require_nonnegative_int(value: Any, error: str) -> int:
    if type(value) is not int or value < 0:
        raise SourceParseError(error)
    return value


def _require_positive_int(value: Any, error: str) -> int:
    result = _require_nonnegative_int(value, error)
    if result == 0:
        raise SourceParseError(error)
    return result


def _require_finite_number(value: Any, error: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SourceParseError(error)
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise SourceParseError(error)
    return result


def _parse_utc_second(value: Any, error: str) -> datetime:
    if (
        not isinstance(value, str)
        or re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
            value,
        )
        is None
    ):
        raise SourceParseError(error)
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        raise SourceParseError(error) from None
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise SourceParseError(error)
    return parsed


def _validate_source_root_claims(
    source_root: Any,
    contract_root: str,
    commercial: Any,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    fields = {
        "schema_version",
        "lane",
        "contract_root_sha256",
        "artifacts",
        "source_artifact_count",
        "hard_rejects",
        "stage_source_ids",
        "rights_classes",
        "raw_source_custody",
        "source_root_state",
        "all_source_identity_and_rights_gates_passed",
        "private_HF_mirror_completed",
        "c4_rx_content_present",
        "first_next_blocker",
        "semantic_rows_compiled",
        "near_semantic_arm_C_executed",
        "connected_split_assigned",
        "cur0s_static_pass_claimed",
        "target_data_learning_claimed",
        "authority_claimed",
        "source_root_sha256",
    }
    root = _require_exact_mapping(
        source_root,
        fields,
        "acquisition_source_root_schema_invalid",
    )
    artifacts = root.get("artifacts")
    if not isinstance(artifacts, list) or not all(
        isinstance(artifact, dict) for artifact in artifacts
    ):
        raise SourceParseError("acquisition_source_root_artifacts_invalid")
    artifact_ids = [artifact.get("source_id") for artifact in artifacts]
    if len(set(artifact_ids)) != len(artifact_ids):
        raise SourceParseError("acquisition_source_root_duplicate_source_id")
    false_fields = {
        "private_HF_mirror_completed",
        "c4_rx_content_present",
        "semantic_rows_compiled",
        "near_semantic_arm_C_executed",
        "connected_split_assigned",
        "cur0s_static_pass_claimed",
        "target_data_learning_claimed",
        "authority_claimed",
    }
    root_body = dict(root)
    root_sha256 = root_body.pop("source_root_sha256", None)
    if (
        root.get("schema_version") != "cur0s_commercial_source_root_v1"
        or root.get("lane") != "C4-COM"
        or root.get("contract_root_sha256") != contract_root
        or type(root.get("source_artifact_count")) is not int
        or root.get("source_artifact_count") != len(artifacts)
        or root.get("raw_source_custody") != "phone_private"
        or root.get("source_root_state") != "passed_scope"
        or root.get("all_source_identity_and_rights_gates_passed") is not True
        or root.get("first_next_blocker") != "private_C4_COM_mirror"
        or any(root.get(field) is not False for field in false_fields)
        or root_sha256 != commercial.canonical_sha256(root_body)
    ):
        raise SourceParseError("acquisition_source_root_claim_invalid")
    for field in ("hard_rejects", "rights_classes"):
        if not isinstance(root.get(field), list):
            raise SourceParseError("acquisition_source_root_summary_invalid")
    stage_source_ids = root.get("stage_source_ids")
    if (
        not isinstance(stage_source_ids, dict)
        or set(stage_source_ids)
        != {
            "C1",
            "C2",
            "B23",
            "C3",
            "C4",
        }
        or any(
            not isinstance(values, list)
            or any(not isinstance(value, str) for value in values)
            for values in stage_source_ids.values()
        )
    ):
        raise SourceParseError("acquisition_source_root_stage_summary_invalid")
    return artifacts, {artifact["source_id"]: artifact for artifact in artifacts}


def _validate_final_source_custody(
    value: Any,
    artifacts: Sequence[Mapping[str, Any]],
    commercial: Any,
) -> None:
    fields = {
        "schema_version",
        "artifact_count",
        "artifacts",
        "candidate_entry_set",
        "C4_COM_and_C4_RX_roots_separate",
        "fd_root_O_NOFOLLOW_readback",
        "raw_payload_egressed",
        "reattestation_root_sha256",
    }
    custody = _require_exact_mapping(
        value,
        fields,
        "acquisition_final_source_custody_schema_invalid",
    )
    observations = custody.get("artifacts")
    expected_observations = []
    for artifact in artifacts:
        manifest = artifact.get("content_manifest")
        if not isinstance(manifest, dict):
            raise SourceParseError("acquisition_source_manifest_invalid")
        expected_observations.append(
            {
                "source_id": artifact.get("source_id"),
                "acquisition_mode": artifact.get("acquisition_mode"),
                "bytes": artifact.get("bytes"),
                "sha256": artifact.get("sha256"),
                "content_manifest_sha256": commercial.canonical_sha256(manifest),
            }
        )
    expected_observations.sort(key=lambda record: record["source_id"])
    body = dict(custody)
    root = body.pop("reattestation_root_sha256", None)
    if (
        custody.get("schema_version") != "cur0s_final_source_custody_reattestation_v1"
        or type(custody.get("artifact_count")) is not int
        or custody.get("artifact_count") != len(expected_observations)
        or observations != expected_observations
        or custody.get("candidate_entry_set") != ["sources"]
        or custody.get("C4_COM_and_C4_RX_roots_separate") is not True
        or custody.get("fd_root_O_NOFOLLOW_readback") is not True
        or custody.get("raw_payload_egressed") is not False
        or root != commercial.canonical_sha256(body)
    ):
        raise SourceParseError("acquisition_final_source_custody_invalid")


def _validate_source_execution_identity(
    value: Any,
    receipt_value: Mapping[str, Any],
    artifacts: Sequence[Mapping[str, Any]],
    commercial: Any,
    preregistration: Mapping[str, Any],
    native_manifest: _RegularArtifact,
) -> None:
    fields = {
        "source_commit",
        "source_file_sha256",
        "source_file_bindings",
        "git_HEAD_verified",
        "bound_source_files_clean",
        "preimport_source_bytes_verified",
        "commercial_source_contract_sha256",
        "commercial_source_contract_root_sha256",
        "phone_toolchain_identity_sha256",
        "phone_toolchain_root_sha256",
        "native_preflight_contract_sha256",
        "native_preflight_contract_root_sha256",
        "native_preflight_execution",
        "native_preflight_final_revalidation",
        "final_source_custody_reattestation",
    }
    identity = _require_exact_mapping(
        value,
        fields,
        "acquisition_source_execution_identity_schema_invalid",
    )
    source_commit = identity.get("source_commit")
    source_file_sha256 = identity.get("source_file_sha256")
    source_file_bindings = identity.get("source_file_bindings")
    prereg_source_bindings = preregistration.get("source_file_bindings")
    expected_hash_fields = {"commercial_sources_sha256", "runner_sha256"}
    if (
        not isinstance(source_commit, str)
        or COMMIT_RE.fullmatch(source_commit) is None
        or not isinstance(source_file_sha256, dict)
        or set(source_file_sha256) != expected_hash_fields
        or not isinstance(source_file_bindings, dict)
        or set(source_file_bindings) != set(BOUND_SOURCE_FILES)
        or identity.get("git_HEAD_verified") is not True
        or identity.get("bound_source_files_clean") is not True
        or identity.get("preimport_source_bytes_verified") is not True
        or source_commit != preregistration.get("source_commit")
        or source_file_bindings != prereg_source_bindings
        or source_file_sha256 != preregistration.get("source_file_sha256")
    ):
        raise SourceParseError("acquisition_source_execution_identity_invalid")
    for field in expected_hash_fields:
        _require_sha256(
            source_file_sha256[field],
            "acquisition_source_file_hash_invalid",
        )
    for relative_path, binding in source_file_bindings.items():
        binding = _require_exact_mapping(
            binding,
            {"bytes", "sha256", "git_blob_oid"},
            "acquisition_source_file_binding_schema_invalid",
        )
        _require_positive_int(
            binding.get("bytes"),
            "acquisition_source_file_binding_bytes_invalid",
        )
        _require_sha256(
            binding.get("sha256"),
            "acquisition_source_file_binding_hash_invalid",
        )
        if (
            not isinstance(binding.get("git_blob_oid"), str)
            or COMMIT_RE.fullmatch(binding["git_blob_oid"]) is None
        ):
            raise SourceParseError("acquisition_source_file_git_oid_invalid")
        hash_field = (
            "commercial_sources_sha256"
            if relative_path == BOUND_SOURCE_FILES[0]
            else "runner_sha256"
        )
        if source_file_sha256[hash_field] != binding["sha256"]:
            raise SourceParseError("acquisition_source_file_hash_binding_invalid")
    toolchain = preregistration.get("phone_toolchain_identity")
    native_contract = preregistration.get("native_preflight")
    if not isinstance(toolchain, Mapping) or not isinstance(native_contract, Mapping):
        raise SourceParseError("acquisition_preregistration_contract_missing")
    if (
        identity.get("commercial_source_contract_sha256")
        != receipt_value.get("commercial_source_contract_sha256")
        or identity.get("commercial_source_contract_root_sha256")
        != receipt_value.get("commercial_source_contract_root_sha256")
        or identity.get("phone_toolchain_identity_sha256")
        != commercial.canonical_sha256(toolchain)
        or identity.get("phone_toolchain_root_sha256")
        != toolchain.get("toolchain_root_sha256")
        or identity.get("native_preflight_contract_sha256")
        != commercial.canonical_sha256(native_contract)
        or identity.get("native_preflight_contract_root_sha256")
        != native_contract.get("contract_root_sha256")
    ):
        raise SourceParseError("acquisition_source_execution_contract_binding_invalid")
    for field in (
        "native_preflight_contract_sha256",
        "native_preflight_contract_root_sha256",
    ):
        _require_sha256(
            identity.get(field),
            "acquisition_native_preflight_binding_invalid",
        )
    native_execution = _validate_native_preflight_execution_receipt(
        identity.get("native_preflight_execution"),
        preregistration,
        native_manifest,
    )
    native_final = _validate_native_preflight_execution_receipt(
        identity.get("native_preflight_final_revalidation"),
        preregistration,
        native_manifest,
    )
    if native_execution != native_final:
        raise SourceParseError("acquisition_native_preflight_revalidation_mismatch")
    _validate_final_source_custody(
        identity.get("final_source_custody_reattestation"),
        artifacts,
        commercial,
    )


def _validate_native_preflight_execution_receipt(
    value: Any,
    preregistration: Mapping[str, Any],
    native_manifest: _RegularArtifact,
) -> dict[str, Any]:
    fields = {
        "schema_version",
        "manifest_sha256",
        "manifest_bytes",
        "entries_verified",
        "passes_completed",
        "same_pid_execveat_verified",
        "sealed_memfd_attestation_verified",
        "fixed_fd_map",
        "fixed_fd_map_matches_preregistration",
        "outer_env_observed",
        "outer_environment_sha256",
        "outer_launch_contract_sha256",
        "outer_launcher_argv_preregistered",
        "helper_dependency_swap_safety_claimed",
        "security_ceiling",
        "validated_before_candidate_preparation_and_execution_claim",
    }
    observed = _require_exact_mapping(
        value,
        fields,
        "acquisition_native_preflight_execution_schema_invalid",
    )
    native = preregistration.get("native_preflight")
    if not isinstance(native, Mapping):
        raise SourceParseError("acquisition_native_preflight_contract_missing")
    static_records = native.get("static_manifest_records")
    fixed_fds = native.get("fixed_fd_map")
    outer_launch = native.get("outer_launch")
    if (
        not isinstance(static_records, list)
        or not isinstance(fixed_fds, Mapping)
        or not isinstance(outer_launch, Mapping)
    ):
        raise SourceParseError("acquisition_native_preflight_contract_invalid")
    expected = {
        "schema_version": "cur0s_native_launch_attestation_v1",
        "manifest_sha256": native_manifest.sha256,
        "manifest_bytes": len(native_manifest.payload),
        "entries_verified": len(static_records) + 1,
        "passes_completed": 2,
        "same_pid_execveat_verified": True,
        "sealed_memfd_attestation_verified": True,
        "fixed_fd_map": dict(fixed_fds),
        "fixed_fd_map_matches_preregistration": True,
        "outer_env_observed": True,
        "outer_environment_sha256": outer_launch.get("outer_environment_sha256"),
        "outer_launch_contract_sha256": native.get("outer_launch_sha256"),
        "outer_launcher_argv_preregistered": True,
        "helper_dependency_swap_safety_claimed": False,
        "security_ceiling": native.get("security_ceiling"),
        "validated_before_candidate_preparation_and_execution_claim": True,
    }
    boolean_fields = {
        "same_pid_execveat_verified",
        "sealed_memfd_attestation_verified",
        "fixed_fd_map_matches_preregistration",
        "outer_env_observed",
        "outer_launcher_argv_preregistered",
        "helper_dependency_swap_safety_claimed",
        "validated_before_candidate_preparation_and_execution_claim",
    }
    integer_fields = {"manifest_bytes", "entries_verified", "passes_completed"}
    observed_fixed_fds = observed.get("fixed_fd_map")
    if (
        observed != expected
        or any(observed.get(field) is not expected[field] for field in boolean_fields)
        or any(type(observed.get(field)) is not int for field in integer_fields)
        or not isinstance(observed_fixed_fds, dict)
        or set(observed_fixed_fds) != set(fixed_fds)
        or any(type(fd) is not int for fd in observed_fixed_fds.values())
    ):
        raise SourceParseError("acquisition_native_preflight_execution_invalid")
    return dict(observed)


def _validate_phone_toolchain_receipt(value: Any, commercial: Any) -> None:
    fields = {
        "toolchain_root_sha256",
        "artifact_count",
        "artifact_manifest_sha256",
        "command_probe_count",
        "command_probe_manifest_sha256",
        "python_stdlib_tree_root_sha256",
        "python_stdlib_tree_entry_count",
        "python_stdlib_tree_volatile_identity",
        "current_process_identity_sha256",
        "current_process_executable_mapping_count",
        "validated_before_candidate_preparation_and_execution_claim",
        "final_revalidation",
    }
    observed = _require_exact_mapping(
        value,
        fields,
        "acquisition_phone_toolchain_receipt_schema_invalid",
    )
    contract = commercial.phone_toolchain_contract()
    artifacts = contract["artifacts"]
    probes = contract["command_probes"]
    stdlib = contract["python_stdlib_tree"]
    volatile = observed.get("python_stdlib_tree_volatile_identity")
    for count_field in (
        "artifact_count",
        "command_probe_count",
        "python_stdlib_tree_entry_count",
    ):
        _require_nonnegative_int(
            observed.get(count_field),
            "acquisition_phone_toolchain_receipt_invalid",
        )
    if (
        observed.get("toolchain_root_sha256") != contract["toolchain_root_sha256"]
        or observed.get("artifact_count") != len(artifacts)
        or observed.get("artifact_manifest_sha256")
        != commercial.canonical_sha256(artifacts)
        or observed.get("command_probe_count") != len(probes)
        or observed.get("command_probe_manifest_sha256")
        != commercial.canonical_sha256(probes)
        or observed.get("python_stdlib_tree_root_sha256") != stdlib["root_sha256"]
        or observed.get("python_stdlib_tree_entry_count") != stdlib["entry_count"]
        or not isinstance(volatile, list)
        or len(volatile) != 9
        or any(type(item) is not int or item < 0 for item in volatile)
        or observed.get("validated_before_candidate_preparation_and_execution_claim")
        is not True
    ):
        raise SourceParseError("acquisition_phone_toolchain_receipt_invalid")
    _require_sha256(
        observed.get("current_process_identity_sha256"),
        "acquisition_current_process_identity_invalid",
    )
    _require_positive_int(
        observed.get("current_process_executable_mapping_count"),
        "acquisition_current_process_mapping_count_invalid",
    )
    final = _require_exact_mapping(
        observed.get("final_revalidation"),
        {
            "toolchain_root_sha256",
            "artifact_count",
            "python_stdlib_tree_root_sha256",
            "current_process_identity_sha256",
            "final_revalidation_passed",
        },
        "acquisition_phone_toolchain_final_schema_invalid",
    )
    expected_final = {
        "toolchain_root_sha256": observed["toolchain_root_sha256"],
        "artifact_count": observed["artifact_count"],
        "python_stdlib_tree_root_sha256": observed["python_stdlib_tree_root_sha256"],
        "current_process_identity_sha256": observed["current_process_identity_sha256"],
        "final_revalidation_passed": True,
    }
    if (
        final != expected_final
        or type(final.get("artifact_count")) is not int
        or final.get("final_revalidation_passed") is not True
    ):
        raise SourceParseError("acquisition_phone_toolchain_final_invalid")


def _validate_runtime_identity(value: Any, commercial: Any) -> None:
    fields = {
        "model",
        "device",
        "soc",
        "architecture",
        "python_platform_system",
        "private_home_sha256",
        "build_fingerprint_sha256",
        "adb_serial_sha256",
        "adb_serial_runtime_visibility",
        "phone_private_runtime_guard_passed",
        "phone_toolchain",
    }
    runtime = _require_exact_mapping(
        value,
        fields,
        "acquisition_runtime_identity_schema_invalid",
    )
    expected = {
        "model": "NX789J",
        "device": "NX789J",
        "soc": "SM8750",
        "architecture": "aarch64",
        "python_platform_system": "Android",
        "private_home_sha256": "sha256:"
        + hashlib.sha256(str(PHONE_HOME).encode("utf-8")).hexdigest(),
        "build_fingerprint_sha256": EXPECTED_BUILD_FINGERPRINT_SHA256,
        "adb_serial_sha256": EXPECTED_ADB_SERIAL_SHA256,
        "adb_serial_runtime_visibility": "external_ADB_custody_only",
        "phone_private_runtime_guard_passed": True,
    }
    if (
        any(
            runtime.get(field) != expected_value
            for field, expected_value in expected.items()
        )
        or runtime.get("phone_private_runtime_guard_passed") is not True
    ):
        raise SourceParseError("acquisition_runtime_identity_invalid")
    _validate_phone_toolchain_receipt(runtime.get("phone_toolchain"), commercial)


def _validate_authority_bindings(value: Any) -> dict[str, Any]:
    fields = {
        "parent_capsule_sha256",
        "parent_frontier_root_sha256",
        "maximal_selector_sha256",
        "campaign_lease_root_sha256",
        "resource_slice_root_sha256",
        "network_policy_root_sha256",
        "preregistration_sha256",
        "preregistration_root_sha256",
        "ACCESS_receipt_sha256",
    }
    bindings = _require_exact_mapping(
        value,
        fields,
        "acquisition_authority_bindings_schema_invalid",
    )
    if (
        bindings.get("parent_capsule_sha256") != EXPECTED_PARENT_CAPSULE_SHA256
        or bindings.get("parent_frontier_root_sha256")
        != EXPECTED_PARENT_FRONTIER_ROOT_SHA256
        or bindings.get("maximal_selector_sha256")
        != EXPECTED_PARENT_FRONTIER_ROOT_SHA256
        or bindings.get("ACCESS_receipt_sha256") != EXPECTED_ACCESS_RECEIPT_SHA256
    ):
        raise SourceParseError("acquisition_authority_parent_binding_invalid")
    for field in fields - {
        "parent_capsule_sha256",
        "parent_frontier_root_sha256",
        "maximal_selector_sha256",
        "ACCESS_receipt_sha256",
    }:
        _require_sha256(
            bindings.get(field),
            "acquisition_authority_hash_invalid",
        )
    return bindings


def _validate_custody(value: Any) -> None:
    expected = {
        "raw_source_owner": "phone",
        "raw_source_path_egressed": False,
        "raw_payload_egressed": False,
        "Mac_raw_cache": False,
        "receipt_contains_hash_bound_aggregates_only": True,
        "C4_COM_and_C4_RX_roots_separate": True,
    }
    boolean_fields = {
        "raw_source_path_egressed",
        "raw_payload_egressed",
        "Mac_raw_cache",
        "receipt_contains_hash_bound_aggregates_only",
        "C4_COM_and_C4_RX_roots_separate",
    }
    if value != expected or any(
        value.get(field) is not expected[field]
        for field in boolean_fields
        if isinstance(value, Mapping)
    ):
        raise SourceParseError("acquisition_custody_claim_invalid")


def _validate_epub_structure_checks(checks: Mapping[str, Any], spec: Any) -> None:
    identity = getattr(spec, "epub_identity", None)
    if identity is None:
        raise SourceParseError("acquisition_epub_identity_missing")
    expected_fields = {
        "all_member_CRCs_verified",
        "container_and_declared_OPF_verified",
        "internal_member_sha256",
        "manifest_and_spine_verified",
        "metadata_observation",
        "mimetype_first_and_stored",
        "navigation_toc_structure",
        "package_identity",
        "preregistered_catalogue_conflict_context_bound",
        "rights_context",
        "rights_link_structure",
        "subject_grade_evidence",
        "xhtml_manifest_item_count",
        "spine_item_count",
    }
    if set(checks) != expected_fields:
        raise SourceParseError("acquisition_inspection_structure_schema_invalid")
    true_fields = {
        "all_member_CRCs_verified",
        "container_and_declared_OPF_verified",
        "manifest_and_spine_verified",
        "mimetype_first_and_stored",
        "preregistered_catalogue_conflict_context_bound",
    }
    if any(checks.get(field) is not True for field in true_fields):
        raise SourceParseError("acquisition_inspection_pass_claim_invalid")
    _require_positive_int(
        checks.get("xhtml_manifest_item_count"),
        "acquisition_inspection_count_invalid",
    )
    _require_positive_int(
        checks.get("spine_item_count"),
        "acquisition_inspection_count_invalid",
    )
    internal_hashes = _require_exact_mapping(
        checks.get("internal_member_sha256"),
        {"container", "opf", "navigation", "rights"},
        "acquisition_epub_internal_hash_schema_invalid",
    )
    for digest in internal_hashes.values():
        _require_sha256(digest, "acquisition_epub_internal_hash_invalid")
    expected_hashes = {
        "opf": "sha256:" + identity.opf_sha256,
        "navigation": "sha256:" + identity.navigation_sha256,
        "rights": "sha256:" + identity.rights_member_sha256,
    }
    if any(
        internal_hashes.get(role) != digest for role, digest in expected_hashes.items()
    ):
        raise SourceParseError("acquisition_epub_internal_hash_mismatch")
    if (
        identity.container_sha256 is not None
        and internal_hashes.get("container") != "sha256:" + identity.container_sha256
    ):
        raise SourceParseError("acquisition_epub_container_hash_mismatch")
    metadata = _require_exact_mapping(
        checks.get("metadata_observation"),
        {
            "dc_creator_values",
            "dc_identifier_values",
            "dc_language_values",
            "dc_publisher_values",
            "dc_rights_values",
            "dc_subject_values",
            "dc_title_values",
            "dcterms_modified_values",
            "grade_metadata_values",
        },
        "acquisition_epub_metadata_observation_schema_invalid",
    )
    if any(
        not isinstance(values, list)
        or any(not isinstance(value, str) for value in values)
        for values in metadata.values()
    ):
        raise SourceParseError("acquisition_epub_metadata_observation_invalid")
    expected_metadata = {
        "dc_creator_values": list(identity.opf_creator_values),
        "dc_identifier_values": [identity.identifier],
        "dc_language_values": [identity.language],
        "dc_publisher_values": list(identity.opf_publisher_values),
        "dc_rights_values": list(identity.opf_rights_values),
        "dc_subject_values": list(identity.opf_subject_values),
        "dc_title_values": [identity.title],
        "dcterms_modified_values": [identity.modified],
    }
    if any(
        metadata.get(field) != expected for field, expected in expected_metadata.items()
    ) or (
        identity.opf_grade_values is not None
        and metadata["grade_metadata_values"] != list(identity.opf_grade_values)
    ):
        raise SourceParseError("acquisition_epub_metadata_observation_invalid")
    package = _require_exact_mapping(
        checks.get("package_identity"),
        {"unique_identifier_id", "unique_identifier_linked", "version"},
        "acquisition_epub_package_identity_schema_invalid",
    )
    if (
        not isinstance(package.get("version"), str)
        or re.fullmatch(r"3\.[0-9]+", package["version"]) is None
        or (
            identity.package_version is not None
            and package.get("version") != identity.package_version
        )
        or not isinstance(package.get("unique_identifier_id"), str)
        or re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9._:-]{0,127}",
            package["unique_identifier_id"],
        )
        is None
        or package.get("unique_identifier_linked") is not True
    ):
        raise SourceParseError("acquisition_epub_package_identity_invalid")
    navigation = _require_exact_mapping(
        checks.get("navigation_toc_structure"),
        {
            "manifest_media_type",
            "manifest_properties",
            "toc_link_count",
            "toc_nav_count",
        },
        "acquisition_epub_navigation_schema_invalid",
    )
    properties = navigation.get("manifest_properties")
    if (
        navigation.get("manifest_media_type") != "application/xhtml+xml"
        or not isinstance(properties, list)
        or len(properties) != len(set(properties))
        or properties.count("nav") != 1
        or any(
            not isinstance(token, str)
            or re.fullmatch(r"[A-Za-z][A-Za-z0-9._:-]*", token) is None
            for token in properties
        )
        or navigation.get("toc_nav_count") != 1
    ):
        raise SourceParseError("acquisition_epub_navigation_invalid")
    _require_positive_int(
        navigation.get("toc_link_count"),
        "acquisition_epub_navigation_invalid",
    )
    expected_rights_context = {
        "artifact_notice_license_id": identity.artifact_notice_license_id,
        "artifact_notice_url": identity.artifact_notice_url,
        "catalogue_license_id": identity.catalogue_license_id,
        "catalogue_or_terms_evidence_runtime_verified": False,
        "preregistered_rights_subject_template_mismatch": (
            identity.rights_subject_template_mismatch
        ),
        "resolved_license_id": identity.resolved_license_id,
    }
    rights_context = checks.get("rights_context")
    if rights_context != expected_rights_context or any(
        type(rights_context.get(field)) is not bool
        for field in (
            "catalogue_or_terms_evidence_runtime_verified",
            "preregistered_rights_subject_template_mismatch",
        )
        if isinstance(rights_context, Mapping)
    ):
        raise SourceParseError("acquisition_epub_rights_context_invalid")
    rights_link = _require_exact_mapping(
        checks.get("rights_link_structure"),
        {
            "artifact_notice_url",
            "manifest_media_type",
            "structured_license_link_count",
        },
        "acquisition_epub_rights_link_schema_invalid",
    )
    if (
        rights_link.get("artifact_notice_url") != identity.artifact_notice_url
        or rights_link.get("manifest_media_type") != "application/xhtml+xml"
    ):
        raise SourceParseError("acquisition_epub_rights_link_invalid")
    _require_positive_int(
        rights_link.get("structured_license_link_count"),
        "acquisition_epub_rights_link_invalid",
    )
    subject_grade = _require_exact_mapping(
        checks.get("subject_grade_evidence"),
        {"catalogue", "download_filename", "opf_observation"},
        "acquisition_epub_subject_grade_schema_invalid",
    )
    expected_catalogue = {
        "evidence_root_sha256": "sha256:" + identity.catalogue_evidence_root_sha256,
        "grade": identity.catalogue_grade,
        "subject": identity.catalogue_subject,
    }
    expected_filename = {
        "filename": spec.filename,
        "grade_token": identity.filename_grade_token,
        "subject_token": identity.filename_subject_token,
    }
    opf_observation = _require_exact_mapping(
        subject_grade.get("opf_observation"),
        {
            "dc_subject_values",
            "grade_metadata_values",
            "grade_assertion_present",
            "subject_assertion_present",
        },
        "acquisition_epub_subject_grade_opf_schema_invalid",
    )
    expected_opf = {
        "dc_subject_values": list(identity.opf_subject_values),
        "grade_metadata_values": metadata["grade_metadata_values"],
        "grade_assertion_present": bool(metadata["grade_metadata_values"]),
        "subject_assertion_present": bool(identity.opf_subject_values),
    }
    if (
        subject_grade.get("catalogue") != expected_catalogue
        or subject_grade.get("download_filename") != expected_filename
        or opf_observation != expected_opf
        or type(expected_catalogue["grade"]) is not int
        or any(
            type(opf_observation.get(field)) is not bool
            for field in ("grade_assertion_present", "subject_assertion_present")
        )
    ):
        raise SourceParseError("acquisition_epub_subject_grade_evidence_invalid")


def _validate_structure_checks(archive_type: str, value: Any, spec: Any) -> None:
    checks = value if isinstance(value, dict) else None
    fields_by_type = {
        "safe_tar_gzip": {
            "all_members_streamed",
            "bundled_license_present",
            "required_dictionary_and_index_members_present",
            "regular_member_count",
            "special_or_link_members_present",
        },
        "safe_crc_verified_nalt_core_zip": {
            "all_member_CRCs_verified",
            "turtle_member_present",
            "authoritative_counts",
            "authoritative_counts_verified",
        },
        "validated_OBO_document": {
            "OBO_term_stanzas",
            "definition_line_count",
            "id_line_count",
            "name_line_count",
            "release_and_license_headers_verified",
        },
        "validated_ontology_text_document": {
            "document_nonempty",
            "release_and_license_headers_verified",
        },
        "well_formed_RDF_XML_document": {
            "RDF_description_count",
            "date_and_public_domain_markers_verified",
            "well_formed_XML",
        },
        "exact_sparse_Git_commit_worktree": {
            "commit_and_tree_verified",
            "Git_transport_redirects_allowed",
            "fetch_command_attempt_count",
            "license_sha256_verified",
            "git_metadata_removed_before_seal",
            "selected_tree_regular_blob_count",
            "sparse_worktree_matches_selected_tree",
            "special_submodule_or_symlink_entries_present",
            "worktree_clean_before_seal",
        },
    }
    if archive_type == "safe_crc_verified_epub":
        if checks is None:
            raise SourceParseError("acquisition_inspection_structure_schema_invalid")
        _validate_epub_structure_checks(checks, spec)
        return
    expected_fields = fields_by_type.get(archive_type)
    if checks is None or expected_fields is None or set(checks) != expected_fields:
        raise SourceParseError("acquisition_inspection_structure_schema_invalid")
    if archive_type == "safe_crc_verified_nalt_core_zip":
        expected_counts = {
            "concepts": 14_196,
            "english_pref_labels": 14_196,
            "alt_labels": 19_075,
            "hidden_labels": 0,
        }
        expected_checks = {
            "all_member_CRCs_verified": True,
            "turtle_member_present": True,
            "authoritative_counts": expected_counts,
            "authoritative_counts_verified": True,
        }
        observed_counts = checks.get("authoritative_counts")
        if (
            checks != expected_checks
            or checks.get("all_member_CRCs_verified") is not True
            or checks.get("turtle_member_present") is not True
            or checks.get("authoritative_counts_verified") is not True
            or not isinstance(observed_counts, dict)
            or any(type(count) is not int for count in observed_counts.values())
        ):
            raise SourceParseError("acquisition_nalt_inspection_invalid")
        return
    false_fields = {
        "special_or_link_members_present",
        "Git_transport_redirects_allowed",
        "special_submodule_or_symlink_entries_present",
    }
    unconstrained_boolean_fields: set[str] = set()
    count_fields = {
        "regular_member_count",
        "OBO_term_stanzas",
        "definition_line_count",
        "id_line_count",
        "name_line_count",
        "RDF_description_count",
        "fetch_command_attempt_count",
        "selected_tree_regular_blob_count",
        "xhtml_manifest_item_count",
        "spine_item_count",
    }
    for field, observed in checks.items():
        if field in false_fields:
            if observed is not False:
                raise SourceParseError("acquisition_inspection_false_claim_invalid")
        elif field in unconstrained_boolean_fields:
            if type(observed) is not bool:
                raise SourceParseError("acquisition_inspection_boolean_invalid")
        elif field in count_fields:
            _require_nonnegative_int(
                observed,
                "acquisition_inspection_count_invalid",
            )
        elif observed is not True:
            raise SourceParseError("acquisition_inspection_pass_claim_invalid")


def _expected_inspection_type(spec: Any, *, is_git: bool) -> str:
    if is_git:
        return "exact_sparse_Git_commit_worktree"
    media_type = spec.media_type.split(";", 1)[0].strip().lower()
    if media_type == "application/x-gzip":
        return "safe_tar_gzip"
    if media_type == "application/epub+zip":
        return "safe_crc_verified_epub"
    if spec.source_id == "usda_nalt_core_2024":
        return "safe_crc_verified_nalt_core_zip"
    if media_type == "text/obo":
        return "validated_OBO_document"
    if media_type == "text/plain":
        return "validated_ontology_text_document"
    if media_type == "application/rdf+xml":
        return "well_formed_RDF_XML_document"
    raise SourceParseError("acquisition_inspection_type_not_derivable")


def _validate_direct_transfer_evidence(
    value: Any,
    spec: Any,
    download_attempts: int,
) -> None:
    evidence = _require_exact_mapping(
        value,
        {
            "schema_version",
            "mode",
            "fixed_chunk_bytes",
            "chunk_count",
            "per_chunk_attempts",
            "total_attempts",
            "every_response_206",
            "every_content_range_exact",
            "no_overlap",
            "no_gap",
            "held_destination_single_inode",
            "full_length_and_sha256_verified",
        },
        "acquisition_transfer_evidence_schema_invalid",
    )
    mode = getattr(spec, "transfer_mode", None)
    fixed_chunk_bytes = getattr(spec, "fixed_chunk_bytes", None)
    expected_bytes = getattr(spec, "expected_bytes", None)
    if type(expected_bytes) is not int or expected_bytes <= 0:
        raise SourceParseError("acquisition_transfer_spec_invalid")
    if mode == "fixed_range_chunks_v1":
        if type(fixed_chunk_bytes) is not int or fixed_chunk_bytes <= 0:
            raise SourceParseError("acquisition_transfer_spec_invalid")
        expected_chunk_count = (
            expected_bytes + fixed_chunk_bytes - 1
        ) // fixed_chunk_bytes
        expected_range_flags = (True, True)
    elif mode == "single_response_v1":
        if fixed_chunk_bytes is not None:
            raise SourceParseError("acquisition_transfer_spec_invalid")
        expected_chunk_count = 1
        expected_range_flags = (False, False)
    else:
        raise SourceParseError("acquisition_transfer_spec_invalid")
    per_chunk_attempts = evidence.get("per_chunk_attempts")
    chunk_count = evidence.get("chunk_count")
    total_attempts = evidence.get("total_attempts")
    every_response_206 = evidence.get("every_response_206")
    every_content_range_exact = evidence.get("every_content_range_exact")
    if (
        evidence.get("schema_version") != "cur0s_direct_transfer_evidence_v1"
        or evidence.get("mode") != mode
        or evidence.get("fixed_chunk_bytes") != fixed_chunk_bytes
        or type(chunk_count) is not int
        or chunk_count != expected_chunk_count
        or not isinstance(per_chunk_attempts, list)
        or len(per_chunk_attempts) != expected_chunk_count
        or any(
            type(attempt) is not int or not 1 <= attempt <= 4
            for attempt in per_chunk_attempts
        )
        or type(total_attempts) is not int
        or total_attempts != sum(per_chunk_attempts)
        or total_attempts != download_attempts
        or every_response_206 is not expected_range_flags[0]
        or every_content_range_exact is not expected_range_flags[1]
        or evidence.get("no_overlap") is not True
        or evidence.get("no_gap") is not True
        or evidence.get("held_destination_single_inode") is not True
        or evidence.get("full_length_and_sha256_verified") is not True
    ):
        raise SourceParseError("acquisition_transfer_evidence_invalid")


def _validate_inspection_summaries(
    value: Any,
    specs: Sequence[Any],
    artifact_by_id: Mapping[str, Mapping[str, Any]],
    git_source_ids: set[str],
) -> None:
    if not isinstance(value, list) or len(value) != len(specs):
        raise SourceParseError("acquisition_inspection_summary_count_invalid")
    for summary, spec in zip(value, specs, strict=True):
        is_git = spec.source_id in git_source_ids
        fields = (
            {
                "source_id",
                "acquisition_mode",
                "archive_or_document_type",
                "member_count",
                "uncompressed_or_document_bytes",
                "required_marker_count",
                "required_markers_verified",
                "structure_checks",
                "raw_payload_egressed",
            }
            if is_git
            else {
                "source_id",
                "acquisition_mode",
                "archive_or_document_type",
                "member_count",
                "uncompressed_or_document_bytes",
                "required_marker_count",
                "required_markers_verified",
                "payload_rights_evidence_root_sha256",
                "external_rights_evidence_runtime_verified",
                "transport_response_attempts",
                "transfer_evidence",
                "structure_checks",
                "raw_payload_egressed",
            }
        )
        summary = _require_exact_mapping(
            summary,
            fields,
            "acquisition_inspection_summary_schema_invalid",
        )
        artifact = artifact_by_id.get(spec.source_id)
        expected_type = _expected_inspection_type(spec, is_git=is_git)
        expected_marker_count = 1 if is_git else len(spec.required_markers)
        _require_nonnegative_int(
            summary.get("required_marker_count"),
            "acquisition_inspection_marker_count_invalid",
        )
        if (
            artifact is None
            or summary.get("source_id") != spec.source_id
            or summary.get("acquisition_mode") != spec.acquisition_mode
            or summary.get("archive_or_document_type") != expected_type
            or summary.get("required_marker_count") != expected_marker_count
            or summary.get("required_markers_verified") is not True
            or summary.get("raw_payload_egressed") is not False
        ):
            raise SourceParseError("acquisition_inspection_summary_binding_invalid")
        _require_positive_int(
            summary.get("member_count"),
            "acquisition_inspection_member_count_invalid",
        )
        observed_bytes = _require_positive_int(
            summary.get("uncompressed_or_document_bytes"),
            "acquisition_inspection_bytes_invalid",
        )
        if is_git and observed_bytes != artifact.get("bytes"):
            raise SourceParseError("acquisition_git_inspection_bytes_mismatch")
        if not is_git:
            _require_sha256(
                summary.get("payload_rights_evidence_root_sha256"),
                "acquisition_inspection_rights_hash_invalid",
            )
            if summary.get("external_rights_evidence_runtime_verified") is not False:
                raise SourceParseError("acquisition_external_rights_claim_invalid")
            attempts = _require_exact_mapping(
                summary.get("transport_response_attempts"),
                {"preflight", "download", "postflight"},
                "acquisition_transport_attempt_schema_invalid",
            )
            for count in attempts.values():
                _require_positive_int(
                    count,
                    "acquisition_transport_attempt_count_invalid",
                )
            _validate_direct_transfer_evidence(
                summary.get("transfer_evidence"),
                spec,
                attempts["download"],
            )
        _validate_structure_checks(
            expected_type,
            summary.get("structure_checks"),
            spec,
        )


def _validate_resource_and_execution_snapshots(
    resource_value: Any,
    execution_value: Any,
    run_id: str,
    thermal_contract: Mapping[str, Any],
) -> None:
    resource_fields = {
        "action_id",
        "phone_execution_ordinal",
        "max_wall_seconds",
        "terminalization_reserve_seconds",
        "maximum_observed_elapsed_seconds",
        "min_free_storage_bytes",
        "minimum_observed_free_storage_bytes",
        "thermal_safety_contract_root_sha256",
        "thermal_group_ceilings_millidegrees_c",
        "maximum_observed_thermal_group_millidegrees_c",
        "observed_thermal_sensor_types_by_group",
        "thermal_unavailable_sentinels_millidegrees_c",
        "thermal_sample_interval_seconds",
        "thermal_sample_count",
        "maximum_readable_thermal_sensor_count",
        "max_private_output_bytes",
        "private_output_bytes_before_receipt",
        "private_output_allocated_bytes_before_receipt",
        "maximum_observed_private_output_bytes",
        "maximum_observed_private_allocated_bytes",
        "maximum_ephemeral_control_bytes",
        "maximum_ephemeral_control_allocated_bytes",
        "ephemeral_control_files_open_at_receipt",
        "lease_expires_at_utc",
        "snapshot_scope",
    }
    snapshot = _require_exact_mapping(
        resource_value,
        resource_fields,
        "acquisition_resource_snapshot_schema_invalid",
    )
    _require_positive_int(
        snapshot.get("phone_execution_ordinal"),
        "acquisition_resource_snapshot_claim_invalid",
    )
    _require_positive_int(
        snapshot.get("terminalization_reserve_seconds"),
        "acquisition_resource_snapshot_claim_invalid",
    )
    _require_nonnegative_int(
        snapshot.get("ephemeral_control_files_open_at_receipt"),
        "acquisition_resource_snapshot_claim_invalid",
    )
    if (
        snapshot.get("action_id") != run_id
        or snapshot.get("phone_execution_ordinal") != 1
        or snapshot.get("terminalization_reserve_seconds") != 30
        or snapshot.get("thermal_unavailable_sentinels_millidegrees_c")
        != [-273_000, -40_960]
        or snapshot.get("ephemeral_control_files_open_at_receipt") != 0
        or snapshot.get("snapshot_scope")
        != "through_receipt_construction_before_publication"
    ):
        raise SourceParseError("acquisition_resource_snapshot_claim_invalid")
    for field in (
        "max_wall_seconds",
        "min_free_storage_bytes",
        "minimum_observed_free_storage_bytes",
        "thermal_sample_interval_seconds",
        "thermal_sample_count",
        "maximum_readable_thermal_sensor_count",
        "max_private_output_bytes",
    ):
        _require_positive_int(snapshot.get(field), "acquisition_resource_bound_invalid")
    for field in resource_fields - {
        "action_id",
        "phone_execution_ordinal",
        "terminalization_reserve_seconds",
        "thermal_unavailable_sentinels_millidegrees_c",
        "ephemeral_control_files_open_at_receipt",
        "lease_expires_at_utc",
        "snapshot_scope",
        "max_wall_seconds",
        "min_free_storage_bytes",
        "minimum_observed_free_storage_bytes",
        "thermal_safety_contract_root_sha256",
        "thermal_group_ceilings_millidegrees_c",
        "maximum_observed_thermal_group_millidegrees_c",
        "observed_thermal_sensor_types_by_group",
        "thermal_sample_interval_seconds",
        "thermal_sample_count",
        "maximum_readable_thermal_sensor_count",
        "max_private_output_bytes",
    }:
        _require_finite_number(
            snapshot.get(field),
            "acquisition_resource_measurement_invalid",
        )
    if (
        snapshot["maximum_observed_elapsed_seconds"] >= snapshot["max_wall_seconds"]
        or snapshot["minimum_observed_free_storage_bytes"]
        < snapshot["min_free_storage_bytes"]
        or snapshot["maximum_observed_private_output_bytes"]
        > snapshot["max_private_output_bytes"]
    ):
        raise SourceParseError("acquisition_resource_ceiling_crossed")
    thermal_groups = thermal_contract["sensor_types_by_group"]
    ceilings = _require_exact_mapping(
        snapshot.get("thermal_group_ceilings_millidegrees_c"),
        set(thermal_groups),
        "acquisition_thermal_ceiling_schema_invalid",
    )
    maxima = _require_exact_mapping(
        snapshot.get("maximum_observed_thermal_group_millidegrees_c"),
        set(thermal_groups),
        "acquisition_thermal_maximum_schema_invalid",
    )
    observed_types = _require_exact_mapping(
        snapshot.get("observed_thermal_sensor_types_by_group"),
        set(thermal_groups),
        "acquisition_thermal_type_schema_invalid",
    )
    if (
        snapshot.get("thermal_safety_contract_root_sha256")
        != thermal_contract["contract_root_sha256"]
        or ceilings != thermal_contract["group_ceilings_millidegrees_c"]
        or observed_types != thermal_groups
    ):
        raise SourceParseError("acquisition_thermal_contract_mismatch")
    for group in thermal_groups:
        _require_positive_int(maxima[group], "acquisition_thermal_maximum_invalid")
        if maxima[group] >= ceilings[group]:
            raise SourceParseError("acquisition_resource_ceiling_crossed")
    _parse_utc_second(
        snapshot.get("lease_expires_at_utc"),
        "acquisition_lease_expiry_invalid",
    )

    execution = _require_exact_mapping(
        execution_value,
        {
            "started_at_utc",
            "snapshot_at_utc",
            "elapsed_seconds_at_snapshot",
            "peak_rss_kib_at_snapshot",
            "python",
        },
        "acquisition_execution_snapshot_schema_invalid",
    )
    started = _parse_utc_second(
        execution.get("started_at_utc"),
        "acquisition_execution_started_at_invalid",
    )
    observed = _parse_utc_second(
        execution.get("snapshot_at_utc"),
        "acquisition_execution_snapshot_at_invalid",
    )
    if observed < started:
        raise SourceParseError("acquisition_execution_time_order_invalid")
    _require_finite_number(
        execution.get("elapsed_seconds_at_snapshot"),
        "acquisition_execution_elapsed_invalid",
    )
    _require_positive_int(
        execution.get("peak_rss_kib_at_snapshot"),
        "acquisition_execution_rss_invalid",
    )
    if (
        not isinstance(execution.get("python"), str)
        or re.fullmatch(
            r"3\.13\.[0-9]+",
            execution["python"],
        )
        is None
    ):
        raise SourceParseError("acquisition_execution_python_invalid")


def _validate_execution_claim(
    candidate_path: Path,
    candidate_metadata: os.stat_result,
    receipt_claim: Any,
    run_id: str,
    preregistration_root_sha256: str,
    contract_root_sha256: str,
) -> str:
    fields = {
        "state",
        "claim_sha256",
        "claim_bytes",
        "stable_control_anchor",
        "execution_claim_filename",
        "claim_egressed",
        "claim_is_crash_anchor",
        "claim_only_state_is_blocked_and_never_replayable",
        "exclusive_Termux_UID_operational_assumption",
        "malicious_same_UID_tamper_resistance_claimed",
        "replay_allowed",
        "terminal_resolution_required",
    }
    claim_receipt = _require_exact_mapping(
        receipt_claim,
        fields,
        "acquisition_execution_claim_receipt_schema_invalid",
    )
    claim_name = f".{run_id}.cur0s_execution_claim.json"
    expected_claim_receipt = {
        "state": "claimed_terminal_pending_once_O_EXCL",
        "claim_sha256": claim_receipt.get("claim_sha256"),
        "claim_bytes": claim_receipt.get("claim_bytes"),
        "stable_control_anchor": str(PHONE_PACKAGE_ROOT),
        "execution_claim_filename": claim_name,
        "claim_egressed": False,
        "claim_is_crash_anchor": True,
        "claim_only_state_is_blocked_and_never_replayable": True,
        "exclusive_Termux_UID_operational_assumption": True,
        "malicious_same_UID_tamper_resistance_claimed": False,
        "replay_allowed": False,
        "terminal_resolution_required": (
            "exact_receipt_bound_COMPLETE_or_stable_control_ABORT"
        ),
    }
    boolean_fields = {
        "claim_egressed",
        "claim_is_crash_anchor",
        "claim_only_state_is_blocked_and_never_replayable",
        "exclusive_Termux_UID_operational_assumption",
        "malicious_same_UID_tamper_resistance_claimed",
        "replay_allowed",
    }
    if claim_receipt != expected_claim_receipt or any(
        claim_receipt.get(field) is not expected_claim_receipt[field]
        for field in boolean_fields
    ):
        raise SourceParseError("acquisition_execution_claim_receipt_invalid")
    claim_sha256 = _require_sha256(
        claim_receipt.get("claim_sha256"),
        "acquisition_execution_claim_hash_invalid",
    )
    _require_positive_int(
        claim_receipt.get("claim_bytes"),
        "acquisition_execution_claim_bytes_invalid",
    )
    expected_candidate = PHONE_RUN_ROOT / run_id / "candidate_runs" / "candidate-001"
    if candidate_path != expected_candidate:
        raise SourceParseError("acquisition_candidate_canonical_path_invalid")
    try:
        anchor_fd = os.open(
            PHONE_PACKAGE_ROOT,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
    except OSError as exc:
        raise SourceParseError("acquisition_control_anchor_open_failed") from exc
    try:
        anchor = os.fstat(anchor_fd)
        if (
            not stat.S_ISDIR(anchor.st_mode)
            or stat.S_IMODE(anchor.st_mode) != 0o700
            or anchor.st_uid != candidate_metadata.st_uid
        ):
            raise SourceParseError("acquisition_control_anchor_identity_invalid")
        relative_candidate = expected_candidate.relative_to(
            PHONE_PACKAGE_ROOT
        ).as_posix()
        with _open_relative_directory_fd(anchor_fd, relative_candidate) as reopened:
            if _stat_identity(os.fstat(reopened)) != _stat_identity(candidate_metadata):
                raise SourceParseError("acquisition_candidate_anchor_binding_invalid")
        abort_name = f".{run_id}.cur0s_ABORT.json"
        try:
            abort_metadata = os.stat(
                abort_name,
                dir_fd=anchor_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            abort_metadata = None
        except OSError as exc:
            raise SourceParseError("acquisition_abort_resolution_check_failed") from exc
        if abort_metadata is not None:
            raise SourceParseError("acquisition_conflicting_terminal_resolutions")
        claim = _read_canonical_contract_json_at(anchor_fd, claim_name, 1024 * 1024)
    finally:
        os.close(anchor_fd)
    if claim.identity[4:6] != (
        candidate_metadata.st_uid,
        candidate_metadata.st_gid,
    ):
        raise SourceParseError("acquisition_execution_claim_owner_invalid")
    observed_claim_sha256 = "sha256:" + hashlib.sha256(claim.payload).hexdigest()
    if (
        observed_claim_sha256 != claim_sha256
        or len(claim.payload) != claim_receipt["claim_bytes"]
    ):
        raise SourceParseError("acquisition_execution_claim_artifact_mismatch")
    claim_value = _require_exact_mapping(
        claim.value,
        {
            "schema_version",
            "state",
            "run_id",
            "output_directory_name",
            "stable_control_anchor",
            "execution_claim_filename",
            "phone_execution_ordinal",
            "preregistration_root_sha256",
            "contract_root_sha256",
            "candidate_directory_prepared_identity",
            "replay_allowed",
            "claim_only_disposition",
            "valid_terminal_resolutions",
        },
        "acquisition_execution_claim_schema_invalid",
    )
    prepared = _require_exact_mapping(
        claim_value.get("candidate_directory_prepared_identity"),
        {"device", "inode", "file_type", "link_count", "bytes", "uid", "gid", "mode"},
        "acquisition_execution_claim_candidate_identity_schema_invalid",
    )
    if (
        claim_value.get("schema_version")
        != "cur0s_commercial_sources_execution_claim_v1"
        or claim_value.get("state") != "claimed_terminal_pending"
        or claim_value.get("run_id") != run_id
        or claim_value.get("output_directory_name") != "candidate-001"
        or claim_value.get("stable_control_anchor") != str(PHONE_PACKAGE_ROOT)
        or claim_value.get("execution_claim_filename") != claim_name
        or type(claim_value.get("phone_execution_ordinal")) is not int
        or claim_value.get("phone_execution_ordinal") != 1
        or claim_value.get("preregistration_root_sha256") != preregistration_root_sha256
        or claim_value.get("contract_root_sha256") != contract_root_sha256
        or claim_value.get("replay_allowed") is not False
        or claim_value.get("claim_only_disposition")
        != "blocked_incomplete_nonreplayable"
        or claim_value.get("valid_terminal_resolutions")
        != [
            "canonical_receipt_bound_COMPLETE_in_candidate",
            "stable_control_anchor_ABORT_without_source_root_pass",
        ]
        or prepared.get("device") != candidate_metadata.st_dev
        or prepared.get("inode") != candidate_metadata.st_ino
        or prepared.get("file_type") != "directory"
        or prepared.get("uid") != candidate_metadata.st_uid
        or prepared.get("gid") != candidate_metadata.st_gid
        or prepared.get("mode") != "0700"
    ):
        raise SourceParseError("acquisition_execution_claim_binding_invalid")
    _require_positive_int(
        prepared.get("link_count"),
        "acquisition_execution_claim_link_count_invalid",
    )
    _require_positive_int(
        prepared.get("bytes"),
        "acquisition_execution_claim_directory_bytes_invalid",
    )
    return claim_sha256


def _derive_canonical_action_path(candidate_path: Path) -> tuple[str, Path]:
    if (
        candidate_path.name != "candidate-001"
        or candidate_path.parent.name != "candidate_runs"
    ):
        raise SourceParseError("acquisition_candidate_canonical_path_invalid")
    action_root = candidate_path.parent.parent
    run_id = action_root.name
    if RUN_ID_RE.fullmatch(run_id) is None or action_root.parent != PHONE_RUN_ROOT:
        raise SourceParseError("acquisition_candidate_canonical_path_invalid")
    expected = PHONE_RUN_ROOT / run_id / "candidate_runs" / "candidate-001"
    if candidate_path != expected:
        raise SourceParseError("acquisition_candidate_canonical_path_invalid")
    return run_id, action_root


def _require_private_directory(
    metadata: os.stat_result,
    *,
    owner_uid: int,
    owner_gid: int,
    exact_mode: int,
    error: str,
) -> None:
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != exact_mode
        or metadata.st_uid != owner_uid
        or metadata.st_gid != owner_gid
        or metadata.st_nlink < 1
    ):
        raise SourceParseError(error)


@contextmanager
def _open_canonical_action_handles(
    candidate_path: Path,
) -> Iterator[tuple[int, int, int, str, Path, int]]:
    run_id, action_root = _derive_canonical_action_path(candidate_path)
    descriptors: list[int] = []
    try:
        try:
            anchor_fd = os.open(
                PHONE_PACKAGE_ROOT,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
        except OSError as exc:
            raise SourceParseError("acquisition_control_anchor_open_failed") from exc
        descriptors.append(anchor_fd)
        anchor = os.fstat(anchor_fd)
        if not stat.S_ISDIR(anchor.st_mode) or stat.S_IMODE(anchor.st_mode) != 0o700:
            raise SourceParseError("acquisition_control_anchor_identity_invalid")
        owner_uid = anchor.st_uid
        owner_gid = anchor.st_gid
        current_fd = anchor_fd
        for name, mode in (
            ("files", 0o771),
            ("home", 0o700),
            ("polymath_gemma4_e4b_frontier", 0o700),
            (run_id, 0o700),
        ):
            try:
                child_fd = os.open(
                    name,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=current_fd,
                )
            except OSError as exc:
                raise SourceParseError("acquisition_action_chain_open_failed") from exc
            descriptors.append(child_fd)
            _require_private_directory(
                os.fstat(child_fd),
                owner_uid=owner_uid,
                owner_gid=owner_gid,
                exact_mode=mode,
                error="acquisition_action_chain_identity_invalid",
            )
            current_fd = child_fd
        action_fd = current_fd
        try:
            candidate_runs_fd = os.open(
                "candidate_runs",
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=action_fd,
            )
        except OSError as exc:
            raise SourceParseError("acquisition_candidate_parent_open_failed") from exc
        descriptors.append(candidate_runs_fd)
        _require_private_directory(
            os.fstat(candidate_runs_fd),
            owner_uid=owner_uid,
            owner_gid=owner_gid,
            exact_mode=0o700,
            error="acquisition_candidate_parent_identity_invalid",
        )
        if set(os.listdir(candidate_runs_fd)) != {"candidate-001"}:
            raise SourceParseError("acquisition_multiple_candidate_resolution")
        try:
            candidate_fd = os.open(
                "candidate-001",
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=candidate_runs_fd,
            )
        except OSError as exc:
            raise SourceParseError("acquisition_candidate_open_failed") from exc
        descriptors.append(candidate_fd)
        _require_private_directory(
            os.fstat(candidate_fd),
            owner_uid=owner_uid,
            owner_gid=owner_gid,
            exact_mode=0o700,
            error="acquisition_candidate_identity_invalid",
        )
        yield action_fd, candidate_runs_fd, candidate_fd, run_id, action_root, owner_uid
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


@contextmanager
def _open_private_directory_at(
    root_fd: int,
    relative: str,
    owner_uid: int,
) -> Iterator[int]:
    parts = PurePosixPath(_safe_archive_name(relative)).parts
    try:
        current_fd = os.dup(root_fd)
        expected_gid = os.fstat(root_fd).st_gid
    except OSError as exc:
        raise SourceParseError("acquisition_private_root_duplicate_failed") from exc
    try:
        for part in parts:
            try:
                child_fd = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=current_fd,
                )
            except OSError as exc:
                raise SourceParseError(
                    "acquisition_private_directory_open_failed"
                ) from exc
            metadata = os.fstat(child_fd)
            mode = stat.S_IMODE(metadata.st_mode)
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or mode & 0o500 != 0o500
                or mode & 0o022
                or metadata.st_uid != owner_uid
                or metadata.st_gid != expected_gid
                or metadata.st_nlink < 1
            ):
                os.close(child_fd)
                raise SourceParseError("acquisition_private_directory_identity_invalid")
            os.close(current_fd)
            current_fd = child_fd
        yield current_fd
    finally:
        os.close(current_fd)


def _read_private_relative_artifact(
    root_fd: int,
    relative: str,
    *,
    exact_mode: int | frozenset[int],
    owner_uid: int,
    max_bytes: int,
    error_prefix: str,
) -> _RegularArtifact:
    safe = PurePosixPath(_safe_archive_name(relative))
    parent = safe.parent.as_posix()
    if parent == ".":
        return _read_regular_artifact_at(
            root_fd,
            safe.name,
            exact_mode=exact_mode,
            owner_uid=owner_uid,
            max_bytes=max_bytes,
            error_prefix=error_prefix,
        )
    with _open_private_directory_at(root_fd, parent, owner_uid) as parent_fd:
        return _read_regular_artifact_at(
            parent_fd,
            safe.name,
            exact_mode=exact_mode,
            owner_uid=owner_uid,
            max_bytes=max_bytes,
            error_prefix=error_prefix,
        )


def _git_blob_oid(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _read_checkout_head(checkout_fd: int, owner_uid: int) -> str:
    with _open_private_directory_at(checkout_fd, ".git", owner_uid) as git_fd:
        head = _read_regular_artifact_at(
            git_fd,
            "HEAD",
            exact_mode=frozenset({0o600, 0o644}),
            owner_uid=owner_uid,
            max_bytes=4096,
            error_prefix="acquisition_git_HEAD",
        )
        try:
            head_text = head.payload.decode("ascii")
        except UnicodeError as exc:
            raise SourceParseError("acquisition_git_HEAD_invalid") from exc
        if not head_text.endswith("\n") or head_text.count("\n") != 1:
            raise SourceParseError("acquisition_git_HEAD_invalid")
        head_value = head_text[:-1]
        if COMMIT_RE.fullmatch(head_value):
            return head_value
        prefix = "ref: "
        if not head_value.startswith(prefix):
            raise SourceParseError("acquisition_git_HEAD_invalid")
        reference = head_value.removeprefix(prefix)
        if not reference.startswith("refs/"):
            raise SourceParseError("acquisition_git_HEAD_reference_invalid")
        try:
            reference_artifact = _read_private_relative_artifact(
                git_fd,
                reference,
                exact_mode=frozenset({0o600, 0o644}),
                owner_uid=owner_uid,
                max_bytes=4096,
                error_prefix="acquisition_git_HEAD_reference",
            )
        except SourceParseError as exc:
            if str(exc) not in {
                "acquisition_git_HEAD_reference_open_failed",
                "acquisition_private_directory_open_failed",
            }:
                raise
            packed = _read_regular_artifact_at(
                git_fd,
                "packed-refs",
                exact_mode=frozenset({0o600, 0o644}),
                owner_uid=owner_uid,
                max_bytes=4 * 1024 * 1024,
                error_prefix="acquisition_git_packed_refs",
            )
            try:
                lines = packed.payload.decode("ascii").splitlines()
            except UnicodeError as decode_error:
                raise SourceParseError(
                    "acquisition_git_packed_refs_invalid"
                ) from decode_error
            matches = [
                line.split(" ", 1)[0]
                for line in lines
                if not line.startswith(("#", "^"))
                and line.endswith(" " + reference)
                and len(line.split(" ", 1)) == 2
            ]
            if len(matches) != 1 or COMMIT_RE.fullmatch(matches[0]) is None:
                raise SourceParseError("acquisition_git_HEAD_reference_invalid")
            return matches[0]
        try:
            reference_text = reference_artifact.payload.decode("ascii")
        except UnicodeError as exc:
            raise SourceParseError("acquisition_git_HEAD_reference_invalid") from exc
        if (
            not reference_text.endswith("\n")
            or reference_text.count("\n") != 1
            or COMMIT_RE.fullmatch(reference_text[:-1]) is None
        ):
            raise SourceParseError("acquisition_git_HEAD_reference_invalid")
        return reference_text[:-1]


def _validate_preregistration_contract(
    preregistration: Mapping[str, Any],
    *,
    run_id: str,
    action_root: Path,
    commercial: Any,
) -> None:
    expected_fields = {
        "schema_version",
        "candidate_id",
        "parent_experiment_id",
        "run_id",
        "state",
        "candidate_output_observed",
        "candidate_output_files_present",
        "phone_execution_started",
        "promotion_allowed",
        "source_commit",
        "source_file_sha256",
        "source_file_bindings",
        "commercial_source_contract",
        "commercial_source_contract_sha256",
        "phone_toolchain_identity",
        "phone_toolchain_identity_sha256",
        "native_preflight",
        "native_preflight_sha256",
        "parent_capsule_sha256",
        "parent_frontier_root_sha256",
        "maximal_selector_sha256",
        "ACCESS_receipt_sha256",
        "campaign_lease",
        "resource_slice",
        "target_device",
        "network_policy",
        "source_checkout_policy",
        "governing_inputs",
        "claim_scope",
        "claim_ceiling",
        "output_directory_name",
        "expected_disposition",
        "transaction_policy",
        "custody",
        "nonclaims",
        "preregistration_root_sha256",
    }
    prereg = _require_exact_mapping(
        preregistration,
        expected_fields,
        "acquisition_preregistration_schema_invalid",
    )
    source_commit = prereg.get("source_commit")
    body = dict(prereg)
    claimed_root = body.pop("preregistration_root_sha256", None)
    if (
        prereg.get("schema_version") != "cur0s_commercial_sources_preregistration_v1"
        or prereg.get("candidate_id")
        != "cur0s_commercial_authority_sources_phone_native_v1"
        or prereg.get("parent_experiment_id") != "EXP-CUR0S-SOVEREIGN-COMPOSITE-V1"
        or prereg.get("run_id") != run_id
        or prereg.get("state") != "frozen_unobserved"
        or prereg.get("candidate_output_observed") is not False
        or prereg.get("candidate_output_files_present") is not False
        or prereg.get("phone_execution_started") is not False
        or prereg.get("promotion_allowed") is not False
        or not isinstance(source_commit, str)
        or COMMIT_RE.fullmatch(source_commit) is None
        or prereg.get("parent_capsule_sha256") != EXPECTED_PARENT_CAPSULE_SHA256
        or prereg.get("parent_frontier_root_sha256")
        != EXPECTED_PARENT_FRONTIER_ROOT_SHA256
        or prereg.get("maximal_selector_sha256") != EXPECTED_PARENT_FRONTIER_ROOT_SHA256
        or prereg.get("ACCESS_receipt_sha256") != EXPECTED_ACCESS_RECEIPT_SHA256
        or prereg.get("output_directory_name") != "candidate-001"
        or claimed_root != commercial.canonical_sha256(body)
    ):
        raise SourceParseError("acquisition_preregistration_binding_invalid")
    contract = prereg.get("commercial_source_contract")
    toolchain = prereg.get("phone_toolchain_identity")
    native = prereg.get("native_preflight")
    if (
        contract != commercial.source_contract()
        or prereg.get("commercial_source_contract_sha256")
        != commercial.canonical_sha256(contract)
        or toolchain != commercial.phone_toolchain_contract()
        or prereg.get("phone_toolchain_identity_sha256")
        != commercial.canonical_sha256(toolchain)
        or not isinstance(native, Mapping)
        or prereg.get("native_preflight_sha256") != commercial.canonical_sha256(native)
    ):
        raise SourceParseError("acquisition_preregistration_contract_invalid")
    eligibility = contract.get("preregistration_eligibility")
    if not isinstance(eligibility, Mapping):
        raise SourceParseError("acquisition_preregistration_eligibility_invalid")
    if (
        eligibility.get("eligible") is not True
        or eligibility.get("selection_critical_identity_blockers") != []
    ):
        blockers = eligibility.get("selection_critical_identity_blockers")
        if isinstance(blockers, list) and any(
            isinstance(blocker, Mapping)
            and blocker.get("reason") == "payload_grade_metadata_identity_unresolved"
            for blocker in blockers
        ):
            raise SourceParseError("payload_grade_metadata_identity_unresolved")
        raise SourceParseError("acquisition_preregistration_ineligible")
    expected_layout = commercial.native_preflight_execution_layout(
        run_id,
        source_commit,
    )
    if (
        native.get("execution_layout") != expected_layout
        or expected_layout.get("action_root") != str(action_root)
        or expected_layout.get("candidate_output")
        != str(action_root / "candidate_runs" / "candidate-001")
    ):
        raise SourceParseError("acquisition_preregistration_layout_invalid")


def _build_action_authority_closure(
    action_fd: int,
    candidate_runs_fd: int,
    *,
    run_id: str,
    action_root: Path,
    owner_uid: int,
    expected_authority: ProductionAuthorityExpectation,
    commercial: Any,
) -> _ActionAuthorityClosure:
    preregistration = _read_canonical_json_artifact_at(
        action_fd,
        "preregistration.json",
        exact_mode=0o600,
        owner_uid=owner_uid,
        max_bytes=64 * 1024 * 1024,
        trailing_newline=True,
        error_prefix="acquisition_preregistration",
    )
    preregistration_sha256 = (
        "sha256:" + hashlib.sha256(preregistration.payload).hexdigest()
    )
    if preregistration_sha256 != expected_authority.preregistration_sha256:
        raise SourceParseError("acquisition_preregistration_out_of_band_mismatch")
    _validate_preregistration_contract(
        preregistration.value,
        run_id=run_id,
        action_root=action_root,
        commercial=commercial,
    )
    native = preregistration.value["native_preflight"]
    native_manifest = _read_regular_artifact_at(
        action_fd,
        "native_preflight.manifest",
        exact_mode=0o600,
        owner_uid=owner_uid,
        max_bytes=4 * 1024 * 1024,
        error_prefix="acquisition_native_manifest",
    )
    try:
        expected_manifest = commercial.build_native_preflight_manifest_bytes(
            preregistration.value
        )
    except commercial.CommercialSourceError as exc:
        raise SourceParseError("acquisition_native_manifest_contract_invalid") from exc
    if native_manifest.payload != expected_manifest:
        raise SourceParseError("acquisition_native_manifest_artifact_mismatch")
    launch_envelope = _read_canonical_json_artifact_at(
        action_fd,
        "native_launch_envelope.json",
        exact_mode=0o600,
        owner_uid=owner_uid,
        max_bytes=4 * 1024 * 1024,
        trailing_newline=True,
        error_prefix="acquisition_native_launch_envelope",
    )
    try:
        expected_envelope = commercial.build_native_launch_envelope(
            preregistration.value,
            native_manifest.payload,
        )
    except commercial.CommercialSourceError as exc:
        raise SourceParseError("acquisition_native_launch_contract_invalid") from exc
    if launch_envelope.value != expected_envelope:
        raise SourceParseError("acquisition_native_launch_envelope_mismatch")
    build_receipt = _read_canonical_json_artifact_at(
        action_fd,
        "native_preflight_build_receipt.json",
        exact_mode=0o600,
        owner_uid=owner_uid,
        max_bytes=4 * 1024 * 1024,
        trailing_newline=False,
        error_prefix="acquisition_native_build_receipt",
    )
    if build_receipt.value != native.get("build_receipt"):
        raise SourceParseError("acquisition_native_build_receipt_artifact_mismatch")
    source_commit = preregistration.value["source_commit"]
    native_source_bindings = native.get("native_source_file_bindings")
    try:
        validated_build_receipt = commercial.validate_native_preflight_build_receipt(
            build_receipt.value,
            source_commit=source_commit,
            source_file_bindings=native_source_bindings,
        )
        expected_native = commercial.build_native_preflight_execution_contract(
            run_id=run_id,
            source_commit=source_commit,
            source_file_bindings=preregistration.value["source_file_bindings"],
            native_source_file_bindings=native_source_bindings,
            native_build_receipt=validated_build_receipt,
        )
    except commercial.CommercialSourceError as exc:
        raise SourceParseError("acquisition_native_build_receipt_invalid") from exc
    if expected_native != native:
        raise SourceParseError("acquisition_native_preflight_reconstruction_mismatch")
    binary = _read_regular_artifact_at(
        action_fd,
        "cur0s_native_preflight",
        exact_mode=0o700,
        owner_uid=owner_uid,
        max_bytes=16 * 1024 * 1024,
        error_prefix="acquisition_native_binary",
    )
    binary_identity = build_receipt.value.get("binary_identity")
    if (
        not isinstance(binary_identity, Mapping)
        or binary.sha256 != binary_identity.get("sha256")
        or len(binary.payload) != binary_identity.get("bytes")
        or binary_identity.get("mode") != "0700"
        or binary_identity.get("uid") != owner_uid
        or binary_identity.get("gid") != binary.identity[5]
        or binary_identity.get("nlink") != 1
    ):
        raise SourceParseError("acquisition_native_binary_artifact_mismatch")
    checkout_relative = f"source/Polymath-AI-{source_commit}"
    with _open_private_directory_at(
        action_fd, checkout_relative, owner_uid
    ) as checkout_fd:
        checkout_identity = _stat_identity(os.fstat(checkout_fd))
        if _read_checkout_head(checkout_fd, owner_uid) != source_commit:
            raise SourceParseError("acquisition_checkout_HEAD_mismatch")
        binding_sets = (
            preregistration.value.get("source_file_bindings"),
            native_source_bindings,
        )
        if any(not isinstance(bindings, Mapping) for bindings in binding_sets):
            raise SourceParseError("acquisition_checkout_bindings_invalid")
        all_bindings: dict[str, Mapping[str, Any]] = {}
        for bindings in binding_sets:
            for relative, binding in bindings.items():
                if relative in all_bindings:
                    if all_bindings[relative] != binding:
                        raise SourceParseError(
                            "acquisition_checkout_duplicate_binding_mismatch"
                        )
                    continue
                if not isinstance(relative, str) or not isinstance(binding, Mapping):
                    raise SourceParseError("acquisition_checkout_bindings_invalid")
                all_bindings[relative] = binding
        artifacts: list[tuple[str, _RegularArtifact]] = []
        for relative, expected in sorted(all_bindings.items()):
            admitted_modes = (
                0o600 if relative in BOUND_SOURCE_FILES else frozenset({0o600, 0o644})
            )
            artifact = _read_private_relative_artifact(
                checkout_fd,
                relative,
                exact_mode=admitted_modes,
                owner_uid=owner_uid,
                max_bytes=4 * 1024 * 1024,
                error_prefix="acquisition_checkout_source_file",
            )
            if (
                set(expected) != {"bytes", "sha256", "git_blob_oid"}
                or len(artifact.payload) != expected.get("bytes")
                or artifact.sha256 != expected.get("sha256")
                or _git_blob_oid(artifact.payload) != expected.get("git_blob_oid")
            ):
                raise SourceParseError("acquisition_checkout_source_binding_mismatch")
            artifacts.append((relative, artifact))
    if set(os.listdir(candidate_runs_fd)) != {"candidate-001"}:
        raise SourceParseError("acquisition_multiple_candidate_resolution")
    return _ActionAuthorityClosure(
        action_root_identity=_stat_identity(os.fstat(action_fd)),
        candidate_runs_identity=_stat_identity(os.fstat(candidate_runs_fd)),
        checkout_identity=checkout_identity,
        preregistration=preregistration,
        native_manifest=native_manifest,
        native_launch_envelope=launch_envelope,
        native_build_receipt=build_receipt,
        native_binary=binary,
        source_file_artifacts=tuple(artifacts),
        source_commit=source_commit,
    )


def _production_verification_record(
    *,
    receipt: _CanonicalJsonArtifact,
    completion: _CanonicalJsonArtifact,
    receipt_root_sha256: str,
    source_root_sha256: str,
    receipt_value: Mapping[str, Any],
    source_id: str,
    artifact: Mapping[str, Any],
    execution_claim_sha256: str,
    authority_closure: _ActionAuthorityClosure,
) -> ProductionVerificationRecord:
    body = {
        "schema_version": PRODUCTION_VERIFICATION_SCHEMA,
        "production_transaction_verified": True,
        "run_id": receipt_value["run_id"],
        "candidate_id": receipt_value["candidate_id"],
        "source_id": source_id,
        "receipt_sha256": "sha256:" + hashlib.sha256(receipt.payload).hexdigest(),
        "receipt_root_sha256": receipt_root_sha256,
        "completion_sha256": "sha256:" + hashlib.sha256(completion.payload).hexdigest(),
        "source_root_sha256": source_root_sha256,
        "source_artifact_sha256": artifact["sha256"],
        "commercial_source_contract_root_sha256": receipt_value[
            "commercial_source_contract_root_sha256"
        ],
        "execution_claim_sha256": execution_claim_sha256,
        "preregistration_sha256": "sha256:"
        + hashlib.sha256(authority_closure.preregistration.payload).hexdigest(),
        "native_manifest_sha256": authority_closure.native_manifest.sha256,
        "native_launch_envelope_sha256": "sha256:"
        + hashlib.sha256(authority_closure.native_launch_envelope.payload).hexdigest(),
        "native_build_receipt_sha256": "sha256:"
        + hashlib.sha256(authority_closure.native_build_receipt.payload).hexdigest(),
        "native_binary_sha256": authority_closure.native_binary.sha256,
        "source_commit": authority_closure.source_commit,
        "verification_scope": (
            "out_of_band_preregistration_and_receipt_exact_passed_acquisition_"
            "native_checkout_source_root_COMPLETE_and_stable_one_shot_claim_"
            "revalidated_before_batch_release"
        ),
    }
    return ProductionVerificationRecord(
        **body,
        verification_root_sha256=canonical_sha256(body),
    )


def _verified_source_unit_envelope(
    unit: SourceUnit,
    verification: ProductionVerificationRecord,
) -> VerifiedSourceUnitEnvelope:
    body = {
        "schema_version": VERIFIED_SOURCE_UNIT_ENVELOPE_SCHEMA,
        "unit_canonical_sha256": unit.canonical_sha256,
        "production_verification_root_sha256": verification.verification_root_sha256,
    }
    return VerifiedSourceUnitEnvelope(
        schema_version=VERIFIED_SOURCE_UNIT_ENVELOPE_SCHEMA,
        unit=unit,
        production_verification=verification,
        envelope_sha256=canonical_sha256(body),
    )


def _validate_terminal_binding(
    action_fd: int,
    candidate_runs_fd: int,
    candidate_fd: int,
    candidate_path: Path,
    source_id: str,
    run_id_from_path: str,
    action_root: Path,
    owner_uid: int,
    expected_authority: ProductionAuthorityExpectation,
) -> _VerifiedSourceBinding:
    from polymath_ai.corpus import cur0s_commercial_sources as commercial

    authority_closure = _build_action_authority_closure(
        action_fd,
        candidate_runs_fd,
        run_id=run_id_from_path,
        action_root=action_root,
        owner_uid=owner_uid,
        expected_authority=expected_authority,
        commercial=commercial,
    )
    try:
        candidate_metadata = os.fstat(candidate_fd)
        entries = set(os.listdir(candidate_fd))
    except OSError as exc:
        raise SourceParseError("acquisition_candidate_read_failed") from exc
    if (
        not stat.S_ISDIR(candidate_metadata.st_mode)
        or stat.S_IMODE(candidate_metadata.st_mode) != 0o700
        or entries != {"sources", "receipt.json", "COMPLETE.json"}
    ):
        raise SourceParseError("acquisition_candidate_shape_invalid")
    receipt = _read_canonical_contract_json_at(candidate_fd, "receipt.json")
    completion = _read_canonical_contract_json_at(candidate_fd, "COMPLETE.json")
    if any(
        artifact.identity[4:6] != (candidate_metadata.st_uid, candidate_metadata.st_gid)
        for artifact in (receipt, completion)
    ):
        raise SourceParseError("acquisition_terminal_artifact_owner_invalid")
    observed_receipt_sha256 = "sha256:" + hashlib.sha256(receipt.payload).hexdigest()
    if observed_receipt_sha256 != expected_authority.acquisition_receipt_sha256:
        raise SourceParseError("acquisition_receipt_out_of_band_mismatch")
    receipt_value = receipt.value
    receipt_body = dict(receipt_value)
    receipt_root = receipt_body.pop("receipt_root_sha256", None)
    contract = commercial.source_contract()
    contract_root = contract["contract_root_sha256"]
    expected_receipt_fields = {
        "schema_version",
        "candidate_id",
        "run_id",
        "state",
        "candidate_output_observed",
        "source_root_state",
        "all_source_identity_and_rights_gates_passed",
        "commercial_source_contract_sha256",
        "commercial_source_contract_root_sha256",
        "source_execution_identity",
        "runtime_identity",
        "authority_bindings",
        "source_root",
        "source_inspection_summaries",
        "first_next_blocker",
        "mandatory_next_disposition",
        "claim_ceiling",
        "semantic_rows_compiled",
        "near_semantic_arm_C_executed",
        "connected_split_assigned",
        "cur0s_static_pass_claimed",
        "cur0s_pass_claimed",
        "composite_cur0_pass_claimed",
        "target_data_learning_claimed",
        "authority_claimed",
        "private_HF_mirror_completed",
        "c4_rx_content_present",
        "custody",
        "execution_claim",
        "preterminal_resource_envelope_snapshot",
        "preterminal_execution_snapshot",
        "pending_transaction_links",
        "nonclaims",
        "receipt_root_sha256",
    }
    false_claim_fields = {
        "semantic_rows_compiled",
        "near_semantic_arm_C_executed",
        "connected_split_assigned",
        "cur0s_static_pass_claimed",
        "cur0s_pass_claimed",
        "composite_cur0_pass_claimed",
        "target_data_learning_claimed",
        "authority_claimed",
        "private_HF_mirror_completed",
        "c4_rx_content_present",
    }
    expected_pending_links = [
        "post_run_evidence_commit",
        "origin_push_readback",
        "capsule_CAS_transition",
        "private_revision_pinned_HF_C4_COM_mirror",
    ]
    expected_nonclaims = [
        "not_semantic_material_compilation",
        "not_near_semantic_Arm_C",
        "not_connected_split_or_exposure_ledger",
        "not_C3_dictionary_or_C4_syllabus_admission",
        "not_CUR_0S_or_CUR_0P_or_composite_CUR_0",
        "not_target_data_learning_or_authority",
        "not_Section_0_5_success",
    ]
    run_id = receipt_value.get("run_id")
    if (
        set(receipt_value) != expected_receipt_fields
        or receipt_value.get("schema_version") != "cur0s_commercial_sources_receipt_v1"
        or receipt_value.get("candidate_id")
        != "cur0s_commercial_authority_sources_phone_native_v1"
        or not isinstance(run_id, str)
        or RUN_ID_RE.fullmatch(run_id) is None
        or run_id != run_id_from_path
        or receipt_value.get("state") != "passed_scope"
        or receipt_value.get("candidate_output_observed") is not True
        or receipt_value.get("source_root_state") != "passed_scope"
        or receipt_value.get("all_source_identity_and_rights_gates_passed") is not True
        or any(receipt_value.get(field) is not False for field in false_claim_fields)
        or receipt_root != commercial.canonical_sha256(receipt_body)
        or receipt_value.get("commercial_source_contract_sha256")
        != commercial.canonical_sha256(contract)
        or receipt_value.get("commercial_source_contract_root_sha256") != contract_root
        or receipt_value.get("first_next_blocker") != "private_C4_COM_mirror"
        or receipt_value.get("mandatory_next_disposition")
        != (
            "retain_phone_private_source_root_mirror_to_private_revision_pinned_"
            "C4_COM_then_compile_semantic_materials_before_near_semantic_Arm_C"
        )
        or receipt_value.get("claim_ceiling")
        != "commercial_source_identity_rights_and_phone_custody_only"
        or receipt_value.get("pending_transaction_links") != expected_pending_links
        or receipt_value.get("nonclaims") != expected_nonclaims
    ):
        raise SourceParseError("acquisition_receipt_binding_invalid")
    complete_value = completion.value
    expected_complete_fields = {
        "schema_version",
        "run_id",
        "state",
        "receipt_sha256",
        "receipt_root_sha256",
        "receipt_bytes",
        "completion_marker_prepared_at_utc",
        "completion_protocol",
        "raw_sources_preserved_on_phone",
        "output_directory_mode",
    }
    receipt_sha256 = "sha256:" + hashlib.sha256(receipt.payload).hexdigest()
    if (
        set(complete_value) != expected_complete_fields
        or complete_value.get("schema_version")
        != "cur0s_commercial_sources_completion_v1"
        or complete_value.get("run_id") != receipt_value.get("run_id")
        or complete_value.get("state") != "passed_scope"
        or complete_value.get("receipt_sha256") != receipt_sha256
        or complete_value.get("receipt_root_sha256") != receipt_root
        or complete_value.get("receipt_bytes") != len(receipt.payload)
        or complete_value.get("completion_protocol")
        != (
            "raw_sources_fsync_read_only_then_receipt_O_EXCL_fsync_read_only_"
            "then_COMPLETE_O_EXCL_fsync_last"
        )
        or complete_value.get("raw_sources_preserved_on_phone") is not True
        or complete_value.get("output_directory_mode") != "owner_only_0700"
    ):
        raise SourceParseError("acquisition_completion_binding_invalid")
    _parse_utc_second(
        complete_value.get("completion_marker_prepared_at_utc"),
        "acquisition_completion_timestamp_invalid",
    )
    source_root = receipt_value.get("source_root")
    artifacts, artifact_by_id = _validate_source_root_claims(
        source_root,
        contract_root,
        commercial,
    )
    try:
        rebuilt_root = commercial.build_source_root(artifacts)
    except commercial.CommercialSourceError as exc:
        raise SourceParseError("acquisition_source_root_invalid") from exc
    if source_root != rebuilt_root or source_root.get("contract_root_sha256") != (
        contract_root
    ):
        raise SourceParseError("acquisition_source_root_binding_invalid")
    direct_specs = tuple(commercial.DIRECT_SOURCES)
    git_specs = tuple(commercial.GIT_SOURCES)
    specs = (*direct_specs, *git_specs)
    spec_by_id = {spec.source_id: spec for spec in specs}
    if len(spec_by_id) != len(specs) or len(artifacts) != len(specs):
        raise SourceParseError("acquisition_source_roster_invalid")
    _validate_source_execution_identity(
        receipt_value.get("source_execution_identity"),
        receipt_value,
        artifacts,
        commercial,
        authority_closure.preregistration.value,
        authority_closure.native_manifest,
    )
    preregistration = authority_closure.preregistration.value
    _validate_runtime_identity(receipt_value.get("runtime_identity"), commercial)
    target_device = _require_exact_mapping(
        preregistration.get("target_device"),
        {
            "adb_serial_sha256",
            "architecture",
            "build_fingerprint_sha256",
            "device",
            "model",
            "private_home",
            "python_platform_system",
            "soc",
        },
        "acquisition_preregistered_target_schema_invalid",
    )
    resource_slice = preregistration.get("resource_slice")
    runtime_identity = receipt_value["runtime_identity"]
    if (
        not isinstance(resource_slice, Mapping)
        or target_device.get("private_home") != str(PHONE_HOME)
        or runtime_identity.get("model") != target_device.get("model")
        or runtime_identity.get("device") != target_device.get("device")
        or runtime_identity.get("soc") != target_device.get("soc")
        or runtime_identity.get("architecture") != target_device.get("architecture")
        or runtime_identity.get("python_platform_system")
        != target_device.get("python_platform_system")
        or runtime_identity.get("build_fingerprint_sha256")
        != target_device.get("build_fingerprint_sha256")
        or runtime_identity.get("adb_serial_sha256")
        != target_device.get("adb_serial_sha256")
        or runtime_identity.get("private_home_sha256")
        != "sha256:"
        + hashlib.sha256(target_device["private_home"].encode("utf-8")).hexdigest()
        or resource_slice.get("phone_adb_serial_sha256")
        != target_device.get("adb_serial_sha256")
        or resource_slice.get("phone_model") != target_device.get("model")
        or resource_slice.get("phone_soc") != target_device.get("soc")
    ):
        raise SourceParseError("acquisition_preregistered_target_binding_invalid")
    authority_bindings = _validate_authority_bindings(
        receipt_value.get("authority_bindings")
    )
    preregistration_sha256 = (
        "sha256:"
        + hashlib.sha256(authority_closure.preregistration.payload).hexdigest()
    )
    if (
        authority_bindings["preregistration_sha256"] != preregistration_sha256
        or authority_bindings["preregistration_root_sha256"]
        != preregistration.get("preregistration_root_sha256")
        or authority_bindings["campaign_lease_root_sha256"]
        != commercial.canonical_sha256(preregistration.get("campaign_lease"))
        or authority_bindings["resource_slice_root_sha256"]
        != commercial.canonical_sha256(preregistration.get("resource_slice"))
        or authority_bindings["network_policy_root_sha256"]
        != commercial.canonical_sha256(preregistration.get("network_policy"))
        or receipt_value.get("commercial_source_contract_sha256")
        != preregistration.get("commercial_source_contract_sha256")
        or receipt_value.get("commercial_source_contract_root_sha256")
        != preregistration["commercial_source_contract"].get("contract_root_sha256")
    ):
        raise SourceParseError("acquisition_preregistration_receipt_binding_invalid")
    _validate_custody(receipt_value.get("custody"))
    _validate_inspection_summaries(
        receipt_value.get("source_inspection_summaries"),
        specs,
        artifact_by_id,
        {spec.source_id for spec in git_specs},
    )
    _validate_resource_and_execution_snapshots(
        receipt_value.get("preterminal_resource_envelope_snapshot"),
        receipt_value.get("preterminal_execution_snapshot"),
        run_id,
        commercial.phone_thermal_safety_contract(),
    )
    lease = preregistration.get("campaign_lease")
    resource_snapshot = receipt_value.get("preterminal_resource_envelope_snapshot")
    if not isinstance(lease, Mapping) or not isinstance(resource_snapshot, Mapping):
        raise SourceParseError("acquisition_campaign_resource_binding_invalid")
    lease_to_snapshot = {
        "action_id": "action_id",
        "max_wall_seconds": "max_wall_seconds",
        "terminalization_reserve_seconds": "terminalization_reserve_seconds",
        "min_free_storage_bytes": "min_free_storage_bytes",
        "thermal_sample_interval_seconds": "thermal_sample_interval_seconds",
        "max_private_output_bytes": "max_private_output_bytes",
        "expires_at_utc": "lease_expires_at_utc",
    }
    if any(
        lease.get(lease_field) != resource_snapshot.get(snapshot_field)
        for lease_field, snapshot_field in lease_to_snapshot.items()
    ):
        raise SourceParseError("acquisition_campaign_resource_binding_invalid")
    thermal_contract = lease.get("thermal_safety_contract")
    if (
        not isinstance(thermal_contract, Mapping)
        or thermal_contract.get("contract_root_sha256")
        != resource_snapshot.get("thermal_safety_contract_root_sha256")
        or thermal_contract.get("group_ceilings_millidegrees_c")
        != resource_snapshot.get("thermal_group_ceilings_millidegrees_c")
        or thermal_contract.get("unavailable_sentinels_millidegrees_c")
        != resource_snapshot.get("thermal_unavailable_sentinels_millidegrees_c")
    ):
        raise SourceParseError("acquisition_campaign_resource_binding_invalid")
    execution_claim_sha256 = _validate_execution_claim(
        candidate_path,
        candidate_metadata,
        receipt_value.get("execution_claim"),
        run_id,
        authority_bindings["preregistration_root_sha256"],
        contract_root,
    )
    if source_id not in spec_by_id or source_id not in artifact_by_id:
        raise SourceParseError("acquisition_source_id_not_admitted")
    spec = spec_by_id[source_id]
    artifact = artifact_by_id[source_id]
    if isinstance(spec, commercial.DirectSourceSpec):
        local_locator = f"sources/direct/{source_id}/{spec.filename}"
        suffix = spec.filename.lower()
        if source_id == "wordnet_3_0" and suffix.endswith(".tar.gz"):
            source_format = "wordnet_tar"
        elif source_id == "usda_nalt_core_2024" and suffix.endswith(".ttl.zip"):
            source_format = "nalt_turtle_zip"
        elif suffix.endswith(".obo"):
            source_format = "obo"
        elif source_id == "usgs_thesaurus_2023_11_02" and suffix.endswith(".rdf"):
            source_format = "usgs_skos_rdf"
        elif source_id.startswith("siyavula_") and suffix.endswith(".epub"):
            source_format = "siyavula_epub"
        else:
            raise SourceParseError("acquisition_source_format_not_derivable")
        source_manifest_json = None
        is_tree = False
    elif isinstance(spec, commercial.GitSourceSpec):
        local_locator = f"sources/git/{source_id}/checkout"
        source_format = "openstax_tree"
        source_manifest_json = _contract_canonical_json_bytes(
            artifact["content_manifest"]
        ).decode("utf-8")
        is_tree = True
    else:
        raise SourceParseError("acquisition_source_spec_type_invalid")
    if artifact.get("local_locator") != local_locator:
        raise SourceParseError("acquisition_source_locator_mismatch")
    context = ParseContext(
        source_id=spec.source_id,
        release_identity=spec.release_identity,
        source_sha256=artifact["sha256"],
        source_locator=local_locator,
        license_id=spec.license_id,
        license_class=spec.license_class,
        rights_proof=spec.rights_proof,
        source_manifest_json=source_manifest_json,
    )
    context.validate()
    production_verification = _production_verification_record(
        receipt=receipt,
        completion=completion,
        receipt_root_sha256=receipt_root,
        source_root_sha256=source_root["source_root_sha256"],
        receipt_value=receipt_value,
        source_id=source_id,
        artifact=artifact,
        execution_claim_sha256=execution_claim_sha256,
        authority_closure=authority_closure,
    )
    return _VerifiedSourceBinding(
        context=context,
        source_format=source_format,
        local_locator=local_locator,
        is_tree=is_tree,
        owner_uid=candidate_metadata.st_uid,
        candidate_path=candidate_path,
        candidate_identity=_stat_identity(candidate_metadata),
        receipt=receipt,
        completion=completion,
        expected_authority=expected_authority,
        authority_closure=authority_closure,
        production_verification=production_verification,
    )


def _reattest_terminal_binding(
    action_fd: int,
    candidate_runs_fd: int,
    candidate_fd: int,
    binding: _VerifiedSourceBinding,
) -> None:
    from polymath_ai.corpus import cur0s_commercial_sources as commercial

    try:
        metadata = os.fstat(candidate_fd)
        entries = set(os.listdir(candidate_fd))
    except OSError as exc:
        raise SourceParseError("acquisition_candidate_read_failed") from exc
    if _stat_identity(metadata) != binding.candidate_identity or entries != {
        "sources",
        "receipt.json",
        "COMPLETE.json",
    }:
        raise SourceParseError("acquisition_candidate_changed")
    run_id, action_root = _derive_canonical_action_path(binding.candidate_path)
    observed_closure = _build_action_authority_closure(
        action_fd,
        candidate_runs_fd,
        run_id=run_id,
        action_root=action_root,
        owner_uid=binding.owner_uid,
        expected_authority=binding.expected_authority,
        commercial=commercial,
    )
    if observed_closure != binding.authority_closure:
        raise SourceParseError("acquisition_retained_authority_artifact_changed")
    receipt = _read_canonical_contract_json_at(candidate_fd, "receipt.json")
    completion = _read_canonical_contract_json_at(candidate_fd, "COMPLETE.json")
    if receipt != binding.receipt or completion != binding.completion:
        raise SourceParseError("acquisition_terminal_artifact_changed")
    receipt_value = receipt.value
    claim_sha256 = _validate_execution_claim(
        binding.candidate_path,
        metadata,
        receipt_value["execution_claim"],
        receipt_value["run_id"],
        receipt_value["authority_bindings"]["preregistration_root_sha256"],
        receipt_value["commercial_source_contract_root_sha256"],
    )
    if claim_sha256 != binding.production_verification.execution_claim_sha256:
        raise SourceParseError("acquisition_execution_claim_changed")


@contextmanager
def _open_relative_directory_fd(
    root_fd: int,
    relative: str,
    *,
    sealed_owner_uid: int | None = None,
) -> Iterator[int]:
    parts = PurePosixPath(_safe_archive_name(relative)).parts
    try:
        current_fd = os.dup(root_fd)
    except OSError as exc:
        raise SourceParseError("acquisition_root_duplicate_failed") from exc
    try:
        for part in parts:
            try:
                child_fd = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=current_fd,
                )
            except OSError as exc:
                raise SourceParseError("acquisition_directory_open_failed") from exc
            child_metadata = os.fstat(child_fd)
            if sealed_owner_uid is not None and (
                stat.S_IMODE(child_metadata.st_mode) != 0o500
                or child_metadata.st_uid != sealed_owner_uid
            ):
                os.close(child_fd)
                raise SourceParseError("acquisition_directory_seal_invalid")
            os.close(current_fd)
            current_fd = child_fd
        yield current_fd
    finally:
        os.close(current_fd)


def iter_verified_normalized_source_units(
    acquisition_candidate: str | os.PathLike[str],
    source_id: str,
    expected_authority: ProductionAuthorityExpectation,
    limits: ParserLimits = DEFAULT_LIMITS,
) -> Iterator[VerifiedSourceUnitEnvelope]:
    """Normalize one exact receipt-bound source without caller-supplied rights.

    This is the sole authoritative production dispatch.  Source identity,
    release, locator, rights, format, and (for Git trees) the full manifest are
    derived from the canonical passed-scope acquisition transaction and frozen
    contract.  No ``ParseContext`` or format selector crosses this boundary.
    Each unit is returned only inside a hash-bound production verification
    envelope, so receipt, source-root, run, candidate, and one-shot claim
    provenance cannot be discarded accidentally at this API boundary.

    The underlying normalizer exhausts, validates, persists, rereads, and
    reattests the complete bounded batch before its first envelope is yielded.
    That is all-or-nothing for parser/validation errors discovered during that
    process; it does not make caller interruption atomic and does not claim
    resistance to a malicious concurrent writer with the same Termux UID.
    """

    limits.validate()
    if not isinstance(expected_authority, ProductionAuthorityExpectation):
        raise SourceParseError("production_authority_expectation_required")
    expected_authority.validate()
    _validate_identifier(source_id, "source_id", limits)
    candidate_path = Path(os.path.abspath(os.fspath(acquisition_candidate)))
    with _open_canonical_action_handles(candidate_path) as handles:
        (
            action_fd,
            candidate_runs_fd,
            candidate_fd,
            run_id,
            action_root,
            owner_uid,
        ) = handles
        binding = _validate_terminal_binding(
            action_fd,
            candidate_runs_fd,
            candidate_fd,
            candidate_path,
            source_id,
            run_id,
            action_root,
            owner_uid,
            expected_authority,
        )
        if binding.is_tree:
            with _open_relative_directory_fd(
                candidate_fd,
                binding.local_locator,
                sealed_owner_uid=binding.owner_uid,
            ) as source_fd:
                source_identity = _stat_identity(os.fstat(source_fd))

                def revalidate_tree_path() -> None:
                    _reattest_terminal_binding(
                        action_fd,
                        candidate_runs_fd,
                        candidate_fd,
                        binding,
                    )
                    with _open_relative_directory_fd(
                        candidate_fd,
                        binding.local_locator,
                        sealed_owner_uid=binding.owner_uid,
                    ) as reopened:
                        if _stat_identity(os.fstat(reopened)) != source_identity:
                            raise SourceParseError("acquisition_source_path_changed")

                for unit in _iter_held_openstax_fd(
                    source_fd,
                    binding.context,
                    limits,
                    revalidate_tree_path,
                    sealed_owner_uid=binding.owner_uid,
                ):
                    yield _verified_source_unit_envelope(
                        unit,
                        binding.production_verification,
                    )
            return
        with _open_relative_regular_fd(
            candidate_fd,
            binding.local_locator,
            sealed_owner_uid=binding.owner_uid,
        ) as source_fd:
            source_identity = _stat_identity(os.fstat(source_fd))

            def revalidate_file_path() -> None:
                _reattest_terminal_binding(
                    action_fd,
                    candidate_runs_fd,
                    candidate_fd,
                    binding,
                )
                with _open_relative_regular_fd(
                    candidate_fd,
                    binding.local_locator,
                    sealed_owner_uid=binding.owner_uid,
                ) as reopened:
                    if _stat_identity(os.fstat(reopened)) != source_identity:
                        raise SourceParseError("acquisition_source_path_changed")

            parser = {
                "wordnet_tar": _parse_wordnet_tar_handle,
                "nalt_turtle_zip": _parse_nalt_turtle_zip_handle,
                "obo": _parse_obo_handle,
                "usgs_skos_rdf": _parse_usgs_skos_rdf_handle,
                "siyavula_epub": _parse_siyavula_epub_handle,
            }.get(binding.source_format)
            if parser is None:
                raise SourceParseError("acquisition_source_format_not_derivable")
            for unit in _iter_held_regular_fd(
                source_fd,
                PurePosixPath(binding.local_locator).name,
                binding.context,
                limits,
                parser,
                revalidate_file_path,
            ):
                yield _verified_source_unit_envelope(
                    unit,
                    binding.production_verification,
                )


__all__ = [
    "DEFAULT_LIMITS",
    "SOURCE_UNIT_SCHEMA",
    "UNVERIFIED_PARSER_FORMATS",
    "ParseContext",
    "ParserLimits",
    "ProductionAuthorityExpectation",
    "ProductionVerificationRecord",
    "ProvenanceRecord",
    "RightsRecord",
    "SourceEdge",
    "SourceFacet",
    "SourceFlags",
    "SourceParseError",
    "SourceUnit",
    "VerifiedSourceUnitEnvelope",
    "canonical_json_bytes",
    "canonical_sha256",
    "iter_unverified_source_units",
    "iter_verified_normalized_source_units",
    "parse_nalt_turtle_zip",
    "parse_obo",
    "parse_openstax_tree",
    "parse_siyavula_epub",
    "parse_usgs_skos_rdf",
    "parse_wordnet_tar",
    "stable_unit_id",
    "validate_source_unit",
]

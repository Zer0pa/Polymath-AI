"""Bounded production parser for the Open English WordNet 2025 GWA-LMF core.

This module deliberately accepts a binary opener rather than a pathname.  It
hash-binds the compressed object, decompresses it exactly once into an injected
bounded spool, and parses the immutable decompressed bytes twice.  The first
pass establishes the complete identifier index; the second validates every
reference and writes typed units to a canonical spool.  Nothing is exposed
until both passes and the canonical-spool hash have completed.

Relations describe source topology only.  Their distinct partition metadata
states that they are dependencies and must never be interpreted as split-union
instructions.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field, fields
from enum import Enum
import hashlib
from io import BytesIO
import json
import math
import re
import time
from typing import Any, BinaryIO, Callable, Iterator, Mapping, Protocol, TypeAlias
import unicodedata
import xml.parsers.expat as expat
import zlib


OEWN_SOURCE_ID = "open_english_wordnet_2025_core_gwa_lmf"
OEWN_UNIT_SCHEMA = "cur0s_oewn_gwa_lmf_unit_v1"
OEWN_CORPUS_SCHEMA = "cur0s_oewn_gwa_lmf_corpus_v1"
DEPENDENCY_ONLY_PARTITION_EFFECT = "dependency_only_never_split_union"

DC_NAMESPACE = "http://purl.org/dc/elements/1.1/"
XSI_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"
XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_XML_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]*$")
_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]*$")
_SCHEMA_LOCATION_RE = re.compile(
    r"^(?:https://globalwordnet\.github\.io/schemas/)?"
    r"WN-LMF-1\.[0-9]+(?:\.[0-9]+)?\.xsd$"
)
_FORBIDDEN_DECLARATION_RE = re.compile(
    rb"<![\x09\x0a\x0d\x20]*(?:DOCTYPE|ENTITY)\b",
    re.IGNORECASE,
)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PARTS_OF_SPEECH = frozenset({"n", "v", "a", "r", "s"})
_TEXT_TAGS = frozenset({"Definition", "ILIDefinition", "Example", "Pronunciation"})


class OewnParseError(RuntimeError):
    """The supplied OEWN object is unsafe, malformed, or exceeds a bound."""


class PartitionEffect(str, Enum):
    """Effects which source topology may have on downstream partitioning."""

    DEPENDENCY_ONLY_NEVER_SPLIT_UNION = DEPENDENCY_ONLY_PARTITION_EFFECT


@dataclass(frozen=True, slots=True)
class DependencyOnlyPartitionMetadata:
    """A relation is a dependency and is never a split-union directive."""

    partition_effect: PartitionEffect = (
        PartitionEffect.DEPENDENCY_ONLY_NEVER_SPLIT_UNION
    )


DEPENDENCY_PARTITION = DependencyOnlyPartitionMetadata()


@dataclass(frozen=True, slots=True)
class OewnParserLimits:
    """Hard limits for compressed input, XML, indexes, spools, and wall time."""

    max_compressed_bytes: int = 64 * 1024 * 1024
    max_uncompressed_bytes: int = 1024 * 1024 * 1024
    max_compression_ratio: float = 200.0
    compression_ratio_grace_bytes: int = 64 * 1024
    compressed_read_chunk_bytes: int = 256 * 1024
    decompressed_output_chunk_bytes: int = 1024 * 1024
    xml_read_chunk_bytes: int = 64 * 1024
    max_xml_markup_bytes: int = 256 * 1024
    max_xml_reference_bytes: int = 4 * 1024
    max_xml_depth: int = 32
    max_xml_elements: int = 6_000_000
    max_attributes_per_element: int = 24
    max_attribute_chars: int = 32 * 1024
    max_total_attribute_chars: int = 512 * 1024 * 1024
    max_text_chars_per_element: int = 8 * 1024 * 1024
    max_total_text_chars: int = 1024 * 1024 * 1024
    max_identifier_chars: int = 1024
    max_lexicons: int = 1
    max_units: int = 1_500_000
    max_relations: int = 4_000_000
    max_relations_per_unit: int = 32_768
    max_references_per_unit: int = 32_768
    max_values_per_unit: int = 8_192
    max_index_bytes: int = 384 * 1024 * 1024
    max_canonical_unit_bytes: int = 16 * 1024 * 1024
    max_canonical_bytes: int = 4 * 1024 * 1024 * 1024
    max_spool_bytes: int = 4 * 1024 * 1024 * 1024
    max_default_in_memory_spool_bytes: int = 32 * 1024 * 1024
    max_wall_seconds: float = 3_600.0
    checkpoint_interval_events: int = 2_048

    def validate(self) -> None:
        for definition in fields(self):
            name = definition.name
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise OewnParseError(f"invalid_limit_type:{name}")
            if not math.isfinite(float(value)) or value <= 0:
                raise OewnParseError(f"invalid_limit_value:{name}")
        if self.compression_ratio_grace_bytes > self.max_compressed_bytes:
            raise OewnParseError("ratio_grace_exceeds_compressed_limit")
        if self.max_canonical_unit_bytes > self.max_canonical_bytes:
            raise OewnParseError("unit_limit_exceeds_canonical_limit")
        if self.max_canonical_unit_bytes > self.max_spool_bytes:
            raise OewnParseError("unit_limit_exceeds_spool_limit")


DEFAULT_LIMITS = OewnParserLimits()


@dataclass(frozen=True, slots=True)
class OewnSourceIdentity:
    """Expected immutable identity of one compressed OEWN release object."""

    release_identity: str
    compressed_sha256: str
    compressed_bytes: int
    expected_schema_location: str
    source_id: str = field(default=OEWN_SOURCE_ID, init=False)

    def validate(self, limits: OewnParserLimits) -> None:
        _bounded_scalar(self.release_identity, "release_identity", limits)
        if not _SHA256_RE.fullmatch(self.compressed_sha256):
            raise OewnParseError("invalid_expected_compressed_sha256")
        if (
            isinstance(self.compressed_bytes, bool)
            or not isinstance(self.compressed_bytes, int)
            or self.compressed_bytes <= 0
            or self.compressed_bytes > limits.max_compressed_bytes
        ):
            raise OewnParseError("invalid_expected_compressed_bytes")
        _bounded_scalar(
            self.expected_schema_location,
            "expected_schema_location",
            limits,
        )
        if not _SCHEMA_LOCATION_RE.fullmatch(self.expected_schema_location):
            raise OewnParseError("invalid_expected_schema_location")


@dataclass(frozen=True, slots=True)
class OewnCheckpoint:
    """Bounded progress state supplied to the injected lease callback."""

    phase: str
    compressed_bytes: int
    uncompressed_bytes: int
    xml_events: int
    units: int
    relations: int
    spool_bytes: int
    elapsed_seconds: float


@dataclass(frozen=True, slots=True)
class OewnText:
    value: str
    language: str | None
    source: str | None
    attributes: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class OewnForm:
    written_form: str
    part_of_speech: str | None
    script: str | None
    tags: str | None
    pronunciations: tuple[OewnText, ...] = ()


@dataclass(frozen=True, slots=True)
class OewnReference:
    target_kind: str
    target_record_id: str
    target_stable_id: str
    partition: DependencyOnlyPartitionMetadata = DEPENDENCY_PARTITION


@dataclass(frozen=True, slots=True)
class OewnRelation:
    stable_id: str
    relation_kind: str
    source_record_id: str
    source_stable_id: str
    target_record_id: str
    target_stable_id: str
    relation_type: str
    attributes: tuple[tuple[str, str], ...]
    occurrence: int
    partition: DependencyOnlyPartitionMetadata = DEPENDENCY_PARTITION


@dataclass(frozen=True, slots=True)
class OewnSyntacticBehavior:
    subcategorization_frame: str
    senses: tuple[OewnReference, ...]


@dataclass(frozen=True, slots=True)
class _OewnUnitBase:
    source_id: str
    release_identity: str
    lexicon_id: str
    language: str
    source_record_id: str
    stable_id: str
    partition: DependencyOnlyPartitionMetadata = DEPENDENCY_PARTITION


@dataclass(frozen=True, slots=True)
class OewnLexicalEntryUnit(_OewnUnitBase):
    lemma: OewnForm = field(default_factory=lambda: OewnForm("", None, None, None))
    forms: tuple[OewnForm, ...] = ()
    senses: tuple[OewnReference, ...] = ()
    syntactic_behaviors: tuple[OewnSyntacticBehavior, ...] = ()

    @property
    def unit_kind(self) -> str:
        return "lexical_entry"


@dataclass(frozen=True, slots=True)
class OewnSenseUnit(_OewnUnitBase):
    lexical_entry: OewnReference = field(
        default_factory=lambda: OewnReference("lexical_entry", "", "")
    )
    synset: OewnReference = field(
        default_factory=lambda: OewnReference("synset", "", "")
    )
    relations: tuple[OewnRelation, ...] = ()
    examples: tuple[OewnText, ...] = ()
    adjective_position: str | None = None

    @property
    def unit_kind(self) -> str:
        return "sense"


@dataclass(frozen=True, slots=True)
class OewnSynsetUnit(_OewnUnitBase):
    ili: str | None = None
    part_of_speech: str = ""
    lexfile: str | None = None
    members: tuple[OewnReference, ...] = ()
    definitions: tuple[OewnText, ...] = ()
    ili_definitions: tuple[OewnText, ...] = ()
    examples: tuple[OewnText, ...] = ()
    relations: tuple[OewnRelation, ...] = ()

    @property
    def unit_kind(self) -> str:
        return "synset"


OewnUnit: TypeAlias = OewnLexicalEntryUnit | OewnSenseUnit | OewnSynsetUnit


@dataclass(frozen=True, slots=True)
class OewnLexiconMetadata:
    lexicon_id: str
    label: str
    language: str
    version: str
    email: str | None
    license: str
    url: str | None
    citation: str | None
    logo: str | None


@dataclass(frozen=True, slots=True)
class OewnCorpusMetadata:
    schema: str
    source_id: str
    release_identity: str
    compressed_sha256: str
    compressed_bytes: int
    uncompressed_sha256: str
    uncompressed_bytes: int
    xml_schema_location: str
    global_label: str
    lexicons: tuple[OewnLexiconMetadata, ...]
    lexical_entry_count: int
    sense_count: int
    synset_count: int
    relation_count: int
    partition: DependencyOnlyPartitionMetadata = DEPENDENCY_PARTITION


class BinaryOpener(Protocol):
    def __call__(self) -> AbstractContextManager[BinaryIO]: ...


class BoundedSpoolFactory(Protocol):
    def __call__(self, purpose: str, maximum_bytes: int) -> BinaryIO: ...


CheckpointCallback: TypeAlias = Callable[[OewnCheckpoint], None]
Clock: TypeAlias = Callable[[], float]


@dataclass(frozen=True, slots=True)
class _StagedRecord:
    sort_key: tuple[int, str, str]
    offset: int
    length: int
    sha256: str


class OewnParsedCorpus:
    """Completed hash-bound corpus backed by an owned canonical binary spool."""

    __slots__ = (
        "_canonical_sha256",
        "_closed",
        "_iterating",
        "_max_unit_bytes",
        "_metadata",
        "_runtime",
        "_spool",
        "_spool_bytes",
        "_spool_sha256",
        "_unit_count",
    )

    def __init__(
        self,
        *,
        metadata: OewnCorpusMetadata,
        spool: BinaryIO,
        spool_sha256: str,
        canonical_sha256: str,
        unit_count: int,
        spool_bytes: int,
        max_unit_bytes: int,
        runtime: _Runtime,
    ) -> None:
        self._metadata = metadata
        self._canonical_sha256 = canonical_sha256
        self._unit_count = unit_count
        self._spool = spool
        self._spool_sha256 = spool_sha256
        self._spool_bytes = spool_bytes
        self._max_unit_bytes = max_unit_bytes
        self._runtime = runtime
        self._closed = False
        self._iterating = False

    @property
    def metadata(self) -> OewnCorpusMetadata:
        return self._metadata

    @property
    def canonical_sha256(self) -> str:
        return self._canonical_sha256

    @property
    def unit_count(self) -> int:
        return self._unit_count

    def __enter__(self) -> OewnParsedCorpus:
        if self._closed:
            raise OewnParseError("corpus_closed")
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._spool.close()

    def iter_canonical_lines(self) -> Iterator[bytes]:
        """Yield immutable unit lines after a complete pre-yield spool rehash."""

        yield from self._iterate_lines()

    def iter_units(self) -> Iterator[OewnUnit]:
        """Yield typed units; malformed internal canonical data fails closed."""

        for line in self._iterate_lines():
            try:
                value = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise OewnParseError("canonical_unit_decode_failed") from exc
            if not isinstance(value, dict):
                raise OewnParseError("canonical_unit_not_object")
            yield _unit_from_mapping(value)

    def _iterate_lines(self) -> Iterator[bytes]:
        if self._closed:
            raise OewnParseError("corpus_closed")
        if self._iterating:
            raise OewnParseError("concurrent_corpus_iteration_forbidden")
        self._verify_spool()
        self._iterating = True
        try:
            self._spool.seek(0)
            for _ in range(self.unit_count):
                line = self._spool.readline(self._max_unit_bytes + 2)
                if not line or len(line) > self._max_unit_bytes + 1:
                    raise OewnParseError("canonical_unit_line_invalid")
                if not line.endswith(b"\n"):
                    raise OewnParseError("canonical_unit_newline_missing")
                self._runtime.checkpoint("canonical_unit_iteration")
                yield line
            if self._spool.read(1):
                raise OewnParseError("canonical_unit_count_mismatch")
        finally:
            self._iterating = False

    def _verify_spool(self) -> None:
        self._spool.seek(0)
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = self._spool.read(256 * 1024)
            if not chunk:
                break
            if len(chunk) > 256 * 1024:
                raise OewnParseError("canonical_spool_oversized_read")
            total += len(chunk)
            if total > self._spool_bytes:
                raise OewnParseError("canonical_spool_byte_mismatch")
            digest.update(chunk)
            self._runtime.checkpoint("canonical_spool_pre_yield_rehash")
        if total != self._spool_bytes:
            raise OewnParseError("canonical_spool_byte_mismatch")
        if "sha256:" + digest.hexdigest() != self._spool_sha256:
            raise OewnParseError("canonical_spool_sha256_mismatch")


@dataclass(slots=True)
class _Runtime:
    limits: OewnParserLimits
    clock: Clock
    callback: CheckpointCallback | None
    started: float = field(init=False)
    last_clock: float = field(init=False)
    compressed_bytes: int = 0
    uncompressed_bytes: int = 0
    xml_events: int = 0
    units: int = 0
    relations: int = 0
    spool_bytes: int = 0

    def __post_init__(self) -> None:
        self.started = self._read_clock()
        self.last_clock = self.started

    def xml_event(self, phase: str) -> None:
        self.xml_events += 1
        if self.xml_events % self.limits.checkpoint_interval_events == 0:
            self.checkpoint(phase)

    def checkpoint(self, phase: str, *, force: bool = False) -> None:
        del force
        now = self._read_clock()
        if now < self.last_clock:
            raise OewnParseError("clock_moved_backwards")
        self.last_clock = now
        elapsed = now - self.started
        if elapsed > self.limits.max_wall_seconds:
            raise OewnParseError("wall_time_limit_exceeded")
        if self.callback is None:
            return
        state = OewnCheckpoint(
            phase=phase,
            compressed_bytes=self.compressed_bytes,
            uncompressed_bytes=self.uncompressed_bytes,
            xml_events=self.xml_events,
            units=self.units,
            relations=self.relations,
            spool_bytes=self.spool_bytes,
            elapsed_seconds=elapsed,
        )
        try:
            self.callback(state)
        except Exception as exc:
            raise OewnParseError("checkpoint_callback_failed") from exc

    def _read_clock(self) -> float:
        try:
            value = self.clock()
        except Exception as exc:
            raise OewnParseError("clock_failed") from exc
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise OewnParseError("clock_returned_invalid_type")
        result = float(value)
        if not math.isfinite(result):
            raise OewnParseError("clock_returned_nonfinite")
        return result


def _bounded_scalar(
    value: str,
    field_name: str,
    limits: OewnParserLimits,
    *,
    maximum: int | None = None,
) -> str:
    if not isinstance(value, str) or not value:
        raise OewnParseError(f"invalid_scalar:{field_name}")
    bound = maximum if maximum is not None else limits.max_attribute_chars
    if len(value) > bound:
        raise OewnParseError(f"scalar_limit_exceeded:{field_name}")
    if value != value.strip() or _CONTROL_RE.search(value):
        raise OewnParseError(f"invalid_scalar_content:{field_name}")
    if unicodedata.normalize("NFC", value) != value:
        raise OewnParseError(f"noncanonical_unicode:{field_name}")
    return value


def _identifier(value: str, field_name: str, limits: OewnParserLimits) -> str:
    _bounded_scalar(
        value,
        field_name,
        limits,
        maximum=limits.max_identifier_chars,
    )
    if not _XML_ID_RE.fullmatch(value):
        raise OewnParseError(f"invalid_identifier:{field_name}")
    return value


def _token(value: str, field_name: str, limits: OewnParserLimits) -> str:
    _bounded_scalar(value, field_name, limits, maximum=limits.max_identifier_chars)
    if not _TOKEN_RE.fullmatch(value):
        raise OewnParseError(f"invalid_token:{field_name}")
    return value


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise OewnParseError("canonical_json_failed") from exc


def _stable_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _stable_id_for(unit_kind: str, source_record_id: str) -> str:
    digest = _stable_digest(
        {
            "schema": OEWN_UNIT_SCHEMA,
            "source_id": OEWN_SOURCE_ID,
            "source_record_id": source_record_id,
            "unit_kind": unit_kind,
        }
    )
    return f"oewn-{unit_kind}-sha256:{digest}"


def _partition_mapping() -> dict[str, str]:
    return {"partition_effect": DEPENDENCY_ONLY_PARTITION_EFFECT}


def _text_mapping(value: OewnText) -> dict[str, Any]:
    return {
        "attributes": [list(item) for item in value.attributes],
        "language": value.language,
        "source": value.source,
        "value": value.value,
    }


def _form_mapping(value: OewnForm) -> dict[str, Any]:
    return {
        "part_of_speech": value.part_of_speech,
        "pronunciations": [_text_mapping(item) for item in value.pronunciations],
        "script": value.script,
        "tags": value.tags,
        "written_form": value.written_form,
    }


def _reference_mapping(value: OewnReference) -> dict[str, Any]:
    return {
        "partition": _partition_mapping(),
        "target_kind": value.target_kind,
        "target_record_id": value.target_record_id,
        "target_stable_id": value.target_stable_id,
    }


def _relation_mapping(value: OewnRelation) -> dict[str, Any]:
    return {
        "attributes": [list(item) for item in value.attributes],
        "occurrence": value.occurrence,
        "partition": _partition_mapping(),
        "relation_kind": value.relation_kind,
        "relation_type": value.relation_type,
        "source_record_id": value.source_record_id,
        "source_stable_id": value.source_stable_id,
        "stable_id": value.stable_id,
        "target_record_id": value.target_record_id,
        "target_stable_id": value.target_stable_id,
    }


def _unit_mapping(value: OewnUnit) -> dict[str, Any]:
    common: dict[str, Any] = {
        "language": value.language,
        "lexicon_id": value.lexicon_id,
        "partition": _partition_mapping(),
        "release_identity": value.release_identity,
        "schema": OEWN_UNIT_SCHEMA,
        "source_id": value.source_id,
        "source_record_id": value.source_record_id,
        "stable_id": value.stable_id,
        "unit_kind": value.unit_kind,
    }
    if isinstance(value, OewnLexicalEntryUnit):
        common.update(
            {
                "forms": [_form_mapping(item) for item in value.forms],
                "lemma": _form_mapping(value.lemma),
                "senses": [_reference_mapping(item) for item in value.senses],
                "syntactic_behaviors": [
                    {
                        "senses": [_reference_mapping(ref) for ref in item.senses],
                        "subcategorization_frame": item.subcategorization_frame,
                    }
                    for item in value.syntactic_behaviors
                ],
            }
        )
    elif isinstance(value, OewnSenseUnit):
        common.update(
            {
                "adjective_position": value.adjective_position,
                "examples": [_text_mapping(item) for item in value.examples],
                "lexical_entry": _reference_mapping(value.lexical_entry),
                "relations": [_relation_mapping(item) for item in value.relations],
                "synset": _reference_mapping(value.synset),
            }
        )
    elif isinstance(value, OewnSynsetUnit):
        common.update(
            {
                "definitions": [_text_mapping(item) for item in value.definitions],
                "examples": [_text_mapping(item) for item in value.examples],
                "ili": value.ili,
                "ili_definitions": [
                    _text_mapping(item) for item in value.ili_definitions
                ],
                "lexfile": value.lexfile,
                "members": [_reference_mapping(item) for item in value.members],
                "part_of_speech": value.part_of_speech,
                "relations": [_relation_mapping(item) for item in value.relations],
            }
        )
    else:
        raise OewnParseError("unknown_unit_type")
    return common


@dataclass(slots=True)
class _TextDraft:
    value: str
    language: str | None
    source: str | None
    attributes: tuple[tuple[str, str], ...]


@dataclass(slots=True)
class _FormDraft:
    written_form: str
    part_of_speech: str | None
    script: str | None
    tags: str | None
    pronunciations: list[_TextDraft] = field(default_factory=list)
    payload_upper_bytes: int = 0


@dataclass(slots=True)
class _RelationDraft:
    relation_kind: str
    target: str
    relation_type: str
    attributes: tuple[tuple[str, str], ...]


@dataclass(slots=True)
class _SenseDraft:
    sense_id: str
    synset_id: str
    adjective_position: str | None
    relations: list[_RelationDraft] = field(default_factory=list)
    examples: list[_TextDraft] = field(default_factory=list)
    payload_upper_bytes: int = 0


@dataclass(slots=True)
class _BehaviorDraft:
    frame: str
    senses: tuple[str, ...]


@dataclass(slots=True)
class _EntryDraft:
    entry_id: str
    lemma: _FormDraft | None = None
    forms: list[_FormDraft] = field(default_factory=list)
    senses: list[_SenseDraft] = field(default_factory=list)
    behaviors: list[_BehaviorDraft] = field(default_factory=list)
    payload_upper_bytes: int = 0


@dataclass(slots=True)
class _SynsetDraft:
    synset_id: str
    ili: str | None
    part_of_speech: str
    lexfile: str | None
    members: tuple[str, ...]
    definitions: list[_TextDraft] = field(default_factory=list)
    ili_definitions: list[_TextDraft] = field(default_factory=list)
    examples: list[_TextDraft] = field(default_factory=list)
    relations: list[_RelationDraft] = field(default_factory=list)
    payload_upper_bytes: int = 0


@dataclass(slots=True)
class _Frame:
    tag: str
    attributes: dict[str, str]
    payload: object | None
    child_counts: dict[str, int] = field(default_factory=dict)
    last_rank: int = -1
    text_parts: list[str] = field(default_factory=list)
    text_chars: int = 0


@dataclass(frozen=True, slots=True)
class _LexiconHeader:
    lexicon_id: str
    label: str
    language: str
    version: str
    email: str | None
    license: str
    url: str | None
    citation: str | None
    logo: str | None


EntryConsumer: TypeAlias = Callable[[_LexiconHeader, _EntryDraft], None]
SynsetConsumer: TypeAlias = Callable[[_LexiconHeader, _SynsetDraft], None]


_ALLOWED_CHILDREN: dict[str, frozenset[str]] = {
    "LexicalResource": frozenset({"GlobalInformation", "Lexicon"}),
    "GlobalInformation": frozenset(),
    "Lexicon": frozenset({"LexicalEntry", "Synset"}),
    "LexicalEntry": frozenset({"Lemma", "Form", "Sense", "SyntacticBehaviour"}),
    "Lemma": frozenset({"Pronunciation"}),
    "Form": frozenset({"Pronunciation"}),
    "Pronunciation": frozenset(),
    "Sense": frozenset({"SenseRelation", "Example"}),
    "SenseRelation": frozenset(),
    "SyntacticBehaviour": frozenset(),
    "Synset": frozenset({"Definition", "ILIDefinition", "Example", "SynsetRelation"}),
    "Definition": frozenset(),
    "ILIDefinition": frozenset(),
    "Example": frozenset(),
    "SynsetRelation": frozenset(),
}

_CHILD_RANKS: dict[str, dict[str, int]] = {
    "LexicalResource": {"GlobalInformation": 0, "Lexicon": 1},
    "Lexicon": {"LexicalEntry": 0, "Synset": 1},
    "LexicalEntry": {
        "Lemma": 0,
        "Form": 1,
        "Sense": 2,
        "SyntacticBehaviour": 3,
    },
}

_XSI_SCHEMA_LOCATION = f"{XSI_NAMESPACE}}}noNamespaceSchemaLocation"
_XML_LANGUAGE = f"{XML_NAMESPACE}}}lang"
_DC_SOURCE = f"{DC_NAMESPACE}}}source"
_DC_TYPE = f"{DC_NAMESPACE}}}type"
_DC_CONTRIBUTOR = f"{DC_NAMESPACE}}}contributor"

_ALLOWED_ATTRIBUTES: dict[str, frozenset[str]] = {
    "LexicalResource": frozenset({_XSI_SCHEMA_LOCATION}),
    "GlobalInformation": frozenset({"label"}),
    "Lexicon": frozenset(
        {
            "id",
            "label",
            "language",
            "email",
            "license",
            "version",
            "url",
            "citation",
            "logo",
        }
    ),
    "LexicalEntry": frozenset({"id"}),
    "Lemma": frozenset({"writtenForm", "partOfSpeech", "script", "tags"}),
    "Form": frozenset({"writtenForm", "script", "tags"}),
    "Pronunciation": frozenset({"variety", "notation", _XML_LANGUAGE, _DC_SOURCE}),
    "Sense": frozenset({"id", "synset", "adjposition"}),
    "SenseRelation": frozenset(
        {"target", "relType", _DC_SOURCE, _DC_TYPE, _DC_CONTRIBUTOR}
    ),
    "SyntacticBehaviour": frozenset({"senses", "subcategorizationFrame"}),
    "Synset": frozenset({"id", "ili", "members", "partOfSpeech", "lexfile"}),
    "Definition": frozenset({_XML_LANGUAGE, _DC_SOURCE, _DC_CONTRIBUTOR}),
    "ILIDefinition": frozenset({_XML_LANGUAGE, _DC_SOURCE, _DC_CONTRIBUTOR}),
    "Example": frozenset({_XML_LANGUAGE, _DC_SOURCE, _DC_CONTRIBUTOR}),
    "SynsetRelation": frozenset(
        {"target", "relType", _DC_SOURCE, _DC_TYPE, _DC_CONTRIBUTOR}
    ),
}

_REQUIRED_ATTRIBUTES: dict[str, frozenset[str]] = {
    "LexicalResource": frozenset({_XSI_SCHEMA_LOCATION}),
    "GlobalInformation": frozenset({"label"}),
    "Lexicon": frozenset({"id", "label", "language", "license", "version"}),
    "LexicalEntry": frozenset({"id"}),
    "Lemma": frozenset({"writtenForm", "partOfSpeech"}),
    "Form": frozenset({"writtenForm"}),
    "Pronunciation": frozenset(),
    "Sense": frozenset({"id", "synset"}),
    "SenseRelation": frozenset({"target", "relType"}),
    "SyntacticBehaviour": frozenset({"senses", "subcategorizationFrame"}),
    "Synset": frozenset({"id", "members", "partOfSpeech"}),
    "Definition": frozenset(),
    "ILIDefinition": frozenset(),
    "Example": frozenset(),
    "SynsetRelation": frozenset({"target", "relType"}),
}


def _payload_upper_bound(*values: str | None, overhead: int = 256) -> int:
    result = overhead
    for value in values:
        if value is not None:
            result += (2 * len(value.encode("utf-8"))) + 32
    return result


def _metadata_upper_bound(attributes: tuple[tuple[str, str], ...]) -> int:
    values = tuple(piece for item in attributes for piece in item)
    return _payload_upper_bound(*values)


def _charge_payload(
    payload: _FormDraft | _SenseDraft | _EntryDraft | _SynsetDraft,
    amount: int,
    limits: OewnParserLimits,
) -> None:
    payload.payload_upper_bytes += amount
    if payload.payload_upper_bytes > limits.max_canonical_unit_bytes:
        raise OewnParseError("record_payload_byte_limit_exceeded")


def _bounded_append(
    values: list[Any],
    value: Any,
    limits: OewnParserLimits,
    error_code: str,
) -> None:
    if len(values) >= limits.max_values_per_unit:
        raise OewnParseError(error_code)
    values.append(value)


def _text_payload_upper_bound(value: _TextDraft) -> int:
    return _payload_upper_bound(
        value.value,
        value.language,
        value.source,
        overhead=512,
    ) + _metadata_upper_bound(value.attributes)


def _relation_payload_upper_bound(value: _RelationDraft) -> int:
    return _payload_upper_bound(
        value.relation_kind,
        value.target,
        value.relation_type,
        overhead=768,
    ) + _metadata_upper_bound(value.attributes)


def _behavior_payload_upper_bound(value: _BehaviorDraft) -> int:
    return _payload_upper_bound(
        value.frame,
        *value.senses,
        overhead=512,
    )


class _GwaLmfDecoder:
    """Expat event state machine; retains at most one source record."""

    def __init__(
        self,
        *,
        limits: OewnParserLimits,
        runtime: _Runtime,
        phase: str,
        entry_consumer: EntryConsumer,
        synset_consumer: SynsetConsumer,
    ) -> None:
        self._limits = limits
        self._runtime = runtime
        self._phase = phase
        self._entry_consumer = entry_consumer
        self._synset_consumer = synset_consumer
        self._stack: list[_Frame] = []
        self._xml_declaration_seen = False
        self._root_closed = False
        self._global_label: str | None = None
        self._schema_location: str | None = None
        self._lexicons: list[_LexiconHeader] = []
        self._namespace_bindings: set[tuple[str | None, str]] = set()
        self._elements = 0
        self._total_attribute_chars = 0
        self._total_text_chars = 0

    def parse(self, source: BinaryIO) -> tuple[str, str, tuple[_LexiconHeader, ...]]:
        parser = expat.ParserCreate(encoding="UTF-8", namespace_separator="}")
        parser.buffer_text = True
        parser.buffer_size = min(8 * 1024, self._limits.xml_read_chunk_bytes)
        parser.namespace_prefixes = False
        parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
        parser.XmlDeclHandler = self._xml_declaration
        parser.StartNamespaceDeclHandler = self._start_namespace
        parser.StartElementHandler = self._start_element
        parser.EndElementHandler = self._end_element
        parser.CharacterDataHandler = self._character_data
        parser.StartDoctypeDeclHandler = self._forbidden_declaration
        parser.EntityDeclHandler = self._forbidden_declaration
        parser.UnparsedEntityDeclHandler = self._forbidden_declaration
        parser.ExternalEntityRefHandler = self._external_entity
        parser.SkippedEntityHandler = self._forbidden_declaration
        parser.ProcessingInstructionHandler = self._processing_instruction

        source.seek(0)
        try:
            while True:
                self._runtime.checkpoint(self._phase)
                chunk = source.read(self._limits.xml_read_chunk_bytes)
                if not chunk:
                    break
                if not isinstance(chunk, bytes):
                    raise OewnParseError("xml_spool_not_binary")
                if len(chunk) > self._limits.xml_read_chunk_bytes:
                    raise OewnParseError("xml_spool_oversized_read")
                parser.Parse(chunk, False)
            parser.Parse(b"", True)
        except OewnParseError:
            raise
        except expat.ExpatError as exc:
            raise OewnParseError("malformed_gwa_lmf_xml") from exc
        except (OSError, ValueError) as exc:
            raise OewnParseError("xml_spool_read_failed") from exc
        if self._stack or not self._root_closed:
            raise OewnParseError("xml_document_incomplete")
        if not self._xml_declaration_seen:
            raise OewnParseError("xml_declaration_missing")
        if self._global_label is None:
            raise OewnParseError("global_information_missing")
        if self._schema_location is None:
            raise OewnParseError("schema_location_missing")
        if len(self._lexicons) != 1:
            raise OewnParseError("unexpected_lexicon_count")
        self._runtime.checkpoint(self._phase, force=True)
        return self._schema_location, self._global_label, tuple(self._lexicons)

    def _xml_declaration(
        self,
        version: str,
        encoding: str | None,
        standalone: int,
    ) -> None:
        self._runtime.xml_event(self._phase)
        if self._xml_declaration_seen or self._stack:
            raise OewnParseError("duplicate_or_late_xml_declaration")
        if version != "1.0" or encoding is None or encoding.lower() != "utf-8":
            raise OewnParseError("unsupported_xml_declaration")
        if standalone not in {-1, 0, 1}:
            raise OewnParseError("invalid_xml_standalone_value")
        self._xml_declaration_seen = True

    def _start_namespace(self, prefix: str | None, uri: str | None) -> None:
        self._runtime.xml_event(self._phase)
        if uri not in {DC_NAMESPACE, XSI_NAMESPACE}:
            raise OewnParseError("unknown_xml_namespace")
        if prefix is None:
            raise OewnParseError("default_xml_namespace_forbidden")
        binding = (prefix, uri)
        if binding in self._namespace_bindings:
            raise OewnParseError("duplicate_xml_namespace_binding")
        self._namespace_bindings.add(binding)

    def _start_element(self, expanded_name: str, attributes: dict[str, str]) -> None:
        self._runtime.xml_event(self._phase)
        if not self._xml_declaration_seen:
            raise OewnParseError("xml_declaration_missing_before_root")
        if "}" in expanded_name or expanded_name not in _ALLOWED_CHILDREN:
            raise OewnParseError(f"unknown_or_namespaced_element:{expanded_name}")
        if self._root_closed:
            raise OewnParseError("element_after_root")
        self._elements += 1
        if self._elements > self._limits.max_xml_elements:
            raise OewnParseError("xml_element_limit_exceeded")
        if len(self._stack) + 1 > self._limits.max_xml_depth:
            raise OewnParseError("xml_depth_limit_exceeded")
        self._validate_attributes(expanded_name, attributes)

        if not self._stack:
            if expanded_name != "LexicalResource":
                raise OewnParseError("gwa_lmf_root_mismatch")
        else:
            parent = self._stack[-1]
            if expanded_name not in _ALLOWED_CHILDREN[parent.tag]:
                raise OewnParseError(
                    f"invalid_child_shape:{parent.tag}:{expanded_name}"
                )
            rank = _CHILD_RANKS.get(parent.tag, {}).get(expanded_name)
            if rank is not None:
                if rank < parent.last_rank:
                    raise OewnParseError(
                        f"invalid_child_order:{parent.tag}:{expanded_name}"
                    )
                parent.last_rank = rank
            parent.child_counts[expanded_name] = (
                parent.child_counts.get(expanded_name, 0) + 1
            )

        payload = self._new_payload(expanded_name, attributes)
        self._stack.append(
            _Frame(
                tag=expanded_name,
                attributes=dict(attributes),
                payload=payload,
            )
        )

    def _validate_attributes(self, tag: str, attributes: Mapping[str, str]) -> None:
        if len(attributes) > self._limits.max_attributes_per_element:
            raise OewnParseError("xml_attribute_count_limit_exceeded")
        names = set(attributes)
        unknown = names - _ALLOWED_ATTRIBUTES[tag]
        missing = _REQUIRED_ATTRIBUTES[tag] - names
        if unknown:
            raise OewnParseError(f"unknown_attribute:{tag}:{sorted(unknown)[0]}")
        if missing:
            raise OewnParseError(f"missing_attribute:{tag}:{sorted(missing)[0]}")
        for name, value in attributes.items():
            _bounded_scalar(value, f"{tag}.{name}", self._limits)
            self._total_attribute_chars += len(name) + len(value)
            if self._total_attribute_chars > self._limits.max_total_attribute_chars:
                raise OewnParseError("xml_total_attribute_chars_limit_exceeded")

    def _new_payload(self, tag: str, attributes: Mapping[str, str]) -> object | None:
        if tag == "LexicalResource":
            location = attributes[_XSI_SCHEMA_LOCATION]
            if not _SCHEMA_LOCATION_RE.fullmatch(location):
                raise OewnParseError("unsupported_gwa_lmf_schema_location")
            self._schema_location = location
            return None
        if tag == "Lexicon":
            language = attributes["language"]
            if language != "en":
                raise OewnParseError("oewn_lexicon_language_mismatch")
            return _LexiconHeader(
                lexicon_id=_identifier(attributes["id"], "lexicon.id", self._limits),
                label=attributes["label"],
                language=language,
                version=attributes["version"],
                email=attributes.get("email"),
                license=attributes["license"],
                url=attributes.get("url"),
                citation=attributes.get("citation"),
                logo=attributes.get("logo"),
            )
        if tag == "LexicalEntry":
            entry = _EntryDraft(
                entry_id=_identifier(attributes["id"], "lexical_entry.id", self._limits)
            )
            _charge_payload(
                entry,
                _payload_upper_bound(entry.entry_id),
                self._limits,
            )
            return entry
        if tag in {"Lemma", "Form"}:
            part_of_speech = attributes.get("partOfSpeech")
            if part_of_speech is not None and part_of_speech not in _PARTS_OF_SPEECH:
                raise OewnParseError("unsupported_part_of_speech")
            form = _FormDraft(
                written_form=attributes["writtenForm"],
                part_of_speech=part_of_speech,
                script=attributes.get("script"),
                tags=attributes.get("tags"),
            )
            _charge_payload(
                form,
                _payload_upper_bound(
                    form.written_form,
                    form.part_of_speech,
                    form.script,
                    form.tags,
                ),
                self._limits,
            )
            return form
        if tag == "Sense":
            adjective_position = attributes.get("adjposition")
            if adjective_position not in {None, "a", "p", "ip"}:
                raise OewnParseError("unsupported_adjective_position")
            sense = _SenseDraft(
                sense_id=_identifier(attributes["id"], "sense.id", self._limits),
                synset_id=_identifier(
                    attributes["synset"], "sense.synset", self._limits
                ),
                adjective_position=adjective_position,
            )
            _charge_payload(
                sense,
                _payload_upper_bound(
                    sense.sense_id,
                    sense.synset_id,
                    sense.adjective_position,
                ),
                self._limits,
            )
            return sense
        if tag in {"SenseRelation", "SynsetRelation"}:
            self._runtime.relations += 1
            if self._runtime.relations > self._limits.max_relations:
                raise OewnParseError("relation_limit_exceeded")
            return _RelationDraft(
                relation_kind=(
                    "sense_relation" if tag == "SenseRelation" else "synset_relation"
                ),
                target=_identifier(attributes["target"], f"{tag}.target", self._limits),
                relation_type=_token(
                    attributes["relType"], f"{tag}.relType", self._limits
                ),
                attributes=_metadata_attributes(
                    attributes,
                    excluded={"target", "relType"},
                ),
            )
        if tag == "SyntacticBehaviour":
            senses = _identifier_list(
                attributes["senses"], "SyntacticBehaviour.senses", self._limits
            )
            return _BehaviorDraft(attributes["subcategorizationFrame"], senses)
        if tag == "Synset":
            part_of_speech = attributes["partOfSpeech"]
            if part_of_speech not in _PARTS_OF_SPEECH:
                raise OewnParseError("unsupported_part_of_speech")
            members = _identifier_list(
                attributes["members"], "Synset.members", self._limits
            )
            synset = _SynsetDraft(
                synset_id=_identifier(attributes["id"], "synset.id", self._limits),
                ili=attributes.get("ili"),
                part_of_speech=part_of_speech,
                lexfile=attributes.get("lexfile"),
                members=members,
            )
            _charge_payload(
                synset,
                _payload_upper_bound(
                    synset.synset_id,
                    synset.ili,
                    synset.part_of_speech,
                    synset.lexfile,
                    *synset.members,
                ),
                self._limits,
            )
            return synset
        return None

    def _character_data(self, value: str) -> None:
        self._runtime.xml_event(self._phase)
        self._total_text_chars += len(value)
        if self._total_text_chars > self._limits.max_total_text_chars:
            raise OewnParseError("xml_total_text_chars_limit_exceeded")
        if not self._stack:
            if value.strip():
                raise OewnParseError("text_outside_root")
            return
        frame = self._stack[-1]
        if frame.tag not in _TEXT_TAGS:
            if value.strip():
                raise OewnParseError(f"unexpected_element_text:{frame.tag}")
            return
        frame.text_chars += len(value)
        if frame.text_chars > self._limits.max_text_chars_per_element:
            raise OewnParseError("xml_element_text_limit_exceeded")
        frame.text_parts.append(value)

    def _end_element(self, expanded_name: str) -> None:
        self._runtime.xml_event(self._phase)
        if not self._stack or self._stack[-1].tag != expanded_name:
            raise OewnParseError("xml_element_stack_mismatch")
        frame = self._stack.pop()
        parent = self._stack[-1] if self._stack else None
        self._finish_frame(frame, parent)
        if expanded_name == "LexicalResource":
            self._root_closed = True

    def _finish_frame(self, frame: _Frame, parent: _Frame | None) -> None:
        tag = frame.tag
        if tag == "GlobalInformation":
            if self._global_label is not None:
                raise OewnParseError("duplicate_global_information")
            self._global_label = frame.attributes["label"]
            return
        if tag == "Lexicon":
            self._require_child_count(frame, "LexicalEntry", minimum=1)
            self._require_child_count(frame, "Synset", minimum=1)
            header = _payload(frame, _LexiconHeader)
            if len(self._lexicons) >= self._limits.max_lexicons:
                raise OewnParseError("lexicon_limit_exceeded")
            self._lexicons.append(header)
            return
        if tag == "LexicalResource":
            self._require_child_count(frame, "GlobalInformation", exact=1)
            self._require_child_count(frame, "Lexicon", exact=1)
            return
        if parent is None:
            raise OewnParseError("orphan_gwa_lmf_element")
        if tag == "Lemma":
            entry = _payload(parent, _EntryDraft)
            if entry.lemma is not None:
                raise OewnParseError("duplicate_lemma")
            lemma = _payload(frame, _FormDraft)
            _charge_payload(entry, lemma.payload_upper_bytes, self._limits)
            entry.lemma = lemma
            return
        if tag == "Form":
            entry = _payload(parent, _EntryDraft)
            form = _payload(frame, _FormDraft)
            _charge_payload(entry, form.payload_upper_bytes, self._limits)
            _bounded_append(
                entry.forms,
                form,
                self._limits,
                "forms_per_entry_limit_exceeded",
            )
            return
        if tag == "Pronunciation":
            form = _payload(parent, _FormDraft)
            pronunciation = self._text(frame)
            _charge_payload(
                form,
                _text_payload_upper_bound(pronunciation),
                self._limits,
            )
            _bounded_append(
                form.pronunciations,
                pronunciation,
                self._limits,
                "pronunciations_per_form_limit_exceeded",
            )
            return
        if tag == "SenseRelation":
            sense = _payload(parent, _SenseDraft)
            if len(sense.relations) >= self._limits.max_relations_per_unit:
                raise OewnParseError("relations_per_unit_limit_exceeded")
            relation = _payload(frame, _RelationDraft)
            _charge_payload(
                sense,
                _relation_payload_upper_bound(relation),
                self._limits,
            )
            _bounded_append(
                sense.relations,
                relation,
                self._limits,
                "relation_value_limit_exceeded",
            )
            return
        if tag == "Sense":
            entry = _payload(parent, _EntryDraft)
            if len(entry.senses) >= self._limits.max_references_per_unit:
                raise OewnParseError("senses_per_entry_limit_exceeded")
            sense = _payload(frame, _SenseDraft)
            _charge_payload(
                entry,
                _payload_upper_bound(sense.sense_id, overhead=512),
                self._limits,
            )
            _bounded_append(
                entry.senses,
                sense,
                self._limits,
                "sense_value_limit_exceeded",
            )
            return
        if tag == "SyntacticBehaviour":
            entry = _payload(parent, _EntryDraft)
            if len(entry.behaviors) >= self._limits.max_references_per_unit:
                raise OewnParseError("behaviors_per_entry_limit_exceeded")
            behavior = _payload(frame, _BehaviorDraft)
            _charge_payload(
                entry,
                _behavior_payload_upper_bound(behavior),
                self._limits,
            )
            _bounded_append(
                entry.behaviors,
                behavior,
                self._limits,
                "behavior_value_limit_exceeded",
            )
            return
        if tag == "LexicalEntry":
            self._require_child_count(frame, "Lemma", exact=1)
            self._require_child_count(frame, "Sense", minimum=1)
            header = self._current_lexicon_header()
            entry = _payload(frame, _EntryDraft)
            self._runtime.units += 1 + len(entry.senses)
            if self._runtime.units > self._limits.max_units:
                raise OewnParseError("unit_limit_exceeded")
            self._entry_consumer(header, entry)
            return
        if tag in {"Definition", "ILIDefinition", "Example"}:
            text = self._text(frame)
            if parent.tag == "Sense":
                sense = _payload(parent, _SenseDraft)
                _charge_payload(
                    sense,
                    _text_payload_upper_bound(text),
                    self._limits,
                )
                _bounded_append(
                    sense.examples,
                    text,
                    self._limits,
                    "examples_per_sense_limit_exceeded",
                )
                return
            synset = _payload(parent, _SynsetDraft)
            _charge_payload(
                synset,
                _text_payload_upper_bound(text),
                self._limits,
            )
            if tag == "Definition":
                _bounded_append(
                    synset.definitions,
                    text,
                    self._limits,
                    "definitions_per_synset_limit_exceeded",
                )
            elif tag == "ILIDefinition":
                _bounded_append(
                    synset.ili_definitions,
                    text,
                    self._limits,
                    "ili_definitions_per_synset_limit_exceeded",
                )
            else:
                _bounded_append(
                    synset.examples,
                    text,
                    self._limits,
                    "examples_per_synset_limit_exceeded",
                )
            return
        if tag == "SynsetRelation":
            synset = _payload(parent, _SynsetDraft)
            if len(synset.relations) >= self._limits.max_relations_per_unit:
                raise OewnParseError("relations_per_unit_limit_exceeded")
            relation = _payload(frame, _RelationDraft)
            _charge_payload(
                synset,
                _relation_payload_upper_bound(relation),
                self._limits,
            )
            _bounded_append(
                synset.relations,
                relation,
                self._limits,
                "relation_value_limit_exceeded",
            )
            return
        if tag == "Synset":
            header = self._current_lexicon_header()
            self._runtime.units += 1
            if self._runtime.units > self._limits.max_units:
                raise OewnParseError("unit_limit_exceeded")
            self._synset_consumer(header, _payload(frame, _SynsetDraft))

    def _current_lexicon_header(self) -> _LexiconHeader:
        for frame in reversed(self._stack):
            if frame.tag == "Lexicon":
                return _payload(frame, _LexiconHeader)
        raise OewnParseError("record_outside_lexicon")

    def _text(self, frame: _Frame) -> _TextDraft:
        value = " ".join("".join(frame.text_parts).split())
        if not value:
            raise OewnParseError(f"empty_text_element:{frame.tag}")
        _bounded_scalar(
            value,
            f"{frame.tag}.text",
            self._limits,
            maximum=self._limits.max_text_chars_per_element,
        )
        return _TextDraft(
            value=value,
            language=frame.attributes.get(_XML_LANGUAGE),
            source=frame.attributes.get(_DC_SOURCE),
            attributes=_metadata_attributes(
                frame.attributes,
                excluded={_XML_LANGUAGE, _DC_SOURCE},
            ),
        )

    @staticmethod
    def _require_child_count(
        frame: _Frame,
        child: str,
        *,
        exact: int | None = None,
        minimum: int | None = None,
    ) -> None:
        count = frame.child_counts.get(child, 0)
        if exact is not None and count != exact:
            raise OewnParseError(f"child_cardinality_mismatch:{frame.tag}:{child}")
        if minimum is not None and count < minimum:
            raise OewnParseError(f"child_cardinality_mismatch:{frame.tag}:{child}")

    def _forbidden_declaration(self, *_args: object) -> None:
        raise OewnParseError("xml_dtd_or_entity_forbidden")

    def _external_entity(self, *_args: object) -> int:
        raise OewnParseError("xml_external_entity_forbidden")

    def _processing_instruction(self, *_args: object) -> None:
        raise OewnParseError("xml_processing_instruction_forbidden")


def _payload(frame: _Frame, expected_type: type[Any]) -> Any:
    if not isinstance(frame.payload, expected_type):
        raise OewnParseError(f"internal_payload_shape_mismatch:{frame.tag}")
    return frame.payload


def _identifier_list(
    value: str,
    field_name: str,
    limits: OewnParserLimits,
) -> tuple[str, ...]:
    pieces = value.split(" ")
    if not pieces or any(not piece for piece in pieces):
        raise OewnParseError(f"invalid_identifier_list:{field_name}")
    if len(pieces) > limits.max_references_per_unit:
        raise OewnParseError(f"identifier_list_limit_exceeded:{field_name}")
    result = tuple(_identifier(piece, field_name, limits) for piece in pieces)
    if len(set(result)) != len(result):
        raise OewnParseError(f"duplicate_identifier_reference:{field_name}")
    return result


def _metadata_attributes(
    attributes: Mapping[str, str],
    *,
    excluded: set[str],
) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (_canonical_attribute_name(name), value)
            for name, value in attributes.items()
            if name not in excluded
        )
    )


def _canonical_attribute_name(name: str) -> str:
    if name.startswith(f"{DC_NAMESPACE}}}"):
        return "dc:" + name.rsplit("}", 1)[1]
    if name.startswith(f"{XML_NAMESPACE}}}"):
        return "xml:" + name.rsplit("}", 1)[1]
    if name.startswith(f"{XSI_NAMESPACE}}}"):
        return "xsi:" + name.rsplit("}", 1)[1]
    return name


@dataclass(slots=True)
class _AuthorityIndex:
    limits: OewnParserLimits
    stable_by_identity: dict[tuple[str, str], str] = field(default_factory=dict)
    identity_by_stable: dict[str, tuple[str, str]] = field(default_factory=dict)
    raw_id_kind: dict[str, str] = field(default_factory=dict)
    entry_ids: set[str] = field(default_factory=set)
    sense_ids: set[str] = field(default_factory=set)
    synset_ids: set[str] = field(default_factory=set)
    sense_owner: dict[str, str] = field(default_factory=dict)
    sense_synset: dict[str, str] = field(default_factory=dict)
    sense_part_of_speech: dict[str, str] = field(default_factory=dict)
    synset_senses: dict[str, list[str]] = field(default_factory=dict)
    synset_part_of_speech: dict[str, str] = field(default_factory=dict)
    index_bytes: int = 0

    def register(self, kind: str, raw_id: str) -> str:
        if raw_id in self.raw_id_kind:
            raise OewnParseError(f"duplicate_global_xml_id:{raw_id}")
        stable_id = _stable_id_for(kind, raw_id)
        identity = (kind, raw_id)
        collision = self.identity_by_stable.get(stable_id)
        if collision is not None and collision != identity:
            raise OewnParseError("stable_id_collision")
        self.raw_id_kind[raw_id] = kind
        self.stable_by_identity[identity] = stable_id
        self.identity_by_stable[stable_id] = identity
        target_set = {
            "lexical_entry": self.entry_ids,
            "sense": self.sense_ids,
            "synset": self.synset_ids,
        }.get(kind)
        if target_set is None:
            raise OewnParseError("unknown_index_unit_kind")
        target_set.add(raw_id)
        self.index_bytes += (
            len(kind.encode("utf-8"))
            + len(raw_id.encode("utf-8"))
            + len(stable_id.encode("ascii"))
            + 128
        )
        if self.index_bytes > self.limits.max_index_bytes:
            raise OewnParseError("identifier_index_limit_exceeded")
        return stable_id

    def stable(self, kind: str, raw_id: str) -> str:
        try:
            return self.stable_by_identity[(kind, raw_id)]
        except KeyError as exc:
            raise OewnParseError(f"missing_{kind}_reference:{raw_id}") from exc


def _index_entry(
    index: _AuthorityIndex,
    _header: _LexiconHeader,
    entry: _EntryDraft,
) -> None:
    if entry.lemma is None:
        raise OewnParseError("entry_lemma_missing")
    part_of_speech = entry.lemma.part_of_speech
    if part_of_speech is None:
        raise OewnParseError("lemma_part_of_speech_missing")
    index.register("lexical_entry", entry.entry_id)
    for sense in entry.senses:
        index.register("sense", sense.sense_id)
        index.sense_owner[sense.sense_id] = entry.entry_id
        index.sense_synset[sense.sense_id] = sense.synset_id
        index.sense_part_of_speech[sense.sense_id] = part_of_speech
        index.synset_senses.setdefault(sense.synset_id, []).append(sense.sense_id)
        index.index_bytes += 32
        if index.index_bytes > index.limits.max_index_bytes:
            raise OewnParseError("identifier_index_limit_exceeded")


def _index_synset(
    index: _AuthorityIndex,
    _header: _LexiconHeader,
    synset: _SynsetDraft,
) -> None:
    index.register("synset", synset.synset_id)
    index.synset_part_of_speech[synset.synset_id] = synset.part_of_speech


def _reference(index: _AuthorityIndex, kind: str, raw_id: str) -> OewnReference:
    return OewnReference(
        target_kind=kind,
        target_record_id=raw_id,
        target_stable_id=index.stable(kind, raw_id),
    )


def _text_value(value: _TextDraft) -> OewnText:
    return OewnText(
        value=value.value,
        language=value.language,
        source=value.source,
        attributes=value.attributes,
    )


def _form_value(value: _FormDraft) -> OewnForm:
    return OewnForm(
        written_form=value.written_form,
        part_of_speech=value.part_of_speech,
        script=value.script,
        tags=value.tags,
        pronunciations=tuple(_text_value(item) for item in value.pronunciations),
    )


def _relations(
    *,
    index: _AuthorityIndex,
    source_kind: str,
    source_id: str,
    target_kind: str,
    drafts: list[_RelationDraft],
) -> tuple[OewnRelation, ...]:
    source_stable = index.stable(source_kind, source_id)
    result: list[OewnRelation] = []
    stable_ids: set[str] = set()
    for ordinal, draft in enumerate(drafts):
        target_stable = index.stable(target_kind, draft.target)
        stable_id = "oewn-relation-sha256:" + _stable_digest(
            {
                "attributes": [list(item) for item in draft.attributes],
                "occurrence": ordinal,
                "partition_effect": DEPENDENCY_ONLY_PARTITION_EFFECT,
                "relation_kind": draft.relation_kind,
                "relation_type": draft.relation_type,
                "schema": OEWN_UNIT_SCHEMA,
                "source_id": OEWN_SOURCE_ID,
                "source_record_id": source_id,
                "source_stable_id": source_stable,
                "target_record_id": draft.target,
                "target_stable_id": target_stable,
            }
        )
        if stable_id in stable_ids:
            raise OewnParseError("relation_stable_id_collision")
        stable_ids.add(stable_id)
        result.append(
            OewnRelation(
                stable_id=stable_id,
                relation_kind=draft.relation_kind,
                source_record_id=source_id,
                source_stable_id=source_stable,
                target_record_id=draft.target,
                target_stable_id=target_stable,
                relation_type=draft.relation_type,
                attributes=draft.attributes,
                occurrence=ordinal,
            )
        )
    return tuple(result)


def _entry_units(
    *,
    identity: OewnSourceIdentity,
    index: _AuthorityIndex,
    header: _LexiconHeader,
    entry: _EntryDraft,
) -> tuple[OewnUnit, ...]:
    if entry.entry_id not in index.entry_ids or entry.lemma is None:
        raise OewnParseError("second_pass_entry_identity_mismatch")
    part_of_speech = entry.lemma.part_of_speech
    if part_of_speech is None:
        raise OewnParseError("lemma_part_of_speech_missing")
    sense_ids = tuple(sense.sense_id for sense in entry.senses)
    if len(set(sense_ids)) != len(sense_ids):
        raise OewnParseError("duplicate_sense_within_entry")
    for behavior in entry.behaviors:
        if not set(behavior.senses).issubset(sense_ids):
            raise OewnParseError("syntactic_behavior_cross_entry_sense")
    entry_unit = OewnLexicalEntryUnit(
        source_id=OEWN_SOURCE_ID,
        release_identity=identity.release_identity,
        lexicon_id=header.lexicon_id,
        language=header.language,
        source_record_id=entry.entry_id,
        stable_id=index.stable("lexical_entry", entry.entry_id),
        lemma=_form_value(entry.lemma),
        forms=tuple(_form_value(item) for item in entry.forms),
        senses=tuple(_reference(index, "sense", item) for item in sense_ids),
        syntactic_behaviors=tuple(
            OewnSyntacticBehavior(
                subcategorization_frame=behavior.frame,
                senses=tuple(
                    _reference(index, "sense", sense_id) for sense_id in behavior.senses
                ),
            )
            for behavior in entry.behaviors
        ),
    )
    units: list[OewnUnit] = [entry_unit]
    for sense in entry.senses:
        if sense.adjective_position is not None and part_of_speech not in {"a", "s"}:
            raise OewnParseError("adjective_position_on_nonadjective_sense")
        if index.sense_owner.get(sense.sense_id) != entry.entry_id:
            raise OewnParseError("second_pass_sense_owner_mismatch")
        if index.sense_synset.get(sense.sense_id) != sense.synset_id:
            raise OewnParseError("second_pass_sense_synset_mismatch")
        synset_part_of_speech = index.synset_part_of_speech.get(sense.synset_id)
        if synset_part_of_speech is None:
            raise OewnParseError(f"missing_synset_reference:{sense.synset_id}")
        if synset_part_of_speech != part_of_speech:
            raise OewnParseError("sense_synset_part_of_speech_mismatch")
        units.append(
            OewnSenseUnit(
                source_id=OEWN_SOURCE_ID,
                release_identity=identity.release_identity,
                lexicon_id=header.lexicon_id,
                language=header.language,
                source_record_id=sense.sense_id,
                stable_id=index.stable("sense", sense.sense_id),
                lexical_entry=_reference(index, "lexical_entry", entry.entry_id),
                synset=_reference(index, "synset", sense.synset_id),
                relations=_relations(
                    index=index,
                    source_kind="sense",
                    source_id=sense.sense_id,
                    target_kind="sense",
                    drafts=sense.relations,
                ),
                examples=tuple(_text_value(item) for item in sense.examples),
                adjective_position=sense.adjective_position,
            )
        )
    return tuple(units)


def _synset_unit(
    *,
    identity: OewnSourceIdentity,
    index: _AuthorityIndex,
    header: _LexiconHeader,
    synset: _SynsetDraft,
) -> OewnSynsetUnit:
    if synset.synset_id not in index.synset_ids:
        raise OewnParseError("second_pass_synset_identity_mismatch")
    if index.synset_part_of_speech.get(synset.synset_id) != synset.part_of_speech:
        raise OewnParseError("second_pass_synset_part_of_speech_mismatch")
    for member in synset.members:
        if member not in index.sense_ids:
            raise OewnParseError(f"missing_sense_reference:{member}")
        if index.sense_synset.get(member) != synset.synset_id:
            raise OewnParseError("synset_member_points_to_other_synset")
        if index.sense_part_of_speech.get(member) != synset.part_of_speech:
            raise OewnParseError("synset_member_part_of_speech_mismatch")
    expected_members = set(index.synset_senses.get(synset.synset_id, ()))
    if set(synset.members) != expected_members:
        raise OewnParseError("synset_members_not_exhaustive")
    return OewnSynsetUnit(
        source_id=OEWN_SOURCE_ID,
        release_identity=identity.release_identity,
        lexicon_id=header.lexicon_id,
        language=header.language,
        source_record_id=synset.synset_id,
        stable_id=index.stable("synset", synset.synset_id),
        ili=synset.ili,
        part_of_speech=synset.part_of_speech,
        lexfile=synset.lexfile,
        members=tuple(_reference(index, "sense", item) for item in synset.members),
        definitions=tuple(_text_value(item) for item in synset.definitions),
        ili_definitions=tuple(_text_value(item) for item in synset.ili_definitions),
        examples=tuple(_text_value(item) for item in synset.examples),
        relations=_relations(
            index=index,
            source_kind="synset",
            source_id=synset.synset_id,
            target_kind="synset",
            drafts=synset.relations,
        ),
    )


class _BoundedMemorySpool(BytesIO):
    """BytesIO which rejects growth before crossing its explicit ceiling."""

    def __init__(self, maximum_bytes: int) -> None:
        super().__init__()
        self._maximum_bytes = maximum_bytes

    def write(self, value: bytes, /) -> int:
        end = self.tell() + len(value)
        if end > self._maximum_bytes:
            raise OewnParseError("default_memory_spool_limit_exceeded")
        return super().write(value)


def _new_spool(
    factory: BoundedSpoolFactory | None,
    purpose: str,
    limits: OewnParserLimits,
    *,
    forbidden: tuple[BinaryIO, ...] = (),
) -> BinaryIO:
    try:
        spool = (
            _BoundedMemorySpool(
                min(limits.max_default_in_memory_spool_bytes, limits.max_spool_bytes)
            )
            if factory is None
            else factory(purpose, limits.max_spool_bytes)
        )
    except Exception as exc:
        raise OewnParseError(f"spool_factory_failed:{purpose}") from exc
    if any(spool is existing for existing in forbidden):
        raise OewnParseError("spool_alias_forbidden")
    required_methods = ("read", "write", "seek", "tell", "truncate", "close")
    if spool is None or any(
        not callable(getattr(spool, name, None)) for name in required_methods
    ):
        raise OewnParseError(f"invalid_binary_spool:{purpose}")
    try:
        if hasattr(spool, "seekable") and not spool.seekable():
            raise OewnParseError(f"spool_not_seekable:{purpose}")
        if hasattr(spool, "readable") and not spool.readable():
            raise OewnParseError(f"spool_not_readable:{purpose}")
        if hasattr(spool, "writable") and not spool.writable():
            raise OewnParseError(f"spool_not_writable:{purpose}")
        spool.seek(0)
        spool.truncate(0)
    except OewnParseError:
        spool.close()
        raise
    except (OSError, ValueError) as exc:
        spool.close()
        raise OewnParseError(f"spool_initialization_failed:{purpose}") from exc
    return spool


def _write_all(
    spool: BinaryIO,
    value: bytes,
    error_code: str,
    runtime: _Runtime,
    phase: str,
) -> None:
    offset = 0
    try:
        while offset < len(value):
            written = spool.write(value[offset:])
            if (
                isinstance(written, bool)
                or not isinstance(written, int)
                or written <= 0
                or written > len(value) - offset
            ):
                raise OewnParseError(error_code)
            offset += written
            runtime.checkpoint(phase)
    except OewnParseError:
        raise
    except (OSError, ValueError) as exc:
        raise OewnParseError(error_code) from exc


def _decompress_to_spool(
    *,
    identity: OewnSourceIdentity,
    opener: BinaryOpener,
    spool: BinaryIO,
    runtime: _Runtime,
) -> tuple[str, int]:
    limits = runtime.limits
    compressed_digest = hashlib.sha256()
    uncompressed_digest = hashlib.sha256()
    decompressor = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
    stream_ended = False
    try:
        manager = opener()
    except Exception as exc:
        raise OewnParseError("compressed_source_open_failed") from exc
    if not hasattr(manager, "__enter__") or not hasattr(manager, "__exit__"):
        raise OewnParseError("binary_opener_must_return_context_manager")
    try:
        with manager as source:
            if not callable(getattr(source, "read", None)):
                raise OewnParseError("binary_opener_returned_non_reader")
            while True:
                runtime.checkpoint("gzip_decompression")
                chunk = source.read(limits.compressed_read_chunk_bytes)
                if not chunk:
                    break
                if not isinstance(chunk, bytes):
                    raise OewnParseError("compressed_source_not_binary")
                if len(chunk) > limits.compressed_read_chunk_bytes:
                    raise OewnParseError("compressed_reader_oversized_chunk")
                if stream_ended:
                    raise OewnParseError("gzip_trailing_data_forbidden")
                runtime.compressed_bytes += len(chunk)
                if runtime.compressed_bytes > limits.max_compressed_bytes:
                    raise OewnParseError("compressed_byte_limit_exceeded")
                compressed_digest.update(chunk)
                _decompress_chunk_bounded(
                    compressed=chunk,
                    decompressor=decompressor,
                    spool=spool,
                    digest=uncompressed_digest,
                    runtime=runtime,
                )
                stream_ended = decompressor.eof
    except OewnParseError:
        raise
    except Exception as exc:
        raise OewnParseError("compressed_source_read_failed") from exc
    if not decompressor.eof:
        raise OewnParseError("truncated_gzip_stream")
    try:
        tail = decompressor.flush()
    except zlib.error as exc:
        raise OewnParseError("gzip_flush_failed") from exc
    _accept_uncompressed(tail, spool, uncompressed_digest, runtime)
    _check_ratio(runtime, final=True)
    observed_compressed = "sha256:" + compressed_digest.hexdigest()
    if runtime.compressed_bytes != identity.compressed_bytes:
        raise OewnParseError("compressed_byte_identity_mismatch")
    if observed_compressed != identity.compressed_sha256:
        raise OewnParseError("compressed_sha256_identity_mismatch")
    if runtime.uncompressed_bytes == 0:
        raise OewnParseError("empty_uncompressed_xml")
    runtime.checkpoint("gzip_decompression", force=True)
    return "sha256:" + uncompressed_digest.hexdigest(), runtime.uncompressed_bytes


def _decompress_chunk_bounded(
    *,
    compressed: bytes,
    decompressor: Any,
    spool: BinaryIO,
    digest: Any,
    runtime: _Runtime,
) -> None:
    pending = compressed
    while pending:
        runtime.checkpoint("gzip_decompression")
        if decompressor.eof:
            raise OewnParseError("gzip_trailing_data_forbidden")
        before = len(pending)
        maximum_output = _next_decompression_output_bound(runtime)
        try:
            output = decompressor.decompress(pending, maximum_output)
        except zlib.error as exc:
            raise OewnParseError("invalid_gzip_stream") from exc
        pending = decompressor.unconsumed_tail
        if decompressor.unused_data:
            raise OewnParseError("gzip_trailing_data_forbidden")
        _accept_uncompressed(output, spool, digest, runtime)
        if pending and len(pending) >= before and not output:
            raise OewnParseError("gzip_decompression_stalled")


def _next_decompression_output_bound(runtime: _Runtime) -> int:
    limits = runtime.limits
    hard_remaining = min(
        limits.max_uncompressed_bytes - runtime.uncompressed_bytes,
        limits.max_spool_bytes - runtime.uncompressed_bytes,
    )
    ratio_denominator = max(
        runtime.compressed_bytes,
        limits.compression_ratio_grace_bytes,
    )
    ratio_ceiling = math.floor(limits.max_compression_ratio * ratio_denominator)
    ratio_remaining = ratio_ceiling - runtime.uncompressed_bytes
    return max(
        1,
        min(
            limits.decompressed_output_chunk_bytes,
            hard_remaining + 1,
            ratio_remaining + 1,
        ),
    )


def _accept_uncompressed(
    value: bytes,
    spool: BinaryIO,
    digest: Any,
    runtime: _Runtime,
) -> None:
    if not value:
        return
    runtime.uncompressed_bytes += len(value)
    runtime.spool_bytes = runtime.uncompressed_bytes
    if runtime.uncompressed_bytes > runtime.limits.max_uncompressed_bytes:
        raise OewnParseError("uncompressed_byte_limit_exceeded")
    if runtime.uncompressed_bytes > runtime.limits.max_spool_bytes:
        raise OewnParseError("xml_spool_byte_limit_exceeded")
    _check_ratio(runtime, final=False)
    digest.update(value)
    _write_all(
        spool,
        value,
        "xml_spool_write_failed",
        runtime,
        "xml_spool_write",
    )


def _check_ratio(runtime: _Runtime, *, final: bool) -> None:
    denominator = runtime.compressed_bytes
    if not final:
        denominator = max(
            denominator,
            runtime.limits.compression_ratio_grace_bytes,
        )
    if denominator <= 0:
        raise OewnParseError("invalid_compression_ratio_denominator")
    ratio = runtime.uncompressed_bytes / denominator
    if ratio > runtime.limits.max_compression_ratio:
        raise OewnParseError("compression_ratio_limit_exceeded")


def _spool_sha256(
    spool: BinaryIO,
    limits: OewnParserLimits,
    runtime: _Runtime,
    phase: str,
) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    try:
        spool.seek(0)
        while True:
            chunk = spool.read(limits.xml_read_chunk_bytes)
            if not chunk:
                break
            if not isinstance(chunk, bytes):
                raise OewnParseError("spool_not_binary")
            if len(chunk) > limits.xml_read_chunk_bytes:
                raise OewnParseError("spool_oversized_read")
            total += len(chunk)
            if total > limits.max_spool_bytes:
                raise OewnParseError("spool_byte_limit_exceeded")
            digest.update(chunk)
            runtime.checkpoint(phase)
    except OewnParseError:
        raise
    except (OSError, ValueError) as exc:
        raise OewnParseError("spool_hash_failed") from exc
    return "sha256:" + digest.hexdigest(), total


@dataclass(slots=True)
class _XmlMarkupBoundScanner:
    maximum_bytes: int
    maximum_reference_bytes: int
    mode: str | None = None
    length: int = 0
    prefix: bytearray = field(default_factory=bytearray)
    quote: int | None = None
    tail: bytearray = field(default_factory=bytearray)

    def feed(self, value: bytes) -> None:
        cursor = 0
        while cursor < len(value):
            if self.mode is None:
                markup_position = value.find(b"<", cursor)
                reference_position = value.find(b"&", cursor)
                positions = [
                    position
                    for position in (markup_position, reference_position)
                    if position >= 0
                ]
                if not positions:
                    return
                position = min(positions)
                if position == reference_position:
                    self.mode = "reference"
                    self.length = 1
                    cursor = position + 1
                    continue
                self.mode = "undetermined"
                self.length = 1
                self.prefix = bytearray(b"<")
                self.quote = None
                self.tail.clear()
                cursor = position + 1
                continue
            byte = value[cursor]
            cursor += 1
            self.length += 1
            if self.length > self.maximum_bytes:
                raise OewnParseError("xml_markup_byte_limit_exceeded")
            if self.mode == "undetermined":
                self._consume_undetermined(byte)
            elif self.mode == "normal":
                self._consume_normal(byte)
            elif self.mode == "comment":
                self._consume_delimited(byte, b"-->")
            elif self.mode == "cdata":
                self._consume_delimited(byte, b"]]>")
            elif self.mode == "processing_instruction":
                self._consume_delimited(byte, b"?>")
            elif self.mode == "reference":
                self._consume_reference(byte)
            else:
                raise OewnParseError("internal_xml_markup_scanner_state")

    def finish(self) -> None:
        if self.mode is not None:
            raise OewnParseError("unterminated_xml_markup")

    def _consume_undetermined(self, byte: int) -> None:
        self.prefix.append(byte)
        prefix = bytes(self.prefix)
        candidates = (b"<!--", b"<![CDATA[", b"<?")
        if prefix == b"<!--":
            self.mode = "comment"
            self.tail = bytearray(prefix[-3:])
            return
        if prefix == b"<![CDATA[":
            self.mode = "cdata"
            self.tail = bytearray(prefix[-3:])
            return
        if prefix == b"<?":
            self.mode = "processing_instruction"
            self.tail = bytearray(prefix[-2:])
            return
        if any(candidate.startswith(prefix) for candidate in candidates):
            return
        self.mode = "normal"
        for prefix_byte in self.prefix[1:]:
            self._consume_normal(prefix_byte)
            if self.mode is None:
                break
        self.prefix.clear()

    def _consume_normal(self, byte: int) -> None:
        if self.quote is not None:
            if byte == self.quote:
                self.quote = None
            return
        if byte in {ord('"'), ord("'")}:
            self.quote = byte
        elif byte == ord(">"):
            self._reset()

    def _consume_delimited(self, byte: int, delimiter: bytes) -> None:
        self.tail.append(byte)
        if len(self.tail) > len(delimiter):
            del self.tail[0]
        if bytes(self.tail) == delimiter:
            self._reset()

    def _consume_reference(self, byte: int) -> None:
        if self.length > self.maximum_reference_bytes:
            raise OewnParseError("xml_reference_byte_limit_exceeded")
        if byte == ord(";"):
            self._reset()
        elif byte == ord("<"):
            raise OewnParseError("unterminated_xml_reference")

    def _reset(self) -> None:
        self.mode = None
        self.length = 0
        self.prefix.clear()
        self.quote = None
        self.tail.clear()


def _reject_forbidden_xml_declarations(
    spool: BinaryIO,
    limits: OewnParserLimits,
    runtime: _Runtime,
) -> None:
    overlap = b""
    markup_scanner = _XmlMarkupBoundScanner(
        limits.max_xml_markup_bytes,
        limits.max_xml_reference_bytes,
    )
    try:
        spool.seek(0)
        while True:
            chunk = spool.read(limits.xml_read_chunk_bytes)
            if not chunk:
                break
            if len(chunk) > limits.xml_read_chunk_bytes:
                raise OewnParseError("xml_spool_oversized_read")
            window = overlap + chunk
            if _FORBIDDEN_DECLARATION_RE.search(window):
                raise OewnParseError("xml_dtd_or_entity_forbidden")
            markup_scanner.feed(chunk)
            overlap = window[-64:]
            runtime.checkpoint("xml_security_scan")
        markup_scanner.finish()
    except OewnParseError:
        raise
    except (OSError, ValueError) as exc:
        raise OewnParseError("xml_declaration_scan_failed") from exc


def _verify_xml_spool(
    spool: BinaryIO,
    expected_sha256: str,
    expected_bytes: int,
    limits: OewnParserLimits,
    runtime: _Runtime,
) -> None:
    observed_sha256, observed_bytes = _spool_sha256(
        spool,
        limits,
        runtime,
        "xml_spool_rehash",
    )
    if observed_bytes != expected_bytes:
        raise OewnParseError("xml_spool_byte_identity_mismatch")
    if observed_sha256 != expected_sha256:
        raise OewnParseError("xml_spool_sha256_mismatch")


@dataclass(slots=True)
class _SecondPassState:
    identity: OewnSourceIdentity
    index: _AuthorityIndex
    stage: BinaryIO
    runtime: _Runtime
    records: list[_StagedRecord] = field(default_factory=list)
    seen_entries: set[str] = field(default_factory=set)
    seen_senses: set[str] = field(default_factory=set)
    seen_synsets: set[str] = field(default_factory=set)
    canonical_bytes: int = 0
    record_index_bytes: int = 0

    def consume_entry(self, header: _LexiconHeader, entry: _EntryDraft) -> None:
        if entry.entry_id in self.seen_entries:
            raise OewnParseError("duplicate_second_pass_entry")
        self.seen_entries.add(entry.entry_id)
        for unit in _entry_units(
            identity=self.identity,
            index=self.index,
            header=header,
            entry=entry,
        ):
            if isinstance(unit, OewnSenseUnit):
                if unit.source_record_id in self.seen_senses:
                    raise OewnParseError("duplicate_second_pass_sense")
                self.seen_senses.add(unit.source_record_id)
            self.stage_unit(unit)

    def consume_synset(self, header: _LexiconHeader, synset: _SynsetDraft) -> None:
        if synset.synset_id in self.seen_synsets:
            raise OewnParseError("duplicate_second_pass_synset")
        self.seen_synsets.add(synset.synset_id)
        self.stage_unit(
            _synset_unit(
                identity=self.identity,
                index=self.index,
                header=header,
                synset=synset,
            )
        )

    def stage_unit(self, unit: OewnUnit) -> None:
        line = _canonical_json(_unit_mapping(unit)) + b"\n"
        if len(line) - 1 > self.runtime.limits.max_canonical_unit_bytes:
            raise OewnParseError("canonical_unit_byte_limit_exceeded")
        self.canonical_bytes += len(line)
        if self.canonical_bytes > self.runtime.limits.max_canonical_bytes:
            raise OewnParseError("canonical_corpus_byte_limit_exceeded")
        if self.canonical_bytes > self.runtime.limits.max_spool_bytes:
            raise OewnParseError("canonical_stage_spool_limit_exceeded")
        try:
            offset = self.stage.tell()
        except (OSError, ValueError) as exc:
            raise OewnParseError("canonical_stage_tell_failed") from exc
        _write_all(
            self.stage,
            line,
            "canonical_stage_write_failed",
            self.runtime,
            "canonical_stage_write",
        )
        rank = {"lexical_entry": 0, "sense": 1, "synset": 2}[unit.unit_kind]
        record = _StagedRecord(
            sort_key=(rank, unit.source_record_id, unit.stable_id),
            offset=offset,
            length=len(line),
            sha256="sha256:" + hashlib.sha256(line).hexdigest(),
        )
        self.records.append(record)
        self.record_index_bytes += (
            len(unit.source_record_id.encode("utf-8"))
            + len(unit.stable_id.encode("ascii"))
            + 128
        )
        if self.record_index_bytes > self.runtime.limits.max_index_bytes:
            raise OewnParseError("canonical_record_index_limit_exceeded")
        self.runtime.spool_bytes = (
            self.runtime.uncompressed_bytes + self.canonical_bytes
        )

    def verify_complete(self) -> None:
        if self.seen_entries != self.index.entry_ids:
            raise OewnParseError("second_pass_entry_set_mismatch")
        if self.seen_senses != self.index.sense_ids:
            raise OewnParseError("second_pass_sense_set_mismatch")
        if self.seen_synsets != self.index.synset_ids:
            raise OewnParseError("second_pass_synset_set_mismatch")
        if len(self.records) != (
            len(self.index.entry_ids)
            + len(self.index.sense_ids)
            + len(self.index.synset_ids)
        ):
            raise OewnParseError("second_pass_unit_count_mismatch")


def _copy_canonical_records(
    *,
    state: _SecondPassState,
    destination: BinaryIO,
) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    records = sorted(state.records, key=lambda item: item.sort_key)
    if len({record.sort_key for record in records}) != len(records):
        raise OewnParseError("canonical_sort_key_collision")
    for record in records:
        try:
            state.stage.seek(record.offset)
            line = state.stage.read(record.length)
        except (OSError, ValueError) as exc:
            raise OewnParseError("canonical_stage_read_failed") from exc
        if not isinstance(line, bytes) or len(line) != record.length:
            raise OewnParseError("canonical_stage_record_truncated")
        if "sha256:" + hashlib.sha256(line).hexdigest() != record.sha256:
            raise OewnParseError("canonical_stage_record_sha256_mismatch")
        _write_all(
            destination,
            line,
            "canonical_spool_write_failed",
            state.runtime,
            "canonical_spool_write",
        )
        digest.update(line)
        total += len(line)
        if total > state.runtime.limits.max_canonical_bytes:
            raise OewnParseError("canonical_corpus_byte_limit_exceeded")
        if total > state.runtime.limits.max_spool_bytes:
            raise OewnParseError("canonical_spool_byte_limit_exceeded")
        state.runtime.checkpoint("canonical_sort_copy")
    state.runtime.spool_bytes = state.runtime.uncompressed_bytes + total
    state.runtime.checkpoint("canonical_sort_copy", force=True)
    return "sha256:" + digest.hexdigest(), total


def _lexicon_metadata(value: _LexiconHeader) -> OewnLexiconMetadata:
    return OewnLexiconMetadata(
        lexicon_id=value.lexicon_id,
        label=value.label,
        language=value.language,
        version=value.version,
        email=value.email,
        license=value.license,
        url=value.url,
        citation=value.citation,
        logo=value.logo,
    )


def _metadata_mapping(value: OewnCorpusMetadata) -> dict[str, Any]:
    return {
        "compressed_bytes": value.compressed_bytes,
        "compressed_sha256": value.compressed_sha256,
        "global_label": value.global_label,
        "lexical_entry_count": value.lexical_entry_count,
        "lexicons": [
            {
                "citation": item.citation,
                "email": item.email,
                "label": item.label,
                "language": item.language,
                "lexicon_id": item.lexicon_id,
                "license": item.license,
                "logo": item.logo,
                "url": item.url,
                "version": item.version,
            }
            for item in value.lexicons
        ],
        "partition": _partition_mapping(),
        "relation_count": value.relation_count,
        "release_identity": value.release_identity,
        "schema": value.schema,
        "sense_count": value.sense_count,
        "source_id": value.source_id,
        "synset_count": value.synset_count,
        "uncompressed_bytes": value.uncompressed_bytes,
        "uncompressed_sha256": value.uncompressed_sha256,
        "xml_schema_location": value.xml_schema_location,
    }


def parse_open_english_wordnet_2025(
    *,
    identity: OewnSourceIdentity,
    binary_opener: BinaryOpener,
    limits: OewnParserLimits = DEFAULT_LIMITS,
    clock: Clock = time.monotonic,
    checkpoint: CheckpointCallback | None = None,
    spool_factory: BoundedSpoolFactory | None = None,
) -> OewnParsedCorpus:
    """Parse one immutable OEWN 2025 gzip object into typed, bounded units.

    The caller owns source custody through ``binary_opener`` and may inject a
    private, bounded spool implementation.  The default is an in-memory
    :class:`io.BytesIO`; this module never creates a filesystem temporary file.
    The returned corpus owns its final spool and must be closed.
    """

    limits.validate()
    identity.validate(limits)
    if not callable(binary_opener):
        raise OewnParseError("binary_opener_not_callable")
    if not callable(clock):
        raise OewnParseError("clock_not_callable")
    if checkpoint is not None and not callable(checkpoint):
        raise OewnParseError("checkpoint_not_callable")
    if spool_factory is not None and not callable(spool_factory):
        raise OewnParseError("spool_factory_not_callable")

    runtime = _Runtime(limits=limits, clock=clock, callback=checkpoint)
    xml_spool = _new_spool(spool_factory, "oewn_xml", limits)
    stage_spool: BinaryIO | None = None
    canonical_spool: BinaryIO | None = None
    returned = False
    try:
        uncompressed_sha256, uncompressed_bytes = _decompress_to_spool(
            identity=identity,
            opener=binary_opener,
            spool=xml_spool,
            runtime=runtime,
        )
        _verify_xml_spool(
            xml_spool,
            uncompressed_sha256,
            uncompressed_bytes,
            limits,
            runtime,
        )
        _reject_forbidden_xml_declarations(xml_spool, limits, runtime)

        index = _AuthorityIndex(limits)
        runtime.units = 0
        runtime.relations = 0
        first_decoder = _GwaLmfDecoder(
            limits=limits,
            runtime=runtime,
            phase="xml_index_pass",
            entry_consumer=lambda header, entry: _index_entry(index, header, entry),
            synset_consumer=lambda header, synset: _index_synset(index, header, synset),
        )
        first_metadata = first_decoder.parse(xml_spool)
        if first_metadata[0] != identity.expected_schema_location:
            raise OewnParseError("xml_schema_location_identity_mismatch")
        first_unit_count = runtime.units
        first_relation_count = runtime.relations
        _verify_xml_spool(
            xml_spool,
            uncompressed_sha256,
            uncompressed_bytes,
            limits,
            runtime,
        )

        stage_spool = _new_spool(
            spool_factory,
            "oewn_units_stage",
            limits,
            forbidden=(xml_spool,),
        )
        state = _SecondPassState(
            identity=identity,
            index=index,
            stage=stage_spool,
            runtime=runtime,
        )
        runtime.units = 0
        runtime.relations = 0
        second_decoder = _GwaLmfDecoder(
            limits=limits,
            runtime=runtime,
            phase="xml_validation_pass",
            entry_consumer=state.consume_entry,
            synset_consumer=state.consume_synset,
        )
        second_metadata = second_decoder.parse(xml_spool)
        if second_metadata != first_metadata:
            raise OewnParseError("xml_metadata_changed_between_passes")
        if runtime.units != first_unit_count:
            raise OewnParseError("xml_unit_count_changed_between_passes")
        if runtime.relations != first_relation_count:
            raise OewnParseError("xml_relation_count_changed_between_passes")
        state.verify_complete()
        _verify_xml_spool(
            xml_spool,
            uncompressed_sha256,
            uncompressed_bytes,
            limits,
            runtime,
        )

        canonical_spool = _new_spool(
            spool_factory,
            "oewn_units_canonical",
            limits,
            forbidden=(xml_spool, stage_spool),
        )
        units_spool_sha256, canonical_bytes = _copy_canonical_records(
            state=state,
            destination=canonical_spool,
        )
        observed_spool_sha256, observed_canonical_bytes = _spool_sha256(
            canonical_spool,
            limits,
            runtime,
            "canonical_spool_postcopy_rehash",
        )
        if observed_spool_sha256 != units_spool_sha256:
            raise OewnParseError("canonical_spool_postcopy_sha256_mismatch")
        if observed_canonical_bytes != canonical_bytes:
            raise OewnParseError("canonical_spool_postcopy_byte_mismatch")

        schema_location, global_label, lexicon_headers = first_metadata
        metadata = OewnCorpusMetadata(
            schema=OEWN_CORPUS_SCHEMA,
            source_id=OEWN_SOURCE_ID,
            release_identity=identity.release_identity,
            compressed_sha256=identity.compressed_sha256,
            compressed_bytes=identity.compressed_bytes,
            uncompressed_sha256=uncompressed_sha256,
            uncompressed_bytes=uncompressed_bytes,
            xml_schema_location=schema_location,
            global_label=global_label,
            lexicons=tuple(_lexicon_metadata(item) for item in lexicon_headers),
            lexical_entry_count=len(index.entry_ids),
            sense_count=len(index.sense_ids),
            synset_count=len(index.synset_ids),
            relation_count=first_relation_count,
        )
        metadata_line = _canonical_json(_metadata_mapping(metadata)) + b"\n"
        root_digest = hashlib.sha256()
        root_digest.update(metadata_line)
        canonical_spool.seek(0)
        while True:
            chunk = canonical_spool.read(limits.xml_read_chunk_bytes)
            if not chunk:
                break
            if len(chunk) > limits.xml_read_chunk_bytes:
                raise OewnParseError("canonical_spool_oversized_read")
            root_digest.update(chunk)
            runtime.checkpoint("canonical_root_hash")
        result = OewnParsedCorpus(
            metadata=metadata,
            spool=canonical_spool,
            spool_sha256=units_spool_sha256,
            canonical_sha256="sha256:" + root_digest.hexdigest(),
            unit_count=len(state.records),
            spool_bytes=canonical_bytes,
            max_unit_bytes=limits.max_canonical_unit_bytes,
            runtime=runtime,
        )
        returned = True
        return result
    except OewnParseError:
        raise
    except Exception as exc:
        raise OewnParseError("unexpected_oewn_parser_failure") from exc
    finally:
        xml_spool.close()
        if stage_spool is not None and stage_spool is not xml_spool:
            stage_spool.close()
        if (
            canonical_spool is not None
            and not returned
            and canonical_spool is not xml_spool
            and canonical_spool is not stage_spool
        ):
            canonical_spool.close()


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise OewnParseError(f"canonical_{label}_keys_mismatch")


def _required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise OewnParseError(f"canonical_{label}_invalid")
    return value


def _optional_string(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _required_string(value, label)


def _partition_from_mapping(value: Any) -> DependencyOnlyPartitionMetadata:
    if value != {"partition_effect": DEPENDENCY_ONLY_PARTITION_EFFECT}:
        raise OewnParseError("canonical_partition_invalid")
    return DEPENDENCY_PARTITION


def _pairs_from_value(value: Any, label: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        raise OewnParseError(f"canonical_{label}_invalid")
    result: list[tuple[str, str]] = []
    for item in value:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not all(isinstance(piece, str) for piece in item)
        ):
            raise OewnParseError(f"canonical_{label}_invalid")
        result.append((item[0], item[1]))
    if result != sorted(result):
        raise OewnParseError(f"canonical_{label}_not_sorted")
    return tuple(result)


def _text_from_mapping(value: Any) -> OewnText:
    if not isinstance(value, dict):
        raise OewnParseError("canonical_text_invalid")
    _exact_keys(value, {"attributes", "language", "source", "value"}, "text")
    return OewnText(
        value=_required_string(value["value"], "text_value"),
        language=_optional_string(value["language"], "text_language"),
        source=_optional_string(value["source"], "text_source"),
        attributes=_pairs_from_value(value["attributes"], "text_attributes"),
    )


def _form_from_mapping(value: Any) -> OewnForm:
    if not isinstance(value, dict):
        raise OewnParseError("canonical_form_invalid")
    _exact_keys(
        value,
        {"part_of_speech", "pronunciations", "script", "tags", "written_form"},
        "form",
    )
    pronunciations = value["pronunciations"]
    if not isinstance(pronunciations, list):
        raise OewnParseError("canonical_pronunciations_invalid")
    return OewnForm(
        written_form=_required_string(value["written_form"], "written_form"),
        part_of_speech=_optional_string(value["part_of_speech"], "form_part_of_speech"),
        script=_optional_string(value["script"], "form_script"),
        tags=_optional_string(value["tags"], "form_tags"),
        pronunciations=tuple(_text_from_mapping(item) for item in pronunciations),
    )


def _reference_from_mapping(value: Any) -> OewnReference:
    if not isinstance(value, dict):
        raise OewnParseError("canonical_reference_invalid")
    _exact_keys(
        value,
        {"partition", "target_kind", "target_record_id", "target_stable_id"},
        "reference",
    )
    return OewnReference(
        target_kind=_required_string(value["target_kind"], "reference_target_kind"),
        target_record_id=_required_string(
            value["target_record_id"], "reference_target_record_id"
        ),
        target_stable_id=_required_string(
            value["target_stable_id"], "reference_target_stable_id"
        ),
        partition=_partition_from_mapping(value["partition"]),
    )


def _relation_from_mapping(value: Any) -> OewnRelation:
    if not isinstance(value, dict):
        raise OewnParseError("canonical_relation_invalid")
    _exact_keys(
        value,
        {
            "attributes",
            "occurrence",
            "partition",
            "relation_kind",
            "relation_type",
            "source_record_id",
            "source_stable_id",
            "stable_id",
            "target_record_id",
            "target_stable_id",
        },
        "relation",
    )
    occurrence = value["occurrence"]
    if (
        isinstance(occurrence, bool)
        or not isinstance(occurrence, int)
        or occurrence < 0
    ):
        raise OewnParseError("canonical_relation_occurrence_invalid")
    return OewnRelation(
        stable_id=_required_string(value["stable_id"], "relation_stable_id"),
        relation_kind=_required_string(value["relation_kind"], "relation_kind"),
        source_record_id=_required_string(
            value["source_record_id"], "relation_source_record_id"
        ),
        source_stable_id=_required_string(
            value["source_stable_id"], "relation_source_stable_id"
        ),
        target_record_id=_required_string(
            value["target_record_id"], "relation_target_record_id"
        ),
        target_stable_id=_required_string(
            value["target_stable_id"], "relation_target_stable_id"
        ),
        relation_type=_required_string(value["relation_type"], "relation_type"),
        attributes=_pairs_from_value(value["attributes"], "relation_attributes"),
        occurrence=occurrence,
        partition=_partition_from_mapping(value["partition"]),
    )


def _list_field(value: Mapping[str, Any], field_name: str) -> list[Any]:
    result = value[field_name]
    if not isinstance(result, list):
        raise OewnParseError(f"canonical_{field_name}_invalid")
    return result


def _unit_common(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("schema") != OEWN_UNIT_SCHEMA:
        raise OewnParseError("canonical_unit_schema_mismatch")
    if value.get("source_id") != OEWN_SOURCE_ID:
        raise OewnParseError("canonical_unit_source_id_mismatch")
    _partition_from_mapping(value.get("partition"))
    return {
        "source_id": OEWN_SOURCE_ID,
        "release_identity": _required_string(
            value.get("release_identity"), "unit_release_identity"
        ),
        "lexicon_id": _required_string(value.get("lexicon_id"), "unit_lexicon_id"),
        "language": _required_string(value.get("language"), "unit_language"),
        "source_record_id": _required_string(
            value.get("source_record_id"), "unit_source_record_id"
        ),
        "stable_id": _required_string(value.get("stable_id"), "unit_stable_id"),
        "partition": DEPENDENCY_PARTITION,
    }


def _unit_from_mapping(value: Mapping[str, Any]) -> OewnUnit:
    common_keys = {
        "language",
        "lexicon_id",
        "partition",
        "release_identity",
        "schema",
        "source_id",
        "source_record_id",
        "stable_id",
        "unit_kind",
    }
    kind = value.get("unit_kind")
    common = _unit_common(value)
    if kind == "lexical_entry":
        _exact_keys(
            value,
            common_keys | {"forms", "lemma", "senses", "syntactic_behaviors"},
            "lexical_entry_unit",
        )
        behaviors: list[OewnSyntacticBehavior] = []
        for behavior in _list_field(value, "syntactic_behaviors"):
            if not isinstance(behavior, dict):
                raise OewnParseError("canonical_syntactic_behavior_invalid")
            _exact_keys(
                behavior,
                {"senses", "subcategorization_frame"},
                "syntactic_behavior",
            )
            senses = behavior["senses"]
            if not isinstance(senses, list):
                raise OewnParseError("canonical_syntactic_behavior_senses_invalid")
            behaviors.append(
                OewnSyntacticBehavior(
                    subcategorization_frame=_required_string(
                        behavior["subcategorization_frame"],
                        "subcategorization_frame",
                    ),
                    senses=tuple(_reference_from_mapping(item) for item in senses),
                )
            )
        return OewnLexicalEntryUnit(
            **common,
            lemma=_form_from_mapping(value["lemma"]),
            forms=tuple(
                _form_from_mapping(item) for item in _list_field(value, "forms")
            ),
            senses=tuple(
                _reference_from_mapping(item) for item in _list_field(value, "senses")
            ),
            syntactic_behaviors=tuple(behaviors),
        )
    if kind == "sense":
        _exact_keys(
            value,
            common_keys
            | {
                "adjective_position",
                "examples",
                "lexical_entry",
                "relations",
                "synset",
            },
            "sense_unit",
        )
        return OewnSenseUnit(
            **common,
            lexical_entry=_reference_from_mapping(value["lexical_entry"]),
            synset=_reference_from_mapping(value["synset"]),
            relations=tuple(
                _relation_from_mapping(item) for item in _list_field(value, "relations")
            ),
            examples=tuple(
                _text_from_mapping(item) for item in _list_field(value, "examples")
            ),
            adjective_position=_optional_string(
                value["adjective_position"],
                "sense_adjective_position",
            ),
        )
    if kind == "synset":
        _exact_keys(
            value,
            common_keys
            | {
                "definitions",
                "examples",
                "ili",
                "ili_definitions",
                "lexfile",
                "members",
                "part_of_speech",
                "relations",
            },
            "synset_unit",
        )
        return OewnSynsetUnit(
            **common,
            ili=_optional_string(value["ili"], "synset_ili"),
            part_of_speech=_required_string(
                value["part_of_speech"], "synset_part_of_speech"
            ),
            lexfile=_optional_string(value["lexfile"], "synset_lexfile"),
            members=tuple(
                _reference_from_mapping(item) for item in _list_field(value, "members")
            ),
            definitions=tuple(
                _text_from_mapping(item) for item in _list_field(value, "definitions")
            ),
            ili_definitions=tuple(
                _text_from_mapping(item)
                for item in _list_field(value, "ili_definitions")
            ),
            examples=tuple(
                _text_from_mapping(item) for item in _list_field(value, "examples")
            ),
            relations=tuple(
                _relation_from_mapping(item) for item in _list_field(value, "relations")
            ),
        )
    raise OewnParseError("canonical_unit_kind_invalid")


__all__ = [
    "BinaryOpener",
    "BoundedSpoolFactory",
    "CheckpointCallback",
    "Clock",
    "DEFAULT_LIMITS",
    "DEPENDENCY_PARTITION",
    "DEPENDENCY_ONLY_PARTITION_EFFECT",
    "DependencyOnlyPartitionMetadata",
    "OEWN_CORPUS_SCHEMA",
    "OEWN_SOURCE_ID",
    "OEWN_UNIT_SCHEMA",
    "OewnCheckpoint",
    "OewnCorpusMetadata",
    "OewnForm",
    "OewnLexicalEntryUnit",
    "OewnLexiconMetadata",
    "OewnParseError",
    "OewnParsedCorpus",
    "OewnParserLimits",
    "OewnReference",
    "OewnRelation",
    "OewnSenseUnit",
    "OewnSourceIdentity",
    "OewnSynsetUnit",
    "OewnSyntacticBehavior",
    "OewnText",
    "OewnUnit",
    "PartitionEffect",
    "parse_open_english_wordnet_2025",
]

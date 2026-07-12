"""Adversarial tests for the standalone OEWN 2025 GWA-LMF parser."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
import gzip
import hashlib
from io import BytesIO
from typing import Iterator

import pytest

from polymath_ai.corpus import cur0s_oewn_parser as oewn


def _fixture_xml(*, reverse_entries: bool = False) -> bytes:
    cat_entry = """
    <LexicalEntry id="ewn-cat-n">
      <Lemma writtenForm="cat" partOfSpeech="n">
        <Pronunciation variety="general" notation="ipa">kæt</Pronunciation>
      </Lemma>
      <Form writtenForm="cats" tags="plural"/>
      <Sense id="ewn-cat-n-1" synset="ewn-0001-n">
        <SenseRelation relType="antonym" target="ewn-dog-n-1"/>
        <SenseRelation relType="derivation" target="ewn-dog-n-1"/>
        <SenseRelation relType="antonym" target="ewn-dog-n-1"/>
        <Example dc:source="fixture">the cat sleeps</Example>
      </Sense>
      <SyntacticBehaviour senses="ewn-cat-n-1"
        subcategorizationFrame="Somebody ----s"/>
    </LexicalEntry>
    """
    dog_entry = """
    <LexicalEntry id="ewn-dog-n">
      <Lemma writtenForm="dog" partOfSpeech="n"/>
      <Sense id="ewn-dog-n-1" synset="ewn-0002-n"/>
    </LexicalEntry>
    """
    entries = dog_entry + cat_entry if reverse_entries else cat_entry + dog_entry
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<LexicalResource
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xsi:noNamespaceSchemaLocation="https://globalwordnet.github.io/schemas/WN-LMF-1.3.xsd">
  <GlobalInformation label="Open English WordNet"/>
  <Lexicon id="ewn" label="Open English WordNet" language="en"
   email="wordnet@example.invalid"
   license="https://creativecommons.org/licenses/by/4.0/"
   version="2025" url="https://en-word.net/">
    {entries}
    <Synset id="ewn-0001-n" ili="i1" members="ewn-cat-n-1"
     partOfSpeech="n" lexfile="noun.animal">
      <Definition xml:lang="en" dc:source="fixture">a small feline</Definition>
      <ILIDefinition>feline animal</ILIDefinition>
      <Example>this cat purrs</Example>
      <SynsetRelation relType="hypernym" target="ewn-0002-n"/>
      <SynsetRelation relType="also" target="ewn-0002-n"/>
    </Synset>
    <Synset id="ewn-0002-n" ili="i2" members="ewn-dog-n-1"
     partOfSpeech="n">
      <Definition>a domesticated canine</Definition>
    </Synset>
  </Lexicon>
</LexicalResource>
""".encode()


def _gzip(value: bytes) -> bytes:
    return gzip.compress(value, compresslevel=9, mtime=0)


def _identity(payload: bytes) -> oewn.OewnSourceIdentity:
    return oewn.OewnSourceIdentity(
        release_identity="english-wordnet-2025-fixture",
        compressed_sha256="sha256:" + hashlib.sha256(payload).hexdigest(),
        compressed_bytes=len(payload),
        expected_schema_location=(
            "https://globalwordnet.github.io/schemas/WN-LMF-1.3.xsd"
        ),
    )


def _parse(
    xml: bytes | None = None,
    *,
    payload: bytes | None = None,
    limits: oewn.OewnParserLimits = oewn.DEFAULT_LIMITS,
    checkpoint: oewn.CheckpointCallback | None = None,
    clock: oewn.Clock | None = None,
    spool_factory: oewn.BoundedSpoolFactory | None = None,
) -> oewn.OewnParsedCorpus:
    compressed = payload if payload is not None else _gzip(xml or _fixture_xml())
    kwargs: dict[str, object] = {
        "identity": _identity(compressed),
        "binary_opener": lambda: nullcontext(BytesIO(compressed)),
        "limits": limits,
        "checkpoint": checkpoint,
        "spool_factory": spool_factory,
    }
    if clock is not None:
        kwargs["clock"] = clock
    return oewn.parse_open_english_wordnet_2025(**kwargs)  # type: ignore[arg-type]


def _units(corpus: oewn.OewnParsedCorpus) -> tuple[oewn.OewnUnit, ...]:
    with corpus:
        return tuple(corpus.iter_units())


def _replace(xml: bytes, before: bytes, after: bytes) -> bytes:
    assert xml.count(before) == 1
    return xml.replace(before, after)


def test_three_typed_unit_kinds_and_metadata_are_retained() -> None:
    corpus = _parse()
    with corpus:
        units = tuple(corpus.iter_units())
        assert corpus.metadata.source_id == oewn.OEWN_SOURCE_ID
        assert corpus.metadata.lexical_entry_count == 2
        assert corpus.metadata.sense_count == 2
        assert corpus.metadata.synset_count == 2
        assert corpus.metadata.relation_count == 5
        assert corpus.unit_count == 6
    entries = [item for item in units if isinstance(item, oewn.OewnLexicalEntryUnit)]
    senses = [item for item in units if isinstance(item, oewn.OewnSenseUnit)]
    synsets = [item for item in units if isinstance(item, oewn.OewnSynsetUnit)]
    assert len(entries) == len(senses) == len(synsets) == 2
    cat = next(item for item in entries if item.source_record_id == "ewn-cat-n")
    assert cat.lemma.written_form == "cat"
    assert cat.lemma.part_of_speech == "n"
    assert cat.lemma.pronunciations[0].value == "kæt"
    assert cat.lemma.pronunciations[0].attributes == (
        ("notation", "ipa"),
        ("variety", "general"),
    )
    assert cat.forms[0].written_form == "cats"
    assert cat.syntactic_behaviors[0].subcategorization_frame == "Somebody ----s"
    feline = next(item for item in synsets if item.source_record_id == "ewn-0001-n")
    assert feline.ili == "i1"
    assert feline.lexfile == "noun.animal"
    assert feline.definitions[0].value == "a small feline"
    assert feline.definitions[0].language == "en"
    assert feline.examples[0].value == "this cat purrs"


def test_adjective_position_is_explicitly_retained_and_type_checked() -> None:
    xml = _fixture_xml()
    xml = _replace(
        xml,
        b'<Lemma writtenForm="cat" partOfSpeech="n">',
        b'<Lemma writtenForm="cat" partOfSpeech="a">',
    )
    xml = _replace(
        xml,
        b'<Sense id="ewn-cat-n-1" synset="ewn-0001-n">',
        b'<Sense id="ewn-cat-n-1" synset="ewn-0001-n" adjposition="p">',
    )
    xml = _replace(
        xml,
        b'members="ewn-cat-n-1"\n     partOfSpeech="n"',
        b'members="ewn-cat-n-1"\n     partOfSpeech="a"',
    )
    units = _units(_parse(xml))
    sense = next(
        item
        for item in units
        if isinstance(item, oewn.OewnSenseUnit)
        and item.source_record_id == "ewn-cat-n-1"
    )
    assert sense.adjective_position == "p"

    invalid = _replace(
        _fixture_xml(),
        b'<Sense id="ewn-cat-n-1" synset="ewn-0001-n">',
        b'<Sense id="ewn-cat-n-1" synset="ewn-0001-n" adjposition="p">',
    )
    with pytest.raises(oewn.OewnParseError, match="nonadjective"):
        _parse(invalid)


def test_directed_topology_order_and_duplicate_multiplicity_are_preserved() -> None:
    units = _units(_parse())
    cat = next(
        item
        for item in units
        if isinstance(item, oewn.OewnSenseUnit)
        and item.source_record_id == "ewn-cat-n-1"
    )
    dog = next(
        item
        for item in units
        if isinstance(item, oewn.OewnSenseUnit)
        and item.source_record_id == "ewn-dog-n-1"
    )
    assert [item.relation_type for item in cat.relations] == [
        "antonym",
        "derivation",
        "antonym",
    ]
    assert [item.occurrence for item in cat.relations] == [0, 1, 2]
    assert len({item.stable_id for item in cat.relations}) == 3
    assert all(item.target_record_id == "ewn-dog-n-1" for item in cat.relations)
    assert dog.relations == ()  # No inferred or required inverse edge.
    assert all(
        item.partition.partition_effect.value == oewn.DEPENDENCY_ONLY_PARTITION_EFFECT
        for item in cat.relations
    )


def test_determinism_and_canonical_top_level_order() -> None:
    first = _parse()
    second = _parse()
    reversed_entries = _parse(_fixture_xml(reverse_entries=True))
    with first, second, reversed_entries:
        first_lines = tuple(first.iter_canonical_lines())
        second_lines = tuple(second.iter_canonical_lines())
        reversed_lines = tuple(reversed_entries.iter_canonical_lines())
        assert first_lines == second_lines == reversed_lines
        assert first.canonical_sha256 == second.canonical_sha256
        # Unit canonicalization is order independent, while the corpus root also
        # binds the exact uncompressed source object identity.
        assert first.canonical_sha256 != reversed_entries.canonical_sha256
        ids = [item.source_record_id for item in first.iter_units()]
        assert ids == sorted(ids[:2]) + sorted(ids[2:4]) + sorted(ids[4:])


def test_opener_is_called_once_and_spools_are_explicitly_injected() -> None:
    payload = _gzip(_fixture_xml())
    opener_calls = 0
    purposes: list[str] = []

    def opener() -> nullcontext[BytesIO]:
        nonlocal opener_calls
        opener_calls += 1
        return nullcontext(BytesIO(payload))

    def factory(purpose: str, maximum_bytes: int) -> BytesIO:
        assert maximum_bytes == oewn.DEFAULT_LIMITS.max_spool_bytes
        purposes.append(purpose)
        return BytesIO()

    with oewn.parse_open_english_wordnet_2025(
        identity=_identity(payload),
        binary_opener=opener,
        spool_factory=factory,
    ) as corpus:
        assert len(tuple(corpus.iter_units())) == 6
    assert opener_calls == 1
    assert purposes == ["oewn_xml", "oewn_units_stage", "oewn_units_canonical"]


@pytest.mark.parametrize(
    "mutator",
    [
        lambda xml: _replace(
            xml,
            b"<LexicalResource",
            b'<LexicalResource xmlns="urn:malicious"',
        ),
        lambda xml: _replace(
            xml,
            b"<Definition xml:lang=",
            b"<dc:Definition xml:lang=",
        ).replace(b"</Definition>", b"</dc:Definition>", 1),
        lambda xml: _replace(
            xml,
            b'xmlns:dc="http://purl.org/dc/elements/1.1/"',
            b'xmlns:dc="urn:wrong-dc"',
        ),
        lambda xml: _replace(
            xml,
            b"<GlobalInformation label=",
            b'<GlobalInformation unknown="x" label=',
        ),
        lambda xml: _replace(
            xml,
            b"<Definition xml:lang=",
            b"<Unknown xml:lang=",
        ).replace(b"</Definition>", b"</Unknown>", 1),
    ],
)
def test_namespaces_unknown_elements_and_unknown_attributes_fail_closed(
    mutator: object,
) -> None:
    xml = mutator(_fixture_xml())  # type: ignore[operator]
    with pytest.raises(oewn.OewnParseError):
        _parse(xml)


def test_doctype_is_rejected_by_raw_scan_across_chunk_boundary() -> None:
    xml = _fixture_xml()
    declaration_end = xml.index(b"?>") + 2
    prefix = xml[:declaration_end] + b"\n" + (b" " * 61)
    malicious = (
        prefix
        + b'<!DOCTYPE LexicalResource [<!ENTITY x "expanded">]>\n'
        + xml[declaration_end:]
    )
    limits = replace(oewn.DEFAULT_LIMITS, xml_read_chunk_bytes=67)
    with pytest.raises(oewn.OewnParseError, match="xml_dtd_or_entity_forbidden"):
        _parse(malicious, limits=limits)


@pytest.mark.parametrize(
    "declaration",
    [
        b'<!ENTITY x "expanded">',
        b'<!DOCTYPE LexicalResource SYSTEM "file:///etc/passwd">',
        b'<!DoCtYpE LexicalResource [ <!EnTiTy x "expanded"> ]>',
    ],
)
def test_all_dtd_and_entity_declaration_forms_are_rejected(
    declaration: bytes,
) -> None:
    xml = _fixture_xml()
    declaration_end = xml.index(b"?>") + 2
    malicious = xml[:declaration_end] + b"\n" + declaration + xml[declaration_end:]
    with pytest.raises(oewn.OewnParseError, match="xml_dtd_or_entity_forbidden"):
        _parse(malicious)


def test_processing_instruction_is_rejected() -> None:
    xml = _fixture_xml()
    xml = _replace(xml, b"<GlobalInformation", b"<?authority no?>\n<GlobalInformation")
    with pytest.raises(oewn.OewnParseError, match="processing_instruction"):
        _parse(xml)


def test_truncated_corrupt_concatenated_and_trailing_gzip_fail_closed() -> None:
    valid = _gzip(_fixture_xml())
    corrupt = bytearray(valid)
    corrupt[-5] ^= 0xFF
    payloads = [
        valid[:-7],
        bytes(corrupt),
        valid + valid,
        valid + b"trailing",
    ]
    for payload in payloads:
        with pytest.raises(oewn.OewnParseError):
            _parse(payload=payload)


def test_gzip_bomb_ratio_and_uncompressed_limit_fail_before_xml_parse() -> None:
    xml = _fixture_xml().replace(b"a small feline", b"a" * 200_000)
    payload = _gzip(xml)
    ratio_limits = replace(
        oewn.DEFAULT_LIMITS,
        max_compression_ratio=2.0,
        max_text_chars_per_element=300_000,
    )
    with pytest.raises(oewn.OewnParseError, match="compression_ratio_limit_exceeded"):
        _parse(payload=payload, limits=ratio_limits)
    byte_limits = replace(
        oewn.DEFAULT_LIMITS,
        max_uncompressed_bytes=10_000,
        max_spool_bytes=20_000,
        max_canonical_unit_bytes=16_000,
    )
    with pytest.raises(oewn.OewnParseError, match="uncompressed_byte_limit_exceeded"):
        _parse(payload=payload, limits=byte_limits)


def test_decompression_writes_are_chunk_bounded_before_limit_checks() -> None:
    observed_writes: list[int] = []

    class TrackingSpool(BytesIO):
        def write(self, value: bytes, /) -> int:
            observed_writes.append(len(value))
            return super().write(value)

    def factory(_purpose: str, _maximum_bytes: int) -> BytesIO:
        return TrackingSpool()

    limits = replace(oewn.DEFAULT_LIMITS, decompressed_output_chunk_bytes=37)
    _units(_parse(limits=limits, spool_factory=factory))
    assert observed_writes
    # Canonical records may be larger; XML decompression writes occur first.
    xml_write_count = 0
    xml_bytes = 0
    expected_xml_bytes = len(_fixture_xml())
    while xml_bytes < expected_xml_bytes:
        size = observed_writes[xml_write_count]
        assert size <= 37
        xml_bytes += size
        xml_write_count += 1
    assert xml_bytes == expected_xml_bytes


def test_default_memory_spool_has_a_small_independent_ceiling() -> None:
    limits = replace(oewn.DEFAULT_LIMITS, max_default_in_memory_spool_bytes=256)
    with pytest.raises(oewn.OewnParseError, match="default_memory_spool_limit"):
        _parse(limits=limits)


def test_markup_is_bounded_before_expat_can_buffer_a_whole_construct() -> None:
    xml = _replace(
        _fixture_xml(),
        b"<GlobalInformation",
        b"<!--" + (b"x" * 600) + b"-->\n  <GlobalInformation",
    )
    limits = replace(oewn.DEFAULT_LIMITS, max_xml_markup_bytes=300)
    with pytest.raises(oewn.OewnParseError, match="xml_markup_byte_limit_exceeded"):
        _parse(xml, limits=limits)


def test_entity_reference_token_is_bounded_before_expat_buffering() -> None:
    xml = _fixture_xml().replace(
        b"a small feline",
        b"&" + (b"entity_name" * 100) + b";",
    )
    limits = replace(oewn.DEFAULT_LIMITS, max_xml_reference_bytes=64)
    with pytest.raises(oewn.OewnParseError, match="xml_reference_byte_limit"):
        _parse(xml, limits=limits)


def test_record_payload_is_bounded_before_canonical_json_allocation() -> None:
    limits = replace(oewn.DEFAULT_LIMITS, max_canonical_unit_bytes=700)
    with pytest.raises(oewn.OewnParseError, match="record_payload_byte_limit"):
        _parse(limits=limits)


def test_repeated_values_are_bounded_while_streaming_each_record() -> None:
    limits = replace(oewn.DEFAULT_LIMITS, max_values_per_unit=2)
    with pytest.raises(oewn.OewnParseError, match="relation_value_limit"):
        _parse(limits=limits)


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"max_xml_depth": 4}, "xml_depth_limit_exceeded"),
        ({"max_xml_elements": 10}, "xml_element_limit_exceeded"),
        ({"max_attributes_per_element": 4}, "xml_attribute_count_limit_exceeded"),
        ({"max_total_attribute_chars": 50}, "xml_total_attribute_chars_limit"),
        ({"max_text_chars_per_element": 5}, "xml_element_text_limit_exceeded"),
        ({"max_total_text_chars": 50}, "xml_total_text_chars_limit_exceeded"),
        ({"max_relations": 1}, "relation_limit_exceeded"),
        ({"max_relations_per_unit": 1}, "relations_per_unit_limit_exceeded"),
        ({"max_units": 2}, "unit_limit_exceeded"),
    ],
)
def test_xml_attribute_text_element_relation_and_unit_limits(
    changes: dict[str, int],
    error: str,
) -> None:
    limits = replace(oewn.DEFAULT_LIMITS, **changes)
    with pytest.raises(oewn.OewnParseError, match=error):
        _parse(limits=limits)


def test_identifier_list_and_reference_count_limits() -> None:
    limits = replace(oewn.DEFAULT_LIMITS, max_references_per_unit=1)
    xml = _fixture_xml().replace(
        b'senses="ewn-cat-n-1"',
        b'senses="ewn-cat-n-1 ewn-dog-n-1"',
    )
    with pytest.raises(oewn.OewnParseError, match="identifier_list_limit_exceeded"):
        _parse(xml, limits=limits)


@pytest.mark.parametrize(
    ("before", "after", "error"),
    [
        (b'synset="ewn-0001-n"', b'synset="ewn-missing-n"', "missing_synset"),
        (
            b'target="ewn-dog-n-1"',
            b'target="ewn-missing-n-1"',
            "missing_sense",
        ),
        (
            b'target="ewn-0002-n"',
            b'target="ewn-missing-n"',
            "missing_synset",
        ),
        (
            b'members="ewn-cat-n-1"',
            b'members="ewn-dog-n-1"',
            "member_points_to_other_synset",
        ),
        (
            b'senses="ewn-cat-n-1"',
            b'senses="ewn-dog-n-1"',
            "syntactic_behavior_cross_entry",
        ),
        (
            b'members="ewn-cat-n-1"\n     partOfSpeech="n"',
            b'members="ewn-cat-n-1"\n     partOfSpeech="v"',
            "part_of_speech_mismatch",
        ),
    ],
)
def test_malformed_cross_record_references_fail_closed(
    before: bytes,
    after: bytes,
    error: str,
) -> None:
    xml = _fixture_xml()
    assert before in xml
    xml = xml.replace(before, after, 1)
    with pytest.raises(oewn.OewnParseError, match=error):
        _parse(xml)


def test_nonexhaustive_synset_membership_fails_closed() -> None:
    xml = _fixture_xml()
    second_sense = (
        b'<Sense id="ewn-cat-n-2" synset="ewn-0001-n"/>\n      <SyntacticBehaviour'
    )
    xml = _replace(xml, b"<SyntacticBehaviour", second_sense)
    with pytest.raises(oewn.OewnParseError, match="synset_members_not_exhaustive"):
        _parse(xml)


def test_duplicate_global_id_is_rejected() -> None:
    xml = _replace(_fixture_xml(), b'id="ewn-dog-n"', b'id="ewn-cat-n"')
    with pytest.raises(oewn.OewnParseError, match="duplicate_global_xml_id"):
        _parse(xml)


def test_stable_id_collision_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oewn, "_stable_id_for", lambda _kind, _raw: "collision")
    with pytest.raises(oewn.OewnParseError, match="stable_id_collision"):
        _parse()


class _LeaseExpired(RuntimeError):
    pass


def test_checkpoint_callback_failure_is_fatal_and_keeps_original_cause() -> None:
    def checkpoint(_state: oewn.OewnCheckpoint) -> None:
        raise _LeaseExpired("lease expired")

    with pytest.raises(
        oewn.OewnParseError, match="checkpoint_callback_failed"
    ) as caught:
        _parse(checkpoint=checkpoint)
    assert isinstance(caught.value.__cause__, _LeaseExpired)


def test_checkpoint_covers_every_long_running_phase() -> None:
    phases: set[str] = set()

    def checkpoint(state: oewn.OewnCheckpoint) -> None:
        phases.add(state.phase)

    with _parse(checkpoint=checkpoint) as corpus:
        tuple(corpus.iter_units())
    assert {
        "gzip_decompression",
        "xml_spool_rehash",
        "xml_security_scan",
        "xml_index_pass",
        "xml_validation_pass",
        "canonical_sort_copy",
        "canonical_spool_postcopy_rehash",
        "canonical_root_hash",
        "canonical_spool_pre_yield_rehash",
        "canonical_unit_iteration",
    }.issubset(phases)


def test_wall_clock_limit_and_clock_failures_are_fatal() -> None:
    ticks = iter([0.0, 2.0])
    limits = replace(oewn.DEFAULT_LIMITS, max_wall_seconds=1.0)
    with pytest.raises(oewn.OewnParseError, match="wall_time_limit_exceeded"):
        _parse(limits=limits, clock=lambda: next(ticks))

    def failed_clock() -> float:
        raise RuntimeError("clock unavailable")

    with pytest.raises(oewn.OewnParseError, match="clock_failed"):
        _parse(clock=failed_clock)


def test_backward_and_nonfinite_clocks_are_rejected() -> None:
    ticks = iter([2.0, 1.0])
    with pytest.raises(oewn.OewnParseError, match="clock_moved_backwards"):
        _parse(clock=lambda: next(ticks))
    with pytest.raises(oewn.OewnParseError, match="clock_returned_nonfinite"):
        _parse(clock=lambda: float("nan"))


def test_compressed_identity_mismatch_fails_closed() -> None:
    payload = _gzip(_fixture_xml())
    identity = oewn.OewnSourceIdentity(
        release_identity="fixture",
        compressed_sha256="sha256:" + ("0" * 64),
        compressed_bytes=len(payload),
        expected_schema_location=(
            "https://globalwordnet.github.io/schemas/WN-LMF-1.3.xsd"
        ),
    )
    with pytest.raises(
        oewn.OewnParseError, match="compressed_sha256_identity_mismatch"
    ):
        oewn.parse_open_english_wordnet_2025(
            identity=identity,
            binary_opener=lambda: nullcontext(BytesIO(payload)),
        )


def test_schema_location_must_be_exactly_pinned_by_source_identity() -> None:
    payload = _gzip(_fixture_xml())
    identity = replace(
        _identity(payload),
        expected_schema_location=(
            "https://globalwordnet.github.io/schemas/WN-LMF-1.4.xsd"
        ),
    )
    with pytest.raises(oewn.OewnParseError, match="schema_location_identity_mismatch"):
        oewn.parse_open_english_wordnet_2025(
            identity=identity,
            binary_opener=lambda: nullcontext(BytesIO(payload)),
        )


def test_canonical_spool_is_rehashed_before_any_yield() -> None:
    spools: dict[str, BytesIO] = {}

    def factory(purpose: str, _maximum_bytes: int) -> BytesIO:
        spool = BytesIO()
        spools[purpose] = spool
        return spool

    corpus = _parse(spool_factory=factory)
    final = spools["oewn_units_canonical"]
    final.seek(0)
    first = final.read(1)
    final.seek(0)
    final.write(bytes([first[0] ^ 1]))
    with (
        corpus,
        pytest.raises(
            oewn.OewnParseError,
            match="canonical_spool_sha256_mismatch",
        ),
    ):
        next(corpus.iter_units())


def test_canonical_spool_growth_is_rejected_before_hashing_the_extra_tail() -> None:
    spools: dict[str, BytesIO] = {}

    def factory(purpose: str, _maximum_bytes: int) -> BytesIO:
        spool = BytesIO()
        spools[purpose] = spool
        return spool

    corpus = _parse(spool_factory=factory)
    final = spools["oewn_units_canonical"]
    final.seek(0, 2)
    final.write(b"unexpected-tail")
    with (
        corpus,
        pytest.raises(
            oewn.OewnParseError,
            match="canonical_spool_byte_mismatch",
        ),
    ):
        next(corpus.iter_units())


def test_spool_alias_is_rejected() -> None:
    shared = BytesIO()

    def factory(_purpose: str, _maximum_bytes: int) -> BytesIO:
        return shared

    with pytest.raises(oewn.OewnParseError, match="spool_alias_forbidden"):
        _parse(spool_factory=factory)


def test_malformed_xml_and_utf16_are_rejected() -> None:
    malformed = _fixture_xml().replace(b"</Synset>", b"</LexicalEntry>", 1)
    with pytest.raises(oewn.OewnParseError, match="malformed_gwa_lmf_xml"):
        _parse(malformed)
    utf16 = _fixture_xml().decode().replace('encoding="UTF-8"', 'encoding="UTF-16"')
    with pytest.raises(oewn.OewnParseError):
        _parse(utf16.encode("utf-16"))


def test_corpus_close_and_concurrent_iteration_are_enforced() -> None:
    corpus = _parse()
    iterator = corpus.iter_units()
    next(iterator)
    with pytest.raises(oewn.OewnParseError, match="concurrent_corpus_iteration"):
        next(corpus.iter_units())
    iterator.close()
    corpus.close()
    with pytest.raises(oewn.OewnParseError, match="corpus_closed"):
        next(corpus.iter_units())


def test_binary_opener_and_factory_failures_are_normalized() -> None:
    payload = _gzip(_fixture_xml())

    def failed_opener() -> nullcontext[BytesIO]:
        raise OSError("custody failure")

    with pytest.raises(oewn.OewnParseError, match="compressed_source_open_failed"):
        oewn.parse_open_english_wordnet_2025(
            identity=_identity(payload),
            binary_opener=failed_opener,
        )

    def failed_factory(_purpose: str, _maximum: int) -> BytesIO:
        raise OSError("spool failure")

    with pytest.raises(oewn.OewnParseError, match="spool_factory_failed"):
        _parse(spool_factory=failed_factory)


def test_no_path_or_pwn_api_is_exposed() -> None:
    assert "path" not in oewn.parse_open_english_wordnet_2025.__annotations__
    assert not any("pwn" in name.lower() for name in oewn.__all__)
    assert oewn.OEWN_SOURCE_ID == "open_english_wordnet_2025_core_gwa_lmf"


def test_callback_receives_monotone_bounded_progress() -> None:
    checkpoints: list[oewn.OewnCheckpoint] = []

    def checkpoint(state: oewn.OewnCheckpoint) -> None:
        checkpoints.append(state)

    _units(_parse(checkpoint=checkpoint))
    assert checkpoints
    elapsed = [item.elapsed_seconds for item in checkpoints]
    assert elapsed == sorted(elapsed)
    assert max(item.compressed_bytes for item in checkpoints) > 0
    assert max(item.uncompressed_bytes for item in checkpoints) > 0
    assert max(item.xml_events for item in checkpoints) > 0


def test_iterator_type_annotation_remains_a_typed_unit_stream() -> None:
    def consume(values: Iterator[oewn.OewnUnit]) -> list[str]:
        return [value.source_record_id for value in values]

    corpus = _parse()
    with corpus:
        assert len(consume(corpus.iter_units())) == 6

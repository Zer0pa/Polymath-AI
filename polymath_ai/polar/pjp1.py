"""PJP1 v1 byte-contract parser for Phase 3/4 consumer preflight."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Any


PJP1_MAGIC = b"PJP1"
PJP1_SCHEMA_VERSION = 1
PJP1_ENDIAN_MARKER = 1
PJP1_HEADER_BYTES = 4096
PJP1_PACKET_LEN = 128
PJP1_JL_DIM = 256
PJP1_EMBED_DIM = 2560
PJP1_META_BYTES = 192
PJP1_TOKEN_BYTES = PJP1_PACKET_LEN * 4
PJP1_ROLE_BYTES = PJP1_PACKET_LEN
PJP1_POLAR_BYTES = PJP1_PACKET_LEN * (PJP1_JL_DIM // 8)
PJP1_POOLED_BYTES = PJP1_JL_DIM // 8
PJP1_SECTION_TABLE_OFFSET = 768
PJP1_SECTION_ENTRY_BYTES = 40

PJP1_EXPECTED_SECTIONS = {
    "metadata": PJP1_META_BYTES,
    "token_ids": PJP1_TOKEN_BYTES,
    "roles": PJP1_ROLE_BYTES,
    "input_polar": PJP1_POLAR_BYTES,
    "target_polar": PJP1_POLAR_BYTES,
    "pooled_answer": PJP1_POOLED_BYTES,
}


class PJP1Error(ValueError):
    """Raised when a PJP1 file violates the v1 byte contract."""


@dataclass(frozen=True)
class PJP1Section:
    name: str
    offset: int
    length: int
    bytes_per_packet: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "offset": self.offset,
            "length": self.length,
            "bytes_per_packet": self.bytes_per_packet,
        }


@dataclass(frozen=True)
class PJP1Contract:
    path: str
    bytes: int
    sha256: str
    schema_version: int
    endian_marker: int
    header_bytes: int
    packet_len: int
    jl_dim: int
    embedding_dim: int
    packet_count: int
    source_record_count: int
    source_real_token_count: int
    slot_count: int
    section_count: int
    source_sha256_stream: str
    vocab_sha256: str
    merges_sha256: str
    embedding_sha256: str
    embedding_manifest_sha256: str
    jl_sha256: str
    created_utc: str
    writer_version: str
    projection_label: str
    sections: tuple[PJP1Section, ...]
    sampled_metadata: tuple[dict[str, Any], ...]
    validation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "schema_version": self.schema_version,
            "endian_marker": self.endian_marker,
            "header_bytes": self.header_bytes,
            "packet_len": self.packet_len,
            "jl_dim": self.jl_dim,
            "embedding_dim": self.embedding_dim,
            "packet_count": self.packet_count,
            "source_record_count": self.source_record_count,
            "source_real_token_count": self.source_real_token_count,
            "slot_count": self.slot_count,
            "section_count": self.section_count,
            "source_sha256_stream": self.source_sha256_stream,
            "vocab_sha256": self.vocab_sha256,
            "merges_sha256": self.merges_sha256,
            "embedding_sha256": self.embedding_sha256,
            "embedding_manifest_sha256": self.embedding_manifest_sha256,
            "jl_sha256": self.jl_sha256,
            "created_utc": self.created_utc,
            "writer_version": self.writer_version,
            "projection_label": self.projection_label,
            "sections": [section.to_dict() for section in self.sections],
            "sampled_metadata": list(self.sampled_metadata),
            "validation": self.validation,
            "phase3_shape": phase3_shape_summary(self),
        }


def inspect_pjp1(path: str | Path, *, metadata_samples: int = 5) -> PJP1Contract:
    pjp1_path = Path(path)
    file_bytes = pjp1_path.stat().st_size
    with pjp1_path.open("rb") as handle:
        header = handle.read(PJP1_HEADER_BYTES)
        if len(header) != PJP1_HEADER_BYTES:
            raise PJP1Error(f"{pjp1_path}: truncated PJP1 header")
        parsed = _parse_header(header)
        sections = _parse_sections(header, parsed["section_count"], parsed["packet_count"])
        validation = _validate_contract(file_bytes, parsed, sections)
        sampled_metadata = _read_metadata_samples(handle, sections, parsed["packet_count"], metadata_samples)

    return PJP1Contract(
        path=str(pjp1_path),
        bytes=file_bytes,
        sha256=_sha256_file(pjp1_path),
        schema_version=parsed["schema_version"],
        endian_marker=parsed["endian_marker"],
        header_bytes=parsed["header_bytes"],
        packet_len=parsed["packet_len"],
        jl_dim=parsed["jl_dim"],
        embedding_dim=parsed["embedding_dim"],
        packet_count=parsed["packet_count"],
        source_record_count=parsed["source_record_count"],
        source_real_token_count=parsed["source_real_token_count"],
        slot_count=parsed["slot_count"],
        section_count=parsed["section_count"],
        source_sha256_stream=parsed["source_sha256_stream"],
        vocab_sha256=parsed["vocab_sha256"],
        merges_sha256=parsed["merges_sha256"],
        embedding_sha256=parsed["embedding_sha256"],
        embedding_manifest_sha256=parsed["embedding_manifest_sha256"],
        jl_sha256=parsed["jl_sha256"],
        created_utc=parsed["created_utc"],
        writer_version=parsed["writer_version"],
        projection_label=parsed["projection_label"],
        sections=tuple(sections),
        sampled_metadata=tuple(sampled_metadata),
        validation=validation,
    )


def phase3_shape_summary(contract: PJP1Contract) -> dict[str, Any]:
    packet_count = contract.packet_count
    bitpacked_input_bytes = packet_count * PJP1_POLAR_BYTES
    bitpacked_target_bytes = packet_count * PJP1_POLAR_BYTES
    unpacked_i8_bytes = packet_count * PJP1_PACKET_LEN * PJP1_JL_DIM
    unpacked_f16_bytes = unpacked_i8_bytes * 2
    unpacked_f32_bytes = unpacked_i8_bytes * 4
    return {
        "packet_shape": {
            "token_ids": [packet_count, PJP1_PACKET_LEN],
            "roles": [packet_count, PJP1_PACKET_LEN],
            "input_polar_bitpacked": [packet_count, PJP1_PACKET_LEN, PJP1_JL_DIM // 8],
            "target_polar_bitpacked": [packet_count, PJP1_PACKET_LEN, PJP1_JL_DIM // 8],
            "pooled_answer_bitpacked": [packet_count, PJP1_JL_DIM // 8],
        },
        "logical_polar_shape": [packet_count, PJP1_PACKET_LEN, PJP1_JL_DIM],
        "bit_order": "lsb_first",
        "direct_bitpacked_input_bytes": bitpacked_input_bytes,
        "direct_bitpacked_target_bytes": bitpacked_target_bytes,
        "unpack_expansion": {
            "int8_sign_bytes": unpacked_i8_bytes,
            "int8_vs_bitpacked_ratio": 8,
            "float16_sign_bytes": unpacked_f16_bytes,
            "float16_vs_bitpacked_ratio": 16,
            "float32_sign_bytes": unpacked_f32_bytes,
            "float32_vs_bitpacked_ratio": 32,
        },
        "phase3_consumer_rule": (
            "Prefer direct bitpacked uint8 consumption. Any int8/f16/f32 unpack "
            "path must report the expanded bytes and staging copy count."
        ),
    }


def write_contract_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sample_pjp1_geometry(path: str | Path, *, max_packets: int = 1024) -> dict[str, Any]:
    """Sample compact projection-geometry metrics from a PJP1 file.

    The returned payload contains only aggregate counts/statistics. It does not
    expose token IDs, raw polar vectors, embeddings, or JL matrix content.
    """

    contract = inspect_pjp1(path, metadata_samples=0)
    if contract.validation["status"] != "pass":
        return {
            "status": "blocked",
            "blockers": ["pjp1_contract_failed"],
            "pjp1_sha256": contract.sha256,
            "pjp1_bytes": contract.bytes,
            "metric_measurement_status": {
                "collision_rate": "blocked_by_pjp1_contract",
                "projected_vector_norm": "blocked_by_pjp1_contract",
                "hamming_distance": "blocked_by_pjp1_contract",
                "jl_distance_distortion": "blocked_by_pjp1_contract",
            },
        }

    section_by_name = {section.name: section for section in contract.sections}
    metadata = section_by_name["metadata"]
    token_ids = section_by_name["token_ids"]
    input_polar = section_by_name["input_polar"]
    sample_packets = contract.packet_count if max_packets <= 0 else min(contract.packet_count, max_packets)
    if sample_packets <= 0:
        return {
            "status": "blocked",
            "blockers": ["no_packets_to_sample"],
            "pjp1_sha256": contract.sha256,
            "pjp1_bytes": contract.bytes,
            "metric_measurement_status": {
                "collision_rate": "blocked_no_packets_to_sample",
                "projected_vector_norm": "blocked_no_packets_to_sample",
                "hamming_distance": "blocked_no_packets_to_sample",
                "jl_distance_distortion": "blocked_no_packets_to_sample",
            },
        }

    seen_projection_owner: dict[bytes, int] = {}
    collision_count = 0
    same_token_duplicate_count = 0
    sampled_real_tokens = 0
    positive_counts: list[int] = []
    hamming_distances: list[int] = []
    previous_vector: bytes | None = None

    with Path(path).open("rb") as handle:
        for packet_index in range(sample_packets):
            handle.seek(metadata.offset + packet_index * PJP1_META_BYTES)
            meta = handle.read(PJP1_META_BYTES)
            if len(meta) != PJP1_META_BYTES:
                raise PJP1Error("truncated metadata during geometry sample")
            real_tokens = min(_parse_packet_metadata(meta)["real_token_count"], PJP1_PACKET_LEN)

            handle.seek(token_ids.offset + packet_index * PJP1_TOKEN_BYTES)
            token_chunk = handle.read(PJP1_TOKEN_BYTES)
            if len(token_chunk) != PJP1_TOKEN_BYTES:
                raise PJP1Error("truncated token_ids during geometry sample")

            handle.seek(input_polar.offset + packet_index * PJP1_POLAR_BYTES)
            polar_chunk = handle.read(PJP1_POLAR_BYTES)
            if len(polar_chunk) != PJP1_POLAR_BYTES:
                raise PJP1Error("truncated input_polar during geometry sample")

            for slot in range(real_tokens):
                token_id = _u32(token_chunk, slot * 4)
                start = slot * (PJP1_JL_DIM // 8)
                vector = polar_chunk[start : start + (PJP1_JL_DIM // 8)]
                positive_counts.append(_popcount_bytes(vector))
                if previous_vector is not None:
                    hamming_distances.append(_hamming_bytes(previous_vector, vector))
                previous_vector = vector

                owner = seen_projection_owner.get(vector)
                if owner is None:
                    seen_projection_owner[vector] = token_id
                elif owner != token_id:
                    collision_count += 1
                else:
                    same_token_duplicate_count += 1
                sampled_real_tokens += 1

    collision_rate = (collision_count / sampled_real_tokens) if sampled_real_tokens else None
    norm = math.sqrt(float(PJP1_JL_DIM))
    blockers: list[str] = []
    if collision_rate is None:
        blockers.append("no_real_tokens_sampled")
    elif collision_rate > 0.001:
        blockers.append("collision_rate_above_0_001")

    return {
        "status": "pass" if not blockers else "partial",
        "blockers": blockers,
        "pjp1_sha256": contract.sha256,
        "pjp1_bytes": contract.bytes,
        "sample_packets": sample_packets,
        "sampled_real_tokens": sampled_real_tokens,
        "collision_count": collision_count,
        "collision_rate": collision_rate,
        "same_token_duplicate_projection_count": same_token_duplicate_count,
        "unique_projection_count": len(seen_projection_owner),
        "projected_vector_norm_mean": norm,
        "projected_vector_norm_p95": norm,
        "positive_bit_count_mean": _mean(positive_counts),
        "positive_bit_count_p05": _percentile(positive_counts, 0.05),
        "positive_bit_count_p50": _percentile(positive_counts, 0.50),
        "positive_bit_count_p95": _percentile(positive_counts, 0.95),
        "hamming_distance_mean": _mean(hamming_distances),
        "hamming_distance_p05": _percentile(hamming_distances, 0.05),
        "hamming_distance_p50": _percentile(hamming_distances, 0.50),
        "hamming_distance_p95": _percentile(hamming_distances, 0.95),
        "jl_distance_distortion_mean": None,
        "jl_distance_distortion_p95": None,
        "metric_measurement_status": {
            "collision_rate": "measured_from_pjp1_projected_vector_sample",
            "projected_vector_norm": "measured_from_bitpacked_polar_dimension",
            "hamming_distance": "measured_between_adjacent_sampled_projected_vectors",
            "jl_distance_distortion": "requires_original_embedding_space_pair_distances_or_native_packetizer_support",
        },
        "jl_distance_distortion_status": "unmeasured_requires_original_embedding_space_pair_distances_or_native_packetizer_support",
        "unmeasured_metrics": {
            "jl_distance_distortion": (
                "requires original embedding-space pair distances or native packetizer "
                "support; PJP1 contains only projected bitpacked polar vectors"
            )
        },
    }


def _parse_header(header: bytes) -> dict[str, Any]:
    if header[:4] != PJP1_MAGIC:
        raise PJP1Error("bad PJP1 magic")

    cursor = 80
    string_fields = [
        ("source_sha256_stream", 64),
        ("vocab_sha256", 64),
        ("merges_sha256", 64),
        ("embedding_sha256", 64),
        ("embedding_manifest_sha256", 64),
        ("jl_sha256", 64),
        ("created_utc", 40),
        ("writer_version", 32),
        ("projection_label", 48),
    ]
    strings: dict[str, str] = {}
    for name, width in string_fields:
        strings[name] = _decode_padded(header[cursor : cursor + width])
        cursor += width

    parsed = {
        "schema_version": _u16(header, 4),
        "endian_marker": _u16(header, 6),
        "header_bytes": _u32(header, 8),
        "packet_len": _u32(header, 12),
        "jl_dim": _u32(header, 16),
        "embedding_dim": _u32(header, 20),
        "packet_count": _u64(header, 24),
        "source_record_count": _u64(header, 32),
        "source_real_token_count": _u64(header, 40),
        "slot_count": _u64(header, 48),
        "section_count": _u32(header, 64),
    }
    parsed.update(strings)
    return parsed


def _parse_sections(header: bytes, section_count: int, packet_count: int) -> list[PJP1Section]:
    sections: list[PJP1Section] = []
    for index in range(section_count):
        cursor = PJP1_SECTION_TABLE_OFFSET + index * PJP1_SECTION_ENTRY_BYTES
        name = _decode_padded(header[cursor : cursor + 24])
        offset = _u64(header, cursor + 24)
        length = _u64(header, cursor + 32)
        bytes_per_packet = length // packet_count if packet_count else 0
        sections.append(PJP1Section(name, offset, length, bytes_per_packet))
    return sections


def _validate_contract(
    file_bytes: int, parsed: dict[str, Any], sections: list[PJP1Section]
) -> dict[str, Any]:
    blockers: list[str] = []

    expected_header = {
        "schema_version": PJP1_SCHEMA_VERSION,
        "endian_marker": PJP1_ENDIAN_MARKER,
        "header_bytes": PJP1_HEADER_BYTES,
        "packet_len": PJP1_PACKET_LEN,
        "jl_dim": PJP1_JL_DIM,
        "embedding_dim": PJP1_EMBED_DIM,
    }
    for key, expected in expected_header.items():
        if parsed[key] != expected:
            blockers.append(f"{key}={parsed[key]} expected {expected}")

    packet_count = parsed["packet_count"]
    if packet_count <= 0:
        blockers.append("packet_count must be positive")
    if parsed["slot_count"] != packet_count * parsed["packet_len"]:
        blockers.append("slot_count does not match packet_count * packet_len")

    section_by_name = {section.name: section for section in sections}
    if set(section_by_name) != set(PJP1_EXPECTED_SECTIONS):
        missing = sorted(set(PJP1_EXPECTED_SECTIONS) - set(section_by_name))
        extra = sorted(set(section_by_name) - set(PJP1_EXPECTED_SECTIONS))
        blockers.append(f"section table mismatch missing={missing} extra={extra}")

    for name, expected_per_packet in PJP1_EXPECTED_SECTIONS.items():
        section = section_by_name.get(name)
        if section is None:
            continue
        expected_len = packet_count * expected_per_packet
        if section.length != expected_len:
            blockers.append(f"{name}.length={section.length} expected {expected_len}")
        if section.bytes_per_packet != expected_per_packet:
            blockers.append(
                f"{name}.bytes_per_packet={section.bytes_per_packet} expected {expected_per_packet}"
            )
        if section.offset < PJP1_HEADER_BYTES:
            blockers.append(f"{name}.offset overlaps header")
        if section.offset + section.length > file_bytes:
            blockers.append(f"{name}.range exceeds file size")

    ranges = sorted((section.offset, section.offset + section.length, section.name) for section in sections)
    for previous, current in zip(ranges, ranges[1:]):
        if previous[1] > current[0]:
            blockers.append(f"sections overlap: {previous[2]} and {current[2]}")

    max_end = max((section.offset + section.length for section in sections), default=PJP1_HEADER_BYTES)
    if file_bytes != max_end:
        blockers.append(f"file size {file_bytes} does not equal section end {max_end}")

    return {
        "status": "pass" if not blockers else "fail",
        "blockers": blockers,
        "section_order": [section.name for section in sections],
        "file_bytes_match_section_table": file_bytes == max_end,
        "direct_bitpacked_contract": "pass" if not blockers else "blocked",
    }


def _read_metadata_samples(
    handle: Any,
    sections: list[PJP1Section],
    packet_count: int,
    metadata_samples: int,
) -> list[dict[str, Any]]:
    metadata = next((section for section in sections if section.name == "metadata"), None)
    if metadata is None:
        return []
    limit = min(packet_count, max(0, metadata_samples))
    samples = []
    for index in range(limit):
        handle.seek(metadata.offset + index * PJP1_META_BYTES)
        chunk = handle.read(PJP1_META_BYTES)
        if len(chunk) != PJP1_META_BYTES:
            raise PJP1Error("truncated metadata sample")
        samples.append(_parse_packet_metadata(chunk))
    return samples


def _parse_packet_metadata(meta: bytes) -> dict[str, Any]:
    cursor = 72
    section_refs = []
    for name in ["input_polar", "target_polar", "pooled_answer", "token_ids", "roles"]:
        section_refs.append({"name": name, "offset": _u64(meta, cursor), "length": _u32(meta, cursor + 8)})
        cursor += 12
    return {
        "packet_id": _u64(meta, 0),
        "record_hash": _u64(meta, 8),
        "source_kind": meta[16],
        "continuation_index": _u16(meta, 17),
        "continuation_count": _u16(meta, 19),
        "source_token_start": _u32(meta, 21),
        "real_token_count": _u16(meta, 25),
        "pad_count": _u16(meta, 27),
        "token_hash": _u64(meta, 29),
        "loss_mask_hex_le": meta[40:56].hex(),
        "pad_mask_hex_le": meta[56:72].hex(),
        "section_refs": section_refs,
        "crc32": _u32(meta, cursor),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decode_padded(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("ascii", errors="replace")


def _u16(buf: bytes, offset: int) -> int:
    return struct.unpack_from("<H", buf, offset)[0]


def _u32(buf: bytes, offset: int) -> int:
    return struct.unpack_from("<I", buf, offset)[0]


def _u64(buf: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", buf, offset)[0]


def _popcount_bytes(data: bytes) -> int:
    return sum(byte.bit_count() for byte in data)


def _hamming_bytes(first: bytes, second: bytes) -> int:
    return sum((left ^ right).bit_count() for left, right in zip(first, second))


def _mean(values: list[int]) -> float | None:
    if not values:
        return None
    return float(sum(values)) / float(len(values))


def _percentile(values: list[int], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return float(ordered[index])

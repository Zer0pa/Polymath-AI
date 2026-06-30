from __future__ import annotations

from pathlib import Path
import struct

import pytest

from polymath_ai.polar import PJP1Error, inspect_pjp1, sample_pjp1_geometry
from polymath_ai.polar.pjp1 import (
    PJP1_HEADER_BYTES,
    PJP1_JL_DIM,
    PJP1_PACKET_LEN,
    PJP1_POLAR_BYTES,
)


def test_inspect_pjp1_contract_reads_shape_and_sections(tmp_path: Path) -> None:
    pjp1 = tmp_path / "sample.pjp1"
    _write_minimal_pjp1(pjp1, packet_count=2)

    contract = inspect_pjp1(pjp1, metadata_samples=2)
    payload = contract.to_dict()

    assert payload["validation"]["status"] == "pass"
    assert payload["packet_len"] == PJP1_PACKET_LEN
    assert payload["jl_dim"] == PJP1_JL_DIM
    assert payload["packet_count"] == 2
    assert payload["phase3_shape"]["logical_polar_shape"] == [2, 128, 256]
    assert payload["phase3_shape"]["direct_bitpacked_input_bytes"] == 2 * PJP1_POLAR_BYTES
    assert payload["phase3_shape"]["unpack_expansion"]["int8_vs_bitpacked_ratio"] == 8
    assert payload["sampled_metadata"][0]["real_token_count"] == 3
    assert payload["sampled_metadata"][1]["packet_id"] == 1


def test_inspect_pjp1_rejects_bad_magic(tmp_path: Path) -> None:
    pjp1 = tmp_path / "bad.pjp1"
    pjp1.write_bytes(b"NOPE" + bytes(PJP1_HEADER_BYTES - 4))

    with pytest.raises(PJP1Error):
        inspect_pjp1(pjp1)


def test_sample_pjp1_geometry_returns_aggregate_metrics_only(tmp_path: Path) -> None:
    pjp1 = tmp_path / "sample.pjp1"
    _write_minimal_pjp1(pjp1, packet_count=2)

    payload = sample_pjp1_geometry(pjp1, max_packets=1)

    assert payload["status"] == "pass"
    assert payload["sample_packets"] == 1
    assert payload["sampled_real_tokens"] == 3
    assert payload["collision_count"] == 0
    assert payload["collision_rate"] == 0.0
    assert payload["projected_vector_norm_mean"] == 16.0
    assert payload["jl_distance_distortion_mean"] is None
    assert (
        payload["metric_measurement_status"]["jl_distance_distortion"]
        == "requires_original_embedding_space_pair_distances_or_native_packetizer_support"
    )
    assert payload["jl_distance_distortion_status"].startswith("unmeasured_requires_original_embedding_space")
    assert "raw_vectors" not in payload
    assert "token_ids" not in payload


def _write_minimal_pjp1(path: Path, *, packet_count: int) -> None:
    section_specs = [
        ("metadata", 192),
        ("token_ids", PJP1_PACKET_LEN * 4),
        ("roles", PJP1_PACKET_LEN),
        ("input_polar", PJP1_POLAR_BYTES),
        ("target_polar", PJP1_POLAR_BYTES),
        ("pooled_answer", PJP1_JL_DIM // 8),
    ]
    header = bytearray(PJP1_HEADER_BYTES)
    header[:4] = b"PJP1"
    _put_u16(header, 4, 1)
    _put_u16(header, 6, 1)
    _put_u32(header, 8, PJP1_HEADER_BYTES)
    _put_u32(header, 12, PJP1_PACKET_LEN)
    _put_u32(header, 16, PJP1_JL_DIM)
    _put_u32(header, 20, 2560)
    _put_u64(header, 24, packet_count)
    _put_u64(header, 32, packet_count)
    _put_u64(header, 40, packet_count * 3)
    _put_u64(header, 48, packet_count * PJP1_PACKET_LEN)
    _put_u32(header, 64, len(section_specs))

    cursor = 80
    for text, width in [
        ("a" * 64, 64),
        ("b" * 64, 64),
        ("c" * 64, 64),
        ("d" * 64, 64),
        ("e" * 64, 64),
        ("f" * 64, 64),
        ("2026-06-29T00:00:00Z", 40),
        ("test_writer", 32),
        ("dense_rademacher_k256_lsb_bitpack", 48),
    ]:
        header[cursor : cursor + len(text)] = text.encode("ascii")
        cursor += width

    payload = bytearray()
    section_cursor = PJP1_HEADER_BYTES
    section_table_cursor = 768
    section_offsets: dict[str, int] = {}
    for name, per_packet in section_specs:
        length = packet_count * per_packet
        section_offsets[name] = section_cursor
        header[section_table_cursor : section_table_cursor + len(name)] = name.encode("ascii")
        _put_u64(header, section_table_cursor + 24, section_cursor)
        _put_u64(header, section_table_cursor + 32, length)
        payload.extend(bytes(length))
        section_cursor += length
        section_table_cursor += 40

    for packet_id in range(packet_count):
        base = section_offsets["metadata"] - PJP1_HEADER_BYTES + packet_id * 192
        _put_u64(payload, base + 0, packet_id)
        _put_u64(payload, base + 8, 1000 + packet_id)
        payload[base + 16] = 1
        _put_u16(payload, base + 17, packet_id)
        _put_u16(payload, base + 19, packet_count)
        _put_u32(payload, base + 21, packet_id * 3)
        _put_u16(payload, base + 25, 3)
        _put_u16(payload, base + 27, PJP1_PACKET_LEN - 3)
        _put_u64(payload, base + 29, 2000 + packet_id)

    path.write_bytes(bytes(header) + bytes(payload))


def _put_u16(buf: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<H", buf, offset, value)


def _put_u32(buf: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", buf, offset, value)


def _put_u64(buf: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<Q", buf, offset, value)

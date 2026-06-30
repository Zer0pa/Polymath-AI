from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO_ROOT / "native/polar_phase34_consumer_preflight/build_phase34_pjp1_i8_staging_bench.sh"

PJP1_HEADER_BYTES = 4096
PJP1_PACKET_LEN = 128
PJP1_JL_DIM = 256
PJP1_EMBED_DIM = 2560
SECTION_TABLE_OFFSET = 768
SECTION_ENTRY_BYTES = 40
SECTION_SPECS = [
    ("metadata", 192),
    ("token_ids", 512),
    ("roles", 128),
    ("input_polar", 4096),
    ("target_polar", 4096),
    ("pooled_answer", 32),
]


def test_pjp1_i8_staging_bench_matches_popcount_oracle(tmp_path: Path) -> None:
    binary = _build_binary()
    pjp1 = tmp_path / "valid.pjp1"
    report = tmp_path / "staging.json"
    _write_patterned_pjp1(pjp1, packet_count=4)

    result = subprocess.run(
        [
            str(binary),
            "--pjp1",
            str(pjp1),
            "--output",
            str(report),
            "--batch-packets",
            "2",
            "--max-batches",
            "2",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert json.loads(result.stdout)["status"] == "pass"
    assert payload["status"] == "pass"
    assert payload["phase3_ready_claim"] is False
    assert payload["pjp1"]["bytes"] == pjp1.stat().st_size
    assert payload["pjp1"]["packet_count"] == 4
    assert payload["qnn_input_shape"] == [2, 128, 256]
    assert payload["batch_count"] == 2
    assert payload["processed_packets"] == 4
    assert payload["slots_checked"] == 4 * PJP1_PACKET_LEN
    assert payload["bytes_read_bitpacked"] == 4 * 2 * 4096
    assert payload["bytes_written_i8"] == 4 * 2 * 128 * 256
    assert payload["expansion_ratio"] == 8
    assert payload["oracle_mismatches"] == 0
    assert payload["staging"]["batches_processed"] == 2
    assert payload["staging"]["active_packets"] == 4
    assert payload["staging"]["bytes_read_bitpacked"] == 4 * 2 * 4096
    assert payload["staging"]["bytes_written_i8_model"] == 4 * 2 * 128 * 256
    assert payload["staging"]["i8_vs_bitpacked_ratio"] == 8
    assert payload["staging"]["oracle_mismatches"] == 0
    assert payload["blockers"] == []


def test_pjp1_i8_staging_bench_rejects_bad_target_section_length(tmp_path: Path) -> None:
    binary = _build_binary()
    pjp1 = tmp_path / "bad_target_len.pjp1"
    report = tmp_path / "staging.json"
    _write_patterned_pjp1(pjp1, packet_count=2, corrupt_target_length=True)

    result = subprocess.run(
        [str(binary), "--pjp1", str(pjp1), "--output", str(report)],
        check=False,
        capture_output=True,
        text=True,
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "fail"
    assert payload["status"] == "fail"
    assert payload["phase3_ready_claim"] is False
    assert payload["batch_count"] == 0
    assert payload["bytes_read_bitpacked"] == 0
    assert payload["bytes_written_i8"] == 0
    assert any("target_polar" in blocker for blocker in payload["blockers"])


def _build_binary() -> Path:
    compiler = os.environ.get("CXX", "clang++")
    if shutil.which(compiler) is None:
        pytest.skip(f"{compiler} is required to build the native staging binary")
    result = subprocess.run([str(BUILD_SCRIPT)], check=True, capture_output=True, text=True)
    return Path(result.stdout.strip())


def _write_patterned_pjp1(path: Path, *, packet_count: int, corrupt_target_length: bool = False) -> None:
    header = bytearray(PJP1_HEADER_BYTES)
    header[:4] = b"PJP1"
    _put_u16(header, 4, 1)
    _put_u16(header, 6, 1)
    _put_u32(header, 8, PJP1_HEADER_BYTES)
    _put_u32(header, 12, PJP1_PACKET_LEN)
    _put_u32(header, 16, PJP1_JL_DIM)
    _put_u32(header, 20, PJP1_EMBED_DIM)
    _put_u64(header, 24, packet_count)
    _put_u64(header, 32, packet_count)
    _put_u64(header, 40, packet_count * 3)
    _put_u64(header, 48, packet_count * PJP1_PACKET_LEN)
    _put_u32(header, 64, len(SECTION_SPECS))

    payload = bytearray()
    section_offsets: dict[str, int] = {}
    section_cursor = PJP1_HEADER_BYTES
    for name, stride in SECTION_SPECS:
        section_offsets[name] = section_cursor
        length = packet_count * stride
        if name == "input_polar":
            payload.extend(_pattern_bytes(length, seed=0x55))
        elif name == "target_polar":
            payload.extend(_pattern_bytes(length, seed=0xA3))
        else:
            payload.extend(bytes(length))
        section_cursor += length

    table_cursor = SECTION_TABLE_OFFSET
    for name, stride in SECTION_SPECS:
        length = packet_count * stride
        if corrupt_target_length and name == "target_polar":
            length -= 1
        header[table_cursor : table_cursor + len(name)] = name.encode("ascii")
        _put_u64(header, table_cursor + 24, section_offsets[name])
        _put_u64(header, table_cursor + 32, length)
        table_cursor += SECTION_ENTRY_BYTES

    path.write_bytes(bytes(header) + bytes(payload))


def _pattern_bytes(length: int, *, seed: int) -> bytes:
    return bytes(((index * 17 + seed) & 0xFF) for index in range(length))


def _put_u16(buf: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<H", buf, offset, value)


def _put_u32(buf: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", buf, offset, value)


def _put_u64(buf: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<Q", buf, offset, value)

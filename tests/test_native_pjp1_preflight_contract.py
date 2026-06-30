from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO_ROOT / "native/polar_phase34_consumer_preflight/build_phase34_native_pjp1_consumer_preflight.sh"

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


def test_native_pjp1_consumer_preflight_accepts_valid_synthetic_contract(tmp_path: Path) -> None:
    binary = _build_binary()
    pjp1 = tmp_path / "valid.pjp1"
    report = tmp_path / "report.json"
    _write_minimal_pjp1(pjp1, packet_count=2)

    result = subprocess.run(
        [str(binary), "--pjp1", str(pjp1), "--output", str(report)],
        check=True,
        capture_output=True,
        text=True,
    )

    stdout_payload = json.loads(result.stdout)
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert stdout_payload["status"] == "pass"
    assert payload["status"] == "pass"
    assert payload["phase3_ready_claim"] is False
    assert payload["header"]["packet_count"] == 2
    assert payload["header"]["slot_count"] == 2 * PJP1_PACKET_LEN
    assert payload["preflight"]["file_size_matches_section_table"] is True
    assert payload["preflight"]["no_section_overlaps"] is True
    assert [section["name"] for section in payload["sections"]] == [name for name, _ in SECTION_SPECS]
    assert [section["stride_bytes"] for section in payload["sections"]] == [stride for _, stride in SECTION_SPECS]


def test_native_pjp1_consumer_preflight_rejects_overlapping_sections(tmp_path: Path) -> None:
    binary = _build_binary()
    pjp1 = tmp_path / "overlap.pjp1"
    report = tmp_path / "report.json"
    _write_minimal_pjp1(pjp1, packet_count=2, overlap_target_with_input=True)

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
    assert payload["preflight"]["no_section_overlaps"] is False
    assert any("sections overlap" in blocker for blocker in payload["blockers"])


def _build_binary() -> Path:
    compiler = os.environ.get("CXX", "clang++")
    if shutil.which(compiler) is None:
        pytest.skip(f"{compiler} is required to build the native preflight binary")
    result = subprocess.run([str(BUILD_SCRIPT)], check=True, capture_output=True, text=True)
    return Path(result.stdout.strip())


def _write_minimal_pjp1(
    path: Path,
    *,
    packet_count: int,
    overlap_target_with_input: bool = False,
) -> None:
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
    section_cursor = PJP1_HEADER_BYTES
    section_offsets: dict[str, int] = {}
    for name, stride in SECTION_SPECS:
        section_offsets[name] = section_cursor
        length = packet_count * stride
        payload.extend(bytes(length))
        section_cursor += length

    table_cursor = SECTION_TABLE_OFFSET
    for name, stride in SECTION_SPECS:
        offset = section_offsets[name]
        if overlap_target_with_input and name == "target_polar":
            offset = section_offsets["input_polar"]
        header[table_cursor : table_cursor + len(name)] = name.encode("ascii")
        _put_u64(header, table_cursor + 24, offset)
        _put_u64(header, table_cursor + 32, packet_count * stride)
        table_cursor += SECTION_ENTRY_BYTES

    path.write_bytes(bytes(header) + bytes(payload))


def _put_u16(buf: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<H", buf, offset, value)


def _put_u32(buf: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", buf, offset, value)


def _put_u64(buf: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<Q", buf, offset, value)

"""Pure-Python tests for device probe parsers."""
from __future__ import annotations

from polymath_ai.device.probe import (
    parse_adb_devices,
    parse_getprop,
    parse_meminfo,
    parse_termux_python_version,
    soc_target_from_reported,
)


def test_parse_adb_devices_basic():
    out = "List of devices attached\nABCDEF12345  device usb:1-5 product:NX775S model:NX775S device:NX775S transport_id:1\n"
    rows = parse_adb_devices(out)
    assert len(rows) == 1
    r = rows[0]
    assert r.serial == "ABCDEF12345"
    assert r.state == "device"
    assert r.transport_id == "1"
    assert r.extra.get("model") == "NX775S"


def test_parse_adb_devices_unauthorized():
    out = "List of devices attached\nXXXX unauthorized\n"
    rows = parse_adb_devices(out)
    assert rows[0].state == "unauthorized"


def test_parse_getprop():
    raw = "[ro.product.model]: [REDMAGIC 10 Pro+]\n[ro.build.version.release]: [15]\n[ro.product.cpu.abi]: [arm64-v8a]\n"
    props = parse_getprop(raw)
    assert props["ro.product.model"] == "REDMAGIC 10 Pro+"
    assert props["ro.build.version.release"] == "15"


def test_parse_meminfo():
    raw = (
        "MemTotal:       24576000 kB\n"
        "MemFree:        18000000 kB\n"
        "MemAvailable:   22000000 kB\n"
    )
    mi = parse_meminfo(raw)
    assert mi["MemTotal"] == 24576000
    assert mi["MemAvailable"] == 22000000


def test_parse_termux_python_version():
    assert parse_termux_python_version("Python 3.12.7") == "3.12.7"
    assert parse_termux_python_version("Python 3.11") == "3.11"
    assert parse_termux_python_version("") is None


def test_soc_target_known_match():
    target, conf = soc_target_from_reported("Snapdragon 8 Gen 3 (SM8650-AC)")
    assert target == "SM8650"
    assert conf == 1.0


def test_soc_target_partial_confidence_for_elite():
    target, conf = soc_target_from_reported("Qualcomm Snapdragon 8 Elite")
    assert target is not None
    assert 0 < conf < 1, "Snapdragon 8 Elite alone should not be a high-confidence match"


def test_soc_target_unknown_returns_zero():
    target, conf = soc_target_from_reported("Some New SoC 9000")
    assert target is None
    assert conf == 0.0

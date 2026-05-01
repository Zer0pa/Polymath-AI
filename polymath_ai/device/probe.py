"""Pure-Python parsers for ADB / getprop / meminfo / Termux output.

The probe pipeline is shell-driven (``scripts/host/phone_probe.sh`` and
``scripts/termux/termux_probe.sh``) and these parsers turn raw text output
into envelope-shaped dicts. Pure-Python so they unit-test without a phone
attached.
"""
from __future__ import annotations

import dataclasses
import re
from typing import Any, Dict, List, Mapping, Optional, Tuple


DEVICE_PROBE_SCHEMA_VERSION = "1.0.0"


# ---------- adb devices ----------


@dataclasses.dataclass
class DeviceProbeResult:
    serial: str
    state: str  # device | unauthorized | offline | recovery | sideload
    transport_id: Optional[str] = None
    extra: Mapping[str, str] = dataclasses.field(default_factory=dict)


def parse_adb_devices(output: str) -> List[DeviceProbeResult]:
    """Parse the output of ``adb devices -l``.

    Example line:
        ABCDEF12345  device usb:1-5 product:NX775S model:NX775S device:NX775S transport_id:1
    """
    rows: List[DeviceProbeResult] = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices") or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial = parts[0]
        state = parts[1]
        extra: Dict[str, str] = {}
        transport_id: Optional[str] = None
        for kv in parts[2:]:
            if ":" in kv:
                k, _, v = kv.partition(":")
                if k == "transport_id":
                    transport_id = v
                else:
                    extra[k] = v
        rows.append(DeviceProbeResult(serial=serial, state=state, transport_id=transport_id, extra=extra))
    return rows


# ---------- getprop ----------


_GETPROP_LINE = re.compile(r"^\[(?P<k>[^\]]+)\]:\s*\[(?P<v>.*)\]\s*$")


def parse_getprop(output: str) -> Dict[str, str]:
    """Parse ``adb shell getprop`` output."""
    out: Dict[str, str] = {}
    for line in output.splitlines():
        m = _GETPROP_LINE.match(line.strip())
        if m:
            out[m.group("k")] = m.group("v")
    return out


# Mapping reported SoC names to a LiteRT/QNN AOT target.
#
# NOTE: this is a *first-pass* heuristic. The PRD forbids compiling QNN
# against a guessed SoC; the executor MUST verify the resolved target on the
# real phone before enabling QNN. ``soc_target_from_reported`` returns
# ``(target, confidence)`` and confidence < 1 means "do not enable QNN".
_SOC_NAME_TO_TARGET: Tuple[Tuple[str, str, float], ...] = (
    # (substring, AOT target, confidence)
    ("sm8650", "SM8650", 1.0),  # Snapdragon 8 Gen 3 - older SoC
    ("snapdragon 8 gen 3", "SM8650", 1.0),
    ("sm8750", "SM8750", 0.9),
    ("snapdragon 8 elite", "SM8750", 0.7),  # blueprint cites SM8650 but newer
    ("snapdragon 8 elite gen 5", "SM8850", 0.9),
    ("sm8850", "SM8850", 1.0),
)


def soc_target_from_reported(reported: str) -> Tuple[Optional[str], float]:
    """Return ``(target, confidence)``.

    Confidence < 1.0 means the executor must still confirm with a probe-side
    AOT compile attempt against an alternative target before enabling QNN.
    """
    if not reported:
        return None, 0.0
    lower = reported.lower()
    best: Tuple[Optional[str], float] = (None, 0.0)
    for needle, target, conf in _SOC_NAME_TO_TARGET:
        if needle in lower and conf > best[1]:
            best = (target, conf)
    return best


# ---------- meminfo ----------


_KB_LINE = re.compile(r"^(?P<k>[A-Za-z()0-9_]+):\s+(?P<v>\d+)\s+kB", re.MULTILINE)


def parse_meminfo(output: str) -> Dict[str, int]:
    """Parse ``adb shell cat /proc/meminfo`` output. Returns kB ints."""
    return {m.group("k"): int(m.group("v")) for m in _KB_LINE.finditer(output)}


# ---------- termux ----------


def parse_termux_python_version(output: str) -> Optional[str]:
    """Parse ``python3 --version`` output. Returns ``None`` if absent."""
    if not output:
        return None
    m = re.search(r"Python\s+(\d+\.\d+(?:\.\d+)?)", output)
    return m.group(1) if m else None


# ---------- envelope template ----------


def probe_summary_template() -> dict:
    """Return a fully-populated envelope template with placeholders."""
    return {
        "schema_version": DEVICE_PROBE_SCHEMA_VERSION,
        "host_machine": None,
        "phone_attached": False,
        "phone_model": None,
        "android_version": None,
        "redmagic_os_version": None,
        "abi": None,
        "soc_reported": None,
        "soc_target": None,
        "soc_target_confidence": 0.0,
        "ram_gb": None,
        "storage_free_gb": None,
        "battery_mode": None,
        "battery_pct": None,
        "battery_temp_c": None,
        "charge_separation_active": None,
        "thermal_status": None,
        "gpu_clock_mhz_p50": None,
        "gpu_clock_mhz_p10": None,
        "fan_state": None,
        "vulkan_version": None,
        "qnn_runtime_present": None,
        "litert_runtime_present": None,
        "termux_python_version": None,
    }

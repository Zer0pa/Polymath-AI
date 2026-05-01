"""Phone attach + Termux + profiler probes.

Every probe writes a ``DEVICE_STATE_SCHEMA``-conformant record to the audit
log and returns the same shape so downstream falsifiers
(``device_soc_mismatch``, ``thermal_throttle``, ``charge_bypass_unproven``,
``oom_or_memory_pressure``) have evidence dicts ready to consume.
"""
from polymath_ai.device.probe import (
    DEVICE_PROBE_SCHEMA_VERSION,
    DeviceProbeResult,
    parse_adb_devices,
    parse_getprop,
    parse_meminfo,
    parse_termux_python_version,
    probe_summary_template,
    soc_target_from_reported,
)

__all__ = [
    "DEVICE_PROBE_SCHEMA_VERSION",
    "DeviceProbeResult",
    "parse_adb_devices",
    "parse_getprop",
    "parse_meminfo",
    "parse_termux_python_version",
    "probe_summary_template",
    "soc_target_from_reported",
]

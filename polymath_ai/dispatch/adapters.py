"""Backend adapter contracts + MacSim implementation.

Real device adapters (Android CPU, Vulkan, LiteRT/QNN) are device-side and
constructed lazily on the phone. The MacSim adapter is host-only and exists
so Phase 0C dry-runs can produce ``ExportProbeRecord`` rows without a phone.
"""
from __future__ import annotations

import dataclasses
from typing import Any, List, Mapping, Optional


@dataclasses.dataclass
class BackendProbeRecord:
    backend_name: str
    available: bool
    version: Optional[str]
    notes: str


@dataclasses.dataclass
class CompileRecord:
    backend_name: str
    graph_scope: str
    target: str
    result: str  # ok | failed | unsupported
    delegate_pct: Optional[float]
    unsupported_ops: List[str] = dataclasses.field(default_factory=list)
    log_path: Optional[str] = None


@dataclasses.dataclass
class DelegateReport:
    backend_name: str
    delegated_op_count: int
    fallback_op_count: int
    delegate_pct: float


class AcceleratorAdapter:
    """Informal protocol; concrete adapters duck-type to this shape."""

    name: str
    supports_training: bool
    supports_inference: bool

    def probe(self) -> BackendProbeRecord:
        raise NotImplementedError

    def compile(self, model_ref: str, graph_scope: str, target: str) -> CompileRecord:
        raise NotImplementedError

    def fallback_reason(self) -> Optional[str]:
        return None


class MacSimAdapter(AcceleratorAdapter):
    """Host-side simulator. Reports ``available=True``, returns deterministic
    golden ``ok`` results so Phase 0C dry-runs can emit envelope-shaped rows
    without a phone.
    """

    name = "mac_sim"
    supports_training = True
    supports_inference = True

    def probe(self) -> BackendProbeRecord:
        return BackendProbeRecord(
            backend_name=self.name,
            available=True,
            version="host-stub",
            notes="MacSim - deterministic golden fixtures only; not a device claim.",
        )

    def compile(self, model_ref: str, graph_scope: str, target: str) -> CompileRecord:
        return CompileRecord(
            backend_name=self.name,
            graph_scope=graph_scope,
            target=target,
            result="ok",
            delegate_pct=1.0,
            unsupported_ops=[],
            log_path=None,
        )


class FallbackAdapter(AcceleratorAdapter):
    """CPU/GPU fallback. ``compile`` always succeeds with delegate_pct=1.0
    because the fallback runs every op natively.
    """

    name = "fallback"
    supports_training = False  # we don't claim training on fallback by default
    supports_inference = True

    def __init__(self, downgrade_reason: str = "manual_fallback") -> None:
        self.downgrade_reason = downgrade_reason

    def probe(self) -> BackendProbeRecord:
        return BackendProbeRecord(
            backend_name=self.name,
            available=True,
            version="cpu-or-gpu-native",
            notes=f"fallback active; reason={self.downgrade_reason}",
        )

    def compile(self, model_ref: str, graph_scope: str, target: str) -> CompileRecord:
        return CompileRecord(
            backend_name=self.name,
            graph_scope=graph_scope,
            target="cpu",
            result="ok",
            delegate_pct=1.0,
            unsupported_ops=[],
        )

    def fallback_reason(self) -> Optional[str]:
        return self.downgrade_reason

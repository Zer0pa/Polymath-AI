"""Backend registry for the Reflex Scheduler.

Each backend is identified by a ``BackendRecord``:
  * `backend_id`  - canonical id, e.g. ``litert_qnn_sm8750``
  * `family`      - the broad class (``cpu``, ``gpu``, ``npu``, ``fallback``, ``host_sim``)
  * `capabilities`- which op kinds it can run (training fwd, training bwd, frozen
                    inference, mixed precision, etc.)
  * `requires_phone` - True if backend is device-side; False for host stubs
  * `confirmed_for_socs` - ((soc, confidence), ...) — gate per SoC; for QNN
                    this is locked at 1.0 only after Phase 0G proof
"""
from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Dict, Iterable, Optional, Sequence, Tuple


class BackendCapability(str, Enum):
    """What an op kind a backend can do."""

    training_forward = "training_forward"
    training_backward = "training_backward"
    inference_only = "inference_only"
    frozen_subgraph_inference = "frozen_subgraph_inference"
    optimizer_step = "optimizer_step"
    eval_only = "eval_only"


@dataclasses.dataclass(frozen=True)
class BackendRecord:
    backend_id: str
    family: str  # cpu | gpu | npu | fallback | host_sim
    capabilities: Tuple[BackendCapability, ...]
    requires_phone: bool
    # When True the backend produces SoC-specific binaries and the
    # scheduler MUST refuse to route to it unless ``confirmed_for_socs``
    # explicitly lists the current SoC at confidence 1.0. NPU AOT
    # (QNN) is the canonical case. CPU / runtime Vulkan / runtime LiteRT
    # GPU backends do NOT need SoC-specific compile and leave this False.
    requires_soc_confirmation: bool = False
    confirmed_for_socs: Tuple[Tuple[str, float], ...] = ()
    notes: str = ""

    def supports(self, cap: BackendCapability) -> bool:
        return cap in self.capabilities

    def is_confirmed_for(self, soc: str, min_confidence: float = 1.0) -> bool:
        for s, conf in self.confirmed_for_socs:
            if s == soc and conf >= min_confidence:
                return True
        return False

    def is_routable_on(self, soc: Optional[str], min_confidence: float = 1.0) -> bool:
        """True if the scheduler may route to this backend on this SoC.

        For backends that don't require SoC confirmation, always True.
        For backends that do, requires the soc to be in confirmed_for_socs.
        """
        if not self.requires_soc_confirmation:
            return True
        if not soc:
            return False
        return self.is_confirmed_for(soc, min_confidence)


class BackendRegistry:
    """Append-only registry. ``register`` raises on duplicate id; ``find``
    yields records matching every supplied predicate (AND semantics).
    """

    def __init__(self) -> None:
        self._by_id: Dict[str, BackendRecord] = {}

    def register(self, record: BackendRecord) -> None:
        if record.backend_id in self._by_id:
            raise ValueError(f"duplicate backend_id: {record.backend_id}")
        self._by_id[record.backend_id] = record

    def get(self, backend_id: str) -> BackendRecord:
        return self._by_id[backend_id]

    def find(
        self,
        *,
        family: Optional[str] = None,
        capability: Optional[BackendCapability] = None,
        requires_phone: Optional[bool] = None,
        soc: Optional[str] = None,
        min_confidence: float = 1.0,
    ) -> list[BackendRecord]:
        out = []
        for r in self._by_id.values():
            if family and r.family != family:
                continue
            if capability and not r.supports(capability):
                continue
            if requires_phone is not None and r.requires_phone != requires_phone:
                continue
            if soc is not None and not r.is_routable_on(soc, min_confidence):
                continue
            out.append(r)
        return out

    def all(self) -> list[BackendRecord]:
        return list(self._by_id.values())


def default_registry() -> BackendRegistry:
    """Bootstrap with the seed backends per PRD §Component Boundaries.

    Confirmed_for_socs for QNN backends is empty until Phase 0G provides
    the compile + delegate proof. The scheduler will refuse to route to
    QNN until at least one SoC is confirmed at confidence 1.0.
    """
    reg = BackendRegistry()

    reg.register(
        BackendRecord(
            backend_id="mac_sim",
            family="host_sim",
            capabilities=(
                BackendCapability.training_forward,
                BackendCapability.training_backward,
                BackendCapability.optimizer_step,
                BackendCapability.eval_only,
            ),
            requires_phone=False,
            notes="Host CPU; deterministic golden fixtures only - not a device claim.",
        )
    )

    reg.register(
        BackendRecord(
            backend_id="android_cpu",
            family="cpu",
            capabilities=(
                BackendCapability.training_forward,
                BackendCapability.training_backward,
                BackendCapability.optimizer_step,
                BackendCapability.eval_only,
            ),
            requires_phone=True,
            notes="On-device Oryon CPU baseline; first real-device backend that must work.",
        )
    )

    reg.register(
        BackendRecord(
            backend_id="vulkan_gpu",
            family="gpu",
            capabilities=(
                BackendCapability.training_forward,
                BackendCapability.training_backward,
                BackendCapability.frozen_subgraph_inference,
            ),
            requires_phone=True,
            notes="Adreno 830 via Vulkan; trainable layers go here in ELO Stage 1.",
        )
    )

    reg.register(
        BackendRecord(
            backend_id="litert_qnn_sm8750",
            family="npu",
            capabilities=(
                BackendCapability.frozen_subgraph_inference,
                BackendCapability.inference_only,
            ),
            requires_phone=True,
            requires_soc_confirmation=True,
            confirmed_for_socs=(("SM8750", 1.0),),
            notes="Hexagon NPU via LiteRT QNN, target SM8750. Phase 0G AOT-compile "
            "proof established 2026-05-02 with ai-edge-litert 2.1.4 + QAIRT 2.44.0.260225 "
            "(matching pair) on Linux x86_64: tiny_block + qwen_block + qwen_frozen_subgraph "
            "(Qwen2.5-1.5B layers 1..26 = the ELO frozen middle, 4.6 GB tflite -> 2.3 GB "
            "Qualcomm SM8750 .bin context binary) all returned models_with_backend=[Qualcomm "
            "...]. See D-029 + runtime/reports/export_probe/2026-05-02T014031Z_litert214_qairt244_FULL/. "
            "Phase 1A QNN routing UNLOCKED.",
        )
    )

    reg.register(
        BackendRecord(
            backend_id="fallback_cpu",
            family="fallback",
            capabilities=(
                BackendCapability.training_forward,
                BackendCapability.training_backward,
                BackendCapability.frozen_subgraph_inference,
                BackendCapability.optimizer_step,
                BackendCapability.eval_only,
            ),
            requires_phone=True,
            notes="Explicit downgrade path. Always works; emits a downgrade record.",
        )
    )

    return reg

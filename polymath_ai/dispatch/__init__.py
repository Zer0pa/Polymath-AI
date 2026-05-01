"""Backend adapters and the export truth-table runner.

Adapters implement a common ``probe / compile / run`` interface so the host
can attempt LiteRT / QNN / Vulkan paths and emit ``ExportProbeRecord`` rows
without changing the runner. PRD §AcceleratorAdapter:

    MacSimAdapter        - host stub, deterministic golden fixtures
    AndroidCPUAdapter    - phone CPU baseline, must work even if accel fails
    VulkanAdapter        - device GPU; LiteRT-GPU or custom Vulkan kernels
    LiteRTQNNAdapter     - NPU; inference only; exact compile/delegate report
    FallbackAdapter      - explicit downgrade record

The truth-table runner (``polymath_ai.dispatch.export_probe``) sweeps
``(model, graph_scope, target)`` combinations and stores a per-combination
``ExportProbeRecord``.
"""
from polymath_ai.dispatch.adapters import (
    AcceleratorAdapter,
    BackendProbeRecord,
    CompileRecord,
    DelegateReport,
    FallbackAdapter,
    MacSimAdapter,
)
from polymath_ai.dispatch.export_probe import (
    ExportProbeRecord,
    ExportProbeSpec,
    PROBE_SCOPES,
    PROBE_TARGETS,
    run_export_probe,
)

__all__ = [
    "AcceleratorAdapter",
    "BackendProbeRecord",
    "CompileRecord",
    "DelegateReport",
    "FallbackAdapter",
    "MacSimAdapter",
    "ExportProbeRecord",
    "ExportProbeSpec",
    "PROBE_SCOPES",
    "PROBE_TARGETS",
    "run_export_probe",
]

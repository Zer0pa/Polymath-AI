"""Polymath AI on-device LLM training research infrastructure.

Boundary: Research infrastructure for in silico on-device LLM training and
multilingual / multi-domain knowledge model construction. Outputs are research
artifacts - model checkpoints, training telemetry, evaluation reports,
throughput measurements. No regulatory certification claims. No clinical or
human-subject use. No surveillance, biometric profiling, or identity inference.
No model weights distributed without explicit license attestation. No training
on copyrighted material without explicit corpus-license decomposition. No
deployment to production without a falsifier-traced acceptance gate.
"""
from polymath_ai._version import __version__, SCHEMA_VERSION

__all__ = ["__version__", "SCHEMA_VERSION"]

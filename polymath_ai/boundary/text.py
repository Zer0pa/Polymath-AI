"""Verbatim boundary block.

Any drift between this string and the boundary block in PRD.md, README.md,
HANDOFF-TO-OVERNIGHT-EXECUTOR.md, or any artifact carrying the boundary is a
``boundary_violation`` falsifier hit.
"""
from __future__ import annotations

import hashlib

# Verbatim boundary text. Hyphen (not em-dash) after "research artifacts"
# matches PRD.md / HANDOFF-TO-OVERNIGHT-EXECUTOR.md exactly.
BOUNDARY_TEXT = (
    "Research infrastructure for in silico on-device LLM training and "
    "multilingual / multi-domain knowledge model construction. Outputs are "
    "research artifacts - model checkpoints, training telemetry, evaluation "
    "reports, throughput measurements. No regulatory certification claims. "
    "No clinical or human-subject use. No surveillance, biometric profiling, "
    "or identity inference. No model weights distributed without explicit "
    "license attestation. No training on copyrighted material without "
    "explicit corpus-license decomposition. No deployment to production "
    "without a falsifier-traced acceptance gate."
)


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


BOUNDARY_SHA256 = _sha256_text(BOUNDARY_TEXT)
BOUNDARY_ID = "boundary:polymath:v1"


def boundary_envelope() -> dict:
    """Return the canonical boundary envelope used in machine-readable rows
    that cannot embed the full block.
    """
    return {
        "boundary_id": BOUNDARY_ID,
        "boundary_text_sha256": BOUNDARY_SHA256,
        "boundary_manifest": "polymath_ai/boundary/text.py",
    }

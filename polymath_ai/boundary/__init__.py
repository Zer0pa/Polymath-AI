"""Boundary text and scanner for the Polymath workstream.

The verbatim boundary block must appear in every artifact, source file, log,
model card, dataset card, evaluation report, checkpoint manifest, Hugging Face
upload, KG node, and handoff. Machine-readable artifacts that cannot embed the
full block must carry ``boundary_id``, ``boundary_text_sha256``, and a link to
the boundary-bearing manifest.
"""
from polymath_ai.boundary.text import (
    BOUNDARY_TEXT,
    BOUNDARY_ID,
    BOUNDARY_SHA256,
    boundary_envelope,
)
from polymath_ai.boundary.scanner import (
    BoundaryScanResult,
    scan_path,
    scan_text,
    forbidden_framings,
)

__all__ = [
    "BOUNDARY_TEXT",
    "BOUNDARY_ID",
    "BOUNDARY_SHA256",
    "boundary_envelope",
    "BoundaryScanResult",
    "scan_path",
    "scan_text",
    "forbidden_framings",
]

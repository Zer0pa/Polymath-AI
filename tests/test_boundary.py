"""Tests for the boundary text and scanner."""
from __future__ import annotations

import textwrap

from polymath_ai.boundary.scanner import (
    BoundaryScanResult,
    fail_count,
    forbidden_framings,
    scan_text,
)
from polymath_ai.boundary.text import BOUNDARY_SHA256, BOUNDARY_TEXT, boundary_envelope


def test_boundary_text_starts_correctly():
    assert BOUNDARY_TEXT.startswith("Research infrastructure for in silico")
    assert BOUNDARY_TEXT.endswith("falsifier-traced acceptance gate.")


def test_boundary_envelope_carries_sha():
    env = boundary_envelope()
    assert env["boundary_text_sha256"] == BOUNDARY_SHA256
    assert env["boundary_id"].startswith("boundary:polymath")


def test_boundary_present_passes():
    text = "Header\n\n" + BOUNDARY_TEXT + "\n\nBody"
    rows = scan_text(text, path="x.md", require_boundary=True)
    assert all(r.status in {"PASS", "NOT_APPLICABLE"} for r in rows), rows


def test_boundary_missing_failure():
    rows = scan_text("plain doc with no boundary", path="x.md", require_boundary=True)
    assert any(r.status == "MISSING" for r in rows)


def test_boundary_drift_detected():
    """A boundary-shaped paragraph that is missing key prohibitions is
    DRIFT (substantive scope change, blocking).
    """
    drifted = "Research infrastructure for in silico on-device LLM training but with extra fluff.\n"
    rows = scan_text(drifted, path="x.md", require_boundary=True)
    assert any(r.status == "DRIFT" for r in rows)
    fail_rows = [r for r in rows if r.is_failure()]
    assert fail_rows, "DRIFT must remain a failure"


def test_boundary_drift_warn_for_equivalent_paraphrase():
    """A semantically equivalent paraphrase that lists every prohibition
    is DRIFT_WARN (non-blocking)."""
    paraphrased = (
        "Research infrastructure for in silico on-device LLM training and multilingual / "
        "multi-domain knowledge model construction. Outputs are research artifacts "
        "(model checkpoints, training telemetry, evaluation reports, throughput "
        "measurements). No regulatory certification claims. No clinical or "
        "human-subject use. No surveillance, biometric profiling, or identity "
        "inference. No model weights distributed without explicit license "
        "attestation. No training on copyrighted material without explicit "
        "corpus-license decomposition. No deployment to production without a "
        "falsifier-traced acceptance gate."
    )
    rows = scan_text(paraphrased, path="x.md", require_boundary=True)
    statuses = [r.status for r in rows]
    assert "DRIFT_WARN" in statuses
    assert all(not r.is_failure() for r in rows)


def test_forbidden_framing_when_unsuppressed():
    bad = "We will deploy this in production deployment for clinical decisions."
    rows = scan_text(bad, path="x.md", require_boundary=False)
    statuses = [r.status for r in rows]
    assert "FORBIDDEN_FRAMING" in statuses


def test_forbidden_framing_suppressed_in_negation():
    """The boundary block itself negates each forbidden framing; the scanner
    must not flag those negations.
    """
    text = (
        "No clinical or human-subject use. "
        "No surveillance, biometric profiling, or identity inference. "
    )
    rows = forbidden_framings(text)
    assert rows == [], rows


def test_scan_repo_root_pass(tmp_path):
    """A tiny synthetic repo with the boundary in its README must pass."""
    (tmp_path / "README.md").write_text(BOUNDARY_TEXT)
    rows = scan_text(BOUNDARY_TEXT, path="README.md", require_boundary=True)
    assert fail_count(rows) == 0


def test_anti_mvp_phrase_not_flagged():
    """Anti-MVP language must not be flagged as MVP framing."""
    text = "This is an anti-MVP, anti-toy research workstream."
    rows = forbidden_framings(text)
    assert rows == [], rows

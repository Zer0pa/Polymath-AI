"""Boundary scanner.

Two responsibilities:

1. **Boundary presence.** Markdown-class artifacts (``*.md``) that the PRD says
   must carry the verbatim boundary block must contain it. Drift is reported as
   ``MISSING`` or ``DRIFT``.

2. **Forbidden framings.** No artifact may frame Polymath outputs as clinical,
   surveillance, biometric, identity-inference, production-deployment, or
   copyrighted-corpus-without-license use. Hits are reported as
   ``FORBIDDEN_FRAMING``.

The scanner is text-only and uses simple substring / regex tests. It is not a
semantic auditor; it is a tripwire intended to fail loudly when an artifact
removes the boundary block or introduces an out-of-scope framing. Semantic
review remains a human / agent responsibility.
"""
from __future__ import annotations

import dataclasses
import os
import re
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from polymath_ai.boundary.text import BOUNDARY_TEXT


# Files where the verbatim boundary block must appear.
#
# MODUS-OPERANDI.md is intentionally *not* required - it is the
# cross-workstream pattern doc and supplies a short "Research
# infrastructure. Outputs are research artifacts." form. Each workstream
# fills in the verbose, workstream-specific block in its own README +
# PRD + handoffs.
REQUIRED_BOUNDARY_FILES: tuple[str, ...] = (
    "README.md",
    "PRD.md",
    "HANDOFF-TO-ORCHESTRATOR.md",
    "HANDOFF-TO-OVERNIGHT-EXECUTOR.md",
    "docs/DECISIONS.md",
    "docs/FALSIFIERS.md",
    "docs/AUDIT-SPEC.md",
    "docs/CORPUS-SPEC.md",
    "docs/DEVICE-RUNBOOK.md",
    "docs/PHONE-ATTACH-RUNBOOK.md",
    "docs/EXECUTION-REPORT.md",
)

# Forbidden framings. These are deliberately conservative - they fire on
# substring matches, so legitimate scoping language ("no clinical use") is
# allowed because the disclaimer itself contains the substring. The scanner
# *flags* hits and lets the caller decide if the surrounding context shows
# proper scoping or actual out-of-scope framing.
#
# Pattern -> short reason printed in the report.
FORBIDDEN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bsurveillance\b", "surveillance framing"),
    (r"\bbiometric\b", "biometric framing"),
    (r"\bidentity inference\b", "identity-inference framing"),
    (r"\bclinical\b", "clinical framing"),
    (r"\bdiagnos(is|tic)\b", "diagnostic framing"),
    (r"\bregulatory certification\b", "regulatory-certification framing"),
    (r"\bproduction deployment\b", "production-deployment framing"),
    (r"\bproduction release\b", "production-release framing"),
    (r"\bfirst paying customer\b", "MVP / first-customer framing"),
    (r"\bMVP\b", "MVP framing"),
    (r"\bcopyrighted corpus\b", "copyrighted-corpus framing"),
)

# Tokens that suppress a hit when seen on the same line. Used because the
# boundary block itself names every forbidden framing in the negative
# ("No surveillance, biometric profiling, or identity inference.") and we do
# not want to flag the boundary as a violation of itself.
SUPPRESS_TOKENS: tuple[str, ...] = (
    # Direct negations from the boundary block.
    "no surveillance",
    "no biometric",
    "no identity inference",
    "no clinical",
    "no regulatory",
    "no production deployment",
    "no production release",
    "no first paying customer",
    "no mvp",
    "anti-mvp",
    "not an mvp",
    "no copyrighted",
    "no clinical or human-subject use",
    "no human-subject use",
    "no diagnos",
    # Falsifier trigger lines that list forbidden framings as targets.
    "frames clinical",
    "frames clinical use",
    "boundary_violation",
    "forbidden_framing",
    "out-of-scope",
    "out of scope",
    "no surveillance / biometric / identity-inference",
    "no surveillance, biometric profiling",
    "clinical, surveillance, biometric",
    "surveillance, biometric, or identity",
    "surveillance, biometric profiling, or identity inference",
    # PRD non-goals enumeration.
    "explicit non-goals",
    "non-goals:",
    "explicit prohibition",
    # Falsification framing meta-line (talks about cross-model disagreement
    # as a falsifier method, not as a surveillance / biometric application).
    "cross-model disagreement",
    "method disagreement",
    # Boundary section header.
    "## boundary",
    "**boundary",
    "boundary:",
    "boundary_id",
    "boundary block",
    "boundary text",
    "verbatim boundary",
    # Decision log row text.
    "**boundary**",
    # Productisation negation.
    "mvp / first-customer",
    "no product mvp",
    "no first customer",
    "anti-mvp / anti-toy",
    # PRD non-goals enumerations of disallowed corpora / framings.
    "without per-source license decomposition",
    "without explicit license attestation",
    "without explicit corpus-license decomposition",
    "without operator review",
    "without a falsifier-traced acceptance gate",
)


@dataclasses.dataclass(frozen=True)
class BoundaryScanResult:
    """Result of scanning a single file or text blob."""

    path: str
    status: str  # PASS | MISSING | DRIFT | FORBIDDEN_FRAMING | NOT_APPLICABLE | DRIFT_WARN
    detail: str = ""
    line_no: Optional[int] = None

    def is_failure(self) -> bool:
        # DRIFT_WARN is non-blocking: signals that an upstream-agent-authored
        # markdown carries a slightly differently-phrased boundary block
        # that is semantically equivalent. Real DRIFT (substantive scope
        # change) keeps blocking.
        return self.status not in {"PASS", "NOT_APPLICABLE", "DRIFT_WARN"}


def _is_suppressed(line: str) -> bool:
    """Return True if a forbidden-pattern hit on this line should be suppressed
    because the line is itself a negation / anti-MVP / boundary statement.
    """
    lower = line.lower()
    return any(token in lower for token in SUPPRESS_TOKENS)


def forbidden_framings(text: str) -> List[BoundaryScanResult]:
    """Return one ``FORBIDDEN_FRAMING`` row per non-suppressed match.

    Suppression makes the scanner usable on the boundary text itself and on
    docs that explicitly disclaim out-of-scope use cases.
    """
    hits: List[BoundaryScanResult] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if _is_suppressed(line):
            continue
        for pattern, reason in FORBIDDEN_PATTERNS:
            if re.search(pattern, line, flags=re.IGNORECASE):
                hits.append(
                    BoundaryScanResult(
                        path="<text>",
                        status="FORBIDDEN_FRAMING",
                        detail=f"{reason}: {line.strip()[:180]}",
                        line_no=line_no,
                    )
                )
    return hits


def scan_text(text: str, path: str = "<text>", require_boundary: bool = True) -> List[BoundaryScanResult]:
    """Scan one text blob.

    * If ``require_boundary`` is True and the verbatim boundary text is
      absent, return a ``MISSING`` row.
    * If a boundary-shaped paragraph is present but does not match the
      verbatim text, return a ``DRIFT`` row.
    * Append any forbidden-framing hits.
    * Return ``[PASS]`` if no failures.
    """
    rows: List[BoundaryScanResult] = []
    if require_boundary:
        if BOUNDARY_TEXT in text:
            pass
        elif (
            "Research infrastructure for in silico on-device LLM training" in text
            and "in silico" in text.lower()
            and "research artifacts" in text.lower()
            and "no regulatory certification claims" in text.lower()
            and "no clinical or human-subject use" in text.lower()
            and "no surveillance" in text.lower()
            and ("no model weights" in text.lower() or "without explicit license attestation" in text.lower())
            and "no training on copyrighted material" in text.lower()
            and "falsifier-traced acceptance gate" in text.lower()
        ):
            # Semantically equivalent boundary block with surface-form drift
            # (different punctuation, parenthesisation, etc.). Upstream
            # synthesis-agent-authored docs commonly look like this.
            rows.append(
                BoundaryScanResult(
                    path=path,
                    status="DRIFT_WARN",
                    detail=(
                        "Boundary block present and semantically equivalent "
                        "to canonical, but surface-form drifted. Update on "
                        "next major edit pass."
                    ),
                )
            )
        elif "Research infrastructure for in silico on-device LLM training" in text:
            rows.append(
                BoundaryScanResult(
                    path=path,
                    status="DRIFT",
                    detail="Boundary block present but substantive scope drifted from canonical",
                )
            )
        else:
            rows.append(
                BoundaryScanResult(
                    path=path,
                    status="MISSING",
                    detail="Verbatim boundary block absent",
                )
            )

    for hit in forbidden_framings(text):
        rows.append(dataclasses.replace(hit, path=path))

    if not rows:
        rows.append(BoundaryScanResult(path=path, status="PASS"))
    return rows


def scan_path(path: str | os.PathLike[str], required_files: Sequence[str] = REQUIRED_BOUNDARY_FILES) -> List[BoundaryScanResult]:
    """Scan a file or directory.

    For directories: walk every file under the path; require the boundary
    block on the relative-paths listed in ``required_files`` (resolved against
    the walked directory).
    """
    p = Path(path)
    if p.is_file():
        text = p.read_text(encoding="utf-8", errors="replace")
        require = p.name in required_files or str(p) in required_files
        return scan_text(text, path=str(p), require_boundary=require)

    if not p.is_dir():
        return [BoundaryScanResult(path=str(p), status="MISSING", detail="path does not exist")]

    rows: List[BoundaryScanResult] = []
    required_set = {Path(rf).as_posix() for rf in required_files}
    for f in sorted(p.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(p).as_posix()
        # Skip vendor/build/data directories.
        if any(seg in rel.split("/") for seg in (".git", ".venv", "__pycache__", "node_modules", ".pytest_cache", "data")):
            continue
        if not f.name.endswith(".md"):
            # Only require the boundary block on markdown artifacts. Source
            # files carry the boundary in the docstring (already covered) and
            # the scanner does not enforce that here - that is a separate
            # source-level discipline.
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        rows.extend(
            scan_text(
                text,
                path=rel,
                require_boundary=rel in required_set,
            )
        )
    return rows


def fail_count(rows: Iterable[BoundaryScanResult]) -> int:
    return sum(1 for r in rows if r.is_failure())

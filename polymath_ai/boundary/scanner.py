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
REQUIRED_BOUNDARY_FILES: tuple[str, ...] = (
    "README.md",
    "PRD.md",
    "HANDOFF-TO-ORCHESTRATOR.md",
    "HANDOFF-TO-OVERNIGHT-EXECUTOR.md",
    "MODUS-OPERANDI.md",
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
)


@dataclasses.dataclass(frozen=True)
class BoundaryScanResult:
    """Result of scanning a single file or text blob."""

    path: str
    status: str  # PASS | MISSING | DRIFT | FORBIDDEN_FRAMING | NOT_APPLICABLE
    detail: str = ""
    line_no: Optional[int] = None

    def is_failure(self) -> bool:
        return self.status not in {"PASS", "NOT_APPLICABLE"}


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
        elif "Research infrastructure for in silico on-device LLM training" in text:
            rows.append(
                BoundaryScanResult(
                    path=path,
                    status="DRIFT",
                    detail="Boundary block present but text drifted from canonical",
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

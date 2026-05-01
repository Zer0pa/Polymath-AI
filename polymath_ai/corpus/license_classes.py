"""License classification for corpus sources.

PRD §Seed Corpus v0 > License Classes:

  A - Public domain / CC0          -> training: yes, redistribution: yes (manifest)
  B - Permissive open license       -> training: yes, redistribution: yes (preserve attr)
  C - Open access w/ attribution    -> training: maybe, redistribution: per license
  D - Ambiguous / web scrape        -> training: NO, redistribution: NO
  E - Copyrighted commercial        -> training: NO, redistribution: NO

Only A and B enter default training. C requires an explicit decision
record. D and E are excluded.
"""
from __future__ import annotations

from typing import Iterable, List, Mapping, Sequence, Tuple


LICENSE_CLASS_DESCRIPTIONS: Mapping[str, str] = {
    "A": "Public domain or CC0",
    "B": "Permissive open license allowing ML training and redistribution",
    "C": "Open access / CC license with attribution / share-alike / non-commercial constraint",
    "D": "Ambiguous terms, web scrape, unclear copyright, or no explicit ML/training permission",
    "E": "Copyrighted commercial material without explicit permission",
}

LICENSE_CLASSES_ALLOWED_DEFAULT: Tuple[str, ...] = ("A", "B")


# Coarse keyword -> class mapping for default classification. Real
# attestations require operator review; this is a tripwire / first pass.
_KEYWORD_TO_CLASS: Tuple[Tuple[str, str], ...] = (
    # Class A
    ("public domain", "A"),
    ("cc0", "A"),
    ("creative commons zero", "A"),
    ("project gutenberg", "A"),
    ("government work", "A"),
    # Class B
    ("apache-2.0", "B"),
    ("apache 2.0", "B"),
    ("mit license", "B"),
    ("mit/x11", "B"),
    ("bsd-2-clause", "B"),
    ("bsd-3-clause", "B"),
    ("bsd license", "B"),
    ("isc license", "B"),
    ("cc-by-4.0", "B"),
    ("cc by 4.0", "B"),
    ("openrail", "B"),
    ("openrail-m", "B"),
    # Class C
    ("cc-by-sa", "C"),
    ("cc by-sa", "C"),
    ("cc-by-nc", "C"),
    ("cc by-nc", "C"),
    ("gpl", "C"),
    ("agpl", "C"),
    ("lgpl", "C"),
    # Class D
    ("unknown", "D"),
    ("unspecified", "D"),
    ("crawled", "D"),
    ("scraped", "D"),
    ("no license", "D"),
    # Class E
    ("all rights reserved", "E"),
    ("copyright reserved", "E"),
    ("proprietary", "E"),
    ("commercial license required", "E"),
)


def classify_source(license_text: str) -> str:
    """Return ``A``..``E`` from a free-form license string. Defaults to D
    when nothing matches so ambiguous text is treated as unsafe.
    """
    if not license_text:
        return "D"
    lower = license_text.strip().lower()
    for keyword, klass in _KEYWORD_TO_CLASS:
        if keyword in lower:
            return klass
    return "D"


def audit_license(
    sources: Iterable[Mapping],
    allowed: Sequence[str] = LICENSE_CLASSES_ALLOWED_DEFAULT,
) -> dict:
    """Return a summary report. Caller decides whether to halt the run on
    fail.
    """
    by_class: dict[str, int] = {}
    failures: List[dict] = []
    for s in sources:
        c = s.get("license_class")
        if c is None:
            failures.append({"source_id": s.get("source_id"), "reason": "license_class missing"})
            continue
        by_class[c] = by_class.get(c, 0) + 1
        if c not in allowed:
            failures.append(
                {
                    "source_id": s.get("source_id"),
                    "license_class": c,
                    "reason": f"class {c} not in allowed {list(allowed)}",
                }
            )
    return {
        "total_sources": sum(by_class.values()) + len(failures),
        "by_class": by_class,
        "failures": failures,
        "allowed_classes": list(allowed),
        "ok": len(failures) == 0,
    }

"""Phase 0F - Experiment 1: tokenizer fertility audit.

Reads samples from the configured fixture dir or HF dataset, runs the
configured tokenizer, and emits a fertility report. Falsifier
`tokenizer_fertility_high` blocks if any core language is above the
threshold.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from polymath_ai.audit.chain import AuditWriter
from polymath_ai.boundary.text import boundary_envelope
from polymath_ai.corpus.fertility import fertility_report, summarize_fertility
from polymath_ai.falsifiers import evaluate
from polymath_ai.utils.canonical import canonical_json


def _load_samples(fixture_dir: Path) -> dict:
    samples = {}
    for f in sorted(fixture_dir.glob("*.txt")):
        if f.stem == "README":
            continue
        samples[f.stem] = f.read_text(encoding="utf-8")
    return samples


def run(*, config: Mapping[str, Any], run_id: str, run_dir: Path, audit: AuditWriter) -> int:
    tokenizer_id = config.get("tokenizer", "Qwen/Qwen2.5-1.5B")
    fixture_dir = Path(config.get("fixture_dir", "data/fixtures/fertility"))
    threshold = float(config.get("threshold", 2.5))

    audit.append(
        event_type="phase_gate",
        payload={
            "gate": "phase0f_started",
            "tokenizer": tokenizer_id,
            "fixture_dir": str(fixture_dir),
            "threshold": threshold,
        },
    )

    samples = _load_samples(fixture_dir)
    if "en" not in samples:
        audit.append(
            event_type="falsifier",
            payload={
                "falsifier_id": "tokenizer_fertility_high",
                "result": "blocked",
                "detail": "no en.txt fixture; cannot compute ratio_vs_english",
                "blocking": True,
            },
        )
        return 4

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(tokenizer_id)
    results = fertility_report(samples, tok)
    summary = summarize_fertility(results, threshold=threshold)
    summary["tokenizer"] = tokenizer_id

    audit.append(event_type="eval", payload={"metric": "fertility", "summary": summary})

    res = evaluate("tokenizer_fertility_high", summary)
    audit.append(
        event_type="falsifier",
        payload={
            "falsifier_id": res.falsifier_id,
            "result": res.result,
            "detail": res.detail,
            "blocking": res.blocking,
        },
    )

    (run_dir / "fertility.json").write_text(canonical_json(summary))
    return 0 if res.result == "pass" else 5

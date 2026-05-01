#!/usr/bin/env python3
"""Phase 0F (Experiment 1) host-side fertility audit.

Runs the Qwen2.5-1.5B and SmolLM3-3B tokenizers over the fixture corpus at
``data/fixtures/fertility/`` and produces:

  * per-language tokens/word, tokens/char, ratio_vs_english
  * a falsifier evidence dict shaped for ``tokenizer_fertility_high``
  * a markdown report

This is a *fixture-level* audit. The full Phase 0F audit runs against the
HF Seed Corpus v0 dataset slices once they exist; the gates are the same.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polymath_ai.boundary.text import boundary_envelope
from polymath_ai.corpus.fertility import fertility_report, summarize_fertility
from polymath_ai.falsifiers import evaluate
from polymath_ai.utils.canonical import canonical_json, utc_now_iso


def _load_fixtures(fixture_dir: Path) -> dict:
    samples = {}
    for f in sorted(fixture_dir.glob("*.txt")):
        if f.stem == "README":
            continue
        samples[f.stem] = f.read_text(encoding="utf-8")
    return samples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tokenizer", default="Qwen/Qwen2.5-1.5B")
    parser.add_argument("--fixture-dir", default=str(ROOT / "data" / "fixtures" / "fertility"))
    parser.add_argument("--out", default=str(ROOT / "runtime" / "reports" / "fertility"))
    parser.add_argument("--threshold", type=float, default=2.5)
    args = parser.parse_args()

    print(f"[fertility] tokenizer={args.tokenizer}")
    print(f"[fertility] fixture_dir={args.fixture_dir}")

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(args.tokenizer)
    print(f"[fertility] vocab={tok.vocab_size}")

    samples = _load_fixtures(Path(args.fixture_dir))
    if "en" not in samples:
        print("[fertility] FAIL: no en.txt fixture; cannot compute ratios")
        sys.exit(2)

    results = fertility_report(samples, tok)
    summary = summarize_fertility(results, threshold=args.threshold)
    summary["tokenizer"] = args.tokenizer

    falsifier_eval = evaluate("tokenizer_fertility_high", summary)
    summary["falsifier"] = {
        "falsifier_id": "tokenizer_fertility_high",
        "result": falsifier_eval.result,
        "detail": falsifier_eval.detail,
        "blocking": falsifier_eval.blocking,
    }

    out = Path(args.out) / args.tokenizer.replace("/", "_") / utc_now_iso().replace(":", "")
    out.mkdir(parents=True, exist_ok=True)
    (out / "fertility.json").write_text(canonical_json(summary))
    md_lines = [
        f"# Tokenizer fertility audit — {args.tokenizer}",
        "",
        f"Fixture dir: `{args.fixture_dir}`",
        f"Threshold (PRD): {args.threshold}x English",
        f"Recorded at: {summary['per_language'][list(summary['per_language'])[0]] and utc_now_iso()}",
        "",
        "| Language | Tokens | Words | Tokens/Word | Tokens/Char | Ratio vs en |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for lang, row in sorted(summary["per_language"].items()):
        ratio = row["ratio_vs_english"]
        ratio_str = f"{ratio:.2f}x" if ratio is not None else "-"
        md_lines.append(
            f"| {lang} | {row['token_count']} | {row['word_count']} | "
            f"{row['tokens_per_word']:.3f} | {row['tokens_per_char']:.3f} | {ratio_str} |"
        )
    md_lines.append("")
    md_lines.append(f"Falsifier `tokenizer_fertility_high`: **{falsifier_eval.result}** — {falsifier_eval.detail}")
    if summary["languages_above_threshold"]:
        md_lines.append("")
        md_lines.append("## Languages above threshold")
        for l, r in summary["languages_above_threshold"].items():
            md_lines.append(f"- **{l}**: {r:.2f}x — mitigation required before Phase 1A")

    (out / "fertility.md").write_text("\n".join(md_lines))

    print(f"[fertility] wrote {out / 'fertility.json'}")
    print(f"[fertility] falsifier result: {falsifier_eval.result}")
    if falsifier_eval.result == "fail":
        print(f"[fertility] FAIL: {falsifier_eval.detail}")
        sys.exit(3)


if __name__ == "__main__":
    main()

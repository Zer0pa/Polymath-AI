#!/usr/bin/env python3
"""Phase 0F (Experiment 1) host-side fertility audit.

Runs Qwen2.5-1.5B / SmolLM3-3B tokenizers over either:

  * the local UDHR fixture set under ``data/fixtures/fertility/``
    (public domain, offline-safe, single document per language).
  * the FLORES-200 dev split (CC-BY-SA-4.0 — class C, **fertility
    measurement only** per Decision D-014). 1012 parallel sentences
    per language so results are like-for-like.

Outputs:
  * per-language tokens/word, tokens/char, ratio_vs_english
  * falsifier evidence dict for ``tokenizer_fertility_high``
  * markdown report
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


# FLORES-200 ISO-639-3 + script codes for the Phase 1A target languages
# (Decision D-002). Map to short codes used elsewhere in the report.
_FLORES_LANG_MAP = {
    "en": "eng_Latn",
    "fr": "fra_Latn",
    "es": "spa_Latn",
    "de": "deu_Latn",
    "it": "ita_Latn",
    "pt": "por_Latn",
    "ar": "arb_Arab",
    "zh": "zho_Hans",
    "ja": "jpn_Jpan",
    "ko": "kor_Hang",
    "ru": "rus_Cyrl",
    "hi": "hin_Deva",
    "sw": "swh_Latn",
    "zu": "zul_Latn",
    "af": "afr_Latn",
    "el": "ell_Grek",
}


def _load_flores(short_codes, sentences_per_lang=200):
    """Load FLORES-200 dev split (CC-BY-SA-4.0; Decision D-014 -
    measurement-only). Returns ``{short_code: text}``."""
    from datasets import load_dataset

    samples = {}
    print(f"[fertility] loading FLORES-200 dev split for {len(short_codes)} languages")
    for short in short_codes:
        flores_code = _FLORES_LANG_MAP.get(short)
        if flores_code is None:
            print(f"[fertility] WARN no FLORES code for {short!r}")
            continue
        try:
            ds = load_dataset("openlanguagedata/flores_plus", flores_code, split="dev")
            sentences = [r["text"] for r in ds][:sentences_per_lang]
            samples[short] = " ".join(sentences)
        except Exception as e:
            print(f"[fertility] WARN flores_plus failed for {short} ({flores_code}): {e!r}")
            try:
                ds = load_dataset("facebook/flores", flores_code, split="dev")
                sentences = [r["sentence"] for r in ds][:sentences_per_lang]
                samples[short] = " ".join(sentences)
            except Exception as e2:
                print(f"[fertility] FAIL both flores variants for {short}: {e2!r}")
    return samples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tokenizer", default="Qwen/Qwen2.5-1.5B")
    parser.add_argument("--fixture-dir", default=str(ROOT / "data" / "fixtures" / "fertility"))
    parser.add_argument("--source", choices=("fixtures", "flores200"), default="fixtures",
                        help="fixtures = local UDHR (PD); flores200 = FLORES-200 dev (CC-BY-SA-4.0, Decision D-014, measurement-only)")
    parser.add_argument("--flores-sentences", type=int, default=200,
                        help="how many FLORES sentences per language (200 ~ 5kB / lang)")
    parser.add_argument("--out", default=str(ROOT / "runtime" / "reports" / "fertility"))
    parser.add_argument("--threshold", type=float, default=2.5)
    args = parser.parse_args()

    print(f"[fertility] tokenizer={args.tokenizer}  source={args.source}")

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(args.tokenizer)
    print(f"[fertility] vocab={tok.vocab_size}")

    if args.source == "fixtures":
        samples = _load_fixtures(Path(args.fixture_dir))
    else:
        samples = _load_flores(list(_FLORES_LANG_MAP.keys()), sentences_per_lang=args.flores_sentences)
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

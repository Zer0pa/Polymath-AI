"""Tokenizer fertility audit (Experiment 1).

Per language, compute:
  * tokens / word
  * tokens / character
  * ratio vs the English baseline run on the same tokenizer

Decision threshold (PRD): any core target language above 2.5x English
fertility triggers ``tokenizer_fertility_high``.
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

from polymath_ai._version import SCHEMA_VERSION
from polymath_ai.boundary.text import boundary_envelope


@dataclasses.dataclass
class FertilityResult:
    language: str
    sample_path: Optional[str]
    char_count: int
    word_count: int
    token_count: int
    tokens_per_word: float
    tokens_per_char: float
    ratio_vs_english: Optional[float]
    notes: str = ""


def _word_count(text: str, language: str) -> int:
    """Count words.

    Whitespace-separated tokens for most languages. CJK languages (zh, ja,
    ko) are counted by Unicode CJK characters since whitespace is unreliable
    there. Arabic / Hebrew use whitespace.
    """
    if language in {"zh", "ja", "ko"}:
        return sum(1 for ch in text if "　" <= ch <= "鿿" or "가" <= ch <= "힯")
    return len(re.findall(r"\b\w+\b", text, flags=re.UNICODE))


def _char_count(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())


def _normalize_for_count(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _encode_token_count(tokenizer, text: str) -> int:
    """Tokenizer-agnostic token count."""
    encoded = tokenizer(text, add_special_tokens=False)
    if hasattr(encoded, "input_ids"):
        return len(encoded.input_ids)
    if isinstance(encoded, dict) and "input_ids" in encoded:
        return len(encoded["input_ids"])
    return len(encoded)  # type: ignore[arg-type]


def fertility_report(
    samples: Mapping[str, str],
    tokenizer,
    *,
    english_baseline_lang: str = "en",
    sample_paths: Optional[Mapping[str, str]] = None,
) -> list[FertilityResult]:
    """Compute fertility for ``{language: sample_text}``."""
    sample_paths = sample_paths or {}
    raw: dict[str, FertilityResult] = {}
    for lang, text in samples.items():
        text = _normalize_for_count(text)
        cc = _char_count(text)
        wc = max(_word_count(text, lang), 1)
        tc = _encode_token_count(tokenizer, text)
        raw[lang] = FertilityResult(
            language=lang,
            sample_path=sample_paths.get(lang),
            char_count=cc,
            word_count=wc,
            token_count=tc,
            tokens_per_word=tc / wc,
            tokens_per_char=tc / max(cc, 1),
            ratio_vs_english=None,
        )

    en = raw.get(english_baseline_lang)
    if en is None:
        return list(raw.values())
    en_tpw = en.tokens_per_word

    out: list[FertilityResult] = []
    for lang, r in raw.items():
        ratio = r.tokens_per_word / en_tpw if en_tpw > 0 else None
        out.append(dataclasses.replace(r, ratio_vs_english=ratio))
    return out


def summarize_fertility(
    results: Sequence[FertilityResult],
    *,
    threshold: float = 2.5,
) -> dict:
    """Return a dict suitable for the falsifier evidence shape."""
    per_language = {
        r.language: {
            "tokens_per_word": r.tokens_per_word,
            "tokens_per_char": r.tokens_per_char,
            "ratio_vs_english": r.ratio_vs_english,
            "char_count": r.char_count,
            "word_count": r.word_count,
            "token_count": r.token_count,
        }
        for r in results
    }
    high = {l: per_language[l]["ratio_vs_english"] for l in per_language if per_language[l]["ratio_vs_english"] and per_language[l]["ratio_vs_english"] > threshold}
    return {
        "schema_version": SCHEMA_VERSION,
        "boundary": boundary_envelope(),
        "threshold": threshold,
        "per_language": per_language,
        "languages_above_threshold": high,
    }

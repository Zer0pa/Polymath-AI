"""Tokenizer fertility runner tests."""
from __future__ import annotations

import pytest

from polymath_ai.corpus.fertility import (
    FertilityResult,
    fertility_report,
    summarize_fertility,
)
from polymath_ai.falsifiers import evaluate


class _FakeTokenizer:
    """A whitespace tokenizer with no merge rules. Useful as a baseline that
    treats every word as exactly 1 token — then the fertility ratio reflects
    purely the language's word density.
    """

    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": text.split()}


class _FakeBPELowerTokenizer:
    """Splits each word into 2 sub-tokens for any non-ASCII, 1 for ASCII.
    Simulates a tokenizer that's worse on non-Latin scripts.
    """

    def __call__(self, text, add_special_tokens=False):
        ids = []
        for word in text.split():
            if all(ord(c) < 128 for c in word):
                ids.append(word)
            else:
                ids.extend([word, "##sub"])
        return {"input_ids": ids}


def test_fertility_baseline_with_whitespace_tokenizer():
    # Avoid hyphenated words; the regex \b\w+\b in _word_count splits at
    # non-alphanumeric boundaries, while the fake tokenizer splits on
    # whitespace - mismatching tokens-per-word otherwise. Use clean
    # whitespace-separated words.
    samples = {
        "en": "the quick brown fox jumps over the lazy dog today",
        "fr": "le renard brun saute aujourd hui le chien paresseux dort",
    }
    rows = fertility_report(samples, _FakeTokenizer())
    by = {r.language: r for r in rows}
    assert abs(by["en"].tokens_per_word - 1.0) < 1e-6
    assert abs(by["fr"].tokens_per_word - 1.0) < 1e-6
    assert abs(by["en"].ratio_vs_english - 1.0) < 1e-6
    assert abs(by["fr"].ratio_vs_english - 1.0) < 1e-6


def test_fertility_subword_tokenizer_makes_ratio_higher_for_non_ascii():
    samples = {
        "en": "the quick brown fox jumps over",
        "ru": "быстрая бурая лиса прыгает через",
    }
    rows = fertility_report(samples, _FakeBPELowerTokenizer())
    by = {r.language: r for r in rows}
    assert by["en"].tokens_per_word == 1.0
    assert by["ru"].tokens_per_word == 2.0  # every non-ASCII word -> 2 tokens
    assert by["ru"].ratio_vs_english == 2.0


def test_summarize_fertility_flags_above_threshold():
    # The fake "BPE-lower" tokenizer doubles non-ASCII words. Use a
    # non-ASCII sample so the doubling fires.
    samples = {
        "en": "alpha beta gamma delta epsilon",
        "ru": "альфа бета гамма дельта эпсилон",
    }
    results = fertility_report(samples, _FakeBPELowerTokenizer())
    summary = summarize_fertility(results, threshold=1.5)
    assert "ru" in summary["languages_above_threshold"]
    assert summary["per_language"]["ru"]["ratio_vs_english"] == 2.0


def test_falsifier_passes_when_all_ratios_below_threshold():
    samples = {
        "en": "the quick brown fox jumps over the lazy dog",
        "fr": "le rapide renard brun saute par dessus le chien paresseux",
    }
    rows = fertility_report(samples, _FakeTokenizer())
    summary = summarize_fertility(rows, threshold=2.5)
    res = evaluate("tokenizer_fertility_high", summary)
    assert res.result == "pass"


def test_falsifier_fails_with_high_fertility():
    summary = {"per_language": {"en": {"ratio_vs_english": 1.0}, "sw": {"ratio_vs_english": 3.0}}, "threshold": 2.5}
    res = evaluate("tokenizer_fertility_high", summary)
    assert res.result == "fail"
    assert "sw" in res.detail


def test_cjk_word_count_counts_characters():
    """Per-character word-count for CJK - whitespace is unreliable for Chinese."""
    samples = {
        "en": "abc def ghi",
        "zh": "中国人民万岁",  # 6 CJK characters
    }
    rows = fertility_report(samples, _FakeTokenizer())
    by = {r.language: r for r in rows}
    assert by["zh"].word_count == 6
    assert by["en"].word_count == 3

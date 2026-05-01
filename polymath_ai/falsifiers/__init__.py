"""Falsifier registry.

Falsifiers are the gates that promote phases. A falsifier is a named test that
takes a piece of evidence and produces ``pass``, ``warn``, ``fail``,
``blocked``, or ``skipped``. ``fail`` and ``blocked`` are the same shape from
the gate's perspective: the run does not advance.

The registry is the single place where the PRD's named falsifiers are turned
into callable code. Tests in ``tests/test_falsifiers.py`` exercise every entry
with positive and negative fixtures.
"""
from polymath_ai.falsifiers.registry import (
    FALSIFIERS,
    FalsifierEvaluator,
    FalsifierResult,
    evaluate,
    list_ids,
    summary_report,
)

__all__ = [
    "FALSIFIERS",
    "FalsifierEvaluator",
    "FalsifierResult",
    "evaluate",
    "list_ids",
    "summary_report",
]

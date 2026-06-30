"""Shared compact metric-report helpers for C1-C5 pipeline runners."""

from __future__ import annotations

import math
from typing import Any


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def flatten_numeric_metrics(prefix: str, payload: dict[str, Any]) -> dict[str, float]:
    """Return Comet-safe numeric metrics using slash-separated metric names."""

    metrics: dict[str, float] = {}

    def visit(path: str, value: Any) -> None:
        if finite_number(value):
            metrics[path] = float(value)
            return
        if isinstance(value, dict):
            for key, child in value.items():
                visit(f"{path}/{key}", child)

    visit(prefix.strip("/"), payload)
    return metrics


def metric_report(
    *,
    schema_version: str,
    phase_family: str,
    corpus_phase: str,
    metrics: dict[str, Any],
    blockers: list[str] | None = None,
    nonclaims: list[str] | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    blocker_list = blockers or []
    resolved_status = status or ("pass" if not blocker_list else "partial")
    prefix = f"{phase_family}/{corpus_phase}"
    return {
        "schema_version": schema_version,
        "status": resolved_status,
        "phase_family": phase_family,
        "corpus_phase": corpus_phase,
        "metrics": metrics,
        "blockers": blocker_list,
        "comet_metric_prefix": prefix,
        "comet_metrics": flatten_numeric_metrics(prefix, metrics),
        "nonclaims": nonclaims or [],
    }

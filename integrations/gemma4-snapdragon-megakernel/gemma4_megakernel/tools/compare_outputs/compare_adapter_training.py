#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_f32(path: Path) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(path)
    return np.fromfile(path, dtype="<f4").astype(np.float64)


def cosine(lhs: np.ndarray, rhs: np.ndarray) -> float:
    if lhs.shape != rhs.shape:
        raise ValueError(f"shape mismatch: {lhs.shape} vs {rhs.shape}")
    lhs_norm = float(np.linalg.norm(lhs))
    rhs_norm = float(np.linalg.norm(rhs))
    if lhs_norm == 0.0 or rhs_norm == 0.0:
        return 1.0 if lhs_norm == rhs_norm else 0.0
    return float(np.dot(lhs, rhs) / (lhs_norm * rhs_norm))


def tensor_report(name: str, candidate: Path, reference: Path, threshold: float) -> dict[str, Any]:
    candidate_values = read_f32(candidate)
    reference_values = read_f32(reference)
    if candidate_values.shape != reference_values.shape:
        return {
            "name": name,
            "status": "fail",
            "reason": f"shape mismatch {candidate_values.shape} vs {reference_values.shape}",
            "candidate": str(candidate),
            "reference": str(reference),
        }
    finite = bool(np.isfinite(candidate_values).all() and np.isfinite(reference_values).all())
    cos = cosine(candidate_values, reference_values) if finite else float("nan")
    abs_error = np.abs(candidate_values - reference_values)
    max_abs = float(abs_error.max()) if abs_error.size else 0.0
    mean_abs = float(abs_error.mean()) if abs_error.size else 0.0
    status = "pass" if finite and cos >= threshold else "fail"
    return {
        "name": name,
        "status": status,
        "cosine": cos,
        "threshold": threshold,
        "max_abs_error": max_abs,
        "mean_abs_error": mean_abs,
        "finite": finite,
        "element_count": int(candidate_values.size),
        "candidate": {
            "path": str(candidate),
            "sha256": sha256_file(candidate),
        },
        "reference": {
            "path": str(reference),
            "sha256": sha256_file(reference),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare phone adapter gradients/update against PyTorch reference.")
    parser.add_argument("--phone-output", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--threshold", default=0.99, type=float)
    parser.add_argument("--check-update", action="store_true")
    args = parser.parse_args()

    checks = [
        tensor_report(
            "adapter_grad_a",
            args.phone_output / "adapter_grad_a.f32.bin",
            args.reference / "adapter_grad_a.f32.bin",
            args.threshold,
        ),
        tensor_report(
            "adapter_grad_b",
            args.phone_output / "adapter_grad_b.f32.bin",
            args.reference / "adapter_grad_b.f32.bin",
            args.threshold,
        ),
    ]
    if args.check_update:
        checks.extend([
            tensor_report(
                "updated_adapter_a",
                args.phone_output / "checkpoint/adapter_a.f32.bin",
                args.reference / "checkpoint/adapter_a.f32.bin",
                args.threshold,
            ),
            tensor_report(
                "updated_adapter_b",
                args.phone_output / "checkpoint/adapter_b.f32.bin",
                args.reference / "checkpoint/adapter_b.f32.bin",
                args.threshold,
            ),
        ])

    cosines = [check.get("cosine", float("nan")) for check in checks]
    finite_cosines = [value for value in cosines if math.isfinite(value)]
    failed = [check for check in checks if check["status"] != "pass"]
    report = {
        "schema_version": "gemma4_adapter_training_compare_v1",
        "status": "pass" if not failed else "fail",
        "threshold": args.threshold,
        "failed_tensor_count": len(failed),
        "tensor_count": len(checks),
        "cosine_min": min(finite_cosines) if finite_cosines else None,
        "cosine_p50": float(np.median(np.asarray(finite_cosines))) if finite_cosines else None,
        "checks": checks,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Phase34B gradient-source metadata contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from polymath_ai.polar.task_aligned_projection import (
    BLOCKED_STATUS,
    FLOAT32_BYTES,
    HIDDEN_DIM,
    LAYER_IDX,
    MATRIX_PASS_STATUS,
    PROJECTION_DIM,
    artifact_identity,
    default_raw_boundary,
    finite_number,
    inspect_float32_matrix_file,
    is_sha256,
    pearson,
    repo_contains,
    report_secret_blockers,
    sha256_file,
    sha256_text,
    utc_stamp,
)


GRADIENT_SOURCE_SCHEMA_VERSION = "phase34b_layer24_gradient_surface_v1"
GRADIENT_SVD_SCHEMA_VERSION = "phase34b_gradient_svd_projection_matrix_v1"
GRADIENT_FIDELITY_SCHEMA_VERSION = "phase34b_gradient_phone_fidelity_v1"
PASS_STATUS = "pass"


def build_gradient_source_report(
    *,
    gradient_matrix_path: str | Path,
    gradient_matrix_sha256: str = "",
    row_count: int | None = None,
    dtype: str = "float32",
    model_identity_sha256: str = "",
    tokenizer_identity_sha256: str = "",
    calibration_corpus_identity_sha256: str = "",
    heldout_overlap_count: int = 0,
    repo_root: str | Path | None = None,
    run_id: str | None = None,
    source_method: str = "offline_autograd_gradient_calibration",
) -> dict[str, Any]:
    path = Path(gradient_matrix_path)
    blockers: list[str] = []
    if not path.is_file():
        blockers.append("gradient_matrix_file_absent")
        byte_count = 0
        inferred_rows = 0
        matrix_sha = ""
    else:
        byte_count = path.stat().st_size
        matrix_sha = sha256_file(path)
        row_bytes = HIDDEN_DIM * FLOAT32_BYTES
        inferred_rows = byte_count // row_bytes
        if byte_count % row_bytes:
            blockers.append("gradient_matrix_byte_count_not_row_aligned")
    rows = int(row_count if row_count is not None else inferred_rows)
    if rows != inferred_rows and path.is_file():
        blockers.append("gradient_row_count_mismatch")
    if rows < PROJECTION_DIM:
        blockers.append("gradient_row_count_below_256_without_predeclared_adaptive_rank")
    if gradient_matrix_sha256 and matrix_sha != gradient_matrix_sha256:
        blockers.append("gradient_matrix_sha256_mismatch")
    if dtype != "float32":
        blockers.append("unsupported_gradient_dtype")
    for key, value in {
        "model_identity_sha256": model_identity_sha256,
        "tokenizer_identity_sha256": tokenizer_identity_sha256,
        "calibration_corpus_identity_sha256": calibration_corpus_identity_sha256,
    }.items():
        if not is_sha256(value):
            blockers.append(f"{key}_missing_or_invalid")
    if heldout_overlap_count != 0:
        blockers.append("heldout_overlap_count_nonzero")
    if repo_root is not None and repo_contains(path, repo_root):
        blockers.append("raw_gradient_matrix_inside_repo")

    stats = _float32_row_stats(path, rows) if path.is_file() and not blockers else {}
    if stats.get("nonfinite_count", 0):
        blockers.append("nonfinite_gradient_values")
    if stats.get("zero_norm_count", 0):
        blockers.append("zero_norm_gradient_rows")

    report = {
        "schema_version": GRADIENT_SOURCE_SCHEMA_VERSION,
        "status": PASS_STATUS if not blockers else BLOCKED_STATUS,
        "first_missing_green_field": "none" if not blockers else blockers[0],
        "blockers": _dedupe(blockers),
        "created_utc": utc_stamp(),
        "run_id": run_id,
        "source_method": source_method,
        "semantic": "representative dL_NLL/dh_layer24 gradient row matrix",
        "layer_idx": LAYER_IDX,
        "capture_site": "post_ple_gate_hidden_pre_native_polar",
        "gradient_matrix": {
            "path_string_sha256": sha256_text(str(path)),
            "sha256": matrix_sha,
            "bytes": byte_count,
            "row_count": rows,
            "width": HIDDEN_DIM,
            "dtype": dtype,
            "raw_rows_embedded": False,
            "raw_rows_in_repo": bool(repo_root is not None and repo_contains(path, repo_root)),
        },
        "quality": stats,
        "model_identity_sha256": model_identity_sha256,
        "tokenizer_identity_sha256": tokenizer_identity_sha256,
        "calibration_corpus_identity_sha256": calibration_corpus_identity_sha256,
        "heldout_overlap_count": heldout_overlap_count,
        "raw_boundary": default_raw_boundary(),
        "nonclaims": [
            "gradient source is a design asset until phone-native fidelity and correlation gates pass",
            "no base model update was authorized by this report",
            "raw gradient rows remain outside git",
        ],
    }
    secret_blockers = report_secret_blockers(report)
    if secret_blockers:
        report["status"] = BLOCKED_STATUS
        report["first_missing_green_field"] = secret_blockers[0]
        report["blockers"] = _dedupe([*report["blockers"], *secret_blockers])
    return report


def build_gradient_svd_projection_report(
    *,
    gradient_matrix_path: str | Path,
    output_matrix_path: str | Path,
    gradient_source_report: Mapping[str, Any],
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    if gradient_source_report.get("status") != PASS_STATUS:
        blockers.append("gradient_source_report_not_pass")
    gradient_path = Path(gradient_matrix_path)
    output_path = Path(output_matrix_path)
    source_rows = int(_mapping(gradient_source_report, "gradient_matrix").get("row_count") or 0)
    if repo_root is not None and repo_contains(output_path, repo_root):
        blockers.append("matrix_output_inside_repo")

    svd: dict[str, Any] = {}
    if not blockers:
        try:
            import numpy as np  # type: ignore[import-not-found]
        except ImportError:
            blockers.append("numpy_unavailable_for_gradient_svd")
        else:
            gradients = np.memmap(gradient_path, dtype="<f4", mode="r", shape=(source_rows, HIDDEN_DIM))
            working = np.asarray(gradients, dtype=np.float64)
            if not bool(np.isfinite(working).all()):
                blockers.append("nonfinite_gradient_values")
            if not blockers:
                working = working - working.mean(axis=0, keepdims=True)
                _, singular_values, vt = np.linalg.svd(working, full_matrices=False)
                tolerance = float(np.finfo(np.float64).eps * max(working.shape) * singular_values[0])
                rank_estimate = int(np.sum(singular_values > tolerance))
                if vt.shape[0] < PROJECTION_DIM or rank_estimate < PROJECTION_DIM:
                    blockers.append("gradient_rank_below_projection_dim")
                else:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    phi = np.asarray(vt[:PROJECTION_DIM], dtype=np.float32)
                    phi.tofile(output_path)
                    energy = np.square(singular_values)
                    svd = {
                        "algorithm": "gradient_centered_svd_vt_top256",
                        "rank_estimate": rank_estimate,
                        "top256_energy_ratio": float(energy[:PROJECTION_DIM].sum() / energy.sum()),
                        "singular_value_1": float(singular_values[0]),
                        "singular_value_256": float(singular_values[PROJECTION_DIM - 1]),
                        "singular_value_last": float(singular_values[-1]),
                    }

    if blockers:
        return {
            "schema_version": GRADIENT_SVD_SCHEMA_VERSION,
            "status": BLOCKED_STATUS,
            "first_missing_green_field": blockers[0],
            "blockers": _dedupe(blockers),
            "created_utc": utc_stamp(),
            "candidate_id": "h2r_gradient_svd_galore",
            "raw_boundary": default_raw_boundary(),
            "nonclaims": ["blocked Gradient-SVD matrix is not a candidate rerun"],
        }

    inspection = inspect_float32_matrix_file(output_path)
    report = {
        "schema_version": GRADIENT_SVD_SCHEMA_VERSION,
        "status": MATRIX_PASS_STATUS if inspection.status == MATRIX_PASS_STATUS else BLOCKED_STATUS,
        "first_missing_green_field": "none" if inspection.status == MATRIX_PASS_STATUS else inspection.blockers[0],
        "blockers": list(inspection.blockers),
        "created_utc": utc_stamp(),
        "candidate_id": "h2r_gradient_svd_galore",
        "matrix_shape": inspection.matrix_shape,
        "matrix_dtype": inspection.matrix_dtype,
        "matrix_sha256": inspection.sha256,
        "matrix_artifact": artifact_identity(output_path, repo_root=repo_root),
        "matrix_validation": inspection.to_dict(),
        "gradient_source_report_sha256": gradient_source_report.get("gradient_matrix", {}).get("sha256"),
        "svd": svd,
        "raw_boundary": default_raw_boundary(),
        "nonclaims": [
            "Gradient-SVD matrix is a candidate design asset until phone gates pass",
            "offline gradient construction is not authority evidence",
        ],
    }
    return report


def build_gradient_phone_fidelity_report(
    *,
    observations: Sequence[Mapping[str, Any]],
    no_update_delta_per_token: float | None,
    run_id: str | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    rows: list[dict[str, float | str]] = []
    for row in observations:
        predicted = row.get("predicted_delta")
        measured = row.get("measured_delta")
        if not finite_number(predicted) or not finite_number(measured):
            blockers.append("nonfinite_fidelity_observation")
            continue
        rows.append(
            {
                "direction_type": str(row.get("direction_type", "unknown")),
                "predicted_delta": float(predicted),
                "measured_delta": float(measured),
            }
        )
    no_update_ok = no_update_delta_per_token is not None and abs(float(no_update_delta_per_token)) <= 1.0e-12
    if not no_update_ok:
        blockers.append("no_update_delta_per_token_nonzero")
    if len(rows) < 8:
        blockers.append("insufficient_fidelity_observations")

    predicted_values = [float(row["predicted_delta"]) for row in rows]
    measured_values = [float(row["measured_delta"]) for row in rows]
    r_value = pearson(predicted_values, measured_values)
    sign_fraction = _sign_agreement_fraction(predicted_values, measured_values)
    gradient_rows = [row for row in rows if str(row["direction_type"]) != "random_control"]
    random_rows = [row for row in rows if str(row["direction_type"]) == "random_control"]
    gradient_sign = _sign_agreement_fraction(
        [float(row["predicted_delta"]) for row in gradient_rows],
        [float(row["measured_delta"]) for row in gradient_rows],
    )
    random_sign = _sign_agreement_fraction(
        [float(row["predicted_delta"]) for row in random_rows],
        [float(row["measured_delta"]) for row in random_rows],
    )
    if not finite_number(r_value) or float(r_value) <= 0.3:
        blockers.append("pearson_r_predicted_vs_measured_below_threshold")
    if not finite_number(sign_fraction) or float(sign_fraction) < 0.75:
        blockers.append("directional_sign_agreement_fraction_below_threshold")
    if finite_number(random_sign) and finite_number(gradient_sign) and float(gradient_sign) <= float(random_sign):
        blockers.append("gradient_directions_not_better_than_random_controls")

    return {
        "schema_version": GRADIENT_FIDELITY_SCHEMA_VERSION,
        "status": PASS_STATUS if not blockers else BLOCKED_STATUS,
        "first_missing_green_field": "none" if not blockers else blockers[0],
        "blockers": _dedupe(blockers),
        "created_utc": utc_stamp(),
        "run_id": run_id,
        "observation_count": len(observations),
        "valid_observation_count": len(rows),
        "no_update_delta_per_token": no_update_delta_per_token,
        "pearson_r_predicted_vs_measured_delta": r_value,
        "directional_sign_agreement_fraction": sign_fraction,
        "gradient_direction_sign_agreement_fraction": gradient_sign,
        "random_control_sign_agreement_fraction": random_sign,
        "raw_boundary": default_raw_boundary(),
        "nonclaims": [
            "phone fidelity probe is a Stage 0 filter only",
            "phone fidelity pass is not Gate E pass",
        ],
    }


def _float32_row_stats(path: Path, rows: int) -> dict[str, Any]:
    try:
        import numpy as np  # type: ignore[import-not-found]
    except ImportError:
        return {"numpy_available": False}
    matrix = np.memmap(path, dtype="<f4", mode="r", shape=(rows, HIDDEN_DIM))
    values = np.asarray(matrix, dtype=np.float64)
    finite = np.isfinite(values)
    norms = np.linalg.norm(values, axis=1)
    centered = values - values.mean(axis=0, keepdims=True)
    _, singular_values, _ = np.linalg.svd(centered, full_matrices=False)
    tolerance = float(np.finfo(np.float64).eps * max(centered.shape) * singular_values[0])
    rank = int(np.sum(singular_values > tolerance))
    energy = np.square(singular_values)
    probabilities = energy / energy.sum() if float(energy.sum()) > 0.0 else energy
    nonzero = probabilities[probabilities > 0.0]
    effective_rank = float(np.exp(-np.sum(nonzero * np.log(nonzero)))) if len(nonzero) else 0.0
    return {
        "numpy_available": True,
        "finite_values": bool(finite.all()),
        "nonfinite_count": int(values.size - finite.sum()),
        "gradient_norm_min": float(norms.min()),
        "gradient_norm_mean": float(norms.mean()),
        "gradient_norm_max": float(norms.max()),
        "zero_norm_count": int(np.sum(norms <= 0.0)),
        "centered_rank_estimate": rank,
        "effective_rank": effective_rank,
        "top256_energy_ratio": float(energy[:PROJECTION_DIM].sum() / energy.sum()) if float(energy.sum()) > 0.0 else None,
        "singular_value_1": float(singular_values[0]),
        "singular_value_256_if_available": float(singular_values[PROJECTION_DIM - 1]) if len(singular_values) >= PROJECTION_DIM else None,
        "singular_value_last": float(singular_values[-1]),
    }


def _sign_agreement_fraction(predicted: Sequence[float], measured: Sequence[float]) -> float | None:
    if not predicted or len(predicted) != len(measured):
        return None
    agree = 0
    valid = 0
    for left, right in zip(predicted, measured, strict=True):
        if left == 0.0 or right == 0.0:
            continue
        valid += 1
        agree += int((left < 0.0) == (right < 0.0))
    return agree / valid if valid else None


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, Mapping) else {}


def _dedupe(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))

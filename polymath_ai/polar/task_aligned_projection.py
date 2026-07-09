"""Task-aligned projection contracts for Phase 3/4 repair.

This module owns cheap, deterministic Stage A checks. It validates projection
matrix metadata and aggregate correlation reports without requiring raw corpus
rows, token-NLL rows, tensors, theta binaries, or secrets to enter reports.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import random
import re
import struct
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence


MATRIX_SCHEMA_VERSION = "phase34_task_aligned_projection_matrix_v1"
ACTIVATION_CAPTURE_SCHEMA_VERSION = "phase34_activation_capture_smoke_v1"
CORRELATION_SCHEMA_VERSION = "phase34_projection_correlation_report_v1"
LAUNCHER_SCHEMA_VERSION = "phase34_task_aligned_projection_launcher_v1"
CHAIN_SCHEMA_VERSION = "phase34_task_aligned_projection_chain_state_v1"
MATRIX_PASS_STATUS = "phase34_projection_matrix_static_contract_pass"
CORRELATION_PASS_STATUS = "phase34_projection_correlation_pass"
BLOCKED_STATUS = "blocked_fail_closed"
FALSIFIED_STATUS = "falsified"
PROJECTION_DIM = 256
HIDDEN_DIM = 2560
FLOAT32_BYTES = 4
EXPECTED_MATRIX_SHAPE = [PROJECTION_DIM, HIDDEN_DIM]
EXPECTED_MATRIX_DTYPE = "float32"
LAYER_IDX = 24
SHA256_LEN = 64

VALID_CANDIDATES = {
    "h0_rademacher",
    "h1_asvd",
    "h2_gradient_svd",
    "h3_pgap",
    "h4_rmt",
    "h5_sign_scale_layer_control",
}
PRIMARY_CANDIDATES = {
    "h0_rademacher",
    "h1_asvd",
    "h2_gradient_svd",
    "h3_pgap",
    "h4_rmt",
}
VALID_CONSTRUCTION_SURFACES = {
    "phone_native",
    "offline_static_asset",
    "host_control_only",
}
VALID_CAPTURE_SITES = {
    "post_ple_gate",
    "post_ple_gate_hidden_pre_native_polar",
    "hidden_state",
    "gradient_h24",
    "other",
}
STAGE_ORDER = [
    "preflight",
    "candidate_matrix_build",
    "matrix_static_tests",
    "d1_micro_correlation",
    "d2_small_correlation",
    "d3_full_correlation",
    "matched_no_update_control",
    "matched_random_theta_control",
    "gate_d2a_mini",
    "gate_d2a_full",
    "gate_e_one_record_probe",
    "gate_e_subset",
    "gate_e_full27",
    "comet_metadata_log",
    "custody_manifest",
]
CORRELATION_STAGE_RULES = {
    "d1_micro_correlation": {
        "min_records": 3,
        "min_perturbation_seeds": 2,
        "min_pearson_r": None,
        "max_p_value": None,
        "min_fraction_aligned": 0.0,
    },
    "d2_small_correlation": {
        "min_records": 9,
        "min_perturbation_seeds": 6,
        "min_pearson_r": 0.0,
        "max_p_value": None,
        "min_fraction_aligned": 0.55,
    },
    "d3_full_correlation": {
        "min_records": 27,
        "min_perturbation_seeds": 20,
        "min_pearson_r": 0.3,
        "max_p_value": 0.05,
        "min_fraction_aligned": 0.65,
    },
}
PHASE34B_CORRELATION_STAGE_OVERRIDES = {
    "d2_small_correlation": {
        "min_pearson_r": 0.2,
        "min_fraction_aligned": 0.60,
    },
}
FORBIDDEN_REPORT_SUFFIXES = {
    ".bin",
    ".bf16.bin",
    ".f32.bin",
    ".jsonl",
    ".onnx",
    ".pjp1",
    ".pqa1",
    ".pt",
    ".pth",
    ".qai1",
    ".raw",
    ".safetensors",
}
SECRET_PATTERNS = (
    re.compile(r"(?i)(COMET_API_KEY\s*=\s*)['\"]?[^'\"\s]+"),
    re.compile(r"(?i)(HF_TOKEN\s*=\s*)['\"]?[^'\"\s]+"),
    re.compile(r"(?i)(HUGGINGFACE_HUB_TOKEN\s*=\s*)['\"]?[^'\"\s]+"),
    re.compile(r"(?i)(GITHUB_TOKEN\s*=\s*)['\"]?[^'\"\s]+"),
    re.compile(r"(?i)(GH_TOKEN\s*=\s*)['\"]?[^'\"\s]+"),
    re.compile(r"(?i)(authorization:\s*bearer\s+)[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(api[_-]?key['\"]?\s*[:=]\s*['\"]?)[A-Za-z0-9_\-]{12,}"),
)


@dataclass(frozen=True)
class MatrixInspection:
    status: str
    path: str
    bytes: int
    sha256: str
    matrix_shape: list[int]
    matrix_dtype: str
    expected_bytes: int
    finite: bool
    nonfinite_count: int
    row_norm_min: float | None
    row_norm_max: float | None
    row_norm_mean: float | None
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "path": self.path,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "matrix_shape": self.matrix_shape,
            "matrix_dtype": self.matrix_dtype,
            "expected_bytes": self.expected_bytes,
            "finite": self.finite,
            "nonfinite_count": self.nonfinite_count,
            "row_norm_min": self.row_norm_min,
            "row_norm_max": self.row_norm_max,
            "row_norm_mean": self.row_norm_mean,
            "blockers": list(self.blockers),
        }


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_canonical_json(value: Any) -> str:
    return sha256_text(json.dumps(value, sort_keys=True, separators=(",", ":")))


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == SHA256_LEN and all(c in "0123456789abcdef" for c in value)


def repo_contains(path: Path, repo_root: str | Path) -> bool:
    try:
        path.resolve().relative_to(Path(repo_root).resolve())
    except ValueError:
        return False
    return True


def artifact_identity(path: str | Path, *, repo_root: str | Path | None = None) -> dict[str, Any]:
    artifact = Path(path)
    exists = artifact.exists()
    payload: dict[str, Any] = {
        "path": str(artifact),
        "exists": exists,
        "suffix": artifact.suffix.lower(),
    }
    if exists and artifact.is_file():
        payload["bytes"] = artifact.stat().st_size
        payload["sha256"] = sha256_file(artifact)
    if repo_root is not None:
        payload["in_repo"] = repo_contains(artifact, repo_root)
    return payload


def inspect_float32_matrix_file(
    path: str | Path,
    *,
    matrix_shape: Sequence[int] = EXPECTED_MATRIX_SHAPE,
) -> MatrixInspection:
    matrix_path = Path(path)
    rows, cols = int(matrix_shape[0]), int(matrix_shape[1])
    expected_bytes = rows * cols * FLOAT32_BYTES
    blockers: list[str] = []
    if not matrix_path.is_file():
        return MatrixInspection(
            status=BLOCKED_STATUS,
            path=str(matrix_path),
            bytes=0,
            sha256="",
            matrix_shape=list(matrix_shape),
            matrix_dtype=EXPECTED_MATRIX_DTYPE,
            expected_bytes=expected_bytes,
            finite=False,
            nonfinite_count=0,
            row_norm_min=None,
            row_norm_max=None,
            row_norm_mean=None,
            blockers=("matrix_file_absent",),
        )

    file_bytes = matrix_path.stat().st_size
    matrix_sha = sha256_file(matrix_path)
    if file_bytes != expected_bytes:
        blockers.append("matrix_byte_count_mismatch")

    row_norms: list[float] = []
    nonfinite_count = 0
    if file_bytes == expected_bytes:
        row_bytes = cols * FLOAT32_BYTES
        with matrix_path.open("rb") as handle:
            for _ in range(rows):
                values = struct.unpack("<" + "f" * cols, handle.read(row_bytes))
                nonfinite_count += sum(1 for value in values if not math.isfinite(value))
                row_norms.append(math.sqrt(sum(float(value) * float(value) for value in values)))
    if nonfinite_count:
        blockers.append("matrix_nonfinite_values")
    if row_norms and min(row_norms) <= 0.0:
        blockers.append("matrix_zero_row_norm")
    if row_norms and max(row_norms) > 10.0:
        blockers.append("matrix_row_norm_excessive")

    status = MATRIX_PASS_STATUS if not blockers else BLOCKED_STATUS
    return MatrixInspection(
        status=status,
        path=str(matrix_path),
        bytes=file_bytes,
        sha256=matrix_sha,
        matrix_shape=list(matrix_shape),
        matrix_dtype=EXPECTED_MATRIX_DTYPE,
        expected_bytes=expected_bytes,
        finite=nonfinite_count == 0 and file_bytes == expected_bytes,
        nonfinite_count=nonfinite_count,
        row_norm_min=min(row_norms) if row_norms else None,
        row_norm_max=max(row_norms) if row_norms else None,
        row_norm_mean=mean(row_norms) if row_norms else None,
        blockers=tuple(dedupe(blockers)),
    )


def build_h0_rademacher_projection(
    output_path: str | Path,
    *,
    seed: int = 20260708,
    repo_root: str | Path | None = None,
    calibration_record_count: int = 0,
    calibration_token_count: int = 0,
    heldout_split_sha256: str = "",
    model_identity_sha256: str = "",
    tokenizer_identity_sha256: str = "",
) -> dict[str, Any]:
    matrix_path = Path(output_path)
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    scale = 1.0 / math.sqrt(HIDDEN_DIM)
    pack = struct.Struct("<f").pack
    with matrix_path.open("wb") as handle:
        for _ in range(PROJECTION_DIM * HIDDEN_DIM):
            handle.write(pack(scale if rng.getrandbits(1) else -scale))

    inspection = inspect_float32_matrix_file(matrix_path)
    declared_inputs = {
        "candidate_id": "h0_rademacher",
        "seed": seed,
        "shape": EXPECTED_MATRIX_SHAPE,
        "dtype": EXPECTED_MATRIX_DTYPE,
        "scale": "1/sqrt(2560)",
        "generator": "python_random_getrandbits_v1",
    }
    return build_projection_matrix_report(
        candidate_id="h0_rademacher",
        matrix_inspection=inspection,
        construction_surface="host_control_only",
        calibration_record_count=calibration_record_count,
        calibration_token_count=calibration_token_count,
        activation_capture_site="other",
        heldout_split_sha256=heldout_split_sha256,
        model_identity_sha256=model_identity_sha256,
        tokenizer_identity_sha256=tokenizer_identity_sha256,
        construction_inputs=declared_inputs,
        repo_root=repo_root,
        nonclaims=[
            "H0 is an incumbent random baseline and cannot promote.",
            "No Gate E pass is implied by matrix construction.",
        ],
    )


def build_h1_asvd_projection(
    activation_capture_path: str | Path,
    output_path: str | Path,
    *,
    calibration_record_count: int,
    activation_capture_sha256: str,
    repo_root: str | Path | None = None,
    heldout_split_sha256: str = "",
    model_identity_sha256: str = "",
    tokenizer_identity_sha256: str = "",
    center_activations: bool = True,
    min_rows: int = PROJECTION_DIM + 1,
) -> dict[str, Any]:
    """Build an ASVD/GPM projection from phone-captured layer activations."""

    activation_path = Path(activation_capture_path)
    matrix_path = Path(output_path)
    blockers: list[str] = []
    row_bytes = HIDDEN_DIM * FLOAT32_BYTES
    activation_bytes = activation_path.stat().st_size if activation_path.is_file() else 0
    row_count = activation_bytes // row_bytes if row_bytes else 0
    activation_sha = sha256_file(activation_path) if activation_path.is_file() else ""

    if not activation_path.is_file():
        blockers.append("activation_capture_file_absent")
    if activation_bytes and activation_bytes % row_bytes != 0:
        blockers.append("activation_capture_byte_count_not_row_aligned")
    if row_count < min_rows:
        blockers.append("activation_capture_rows_below_asvd_min")
    if activation_capture_sha256 and activation_sha != activation_capture_sha256:
        blockers.append("activation_capture_sha256_mismatch")
    if repo_root is not None and repo_contains(activation_path, repo_root):
        blockers.append("raw_activation_capture_inside_repo")
    if repo_root is not None and repo_contains(matrix_path, repo_root):
        blockers.append("matrix_output_inside_repo")

    np: Any | None = None
    if not blockers:
        try:
            import numpy as np_import  # type: ignore[import-not-found]

            np = np_import
        except ImportError:
            blockers.append("numpy_unavailable_for_asvd")

    svd_metadata: dict[str, Any] = {}
    if not blockers and np is not None:
        matrix_path.parent.mkdir(parents=True, exist_ok=True)
        activations = np.memmap(
            activation_path,
            dtype="<f4",
            mode="r",
            shape=(row_count, HIDDEN_DIM),
        )
        working = np.asarray(activations, dtype=np.float64)
        finite = bool(np.isfinite(working).all())
        if not finite:
            blockers.append("activation_capture_nonfinite_values")
        row_norms = np.linalg.norm(working, axis=1)
        if bool(np.any(row_norms <= 0.0)):
            blockers.append("activation_capture_zero_row_norm")

        if not blockers:
            if center_activations:
                working = working - working.mean(axis=0, keepdims=True)
            _, singular_values, vt = np.linalg.svd(working, full_matrices=False)
            tolerance = float(np.finfo(np.float64).eps * max(working.shape) * singular_values[0])
            rank_estimate = int(np.sum(singular_values > tolerance))
            if vt.shape[0] < PROJECTION_DIM or rank_estimate < PROJECTION_DIM:
                blockers.append("activation_capture_rank_below_projection_dim")
            else:
                phi = np.asarray(vt[:PROJECTION_DIM], dtype=np.float32)
                pivot_indices = np.argmax(np.abs(phi), axis=1)
                for row_idx, pivot_idx in enumerate(pivot_indices):
                    if phi[row_idx, pivot_idx] < 0.0:
                        phi[row_idx, :] *= -1.0
                phi.tofile(matrix_path)
                spectrum_energy = np.square(singular_values)
                total_energy = float(spectrum_energy.sum())
                top_energy = float(spectrum_energy[:PROJECTION_DIM].sum())
                svd_metadata = {
                    "algorithm": "numpy_linalg_svd_vt_topk",
                    "center_activations": center_activations,
                    "activation_rows": int(row_count),
                    "hidden_dim": HIDDEN_DIM,
                    "projection_dim": PROJECTION_DIM,
                    "rank_estimate": rank_estimate,
                    "explained_variance_ratio_top256": top_energy / total_energy if total_energy > 0.0 else None,
                    "singular_value_1": float(singular_values[0]),
                    "singular_value_256": float(singular_values[PROJECTION_DIM - 1]),
                    "singular_value_last": float(singular_values[-1]),
                    "activation_row_norm_min": float(row_norms.min()),
                    "activation_row_norm_max": float(row_norms.max()),
                    "activation_row_norm_mean": float(row_norms.mean()),
                }

    if blockers:
        return build_blocked_projection_matrix_report(
            candidate_id="h1_asvd",
            first_missing_green_field=blockers[0],
            blockers=blockers,
            construction_surface="phone_native",
            activation_capture_site="post_ple_gate_hidden_pre_native_polar",
            calibration_record_count=calibration_record_count,
            calibration_token_count=int(row_count),
            heldout_split_sha256=heldout_split_sha256,
            model_identity_sha256=model_identity_sha256,
            tokenizer_identity_sha256=tokenizer_identity_sha256,
        )

    inspection = inspect_float32_matrix_file(matrix_path)
    construction_inputs = {
        "candidate_id": "h1_asvd",
        "algorithm": "activation_covariance_svd",
        "matrix_rows_from": "top_256_right_singular_vectors",
        "shape": EXPECTED_MATRIX_SHAPE,
        "dtype": EXPECTED_MATRIX_DTYPE,
        "activation_capture": {
            "sha256": activation_sha,
            "path_string_sha256": sha256_text(str(activation_path)),
            "bytes": activation_bytes,
            "row_count": int(row_count),
            "record_count": calibration_record_count,
            "raw_rows_embedded": False,
            "raw_rows_in_repo": False,
        },
        "svd": svd_metadata,
    }
    return build_projection_matrix_report(
        candidate_id="h1_asvd",
        matrix_inspection=inspection,
        construction_surface="phone_native",
        calibration_record_count=calibration_record_count,
        calibration_token_count=int(row_count),
        activation_capture_site="post_ple_gate_hidden_pre_native_polar",
        heldout_split_sha256=heldout_split_sha256,
        model_identity_sha256=model_identity_sha256,
        tokenizer_identity_sha256=tokenizer_identity_sha256,
        construction_inputs=construction_inputs,
        repo_root=repo_root,
        nonclaims=[
            "ASVD matrix construction is not a Gate E pass.",
            "Correlation and authority gates must pass before promotion.",
            "Raw activation rows remain outside git.",
        ],
    )


def build_h4_rmt_projection(
    activation_capture_path: str | Path,
    output_path: str | Path,
    *,
    calibration_record_count: int,
    activation_capture_sha256: str,
    repo_root: str | Path | None = None,
    heldout_split_sha256: str = "",
    model_identity_sha256: str = "",
    tokenizer_identity_sha256: str = "",
    seed: int = 202607084,
    center_activations: bool = True,
    min_signal_rank: int = 1,
) -> dict[str, Any]:
    """Build an RMT-pruned projection with deterministic random complement fill."""

    activation_path = Path(activation_capture_path)
    matrix_path = Path(output_path)
    blockers: list[str] = []
    row_bytes = HIDDEN_DIM * FLOAT32_BYTES
    activation_bytes = activation_path.stat().st_size if activation_path.is_file() else 0
    row_count = activation_bytes // row_bytes if row_bytes else 0
    activation_sha = sha256_file(activation_path) if activation_path.is_file() else ""

    if not activation_path.is_file():
        blockers.append("activation_capture_file_absent")
    if activation_bytes and activation_bytes % row_bytes != 0:
        blockers.append("activation_capture_byte_count_not_row_aligned")
    if row_count < 2:
        blockers.append("activation_capture_rows_below_rmt_min")
    if activation_capture_sha256 and activation_sha != activation_capture_sha256:
        blockers.append("activation_capture_sha256_mismatch")
    if repo_root is not None and repo_contains(activation_path, repo_root):
        blockers.append("raw_activation_capture_inside_repo")
    if repo_root is not None and repo_contains(matrix_path, repo_root):
        blockers.append("matrix_output_inside_repo")

    np: Any | None = None
    if not blockers:
        try:
            import numpy as np_import  # type: ignore[import-not-found]

            np = np_import
        except ImportError:
            blockers.append("numpy_unavailable_for_rmt")

    rmt_metadata: dict[str, Any] = {}
    if not blockers and np is not None:
        matrix_path.parent.mkdir(parents=True, exist_ok=True)
        activations = np.memmap(
            activation_path,
            dtype="<f4",
            mode="r",
            shape=(row_count, HIDDEN_DIM),
        )
        working = np.asarray(activations, dtype=np.float64)
        finite = bool(np.isfinite(working).all())
        if not finite:
            blockers.append("activation_capture_nonfinite_values")
        row_norms = np.linalg.norm(working, axis=1)
        if bool(np.any(row_norms <= 0.0)):
            blockers.append("activation_capture_zero_row_norm")

        if not blockers:
            if center_activations:
                working = working - working.mean(axis=0, keepdims=True)
            _, singular_values, vt = np.linalg.svd(working, full_matrices=False)
            tolerance = float(np.finfo(np.float64).eps * max(working.shape) * singular_values[0])
            rank_estimate = int(np.sum(singular_values > tolerance))
            if rank_estimate < min_signal_rank:
                blockers.append("activation_capture_rank_below_rmt_min_signal")
            else:
                eigenvalues = np.square(singular_values) / max(row_count - 1, 1)
                positive_eigs = eigenvalues[eigenvalues > tolerance]
                if positive_eigs.size == 0:
                    blockers.append("activation_capture_covariance_spectrum_empty")
                else:
                    tail_start = min(len(positive_eigs) // 2, max(len(positive_eigs) - 1, 0))
                    noise_variance = float(np.median(positive_eigs[tail_start:]))
                    aspect_ratio = float(HIDDEN_DIM / max(row_count, 1))
                    mp_upper = noise_variance * (1.0 + math.sqrt(aspect_ratio)) ** 2
                    signal_rank = int(np.sum(eigenvalues > mp_upper))
                    if signal_rank < min_signal_rank:
                        signal_rank = min(min_signal_rank, rank_estimate)
                    signal_rank = min(signal_rank, rank_estimate, PROJECTION_DIM, vt.shape[0])
                    signal = np.asarray(vt[:signal_rank], dtype=np.float64)
                    complement_count = PROJECTION_DIM - signal_rank
                    complement_rows: list[Any] = []
                    rng = random.Random(seed)
                    if complement_count:
                        for _ in range(complement_count):
                            values = np.fromiter(
                                (
                                    1.0 if rng.getrandbits(1) else -1.0
                                    for _ in range(HIDDEN_DIM)
                                ),
                                dtype=np.float64,
                                count=HIDDEN_DIM,
                            )
                            if signal_rank:
                                values = values - signal.T @ (signal @ values)
                            for previous in complement_rows:
                                values = values - previous * float(np.dot(previous, values))
                            norm = float(np.linalg.norm(values))
                            if norm <= 0.0 or not math.isfinite(norm):
                                blockers.append("rmt_random_complement_zero_norm")
                                break
                            complement_rows.append(values / norm)
                    if not blockers:
                        if complement_rows:
                            phi = np.vstack([signal, np.vstack(complement_rows)])
                        else:
                            phi = signal
                        if phi.shape != (PROJECTION_DIM, HIDDEN_DIM):
                            blockers.append("rmt_projection_shape_mismatch")
                        else:
                            phi = np.asarray(phi, dtype=np.float32)
                            pivot_indices = np.argmax(np.abs(phi), axis=1)
                            for row_idx, pivot_idx in enumerate(pivot_indices):
                                if phi[row_idx, pivot_idx] < 0.0:
                                    phi[row_idx, :] *= -1.0
                            phi.tofile(matrix_path)
                            total_energy = float(np.square(singular_values).sum())
                            signal_energy = float(np.square(singular_values[:signal_rank]).sum())
                            rmt_metadata = {
                                "algorithm": "activation_covariance_rmt_signal_plus_rademacher_complement",
                                "center_activations": center_activations,
                                "activation_rows": int(row_count),
                                "hidden_dim": HIDDEN_DIM,
                                "projection_dim": PROJECTION_DIM,
                                "rank_estimate": rank_estimate,
                                "signal_rank": signal_rank,
                                "complement_rank": complement_count,
                                "noise_variance_estimate": noise_variance,
                                "aspect_ratio_hidden_over_rows": aspect_ratio,
                                "marchenko_pastur_upper": mp_upper,
                                "signal_energy_ratio": signal_energy / total_energy if total_energy > 0.0 else None,
                                "singular_value_1": float(singular_values[0]),
                                "singular_value_signal_last": float(singular_values[signal_rank - 1]),
                                "singular_value_last": float(singular_values[-1]),
                                "activation_row_norm_min": float(row_norms.min()),
                                "activation_row_norm_max": float(row_norms.max()),
                                "activation_row_norm_mean": float(row_norms.mean()),
                                "deterministic_complement_seed": seed,
                            }

    if blockers:
        return build_blocked_projection_matrix_report(
            candidate_id="h4_rmt",
            first_missing_green_field=blockers[0],
            blockers=blockers,
            construction_surface="phone_native",
            activation_capture_site="post_ple_gate_hidden_pre_native_polar",
            calibration_record_count=calibration_record_count,
            calibration_token_count=int(row_count),
            heldout_split_sha256=heldout_split_sha256,
            model_identity_sha256=model_identity_sha256,
            tokenizer_identity_sha256=tokenizer_identity_sha256,
        )

    inspection = inspect_float32_matrix_file(matrix_path)
    construction_inputs = {
        "candidate_id": "h4_rmt",
        "algorithm": "rmt_spectral_pruning_with_deterministic_complement",
        "matrix_rows_from": "signal_right_singular_vectors_then_orthogonalized_rademacher_fill",
        "shape": EXPECTED_MATRIX_SHAPE,
        "dtype": EXPECTED_MATRIX_DTYPE,
        "activation_capture": {
            "sha256": activation_sha,
            "path_string_sha256": sha256_text(str(activation_path)),
            "bytes": activation_bytes,
            "row_count": int(row_count),
            "record_count": calibration_record_count,
            "raw_rows_embedded": False,
            "raw_rows_in_repo": False,
        },
        "rmt": rmt_metadata,
    }
    return build_projection_matrix_report(
        candidate_id="h4_rmt",
        matrix_inspection=inspection,
        construction_surface="phone_native",
        calibration_record_count=calibration_record_count,
        calibration_token_count=int(row_count),
        activation_capture_site="post_ple_gate_hidden_pre_native_polar",
        heldout_split_sha256=heldout_split_sha256,
        model_identity_sha256=model_identity_sha256,
        tokenizer_identity_sha256=tokenizer_identity_sha256,
        construction_inputs=construction_inputs,
        repo_root=repo_root,
        nonclaims=[
            "RMT matrix construction is not a Gate E pass.",
            "Correlation and authority gates must pass before promotion.",
            "Random complement is deterministic fallback fill, not evidence of improvement.",
            "Raw activation rows remain outside git.",
        ],
    )


def build_blocked_projection_matrix_report(
    *,
    candidate_id: str,
    first_missing_green_field: str,
    blockers: Sequence[str],
    construction_surface: str,
    activation_capture_site: str,
    calibration_record_count: int = 0,
    calibration_token_count: int = 0,
    heldout_split_sha256: str = "",
    model_identity_sha256: str = "",
    tokenizer_identity_sha256: str = "",
) -> dict[str, Any]:
    all_blockers = dedupe([first_missing_green_field, *blockers])
    return {
        "schema_version": MATRIX_SCHEMA_VERSION,
        "status": BLOCKED_STATUS,
        "first_missing_green_field": first_missing_green_field,
        "blockers": all_blockers,
        "created_utc": utc_stamp(),
        "candidate_id": candidate_id,
        "matrix_shape": EXPECTED_MATRIX_SHAPE,
        "matrix_dtype": EXPECTED_MATRIX_DTYPE,
        "matrix_sha256": "",
        "construction_surface": construction_surface,
        "calibration_record_count": calibration_record_count,
        "calibration_token_count": calibration_token_count,
        "layer_idx": LAYER_IDX,
        "activation_capture_site": activation_capture_site,
        "heldout_split_sha256": heldout_split_sha256,
        "model_identity_sha256": model_identity_sha256,
        "tokenizer_identity_sha256": tokenizer_identity_sha256,
        "raw_matrix_binary_in_repo": False,
        "raw_calibration_rows_in_repo": False,
        "matrix_validation": {
            "status": BLOCKED_STATUS,
            "blockers": all_blockers,
        },
        "raw_boundary": default_raw_boundary(),
        "nonclaims": [
            "blocked projection matrix report is not a candidate pass",
            "no Gate E pass unless authority report says pass",
        ],
    }


def build_activation_capture_smoke_report(
    *,
    native_report: Mapping[str, Any],
    raw_capture_bytes: int,
    raw_capture_sha256: str,
    raw_capture_phone_path_sha256: str,
    phone_run_root: str,
    runner_sha256: str,
    min_promotable_rows: int = PROJECTION_DIM,
) -> dict[str, Any]:
    capture = mapping(native_report, "phase34_activation_capture_contract")
    raw_boundary = mapping(native_report, "raw_boundary_proof")
    blockers: list[str] = []

    if native_report.get("status") != "pass":
        blockers.append("native_capture_report_not_pass")
    if capture.get("requested") is not True:
        blockers.append("activation_capture_not_requested")
    if capture.get("written") is not True:
        blockers.append("activation_capture_not_written")
    require_equal(blockers, capture.get("layer_index"), LAYER_IDX, "activation_capture_layer_mismatch")
    if capture.get("site") != "post_ple_gate_hidden_pre_native_polar":
        blockers.append("activation_capture_site_mismatch")
    require_equal(blockers, capture.get("dtype"), EXPECTED_MATRIX_DTYPE, "activation_capture_dtype_mismatch")
    require_equal(blockers, capture.get("shape_width"), HIDDEN_DIM, "activation_capture_width_mismatch")
    record_count = capture.get("record_count")
    row_count = capture.get("row_count")
    if not positive_int(record_count):
        blockers.append("activation_capture_record_count_zero")
    if not positive_int(row_count):
        blockers.append("activation_capture_row_count_zero")
    expected_bytes = int(row_count or 0) * HIDDEN_DIM * FLOAT32_BYTES
    if raw_capture_bytes != expected_bytes:
        blockers.append("activation_capture_byte_count_mismatch")
    if not is_sha256(raw_capture_sha256) or capture.get("sha256") != raw_capture_sha256:
        blockers.append("activation_capture_sha256_mismatch")
    if not is_sha256(raw_capture_phone_path_sha256):
        blockers.append("activation_capture_path_sha256_missing")
    if raw_boundary.get("raw_activation_capture_rows_embedded") is not False:
        blockers.append("raw_activation_capture_rows_embedded")
    if raw_boundary.get("secrets_embedded") is not False:
        blockers.append("secrets_embedded")

    promotable = not blockers and int(row_count or 0) >= min_promotable_rows
    if not promotable:
        blockers.append("activation_capture_rows_below_promotable_asvd_min")

    status = "pass" if not blockers else BLOCKED_STATUS
    first_missing = "none" if not blockers else blockers[0]
    return {
        "schema_version": ACTIVATION_CAPTURE_SCHEMA_VERSION,
        "status": status,
        "first_missing_green_field": first_missing,
        "blockers": dedupe(blockers),
        "created_utc": utc_stamp(),
        "candidate_id": "h1_asvd",
        "construction_surface": "phone_native",
        "layer_idx": LAYER_IDX,
        "activation_capture_site": "post_ple_gate_hidden_pre_native_polar",
        "calibration_record_count": int(record_count or 0),
        "calibration_row_count": int(row_count or 0),
        "min_promotable_rows": min_promotable_rows,
        "raw_capture_bytes": raw_capture_bytes,
        "raw_capture_sha256": raw_capture_sha256,
        "raw_capture_phone_path_sha256": raw_capture_phone_path_sha256,
        "phone_run_root": phone_run_root,
        "runner_sha256": runner_sha256,
        "native_report_status": native_report.get("status"),
        "native_report_progress_event_count": mapping(native_report, "native_runtime_profile").get("progress_event_count"),
        "raw_boundary": default_raw_boundary(),
        "nonclaims": [
            "activation capture smoke is not ASVD construction",
            "one-record capture is not promotable calibration",
            "raw activation rows remain outside git",
            "no Gate E pass unless authority report says pass",
        ],
    }


def validate_activation_capture_smoke_report(report: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    require_equal(blockers, report.get("schema_version"), ACTIVATION_CAPTURE_SCHEMA_VERSION, "bad_activation_capture_schema")
    require_equal(blockers, report.get("candidate_id"), "h1_asvd", "bad_activation_capture_candidate")
    require_equal(blockers, report.get("construction_surface"), "phone_native", "bad_activation_capture_surface")
    require_equal(blockers, report.get("layer_idx"), LAYER_IDX, "bad_activation_capture_layer")
    if report.get("activation_capture_site") != "post_ple_gate_hidden_pre_native_polar":
        blockers.append("bad_activation_capture_site")
    if not nonnegative_int(report.get("calibration_record_count")):
        blockers.append("bad_activation_capture_record_count")
    if not nonnegative_int(report.get("calibration_row_count")):
        blockers.append("bad_activation_capture_row_count")
    if not nonnegative_int(report.get("raw_capture_bytes")):
        blockers.append("bad_activation_capture_bytes")
    if not is_sha256(report.get("raw_capture_sha256")):
        blockers.append("bad_activation_capture_sha256")
    if not is_sha256(report.get("runner_sha256")):
        blockers.append("bad_activation_capture_runner_sha256")
    blockers.extend(raw_boundary_blockers(mapping(report, "raw_boundary")))
    blockers.extend(report_secret_blockers(report))
    return dedupe(blockers)


def build_projection_matrix_report(
    *,
    candidate_id: str,
    matrix_inspection: MatrixInspection,
    construction_surface: str,
    calibration_record_count: int,
    calibration_token_count: int,
    activation_capture_site: str,
    heldout_split_sha256: str,
    model_identity_sha256: str,
    tokenizer_identity_sha256: str,
    construction_inputs: Mapping[str, Any] | None = None,
    repo_root: str | Path | None = None,
    nonclaims: Sequence[str] = (),
) -> dict[str, Any]:
    artifact = artifact_identity(matrix_inspection.path, repo_root=repo_root)
    raw_matrix_in_repo = bool(artifact.get("in_repo"))
    report = {
        "schema_version": MATRIX_SCHEMA_VERSION,
        "status": MATRIX_PASS_STATUS,
        "first_missing_green_field": "none",
        "blockers": [],
        "created_utc": utc_stamp(),
        "candidate_id": candidate_id,
        "matrix_shape": list(matrix_inspection.matrix_shape),
        "matrix_dtype": matrix_inspection.matrix_dtype,
        "matrix_sha256": matrix_inspection.sha256,
        "construction_surface": construction_surface,
        "calibration_record_count": calibration_record_count,
        "calibration_token_count": calibration_token_count,
        "layer_idx": LAYER_IDX,
        "activation_capture_site": activation_capture_site,
        "heldout_split_sha256": heldout_split_sha256,
        "model_identity_sha256": model_identity_sha256,
        "tokenizer_identity_sha256": tokenizer_identity_sha256,
        "raw_matrix_binary_in_repo": raw_matrix_in_repo,
        "raw_calibration_rows_in_repo": False,
        "matrix_artifact": artifact,
        "matrix_validation": matrix_inspection.to_dict(),
        "construction_inputs_sha256": sha256_canonical_json(construction_inputs or {}),
        "construction_inputs_public": dict(construction_inputs or {}),
        "raw_boundary": default_raw_boundary(),
        "nonclaims": list(nonclaims)
        or [
            "matrix construction is a Stage A filter only",
            "no Gate E pass unless authority report says pass",
        ],
    }
    blockers = validate_projection_matrix_report(report, repo_root=repo_root)
    if blockers:
        report["status"] = BLOCKED_STATUS
        report["first_missing_green_field"] = blockers[0]
        report["blockers"] = blockers
    return report


def validate_projection_matrix_report(
    report: Mapping[str, Any],
    *,
    repo_root: str | Path | None = None,
) -> list[str]:
    blockers: list[str] = []
    require_equal(blockers, report.get("schema_version"), MATRIX_SCHEMA_VERSION, "bad_matrix_schema_version")
    if report.get("candidate_id") not in VALID_CANDIDATES:
        blockers.append("bad_candidate_id")
    require_equal(blockers, report.get("matrix_shape"), EXPECTED_MATRIX_SHAPE, "bad_matrix_shape")
    require_equal(blockers, report.get("matrix_dtype"), EXPECTED_MATRIX_DTYPE, "bad_matrix_dtype")
    if report.get("status") != BLOCKED_STATUS and not is_sha256(report.get("matrix_sha256")):
        blockers.append("bad_matrix_sha256")
    if report.get("construction_surface") not in VALID_CONSTRUCTION_SURFACES:
        blockers.append("bad_construction_surface")
    if not nonnegative_int(report.get("calibration_record_count")):
        blockers.append("bad_calibration_record_count")
    if not nonnegative_int(report.get("calibration_token_count")):
        blockers.append("bad_calibration_token_count")
    require_equal(blockers, report.get("layer_idx"), LAYER_IDX, "bad_layer_idx")
    if report.get("activation_capture_site") not in VALID_CAPTURE_SITES:
        blockers.append("bad_activation_capture_site")
    for key in ("heldout_split_sha256", "model_identity_sha256", "tokenizer_identity_sha256"):
        value = report.get(key)
        if value and not is_sha256(value):
            blockers.append(f"bad_{key}")
    if report.get("raw_matrix_binary_in_repo") is not False:
        blockers.append("raw_matrix_binary_in_repo")
    if report.get("raw_calibration_rows_in_repo") is not False:
        blockers.append("raw_calibration_rows_in_repo")
    matrix_validation = mapping(report, "matrix_validation")
    if report.get("status") != BLOCKED_STATUS and matrix_validation.get("status") != MATRIX_PASS_STATUS:
        blockers.append("matrix_value_validation_not_pass")
    artifact = mapping(report, "matrix_artifact")
    if repo_root is not None and artifact.get("path"):
        artifact_path = Path(str(artifact["path"]))
        if repo_contains(artifact_path, repo_root):
            blockers.append("matrix_artifact_path_inside_repo")
    blockers.extend(report_secret_blockers(report))
    blockers.extend(raw_boundary_blockers(mapping(report, "raw_boundary")))
    return dedupe(blockers)


def build_projection_correlation_report(
    *,
    stage_id: str,
    observations: Sequence[Mapping[str, Any]],
    no_update_delta_per_token: float | None,
    incumbent_candidate_id: str = "h0_rademacher",
    run_id: str | None = None,
    profile: str = "phase34",
) -> dict[str, Any]:
    blockers: list[str] = []
    if stage_id not in CORRELATION_STAGE_RULES:
        blockers.append("bad_correlation_stage_id")
    no_update_ok = no_update_delta_per_token is not None and abs(float(no_update_delta_per_token)) <= 1.0e-12
    if not no_update_ok:
        blockers.append("no_update_delta_per_token_nonzero")

    candidates = sorted({str(row.get("candidate_id")) for row in observations if row.get("candidate_id")})
    summaries = {
        candidate_id: summarize_candidate_correlation(candidate_id, observations)
        for candidate_id in candidates
    }
    if not summaries:
        blockers.append("no_candidate_observations")

    rules = dict(CORRELATION_STAGE_RULES.get(stage_id, {}))
    if profile == "phase34b":
        rules.update(PHASE34B_CORRELATION_STAGE_OVERRIDES.get(stage_id, {}))
    elif profile != "phase34":
        blockers.append("bad_correlation_profile")
    h0_r = summaries.get(incumbent_candidate_id, {}).get("pearson_r")
    for candidate_id, summary in summaries.items():
        summary_blockers = candidate_stage_blockers(candidate_id, summary, rules, h0_r)
        summary["status"] = CORRELATION_PASS_STATUS if not summary_blockers else FALSIFIED_STATUS
        summary["first_missing_green_field"] = summary_blockers[0] if summary_blockers else "none"
        summary["blockers"] = summary_blockers

    promotable_passes = [
        candidate_id
        for candidate_id, summary in summaries.items()
        if candidate_id != incumbent_candidate_id and summary.get("status") == CORRELATION_PASS_STATUS
    ]
    if not promotable_passes and summaries:
        blockers.append("no_promotable_candidate_passed_correlation")

    status = CORRELATION_PASS_STATUS if not blockers else FALSIFIED_STATUS
    first_missing = blockers[0] if blockers else "none"
    return {
        "schema_version": CORRELATION_SCHEMA_VERSION,
        "status": status,
        "first_missing_green_field": first_missing,
        "blockers": dedupe(blockers),
        "created_utc": utc_stamp(),
        "run_id": run_id,
        "profile": profile,
        "stage_id": stage_id,
        "records": rules.get("min_records"),
        "perturbation_seeds": rules.get("min_perturbation_seeds"),
        "no_update_delta_per_token": no_update_delta_per_token,
        "incumbent_candidate_id": incumbent_candidate_id,
        "candidate_summaries": summaries,
        "observation_count": len(observations),
        "raw_boundary": default_raw_boundary(),
        "nonclaims": [
            "correlation status is diagnostic only",
            "Gate D polar pass is not language-model improvement",
            "no Gate E pass unless authority report says pass",
        ],
    }


def validate_projection_correlation_report(report: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    require_equal(blockers, report.get("schema_version"), CORRELATION_SCHEMA_VERSION, "bad_correlation_schema_version")
    if report.get("stage_id") not in CORRELATION_STAGE_RULES:
        blockers.append("bad_correlation_stage_id")
    if not isinstance(report.get("candidate_summaries"), dict):
        blockers.append("candidate_summaries_missing")
    if report.get("no_update_delta_per_token") is None:
        blockers.append("no_update_delta_per_token_missing")
    elif abs(float(report["no_update_delta_per_token"])) > 1.0e-12:
        blockers.append("no_update_delta_per_token_nonzero")
    blockers.extend(report_secret_blockers(report))
    blockers.extend(raw_boundary_blockers(mapping(report, "raw_boundary")))
    return dedupe(blockers)


def summarize_candidate_correlation(
    candidate_id: str,
    observations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = [row for row in observations if row.get("candidate_id") == candidate_id]
    polar_improvements: list[float] = []
    nll_improvements: list[float] = []
    seeds: set[str] = set()
    nonfinite = False
    for row in rows:
        polar_delta = row.get("polar_loss_delta")
        nll_delta = row.get("nll_delta_per_token")
        if not finite_number(polar_delta) or not finite_number(nll_delta):
            nonfinite = True
            continue
        polar_improvements.append(-float(polar_delta))
        nll_improvements.append(-float(nll_delta))
        seeds.add(str(row.get("seed")))

    pearson_r = pearson(polar_improvements, nll_improvements)
    p_value = pearson_p_value_approx(pearson_r, len(polar_improvements))
    return {
        "candidate_id": candidate_id,
        "observation_count": len(rows),
        "valid_observation_count": len(polar_improvements),
        "perturbation_seed_count": len(seeds),
        "nonfinite_observed": nonfinite,
        "pearson_r": pearson_r,
        "p_value": p_value,
        "fraction_aligned": fraction_aligned(polar_improvements, nll_improvements),
        "polar_improvement_mean": mean(polar_improvements) if polar_improvements else None,
        "nll_improvement_mean": mean(nll_improvements) if nll_improvements else None,
        "diagnostic_only": candidate_id == "h0_rademacher",
    }


def candidate_stage_blockers(
    candidate_id: str,
    summary: Mapping[str, Any],
    rules: Mapping[str, Any],
    h0_pearson_r: Any,
) -> list[str]:
    blockers: list[str] = []
    if summary.get("nonfinite_observed") is True:
        blockers.append("nonfinite_nll_or_polar_delta")
    if int(summary.get("valid_observation_count") or 0) < int(rules.get("min_records") or 0):
        blockers.append("insufficient_record_observations")
    if int(summary.get("perturbation_seed_count") or 0) < int(rules.get("min_perturbation_seeds") or 0):
        blockers.append("insufficient_perturbation_seeds")
    pearson_r = summary.get("pearson_r")
    min_r = rules.get("min_pearson_r")
    if min_r is not None and (not finite_number(pearson_r) or float(pearson_r) <= float(min_r)):
        blockers.append("pearson_r_below_stage_threshold")
    max_p = rules.get("max_p_value")
    p_value = summary.get("p_value")
    if max_p is not None and (not finite_number(p_value) or float(p_value) >= float(max_p)):
        blockers.append("p_value_above_stage_threshold")
    fraction = summary.get("fraction_aligned")
    min_fraction = rules.get("min_fraction_aligned")
    if min_fraction is not None and (not finite_number(fraction) or float(fraction) <= float(min_fraction)):
        blockers.append("fraction_aligned_below_stage_threshold")
    if candidate_id == "h0_rademacher":
        blockers.append("h0_negative_control_not_promotable")
    if candidate_id != "h0_rademacher" and finite_number(h0_pearson_r) and finite_number(pearson_r):
        if float(h0_pearson_r) > float(pearson_r):
            blockers.append("incumbent_h0_better_than_candidate")
    return dedupe(blockers)


def build_launcher_plan(
    *,
    run_id: str,
    report_root: str | Path,
    phone_run_root: str,
    host_scratch_root: str | Path,
    candidates: Sequence[str] = ("h0_rademacher", "h1_asvd"),
    phone_serial: str = "FY25013101C8",
) -> dict[str, Any]:
    blockers = [f"bad_candidate:{candidate}" for candidate in candidates if candidate not in PRIMARY_CANDIDATES]
    return {
        "schema_version": LAUNCHER_SCHEMA_VERSION,
        "status": "pass" if not blockers else BLOCKED_STATUS,
        "first_missing_green_field": blockers[0] if blockers else "none",
        "blockers": blockers,
        "created_utc": utc_stamp(),
        "run_id": run_id,
        "phone_serial": phone_serial,
        "report_root": str(report_root),
        "phone_run_root": phone_run_root,
        "host_scratch_root": str(host_scratch_root),
        "candidates": list(candidates),
        "stage_order": STAGE_ORDER,
        "forced_comet": {
            "workspace": "zer0pa-imc",
            "project_name": "mobile-polymath-ai-training",
        },
        "authority_guard": {
            "gate_e_required_for_promotion": True,
            "gate_e_nll_delta_per_token_must_be_negative": True,
            "long_gate_e_full27_requires_prior_gates_green": True,
        },
        "raw_boundary": default_raw_boundary(),
        "nonclaims": [
            "launcher plan does not execute phone training",
            "no Gate E pass unless authority report says pass",
        ],
    }


def initialize_chain_state(
    *,
    run_root: str | Path,
    run_id: str,
    candidate_ids: Sequence[str],
    force_comet_workspace: str = "zer0pa-imc",
    force_comet_project: str = "mobile-polymath-ai-training",
) -> dict[str, Any]:
    root = Path(run_root)
    root.mkdir(parents=True, exist_ok=True)
    for name in ("reports", "metadata", "predictions"):
        (root / name).mkdir(exist_ok=True)
    stop_path = root / "STOP"
    if not stop_path.exists():
        stop_path.write_text("", encoding="utf-8")

    stages = [{"stage_id": stage, "status": "pending"} for stage in STAGE_ORDER]
    state = {
        "schema_version": CHAIN_SCHEMA_VERSION,
        "status": "initialized",
        "first_missing_green_field": "preflight_not_run",
        "run_id": run_id,
        "created_utc": utc_stamp(),
        "run_root": str(root),
        "candidate_ids": list(candidate_ids),
        "stage_order": STAGE_ORDER,
        "stages": stages,
        "stop_file": str(stop_path),
        "stop_semantics": "non-empty STOP requests pause before the next safe stage",
        "forced_comet": {
            "workspace": force_comet_workspace,
            "project_name": force_comet_project,
        },
        "raw_boundary": default_raw_boundary(),
        "nonclaims": [
            "chain initialization is not a Stage C/D/Gate E pass",
            "no Gate E pass unless authority report says pass",
        ],
    }
    write_json(root / "chain_state.json", state)
    write_json(root / "supervisor_status.json", {"status": "initialized", "run_id": run_id, "updated_utc": utc_stamp()})
    append_jsonl(root / "chain_events.jsonl", {"event": "chain_initialized", "run_id": run_id, "created_utc": utc_stamp()})
    append_jsonl(root / "supervisor_events.jsonl", {"event": "supervisor_initialized", "run_id": run_id, "created_utc": utc_stamp()})
    return state


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: str | Path, payload: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def default_raw_boundary() -> dict[str, bool]:
    return {
        "metadata_only_report": True,
        "raw_rows_embedded": False,
        "raw_tensors_embedded": False,
        "theta_binaries_embedded": False,
        "tokens_embedded": False,
        "logits_embedded": False,
        "secrets_embedded": False,
    }


def raw_boundary_blockers(raw_boundary: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if raw_boundary.get("metadata_only_report") is not True:
        blockers.append("raw_boundary_not_metadata_only")
    for key in (
        "raw_rows_embedded",
        "raw_tensors_embedded",
        "theta_binaries_embedded",
        "tokens_embedded",
        "logits_embedded",
        "secrets_embedded",
    ):
        if raw_boundary.get(key) is not False:
            blockers.append(key)
    return blockers


def report_secret_blockers(report: Mapping[str, Any]) -> list[str]:
    text = json.dumps(report, sort_keys=True)
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        return ["secret_pattern_embedded"]
    return []


def require_equal(blockers: list[str], actual: Any, expected: Any, blocker: str) -> None:
    if actual != expected:
        blockers.append(blocker)


def mapping(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    x_mean = mean(xs)
    y_mean = mean(ys)
    x_var = sum((x - x_mean) ** 2 for x in xs)
    y_var = sum((y - y_mean) ** 2 for y in ys)
    if x_var == 0.0 or y_var == 0.0:
        return None
    covariance = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    return covariance / math.sqrt(x_var * y_var)


def pearson_p_value_approx(r_value: float | None, n: int) -> float | None:
    if r_value is None or n < 3:
        return None
    r_abs = min(abs(float(r_value)), 0.999999999)
    if r_abs > 0.999999:
        return 0.0
    t_value = r_abs * math.sqrt((n - 2) / max(1.0e-12, 1.0 - r_abs * r_abs))
    return math.erfc(t_value / math.sqrt(2.0))


def fraction_aligned(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    pairs = [(x, y) for x, y in zip(xs, ys) if x != 0.0 and y != 0.0]
    if not pairs:
        return None
    aligned = sum(1 for x, y in pairs if (x > 0.0) == (y > 0.0))
    return aligned / len(pairs)


def dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result

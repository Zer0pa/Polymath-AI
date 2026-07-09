from __future__ import annotations

from pathlib import Path

import pytest

from polymath_ai.polar.gradient_source import (
    build_gradient_source_report,
    build_gradient_svd_projection_report,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def test_gradient_source_report_passes_for_outside_git_matrix(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    matrix = tmp_path / "gradients.f32"
    rng = np.random.default_rng(22)
    rows = rng.normal(size=(300, 2560)).astype("<f4")
    rows.tofile(matrix)

    report = build_gradient_source_report(
        gradient_matrix_path=matrix,
        model_identity_sha256=SHA_A,
        tokenizer_identity_sha256=SHA_B,
        calibration_corpus_identity_sha256=SHA_C,
        repo_root=Path.cwd(),
    )

    assert report["status"] == "pass"
    assert report["gradient_matrix"]["row_count"] == 300
    assert report["quality"]["centered_rank_estimate"] >= 256
    assert report["gradient_matrix"]["raw_rows_in_repo"] is False


def test_gradient_source_report_blocks_inside_repo_matrix() -> None:
    repo_matrix = Path("runtime/tmp/test_phase34b_gradient_inside_repo.f32")
    try:
        repo_matrix.parent.mkdir(parents=True, exist_ok=True)
        repo_matrix.write_bytes(b"\x00" * (256 * 2560 * 4))
        report = build_gradient_source_report(
            gradient_matrix_path=repo_matrix,
            model_identity_sha256=SHA_A,
            tokenizer_identity_sha256=SHA_B,
            calibration_corpus_identity_sha256=SHA_C,
            repo_root=Path.cwd(),
        )
        assert report["status"] == "blocked_fail_closed"
        assert "raw_gradient_matrix_inside_repo" in report["blockers"]
    finally:
        repo_matrix.unlink(missing_ok=True)


def test_gradient_svd_projection_builds_matrix_from_passed_source(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    gradient_matrix = tmp_path / "gradients.f32"
    output_matrix = tmp_path / "phi_grad.f32"
    rng = np.random.default_rng(23)
    rows = rng.normal(size=(300, 2560)).astype("<f4")
    rows.tofile(gradient_matrix)
    source_report = build_gradient_source_report(
        gradient_matrix_path=gradient_matrix,
        model_identity_sha256=SHA_A,
        tokenizer_identity_sha256=SHA_B,
        calibration_corpus_identity_sha256=SHA_C,
        repo_root=Path.cwd(),
    )

    report = build_gradient_svd_projection_report(
        gradient_matrix_path=gradient_matrix,
        output_matrix_path=output_matrix,
        gradient_source_report=source_report,
        repo_root=Path.cwd(),
    )

    assert report["status"] == "phase34_projection_matrix_static_contract_pass"
    assert report["candidate_id"] == "h2r_gradient_svd_galore"
    assert report["matrix_shape"] == [256, 2560]

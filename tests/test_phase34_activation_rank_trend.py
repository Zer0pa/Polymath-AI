from __future__ import annotations

from pathlib import Path

import pytest

from polymath_ai.polar.asvd_calibration import build_activation_rank_trend_report


def test_activation_rank_trend_passes_for_diverse_outside_git_chunks(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    rng = np.random.default_rng(32)
    chunks = []
    for index in range(2):
        path = tmp_path / f"chunk{index}.f32"
        rows = rng.normal(size=(160, 2560)).astype("<f4")
        rows.tofile(path)
        chunks.append(
            {
                "activation_capture_f32": str(path),
                "record_count": 64,
            }
        )

    report = build_activation_rank_trend_report(chunks=chunks, repo_root=Path.cwd())

    assert report["status"] == "pass"
    assert report["calibration_row_count"] == 320
    assert report["final_stats"]["centered_rank_estimate"] >= 256
    assert report["rank_trend"]


def test_activation_rank_trend_blocks_low_rank_chunks(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    rng = np.random.default_rng(33)
    path = tmp_path / "low_rank.f32"
    basis = rng.normal(size=(4, 2560))
    coeffs = rng.normal(size=(64, 4))
    rows = (coeffs @ basis).astype("<f4")
    rows.tofile(path)

    report = build_activation_rank_trend_report(
        chunks=[{"activation_capture_f32": str(path), "record_count": 16}],
        repo_root=Path.cwd(),
    )

    assert report["status"] == "blocked_fail_closed"
    assert "activation_capture_rank_below_projection_dim" in report["blockers"]


def test_activation_rank_trend_blocks_inside_repo_chunk() -> None:
    path = Path("runtime/tmp/test_phase34b_activation_inside_repo.f32")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x00" * (4 * 2560 * 4))
        report = build_activation_rank_trend_report(
            chunks=[{"activation_capture_f32": str(path), "record_count": 1}],
            repo_root=Path.cwd(),
        )
        assert report["status"] == "blocked_fail_closed"
        assert "raw_activation_chunk_inside_repo" in report["blockers"]
    finally:
        path.unlink(missing_ok=True)

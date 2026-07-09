from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from polymath_ai.polar.task_aligned_projection import (
    CORRELATION_PASS_STATUS,
    FALSIFIED_STATUS,
    build_projection_correlation_report,
    validate_projection_correlation_report,
)


def test_d3_correlation_passes_for_candidate_and_keeps_h0_nonpromotable() -> None:
    observations = []
    for index in range(27):
        seed = index % 20
        observations.append(
            {
                "candidate_id": "h0_rademacher",
                "seed": seed,
                "polar_loss_delta": -float(index + 1),
                "nll_delta_per_token": 0.01 if seed % 2 == 0 else -0.01,
            }
        )
        observations.append(
            {
                "candidate_id": "h1_asvd",
                "seed": seed,
                "polar_loss_delta": -float(index + 1),
                "nll_delta_per_token": -float(index + 1) / 1000.0,
            }
        )

    report = build_projection_correlation_report(
        stage_id="d3_full_correlation",
        observations=observations,
        no_update_delta_per_token=0.0,
    )

    assert report["status"] == CORRELATION_PASS_STATUS
    assert report["candidate_summaries"]["h1_asvd"]["status"] == CORRELATION_PASS_STATUS
    assert report["candidate_summaries"]["h1_asvd"]["pearson_r"] > 0.99
    assert report["candidate_summaries"]["h0_rademacher"]["diagnostic_only"] is True
    assert "h0_negative_control_not_promotable" in report["candidate_summaries"]["h0_rademacher"]["blockers"]
    assert validate_projection_correlation_report(report) == []


def test_d2_correlation_fails_when_no_update_control_moves() -> None:
    observations = [
        {
            "candidate_id": "h1_asvd",
            "seed": seed,
            "polar_loss_delta": -float(seed + 1),
            "nll_delta_per_token": -float(seed + 1) / 1000.0,
        }
        for seed in range(6)
    ]

    report = build_projection_correlation_report(
        stage_id="d2_small_correlation",
        observations=observations,
        no_update_delta_per_token=0.0001,
    )

    assert report["status"] == FALSIFIED_STATUS
    assert "no_update_delta_per_token_nonzero" in report["blockers"]


def test_phase34b_d2_uses_stricter_signal_threshold() -> None:
    observations = [
        {
            "candidate_id": "h1_asvd",
            "seed": seed,
            "polar_loss_delta": -float(seed + 1),
            "nll_delta_per_token": -0.001 if seed in (0, 1, 2, 3, 4) else 0.001,
        }
        for seed in range(9)
    ]

    report = build_projection_correlation_report(
        stage_id="d2_small_correlation",
        observations=observations,
        no_update_delta_per_token=0.0,
        profile="phase34b",
    )

    assert report["status"] == FALSIFIED_STATUS
    assert report["profile"] == "phase34b"
    assert "no_promotable_candidate_passed_correlation" in report["blockers"]
    assert "pearson_r_below_stage_threshold" in report["candidate_summaries"]["h1_asvd"]["blockers"]


def test_correlation_report_script_writes_json(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "report.json"
    payload = {
        "stage_id": "d2_small_correlation",
        "no_update_delta_per_token": 0.0,
        "observations": [
            {
                "candidate_id": "h1_asvd",
                "seed": seed,
                "polar_loss_delta": -float(seed + 1),
                "nll_delta_per_token": -float(seed + 1) / 1000.0,
            }
            for seed in range(9)
        ],
    }
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/host/build_phase34_projection_correlation_report.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["status"] == CORRELATION_PASS_STATUS

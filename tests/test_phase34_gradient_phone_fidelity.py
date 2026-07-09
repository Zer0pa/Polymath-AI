from __future__ import annotations

from polymath_ai.polar.gradient_source import build_gradient_phone_fidelity_report


def test_gradient_phone_fidelity_passes_when_predictions_match_phone_deltas() -> None:
    observations = []
    for idx in range(12):
        is_random = idx >= 10
        predicted = 0.001 if is_random else -0.01 * (idx + 1)
        observations.append(
            {
                "direction_type": "random_control" if is_random else "top_gradient_svd_direction",
                "predicted_delta": predicted,
                "measured_delta": -0.001 if is_random else predicted * 1.1,
            }
        )

    report = build_gradient_phone_fidelity_report(
        observations=observations,
        no_update_delta_per_token=0.0,
    )

    assert report["status"] == "pass"
    assert report["pearson_r_predicted_vs_measured_delta"] > 0.99


def test_gradient_phone_fidelity_blocks_mismatched_signs() -> None:
    observations = []
    for idx in range(10):
        predicted = -0.01 * (idx + 1)
        observations.append(
            {
                "direction_type": "top_gradient_svd_direction" if idx < 8 else "random_control",
                "predicted_delta": predicted,
                "measured_delta": -predicted,
            }
        )

    report = build_gradient_phone_fidelity_report(
        observations=observations,
        no_update_delta_per_token=0.0,
    )

    assert report["status"] == "blocked_fail_closed"
    assert "pearson_r_predicted_vs_measured_below_threshold" in report["blockers"]

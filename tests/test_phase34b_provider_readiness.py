from __future__ import annotations

from polymath_ai.polar.phase34b_provider_readiness import build_provider_readiness_report


def test_provider_readiness_passes_with_presence_and_safe_checks() -> None:
    report = build_provider_readiness_report(
        env_names_present=["COMET_API_KEY", "COMET_WORKSPACE", "COMET_PROJECT_NAME"],
        comet_workspace="zer0pa-imc",
        comet_project_name="mobile-polymath-ai-training",
        safe_checks={
            "phone_adb_termux": {"status": "pass", "secret_values_observed": False},
            "comet": {"status": "pass", "secret_values_observed": False},
        },
    )

    assert report["status"] == "pass"
    assert report["env_presence"]["COMET_API_KEY"] is True
    assert "COMET_API_KEY=" not in str(report)


def test_provider_readiness_blocks_wrong_comet_target() -> None:
    report = build_provider_readiness_report(
        env_names_present=["COMET_API_KEY", "COMET_WORKSPACE", "COMET_PROJECT_NAME"],
        comet_workspace="zer0pa",
        comet_project_name="mobile-polymath-ai-training",
        safe_checks={
            "phone_adb_termux": {"status": "pass", "secret_values_observed": False},
            "comet": {"status": "pass", "secret_values_observed": False},
        },
    )

    assert report["status"] == "blocked_fail_closed"
    assert "comet_workspace_not_forced" in report["blockers"]


def test_provider_readiness_blocks_secret_observation() -> None:
    report = build_provider_readiness_report(
        env_names_present=["COMET_API_KEY", "COMET_WORKSPACE", "COMET_PROJECT_NAME"],
        comet_workspace="zer0pa-imc",
        comet_project_name="mobile-polymath-ai-training",
        safe_checks={
            "phone_adb_termux": {"status": "pass", "secret_values_observed": True},
            "comet": {"status": "pass", "secret_values_observed": False},
        },
    )

    assert report["status"] == "blocked_fail_closed"
    assert "secret_values_observed:phone_adb_termux" in report["blockers"]

"""Metadata-only Phase34B provider readiness contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
from typing import Any

from polymath_ai.polar.task_aligned_projection import (
    BLOCKED_STATUS,
    report_secret_blockers,
    utc_stamp,
)


SCHEMA_VERSION = "phase34b_provider_readiness_v1"
PASS_STATUS = "pass"
REQUIRED_COMET_WORKSPACE = "zer0pa-imc"
REQUIRED_COMET_PROJECT = "mobile-polymath-ai-training"
REQUIRED_ENV_NAMES = (
    "COMET_API_KEY",
    "COMET_WORKSPACE",
    "COMET_PROJECT_NAME",
)
OPTIONAL_ENV_NAMES = (
    "HF_TOKEN",
    "HUGGINGFACE_HUB_TOKEN",
    "GH_TOKEN",
    "GITHUB_TOKEN",
)


def build_provider_readiness_report(
    *,
    env_names_present: Sequence[str] | None = None,
    safe_checks: Mapping[str, Mapping[str, Any]] | None = None,
    comet_workspace: str | None = None,
    comet_project_name: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    present = set(env_names_present or [])
    safe_check_payload = {str(key): dict(value) for key, value in (safe_checks or {}).items()}
    workspace = comet_workspace or ("COMET_WORKSPACE" if "COMET_WORKSPACE" in present else "")
    project = comet_project_name or ("COMET_PROJECT_NAME" if "COMET_PROJECT_NAME" in present else "")
    blockers: list[str] = []

    for name in REQUIRED_ENV_NAMES:
        if name not in present:
            blockers.append(f"env_presence_missing:{name}")
    if comet_workspace is not None and comet_workspace != REQUIRED_COMET_WORKSPACE:
        blockers.append("comet_workspace_not_forced")
    if comet_project_name is not None and comet_project_name != REQUIRED_COMET_PROJECT:
        blockers.append("comet_project_not_forced")

    required_checks = ("phone_adb_termux", "comet")
    for check_name in required_checks:
        check = safe_check_payload.get(check_name, {})
        if check.get("status") != PASS_STATUS:
            blockers.append(f"safe_check_not_pass:{check_name}")
    for check_name, check in safe_check_payload.items():
        if check.get("secret_values_observed") is True:
            blockers.append(f"secret_values_observed:{check_name}")

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": PASS_STATUS if not blockers else BLOCKED_STATUS,
        "first_missing_green_field": "none" if not blockers else blockers[0],
        "blockers": _dedupe(blockers),
        "created_utc": utc_stamp(),
        "run_id": run_id,
        "env_presence": {name: name in present for name in [*REQUIRED_ENV_NAMES, *OPTIONAL_ENV_NAMES]},
        "comet_target": {
            "workspace": comet_workspace,
            "project_name": comet_project_name,
            "workspace_required": REQUIRED_COMET_WORKSPACE,
            "project_required": REQUIRED_COMET_PROJECT,
        },
        "safe_checks": safe_check_payload,
        "provider_capability_capsule": {
            "phone_adb_termux": "authority execution target",
            "hugging_face": "corpus/model provenance when needed",
            "github": "custody commits/PRs only when authorized",
            "comet": "metadata-only numeric logging",
            "runpod": "optional offline gradient/tool host",
        },
        "raw_boundary": {
            "metadata_only_report": True,
            "raw_rows_embedded": False,
            "raw_tensors_embedded": False,
            "theta_binaries_embedded": False,
            "secrets_embedded": False,
        },
        "nonclaims": [
            "provider readiness does not execute phone work",
            "provider readiness does not authorize candidate reruns",
            "Comet dashboard presence is not authority evidence",
        ],
    }
    secret_blockers = report_secret_blockers(report)
    if secret_blockers:
        report["status"] = BLOCKED_STATUS
        report["first_missing_green_field"] = secret_blockers[0]
        report["blockers"] = _dedupe([*report["blockers"], *secret_blockers])
        report["raw_boundary"]["secrets_embedded"] = True
    return report


def env_names_present_from_process(environ: Mapping[str, str] | None = None) -> list[str]:
    source = os.environ if environ is None else environ
    names = [*REQUIRED_ENV_NAMES, *OPTIONAL_ENV_NAMES]
    return [name for name in names if source.get(name)]


def _dedupe(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))

"""``PolymathEnvelope`` schema and constructor.

The envelope is the universal wrapper. Every run, evaluation, checkpoint,
export probe, and sync event emits one. The exact field set is locked by the
PRD; deviations require a ``docs/DECISIONS.md`` entry.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from polymath_ai._version import SCHEMA_VERSION
from polymath_ai.boundary.text import BOUNDARY_TEXT
from polymath_ai.utils.canonical import hash_mapping


_PHASE_ENUM = [
    "phase0a_substrate",
    "phase0b_elo_correctness",
    "phase0c_export_truth_table",
    "phase0d_device_attach",
    "phase0e_experiment0",
    "phase0f_experiment1_fertility",
    "phase0g_experiment2_smollm3_export",
    "phase0h_cutover_review",
    "phase1a_qwen_elo_100m",
    "phase1b_cross_lingual",
    "phase2_smollm3_track",
    "phase3_multimodal",
    "ad_hoc",
]

_BACKEND_ENUM = [
    "mac_sim",
    "android_cpu",
    "vulkan_gpu",
    "litert_qnn",
    "qnn_direct",
    "fallback",
]

_FALSIFICATION_STATUS_ENUM = ["pass", "warn", "fail", "blocked", "unknown"]


ENVELOPE_SCHEMA: dict = {
    "type": "object",
    "required": [
        "schema_version",
        "boundary",
        "run_id",
        "phase",
        "git_sha",
        "config_sha256",
        "model",
        "corpus",
        "device_state",
        "backend",
        "outputs",
        "falsification",
        "provenance",
        "artifact_refs",
    ],
    "properties": {
        "schema_version": {"type": "string"},
        "boundary": {"type": "string"},
        "run_id": {"type": "string"},
        "phase": {"type": "string", "enum": _PHASE_ENUM},
        "experiment_id": {"type": ["string", "null"]},
        "git_sha": {"type": "string"},
        "config_sha256": {"type": "string"},
        "model": {
            "type": "object",
            "required": ["model_id"],
            "properties": {
                "model_id": {"type": "string"},
                "revision": {"type": ["string", "null"]},
                "model_sha256": {"type": ["string", "null"]},
                "tokenizer_sha256": {"type": ["string", "null"]},
                "license_attestation_id": {"type": ["string", "null"]},
            },
        },
        "corpus": {
            "type": "object",
            "properties": {
                "manifest_sha256": {"type": ["string", "null"]},
                "slice_id": {"type": ["string", "null"]},
                "license_summary": {"type": ["string", "null"]},
            },
        },
        "device_state": {"type": "object"},
        "backend": {"type": "string", "enum": _BACKEND_ENUM},
        "outputs": {"type": "object"},
        "falsification": {
            "type": "object",
            "required": ["status", "falsifier_ids", "blocking_failures"],
            "properties": {
                "status": {"type": "string", "enum": _FALSIFICATION_STATUS_ENUM},
                "falsifier_ids": {"type": "array", "items": {"type": "string"}},
                "blocking_failures": {"type": "array", "items": {"type": "string"}},
            },
        },
        "provenance": {
            "type": "object",
            "required": ["agent_role"],
            "properties": {
                "agent_role": {"type": "string"},
                "agent_model": {"type": ["string", "null"]},
                "source_files": {"type": "array", "items": {"type": "string"}},
                "input_hashes": {"type": "array", "items": {"type": "string"}},
                "output_hashes": {"type": "array", "items": {"type": "string"}},
            },
        },
        "artifact_refs": {
            "type": "object",
            "properties": {
                "github_paths": {"type": "array", "items": {"type": "string"}},
                "hf_private_refs": {"type": "array", "items": {"type": "string"}},
                "pending_local_paths": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}


def _default_device_state() -> dict:
    return {
        "host_machine": None,
        "phone_attached": False,
        "phone_model": None,
        "soc_reported": None,
        "ram_gb": None,
        "battery_mode": None,
        "thermal_status": None,
        "gpu_clock_mhz_p50": None,
        "gpu_clock_mhz_p10": None,
    }


def _default_falsification() -> dict:
    return {
        "status": "unknown",
        "falsifier_ids": [],
        "blocking_failures": [],
    }


def new_envelope(
    *,
    run_id: str,
    phase: str,
    git_sha: str = "unknown",
    config_sha256: str = "sha256:unknown",
    model_id: str = "tiny.qwen.shape",
    backend: str = "mac_sim",
    agent_role: str = "overnight-executor",
    agent_model: Optional[str] = None,
    experiment_id: Optional[str] = None,
    overrides: Optional[Mapping[str, Any]] = None,
) -> dict:
    """Construct a fresh envelope. Caller fills outputs/artifact_refs as work
    progresses, then validates before serializing.
    """
    env: dict = {
        "schema_version": SCHEMA_VERSION,
        "boundary": BOUNDARY_TEXT,
        "run_id": run_id,
        "phase": phase,
        "experiment_id": experiment_id,
        "git_sha": git_sha,
        "config_sha256": config_sha256,
        "model": {
            "model_id": model_id,
            "revision": None,
            "model_sha256": None,
            "tokenizer_sha256": None,
            "license_attestation_id": None,
        },
        "corpus": {
            "manifest_sha256": None,
            "slice_id": None,
            "license_summary": None,
        },
        "device_state": _default_device_state(),
        "backend": backend,
        "outputs": {},
        "falsification": _default_falsification(),
        "provenance": {
            "agent_role": agent_role,
            "agent_model": agent_model,
            "source_files": [],
            "input_hashes": [],
            "output_hashes": [],
        },
        "artifact_refs": {
            "github_paths": [],
            "hf_private_refs": [],
            "pending_local_paths": [],
        },
    }
    if overrides:
        for k, v in overrides.items():
            env[k] = v
    return env


def fingerprint_envelope(env: Mapping[str, Any]) -> str:
    """Stable fingerprint over invariant envelope fields (model, corpus,
    config). ``outputs``, ``provenance.input_hashes``, and ``artifact_refs``
    are excluded so the fingerprint is stable across resumes that produce the
    same scientific contract.
    """
    invariant = {
        "schema_version": env["schema_version"],
        "phase": env["phase"],
        "experiment_id": env.get("experiment_id"),
        "config_sha256": env["config_sha256"],
        "model": env["model"],
        "corpus": env["corpus"],
        "backend": env["backend"],
    }
    return hash_mapping(invariant)

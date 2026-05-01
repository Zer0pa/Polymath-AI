"""Record-level schemas for audit, KG, corpus, eval, dispatch, sync,
falsifier, and reasoner-tuple objects."""
from __future__ import annotations


_BOUNDARY_REF = {
    "type": "object",
    "required": ["boundary_id", "boundary_text_sha256"],
    "properties": {
        "boundary_id": {"type": "string"},
        "boundary_text_sha256": {"type": "string"},
        "boundary_manifest": {"type": ["string", "null"]},
    },
}


# Audit hash-chain row.
AUDIT_ROW_SCHEMA: dict = {
    "type": "object",
    "required": [
        "schema_version",
        "recorded_at",
        "run_id",
        "event_type",
        "payload",
        "prev_event_hash",
        "event_hash",
    ],
    "properties": {
        "schema_version": {"type": "string"},
        "recorded_at": {"type": "string"},
        "run_id": {"type": "string"},
        "event_type": {
            "type": "string",
            "enum": [
                "genesis",
                "train_step",
                "checkpoint",
                "eval",
                "decision",
                "sync",
                "falsifier",
                "device_probe",
                "export_probe",
                "boundary_check",
                "reasoner_tuple",
                "phase_gate",
            ],
        },
        "payload": {"type": "object"},
        "prev_event_hash": {"type": "string"},
        "event_hash": {"type": "string"},
        "boundary": _BOUNDARY_REF,
    },
}


# Checkpoint manifest row.
CHECKPOINT_RECORD_SCHEMA: dict = {
    "type": "object",
    "required": [
        "schema_version",
        "boundary",
        "run_id",
        "checkpoint_kind",
        "model_id",
        "checkpoint_sha256",
        "trainable_param_names",
        "frozen_param_hash_sample",
        "optimizer_state_keys",
        "step",
        "tokens_seen",
        "config_sha256",
        "corpus_slice_id",
        "base_model_pointer",
    ],
    "properties": {
        "schema_version": {"type": "string"},
        "boundary": _BOUNDARY_REF,
        "run_id": {"type": "string"},
        "checkpoint_kind": {
            "type": "string",
            "enum": [
                "stage1_boundary",
                "stage1_full_resume",
                "stage2_alignment",
                "stage2_merged",
                "smoke",
                "ablation",
            ],
        },
        "model_id": {"type": "string"},
        "checkpoint_sha256": {"type": "string"},
        "trainable_param_names": {"type": "array", "items": {"type": "string"}},
        "frozen_param_hash_sample": {"type": "object"},
        "optimizer_state_keys": {"type": "array", "items": {"type": "string"}},
        "step": {"type": "integer"},
        "tokens_seen": {"type": "integer"},
        "config_sha256": {"type": "string"},
        "corpus_slice_id": {"type": ["string", "null"]},
        "base_model_pointer": {"type": ["string", "null"]},
        "license_attestation_id": {"type": ["string", "null"]},
        "hf_repo_id": {"type": ["string", "null"]},
        "hf_path": {"type": ["string", "null"]},
        "local_path": {"type": ["string", "null"]},
    },
}


# Corpus manifest schema.
CORPUS_MANIFEST_SCHEMA: dict = {
    "type": "object",
    "required": [
        "schema_version",
        "boundary",
        "manifest_id",
        "manifest_sha256",
        "stage",
        "tokens_target",
        "domain_mix",
        "language_mix",
        "license_classes_allowed",
        "sources",
    ],
    "properties": {
        "schema_version": {"type": "string"},
        "boundary": _BOUNDARY_REF,
        "manifest_id": {"type": "string"},
        "manifest_sha256": {"type": "string"},
        "stage": {
            "type": "string",
            "enum": ["smoke", "experiment0", "phase1a", "phase1b", "phase2", "ad_hoc"],
        },
        "tokens_target": {"type": "integer"},
        "domain_mix": {"type": "object"},
        "language_mix": {"type": "object"},
        "license_classes_allowed": {"type": "array", "items": {"type": "string"}},
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source_id", "license_class", "language", "domain"],
                "properties": {
                    "source_id": {"type": "string"},
                    "uri": {"type": ["string", "null"]},
                    "license_class": {"type": "string", "enum": ["A", "B", "C", "D", "E"]},
                    "license_attestation_id": {"type": ["string", "null"]},
                    "language": {"type": "string"},
                    "domain": {"type": "string"},
                    "ocr_provenance_id": {"type": ["string", "null"]},
                    "tokens_estimate": {"type": ["integer", "null"]},
                    "chunk_count": {"type": ["integer", "null"]},
                    "notes": {"type": ["string", "null"]},
                },
            },
        },
    },
}


# Device state record.
DEVICE_STATE_SCHEMA: dict = {
    "type": "object",
    "required": ["schema_version", "boundary", "host_machine", "phone_attached"],
    "properties": {
        "schema_version": {"type": "string"},
        "boundary": _BOUNDARY_REF,
        "host_machine": {"type": ["string", "null"]},
        "phone_attached": {"type": "boolean"},
        "phone_model": {"type": ["string", "null"]},
        "android_version": {"type": ["string", "null"]},
        "redmagic_os_version": {"type": ["string", "null"]},
        "abi": {"type": ["string", "null"]},
        "soc_reported": {"type": ["string", "null"]},
        "soc_target": {"type": ["string", "null"]},
        "ram_gb": {"type": ["number", "null"]},
        "storage_free_gb": {"type": ["number", "null"]},
        "battery_mode": {"type": ["string", "null"]},
        "battery_pct": {"type": ["number", "null"]},
        "battery_temp_c": {"type": ["number", "null"]},
        "charge_separation_active": {"type": ["boolean", "null"]},
        "thermal_status": {"type": ["string", "null"]},
        "gpu_clock_mhz_p50": {"type": ["number", "null"]},
        "gpu_clock_mhz_p10": {"type": ["number", "null"]},
        "fan_state": {"type": ["string", "null"]},
        "vulkan_version": {"type": ["string", "null"]},
        "qnn_runtime_present": {"type": ["boolean", "null"]},
        "litert_runtime_present": {"type": ["boolean", "null"]},
        "termux_python_version": {"type": ["string", "null"]},
    },
}


DISPATCH_RECORD_SCHEMA: dict = {
    "type": "object",
    "required": [
        "schema_version",
        "boundary",
        "run_id",
        "dispatch_id",
        "op_class",
        "op_shape",
        "backend_chosen",
        "backend_alternatives",
        "scheduler_policy",
    ],
    "properties": {
        "schema_version": {"type": "string"},
        "boundary": _BOUNDARY_REF,
        "run_id": {"type": "string"},
        "dispatch_id": {"type": "string"},
        "op_class": {"type": "string"},
        "op_shape": {"type": "object"},
        "backend_chosen": {"type": "string"},
        "backend_alternatives": {"type": "array", "items": {"type": "string"}},
        "scheduler_policy": {"type": "string", "enum": ["static", "reflex_ucb", "reflex_eps_greedy", "fallback"]},
        "latency_ms": {"type": ["number", "null"]},
        "energy_mj": {"type": ["number", "null"]},
        "queue_id": {"type": ["string", "null"]},
        "fallback_reason": {"type": ["string", "null"]},
    },
}


EVAL_RECORD_SCHEMA: dict = {
    "type": "object",
    "required": [
        "schema_version",
        "boundary",
        "run_id",
        "eval_id",
        "metric",
        "scope",
        "value",
        "baseline_ref",
        "model_ref",
        "corpus_ref",
    ],
    "properties": {
        "schema_version": {"type": "string"},
        "boundary": _BOUNDARY_REF,
        "run_id": {"type": "string"},
        "eval_id": {"type": "string"},
        "metric": {"type": "string"},
        "scope": {"type": "object"},
        "value": {"type": ["number", "string", "object", "null"]},
        "baseline_ref": {"type": ["string", "null"]},
        "model_ref": {"type": "string"},
        "corpus_ref": {"type": ["string", "null"]},
        "delta_vs_baseline": {"type": ["number", "null"]},
        "notes": {"type": ["string", "null"]},
    },
}


FALSIFIER_RESULT_SCHEMA: dict = {
    "type": "object",
    "required": [
        "schema_version",
        "boundary",
        "run_id",
        "falsifier_id",
        "result",
        "evidence",
        "blocking",
    ],
    "properties": {
        "schema_version": {"type": "string"},
        "boundary": _BOUNDARY_REF,
        "run_id": {"type": "string"},
        "falsifier_id": {"type": "string"},
        "result": {"type": "string", "enum": ["pass", "warn", "fail", "blocked", "skipped"]},
        "evidence": {"type": "object"},
        "blocking": {"type": "boolean"},
        "remediation_action": {"type": ["string", "null"]},
        "decision_id": {"type": ["string", "null"]},
    },
}


PENDING_UPLOAD_SCHEMA: dict = {
    "type": "object",
    "required": [
        "schema_version",
        "boundary",
        "pending_id",
        "local_path",
        "sha256",
        "size_bytes",
        "intended_target",
    ],
    "properties": {
        "schema_version": {"type": "string"},
        "boundary": _BOUNDARY_REF,
        "pending_id": {"type": "string"},
        "local_path": {"type": "string"},
        "sha256": {"type": "string"},
        "size_bytes": {"type": "integer"},
        "intended_target": {
            "type": "object",
            "required": ["target_kind", "repo_id"],
            "properties": {
                "target_kind": {
                    "type": "string",
                    "enum": ["hf_dataset", "hf_model", "hf_space", "github", "external"],
                },
                "repo_id": {"type": "string"},
                "path_in_repo": {"type": ["string", "null"]},
            },
        },
        "license_attestation_id": {"type": ["string", "null"]},
        "blocked_by": {"type": ["string", "null"]},
        "queued_at": {"type": "string"},
    },
}


REASONER_TUPLE_SCHEMA: dict = {
    "type": "object",
    "required": [
        "schema_version",
        "boundary",
        "run_id",
        "tuple_id",
        "input",
        "output",
        "judgment",
        "hashes",
    ],
    "properties": {
        "schema_version": {"type": "string"},
        "boundary": _BOUNDARY_REF,
        "run_id": {"type": "string"},
        "tuple_id": {"type": "string"},
        "input": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "language": {"type": ["string", "null"]},
                "domain": {"type": ["string", "null"]},
                "source_refs": {"type": "array", "items": {"type": "string"}},
            },
        },
        "output": {
            "type": "object",
            "properties": {
                "model_id": {"type": "string"},
                "checkpoint_sha256": {"type": ["string", "null"]},
                "text": {"type": "string"},
            },
        },
        "judgment": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["pass", "warn", "fail"]},
                "falsifier_ids": {"type": "array", "items": {"type": "string"}},
                "teacher_panel": {"type": "array"},
            },
        },
        "correction": {"type": ["object", "null"]},
        "hashes": {
            "type": "object",
            "required": ["input_sha256", "output_sha256", "judgment_sha256"],
            "properties": {
                "input_sha256": {"type": "string"},
                "output_sha256": {"type": "string"},
                "judgment_sha256": {"type": "string"},
            },
        },
    },
}


SYNC_EVENT_SCHEMA: dict = {
    "type": "object",
    "required": [
        "schema_version",
        "boundary",
        "run_id",
        "sync_id",
        "kind",
        "result",
    ],
    "properties": {
        "schema_version": {"type": "string"},
        "boundary": _BOUNDARY_REF,
        "run_id": {"type": "string"},
        "sync_id": {"type": "string"},
        "kind": {
            "type": "string",
            "enum": [
                "github_push",
                "hf_push",
                "hf_pull",
                "adb_pull",
                "adb_push",
                "pending_upload_emit",
                "pending_upload_flush",
            ],
        },
        "result": {"type": "string", "enum": ["ok", "deferred", "failed"]},
        "target_ref": {"type": ["string", "null"]},
        "artifact_sha256": {"type": ["string", "null"]},
        "size_bytes": {"type": ["integer", "null"]},
        "error": {"type": ["string", "null"]},
    },
}

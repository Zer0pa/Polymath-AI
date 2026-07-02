#!/usr/bin/env python3
"""Prepare and validate the WaveC Gemma E4B decoder/FFN island QNN exporter."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from polymath_ai.polar.wavec_gemma_qnn_exporter import (  # noqa: E402
    AUTHORITY_MATERIAL,
    EXPECTED_GRAPH,
    EXPECTED_MODEL_ID,
    EXPECTED_MODEL_REVISION,
    EXPECTED_ORIGINAL_CONFIG_OID,
    EXPECTED_ORIGINAL_CONFIG_SIZE_BYTES,
    EXPECTED_PRODUCER_KIND,
    EXPORTER_SCHEMA_VERSION,
    REQUIRED_CONFIG,
    validate_gemma_decoder_to_qnn_exporter_report,
)
from polymath_ai.polar.wavec_full_gemma_qnn import (  # noqa: E402
    EXPECTED_BYTES,
    EXPECTED_DTYPE,
    EXPECTED_SHAPE,
)


DEFAULT_REPORT = (
    "runtime/reports/polar_phase34_consumer_preflight/active_wave/"
    "gemma_decoder_to_qnn_exporter/gemma_decoder_to_qnn_exporter_report.json"
)
QNN_OP_PLAN = [
    "RMSNorm(input, input_layernorm.weight, epsilon=1e-6)",
    "MatMul(normed, mlp.gate_proj.weight^T)",
    "MatMul(normed, mlp.up_proj.weight^T)",
    "GELU_TANH(gate)",
    "ElementWiseMultiply(activation, up)",
    "MatMul(ffn, mlp.down_proj.weight^T)",
    "ElementWiseAdd(input, down_projection)",
]


def main() -> int:
    args = parse_args()
    if args.print_schema:
        print_schema()
        return 0

    report = build_report(args)
    blockers = validate_gemma_decoder_to_qnn_exporter_report(report, require_status=False)
    report["blockers"] = sorted(set([*report.get("blockers", []), *blockers]))
    report["status"] = "pass" if not report["blockers"] else "blocked"
    report["first_missing_green_field"] = first_missing_green_field(report)

    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0 if report["status"] == "pass" else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-safetensors", required=False, help="Outside-git Gemma E4B model.safetensors.")
    parser.add_argument("--model-safetensors-sha256", default="", help="Preverified model.safetensors SHA-256.")
    parser.add_argument("--model-safetensors-bytes", type=int, default=0, help="Preverified model.safetensors byte count.")
    parser.add_argument(
        "--model-source-location",
        choices=("local", "phone_preverified"),
        default="local",
        help="Use phone_preverified when Execution/Steward already supplied phone-local path, SHA-256, and byte count.",
    )
    parser.add_argument("--model-config", required=False, help="Outside-git Gemma E4B config.json.")
    parser.add_argument(
        "--model-config-spec",
        required=False,
        help="Repo model_spec JSON accepted by Pipeline as derived metadata, not restored HF config.json.",
    )
    parser.add_argument("--model-revision", default=EXPECTED_MODEL_REVISION)
    parser.add_argument("--work-root", required=False, help="Outside-git exporter work root.")
    parser.add_argument("--qairt-root", required=False, help="Outside-git QAIRT SDK root.")
    parser.add_argument("--android-ndk-root", required=False, help="Outside-git Android NDK root.")
    parser.add_argument("--phone-work-root", default="/data/local/tmp/polymath_gemma4_gate/wavec/full_gemma_qnn_export")
    parser.add_argument("--model-library", default="", help="Phone-local generated QNN model library path.")
    parser.add_argument("--model-library-sha256", default="")
    parser.add_argument("--model-library-bytes", type=int, default=0)
    parser.add_argument("--context-path", default="", help="Phone-local generated QNN context path.")
    parser.add_argument("--context-sha256", default="")
    parser.add_argument("--context-bytes", type=int, default=0)
    parser.add_argument("--qnn-context-binary-generator", default="")
    parser.add_argument("--qnn-context-binary-generator-sha256", default="")
    parser.add_argument("--qnn-context-binary-utility", default="")
    parser.add_argument("--qnn-context-binary-utility-sha256", default="")
    parser.add_argument("--qnn-net-run", default="")
    parser.add_argument("--qnn-net-run-sha256", default="")
    parser.add_argument("--qairt-sdk-version", default="")
    parser.add_argument("--android-ndk-version", default="")
    parser.add_argument("--context-utility-graph-match", action="store_true")
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--print-schema", action="store_true")
    return parser.parse_args()


def print_schema() -> None:
    print(
        json.dumps(
            {
                "schema_version": EXPORTER_SCHEMA_VERSION,
                "preferred_route": "qnn_cpp_generated_model_library",
                "secondary_route": "litert_aot_only_if_it_emits_same_qnn_context_contract_without_fallback",
                "model_source_contract": {
                    "model_id": EXPECTED_MODEL_ID,
                    "revision": EXPECTED_MODEL_REVISION,
                    "accepted_config_sources": [
                        "original HF config.json",
                        "JSON with top-level text_config",
                        "repo model_spec JSON with hf_config_summary.text_config after Pipeline acceptance",
                    ],
                    "accepted_model_source_locations": [
                        "local outside-git file",
                        "phone_preverified outside-git path with SHA-256 and byte count",
                    ],
                    "required_files": ["model.safetensors", "config.json or accepted model_spec-derived config metadata"],
                    "location": "outside_git",
                    "model_spec_provenance_requires": {
                        "repo_id": EXPECTED_MODEL_ID,
                        "revision": EXPECTED_MODEL_REVISION,
                        "expected_original_config_oid": EXPECTED_ORIGINAL_CONFIG_OID,
                        "expected_original_config_size_bytes": EXPECTED_ORIGINAL_CONFIG_SIZE_BYTES,
                        "explicitly_not_original_hf_config_restored": True,
                    },
                },
                "graph_contract": {
                    "name": EXPECTED_GRAPH,
                    "input_shape": EXPECTED_SHAPE,
                    "output_shape": EXPECTED_SHAPE,
                    "dtype": EXPECTED_DTYPE,
                    "bytes": EXPECTED_BYTES,
                    "qnn_op_plan": QNN_OP_PLAN,
                },
                "pass_requires": [
                    "real restored Gemma E4B safetensors",
                    "QNN C++ generated Android model library outside git",
                    "qnn-context-binary-generator against libQnnHtp.so",
                    "qnn-context-binary-utility graph match",
                    "qnn-net-run --retrieve_context output contract validated by run_wavec_full_gemma_qnn_forward.py",
                    "Phase4 OpenCL consumption validated by run_wavec_full_gemma_consumed_tensor_report.py",
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": EXPORTER_SCHEMA_VERSION,
        "status": "pending_validation",
        "phase3_ready_claim": False,
        "phase4_ready_claim": False,
        "learning_claim": False,
        "full_gemma_htp_forward_claim": False,
        "authority_material": AUTHORITY_MATERIAL,
        "model_source": model_source_payload(args),
        "graph": graph_payload(),
        "conversion": conversion_payload(args),
        "qnn_context": qnn_context_payload(args),
        "receiving_validators": {
            "qnn_forward": "scripts/host/run_wavec_full_gemma_qnn_forward.py",
            "phase4_consumed_tensor": "scripts/host/run_wavec_full_gemma_consumed_tensor_report.py",
        },
        "raw_payload_rules": {
            "raw_model_context_tensor_payloads_outside_git": True,
            "raw_payloads_in_git": False,
            "metadata_report_only_in_repo": True,
            "repo_paths": [args.report],
        },
        "blockers": pre_validation_blockers(args),
        "stop_conditions": [
            "gemma_e4b_model_safetensors_for_context_export_missing",
            "qnn_cpp_model_library_build_failed",
            "qnn_context_binary_generator_failed",
            "qnn_context_utility_graph_mismatch",
            "qnn_net_run_output_contract_mismatch",
            "qnn_profile_metadata_missing",
            "phase4_consumed_tensor_sha_mismatch",
            "adapter_pre_post_sha_unchanged",
            "raw_payload_entered_git",
        ],
        "nonclaims": [
            "No C5 pass.",
            "No learning or model-quality claim.",
            "No Phase3/4 readiness.",
            "No full-Gemma HTP forward claim until phone QNN context/run/profile evidence validates.",
        ],
    }
    return report


def model_source_payload(args: argparse.Namespace) -> dict[str, Any]:
    model_path = Path(args.model_safetensors) if args.model_safetensors else None
    config_path = selected_config_path(args)
    config = load_config_summary(config_path) if config_path and config_path.is_file() else {}
    model_file_present = bool(model_path and model_path.is_file())
    model_preverified = bool(
        args.model_source_location == "phone_preverified"
        and args.model_safetensors
        and args.model_safetensors_sha256
        and args.model_safetensors_bytes > 0
    )
    return {
        "model_id": EXPECTED_MODEL_ID,
        "revision": args.model_revision,
        "path": str(model_path) if model_path else "",
        "config_path": str(config_path) if config_path else "",
        "config_source": config_source_payload(args, config_path),
        "source_location": args.model_source_location,
        "outside_git": model_path_outside_git(model_path) if model_path else False,
        "config_json_present": bool(config_path and config_path.is_file()),
        "model_safetensors_present": model_file_present or model_preverified,
        "model_safetensors_sha256": sha256_file(model_path) if model_file_present else args.model_safetensors_sha256,
        "model_safetensors_bytes": model_path.stat().st_size if model_file_present else args.model_safetensors_bytes,
        "config": config,
    }


def load_config_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    text = config_text_section(payload)
    return {key: text.get(key) for key in REQUIRED_CONFIG}


def config_text_section(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("hf_config_summary"), dict):
        hf_text = payload["hf_config_summary"].get("text_config")
        if isinstance(hf_text, dict):
            return hf_text
    text_config = payload.get("text_config")
    if isinstance(text_config, dict):
        return text_config
    return payload


def config_source_payload(args: argparse.Namespace, config_path: Path | None) -> dict[str, Any]:
    if not config_path:
        return {}
    if args.model_config_spec:
        return model_spec_config_source_payload(config_path)
    return {
        "kind": "hf_config_json",
        "path": str(config_path),
        "explicitly_not_original_hf_config_restored": False,
    }


def model_spec_config_source_payload(config_path: Path) -> dict[str, Any]:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    base_repo = payload.get("repos", {}).get("base", {})
    config_manifest = find_file_manifest_entry(payload, "base", "config.json")
    return {
        "kind": "model_spec_derived_metadata",
        "path": str(config_path),
        "model_spec_sha256": sha256_file(config_path),
        "explicitly_not_original_hf_config_restored": True,
        "repo_id": base_repo.get("id"),
        "revision": base_repo.get("sha"),
        "expected_original_config_oid": config_manifest.get("oid"),
        "expected_original_config_size_bytes": config_manifest.get("size"),
    }


def find_file_manifest_entry(payload: dict[str, Any], family: str, filename: str) -> dict[str, Any]:
    entries = payload.get("file_manifest", {}).get(family, [])
    for entry in entries:
        if isinstance(entry, dict) and entry.get("path") == filename:
            return entry
    return {}


def graph_payload() -> dict[str, Any]:
    tensor = {"shape": EXPECTED_SHAPE, "dtype": EXPECTED_DTYPE, "bytes": EXPECTED_BYTES}
    return {
        "name": EXPECTED_GRAPH,
        "producer_kind": EXPECTED_PRODUCER_KIND,
        "scope": "gemma4_e4b_ffn_residual_layer0",
        "input": tensor,
        "output": tensor,
        "qnn_op_plan": QNN_OP_PLAN,
    }


def conversion_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "route": "qnn_cpp_model_library_to_context",
        "preferred_route": "qnn_cpp_generated_model_library",
        "secondary_route": "litert_aot_only_if_same_qnn_context_contract_no_fallback",
        "litert_aot_primary": False,
        "uses_real_restored_weights": bool(args.model_safetensors),
        "random_init_weights": False,
        "metadata_only_manifest": False,
        "cpu_fallback": False,
        "qairt_root": args.qairt_root or "",
        "android_ndk_root": args.android_ndk_root or "",
        "qairt_sdk_version": args.qairt_sdk_version,
        "android_ndk_version": args.android_ndk_version,
        "qnn_op_plan": QNN_OP_PLAN,
        "generated_artifact_contract": {
            "source_cpp": "outside_work_root/gemma4_e4b_ffn_residual_layer0_qnn_model.cpp",
            "weight_blobs": "outside_work_root/weights/*.raw",
            "android_model_library": "outside_work_root/out/libgemma4_e4b_ffn_residual_layer0.so",
        },
        "model_library": {
            "path": args.model_library,
            "outside_git": not path_in_repo(Path(args.model_library)) if args.model_library else False,
            "sha256": args.model_library_sha256,
            "bytes": args.model_library_bytes,
        },
    }


def qnn_context_payload(args: argparse.Namespace) -> dict[str, Any]:
    qairt_root = (args.qairt_root or "").rstrip("/")
    return {
        "backend_execution": "qnn_htp",
        "cpu_fallback": False,
        "context_generated": bool(args.context_path),
        "qairt_root": qairt_root,
        "backend": f"{qairt_root}/lib/aarch64-android/libQnnHtp.so" if qairt_root else "",
        "context_path": args.context_path,
        "context_sha256": args.context_sha256,
        "context_bytes": args.context_bytes,
        "graph_name": EXPECTED_GRAPH,
        "context_utility_graph_match": args.context_utility_graph_match,
        "phone_work_root": args.phone_work_root,
        "tool_identities": {
            "qnn_context_binary_generator": {
                "path": args.qnn_context_binary_generator,
                "identity_sha256": args.qnn_context_binary_generator_sha256,
            },
            "qnn_context_binary_utility": {
                "path": args.qnn_context_binary_utility,
                "identity_sha256": args.qnn_context_binary_utility_sha256,
            },
            "qnn_net_run": {
                "path": args.qnn_net_run,
                "identity_sha256": args.qnn_net_run_sha256,
            },
        },
    }


def pre_validation_blockers(args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    model_path = Path(args.model_safetensors) if args.model_safetensors else None
    config_path = selected_config_path(args)
    work_root = Path(args.work_root) if args.work_root else None
    model_preverified = (
        args.model_source_location == "phone_preverified"
        and bool(args.model_safetensors)
        and bool(args.model_safetensors_sha256)
        and args.model_safetensors_bytes > 0
    )
    if not model_preverified and (not model_path or not model_path.is_file()):
        blockers.append("gemma_e4b_model_safetensors_for_context_export_missing")
    if not config_path or not config_path.is_file():
        blockers.append("gemma_e4b_config_json_for_context_export_missing")
    if work_root and path_in_repo(work_root):
        blockers.append("export_work_root_inside_repo")
    if args.context_path and not args.context_path.startswith(("/data/local/tmp/", "/sdcard/", "/storage/emulated/0/")):
        blockers.append("context_path_not_phone_local")
    return blockers


def selected_config_path(args: argparse.Namespace) -> Path | None:
    if args.model_config_spec:
        return Path(args.model_config_spec)
    if args.model_config:
        return Path(args.model_config)
    return None


def first_missing_green_field(report: dict[str, Any]) -> str:
    blockers = report.get("blockers", [])
    if not blockers:
        return "none"
    priority = [
        "gemma_e4b_model_safetensors_for_context_export_missing",
        "gemma_e4b_config_json_for_context_export_missing",
        "model_safetensors_missing",
        "qnn_context_not_generated",
        "qnn_context_utility_graph_mismatch",
        "bad_qnn_context_sha256",
    ]
    for code in priority:
        if code in blockers:
            return code
    return blockers[0]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_in_repo(path: Path | None) -> bool:
    if path is None:
        return False
    try:
        path.expanduser().resolve().relative_to(ROOT)
        return True
    except (OSError, ValueError):
        return False


def model_path_outside_git(path: Path | None) -> bool:
    if path is None:
        return False
    text = str(path)
    if text.startswith(("/data/local/tmp/", "/sdcard/", "/storage/emulated/0/", "/data/data/com.termux/files/home/")):
        return True
    return not path_in_repo(path)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate a fail-closed WaveC Gemma E4B FFN/residual QNN C++ model-library package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shlex
import struct
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from polymath_ai.polar.wavec_full_gemma_qnn import EXPECTED_BYTES, EXPECTED_DTYPE, EXPECTED_SHAPE  # noqa: E402
from polymath_ai.polar.wavec_gemma_qnn_exporter import (  # noqa: E402
    EXPECTED_GRAPH,
    EXPECTED_MODEL_ID,
    EXPECTED_MODEL_REVISION,
    REQUIRED_CONFIG,
)


SCHEMA_VERSION = "waveC_qnn_cpp_ffn_residual_generator_report_v1"
HIDDEN = 2560
SEQ = 16
INTERMEDIATE = 10240
RMS_EPS = 1.0e-6
MODEL_LIBRARY_NAME = "libgemma4_e4b_ffn_residual_layer0.so"
CONTEXT_NAME = "gemma4_e4b_ffn_residual_layer0.qnn.bin"
LAYER0_PREFIX = "model.language_model.layers.0."
REQUIRED_TENSORS = {
    "input_layernorm": {
        "key": LAYER0_PREFIX + "input_layernorm.weight",
        "shape": [HIDDEN],
        "blob": "input_layernorm_f32.raw",
        "qnn_tensor": "gemma4_layer0_input_layernorm_f32",
    },
    "mlp_gate_proj": {
        "key": LAYER0_PREFIX + "mlp.gate_proj.weight",
        "shape": [INTERMEDIATE, HIDDEN],
        "blob": "mlp_gate_proj_f32.raw",
        "qnn_tensor": "gemma4_layer0_mlp_gate_proj_f32",
    },
    "mlp_up_proj": {
        "key": LAYER0_PREFIX + "mlp.up_proj.weight",
        "shape": [INTERMEDIATE, HIDDEN],
        "blob": "mlp_up_proj_f32.raw",
        "qnn_tensor": "gemma4_layer0_mlp_up_proj_f32",
    },
    "mlp_down_proj": {
        "key": LAYER0_PREFIX + "mlp.down_proj.weight",
        "shape": [HIDDEN, INTERMEDIATE],
        "blob": "mlp_down_proj_f32.raw",
        "qnn_tensor": "gemma4_layer0_mlp_down_proj_f32",
    },
}
FAILURE_TAXONOMY = (
    "source_missing",
    "exporter_failure",
    "quantization_or_layout_failure",
    "model_library_failure",
    "context_generation_failure",
    "htp_runtime_failure",
    "consumed_tensor_failure",
)
PROBE_LADDER = [
    {
        "stage": "primitive_rmsnorm_decomposition_probe",
        "contract": "[16,2560] hidden rows; primitive reduce/multiply/add/rsqrt path, no assumed fused RMSNorm",
        "failure_stage": "quantization_or_layout_failure_or_context_generation_failure",
    },
    {
        "stage": "primitive_gelu_tanh_lowering_probe",
        "contract": "GELU-tanh decomposition with primitive multiply/add/tanh path, no assumed fused GELU",
        "failure_stage": "quantization_or_layout_failure_or_context_generation_failure",
    },
    {
        "stage": "quantized_tiny_matmul_static_weight_probe",
        "contract": "deterministic tiny MatMul/FullyConnected with explicit activation/weight dtype, scale, zero point, orientation",
        "failure_stage": "quantization_or_layout_failure_or_context_generation_failure",
    },
    {
        "stage": "full_gemma4_e4b_ffn_residual_layer0_probe",
        "contract": "[1,16,2560] -> [1,16,2560] Gemma FFN/residual island with context utility, net-run, profile, and Phase4 consumption validators",
        "failure_stage": "context_generation_failure_or_htp_runtime_failure_or_consumed_tensor_failure",
    },
]
DTYPE_LAYOUT_STOP_CONDITIONS = [
    "all_float32_htp_matmul_not_assumed_without_qairt_context_evidence",
    "fp16_or_fp32_boundary_requires_context_generator_and_net_run_acceptance",
    "preferred_internal_contract_is_explicit_quantized_activations_and_weights_with_recorded_scales_zero_points_orientation",
    "missing_scale_zero_point_orientation_or_axis_metadata_is_quantization_or_layout_failure",
    "partial_delegation_cpu_gpu_fallback_or_missing_profile_is_fail_closed",
]
REQUIRED_QNN_EVIDENCE_FIELDS = [
    "qnn_backend_path",
    "qnn_backend_sha256",
    "qnn_context_binary_sha256",
    "qnn_context_const_size",
    "qnn_context_opDataSize",
    "qnn_context_ioTensorSize",
    "qnn_context_spill_or_ddr_bytes",
    "qnn_context_hvx_threads",
    "qnn_context_binary_utility_graph_name",
    "qnn_context_binary_utility_input_shape_dtype",
    "qnn_context_binary_utility_output_shape_dtype",
    "qnn_net_run_output_bytes",
    "qnn_net_run_output_sha256",
    "qnn_profile_log_path_hash",
    "qnn_profile_viewer_parse_status",
    "qnn_execute_profile_fields",
]


def main() -> int:
    args = parse_args()
    if args.print_schema:
        print_schema()
        return 0

    report = generate_package(args)
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0 if report["status"] == "pass" else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-safetensors", default="")
    parser.add_argument("--model-safetensors-sha256", default="")
    parser.add_argument("--model-safetensors-bytes", type=int, default=0)
    parser.add_argument("--model-source-location", choices=("local", "phone_preverified"), default="phone_preverified")
    parser.add_argument("--model-config-spec", type=Path, required=False)
    parser.add_argument("--work-root", type=Path, required=False)
    parser.add_argument("--qairt-root", required=False, default="/data/local/tmp/qairt-2.44")
    parser.add_argument("--android-ndk-root", required=False, default="")
    parser.add_argument("--phone-work-root", default="/data/local/tmp/polymath_gemma4_gate/wavec/full_gemma_qnn_export")
    parser.add_argument("--phone-ssh-host", default="127.0.0.1")
    parser.add_argument("--phone-ssh-port", type=int, default=8022)
    parser.add_argument("--phone-ssh-user", default="u0_a536")
    parser.add_argument("--phone-ssh-identity", default="")
    parser.add_argument("--phone-ssh-extra-arg", action="append", default=[])
    parser.add_argument("--phone-materialization-timeout-sec", type=int, default=7200)
    parser.add_argument("--phone-materialization-plan-only", action="store_true")
    parser.add_argument("--materialize-weight-blobs", action="store_true")
    parser.add_argument(
        "--report",
        default="runtime/reports/polar_phase34_consumer_preflight/active_wave/qnn_cpp_ffn_residual_generator/qnn_cpp_ffn_residual_generator_report.json",
    )
    parser.add_argument("--print-schema", action="store_true")
    args = parser.parse_args()
    if not args.print_schema:
        if not args.model_safetensors:
            parser.error("--model-safetensors is required")
        if not args.model_safetensors_sha256:
            parser.error("--model-safetensors-sha256 is required")
        if not args.model_safetensors_bytes:
            parser.error("--model-safetensors-bytes is required")
        if not args.model_config_spec:
            parser.error("--model-config-spec is required")
        if not args.work_root:
            parser.error("--work-root is required")
    return args


def print_schema() -> None:
    print(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "graph": EXPECTED_GRAPH,
                "input": {"shape": EXPECTED_SHAPE, "dtype": EXPECTED_DTYPE, "bytes": EXPECTED_BYTES},
                "output": {"shape": EXPECTED_SHAPE, "dtype": EXPECTED_DTYPE, "bytes": EXPECTED_BYTES},
                "required_layer0_tensors": REQUIRED_TENSORS,
                "failure_taxonomy": list(FAILURE_TAXONOMY),
                "phone_materialization_contract": {
                    "method": "phone_ssh_selected_safetensors_range_extraction",
                    "requires_full_local_model_copy": False,
                    "selected_tensors_only": list(REQUIRED_TENSORS),
                    "plan_only_flag": "--phone-materialization-plan-only",
                },
                "probe_ladder": PROBE_LADDER,
                "dtype_layout_stop_conditions": DTYPE_LAYOUT_STOP_CONDITIONS,
                "required_qnn_evidence_fields": REQUIRED_QNN_EVIDENCE_FIELDS,
                "raw_boundary": "work-root must be outside git; repo receives metadata reports only",
            },
            indent=2,
            sort_keys=True,
        )
    )


def generate_package(args: argparse.Namespace) -> dict[str, Any]:
    blockers = validate_inputs(args)
    generated: dict[str, Any] = {}
    tensor_manifest: dict[str, Any] = {}
    if not blockers:
        work_root = args.work_root.expanduser().resolve()
        create_layout(work_root)
        try:
            if args.materialize_weight_blobs:
                tensor_manifest = materialize_weight_blobs(args, work_root)
            else:
                tensor_manifest = expected_weight_manifest(args)
            generated = write_generated_files(args, work_root, tensor_manifest)
        except RuntimeError as exc:
            blockers.append(str(exc))

    status = "pass" if not blockers else "blocked"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "first_missing_green_field": "none" if status == "pass" else blockers[0],
        "phase3_ready_claim": False,
        "phase4_ready_claim": False,
        "full_gemma_htp_forward_claim": False,
        "learning_claim": False,
        "graph": {
            "name": EXPECTED_GRAPH,
            "scope": "gemma4_e4b_ffn_residual_layer0",
            "input": {"shape": EXPECTED_SHAPE, "dtype": EXPECTED_DTYPE, "bytes": EXPECTED_BYTES},
            "output": {"shape": EXPECTED_SHAPE, "dtype": EXPECTED_DTYPE, "bytes": EXPECTED_BYTES},
            "op_plan": [
                "RMSNorm",
                "MatMul(gate)",
                "MatMul(up)",
                "GELU_TANH",
                "ElementWiseMultiply",
                "MatMul(down)",
                "ElementWiseAdd(residual)",
            ],
        },
        "model_source": {
            "path": args.model_safetensors,
            "sha256": args.model_safetensors_sha256,
            "bytes": args.model_safetensors_bytes,
            "source_location": args.model_source_location,
            "model_id": EXPECTED_MODEL_ID,
            "revision": EXPECTED_MODEL_REVISION,
            "materialization": {
                "requested": args.materialize_weight_blobs,
                "method": materialization_method(args),
                "phone_work_root": args.phone_work_root,
                "phone_ssh_host": args.phone_ssh_host,
                "phone_ssh_port": args.phone_ssh_port,
                "phone_ssh_user": args.phone_ssh_user,
                "plan_only": args.phone_materialization_plan_only,
                "requires_full_local_model_copy": False,
            },
        },
        "config_spec": {
            "path": str(args.model_config_spec),
            "sha256": sha256_file(args.model_config_spec) if args.model_config_spec.is_file() else "",
            "required_config": REQUIRED_CONFIG,
        },
        "qnn_cpp_generator": {
            "route": "qnn_cpp_generated_model_library",
            "qnn_op_lowering_status": "candidate_qnn_builtin_lowering_pending_compile_and_context_generation",
            "authority_note": (
                "Generated full-island C++ is not authority until the primitive/quantized probe ladder, "
                "QNN HTP context generation, qnn-net-run output, profile parse, and Phase4 consumption validate."
            ),
            "qnn_op_lowering_failure_stage_if_rejected": "quantization_or_layout_failure_or_model_library_failure_or_context_generation_failure",
            "probe_ladder_required_before_full_island": PROBE_LADDER,
            "dtype_layout_stop_conditions": DTYPE_LAYOUT_STOP_CONDITIONS,
            "required_tensors": REQUIRED_TENSORS,
            "tensor_manifest": tensor_manifest,
            "generated": generated,
        },
        "execution_contract": {
            "build_script": generated.get("build_script", {}).get("path"),
            "context_script": generated.get("context_script", {}).get("path"),
            "model_library_name": MODEL_LIBRARY_NAME,
            "context_name": CONTEXT_NAME,
            "next_validators": [
                "scripts/host/run_wavec_full_gemma_qnn_forward.py",
                "scripts/host/run_wavec_full_gemma_consumed_tensor_report.py",
            ],
            "expected_first_green_fields": [
                "primitive_rmsnorm_decomposition_probe_green",
                "primitive_gelu_tanh_lowering_probe_green",
                "quantized_tiny_matmul_static_weight_probe_green",
                "qnn_cpp_source_generated",
                "qnn_static_weight_blobs_outside_git",
                "android_model_library_built",
                "qnn_context_binary_generated",
                "qnn_context_utility_graph_match",
                "qnn_net_run_output_163840_bytes",
                "qnn_profile_metadata_present",
                "phase4_exact_tensor_consumption",
            ],
            "required_qnn_evidence_fields": REQUIRED_QNN_EVIDENCE_FIELDS,
        },
        "blockers": blockers,
        "failure_taxonomy": list(FAILURE_TAXONOMY),
        "probe_ladder": PROBE_LADDER,
        "dtype_layout_stop_conditions": DTYPE_LAYOUT_STOP_CONDITIONS,
        "required_qnn_evidence_fields": REQUIRED_QNN_EVIDENCE_FIELDS,
        "raw_payload_rules": {
            "work_root": str(args.work_root) if args.work_root else "",
            "work_root_outside_git": bool(args.work_root and not path_in_repo(args.work_root)),
            "repo_receives_metadata_only": True,
            "raw_model_context_tensor_generated_qnn_payloads_in_git": False,
        },
        "nonclaims": [
            "No C5 pass.",
            "No learning or model-quality claim.",
            "No Phase3/4 readiness.",
            "No full-Gemma HTP forward claim until QNN context/net-run/profile and Phase4 consumption validate.",
        ],
    }


def validate_inputs(args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    if not is_sha256(args.model_safetensors_sha256):
        blockers.append("model_safetensors_sha256_invalid")
    if args.model_safetensors_bytes != 15_992_595_884:
        blockers.append("model_safetensors_bytes_mismatch")
    if not args.model_config_spec.is_file():
        blockers.append("model_config_spec_missing")
    elif sha256_file(args.model_config_spec) != "942c8eb338306edb5afbcc415a1b0bf97ae5e041a26fe5eedd62226fafd04e2b":
        blockers.append("model_config_spec_sha256_mismatch")
    if args.work_root and path_in_repo(args.work_root):
        blockers.append("work_root_inside_repo")
    if args.materialize_weight_blobs and args.model_source_location == "local" and not Path(args.model_safetensors).is_file():
        blockers.append("source_missing:materialize_weight_blobs_requires_local_readable_model_safetensors")
    if args.materialize_weight_blobs and args.model_source_location == "phone_preverified":
        if not args.phone_materialization_plan_only and (not args.phone_ssh_host or not args.phone_ssh_user):
            blockers.append("source_missing:phone_materialization_ssh_config_missing")
        if args.phone_materialization_timeout_sec <= 0:
            blockers.append("source_missing:phone_materialization_timeout_invalid")
    return blockers


def create_layout(work_root: Path) -> None:
    for child in ("src", "scripts", "weights", "out", "context", "run", "metadata"):
        (work_root / child).mkdir(parents=True, exist_ok=True)


def materialization_method(args: argparse.Namespace) -> str:
    if not args.materialize_weight_blobs:
        return "not_requested"
    if args.model_source_location == "local":
        return "host_local_safetensors_selected_range_extraction"
    if args.phone_materialization_plan_only:
        return "phone_ssh_selected_safetensors_range_extraction_plan_only"
    return "phone_ssh_selected_safetensors_range_extraction"


def expected_weight_manifest(args: argparse.Namespace) -> dict[str, Any]:
    return {
        role: {
            "source_key": spec["key"],
            "expected_shape": spec["shape"],
            "expected_dtype": "bf16_or_f16_or_f32_converted_to_f32_static_blob",
            "outside_git_blob": str(args.work_root / "weights" / spec["blob"]),
            "qnn_tensor": spec["qnn_tensor"],
            "materialized": False,
        }
        for role, spec in REQUIRED_TENSORS.items()
    }


def materialize_weight_blobs(args: argparse.Namespace, work_root: Path) -> dict[str, Any]:
    if args.model_source_location == "phone_preverified":
        return materialize_phone_weight_blobs(args, work_root)
    return materialize_local_weight_blobs(Path(args.model_safetensors), work_root / "weights")


def materialize_local_weight_blobs(model_path: Path, weights_root: Path) -> dict[str, Any]:
    header, data_start = read_safetensors_header(model_path)
    manifest: dict[str, Any] = {}
    for role, spec in REQUIRED_TENSORS.items():
        entry = header.get(spec["key"])
        if not isinstance(entry, dict):
            raise RuntimeError(f"exporter_failure:missing_tensor:{spec['key']}")
        shape = entry.get("shape")
        if shape != spec["shape"]:
            raise RuntimeError(f"exporter_failure:tensor_shape_mismatch:{spec['key']}")
        dtype = str(entry.get("dtype", "")).upper()
        offsets = entry.get("data_offsets")
        if dtype not in {"BF16", "F16", "F32"}:
            raise RuntimeError(f"quantization_or_layout_failure:tensor_dtype_unsupported:{spec['key']}:{dtype}")
        if not isinstance(offsets, list) or len(offsets) != 2:
            raise RuntimeError(f"exporter_failure:tensor_offsets_invalid:{spec['key']}")
        start, stop = int(offsets[0]), int(offsets[1])
        blob_path = weights_root / spec["blob"]
        write_f32_blob(model_path, data_start + start, stop - start, dtype, blob_path)
        manifest[role] = {
            "source_key": spec["key"],
            "shape": shape,
            "source_dtype": dtype,
            "outside_git_blob": str(blob_path),
            "bytes": blob_path.stat().st_size,
            "sha256": sha256_file(blob_path),
            "qnn_tensor": spec["qnn_tensor"],
            "materialized": True,
            "materialization_method": "host_local_safetensors_selected_range_extraction",
        }
    return manifest


def materialize_phone_weight_blobs(args: argparse.Namespace, work_root: Path) -> dict[str, Any]:
    local_script = work_root / "scripts" / "phone_materialize_selected_safetensors.py"
    local_plan = work_root / "metadata" / "phone_materialization_plan.json"
    remote_root = args.phone_work_root.rstrip("/")
    remote_script = f"{remote_root}/scripts/phone_materialize_selected_safetensors.py"
    remote_manifest = f"{remote_root}/metadata/materialized_weight_manifest.json"
    local_script.write_text(render_phone_materializer_script(), encoding="utf-8")
    local_plan.write_text(
        json.dumps(phone_materialization_plan(args, remote_script, remote_manifest), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if args.phone_materialization_plan_only:
        return expected_phone_weight_manifest(args, work_root, local_script, local_plan, remote_manifest)

    run_checked(
        ssh_command(args, f"mkdir -p {shlex.quote(remote_root)}/scripts {shlex.quote(remote_root)}/metadata {shlex.quote(remote_root)}/weights"),
        "source_missing:phone_materialization_remote_mkdir_failed",
        timeout=60,
    )
    run_checked(
        scp_to_phone_command(args, local_script, remote_script),
        "source_missing:phone_materialization_script_push_failed",
        timeout=120,
    )
    remote_command = " ".join(
        [
            "python3",
            shlex.quote(remote_script),
            "--model",
            shlex.quote(args.model_safetensors),
            "--expected-sha256",
            shlex.quote(args.model_safetensors_sha256),
            "--expected-bytes",
            str(args.model_safetensors_bytes),
            "--out-root",
            shlex.quote(remote_root),
            "--manifest",
            shlex.quote(remote_manifest),
        ]
    )
    run_checked(
        ssh_command(args, remote_command),
        "source_missing:phone_materialization_remote_extract_failed",
        timeout=args.phone_materialization_timeout_sec,
    )

    local_manifest = work_root / "metadata" / "materialized_weight_manifest.json"
    run_checked(
        scp_from_phone_command(args, remote_manifest, local_manifest),
        "source_missing:phone_materialization_manifest_pull_failed",
        timeout=120,
    )
    manifest = json.loads(local_manifest.read_text(encoding="utf-8"))
    for role, spec in REQUIRED_TENSORS.items():
        remote_blob = manifest[role]["phone_blob_path"]
        local_blob = work_root / "weights" / spec["blob"]
        run_checked(
            scp_from_phone_command(args, remote_blob, local_blob),
            f"source_missing:phone_materialization_blob_pull_failed:{role}",
            timeout=args.phone_materialization_timeout_sec,
        )
        if local_blob.stat().st_size != int(manifest[role]["bytes"]):
            raise RuntimeError(f"source_missing:phone_materialization_partial_blob_transfer:{role}")
        actual_sha = sha256_file(local_blob)
        if actual_sha != manifest[role]["sha256"]:
            raise RuntimeError(f"source_missing:phone_materialization_blob_sha256_mismatch:{role}")
        manifest[role]["outside_git_blob"] = str(local_blob)
        manifest[role]["host_blob_sha256"] = actual_sha
        manifest[role]["host_blob_bytes"] = local_blob.stat().st_size
    return manifest


def expected_phone_weight_manifest(
    args: argparse.Namespace,
    work_root: Path,
    local_script: Path,
    local_plan: Path,
    remote_manifest: str,
) -> dict[str, Any]:
    manifest = expected_weight_manifest(args)
    for role, spec in REQUIRED_TENSORS.items():
        manifest[role].update(
            {
                "materialization_method": "phone_ssh_selected_safetensors_range_extraction",
                "phone_model_path": args.model_safetensors,
                "phone_work_root": args.phone_work_root,
                "phone_blob_path": f"{args.phone_work_root.rstrip('/')}/weights/{spec['blob']}",
                "remote_manifest": remote_manifest,
                "local_materializer_script": str(local_script),
                "local_materialization_plan": str(local_plan),
                "materialized": False,
                "plan_only": True,
            }
        )
    return manifest


def phone_materialization_plan(args: argparse.Namespace, remote_script: str, remote_manifest: str) -> dict[str, Any]:
    return {
        "method": "phone_ssh_selected_safetensors_range_extraction",
        "model_source": {
            "phone_path": args.model_safetensors,
            "expected_sha256": args.model_safetensors_sha256,
            "expected_bytes": args.model_safetensors_bytes,
        },
        "transport": {
            "ssh_host": args.phone_ssh_host,
            "ssh_port": args.phone_ssh_port,
            "ssh_user": args.phone_ssh_user,
            "identity_path_present": bool(args.phone_ssh_identity),
            "extra_arg_count": len(args.phone_ssh_extra_arg or []),
            "timeout_sec": args.phone_materialization_timeout_sec,
        },
        "remote": {
            "phone_work_root": args.phone_work_root,
            "script": remote_script,
            "manifest": remote_manifest,
        },
        "required_tensors": REQUIRED_TENSORS,
        "raw_boundary": {
            "copies_full_model_to_host": False,
            "copies_selected_weight_blobs_only": True,
            "host_work_root_must_be_outside_git": True,
        },
    }


def render_phone_materializer_script() -> str:
    tensors_json = json.dumps(REQUIRED_TENSORS, sort_keys=True)
    return f'''#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

TENSORS = json.loads({tensors_json!r})


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize selected Gemma E4B safetensors ranges on Termux.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-bytes", type=int, required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()

    model = Path(args.model)
    out_root = Path(args.out_root)
    weights_root = out_root / "weights"
    weights_root.mkdir(parents=True, exist_ok=True)
    Path(args.manifest).parent.mkdir(parents=True, exist_ok=True)

    if not model.is_file():
        raise SystemExit("source_missing:phone_model_path_unreadable")
    if model.stat().st_size != args.expected_bytes:
        raise SystemExit("source_missing:phone_model_size_mismatch")
    model_sha = sha256_file(model)
    if model_sha != args.expected_sha256:
        raise SystemExit("source_missing:phone_model_sha256_mismatch")

    header, data_start = read_safetensors_header(model)
    manifest = {{}}
    for role, spec in TENSORS.items():
        entry = header.get(spec["key"])
        if not isinstance(entry, dict):
            raise SystemExit(f"exporter_failure:missing_tensor:{{spec['key']}}")
        shape = entry.get("shape")
        if shape != spec["shape"]:
            raise SystemExit(f"exporter_failure:tensor_shape_mismatch:{{spec['key']}}")
        dtype = str(entry.get("dtype", "")).upper()
        if dtype not in {{"BF16", "F16", "F32"}}:
            raise SystemExit(f"quantization_or_layout_failure:tensor_dtype_unsupported:{{spec['key']}}:{{dtype}}")
        offsets = entry.get("data_offsets")
        if not isinstance(offsets, list) or len(offsets) != 2:
            raise SystemExit(f"exporter_failure:tensor_offsets_invalid:{{spec['key']}}")
        start, stop = int(offsets[0]), int(offsets[1])
        if start < 0 or stop <= start:
            raise SystemExit(f"exporter_failure:tensor_offsets_invalid:{{spec['key']}}")
        absolute_start = data_start + start
        length = stop - start
        if absolute_start + length > args.expected_bytes:
            raise SystemExit(f"exporter_failure:tensor_range_exceeds_file_size:{{spec['key']}}")

        blob = weights_root / spec["blob"]
        write_f32_blob(model, absolute_start, length, dtype, blob)
        manifest[role] = {{
            "source_key": spec["key"],
            "shape": shape,
            "source_dtype": dtype,
            "data_offsets": [start, stop],
            "absolute_data_offsets": [absolute_start, absolute_start + length],
            "source_bytes": length,
            "phone_blob_path": str(blob),
            "bytes": blob.stat().st_size,
            "sha256": sha256_file(blob),
            "qnn_tensor": spec["qnn_tensor"],
            "materialized": True,
            "materialization_method": "phone_ssh_selected_safetensors_range_extraction",
        }}
    Path(args.manifest).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
    print(args.manifest)
    return 0


def read_safetensors_header(path: Path) -> tuple[dict, int]:
    with path.open("rb") as handle:
        raw_len = handle.read(8)
        if len(raw_len) != 8:
            raise SystemExit("exporter_failure:safetensors_header_length_missing")
        header_len = struct.unpack("<Q", raw_len)[0]
        header = json.loads(handle.read(header_len).decode("utf-8"))
    return header, 8 + int(header_len)


def write_f32_blob(model_path: Path, offset: int, length: int, dtype: str, out: Path) -> None:
    raw = read_range(model_path, offset, length)
    with out.open("wb") as handle:
        if dtype == "F32":
            handle.write(raw)
            return
        if dtype == "F16":
            for index in range(0, len(raw), 2):
                value = struct.unpack("<e", raw[index : index + 2])[0]
                handle.write(struct.pack("<f", float(value)))
            return
        for index in range(0, len(raw), 2):
            bits = struct.unpack("<H", raw[index : index + 2])[0]
            handle.write(struct.pack("<I", bits << 16))


def read_range(path: Path, offset: int, length: int) -> bytes:
    with path.open("rb") as handle:
        handle.seek(offset)
        data = handle.read(length)
    if len(data) != length:
        raise SystemExit("exporter_failure:safetensors_tensor_range_truncated")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
'''


def ssh_target(args: argparse.Namespace) -> str:
    return f"{args.phone_ssh_user}@{args.phone_ssh_host}" if args.phone_ssh_user else args.phone_ssh_host


def ssh_options(args: argparse.Namespace) -> list[str]:
    options = [
        "-p",
        str(args.phone_ssh_port),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=20",
        "-o",
        "StrictHostKeyChecking=accept-new",
    ]
    if args.phone_ssh_identity:
        options.extend(["-i", args.phone_ssh_identity])
    options.extend(args.phone_ssh_extra_arg or [])
    return options


def ssh_command(args: argparse.Namespace, remote_command: str) -> list[str]:
    return ["ssh", *ssh_options(args), ssh_target(args), remote_command]


def scp_to_phone_command(args: argparse.Namespace, local: Path, remote: str) -> list[str]:
    return ["scp", *scp_options(args), str(local), f"{ssh_target(args)}:{remote}"]


def scp_from_phone_command(args: argparse.Namespace, remote: str, local: Path) -> list[str]:
    local.parent.mkdir(parents=True, exist_ok=True)
    return ["scp", *scp_options(args), f"{ssh_target(args)}:{remote}", str(local)]


def scp_options(args: argparse.Namespace) -> list[str]:
    options = ssh_options(args)
    scp = []
    index = 0
    while index < len(options):
        option = options[index]
        if option == "-p":
            scp.extend(["-P", options[index + 1]])
            index += 2
            continue
        scp.append(option)
        index += 1
    return scp


def run_checked(command: list[str], failure_field: str, *, timeout: int) -> None:
    completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False)
    if completed.returncode != 0:
        stderr = completed.stderr.strip().splitlines()
        stdout = completed.stdout.strip().splitlines()
        detail = stderr[-1] if stderr else (stdout[-1] if stdout else f"exit_code_{completed.returncode}")
        raise RuntimeError(f"{failure_field}:{detail[:240]}")


def read_safetensors_header(path: Path) -> tuple[dict[str, Any], int]:
    with path.open("rb") as handle:
        raw_len = handle.read(8)
        if len(raw_len) != 8:
            raise RuntimeError("exporter_failure:safetensors_header_length_missing")
        header_len = struct.unpack("<Q", raw_len)[0]
        header = json.loads(handle.read(header_len).decode("utf-8"))
    return header, 8 + int(header_len)


def write_f32_blob(model_path: Path, offset: int, length: int, dtype: str, out: Path) -> None:
    raw = read_range(model_path, offset, length)
    with out.open("wb") as handle:
        if dtype == "F32":
            handle.write(raw)
            return
        if dtype == "F16":
            for index in range(0, len(raw), 2):
                value = struct.unpack("<e", raw[index : index + 2])[0]
                handle.write(struct.pack("<f", float(value)))
            return
        for index in range(0, len(raw), 2):
            bits = struct.unpack("<H", raw[index : index + 2])[0]
            handle.write(struct.pack("<I", bits << 16))


def read_range(path: Path, offset: int, length: int) -> bytes:
    with path.open("rb") as handle:
        handle.seek(offset)
        data = handle.read(length)
    if len(data) != length:
        raise RuntimeError("exporter_failure:safetensors_tensor_range_truncated")
    return data


def write_generated_files(args: argparse.Namespace, work_root: Path, tensor_manifest: dict[str, Any]) -> dict[str, Any]:
    cpp = work_root / "src" / "gemma4_e4b_ffn_residual_layer0_qnn_model.cpp"
    build = work_root / "scripts" / "build_android_model_library.sh"
    context = work_root / "scripts" / "generate_phone_context.sh"
    metadata = work_root / "metadata" / "tensor_manifest.json"
    cpp.write_text(render_cpp_source(), encoding="utf-8")
    build.write_text(render_build_script(args, work_root), encoding="utf-8")
    context.write_text(render_context_script(args), encoding="utf-8")
    metadata.write_text(json.dumps(tensor_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    build.chmod(0o755)
    context.chmod(0o755)
    return {
        "cpp_source": file_payload(cpp),
        "build_script": file_payload(build),
        "context_script": file_payload(context),
        "tensor_manifest": file_payload(metadata),
    }


def render_cpp_source() -> str:
    return f'''#include "QnnModel.hpp"
#include "QnnOpDef.h"

#define DO_GRAPH_NODE_VALIDATIONS 1

using namespace qnn_wrapper_api;

namespace {{
Qnn_Tensor_t appTensor(const char* name, uint32_t* dims, uint32_t rank, Qnn_TensorType_t type) {{
  return (Qnn_Tensor_t){{
      .version = QNN_TENSOR_VERSION_1,
      .v1      = {{.id             = 0,
             .name           = name,
             .type           = type,
             .dataFormat     = QNN_TENSOR_DATA_FORMAT_FLAT_BUFFER,
             .dataType       = QNN_DATATYPE_FLOAT_32,
             .quantizeParams = {{QNN_DEFINITION_UNDEFINED,
                                QNN_QUANTIZATION_ENCODING_UNDEFINED,
                                {{.scaleOffsetEncoding = {{.scale = 0.0f, .offset = 0}}}}}},
             .rank           = rank,
             .dimensions     = dims,
             .memType        = QNN_TENSORMEMTYPE_RAW,
             .clientBuf      = {{.data = nullptr, .dataSize = 0}}}}}};
}}

Qnn_Tensor_t staticTensor(const char* name, uint32_t* dims, uint32_t rank, void* data, uint32_t dataSize) {{
  Qnn_Tensor_t tensor = appTensor(name, dims, rank, QNN_TENSOR_TYPE_STATIC);
  tensor.v1.clientBuf = {{.data = data, .dataSize = dataSize}};
  return tensor;
}}
}}

extern "C" {{
QNN_API
ModelError_t QnnModel_composeGraphs(Qnn_BackendHandle_t backendHandle,
                                    QNN_INTERFACE_VER_TYPE interface,
                                    Qnn_ContextHandle_t contextHandle,
                                    const GraphConfigInfo_t** graphsConfigInfo,
                                    const uint32_t numGraphsConfigInfo,
                                    GraphInfoPtr_t** graphsInfo,
                                    uint32_t* numGraphsInfo,
                                    bool debug,
                                    QnnLog_Callback_t logCallback,
                                    QnnLog_Level_t maxLogLevel) {{
  (void)logCallback;
  (void)maxLogLevel;
  ModelError_t err = MODEL_NO_ERROR;
  QnnModel model;
  const QnnGraph_Config_t** graphConfigs = nullptr;
  VALIDATE(getQnnGraphConfigFromInfo("{EXPECTED_GRAPH}", graphsConfigInfo, numGraphsConfigInfo, graphConfigs), err);
  VALIDATE(model.initialize(backendHandle, interface, contextHandle, "{EXPECTED_GRAPH}", debug, DO_GRAPH_NODE_VALIDATIONS, graphConfigs), err);

  uint32_t dims_hidden[] = {{1, {SEQ}, {HIDDEN}}};
  uint32_t dims_intermediate[] = {{1, {SEQ}, {INTERMEDIATE}}};
  uint32_t dims_norm[] = {{{HIDDEN}}};
  uint32_t dims_gate_w[] = {{{INTERMEDIATE}, {HIDDEN}}};
  uint32_t dims_down_w[] = {{{HIDDEN}, {INTERMEDIATE}}};

  VALIDATE(model.addTensor("gemma_hidden_input", appTensor("gemma_hidden_input", dims_hidden, 3, QNN_TENSOR_TYPE_APP_WRITE)), err);
  VALIDATE(model.addTensor("gemma_layer0_normed", appTensor("gemma_layer0_normed", dims_hidden, 3, QNN_TENSOR_TYPE_NATIVE)), err);
  VALIDATE(model.addTensor("gemma_layer0_gate", appTensor("gemma_layer0_gate", dims_intermediate, 3, QNN_TENSOR_TYPE_NATIVE)), err);
  VALIDATE(model.addTensor("gemma_layer0_up", appTensor("gemma_layer0_up", dims_intermediate, 3, QNN_TENSOR_TYPE_NATIVE)), err);
  VALIDATE(model.addTensor("gemma_layer0_gelu", appTensor("gemma_layer0_gelu", dims_intermediate, 3, QNN_TENSOR_TYPE_NATIVE)), err);
  VALIDATE(model.addTensor("gemma_layer0_ffn", appTensor("gemma_layer0_ffn", dims_intermediate, 3, QNN_TENSOR_TYPE_NATIVE)), err);
  VALIDATE(model.addTensor("gemma_layer0_down", appTensor("gemma_layer0_down", dims_hidden, 3, QNN_TENSOR_TYPE_NATIVE)), err);
  VALIDATE(model.addTensor("gemma_hidden_output", appTensor("gemma_hidden_output", dims_hidden, 3, QNN_TENSOR_TYPE_APP_READ)), err);

  VALIDATE(model.addTensor("gemma4_layer0_input_layernorm_f32", staticTensor("gemma4_layer0_input_layernorm_f32", dims_norm, 1, BINVARSTART(input_layernorm_f32), BINLEN(input_layernorm_f32))), err);
  VALIDATE(model.addTensor("gemma4_layer0_mlp_gate_proj_f32", staticTensor("gemma4_layer0_mlp_gate_proj_f32", dims_gate_w, 2, BINVARSTART(mlp_gate_proj_f32), BINLEN(mlp_gate_proj_f32))), err);
  VALIDATE(model.addTensor("gemma4_layer0_mlp_up_proj_f32", staticTensor("gemma4_layer0_mlp_up_proj_f32", dims_gate_w, 2, BINVARSTART(mlp_up_proj_f32), BINLEN(mlp_up_proj_f32))), err);
  VALIDATE(model.addTensor("gemma4_layer0_mlp_down_proj_f32", staticTensor("gemma4_layer0_mlp_down_proj_f32", dims_down_w, 2, BINVARSTART(mlp_down_proj_f32), BINLEN(mlp_down_proj_f32))), err);

  // Candidate QNN builtin lowering. Execution must compile and run this against
  // installed QAIRT headers. If a constant, parameter, layout, or HTP backend
  // contract is rejected, classify with the exact compiler/QNN stderr stage.
  const char* rms_inputs[] = {{"gemma_hidden_input", "gemma4_layer0_input_layernorm_f32"}};
  Qnn_Tensor_t rms_outputs[] = {{appTensor("gemma_layer0_normed", dims_hidden, 3, QNN_TENSOR_TYPE_NATIVE)}};
  VALIDATE(model.addNode(QNN_OPCONFIG_VERSION_1, "gemma4_layer0_rmsnorm", QNN_OP_PACKAGE_NAME_QTI_AISW, QNN_OP_RMS_NORM, nullptr, 0, rms_inputs, 2, rms_outputs, 1), err);

  const char* gate_inputs[] = {{"gemma_layer0_normed", "gemma4_layer0_mlp_gate_proj_f32"}};
  Qnn_Tensor_t gate_outputs[] = {{appTensor("gemma_layer0_gate", dims_intermediate, 3, QNN_TENSOR_TYPE_NATIVE)}};
  VALIDATE(model.addNode(QNN_OPCONFIG_VERSION_1, "gemma4_layer0_gate_matmul", QNN_OP_PACKAGE_NAME_QTI_AISW, QNN_OP_MAT_MUL, nullptr, 0, gate_inputs, 2, gate_outputs, 1), err);

  const char* up_inputs[] = {{"gemma_layer0_normed", "gemma4_layer0_mlp_up_proj_f32"}};
  Qnn_Tensor_t up_outputs[] = {{appTensor("gemma_layer0_up", dims_intermediate, 3, QNN_TENSOR_TYPE_NATIVE)}};
  VALIDATE(model.addNode(QNN_OPCONFIG_VERSION_1, "gemma4_layer0_up_matmul", QNN_OP_PACKAGE_NAME_QTI_AISW, QNN_OP_MAT_MUL, nullptr, 0, up_inputs, 2, up_outputs, 1), err);

  const char* gelu_inputs[] = {{"gemma_layer0_gate"}};
  Qnn_Tensor_t gelu_outputs[] = {{appTensor("gemma_layer0_gelu", dims_intermediate, 3, QNN_TENSOR_TYPE_NATIVE)}};
  VALIDATE(model.addNode(QNN_OPCONFIG_VERSION_1, "gemma4_layer0_gelu_tanh", QNN_OP_PACKAGE_NAME_QTI_AISW, QNN_OP_GELU, nullptr, 0, gelu_inputs, 1, gelu_outputs, 1), err);

  const char* multiply_inputs[] = {{"gemma_layer0_gelu", "gemma_layer0_up"}};
  Qnn_Tensor_t multiply_outputs[] = {{appTensor("gemma_layer0_ffn", dims_intermediate, 3, QNN_TENSOR_TYPE_NATIVE)}};
  VALIDATE(model.addNode(QNN_OPCONFIG_VERSION_1, "gemma4_layer0_gated_multiply", QNN_OP_PACKAGE_NAME_QTI_AISW, QNN_OP_ELEMENT_WISE_MULTIPLY, nullptr, 0, multiply_inputs, 2, multiply_outputs, 1), err);

  const char* down_inputs[] = {{"gemma_layer0_ffn", "gemma4_layer0_mlp_down_proj_f32"}};
  Qnn_Tensor_t down_outputs[] = {{appTensor("gemma_layer0_down", dims_hidden, 3, QNN_TENSOR_TYPE_NATIVE)}};
  VALIDATE(model.addNode(QNN_OPCONFIG_VERSION_1, "gemma4_layer0_down_matmul", QNN_OP_PACKAGE_NAME_QTI_AISW, QNN_OP_MAT_MUL, nullptr, 0, down_inputs, 2, down_outputs, 1), err);

  const char* residual_inputs[] = {{"gemma_hidden_input", "gemma_layer0_down"}};
  Qnn_Tensor_t residual_outputs[] = {{appTensor("gemma_hidden_output", dims_hidden, 3, QNN_TENSOR_TYPE_APP_READ)}};
  VALIDATE(model.addNode(QNN_OPCONFIG_VERSION_1, "gemma4_layer0_residual_add", QNN_OP_PACKAGE_NAME_QTI_AISW, QNN_OP_ELEMENT_WISE_ADD, nullptr, 0, residual_inputs, 2, residual_outputs, 1), err);

  QnnModel* models[] = {{&model}};
  uint32_t numModels = 1;
  VALIDATE(getGraphInfoFromModels(*models, numModels, graphsInfo), err);
  *numGraphsInfo = numModels;

  return err;
}}

QNN_API
ModelError_t QnnModel_freeGraphsInfo(GraphInfoPtr_t** graphs, uint32_t numGraphsInfo) {{
  return qnn_wrapper_api::freeGraphsInfo(graphs, numGraphsInfo);
}}
}}
'''


def render_build_script(args: argparse.Namespace, work_root: Path) -> str:
    qairt = args.qairt_root.rstrip("/")
    ndk = args.android_ndk_root.rstrip("/") or "${ANDROID_NDK_ROOT:?ANDROID_NDK_ROOT required}"
    return f"""#!/usr/bin/env bash
set -euo pipefail
WORK_ROOT={shlex.quote(str(work_root))}
Q={shlex.quote(qairt)}
NDK={shlex.quote(ndk)}
mkdir -p "$WORK_ROOT/out" "$WORK_ROOT/obj"
"$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android35-clang++" \\
  -std=c++20 -O2 -fPIC -fvisibility=hidden -shared \\
  "-DQNN_API=__attribute__((visibility(\\\"default\\\")))" \\
  -I"$Q/include/QNN" -I"$Q/share/QNN/converter/jni" -I"$Q/share/QNN/converter/jni/linux" \\
  "$Q/share/QNN/converter/jni/QnnModel.cpp" \\
  "$Q/share/QNN/converter/jni/QnnWrapperUtils.cpp" \\
  "$Q/share/QNN/converter/jni/linux/QnnModelPal.cpp" \\
  "$WORK_ROOT/src/gemma4_e4b_ffn_residual_layer0_qnn_model.cpp" \\
  -ldl -o "$WORK_ROOT/out/{MODEL_LIBRARY_NAME}"
sha256sum "$WORK_ROOT/out/{MODEL_LIBRARY_NAME}" > "$WORK_ROOT/out/model_library.sha256"
wc -c "$WORK_ROOT/out/{MODEL_LIBRARY_NAME}" > "$WORK_ROOT/out/model_library.bytes"
"""


def render_context_script(args: argparse.Namespace) -> str:
    phone_root = args.phone_work_root.rstrip("/")
    qairt = args.qairt_root.rstrip("/")
    return f"""#!/usr/bin/env bash
set -euo pipefail
PHONE_ROOT={shlex.quote(phone_root)}
Q={shlex.quote(qairt)}
MODEL="$PHONE_ROOT/models/{MODEL_LIBRARY_NAME}"
CONTEXT_DIR="$PHONE_ROOT/context"
mkdir -p "$CONTEXT_DIR"
"$Q/bin/aarch64-android/qnn-context-binary-generator" \\
  --model="$MODEL" \\
  --backend="$Q/lib/aarch64-android/libQnnHtp.so" \\
  --binary_file="{CONTEXT_NAME}" \\
  --output_dir="$CONTEXT_DIR" \\
  --log_level info > "$CONTEXT_DIR/context_stdout.log" 2> "$CONTEXT_DIR/context_stderr.log"
"$Q/bin/aarch64-android/qnn-context-binary-utility" \\
  --context_binary="$CONTEXT_DIR/{CONTEXT_NAME}" \\
  --json_file="$CONTEXT_DIR/context_info.json" \\
  > "$CONTEXT_DIR/utility_stdout.log" 2> "$CONTEXT_DIR/utility_stderr.log"
sha256sum "$CONTEXT_DIR/{CONTEXT_NAME}" > "$CONTEXT_DIR/context.sha256"
wc -c "$CONTEXT_DIR/{CONTEXT_NAME}" > "$CONTEXT_DIR/context.bytes"
"""


def file_payload(path: Path) -> dict[str, Any]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def path_in_repo(path: Path) -> bool:
    try:
        path.expanduser().resolve().relative_to(ROOT)
        return True
    except (OSError, ValueError):
        return False


def is_sha256(value: str) -> bool:
    return len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())

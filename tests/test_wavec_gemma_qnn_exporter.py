from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from polymath_ai.polar.wavec_full_gemma_qnn import EXPECTED_BYTES, EXPECTED_DTYPE, EXPECTED_SHAPE
from polymath_ai.polar.wavec_gemma_qnn_exporter import (
    AUTHORITY_MATERIAL,
    EXPECTED_GRAPH,
    EXPECTED_MODEL_ID,
    EXPECTED_MODEL_REVISION,
    EXPECTED_PRODUCER_KIND,
    EXPORTER_SCHEMA_VERSION,
    REQUIRED_CONFIG,
    validate_gemma_decoder_to_qnn_exporter_report,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
PHONE_ROOT = "/data/local/tmp/polymath_gemma4_gate/wavec/full_gemma_qnn_export"
BACKEND = "/data/local/tmp/qairt-2.44/lib/aarch64-android/libQnnHtp.so"
SCRIPT = Path("scripts/host/run_wavec_gemma_decoder_to_qnn_exporter.py")


def valid_exporter_report() -> dict:
    return {
        "schema_version": EXPORTER_SCHEMA_VERSION,
        "status": "pass",
        "phase3_ready_claim": False,
        "phase4_ready_claim": False,
        "learning_claim": False,
        "full_gemma_htp_forward_claim": False,
        "authority_material": AUTHORITY_MATERIAL,
        "model_source": {
            "model_id": EXPECTED_MODEL_ID,
            "revision": EXPECTED_MODEL_REVISION,
            "path": "/outside-git/gemma4_e4b/model.safetensors",
            "outside_git": True,
            "config_json_present": True,
            "model_safetensors_present": True,
            "model_safetensors_sha256": SHA_A,
            "model_safetensors_bytes": 15_992_595_884,
            "config": dict(REQUIRED_CONFIG),
        },
        "graph": {
            "name": EXPECTED_GRAPH,
            "producer_kind": EXPECTED_PRODUCER_KIND,
            "scope": "gemma4_e4b_ffn_residual_layer0",
            "input": {"shape": EXPECTED_SHAPE, "dtype": EXPECTED_DTYPE, "bytes": EXPECTED_BYTES},
            "output": {"shape": EXPECTED_SHAPE, "dtype": EXPECTED_DTYPE, "bytes": EXPECTED_BYTES},
        },
        "conversion": {
            "route": "qnn_cpp_model_library_to_context",
            "preferred_route": "qnn_cpp_generated_model_library",
            "litert_aot_primary": False,
            "uses_real_restored_weights": True,
            "random_init_weights": False,
            "metadata_only_manifest": False,
            "cpu_fallback": False,
            "qairt_sdk_version": "2.44",
            "android_ndk_version": "r27",
            "qnn_op_plan": ["RMSNorm", "MatMul", "ElementWiseAdd"],
            "model_library": {
                "path": f"{PHONE_ROOT}/models/libgemma4_e4b_ffn_residual_layer0.so",
                "outside_git": True,
                "sha256": SHA_B,
                "bytes": 123456,
            },
        },
        "qnn_context": {
            "backend_execution": "qnn_htp",
            "cpu_fallback": False,
            "context_generated": True,
            "qairt_root": "/data/local/tmp/qairt-2.44",
            "backend": BACKEND,
            "context_path": f"{PHONE_ROOT}/context/gemma4_e4b_ffn_residual_layer0.qnn.bin",
            "context_sha256": SHA_C,
            "context_bytes": 654321,
            "graph_name": EXPECTED_GRAPH,
            "context_utility_graph_match": True,
            "tool_identities": {
                "qnn_context_binary_generator": {
                    "path": "/data/local/tmp/qairt-2.44/bin/aarch64-android/qnn-context-binary-generator",
                    "identity_sha256": SHA_A,
                },
                "qnn_context_binary_utility": {
                    "path": "/data/local/tmp/qairt-2.44/bin/aarch64-android/qnn-context-binary-utility",
                    "identity_sha256": SHA_B,
                },
                "qnn_net_run": {
                    "path": "/data/local/tmp/qairt-2.44/bin/aarch64-android/qnn-net-run",
                    "identity_sha256": SHA_C,
                },
            },
        },
        "raw_payload_rules": {
            "raw_model_context_tensor_payloads_outside_git": True,
            "raw_payloads_in_git": False,
            "metadata_report_only_in_repo": True,
            "repo_paths": ["runtime/reports/polar_phase34_consumer_preflight/wavec/report.json"],
        },
    }


def test_valid_exporter_report_passes() -> None:
    assert validate_gemma_decoder_to_qnn_exporter_report(valid_exporter_report()) == []


def test_rejects_relu_identity_qwen_graphs() -> None:
    for graph in ["gemma_hidden2560_relu", "gemma_hidden2560_identity_add", "qwen_block"]:
        report = valid_exporter_report()
        report["graph"]["name"] = graph
        report["qnn_context"]["graph_name"] = graph

        blockers = validate_gemma_decoder_to_qnn_exporter_report(report)

        assert "wrong_graph_name" in blockers
        assert "qnn_context_graph_name_mismatch" in blockers


def test_rejects_metadata_only_and_fallback_routes() -> None:
    report = valid_exporter_report()
    report["conversion"]["metadata_only_manifest"] = True
    report["conversion"]["cpu_fallback"] = True
    report["qnn_context"]["backend_execution"] = "cpu_reference"
    report["qnn_context"]["cpu_fallback"] = True

    blockers = validate_gemma_decoder_to_qnn_exporter_report(report)

    assert "conversion_metadata_only_manifest_true" in blockers
    assert "conversion_cpu_fallback_true" in blockers
    assert "qnn_backend_execution_not_htp" in blockers
    assert "qnn_cpu_fallback_true" in blockers


def test_rejects_litert_aot_as_primary_route() -> None:
    report = valid_exporter_report()
    report["conversion"]["route"] = "litert_aot_to_qnn_context"
    report["conversion"]["litert_aot_primary"] = True

    blockers = validate_gemma_decoder_to_qnn_exporter_report(report)

    assert "wrong_conversion_route" in blockers
    assert "litert_aot_marked_primary" in blockers


def test_rejects_wrong_tensor_shape_and_context_without_utility_match() -> None:
    report = valid_exporter_report()
    report["graph"]["output"]["bytes"] = 1
    report["qnn_context"]["context_utility_graph_match"] = False

    blockers = validate_gemma_decoder_to_qnn_exporter_report(report)

    assert "graph_output_wrong_bytes" in blockers
    assert "qnn_context_utility_graph_mismatch" in blockers


def test_rejects_raw_export_payload_in_repo_path() -> None:
    report = valid_exporter_report()
    report["raw_payload_rules"]["repo_paths"] = ["runtime/reports/bad_context.qnn.bin"]

    assert "raw_export_payload_path_in_repo" in validate_gemma_decoder_to_qnn_exporter_report(report)


def test_exporter_script_blocks_without_model_source(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--report", str(report)],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert result.returncode == 2
    assert payload["status"] == "blocked"
    assert payload["first_missing_green_field"] == "gemma_e4b_model_safetensors_for_context_export_missing"
    assert "gemma_e4b_model_safetensors_for_context_export_missing" in payload["blockers"]
    assert payload["conversion"]["route"] == "qnn_cpp_model_library_to_context"

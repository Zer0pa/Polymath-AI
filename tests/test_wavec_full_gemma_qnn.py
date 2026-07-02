from __future__ import annotations

from polymath_ai.polar.wavec_full_gemma_qnn import (
    AUTHORITY_MATERIAL,
    CONSUMED_SCHEMA_VERSION,
    EXPECTED_BYTES,
    EXPECTED_DTYPE,
    EXPECTED_SHAPE,
    FORWARD_SCHEMA_VERSION,
    PRODUCER_KIND,
    parse_qnn_profile_viewer_text,
    validate_full_gemma_consumed_tensor_report,
    validate_full_gemma_qnn_forward_report,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
GRAPH = "gemma_e4b_decoder_block0_forward_island"
BACKEND = "/data/local/tmp/qairt-2.44/lib/aarch64-android/libQnnHtp.so"


def valid_forward_report() -> dict:
    return {
        "schema_version": FORWARD_SCHEMA_VERSION,
        "status": "pass",
        "corpus_phase": "C1",
        "phase3_ready_claim": False,
        "phase4_ready_claim": False,
        "learning_claim": False,
        "authority_material": AUTHORITY_MATERIAL,
        "qnn": {
            "producer_kind": PRODUCER_KIND,
            "backend_execution": "qnn_htp",
            "cpu_fallback": False,
            "qnn_htp_backend_verified": True,
            "context_path": "/data/local/tmp/polymath_gemma4_gate/wavec/context/full_gemma.qnn.bin",
            "context_sha256": SHA_A,
            "backend": BACKEND,
            "graph": GRAPH,
            "input": {
                "path": "/sdcard/Download/polymath_phase34/wavec/input.f32.bin",
                "shape": EXPECTED_SHAPE,
                "dtype": EXPECTED_DTYPE,
                "bytes": EXPECTED_BYTES,
                "sha256": SHA_B,
                "packet_sha256": SHA_B,
            },
            "output": {
                "path": "/sdcard/Download/polymath_phase34/wavec/output.raw",
                "shape": EXPECTED_SHAPE,
                "dtype": EXPECTED_DTYPE,
                "bytes": EXPECTED_BYTES,
                "sha256": SHA_C,
                "packet_sha256": SHA_B,
            },
            "profile": {
                "qnn_profile_parse_attempted": True,
                "qnn_net_run_wall_ms": 548.272958,
                "qnn_accelerator_execute_ms": None,
                "qnn_accelerator_execute_ms_unavailable_reason": "profile_viewer_did_not_expose_execute_duration",
                "profile_log": {
                    "remote_path": "/sdcard/Download/polymath_phase34/wavec/run/qnn-profiling-data_0.log",
                    "sha256": SHA_D,
                    "bytes": 4096,
                },
            },
        },
        "raw_payload_rules": {
            "raw_pjp1_pulled_to_host": False,
            "raw_qnn_output_pulled_to_repo": False,
            "raw_model_or_checkpoint_pulled_to_repo": False,
            "compact_hash_report_only": True,
            "repo_paths": ["runtime/reports/polar_phase34_consumer_preflight/wavec/report.json"],
        },
    }


def valid_consumed_report() -> dict:
    return {
        "schema_version": CONSUMED_SCHEMA_VERSION,
        "status": "pass",
        "corpus_phase": "C1",
        "phase3_ready_claim": False,
        "phase4_ready_claim": False,
        "learning_claim": False,
        "authority_material": AUTHORITY_MATERIAL,
        "qnn_forward_blockers": [],
        "phase4_bridge_blockers": [],
        "qnn_forward": {
            "context_sha256": SHA_A,
            "graph": GRAPH,
            "backend": BACKEND,
            "output_sha256": SHA_C,
        },
        "phase4_consumption": {
            "phase3_output_sha256": SHA_C,
            "phase3_graph": GRAPH,
            "phase3_backend": BACKEND,
            "phase3_context_sha256": SHA_A,
            "exact_tensor_sha256_match": True,
            "graph_match": True,
            "backend_match": True,
            "context_sha256_match": True,
            "consumed_output_causes_update": True,
            "adapter_changed": True,
            "adapter_delta_norm_l2": 2.18e-7,
        },
        "raw_payload_rules": {
            "raw_suffix_scan_count_zero": True,
            "raw_payloads_in_git": False,
        },
    }


def test_valid_forward_report_passes() -> None:
    assert validate_full_gemma_qnn_forward_report(valid_forward_report()) == []


def test_rejects_relu_graph_as_full_gemma() -> None:
    report = valid_forward_report()
    report["qnn"]["graph"] = "gemma_hidden2560_relu"

    blockers = validate_full_gemma_qnn_forward_report(report)

    assert "disallowed_full_gemma_graph:gemma_hidden2560_relu" in blockers


def test_rejects_identity_graph_as_full_gemma() -> None:
    report = valid_forward_report()
    report["qnn"]["graph"] = "gemma_hidden2560_identity_add"

    blockers = validate_full_gemma_qnn_forward_report(report)

    assert "disallowed_full_gemma_graph:gemma_hidden2560_identity_add" in blockers


def test_rejects_cpu_fallback_as_qnn_green() -> None:
    report = valid_forward_report()
    report["qnn"]["backend_execution"] = "cpu_reference"
    report["qnn"]["cpu_fallback"] = True

    blockers = validate_full_gemma_qnn_forward_report(report)

    assert "qnn_backend_execution_not_htp" in blockers
    assert "qnn_cpu_fallback_true" in blockers


def test_requires_profile_log_identity() -> None:
    report = valid_forward_report()
    report["qnn"]["profile"]["profile_log"]["sha256"] = ""

    blockers = validate_full_gemma_qnn_forward_report(report)

    assert "bad_qnn_profile_log_sha256" in blockers


def test_rejects_raw_payload_path_in_repo() -> None:
    report = valid_forward_report()
    report["raw_payload_rules"]["repo_paths"] = ["runtime/reports/bad_tensor.raw"]

    assert "raw_payload_path_in_repo" in validate_full_gemma_qnn_forward_report(report)


def test_profile_parser_extracts_execute_duration() -> None:
    parsed = parse_qnn_profile_viewer_text("Graph Execute qnn_partition_0: 1234 us\n")

    assert parsed["qnn_profile_parse_attempted"] is True
    assert parsed["qnn_accelerator_execute_ms"] == 1.234
    assert parsed["qnn_accelerator_execute_ms_unavailable_reason"] is None


def test_valid_consumed_report_passes() -> None:
    assert validate_full_gemma_consumed_tensor_report(valid_consumed_report()) == []


def test_consumed_report_rejects_tensor_mismatch() -> None:
    report = valid_consumed_report()
    report["phase4_consumption"]["exact_tensor_sha256_match"] = False

    assert "phase4_tensor_sha256_mismatch" in validate_full_gemma_consumed_tensor_report(report)


def test_consumed_report_rejects_upstream_blockers() -> None:
    report = valid_consumed_report()
    report["qnn_forward_blockers"] = ["disallowed_full_gemma_graph:gemma_hidden2560_relu"]

    assert "qnn_forward_blockers_present" in validate_full_gemma_consumed_tensor_report(report)


def test_consumed_report_rejects_unchanged_adapter() -> None:
    report = valid_consumed_report()
    report["phase4_consumption"]["adapter_changed"] = False

    assert "adapter_hash_unchanged_after_update" in validate_full_gemma_consumed_tensor_report(report)

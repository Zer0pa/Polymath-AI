"""Fail-closed contracts for the WaveC Gemma decoder-to-QNN exporter."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from polymath_ai.polar.wavec_full_gemma_qnn import (
    ALLOWED_PHONE_PREFIXES,
    DISALLOWED_FULL_GEMMA_GRAPHS,
    EXPECTED_BYTES,
    EXPECTED_DTYPE,
    EXPECTED_SHAPE,
    FORBIDDEN_REPO_RAW_SUFFIXES,
    SHA256_PATTERN,
)


EXPORTER_SCHEMA_VERSION = "waveC_gemma_decoder_to_qnn_exporter_report_v1"
EXPORTER_STATUS_PASS = "pass"
EXPECTED_MODEL_ID = "google/gemma-4-E4B"
EXPECTED_MODEL_REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
EXPECTED_ORIGINAL_CONFIG_OID = "080fd8d51bb6e846df168157c9d57b928a2a2687"
EXPECTED_ORIGINAL_CONFIG_SIZE_BYTES = 5105
EXPECTED_GRAPH = "gemma4_e4b_ffn_residual_layer0_forward_island_seq16_hidden2560"
EXPECTED_PRODUCER_KIND = "gemma4_e4b_decoder_to_qnn_context_exporter"
AUTHORITY_MATERIAL = "waveC_gemma_decoder_to_qnn_exporter_preflight_only"
DISALLOWED_GRAPH_TOKENS = ("qwen", "smollm", "relu", "identity")
REQUIRED_CONFIG = {
    "hidden_size": 2560,
    "num_hidden_layers": 42,
    "num_attention_heads": 8,
    "num_key_value_heads": 2,
    "head_dim": 256,
    "intermediate_size": 10240,
}
RAW_EXPORT_SUFFIXES = FORBIDDEN_REPO_RAW_SUFFIXES + (".tflite", ".so", ".cpp", ".cc")


def validate_gemma_decoder_to_qnn_exporter_report(
    report: dict[str, Any], *, require_status: bool = True
) -> list[str]:
    """Return blocker codes for a Gemma decoder-to-QNN exporter report."""

    blockers: list[str] = []
    require_equal(blockers, report.get("schema_version"), EXPORTER_SCHEMA_VERSION, "wrong_schema_version")
    if require_status:
        require_equal(blockers, report.get("status"), EXPORTER_STATUS_PASS, "status_not_pass")
    require_false(blockers, report.get("phase3_ready_claim"), "phase3_ready_claim_true")
    require_false(blockers, report.get("phase4_ready_claim"), "phase4_ready_claim_true")
    require_false(blockers, report.get("learning_claim"), "learning_claim_true")
    require_false(blockers, report.get("full_gemma_htp_forward_claim"), "full_gemma_htp_forward_claim_true")
    require_equal(blockers, report.get("authority_material"), AUTHORITY_MATERIAL, "wrong_authority_material")

    model_source = require_mapping(blockers, report.get("model_source"), "missing_model_source")
    graph = require_mapping(blockers, report.get("graph"), "missing_graph")
    conversion = require_mapping(blockers, report.get("conversion"), "missing_conversion")
    qnn_context = require_mapping(blockers, report.get("qnn_context"), "missing_qnn_context")
    raw_rules = require_mapping(blockers, report.get("raw_payload_rules"), "missing_raw_payload_rules")

    if model_source:
        validate_model_source(blockers, model_source)
    if graph:
        validate_graph(blockers, graph)
    if conversion:
        validate_conversion(blockers, conversion)
    if qnn_context:
        validate_qnn_context(blockers, qnn_context)
    if raw_rules:
        validate_raw_payload_rules(blockers, raw_rules)
    return blockers


def validate_model_source(blockers: list[str], model_source: dict[str, Any]) -> None:
    require_equal(blockers, model_source.get("model_id"), EXPECTED_MODEL_ID, "wrong_model_id")
    require_equal(blockers, model_source.get("revision"), EXPECTED_MODEL_REVISION, "wrong_model_revision")
    require_true(blockers, model_source.get("outside_git"), "model_source_not_outside_git")
    require_true(blockers, model_source.get("config_json_present"), "model_config_json_missing")
    require_true(blockers, model_source.get("model_safetensors_present"), "model_safetensors_missing")
    require_sha256(blockers, model_source.get("model_safetensors_sha256"), "bad_model_safetensors_sha256")
    require_positive_int(blockers, model_source.get("model_safetensors_bytes"), "bad_model_safetensors_bytes")
    path = model_source.get("path")
    require_present(blockers, path, "missing_model_source_path")
    if isinstance(path, str) and path_in_repo(path):
        blockers.append("model_source_path_in_repo")

    config = require_mapping(blockers, model_source.get("config"), "missing_model_config")
    if config:
        for key, expected in REQUIRED_CONFIG.items():
            require_equal(blockers, config.get(key), expected, f"model_config_{key}_mismatch")
    validate_config_source(blockers, model_source.get("config_source"))


def validate_config_source(blockers: list[str], config_source: Any) -> None:
    mapping = require_mapping(blockers, config_source, "missing_config_source")
    if not mapping:
        return
    kind = mapping.get("kind")
    if kind not in {"hf_config_json", "model_spec_derived_metadata"}:
        blockers.append("unknown_config_source_kind")
    if kind != "model_spec_derived_metadata":
        return
    require_true(
        blockers,
        mapping.get("explicitly_not_original_hf_config_restored"),
        "model_spec_config_not_explicitly_labeled_derived",
    )
    require_equal(blockers, mapping.get("repo_id"), EXPECTED_MODEL_ID, "config_source_repo_id_mismatch")
    require_equal(blockers, mapping.get("revision"), EXPECTED_MODEL_REVISION, "config_source_revision_mismatch")
    require_equal(
        blockers,
        mapping.get("expected_original_config_oid"),
        EXPECTED_ORIGINAL_CONFIG_OID,
        "config_source_original_config_oid_mismatch",
    )
    require_equal(
        blockers,
        mapping.get("expected_original_config_size_bytes"),
        EXPECTED_ORIGINAL_CONFIG_SIZE_BYTES,
        "config_source_original_config_size_mismatch",
    )
    require_sha256(blockers, mapping.get("model_spec_sha256"), "bad_model_spec_sha256")


def validate_graph(blockers: list[str], graph: dict[str, Any]) -> None:
    require_equal(blockers, graph.get("name"), EXPECTED_GRAPH, "wrong_graph_name")
    require_equal(blockers, graph.get("producer_kind"), EXPECTED_PRODUCER_KIND, "wrong_producer_kind")
    require_equal(blockers, graph.get("scope"), "gemma4_e4b_ffn_residual_layer0", "wrong_graph_scope")
    name = graph.get("name")
    if not isinstance(name, str) or not name:
        blockers.append("missing_graph_name")
        return
    if name in DISALLOWED_FULL_GEMMA_GRAPHS:
        blockers.append(f"disallowed_full_gemma_graph:{name}")
    lowered = name.lower()
    if "gemma" not in lowered:
        blockers.append("graph_not_gemma_scoped")
    if "ffn" not in lowered and "decoder" not in lowered:
        blockers.append("graph_not_forward_island_scoped")
    for token in DISALLOWED_GRAPH_TOKENS:
        if token in lowered:
            blockers.append(f"disallowed_graph_token:{token}")
    validate_tensor_contract(blockers, graph.get("input"), "graph_input")
    validate_tensor_contract(blockers, graph.get("output"), "graph_output")


def validate_conversion(blockers: list[str], conversion: dict[str, Any]) -> None:
    require_equal(blockers, conversion.get("route"), "qnn_cpp_model_library_to_context", "wrong_conversion_route")
    require_true(blockers, conversion.get("uses_real_restored_weights"), "conversion_not_bound_to_real_weights")
    require_false(blockers, conversion.get("random_init_weights"), "conversion_random_init_weights_true")
    require_false(blockers, conversion.get("metadata_only_manifest"), "conversion_metadata_only_manifest_true")
    require_false(blockers, conversion.get("cpu_fallback"), "conversion_cpu_fallback_true")
    require_equal(blockers, conversion.get("preferred_route"), "qnn_cpp_generated_model_library", "wrong_preferred_route")
    require_present(blockers, conversion.get("qairt_sdk_version"), "missing_qairt_sdk_version")
    require_present(blockers, conversion.get("android_ndk_version"), "missing_android_ndk_version")
    require_present(blockers, conversion.get("qnn_op_plan"), "missing_qnn_op_plan")
    require_false(blockers, conversion.get("litert_aot_primary"), "litert_aot_marked_primary")
    model_library = require_mapping(blockers, conversion.get("model_library"), "missing_model_library_artifact")
    if model_library:
        require_true(blockers, model_library.get("outside_git"), "model_library_not_outside_git")
        require_sha256(blockers, model_library.get("sha256"), "bad_model_library_sha256")
        require_positive_int(blockers, model_library.get("bytes"), "bad_model_library_bytes")
        path = model_library.get("path")
        require_present(blockers, path, "missing_model_library_path")
        if isinstance(path, str) and path_in_repo(path):
            blockers.append("model_library_path_in_repo")


def validate_qnn_context(blockers: list[str], qnn_context: dict[str, Any]) -> None:
    require_equal(blockers, qnn_context.get("backend_execution"), "qnn_htp", "qnn_backend_execution_not_htp")
    require_false(blockers, qnn_context.get("cpu_fallback"), "qnn_cpu_fallback_true")
    require_true(blockers, qnn_context.get("context_generated"), "qnn_context_not_generated")
    require_present(blockers, qnn_context.get("qairt_root"), "missing_qairt_root")
    backend = qnn_context.get("backend")
    require_present(blockers, backend, "missing_qnn_backend")
    if isinstance(backend, str) and "libQnnHtp.so" not in backend:
        blockers.append("qnn_backend_not_libQnnHtp")
    require_phone_path(blockers, qnn_context.get("context_path"), "qnn_context_path")
    require_sha256(blockers, qnn_context.get("context_sha256"), "bad_qnn_context_sha256")
    require_positive_int(blockers, qnn_context.get("context_bytes"), "bad_qnn_context_bytes")
    require_equal(blockers, qnn_context.get("graph_name"), EXPECTED_GRAPH, "qnn_context_graph_name_mismatch")
    require_true(blockers, qnn_context.get("context_utility_graph_match"), "qnn_context_utility_graph_mismatch")
    tools = require_mapping(blockers, qnn_context.get("tool_identities"), "missing_qnn_tool_identities")
    if tools:
        require_tool(blockers, tools.get("qnn_context_binary_generator"), "qnn_context_binary_generator")
        require_tool(blockers, tools.get("qnn_context_binary_utility"), "qnn_context_binary_utility")
        require_tool(blockers, tools.get("qnn_net_run"), "qnn_net_run")


def validate_raw_payload_rules(blockers: list[str], raw_rules: dict[str, Any]) -> None:
    require_true(blockers, raw_rules.get("raw_model_context_tensor_payloads_outside_git"), "raw_payloads_not_outside_git")
    require_false(blockers, raw_rules.get("raw_payloads_in_git"), "raw_payloads_in_git")
    require_true(blockers, raw_rules.get("metadata_report_only_in_repo"), "metadata_report_only_in_repo_false")
    for path in raw_rules.get("repo_paths", []):
        if str(path).endswith(RAW_EXPORT_SUFFIXES):
            blockers.append("raw_export_payload_path_in_repo")


def validate_tensor_contract(blockers: list[str], tensor: Any, prefix: str) -> None:
    mapping = require_mapping(blockers, tensor, f"missing_{prefix}")
    if not mapping:
        return
    require_equal(blockers, mapping.get("shape"), EXPECTED_SHAPE, f"{prefix}_wrong_shape")
    require_equal(blockers, mapping.get("dtype"), EXPECTED_DTYPE, f"{prefix}_wrong_dtype")
    require_equal(blockers, mapping.get("bytes"), EXPECTED_BYTES, f"{prefix}_wrong_bytes")


def require_tool(blockers: list[str], tool: Any, prefix: str) -> None:
    mapping = require_mapping(blockers, tool, f"missing_{prefix}")
    if not mapping:
        return
    require_phone_path(blockers, mapping.get("path"), f"{prefix}_path")
    require_sha256(blockers, mapping.get("identity_sha256"), f"bad_{prefix}_identity_sha256")


def path_in_repo(path: str) -> bool:
    try:
        candidate = Path(path).expanduser().resolve()
        repo = Path(__file__).resolve().parents[2]
        candidate.relative_to(repo)
        return True
    except (OSError, ValueError):
        return False


def require_mapping(blockers: list[str], value: Any, code: str) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        blockers.append(code)
        return None
    return value


def require_present(blockers: list[str], value: Any, code: str) -> None:
    if value is None or value == "":
        blockers.append(code)


def require_equal(blockers: list[str], value: Any, expected: Any, code: str) -> None:
    if value != expected:
        blockers.append(code)


def require_true(blockers: list[str], value: Any, code: str) -> None:
    if value is not True:
        blockers.append(code)


def require_false(blockers: list[str], value: Any, code: str) -> None:
    if value is not False:
        blockers.append(code)


def require_sha256(blockers: list[str], value: Any, code: str) -> None:
    if not isinstance(value, str) or not SHA256_PATTERN.match(value):
        blockers.append(code)


def require_positive_int(blockers: list[str], value: Any, code: str) -> None:
    if not isinstance(value, int) or value <= 0:
        blockers.append(code)


def require_phone_path(blockers: list[str], value: Any, code: str) -> None:
    require_present(blockers, value, f"missing_{code}")
    if isinstance(value, str) and not value.startswith(ALLOWED_PHONE_PREFIXES):
        blockers.append(f"{code}_not_phone_path")

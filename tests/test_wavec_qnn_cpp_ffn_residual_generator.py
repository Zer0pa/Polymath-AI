from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from polymath_ai.polar.wavec_gemma_qnn_exporter import EXPECTED_GRAPH, REQUIRED_CONFIG


SCRIPT = Path("scripts/host/run_wavec_qnn_cpp_ffn_residual_generator.py")
MODEL_SPEC = Path("integrations/gemma4-snapdragon-megakernel/model_spec/gemma4_e4b.json")
PHONE_MODEL = (
    "/data/data/com.termux/files/home/polymath_model_sources/"
    "gemma4_e4b_7aa32e6889efd6300124851b164f8b364314c3d8/model.safetensors"
)
PHONE_MODEL_SHA = "43fb96cec3045b72852c787540300dc5b258634b7a025f7c80355ac0788b9651"
PHONE_MODEL_BYTES = "15992595884"


def load_generator_module():
    spec = importlib.util.spec_from_file_location("wavec_qnn_cpp_ffn_residual_generator", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_generator_print_schema() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--print-schema"],
        text=True,
        capture_output=True,
        check=True,
    )

    schema = json.loads(result.stdout)
    assert schema["schema_version"] == "waveC_qnn_cpp_ffn_residual_generator_report_v1"
    assert schema["graph"] == EXPECTED_GRAPH
    assert schema["required_layer0_tensors"]["mlp_gate_proj"]["shape"] == [10240, 2560]
    assert schema["probe_ladder"][0]["stage"] == "primitive_rmsnorm_decomposition_probe"
    assert schema["probe_ladder"][1]["stage"] == "primitive_gelu_tanh_lowering_probe"
    assert schema["probe_ladder"][2]["stage"] == "quantized_tiny_matmul_static_weight_probe"
    assert "all_float32_htp_matmul_not_assumed_without_qairt_context_evidence" in schema[
        "dtype_layout_stop_conditions"
    ]
    assert "qnn_profile_viewer_parse_status" in schema["required_qnn_evidence_fields"]
    assert schema["probe_ladder_sources"][0]["source"] == "primitive_rmsnorm_decomposition_probe.cpp"
    assert schema["probe_ladder_sources"][0]["axis"] == 2
    assert schema["probe_ladder_sources"][0]["reduce_mean_param"] == "QNN_OP_REDUCE_MEAN_PARAM_AXES"
    assert schema["probe_ladder_sources"][0]["keep_dims"] is True
    assert schema["probe_ladder_sources"][1]["secondary_input"] == "up_activation_for_ffn_multiply"
    assert schema["probe_ladder_sources"][1]["constants"]["sqrt_2_over_pi"] == 0.7978845608028654
    assert schema["probe_ladder_sources"][2]["activation_dtype"] == "uint16_asymmetric"
    assert schema["probe_ladder_sources"][2]["weight_dtype"] == "uint8_asymmetric"
    assert schema["probe_ladder_sources"][2]["fully_connected_keep_dims_param"] == (
        "QNN_OP_FULLY_CONNECTED_PARAM_KEEP_DIMS=true"
    )
    assert schema["probe_ladder_sources"][2]["matmul_variant_param"] == (
        "QNN_OP_MAT_MUL_PARAM_TRANSPOSE_IN1=false_with_pretransposed_weight_3x4"
    )
    assert "orientation" in schema["probe_ladder_sources"][2]


def test_generator_rejects_repo_work_root(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--model-safetensors",
            PHONE_MODEL,
            "--model-safetensors-sha256",
            PHONE_MODEL_SHA,
            "--model-safetensors-bytes",
            PHONE_MODEL_BYTES,
            "--model-config-spec",
            str(MODEL_SPEC),
            "--work-root",
            "runtime/reports/bad_qnn_work_root",
            "--report",
            str(report),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert result.returncode == 2
    assert payload["first_missing_green_field"] == "work_root_inside_repo"
    assert "work_root_inside_repo" in payload["blockers"]


def test_local_materialization_still_requires_local_model_file(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--model-source-location",
            "local",
            "--model-safetensors",
            str(tmp_path / "missing_model.safetensors"),
            "--model-safetensors-sha256",
            PHONE_MODEL_SHA,
            "--model-safetensors-bytes",
            PHONE_MODEL_BYTES,
            "--model-config-spec",
            str(MODEL_SPEC),
            "--work-root",
            str(tmp_path / "outside_work"),
            "--materialize-weight-blobs",
            "--report",
            str(report),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert result.returncode == 2
    assert payload["first_missing_green_field"] == (
        "source_missing:materialize_weight_blobs_requires_local_readable_model_safetensors"
    )


def test_phone_preverified_materialization_plan_does_not_require_host_model(tmp_path: Path) -> None:
    work_root = tmp_path / "outside_work"
    report = tmp_path / "report.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--model-source-location",
            "phone_preverified",
            "--model-safetensors",
            PHONE_MODEL,
            "--model-safetensors-sha256",
            PHONE_MODEL_SHA,
            "--model-safetensors-bytes",
            PHONE_MODEL_BYTES,
            "--model-config-spec",
            str(MODEL_SPEC),
            "--work-root",
            str(work_root),
            "--materialize-weight-blobs",
            "--phone-materialization-plan-only",
            "--report",
            str(report),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    manifest = payload["qnn_cpp_generator"]["tensor_manifest"]

    assert result.returncode == 0
    assert payload["status"] == "pass"
    assert payload["first_missing_green_field"] == "none"
    assert payload["model_source"]["materialization"]["method"] == (
        "phone_ssh_selected_safetensors_range_extraction_plan_only"
    )
    assert manifest["mlp_gate_proj"]["materialization_method"] == "phone_ssh_selected_safetensors_range_extraction"
    assert manifest["mlp_gate_proj"]["phone_model_path"] == PHONE_MODEL
    assert manifest["mlp_gate_proj"]["materialized"] is False
    assert (work_root / "scripts" / "phone_materialize_selected_safetensors.py").is_file()
    assert (work_root / "metadata" / "phone_materialization_plan.json").is_file()
    assert not (work_root / "weights" / "mlp_gate_proj_f32.raw").exists()


def test_phone_materialization_non_plan_requires_identity_or_config(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--model-source-location",
            "phone_preverified",
            "--model-safetensors",
            PHONE_MODEL,
            "--model-safetensors-sha256",
            PHONE_MODEL_SHA,
            "--model-safetensors-bytes",
            PHONE_MODEL_BYTES,
            "--model-config-spec",
            str(MODEL_SPEC),
            "--work-root",
            str(tmp_path / "outside_work"),
            "--materialize-weight-blobs",
            "--report",
            str(report),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert result.returncode == 2
    assert payload["first_missing_green_field"] == "source_missing:phone_materialization_ssh_identity_or_config_missing"


def test_phone_materialization_rejects_unreadable_identity_path(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    missing_identity = tmp_path / "missing_identity"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--model-source-location",
            "phone_preverified",
            "--model-safetensors",
            PHONE_MODEL,
            "--model-safetensors-sha256",
            PHONE_MODEL_SHA,
            "--model-safetensors-bytes",
            PHONE_MODEL_BYTES,
            "--model-config-spec",
            str(MODEL_SPEC),
            "--work-root",
            str(tmp_path / "outside_work"),
            "--materialize-weight-blobs",
            "--phone-ssh-identity",
            str(missing_identity),
            "--report",
            str(report),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert result.returncode == 2
    assert payload["first_missing_green_field"] == "source_missing:phone_materialization_ssh_identity_missing_or_unreadable"


def test_phone_materialization_ssh_identity_propagates_to_ssh_and_scp(tmp_path: Path) -> None:
    module = load_generator_module()
    identity = tmp_path / "polymath_host"
    identity.write_text("placeholder test key path only\n", encoding="utf-8")
    args = argparse.Namespace(
        phone_ssh_host="127.0.0.1",
        phone_ssh_port=8022,
        phone_ssh_user="u0_a536",
        phone_ssh_identity=str(identity),
        phone_ssh_config="",
        phone_ssh_extra_arg=[],
    )

    ssh_command = module.ssh_command(args, "true")
    scp_command = module.scp_from_phone_command(args, "/remote/blob.raw", tmp_path / "blob.raw")

    assert "-i" in ssh_command
    assert str(identity) in ssh_command
    assert "-i" in scp_command
    assert str(identity) in scp_command
    assert "placeholder test key path only" not in " ".join(ssh_command)


def test_phone_materialization_ssh_config_propagates_to_ssh_and_scp(tmp_path: Path) -> None:
    module = load_generator_module()
    config = tmp_path / "ssh_config"
    config.write_text("Host phone\n  HostName 127.0.0.1\n", encoding="utf-8")
    args = argparse.Namespace(
        phone_ssh_host="127.0.0.1",
        phone_ssh_port=8022,
        phone_ssh_user="u0_a536",
        phone_ssh_identity="",
        phone_ssh_config=str(config),
        phone_ssh_extra_arg=[],
    )

    ssh_command = module.ssh_command(args, "true")
    scp_command = module.scp_to_phone_command(args, tmp_path / "local.py", "/remote/local.py")

    assert "-F" in ssh_command
    assert str(config) in ssh_command
    assert "-F" in scp_command
    assert str(config) in scp_command


def test_generator_writes_fail_closed_source_package_outside_git(tmp_path: Path) -> None:
    work_root = tmp_path / "outside_work"
    report = tmp_path / "report.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--model-source-location",
            "phone_preverified",
            "--model-safetensors",
            PHONE_MODEL,
            "--model-safetensors-sha256",
            PHONE_MODEL_SHA,
            "--model-safetensors-bytes",
            PHONE_MODEL_BYTES,
            "--model-config-spec",
            str(MODEL_SPEC),
            "--work-root",
            str(work_root),
            "--qairt-root",
            "/data/local/tmp/qairt-2.44",
            "--android-ndk-root",
            "/opt/android-ndk-r27",
            "--report",
            str(report),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    cpp_path = Path(payload["qnn_cpp_generator"]["generated"]["cpp_source"]["path"])
    cpp = cpp_path.read_text(encoding="utf-8")

    assert result.returncode == 0
    assert payload["status"] == "pass"
    assert payload["first_missing_green_field"] == "none"
    assert payload["config_spec"]["required_config"] == REQUIRED_CONFIG
    assert payload["raw_payload_rules"]["work_root_outside_git"] is True
    assert EXPECTED_GRAPH in cpp
    assert "gemma_hidden2560_relu" not in cpp
    assert "gemma_hidden2560_identity_add" not in cpp
    assert "qwen" not in cpp.lower()
    assert payload["qnn_cpp_generator"]["probe_ladder_required_before_full_island"][0]["stage"] == (
        "primitive_rmsnorm_decomposition_probe"
    )
    assert payload["qnn_cpp_generator"]["probe_ladder_required_before_full_island"][1]["stage"] == (
        "primitive_gelu_tanh_lowering_probe"
    )
    assert payload["qnn_cpp_generator"]["probe_ladder_required_before_full_island"][2]["stage"] == (
        "quantized_tiny_matmul_static_weight_probe"
    )
    assert "missing_scale_zero_point_orientation_or_axis_metadata_is_quantization_or_layout_failure" in payload[
        "qnn_cpp_generator"
    ]["dtype_layout_stop_conditions"]
    assert "qnn_context_opDataSize" in payload["execution_contract"]["required_qnn_evidence_fields"]
    assert "qnn_execute_profile_fields" in payload["execution_contract"]["required_qnn_evidence_fields"]
    assert payload["execution_contract"]["qairt_wrapper_source_route"]["phone_qairt_root"] == "/data/local/tmp/qairt-2.44"
    assert payload["execution_contract"]["qairt_wrapper_source_route"]["stage_from_phone_when_host_missing"] is True
    assert payload["execution_contract"]["qairt_wrapper_source_route"]["failure_field"] == (
        "model_library_failure:missing_host_qairt_wrapper_sources"
    )
    assert (work_root / "scripts" / "build_android_model_library.sh").is_file()
    assert (work_root / "scripts" / "generate_phone_context.sh").is_file()
    assert (work_root / "src" / "probes" / "primitive_rmsnorm_decomposition_probe.cpp").is_file()
    assert (work_root / "src" / "probes" / "primitive_gelu_tanh_lowering_probe.cpp").is_file()
    assert (work_root / "src" / "probes" / "quantized_tiny_matmul_static_weight_probe.cpp").is_file()
    assert (work_root / "metadata" / "probe_ladder_manifest.json").is_file()
    assert (work_root / "scripts" / "build_probe_ladder.sh").is_file()
    assert (work_root / "scripts" / "run_probe_ladder_contexts.sh").is_file()
    rms_probe = (work_root / "src" / "probes" / "primitive_rmsnorm_decomposition_probe.cpp").read_text(
        encoding="utf-8"
    )
    gelu_probe = (work_root / "src" / "probes" / "primitive_gelu_tanh_lowering_probe.cpp").read_text(
        encoding="utf-8"
    )
    matmul_probe = (work_root / "src" / "probes" / "quantized_tiny_matmul_static_weight_probe.cpp").read_text(
        encoding="utf-8"
    )
    assert "QNN_OP_RMS_NORM" not in rms_probe
    assert "QNN_OP_REDUCE_MEAN_PARAM_AXES" in rms_probe
    assert "appTensor(\"rms_input\", dims_hidden, 3" in rms_probe
    assert "appTensor(\"rms_mean\", dims_reduce, 3" in rms_probe
    assert "QNN_OP_GELU" not in gelu_probe
    assert "0.7978845608028654" in gelu_probe
    assert "\"gelu_native\", \"gelu_up\"" in gelu_probe
    assert "QNN_OP_FULLY_CONNECTED_PARAM_KEEP_DIMS" in matmul_probe
    assert "QNN_OP_MAT_MUL_PARAM_TRANSPOSE_IN1" in matmul_probe
    assert "QNN_DATATYPE_UFIXED_POINT_16" in matmul_probe
    assert "QNN_DATATYPE_UFIXED_POINT_8" in matmul_probe
    assert "appTensor(\"qmat_input_f32\", dims_input, 3" in matmul_probe
    assert "appTensor(\"qmat_output_f32\", dims_output, 3" in matmul_probe

    build_script = (work_root / "scripts" / "build_android_model_library.sh").read_text(encoding="utf-8")
    assert "ANDROID_NDK_PREBUILT" in build_script
    assert "QAIRT_HOST_ROOT" in build_script
    assert "STAGED_Q=" in build_script
    assert "stage_qairt_wrappers_from_phone" in build_script
    assert "model_library_failure:missing_host_qairt_wrapper_sources" in build_script
    assert "QnnModel.cpp" in build_script
    assert "QnnWrapperUtils.cpp" in build_script
    assert "QnnModelPal.cpp" in build_script
    assert 'NDK_PREBUILT="darwin-x86_64"' in build_script
    assert 'NDK_PREBUILT="linux-x86_64"' in build_script
    assert "model_library_failure:ndk_prebuilt_compiler_missing" in build_script
    assert "prebuilt/linux-x86_64/bin/aarch64-linux-android35-clang++" not in build_script
    probe_build_script = (work_root / "scripts" / "build_probe_ladder.sh").read_text(encoding="utf-8")
    assert "QAIRT_HOST_ROOT" in probe_build_script
    assert "stage_qairt_wrappers_from_phone" in probe_build_script
    assert "model_library_failure:missing_host_qairt_wrapper_sources" in probe_build_script
    context_script = (work_root / "scripts" / "run_probe_ladder_contexts.sh").read_text(encoding="utf-8")
    assert "QAIRT_EXEC_ROOT" in context_script
    assert "prepare_qairt_exec_root" in context_script
    assert "$PHONE_ROOT/qairt_exec" in context_script
    assert "qnn_context_binary_generator_permission_denied_or_unstageable" in context_script
    assert "Q_SRC=/data/local/tmp/qairt-2.44" in context_script
    assert "Q=\"$Q_EXEC\"" in context_script

    probe_manifest = json.loads((work_root / "metadata" / "probe_ladder_manifest.json").read_text(encoding="utf-8"))
    assert probe_manifest["stage_order"] == [
        "primitive_rmsnorm_decomposition_probe",
        "primitive_gelu_tanh_lowering_probe",
        "quantized_tiny_matmul_static_weight_probe",
        "full_gemma4_e4b_ffn_residual_layer0_probe",
    ]
    assert probe_manifest["full_island_runnable_only_after"] == [
        "primitive_rmsnorm_decomposition_probe",
        "primitive_gelu_tanh_lowering_probe",
        "quantized_tiny_matmul_static_weight_probe",
    ]
    matmul = probe_manifest["probes"][2]
    for field in ("activation_dtype", "weight_dtype", "activation_scale", "activation_zero_point", "weight_scale", "weight_zero_point", "orientation"):
        assert field in matmul

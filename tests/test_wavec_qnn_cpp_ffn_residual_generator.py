from __future__ import annotations

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
    assert (work_root / "scripts" / "build_android_model_library.sh").is_file()
    assert (work_root / "scripts" / "generate_phone_context.sh").is_file()

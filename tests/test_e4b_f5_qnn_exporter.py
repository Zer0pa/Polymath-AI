from __future__ import annotations

import ctypes
import errno
import json
import os
import re

import pytest

from polymath_ai.frontier import e4b_f5_qnn_exporter
from polymath_ai.frontier.e4b_f5_probe import ProbeContractError
from polymath_ai.frontier.e4b_f5_qnn_exporter import (
    BACKEND_CONFIG,
    EXTENSIONS_CONFIG,
    QAIRT_BUILD_SOURCE_SHA256,
    _open_regular_nofollow,
    publish_directory_noreplace,
    render_build_script,
    render_context_script,
    render_direct_qnn_cpp,
    render_packed_tensor_assembly,
    unpack_low_bits,
    validate_qairt_configs,
)


def test_unpack_w4_matches_transformers_low_nibble_then_high_nibble():
    assert unpack_low_bits(bytes([0xF0, 0x87]), num_bits=4, signed_shift=-8, logical_values=4) == bytes(
        [0xF8, 0x07, 0xFF, 0x00]
    )


def test_unpack_w2_matches_transformers_lsb_lane_order():
    # 0b11100100 stores lanes 0,1,2,3; shifting by -2 yields -2,-1,0,1.
    assert unpack_low_bits(bytes([0xE4]), num_bits=2, signed_shift=-2, logical_values=4) == bytes(
        [0xFE, 0xFF, 0x00, 0x01]
    )


def test_unpack_rejects_wrong_storage_size():
    with pytest.raises(ProbeContractError, match="packed byte count mismatch"):
        unpack_low_bits(b"", num_bits=2, signed_shift=-2, logical_values=4)


def test_cpp_is_complete_full_dimension_two_graph_generator():
    source = render_direct_qnn_cpp()
    required = [
        "2048ull * 2560ull",
        "262144ull * 2560ull",
        "QNN_DATATYPE_SFIXED_POINT_8",
        "QNN_DATATYPE_FLOAT_16",
        "QNN_QUANTIZATION_ENCODING_BW_AXIS_SCALE_OFFSET",
        "QNN_OP_MAT_MUL_PARAM_TRANSPOSE_IN1",
        "parameters[1].scalarParam.bool8Value = 1",
        '"lm_head_output_f16_pre_softcap"',
        "getGraphInfoFromModels(models, 2, graphsInfo)",
    ]
    for fragment in required:
        assert fragment in source
    assert "QNN_DATATYPE_UFIXED_POINT_2" not in source
    assert "QNN_DATATYPE_UFIXED_POINT_4" not in source
    assert "TODO" not in source


def test_cpp_preserves_exact_srq_and_uncalibrated_head_contracts():
    source = render_direct_qnn_cpp()
    assert "qInputScaleValue <= 0.0f" in source
    assert "qOutputScaleValue <= 0.0f" in source
    assert "headInputScaleValue != 0.0f" in source
    assert "headOutputScaleValue != 0.0f" in source
    assert "scaleOffsetQuantization(qInputScaleValue)" in source
    assert "scaleOffsetQuantization(qOutputScaleValue)" in source


def test_assembly_embeds_all_eight_exact_tensors_lsb_sources():
    assembly = render_packed_tensor_assembly()
    assert assembly.count(".incbin") == 8
    assert 'tensors/w4_q_proj_weight.u4.packed.bin' in assembly
    assert 'tensors/w2_lm_head_weight.u2.packed.bin' in assembly
    assert '.section .note.GNU-stack' in assembly


def test_build_script_binds_every_qairt_source_and_emits_no_backend_pass():
    script = render_build_script()
    for relative, digest in QAIRT_BUILD_SOURCE_SHA256.items():
        assert relative in script
        assert digest in script
    assert "source_compile_passed_backend_unvalidated" in script
    assert "provider_context_generated" not in script


def test_context_script_is_reference_gated_and_soc69_v79_bound():
    script = render_context_script()
    assert '"schema_version": "gemma4_e4b_f5_reference_gate_v1"' in script
    assert '"status": "passed_scope"' in script
    assert "l2_threshold_policy_sha256" in script
    assert "reference_output_sha256" in script
    assert "qnn-context-binary-generator" in script
    assert '"soc_model": 69' in script
    assert '"dsp_arch": 79' in script
    assert "phone_execution_count" in script
    assert "object_pairs_hook=reject_duplicates" in script
    assert "parse_constant=reject_constant" in script
    assert 'observed_library = digest(root / "build/libgemma4_e4b_f5_lowbit_probes.so")' in script
    assert 'observed_library != build.get("library")' in script
    assert 'observed_manifest != build.get("package_manifest")' in script
    assert 'root / "package_manifest.sha256"' in script
    assert "package manifest sidecar mismatch" in script
    assert "os.O_EXCL" in script
    assert "os.fsync" in script


def test_build_receipt_is_exclusive_and_fsynced():
    script = render_build_script()
    assert "os.O_EXCL" in script
    assert "O_NOFOLLOW" in script
    assert "os.fsync" in script
    assert "allow_nan=False" in script


def test_exact_qairt_config_schema_rejects_drift():
    validate_qairt_configs(BACKEND_CONFIG, EXTENSIONS_CONFIG)
    drifted = json.loads(json.dumps(BACKEND_CONFIG))
    drifted["graphs"][0]["vtcm_mb"] = 8
    with pytest.raises(ProbeContractError, match="backend config"):
        validate_qairt_configs(drifted, EXTENSIONS_CONFIG)


def test_open_regular_nofollow_rejects_symlink(tmp_path):
    target = tmp_path / "target"
    target.write_bytes(b"carrier")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(ProbeContractError, match="without following links"):
        _open_regular_nofollow(link)


def test_no_replace_publication_succeeds_once(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    (source / "marker").write_text("complete", encoding="utf-8")
    publish_directory_noreplace(source, destination)
    assert not source.exists()
    assert (destination / "marker").read_text(encoding="utf-8") == "complete"


def test_no_replace_publication_refuses_attacker_empty_directory(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    with pytest.raises(ProbeContractError, match="destination already exists"):
        publish_directory_noreplace(source, destination)
    assert source.is_dir()
    assert destination.is_dir()


def test_android_no_replace_publication_uses_renameat2_and_maps_eexist(
    monkeypatch, tmp_path
):
    calls = []

    class FakeRenameAt2:
        argtypes = None
        restype = None

        def __call__(self, *args):
            calls.append(args)
            ctypes.set_errno(errno.EEXIST)
            return -1

    class FakeLibc:
        renameat2 = FakeRenameAt2()

    monkeypatch.setattr(e4b_f5_qnn_exporter.sys, "platform", "android")
    monkeypatch.setattr(
        e4b_f5_qnn_exporter.ctypes, "CDLL", lambda *_args, **_kwargs: FakeLibc()
    )

    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    with pytest.raises(ProbeContractError, match="destination already exists"):
        publish_directory_noreplace(source, destination)

    assert calls == [(-100, os.fsencode(source), -100, os.fsencode(destination), 1)]
    assert source.is_dir()
    assert destination.is_dir()


def test_rendered_config_payloads_are_strict_json_compatible():
    payload = {
        "graphs": [
            {"graph_names": ["gemma4_e4b_f5_w4_q_proj"], "vtcm_mb": 2},
            {"graph_names": ["gemma4_e4b_f5_w2_lm_head"], "vtcm_mb": 2},
        ],
        "devices": [{"soc_model": 69, "dsp_arch": "v79"}],
    }
    assert json.loads(json.dumps(payload, allow_nan=False)) == payload


@pytest.mark.parametrize("script", [render_build_script(), render_context_script()])
def test_generated_python_heredocs_compile(script):
    blocks = re.findall(r"<<'PY'\n(.*?)\nPY", script, flags=re.DOTALL)
    assert blocks
    for index, block in enumerate(blocks):
        compile(block, f"generated_heredoc_{index}", "exec")

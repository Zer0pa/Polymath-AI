from __future__ import annotations

from pathlib import Path
import struct

import numpy as np
import pytest

from polymath_ai.frontier import e4b_l2_int16_v2 as v2
from polymath_ai.frontier.e4b_l2_projection_gate import (
    ProjectionGateError,
    canonical_json,
    sha256_bytes,
)


ROOT = Path(__file__).resolve().parents[1]
V1_PREREG = (
    ROOT / "runtime/reports/apex_frontier/20260711T020600Z_l2_int16_head_prereg_v2"
)
FRONTIER_SELECTOR = (
    ROOT / "runtime/reports/apex_frontier/frontier_event_20260711T101133Z.json"
)
PARENT_CAPSULE = (
    ROOT / "docs/APEX-CURRENT-REALITY-CAPSULE-GEMMA4-E4B-QNN-CELL-2026-07-10.yaml"
)
ACCESS_RECEIPT = (
    ROOT / "runtime/reports/apex_frontier/access_refresh_20260711T020533Z.json"
)
SOURCE_REVISION = "a" * 40


def _f32_words(*words: int) -> bytes:
    return b"".join(struct.pack("<I", word) for word in words)


def _patch_scale_contract(monkeypatch, payload: bytes) -> None:
    monkeypatch.setattr(v2, "ROW_SCALE_COUNT", len(payload) // 4)
    monkeypatch.setattr(v2, "ORIGINAL_SCALE_BYTES", len(payload))
    monkeypatch.setattr(v2, "ORIGINAL_SCALE_SHA256", sha256_bytes(payload))


def _build_prereg(tmp_path: Path, monkeypatch) -> Path:
    scales = _f32_words(0x3F800001, 0x3F808000, 0x3F818000, 0x3F80FFFF)
    _patch_scale_contract(monkeypatch, scales)
    monkeypatch.setattr(v2, "_validate_frontier_selector", lambda _path: None)
    source_binding = {
        "repository": "Zer0pa/Polymath-AI",
        "revision": SOURCE_REVISION,
        "module_relative_path": v2.MODULE_RELATIVE_PATH,
        "module_sha256": v2.sha256_path(Path(v2.__file__)),
        "git_blob_oid": "c" * 40,
        "head_equals_revision": True,
        "module_clean": True,
    }
    monkeypatch.setattr(
        v2, "_validate_source_revision", lambda _revision: source_binding
    )
    runtime_binding = {
        "execution_plane": "phone_native_termux",
        "device": v2.RESOURCE_SLICE["phone"],
        "root": str(tmp_path),
        "input_locators": [],
        "output_locator": "v2_prereg",
        "raw_output_custody": "phone_private_no_egress",
        "raw_phone_private_upload": False,
        "qnn_execution": False,
    }
    monkeypatch.setattr(
        v2, "_validate_phone_runtime_paths", lambda **_kwargs: runtime_binding
    )
    scale_path = tmp_path / "scales.f32.bin"
    scale_path.write_bytes(scales)
    output = tmp_path / "v2_prereg"
    v2.build_int16_v2_preregistration(
        parent_int16_prereg_dir=V1_PREREG,
        frontier_selector=FRONTIER_SELECTOR,
        parent_capsule=PARENT_CAPSULE,
        access_receipt=ACCESS_RECEIPT,
        phone_runtime_root=tmp_path,
        original_scale_path=scale_path,
        output_dir=output,
        created_at_utc="2026-07-11T10:20:00Z",
        source_revision=SOURCE_REVISION,
    )
    return output


def test_bf16_rne_scale_conversion_is_bit_exact_and_ties_to_even():
    source = _f32_words(
        0x3F800000,
        0x3F807FFF,
        0x3F808000,
        0x3F808001,
        0x3F817FFF,
        0x3F818000,
        0x3F818001,
    )
    observed = v2.bf16_rne_scales_as_exact_f32(source, expected_count=7)
    assert observed == _f32_words(
        0x3F800000,
        0x3F800000,
        0x3F800000,
        0x3F810000,
        0x3F810000,
        0x3F820000,
        0x3F820000,
    )
    assert all((word & 0xFFFF) == 0 for (word,) in struct.iter_unpack("<I", observed))


@pytest.mark.parametrize("word", [0x00000000, 0xBF800000, 0x7F800000, 0x7FC00000])
def test_bf16_rne_scale_conversion_rejects_nonpositive_or_nonfinite(word: int):
    with pytest.raises(ProjectionGateError, match="positive finite"):
        v2.bf16_rne_scales_as_exact_f32(_f32_words(word), expected_count=1)


def test_v2_policy_preserves_only_the_governing_numeric_subset():
    policy = v2.int16_v2_candidate_policy()
    assert policy["candidate_id"] == (
        "w2_s16_activation_bw2_weight_bf16_rne_scale_s16_output_2m10_v2"
    )
    assert policy["frontier_selector_sha256"] == (
        "bb045f0761405b521705609d473fa1cb7b504634197256b2b684c061e1fc4d78"
    )
    authority = policy["authority_edge"]
    assert sha256_bytes(
        canonical_json(authority["numeric_and_ranking_thresholds"])
    ) == ("30704ef1cb88042a1451f46b5c516b815cbb440a7227b9013893ee7b42cdd914")
    assert authority["threshold_values_changed_from_parent"] is False
    assert policy["input_quantization"]["scale"] == 2**-9
    assert policy["output_quantization"]["scale"] == 2**-10
    assert policy["weight_quantization"]["axis"] == 0
    assert policy["weight_quantization"]["transpose_in1"] is True
    assert policy["weight_quantization"]["storage_bitwidth"] == 2


def test_governing_frontier_selector_contract_is_exact():
    v2._validate_frontier_selector(FRONTIER_SELECTOR)
    assert sha256_bytes(FRONTIER_SELECTOR.read_bytes()) == v2.FRONTIER_SELECTOR_SHA256


def test_v2_preregistration_freezes_scale_and_inputs_without_output(
    tmp_path: Path,
    monkeypatch,
):
    output = _build_prereg(tmp_path, monkeypatch)
    manifest, digest = v2.validate_int16_v2_preregistration(output)
    assert digest == sha256_bytes((output / "preregistration.json").read_bytes())
    assert manifest["state"] == "frozen_unobserved"
    assert manifest["v2_candidate_output_files_present"] is False
    assert manifest["provider_build_allowed"] is False
    assert (
        manifest["required_next_gate"]["provider_build_before_pass_forbidden"] is True
    )
    assert len(manifest["cases"]) == 3
    assert all(
        record["v2_oracle_output_present"] is False for record in manifest["cases"]
    )
    assert manifest["runtime_binding"]["absolute_paths_egressed"] is False
    assert "root" not in manifest["runtime_binding"]
    assert str(tmp_path) not in (output / "preregistration.json").read_text()
    transformed = (
        output / manifest["candidate_contract"]["transformed_scale_relative_path"]
    )
    assert transformed.read_bytes() == _f32_words(
        0x3F800000, 0x3F800000, 0x3F820000, 0x3F810000
    )
    assert not list(output.rglob("*oracle*.raw"))


def test_rendered_v2_head_changes_only_admitted_head_abi():
    source = v2.render_int16_v2_head_cpp()
    required = [
        '"lm_head_input_s16_v2"',
        '"lm_head_weight_s8_bw2_bf16_rne_scale_v2"',
        '"lm_head_output_s16_2m10_pre_softcap_v2"',
        "QNN_DATATYPE_SFIXED_POINT_16",
        "scaleOffsetQuantization(0.0019531250f)",
        "scaleOffsetQuantization(0.0009765625f)",
        "weightQuantization(spec.weightBits",
    ]
    assert all(fragment in source for fragment in required)
    assert "lm_head_input_f16" not in source
    assert "lm_head_output_f16_pre_softcap" not in source


def test_transformers_lane_order_is_preserved_by_oracle_unpack():
    packed = np.zeros((1, v2.INPUT_FEATURES // 4), dtype=np.uint8)
    packed[0, 0] = 0b_11_10_01_00
    unpacked = v2._unpack_weight_rows(packed)
    assert unpacked.dtype == np.int8
    assert unpacked.shape == (1, v2.INPUT_FEATURES)
    assert unpacked[0, :4].tolist() == [-2, -1, 0, 1]
    assert np.all(unpacked[0, 4:] == -2)


def test_provider_metadata_surface_rejects_the_full_phone_prereg_tree(
    tmp_path: Path,
    monkeypatch,
):
    prereg = _build_prereg(tmp_path, monkeypatch)
    with pytest.raises(ProjectionGateError, match="directory forbidden"):
        v2.validate_int16_v2_preregistration_metadata(prereg)

    metadata = tmp_path / "sanitized_metadata"
    metadata.mkdir()
    for name in (
        "preregistration.json",
        "preregistration.json.sha256",
        "threshold_policy.json",
        "threshold_policy.json.sha256",
    ):
        (metadata / name).write_bytes((prereg / name).read_bytes())
    manifest, _ = v2.validate_int16_v2_preregistration_metadata(metadata)
    assert manifest["runtime_binding"]["absolute_paths_egressed"] is False
    (metadata / "unexpected_phone_private.raw").write_bytes(b"forbidden")
    with pytest.raises(ProjectionGateError, match="file-tree whitelist"):
        v2.validate_int16_v2_preregistration_metadata(metadata)


def test_source_closure_binds_oracle_provider_and_import_initializers():
    required = {
        "polymath_ai/__init__.py",
        "polymath_ai/frontier/__init__.py",
        "polymath_ai/frontier/e4b_l2_int16_v2.py",
        "polymath_ai/frontier/e4b_l2_int16_v2_verifier.py",
        "polymath_ai/frontier/e4b_l2_int16_v2_package.py",
        "polymath_ai/frontier/e4b_l2_int16_package.py",
        "scripts/host/build_e4b_l2_int16_v2_package.py",
        "scripts/termux/run_e4b_l2_int16_v2_oracle.py",
    }
    assert required <= set(v2.SOURCE_CLOSURE_RELATIVE_PATHS)


@pytest.mark.parametrize(
    "value",
    [
        "/data/local/tmp/raw",
        "FY25013101C8",
        "20260711T102000Z_fy25013101c8",
        "20260711T102000Z_secret.token",
        "2026-07-11T10:20:00Z_oracle",
        "20261340T996060Z_l2_s16_v2_exact_oracle",
    ],
)
def test_sanitized_run_id_rejects_paths_serials_and_secret_like_values(value: str):
    with pytest.raises(ProjectionGateError, match="sanitized experiment identifier"):
        v2.validate_sanitized_run_id(value)
    v2.validate_sanitized_run_id("20260711T102000Z_l2_s16_v2_exact_oracle")
    v2.validate_sanitized_run_id("20260711T102500Z_l2_s16_v2_exact_verification")

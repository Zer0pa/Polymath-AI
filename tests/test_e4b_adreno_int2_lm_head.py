from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys

import pytest

from polymath_ai.frontier import e4b_adreno_int2_lm_head as adreno
from polymath_ai.frontier import e4b_l2_projection_gate as governing_gate


ROOT = Path(__file__).resolve().parents[1]
NATIVE_SOURCE = ROOT / "native/e4b_adreno_int2_lm_head/e4b_adreno_int2_lm_head.cpp"
NATIVE_RUNTIME = ROOT / "native/e4b_adreno_int2_lm_head/opencl_dynamic_runtime.cpp"
FROZEN_SELECTOR_PATH = (
    ROOT / "runtime/reports/apex_frontier/frontier_event_20260711T150552Z.json"
)
FROZEN_OPENCL_EVIDENCE_PATH = ROOT / (
    "runtime/reports/apex_frontier/"
    "20260711T145203Z_adreno_opencl_contract/opencl_contract_report.json"
)
FROZEN_S16_FALSIFICATION_PATH = ROOT / (
    "runtime/reports/apex_frontier/"
    "20260711T144510Z_l2_int16_v2_exact_oracle_attempt/"
    "oracle_falsification_report.json"
)
OPENCL_EXTENSION_DUMP_PATH = ROOT / (
    "runtime/reports/gemma4_megakernel/hardware_native_povc/"
    "20260523T205438Z_h11d_recordable_queues/H11-D-recordable-queues/"
    "extension_dump.json"
)


def opencl_contract() -> dict[str, object]:
    extensions = json.loads(OPENCL_EXTENSION_DUMP_PATH.read_text(encoding="utf-8"))[
        "device"
    ]["extensions"]
    return {
        "schema_version": adreno.OPENCL_CONTRACT_SCHEMA,
        "state": "passed_scope",
        "candidate_output_observed": False,
        "model_or_tensor_access_count": 0,
        "loader": {
            "loaded_path": "/vendor/lib64/libOpenCL.so",
            "route": "android_sphal",
        },
        "identity": {
            "platform_name": "QUALCOMM Snapdragon(TM)",
            "platform_vendor": "QUALCOMM",
            "platform_version": "OpenCL 3.0 QUALCOMM build: 0800.40",
            "device_name": "QUALCOMM Adreno(TM) 830",
            "device_vendor": "QUALCOMM",
            "driver_version": (
                "OpenCL 3.0 QUALCOMM build: 0800.40 Compiler E031.47.18.30"
            ),
            "device_version": "OpenCL 3.0 Adreno(TM) 830",
            "opencl_c_version": "OpenCL C 3.0 Adreno(TM) 830",
            "device_extensions": extensions,
            "address_bits": 64,
            "endian_little": True,
        },
        "limits": {
            "max_work_group_size": 1024,
            "production_kernel_max_work_group_size": 1024,
            "local_mem_bytes": 32768,
            "max_mem_alloc_bytes": 1_073_741_824,
        },
        "compiler_probe": {
            "build_options": "-cl-std=CL3.0",
            "build_succeeded": True,
            "production_kernel_compiled": True,
            "local_size_64_succeeded": True,
            "bf16_product_succeeded": True,
            "bf16_intrinsic_signature": ("float_qcom_mad32_bf16_ushort_ushort_float"),
            "intrinsic_and_rne_runtime_conformance": True,
            "production_buffer_allocation_succeeded": True,
            "production_buffer_bytes": [
                adreno.PACKED_WEIGHT_BYTES,
                adreno.SCALE_BF16_BYTES,
                adreno.INPUT_BYTES,
                adreno.OUTPUT_BYTES,
            ],
            "production_kernel_arguments_bound": True,
            "fast_math_enabled": False,
            "subgroup_reduce_used": False,
        },
        "arithmetic_observed_bits": [
            "0x40a00000",
            "0xbfc00000",
            "0x40800000",
            "0x3f820200",
            "0x00003f80",
            "0x00003f82",
        ],
    }


def s16_falsification() -> dict[str, object]:
    return {
        "schema_version": adreno.S16_FALSIFICATION_SCHEMA,
        "status": "falsified_scope",
        "candidate_id": adreno.S16_CANDIDATE_ID,
        "governing_bindings": {"oracle_gate_sha256": adreno.S16_ORACLE_GATE_SHA256},
        "adjudication": {"standard_htp_s16_family_exhausted": True},
        "branch_transition": {
            "mandatory_successor": (
                "Adreno_OpenCL_direct_packed_INT2_BF16_product_FP32_accumulation_"
                "BF16_RNE_output"
            )
        },
    }


def selector(opencl_report_sha256: str) -> dict[str, object]:
    selected = {
        "candidate_id": adreno.CANDIDATE_ID,
        "model_sha256": adreno.MODEL_SHA256,
        "packed_weight_sha256": adreno.PACKED_WEIGHT_SHA256,
        "packed_weight_bytes": adreno.PACKED_WEIGHT_BYTES,
        "original_scale_sha256": adreno.SCALE_F32_SHA256,
        "original_scale_bytes": adreno.SCALE_F32_BYTES,
        "scale_transform": (
            "float32_to_bfloat16_RNE_then_signed_INT2_product_to_bfloat16_RNE"
        ),
        "input_dtype": "bfloat16_bits_in_ushort",
        "input_shape": [1, 1, adreno.INPUT_FEATURES],
        "weight_storage": "direct_U2_four_lanes_per_byte_no_dense_expansion",
        "signed_lane_mapping": [-2, -1, 0, 1],
        "output_dtype": "bfloat16_bits_in_ushort",
        "output_shape": [1, 1, adreno.OUTPUT_FEATURES],
        "product_intrinsic": "qcom_mad32_bf16_scalar_ushort_ushort_float",
        "accumulator_dtype": "float32",
        "workgroup_size": 64,
        "rows_per_workgroup": 8,
        "workgroup_count": 32_768,
        "packed_byte_lane_mapping": "lane_l_consumes_byte_l_plus_64t_for_t_0_through_9",
        "lane_accumulators": 4,
        "lane_accumulator_combine": "(a0_plus_a1)_plus_(a2_plus_a3)",
        "workgroup_reduction": "fixed_local_memory_strides_32_16_8_4_2_1",
        "subgroup_reduce_builtin_used": False,
        "output_rounding": "bit_exact_bfloat16_round_to_nearest_even",
        "weight_residency": "one_upload_one_context_all_cases_and_replays",
        "full_case_replays": 2,
        "byte_identical_replay_required": True,
        "dense_weight_expansion_allowed": False,
        "numeric_ranking_threshold_subset_sha256": hashlib.sha256(
            adreno.canonical_json(adreno.FROZEN_THRESHOLDS)
        ).hexdigest(),
        "thresholds_changed": False,
        "candidate_output_observed": False,
    }
    return {
        "schema_version": "gemma4_e4b_frontier_event_v1",
        "state": "selected",
        "parent_frontier_root_sha256": "b" * 64,
        "parent_capsule_sha256": "c" * 64,
        "immutable_candidate_contract": selected,
        "off_lattice_sentinel_contract": {
            "input_shape": [1, 1, adreno.INPUT_FEATURES],
            "construction": (
                "all_zero_BF16_except_one_preregistered_feature_equal_to_2^-10_BF16"
            ),
            "nonzero_feature_index": 0,
            "nonzero_value_bfloat16_bits": "0x3a80",
            "value_is_multiple_of_2^-9": False,
            "input_bytes": adreno.INPUT_BYTES,
            "input_sha256": adreno.SENTINEL_INPUT_SHA256,
            "reference_output_bytes": adreno.OUTPUT_BYTES,
            "reference_rule": (
                "single_product_exact_BF16_semantics_without_reduction_order_ambiguity"
            ),
            "pass_rule": (
                "full_width_524288_byte_reference_candidate_equality_and_byte_identical_replays"
            ),
            "candidate_output_observed": False,
        },
        "frozen_authority_gate": {
            "case_ids": [case["case_id"] for case in adreno.FROZEN_CASES],
            "authority_output_sha256": [
                case["authority_sha256"] for case in adreno.FROZEN_CASES
            ],
            **adreno.FROZEN_THRESHOLDS,
            "every_metric_every_case_must_pass": True,
            "replay_outputs_must_be_byte_identical": True,
        },
        "phone_execution_started": False,
        "candidate_output_observed": False,
        "live_opencl_contract": {
            "report_sha256": opencl_report_sha256,
            "opencl_icd_sha256": adreno.VENDOR_RUNTIME_FILES[0]["sha256"],
            "adreno_opencl_driver_sha256": adreno.VENDOR_RUNTIME_FILES[1]["sha256"],
            "adreno_opencl_compiler_sha256": adreno.VENDOR_RUNTIME_FILES[2]["sha256"],
        },
    }


def opencl_evidence() -> dict[str, object]:
    return {
        "schema_version": "gemma4_e4b_adreno_opencl_contract_report_v1",
        "status": "passed_scope",
        "device_identity": {
            "android_build_fingerprint_sha256": (
                adreno.ANDROID_BUILD_FINGERPRINT_STDOUT_SHA256
            )
        },
        "loader_contract": {
            item["role"]: {"bytes": item["bytes"], "sha256": item["sha256"]}
            for item in adreno.VENDOR_RUNTIME_FILES
        },
        "extension_contract": {
            "required_extensions_present": [
                "cl_qcom_bfloat16_product",
                "cl_khr_subgroups",
            ]
        },
        "bfloat16_product_contract": {
            "required_build_option": "-cl-std=CL3.0",
            "exact_signature": "float_qcom_mad32_bf16_ushort_ushort_float",
        },
        "arithmetic_conformance": {
            "bf16_3f81_times_bf16_3f81_f32_bits": "0x3f820200",
            "bfloat16_rne_tie_3f808000": "0x3f80",
            "bfloat16_rne_tie_3f818000": "0x3f82",
        },
        "workgroup_contract": {
            "selected_local_workgroup_size": 64,
            "required_reduction": "explicit_fixed_local_memory_binary_tree",
        },
        "custody": {"model_or_tensor_access_count": 0},
    }


def write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def initialize_git_repository(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-qm", "freeze source"], check=True
    )


def load_phone_gate():
    path = ROOT / "scripts/termux/run_e4b_adreno_int2_phone_gate.py"
    spec = importlib.util.spec_from_file_location("_test_e4b_adreno_phone_gate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_geometry_is_exact_direct_packed_w2_contract() -> None:
    assert adreno.CANDIDATE_ID == (
        "adreno_opencl_direct_packed_w2_scalar_bf16_product_fp32_tree_bf16_rne_v1"
    )
    assert adreno.PACKED_BYTES_PER_ROW == 640
    assert adreno.PACKED_WEIGHT_BYTES == 167_772_160
    assert adreno.LOCAL_SIZE == 64
    assert adreno.ROWS_PER_WORKGROUP == 8
    assert adreno.WORKGROUP_COUNT == 32_768


def test_lane_byte_mapping_covers_every_feature_and_output_row_exactly_once() -> None:
    features = []
    for lane in range(64):
        for iteration in range(10):
            packed_column = lane + 64 * iteration
            features.extend(4 * packed_column + bit_lane for bit_lane in range(4))
    assert len(features) == 2_560
    assert sorted(features) == list(range(2_560))
    rows = [
        group * 8 + row_in_group for group in range(32_768) for row_in_group in range(8)
    ]
    assert rows == list(range(262_144))


def test_standalone_metrics_match_governing_projection_gate() -> None:
    reference = [((index * 17) % 101 - 50) / 8.0 for index in range(64)]
    candidate = [
        value + (((index * 13) % 7) - 3) / 4096.0
        for index, value in enumerate(reference)
    ]
    observed = adreno.vector_metrics(reference, candidate)
    governing = governing_gate.vector_metrics(reference, candidate)
    for key in (
        "max_abs",
        "rms",
        "relative_l2",
        "cosine",
        "top_k_set_overlap",
        "top_1_equal",
    ):
        assert observed[key] == governing[key]
    observed["softmax_js_divergence"] = adreno.softmax_js_divergence(
        reference, candidate
    )
    governing["softmax_js_divergence"] = governing_gate.softmax_js_divergence(
        reference, candidate
    )
    assert observed["softmax_js_divergence"] == governing["softmax_js_divergence"]
    assert adreno.adjudicate_metrics(observed, adreno.FROZEN_THRESHOLDS) == (
        governing_gate.adjudicate_metrics(governing, adreno.FROZEN_THRESHOLDS)
    )


def test_off_lattice_sentinel_is_exactly_one_0x3a80_feature() -> None:
    payload = adreno.off_s16_lattice_sentinel()
    assert len(payload) == 5_120
    assert hashlib.sha256(payload).hexdigest() == adreno.SENTINEL_INPUT_SHA256
    words = struct.unpack("<2560H", payload)
    assert words[0] == 0x3A80
    assert set(words[1:]) == {0}
    assert adreno.bf16_bits_to_float(words[0]) == 2.0**-10
    assert not (adreno.bf16_bits_to_float(words[0]) * 512.0).is_integer()


def test_s16_input_is_recovered_as_bf16_without_fp16_substitution(monkeypatch) -> None:
    monkeypatch.setattr(adreno, "INPUT_BYTES", 8)
    payload = struct.pack("<hhhh", -512, -1, 0, 511)
    observed = adreno.s16_input_to_bf16(payload)
    values = [
        adreno.bf16_bits_to_float(bits)
        for (bits,) in struct.iter_unpack("<H", observed)
    ]
    assert values == [-1.0, -1.0 / 512.0, 0.0, 1.0]


def test_bf16_rne_ties_round_to_even() -> None:
    low_tie = struct.unpack("<f", struct.pack("<I", 0x3F808000))[0]
    high_tie = struct.unpack("<f", struct.pack("<I", 0x3F818000))[0]
    assert adreno.float32_to_bf16_rne_bits(low_tie) == 0x3F80
    assert adreno.float32_to_bf16_rne_bits(high_tie) == 0x3F82


def test_scale_transform_emits_exact_f32_and_compact_bf16(monkeypatch) -> None:
    monkeypatch.setattr(adreno, "SCALE_F32_BYTES", 12)
    monkeypatch.setattr(adreno, "SCALE_BF16_BYTES", 6)
    source = struct.pack("<fff", 1.0, 0.5, 0.25)
    exact, compact = adreno.bf16_rne_scales(source)
    assert exact == source
    assert struct.unpack("<3H", compact) == (0x3F80, 0x3F00, 0x3E80)


@pytest.mark.parametrize("value", [0.0, -1.0, float("inf"), float("nan")])
def test_scale_transform_rejects_invalid_rows(monkeypatch, value: float) -> None:
    monkeypatch.setattr(adreno, "SCALE_F32_BYTES", 4)
    with pytest.raises(adreno.AdrenoGateError, match="invalid row scale"):
        adreno.bf16_rne_scales(struct.pack("<f", value))


def test_sentinel_reference_uses_low_two_bits_and_signed_mapping(monkeypatch) -> None:
    monkeypatch.setattr(adreno, "OUTPUT_FEATURES", 2)
    monkeypatch.setattr(adreno, "PACKED_BYTES_PER_ROW", 1)
    monkeypatch.setattr(adreno, "PACKED_WEIGHT_BYTES", 2)
    monkeypatch.setattr(adreno, "SCALE_BF16_BYTES", 4)
    monkeypatch.setattr(adreno, "OUTPUT_BYTES", 4)
    packed = bytes([0b00000000, 0b00000011])
    scales = struct.pack("<HH", 0x3F80, 0x3F80)
    observed = struct.unpack("<HH", adreno.sentinel_reference_output(packed, scales))
    assert observed == (0xBB00, 0x3A80)


def test_opencl_contract_normalizes_exact_sp_hal_cl3_scalar_bf16() -> None:
    observed = adreno.normalize_opencl_contract(opencl_contract())
    assert observed["loader"] == {
        "loaded_path": "/vendor/lib64/libOpenCL.so",
        "route": "android_sphal",
    }
    assert observed["compiler_probe"]["build_options"] == "-cl-std=CL3.0"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda value: value["identity"].update(
                device_extensions="cl_khr_subgroups"
            ),
            "extensions",
        ),
        (
            lambda value: value["compiler_probe"].update(build_options="-cl-std=CL2.0"),
            "standard",
        ),
        (
            lambda value: value["compiler_probe"].update(fast_math_enabled=True),
            "fast math",
        ),
        (lambda value: value["limits"].update(max_mem_alloc_bytes=1), "allocation"),
    ],
)
def test_opencl_contract_fails_closed_on_runtime_drift(mutation, message: str) -> None:
    value = opencl_contract()
    mutation(value)
    with pytest.raises(adreno.AdrenoGateError, match=message):
        adreno.normalize_opencl_contract(value)


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    [
        ("immutable_candidate_contract", "workgroup_size", 32, "candidate field"),
        ("off_lattice_sentinel_contract", "nonzero_feature_index", 1, "sentinel"),
        ("off_lattice_sentinel_contract", "input_bytes", 5118, "sentinel"),
        ("off_lattice_sentinel_contract", "input_sha256", "0" * 64, "sentinel"),
        ("off_lattice_sentinel_contract", "reference_output_bytes", 1, "sentinel"),
        ("off_lattice_sentinel_contract", "pass_rule", "relaxed", "sentinel"),
    ],
)
def test_frontier_selector_rejects_frozen_candidate_and_sentinel_drift(
    section: str, field: str, value: object, message: str
) -> None:
    candidate = selector(adreno.FROZEN_OPENCL_EVIDENCE_SHA256)
    candidate[section][field] = value
    with pytest.raises(adreno.AdrenoGateError, match=message):
        adreno._validate_frontier_selector(candidate)


def test_preregistration_rejects_jointly_mutated_ancestor_reports(
    tmp_path: Path,
) -> None:
    assert adreno.sha256_path(FROZEN_SELECTOR_PATH) == (
        adreno.FROZEN_FRONTIER_SELECTOR_SHA256
    )
    assert adreno.sha256_path(FROZEN_OPENCL_EVIDENCE_PATH) == (
        adreno.FROZEN_OPENCL_EVIDENCE_SHA256
    )
    assert adreno.sha256_path(FROZEN_S16_FALSIFICATION_PATH) == (
        adreno.FROZEN_S16_FALSIFICATION_SHA256
    )
    opencl_path = tmp_path / "execution_contract.json"
    write_json(opencl_path, opencl_contract())
    frozen = {
        "selector": FROZEN_SELECTOR_PATH,
        "opencl": FROZEN_OPENCL_EVIDENCE_PATH,
        "s16": FROZEN_S16_FALSIFICATION_PATH,
    }
    for target, source in frozen.items():
        mutated = tmp_path / f"mutated_{target}.json"
        mutated.write_bytes(source.read_bytes() + b"\n")
        paths = dict(frozen)
        paths[target] = mutated
        with pytest.raises(adreno.AdrenoGateError, match="ancestor digest drifted"):
            adreno.build_preregistration(
                repository_root=ROOT,
                frontier_selector_path=paths["selector"],
                s16_falsification_path=paths["s16"],
                opencl_evidence_report_path=paths["opencl"],
                opencl_contract_path=opencl_path,
                output_dir=tmp_path / f"rejected_{target}",
                created_at_utc="2026-07-11T15:30:00Z",
            )


def test_preregistration_binds_selector_falsifier_source_and_unobserved_state(
    monkeypatch,
    tmp_path: Path,
) -> None:
    selector_path = FROZEN_SELECTOR_PATH
    falsification_path = FROZEN_S16_FALSIFICATION_PATH
    opencl_path = tmp_path / "opencl.json"
    evidence_path = FROZEN_OPENCL_EVIDENCE_PATH
    write_json(opencl_path, opencl_contract())
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "bound.py").write_text("BOUND = True\n", encoding="utf-8")
    initialize_git_repository(repository)
    monkeypatch.setattr(adreno, "SOURCE_CLOSURE", ("bound.py",))
    output = tmp_path / "prereg"
    prereg = adreno.build_preregistration(
        repository_root=repository,
        frontier_selector_path=selector_path,
        s16_falsification_path=falsification_path,
        opencl_evidence_report_path=evidence_path,
        opencl_contract_path=opencl_path,
        output_dir=output,
        created_at_utc="2026-07-11T15:30:00Z",
    )
    assert prereg["state"] == "frozen_unobserved"
    assert prereg["candidate_output_observed"] is False
    assert prereg["kernel_contract"]["dense_weight_expansion"] is False
    sentinel = prereg["off_s16_lattice_sentinel"]
    assert sentinel["contains_value_off_s16_2m9_lattice"] is True
    assert "every_value_off_s16_2m9_lattice" not in sentinel
    adreno.validate_preregistration(prereg)
    adreno.validate_source_closure(repository, prereg)
    assert prereg["source_closure"][0]["git_mode"] == "100644"
    preregistration_mutations = (
        lambda value: value.update(frontier_selector_sha256="0" * 64),
        lambda value: value.update(parent_frontier_root_sha256="0" * 64),
        lambda value: value.update(parent_capsule_sha256="0" * 64),
        lambda value: value["mandatory_predecessor"].update(sha256="0" * 64),
        lambda value: value["mandatory_predecessor"].update(
            oracle_gate_sha256="0" * 64
        ),
        lambda value: value["opencl_evidence"].update(report_sha256="0" * 64),
        lambda value: value.update(opencl_contract_source_sha256="0" * 64),
        lambda value: value["phone_execution_envelope"].update(
            thermal_stop_at_or_above_millidegrees_c=90_001
        ),
        lambda value: value["kernel_contract"].update(local_size=32),
        lambda value: value["residency_and_replay"].update(dispatch_count=7),
        lambda value: value["custody"].update(
            raw_phone_private_upload_to_provider=True
        ),
        lambda value: value["toolchain_contract"].update(
            arbitrary_CXX_override_allowed=True
        ),
    )
    for mutation in preregistration_mutations:
        drifted = copy.deepcopy(prereg)
        mutation(drifted)
        with pytest.raises(adreno.AdrenoGateError, match="drifted"):
            adreno.validate_preregistration(drifted)
    assert (
        prereg["source_binding"]["revision"]
        == subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout.strip()
    )
    os.chmod(repository / "bound.py", 0o755)
    with pytest.raises(adreno.AdrenoGateError, match="mode drifted"):
        adreno.validate_source_closure(repository, prereg)
    os.chmod(repository / "bound.py", 0o644)
    (repository / "bound.py").write_text("BOUND = False\n", encoding="utf-8")
    with pytest.raises(adreno.AdrenoGateError, match="mismatch|drifted"):
        adreno.validate_source_closure(repository, prereg)
    with pytest.raises(FileExistsError):
        adreno.build_preregistration(
            repository_root=repository,
            frontier_selector_path=selector_path,
            s16_falsification_path=falsification_path,
            opencl_evidence_report_path=evidence_path,
            opencl_contract_path=opencl_path,
            output_dir=output,
            created_at_utc="2026-07-11T15:30:01Z",
        )


def test_atomic_directory_publish_collision_preserves_both_trees(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    (source / "source.txt").write_text("source", encoding="utf-8")
    (destination / "destination.txt").write_text("destination", encoding="utf-8")
    with pytest.raises(FileExistsError):
        adreno._rename_noreplace(source, destination)
    assert (source / "source.txt").read_text(encoding="utf-8") == "source"
    assert (destination / "destination.txt").read_text(encoding="utf-8") == (
        "destination"
    )


def test_atomic_noreplace_admits_termux_android_platform(monkeypatch) -> None:
    calls: list[tuple[object, ...]] = []

    class FakeRenameAt2:
        argtypes = None
        restype = None

        def __call__(self, *arguments):
            calls.append(arguments)
            return 0

    class FakeLibrary:
        renameat2 = FakeRenameAt2()

    monkeypatch.setattr(adreno.sys, "platform", "android")
    monkeypatch.setattr(adreno.ctypes, "CDLL", lambda *_args, **_kwargs: FakeLibrary())
    adreno._rename_noreplace(Path("source"), Path("destination"))
    assert len(calls) == 1
    assert calls[0][-1] == 1


def test_receipt_transaction_is_complete_immutable_and_collision_safe(
    tmp_path: Path,
) -> None:
    phone_gate = load_phone_gate()
    receipt_dir = tmp_path / "receipt"
    payload = {
        "schema_version": adreno.PHONE_RECEIPT_SCHEMA,
        "status": "blocked_fail_closed",
    }
    digest = phone_gate.publish_receipt_transaction(receipt_dir, payload)
    assert digest == hashlib.sha256(adreno.canonical_json(payload)).hexdigest()
    assert phone_gate.load_complete_receipt(receipt_dir) == payload
    before = {path.name: path.read_bytes() for path in sorted(receipt_dir.iterdir())}
    with pytest.raises(FileExistsError):
        phone_gate.publish_receipt_transaction(receipt_dir, {"status": "replaced"})
    assert {
        path.name: path.read_bytes() for path in sorted(receipt_dir.iterdir())
    } == before


def test_receipt_transaction_rejects_incomplete_directory(tmp_path: Path) -> None:
    phone_gate = load_phone_gate()
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    (incomplete / "receipt.json").write_text("{}", encoding="utf-8")
    with pytest.raises(phone_gate.PhoneExecutionError, match="incomplete"):
        phone_gate.load_complete_receipt(incomplete)


def test_receipt_transaction_verifies_successful_rename_after_parent_fsync_error(
    monkeypatch, tmp_path: Path
) -> None:
    phone_gate = load_phone_gate()
    original_fsync = phone_gate.contract._fsync_directory
    call_count = 0

    def fail_after_rename(path: Path) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise OSError("simulated parent fsync failure after rename")
        original_fsync(path)

    monkeypatch.setattr(phone_gate.contract, "_fsync_directory", fail_after_rename)
    payload = {"status": "falsified_scope", "candidate_execution_count": 1}
    receipt_dir = tmp_path / "receipt"
    digest = phone_gate.publish_receipt_transaction(receipt_dir, payload)
    assert digest == hashlib.sha256(adreno.canonical_json(payload)).hexdigest()
    assert phone_gate.load_complete_receipt(receipt_dir) == payload


def test_retained_payload_hash_rejects_validate_then_read_mutation(
    monkeypatch, tmp_path: Path
) -> None:
    phone_gate = load_phone_gate()
    source = tmp_path / "tensor.bin"
    source.write_bytes(b"good")
    digest = hashlib.sha256(b"good").hexdigest()
    monkeypatch.setattr(phone_gate.contract, "read_regular", lambda _path: b"evil")
    with pytest.raises(phone_gate.PhoneExecutionError, match="changed during"):
        phone_gate.read_frozen_payload(
            source,
            expected_bytes=4,
            expected_sha256=digest,
            label="test tensor",
        )


def test_minimal_phone_environment_drops_hostile_inherited_variables(
    monkeypatch, tmp_path: Path
) -> None:
    phone_gate = load_phone_gate()
    for key in (
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
        "CPATH",
        "CPLUS_INCLUDE_PATH",
        "HF_TOKEN",
        "COMET_API_KEY",
        "PYTHONPATH",
        "BASH_ENV",
        "ENV",
        "CXX",
    ):
        monkeypatch.setenv(key, "hostile")
    environment = phone_gate.minimal_phone_environment(temporary_directory=tmp_path)
    assert not set(environment).intersection(
        {
            "LD_PRELOAD",
            "LD_LIBRARY_PATH",
            "CPATH",
            "CPLUS_INCLUDE_PATH",
            "HF_TOKEN",
            "COMET_API_KEY",
            "PYTHONPATH",
            "BASH_ENV",
            "ENV",
            "CXX",
        }
    )


def test_native_command_never_receives_authority_reference_paths(
    tmp_path: Path,
) -> None:
    phone_gate = load_phone_gate()
    authority = tmp_path / "private_references/authority.bf16.raw"
    case = {
        "contract": {"case_id": "authority_case"},
        "input_path": tmp_path / "private_inputs/input.bf16.raw",
        "authority": authority,
        "output_paths": [
            tmp_path / "private_outputs/replay0.bf16.raw",
            tmp_path / "private_outputs/replay1.bf16.raw",
        ],
    }
    command = phone_gate.native_command(
        binary_path=tmp_path / "native/binary",
        packed_weight_path=tmp_path / "private_tensors/packed.bin",
        scale_path=tmp_path / "private_tensors/scale.bf16.raw",
        native_summary_path=tmp_path / "native/summary.json",
        all_cases=[case],
    )
    assert str(authority) not in command
    assert command.count("--case") == 1
    assert "--packed-weight" in command
    assert "--scale-bf16" in command


def test_host_and_phone_use_standalone_source_bound_import_route() -> None:
    host = (ROOT / "scripts/host/build_e4b_adreno_int2_prereg.py").read_text(
        encoding="utf-8"
    )
    phone = (ROOT / "scripts/termux/run_e4b_adreno_int2_phone_gate.py").read_text(
        encoding="utf-8"
    )
    for source in (host, phone):
        assert "spec_from_file_location" in source
        assert "from polymath_ai.frontier import" not in source
    assert set(adreno.SOURCE_CLOSURE) == {
        "polymath_ai/frontier/e4b_adreno_int2_lm_head.py",
        "scripts/host/build_e4b_adreno_int2_prereg.py",
        "scripts/termux/run_e4b_adreno_int2_phone_gate.py",
        "native/e4b_adreno_int2_lm_head/opencl_dynamic_runtime.h",
        "native/e4b_adreno_int2_lm_head/opencl_dynamic_runtime.cpp",
        "native/e4b_adreno_int2_lm_head/e4b_adreno_int2_lm_head.cpp",
        "native/e4b_adreno_int2_lm_head/build_phone.sh",
    }
    build_script = ROOT / "native/e4b_adreno_int2_lm_head/build_phone.sh"
    assert stat.S_IMODE(build_script.stat().st_mode) == 0o755
    assert os.access(build_script, os.X_OK)
    assert str(build_script.relative_to(ROOT)) in adreno.SOURCE_EXECUTABLES
    build_source = build_script.read_text(encoding="utf-8")
    assert '$(/system/bin/uname -m)' in build_source
    assert '$(uname -m)' not in build_source


def test_sentinel_output_validation_rejects_undersized_payload(tmp_path: Path) -> None:
    phone_gate = load_phone_gate()
    outputs = [tmp_path / "first.raw", tmp_path / "second.raw"]
    for path in outputs:
        path.write_bytes(b"short")
    sentinel = {"output_paths": outputs}
    with pytest.raises(
        phone_gate.contract.AdrenoGateError, match="byte count mismatch"
    ):
        phone_gate.adjudicate_outputs(
            cases=[],
            sentinel=sentinel,
            sentinel_reference=b"\0" * adreno.OUTPUT_BYTES,
        )


def test_replay_mismatch_falsifies_otherwise_exact_authority_case(
    tmp_path: Path,
) -> None:
    phone_gate = load_phone_gate()
    authority_payload = b"\x80\x3f" * adreno.OUTPUT_FEATURES
    authority = tmp_path / "authority.raw"
    authority.write_bytes(authority_payload)
    first = tmp_path / "first.raw"
    second = tmp_path / "second.raw"
    first.write_bytes(authority_payload)
    replay_payload = bytearray(authority_payload)
    replay_payload[-1] ^= 1
    second.write_bytes(replay_payload)
    sentinel_first = tmp_path / "sentinel_first.raw"
    sentinel_second = tmp_path / "sentinel_second.raw"
    sentinel_first.write_bytes(authority_payload)
    sentinel_second.write_bytes(authority_payload)
    case_results, sentinel_result, every_passed = phone_gate.adjudicate_outputs(
        cases=[
            {
                "contract": {
                    "case_id": "authority_case",
                    "authority_bytes": adreno.OUTPUT_BYTES,
                    "authority_sha256": hashlib.sha256(authority_payload).hexdigest(),
                },
                "authority": authority,
                "output_paths": [first, second],
            }
        ],
        sentinel={"output_paths": [sentinel_first, sentinel_second]},
        sentinel_reference=authority_payload,
    )
    assert every_passed is False
    assert case_results[0]["passed"] is False
    assert case_results[0]["failures"] == ["replay_not_byte_identical"]
    assert sentinel_result["passed"] is True


def test_native_return_code_and_replay_claims_must_match_observed_outputs(
    tmp_path: Path,
) -> None:
    phone_gate = load_phone_gate()
    case_ids = [case["case_id"] for case in adreno.FROZEN_CASES]
    case_ids.append(adreno.SENTINEL_CASE_ID)
    summary = {
        "schema_version": "gemma4_e4b_adreno_int2_native_summary_v1",
        "candidate_id": adreno.CANDIDATE_ID,
        "build_options": "-cl-std=CL3.0",
        "lifecycle": {
            "process_count": 1,
            "context_count": 1,
            "program_build_count": 1,
            "packed_weight_upload_count": 1,
            "scale_upload_count": 1,
            "authority_case_count": 3,
            "sentinel_case_count": 1,
            "replays_per_case": 2,
            "dispatch_count": 8,
        },
        "cases": [
            {
                "case_id": case_id,
                "kernel_elapsed_ns": [1, 1],
                "replay_byte_identical": index != 0,
            }
            for index, case_id in enumerate(case_ids)
        ],
        "all_replays_byte_identical": False,
    }
    summary_path = tmp_path / "summary.json"
    write_json(summary_path, summary)
    preregistration = {"cases": [{"case_id": case_id} for case_id in case_ids[:-1]]}
    with pytest.raises(phone_gate.PhoneExecutionError, match="return code"):
        phone_gate.validate_native_summary(summary_path, preregistration, 0)
    validated = phone_gate.validate_native_summary(summary_path, preregistration, 2)
    observed_cases = [
        {"case_id": case_id, "replay_byte_identical": True} for case_id in case_ids[:-1]
    ]
    observed_sentinel = {
        "case_id": case_ids[-1],
        "replay_byte_identical": True,
    }
    with pytest.raises(phone_gate.PhoneExecutionError, match="independently"):
        phone_gate.validate_native_replay_observations(
            validated, observed_cases, observed_sentinel
        )


def test_failure_receipt_tracks_launch_and_partial_output_state() -> None:
    source = (ROOT / "scripts/termux/run_e4b_adreno_int2_phone_gate.py").read_text(
        encoding="utf-8"
    )
    assert 'progress["native_launch_state"] = "process_started"' in source
    assert 'progress["candidate_execution_count"] = 1' in source
    assert (
        '"candidate_execution_count": progress["candidate_execution_count"]' in source
    )
    assert '"present_unadjudicated_or_partial"' in source
    assert 'progress["candidate_output_adjudicated"] = True' in source
    assert '"adjudication_status": progress["adjudication_status"]' in source


def test_late_blocker_receipt_preserves_completed_adjudication_truth(
    monkeypatch, tmp_path: Path
) -> None:
    phone_gate = load_phone_gate()
    run_root = tmp_path / "run"
    run_root.mkdir()
    receipt_dir = tmp_path / "receipt"
    observed: dict[str, object] = {}

    def fail_after_adjudication(_args, progress: dict[str, object]) -> int:
        progress.update(
            {
                "native_launch_state": "process_returned",
                "candidate_execution_count": 1,
                "candidate_output_state": "fully_adjudicated",
                "candidate_output_adjudicated": True,
                "adjudication_status": "falsified_scope",
                "every_case_and_metric_passed": False,
            }
        )
        raise phone_gate.PhoneExecutionError("late resource guard failure")

    def capture_receipt(_directory: Path, payload: dict[str, object]) -> str:
        observed.update(payload)
        return "0" * 64

    monkeypatch.setattr(phone_gate, "execute", fail_after_adjudication)
    monkeypatch.setattr(phone_gate, "publish_receipt_transaction", capture_receipt)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "phone_gate",
            "--preregistration",
            str(tmp_path / "prereg.json"),
            "--prereg-sha256",
            "a" * 64,
            "--run-root",
            str(run_root),
            "--packed-weight",
            str(tmp_path / "packed.bin"),
            "--source-scale",
            str(tmp_path / "scale.bin"),
            "--receipt-dir",
            str(receipt_dir),
        ],
    )
    assert phone_gate.main() == 3
    assert observed["candidate_output_adjudicated"] is True
    assert observed["adjudication_status"] == "falsified_scope"
    assert observed["bounded_terminal_head_every_case_and_metric_passed"] is False


def test_runtime_environment_binds_full_ordered_identity() -> None:
    environment = adreno.runtime_environment(opencl_contract())
    assert environment["POLYMATH_EXPECT_OPENCL_LOAD_ROUTE"] == "android_sphal"
    assert environment["POLYMATH_EXPECT_OPENCL_DEVICE_NAME"] == (
        "QUALCOMM Adreno(TM) 830"
    )
    extensions = json.loads(OPENCL_EXTENSION_DUMP_PATH.read_text(encoding="utf-8"))[
        "device"
    ]["extensions"]
    assert environment["POLYMATH_EXPECT_OPENCL_DEVICE_EXTENSIONS"] == extensions
    assert extensions.endswith(" ")


def test_native_source_uses_typed_scalar_intrinsic_and_fixed_tree() -> None:
    source = NATIVE_SOURCE.read_text(encoding="utf-8")
    assert "qcom_mad32_bf16(input_tile[input_base + 0u]" in source
    assert "ushort2" not in source
    assert "sub_group_reduce" not in source
    assert "-cl-std=CL3.0" in source
    assert "-cl-fast-relaxed-math" not in source
    assert "packed_column = lane" in source
    assert "packed_column += LOCAL_SIZE" in source
    assert "(acc0 + acc1) + (acc2 + acc3)" in source
    assert "stride = LOCAL_SIZE >> 1" in source
    assert "stride >>= 1" in source
    assert "f32_to_bf16_rne(reduction[0u])" in source


def test_native_probe_is_source_neutral_and_executes_arithmetic_conformance() -> None:
    source = NATIVE_SOURCE.read_text(encoding="utf-8")
    assert 'option == "--probe-contract"' in source
    assert 'model_or_tensor_access_count\\":0' in source
    assert "e4b_intrinsic_contract_probe" in source
    assert "0x3F820200U" in source
    assert "production kernel rejected local size 64" in source
    assert '"production_buffer_allocation_succeeded\\":true' in source
    assert '"production_kernel_arguments_bound\\":true' in source
    assert "kProductionBufferBytes" in source
    assert "probe clSetKernelArg production geometry" in source
    assert "kPackedWeightBytes" in source
    assert "kScaleBytes" in source
    assert "kInputBytes" in source
    assert "kOutputBytes" in source
    assert source.count("api.release_program(program);") == 1


def test_native_runtime_uses_android_sphal_and_exact_identity_binding() -> None:
    source = NATIVE_RUNTIME.read_text(encoding="utf-8")
    assert 'kOpenClLibraryPath = "/vendor/lib64/libOpenCL.so"' in source
    assert "android_load_sphal_library" in source
    assert "POLYMATH_EXPECT_OPENCL_DEVICE_EXTENSIONS" in source
    assert "identity.max_mem_alloc_bytes < 167'772'160U" in source


def test_native_sources_are_host_syntax_clean() -> None:
    compiler = shutil.which("clang++")
    if compiler is None:
        pytest.skip("clang++ unavailable")
    subprocess.run(
        [
            compiler,
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Wshadow",
            "-Wconversion",
            "-Wsign-conversion",
            "-fsyntax-only",
            str(NATIVE_RUNTIME),
            str(NATIVE_SOURCE),
        ],
        check=True,
        cwd=ROOT,
    )

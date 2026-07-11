from __future__ import annotations

import json
from pathlib import Path
import struct
import subprocess
import sys

import pytest

from polymath_ai.frontier import e4b_l2_int16_v2 as v2
from polymath_ai.frontier import e4b_l2_int16_v2_package as package
from polymath_ai.frontier import e4b_l2_int16_v2_verifier as verifier
from polymath_ai.frontier.e4b_f5_probe import QAT_MODEL_SHA256
from polymath_ai.frontier.e4b_f5_qnn_exporter import LM_HEAD_GRAPH, Q_PROJ_GRAPH
from polymath_ai.frontier.e4b_l2_projection_gate import (
    ProjectionGateError,
    canonical_json,
    sha256_bytes,
)


ROOT = Path(__file__).resolve().parents[1]
V1_PREREG = (
    ROOT / "runtime/reports/apex_frontier/20260711T020600Z_l2_int16_head_prereg_v2"
)
FP16_GATE = (
    ROOT
    / "runtime/reports/apex_frontier/20260711T015600Z_l2_projection_reference_attempt2"
    / "reference_gate.json"
)
FRONTIER_SELECTOR = (
    ROOT / "runtime/reports/apex_frontier/frontier_event_20260711T101133Z.json"
)
PARENT_CAPSULE = (
    ROOT
    / "docs/APEX-CURRENT-REALITY-CAPSULE-GEMMA4-E4B-QNN-CELL-2026-07-10.yaml.archive"
    / "66072e0dee357c9d7c178c3fa3628a6230fa5992659325b80e7eefa6e4dbdd2b.yaml"
)
ACCESS_RECEIPT = (
    ROOT / "runtime/reports/apex_frontier/access_refresh_20260711T020533Z.json"
)
SOURCE_REVISION = "a" * 40
PARENT_CAPSULE_SHA256 = v2.PARENT_CAPSULE_SHA256


def _record(path: Path, root: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {
        "relative_path": path.relative_to(root).as_posix(),
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }


def _write_prereg(tmp_path: Path, monkeypatch) -> Path:
    scales = b"".join(
        struct.pack("<f", value) for value in (1.0001, 1.00390625, 0.5, 2.0)
    )
    scale_sha = sha256_bytes(scales)
    for module in (v2, package):
        monkeypatch.setattr(module, "ORIGINAL_SCALE_BYTES", len(scales))
        monkeypatch.setattr(module, "ORIGINAL_SCALE_SHA256", scale_sha)
    monkeypatch.setattr(v2, "ROW_SCALE_COUNT", 4)
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
    scale_path = tmp_path / "original_scale.f32.bin"
    scale_path.write_bytes(scales)
    prereg = tmp_path / "v2_prereg"
    v2.build_int16_v2_preregistration(
        parent_int16_prereg_dir=V1_PREREG,
        frontier_selector=FRONTIER_SELECTOR,
        parent_capsule=PARENT_CAPSULE,
        access_receipt=ACCESS_RECEIPT,
        phone_runtime_root=tmp_path,
        original_scale_path=scale_path,
        output_dir=prereg,
        created_at_utc="2026-07-11T10:20:00Z",
        source_revision=SOURCE_REVISION,
    )
    return prereg


def _resource_snapshots(*, independent: bool) -> list[dict[str, object]]:
    prefix = "independent_" if independent else ""
    checkpoints = [f"{prefix}before_first_row_block"]
    checkpoints.extend(
        f"{prefix}after_rows_{start}_{min(start + v2.ORACLE_ROW_BLOCK_SIZE, v2.OUTPUT_FEATURES)}"
        for start in range(
            0,
            v2.OUTPUT_FEATURES - v2.ORACLE_ROW_BLOCK_SIZE,
            v2.ORACLE_ROW_BLOCK_SIZE,
        )
    )
    return [
        {
            "checkpoint": checkpoint,
            "sensor_type": v2.THERMAL_SENSOR_TYPE,
            "temperature_millidegrees_c": 50_000,
            "available_memory_bytes": v2.MIN_AVAILABLE_MEMORY_BYTES,
            "available_storage_bytes": v2.MIN_AVAILABLE_STORAGE_BYTES,
            "elapsed_seconds": float(index),
        }
        for index, checkpoint in enumerate(checkpoints)
    ]


def _sanitized_runtime_binding() -> dict[str, object]:
    return {
        "execution_plane": "phone_native_termux",
        "device": v2.RESOURCE_SLICE["phone"],
        "phone_serial_sha256": v2.RESOURCE_SLICE["phone_serial_sha256"],
        "runtime_root_sha256": "d" * 64,
        "raw_output_custody": "phone_private_no_egress",
        "raw_phone_private_upload": False,
        "qnn_execution": False,
        "absolute_paths_egressed": False,
    }


def _write_canonical_with_sidecar(path: Path, payload: dict[str, object]) -> str:
    path.write_bytes(canonical_json(payload))
    digest = sha256_bytes(path.read_bytes())
    path.with_suffix(path.suffix + ".sha256").write_text(
        f"{digest}  {path.name}\n",
        encoding="ascii",
    )
    return digest


def _write_sanitized_authorization(
    prereg: Path,
    output: Path,
) -> tuple[Path, Path, Path]:
    manifest = json.loads((prereg / "preregistration.json").read_bytes())
    output.mkdir()
    metadata = output / "prereg_metadata"
    metadata.mkdir()
    for name in (
        "preregistration.json",
        "preregistration.json.sha256",
        "threshold_policy.json",
        "threshold_policy.json.sha256",
    ):
        (metadata / name).write_bytes((prereg / name).read_bytes())
    cases = []
    metrics = {
        "count": v2.OUTPUT_FEATURES,
        "max_abs": 0.0,
        "rms": 0.0,
        "relative_l2": 0.0,
        "cosine": 1.0,
        "top_k": 32,
        "top_k_set_overlap": 1.0,
        "top_1_equal": True,
        "reference_top_k": list(range(32)),
        "candidate_top_k": list(range(32)),
        "softmax_js_divergence": 0.0,
    }
    for prereg_case in manifest["cases"]:
        candidate_sha256 = sha256_bytes(prereg_case["case_id"].encode("ascii"))
        output_relative = (
            "oracle_outputs/gemma4_e4b_f5_w2_lm_head."
            f"{prereg_case['case_id']}.exact_int32_oracle.s16.raw"
        )
        cases.append(
            {
                "case_id": prereg_case["case_id"],
                "input_sha256": prereg_case["s16_input_sha256"],
                "authority_output": {
                    "relative_path": prereg_case["authority_output"][
                        "provider_relative_path"
                    ],
                    "bytes": prereg_case["authority_output"]["bytes"],
                    "sha256": prereg_case["authority_output"]["sha256"],
                },
                "candidate_output": {
                    "relative_path": output_relative,
                    "bytes": v2.OUTPUT_FEATURES * 2,
                    "sha256": candidate_sha256,
                    "dtype": "int16",
                    "scale": v2.OUTPUT_SCALE,
                    "shape": [1, 1, v2.OUTPUT_FEATURES],
                },
                "exact_int32_dot": {
                    "input_features": v2.INPUT_FEATURES,
                    "output_features": v2.OUTPUT_FEATURES,
                    "multiply_accumulate_count": v2.FULL_WIDTH_DOT_PRODUCTS_PER_CASE,
                    "accumulator_dtype": "int32",
                    "worst_case_abs_bound": 20_971_520,
                    "int32_safe": True,
                },
                "s16_saturation_count": 0,
                "metrics": metrics,
                "failures": [],
                "passed": True,
            }
        )
    gate = {
        "schema_version": v2.V2_ORACLE_SCHEMA,
        "status": "passed_scope",
        "scope": "full_width_exact_INT32_dot_pre_provider_falsifier",
        "run_id": "20260711T102000Z_l2_s16_v2_exact_oracle",
        "candidate_id": v2.V2_CANDIDATE_ID,
        "frontier_selector_sha256": v2.FRONTIER_SELECTOR_SHA256,
        "parent_capsule_sha256": v2.PARENT_CAPSULE_SHA256,
        "access_receipt_sha256": v2.ACCESS_RECEIPT_SHA256,
        "resource_slice": v2.RESOURCE_SLICE,
        "phone_execution_envelope": v2.execution_envelope(),
        "source_revision": SOURCE_REVISION,
        "implementation_module_sha256": manifest["implementation_module_sha256"],
        "preregistration_sha256": sha256_bytes(
            (prereg / "preregistration.json").read_bytes()
        ),
        "threshold_policy_sha256": manifest["threshold_policy_sha256"],
        "numeric_and_ranking_threshold_subset_sha256": v2.NUMERIC_THRESHOLD_SUBSET_SHA256,
        "packed_weight_sha256": v2.PACKED_WEIGHT_SHA256,
        "transformed_scale_sha256": manifest["candidate_contract"][
            "transformed_scale_sha256"
        ],
        "scale_transform": "float32_to_bfloat16_RNE_then_exact_float32_storage",
        "input_scale": v2.INPUT_SCALE,
        "output_scale": v2.OUTPUT_SCALE,
        "oracle_execution_count": 3,
        "full_width_dot_products_total": v2.FULL_WIDTH_DOT_PRODUCTS_PER_CASE * 3,
        "case_records": cases,
        "every_case_passed": True,
        "provider_build_allowed": True,
        "qnn_execution_count": 0,
        "phone_qnn_execution_count": 0,
        "phone_native_exact_oracle_execution_count": 1,
        "wall_time_seconds": 127.0,
        "python_version": v2.ORACLE_PYTHON_VERSION,
        "python_executable_sha256": "e" * 64,
        "numpy_version": v2.ORACLE_NUMPY_VERSION,
        "runtime_binding": _sanitized_runtime_binding(),
        "resource_snapshots": _resource_snapshots(independent=False),
        "custody": {
            "raw_candidate_outputs": "phone_private",
            "raw_authority_outputs": "phone_private",
            "raw_output_egress": False,
            "sanitized_gate_egress_allowed": True,
            "qnn_phone_execution_is_distinct": True,
        },
        "failure_rule": "provider_build_forbidden_unless_status_passed_scope_and_every_case_passed",
        "claim_boundary": "exact_quantized_oracle_only_no_provider_or_phone_execution",
    }
    gate_path = output / "oracle_gate.json"
    gate_sha256 = _write_canonical_with_sidecar(gate_path, gate)
    receipt_cases = [
        {
            "case_id": frozen["case_id"],
            "input_sha256": frozen["s16_input_sha256"],
            "authority_output_sha256": frozen["authority_output"]["sha256"],
            "candidate_output_sha256": gate_case["candidate_output"]["sha256"],
            "metrics_sha256": sha256_bytes(canonical_json(gate_case["metrics"])),
            "exact_int32_dot_output_match": True,
            "unchanged_metrics_recomputed_from_phone_local_raw": True,
            "passed": True,
        }
        for gate_case, frozen in zip(cases, v2.FROZEN_CASES, strict=True)
    ]
    receipt = {
        "schema_version": verifier.VERIFICATION_SCHEMA,
        "status": "passed_scope",
        "scope": "independent_phone_native_full_width_exact_INT32_dot_and_metric_recomputation",
        "run_id": "20260711T102500Z_l2_s16_v2_exact_verification",
        "candidate_id": v2.V2_CANDIDATE_ID,
        "source_revision": SOURCE_REVISION,
        "candidate_module_sha256": manifest["implementation_module_sha256"],
        "verifier_module_sha256": v2.sha256_path(Path(verifier.__file__)),
        "parent_capsule_sha256": v2.PARENT_CAPSULE_SHA256,
        "access_receipt_sha256": v2.ACCESS_RECEIPT_SHA256,
        "frontier_selector_sha256": v2.FRONTIER_SELECTOR_SHA256,
        "resource_slice": v2.RESOURCE_SLICE,
        "phone_execution_envelope": v2.execution_envelope(),
        "preregistration_sha256": sha256_bytes(
            (prereg / "preregistration.json").read_bytes()
        ),
        "oracle_gate_sha256": gate_sha256,
        "packed_weight_sha256": v2.PACKED_WEIGHT_SHA256,
        "transformed_scale_sha256": manifest["candidate_contract"][
            "transformed_scale_sha256"
        ],
        "numeric_and_ranking_threshold_subset_sha256": v2.NUMERIC_THRESHOLD_SUBSET_SHA256,
        "case_records": receipt_cases,
        "verification_evidence_root_sha256": verifier._verification_root(receipt_cases),
        "phone_native_exact_oracle_execution_count": 1,
        "phone_native_independent_verification_count": 1,
        "phone_qnn_execution_count": 0,
        "every_case_passed": True,
        "provider_build_allowed": True,
        "python_version": v2.ORACLE_PYTHON_VERSION,
        "python_executable_sha256": "f" * 64,
        "numpy_version": v2.ORACLE_NUMPY_VERSION,
        "wall_time_seconds": 127.0,
        "runtime_binding": _sanitized_runtime_binding(),
        "resource_snapshots": _resource_snapshots(independent=True),
        "custody": {
            "raw_authority_and_candidate_outputs": "phone_private_not_in_receipt",
            "raw_artifact_egress_count": 0,
            "raw_phone_private_upload": False,
            "sanitized_hash_metric_receipt_only": True,
        },
    }
    receipt_path = output / "verification_receipt.json"
    _write_canonical_with_sidecar(receipt_path, receipt)
    return metadata, gate_path, receipt_path


def _write_base_package(root: Path, packed: bytes, original_scale: bytes) -> None:
    for directory in ("tensors", "source", "config"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    tensor_payloads = {
        package.PACKED_BASE_RELATIVE_PATH: packed,
        package.SCALE_BASE_RELATIVE_PATH: original_scale,
    }
    for index in range(6):
        tensor_payloads[f"tensors/aux_{index}.bin"] = bytes([index])
    tensor_files = []
    for relative, payload in tensor_payloads.items():
        path = root / relative
        path.write_bytes(payload)
        tensor_files.append(_record(path, root))
    generated_payloads = {
        "source/direct_qnn_probes.cpp": b"base FP16 source\n",
        "source/packed_tensors.S": b"base assembly\n",
        "build_model_library.sh": (
            b'#!/usr/bin/env bash\nset -euo pipefail\n\nROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\n'
        ),
        "run_context_generation.sh": (
            b'#!/usr/bin/env bash\nset -euo pipefail\n\nROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\n'
            b'REFERENCE_GATE="${REFERENCE_GATE:?}"\nOUT="$ROOT/context"\n'
        ),
        "config/backend.json": b"{}\n",
        "config/extensions.json": b"{}\n",
    }
    generated_files = []
    for relative, payload in generated_payloads.items():
        path = root / relative
        path.write_bytes(payload)
        generated_files.append(_record(path, root))
    manifest = {
        "schema_version": "gemma4_e4b_f5_direct_qnn_probe_package_v1",
        "status": "proposed_executable_backend_unvalidated",
        "claim_class": "source_generation_only",
        "artifact": {
            "carrier_sha256": QAT_MODEL_SHA256,
            "full_provider_identity_green": True,
        },
        "lowering": {"lm_head": {}},
        "graphs": [
            {"name": Q_PROJ_GRAPH, "tensor_abi": {}},
            {"name": LM_HEAD_GRAPH, "tensor_abi": {}},
        ],
        "tensor_files": tensor_files,
        "generated_files": generated_files,
        "execution_preconditions": {},
    }
    encoded = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    (root / "package_manifest.json").write_bytes(encoded)
    digest = sha256_bytes(encoded)
    (root / "package_manifest.sha256").write_text(
        f"{digest}  package_manifest.json\n",
        encoding="ascii",
    )


def test_provider_materialization_requires_passed_oracle_and_gates_compile(
    tmp_path: Path,
    monkeypatch,
):
    packed = b"\x1b"
    packed_sha = sha256_bytes(packed)
    for module in (v2, verifier, package):
        monkeypatch.setattr(module, "PACKED_WEIGHT_BYTES", len(packed))
        monkeypatch.setattr(module, "PACKED_WEIGHT_SHA256", packed_sha)
    prereg = _write_prereg(tmp_path, monkeypatch)
    original_scale = (tmp_path / "original_scale.f32.bin").read_bytes()
    prereg_metadata, oracle_gate, verification_receipt = _write_sanitized_authorization(
        prereg,
        tmp_path / "oracle",
    )
    context_gate = tmp_path / "context_gate.json"
    package.build_int16_v2_context_gate(
        fp16_falsification_gate=FP16_GATE,
        int16_v2_prereg_dir=prereg_metadata,
        int16_v2_oracle_gate=oracle_gate,
        int16_v2_verification_receipt=verification_receipt,
        provider_original_scale=tmp_path / "original_scale.f32.bin",
        output_path=context_gate,
        source_revision=SOURCE_REVISION,
        parent_capsule_sha256=PARENT_CAPSULE_SHA256,
        frontier_selector_sha256=v2.FRONTIER_SELECTOR_SHA256,
    )
    base = tmp_path / "base"
    base.mkdir()
    _write_base_package(base, packed, original_scale)
    output = tmp_path / "variant"
    result = package.materialize_int16_v2_variant(
        base_package_dir=base,
        fp16_falsification_gate=FP16_GATE,
        int16_v2_prereg_dir=prereg_metadata,
        int16_v2_oracle_gate=oracle_gate,
        int16_v2_verification_receipt=verification_receipt,
        context_gate=context_gate,
        output_dir=output,
        source_revision=SOURCE_REVISION,
        parent_capsule_sha256=PARENT_CAPSULE_SHA256,
        frontier_selector_sha256=v2.FRONTIER_SELECTOR_SHA256,
    )
    variant = json.loads((output / "package_manifest.json").read_bytes())
    assert result["oracle_gate_sha256"] == sha256_bytes(oracle_gate.read_bytes())
    assert variant["variant_identity"]["candidate_id"] == v2.V2_CANDIDATE_ID
    assert variant["lowering"]["lm_head"]["activation_abi"]["output_scale"] == 2**-10
    assert (output / package.PACKED_BASE_RELATIVE_PATH).read_bytes() == packed
    assert (output / package.SCALE_BASE_RELATIVE_PATH).read_bytes() == (
        v2.bf16_rne_scales_as_exact_f32(
            original_scale,
            expected_count=len(original_scale) // 4,
        )
    )
    build_script = (output / "build_model_library.sh").read_text()
    assert "verify_v2_provider_build.py" in build_script
    assert "v2_phone_verification_receipt.json" in build_script
    context_script = (output / "run_context_generation.sh").read_text()
    assert "verify_v2_context_gate.py" in context_script
    authorization = json.loads(
        (output / "config/v2_provider_build_authorization.json").read_bytes()
    )
    assert authorization["oracle_gate_sha256"] == sha256_bytes(oracle_gate.read_bytes())
    assert authorization["context_gate_sha256"] == sha256_bytes(
        context_gate.read_bytes()
    )
    subprocess.run(
        [
            sys.executable,
            str(output / "source/verify_v2_provider_build.py"),
            str(oracle_gate),
            str(verification_receipt),
            str(output / "config/v2_provider_build_authorization.json"),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(output / "source/verify_v2_context_gate.py"),
            str(context_gate),
            str(output / "config/v2_provider_build_authorization.json"),
        ],
        check=True,
    )

    with pytest.raises(ProjectionGateError, match="variant output already exists"):
        package.materialize_int16_v2_variant(
            base_package_dir=base,
            fp16_falsification_gate=FP16_GATE,
            int16_v2_prereg_dir=prereg_metadata,
            int16_v2_oracle_gate=oracle_gate,
            int16_v2_verification_receipt=verification_receipt,
            context_gate=context_gate,
            output_dir=output,
            source_revision=SOURCE_REVISION,
            parent_capsule_sha256=PARENT_CAPSULE_SHA256,
            frontier_selector_sha256=v2.FRONTIER_SELECTOR_SHA256,
        )


def test_context_gate_and_provider_reject_failed_oracle_before_base_build(
    tmp_path: Path,
    monkeypatch,
):
    prereg = _write_prereg(tmp_path, monkeypatch)
    metadata, failed, receipt = _write_sanitized_authorization(
        prereg,
        tmp_path / "authorization",
    )
    gate = json.loads(failed.read_bytes())
    gate["status"] = "falsified_scope"
    gate["every_case_passed"] = False
    gate["provider_build_allowed"] = False
    _write_canonical_with_sidecar(failed, gate)
    with pytest.raises(ProjectionGateError, match="oracle gate mismatch: status"):
        package.build_int16_v2_context_gate(
            fp16_falsification_gate=FP16_GATE,
            int16_v2_prereg_dir=metadata,
            int16_v2_oracle_gate=failed,
            int16_v2_verification_receipt=receipt,
            provider_original_scale=tmp_path / "original_scale.f32.bin",
            output_path=tmp_path / "context.json",
            source_revision=SOURCE_REVISION,
            parent_capsule_sha256=PARENT_CAPSULE_SHA256,
            frontier_selector_sha256=v2.FRONTIER_SELECTOR_SHA256,
        )


@pytest.mark.parametrize(
    "forgery", ["invalid_output_sha", "fabricated_metrics", "secret_run_id"]
)
def test_sanitized_authorization_rejects_forged_phone_evidence(
    tmp_path: Path,
    monkeypatch,
    forgery: str,
):
    prereg = _write_prereg(tmp_path, monkeypatch)
    metadata, gate_path, receipt_path = _write_sanitized_authorization(
        prereg,
        tmp_path / "authorization",
    )
    verifier.validate_sanitized_phone_authorization(
        prereg_metadata_dir=metadata,
        oracle_gate_path=gate_path,
        verification_receipt_path=receipt_path,
    )
    gate = json.loads(gate_path.read_bytes())
    if forgery == "invalid_output_sha":
        gate["case_records"][0]["candidate_output"]["sha256"] = "not-a-sha256"
    elif forgery == "fabricated_metrics":
        gate["case_records"][0]["metrics"] = {"fabricated": "yes"}
    else:
        gate["run_id"] = "/data/local/tmp/FY25013101C8/secret.token"
    gate_sha256 = _write_canonical_with_sidecar(gate_path, gate)
    receipt = json.loads(receipt_path.read_bytes())
    receipt["oracle_gate_sha256"] = gate_sha256
    _write_canonical_with_sidecar(receipt_path, receipt)
    with pytest.raises(ProjectionGateError):
        verifier.validate_sanitized_phone_authorization(
            prereg_metadata_dir=metadata,
            oracle_gate_path=gate_path,
            verification_receipt_path=receipt_path,
        )


@pytest.mark.parametrize("nested_surface", ["case", "metric", "output"])
def test_phone_local_gate_rejects_nested_custody_fields_before_receipt(
    tmp_path: Path,
    monkeypatch,
    nested_surface: str,
):
    prereg = _write_prereg(tmp_path, monkeypatch)
    _, gate_path, _ = _write_sanitized_authorization(
        prereg,
        tmp_path / "authorization",
    )
    gate = json.loads(gate_path.read_bytes())
    case = gate["case_records"][0]
    if nested_surface == "case":
        case["raw_phone_path"] = "/data/local/tmp/FY25013101C8"
    elif nested_surface == "metric":
        case["metrics"]["secret"] = "FY25013101C8"
    else:
        case["candidate_output"]["raw_locator"] = "/data/local/tmp/output.raw"
    _write_canonical_with_sidecar(gate_path, gate)
    with pytest.raises(ProjectionGateError, match="structure mismatch"):
        v2.validate_passed_int16_v2_oracle_local(
            prereg_dir=prereg,
            oracle_gate_path=gate_path,
            authority_root=tmp_path / "phone_private_authority",
        )

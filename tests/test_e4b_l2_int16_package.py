from __future__ import annotations

import json
from pathlib import Path

import pytest

from polymath_ai.frontier.e4b_f5_probe import QAT_MODEL_SHA256
from polymath_ai.frontier.e4b_f5_qnn_exporter import LM_HEAD_GRAPH, Q_PROJ_GRAPH
from polymath_ai.frontier.e4b_l2_int16_package import (
    INT16_POLICY_SHA256,
    INT16_PREREG_SHA256,
    ProjectionGateError,
    build_int16_context_gate,
    materialize_int16_variant,
)
from polymath_ai.frontier.e4b_l2_projection_gate import canonical_json, sha256_bytes


ROOT = Path(__file__).resolve().parents[1]
FP16_GATE = (
    ROOT
    / "runtime/reports/apex_frontier/20260711T015600Z_l2_projection_reference_attempt2"
    / "reference_gate.json"
)
INT16_PREREG = (
    ROOT
    / "runtime/reports/apex_frontier/20260711T020600Z_l2_int16_head_prereg_v2"
)
SOURCE_REVISION = "a" * 40
PARENT_CAPSULE_SHA256 = "b" * 64
FRONTIER_SELECTOR_SHA256 = "c" * 64


def _record(path: Path, root: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {
        "relative_path": path.relative_to(root).as_posix(),
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }


def _write_base_package(root: Path) -> None:
    for directory in ("tensors", "source", "config"):
        (root / directory).mkdir(parents=True, exist_ok=True)

    tensor_files = []
    for index in range(8):
        path = root / "tensors" / f"tensor_{index}.raw"
        path.write_bytes(bytes([index]))
        tensor_files.append(_record(path, root))

    generated_payloads = {
        "source/direct_qnn_probes.cpp": b"base FP16 source\n",
        "source/packed_tensors.S": b"base assembly\n",
        "build_model_library.sh": b"#!/usr/bin/env bash\n",
        "run_context_generation.sh": b"#!/usr/bin/env bash\n",
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


def _build_gate(path: Path) -> dict[str, object]:
    build_int16_context_gate(
        fp16_falsification_gate=FP16_GATE,
        int16_prereg_dir=INT16_PREREG,
        output_path=path,
        source_revision=SOURCE_REVISION,
        parent_capsule_sha256=PARENT_CAPSULE_SHA256,
        frontier_selector_sha256=FRONTIER_SELECTOR_SHA256,
    )
    return json.loads(path.read_bytes())


def test_context_gate_exactly_matches_existing_context_runner_shape(tmp_path: Path):
    path = tmp_path / "context_gate.json"
    gate = _build_gate(path)
    assert canonical_json(gate) == path.read_bytes()
    assert gate["l2_threshold_policy_sha256"] == INT16_POLICY_SHA256
    assert gate["int16_preregistration_sha256"] == INT16_PREREG_SHA256
    assert set(gate["probes"]) == {Q_PROJ_GRAPH, LM_HEAD_GRAPH}
    assert gate["candidate_output_observed"] is False
    assert gate["provider_context_generated"] is False
    assert gate["phone_execution_count"] == 0
    assert gate["source_revision"] == SOURCE_REVISION
    assert gate["parent_capsule_sha256"] == PARENT_CAPSULE_SHA256
    assert gate["frontier_selector_sha256"] == FRONTIER_SELECTOR_SHA256
    digest = sha256_bytes(path.read_bytes())
    assert path.with_suffix(".json.sha256").read_text(encoding="ascii") == (
        f"{digest}  context_gate.json\n"
    )


def test_variant_materialization_is_no_replace_and_rewrites_only_head_abi(
    tmp_path: Path,
):
    base = tmp_path / "base"
    base.mkdir()
    _write_base_package(base)
    context_gate = tmp_path / "context_gate.json"
    _build_gate(context_gate)

    output = tmp_path / "variant"
    result = materialize_int16_variant(
        base_package_dir=base,
        fp16_falsification_gate=FP16_GATE,
        int16_prereg_dir=INT16_PREREG,
        context_gate=context_gate,
        output_dir=output,
        source_revision=SOURCE_REVISION,
        parent_capsule_sha256=PARENT_CAPSULE_SHA256,
        frontier_selector_sha256=FRONTIER_SELECTOR_SHA256,
    )
    manifest = json.loads((output / "package_manifest.json").read_bytes())
    assert result["manifest_sha256"] == sha256_bytes(
        (output / "package_manifest.json").read_bytes()
    )
    assert manifest["variant_identity"]["source_revision"] == SOURCE_REVISION
    assert manifest["variant_identity"]["context_gate_sha256"] == sha256_bytes(
        context_gate.read_bytes()
    )
    assert manifest["lowering"]["lm_head"]["activation_abi"] == {
        "candidate_output_observed": False,
        "input_dtype": "QNN_DATATYPE_SFIXED_POINT_16",
        "input_scale": 1.0 / 512.0,
        "output_dtype": "QNN_DATATYPE_SFIXED_POINT_16",
        "output_scale": 1.0 / 256.0,
    }
    source = (output / "source/direct_qnn_probes.cpp").read_text()
    assert "lm_head_input_s16" in source
    assert "lm_head_input_f16" not in source
    assert (output / "source/packed_tensors.S").read_bytes() == (
        base / "source/packed_tensors.S"
    ).read_bytes()

    with pytest.raises(ProjectionGateError, match="output already exists"):
        materialize_int16_variant(
            base_package_dir=base,
            fp16_falsification_gate=FP16_GATE,
            int16_prereg_dir=INT16_PREREG,
            context_gate=context_gate,
            output_dir=output,
            source_revision=SOURCE_REVISION,
            parent_capsule_sha256=PARENT_CAPSULE_SHA256,
            frontier_selector_sha256=FRONTIER_SELECTOR_SHA256,
        )


def test_variant_rejects_self_authorized_or_noncanonical_context_gate(tmp_path: Path):
    base = tmp_path / "base"
    base.mkdir()
    _write_base_package(base)
    context_gate = tmp_path / "context_gate.json"
    gate = _build_gate(context_gate)
    gate["provider_context_generated"] = True
    context_gate.write_text(json.dumps(gate, indent=2), encoding="utf-8")
    digest = sha256_bytes(context_gate.read_bytes())
    context_gate.with_suffix(".json.sha256").write_text(
        f"{digest}  context_gate.json\n",
        encoding="ascii",
    )

    with pytest.raises(ProjectionGateError, match="not canonical"):
        materialize_int16_variant(
            base_package_dir=base,
            fp16_falsification_gate=FP16_GATE,
            int16_prereg_dir=INT16_PREREG,
            context_gate=context_gate,
            output_dir=tmp_path / "variant",
            source_revision=SOURCE_REVISION,
            parent_capsule_sha256=PARENT_CAPSULE_SHA256,
            frontier_selector_sha256=FRONTIER_SELECTOR_SHA256,
        )
